"""P5-05 immutable Study Session v4 authority-pin schema contract."""

from __future__ import annotations

import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from models import db
from models.study_session_authority_pin import StudySessionAuthorityPin


migration = importlib.import_module(
    "migrations.versions.20260921_000042_add_study_session_authority_pins"
)


class StudySessionAuthorityPinSchemaTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
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

    @staticmethod
    def _bind_operations(connection) -> None:
        op._proxy = Operations(MigrationContext.configure(connection))

    def test_metadata_keeps_note_cas_separate_from_card_revision(self):
        table = StudySessionAuthorityPin.__table__
        self.assertNotIn("base_progress_revision", table.c)
        self.assertEqual(
            {item.target_fullname for item in table.c.session_card_id.foreign_keys},
            {"study_session_cards.id"},
        )
        self.assertEqual(
            {item.target_fullname for item in table.c.subject_id.foreign_keys},
            {"study_progress_subjects.id"},
        )
        self.assertEqual(
            {
                "logical_note_key",
                "subject_generation",
                "base_authority_revision",
                "base_semantic_state_hash",
                "enrollment_epoch",
            }
            - set(table.c.keys()),
            set(),
        )

    def test_upgrade_is_idempotent_and_matches_metadata_contract(self):
        table = StudySessionAuthorityPin.__table__
        with db.engine.begin() as connection:
            table.drop(bind=connection, checkfirst=True)
            self._bind_operations(connection)
            migration.upgrade()
            migration.upgrade()
            self.assertTrue(sa.inspect(connection).has_table(table.name))
            migration._assert_table_contract(connection, table)

    def test_upgrade_rejects_incompatible_preexisting_table(self):
        table = StudySessionAuthorityPin.__table__
        with db.engine.begin() as connection:
            table.drop(bind=connection, checkfirst=True)
            connection.exec_driver_sql(
                "CREATE TABLE study_session_authority_pins "
                "(session_card_id INTEGER PRIMARY KEY)"
            )
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                migration.upgrade()

    def test_create_all_is_inert_and_empty_downgrade_removes_only_pin_table(self):
        self.assertEqual(StudySessionAuthorityPin.query.count(), 0)
        with db.engine.begin() as connection:
            self._bind_operations(connection)
            migration.downgrade()
            inspector = sa.inspect(connection)
            self.assertFalse(inspector.has_table(StudySessionAuthorityPin.__tablename__))
            self.assertTrue(inspector.has_table("study_sessions"))
            self.assertTrue(inspector.has_table("study_session_cards"))

    def test_downgrade_refuses_nonempty_pin_table(self):
        table = StudySessionAuthorityPin.__table__
        with db.engine.begin() as connection:
            table.drop(bind=connection, checkfirst=True)
            connection.exec_driver_sql(
                "CREATE TABLE study_session_authority_pins "
                "(session_card_id INTEGER PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO study_session_authority_pins (session_card_id) VALUES (1)"
            )
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "prohibited"):
                migration.downgrade()
            self.assertTrue(sa.inspect(connection).has_table(table.name))


if __name__ == "__main__":
    unittest.main()
