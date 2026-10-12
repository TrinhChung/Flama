"""Library filters, usage and standalone preview consumed by the React editor."""

import unittest
from sqlalchemy import event

from app import create_app
from models import db
from models.study_application import StudyApplication
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User
from tests.study_note_fixtures import create_note_user, attach_template


class TemplateLibraryFrontendContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
        })

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            for name in ("owner", "other"):
                user = create_note_user(db.session, username=name, email=f"{name}@example.com")
                user.set_password("password")
                db.session.add(user)
            db.session.commit()
        self.client.post("/login", data={"email": "owner@example.com", "password": "password"})
        self.note_types = []
        for name in ("First", "Second"):
            response = self.client.post("/api/note-types", json={
                "name": name, "field_defs": [{"name": "Word", "field_type": "text"}],
            })
            self.assertEqual(response.status_code, 201, response.get_json())
            self.note_types.append(response.get_json())
        response = self.client.post("/api/card-templates", json={
            "name": "Independent", "front_html": "<b>{{term}}</b>",
            "back_html": "{{FrontSide}}", "shared_css": "b { color: red; }",
            "input_schema": [{"key": "term", "type": "text", "required": True}],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.template = response.get_json()
        self.path = f"/api/card-templates/{self.template['id']}"

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _attach(self, index, occurrence="compat"):
        response = self.client.post(f"/api/note-types/{self.note_types[index]['id']}/template-applications", json={
            "template_id": self.template["id"], "occurrence_key": occurrence,
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _items(self, group):
        response = self.client.get(f"/api/card-templates?group={group}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["schema_version"], "template-library.v2")
        return {item["id"]: item for item in response.get_json()["items"]}

    def test_compact_pages_omit_source_and_preserve_detail_and_usage(self):
        self._attach(0)
        self._attach(1)
        with self.app.app_context():
            owner = User.query.filter_by(username="owner").one()
            other = User.query.filter_by(username="other").one()
            db.session.add_all([
                Template(owner_user_id=owner.id, name=f"Paged {index:03}",
                         front_html="x" * 16000, back_html="{{term}}", shared_css="css",
                         input_schema=[{"key": "term", "type": "text"}])
                for index in range(30)
            ])
            db.session.add(Template(owner_user_id=other.id, name="Foreign", front_html="private"))
            db.session.commit()
            loaded = []

            def capture(template, _context):
                loaded.append(template.id)

            event.listen(Template, "load", capture)
            try:
                response = self.client.get("/api/card-templates?compact=1&page=1&page_size=3")
            finally:
                event.remove(Template, "load", capture)
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["pagination"], {"page": 1, "page_size": 3, "total": 33, "has_more": True})
        self.assertEqual(len(data["items"]), 3)
        self.assertEqual(len(loaded), 3)
        for item in data["items"]:
            self.assertFalse({"front_html", "back_html", "shared_css"} & item.keys())
        reusable = next(item for item in data["items"] if item["id"] == self.template["id"])
        self.assertEqual(reusable["id"], self.template["id"])
        self.assertEqual((reusable["application_count"], reusable["note_type_count"]), (2, 2))
        detail = self.client.get(self.path).get_json()
        self.assertEqual(detail["front_html"], "<b>{{term}}</b>")
        self.assertEqual(detail["input_schema"], reusable["input_schema"])
        second = self.client.get("/api/card-templates?compact=1&page=2&page_size=3").get_json()
        self.assertFalse({item["id"] for item in data["items"]} & {item["id"] for item in second["items"]})

    def test_compact_list_preserves_legacy_input_inference(self):
        with self.app.app_context():
            owner = User.query.filter_by(username="owner").one()
            legacy = attach_template(db.session, note_type_id=self.note_types[0]["id"],
                owner_user_id=owner.id, name="Legacy", front_html="{{Word}}",
                back_html="{{FrontSide}}", input_schema=[])
            db.session.add(legacy)
            db.session.commit()
            template_id = legacy.id
        full = self.client.get("/api/card-templates?q=Legacy").get_json()["items"][0]
        compact = self.client.get("/api/card-templates?q=Legacy&compact=1&page=1").get_json()["items"][0]
        self.assertEqual(compact["id"], template_id)
        self.assertEqual(compact["input_schema"], full["input_schema"])
        self.assertEqual(compact["input_schema"][0]["key"], "Word")

    def test_invalid_pagination_returns_validation_error(self):
        for query in ("page=0", "page=-1", "page=oops", "page_size=0", "page=" + "9" * 5000):
            response = self.client.get(f"/api/card-templates?{query}")
            self.assertEqual(response.status_code, 400, response.get_json())

    def test_groups_count_active_occurrences_and_distinct_note_types(self):
        template_id = self.template["id"]
        self.assertIn(template_id, self._items("standalone"))
        self.assertNotIn(template_id, self._items("in_use"))
        first = self._attach(0)
        duplicate = self.client.post(f"/api/note-types/{self.note_types[0]['id']}/template-applications", json={
            "template_id": self.template["id"], "occurrence_key": "reverse",
        })
        self.assertEqual(duplicate.status_code, 409, duplicate.get_json())
        self.assertEqual(duplicate.get_json()["error"], "APPLICATION_EXISTS")
        self._attach(1)
        item = self._items("in_use")[template_id]
        self.assertEqual((item["application_count"], item["note_type_count"]), (2, 2))
        self.assertNotIn(template_id, self._items("standalone"))
        response = self.client.get(self.path)
        data = response.get_json()
        self.assertEqual(data["application_count"], 2)
        self.assertEqual({row["note_type_name"] for row in data["applications"]}, {"First", "Second"})
        self.assertEqual({row["application_id"] for row in data["applications"]}, {
            row["id"] for row in data["applications"]
        })
        response = self.client.delete(f"/api/note-types/{self.note_types[0]['id']}/template-applications/{first['id']}")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.client.get(self.path).get_json()["application_count"], 1)

    def test_origin_groups_and_invalid_group(self):
        self.assertIn(self.template["id"], self._items("mine"))
        self.assertNotIn(self.template["id"], self._items("market"))
        with self.app.app_context():
            db.session.get(Template, self.template["id"]).origin = "market_copy"
            db.session.commit()
        self.assertNotIn(self.template["id"], self._items("mine"))
        self.assertIn(self.template["id"], self._items("market"))
        response = self.client.get("/api/card-templates?group=unknown")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["field"], "group")

    def test_legacy_multiple_applications_list_one_definition_with_distinct_note_count(self):
        from models.note import Note
        self._attach(0)
        with self.app.app_context():
            owner = User.query.filter_by(username="owner").one()
            note = Note(user_id=owner.id, note_type_id=self.note_types[0]["id"],
                        field_values={"Word": "word"})
            db.session.add(note)
            db.session.add(StudyApplication(note_type_id=self.note_types[0]["id"],
                template_id=self.template["id"], occurrence_key="historical-repeat",
                status_code="ACTIVE", position=9))
            db.session.commit()
        response = self.client.get(f"/api/note-types/{self.note_types[0]['id']}/templates")
        self.assertEqual(response.status_code, 200, response.get_json())
        matches = [item for item in response.get_json()["items"]
                   if item["id"] == self.template["id"]]
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0]["note_count"], 1)

    def test_note_type_template_list_includes_active_shared_definition_and_scopes_counts(self):
        from models.card import Card
        from models.note import Note
        first = self._attach(0)
        second = self._attach(1)
        response = self.client.patch(f"/api/note-types/{self.note_types[0]['id']}/template-applications/{first['id']}", json={"position": 7, "is_default": True})
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            owner = User.query.filter_by(username="owner").one()
            for index, applications in ((0, [first]), (1, [second])):
                count = 1 if index == 0 else 2
                for _ in range(count):
                    note = Note(user_id=owner.id, note_type_id=self.note_types[index]["id"], field_values={"Word": "word"})
                    db.session.add(note)
                    db.session.flush()
                    self.assertEqual(Card.query.filter_by(note_id=note.id,
                        template_id=self.template["id"]).count(), len(applications))
            db.session.commit()
        for index, expected in ((0, 1), (1, 2)):
            response = self.client.get(f"/api/note-types/{self.note_types[index]['id']}/templates")
            self.assertEqual(response.status_code, 200, response.get_json())
            matching = [item for item in response.get_json()["items"] if item["id"] == self.template["id"]]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["note_count"], expected)
            self.assertEqual(matching[0]["note_type_id"], self.note_types[index]["id"])
            if index == 0:
                self.assertEqual(matching[0]["position"], 7)
        self.client.delete(f"/api/note-types/{self.note_types[0]['id']}/template-applications/{first['id']}")
        response = self.client.get(f"/api/note-types/{self.note_types[0]['id']}/templates")
        self.assertNotIn(self.template["id"], {item["id"] for item in response.get_json()["items"]})
        with self.app.app_context():
            self.assertEqual(Card.query.filter_by(template_id=self.template["id"]).count(), 2)
            from models.card import INCLUDE_RETIRED_CARDS
            self.assertEqual(Card.query.filter_by(template_id=self.template["id"])
                .execution_options(**{INCLUDE_RETIRED_CARDS: True}).count(), 3)

    def test_preview_renders_draft_and_preserves_source_and_history(self):
        before = self.client.get(self.path).get_json()
        history = self.client.get(self.path + "/versions").get_json()
        response = self.client.post(self.path + "/preview", json={
            "front_html": "<i>{{term}}</i>", "back_html": "<p>{{term}}</p>",
            "sample_values": {"term": "犬"},
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        data = response.get_json()
        self.assertIn("<i>犬</i>", data["front_html"])
        self.assertIn("<p>犬</p>", data["back_html"])
        self.assertIn("front_renderer_payload", data)
        self.assertIn("back_renderer_payload", data)
        self.assertIn("no-store", response.headers["Cache-Control"])
        self.assertEqual(self.client.get(self.path).get_json(), before)
        self.assertEqual(self.client.get(self.path + "/versions").get_json(), history)

    def test_preview_validates_input_schema_samples_and_compile_without_writes(self):
        response = self.client.post(self.path + "/preview", json={
            "front_html": "{{new_input}}", "input_schema": [{"key": "new_input"}],
            "sample_values": {"new_input": "猫"},
        })
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertIn("猫", response.get_json()["front_html"])
        for payload, code in (
            ([], "VALIDATION_ERROR"),
            ({"sample_values": []}, "VALIDATION_ERROR"),
            ({"sample_values": {"unknown": "x"}}, "INPUT_NOT_FOUND"),
            ({"sample_values": {"term": 1}}, "VALIDATION_ERROR"),
            ({"sample_values": {"term": "x" * 100001}}, "VALIDATION_ERROR"),
            ({"input_schema": [{"key": "FrontSide"}]}, "VALIDATION_ERROR"),
            ({"front_html": "{{#unclosed}}"}, "TEMPLATE_COMPILE_ERROR"),
        ):
            with self.subTest(code=code, keys=list(payload) if isinstance(payload, dict) else payload):
                response = self.client.post(self.path + "/preview", json=payload)
                self.assertEqual(response.status_code, 400, response.get_json())
                self.assertEqual(response.get_json()["error"], code)
        with self.app.app_context():
            self.assertEqual(TemplateVersion.query.filter_by(template_id=self.template["id"]).count(), 1)
            self.assertEqual(db.session.get(Template, self.template["id"]).front_html, self.template["front_html"])

    def test_foreign_usage_is_hidden_and_preview_requires_ownership(self):
        self._attach(0)
        self.client.post("/logout")
        self.client.post("/login", data={"email": "other@example.com", "password": "password"})
        other_type = self.client.post("/api/note-types", json={
            "name": "Private", "field_defs": [{"name": "Secret", "field_type": "text"}],
        }).get_json()
        with self.app.app_context():
            db.session.add(StudyApplication(
                note_type_id=other_type["id"], template_id=self.template["id"],
                occurrence_key="foreign", status_code="ACTIVE", input_bindings={},
            ))
            db.session.commit()
        self.assertNotIn(self.template["id"], self._items("all"))
        self.assertEqual(self.client.post(self.path + "/preview", json={}).status_code, 404)
        self.client.post("/logout")
        self.assertEqual(self.client.post(self.path + "/preview", json={}).status_code, 401)
        self.client.post("/login", data={"email": "owner@example.com", "password": "password"})
        data = self.client.get(self.path).get_json()
        self.assertEqual((data["application_count"], data["note_type_count"]), (1, 1))
        self.assertEqual([row["note_type_name"] for row in data["applications"]], ["First"])
