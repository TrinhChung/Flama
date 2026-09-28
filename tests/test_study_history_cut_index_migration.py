"""P5 history-cut index migration keeps NOTE lock ranges narrow."""

from __future__ import annotations

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.user import User


migration = importlib.import_module(
    "migrations.versions.20260924_000044_add_history_note_cut_index"
)


class StudyHistoryCutIndexMigrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "STARTUP_RUN_MAINTENANCE": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _index_columns(self):
        return next(
            (
                item["column_names"]
                for item in sa.inspect(db.engine).get_indexes(
                    StudyProgressHistoryFact.__tablename__
                )
                if item["name"] == migration.INDEX_NAME
            ),
            None,
        )

    @staticmethod
    def _bind(connection):
        op._proxy = Operations(MigrationContext.configure(connection))

    def test_upgrade_from_old_schema_and_empty_downgrade_are_idempotent(self):
        index = next(
            item
            for item in StudyProgressHistoryFact.__table__.indexes
            if item.name == migration.INDEX_NAME
        )
        index.drop(bind=db.engine)
        self.assertIsNone(self._index_columns())
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.upgrade()
            migration.upgrade()
        self.assertEqual(self._index_columns(), migration.INDEX_COLUMNS)
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.downgrade()
            migration.downgrade()
        self.assertIsNone(self._index_columns())

    def test_downgrade_refuses_active_note_cohort(self):
        user = User(username="history-index", email="history-index@example.test")
        db.session.add(user)
        db.session.flush()
        now = datetime(2026, 9, 24)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=user.id,
                mode_code="NOTE",
                epoch=1,
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()
        with db.engine.begin() as connection:
            self._bind(connection)
            with self.assertRaisesRegex(RuntimeError, "NOTE learners exist"):
                migration.downgrade()
        self.assertEqual(self._index_columns(), migration.INDEX_COLUMNS)


if __name__ == "__main__":
    unittest.main()
