"""New accounts start in NOTE authority only when the rollout flags allow it."""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app import create_app
from app.services import auth_service, google_auth_service
from app.services.study_authority_enrollment_service import (
    StudyAuthorityEnrollmentError,
)
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.user import User


class NewLearnerNoteEnrollmentTests(unittest.TestCase):
    def _make_app(self, **flags):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                **flags,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _register(self, name="learner"):
        return auth_service.register_user_and_commit(
            f"{name}@example.test", name, "Secret-pass-123"
        )

    def _mode(self, user_id):
        row = db.session.get(StudyAuthorityEnrollment, int(user_id))
        return None if row is None else (row.mode_code, int(row.epoch))

    def test_flag_off_keeps_legacy_default(self):
        self._make_app(STUDY_WIRE_V4_ENABLED=True)
        user = self._register()
        self.assertIsNone(self._mode(user.id))

    def test_registration_enrolls_note_when_enabled(self):
        self._make_app(
            STUDY_WIRE_V4_ENABLED=True,
            STUDY_NEW_LEARNER_NOTE_ENABLED=True,
        )
        user = self._register()
        self.assertEqual(self._mode(user.id), ("NOTE", 1))

    def test_requires_wire_v4_and_async_off(self):
        self._make_app(STUDY_NEW_LEARNER_NOTE_ENABLED=True)
        self.assertIsNone(self._mode(self._register("no-v4").id))
        self.app.config.update(
            STUDY_WIRE_V4_ENABLED=True, STUDY_ASYNC_BATCH_ENABLED=True
        )
        self.assertIsNone(self._mode(self._register("async-on").id))

    def test_refusal_keeps_account_created_on_legacy(self):
        self._make_app(
            STUDY_WIRE_V4_ENABLED=True,
            STUDY_NEW_LEARNER_NOTE_ENABLED=True,
        )
        refusal = StudyAuthorityEnrollmentError("SIMULATED", "refused")
        with patch(
            "app.services.study_authority_enrollment_service."
            "stage_note_authority_enrollment",
            side_effect=refusal,
        ), self.assertLogs(
            "app.services.study_authority_enrollment_service", level="WARNING"
        ):
            user = self._register()
        self.assertIsNotNone(db.session.get(User, user.id))
        self.assertIsNone(self._mode(user.id))

    def test_learners_cli_lists_ids_by_current_mode(self):
        self._make_app(STUDY_WIRE_V4_ENABLED=True)
        legacy = self._register("stays-legacy")
        self.app.config["STUDY_NEW_LEARNER_NOTE_ENABLED"] = True
        note = self._register("starts-note")
        runner = self.app.test_cli_runner()

        def ids(*args):
            result = runner.invoke(args=["study-authority-learners", *args])
            self.assertEqual(result.exit_code, 0, result.output)
            return [int(line) for line in result.output.split()]

        self.assertEqual(ids(), [legacy.id, note.id])
        self.assertEqual(ids("--mode", "LEGACY"), [legacy.id])
        self.assertEqual(ids("--mode", "note"), [note.id])

    def test_google_provisioning_enrolls_note_when_enabled(self):
        self._make_app(
            STUDY_WIRE_V4_ENABLED=True,
            STUDY_NEW_LEARNER_NOTE_ENABLED=True,
        )
        user, action = google_auth_service.resolve_or_create_user(
            {"sub": "g-sub-note-1", "email": "google-note@example.test"}
        )
        self.assertEqual(action, "created")
        self.assertEqual(self._mode(user.id), ("NOTE", 1))


if __name__ == "__main__":
    unittest.main()
