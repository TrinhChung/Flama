"""Independent definitions, occurrence selection, and frozen render inputs."""

import unittest
from unittest.mock import patch

from tests import test_study_composition_service as compositions
from tests import test_study_session_install_usage as installs
from app.repositories import template_release_repository, template_library_repository
from app.services import study_session_service
from app.services.study_composition_service import (
    apply_composition_selection_to_query, count_notes_by_composition,
    group_available_compositions, list_available_compositions_for_query,
    resolve_composition_selection, resolve_compatibility_composition_for_card,
)
from models import db
from models.card import Card
from models.deck_install import DeckInstall
from models.deck_release import DeckRelease
from models.deck_release_template_pin import DeckReleaseTemplatePin
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template
from models.template_release import TemplateRelease
from models.template_subscription import TemplateSubscription
from models.study_session import StudySession
from app.validators.template_library import TemplateLibraryError


class StudyTemplateApplicationTests(unittest.TestCase):
    setUp = compositions.StudyCompositionServiceTests.setUp
    tearDown = compositions.StudyCompositionServiceTests.tearDown

    def _query(self):
        return Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck.id)

    def _open(self, composition_id, bindings=None):
        query = self._query()
        selection = resolve_composition_selection(query, clone_scope=None,
            requested_composition_id=composition_id, request_source="test")
        return study_session_service.open_study_session(user=self.user, query=query,
            clone_scope=None, scope_type="deck", scope_id=str(self.deck.id), timezone_name="UTC", wire_schema_version="study-session.v4",
            composition_selection=selection, input_bindings=bindings)

    def test_independent_template_applies_to_two_note_types_with_note_authority(self):
        second_type = NoteType(name="Another NoteType", user_id=self.user.id)
        template = Template(name="Reusable", owner_user_id=self.user.id,
                            front_html="{{term}}", back_html="", input_schema=[{"key": "term"}])
        db.session.add_all([second_type, template])
        db.session.flush()
        second_note = Note(user_id=self.user.id, deck_id=self.deck.id,
                           note_type_id=second_type.id, field_values={"Other": "other"})
        apps = [StudyApplication(template_id=template.id, note_type_id=note_type.id,
                                 occurrence_key="attached", display_name=f"Use {index}", position=index)
                for index, note_type in enumerate((self.note_type, second_type))]
        db.session.add_all([second_note, *apps])
        db.session.flush()
        cards = [Card.query.filter_by(note_id=note.id, application_id=application.id).one()
                 for note, application in zip((self.note, second_note), apps)]
        db.session.commit()
        query = self._query().filter(Card.template_id == template.id)
        available = list_available_compositions_for_query(query, clone_scope=None)
        self.assertEqual(len(available), 2)
        self.assertEqual({item.note_type_id for item in available}, {self.note_type.id, second_type.id})
        self.assertEqual(len(group_available_compositions(available)), 2)
        self.assertEqual(count_notes_by_composition(query, clone_scope=None, compositions=available),
                         {item.composition_id: 1 for item in available})
        for card in cards:
            composition = resolve_compatibility_composition_for_card(card)
            self.assertEqual(composition.note_type_id, card.note.note_type_id)
            self.assertEqual(
                composition.composition_id,
                f"comp:notetype:{card.note.note_type_id}:template:{template.id}",
            )
            self.assertEqual(composition.study_application_id, card.application_id)
            selection = resolve_composition_selection(query, clone_scope=None,
                requested_composition_id=composition.composition_id, request_source="test")
            selected = apply_composition_selection_to_query(query, clone_scope=None, selection=selection).all()
            self.assertEqual([row.id for row in selected], [card.id])

    def test_session_binding_override_is_frozen_and_does_not_change_application(self):
        values = self.note.field_values
        fields = [FieldDef(note_type_id=self.note_type.id, name=name, field_type="text", position=index)
                  for index, name in enumerate(("Front", "Back"))]
        db.session.add_all(fields)
        db.session.flush()
        # Explicit fixture disposition: bind the previously undeclared values
        # to the newly declared definitions, instead of relying on name reuse.
        self.note.field_values = values
        template = self.template_1
        template.front_html, template.back_html = "{{term}}", ""
        template.input_schema = [{"key": "term", "type": "text"}]
        self.card_1.application.input_bindings = {"term": fields[0].id}
        db.session.commit()
        composition_id = resolve_compatibility_composition_for_card(self.card_1).composition_id
        snapshot = self._open(composition_id, {"term": fields[1].id})
        content = next(iter(snapshot["contents"].values()))
        self.assertEqual(content["render_context"]["term"], "test back")
        projection = next(iter(snapshot["templates"].values()))["binding_projection"]
        self.assertEqual(projection["input_bindings"], {"term": fields[1].id})
        self.assertEqual([row["name"] for row in projection["field_defs"]], ["Front", "Back"])
        self.assertEqual(self.card_1.application.input_bindings, {"term": fields[0].id})
        self.assertEqual(template.front_html, "{{term}}")
        stored = db.session.get(study_session_service.StudySession, snapshot["session_id"]).config_snapshot_json
        self.card_1.application.input_bindings = {"term": fields[1].id}
        template.front_html = "changed{{term}}"
        db.session.commit()
        self.assertEqual(db.session.get(study_session_service.StudySession, snapshot["session_id"]).config_snapshot_json, stored)
        self.assertEqual(content["render_context"]["term"], "test back")

    def test_transient_bindings_reject_malformed_unknown_cross_type_and_wrong_kind(self):
        other = NoteType(name="Other", user_id=self.user.id)
        fields = [FieldDef(note_type_id=self.note_type.id, name="Front", field_type="text"),
                  FieldDef(note_type_id=self.note_type.id, name="Voice", field_type="audio")]
        db.session.add_all([other, *fields])
        db.session.flush()
        foreign = FieldDef(note_type_id=other.id, name="Foreign", field_type="text")
        db.session.add(foreign)
        self.template_1.input_schema = [{"key": "term", "type": "text"}]
        self.template_1.front_html = "{{term}}"
        db.session.commit()
        composition_id = resolve_compatibility_composition_for_card(self.card_1).composition_id
        cases = [([], "VALIDATION_ERROR"), ("bad", "VALIDATION_ERROR"),
                 ({"unknown": fields[0].id}, "INPUT_NOT_FOUND"),
                 ({"term": foreign.id}, "FIELD_OUT_OF_SCOPE"),
                 ({"term": fields[1].id}, "INPUT_TYPE_MISMATCH"),
                 ({"term": []}, "FIELD_OUT_OF_SCOPE")]
        for mapping, code in cases:
            with self.subTest(mapping=mapping), self.assertRaises(TemplateLibraryError) as raised:
                self._open(composition_id, mapping)
            self.assertEqual(raised.exception.code, code)
            db.session.rollback()
            self.assertEqual(StudySession.query.count(), 0)

    def test_empty_override_shadows_legacy_inputs_without_saving(self):
        values = self.note.field_values
        field = FieldDef(note_type_id=self.note_type.id, name="Front", field_type="text")
        db.session.add(field)
        db.session.flush()
        self.note.field_values = values
        db.session.commit()
        composition_id = resolve_compatibility_composition_for_card(self.card_1).composition_id
        snapshot = self._open(composition_id, {})
        content = next(iter(snapshot["contents"].values()))
        self.assertEqual(content["render_context"]["Front"], "")
        self.assertIsNone(self.card_1.application.input_bindings)


class StudyTemplateReleaseSessionTests(unittest.TestCase):
    setUpClass = classmethod(installs.StudySessionInstallUsageTests.setUpClass.__func__)
    setUp = installs.StudySessionInstallUsageTests.setUp
    _cleanup = installs.StudySessionInstallUsageTests._cleanup
    _install_overlay = installs.StudySessionInstallUsageTests._install_overlay
    _open = installs.StudySessionInstallUsageTests._open

    def test_session_batch_resolves_pins_and_canonical_copy_without_source_mutation(self):
        self._install_overlay(notes=3)
        with self.app.app_context():
            install = db.session.get(DeckInstall, self.install_id)
            source = template_library_repository.applications(db.session, install.source_note_type_id)[0].template
            field = FieldDef.query.filter_by(note_type_id=install.source_note_type_id).one()
            application = StudyApplication.query.filter_by(template_id=source.id).one()
            source.front_html = "pinned {{term}}"
            source.input_schema = [{"key": "term", "type": "text"}]
            application.input_bindings = {"term": field.id}
            db.session.commit()
            release = TemplateRelease(template_id=source.id, version_id=source.current_version_id,
                                      sequence_no=1, version_label="v1")
            deck_release = DeckRelease(deck_item_id=install.deck_item_id, sequence_no=1,
                                       version_label="v1", status="published", template_pins_initialized=True)
            db.session.add_all([release, deck_release])
            db.session.flush()
            db.session.add(DeckReleaseTemplatePin(deck_release_id=deck_release.id,
                source_template_id=source.id, template_release_id=release.id,
                applications_json={application.id: {"input_bindings": {"term": field.id}}}))
            install.applied_release_id = deck_release.id
            db.session.commit()
            source.front_html = "new source {{term}}"
            application.input_bindings = {}
            db.session.commit()
            source_id, release_id, field_id = source.id, release.id, field.id
        with patch.object(template_release_repository, "load_effective_template_overrides",
                          wraps=template_release_repository.load_effective_template_overrides) as load:
            pinned = self._open()
        self.assertEqual(load.call_count, 1)
        self.assertEqual(next(iter(pinned["templates"].values()))["front_source"], "pinned {{term}}")
        self.assertEqual({row["render_context"]["term"] for row in pinned["contents"].values()}, {"w0", "w1", "w2"})
        with patch.object(template_release_repository, "load_effective_template_overrides",
                          wraps=template_release_repository.load_effective_template_overrides) as load:
            prepared = self.client.get(
                f"/api/study/scopes/deck/{self.local_deck_id}/compositions?include_template_inputs=1"
            )
        self.assertEqual(prepared.status_code, 200, prepared.get_json())
        self.assertEqual(load.call_count, 1)
        entry = next(iter(prepared.get_json()["template_inputs"].values()))
        self.assertEqual(entry["input_schema"][0]["key"], "term")
        self.assertEqual(entry["input_bindings"], {"term": field_id})
        with self.app.app_context():
            local = Template(owner_user_id=self.user_id, origin="market_copy", name="Local",
                             front_html="local {{term}}", back_html="", input_schema=[{"key": "term"}])
            db.session.add(local)
            db.session.flush()
            db.session.add(TemplateSubscription(user_id=self.user_id, source_template_id=source_id,
                                               local_template_id=local.id, applied_release_id=release_id))
            db.session.commit()
            self.assertEqual(db.session.get(Template, source_id).front_html, "new source {{term}}")
        canonical = self._open()
        self.assertEqual(next(iter(canonical["templates"].values()))["front_source"], "local {{term}}")
        self.assertEqual({row["render_context"]["term"] for row in canonical["contents"].values()}, {"w0", "w1", "w2"})
        self.assertEqual(next(iter(canonical["templates"].values()))["id"], source_id)
        self.assertEqual(next(iter(pinned["templates"].values()))["front_source"], "pinned {{term}}")


if __name__ == "__main__":
    unittest.main()
