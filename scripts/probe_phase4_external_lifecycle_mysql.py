"""Exercise P4-08 external/lifecycle transactions on disposable local MySQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timedelta, timezone
import importlib
import json
import os
from pathlib import Path
import secrets
import sys
from threading import Barrier, Lock
from unittest.mock import patch

from dotenv import load_dotenv
from flask_migrate import stamp, upgrade
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services import (
    anki_sync_service,
    deck_management_service,
    flashcard_content_service,
    study_service,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_import_session import ConnectImportSession
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from scripts.probe_phase4_shadow_schema_mysql import (
    PROBE_NAME_PATTERN,
    _connection_settings,
    _database_uri,
    _source_database_collation,
)


def _seed_fixture() -> dict[str, object]:
    user = User(
        username="p4-external-probe",
        email="p4-external-probe@example.test",
        timezone="Asia/Tokyo",
    )
    user.set_password("password")
    db.session.add(user)
    db.session.flush()
    deck = Deck(name="P4 external probe", owner_user_id=user.id)
    note_type = NoteType(name="P4 external type", user_id=user.id)
    db.session.add_all((deck, note_type))
    db.session.flush()
    field = FieldDef(
        note_type_id=note_type.id,
        name="Word",
        field_type="text",
        position=0,
        required=True,
    )
    template = Template(
        name="Probe template",
        note_type_id=note_type.id,
        position=0,
        is_default=True,
        front_html="{{Word}}",
        back_html="{{Word}}",
    )
    db.session.add_all((field, template))
    db.session.flush()

    external_note = Note(
        user_id=user.id,
        note_type_id=note_type.id,
        deck_id=deck.id,
        field_values={"Word": "external-stable"},
    )
    delete_note = Note(
        user_id=user.id,
        note_type_id=note_type.id,
        deck_id=deck.id,
        field_values={"Word": "delete-me"},
    )
    reset_note = Note(
        user_id=user.id,
        note_type_id=note_type.id,
        deck_id=deck.id,
        field_values={"Word": "reset-me"},
    )
    db.session.add_all((external_note, delete_note, reset_note))
    db.session.flush()
    external_card = Card(note_id=external_note.id, template_id=template.id)
    delete_card = Card(note_id=delete_note.id, template_id=template.id)
    reset_card = Card(note_id=reset_note.id, template_id=template.id)
    db.session.add_all((external_card, delete_card, reset_card))
    db.session.flush()

    import_session = ConnectImportSession(
        user_id=user.id,
        source="anki",
        source_key="p4-external-probe-source",
        mode="strict",
        status="importing",
        expires_at=datetime.now(timezone.utc).replace(tzinfo=None)
        + timedelta(hours=1),
    )
    db.session.add(import_session)
    db.session.flush()
    source_note = ConnectSourceNoteRef(
        user_id=user.id,
        source_key=import_session.source_key,
        external_note_id="1001",
        source_model_id="probe-model",
        source_deck_path="Probe",
        note_id=external_note.id,
        content_hash="1" * 64,
        last_session_id=import_session.id,
    )
    source_card = ConnectSourceCardRef(
        user_id=user.id,
        source_key=import_session.source_key,
        external_card_id="2001",
        external_note_id="1001",
        source_ord=0,
        card_id=external_card.id,
        last_session_id=import_session.id,
    )
    db.session.add_all((source_note, source_card))
    db.session.commit()
    return {
        "user_id": int(user.id),
        "deck_id": int(deck.id),
        "external_note_id": str(external_note.id),
        "external_card_id": str(external_card.id),
        "delete_note_id": str(delete_note.id),
        "delete_card_id": str(delete_card.id),
        "reset_note_id": str(reset_note.id),
        "reset_card_id": str(reset_card.id),
        "session_id": str(import_session.id),
    }


def _snapshot(*, digest: str, base: str | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "externalNoteId": "1001",
        "sourceCardId": "2001",
        "ord": 0,
        "snapshotHash": digest * 64,
        "type": 2,
        "queue": 2,
        "due": 50003,
        "sourceToday": 50000,
        "interval": 14 if digest == "a" else 20,
        "factor": 2500,
        "reps": 2,
        "lapses": 1,
        "left": 0,
    }
    if base is not None:
        payload["baseSnapshotHash"] = base * 64
    return payload


def run_probe() -> dict[str, object]:
    load_dotenv()
    settings = _connection_settings()
    database_name = (
        f"flama_p4_shadow_probe_external_{os.getpid()}_{secrets.token_hex(4)}".lower()
    )
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Refusing unsafe disposable database name.")

    admin = pymysql.connect(**settings)
    app = None
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
                "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": True,
                "REDIS_URL": "",
            }
        )
        migration = importlib.import_module(
            "migrations.versions.20260913_000039_add_study_progress_shadow_schema"
        )
        with app.app_context():
            baseline = sa.MetaData()
            target_names = {table.name for table in migration.TARGET_TABLES}
            for table in db.metadata.sorted_tables:
                if table.name not in target_names:
                    table.to_metadata(baseline)
            baseline.create_all(bind=db.engine)
            stamp(revision="20260913_000038", directory="migrations")
            upgrade(directory="migrations")
            fixture = _seed_fixture()

            session = db.session.get(ConnectImportSession, fixture["session_id"])
            applied = anki_sync_service.import_progress(
                int(fixture["user_id"]), session, [_snapshot(digest="a")]
            )
            if applied[0]["state"] != "applied":
                raise AssertionError(f"Initial external snapshot failed: {applied!r}")
            db.session.commit()

            progress = CardProgress.query.filter_by(
                user_id=fixture["user_id"], card_id=fixture["external_card_id"]
            ).one()
            before_fault = (
                int(progress.revision),
                int(progress.interval_days),
                ConnectSourceCardRef.query.filter_by(external_card_id="2001").one().snapshot_hash,
                StudyProgressSubject.query.filter_by(
                    logical_note_key=str(fixture["external_note_id"]).encode("utf-8")
                ).one().mirror_revision,
            )
            with patch(
                "app.services.study_progress_shadow_mirror_service.finalize_external_progress_mirror",
                side_effect=RuntimeError("p4 external probe fault"),
            ):
                failed = anki_sync_service.import_progress(
                    int(fixture["user_id"]),
                    session,
                    [_snapshot(digest="c", base="a")],
                )
            db.session.commit()
            if failed[0]["state"] != "failed":
                raise AssertionError("External mirror fault escaped savepoint handling.")
            progress = CardProgress.query.filter_by(
                user_id=fixture["user_id"], card_id=fixture["external_card_id"]
            ).one()
            after_fault = (
                int(progress.revision),
                int(progress.interval_days),
                ConnectSourceCardRef.query.filter_by(external_card_id="2001").one().snapshot_hash,
                StudyProgressSubject.query.filter_by(
                    logical_note_key=str(fixture["external_note_id"]).encode("utf-8")
                ).one().mirror_revision,
            )
            if after_fault != before_fault:
                raise AssertionError("External mirror fault leaked authoritative state.")

            pointer_before_revlog = progress.last_review_event_id
            revision_before_revlog = int(progress.revision)
            reviewed_ms = int(
                datetime(2026, 9, 14, 1, tzinfo=timezone.utc).timestamp() * 1000
            )
            revlog = anki_sync_service.import_reviews(
                int(fixture["user_id"]),
                session,
                [
                    {
                        "sourceReviewId": reviewed_ms,
                        "sourceCardId": "2001",
                        "ease": 3,
                        "type": 1,
                        "ivl": 14,
                        "lastIvl": 10,
                        "factor": 2500,
                        "time": 1200,
                    }
                ],
            )
            db.session.commit()
            if revlog[0]["state"] != "imported":
                raise AssertionError(f"Revlog import failed: {revlog!r}")
            progress = CardProgress.query.filter_by(
                user_id=fixture["user_id"], card_id=fixture["external_card_id"]
            ).one()
            contributor = StudyProgressContributor.query.filter_by(
                live_card_progress_id=progress.id
            ).one()
            if (
                int(progress.revision) != revision_before_revlog
                or progress.last_review_event_id != pointer_before_revlog
                or contributor.history_completeness_code != "HISTORY_MIXED_PARTIAL"
            ):
                raise AssertionError("Revlog mutated current state or missed mixed history.")

            study_service.execute_native_review_command(
                user=db.session.get(User, fixture["user_id"]),
                card=db.session.get(Card, fixture["delete_card_id"]),
                action="good",
                payload={"duration_ms": 100},
                clone_scope=None,
                requested_scope_id=int(fixture["deck_id"]),
                timezone_name="Asia/Tokyo",
                now=datetime(2026, 9, 14, 10, 0, 0),
            )
            deleted_event_id = ReviewEvent.query.filter_by(
                card_id=fixture["delete_card_id"]
            ).one().id
            flashcard_content_service.delete_note(
                user_id=int(fixture["user_id"]),
                note_id=str(fixture["delete_note_id"]),
            )
            deleted_subject = StudyProgressSubject.query.filter_by(
                logical_note_key=str(fixture["delete_note_id"]).encode("utf-8")
            ).one()
            if (
                deleted_subject.status_code != "TOMBSTONED_SUBJECT_DELETED"
                or db.session.get(Card, fixture["delete_card_id"]) is not None
                or db.session.get(ReviewEvent, deleted_event_id) is None
            ):
                raise AssertionError("Delete lifecycle lost its tombstone/history contract.")
            study_service.execute_native_review_command(
                user=db.session.get(User, fixture["user_id"]),
                card=db.session.get(Card, fixture["reset_card_id"]),
                action="good",
                payload={"duration_ms": 100},
                clone_scope=None,
                requested_scope_id=int(fixture["deck_id"]),
                timezone_name="Asia/Tokyo",
                now=datetime(2026, 9, 14, 10, 2, 0),
            )
            db.session.remove()

        barrier = Barrier(2)
        errors: list[str] = []
        race_states: list[str] = []
        result_lock = Lock()

        def external_writer() -> None:
            with app.app_context():
                try:
                    race_session = db.session.get(
                        ConnectImportSession, fixture["session_id"]
                    )
                    barrier.wait(timeout=10)
                    result = anki_sync_service.import_progress(
                        int(fixture["user_id"]),
                        race_session,
                        [_snapshot(digest="b", base="a")],
                    )
                    db.session.commit()
                    with result_lock:
                        race_states.append(str(result[0]["state"]))
                except Exception as exc:  # pragma: no cover - reported by probe
                    db.session.rollback()
                    with result_lock:
                        errors.append(f"external:{type(exc).__name__}:{exc}")
                finally:
                    db.session.remove()

        def native_writer() -> None:
            with app.app_context():
                try:
                    barrier.wait(timeout=10)
                    study_service.execute_native_review_command(
                        user=db.session.get(User, fixture["user_id"]),
                        card=db.session.get(Card, fixture["external_card_id"]),
                        action="good",
                        payload={"duration_ms": 100},
                        clone_scope=None,
                        requested_scope_id=int(fixture["deck_id"]),
                        timezone_name="Asia/Tokyo",
                        now=datetime(2026, 9, 14, 10, 5, 0),
                    )
                except Exception as exc:  # pragma: no cover - reported by probe
                    db.session.rollback()
                    with result_lock:
                        errors.append(f"native:{type(exc).__name__}:{exc}")
                finally:
                    db.session.remove()

        with ThreadPoolExecutor(max_workers=2) as executor:
            futures = [executor.submit(external_writer), executor.submit(native_writer)]
            done, pending = wait(futures, timeout=30)
            if pending:
                raise AssertionError("Native/external race timed out or deadlocked.")
            for future in done:
                future.result()
        if errors:
            raise AssertionError(f"Native/external race failed: {errors!r}")
        if race_states not in (["applied"], ["local_conflict"]):
            raise AssertionError(f"Unexpected external race result: {race_states!r}")

        with app.app_context():
            external_note = db.session.get(Note, fixture["external_note_id"])
            external_card = db.session.get(Card, fixture["external_card_id"])
            if (
                external_note is None
                or external_note.field_values != {"Word": "external-stable"}
                or external_card is None
            ):
                raise AssertionError("External/native race mutated source content.")
            subject = StudyProgressSubject.query.filter_by(
                learner_user_id=fixture["user_id"],
                logical_note_key=str(fixture["external_note_id"]).encode("utf-8"),
            ).one()
            live_contributor = StudyProgressContributor.query.filter_by(
                subject_id=subject.id,
                contributor_status="ACTIVE",
            ).one()
            if live_contributor.history_completeness_code != "HISTORY_MIXED_PARTIAL":
                raise AssertionError(
                    "Native review after an external snapshot was not classified mixed."
                )
            before_reset_generation = int(subject.subject_generation)
            deck_management_service.reset_deck_progress(
                deck_obj=db.session.get(Deck, fixture["deck_id"]),
                user_id=int(fixture["user_id"]),
            )
            subject = db.session.get(StudyProgressSubject, subject.id)
            reset_subject = StudyProgressSubject.query.filter_by(
                learner_user_id=fixture["user_id"],
                logical_note_key=str(fixture["reset_note_id"]).encode("utf-8"),
            ).one()
            if (
                subject.status_code != "TOMBSTONED_RESET"
                or int(subject.subject_generation) != before_reset_generation + 1
                or reset_subject.status_code != "TOMBSTONED_RESET"
                or CardProgress.query.filter_by(
                    user_id=fixture["user_id"]
                ).count()
            ):
                raise AssertionError("Reset did not atomically close the generation.")

            study_service.execute_native_review_command(
                user=db.session.get(User, fixture["user_id"]),
                card=db.session.get(Card, fixture["external_card_id"]),
                action="good",
                payload={"duration_ms": 100},
                clone_scope=None,
                requested_scope_id=int(fixture["deck_id"]),
                timezone_name="Asia/Tokyo",
                now=datetime(2026, 9, 14, 10, 10, 0),
            )
            subject = db.session.get(StudyProgressSubject, subject.id)
            if int(subject.subject_generation) != before_reset_generation + 2:
                raise AssertionError("Post-reset review reused the closed generation.")

            result = {
                "database_name": database_name,
                "external_savepoint_rollback_verified": True,
                "revlog_history_only_verified": True,
                "delete_tombstone_verified": True,
                "native_external_race_state": race_states[0],
                "native_external_race_deadlock_free": True,
                "reset_generation_verified": True,
                "post_reset_generation": int(subject.subject_generation),
                "history_fact_count": StudyProgressHistoryFact.query.count(),
                "lifecycle_event_count": StudyProgressLifecycleEvent.query.count(),
                "source_content_unchanged": True,
            }
            db.session.remove()
            db.engine.dispose()
            return result
    finally:
        try:
            db.session.remove()
            if app is not None:
                with app.app_context():
                    db.engine.dispose()
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
