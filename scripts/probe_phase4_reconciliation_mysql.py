"""Rehearse P4-10/P4-11 on disposable MySQL with a SELECT-only audit user.

The probe creates and drops only its uniquely named database and principal.
With --schema-snapshot-baseline it reads schema DDL and Alembic head from the
configured source database, but copies no application rows into the probe.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
import hashlib
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import time
from urllib.parse import quote_plus

from dotenv import load_dotenv
from flask_migrate import downgrade, stamp, upgrade
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app, create_audit_app
from app.services.study_architecture_audit_service import build_study_architecture_audit
from app.services.study_phase4_preflight_service import collect_connection_safety
from app.services.study_progress_backfill_service import run_current_progress_backfill
from app.services.study_progress_reconciliation_service import (
    build_study_progress_reconciliation,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from scripts.probe_phase4_resumable_backfill_mysql import _seed_fixture
from scripts.probe_phase4_shadow_schema_mysql import (
    PROBE_NAME_PATTERN,
    _connection_settings,
    _database_uri,
)


SCHEMA_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def _restore_configured_prephase4_schema(
    admin: pymysql.connections.Connection,
    settings: dict[str, object],
    target_database: str,
) -> tuple[int, int, str]:
    """Replay core SHOW CREATE TABLE as head 38; omit existing shadow tables."""

    source_database = os.getenv("DB_NAME", "").strip()
    if (
        not SCHEMA_IDENTIFIER.fullmatch(source_database)
        or source_database == target_database
    ):
        raise RuntimeError("A distinct, safe DB_NAME is required for schema restore.")
    source = pymysql.connect(**settings, database=source_database)
    try:
        with source.cursor() as cursor:
            cursor.execute("SET SESSION transaction_read_only = ON")
            cursor.execute("SELECT version_num FROM alembic_version")
            heads = tuple(row[0] for row in cursor.fetchall())
            if heads not in {("20260913_000038",), ("20260913_000039",)}:
                raise RuntimeError("Schema source must be at head 38 or 39.")
            cursor.execute("SHOW FULL TABLES")
            all_tables = sorted(
                str(row[0]) for row in cursor.fetchall() if str(row[1]).upper() == "BASE TABLE"
            )
            migration = importlib.import_module(
                "migrations.versions.20260913_000039_add_study_progress_shadow_schema"
            )
            shadow_names = {table.name for table in migration.TARGET_TABLES}
            tables = [table for table in all_tables if table not in shadow_names]
            excluded_shadow_count = len(all_tables) - len(tables)
            if heads[0] == "20260913_000039" and excluded_shadow_count != len(shadow_names):
                raise RuntimeError("Head 39 source is missing expected shadow tables.")
            if "alembic_version" not in tables:
                raise RuntimeError("Schema source lacks alembic_version.")
            statements = []
            for table in tables:
                if not SCHEMA_IDENTIFIER.fullmatch(table):
                    raise RuntimeError("Refusing unsafe schema table identifier.")
                cursor.execute(f"SHOW CREATE TABLE `{table}`")
                statements.append(str(cursor.fetchone()[1]))
        with admin.cursor() as cursor:
            cursor.execute(f"USE `{target_database}`")
            cursor.execute("SET FOREIGN_KEY_CHECKS=0")
            try:
                for statement in statements:
                    cursor.execute(statement)
            finally:
                cursor.execute("SET FOREIGN_KEY_CHECKS=1")
            cursor.execute(
                "INSERT INTO alembic_version (version_num) VALUES (%s)",
                ("20260913_000038",),
            )
        return len(tables), excluded_shadow_count, str(heads[0])
    finally:
        source.close()


def _reader_uri(settings: dict[str, object], database_name: str, user: str, password: str) -> str:
    return (
        "mysql+pymysql://"
        f"{quote_plus(user)}:{quote_plus(password)}"
        f"@{settings['host']}:{settings['port']}/{database_name}?charset=utf8mb4"
    )


def _database_content_checksum(
    admin: pymysql.connections.Connection, database_name: str, tables: list[str]
) -> str:
    inventory: list[tuple[str, int, int]] = []
    with admin.cursor() as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM `{database_name}`.`{table}`")
            count = int(cursor.fetchone()[0])
            cursor.execute(f"CHECKSUM TABLE `{database_name}`.`{table}`")
            checksum = cursor.fetchone()[1]
            if checksum is None:
                raise AssertionError(f"MySQL did not checksum disposable table {table}.")
            inventory.append((table, count, int(checksum)))
    return hashlib.sha256(
        json.dumps(inventory, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _restore_synthetic_snapshot(
    admin: pymysql.connections.Connection,
    *,
    source_database: str,
    restored_database: str,
) -> dict[str, object]:
    started = time.perf_counter()
    with admin.cursor() as cursor:
        cursor.execute(f"USE `{source_database}`")
        cursor.execute("SHOW FULL TABLES")
        tables = sorted(
            str(row[0]) for row in cursor.fetchall() if str(row[1]).upper() == "BASE TABLE"
        )
        statements = []
        for table in tables:
            if not SCHEMA_IDENTIFIER.fullmatch(table):
                raise RuntimeError("Refusing unsafe disposable table identifier.")
            cursor.execute(f"SHOW CREATE TABLE `{table}`")
            statements.append(str(cursor.fetchone()[1]))
        cursor.execute(f"USE `{restored_database}`")
        cursor.execute("SET FOREIGN_KEY_CHECKS=0")
        try:
            for statement in statements:
                cursor.execute(statement)
            for table in tables:
                cursor.execute(
                    f"INSERT INTO `{restored_database}`.`{table}` "
                    f"SELECT * FROM `{source_database}`.`{table}`"
                )
        finally:
            cursor.execute("SET FOREIGN_KEY_CHECKS=1")
    source_digest = _database_content_checksum(admin, source_database, tables)
    restored_digest = _database_content_checksum(admin, restored_database, tables)
    if source_digest != restored_digest:
        raise AssertionError("Synthetic backup/restore table content checksum differs.")
    return {
        "table_count": len(tables),
        "checksum_sha256": source_digest,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }


def _flags_off_restart(database_name: str, *, expected_progress: int,
                       expected_subjects: int, expected_runs: int) -> bool:
    subprocess_env = {
        **os.environ,
        "DB_NAME": database_name,
        "STARTUP_RUN_MAINTENANCE": "1",
        "STARTUP_RUN_DB_CREATE_ALL": "0",
        "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": "0",
        "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED": "0",
        "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED": "0",
        "REDIS_URL": "",
    }
    script = (
        "import json, wsgi; "
        "from models.card_progress import CardProgress; "
        "from models.study_progress_subject import StudyProgressSubject; "
        "from models.study_progress_backfill_run import StudyProgressBackfillRun; "
        "ctx=wsgi.app.app_context(); ctx.push(); "
        "print(json.dumps({'progress':CardProgress.query.count(), "
        "'subjects':StudyProgressSubject.query.count(), "
        "'runs':StudyProgressBackfillRun.query.count(), "
        "'write_enabled':wsgi.app.config['STUDY_PROGRESS_SHADOW_WRITE_ENABLED'], "
        "'compare_enabled':wsgi.app.config['STUDY_PROGRESS_SHADOW_COMPARE_ENABLED']}))"
    )
    restarted = subprocess.run(
        [sys.executable, "-c", script],
        cwd=ROOT_DIR,
        env=subprocess_env,
        capture_output=True,
        text=True,
        timeout=60,
        check=False,
    )
    if restarted.returncode != 0:
        raise AssertionError(
            "Flags-off wsgi.py restart failed; stderr tail: " + restarted.stderr[-500:]
        )
    startup_state = json.loads(restarted.stdout.strip().splitlines()[-1])
    expected = {
        "progress": expected_progress,
        "subjects": expected_subjects,
        "runs": expected_runs,
        "write_enabled": False,
        "compare_enabled": False,
    }
    if startup_state != expected:
        raise AssertionError(f"Flags-off restart changed progress/shadow state: {startup_state}")
    return True


def _shadow_index_plans(session: sa.orm.Session) -> dict[str, dict[str, object]]:
    subject = session.execute(sa.text(
        "SELECT id, learner_user_id, logical_note_key, subject_generation "
        "FROM study_progress_subjects ORDER BY id LIMIT 1"
    )).one()
    run_id = session.execute(sa.text(
        "SELECT id FROM study_progress_backfill_runs ORDER BY started_at DESC LIMIT 1"
    )).scalar_one()
    statements = {
        "subject_lookup": (
            "SELECT id FROM study_progress_subjects "
            "WHERE learner_user_id=:learner AND logical_note_key=:note_key LIMIT 1",
            {"learner": subject.learner_user_id, "note_key": subject.logical_note_key},
        ),
        "current_contributors": (
            "SELECT id FROM study_progress_contributors "
            "WHERE subject_id=:subject_id AND subject_generation=:generation "
            "AND contributor_status='ACTIVE' ORDER BY id LIMIT 100",
            {"subject_id": subject.id, "generation": subject.subject_generation},
        ),
        "disposition_resume": (
            "SELECT id FROM study_progress_backfill_dispositions "
            "WHERE run_id=:run_id AND source_kind='CARD_PROGRESS' "
            "AND disposition_code='RETRY_PENDING'",
            {"run_id": run_id},
        ),
    }

    def table_nodes(value: object) -> list[dict[str, object]]:
        if isinstance(value, dict):
            found = [value] if "table_name" in value else []
            for child in value.values():
                found.extend(table_nodes(child))
            return found
        if isinstance(value, list):
            return [node for child in value for node in table_nodes(child)]
        return []

    results: dict[str, dict[str, object]] = {}
    for name, (query, params) in statements.items():
        raw_json = session.execute(sa.text("EXPLAIN FORMAT=JSON " + query), params).scalar_one()
        nodes = table_nodes(json.loads(raw_json))
        if len(nodes) != 1:
            raise AssertionError(f"Unexpected EXPLAIN table topology for {name}.")
        node = nodes[0]
        started = time.perf_counter()
        analyze_tree = str(session.execute(
            sa.text("EXPLAIN ANALYZE " + query), params
        ).scalar_one())
        results[name] = {
            "access_type": str(node.get("access_type", "")),
            "key": str(node.get("key", "")),
            "estimated_rows_per_scan": int(node.get("rows_examined_per_scan", 0)),
            "explain_analyze_seconds": round(time.perf_counter() - started, 4),
            "analyze_plan_sha256": hashlib.sha256(analyze_tree.encode()).hexdigest(),
        }
    return results


def _seed_extra_progress(*, user_id: int, deck_id: int, row_count: int) -> None:
    note_type = NoteType.query.filter_by(user_id=user_id).one()
    template = Template.query.filter_by(note_type_id=note_type.id, is_default=True).one()
    fixed_now = datetime(2026, 9, 14, 12, 0, 0)
    notes = [
        Note(
            user_id=user_id,
            note_type_id=note_type.id,
            deck_id=deck_id,
            field_values={"Word": f"reconciliation-{index}"},
            created_at=fixed_now - timedelta(days=1),
        )
        for index in range(row_count)
    ]
    db.session.add_all(notes)
    db.session.flush()
    cards = [
        Card(
            note_id=note.id,
            template_id=template.id,
            created_at=fixed_now - timedelta(days=1),
        )
        for note in notes
    ]
    db.session.add_all(cards)
    db.session.flush()
    rows = []
    for index, card in enumerate(cards):
        if row_count == 16422:
            # P4-01 production snapshot: 432/1596/224/14172, including the
            # fixture's two review rows. This remains synthetic, not a copy.
            queue = (
                "new" if index < 432 else
                "learning" if index < 2028 else
                "relearning" if index < 2252 else
                "review"
            )
        else:
            queue = ("new", "learning", "relearning", "review")[index % 4]
        rows.append(
            CardProgress(
                user_id=user_id,
                card_id=card.id,
                queue=queue,
                step_index=0,
                due_at=(
                    fixed_now + timedelta(minutes=10 + index % 7)
                    if queue in {"learning", "relearning"}
                    else None
                ),
                due_day=22000 if queue == "review" else None,
                interval_days=3,
                interval_days_raw=3.0,
                is_suspended=False,
                is_buried=False,
                review_kind="review",
                scheduler_mode="legacy",
                ease_factor=2.5,
                reps=2,
                lapses=0,
                last_leech_lapses=0,
                revision=0,
                created_at=fixed_now - timedelta(days=1),
                updated_at=fixed_now - timedelta(days=1),
            )
        )
    db.session.add_all(rows)
    db.session.commit()


def run_probe(
    *,
    extra_rows: int = 300,
    schema_snapshot_baseline: bool = False,
    rollout_rehearsal: bool = False,
) -> dict[str, object]:
    if not 1 <= extra_rows <= 16422:
        raise ValueError("extra_rows must be between 1 and 16422")
    if rollout_rehearsal and not schema_snapshot_baseline:
        raise ValueError("Rollout rehearsal requires --schema-snapshot-baseline")
    load_dotenv()
    settings = _connection_settings()
    suffix = secrets.token_hex(4)
    database_name = f"flama_p4_shadow_probe_reconciliation_{os.getpid()}_{suffix}"
    reader_user = f"p4audit_{suffix}"
    reader_password = secrets.token_urlsafe(24)
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Refusing unsafe disposable database name.")
    if not reader_user.replace("_", "").isalnum():
        raise RuntimeError("Refusing unsafe disposable principal name.")

    admin = pymysql.connect(**settings)
    writer_app = None
    audit_app = None
    database_created = False
    reader_created = False
    restored_database_name = f"flama_p4_shadow_probe_restore_{os.getpid()}_{suffix}"
    restored_database_created = False
    backup_restore_evidence: dict[str, object] | None = None
    restored_table_count = 0
    excluded_preexisting_shadow_tables = 0
    schema_source_head: str | None = None
    database_collation = ""
    roundtrip_verified = False
    flags_off_wakeup_verified = False
    flags_off_rollback_verified = False
    migration_seconds = 0.0
    backfill_seconds = 0.0
    audit_seconds = 0.0
    mysql_environment: dict[str, str] = {}
    index_plans: dict[str, dict[str, object]] = {}
    try:
        with admin.cursor() as cursor:
            source_database = os.getenv("DB_NAME", "").strip()
            if schema_snapshot_baseline:
                if not SCHEMA_IDENTIFIER.fullmatch(source_database):
                    raise RuntimeError("A safe DB_NAME is required for schema restore.")
                cursor.execute(
                    "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
                    "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
                    (source_database,),
                )
                source_collation = cursor.fetchone()
                if source_collation is None or source_collation[0] != "utf8mb4":
                    raise RuntimeError("Schema source must use utf8mb4.")
                database_collation = str(source_collation[1])
            else:
                cursor.execute("SELECT @@collation_server")
                database_collation = str(cursor.fetchone()[0])
            if not SCHEMA_IDENTIFIER.fullmatch(database_collation):
                raise RuntimeError("Refusing unsafe source database collation.")
            cursor.execute(
                f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 "
                f"COLLATE {database_collation}"
            )
            cursor.execute(
                "SELECT VERSION(), @@sql_mode, @@time_zone, "
                "@@character_set_server, @@collation_server"
            )
            values = cursor.fetchone()
            mysql_environment = dict(zip(
                ("version", "sql_mode", "time_zone", "character_set", "collation"),
                (str(value) for value in values),
            ))
        database_created = True
        if schema_snapshot_baseline:
            (
                restored_table_count,
                excluded_preexisting_shadow_tables,
                schema_source_head,
            ) = _restore_configured_prephase4_schema(
                admin, settings, database_name
            )
        writer_app = create_app(
            {
                "SQLALCHEMY_DATABASE_URI": _database_uri(settings, database_name),
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_RUN_DB_CREATE_ALL": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
                "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": True,
                "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED": True,
                "REDIS_URL": "",
            }
        )
        migration = importlib.import_module(
            "migrations.versions.20260913_000039_add_study_progress_shadow_schema"
        )
        with writer_app.app_context():
            if not schema_snapshot_baseline:
                baseline = sa.MetaData()
                shadow_names = {table.name for table in migration.TARGET_TABLES}
                for table in db.metadata.sorted_tables:
                    if table.name not in shadow_names:
                        table.to_metadata(baseline)
                baseline.create_all(bind=db.engine)
                stamp(revision="20260913_000038", directory="migrations")
            elif sa.inspect(db.engine).has_table("study_progress_subjects"):
                raise AssertionError("Pre-Phase4 schema restore already contains shadow tables.")
            migration_started = time.perf_counter()
            upgrade(directory="migrations")
            if rollout_rehearsal:
                downgrade(revision="20260913_000038", directory="migrations")
                if sa.inspect(db.engine).has_table("study_progress_subjects"):
                    raise AssertionError("Disposable downgrade left shadow subject table.")
                upgrade(directory="migrations")
                if not sa.inspect(db.engine).has_table("study_progress_subjects"):
                    raise AssertionError("Disposable re-upgrade lacks shadow subject table.")
                roundtrip_verified = True
            migration_seconds = time.perf_counter() - migration_started
            fixture = _seed_fixture()
            _seed_extra_progress(
                user_id=int(fixture["user_id"]),
                deck_id=int(fixture["deck_id"]),
                row_count=extra_rows,
            )
            if rollout_rehearsal:
                if not PROBE_NAME_PATTERN.fullmatch(restored_database_name):
                    raise RuntimeError("Refusing unsafe restored database name.")
                with admin.cursor() as cursor:
                    cursor.execute(
                        f"CREATE DATABASE `{restored_database_name}` CHARACTER SET utf8mb4 "
                        f"COLLATE {database_collation}"
                    )
                restored_database_created = True
                backup_restore_evidence = _restore_synthetic_snapshot(
                    admin,
                    source_database=database_name,
                    restored_database=restored_database_name,
                )
            if rollout_rehearsal:
                db.session.remove()
                flags_off_wakeup_verified = _flags_off_restart(
                    database_name,
                    expected_progress=extra_rows + 2,
                    expected_subjects=0,
                    expected_runs=0,
                )
            backfill_started = time.perf_counter()
            backfill = run_current_progress_backfill(db.session, apply=True)
            backfill_seconds = time.perf_counter() - backfill_started
            if not backfill.complete or backfill.source_count != extra_rows + 2:
                raise AssertionError("Disposable MySQL backfill did not account for all sources.")
            index_plans = _shadow_index_plans(db.session)
            if extra_rows >= 1000 and any(
                plan["access_type"] == "ALL" or not plan["key"]
                for plan in index_plans.values()
            ):
                raise AssertionError("Representative shadow lookup used an unindexed table scan.")
            db.session.remove()
            db.engine.dispose()
            if rollout_rehearsal:
                flags_off_rollback_verified = _flags_off_restart(
                    database_name,
                    expected_progress=extra_rows + 2,
                    expected_subjects=extra_rows + 2,
                    expected_runs=1,
                )

        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE USER '{reader_user}'@'localhost' "
                "IDENTIFIED WITH mysql_native_password BY %s",
                (reader_password,),
            )
            reader_created = True
            cursor.execute(
                f"GRANT SELECT ON `{database_name}`.* TO '{reader_user}'@'localhost'"
            )

        audit_app = create_audit_app(
            {
                "SQLALCHEMY_DATABASE_URI": _reader_uri(
                    settings, database_name, reader_user, reader_password
                ),
                "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED": True,
                "REDIS_URL": "",
            }
        )
        with audit_app.app_context():
            connection = collect_connection_safety()
            if not connection["select_only_verified"]:
                raise AssertionError("Audit connection is not SELECT-only.")
            isolation = str(
                db.session.execute(sa.text("SELECT @@transaction_isolation")).scalar()
            ).upper()
            if isolation != "REPEATABLE-READ":
                raise AssertionError(f"Expected REPEATABLE-READ, got {isolation}.")
            fixed_now = datetime(2026, 9, 14, 12, 0, 0)
            audit_started = time.perf_counter()
            first = build_study_progress_reconciliation(db.session, observed_at=fixed_now)
            second = build_study_progress_reconciliation(db.session, observed_at=fixed_now)
            audit_seconds = time.perf_counter() - audit_started
            if first != second or first["gate"]["status"] != "PASS":
                raise AssertionError(
                    "MySQL reconciliation was not deterministic and clean: "
                    + json.dumps(first["unexplained"]["by_code"], sort_keys=True)
                )
            if first["accounting"]["source_rows"] != extra_rows + 2:
                raise AssertionError("Audit source count differs from backfill source count.")
            if db.session.new or db.session.dirty or db.session.deleted:
                raise AssertionError("Read-only audit session acquired pending writes.")
            full_audit = build_study_architecture_audit(now=fixed_now)
            if full_audit["shadow_reconciliation"]["gate"]["status"] != "PASS":
                raise AssertionError("Full read-only audit did not embed a clean reconciliation.")
            result = {
                "disposable_database_removed": True,
                "select_only_principal_removed": True,
                "select_only_verified": True,
                "snapshot_isolation": isolation,
                "schema_snapshot_baseline": schema_snapshot_baseline,
                "schema_source_head": schema_source_head,
                "database_collation": database_collation,
                "restored_prephase4_tables": restored_table_count,
                "excluded_preexisting_shadow_tables": excluded_preexisting_shadow_tables,
                "migration_roundtrip_verified": roundtrip_verified,
                "flags_off_wsgi_restart_verified": flags_off_wakeup_verified,
                "flags_off_runtime_rollback_verified": flags_off_rollback_verified,
                "mysql_environment": mysql_environment,
                "migration_roundtrip_seconds": round(migration_seconds, 3),
                "backfill_seconds": round(backfill_seconds, 3),
                "backfill_batches": backfill.batches,
                "backfill_rows_per_second": round((extra_rows + 2) / max(backfill_seconds, 0.001), 2),
                "two_reconciliation_runs_seconds": round(audit_seconds, 3),
                "full_audit_reconciliation_verified": True,
                "index_plans": index_plans,
                "backup_restore": backup_restore_evidence,
                "source_rows": first["accounting"]["source_rows"],
                "query_scopes": first["query_parity"]["scope_count"],
                "zero_unexplained": first["accounting"]["zero_unexplained"],
                "two_runs_identical": True,
                "checksum_sha256": first["checksum_sha256"],
            }
            db.session.remove()
            db.engine.dispose()
            return result
    finally:
        for app in (audit_app, writer_app):
            if app is not None:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
        with admin.cursor() as cursor:
            if reader_created:
                cursor.execute(f"DROP USER '{reader_user}'@'localhost'")
            if restored_database_created:
                cursor.execute(f"DROP DATABASE `{restored_database_name}`")
            if database_created:
                cursor.execute(f"DROP DATABASE `{database_name}`")
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--extra-rows", type=int, default=300)
    parser.add_argument("--schema-snapshot-baseline", action="store_true")
    parser.add_argument("--rollout-rehearsal", action="store_true")
    args = parser.parse_args()
    print(
        json.dumps(
            run_probe(
                extra_rows=args.extra_rows,
                schema_snapshot_baseline=args.schema_snapshot_baseline,
                rollout_rehearsal=args.rollout_rehearsal,
            ),
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
