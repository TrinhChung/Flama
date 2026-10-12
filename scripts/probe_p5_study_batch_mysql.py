"""Probe canonical NOTE batch commands and durable worker recovery in disposable MySQL.

No configured application rows are read or modified. Child-process recovery
accepts only a validated generated probe database, never the configured DB.
Includes test-gated HTTP NOTE admission/worker recovery, not production Redis/load evidence.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import threading
from unittest.mock import patch
from uuid import uuid4

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services import study_session_service, study_worker_service
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment, enroll_new_learner_note_authority
from app.repositories.template_library_repository import create_attached_template
from app.services.study_composition_service import make_compatibility_composition_id
from app.services.study_note_batch_service import commit_note_study_session_batch
from app.services.study_queue_service import clear_study_queue, pop_study_batch
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_batch import StudySessionBatch
from models.template import Template
from models.user import User
from scripts.mysql_probe_db import (
    _connection_settings,
    _database_uri,
    _source_database_collation,
)

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_batch_probe_[0-9]+_[a-f0-9]{8}$")


def _probe_app(uri: str):
    url = sa.engine.make_url(uri)
    if (
        url.get_backend_name() != "mysql"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not PROBE_NAME_PATTERN.fullmatch(url.database or "")
    ):
        raise RuntimeError("Refusing a non-local/non-disposable batch probe database.")
    return create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": uri,
        "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False,
        "STARTUP_CHECK_DB_CONNECTIVITY": False,
        "WTF_CSRF_ENABLED": False,
        "REDIS_URL": "",
        "STUDY_QUEUE_NAMESPACE": "",
        "STUDY_ASYNC_BATCH_ENABLED": True,
        "STUDY_WIRE_V3_ENABLED": False,
        "STUDY_WIRE_V4_ENABLED": False,
        "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": False,
    })


def _probe_note_batch_command(app, *, recovery_uri: str | None = None, continuous_probe=None) -> None:
    """Prove HTTP admission with canonical concurrency or fresh-process recovery."""
    suffix = "continuous" if continuous_probe else ("transport" if recovery_uri is not None else "command")
    with app.app_context():
        user = User(username=f"note-batch-{suffix}", email=f"note-batch-{suffix}@example.test")
        db.session.add(user)
        db.session.flush()
        enroll_new_learner_note_authority(db.session, user=user)
        note_type = NoteType(name="NOTE batch probe", user_id=user.id)
        deck = Deck(name="NOTE batch probe", owner_user_id=user.id)
        db.session.add_all([note_type, deck])
        db.session.flush()
        db.session.add(FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0))
        note = Note(user_id=user.id, deck_id=deck.id, note_type_id=note_type.id, field_values={"Word": "probe"})
        db.session.add(note)
        db.session.flush()
        composition_id = None
        for number in range(2):
            template = create_attached_template(db.session, note_type=note_type,
                name=f"NOTE sibling {number}",
                front_html="{{Word}}", back_html="{{Word}}", is_default=number == 0,
            )
            db.session.add(template)
            db.session.flush()
            if number == 0:
                composition_id = make_compatibility_composition_id(note_type.id, template.id)
        user_id, deck_id = user.id, deck.id
        db.session.commit()
        stage_note_authority_enrollment(db.session, learner_user_id=user_id, now_utc=datetime.utcnow())
        db.session.commit()
    client = app.test_client()
    with client.session_transaction() as login:
        login["_user_id"] = str(user_id)
        login["_fresh"] = True
    with patch.dict(app.config, STUDY_WIRE_V4_ENABLED=True):
        opened = client.post("/api/study/sessions", json={
            "scope": "deck", "scope_id": deck_id, "composition_id": composition_id,
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        })
    if opened.status_code != 201:
        raise AssertionError(f"NOTE probe session did not open: {opened.get_json()}")
    snapshot = opened.get_json()
    session_id = snapshot["session_id"]
    card = snapshot["cards"][0]
    policy = snapshot["policies"][card["policy_key"]]

    def event(sequence):
        event_id = str(uuid4())
        rating = "easy" if sequence == 1 else "hard"
        return {
            "event_id": event_id, "operation_key": event_id, "sequence": sequence,
            "card_id": card["card_id"], "rating": rating, "action_key": f"review.{rating}",
            "action_contract_version": "1", "trigger_key": f"scheduler.review.{rating}",
            "trigger_contract_version": "1", "policy_key": card["policy_key"],
            "scheduler_offset_ms": sequence * 1000 + 283, "duration_ms": 500,
            "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
            "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
            "study_session_id": session_id,
            **{key: value for key, value in card["authority_pin"].items() if key != "schema_version"},
        }

    batch_ids = []
    pending_live_payload = None
    for sequence, events in enumerate(([event(1)], [event(2)], [event(3), event(4)]), start=1):
        payload = {
            "schema_version": "study-batch.v3", "batch_id": str(uuid4()),
            "batch_sequence": sequence, "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"], "commit_reason": "rollover",
            "is_final": sequence == 3, "events": events, "final_states": [],
        }
        if continuous_probe is not None and sequence == 3:
            # Admit the final two actions only through normal-mode HTTP after
            # the separate continuous process publishes real Redis readiness.
            pending_live_payload = payload
            batch_ids.append(payload["batch_id"])
            continue
        response = client.post(f"/api/study/sessions/{session_id}/batch", json=payload)
        if response.status_code != 202:
            raise AssertionError(f"NOTE HTTP admission failed: {response.get_json()}")
        batch_ids.append(payload["batch_id"])
    with app.app_context():
        first_job = pop_study_batch(timeout=0)
        clear_study_queue()

    def process(batch_id):
        result = commit_note_study_session_batch(
            user=db.session.get(User, user_id), session_id=session_id, batch_id=batch_id,
        )
        if db.session().in_transaction():
            raise AssertionError("NOTE batch command leaked its DB transaction.")
        return result

    def check(revision, status="open"):
        from app.services.study_progress_shadow_codec import decode_float

        db.session.expire_all()  # Verify stored MySQL values, not assignment cache.
        subjects = StudyProgressSubject.query.filter_by(learner_user_id=user_id).all()
        if len(subjects) != 1 or subjects[0].authority_revision != revision:
            raise AssertionError("NOTE authority row advanced incorrectly.")
        # The Note's one row holds the state; no Card carries progress (ADR P10).
        if sa.inspect(db.engine).has_table("card_progress"):
            raise AssertionError("Retired card_progress was recreated.")
        expected_ease = {1: 2.5, 2: 2.35, 4: 2.05}[revision]
        if decode_float(subjects[0].state_payload["ease"], field_name="ease") != expected_ease:
            raise AssertionError("NOTE mixed-rating numeric state changed on MySQL read.")
        if ReviewEvent.query.filter_by(study_session_id=session_id).count() != revision:
            raise AssertionError("NOTE batch duplicated or lost an event.")
        if StudyAuthorityCommandReceipt.query.filter_by(learner_user_id=user_id).count() != revision:
            raise AssertionError("NOTE batch receipt is missing or duplicated.")
        if StudyProgressHistoryFact.query.filter(
            StudyProgressHistoryFact.learner_user_id == user_id,
            StudyProgressHistoryFact.review_event_id.isnot(None),
        ).count() != revision:
            raise AssertionError("NOTE batch history fact is missing or duplicated.")
        if db.session.get(StudySession, session_id).status != status:
            raise AssertionError("NOTE session was finalized incorrectly.")
        if any(pin.base_authority_revision != 0 for pin in StudySessionAuthorityPin.query.filter_by(learner_user_id=user_id)):
            raise AssertionError("NOTE batch mutated an immutable session pin.")
        db.session.rollback()

    if continuous_probe is not None:
        continuous_probe(
            app, session_id, batch_ids, first_job, http_client=client,
            pending_payload=pending_live_payload,
            open_payload={
                "scope": "deck", "scope_id": deck_id, "composition_id": composition_id,
                "accepted_session_schema_versions": ["study-session.v4"],
                "accepted_batch_schema_versions": ["study-batch.v3"],
            },
        )
        with app.app_context():
            check(4, "committed")
        response = client.get(f"/api/study/sessions/{session_id}/batch/{batch_ids[-1]}")
        if response.status_code != 200 or response.get_json()["receipt"]["cumulative_event_count"] != 4:
            raise AssertionError("Continuous NOTE consumer did not expose its final receipt.")
        return

    if recovery_uri is not None:
        with app.app_context():
            commit = db.session.commit
            commit_calls = 0

            def fail_first_commit():
                nonlocal commit_calls
                commit_calls += 1
                if commit_calls == 1:
                    raise RuntimeError("probe: NOTE transient commit fault")
                return commit()

            with patch.object(db.session, "commit", side_effect=fail_first_commit):
                outcome = study_worker_service.process_single_study_batch(first_job)
            if outcome["status"] != "retrying" or outcome["attempts"] != 1:
                raise AssertionError("NOTE retry budget was not persisted before restart.")
            clear_study_queue()
            db.session.remove()
        env = dict(os.environ)
        env["P5_BATCH_PROBE_DATABASE_URI"] = recovery_uri
        recovered = subprocess.run(
            [sys.executable, str(Path(__file__).resolve()), "--worker-once"],
            cwd=ROOT_DIR, env=env, capture_output=True, text=True, timeout=45, check=False,
        )
        if recovered.returncode:
            raise AssertionError(f"NOTE recovery subprocess failed (exit={recovered.returncode}).")
        report = json.loads(recovered.stdout.strip().splitlines()[-1])
        if report["processed_count"] != 3 or report["failed_count"]:
            raise AssertionError(f"NOTE recovery did not finish three admitted batches: {report}")
        with app.app_context():
            check(4, "committed")
            first = StudySessionBatch.query.filter_by(session_id=session_id, batch_id=batch_ids[0]).one()
            if first.attempt_count != 1:
                raise AssertionError("NOTE restart reset the durable retry budget.")
        response = client.get(f"/api/study/sessions/{session_id}/batch/{batch_ids[-1]}")
        if response.status_code != 200 or response.get_json()["receipt"]["cumulative_event_count"] != 4:
            raise AssertionError("NOTE status did not expose the verified final receipt.")
        return

    ready = threading.Barrier(2, timeout=10)

    def first_worker():
        with app.app_context():
            db.session.execute(sa.text("SET SESSION innodb_lock_wait_timeout = 5"))
            cached = StudySessionBatch.query.filter_by(batch_id=batch_ids[0]).one()
            if cached.status != "enqueued":
                raise AssertionError("NOTE concurrency fixture was already processed.")
            ready.wait()
            return process(batch_ids[0])

    with app.app_context():
        # Establish a stale repeatable-read snapshot BEFORE the first batch.
        if ReviewEvent.query.filter_by(study_session_id=session_id).count() != 0:
            raise AssertionError("NOTE prefix fixture is not empty.")
        # Keep stale ORM objects as well as an old MySQL RR snapshot. Status
        # must refresh the canonical token/state before comparing continuation.
        cached_subjects = StudyProgressSubject.query.filter_by(learner_user_id=user_id).all()
        command = study_session_service.apply_idempotent_existing_state_note_review
        with patch.object(study_session_service, "apply_idempotent_existing_state_note_review", wraps=command) as applied:
            with ThreadPoolExecutor(max_workers=2) as executor:
                futures = [executor.submit(first_worker) for _ in range(2)]
                receipts = [future.result(timeout=30) for future in futures]
            if receipts[0] != receipts[1] or applied.call_count != 1:
                raise AssertionError("Competing NOTE workers applied a command twice.")
        status = study_session_service.get_study_session_status(
            user=db.session.get(User, user_id), session_id=session_id,
        )
        if status["stale"] or status["batch_stream"]["completed_event_count"] != 1:
            raise AssertionError(f"Own NOTE prefix was incorrectly marked stale: {status}")
        if db.session().in_transaction():
            raise AssertionError("NOTE status retained a read transaction.")
        second = process(batch_ids[1])
        if second["cumulative_event_count"] != 2 or second["applied_event_count"] != 1:
            raise AssertionError("NOTE continuation did not refresh its committed prefix.")
        check(2)

        calls = 0

        def fault_after_second_action(*args, **kwargs):
            nonlocal calls
            calls += 1
            result = command(*args, **kwargs)
            if calls == 2:
                raise RuntimeError("probe: NOTE action fault")
            return result

        with patch.object(study_session_service, "apply_idempotent_existing_state_note_review", side_effect=fault_after_second_action):
            try:
                process(batch_ids[2])
            except RuntimeError as exc:
                if str(exc) != "probe: NOTE action fault":
                    raise
            else:
                raise AssertionError("NOTE action fault was not exercised.")
        check(2)
        commit = db.session.commit

        def uncertain_commit():
            commit()
            raise RuntimeError("probe: NOTE acknowledgement lost")

        with patch.object(db.session, "commit", side_effect=uncertain_commit):
            try:
                process(batch_ids[2])
            except RuntimeError as exc:
                if str(exc) != "probe: NOTE acknowledgement lost":
                    raise
            else:
                raise AssertionError("NOTE uncertain COMMIT was not exercised.")
        final_receipt = process(batch_ids[2])
        if final_receipt["applied_event_count"] != 2 or not final_receipt["is_final"]:
            raise AssertionError("NOTE final receipt changed after uncertain COMMIT.")
        check(4, "committed")


def run_probe(*, continuous_probe=None) -> dict:
    load_dotenv()
    settings = _connection_settings()
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Batch probe requires local MySQL.")
    database_name = f"flama_p5_batch_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Refusing unsafe probe database name.")
    admin = pymysql.connect(**settings)
    app = None
    created = False
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE {collation}"
            )
        created = True
        uri = _database_uri(settings, database_name)
        app = _probe_app(uri)
        with app.app_context():
            db.create_all()
        _probe_note_batch_command(app)
        _probe_note_batch_command(app, recovery_uri=uri)
        if continuous_probe is not None:
            _probe_note_batch_command(app, continuous_probe=continuous_probe)
        with app.app_context():
            version = db.session.execute(sa.text("SELECT VERSION()")).scalar_one()
        return {
            "status": "PASS", "mysql_version": version,
            "note_internal_competing_commands": "PASS",
            "note_internal_cross_batch_current_read": "PASS",
            "note_internal_atomic_fault_rollback": "PASS",
            "note_internal_uncertain_commit_replay": "PASS",
            "note_repeated_hard_numeric_projection_after_mysql_reload": "PASS",
            "note_http_admission_and_status": "PASS",
            "note_continuation_status_current_read": "PASS",
            "note_separate_process_outbox_recovery": "PASS",
            "note_retry_budget_after_restart": "PASS",
            "configured_database_modified": False,
            "note_v4_async_tested": True,
            "production_consumer_or_redis_tested": False,
        }
    finally:
        if app is not None:
            with app.app_context():
                clear_study_queue()
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{database_name}`")
        admin.close()


if __name__ == "__main__":
    if sys.argv[1:] == ["--worker-once"]:
        child_app = _probe_app(os.environ["P5_BATCH_PROBE_DATABASE_URI"])
        with child_app.app_context():
            print(json.dumps(study_worker_service.drain_study_queue(max_jobs=10)))
            db.session.remove()
            db.engine.dispose()
    elif sys.argv[1:]:
        raise SystemExit("Only --worker-once is supported for internal recovery probes.")
    else:
        print(json.dumps(run_probe(), sort_keys=True))
