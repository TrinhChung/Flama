"""Unit and integration tests for dynamic default template content (GT-01)."""

import unittest

from app import create_app
from app.services.flashcards_share_service import default_template_sources
from models import db
from models.deck import Deck
from models.user import User


class TemplateDefaultContentTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    def setUp(self):
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Deck A", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    # Part A: Helper unit tests
    def test_helper_two_fields(self):
        front, back = default_template_sources([(0, "Kanji"), (1, "Meaning"), (2, "Audio")])
        self.assertEqual(front, "{{Kanji}}")
        self.assertEqual(back, "{{Kanji}}<hr>{{Meaning}}")

    def test_helper_sorts_by_position(self):
        front, back = default_template_sources([(1, "Meaning"), (0, "Kanji")])
        self.assertEqual(front, "{{Kanji}}")
        self.assertEqual(back, "{{Kanji}}<hr>{{Meaning}}")

    def test_helper_single_field(self):
        front, back = default_template_sources([(0, "Front")])
        self.assertEqual(front, "{{Front}}")
        self.assertEqual(back, "{{Front}}")

    def test_helper_skips_blank_names(self):
        front, back = default_template_sources([(0, "  "), (1, "Back")])
        self.assertEqual(front, "{{Back}}")
        self.assertEqual(back, "{{Back}}")

    def test_helper_empty_falls_back(self):
        front, back = default_template_sources([])
        self.assertEqual(front, "{{Word}}")
        self.assertEqual(back, "{{Word}}")

    def test_helper_keeps_unicode_name(self):
        front, back = default_template_sources([(0, "漢字"), (1, "Nghĩa")])
        self.assertEqual(front, "{{漢字}}")
        self.assertEqual(back, "{{漢字}}<hr>{{Nghĩa}}")

    # Part B: REST integration tests
    def test_create_note_type_without_template_uses_fields(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "NT A",
                "field_defs": [
                    {"name": "Kanji", "field_type": "text", "position": 0, "required": True},
                    {"name": "Meaning", "field_type": "text", "position": 1},
                ],
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get("templates"))
        first_tpl = data["templates"][0]
        self.assertEqual(first_tpl["front_html"], "{{Kanji}}")
        self.assertEqual(first_tpl["back_html"], "{{Kanji}}<hr>{{Meaning}}")

    def test_create_note_type_explicit_template_unchanged(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "NT A Explicit",
                "field_defs": [
                    {"name": "Kanji", "field_type": "text", "position": 0, "required": True},
                    {"name": "Meaning", "field_type": "text", "position": 1},
                ],
                "template": {
                    "front_html": "<b>{{Meaning}}</b>",
                    "back_html": "X",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get("templates"))
        first_tpl = data["templates"][0]
        self.assertEqual(first_tpl["front_html"], "<b>{{Meaning}}</b>")
        self.assertEqual(first_tpl["back_html"], "X")

    def test_create_template_defaults_to_fields(self):
        res_create = self.client.post(
            "/api/note-types",
            json={
                "name": "NT For Tpl",
                "field_defs": [
                    {"name": "Kanji", "field_type": "text", "position": 0, "required": True},
                    {"name": "Meaning", "field_type": "text", "position": 1},
                ],
            },
        )
        self.assertEqual(res_create.status_code, 201)
        nt_id = res_create.get_json()["id"]

        res_tpl = self.client.post(
            f"/api/note-types/{nt_id}/templates",
            json={"name": "Card 2"},
        )
        self.assertEqual(res_tpl.status_code, 201)
        tpl_data = res_tpl.get_json()
        self.assertEqual(tpl_data["name"], "Card 2")
        self.assertEqual(tpl_data["front_html"], "{{Kanji}}")
        self.assertEqual(tpl_data["back_html"], "{{Kanji}}<hr>{{Meaning}}")

    def test_create_template_partial_payload(self):
        res_create = self.client.post(
            "/api/note-types",
            json={
                "name": "NT For Partial Tpl",
                "field_defs": [
                    {"name": "Kanji", "field_type": "text", "position": 0, "required": True},
                    {"name": "Meaning", "field_type": "text", "position": 1},
                ],
            },
        )
        self.assertEqual(res_create.status_code, 201)
        nt_id = res_create.get_json()["id"]

        res_tpl = self.client.post(
            f"/api/note-types/{nt_id}/templates",
            json={"front_html": "{{Meaning}}"},
        )
        self.assertEqual(res_tpl.status_code, 201)
        tpl_data = res_tpl.get_json()
        self.assertEqual(tpl_data["front_html"], "{{Meaning}}")
        self.assertEqual(tpl_data["back_html"], "{{Kanji}}<hr>{{Meaning}}")

    def test_create_note_type_default_fields_still_word(self):
        response = self.client.post(
            "/api/note-types",
            json={"name": "NT B"},
        )
        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertTrue(data.get("templates"))
        first_tpl = data["templates"][0]
        self.assertEqual(first_tpl["front_html"], "{{Word}}")
        self.assertEqual(first_tpl["back_html"], "{{Word}}")


if __name__ == "__main__":
    unittest.main()
