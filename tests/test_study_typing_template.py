"""Typing-answer templates: answers input validation, bindings and study artifact."""

import unittest
from types import SimpleNamespace

from app import create_app
from app.services.study_artifact_service import (
    build_content_artifact,
    build_effective_study_card,
    build_template_artifact,
    template_version,
)
from app.validators.template_library import (
    TemplateLibraryError,
    infer_input_schema,
    input_accepts_field_type,
    validate_input_schema,
)
from models import db
from models.card import Card
from models.user import User


class AnswersInputSchemaTests(unittest.TestCase):
    def test_answers_input_gets_default_typing_options(self):
        schema = validate_input_schema([{"key": "answer", "type": "answers"}])
        self.assertEqual(schema, [{
            "key": "answer", "label": "answer", "type": "answers", "required": False,
            "typing": {"show_length": True, "hints": True},
        }])

    def test_typing_options_are_kept_and_completed(self):
        schema = validate_input_schema([{"key": "answer", "type": "answers", "typing": {"hints": False}}])
        self.assertEqual(schema[0]["typing"], {"show_length": True, "hints": False})

    def test_invalid_typing_definitions_are_rejected(self):
        for schema in (
            [{"key": "answer", "type": "text", "typing": {"hints": True}}],
            [{"key": "answer", "type": "answers", "typing": {"hints": "yes"}}],
            [{"key": "answer", "type": "answers", "typing": {"autosubmit": True}}],
            [{"key": "answer", "type": "answers", "typing": []}],
            [{"key": "a", "type": "answers"}, {"key": "b", "type": "answers"}],
        ):
            with self.assertRaises(TemplateLibraryError, msg=schema):
                validate_input_schema(schema)

    def test_text_and_answers_bind_to_each_other_only(self):
        self.assertTrue(input_accepts_field_type("answers", "text"))
        self.assertTrue(input_accepts_field_type("answers", "answers"))
        self.assertTrue(input_accepts_field_type("text", "answers"))
        self.assertFalse(input_accepts_field_type("answers", "richtext"))
        self.assertFalse(input_accepts_field_type("answers", "image"))
        self.assertFalse(input_accepts_field_type("image", "text"))

    def test_inferred_schema_never_creates_a_typing_input(self):
        fields = [SimpleNamespace(name="Meaning", field_type="answers")]
        schema = infer_input_schema("{{Meaning}}", "", fields)
        self.assertEqual(schema, [{"key": "Meaning", "label": "Meaning", "type": "text", "required": False}])


class TypingTemplateArtifactTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
        })

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="owner", email="owner@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
        self.client.post("/login", data={"email": "owner@example.com", "password": "password"})
        response = self.client.post("/api/note-types", json={
            "name": "Vocab",
            "field_defs": [
                {"name": "Word", "field_type": "text"},
                {"name": "Meaning", "field_type": "text"},
                {"name": "Picture", "field_type": "image"},
            ],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.note_type = response.get_json()
        self.fields = {field["name"]: field["id"] for field in self.note_type["field_defs"]}

    def tearDown(self):
        with self.app.app_context():
            db.session.rollback()
            db.session.remove()
            db.drop_all()

    def _template(self, input_schema, front="{{prompt}}"):
        response = self.client.post("/api/card-templates", json={
            "name": "Typing", "front_html": front, "back_html": "{{FrontSide}}<hr>{{answer}}",
            "input_schema": input_schema,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _attach(self, template_id, bindings):
        return self.client.post(
            f"/api/note-types/{self.note_type['id']}/template-applications",
            json={"template_id": template_id, "occurrence_key": "typing", "input_bindings": bindings},
        )

    def _typing_schema(self, typing=None):
        answer = {"key": "answer", "label": "Answer", "type": "answers", "required": True}
        if typing is not None:
            answer["typing"] = typing
        return [{"key": "prompt", "label": "Prompt", "type": "text", "required": True}, answer]

    def test_answers_input_binds_to_text_field_and_reaches_study_artifacts(self):
        template = self._template(self._typing_schema({"show_length": False}))
        self.assertEqual(template["input_schema"][1]["typing"], {"show_length": False, "hints": True})
        response = self._attach(template["id"], {"prompt": self.fields["Meaning"], "answer": self.fields["Word"]})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.assertEqual(response.get_json()["warnings"], [])
        note = self.client.post("/api/notes", json={
            "note_type_id": self.note_type["id"],
            "field_values": {"Word": "食べる\nたべる", "Meaning": "ăn"},
        })
        self.assertEqual(note.status_code, 201, note.get_json())
        with self.app.app_context():
            card = Card.query.filter_by(note_id=note.get_json()["id"], template_id=template["id"]).one()
            context = build_effective_study_card(card=card, clone_scope=None)
            artifact = build_template_artifact(context)
            self.assertEqual(artifact["typing_input"], {
                "schema_version": "study-typing-input.v1",
                "key": "answer",
                "show_length": False,
                "hints": True,
            })
            self.assertEqual(artifact["version"], template_version(context))
            content = build_content_artifact(context)
            self.assertEqual(content["field_values"]["answer"], "食べる\nたべる")

    def test_answers_input_rejects_incompatible_fields(self):
        template = self._template(self._typing_schema())
        for field in ("Picture",):
            response = self._attach(template["id"], {"prompt": self.fields["Meaning"], "answer": self.fields[field]})
            self.assertEqual(response.status_code, 400, response.get_json())

    def test_answers_field_type_is_created_saved_and_bound_but_never_switched_bare(self):
        created = self.client.post(f"/api/note-types/{self.note_type['id']}/fields", json={"name": "Accepted", "field_type": "answers"})
        self.assertEqual(created.status_code, 201, created.get_json())
        accepted_id = created.get_json()["id"]
        note = self.client.post("/api/notes", json={
            "note_type_id": self.note_type["id"],
            "field_values": {"Word": "食べる", "Accepted": "ăn\r\ndùng bữa"},
        })
        self.assertEqual(note.status_code, 201, note.get_json())
        template = self._template(self._typing_schema())
        response = self._attach(template["id"], {"prompt": self.fields["Word"], "answer": accepted_id})
        self.assertEqual(response.status_code, 201, response.get_json())
        with self.app.app_context():
            card = Card.query.filter_by(note_id=note.get_json()["id"], template_id=template["id"]).one()
            content = build_content_artifact(build_effective_study_card(card=card, clone_scope=None))
            self.assertEqual(content["field_values"]["answer"], "ăn\ndùng bữa")

        bare = self.client.patch(
            f"/api/note-types/{self.note_type['id']}/fields/{self.fields['Meaning']}",
            json={"field_type": "answers"},
        )
        self.assertEqual(bare.status_code, 409, bare.get_json())
        back = self.client.patch(f"/api/note-types/{self.note_type['id']}/fields/{accepted_id}", json={"field_type": "text"})
        self.assertEqual(back.status_code, 200, back.get_json())

    def test_templates_without_answers_input_keep_their_artifact(self):
        template = self._template([{"key": "prompt", "label": "Prompt", "type": "text", "required": True}])
        response = self._attach(template["id"], {"prompt": self.fields["Word"]})
        self.assertEqual(response.status_code, 201, response.get_json())
        note = self.client.post("/api/notes", json={"note_type_id": self.note_type["id"], "field_values": {"Word": "犬"}})
        self.assertEqual(note.status_code, 201, note.get_json())
        with self.app.app_context():
            card = Card.query.filter_by(note_id=note.get_json()["id"], template_id=template["id"]).one()
            artifact = build_template_artifact(build_effective_study_card(card=card, clone_scope=None))
            self.assertNotIn("typing_input", artifact)


if __name__ == "__main__":
    unittest.main()
