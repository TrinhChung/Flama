"""P5-04 learner authority route must fence and fail closed."""

from __future__ import annotations

from datetime import datetime
import unittest

from sqlalchemy import text

from app import create_app
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    _decode_route,
    lock_study_authority_route,
)
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.user import User


class StudyAuthorityRepositoryTests(unittest.TestCase):
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
        user = User(email="authority@example.test", username="authority-user")
        db.session.add(user)
        db.session.commit()
        self.user_id = int(user.id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_absent_enrollment_requires_explicit_migration(self):
        with self.assertRaises(StudyAuthorityFenceError) as failure:
            lock_study_authority_route(db.session, learner_user_id=self.user_id)
        self.assertEqual(failure.exception.code, "STUDY_AUTHORITY_MIGRATION_REQUIRED")

    def test_persisted_legacy_enrollment_requires_explicit_migration(self):
        now = datetime(2026, 9, 21)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=self.user_id,
                mode_code="LEGACY",
                epoch=4,
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()
        with self.assertRaises(StudyAuthorityFenceError) as failure:
            lock_study_authority_route(db.session, learner_user_id=self.user_id)
        self.assertEqual(failure.exception.code, "STUDY_AUTHORITY_MIGRATION_REQUIRED")

    def test_pending_insert_is_not_autoflushed_before_fence(self):
        pending = User(email="pending@example.test", username="pending-user")
        db.session.add(pending)
        with self.assertRaises(StudyAuthorityFenceError):
            lock_study_authority_route(db.session, learner_user_id=self.user_id)
        self.assertIsNone(pending.id)

    def test_missing_or_invalid_learner_fails_closed(self):
        cases = ((0, "INVALID_LEARNER_ID"), (999999, "LEARNER_NOT_FOUND"))
        for learner_id, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(StudyAuthorityFenceError) as failure:
                    lock_study_authority_route(
                        db.session, learner_user_id=learner_id
                    )
                self.assertEqual(failure.exception.code, code)

    def test_note_unknown_mode_and_bad_epoch_fail_closed(self):
        cases = (
            ("NOTE", 0, "INVALID_AUTHORITY_EPOCH"),
            ("UNKNOWN", 1, "INVALID_AUTHORITY_MODE"),
            ("NOTE", -1, "INVALID_AUTHORITY_EPOCH"),
        )
        for mode_code, epoch, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(StudyAuthorityFenceError) as failure:
                    _decode_route(
                        learner_user_id=self.user_id,
                        mode_code=mode_code,
                        epoch=epoch,
                        persisted=True,
                    )
                self.assertEqual(failure.exception.code, code)

    def test_note_enrollment_is_the_only_runtime_authority(self):
        now = "2026-09-21 00:00:00.000000"
        db.session.execute(text("PRAGMA ignore_check_constraints = ON"))
        db.session.execute(
            text(
                "INSERT INTO study_authority_enrollments "
                "(learner_user_id, mode_code, epoch, created_at, updated_at) "
                "VALUES (:user_id, 'NOTE', 1, :now, :now)"
            ),
            {"user_id": self.user_id, "now": now},
        )
        db.session.commit()
        route = lock_study_authority_route(db.session, learner_user_id=self.user_id)
        self.assertEqual((route.mode_code, route.epoch), ("NOTE", 1))

        route = lock_study_authority_route(
            db.session,
            learner_user_id=self.user_id,
            allow_note_authority=True,
        )
        self.assertEqual(route.mode_code, "NOTE")
        self.assertEqual(route.epoch, 1)
        self.assertTrue(route.persisted)

    def test_note_opt_in_still_rejects_non_positive_epoch(self):
        with self.assertRaises(StudyAuthorityFenceError) as failure:
            _decode_route(
                learner_user_id=self.user_id,
                mode_code="NOTE",
                epoch=0,
                persisted=True,
                allow_note_authority=True,
            )
        self.assertEqual(failure.exception.code, "INVALID_AUTHORITY_EPOCH")


if __name__ == "__main__":
    unittest.main()
