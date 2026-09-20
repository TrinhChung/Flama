"""Rehearse the P4-06 schema and codec contract on a disposable local MySQL DB."""

from __future__ import annotations

from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
from types import SimpleNamespace
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask_migrate import downgrade, stamp, upgrade
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.repositories.study_progress_shadow_repository import ensure_and_lock_subject
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    MAPPER_VERSION,
    PROJECTION_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import decode_raw_card_progress
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    build_contributor_evidence,
    map_card_progress,
)
from models import db
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.user import User


PROBE_NAME_PATTERN = re.compile(r"^flama_p4_shadow_probe_[a-z0-9_]+$")
SCHEMA_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def _connection_settings() -> dict[str, object]:
    password = os.getenv("DB_PASSWORD", "")
    user = os.getenv("DB_USER", "").strip()
    if not user:
        raise RuntimeError("DB_USER is required for the disposable MySQL probe.")
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1").strip() or "127.0.0.1",
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": user,
        "password": password,
        "charset": "utf8mb4",
        "autocommit": True,
    }


def _source_database_collation(admin: pymysql.connections.Connection) -> str:
    """Match the configured schema default without reading application rows."""

    source_database = os.getenv("DB_NAME", "").strip()
    if not SCHEMA_IDENTIFIER.fullmatch(source_database):
        raise RuntimeError("A safe DB_NAME is required for the disposable MySQL probe.")
    with admin.cursor() as cursor:
        cursor.execute(
            "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
            "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
            (source_database,),
        )
        row = cursor.fetchone()
    if row is None or row[0] != "utf8mb4" or not SCHEMA_IDENTIFIER.fullmatch(str(row[1])):
        raise RuntimeError("The configured schema must use a safe utf8mb4 collation.")
    return str(row[1])


def _database_uri(settings: dict[str, object], database_name: str) -> str:
    return (
        "mysql+pymysql://"
        f"{quote_plus(str(settings['user']))}:{quote_plus(str(settings['password']))}"
        f"@{settings['host']}:{settings['port']}/{database_name}?charset=utf8mb4"
    )


def _fixture() -> SimpleNamespace:
    now = datetime(2026, 9, 13, 12, 34, 56, 123456)
    return SimpleNamespace(
        id=1,
        user_id=1,
        card_id="probe-card",
        queue="review",
        step_index=0,
        due_at=now,
        due_day=739507,
        interval_days=5,
        interval_days_raw=5.75,
        is_suspended=False,
        is_buried=False,
        buried_until_day=None,
        review_kind="review",
        scheduler_mode="legacy",
        ease_factor=2.5,
        memory_stability=None,
        memory_difficulty=None,
        suspension_reason=None,
        last_leech_at=None,
        last_leech_lapses=0,
        last_review_event_id=None,
        reps=4,
        lapses=1,
        last_reviewed_at=now,
        revision=7,
        created_at=now,
        updated_at=now,
    )


def run_probe() -> dict[str, object]:
    load_dotenv()
    settings = _connection_settings()
    database_name = (
        f"flama_p4_shadow_probe_{os.getpid()}_{secrets.token_hex(4)}".lower()
    )
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Refusing unsafe disposable database name.")

    admin = pymysql.connect(**settings)
    try:
        source_collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 "
                f"COLLATE {source_collation}"
            )

        app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": _database_uri(settings, database_name),
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_RUN_DB_CREATE_ALL": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )
        migration = importlib.import_module(
            "migrations.versions.20260913_000039_add_study_progress_shadow_schema"
        )
        with app.app_context():
            # The repository's migration history starts after its original
            # baseline schema.  Reproduce the real pre-P4 shape explicitly,
            # excluding every new shadow table, then stamp the verified head.
            baseline_metadata = sa.MetaData()
            target_names = {table.name for table in migration.TARGET_TABLES}
            for table in db.metadata.sorted_tables:
                if table.name not in target_names:
                    table.to_metadata(baseline_metadata)
            baseline_metadata.create_all(bind=db.engine)
            with db.engine.connect() as connection:
                database_collation = connection.execute(
                    sa.text(
                        "SELECT DEFAULT_COLLATION_NAME "
                        "FROM information_schema.SCHEMATA "
                        "WHERE SCHEMA_NAME = DATABASE()"
                    )
                ).scalar_one()
            stamp(revision="20260913_000038", directory="migrations")
            upgrade(directory="migrations")
            inspector = sa.inspect(db.engine)
            issues = {
                table.name: migration._table_contract_issues(
                    inspector, table, db.engine.dialect
                )
                for table in migration.TARGET_TABLES
            }
            if any(issues.values()):
                raise AssertionError(f"MySQL schema contract mismatch: {issues!r}")

            with db.engine.connect() as connection:
                live_fk_collations = {
                    row.table_name: {
                        "parent": row.parent_collation,
                        "child": row.child_collation,
                    }
                    for row in connection.execute(
                        sa.text(
                            "SELECT 'study_progress_subjects.live_note_id' AS table_name, "
                            "parent.COLLATION_NAME AS parent_collation, "
                            "child.COLLATION_NAME AS child_collation "
                            "FROM information_schema.COLUMNS parent "
                            "JOIN information_schema.COLUMNS child "
                            "ON child.TABLE_SCHEMA = parent.TABLE_SCHEMA "
                            "WHERE parent.TABLE_SCHEMA = DATABASE() "
                            "AND parent.TABLE_NAME = 'notes' AND parent.COLUMN_NAME = 'id' "
                            "AND child.TABLE_NAME = 'study_progress_subjects' "
                            "AND child.COLUMN_NAME = 'live_note_id' "
                            "UNION ALL "
                            "SELECT 'study_progress_contributors.live_card_id', "
                            "parent.COLLATION_NAME, child.COLLATION_NAME "
                            "FROM information_schema.COLUMNS parent "
                            "JOIN information_schema.COLUMNS child "
                            "ON child.TABLE_SCHEMA = parent.TABLE_SCHEMA "
                            "WHERE parent.TABLE_SCHEMA = DATABASE() "
                            "AND parent.TABLE_NAME = 'cards' AND parent.COLUMN_NAME = 'id' "
                            "AND child.TABLE_NAME = 'study_progress_contributors' "
                            "AND child.COLUMN_NAME = 'live_card_id'"
                        )
                    )
                }
            if len(live_fk_collations) != 2 or any(
                value["parent"] != value["child"]
                for value in live_fk_collations.values()
            ):
                raise AssertionError(
                    "Live FK collations do not match their parents: "
                    f"{live_fk_collations!r}"
                )

            user = User(email="phase4-probe@example.test", username="phase4-probe")
            db.session.add(user)
            db.session.commit()

            now = datetime(2026, 9, 13, 12, 34, 56, 123456)
            first = ensure_and_lock_subject(
                db.session,
                learner_user_id=user.id,
                logical_note_key="probe-note",
                live_note_id=None,
                now_utc=now,
            )
            second = ensure_and_lock_subject(
                db.session,
                learner_user_id=user.id,
                logical_note_key="probe-note",
                live_note_id=None,
                now_utc=now,
            )
            if first.id != second.id:
                raise AssertionError("First-create subject identity is not stable.")
            try:
                with db.session.begin_nested():
                    db.session.add(
                        StudyProgressSubject(
                            learner_user_id=user.id,
                            logical_note_key=b"probe-note",
                            created_at=now,
                            updated_at=now,
                        )
                    )
                    db.session.flush()
            except sa.exc.IntegrityError:
                pass
            else:
                raise AssertionError("Duplicate learner/Note subject key was accepted.")
            if db.session.get(StudyProgressSubject, first.id) is None:
                raise AssertionError("Duplicate-key savepoint erased the existing subject.")

            source = _fixture()
            source.user_id = user.id
            mapped = map_card_progress(source, card_created_at=now)
            if not isinstance(mapped, MappedCardProgress):
                raise AssertionError(f"Probe fixture did not map: {mapped!r}")
            evidence = build_contributor_evidence(
                mapped,
                source,
                subject_generation=1,
                pointer_status="ABSENT",
                history_completeness_code="HISTORY_SNAPSHOT_ONLY",
                current_provenance_code="UNKNOWN_LEGACY",
                lineage_vector_hash=b"l" * 32,
            )

            first.status_code = "MIRRORED_SINGLE"
            first.mirror_revision = 1
            first.contributor_count = 1
            first.authority_vector_hash = mapped.semantic_state_hash
            first.lineage_vector_hash = b"l" * 32
            first.mapper_version = MAPPER_VERSION
            first.last_mirrored_at = now
            first.updated_at = now
            db.session.add(
                StudyProgressState(
                    subject_id=first.id,
                    subject_generation=1,
                    mirror_revision=1,
                    algorithm_key=ALGORITHM_KEY,
                    algorithm_version=ALGORITHM_VERSION,
                    state_schema_version=STATE_SCHEMA_VERSION,
                    storage_codec=STORAGE_CODEC,
                    state_payload=mapped.state.payload,
                    state_payload_size=mapped.state.size,
                    algorithm_state_hash=mapped.algorithm_state_hash,
                    semantic_state_hash=mapped.semantic_state_hash,
                    created_at=now,
                    updated_at=now,
                )
            )
            contributor = StudyProgressContributor(
                subject_id=first.id,
                subject_generation=1,
                source_progress_id=evidence.source_progress_id,
                # The probe has no authoritative CardProgress parent row, so
                # only the immutable identity is populated here.
                live_card_progress_id=None,
                logical_card_key=evidence.logical_card_key,
                live_card_id=None,
                card_progress_revision=evidence.card_progress_revision,
                raw_schema_version=evidence.raw_schema_version,
                storage_codec=evidence.storage_codec,
                raw_payload=evidence.raw.payload,
                raw_payload_size=evidence.raw.size,
                raw_progress_hash=evidence.raw.digest,
                pointer_status=evidence.pointer_status,
                history_completeness_code=evidence.history_completeness_code,
                current_provenance_code=evidence.current_provenance_code,
                lineage_vector_hash=evidence.lineage_vector_hash,
                contributor_status=evidence.contributor_status,
                created_at=now,
                updated_at=now,
            )
            db.session.add(contributor)
            db.session.flush()
            db.session.add(
                StudyProgressAvailability(
                    contributor_id=contributor.id,
                    subject_id=first.id,
                    subject_generation=1,
                    projection_version=PROJECTION_VERSION,
                    normalized_queue=mapped.availability.normalized_queue,
                    due_at=mapped.availability.due_at,
                    due_day=mapped.availability.due_day,
                    is_suspended=mapped.availability.is_suspended,
                    is_buried=mapped.availability.is_buried,
                    buried_until_day=mapped.availability.buried_until_day,
                    card_created_at=now,
                    card_order_key=mapped.availability.card_order_key,
                    state_schema_version=STATE_SCHEMA_VERSION,
                    semantic_state_hash=mapped.semantic_state_hash,
                    created_at=now,
                    updated_at=now,
                )
            )
            db.session.commit()

            loaded = db.session.get(StudyProgressContributor, contributor.id)
            decoded = decode_raw_card_progress(
                loaded.raw_payload,
                expected_size=loaded.raw_payload_size,
                expected_hash=loaded.raw_progress_hash,
            )
            if decoded["interval_days_raw"] != 5.75:
                raise AssertionError("MySQL JSON/raw codec round-trip changed a float.")
            stored_due = db.session.get(
                StudyProgressAvailability, contributor.id
            ).due_at
            if stored_due != now:
                raise AssertionError(
                    f"MySQL DATETIME(6) round-trip changed {now!r} to {stored_due!r}."
                )

            db.session.delete(user)
            db.session.commit()
            row_counts = {
                table.name: int(
                    db.session.execute(
                        sa.select(sa.func.count()).select_from(table)
                    ).scalar_one()
                )
                for table in migration.TARGET_TABLES
            }
            if any(row_counts.values()):
                raise AssertionError(f"Probe cleanup left shadow rows: {row_counts!r}")

            # The SELECT accounting above opens a new ORM transaction.  Close
            # it before Alembic takes metadata locks for the guarded drops.
            db.session.rollback()
            db.session.remove()
            downgrade(revision="20260913_000038", directory="migrations")
            after_downgrade = set(sa.inspect(db.engine).get_table_names())
            if any(table.name in after_downgrade for table in migration.TARGET_TABLES):
                raise AssertionError("Empty-only downgrade left a target table behind.")
            # Reproduce the historical development/CI startup path where
            # create_all pre-creates current model tables before Alembic records
            # revision 39.
            db.create_all()
            upgrade(directory="migrations")
            final_counts = {
                table.name: int(
                    db.session.execute(
                        sa.select(sa.func.count()).select_from(table)
                    ).scalar_one()
                )
                for table in migration.TARGET_TABLES
            }
            return {
                "database_head": "20260913_000039",
                "database_name": database_name,
                "database_collation": database_collation,
                "live_fk_collations": live_fk_collations,
                "schema_contract_issues": issues,
                "first_create_subject_id_stable": True,
                "duplicate_subject_unique_savepoint_verified": True,
                "raw_codec_round_trip": True,
                "datetime_microseconds_round_trip": True,
                "empty_only_downgrade_rehearsed": True,
                "startup_create_all_contract_revalidated": True,
                "final_shadow_row_counts": final_counts,
            }
    finally:
        try:
            db.session.remove()
        except Exception:
            pass
        with admin.cursor() as cursor:
            if not PROBE_NAME_PATTERN.fullmatch(database_name):
                raise RuntimeError("Refusing unsafe disposable database cleanup.")
            cursor.execute(f"DROP DATABASE `{database_name}`")
        admin.close()


def main() -> int:
    print(json.dumps(run_probe(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
