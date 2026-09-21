"""P5 migration 43 admits NOTE without enrolling learners implicitly."""

from __future__ import annotations

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from sqlalchemy.exc import IntegrityError

from app import create_app
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.user import User


migration = importlib.import_module(
    "migrations.versions.20260921_000043_admit_note_authority_enrollment"
)


class StudyAuthorityNoteEnrollmentTests(unittest.TestCase):
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
        user = User(email="note-mode@example.test", username="note-mode")
        db.session.add(user)
        db.session.commit()
        self.user_id = int(user.id)

    def tearDown(self):
        op._proxy = None
        db.session.remove()
        db.drop_all()
        self.context.pop()

    @staticmethod
    def _bind(connection) -> None:
        op._proxy = Operations(MigrationContext.configure(connection))

    def test_upgrade_is_idempotent_and_creates_no_enrollment(self):
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.upgrade()
            migration.upgrade()
        self.assertEqual(StudyAuthorityEnrollment.query.count(), 0)

    def test_note_requires_positive_epoch_and_unknown_mode_is_rejected(self):
        now = datetime(2026, 9, 21)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=self.user_id,
                mode_code="NOTE",
                epoch=1,
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()
        self.assertEqual(StudyAuthorityEnrollment.query.one().mode_code, "NOTE")

        db.session.delete(StudyAuthorityEnrollment.query.one())
        db.session.commit()
        for mode, epoch in (("NOTE", 0), ("UNKNOWN", 1)):
            with self.subTest(mode=mode, epoch=epoch):
                db.session.add(
                    StudyAuthorityEnrollment(
                        learner_user_id=self.user_id,
                        mode_code=mode,
                        epoch=epoch,
                        created_at=now,
                        updated_at=now,
                    )
                )
                with self.assertRaises(IntegrityError):
                    db.session.commit()
                db.session.rollback()

    def test_downgrade_refuses_while_note_rows_exist(self):
        now = datetime(2026, 9, 21)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=self.user_id,
                mode_code="NOTE",
                epoch=2,
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()
        with db.engine.begin() as connection:
            self._bind(connection)
            with self.assertRaisesRegex(RuntimeError, "NOTE rows exist"):
                migration.downgrade()

    def test_empty_note_cohort_can_downgrade_and_reupgrade(self):
        now = datetime(2026, 9, 21)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=self.user_id,
                mode_code="LEGACY",
                epoch=0,
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()
        with db.engine.begin() as connection:
            self._bind(connection)
            migration.downgrade()
            migration.upgrade()
        row = db.session.get(StudyAuthorityEnrollment, self.user_id)
        self.assertEqual(row.mode_code, "LEGACY")


if __name__ == "__main__":
    unittest.main()
