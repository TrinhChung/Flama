"""Security-focused integration tests for flashcard validation and media uploads."""

from __future__ import annotations

import io
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


class FlashcardValidationSecurityTests(unittest.TestCase):
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
            user = User(username="admin", email="admin-security@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Security Deck")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin-security@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _create_note_type_with_media(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Security Note Type",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Meaning", "field_type": "richtext", "position": 1, "required": False},
                    {"name": "Picture", "field_type": "image", "position": 2, "required": False},
                    {"name": "Sound", "field_type": "audio", "position": 3, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}}</div><div>{{{Meaning}}}</div>{{{Picture}}}{{{Sound}}}",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _create_note(self, note_type_id: str, *, word: str = "犬", meaning: str = "<b>dog</b>") -> str:
        response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": word,
                    "Meaning": meaning,
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["id"]

    def test_text_input_normal_and_richtext_sanitized(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(
            note_type["id"],
            word="猫",
            meaning="<b>cat</b><script>alert(1)</script>",
        )

        detail_resp = self.client.get(f"/api/notes/{note_id}")
        self.assertEqual(detail_resp.status_code, 200)
        values = (detail_resp.get_json() or {}).get("field_values") or {}
        self.assertEqual(values.get("Word"), "猫")
        self.assertIn("<b>cat</b>", values.get("Meaning", ""))
        self.assertNotIn("<script>", values.get("Meaning", ""))

    def test_text_input_rejects_basic_xss_payload(self):
        note_type = self._create_note_type_with_media()
        response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type["id"],
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "<script>alert(1)</script>",
                    "Meaning": "ok",
                },
            },
        )
        self.assertEqual(response.status_code, 400)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("error"), "VALIDATION_ERROR")
        self.assertEqual(payload.get("field"), "Word")

    def test_upload_valid_image_file(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "normal.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        asset_id = (upload_resp.get_json() or {}).get("asset_id")
        self.assertTrue(asset_id)

        proxy_resp = self.client.get(f"/media/proxy/{asset_id}")
        self.assertEqual(proxy_resp.status_code, 200)
        _ = proxy_resp.get_data()
        proxy_resp.close()
        self.assertEqual(proxy_resp.headers.get("X-Content-Type-Options"), "nosniff")

    def test_upload_valid_audio_file(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Sound",
                "file": (io.BytesIO(_MIN_WAV_BYTES), "voice.wav", "audio/wav"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)

        with self.app.app_context():
            asset_id = (upload_resp.get_json() or {}).get("asset_id")
            asset = MediaAsset.query.get(asset_id)
            self.assertIsNotNone(asset)
            self.assertEqual(asset.mime_type, "audio/wav")

    def test_upload_rejects_fake_extension(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(b"MZ-not-an-image"), "fake.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 415)
        payload = upload_resp.get_json() or {}
        self.assertIn(payload.get("error"), {"MEDIA_SIGNATURE_INVALID", "MEDIA_TYPE_NOT_ALLOWED"})

    def test_upload_rejects_file_over_size_limit(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])
        self.app.config["FLASHCARD_MEDIA_MAX_BYTES"] = 8

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "too-large.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 413)
        payload = upload_resp.get_json() or {}
        self.assertEqual(payload.get("error"), "MEDIA_TOO_LARGE")

    def test_upload_handles_abnormal_filename_and_safe_storage_path(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "../../evil<script>.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        asset_id = (upload_resp.get_json() or {}).get("asset_id")

        with self.app.app_context():
            asset = MediaAsset.query.get(asset_id)
            self.assertIsNotNone(asset)
            self.assertNotIn("..", asset.filename)
            self.assertNotIn("<", asset.filename)
            self.assertNotIn("..", asset.storage_path)

            upload_root = Path(self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
            full_path = (upload_root / asset.storage_path).resolve()
            self.assertTrue(full_path.is_file())
            self.assertTrue(str(full_path).startswith(str(upload_root)))

            note = Note.query.get(note_id)
            self.assertIsNotNone(note)
            self.assertIn("Picture", note.field_values or {})

    def test_browse_cards_rejects_sql_injection_probe_in_query(self):
        note_type = self._create_note_type_with_media()
        self._create_note(note_type["id"], word="犬", meaning="dog")

        response = self.client.get("/vocabulary/api/browse/cards?q=' OR 1=1 --")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("field"), "q")

    def test_admin_users_api_rejects_sql_injection_probe_in_query(self):
        response = self.client.get("/admin/api/users?q=1 UNION SELECT")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("field"), "q")


if __name__ == "__main__":
    unittest.main()
