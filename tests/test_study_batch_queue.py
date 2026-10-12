"""Tests for asynchronous study review batch processing via Redis."""

from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import text

from app import create_app
from app.services.study_queue_service import (
    acquire_batch_lock,
    acquire_session_lock,
    clear_study_queue,
    enqueue_study_batch,
    get_dlq_length,
    get_queue_length,
    is_batch_processed,
    pop_dlq_job,
    pop_study_batch,
    release_batch_lock,
    release_session_lock,
)
from app.services.study_algorithm_registry import (
    AlgorithmLifecycleState,
    AlgorithmResolutionPurpose,
    StudyAlgorithmNotFoundError,
    resolve_study_algorithm,
)
from app.services.study_worker_service import (
    drain_study_queue,
    process_single_study_batch,
    recover_admitted_study_batches,
)
from app.services.study_session_service import (
    StudySessionError,
    _request_hash,
    enqueue_study_session_batch,
)
from models import db
from models.card import Card, split_card_key
from models.card_progress import CardProgress
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.template import Template
from models.user import User


class StudyBatchQueueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
                "REDIS_URL": "",
                "STUDY_QUEUE_NAMESPACE": "",
                "STUDY_ASYNC_BATCH_ENABLED": True,
            }
        )

    def setUp(self):
        clear_study_queue()
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="batch_student", email="student@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Batch Deck", owner_user_id=user.id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            note_type = NoteType(name="Batch Note Type", user_id=user.id)
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            template = Template(
                name="Front/Back",
                note_type_id=note_type.id,
                front_html="{{Word}}",
                back_html="{{Word}}",
            )
            db.session.add(template)
            db.session.flush()

            # Create 100 cards for testing batches of 50
            self.cards = []
            for i in range(100):
                note = Note(
                    user_id=user.id,
                    deck_id=deck.id,
                    note_type_id=note_type.id,
                    field_values={"Word": f"Word_{i}"},
                )
                db.session.add(note)
                db.session.flush()
                card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()
                self.cards.append(card.id)

            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "student@example.com", "password": "password"},
            follow_redirects=False,
        )

    def tearDown(self):
        clear_study_queue()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _open_session(self):
        response = self.client.post(
            "/api/study/sessions",
            json={"scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _open_session_v3(self):
        previous = self.app.config["STUDY_WIRE_V3_ENABLED"]
        self.app.config["STUDY_WIRE_V3_ENABLED"] = True
        try:
            response = self.client.post(
                "/api/study/sessions",
                json={
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "accepted_session_schema_versions": [
                        "study-session.v3",
                        "study-session.v2",
                    ],
                },
            )
        finally:
            self.app.config["STUDY_WIRE_V3_ENABLED"] = previous
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _make_events(self, snapshot, start_idx: int, count: int):
        events = []
        cards = snapshot["cards"]
        for i in range(count):
            seq = start_idx + i
            card = cards[(seq - 1) % len(cards)]
            event = {
                    "event_id": str(uuid4()),
                    "sequence": seq,
                    "card_id": card["card_id"],
                    "rating": "good",
                    "action_key": "review.good",
                    "trigger_key": "scheduler.review.good",
                    "trigger_contract_version": "1",
                    "policy_key": card["policy_key"],
                    "scheduler_offset_ms": seq * 1000,
                    "duration_ms": 500,
                }
            if snapshot["schema_version"] == "study-session.v3":
                policy = snapshot["policies"][card["policy_key"]]
                event.update(
                    {
                        "action_contract_version": "1",
                        "algorithm_key": snapshot["scheduler_algorithm"],
                        "algorithm_version": snapshot["algorithm_version"],
                        "config_schema_version": policy["config_schema_version"],
                        "config_hash": policy["config_hash"],
                        "study_session_id": snapshot["session_id"],
                    }
                )
            events.append(event)
        return events

    def _admit_single_event_job(self, snapshot, **overrides):
        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": str(uuid4()),
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": self._make_events(snapshot, 1, 1),
            **overrides,
        }
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch", json=payload
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        job = pop_study_batch(timeout=0)
        self.assertIsNotNone(job)
        return job

    def test_uncertain_commit_preserves_completed_batch_and_retry_budget(self):
        snapshot = self._open_session()
        job = self._admit_single_event_job(snapshot, is_final=True)
        with self.app.app_context():
            real_commit = db.session.commit

            def commit_then_disconnect():
                real_commit()
                raise RuntimeError("commit succeeded but acknowledgement was lost")

            with patch(
                "app.services.study_worker_service.db.session.commit",
                side_effect=commit_then_disconnect,
            ) as commit, patch(
                "app.services.study_worker_service.push_to_dlq"
            ) as dlq:
                outcome = process_single_study_batch(job, max_retries=1)
            self.assertEqual(outcome["status"], "already_processed")
            self.assertEqual(commit.call_count, 1)
            dlq.assert_not_called()
            self.assertFalse(db.session().in_transaction())
            batch = StudySessionBatch.query.filter_by(batch_id=job["batch_id"]).one()
            self.assertEqual(batch.status, "completed")
            self.assertEqual(batch.attempt_count, 0)
            self.assertIsNone(batch.error_message)
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(get_queue_length(), 0)
            self.assertEqual(
                db.session.get(StudySession, snapshot["session_id"]).status, "committed"
            )
            replay = process_single_study_batch(job)
            self.assertEqual(replay["status"], "already_processed")
            self.assertEqual(ReviewEvent.query.count(), 1)

    def test_worker_rejects_changed_envelope_even_with_admission_hash(self):
        snapshot = self._open_session()
        job = self._admit_single_event_job(snapshot)
        changed_events = json.loads(json.dumps(job["events"]))
        changed_events[0]["duration_ms"] += 1
        for change in ({"events": changed_events}, {"is_final": True}):
            with self.subTest(change=change), self.app.app_context():
                with patch("app.services.study_worker_service.push_to_dlq") as dlq:
                    outcome = process_single_study_batch({**job, **change})
                self.assertEqual(outcome.get("error_code"), "BATCH_IDEMPOTENCY_CONFLICT")
                dlq.assert_called_once()
                self.assertFalse(db.session().in_transaction())
                self.assertEqual(ReviewEvent.query.count(), 0)
                batch = StudySessionBatch.query.filter_by(batch_id=job["batch_id"]).one()
                self.assertEqual(batch.status, "enqueued")
                self.assertEqual(batch.attempt_count, 0)
        with self.app.app_context():
            self.assertEqual(process_single_study_batch(job)["status"], "completed")
            self.assertEqual(ReviewEvent.query.count(), 1)

    def test_nonblocking_queue_pop_does_not_wait_for_redis(self):
        from unittest.mock import Mock

        client = Mock()
        client.lpop.return_value = None
        with patch("app.services.study_queue_service.redis_client", return_value=client):
            self.assertIsNone(pop_study_batch(timeout=0))
            client.lpop.assert_called_once_with("flama:study:queue")
            client.blpop.assert_not_called()

    def test_worker_refreshes_cached_batch_after_another_commit(self):
        snapshot = self._open_session()
        job = self._admit_single_event_job(snapshot)
        with self.app.app_context():
            cached = StudySessionBatch.query.filter_by(batch_id=job["batch_id"]).one()
            db.session.execute(text(
                "UPDATE study_session_batches SET status = 'completed' WHERE id = :id"
            ), {"id": cached.id})
            self.assertEqual(cached.status, "enqueued")
            outcome = process_single_study_batch(job)
            self.assertEqual(outcome["status"], "already_processed")
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(ReviewEvent.query.count(), 0)

    def test_closed_session_cannot_admit_a_new_batch(self):
        snapshot = self._open_session()
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            session.status = "committed"
            db.session.commit()
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": str(uuid4()),
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "SESSION_NOT_OPEN")
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)
        self.assertEqual(get_queue_length(), 0)

    def test_expired_session_recovers_admitted_batch_but_refuses_new_one(self):
        snapshot = self._open_session()
        job = self._admit_single_event_job(snapshot)
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            session.expires_at = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(seconds=1)
            db.session.commit()
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": str(uuid4()),
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 2, 1),
            },
        )
        self.assertEqual(response.status_code, 410, response.get_json())
        self.assertEqual(response.get_json()["error"], "SESSION_EXPIRED")
        with self.app.app_context():
            self.assertEqual(recover_admitted_study_batches()["requeued_count"], 1)
            self.assertEqual(drain_study_queue()["processed_count"], 1)
            batch = StudySessionBatch.query.filter_by(batch_id=job["batch_id"]).one()
            self.assertEqual(batch.status, "completed")
            self.assertEqual(StudySessionBatch.query.count(), 1)

    def test_partially_overlapping_batch_never_receives_false_success(self):
        snapshot = self._open_session()
        events = self._make_events(snapshot, 1, 2)
        first_job = self._admit_single_event_job(snapshot, events=events[:1])
        overlapping_job = self._admit_single_event_job(snapshot, events=events)
        with self.app.app_context():
            self.assertEqual(process_single_study_batch(first_job)["status"], "completed")
            result = process_single_study_batch(overlapping_job)
            self.assertEqual(result["status"], "failed")
            self.assertEqual(result["error_code"], "BATCH_EVENT_CONFLICT")
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(ReviewEvent.query.count(), 1)
            batch = StudySessionBatch.query.filter_by(batch_id=overlapping_job["batch_id"]).one()
            self.assertEqual(batch.status, "failed")
            self.assertEqual(batch.attempt_count, 0)
            self.assertEqual(len(json.loads(batch.payload_json)["events"]), 2)
            db.session.rollback()
            self.assertEqual(recover_admitted_study_batches()["requeued_count"], 0)

    def test_invalid_admitted_event_fails_durably_instead_of_recovery_loop(self):
        snapshot = self._open_session()
        events = self._make_events(snapshot, 1, 1)
        events[0]["event_id"] = "invalid-uuid"
        job = self._admit_single_event_job(snapshot, events=events)
        with self.app.app_context():
            result = process_single_study_batch(job)
            self.assertEqual(result.get("error_code"), "INVALID_EVENT_ID")
            self.assertFalse(db.session().in_transaction())
            batch = StudySessionBatch.query.filter_by(batch_id=job["batch_id"]).one()
            self.assertEqual(batch.status, "failed")
            self.assertIn("INVALID_EVENT_ID", batch.error_message)
            self.assertEqual(ReviewEvent.query.count(), 0)
            db.session.rollback()
            self.assertEqual(recover_admitted_study_batches()["requeued_count"], 0)

    def test_reordered_batch_waits_for_predecessor_without_spending_retry(self):
        snapshot = self._open_session()
        events = self._make_events(snapshot, 1, 2)
        first_job = self._admit_single_event_job(snapshot, events=events[:1])
        second_job = self._admit_single_event_job(snapshot, events=events[1:], is_final=True)
        enqueue_study_batch(second_job)
        enqueue_study_batch(first_job)
        with self.app.app_context():
            first_pass = drain_study_queue()
            self.assertEqual(first_pass["retrying_count"], 1)
            self.assertEqual(first_pass["processed_count"], 0)
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(get_queue_length(), 2)
            second_pass = drain_study_queue()
            self.assertEqual(second_pass["processed_count"], 2)
            self.assertEqual(ReviewEvent.query.count(), 2)
            self.assertEqual(
                db.session.get(StudySession, snapshot["session_id"]).status, "committed"
            )
            for batch in StudySessionBatch.query.all():
                self.assertEqual(batch.status, "completed")
                self.assertEqual(batch.attempt_count, 0)

    def test_empty_final_batch_waits_for_all_earlier_admissions(self):
        snapshot = self._open_session()
        first_job = self._admit_single_event_job(snapshot)
        final_job = self._admit_single_event_job(snapshot, events=[], is_final=True)
        enqueue_study_batch(final_job)
        enqueue_study_batch(first_job)
        with self.app.app_context():
            self.assertEqual(drain_study_queue()["retrying_count"], 1)
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(drain_study_queue()["processed_count"], 2)
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(
                db.session.get(StudySession, snapshot["session_id"]).status, "committed"
            )
            self.assertTrue(all(batch.status == "completed" for batch in StudySessionBatch.query.all()))

    def test_pending_final_admission_refuses_another_new_batch(self):
        snapshot = self._open_session()
        self._admit_single_event_job(snapshot, is_final=True)
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": str(uuid4()),
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 2, 1),
            },
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "BATCH_AFTER_FINAL")
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 1)

    def test_final_batch_cannot_hide_a_failed_predecessor(self):
        snapshot = self._open_session()
        events = self._make_events(snapshot, 1, 1)
        events[0]["event_id"] = "invalid-uuid"
        first_job = self._admit_single_event_job(snapshot, events=events)
        final_job = self._admit_single_event_job(snapshot, events=[], is_final=True)
        with self.app.app_context():
            self.assertEqual(process_single_study_batch(first_job)["error_code"], "INVALID_EVENT_ID")
            outcome = process_single_study_batch(final_job)
            self.assertEqual(outcome.get("error_code"), "BATCH_PREDECESSOR_FAILED")
            self.assertEqual(db.session.get(StudySession, snapshot["session_id"]).status, "open")
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertTrue(all(batch.status == "failed" for batch in StudySessionBatch.query.all()))

    def test_deleted_card_cannot_produce_a_false_completed_receipt(self):
        snapshot = self._open_session()
        job = self._admit_single_event_job(snapshot)
        with self.app.app_context():
            # A Card is the Note's presentation (ADR P11): it disappears with its Note.
            note_id, _application_id = split_card_key(job["events"][0]["card_id"])
            db.session.execute(text("DELETE FROM notes WHERE id = :id"), {"id": note_id})
            db.session.commit()
            result = process_single_study_batch(job)
            self.assertIn(result.get("error_code"), {"CARD_OUTSIDE_SESSION", "BATCH_CARD_MISSING"})
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)
            batch = StudySessionBatch.query.filter_by(batch_id=job["batch_id"]).one()
            self.assertEqual(batch.status, "failed")

    def test_enqueue_batch_endpoint_returns_202_accepted(self):
        snapshot = self._open_session()
        events = self._make_events(snapshot, 1, 50)
        batch_id = str(uuid4())

        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": batch_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": events,
        }

        res = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json=payload,
        )
        self.assertEqual(res.status_code, 202, res.get_json())
        data = res.get_json()
        self.assertEqual(data["status"], "enqueued")
        self.assertEqual(data["batch_id"], batch_id)
        self.assertEqual(data["event_count"], 50)

        # Check queue length
        self.assertEqual(get_queue_length(), 1)

        # Drain worker
        with self.app.app_context():
            stats = drain_study_queue()
            self.assertEqual(stats["processed_count"], 1)

            # Verify review events were saved
            saved_events = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).order_by(ReviewEvent.sequence_no.asc()).all()
            self.assertEqual(len(saved_events), 50)
            first_payload = json.loads(saved_events[0].payload_json)
            self.assertEqual(first_payload["schema_version"], "review-event-payload.v1")
            self.assertEqual(
                first_payload["provenance"]["source_path"],
                "native.session.worker",
            )
            self.assertEqual(
                first_payload["provenance"]["study_session_id"],
                snapshot["session_id"],
            )
            self.assertEqual(first_payload["provenance"]["request_id"], batch_id)
            self.assertNotIn("policy_key", first_payload)

            # Verify batch status in DB
            batch_record = StudySessionBatch.query.filter_by(batch_id=batch_id).first()
            self.assertIsNotNone(batch_record)
            self.assertEqual(batch_record.status, "completed")
            self.assertEqual(batch_record.event_count, 50)

    def test_enqueue_replay_releases_learner_fence(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": batch_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": self._make_events(snapshot, 1, 1),
        }
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            def assert_unlocked_before_push(_job_payload):
                self.assertFalse(db.session().in_transaction())

            with patch(
                "app.services.study_queue_service.enqueue_study_batch",
                side_effect=assert_unlocked_before_push,
            ) as enqueue:
                first = enqueue_study_session_batch(
                    user=user, session_id=snapshot["session_id"], payload=payload
                )
                self.assertEqual(first["status"], "enqueued")
                self.assertFalse(db.session().in_transaction())

                replay = enqueue_study_session_batch(
                    user=user, session_id=snapshot["session_id"], payload=payload
                )
                self.assertEqual(replay["status"], "enqueued")
                self.assertFalse(db.session().in_transaction())
                self.assertEqual(enqueue.call_count, 2)

            batch = StudySessionBatch.query.filter_by(
                session_id=snapshot["session_id"], batch_id=batch_id
            ).one()
            batch.status = "completed"
            db.session.commit()
            completed = enqueue_study_session_batch(
                user=user, session_id=snapshot["session_id"], payload=payload
            )
            self.assertEqual(completed["status"], "already_processed")
            self.assertFalse(db.session().in_transaction())

    def test_batch_id_collision_cannot_replace_durable_admission_payload(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": batch_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "events": self._make_events(snapshot, 1, 1),
        }
        endpoint = f"/api/study/sessions/{snapshot['session_id']}/batch"
        first = self.client.post(endpoint, json=payload)
        self.assertEqual(first.status_code, 202, first.get_json())
        self.assertEqual(get_queue_length(), 1)

        changed = {**payload, "commit_reason": "manual_exit"}
        collision = self.client.post(endpoint, json=changed)
        self.assertEqual(collision.status_code, 409, collision.get_json())
        self.assertEqual(collision.get_json()["error"], "BATCH_IDEMPOTENCY_CONFLICT")
        self.assertEqual(get_queue_length(), 1)
        with self.app.app_context():
            batch = StudySessionBatch.query.filter_by(batch_id=batch_id).one()
            original_hash = batch.request_hash
            self.assertEqual(json.loads(batch.payload_json)["commit_reason"], "rollover")
            with patch("app.services.study_worker_service.push_to_dlq") as push_to_dlq:
                result = process_single_study_batch({
                    "batch_id": batch_id,
                    "session_id": snapshot["session_id"],
                    "user_id": self.user_id,
                    "request_hash": "forged-payload-hash",
                    "events": changed["events"],
                })
                push_to_dlq.assert_called_once()
            self.assertEqual(result["error_code"], "BATCH_IDEMPOTENCY_CONFLICT")
            self.assertEqual(batch.request_hash, original_hash)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(ReviewEvent.query.count(), 0)

            with patch("app.services.study_worker_service.push_to_dlq") as push_to_dlq:
                missing_hash = process_single_study_batch({
                    "batch_id": batch_id,
                    "session_id": snapshot["session_id"],
                    "user_id": self.user_id,
                    "events": changed["events"],
                })
                push_to_dlq.assert_called_once()
            self.assertEqual(
                missing_hash.get("error_code"), "BATCH_IDEMPOTENCY_CONFLICT"
            )

            batch.status = "completed"
            db.session.commit()
        completed_collision = self.client.post(endpoint, json=changed)
        self.assertEqual(completed_collision.status_code, 409, completed_collision.get_json())
        self.assertEqual(
            completed_collision.get_json()["error"], "BATCH_IDEMPOTENCY_CONFLICT"
        )

    def test_concurrent_batch_unique_key_winner_must_match_request_hash(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": batch_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": self._make_events(snapshot, 1, 1),
        }
        with self.app.app_context():
            db.session.add(StudySessionBatch(
                session_id=snapshot["session_id"],
                user_id=self.user_id,
                batch_id=batch_id,
                batch_sequence=1,
                event_count=1,
                status="enqueued",
                commit_reason="rollover",
                is_final=False,
                request_hash="different-winner-payload",
                payload_json=json.dumps(payload),
                enqueued_at=datetime.now(timezone.utc).replace(tzinfo=None),
            ))
            db.session.commit()
            user = db.session.get(User, self.user_id)
            query_class = type(StudySessionBatch.query)
            real_first = query_class.first
            skipped_first_batch_read = False

            def simulate_losing_the_unique_key(query):
                nonlocal skipped_first_batch_read
                entity = query.column_descriptions[0].get("entity")
                if entity is StudySessionBatch and not skipped_first_batch_read:
                    skipped_first_batch_read = True
                    return None
                return real_first(query)

            with patch.object(query_class, "first", simulate_losing_the_unique_key), patch(
                "app.services.study_queue_service.enqueue_study_batch"
            ) as enqueue:
                with self.assertRaises(StudySessionError) as failure:
                    enqueue_study_session_batch(
                        user=user, session_id=snapshot["session_id"], payload=payload
                    )
                self.assertEqual(failure.exception.code, "BATCH_IDEMPOTENCY_CONFLICT")
                enqueue.assert_not_called()
            self.assertTrue(skipped_first_batch_read)
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(StudySessionBatch.query.count(), 1)

            winner = StudySessionBatch.query.filter_by(batch_id=batch_id).one()
            winner.request_hash = _request_hash(payload)
            db.session.commit()
            skipped_first_batch_read = False
            with patch.object(query_class, "first", simulate_losing_the_unique_key), patch(
                "app.services.study_queue_service.enqueue_study_batch"
            ) as enqueue:
                matching = enqueue_study_session_batch(
                    user=user, session_id=snapshot["session_id"], payload=payload
                )
                self.assertEqual(matching["status"], "enqueued")
                enqueue.assert_called_once()
            self.assertFalse(db.session().in_transaction())

    def test_admitted_batch_recovers_after_queue_loss(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        clear_study_queue()  # Simulate a process/Redis queue loss after DB admission.
        with self.app.app_context():
            recovered = recover_admitted_study_batches()
            self.assertEqual(recovered["requeued_count"], 1)
            self.assertEqual(recovered["blocked"], [])
            self.assertFalse(db.session().in_transaction())
            self.assertEqual(get_queue_length(), 1)
            drained = drain_study_queue()
            self.assertEqual(drained["processed_count"], 1)
            batch = StudySessionBatch.query.filter_by(batch_id=batch_id).one()
            self.assertEqual(batch.status, "completed")
            self.assertEqual(
                ReviewEvent.query.filter_by(study_session_id=snapshot["session_id"]).count(),
                1,
            )

    def test_idle_drain_recovers_durable_admission_after_queue_loss(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        clear_study_queue()
        with self.app.app_context():
            drained = drain_study_queue()
            self.assertEqual(drained["processed_count"], 1)
            self.assertEqual(get_queue_length(), 0)
            self.assertEqual(
                StudySessionBatch.query.filter_by(batch_id=batch_id).one().status,
                "completed",
            )

    def test_recovered_duplicate_delivery_commits_once(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        self.assertEqual(get_queue_length(), 1)
        with self.app.app_context():
            recovered = recover_admitted_study_batches()
            self.assertEqual(recovered["requeued_count"], 1)
            self.assertEqual(get_queue_length(), 2)
            drained = drain_study_queue()
            self.assertEqual(drained["processed_count"], 1)
            self.assertEqual(drained["skipped_count"], 1)
            self.assertEqual(
                ReviewEvent.query.filter_by(study_session_id=snapshot["session_id"]).count(),
                1,
            )

    def test_recovery_preserves_retry_budget_after_queue_loss(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())

        with self.app.app_context():
            for expected_attempt in (1, 2, 3):
                job = pop_study_batch(timeout=0)
                self.assertIsNotNone(job)
                self.assertEqual(job["attempts"], expected_attempt - 1)
                real_commit = db.session.commit
                commit_calls = 0

                def fail_first_commit():
                    nonlocal commit_calls
                    commit_calls += 1
                    if commit_calls == 1:
                        raise RuntimeError("simulated transient commit failure")
                    return real_commit()

                with patch(
                    "app.services.study_worker_service.db.session.commit",
                    side_effect=fail_first_commit,
                ):
                    outcome = process_single_study_batch(job)
                batch = StudySessionBatch.query.filter_by(batch_id=batch_id).one()
                self.assertEqual(batch.attempt_count, expected_attempt)
                persisted_status = batch.status
                self.assertEqual(commit_calls, 2)
                db.session.rollback()
                if expected_attempt < 3:
                    self.assertEqual(outcome["status"], "retrying")
                    clear_study_queue()  # Retry payload is lost before the next worker.
                    recovered = recover_admitted_study_batches()
                    self.assertEqual(recovered["requeued_count"], 1)
                else:
                    self.assertEqual(outcome["status"], "failed")
                    self.assertEqual(persisted_status, "failed")
                    self.assertEqual(recover_admitted_study_batches()["scanned_count"], 0)
            self.assertEqual(ReviewEvent.query.count(), 0)

    def test_retry_metadata_commit_failure_leaves_outbox_recoverable(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        with self.app.app_context():
            job = pop_study_batch(timeout=0)
            self.assertIsNotNone(job)
            with patch(
                "app.services.study_worker_service.db.session.commit",
                side_effect=RuntimeError("database unavailable"),
            ):
                outcome = process_single_study_batch(job)
            self.assertEqual(outcome["status"], "retry_persist_failed")
            self.assertEqual(get_queue_length(), 0)
            batch = StudySessionBatch.query.filter_by(batch_id=batch_id).one()
            self.assertEqual(batch.status, "enqueued")
            self.assertEqual(batch.attempt_count, 0)
            db.session.rollback()
            self.assertEqual(recover_admitted_study_batches()["requeued_count"], 1)

    def test_admitted_job_cannot_mutate_committed_session(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": batch_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": self._make_events(snapshot, 1, 1),
        }
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json=payload,
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        with self.app.app_context(), patch(
            "app.services.study_worker_service.push_to_dlq"
        ) as push_to_dlq:
            session = db.session.get(StudySession, snapshot["session_id"])
            session.status = "committed"
            db.session.commit()
            drained = drain_study_queue()
            self.assertEqual(drained["processed_count"], 0)
            push_to_dlq.assert_called_once()
            batch = StudySessionBatch.query.filter_by(batch_id=batch_id).one()
            self.assertEqual(batch.status, "failed")
            self.assertEqual(ReviewEvent.query.count(), 0)
            db.session.rollback()
            self.assertEqual(recover_admitted_study_batches()["scanned_count"], 0)
        replay = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch", json=payload
        )
        self.assertEqual(replay.status_code, 409, replay.get_json())
        self.assertEqual(replay.get_json()["error"], "BATCH_FAILED")

    def test_recovery_never_queues_corrupt_admission_payload(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        clear_study_queue()
        with self.app.app_context():
            batch = StudySessionBatch.query.filter_by(batch_id=batch_id).one()
            payload = json.loads(batch.payload_json)
            payload["events"] = []
            batch.payload_json = json.dumps(payload)
            db.session.commit()
            recovered = recover_admitted_study_batches()
            self.assertEqual(recovered["requeued_count"], 0)
            self.assertEqual(
                recovered["blocked"],
                [{"batch_id": batch_id, "code": "BATCH_OUTBOX_INVALID"}],
            )
            self.assertEqual(get_queue_length(), 0)
            self.assertEqual(batch.status, "enqueued")

    def test_recovery_never_requeues_legacy_job_after_note_enrollment(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        clear_study_queue()
        with self.app.app_context():
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.add(StudyAuthorityEnrollment(
                learner_user_id=self.user_id,
                mode_code="NOTE",
                epoch=1,
                created_at=now,
                updated_at=now,
            ))
            db.session.commit()
            recovered = recover_admitted_study_batches()
            self.assertEqual(recovered["requeued_count"], 0)
            self.assertEqual(
                recovered["blocked"],
                [{"batch_id": batch_id, "code": "ASYNC_BATCH_NOTE_UNSUPPORTED"}],
            )
            self.assertEqual(get_queue_length(), 0)

    def test_recovery_does_not_rollback_callers_open_transaction(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            user.username = "pending-caller-change"
            with self.assertRaises(RuntimeError):
                recover_admitted_study_batches()
            self.assertEqual(user.username, "pending-caller-change")
            self.assertTrue(db.session().in_transaction())
            db.session.rollback()

    def test_batch_endpoint_fails_closed_when_async_admission_is_disabled(self):
        snapshot = self._open_session()
        previous = self.app.config["STUDY_ASYNC_BATCH_ENABLED"]
        self.app.config["STUDY_ASYNC_BATCH_ENABLED"] = False
        try:
            response = self.client.post(
                f"/api/study/sessions/{snapshot['session_id']}/batch",
                json={
                    "schema_version": "study-batch.v1",
                    "batch_id": str(uuid4()),
                    "session_token": snapshot["session_token"],
                    "snapshot_hash": snapshot["snapshot_hash"],
                    "events": [],
                },
            )
        finally:
            self.app.config["STUDY_ASYNC_BATCH_ENABLED"] = previous

        self.assertEqual(response.status_code, 503, response.get_json())
        self.assertEqual(response.get_json()["error"], "ASYNC_BATCH_DISABLED")
        self.assertEqual(get_queue_length(), 0)

    def test_enabled_async_flag_still_fails_closed_without_production_worker(self):
        snapshot = self._open_session()
        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": str(uuid4()),
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": [],
        }
        previous = self.app.config["TESTING"]
        self.app.config["TESTING"] = False
        try:
            batch_response = self.client.post(
                f"/api/study/sessions/{snapshot['session_id']}/batch",
                json=payload,
            )
            commit_response = self.client.post(
                f"/api/study/sessions/{snapshot['session_id']}/commit?async=1",
                json=payload,
            )
        finally:
            self.app.config["TESTING"] = previous

        for response in (batch_response, commit_response):
            self.assertEqual(response.status_code, 503, response.get_json())
            self.assertEqual(
                response.get_json()["error"], "ASYNC_BATCH_WORKER_UNAVAILABLE"
            )
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)
        self.assertEqual(get_queue_length(), 0)

    def test_production_ready_pool_accepts_both_legacy_wire_versions(self):
        for open_session, schema in ((self._open_session, "study-batch.v1"), (self._open_session_v3, "study-batch.v2")):
            snapshot = open_session()
            payload = {
                "schema_version": schema, "batch_id": str(uuid4()),
                "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
                "events": self._make_events(snapshot, 1, 1), "is_final": True,
            }
            with self.subTest(schema=schema), patch.dict(self.app.config, TESTING=False), patch(
                "app.services.study_session_service.has_ready_study_worker", return_value=True,
            ) as ready:
                response = self.client.post(f"/api/study/sessions/{snapshot['session_id']}/batch", json=payload)
                self.assertEqual(response.status_code, 202, response.get_json())
                ready.assert_called_once_with("study-session.v4")
                with self.app.app_context():
                    self.assertEqual(drain_study_queue()["processed_count"], 1)
                    self.assertEqual(ReviewEvent.query.filter_by(study_session_id=snapshot["session_id"]).count(), 1)

    def test_note_route_rejects_batch_before_queue_or_progress_write(self):
        snapshot = self._open_session()
        with self.app.app_context():
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            db.session.add(StudyAuthorityEnrollment(
                learner_user_id=self.user_id,
                mode_code="NOTE",
                epoch=1,
                created_at=now,
                updated_at=now,
            ))
            db.session.commit()

        payload = {
            "schema_version": "study-batch.v1",
            "batch_id": str(uuid4()),
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": self._make_events(snapshot, 1, 1),
        }
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json=payload,
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "ASYNC_BATCH_NOTE_UNSUPPORTED")
        self.assertEqual(get_queue_length(), 0)
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(ReviewEvent.query.count(), 0)

            job_payload = {
                "schema_version": "study-batch-job.v1",
                "source_schema_version": "study-batch.v1",
                "session_wire_schema_version": "study-session.v2",
                "batch_id": payload["batch_id"],
                "session_id": snapshot["session_id"],
                "user_id": self.user_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": payload["events"],
            }
            with patch("app.services.study_worker_service.push_to_dlq") as push_to_dlq:
                result = process_single_study_batch(job_payload)
                push_to_dlq.assert_called_once()
            self.assertEqual(result["status"], "authority_mode_unsupported")
            self.assertEqual(result["error_code"], "ASYNC_BATCH_NOTE_UNSUPPORTED")
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(ReviewEvent.query.count(), 0)

    def test_v4_session_cannot_fall_back_to_legacy_batch_worker(self):
        snapshot = self._open_session()
        with self.app.app_context():
            session = db.session.get(StudySession, snapshot["session_id"])
            session.wire_schema_version = "study-session.v4"
            db.session.commit()

        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v3",
                "batch_id": str(uuid4()),
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "events": [],
            },
        )
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "ASYNC_BATCH_NOTE_UNSUPPORTED")
        self.assertEqual(get_queue_length(), 0)
        with self.app.app_context(), patch(
            "app.services.study_worker_service.push_to_dlq"
        ) as push_to_dlq:
            result = process_single_study_batch({
                "batch_id": str(uuid4()),
                "session_id": snapshot["session_id"],
                "user_id": self.user_id,
                "events": [],
            })
            push_to_dlq.assert_called_once()
            self.assertEqual(result["error_code"], "ASYNC_BATCH_NOTE_UNSUPPORTED")
            self.assertEqual(CardProgress.query.count(), 0)

    def test_v3_batch_uses_paired_envelope_and_worker_exact_identity(self):
        snapshot = self._open_session_v3()
        batch_id = str(uuid4())
        response = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v2",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "rollover",
                "events": self._make_events(snapshot, 1, 1),
            },
        )
        self.assertEqual(response.status_code, 202, response.get_json())
        with self.app.app_context():
            result = drain_study_queue()
            event = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).one()
            event_payload = json.loads(event.payload_json)
        self.assertEqual(result["processed_count"], 1)
        self.assertEqual(
            event_payload["provenance"]["wire_schema_version"],
            "study-session.v3",
        )

    def test_v3_worker_rejects_missing_identity_before_review_write(self):
        snapshot = self._open_session_v3()
        batch_id = str(uuid4())
        event = self._make_events(snapshot, 1, 1)[0]
        del event["action_contract_version"]
        job_payload = {
            "schema_version": "study-batch-job.v1",
            "source_schema_version": "study-batch.v2",
            "session_wire_schema_version": "study-session.v3",
            "batch_id": batch_id,
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "events": [event],
        }
        with self.app.app_context(), patch(
            "app.services.study_worker_service.push_to_dlq"
        ) as push_to_dlq:
            result = process_single_study_batch(job_payload)
            event_count = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).count()
        self.assertEqual(result["status"], "wire_contract_invalid")
        self.assertEqual(result["error_code"], "WIRE_CONTRACT_MISMATCH")
        self.assertEqual(event_count, 0)
        push_to_dlq.assert_called_once()

    def test_100_cards_creates_two_batches_without_blocking_progression(self):
        snapshot = self._open_session()
        batch_1_id = str(uuid4())
        batch_2_id = str(uuid4())

        events_1 = self._make_events(snapshot, 1, 50)
        events_2 = self._make_events(snapshot, 51, 50)

        # Batch 1 (cards 1..50)
        res1 = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_1_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "rollover",
                "is_final": False,
                "events": events_1,
            },
        )
        self.assertEqual(res1.status_code, 202)

        # Batch 2 (cards 51..100)
        res2 = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_2_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "rollover",
                "is_final": False,
                "events": events_2,
            },
        )
        self.assertEqual(res2.status_code, 202)
        self.assertEqual(get_queue_length(), 2)

        # Worker drains both batches
        with self.app.app_context():
            stats = drain_study_queue()
            self.assertEqual(stats["processed_count"], 2)

            # Total 100 events
            total_events = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).count()
            self.assertEqual(total_events, 100)

    def test_remaining_cards_below_50_flushed_when_session_finalized(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        # Only 15 remaining cards
        events = self._make_events(snapshot, 1, 15)

        res = self.client.post(
            f"/api/study/sessions/{snapshot['session_id']}/batch",
            json={
                "schema_version": "study-batch.v1",
                "batch_id": batch_id,
                "session_token": snapshot["session_token"],
                "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "auto_finish",
                "is_final": True,
                "events": events,
            },
        )
        self.assertEqual(res.status_code, 202)
        self.assertEqual(res.get_json()["event_count"], 15)

        with self.app.app_context():
            stats = drain_study_queue()
            self.assertEqual(stats["processed_count"], 1)

            saved_events = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).count()
            self.assertEqual(saved_events, 15)

            session = db.session.get(StudySession, snapshot["session_id"])
            self.assertEqual(session.status, "committed")

    def test_idempotency_duplicate_delivery_does_not_duplicate_reviews(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        events = self._make_events(snapshot, 1, 50)

        job_payload = {
            "schema_version": "study-batch-job.v1",
            "batch_id": batch_id,
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": events,
            "enqueued_at": datetime.now(timezone.utc).isoformat(),
        }

        with self.app.app_context():
            # First execution
            result1 = process_single_study_batch(job_payload)
            self.assertEqual(result1["status"], "completed")
            count1 = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).count()
            self.assertEqual(count1, 50)

            # Second execution with the exact same batch_id (replayed/retried)
            result2 = process_single_study_batch(job_payload)
            self.assertEqual(result2["status"], "already_processed")

            count2 = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).count()
            # Must NOT duplicate
            self.assertEqual(count2, 50)

    def test_worker_cache_key_is_scoped_to_session_and_batch(self):
        batch_id = str(uuid4())
        first_session = self._open_session()
        first_job = {
            "schema_version": "study-batch-job.v1",
            "batch_id": batch_id,
            "session_id": first_session["session_id"],
            "user_id": self.user_id,
            "session_token": first_session["session_token"],
            "snapshot_hash": first_session["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": self._make_events(first_session, 1, 1),
        }
        with self.app.app_context():
            first_result = process_single_study_batch(first_job)
            self.assertEqual(first_result["status"], "completed", first_result)
            with patch("app.services.study_worker_service.push_to_dlq"):
                forged_replay = process_single_study_batch(
                    {**first_job, "request_hash": "forged-replay"}
                )
            self.assertEqual(
                forged_replay.get("error_code"), "BATCH_IDEMPOTENCY_CONFLICT"
            )

        second_session = self._open_session()
        second_job = {
            **first_job,
            "session_id": second_session["session_id"],
            "session_token": second_session["session_token"],
            "snapshot_hash": second_session["snapshot_hash"],
            "events": self._make_events(second_session, 1, 1),
        }
        with self.app.app_context():
            second_result = process_single_study_batch(second_job)
            self.assertEqual(second_result["status"], "completed", second_result)
            self.assertEqual(
                ReviewEvent.query.filter_by(
                    study_session_id=second_session["session_id"]
                ).count(),
                1,
            )

    def test_worker_resolves_pinned_algorithm_as_an_accepted_job(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        job_payload = {
            "schema_version": "study-batch-job.v1",
            "batch_id": batch_id,
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": self._make_events(snapshot, 1, 1),
        }

        with self.app.app_context(), patch(
            "app.services.study_worker_service.resolve_study_algorithm",
            wraps=resolve_study_algorithm,
        ) as resolver:
            result = process_single_study_batch(job_payload)

        self.assertEqual(result["status"], "completed")
        resolver.assert_called_once_with(
            "legacy-anki",
            "1.0.0",
            purpose=AlgorithmResolutionPurpose.ACCEPTED_JOB,
        )

    def test_worker_missing_session_releases_learner_fence(self):
        job_payload = {
            "batch_id": str(uuid4()),
            "session_id": str(uuid4()),
            "user_id": self.user_id,
            "events": [],
        }
        with self.app.app_context(), patch(
            "app.services.study_worker_service.push_to_dlq"
        ):
            result = process_single_study_batch(job_payload)
            self.assertEqual(result["status"], "session_not_found")
            self.assertFalse(db.session().in_transaction())

    def test_worker_completed_db_batch_replay_releases_learner_fence(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        with self.app.app_context():
            db.session.add(
                StudySessionBatch(
                    session_id=snapshot["session_id"],
                    user_id=self.user_id,
                    batch_id=batch_id,
                    status="completed",
                    request_hash="already-recorded",
                )
            )
            db.session.commit()
            result = process_single_study_batch(
                {
                    "batch_id": batch_id,
                    "session_id": snapshot["session_id"],
                    "user_id": self.user_id,
                    "events": [],
                }
            )
            self.assertEqual(result["status"], "already_processed")
            self.assertFalse(db.session().in_transaction())

    def test_worker_event_reuse_without_batch_row_fails_and_releases_learner_fence(self):
        snapshot = self._open_session()
        events = self._make_events(snapshot, 1, 1)
        job_payload = {
            "schema_version": "study-batch-job.v1",
            "batch_id": str(uuid4()),
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": events,
        }
        with self.app.app_context():
            first = process_single_study_batch(job_payload)
            self.assertEqual(first["status"], "completed")
            replay = process_single_study_batch(
                {**job_payload, "batch_id": str(uuid4())}
            )
            self.assertEqual(replay["status"], "failed")
            self.assertEqual(replay["error_code"], "BATCH_EVENT_CONFLICT")
            self.assertFalse(db.session().in_transaction())

    def test_worker_rejects_retired_algorithm_before_review_write(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        job_payload = {
            "schema_version": "study-batch-job.v1",
            "batch_id": batch_id,
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": self._make_events(snapshot, 1, 1),
        }
        unavailable = StudyAlgorithmNotFoundError(
            "legacy-anki",
            "1.0.0",
            purpose=AlgorithmResolutionPurpose.ACCEPTED_JOB,
            lifecycle_state=AlgorithmLifecycleState.RETIRED,
            reason="RETIRED",
        )

        with self.app.app_context(), patch(
            "app.services.study_worker_service.resolve_study_algorithm",
            side_effect=unavailable,
        ), patch("app.services.study_worker_service.push_to_dlq") as push_to_dlq:
            result = process_single_study_batch(job_payload)
            event_count = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).count()

        self.assertEqual(result["status"], "algorithm_unavailable")
        self.assertEqual(result["error_code"], "ALGORITHM_UNAVAILABLE")
        self.assertEqual(result["reason"], "RETIRED")
        self.assertEqual(result["purpose"], "accepted-job")
        self.assertEqual(event_count, 0)
        push_to_dlq.assert_called_once()

    def test_worker_failure_and_retry_handling(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        events = self._make_events(snapshot, 1, 10)

        job_payload = {
            "schema_version": "study-batch-job.v1",
            "batch_id": batch_id,
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": events,
            "attempts": 0,
            "max_retries": 3,
        }

        with self.app.app_context():
            # Simulate transient failure on first attempt
            with patch("app.services.study_worker_service.db.session.commit", side_effect=Exception("Transient DB Lock")):
                res1 = process_single_study_batch(job_payload)
                self.assertEqual(res1["status"], "retrying")
                self.assertEqual(res1["attempts"], 1)

            # Next attempt without error succeeds
            res2 = process_single_study_batch(job_payload)
            self.assertEqual(res2["status"], "completed")

            events_count = ReviewEvent.query.filter_by(
                study_session_id=snapshot["session_id"]
            ).count()
            self.assertEqual(events_count, 10)

    def test_dlq_on_exceeded_retries(self):
        snapshot = self._open_session()
        batch_id = str(uuid4())
        events = self._make_events(snapshot, 1, 10)

        job_payload = {
            "schema_version": "study-batch-job.v1",
            "batch_id": batch_id,
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": events,
            "attempts": 2,  # Last attempt
            "max_retries": 3,
        }

        with self.app.app_context():
            with patch("app.services.study_worker_service.db.session.commit", side_effect=Exception("Permanent DB Error")):
                res = process_single_study_batch(job_payload, max_retries=3)
                self.assertEqual(res["status"], "failed")

            # Verify pushed to DLQ
            self.assertEqual(get_dlq_length(), 1)
            dlq_job = pop_dlq_job()
            self.assertIsNotNone(dlq_job)
            self.assertEqual(dlq_job["batch_id"], batch_id)
            self.assertIn("Permanent DB Error", dlq_job["error"])

    def test_concurrent_workers_lock_prevents_double_processing(self):
        batch_id = str(uuid4())
        # Acquire lock simulating worker 1
        owner_token = acquire_batch_lock(batch_id, timeout=60)
        self.assertIsNotNone(owner_token)

        # Worker 2 attempts to acquire lock for same batch
        acquired_again = acquire_batch_lock(batch_id, timeout=60)
        self.assertIsNone(acquired_again)

        # Release lock
        self.assertTrue(release_batch_lock(batch_id, owner_token))
        # Worker 2 can now acquire
        next_owner_token = acquire_batch_lock(batch_id, timeout=60)
        self.assertIsNotNone(next_owner_token)
        self.assertTrue(release_batch_lock(batch_id, next_owner_token))

    def test_expired_owner_cannot_release_replacement_local_lock(self):
        batch_id = str(uuid4())
        with patch(
            "app.services.study_queue_service.redis_client",
            side_effect=RuntimeError("offline"),
        ), patch(
            "app.services.study_queue_service.time.time",
            side_effect=[1000, 1002, 1002],
        ):
            expired_token = acquire_batch_lock(batch_id, timeout=1)
            replacement_token = acquire_batch_lock(batch_id, timeout=60)
            self.assertIsNotNone(expired_token)
            self.assertIsNotNone(replacement_token)
            self.assertNotEqual(expired_token, replacement_token)
            self.assertFalse(release_batch_lock(batch_id, expired_token))
            self.assertIsNone(acquire_batch_lock(batch_id, timeout=60))
            self.assertTrue(release_batch_lock(batch_id, replacement_token))

    def test_redis_lock_release_uses_atomic_owner_compare(self):
        class FakeRedis:
            def __init__(self):
                self.values = {}
                self.eval_calls = 0

            def set(self, key, value, *, ex, nx):
                if nx and key in self.values:
                    return False
                self.values[key] = value
                return True

            def eval(self, script, key_count, key, owner_token):
                self.eval_calls += 1
                self.assert_contract(script, key_count)
                if self.values.get(key) != owner_token:
                    return 0
                del self.values[key]
                return 1

            @staticmethod
            def assert_contract(script, key_count):
                if (
                    key_count != 1
                    or "redis.call('GET'" not in script
                    or "redis.call('DEL'" not in script
                ):
                    raise AssertionError("Redis release must compare ownership before deletion.")

        fake_redis = FakeRedis()
        batch_id = str(uuid4())
        with patch("app.services.study_queue_service.redis_client", return_value=fake_redis):
            expired_token = acquire_batch_lock(batch_id, timeout=1)
            self.assertIsNotNone(expired_token)
            lock_key = f"flama:study:lock:batch:{batch_id}"
            fake_redis.values[lock_key] = "replacement-owner"
            self.assertFalse(release_batch_lock(batch_id, expired_token))
            self.assertEqual(fake_redis.values[lock_key], "replacement-owner")
            self.assertTrue(release_batch_lock(batch_id, "replacement-owner"))
            self.assertEqual(fake_redis.eval_calls, 2)

    def test_session_lock_release_requires_owner_token(self):
        session_id = str(uuid4())
        with patch("app.services.study_queue_service.redis_client", side_effect=RuntimeError("offline")):
            owner_token = acquire_session_lock(session_id)
            self.assertIsNotNone(owner_token)
            self.assertFalse(release_session_lock(session_id, "wrong-owner"))
            self.assertIsNone(acquire_session_lock(session_id))
            self.assertTrue(release_session_lock(session_id, owner_token))

    def test_drain_requeues_locked_job_without_spinning(self):
        snapshot = self._open_session()
        job = {
            "schema_version": "study-batch-job.v1",
            "batch_id": str(uuid4()),
            "session_id": snapshot["session_id"],
            "user_id": self.user_id,
            "session_token": snapshot["session_token"],
            "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover",
            "is_final": False,
            "events": self._make_events(snapshot, 1, 1),
        }
        enqueue_study_batch(job)
        owner_token = acquire_session_lock(snapshot["session_id"])
        self.assertIsNotNone(owner_token)
        try:
            with self.app.app_context():
                result = drain_study_queue(max_jobs=10)
            self.assertEqual(result["retrying_count"], 1)
            self.assertEqual(get_queue_length(), 1)
        finally:
            release_session_lock(snapshot["session_id"], owner_token)
        with self.app.app_context():
            resumed = drain_study_queue(max_jobs=10)
            self.assertEqual(resumed["processed_count"], 1)
            self.assertEqual(
                ReviewEvent.query.filter_by(study_session_id=snapshot["session_id"]).count(),
                1,
            )
