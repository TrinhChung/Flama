"""MCP NOTE template topology preserves canonical progress atomically."""

from copy import deepcopy
from datetime import datetime, timezone
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests import test_study_direct_note_replay as fixtures
from tests import test_study_content_delete as content_delete_tests
from app.services.mcp.note_type_tools import preview_note_type_update, update_note_type
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from app.services.study_authority_enrollment_service import stage_legacy_authority_enrollment
from app.services.study_composition_service import make_compatibility_composition_id
from app.services.study_progress_shadow_mapper import map_card_progress
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.template import Template
from models.user import User


class StudyNoteTemplateTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def _review(self):
        self._answer()
        self._answer({**self.payload, "rating": "hard", "operation_key": str(uuid4())})

    def _identity(self):
        state = StudyProgressState.query.one()
        subject = StudyProgressSubject.query.one()
        token = StudyAuthoritySubjectToken.query.one()
        return deepcopy(state.state_payload), bytes(state.semantic_state_hash), subject.subject_generation, token.authority_revision

    def _update(self, changes, *, confirmed=False, **kwargs):
        note_type_id = NoteType.query.one().id
        if confirmed:
            preview = preview_note_type_update(user_id=self.user_id, note_type_id=note_type_id, templates=changes)
            kwargs.update(preview_id=preview["preview_id"], confirm=True)
        return update_note_type(user_id=self.user_id, note_type_id=note_type_id, templates=changes, **kwargs)

    def _assert_state(self, before, *, cards, generations):
        db.session.expire_all()
        after = self._identity()
        self.assertEqual(after[:2], before[:2])
        self.assertEqual(after[2:], (before[2] + generations, before[3]))
        self.assertEqual(Card.query.count(), cards)
        self.assertEqual(CardProgress.query.count(), cards)
        self.assertEqual(Template.query.filter_by(is_default=True).count(), 1)
        self.assertEqual(ReviewEvent.query.count(), before[3])
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), before[3])
        for progress in CardProgress.query.all():
            mapped = map_card_progress(progress, card_created_at=progress.card.created_at, card_order_key=progress.card_id)
            self.assertEqual(mapped.state.payload, before[0])
            self.assertEqual(mapped.semantic_state_hash, before[1])
        self.assertEqual(StudyProgressContributor.query.filter_by(contributor_status="ACTIVE").count(), cards)

    def test_multiple_additions_preserve_reviewed_state_and_cancel_old_session(self):
        self._review()
        with self.app.app_context():
            card = db.session.get(Card, self.card_ids[0])
            composition = make_compatibility_composition_id(card.note.note_type_id, card.template_id)
        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            opened = self.client.post("/api/study/sessions", json={"scope": "deck", "scope_id": self.deck_id,
                "composition_id": composition, "accepted_session_schema_versions": ["study-session.v4"]})
        self.assertEqual(opened.status_code, 201, opened.get_json())
        with self.app.app_context():
            before = self._identity()
            result = self._update({"added": [{"name": "Reverse"}, {"name": "Listening"}]})
            self.assertEqual(len(result["templates"]), 4)
            self._assert_state(before, cards=4, generations=2)
            self.assertEqual(db.session.get(StudySession, opened.get_json()["session_id"]).status, "cancelled")
            added = StudyProgressContributor.query.filter_by(contributor_status="ACTIVE").filter(
                StudyProgressContributor.live_card_id.notin_(self.card_ids)).all()
            self.assertEqual(len(added), 2)
            self.assertTrue(all(row.current_provenance_code == "NATIVE_MCP" for row in added))
            rollback = stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id,
                now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
            self.assertEqual(rollback.card_count, 4)
            db.session.commit()

    def test_replace_entire_list_keeps_note_state_and_detached_history(self):
        self._review()
        with self.app.app_context():
            before = self._identity()
            result = self._update([{"name": "Replacement A"}, {"name": "Replacement B"}], confirmed=True)
            self.assertEqual(len(result["templates"]), 2)
            self._assert_state(before, cards=2, generations=3)
            self.assertFalse(set(self.card_ids) & {row.id for row in Card.query.all()})
            for card_id in self.card_ids:
                detached = StudyProgressContributor.query.filter_by(logical_card_key=card_id.encode()).order_by(
                    StudyProgressContributor.subject_generation.desc()).first()
                self.assertEqual(detached.contributor_status, "DETACHED")
                self.assertIsNone(detached.live_card_id)
            self.assertEqual({row.card_id for row in ReviewEvent.query.all()}, {self.card_ids[0]})

    def test_remove_default_promotes_surviving_sibling_without_reset(self):
        with self.app.app_context():
            before = self._identity()
            result = self._update({"removed": ["Card 0"]}, confirmed=True)
            self.assertEqual(result["templates"][0]["name"], "Card 1")
            self.assertTrue(result["templates"][0]["is_default"])
            self._assert_state(before, cards=1, generations=1)

    def test_identity_only_updates_keep_cards_and_generation(self):
        with self.app.app_context():
            before = self._identity()
            rows = Template.query.order_by(Template.name).all()
            result = self._update([{"id": rows[0].id, "name": "Renamed", "front_html": "<b>{{Word}}</b>"},
                {"id": rows[1].id, "name": rows[1].name}])
            self.assertEqual(len(result["templates"]), 2)
            self._assert_state(before, cards=2, generations=0)
            self.assertEqual({row.id for row in Card.query.all()}, set(self.card_ids))

    def test_second_expansion_fault_rolls_back_fields_metadata_and_all_cards(self):
        with self.app.app_context():
            before = self._identity()
            original = lifecycle.finalize_note_authority_sibling_expansion
            calls = 0
            def fail_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                result = original(*args, **kwargs)
                if calls == 2:
                    raise RuntimeError("injected expansion fault")
                return result
            with patch.object(lifecycle, "finalize_note_authority_sibling_expansion", side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, "injected expansion fault"):
                    self._update({"added": [{"name": "A"}, {"name": "B"}]}, name="Uncommitted name",
                        fields={"added": [{"name": "Extra"}]})
            self.assertFalse(db.session().in_transaction())
            self._assert_state(before, cards=2, generations=0)
            self.assertEqual(NoteType.query.one().name, "Direct replay")
            self.assertEqual(FieldDef.query.count(), 1)

    def test_removal_fault_rolls_back_prior_additions(self):
        with self.app.app_context():
            before = self._identity()
            original = lifecycle.finalize_note_authority_sibling_removal
            def fail_after_removal(*args, **kwargs):
                original(*args, **kwargs)
                raise RuntimeError("injected removal fault")
            with patch.object(lifecycle, "finalize_note_authority_sibling_removal", side_effect=fail_after_removal):
                with self.assertRaisesRegex(RuntimeError, "injected removal fault"):
                    self._update([{"name": "Replacement"}], confirmed=True)
            self.assertFalse(db.session().in_transaction())
            self._assert_state(before, cards=2, generations=0)

    def test_empty_list_and_ambiguous_identity_reject_without_writes(self):
        with self.app.app_context():
            before = self._identity()
            template_id = Template.query.first().id
            for changes in ([], [{"id": "not-owned", "name": "A"}],
                    [{"id": template_id}, {"id": template_id}], {"added": [{"name": "Card 0"}]}):
                with self.subTest(changes=changes), self.assertRaises(RequestValidationError):
                    self._update(changes, confirmed=True, name="Must roll back")
                self._assert_state(before, cards=2, generations=0)
                self.assertEqual(NoteType.query.one().name, "Direct replay")

    def test_preview_rejects_same_count_template_edit_without_timestamp_change(self):
        with self.app.app_context():
            before = self._identity()
            nt = NoteType.query.one()
            original_timestamp = nt.updated_at
            changes = {"removed": ["Card 0"]}
            preview = preview_note_type_update(user_id=self.user_id, note_type_id=nt.id, templates=changes)
            template = Template.query.filter_by(name="Card 1").one()
            template.front_html = "<b>Concurrent edit</b>"
            db.session.commit()
            self.assertEqual(nt.updated_at, original_timestamp)
            with self.assertRaises(RequestValidationError) as failure:
                self._update(changes, preview_id=preview["preview_id"], confirm=True)
            self.assertEqual(failure.exception.code, "STALE_PREVIEW_ERROR")
            self._assert_state(before, cards=2, generations=0)
            self.assertEqual(Template.query.filter_by(name="Card 1").one().front_html, "<b>Concurrent edit</b>")

    def test_shared_release_guard_still_prevents_template_mutation(self):
        with self.app.app_context():
            before = self._identity()
            with patch("app.services.deck_working_tree_service.note_type_has_shared_release_dependents", return_value=True):
                with self.assertRaises(RequestValidationError) as failure:
                    self._update({"added": [{"name": "Blocked"}]})
            self.assertEqual(failure.exception.code, "SHARED_SCHEMA_VERSIONING_REQUIRED")
            self._assert_state(before, cards=2, generations=0)

    def test_other_legacy_learner_progress_is_retired_with_removed_template(self):
        with self.app.app_context():
            before = self._identity()
            other = User(username="other-template", email="other-template@example.test")
            db.session.add(other)
            db.session.flush()
            other_id = other.id
            db.session.add(CardProgress(user_id=other_id, card_id=self.card_ids[0]))
            db.session.commit()
            self._update({"removed": ["Card 0"]}, confirmed=True)
            self._assert_state(before, cards=1, generations=1)
            self.assertEqual(CardProgress.query.filter_by(user_id=other_id).count(), 0)

    def test_second_note_learner_keeps_one_state_across_mcp_add_and_remove(self):
        with self.app.app_context():
            reader_id = content_delete_tests.StudyContentDeleteTests._add_note_source_reader(self)
            tokens = lambda: {row.subject_id: (row.authority_revision, row.semantic_state_hash)
                for row in StudyAuthoritySubjectToken.query.all()}
            before = tokens()
            self._update({"added": [{"name": "Reverse"}]})
            db.session.expire_all()
            self.assertEqual(Card.query.count(), 3)
            self.assertEqual(CardProgress.query.filter_by(user_id=reader_id).count(), 3)
            self.assertEqual(CardProgress.query.filter_by(user_id=self.user_id).count(), 3)
            self.assertEqual(tokens(), before)
            self._update({"removed": ["Card 0"]}, confirmed=True)
            db.session.expire_all()
            self.assertEqual(Card.query.count(), 2)
            self.assertEqual(CardProgress.query.filter_by(user_id=reader_id).count(), 2)
            self.assertEqual(tokens(), before)
            self.assertEqual(StudyProgressState.query.count(), 2)
