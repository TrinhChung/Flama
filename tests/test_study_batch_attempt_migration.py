"""P5 durable batch retry counter expands safely and guards downgrade."""

from __future__ import annotations

from datetime import datetime, timedelta
import importlib
import unittest
from uuid import uuid4

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from models import db
from models.study_session import StudySession
from models.study_session_batch import StudySessionBatch
from models.user import User


migration = importlib.import_module(
    "migrations.versions.20260925_000045_add_study_batch_attempt_count"
)


class StudyBatchAttemptMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def _bind(connection):
        op._proxy = Operations(MigrationContext.configure(connection))

    def _column(self):
        return next(
            (
                row for row in sa.inspect(db.engine).get_columns(migration.TABLE_NAME)
                if row["name"] == migration.COLUMN_NAME
            ),
            None,
        )

    def test_additive_upgrade_preserves_rows_and_empty_downgrade(self):
        user = User(username="old-batch", email="old-batch@example.test")
        db.session.add(user)
        db.session.flush()
        now = datetime(2026, 9, 25)
        session = StudySession(
            user_id=user.id,
            scope_id="1",
            snapshot_hash="snapshot",
            token_hash="token",
            expires_at=now + timedelta(hours=1),
        )
        db.session.add(session)
        db.session.commit()
        user_id, session_id = user.id, session.id
        db.session.rollback()
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.downgrade()
            migration.downgrade()
        self.assertIsNone(self._column())
        with db.engine.begin() as connection:
            connection.execute(
                sa.text(
                    "INSERT INTO study_session_batches "
                    "(id, session_id, user_id, batch_id, batch_sequence, "
                    "event_count, status, is_final, request_hash, enqueued_at, "
                    "created_at, updated_at) VALUES "
                    "(:id, :session_id, :user_id, 'old-completed', 1, 0, "
                    "'completed', 0, 'old-hash', :now, :now, :now)"
                ),
                {
                    "id": str(uuid4()),
                    "session_id": session_id,
                    "user_id": user_id,
                    "now": now,
                },
            )
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.upgrade()
            migration.upgrade()
        column = self._column()
        self.assertIsNotNone(column)
        self.assertFalse(column["nullable"])
        with db.engine.connect() as connection:
            attempts = connection.execute(
                sa.text(
                    "SELECT attempt_count FROM study_session_batches "
                    "WHERE batch_id = 'old-completed'"
                )
            ).scalar_one()
        self.assertEqual(attempts, 0)

    def test_downgrade_refuses_in_flight_or_counted_attempt(self):
        user = User(username="batch-migration", email="batch-migration@example.test")
        db.session.add(user)
        db.session.flush()
        now = datetime(2026, 9, 25)
        session = StudySession(
            user_id=user.id,
            scope_id="1",
            snapshot_hash="snapshot",
            token_hash="token",
            expires_at=now + timedelta(hours=1),
        )
        db.session.add(session)
        db.session.flush()
        batch = StudySessionBatch(
            session_id=session.id,
            user_id=user.id,
            batch_id="retry-test",
            status="enqueued",
            request_hash="hash",
            payload_json="{}",
        )
        db.session.add(batch)
        db.session.commit()
        with db.engine.begin() as connection:
            self._bind(connection)
            with self.assertRaisesRegex(RuntimeError, "admissions or attempts remain"):
                migration.downgrade()
        batch.status = "completed"
        batch.attempt_count = 1
        db.session.commit()
        with db.engine.begin() as connection:
            self._bind(connection)
            with self.assertRaisesRegex(RuntimeError, "admissions or attempts remain"):
                migration.downgrade()
        self.assertIsNotNone(self._column())

    def test_upgrade_rejects_existing_counter_without_zero_default(self):
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.downgrade()
            connection.execute(sa.text(
                "ALTER TABLE study_session_batches "
                "ADD COLUMN attempt_count INTEGER NOT NULL DEFAULT 1"
            ))
            with self.assertRaisesRegex(RuntimeError, "incompatible contract"):
                migration.upgrade()


if __name__ == "__main__":
    unittest.main()
