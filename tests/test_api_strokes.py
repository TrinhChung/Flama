"""Tests for Strokes REST API endpoints."""

import json
import unittest
from app import create_app
from models import db
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.user import User


class TestApiStrokes(unittest.TestCase):
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

        user = User(username="api_stroke_user", email="api_stroke_user@example.com")
        user.set_password("password123")
        db.session.add(user)
        db.session.flush()

        note_type = NoteType(user_id=user.id, name="Test Note Type")
        deck = Deck(name="Test Deck", owner_user_id=user.id)
        db.session.add_all([note_type, deck])
        db.session.flush()

        note = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "日本語を勉強する", "Meaning": "To study Japanese"},
        )
        db.session.add(note)
        db.session.commit()

        self.user = user
        self.deck = deck
        self.note = note

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user.id)
            sess["_fresh"] = True

    def test_generate_strokes_api(self):
        self._login()
        res = self.client.post(
            "/api/strokes/generate",
            json={
                "text": "日本語を勉強する",
                "locale": "ja",
                "format": "html",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["characters"], ["日", "本", "語", "勉", "強"])
        self.assertIn("flama-stroke-diagram", data["output"])
        self.assertIn("/static/strokes/ja/52c9.svg", data["output"])

    def test_generate_strokes_chinese_api(self):
        self._login()
        res = self.client.post(
            "/api/strokes/generate",
            json={
                "text": "学习中文",
                "locale": "zh-CN",
                "format": "html",
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["characters"], ["学", "习", "中", "文"])
        self.assertIn("/static/strokes/zh/5b66.svg", data["output"])

    def test_batch_generate_strokes_api(self):
        self._login()
        res = self.client.post(
            f"/api/decks/{self.deck.id}/strokes/batch-generate",
            json={
                "source_field": "Expression",
                "target_field": "StrokeDiagram",
                "locale": "ja",
                "overwrite": True,
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertEqual(data["total_processed"], 1)
        self.assertEqual(data["updated"], 1)

        db.session.refresh(self.note)
        self.assertIn("/static/strokes/ja/52c9.svg", self.note.field_values.get("StrokeDiagram", ""))


if __name__ == "__main__":
    unittest.main()
