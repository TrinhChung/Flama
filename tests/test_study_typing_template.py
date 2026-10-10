"""Answers inputs, template-authored answer boxes, bindings and study artifacts.

The host typing mode is parked (STUDY_TYPING_ANSWER_PLAN §12): templates check
typed answers in their own HTML/JS. Tests of the parked behavior are skipped
and kept so the mode can be restored.
"""

import unittest
from types import SimpleNamespace

from app import create_app
from app.services.flashcard_renderer import (
    prepare_client_template_source,
    render_template_pair,
    sanitize_html_fragment,
)
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

PARKED = "Parked 2026-10-10 with the host typing mode (STUDY_TYPING_ANSWER_PLAN §12)."


class AnswersInputSchemaTests(unittest.TestCase):
    def test_answers_inputs_store_no_typing_options_and_are_not_limited(self):
        schema = validate_input_schema([
            {"key": "first", "type": "answers", "typing": {"hints": False}},
            {"key": "second", "type": "answers"},
        ])
        self.assertEqual(schema, [
            {"key": "first", "label": "first", "type": "answers", "required": False},
            {"key": "second", "label": "second", "type": "answers", "required": False},
        ])

    @unittest.skip(PARKED)
    def test_answers_input_gets_default_typing_options(self):
        schema = validate_input_schema([{"key": "answer", "type": "answers"}])
        self.assertEqual(schema, [{
            "key": "answer", "label": "answer", "type": "answers", "required": False,
            "typing": {"show_length": True, "hints": True},
        }])

    @unittest.skip(PARKED)
    def test_typing_options_are_kept_and_completed(self):
        schema = validate_input_schema([{"key": "answer", "type": "answers", "typing": {"hints": False}}])
        self.assertEqual(schema[0]["typing"], {"show_length": True, "hints": False})

    @unittest.skip(PARKED)
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

    def test_answers_input_binds_to_text_field_and_reaches_the_content_artifact(self):
        template = self._template(self._typing_schema({"show_length": False}))
        self.assertNotIn("typing", template["input_schema"][1])
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
            self.assertNotIn("typing_input", artifact)
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


class TemplateAnswerBoxTests(unittest.TestCase):
    """A template may carry its own answer box; field content may not."""

    FRONT = (
        '<div class="prompt">{{Prompt}}</div>'
        '<label for="guess">Đáp án</label>'
        '<input id="guess" type="text" placeholder="Gõ đáp án" autocomplete="off" spellcheck="false">'
        '<button type="button" id="check">Kiểm tra</button>'
        '<div id="answers" hidden>{{Answer}}</div>'
        '<script>document.getElementById("check").addEventListener("click", function () {});</script>'
    )

    def setUp(self):
        self.fields = [
            SimpleNamespace(id="f-prompt", name="Prompt", field_type="text", position=0, required=False),
            SimpleNamespace(id="f-answer", name="Answer", field_type="answers", position=1, required=False),
        ]

    def test_study_template_source_keeps_the_answer_box_and_script(self):
        prepared = prepare_client_template_source(self.FRONT, self.fields)
        self.assertIn('<label for="guess">Đáp án</label>', prepared["source"])
        self.assertIn('<input id="guess" type="text" placeholder="Gõ đáp án" autocomplete="off" spellcheck="false">', prepared["source"])
        self.assertIn('<div id="answers" hidden="">{{Answer}}</div>', prepared["source"])
        self.assertEqual(len(prepared["inline_scripts"]), 1)

    def test_server_render_keeps_the_answer_box_and_answer_lines(self):
        template = SimpleNamespace(
            id="tpl-box", updated_at="t1", front_html=self.FRONT, back_html="{{Prompt}}<hr>{{Answer}}",
            shared_css="", input_schema=None,
        )
        rendered = render_template_pair(
            template=template, field_defs=self.fields,
            field_values={"Prompt": "最低", "Answer": "tối thiểu\nít nhất"},
        )
        self.assertIn('<input id="guess" type="text"', rendered["front_html"])
        self.assertIn("tối thiểu<br>ít nhất", rendered["front_html"])
        self.assertIn("<script>", rendered["front_html"])

    def test_field_content_still_cannot_add_form_controls(self):
        self.assertEqual(sanitize_html_fragment('<input id="x" value="a">ăn<label>b</label>'), "ănb")


if __name__ == "__main__":
    unittest.main()
