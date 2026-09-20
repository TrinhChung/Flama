"""Exercise P4-07 atomicity and lock ordering on a disposable local MySQL DB."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
import secrets
import sys
from threading import Barrier, Lock
from unittest.mock import patch
from uuid import uuid4

from dotenv import load_dotenv
from flask_migrate import stamp, upgrade
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services import study_service, study_session_service
from app.services.mcp.study_tools import submit_review
from app.services.study_worker_service import process_single_study_batch
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
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
        username="p4-mirror-probe",
        email="p4-mirror-probe@example.test",
        timezone="Asia/Tokyo",
    )
    user.set_password("password")
    db.session.add(user)
    db.session.flush()
    deck = Deck(name="P4 mirror probe", owner_user_id=user.id)
    note_type = NoteType(name="P4 mirror type", user_id=user.id)
    db.session.add_all((deck, note_type))
    db.session.flush()
    db.session.add(
        FieldDef(
            note_type_id=note_type.id,
            name="Word",
            field_type="text",
            position=0,
            required=True,
        )
    )
    templates = [
        Template(
            name=f"Probe template {index}",
            note_type_id=note_type.id,
            position=index,
            is_default=index == 0,
            front_html="{{Word}}",
            back_html="{{Word}}",
        )
        for index in range(4)
    ]
    db.session.add_all(templates)
    db.session.flush()
    fanin_note = Note(
        user_id=user.id,
        note_type_id=note_type.id,
        deck_id=deck.id,
        field_values={"Word": "fan-in"},
    )
    worker_note = Note(
        user_id=user.id,
        note_type_id=note_type.id,
        deck_id=deck.id,
        field_values={"Word": "worker"},
    )
    fault_note = Note(
        user_id=user.id,
        note_type_id=note_type.id,
        deck_id=deck.id,
        field_values={"Word": "fault"},
    )
    db.session.add_all((fanin_note, worker_note, fault_note))
    db.session.flush()
    fanin_cards = [
        Card(note_id=fanin_note.id, template_id=templates[index].id)
        for index in range(3)
    ]
    worker_card = Card(note_id=worker_note.id, template_id=templates[0].id)
    fault_card = Card(note_id=fault_note.id, template_id=templates[0].id)
    db.session.add_all((*fanin_cards, worker_card, fault_card))
    db.session.commit()
    return {
        "user_id": int(user.id),
        "deck_id": int(deck.id),
        "fanin_note_id": str(fanin_note.id),
        "fanin_card_ids": tuple(str(card.id) for card in fanin_cards),
        "worker_card_id": str(worker_card.id),
        "fault_note_id": str(fault_note.id),
        "fault_card_id": str(fault_card.id),
    }


def _session_payload(snapshot: dict[str, object]) -> dict[str, object]:
    card = snapshot["cards"][0]  # type: ignore[index]
    return {
        "schema_version": "study-commit.v1",
        "commit_id": str(uuid4()),
        "session_token": snapshot["session_token"],
        "snapshot_hash": snapshot["snapshot_hash"],
        "commit_reason": "manual_exit",
        "events": [
            {
                "event_id": str(uuid4()),
                "sequence": 1,
                "card_id": card["card_id"],
                "rating": "good",
                "policy_key": card["policy_key"],
                "scheduler_offset_ms": 1000,
                "duration_ms": 100,
            }
        ],
        "final_states": [],
    }


def run_probe() -> dict[str, object]:
    load_dotenv()
    settings = _connection_settings()
    database_name = (
        f"flama_p4_shadow_probe_mirror_{os.getpid()}_{secrets.token_hex(4)}".lower()
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
                "STUDY_ASYNC_BATCH_ENABLED": True,
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
            user = db.session.get(User, fixture["user_id"])
            session_snapshot = study_session_service.open_study_session(
                user=user,
                query=Card.query.filter(Card.id == fixture["fanin_card_ids"][0]),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(fixture["deck_id"]),
                timezone_name="Asia/Tokyo",
                now=datetime(2026, 9, 13, 10, 0, 0),
            )
            session_payload = _session_payload(session_snapshot)
            db.session.remove()

        barrier = Barrier(3)
        errors: list[str] = []
        error_lock = Lock()

        def capture(operation) -> None:
            try:
                with app.app_context():
                    barrier.wait(timeout=10)
                    operation()
                    db.session.remove()
            except Exception as exc:  # pragma: no cover - only reported by probe
                try:
                    db.session.rollback()
                    db.session.remove()
                except Exception:
                    pass
                with error_lock:
                    errors.append(f"{type(exc).__name__}: {exc}")

        def commit_session() -> None:
            study_session_service.commit_study_session(
                user=db.session.get(User, fixture["user_id"]),
                session_id=str(session_snapshot["session_id"]),
                payload=session_payload,
                now=datetime(2026, 9, 13, 10, 0, 5),
            )

        def direct_review() -> None:
            study_service.execute_native_review_command(
                user=db.session.get(User, fixture["user_id"]),
                card=db.session.get(Card, fixture["fanin_card_ids"][1]),
                action="good",
                payload={"duration_ms": 100},
                clone_scope=None,
                requested_scope_id=int(fixture["deck_id"]),
                timezone_name="Asia/Tokyo",
                now=datetime(2026, 9, 13, 10, 0, 1),
            )

        def mcp_review() -> None:
            submit_review(
                user_id=int(fixture["user_id"]),
                card_id=str(fixture["fanin_card_ids"][2]),
                rating="good",
                duration_ms=100,
            )

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [
                executor.submit(capture, commit_session),
                executor.submit(capture, direct_review),
                executor.submit(capture, mcp_review),
            ]
            done, pending = wait(futures, timeout=30)
            if pending:
                raise AssertionError("Concurrent P4-07 writers timed out or deadlocked.")
            for future in done:
                future.result()
        if errors:
            raise AssertionError(f"Concurrent P4-07 writers failed: {errors!r}")

        with app.app_context():
            fanin_subject = StudyProgressSubject.query.filter_by(
                learner_user_id=fixture["user_id"],
                logical_note_key=str(fixture["fanin_note_id"]).encode("utf-8"),
            ).one()
            if (
                fanin_subject.mirror_revision != 3
                or fanin_subject.subject_generation != 3
                or fanin_subject.contributor_count != 3
            ):
                raise AssertionError(
                    "Concurrent sibling writers lost a mirror revision/generation: "
                    f"revision={fanin_subject.mirror_revision}, "
                    f"generation={fanin_subject.subject_generation}, "
                    f"contributors={fanin_subject.contributor_count}."
                )
            fanin_progress = CardProgress.query.filter(
                CardProgress.user_id == fixture["user_id"],
                CardProgress.card_id.in_(fixture["fanin_card_ids"]),
            ).all()
            if len(fanin_progress) != 3 or any(
                row.last_review_event_id is None for row in fanin_progress
            ):
                raise AssertionError("Concurrent writers lost a progress event pointer.")
            if StudyProgressContributor.query.filter_by(
                subject_id=fanin_subject.id,
                subject_generation=fanin_subject.subject_generation,
                contributor_status="ACTIVE",
            ).count() != 3:
                raise AssertionError("Final fan-in contributor vector is incomplete.")

            worker_snapshot = study_session_service.open_study_session(
                user=db.session.get(User, fixture["user_id"]),
                query=Card.query.filter(Card.id == fixture["worker_card_id"]),
                clone_scope=None,
                scope_type="deck",
                scope_id=str(fixture["deck_id"]),
                timezone_name="Asia/Tokyo",
                now=datetime(2026, 9, 13, 11, 0, 0),
            )
            worker_event = _session_payload(worker_snapshot)["events"]
            batch_id = str(uuid4())
            worker_result = process_single_study_batch(
                {
                    "schema_version": "study-batch-job.v1",
                    "batch_id": batch_id,
                    "session_id": worker_snapshot["session_id"],
                    "user_id": fixture["user_id"],
                    "session_token": worker_snapshot["session_token"],
                    "snapshot_hash": worker_snapshot["snapshot_hash"],
                    "commit_reason": "rollover",
                    "is_final": False,
                    "events": worker_event,
                    "enqueued_at": datetime.now(timezone.utc).isoformat(),
                }
            )
            if worker_result["status"] != "completed":
                raise AssertionError(f"MySQL worker mirror failed: {worker_result!r}")

            before_fault_progress = CardProgress.query.count()
            before_fault_events = ReviewEvent.query.count()
            try:
                with patch(
                    "app.services.study_progress_shadow_mirror_service._append_history_facts",
                    side_effect=RuntimeError("probe fault"),
                ):
                    study_service.execute_native_review_command(
                        user=db.session.get(User, fixture["user_id"]),
                        card=db.session.get(Card, fixture["fault_card_id"]),
                        action="good",
                        payload={"duration_ms": 100},
                        clone_scope=None,
                        requested_scope_id=int(fixture["deck_id"]),
                        timezone_name="Asia/Tokyo",
                        now=datetime(2026, 9, 13, 12, 0, 0),
                    )
            except RuntimeError as exc:
                if str(exc) != "probe fault":
                    raise
            else:
                raise AssertionError("Fault injection did not abort the native unit.")

            if CardProgress.query.count() != before_fault_progress:
                raise AssertionError("Mirror fault committed authoritative CardProgress.")
            if ReviewEvent.query.count() != before_fault_events:
                raise AssertionError("Mirror fault committed authoritative ReviewEvent.")
            if StudyProgressSubject.query.filter_by(
                learner_user_id=fixture["user_id"],
                logical_note_key=str(fixture["fault_note_id"]).encode("utf-8"),
            ).count():
                raise AssertionError("Mirror fault committed its coordination subject.")

            lock_subject_id = int(fanin_subject.id)
            locked_card_id = str(fixture["fanin_card_ids"][0])
            before_lock_revision = int(
                CardProgress.query.filter_by(
                    user_id=fixture["user_id"], card_id=locked_card_id
                ).one().revision
            )
            before_lock_mirror_revision = int(fanin_subject.mirror_revision)
            before_lock_events = ReviewEvent.query.count()
            db.session.remove()

            lock_connection = pymysql.connect(
                **{**settings, "database": database_name, "autocommit": False}
            )
            try:
                with lock_connection.cursor() as cursor:
                    cursor.execute(
                        "SELECT id FROM study_progress_subjects WHERE id=%s FOR UPDATE",
                        (lock_subject_id,),
                    )
                    if cursor.fetchone() is None:
                        raise AssertionError("Lock-timeout probe subject disappeared.")

                def timeout_writer() -> None:
                    with app.app_context():
                        db.session.execute(sa.text("SET SESSION innodb_lock_wait_timeout=1"))
                        try:
                            study_service.execute_native_review_command(
                                user=db.session.get(User, fixture["user_id"]),
                                card=db.session.get(Card, locked_card_id),
                                action="good",
                                payload={"duration_ms": 100},
                                clone_scope=None,
                                requested_scope_id=int(fixture["deck_id"]),
                                timezone_name="Asia/Tokyo",
                                now=datetime(2026, 9, 13, 12, 1, 0),
                            )
                        except sa.exc.OperationalError as exc:
                            if int(exc.orig.args[0]) != 1205:
                                raise
                        else:
                            raise AssertionError("Locked subject did not cause a bounded timeout.")
                        finally:
                            db.session.rollback()
                            db.session.remove()

                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(timeout_writer).result(timeout=10)
            finally:
                lock_connection.rollback()
                lock_connection.close()

            if (
                int(CardProgress.query.filter_by(
                    user_id=fixture["user_id"], card_id=locked_card_id
                ).one().revision) != before_lock_revision
                or int(db.session.get(StudyProgressSubject, lock_subject_id).mirror_revision)
                != before_lock_mirror_revision
                or ReviewEvent.query.count() != before_lock_events
            ):
                raise AssertionError("Lock timeout committed a partial native review.")

            result = {
                "database_name": database_name,
                "concurrent_writers": ["native_session", "native_direct", "native_mcp"],
                "deadlock_free": True,
                "fanin_subject_generation": int(fanin_subject.subject_generation),
                "fanin_mirror_revision": int(fanin_subject.mirror_revision),
                "fanin_contributor_count": int(fanin_subject.contributor_count),
                "worker_status": worker_result["status"],
                "history_fact_count": StudyProgressHistoryFact.query.count(),
                "fault_rollback_verified": True,
                "lock_timeout_atomic_rollback_verified": True,
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
