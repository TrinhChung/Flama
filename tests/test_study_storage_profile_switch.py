"""P9-06: the one-way NOTE storage profile switch and its Connect ref mapping."""

from __future__ import annotations

from datetime import datetime
import unittest
from unittest import mock
from uuid import uuid4

# Import the app (through the Anki tests) before any model module.
from tests import test_anki_import_api as anki_tests  # noqa: I001
from tests import test_study_canonical_connect as connect_tests
from app.services.study_storage_profile_service import (
    StorageProfileSwitchError,
    apply_storage_profile_switch,
    plan_storage_profile_switch,
)
from models import db
from models.connect_source_card_ref import ConnectSourceCardRef
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_authority_subject_token import StudyAuthoritySubjectToken

BOTH_PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1"})


class StudyStorageProfileSwitchTests(unittest.TestCase):
    setUp = anki_tests.AnkiImportApiTests.setUp
    tearDown = anki_tests.AnkiImportApiTests.tearDown
    _login = anki_tests.AnkiImportApiTests._login
    _session_payload = anki_tests.AnkiImportApiTests._session_payload
    _create_session = anki_tests.AnkiImportApiTests._create_session
    _upload_package = anki_tests.AnkiImportApiTests._upload_package
    _sync = connect_tests.StudyCanonicalConnectTests._sync
    _ref = connect_tests.StudyCanonicalConnectTests._ref

    def _prepare(self):
        """A NOTE learner whose Anki ref was synced under PROJECTION_V1."""
        from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
        from models.card import Card
        from models.note import Note

        self.app.config["STUDY_PROGRESS_SHADOW_WRITE_ENABLED"] = True
        self._login()
        self.session_id = self._create_session()["importSessionId"]
        self._upload_package(self.session_id, "cards", 0, [{
            "ankiNoteId": 3101, "sourceModelId": "anki-model-1", "sourceDeckId": "anki-inbox",
            "sourceDeckPath": "Inbox", "contentHash": "3" * 64,
            "note": {"deckName": "Inbox", "modelName": self.note_type_id,
                     "fields": {"Word": "switch", "Meaning": "fence"}, "tags": []},
        }])
        with self.app.app_context():
            from models.user import User

            # The switch requires every account to be a NOTE learner (D9-09).
            for user in User.query.order_by(User.id).all():
                stage_note_authority_enrollment(db.session, learner_user_id=user.id,
                                                now_utc=datetime(2026, 9, 23, 9, 0, 0))
            db.session.commit()
            self.card_id = Card.query.order_by(Card.id).first().id
            self.deck_id = Note.query.one().deck_id
        applied = self._sync(0)
        self.assertEqual(applied["state"], "applied")

    def test_plan_maps_unchanged_refs_and_flags_diverged_ones(self):
        self._prepare()
        with self.app.app_context():
            plan = plan_storage_profile_switch(db.session)
            self.assertEqual(plan["connect_refs"], {"authority": 1, "needs_confirmation": 0})
            self.assertIn("RELEASE_DOES_NOT_SUPPORT_CANONICAL_V1", plan["blockers"])
            with self.assertRaises(StorageProfileSwitchError) as blocked:
                apply_storage_profile_switch(db.session)
            self.assertEqual(blocked.exception.code, "SWITCH_BLOCKED")
            db.session.rollback()

        answered = self.client.post(f"/api/study/{self.card_id}/answer", json={
            "rating": "good", "operation_key": str(uuid4()), "duration_ms": 500,
            "scope": "deck", "scope_id": self.deck_id})
        self.assertEqual(answered.status_code, 200, answered.get_json())
        with self.app.app_context():
            plan = plan_storage_profile_switch(db.session)
            self.assertEqual(plan["connect_refs"], {"authority": 0, "needs_confirmation": 1})

    def test_switch_maps_refs_bumps_the_epoch_and_is_one_way(self):
        self._prepare()
        with mock.patch("app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES):
            with self.app.app_context():
                revision = int(StudyAuthoritySubjectToken.query.one().authority_revision)
                self.assertEqual(plan_storage_profile_switch(db.session)["blockers"], [])
                result = apply_storage_profile_switch(db.session, now_utc=datetime(2026, 10, 2, 18, 0))
                db.session.commit()
                self.assertEqual((result["profile"], result["epoch"]), ("CANONICAL_V1", 2))
                profile = db.session.get(StudyAuthorityStorageProfile, 1)
                self.assertEqual((profile.profile_code, profile.epoch), ("CANONICAL_V1", 2))
                ref = self._ref()
                self.assertEqual((ref.applied_local_revision_state, ref.applied_authority_revision),
                                 ("AUTHORITY", revision))
                with self.assertRaises(StorageProfileSwitchError) as again:
                    apply_storage_profile_switch(db.session)
                self.assertEqual(again.exception.code, "PROFILE_ALREADY_SWITCHED")
                db.session.rollback()
            # After the switch the same snapshot is unchanged: no spurious conflict.
            replay = self._sync(1)
            self.assertEqual((replay["state"], replay["code"]), ("unchanged", "PROGRESS_UNCHANGED"))
            changed = self._sync(2, snapshotHash="b" * 64, baseSnapshotHash="a" * 64, interval=21)
            self.assertEqual((changed["state"], changed["code"]), ("applied", "PROGRESS_APPLIED"))
            with self.app.app_context():
                self.assertEqual(ConnectSourceCardRef.query.one().applied_authority_revision, revision + 1)


if __name__ == "__main__":
    unittest.main()
