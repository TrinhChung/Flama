"""Consumer control-plane tests; real Redis Lua/process proof is separate."""

from datetime import datetime, timedelta
import threading
import unittest
from unittest.mock import Mock, patch
from uuid import uuid4

from flask import Flask
from sqlalchemy import event, text

from app.repositories.study_batch_repository import read_admitted_batch_page
from app.services import study_consumer_service as consumer_service
from app.services import study_worker_readiness_service as readiness
from app.services.study_consumer_service import StudyBatchConsumer, StudyConsumerOptions, probe_study_worker_database, run_study_consumer
from app.services.study_queue_namespace import study_queue_key, study_queue_prefix
from app.services.study_queue_service import (
    acquire_batch_lock, clear_study_queue, enqueue_study_batch, get_dlq_length,
    is_batch_processed, mark_batch_processed, pop_study_batch, push_to_dlq,
)
from app.services.study_worker_service import recover_admitted_study_batches
from models import db
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.user import User
from study_worker import create_worker_app


CONFIG = {
    "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "REDIS_URL": "", "STUDY_QUEUE_NAMESPACE": "consumer-test", "WTF_CSRF_ENABLED": False,
}
EMPTY_COUNTS = dict(processed_count=0, failed_count=0, retrying_count=0, skipped_count=0)


class StudyConsumerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_worker_app(CONFIG)

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        clear_study_queue()

    def tearDown(self):
        clear_study_queue()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _outbox(self, count=3):
        learner = User(username="consumer", email="consumer@example.test")
        db.session.add(learner)
        db.session.flush()
        session = StudySession(
            user_id=learner.id, scope_id="1", snapshot_hash="snapshot", token_hash="token",
            expires_at=datetime(2026, 9, 27),
        )
        db.session.add(session)
        db.session.flush()
        ids = []
        for sequence in range(1, count + 1):
            batch_id = str(uuid4())
            ids.append(batch_id)
            db.session.add(StudySessionBatch(
                user_id=learner.id, session_id=session.id, batch_id=batch_id,
                batch_sequence=sequence, request_hash="invalid", payload_json="{}",
                enqueued_at=datetime(2026, 9, 26),
            ))
        db.session.commit()
        return ids

    def test_cursor_advances_past_blocked_rows_and_wraps_without_mutation(self):
        ids = self._outbox()
        first = recover_admitted_study_batches(max_jobs=2)
        self.assertEqual([row["batch_id"] for row in first["blocked"]], ids[:2])
        self.assertIsNotNone(first["next_cursor"])
        self.assertFalse(db.session().in_transaction())
        second = recover_admitted_study_batches(max_jobs=2, after=first["next_cursor"])
        self.assertEqual([row["batch_id"] for row in second["blocked"]], ids[2:])
        self.assertIsNone(second["next_cursor"])
        self.assertEqual(recover_admitted_study_batches(max_jobs=2)["next_cursor"], first["next_cursor"])
        self.assertEqual(StudySessionBatch.query.filter_by(status="enqueued", attempt_count=0).count(), 3)

    def test_cursor_handles_removed_head_and_late_insert_on_next_sweep(self):
        ids = self._outbox(2)
        first = recover_admitted_study_batches(max_jobs=1)
        batch = StudySessionBatch.query.filter_by(batch_id=ids[0]).one()
        # A row disappearing from the enqueued index must not shift OFFSET.
        batch.status = "completed"
        db.session.add(StudySessionBatch(
            user_id=batch.user_id, session_id=batch.session_id, batch_id="late-commit",
            batch_sequence=3, request_hash="invalid", payload_json="{}",
            enqueued_at=batch.enqueued_at - timedelta(seconds=1),
        ))
        db.session.commit()
        second = recover_admitted_study_batches(max_jobs=1, after=first["next_cursor"])
        self.assertEqual(second["blocked"][0]["batch_id"], ids[1])
        tail = recover_admitted_study_batches(max_jobs=1, after=second["next_cursor"])
        self.assertEqual(tail["scanned_count"], 0)
        self.assertIsNone(tail["next_cursor"])
        self.assertEqual(recover_admitted_study_batches(max_jobs=1)["blocked"][0]["batch_id"], "late-commit")

    def test_sweep_wraps_even_when_new_admissions_keep_arriving(self):
        ids = self._outbox(1)
        first = recover_admitted_study_batches(max_jobs=1)
        original = StudySessionBatch.query.filter_by(batch_id=ids[0]).one()
        db.session.add(StudySessionBatch(
            user_id=original.user_id, session_id=original.session_id, batch_id="new-tail",
            batch_sequence=2, request_hash="invalid", payload_json="{}",
            enqueued_at=original.enqueued_at + timedelta(seconds=1),
        ))
        db.session.commit()
        end = recover_admitted_study_batches(max_jobs=1, after=first["next_cursor"])
        self.assertEqual(end["scanned_count"], 0)
        self.assertIsNone(end["next_cursor"])
        restarted = recover_admitted_study_batches(max_jobs=1)
        self.assertEqual(restarted["blocked"][0]["batch_id"], ids[0])
        self.assertNotEqual(restarted["next_cursor"].sweep_end, first["next_cursor"].sweep_end)
        tail = recover_admitted_study_batches(max_jobs=1, after=restarted["next_cursor"])
        self.assertEqual(tail["blocked"][0]["batch_id"], "new-tail")

    def test_recovery_releases_failed_read_and_validates_bounds(self):
        for limit in (0, -1, True, 1.5, 1001):
            with self.subTest(limit=limit), self.assertRaises(ValueError):
                read_admitted_batch_page(limit=limit)
        def fail(**_kwargs):
            db.session.execute(text("SELECT 1"))
            raise RuntimeError("read failed")
        with patch("app.services.study_worker_service.read_admitted_batch_page", side_effect=fail):
            with self.assertRaisesRegex(RuntimeError, "read failed"):
                recover_admitted_study_batches()
        self.assertFalse(db.session().in_transaction())

    def test_busy_queue_still_scans_later_pages_then_starts_next_sweep(self):
        self._outbox()
        ticks = [0.0]
        consumer = StudyBatchConsumer(options=StudyConsumerOptions(recovery_page_size=1), clock=lambda: ticks[0])
        cursors = []
        with patch.object(consumer_service, "drain_study_queue", return_value={**EMPTY_COUNTS, "processed_count": 10}) as drain:
            for tick in (0, 1, 5, 10, 15, 20):
                ticks[0] = tick
                result = consumer.step()
                if result["recovery"]:
                    cursors.append(result["recovery"]["next_cursor"])
                self.assertFalse(db.session().in_transaction())
            self.assertEqual(drain.call_count, 6)
            self.assertTrue(all(call.kwargs["recover_when_idle"] is False for call in drain.call_args_list))
        self.assertEqual(len(cursors), 5)
        self.assertEqual([cursor.batch_sequence if cursor else None for cursor in cursors], [1, 2, 3, None, 1])

    def test_probe_is_read_only_and_checks_empty_note_tables(self):
        statements = []
        def capture(_conn, _cursor, statement, *_args):
            statements.append(statement)
        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            probe_study_worker_database()
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertTrue(statements)
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT") for sql in statements))
        self.assertFalse(db.session().in_transaction())
        db.session.execute(text("DROP TABLE study_session_authority_pins"))
        db.session.commit()
        with self.assertRaises(Exception):
            probe_study_worker_database()
        self.assertFalse(db.session().in_transaction())

    def test_probe_does_not_rollback_callers_transaction(self):
        learner = User(username="pending", email="pending@example.test")
        db.session.add(learner)
        with self.assertRaisesRegex(RuntimeError, "transaction-neutral"):
            probe_study_worker_database()
        self.assertIn(learner, db.session.new)

    def test_readiness_is_not_published_if_db_probe_fails(self):
        with patch.object(consumer_service, "probe_study_worker_database", side_effect=RuntimeError), patch.object(
            consumer_service, "publish_study_worker_heartbeat",
        ) as publish:
            with self.assertRaises(RuntimeError):
                StudyBatchConsumer().step()
            publish.assert_not_called()

    def test_run_rolls_back_failed_pass_recovers_and_withdraws_on_stop(self):
        stop = threading.Event()
        consumer = StudyBatchConsumer()
        attempts = []
        def step():
            attempts.append(1)
            if len(attempts) == 1:
                db.session.add(User(username="rollback", email="rollback@example.test"))
                db.session.flush()
                raise RuntimeError("transient")
            self.assertEqual(User.query.count(), 0)
            stop.set()
            return {**EMPTY_COUNTS, "processed_count": 1}
        with patch.object(consumer, "step", side_effect=step), patch.object(consumer, "withdraw") as withdraw, patch.object(stop, "wait", return_value=False) as wait:
            run_study_consumer(self.app, stop_event=stop, consumer=consumer)
        self.assertEqual(len(attempts), 2)
        self.assertEqual(withdraw.call_count, 2)
        wait.assert_called_once_with(1.0)
        self.assertFalse(db.session().in_transaction())

    def test_pre_stopped_consumer_never_starts_work(self):
        stop = threading.Event()
        stop.set()
        consumer = StudyBatchConsumer()
        with patch.object(consumer, "step") as step, patch.object(consumer, "withdraw") as withdraw:
            run_study_consumer(self.app, stop_event=stop, consumer=consumer)
        step.assert_not_called()
        withdraw.assert_called_once()

    def test_worker_options_reject_unbounded_or_invalid_settings(self):
        for args in ({"idle_interval": 0}, {"recovery_interval": float("inf")}, {"heartbeat_interval": 15}, {"jobs_per_pass": True}, {"recovery_page_size": 1001}):
            with self.subTest(args=args), self.assertRaises(ValueError):
                StudyConsumerOptions(**args)

    def test_worker_entrypoint_forces_maintenance_off(self):
        with patch.object(db, "create_all", side_effect=AssertionError("startup mutated schema")):
            app = create_worker_app({**CONFIG, "STARTUP_RUN_MAINTENANCE": True, "STARTUP_RUN_DB_CREATE_ALL": True})
        self.assertFalse(app.config["STARTUP_RUN_MAINTENANCE"])
        self.assertFalse(app.config["STARTUP_CHECK_DB_CONNECTIVITY"])


class StudyWorkerReadinessTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(CONFIG)
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.worker_id = uuid4().hex

    def test_readiness_uses_shared_contract_pool_and_redis_clock(self):
        client = Mock()
        client.eval.return_value = 1
        with patch.object(readiness, "redis_client", return_value=client):
            self.assertTrue(readiness.publish_study_worker_heartbeat(self.worker_id))
            publish = client.eval.call_args
            self.assertIn("redis.call('TIME')", publish.args[0])
            self.assertIn("PEXPIRE", publish.args[0])
            self.assertEqual(publish.args[3:], (self.worker_id, 30000))
            self.assertTrue(readiness.has_ready_study_worker("study-session.v4"))
            self.assertEqual(client.eval.call_args.args[2], publish.args[2])
            self.assertIn("ZCOUNT", client.eval.call_args.args[0])
            self.assertNotIn("consumer@example", publish.args[2])
            client.eval.reset_mock()
            self.assertFalse(readiness.has_ready_study_worker("study-session.v999"))
            client.eval.assert_not_called()

    def test_readiness_fails_closed_for_missing_redis_namespace_or_expired_pool(self):
        with patch.object(readiness, "redis_client", side_effect=ConnectionError):
            self.assertFalse(readiness.publish_study_worker_heartbeat(self.worker_id))
            self.assertFalse(readiness.has_ready_study_worker("study-session.v4"))
        with patch.object(readiness, "redis_client", return_value=Mock(eval=Mock(return_value=0))):
            self.assertFalse(readiness.has_ready_study_worker("study-session.v4"))
        with patch.dict(self.app.config, STUDY_QUEUE_NAMESPACE=""):
            self.assertFalse(readiness.has_ready_study_worker("study-session.v4"))
            with self.assertRaises(ValueError):
                readiness.publish_study_worker_heartbeat(self.worker_id)

    def test_shutdown_only_withdraws_own_member_and_contract_versions_are_isolated(self):
        client = Mock()
        with patch.object(readiness, "redis_client", return_value=client):
            readiness.withdraw_study_worker_heartbeat(self.worker_id)
            old_key = client.zrem.call_args.args[0]
            self.assertEqual(client.zrem.call_args.args[1:], (self.worker_id,))
            client.delete.assert_not_called()
            with patch.object(readiness, "WORKER_CONTRACT", "study-consumer.future"):
                readiness.withdraw_study_worker_heartbeat(self.worker_id)
            self.assertNotEqual(old_key, client.zrem.call_args.args[0])
        with self.assertRaises(ValueError):
            readiness.withdraw_study_worker_heartbeat("*")

    def test_namespace_separates_database_and_survives_credential_rotation(self):
        with patch.dict(self.app.config, SQLALCHEMY_DATABASE_URI="mysql+pymysql://reader:secret@localhost/db_one"):
            first = study_queue_prefix()
        with patch.dict(self.app.config, SQLALCHEMY_DATABASE_URI="mysql+pymysql://writer:rotated@localhost/db_one"):
            self.assertEqual(first, study_queue_prefix())
        with patch.dict(self.app.config, SQLALCHEMY_DATABASE_URI="mysql+pymysql://reader:secret@localhost/db_two"):
            self.assertNotEqual(first, study_queue_prefix())
        self.assertNotIn("secret", first)
        with patch.dict(self.app.config, STUDY_QUEUE_NAMESPACE="bad:* namespace"):
            with self.assertRaises(ValueError):
                study_queue_prefix()

    def test_local_fallback_queue_locks_markers_and_cleanup_are_namespace_scoped(self):
        for namespace in ("first", "second"):
            with patch.dict(self.app.config, STUDY_QUEUE_NAMESPACE=namespace):
                clear_study_queue()
                enqueue_study_batch({"batch_id": namespace})
                self.assertIsNotNone(acquire_batch_lock("same-batch"))
                mark_batch_processed("same-batch")
                push_to_dlq({"batch_id": namespace}, "test")
        with patch.dict(self.app.config, STUDY_QUEUE_NAMESPACE="first"):
            clear_study_queue()
            self.assertIsNone(pop_study_batch(timeout=0))
            self.assertFalse(is_batch_processed("same-batch"))
        with patch.dict(self.app.config, STUDY_QUEUE_NAMESPACE="second"):
            self.assertEqual(pop_study_batch(timeout=0)["batch_id"], "second")
            self.assertTrue(is_batch_processed("same-batch"))
            self.assertIsNone(acquire_batch_lock("same-batch"))
            self.assertEqual(get_dlq_length(), 1)
            clear_study_queue()

    def test_redis_queue_and_locks_use_the_same_scoped_prefix(self):
        client = Mock()
        client.lpop.return_value = '[]'
        with patch("app.services.study_queue_service.redis_client", return_value=client):
            enqueue_study_batch({"batch_id": "test"})
            self.assertEqual(client.rpush.call_args.args[0], study_queue_key("queue"))
            self.assertIsNone(pop_study_batch(timeout=0))
            acquire_batch_lock("test")
            self.assertEqual(client.set.call_args.args[0], study_queue_key("lock:batch:test"))


if __name__ == "__main__":
    unittest.main()
