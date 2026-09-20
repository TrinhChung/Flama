"""Exercise P4-09 crash/resume and stale-CAS behavior on disposable MySQL."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import secrets
import sys

from dotenv import load_dotenv
from flask_migrate import stamp, upgrade
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services import browse_card_service, deck_management_service
from app.services import study_progress_shadow_mirror_service as mirror
from app.services.study_progress_backfill_service import (
    StudyProgressBackfillError,
    run_current_progress_backfill,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_progress_backfill_checkpoint import StudyProgressBackfillCheckpoint
from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from scripts.probe_phase4_shadow_schema_mysql import (
    PROBE_NAME_PATTERN,
    _connection_settings,
    _database_uri,
    _source_database_collation,
)


def _progress(*, user_id: int, card_id: str, interval_days: int) -> CardProgress:
    return CardProgress(
        user_id=user_id,
        card_id=card_id,
        queue="review",
        step_index=0,
        due_day=22000,
        interval_days=interval_days,
        interval_days_raw=float(interval_days),
        is_suspended=False,
        is_buried=False,
        review_kind="review",
        scheduler_mode="legacy",
        ease_factor=2.5,
        reps=3,
        lapses=0,
        last_leech_lapses=0,
        revision=0,
        created_at=datetime(2026, 9, 14, 8, 0, 0),
        updated_at=datetime(2026, 9, 14, 8, 0, 0),
    )


def _seed_fixture() -> dict[str, object]:
    user = User(
        username="p4-backfill-probe",
        email="p4-backfill-probe@example.test",
        timezone="Asia/Tokyo",
    )
    user.set_password("password")
    db.session.add(user)
    db.session.flush()
    deck = Deck(name="P4 backfill probe", owner_user_id=user.id)
    note_type = NoteType(name="P4 backfill type", user_id=user.id)
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
    first_template = Template(
        note_type_id=note_type.id,
        name="Recognition",
        position=0,
        is_default=True,
        front_html="{{Word}}",
        back_html="{{Word}}",
    )
    second_template = Template(
        note_type_id=note_type.id,
        name="Recall",
        position=1,
        is_default=False,
        front_html="{{Word}}",
        back_html="{{Word}}",
    )
    db.session.add_all((first_template, second_template))
    db.session.flush()
    notes = [
        Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Word": f"probe-{index}"},
        )
        for index in range(3)
    ]
    db.session.add_all(notes)
    db.session.flush()
    first_cards = [
        Card(note_id=note.id, template_id=first_template.id) for note in notes
    ]
    third_sibling = Card(note_id=notes[2].id, template_id=second_template.id)
    db.session.add_all((*first_cards, third_sibling))
    db.session.flush()
    db.session.add_all(
        (
            _progress(user_id=int(user.id), card_id=str(first_cards[0].id), interval_days=4),
            _progress(user_id=int(user.id), card_id=str(first_cards[1].id), interval_days=6),
        )
    )
    db.session.commit()
    return {
        "user_id": int(user.id),
        "deck_id": int(deck.id),
        "note_ids": tuple(str(note.id) for note in notes),
        "card_ids": tuple(str(card.id) for card in first_cards),
        "third_sibling_id": str(third_sibling.id),
    }


def run_probe() -> dict[str, object]:
    load_dotenv()
    settings = _connection_settings()
    database_name = (
        f"flama_p4_shadow_probe_backfill_{os.getpid()}_{secrets.token_hex(4)}".lower()
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
                "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED": True,
                "REDIS_URL": "",
            }
        )
        migration = importlib.import_module(
            "migrations.versions.20260913_000039_add_study_progress_shadow_schema"
        )
        with app.app_context():
            baseline = sa.MetaData()
            shadow_names = {table.name for table in migration.TARGET_TABLES}
            for table in db.metadata.sorted_tables:
                if table.name not in shadow_names:
                    table.to_metadata(baseline)
            baseline.create_all(bind=db.engine)
            stamp(revision="20260913_000038", directory="migrations")
            upgrade(directory="migrations")
            fixture = _seed_fixture()

            dry_run = run_current_progress_backfill(db.session)
            if (
                not dry_run.complete
                or dry_run.source_count != 2
                or StudyProgressBackfillRun.query.count()
                or StudyProgressSubject.query.count()
            ):
                raise AssertionError("Dry-run wrote rows or failed source accounting.")

            def checkpoint_fault(boundary: str, _context: object) -> None:
                if boundary == "checkpoint":
                    raise RuntimeError("p4-backfill-probe-checkpoint-fault")

            try:
                run_current_progress_backfill(
                    db.session,
                    apply=True,
                    fault_injector=checkpoint_fault,
                )
            except StudyProgressBackfillError:
                pass
            else:  # pragma: no cover - probe assertion
                raise AssertionError("Injected checkpoint failure unexpectedly committed.")

            failed_run = StudyProgressBackfillRun.query.one()
            failed_checkpoint = StudyProgressBackfillCheckpoint.query.one()
            if (
                failed_run.status_code != "FAILED"
                or failed_checkpoint.last_source_id is not None
                or StudyProgressBackfillDisposition.query.count()
                or StudyProgressSubject.query.count()
            ):
                raise AssertionError("Checkpoint fault crossed an uncommitted batch.")
            resumed = run_current_progress_backfill(
                db.session,
                apply=True,
                run_id=str(failed_run.id),
            )
            if not resumed.complete or resumed.source_count != 2:
                raise AssertionError("Failed run did not resume to complete accounting.")
            before_replay_revision = {
                int(row.id): int(row.mirror_revision)
                for row in StudyProgressSubject.query.all()
            }
            replay = run_current_progress_backfill(
                db.session,
                apply=True,
                run_id=str(failed_run.id),
            )
            after_replay_revision = {
                int(row.id): int(row.mirror_revision)
                for row in StudyProgressSubject.query.all()
            }
            if not replay.complete or before_replay_revision != after_replay_revision:
                raise AssertionError("Completed replay was not idempotent.")

            third_card = db.session.get(Card, fixture["card_ids"][2])
            plan = mirror.prepare_native_mirror(
                db.session,
                learner_user_id=int(fixture["user_id"]),
                cards=(third_card,),
            )
            db.session.add(
                _progress(
                    user_id=int(fixture["user_id"]),
                    card_id=str(third_card.id),
                    interval_days=8,
                )
            )
            mirror.finalize_native_mirror(plan, review_events=())
            db.session.commit()

            added_once = False

            def add_sibling_writer() -> None:
                with app.app_context():
                    sibling = db.session.get(Card, fixture["third_sibling_id"])
                    writer_plan = mirror.prepare_native_mirror(
                        db.session,
                        learner_user_id=int(fixture["user_id"]),
                        cards=(sibling,),
                    )
                    db.session.add(
                        _progress(
                            user_id=int(fixture["user_id"]),
                            card_id=str(sibling.id),
                            interval_days=13,
                        )
                    )
                    mirror.finalize_native_mirror(writer_plan, review_events=())
                    db.session.commit()
                    db.session.remove()

            def inject_concurrent_add(boundary: str, _context: object) -> None:
                nonlocal added_once
                if boundary != "read" or added_once:
                    return
                added_once = True
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(add_sibling_writer).result(timeout=30)

            concurrent_run = run_current_progress_backfill(
                db.session,
                apply=True,
                fault_injector=inject_concurrent_add,
            )
            third_subject = StudyProgressSubject.query.filter_by(
                learner_user_id=fixture["user_id"],
                logical_note_key=str(fixture["note_ids"][2]).encode("utf-8"),
            ).one()
            if (
                not concurrent_run.complete
                or concurrent_run.retry_count != 1
                or int(third_subject.subject_generation) != 2
                or int(third_subject.contributor_count) != 2
                or third_subject.status_code != "QUARANTINED_STATE_DIVERGENCE"
            ):
                raise AssertionError("Concurrent Card create bypassed the generation/vector CAS.")
            concurrent_generation = int(third_subject.subject_generation)

            reset_once = False

            def reset_writer() -> None:
                with app.app_context():
                    deck_management_service.reset_deck_progress(
                        deck_obj=db.session.get(Deck, fixture["deck_id"]),
                        user_id=int(fixture["user_id"]),
                    )
                    db.session.remove()

            def inject_concurrent_reset(boundary: str, _context: object) -> None:
                nonlocal reset_once
                if boundary != "read" or reset_once:
                    return
                reset_once = True
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(reset_writer).result(timeout=30)

            reset_run = run_current_progress_backfill(
                db.session,
                apply=True,
                fault_injector=inject_concurrent_reset,
            )
            if (
                not reset_run.complete
                or reset_run.retry_count != 1
                or reset_run.disposition_counts != {"TOMBSTONED_RESET": 4}
                or CardProgress.query.count()
            ):
                raise AssertionError("Concurrent reset was not retained and accounted.")

            deleted_card_id = str(fixture["card_ids"][0])
            deleted_card = db.session.get(Card, deleted_card_id)
            delete_plan = mirror.prepare_native_mirror(
                db.session,
                learner_user_id=int(fixture["user_id"]),
                cards=(deleted_card,),
            )
            db.session.add(
                _progress(
                    user_id=int(fixture["user_id"]),
                    card_id=deleted_card_id,
                    interval_days=9,
                )
            )
            mirror.finalize_native_mirror(delete_plan, review_events=())
            db.session.commit()

            delete_once = False

            def delete_writer() -> None:
                with app.app_context():
                    browse_card_service.delete_browse_card(
                        user_id=int(fixture["user_id"]),
                        admin_mode=False,
                        card_id=deleted_card_id,
                    )
                    db.session.remove()

            def inject_concurrent_delete(boundary: str, _context: object) -> None:
                nonlocal delete_once
                if boundary != "read" or delete_once:
                    return
                delete_once = True
                with ThreadPoolExecutor(max_workers=1) as executor:
                    executor.submit(delete_writer).result(timeout=30)

            delete_run = run_current_progress_backfill(
                db.session,
                apply=True,
                fault_injector=inject_concurrent_delete,
            )
            if (
                not delete_run.complete
                or delete_run.retry_count != 1
                or delete_run.disposition_counts != {"TOMBSTONED_SUBJECT_DELETED": 1}
                or CardProgress.query.count()
                or db.session.get(Card, deleted_card_id) is not None
            ):
                raise AssertionError("Concurrent Card deletion was not fenced/accounted.")

            result = {
                "database_name": database_name,
                "dry_run_read_only": True,
                "checkpoint_rollback_verified": True,
                "crash_resume_verified": True,
                "completed_replay_idempotent": True,
                "two_connection_races_deadlock_free": True,
                "concurrent_card_create_retry_count": concurrent_run.retry_count,
                "concurrent_card_create_generation": concurrent_generation,
                "concurrent_reset_retry_count": reset_run.retry_count,
                "concurrent_reset_dispositions": reset_run.disposition_counts,
                "concurrent_delete_retry_count": delete_run.retry_count,
                "concurrent_delete_dispositions": delete_run.disposition_counts,
                "source_authority_unchanged_by_backfill": True,
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
