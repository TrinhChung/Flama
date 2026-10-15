"""Personal presets and transient overrides use effective presentation scopes."""

import unittest
from unittest.mock import patch
from tests import test_study_composition_service as compositions
from tests import test_study_session_install_usage as installs
from app.services import study_session_service, study_template_preset_service
from app.repositories import template_library_repository
from app.services.study_composition_service import resolve_compatibility_composition_for_card
from app.validators.template_library import TemplateLibraryError
from models import db
from models.card import Card
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_install import DeckInstall
from models.field_def import FieldDef
from models.note import Note
from models.study_template_preset import StudyTemplatePreset
from models.template import Template


class StudyTemplatePresetTests(unittest.TestCase):
    setUp = compositions.StudyCompositionServiceTests.setUp
    tearDown = compositions.StudyCompositionServiceTests.tearDown

    def _binding(self):
        values = self.note.field_values
        field = FieldDef(note_type_id=self.note_type.id, name="Front", field_type="text")
        db.session.add(field)
        db.session.flush()
        self.note.field_values = values
        self.template_1.front_html, self.template_1.back_html = "{{term}}", ""
        self.template_1.input_schema = [{"key": "term", "type": "text"}]
        db.session.commit()
        return resolve_compatibility_composition_for_card(self.card_1).composition_id, field

    def test_saved_choice_and_binding_auto_apply_only_for_its_user_and_deck(self):
        composition_id, field = self._binding()
        saved = study_template_preset_service.save_preset(user_id=self.user.id, deck_id=self.deck.id,
            payload={"selected_compositions": [composition_id], "input_bindings": {composition_id: {"term": field.id}}, "ask_before_study": False})
        self.assertEqual(saved["stale_compositions"], [])
        snapshot = study_session_service.open_study_session(user=self.user,
            query=Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck.id),
            clone_scope=None, scope_type="deck", scope_id=str(self.deck.id), timezone_name="UTC", wire_schema_version="study-session.v4")
        self.assertEqual(snapshot["selected_composition_id"], composition_id)
        self.assertEqual(next(iter(snapshot["contents"].values()))["render_context"]["term"], "test front")
        self.assertIsNone(study_template_preset_service.session_input_bindings(self.user.id + 1, "deck", self.deck.id, composition_id))
        self.assertIsNone(study_template_preset_service.session_input_bindings(self.user.id, "deck", self.deck.id + 1, composition_id))
        self.assertIsNone(self.card_1.application.input_bindings)

    def test_invalid_saved_bindings_leave_existing_preset_unchanged(self):
        composition_id, field = self._binding()
        payload = {"selected_compositions": [composition_id], "input_bindings": {composition_id: {"term": field.id}}, "ask_before_study": False}
        study_template_preset_service.save_preset(user_id=self.user.id, deck_id=self.deck.id, payload=payload)
        with self.assertRaises(TemplateLibraryError):
            study_template_preset_service.save_preset(user_id=self.user.id, deck_id=self.deck.id,
                payload={**payload, "input_bindings": {composition_id: {"term": "foreign"}}})
        db.session.rollback()
        row = StudyTemplatePreset.query.one()
        self.assertEqual(row.input_bindings, payload["input_bindings"])

    def test_retired_saved_choice_reports_stale_before_session(self):
        composition_id, _field = self._binding()
        study_template_preset_service.save_preset(user_id=self.user.id, deck_id=self.deck.id,
            payload={"selected_compositions": [composition_id], "ask_before_study": False})
        self.card_1.application.status_code = "RETIRED"
        db.session.commit()
        preset = study_template_preset_service.get_preset(user_id=self.user.id, deck_id=self.deck.id)
        self.assertEqual(preset["stale_compositions"], [composition_id])
        with self.assertRaises(TemplateLibraryError) as raised:
            study_template_preset_service.resolve_session_preset(self.user.id, "deck", self.deck.id, None)
        self.assertEqual((raised.exception.code, raised.exception.status), ("COMPOSITION_STALE", 409))

    def test_preparation_is_opt_in_and_exposes_scoped_defaults_without_note_values(self):
        composition_id, field = self._binding()
        self.card_1.application.input_bindings = {"term": field.id}
        db.session.commit()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"], session["_fresh"] = str(self.user.id), True
        url = f"/api/study/scopes/deck/{self.deck.id}/compositions"
        response = client.get(url)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertNotIn("template_inputs", response.get_json())
        response = client.get(url + "?include_template_inputs=1&include_counts=1")
        self.assertEqual(response.status_code, 200, response.get_json())
        inputs = response.get_json()["template_inputs"][composition_id]
        self.assertEqual(inputs["input_bindings"], {"term": field.id})
        self.assertEqual(inputs["field_defs"][0]["id"], field.id)
        self.assertEqual(inputs["warnings"], [])
        self.assertNotIn("field_values", inputs)
        self.assertEqual(response.get_json()["note_counts"], {composition_id: 1})


class StudyInstalledTemplatePresetTests(unittest.TestCase):
    setUpClass = classmethod(installs.StudySessionInstallUsageTests.setUpClass.__func__)
    setUp = installs.StudySessionInstallUsageTests.setUp
    _cleanup = installs.StudySessionInstallUsageTests._cleanup
    _install_overlay = installs.StudySessionInstallUsageTests._install_overlay

    def test_overlay_added_fields_are_bindable_and_disabled_fields_are_out_of_scope(self):
        self._install_overlay(notes=1)
        with self.app.app_context():
            install = db.session.get(DeckInstall, self.install_id)
            template = template_library_repository.applications(db.session, install.source_note_type_id)[0].template
            field = FieldDef.query.filter_by(note_type_id=install.source_note_type_id).one()
            template.input_schema = [{"key": "term", "type": "text"}]
            added = DeckCloneAddedFieldDef(deck_install_id=install.id, name="Personal", field_type="text")
            db.session.add_all([added, DeckCloneFieldDefOverride(deck_install_id=install.id,
                source_field_def_id=field.id, is_disabled=True)])
            db.session.commit()
            added_id, disabled_id = added.id, field.id
        compositions = self.client.get(f"/api/study/scopes/deck/{self.local_deck_id}/compositions?include_template_inputs=1").get_json()
        composition_id = compositions["compositions"][0]["composition_id"]
        inputs = compositions["template_inputs"][composition_id]
        self.assertEqual([field["id"] for field in inputs["field_defs"]], [added_id])
        url = f"/api/decks/{self.local_deck_id}/study-template-preset"
        payload = {"selected_compositions": [composition_id], "input_bindings": {composition_id: {"term": added_id}}}
        response = self.client.put(url, json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        payload["input_bindings"][composition_id]["term"] = disabled_id
        response = self.client.put(url, json=payload)
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["error"], "FIELD_OUT_OF_SCOPE")
        # A successful binding to the added field freezes the effective IDs.
        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            response = self.client.post("/api/study/sessions", json={"scope": "deck", "scope_id": self.local_deck_id,
                "composition_id": composition_id, "input_bindings": {"term": added_id},
                "accepted_session_schema_versions": ["study-session.v4"]})
        self.assertEqual(response.status_code, 201, response.get_json())
        artifact = next(iter(response.get_json()["templates"].values()))
        self.assertEqual(artifact["binding_projection"]["input_bindings"], {"term": added_id})
        self.assertEqual([field["id"] for field in artifact["binding_projection"]["field_defs"]], [added_id])
        # The identical transient override is rejected without creating a lease.
        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            response = self.client.post("/api/study/sessions", json={"scope": "deck", "scope_id": self.local_deck_id,
                "composition_id": composition_id, "input_bindings": {"term": disabled_id},
                "accepted_session_schema_versions": ["study-session.v4"]})
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["error"], "FIELD_OUT_OF_SCOPE")

    def test_overlay_field_type_override_is_used_by_preset_validation(self):
        self._install_overlay(notes=1)
        with self.app.app_context():
            install = db.session.get(DeckInstall, self.install_id)
            template = template_library_repository.applications(db.session, install.source_note_type_id)[0].template
            field = FieldDef.query.filter_by(note_type_id=install.source_note_type_id).one()
            template.input_schema = [{"key": "term", "type": "text"}]
            db.session.add(DeckCloneFieldDefOverride(deck_install_id=install.id,
                source_field_def_id=field.id, properties={"field_type": "audio"}))
            db.session.commit()
            field_id = field.id
        compositions = self.client.get(f"/api/study/scopes/deck/{self.local_deck_id}/compositions").get_json()
        composition_id = compositions["compositions"][0]["composition_id"]
        response = self.client.put(f"/api/decks/{self.local_deck_id}/study-template-preset", json={
            "selected_compositions": [composition_id], "input_bindings": {composition_id: {"term": field_id}}})
        self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(response.get_json()["error"], "INPUT_TYPE_MISMATCH")


if __name__ == "__main__":
    unittest.main()
