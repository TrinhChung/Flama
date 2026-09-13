"""Schema, migration, default-off and first-create contracts for P4-06."""

from __future__ import annotations

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from app import create_app
from app.repositories.study_progress_shadow_repository import (
    StaleStudyProgressFenceError,
    assert_subject_finalization_fence,
    ensure_and_lock_subject,
)
from models import db
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_types import MYSQL_PARENT_COLLATIONS_INFO_KEY
from models.user import User


migration = importlib.import_module(
    "migrations.versions.20260913_000039_add_study_progress_shadow_schema"
)


class StudyProgressShadowSchemaTests(unittest.TestCase):
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
        context = MigrationContext.configure(connection)
        op._proxy = Operations(context)

    @staticmethod
    def _drop_shadow_tables(connection) -> None:
        connection.exec_driver_sql("PRAGMA foreign_keys=OFF")
        for table in reversed(migration.TARGET_TABLES):
            table.drop(bind=connection, checkfirst=True)
        connection.exec_driver_sql("PRAGMA foreign_keys=ON")

    def test_metadata_contains_exact_additive_table_set(self):
        expected = {table.name for table in migration.TARGET_TABLES}
        actual = {
            name for name in db.metadata.tables if name.startswith("study_progress_")
        }
        self.assertEqual(actual, expected)
        self.assertEqual(len(actual), 10)

    def test_live_string_fks_declare_parent_collation_sources(self):
        expected = {
            "study_progress_subjects": {
                "live_note_id": ("notes", "id"),
            },
            "study_progress_contributors": {
                "live_card_id": ("cards", "id"),
            },
        }
        actual = {
            table.name: table.info.get(MYSQL_PARENT_COLLATIONS_INFO_KEY)
            for table in migration.TARGET_TABLES
            if MYSQL_PARENT_COLLATIONS_INFO_KEY in table.info
        }
        self.assertEqual(actual, expected)

    def test_upgrade_creates_missing_tables_and_revalidates_idempotently(self):
        with db.engine.begin() as connection:
            self._drop_shadow_tables(connection)
            self._bind_operations(connection)
            migration.upgrade()
            migration.upgrade()
            inspector = sa.inspect(connection)
            for table in migration.TARGET_TABLES:
                self.assertTrue(inspector.has_table(table.name))
                self.assertEqual(
                    migration._table_contract_issues(
                        inspector, table, connection.dialect
                    ),
                    [],
                )

    def test_upgrade_fails_closed_for_incompatible_create_all_history(self):
        with db.engine.begin() as connection:
            self._drop_shadow_tables(connection)
            connection.exec_driver_sql(
                "CREATE TABLE study_progress_subjects (id INTEGER PRIMARY KEY)"
            )
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                migration.upgrade()

    def test_empty_downgrade_drops_all_tables(self):
        with db.engine.begin() as connection:
            self._bind_operations(connection)
            migration.downgrade()
            inspector = sa.inspect(connection)
            for table in migration.TARGET_TABLES:
                self.assertFalse(inspector.has_table(table.name))

    def test_nonempty_downgrade_fails_without_dropping_evidence(self):
        db.session.add(
            StudyProgressBackfillRun(
                id="00000000-0000-0000-0000-000000000001",
                run_kind="FULL",
                status_code="PENDING",
                repository_commit="0" * 40,
                database_head="20260913_000039",
                audit_schema_version="phase4-preflight.v1",
                mapper_version="card-progress-legacy-anki.v1",
                state_schema_version="anki-card-state.v1",
                projection_version="availability-anchor.v1",
                contract_hash=b"c" * 32,
                observed_at=datetime(2026, 9, 13),
                started_at=datetime(2026, 9, 13),
                updated_at=datetime(2026, 9, 13),
            )
        )
        db.session.commit()
        with db.engine.begin() as connection:
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "prohibited"):
                migration.downgrade()
            self.assertTrue(
                sa.inspect(connection).has_table("study_progress_backfill_runs")
            )

    def test_all_three_flags_default_off_and_startup_creates_no_rows(self):
        for name in (
            "STUDY_PROGRESS_SHADOW_WRITE_ENABLED",
            "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED",
            "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED",
        ):
            self.assertIs(self.app.config[name], False)
        self.assertNotIn("STUDY_PROGRESS_SHADOW_READ_AUTHORITY", self.app.config)
        for table in migration.TARGET_TABLES:
            self.assertEqual(
                db.session.execute(
                    sa.select(sa.func.count()).select_from(table)
                ).scalar_one(),
                0,
            )

    def test_subject_first_create_is_unique_locked_and_has_no_self_commit(self):
        user = User(email="p4@example.test", username="p4-user")
        db.session.add(user)
        db.session.commit()

        now = datetime(2026, 9, 13, 12)
        first = ensure_and_lock_subject(
            db.session,
            learner_user_id=user.id,
            logical_note_key="note-a",
            live_note_id=None,
            now_utc=now,
        )
        second = ensure_and_lock_subject(
            db.session,
            learner_user_id=user.id,
            logical_note_key="note-a",
            live_note_id=None,
            now_utc=now,
        )
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.subject_generation, 1)
        self.assertEqual(first.mirror_revision, 0)
        self.assertEqual(first.status_code, "NO_CURRENT_PROGRESS")
        assert_subject_finalization_fence(
            first, expected_generation=1, expected_mirror_revision=0
        )
        with self.assertRaises(StaleStudyProgressFenceError):
            assert_subject_finalization_fence(
                first, expected_generation=1, expected_mirror_revision=1
            )
        db.session.rollback()

        count = db.session.execute(
            sa.select(sa.func.count()).select_from(
                migration.StudyProgressSubject.__table__
            )
        ).scalar_one()
        self.assertEqual(count, 0)


if __name__ == "__main__":
    unittest.main()
