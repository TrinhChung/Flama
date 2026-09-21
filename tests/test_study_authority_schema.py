"""P5-02 additive authority storage must remain inert until the cutover."""

from __future__ import annotations

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError

from app import create_app
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.user import User


migration = importlib.import_module(
    "migrations.versions.20260921_000040_add_study_authority_fence"
)


class StudyAuthoritySchemaTests(unittest.TestCase):
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

    @staticmethod
    def _drop_authority_tables(connection) -> None:
        for table in reversed(migration.TARGET_TABLES):
            table.drop(bind=connection, checkfirst=True)

    def test_metadata_declares_separate_enrollment_and_subject_token(self):
        self.assertEqual(
            {table.name for table in migration.TARGET_TABLES},
            {"study_authority_enrollments", "study_authority_subject_tokens"},
        )
        self.assertEqual(
            next(iter(StudyAuthorityEnrollment.__table__.c.learner_user_id.foreign_keys)).target_fullname,
            "users.id",
        )
        self.assertEqual(
            next(iter(StudyAuthoritySubjectToken.__table__.c.subject_id.foreign_keys)).target_fullname,
            "study_progress_subjects.id",
        )

    def test_upgrade_from_pre_p5_schema_and_idempotent_create_all_history(self):
        with db.engine.begin() as connection:
            self._drop_authority_tables(connection)
            self._bind_operations(connection)
            migration.upgrade()
            migration.upgrade()
            inspector = sa.inspect(connection)
            for table in migration.TARGET_TABLES:
                self.assertTrue(inspector.has_table(table.name))
                migration._assert_table_contract(connection, table)

    def test_upgrade_rejects_incompatible_preexisting_table(self):
        with db.engine.begin() as connection:
            self._drop_authority_tables(connection)
            connection.exec_driver_sql(
                "CREATE TABLE study_authority_enrollments (learner_user_id INTEGER PRIMARY KEY)"
            )
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "does not match"):
                migration.upgrade()

    def test_schema_creates_no_enrollments_or_tokens_and_cannot_store_note_mode(self):
        with db.engine.begin() as connection:
            self._drop_authority_tables(connection)
            self._bind_operations(connection)
            migration.upgrade()
        db.session.add(User(email="p5@example.test", username="p5-user"))
        db.session.commit()
        self.assertEqual(StudyAuthorityEnrollment.query.count(), 0)
        self.assertEqual(StudyAuthoritySubjectToken.query.count(), 0)

        user = User.query.filter_by(username="p5-user").one()
        now = datetime(2026, 9, 21)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=user.id,
                mode_code="NOTE",
                epoch=1,
                created_at=now,
                updated_at=now,
            )
        )
        with self.assertRaises(IntegrityError):
            db.session.commit()
        db.session.rollback()
        self.assertEqual(StudyAuthorityEnrollment.query.count(), 0)

    def test_empty_downgrade_only(self):
        with db.engine.begin() as connection:
            self._bind_operations(connection)
            migration.downgrade()
            inspector = sa.inspect(connection)
            for table in migration.TARGET_TABLES:
                self.assertFalse(inspector.has_table(table.name))

    def test_downgrade_refuses_to_drop_persisted_enrollment(self):
        user = User(email="p5@example.test", username="p5-user")
        db.session.add(user)
        db.session.flush()
        now = datetime(2026, 9, 21)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=user.id,
                mode_code="LEGACY",
                epoch=0,
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()
        with db.engine.begin() as connection:
            self._bind_operations(connection)
            with self.assertRaisesRegex(RuntimeError, "prohibited"):
                migration.downgrade()
            self.assertTrue(sa.inspect(connection).has_table("study_authority_enrollments"))


if __name__ == "__main__":
    unittest.main()
