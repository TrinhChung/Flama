"""Code rollback requires quiesced writers and no pending/NOTE authority work."""

from contextlib import redirect_stdout
from datetime import datetime
import io
import json
import unittest
from unittest.mock import patch

from sqlalchemy import event, text

from app.services.study_deploy_safety_service import inspect_study_code_rollback
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.user import User
import study_worker


class StudyDeploySafetyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = study_worker.create_worker_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "REDIS_URL": "", "STUDY_QUEUE_NAMESPACE": "", "WTF_CSRF_ENABLED": False,
        })

    def setUp(self):
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _seed(self, *, mode="LEGACY", status="completed"):
        now = datetime(2026, 9, 26)
        user = User(username="rollback-check", email="rollback-check@example.test")
        db.session.add(user)
        db.session.flush()
        db.session.add(StudyAuthorityEnrollment(learner_user_id=user.id, mode_code=mode, epoch=1, created_at=now, updated_at=now))
        session = StudySession(user_id=user.id, scope_id="1", snapshot_hash="snapshot", token_hash="token", expires_at=now)
        db.session.add(session)
        db.session.flush()
        db.session.add(StudySessionBatch(session_id=session.id, user_id=user.id, batch_id="probe", request_hash="hash", status=status))
        db.session.commit()

    def test_missing_quiescence_assertion_blocks_without_reading_or_mutating(self):
        with patch.object(db.session, "execute") as execute:
            result = inspect_study_code_rollback()
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["reasons"], ["WRITERS_NOT_QUIESCED"])
        execute.assert_not_called()

    def test_quiesced_empty_database_passes_with_selects_only(self):
        statements = []
        def capture(_connection, _cursor, statement, *_args):
            statements.append(statement)
        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            result = inspect_study_code_rollback(writers_quiesced=True)
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(result["status"], "PASS")
        self.assertEqual(result["reasons"], [])
        self.assertEqual(len(statements), 2)
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT") for sql in statements))
        self.assertFalse(db.session().in_transaction())

    def test_note_enrollment_blocks_without_automatically_rolling_back_authority(self):
        self._seed(mode="NOTE")
        result = inspect_study_code_rollback(writers_quiesced=True)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["reasons"], ["NOTE_AUTHORITY_REQUIRES_EXPLICIT_ROLLBACK"])
        self.assertEqual(StudyAuthorityEnrollment.query.one().mode_code, "NOTE")

    def test_all_unfinished_or_unknown_batch_statuses_block(self):
        self._seed()
        for status in ("enqueued", "processing", "unknown"):
            with self.subTest(status=status):
                StudySessionBatch.query.one().status = status
                db.session.commit()
                result = inspect_study_code_rollback(writers_quiesced=True)
                self.assertEqual(result["status"], "BLOCK")
                self.assertEqual(result["reasons"], ["UNFINISHED_STUDY_BATCHES"])
                batch = StudySessionBatch.query.one()
                self.assertEqual(batch.status, status)
                self.assertEqual(batch.attempt_count, 0)

    def test_terminal_legacy_work_can_roll_back_code(self):
        self._seed()
        for status in ("completed", "failed"):
            StudySessionBatch.query.one().status = status
            db.session.commit()
            self.assertEqual(inspect_study_code_rollback(writers_quiesced=True)["status"], "PASS")

    def test_schema_failure_is_unverified_not_safe_to_roll_back(self):
        db.session.execute(text("DROP TABLE study_session_batches"))
        db.session.commit()
        result = inspect_study_code_rollback(writers_quiesced=True)
        self.assertEqual(result["status"], "BLOCK")
        self.assertEqual(result["reasons"], ["STUDY_CODE_ROLLBACK_UNVERIFIED"])
        self.assertFalse(db.session().in_transaction())

    def test_caller_transaction_is_not_rolled_back(self):
        user = User(username="pending", email="pending@example.test")
        db.session.add(user)
        with self.assertRaisesRegex(RuntimeError, "transaction-neutral"):
            inspect_study_code_rollback(writers_quiesced=True)
        self.assertIn(user, db.session.new)

    def test_cli_emits_typed_verdict_exit_codes_and_never_starts_consumer(self):
        with patch.object(study_worker, "create_worker_app", return_value=self.app), patch.object(study_worker.logging, "basicConfig"), patch(
            "app.services.study_consumer_service.run_study_consumer",
        ) as run:
            for args, status, code in (
                (["--check-code-rollback"], "BLOCK", 1),
                (["--check-code-rollback", "--writers-quiesced"], "PASS", 0),
            ):
                output = io.StringIO()
                with redirect_stdout(output):
                    self.assertEqual(study_worker.main(args), code)
                self.assertEqual(json.loads(output.getvalue())["status"], status)
            run.assert_not_called()

    def test_readiness_cli_checks_pool_without_starting_consumer(self):
        with patch.object(study_worker, "create_worker_app", return_value=self.app), patch.object(study_worker.logging, "basicConfig"), patch(
            "app.services.study_consumer_service.run_study_consumer",
        ) as run:
            for ready, code in ((True, 0), (False, 1)):
                with patch("app.services.study_worker_readiness_service.has_ready_study_worker", return_value=ready) as check:
                    self.assertEqual(study_worker.main(["--check-ready"]), code)
                    check.assert_called_once_with("study-session.v4")
            run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
