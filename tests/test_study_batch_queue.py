"""Queue infrastructure and durable NOTE worker integration.

Per-Card LEGACY worker execution has been retired. Canonical NOTE command
fault/receipt cases live in test_study_note_batch; this file qualifies queue
hints, ownership locks and large HTTP-admitted NOTE batches through the worker.
"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from app.services.study_queue_service import (
    acquire_batch_lock, acquire_session_lock, clear_study_queue, enqueue_study_batch,
    get_queue_length, pop_study_batch,
    release_batch_lock, release_session_lock,
)
from app.services.study_worker_service import drain_study_queue, process_single_study_batch, recover_admitted_study_batches
from models import db
from models.note import Note
from models.review_event import ReviewEvent
from models.study_progress_subject import StudyProgressSubject
from models.study_session_batch import StudySessionBatch
from models.user import User
from tests import test_study_note_batch as fixtures
from tests.study_note_fixtures import assert_retired_progress_absent


class StudyBatchQueueTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyNoteBatchTests.setUpClass.__func__)
    _cleanup = fixtures.StudyNoteBatchTests._cleanup
    _seed = fixtures.StudyNoteBatchTests._seed
    _event = fixtures.StudyNoteBatchTests._event
    _batch_payload = fixtures.StudyNoteBatchTests._batch_payload
    _http_admit = fixtures.StudyNoteBatchTests._http_admit

    def setUp(self):
        clear_study_queue()
        self.addCleanup(self._cleanup)
        self._seed(note_count=100)
        self.assertEqual(len(self.snapshot["cards"]), 100)
        self.assertTrue(all(len(card["card_id"]) == 73 for card in self.snapshot["cards"]))

    def _events(self, first, count):
        return [self._event(sequence, card=self.snapshot["cards"][(sequence-1) % 100])
                for sequence in range(first, first + count)]

    def _admitted_job(self, *, final=True):
        payload = self._batch_payload(1, self._events(1, 1), final=final)
        self._http_admit(payload)
        job = pop_study_batch(timeout=0)
        self.assertIsNotNone(job)
        return payload, job

    @staticmethod
    def _changed_subjects():
        return StudyProgressSubject.query.filter(StudyProgressSubject.authority_revision > 0)

    def test_100_notes_create_two_batches_without_blocking_progression(self):
        first = self._batch_payload(1, self._events(1, 50))
        second = self._batch_payload(2, self._events(51, 50), final=True)
        self._http_admit(first)
        self._http_admit(second)
        with self.app.app_context():
            self.assertEqual(drain_study_queue(max_jobs=10)["processed_count"], 2)
            self.assertEqual(ReviewEvent.query.count(), 100)
            self.assertEqual(StudyProgressSubject.query.count(), 100)
            self.assertTrue(all(subject.authority_revision == 1 for subject in StudyProgressSubject.query.all()))
            self.assertEqual([batch.event_count for batch in StudySessionBatch.query.order_by(StudySessionBatch.batch_sequence)], [50, 50])
            assert_retired_progress_absent(self, db.session)

    def test_queue_loss_recovers_durable_http_admission(self):
        payload, _job = self._admitted_job()
        clear_study_queue()
        with self.app.app_context():
            recovered = recover_admitted_study_batches()
            self.assertEqual(recovered["requeued_count"], 1)
            self.assertEqual(drain_study_queue()["processed_count"], 1)
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(StudySessionBatch.query.one().batch_id, payload["batch_id"])
            assert_retired_progress_absent(self, db.session)

    def test_terminal_receipt_replay_does_not_duplicate_reviews(self):
        _payload, job = self._admitted_job()
        with self.app.app_context():
            first = process_single_study_batch(job)
            replay = process_single_study_batch(job)
            self.assertEqual(first["status"], "completed")
            self.assertEqual(replay["status"], "already_processed")
            self.assertEqual(ReviewEvent.query.count(), 1)
            self.assertEqual(self._changed_subjects().one().authority_revision, 1)

    def test_forged_job_cannot_replace_admitted_payload(self):
        _payload, job = self._admitted_job()
        forged = {**job, "snapshot_hash": "f" * 64}
        with self.app.app_context():
            refused = process_single_study_batch(forged)
            self.assertNotEqual(refused["status"], "completed")
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(self._changed_subjects().count(), 0)
            self.assertEqual(StudySessionBatch.query.one().status, "enqueued")
            self.assertEqual(process_single_study_batch(job)["status"], "completed")
            self.assertEqual(ReviewEvent.query.count(), 1)

    def test_deleted_note_cannot_produce_a_false_completed_receipt(self):
        _payload, job = self._admitted_job()
        with self.app.app_context():
            note_id = self.snapshot["cards"][0]["card_id"].split(".")[0]
            db.session.delete(db.session.get(Note, note_id))
            db.session.flush()
            db.session.commit()
            result = process_single_study_batch(job)
            self.assertNotEqual(result["status"], "completed")
            self.assertEqual(StudySessionBatch.query.one().status, "failed")
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(self._changed_subjects().count(), 0)
            assert_retired_progress_absent(self, db.session)

    def test_locked_session_requeues_once_and_completes_after_owner_releases(self):
        _payload, job = self._admitted_job()
        enqueue_study_batch(job)
        owner = acquire_session_lock(self.snapshot["session_id"])
        self.assertIsNotNone(owner)
        try:
            with self.app.app_context():
                result = drain_study_queue(max_jobs=10)
                self.assertEqual(result["retrying_count"], 1)
                self.assertEqual(get_queue_length(), 1)
                self.assertEqual(ReviewEvent.query.count(), 0)
        finally:
            release_session_lock(self.snapshot["session_id"], owner)
        with self.app.app_context():
            self.assertEqual(drain_study_queue(max_jobs=10)["processed_count"], 1)
            self.assertEqual(ReviewEvent.query.count(), 1)

    def test_old_batch_wire_is_rejected_before_admission_or_progress(self):
        payload = {**self._batch_payload(1, self._events(1, 1)), "schema_version": "study-batch.v1"}
        self._http_admit(payload, expected=422)
        with self.app.app_context():
            self.assertEqual(StudySessionBatch.query.count(), 0)
            self.assertEqual(ReviewEvent.query.count(), 0)
            self.assertEqual(self._changed_subjects().count(), 0)
            assert_retired_progress_absent(self, db.session)
        self.assertEqual(get_queue_length(), 0)

    def test_nonblocking_queue_pop_does_not_wait_for_redis(self):
        from unittest.mock import Mock

        client = Mock()
        client.lpop.return_value = None
        with patch("app.services.study_queue_service.redis_client", return_value=client):
            self.assertIsNone(pop_study_batch(timeout=0))
            client.lpop.assert_called_once_with("flama:study:queue")
            client.blpop.assert_not_called()

    def test_recovery_does_not_rollback_callers_open_transaction(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            user.username = "pending-caller-change"
            with self.assertRaises(RuntimeError):
                recover_admitted_study_batches()
            self.assertEqual(user.username, "pending-caller-change")
            self.assertTrue(db.session().in_transaction())
            db.session.rollback()

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


if __name__ == "__main__":
    unittest.main()
