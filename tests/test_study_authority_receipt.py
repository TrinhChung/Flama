"""P5-05 durable NOTE command receipt schema contract."""

from __future__ import annotations

import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from models import db
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt


migration = importlib.import_module(
    "migrations.versions.20260921_000041_add_study_authority_command_receipts"
)


class StudyAuthorityReceiptSchemaTests(unittest.TestCase):
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

    def test_metadata_declares_receipt_identity_and_evidence_links(self):
        table = StudyAuthorityCommandReceipt.__table__
        self.assertEqual(
            {item.target_fullname for item in table.c.subject_id.foreign_keys},
            {"study_progress_subjects.id"},
        )
        self.assertEqual(
            {item.target_fullname for item in table.c.review_event_id.foreign_keys},
            {"review_events.id"},
        )
        self.assertEqual(
            {item.target_fullname for item in table.c.history_fact_id.foreign_keys},
            {"study_progress_history_facts.id"},
        )
        unique_names = {
            constraint.name
            for constraint in table.constraints
            if isinstance(constraint, sa.UniqueConstraint)
        }
        self.assertEqual(
            unique_names,
            {
                "uq_study_authority_receipt_operation",
                "uq_study_authority_receipt_event",
                "uq_study_authority_receipt_history",
            },
        )

    def test_upgrade_is_idempotent_and_matches_metadata_contract(self):
        table = StudyAuthorityCommandReceipt.__table__
        with db.engine.begin() as connection:
            table.drop(bind=connection, checkfirst=True)
            self._bind_operations(connection)
            migration.upgrade()
            migration.upgrade()
            self.assertTrue(sa.inspect(connection).has_table(table.name))
            migration._assert_table_contract(connection, table)

    def test_upgrade_rejects_incompatible_preexisting_table(self):
        table = StudyAuthorityCommandReceipt.__table__
        with db.engine.begin() as connection:
            table.drop(bind=connection, checkfirst=True)
            connection.exec_driver_sql(
                "CREATE TABLE study_authority_command_receipts "
                "(id INTEGER PRIMARY KEY)"
            )
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                migration.upgrade()

    def test_empty_downgrade_only(self):
        with db.engine.begin() as connection:
            self._bind_operations(connection)
            migration.downgrade()
            self.assertFalse(
                sa.inspect(connection).has_table(
                    StudyAuthorityCommandReceipt.__tablename__
                )
            )

    def test_downgrade_refuses_nonempty_receipt_table(self):
        table = StudyAuthorityCommandReceipt.__table__
        with db.engine.begin() as connection:
            table.drop(bind=connection, checkfirst=True)
            connection.exec_driver_sql(
                "CREATE TABLE study_authority_command_receipts "
                "(id INTEGER PRIMARY KEY)"
            )
            connection.exec_driver_sql(
                "INSERT INTO study_authority_command_receipts (id) VALUES (1)"
            )
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "prohibited"):
                migration.downgrade()
            self.assertTrue(
                sa.inspect(connection).has_table(
                    StudyAuthorityCommandReceipt.__tablename__
                )
            )


if __name__ == "__main__":
    unittest.main()
