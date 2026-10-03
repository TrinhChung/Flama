"""MCP NOTE template topology keeps the Note's one progress row, atomically (ADR P10)."""

from copy import deepcopy
import unittest
from unittest.mock import patch
from uuid import uuid4

from tests import test_study_direct_note_replay as fixtures
from tests import test_study_content_delete as content_delete_tests
from app.services.mcp.note_type_tools import preview_note_type_update, update_note_type
from app.services import study_content_delete_service as content_topology
from app.services.study_composition_service import make_compatibility_composition_id
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
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
        subject = StudyProgressSubject.query.one()
        return (deepcopy(subject.state_payload), bytes(subject.semantic_state_hash),
                subject.subject_generation, subject.authority_revision)

    def _update(self, changes, *, confirmed=False, **kwargs):
        note_type_id = NoteType.query.one().id
        if confirmed:
            preview = preview_note_type_update(user_id=self.user_id, note_type_id=note_type_id, templates=changes)
            kwargs.update(preview_id=preview["preview_id"], confirm=True)
        return update_note_type(user_id=self.user_id, note_type_id=note_type_id, templates=changes, **kwargs)

    def _assert_state(self, before, *, cards):
        db.session.expire_all()
        # Template topology changes neither the Note's state nor its row's generation.
        self.assertEqual(self._identity(), before)
        self.assertEqual(Card.query.count(), cards)
        self.assertEqual(CardProgress.query.count(), 0)
        self.assertEqual(Template.query.filter_by(is_default=True).count(), 1)
        self.assertEqual(ReviewEvent.query.count(), before[3])
        self.assertEqual(StudyAuthorityCommandReceipt.query.count(), before[3])

    def test_multiple_additions_preserve_reviewed_state_and_keep_old_session(self):
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
            self._assert_state(before, cards=4)
            # The row's pins stay valid: the open session keeps its own Cards (ADR P10).
            self.assertEqual(db.session.get(StudySession, opened.get_json()["session_id"]).status, "open")

    def test_replace_entire_list_keeps_note_state_and_detached_history(self):
        self._review()
        with self.app.app_context():
            before = self._identity()
            result = self._update([{"name": "Replacement A"}, {"name": "Replacement B"}], confirmed=True)
            self.assertEqual(len(result["templates"]), 2)
            self._assert_state(before, cards=2)
            self.assertFalse(set(self.card_ids) & {row.id for row in Card.query.all()})
            # The removed Cards' history stays on its ReviewEvents.
            self.assertEqual({row.card_id for row in ReviewEvent.query.all()}, {self.card_ids[0]})

    def test_remove_default_promotes_surviving_sibling_without_reset(self):
        with self.app.app_context():
            before = self._identity()
            result = self._update({"removed": ["Card 0"]}, confirmed=True)
            self.assertEqual(result["templates"][0]["name"], "Card 1")
            self.assertTrue(result["templates"][0]["is_default"])
            self._assert_state(before, cards=1)

    def test_identity_only_updates_keep_cards_and_generation(self):
        with self.app.app_context():
            before = self._identity()
            rows = Template.query.order_by(Template.name).all()
            result = self._update([{"id": rows[0].id, "name": "Renamed", "front_html": "<b>{{Word}}</b>"},
                {"id": rows[1].id, "name": rows[1].name}])
            self.assertEqual(len(result["templates"]), 2)
            self._assert_state(before, cards=2)
            self.assertEqual({row.id for row in Card.query.all()}, set(self.card_ids))

    def test_second_expansion_fault_rolls_back_fields_metadata_and_all_cards(self):
        with self.app.app_context():
            before = self._identity()
            original = content_topology.finalize_content_expansion
            calls = 0
            def fail_second(*args, **kwargs):
                nonlocal calls
                calls += 1
                result = original(*args, **kwargs)
                if calls == 2:
                    raise RuntimeError("injected expansion fault")
                return result
            with patch.object(content_topology, "finalize_content_expansion", side_effect=fail_second):
                with self.assertRaisesRegex(RuntimeError, "injected expansion fault"):
                    self._update({"added": [{"name": "A"}, {"name": "B"}]}, name="Uncommitted name",
                        fields={"added": [{"name": "Extra"}]})
            self.assertFalse(db.session().in_transaction())
            self._assert_state(before, cards=2)
            self.assertEqual(NoteType.query.one().name, "Direct replay")
            self.assertEqual(FieldDef.query.count(), 1)

    def test_removal_fault_rolls_back_prior_additions(self):
        with self.app.app_context():
            before = self._identity()
            original = content_topology.finalize_content_delete
            def fail_after_removal(*args, **kwargs):
                original(*args, **kwargs)
                raise RuntimeError("injected removal fault")
            with patch.object(content_topology, "finalize_content_delete", side_effect=fail_after_removal):
                with self.assertRaisesRegex(RuntimeError, "injected removal fault"):
                    self._update([{"name": "Replacement"}], confirmed=True)
            self.assertFalse(db.session().in_transaction())
            self._assert_state(before, cards=2)

    def test_empty_list_and_ambiguous_identity_reject_without_writes(self):
        with self.app.app_context():
            before = self._identity()
            template_id = Template.query.first().id
            for changes in ([], [{"id": "not-owned", "name": "A"}],
                    [{"id": template_id}, {"id": template_id}], {"added": [{"name": "Card 0"}]}):
                with self.subTest(changes=changes), self.assertRaises(RequestValidationError):
                    self._update(changes, confirmed=True, name="Must roll back")
                self._assert_state(before, cards=2)
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
            self._assert_state(before, cards=2)
            self.assertEqual(Template.query.filter_by(name="Card 1").one().front_html, "<b>Concurrent edit</b>")

    def test_shared_release_guard_still_prevents_template_mutation(self):
        with self.app.app_context():
            before = self._identity()
            with patch("app.services.deck_working_tree_service.note_type_has_shared_release_dependents", return_value=True):
                with self.assertRaises(RequestValidationError) as failure:
                    self._update({"added": [{"name": "Blocked"}]})
            self.assertEqual(failure.exception.code, "SHARED_SCHEMA_VERSIONING_REQUIRED")
            self._assert_state(before, cards=2)

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
            self._assert_state(before, cards=1)
            self.assertEqual(CardProgress.query.filter_by(user_id=other_id).count(), 0)

    def test_second_note_learner_keeps_one_state_across_mcp_add_and_remove(self):
        with self.app.app_context():
            reader_id = content_delete_tests.StudyContentDeleteTests._add_note_source_reader(self)
            tokens = lambda: {row.id: (row.authority_revision, row.semantic_state_hash)
                for row in StudyProgressSubject.query.all()}
            before = tokens()
            self._update({"added": [{"name": "Reverse"}]})
            db.session.expire_all()
            self.assertEqual(Card.query.count(), 3)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(tokens(), before)
            self._update({"removed": ["Card 0"]}, confirmed=True)
            db.session.expire_all()
            self.assertEqual(Card.query.count(), 2)
            self.assertEqual(CardProgress.query.count(), 0)
            self.assertEqual(tokens(), before)
            self.assertEqual(StudyProgressSubject.query.filter(
                StudyProgressSubject.state_payload.isnot(None)).count(), 2)
            self.assertEqual({row.learner_user_id for row in StudyProgressSubject.query.all()},
                             {self.user_id, reader_id})
