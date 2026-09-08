"""Tests for asynchronous study review batch processing via Redis."""

from datetime import datetime, timedelta, timezone
import json
import unittest
from unittest.mock import patch
from uuid import uuid4

from app import create_app
from app.services.study_queue_service import (
    acquire_batch_lock,
    clear_study_queue,
    enqueue_study_batch,
    get_dlq_length,
    get_queue_length,
    is_batch_processed,
    pop_dlq_job,
    release_batch_lock,
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
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
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
                card = Card(
                    note_id=note.id,
                    template_id=template.id,
                )
                db.session.add(card)
                db.session.flush()
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
        acquired = acquire_batch_lock(batch_id, timeout=60)
        self.assertTrue(acquired)

        # Worker 2 attempts to acquire lock for same batch
        acquired_again = acquire_batch_lock(batch_id, timeout=60)
        self.assertFalse(acquired_again)

        # Release lock
        release_batch_lock(batch_id)
        # Worker 2 can now acquire
        self.assertTrue(acquire_batch_lock(batch_id, timeout=60))
        release_batch_lock(batch_id)
