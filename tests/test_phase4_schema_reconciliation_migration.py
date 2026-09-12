"""Tests for the schema reconciliation that closes P4-01 drift."""

from __future__ import annotations

import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from app.services.study_phase4_preflight_service import (
    _repository_inventory,
    _schema_inventory,
)
from models import db


migration = importlib.import_module(
    "migrations.versions.20260913_000038_reconcile_phase4_preflight_schema"
)


class Phase4SchemaReconciliationMigrationTests(unittest.TestCase):
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

    def test_upgrade_repairs_legacy_marketplace_shape(self):
        with self.app.app_context():
            with db.engine.begin() as connection:
                self._bind_operations(connection)
                op.drop_index(
                    "ix_deck_marketplace_items_student_offer_mode",
                    table_name="deck_marketplace_items",
                )
                with op.batch_alter_table("deck_marketplace_items") as batch_op:
                    batch_op.alter_column(
                        "taxonomy_metadata",
                        existing_type=sa.JSON(),
                        existing_nullable=False,
                        nullable=True,
                    )
                    batch_op.alter_column(
                        "student_offer_mode",
                        existing_type=sa.String(length=32),
                        existing_nullable=False,
                        type_=sa.String(length=16),
                    )

                migration.upgrade()
                migration.upgrade()

                inspector = sa.inspect(connection)
                columns = {
                    row["name"]: row
                    for row in inspector.get_columns("deck_marketplace_items")
                }
                self.assertFalse(columns["taxonomy_metadata"]["nullable"])
                self.assertEqual(
                    columns["student_offer_mode"]["type"].length,
                    32,
                )
                self.assertIn(
                    "ix_deck_marketplace_items_student_offer_mode",
                    {
                        row["name"]
                        for row in inspector.get_indexes(
                            "deck_marketplace_items"
                        )
                    },
                )

            schema = _schema_inventory(_repository_inventory())
            self.assertEqual(schema["drift"], [])

    def test_upgrade_fails_before_shrinking_unsafe_student_offer_column(self):
        with self.app.app_context(), db.engine.begin() as connection:
            self._bind_operations(connection)
            with op.batch_alter_table("deck_marketplace_items") as batch_op:
                batch_op.alter_column(
                    "student_offer_mode",
                    existing_type=sa.String(length=32),
                    existing_nullable=False,
                    type_=sa.String(length=64),
                )

            with self.assertRaisesRegex(RuntimeError, "cannot be safely normalized"):
                migration.upgrade()

            columns = {
                row["name"]: row
                for row in sa.inspect(connection).get_columns(
                    "deck_marketplace_items"
                )
            }
            self.assertEqual(columns["student_offer_mode"]["type"].length, 64)

    def test_downgrade_is_non_destructive(self):
        with self.app.app_context(), db.engine.begin() as connection:
            self._bind_operations(connection)
            migration.downgrade()

            self.assertTrue(
                sa.inspect(connection).has_table("deck_marketplace_items")
            )


if __name__ == "__main__":
    unittest.main()
