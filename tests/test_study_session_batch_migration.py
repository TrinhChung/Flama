"""Contract tests for the independent StudySessionBatch migration repair."""

from __future__ import annotations

import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from models import db


migration = importlib.import_module(
    "migrations.versions.20260913_000037_add_study_session_batches"
)


class StudySessionBatchMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
            }
        )
        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @staticmethod
    def _bind_operations(connection) -> None:
        context = MigrationContext.configure(connection)
        op._proxy = Operations(context)

    def test_upgrade_creates_missing_table_and_is_idempotent(self):
        with self.app.app_context(), db.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE study_session_batches")
            self._bind_operations(connection)

            migration.upgrade()
            migration.upgrade()

            inspector = sa.inspect(connection)
            self.assertTrue(inspector.has_table("study_session_batches"))
            self.assertEqual(
                migration._existing_contract_issues(inspector),
                [],
            )

    def test_upgrade_accepts_create_all_compatible_table(self):
        with self.app.app_context(), db.engine.begin() as connection:
            self._bind_operations(connection)

            migration.upgrade()

            inspector = sa.inspect(connection)
            self.assertEqual(
                migration._existing_contract_issues(inspector),
                [],
            )

    def test_upgrade_fails_closed_for_incompatible_existing_table(self):
        with self.app.app_context(), db.engine.begin() as connection:
            connection.exec_driver_sql("DROP TABLE study_session_batches")
            connection.exec_driver_sql(
                "CREATE TABLE study_session_batches (id VARCHAR(36) PRIMARY KEY)"
            )
            self._bind_operations(connection)

            with self.assertRaisesRegex(
                RuntimeError,
                "does not match the runtime contract",
            ):
                migration.upgrade()

    def test_upgrade_rejects_malformed_forward_attempt_column(self):
        with self.app.app_context(), db.engine.begin() as connection:
            connection.exec_driver_sql(
                "ALTER TABLE study_session_batches DROP COLUMN attempt_count"
            )
            connection.exec_driver_sql(
                "ALTER TABLE study_session_batches ADD COLUMN attempt_count TEXT"
            )
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "attempt_count"):
                migration.upgrade()

    def test_downgrade_preserves_table_and_rows(self):
        with self.app.app_context(), db.engine.begin() as connection:
            self._bind_operations(connection)
            connection.exec_driver_sql(
                "INSERT INTO study_session_batches ("
                "id, session_id, user_id, batch_id, batch_sequence, event_count, "
                "status, is_final, request_hash, enqueued_at, created_at, updated_at"
                ") VALUES ("
                "'batch-row', 'missing-session', 999, 'client-batch', 1, 0, "
                "'enqueued', 0, 'hash', CURRENT_TIMESTAMP, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP"
                ")"
            )

            migration.downgrade()

            self.assertTrue(sa.inspect(connection).has_table("study_session_batches"))
            count = connection.execute(
                sa.text("SELECT COUNT(*) FROM study_session_batches")
            ).scalar_one()
            self.assertEqual(count, 1)


if __name__ == "__main__":
    unittest.main()
