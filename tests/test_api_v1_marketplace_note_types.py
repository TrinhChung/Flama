"""Unit tests for REST API V1 marketplace note type & template resources."""

import unittest

from app import create_app
from models import db
from models.field_def import FieldDef
from models.note_type import NoteType
from models.template import Template
from models.user import User



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

    def test_recommendations_endpoint(self):
        self._login("learner@example.com")

        res = self.client.get("/api/marketplace/note-types/recommendations")
        self.assertEqual(res.status_code, 200)
        self.assertIn("recommended_for_you", res.get_json())



if __name__ == "__main__":
    unittest.main()
