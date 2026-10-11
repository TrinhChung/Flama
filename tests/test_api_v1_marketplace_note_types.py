"""Unit tests for REST API V1 marketplace note type & template resources."""

import unittest

from app import create_app
from models import db
from models.field_def import FieldDef
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note import Note
from models.template import Template
from models.user import User
from models.deck import Deck



class MarketplaceNoteTypesApiV1Tests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Author user
            author = User(
                username="author",
                email="author@example.com",
                is_admin=False,
            )
            author.set_password("password123")
            db.session.add(author)
            db.session.flush()
            self.author_id = author.id

            # Learner user
            learner = User(
                username="learner",
                email="learner@example.com",
                is_admin=False,
            )
            learner.set_password("password123")
            db.session.add(learner)
            db.session.flush()
            self.learner_id = learner.id

            # Create NoteType with FieldDef and Template
            note_type = NoteType(
                name="Japanese Vocab Model",
                description="Sample description for Japanese Vocab Model",
                user_id=author.id,
                publish_status="published",
                pricing_mode="free",
                primary_category="Vocabulary",
                preview_text="Sample preview text",
                version="1.0.0",
            )

            db.session.add(note_type)
            db.session.flush()

            field1 = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                position=0,
                field_type="text",
            )
            field2 = FieldDef(
                note_type_id=note_type.id,
                name="Meaning",
                position=1,
                field_type="text",
            )
            db.session.add_all([field1, field2])

            template = Template(
                note_type_id=note_type.id,
                name="Card 1",
                front_html="<div>{{Word}}</div>",
                back_html="<div>{{FrontSide}}<hr>{{Meaning}}</div>",
                shared_css="body { font-family: sans-serif; }",
                position=0,
            )
            db.session.add(template)
            db.session.commit()

            self.note_type_id = note_type.id
            self.template_id = template.id

    def _login(self, email="learner@example.com", password="password123"):
        res = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": password},
        )
        self.assertEqual(res.status_code, 200)

    def test_hub_and_list_note_types(self):
        self._login("learner@example.com")


        # Test hub canonical /api/marketplace/note-types/hub
        res = self.client.get("/api/marketplace/note-types/hub")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("marketplace", data)

        # Test list canonical /api/marketplace/note-types
        res = self.client.get("/api/marketplace/note-types")
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("items", data)
        self.assertGreaterEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["id"], self.note_type_id)

    def test_get_detail_and_preview_template(self):
        self._login("learner@example.com")

        # Get detail canonical V1
        res = self.client.get(f"/api/marketplace/note-types/{self.note_type_id}")
        self.assertEqual(res.status_code, 200)
        detail = res.get_json()
        self.assertEqual(detail["id"], self.note_type_id)
        self.assertFalse(detail["is_installed"])

        # Preview template V1
        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/templates/{self.template_id}/preview"
        )
        self.assertEqual(res.status_code, 200)
        preview = res.get_json()
        self.assertIn("front_html", preview)
        self.assertIn("back_html", preview)
        self.assertIn("Word", preview["front_html"])

    def test_compact_list_keeps_definitions_in_detail_only(self):
        self._login("learner@example.com")
        response = self.client.get("/api/shared/note-types?compact=1&page=1&page_size=24")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["pagination"]["total"], 1)
        self.assertEqual(data["items"][0]["id"], self.note_type_id)
        self.assertNotIn("templates", data["items"][0])
        self.assertNotIn("field_defs", data["items"][0])
        detail = self.client.get(f"/api/shared/note-types/{self.note_type_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(len(detail.get_json()["templates"]), 1)
        self.assertEqual(len(detail.get_json()["field_defs"]), 2)

    def test_save_and_install_note_type(self):
        self._login("learner@example.com")

        # Save item
        res = self.client.post(f"/api/marketplace/note-types/{self.note_type_id}/save")
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.get_json()["saved"])

        # Unsave item
        res = self.client.delete(
            f"/api/marketplace/note-types/{self.note_type_id}/save"
        )
        self.assertEqual(res.status_code, 200)
        self.assertFalse(res.get_json()["saved"])

        # Install free item
        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/install"
        )
        self.assertEqual(res.status_code, 201)
        install_data = res.get_json()
        self.assertEqual(install_data["source_note_type_id"], self.note_type_id)
        self.assertIn("installed_note_type_id", install_data)

    def test_installed_note_type_cannot_be_redistributed(self):
        self._login("learner@example.com")
        install_response = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/install"
        )
        self.assertEqual(install_response.status_code, 201)
        installed_note_type_id = install_response.get_json()["installed_note_type_id"]

        library_response = self.client.get("/api/note-types")
        installed_row = next(
            row
            for row in library_response.get_json()["items"]
            if row["id"] == installed_note_type_id
        )
        self.assertTrue(installed_row["is_marketplace_install"])

        republish_response = self.client.post(
            f"/api/note-types/{installed_note_type_id}/publish",
            json={},
        )
        self.assertEqual(republish_response.status_code, 409)
        self.assertEqual(republish_response.get_json()["error"], "CONFLICT")

        patch_publish_response = self.client.patch(
            f"/api/note-types/{installed_note_type_id}",
            json={"publish_status": "published"},
        )
        self.assertEqual(patch_publish_response.status_code, 409)
        self.assertEqual(patch_publish_response.get_json()["error"], "CONFLICT")

        with self.app.app_context():
            learner_deck = Deck(name="Learner installed template deck", owner_user_id=self.learner_id)
            db.session.add(learner_deck)
            db.session.flush()
            db.session.add(
                Note(
                    note_type_id=installed_note_type_id,
                    user_id=self.learner_id,
                    deck_id=learner_deck.id,
                    field_values={"Word": "private copy", "Meaning": "must not redistribute"},
                )
            )
            db.session.commit()
            learner_deck_id = learner_deck.id

        publish_options_response = self.client.get("/api/shared/decks/publish-options")
        learner_deck_option = next(
            row
            for row in publish_options_response.get_json()["items"]
            if row["id"] == learner_deck_id
        )
        self.assertFalse(learner_deck_option["is_selectable"])
        self.assertEqual(learner_deck_option["block_code"], "marketplace_note_type")

        deck_republish_response = self.client.post(
            "/api/shared/decks",
            json={
                "title": "Installed template redistribution",
                "source_deck_id": learner_deck_id,
                "source_note_type_id": installed_note_type_id,
            },
        )
        self.assertEqual(deck_republish_response.status_code, 409)
        self.assertEqual(deck_republish_response.get_json()["field"], "source_deck_id")

        author_client = self.app.test_client()
        login_response = author_client.post(
            "/api/auth/login",
            json={"email": "author@example.com", "password": "password123"},
        )
        self.assertEqual(login_response.status_code, 200)
        delete_source_response = author_client.delete(
            f"/api/note-types/{self.note_type_id}"
        )
        self.assertEqual(delete_source_response.status_code, 200)
        self.assertTrue(delete_source_response.get_json()["archived"])
        with self.app.app_context():
            source_note_type = db.session.get(NoteType, self.note_type_id)
            self.assertIsNotNone(source_note_type)
            self.assertEqual(source_note_type.publish_status, "archived")
            self.assertEqual(
                NoteTypeInstall.query.filter_by(
                    source_note_type_id=self.note_type_id,
                    user_id=self.learner_id,
                ).count(),
                1,
            )

    def test_owner_cannot_install_own_note_type(self):
        self._login("author@example.com")

        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/install"
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "VALIDATION_ERROR")

    def test_publish_note_type(self):
        self._login("author@example.com")

        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/publish",
            json={
                "publish_status": "unlisted",
                "description": "Custom vocab note type",
                "domain": "japanese",
                "subject": "japanese",
                "difficulty_band": "beginner",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["meaning_recall"],
            },
        )
        self.assertEqual(res.status_code, 200)
        self.assertEqual(res.get_json()["publish_status"], "unlisted")

    def test_publish_note_type_accepts_react_professional_taxonomy(self):
        self._login("author@example.com")
        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/publish",
            json={
                "publish_status": "published",
                "description": "Professional coding template",
                "primary_category": "Custom Technology",
                "domain": "professional_skills",
                "subject": "it_coding",
                "difficulty_band": "intermediate",
                "learning_goals": ["concept_recall"],
                "primary_topics": ["business"],
            },
        )
        self.assertEqual(res.status_code, 200)
        payload = res.get_json()
        self.assertEqual(payload["primary_category"], "Custom Technology")
        self.assertEqual(payload["taxonomy_metadata"]["subject"], "it_coding")

    def test_recommendations_endpoint(self):
        self._login("learner@example.com")

        res = self.client.get("/api/marketplace/note-types/recommendations")
        self.assertEqual(res.status_code, 200)
        self.assertIn("recommended_for_you", res.get_json())

    def test_install_shared_note_type_template_success(self):
        self._login("learner@example.com")

        # Before installation, detail should show is_installed: False
        detail_res = self.client.get(f"/api/marketplace/note-types/{self.note_type_id}")
        self.assertEqual(detail_res.status_code, 200)
        templates = detail_res.get_json().get("templates", [])
        self.assertTrue(len(templates) > 0)
        self.assertFalse(templates[0].get("is_installed", False))

        # Install individual template
        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/templates/{self.template_id}/install"
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["source_template_id"], self.template_id)
        self.assertFalse(data["already_installed"])
        local_template_id = data["local_template_id"]
        self.assertIsNotNone(local_template_id)

        # Installing again returns already_installed: True
        res_again = self.client.post(
            f"/api/shared/note-types/{self.note_type_id}/templates/{self.template_id}/install"
        )
        self.assertEqual(res_again.status_code, 200)
        self.assertTrue(res_again.get_json()["already_installed"])
        self.assertEqual(res_again.get_json()["local_template_id"], local_template_id)

        # Now detail endpoint should show template as installed
        detail_res2 = self.client.get(f"/api/marketplace/note-types/{self.note_type_id}")
        self.assertEqual(detail_res2.status_code, 200)
        templates2 = detail_res2.get_json().get("templates", [])
        self.assertTrue(templates2[0].get("is_installed"))
        self.assertEqual(templates2[0].get("installed_template_id"), local_template_id)

    def test_install_shared_note_type_template_as_owner_fails(self):
        self._login("author@example.com")
        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/templates/{self.template_id}/install"
        )
        self.assertEqual(res.status_code, 409)
        self.assertEqual(res.get_json()["error"], "VALIDATION_ERROR")

    def test_install_shared_note_type_template_invalid_template(self):
        self._login("learner@example.com")
        res = self.client.post(
            f"/api/marketplace/note-types/{self.note_type_id}/templates/non-existent-id/install"
        )
        self.assertEqual(res.status_code, 404)


if __name__ == "__main__":
    unittest.main()

