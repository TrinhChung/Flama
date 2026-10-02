"""Every new account starts in NOTE authority; nothing creates LEGACY learners (P9-05c, D9-09)."""

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

REFUSAL_TARGET = (
    "app.services.study_authority_enrollment_service.stage_note_authority_enrollment"
)


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

    def test_registration_enrolls_note_whatever_the_flags(self):
        self._make_app()
        for index, flags in enumerate((
            {},
            {"STUDY_WIRE_V4_ENABLED": True, "STUDY_NEW_LEARNER_NOTE_ENABLED": True},
            {"STUDY_NEW_LEARNER_NOTE_ENABLED": False, "STUDY_WIRE_V4_ENABLED": False},
            {"STUDY_WIRE_V4_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": True},
        )):
            with self.subTest(flags=flags), patch.dict(self.app.config, flags):
                user = self._register(f"learner{index}")
                self.assertEqual(self._mode(user.id), ("NOTE", 1))

    def test_refused_enrollment_creates_no_account(self):
        self._make_app()
        with patch(REFUSAL_TARGET, side_effect=StudyAuthorityEnrollmentError("SIMULATED", "refused")), \
                self.assertLogs("app.services.study_authority_enrollment_service", level="WARNING"):
            with self.assertRaises(StudyAuthorityEnrollmentError):
                self._register()
        db.session.rollback()
        self.assertEqual(User.query.count(), 0)
        self.assertEqual(StudyAuthorityEnrollment.query.count(), 0)

    def test_signup_api_reports_refused_enrollment(self):
        self._make_app()
        client = self.app.test_client()
        with patch(REFUSAL_TARGET, side_effect=StudyAuthorityEnrollmentError("SIMULATED", "refused")), \
                self.assertLogs("app.services.study_authority_enrollment_service", level="WARNING"):
            response = client.post("/api/auth/register", json={
                "email": "api-learner@example.test", "username": "api_learner",
                "password": "Secret-pass-123", "confirm_password": "Secret-pass-123",
            })
        self.assertEqual(response.status_code, 503, response.get_json())
        self.assertEqual(response.get_json()["error"], "NOTE_ENROLLMENT_FAILED")
        self.assertEqual(User.query.count(), 0)

    def test_enrollment_cli_refuses_legacy(self):
        self._make_app()
        user = self._register()
        runner = self.app.test_cli_runner()
        for args in (["--mode", "LEGACY"], ["--mode", "legacy", "--apply"]):
            refused = runner.invoke(args=["study-authority-enrollment", "--user-id", str(user.id), *args])
            self.assertNotEqual(refused.exit_code, 0, refused.output)
            self.assertIn("LEGACY_ENROLLMENT_RETIRED", refused.output)
        self.assertEqual(self._mode(user.id), ("NOTE", 1))

    def test_learners_cli_lists_ids_by_current_mode(self):
        self._make_app()
        # Accounts created before NOTE-only signup have no enrollment row.
        legacy = User(username="stays-legacy", email="stays-legacy@example.test")
        legacy.set_password("Secret-pass-123")
        db.session.add(legacy)
        db.session.commit()
        note = self._register("starts-note")
        runner = self.app.test_cli_runner()

        def ids(*args):
            result = runner.invoke(args=["study-authority-learners", *args])
            self.assertEqual(result.exit_code, 0, result.output)
            return [int(line) for line in result.output.split()]

        self.assertEqual(ids(), [legacy.id, note.id])
        self.assertEqual(ids("--mode", "LEGACY"), [legacy.id])
        self.assertEqual(ids("--mode", "note"), [note.id])

    def test_google_provisioning_enrolls_note_whatever_the_flags(self):
        self._make_app(STUDY_WIRE_V4_ENABLED=False)
        user, action = google_auth_service.resolve_or_create_user(
            {"sub": "g-sub-note-1", "email": "google-note@example.test"}
        )
        self.assertEqual(action, "created")
        self.assertEqual(self._mode(user.id), ("NOTE", 1))

    def test_google_provisioning_refusal_creates_no_account(self):
        self._make_app()
        with patch(REFUSAL_TARGET, side_effect=StudyAuthorityEnrollmentError("SIMULATED", "refused")), \
                self.assertLogs("app.services.study_authority_enrollment_service", level="WARNING"):
            with self.assertRaises(Exception):
                google_auth_service.resolve_or_create_user(
                    {"sub": "g-sub-refused", "email": "google-refused@example.test"}
                )
        db.session.rollback()
        self.assertEqual(User.query.count(), 0)

    def test_one_time_cutover_keeps_future_signup_canonical_without_rerunning_migration(self):
        from sqlalchemy import event
        import re

        from app.repositories.study_authority_repository import lock_study_authority_route
        from app.services.study_storage_profile_service import apply_storage_profile_switch, StorageProfileSwitchError
        from models.study_authority_storage_profile import StudyAuthorityStorageProfile

        self._make_app()
        before = self._register("before_cutover")
        switched = apply_storage_profile_switch(db.session)
        db.session.commit()
        self.assertEqual(self._mode(before.id), ("NOTE", 1))
        engine = db.engine
        statements = []

        def record(_conn, _cursor, statement, *_args):
            if re.search(r"\bcard_progress\b", statement, re.IGNORECASE):
                statements.append(statement)

        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))
        after = self._register("after_cutover")
        google, action = google_auth_service.resolve_or_create_user(
            {"sub": "g-after-cutover", "email": "g-after-cutover@example.test"}
        )
        self.assertEqual(action, "created")
        for user in (after, google):
            self.assertEqual(self._mode(user.id), ("NOTE", 1))
            route = lock_study_authority_route(db.session, learner_user_id=user.id, allow_note_authority=True)
            self.assertEqual(route.storage_profile, "CANONICAL_V1")
            db.session.rollback()
        with self.assertRaises(StorageProfileSwitchError) as repeated:
            apply_storage_profile_switch(db.session)
        db.session.rollback()
        self.assertEqual(repeated.exception.code, "PROFILE_ALREADY_SWITCHED")
        profile = db.session.get(StudyAuthorityStorageProfile, 1)
        self.assertEqual((profile.profile_code, profile.epoch), ("CANONICAL_V1", switched["epoch"]))
        self.assertEqual(statements, [])


if __name__ == "__main__":
    unittest.main()
