"""REST API tests for worksheets blueprint."""

import json
import unittest

from app import create_app
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.user import User


class TestWorksheetAPI(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = User(username="worksheet_api_user", email="worksheet_api@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        note_type = NoteType(user_id=user.id, name="Standard")
        db.session.add(note_type)
        db.session.flush()

        f1 = FieldDef(note_type_id=note_type.id, name="Expression", position=0)
        f2 = FieldDef(note_type_id=note_type.id, name="Reading", position=1)
        f3 = FieldDef(note_type_id=note_type.id, name="Meaning", position=2)
        db.session.add_all([f1, f2, f3])
        db.session.flush()

        deck = Deck(name="API Test Deck", owner_user_id=user.id)
        db.session.add(deck)
        db.session.flush()

        note = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "勉強", "Reading": "べんきょう", "Meaning": "Học tập"},
        )
        db.session.add(note)
        db.session.commit()

        self.user = user
        self.deck = deck

        # Log in user
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(user.id)

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_get_templates(self):
        resp = self.client.get("/api/worksheets/templates")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("templates", data)
        self.assertGreaterEqual(len(data["templates"]), 5)

    def test_get_deck_meta(self):
        resp = self.client.get(f"/api/decks/{self.deck.id}/worksheets/meta")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["deck_id"], self.deck.id)
        self.assertEqual(data["total_notes"], 1)
        self.assertIn("suggested_mappings", data)

    def test_post_preview(self):
        payload = {
            "template_id": "kanji_stroke",
            "deck_id": self.deck.id,
            "field_mapping": {
                "kanji": "Expression",
                "reading": "Reading",
                "meaning": "Meaning",
            },
            "options": {
                "rows_per_page": 5,
            },
        }
        resp = self.client.post(
            "/api/worksheets/preview",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["template"]["id"], "kanji_stroke")
        self.assertEqual(data["total_items"], 2)  # 勉, 強
        self.assertEqual(data["total_pages"], 1)

    def test_post_render_html(self):
        payload = {
            "template_id": "kanji_stroke",
            "deck_id": self.deck.id,
            "field_mapping": {
                "kanji": "Expression",
            },
        }
        resp = self.client.post(
            "/api/worksheets/render-html",
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIn("text/html", resp.content_type)
        self.assertIn(b"<!DOCTYPE html>", resp.data)


if __name__ == "__main__":
    unittest.main()
