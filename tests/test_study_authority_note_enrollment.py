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
from app.services.study_authority_enrollment_service import (
    stage_legacy_authority_enrollment,
    stage_note_authority_enrollment,
)
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

    def test_empty_learner_can_enroll_and_roll_back_without_subjects(self):
        enrolled = stage_note_authority_enrollment(
            db.session,
            learner_user_id=self.user_id,
            now_utc=datetime(2026, 9, 22, 8, 0, 0),
        )
        self.assertEqual(enrolled.mode_code, "NOTE")
        self.assertEqual(enrolled.epoch, 1)
        self.assertEqual(enrolled.subject_count, 0)
        self.assertEqual(enrolled.card_count, 0)
        db.session.commit()

        rolled_back = stage_legacy_authority_enrollment(
            db.session,
            learner_user_id=self.user_id,
            now_utc=datetime(2026, 9, 22, 8, 1, 0),
        )
        self.assertEqual(rolled_back.previous_mode, "NOTE")
        self.assertEqual(rolled_back.mode_code, "LEGACY")
        self.assertEqual(rolled_back.epoch, 2)
        self.assertEqual(rolled_back.subject_count, 0)
        self.assertEqual(rolled_back.card_count, 0)
        db.session.commit()

        enrollment = db.session.get(StudyAuthorityEnrollment, self.user_id)
        self.assertEqual(enrollment.mode_code, "LEGACY")
        self.assertEqual(enrollment.epoch, 2)


if __name__ == "__main__":
    unittest.main()
