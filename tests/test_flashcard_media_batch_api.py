"""Integration tests for batch flashcard media uploads."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from pathlib import Path

from app import create_app
from models import db
from models.deck import Deck
from models.flashcard import MediaAsset, Note
from models.user import User


_MIN_PNG_BYTES = (
    b"\x89PNG\r\n\x1a\n"
    b"\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde"
    b"\x00\x00\x00\nIDATx\x9cc`\x00\x00\x00\x02\x00\x01\xe2!\xbc3"
    b"\x00\x00\x00\x00IEND\xaeB`\x82"
)

_MIN_WAV_BYTES = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


class FlashcardMediaBatchApiTests(unittest.TestCase):
    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": self.upload_tmp.name,
                "FLASHCARD_MEDIA_MAX_BYTES": 10 * 1024 * 1024,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username="batchuser", email="batch@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Batch Deck")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "batch@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _create_note_type(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Batch Note Type",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Picture", "field_type": "image", "position": 1, "required": False},
                    {"name": "Sound", "field_type": "audio", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}}</div>{{{Picture}}}{{{Sound}}}",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _create_note(self, note_type_id: str, word: str = "Test"):
        response = self.client.post(
            "/api/notes",
            json={
                "deck_id": self.deck_id,
                "note_type_id": note_type_id,
                "field_values": {"Word": word, "Picture": "", "Sound": ""},
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["id"]

    def test_batch_upload_successful(self):
        note_type = self._create_note_type()
        note_id_1 = self._create_note(note_type["id"], word="One")
        note_id_2 = self._create_note(note_type["id"], word="Two")

        manifest = [
            {"item_id": "item_1", "note_id": note_id_1, "field_name": "Sound", "file_key": "file_0"},
            {"item_id": "item_2", "note_id": note_id_2, "field_name": "Sound", "file_key": "file_1"},
        ]

        response = self.client.post(
            "/api/notes/media/batch",
            data={
                "manifest": json.dumps(manifest),
                "file_0": (io.BytesIO(_MIN_WAV_BYTES), "sound1.wav", "audio/wav"),
                "file_1": (io.BytesIO(_MIN_WAV_BYTES), "sound2.wav", "audio/wav"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["success_count"], 2)
        self.assertEqual(data["failed_count"], 0)
        self.assertEqual(len(data["items"]), 2)

        with self.app.app_context():
            note1 = Note.query.get(note_id_1)
            note2 = Note.query.get(note_id_2)
            self.assertTrue(note1.field_values.get("Sound"))
            self.assertTrue(note2.field_values.get("Sound"))

    def test_batch_upload_partial_errors(self):
        note_type = self._create_note_type()
        note_id_1 = self._create_note(note_type["id"], word="Valid")

        manifest = [
            {"item_id": "item_1", "note_id": note_id_1, "field_name": "Sound", "file_key": "file_0"},
            {"item_id": "item_2", "note_id": "non_existent_note_id", "field_name": "Sound", "file_key": "file_1"},
        ]

        response = self.client.post(
            "/api/notes/media/batch",
            data={
                "manifest": json.dumps(manifest),
                "file_0": (io.BytesIO(_MIN_WAV_BYTES), "sound1.wav", "audio/wav"),
                "file_1": (io.BytesIO(_MIN_WAV_BYTES), "sound2.wav", "audio/wav"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data["success"])
        self.assertEqual(data["success_count"], 1)
        self.assertEqual(data["failed_count"], 1)

    def test_batch_upload_empty_manifest_fails(self):
        response = self.client.post(
            "/api/notes/media/batch",
            data={"manifest": "[]"},
            content_type="multipart/form-data",
        )
        self.assertEqual(response.status_code, 400)
