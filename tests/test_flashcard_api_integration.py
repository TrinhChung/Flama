"""Integration tests for flashcard API CRUD, preview, and study."""

import unittest

from app import create_app
from models import db
from models.flashcard import Card, Note, NoteType
from models.user import User
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_progress import VocabularyProgress


class FlashcardApiIntegrationTests(unittest.TestCase):
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
            user = User(username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = VocabularyDeck(name="Deck A")
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

    def _create_note_type(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Japanese Vocabulary",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Reading", "field_type": "text", "position": 1, "required": False},
                    {"name": "Meaning", "field_type": "richtext", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}} - {{Reading}} {{{Meaning}}}</div>",
                    "shared_css": ".card{color:red;}",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def test_crud_preview_flow(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "犬", "Reading": "いぬ", "Meaning": "<b>dog</b>"},
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        preview_resp = self.client.post(
            f"/api/note-types/{note_type_id}/templates/{template_id}/preview",
            json={"note_id": note_id},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.get_json()
        self.assertIn("犬", preview["front_html"])
        self.assertIn("いぬ", preview["back_html"])
        self.assertIn("<b>dog</b>", preview["back_html"])

    def test_add_field_without_schema_change(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        field_resp = self.client.post(
            f"/api/note-types/{note_type_id}/fields",
            json={"name": "PitchAccent", "field_type": "text", "required": False},
        )
        self.assertEqual(field_resp.status_code, 201)

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "橋",
                    "Reading": "はし",
                    "Meaning": "bridge",
                    "PitchAccent": "L-H",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        detail_resp = self.client.get(f"/api/notes/{note_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.get_json()["field_values"]["PitchAccent"], "L-H")

    def test_study_next_and_answer(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "猫", "Reading": "ねこ", "Meaning": "cat"},
            },
        )

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        payload = next_resp.get_json()
        self.assertIsNotNone(payload["card_id"])
        self.assertIn("猫", payload["rendered_front_html"])

        answer_resp = self.client.post(
            f"/api/study/{payload['card_id']}/answer",
            json={"rating": "good"},
        )
        self.assertEqual(answer_resp.status_code, 200)
        self.assertTrue(answer_resp.get_json()["success"])

        with self.app.app_context():
            progress = VocabularyProgress.query.filter_by(
                user_id=self.user_id,
                new_card_id=payload["card_id"],
            ).first()
            self.assertIsNotNone(progress)
            self.assertIn(progress.queue, {"learning", "review", "relearning", "new"})
            self.assertIsNotNone(progress.reps)


if __name__ == "__main__":
    unittest.main()
