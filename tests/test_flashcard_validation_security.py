"""Security-focused integration tests for flashcard validation and media uploads."""

from __future__ import annotations

import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError
from werkzeug.datastructures import FileStorage

from app import create_app
from app.services import flashcard_media_api_service
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

_SAFE_SVG_BYTES = (
    b'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10">'
    b'<circle cx="5" cy="5" r="4" fill="red"/></svg>'
)


class FlashcardValidationSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upload_root = tempfile.TemporaryDirectory()
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": cls.upload_root.name,
                "FLASHCARD_MEDIA_MAX_BYTES": 10 * 1024 * 1024,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    @classmethod
    def tearDownClass(cls):
        cls.upload_root.cleanup()

    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory(dir=self.upload_root.name)
        self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = self.upload_tmp.name
        self.app.config["FLASHCARD_MEDIA_MAX_BYTES"] = 10 * 1024 * 1024
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

    def _create_note_type_with_markdown(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Security Markdown Note Type",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Notes", "field_type": "markdown", "position": 1, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}}</div><div>{{{Notes}}}</div>",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

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

    def test_media_fields_accept_typed_urls_and_reject_html_or_wrong_kind(self):
        note_type = self._create_note_type_with_media()
        rejected = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type["id"],
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "猫",
                    "Meaning": "Con mèo",
                    "Picture": '<svg viewBox="0 0 10 10"><circle cx="5" cy="5" r="4" fill="red"/></svg>',
                    "Sound": "/media/library/stroke_ja_65e5.svg",
                },
            },
        )
        self.assertEqual(rejected.status_code, 400)

        response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type["id"],
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "猫",
                    "Meaning": "Con mèo",
                    "Picture": "/static/strokes/ja/52c9.svg",
                    "Sound": "https://media.example.com/cat.mp3",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        note_id = response.get_json()["id"]

        detail_resp = self.client.get(f"/api/notes/{note_id}")
        self.assertEqual(detail_resp.status_code, 200)
        values = (detail_resp.get_json() or {}).get("field_values") or {}
        self.assertEqual(values.get("Picture"), "/static/strokes/ja/52c9.svg")
        self.assertEqual(values.get("Sound"), "https://media.example.com/cat.mp3")

        # Update note via patch with another URL and snippet
        patch_resp = self.client.patch(
            f"/api/notes/{note_id}",
            json={
                "field_values": {
                    "Picture": "/static/strokes/ja/52c9.svg",
                },
            },
        )
        self.assertEqual(patch_resp.status_code, 200)
        updated_values = (patch_resp.get_json() or {}).get("field_values") or {}
        self.assertEqual(updated_values.get("Picture"), "/static/strokes/ja/52c9.svg")

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

    def test_v1_upload_removes_file_when_database_commit_fails(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        with self.app.app_context():
            uploaded = FileStorage(
                stream=io.BytesIO(_MIN_PNG_BYTES),
                filename="rollback.png",
                content_type="image/png",
            )
            with patch.object(
                flashcard_media_api_service.db.session,
                "commit",
                side_effect=SQLAlchemyError("forced commit failure"),
            ):
                with self.assertRaises(SQLAlchemyError):
                    flashcard_media_api_service.upload_media(
                        user_id=self.user_id,
                        note_id=note_id,
                        field_name="Picture",
                        uploaded=uploaded,
                        upload_root=Path(self.upload_tmp.name),
                        max_bytes=10 * 1024 * 1024,
                        scanner=None,
                        scan_enabled=False,
                        markdown_inline=False,
                    )

            self.assertEqual(MediaAsset.query.filter_by(note_id=note_id).count(), 0)
            stored_files = [
                path
                for path in Path(self.upload_tmp.name).rglob("*")
                if path.is_file()
            ]
            self.assertEqual(stored_files, [])

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
            self.assertIn(asset.mime_type, {"audio/wav", "audio/x-wav"})

    def test_upload_valid_safe_svg_file(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(_SAFE_SVG_BYTES), "safe.svg", "image/svg+xml"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)

    def test_upload_rejects_svg_script_hidden_after_padding(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])
        padded_svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            + (b" " * 9_000)
            + b"<script>alert(1)</script><circle cx='5' cy='5' r='4'/></svg>"
        )

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(padded_svg), "padded.svg", "image/svg+xml"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 415)
        payload = upload_resp.get_json() or {}
        self.assertEqual(payload.get("error"), "MEDIA_SIGNATURE_INVALID")

    def test_upload_rejects_svg_external_style_url(self):
        note_type = self._create_note_type_with_media()
        note_id = self._create_note(note_type["id"])
        external_svg = (
            b'<svg xmlns="http://www.w3.org/2000/svg">'
            b'<style>circle { fill: url(https://attacker.example/payload); }</style>'
            b"<circle cx='5' cy='5' r='4'/></svg>"
        )

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Picture",
                "file": (io.BytesIO(external_svg), "external.svg", "image/svg+xml"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 415)
        payload = upload_resp.get_json() or {}
        self.assertEqual(payload.get("error"), "MEDIA_SIGNATURE_INVALID")

    def test_patch_note_accepts_audio_filename_reference(self):
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
        asset_id = (upload_resp.get_json() or {})["asset_id"]

        patch_resp = self.client.patch(
            f"/api/notes/{note_id}",
            json={"field_values": {"Sound": "voice.wav"}},
        )
        self.assertEqual(patch_resp.status_code, 200)
        payload = patch_resp.get_json() or {}
        values = payload.get("field_values") or {}
        self.assertEqual(values.get("Sound"), f"/media/proxy/{asset_id}")

    def test_patch_note_accepts_audio_sound_tag_reference(self):
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
        asset_id = (upload_resp.get_json() or {})["asset_id"]

        patch_resp = self.client.patch(
            f"/api/notes/{note_id}",
            json={"field_values": {"Sound": "[sound:voice.wav]"}},
        )
        self.assertEqual(patch_resp.status_code, 200)
        payload = patch_resp.get_json() or {}
        values = payload.get("field_values") or {}
        self.assertEqual(values.get("Sound"), f"/media/proxy/{asset_id}")

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

    def test_upload_markdown_inline_media_keeps_field_value_unchanged(self):
        note_type = self._create_note_type_with_markdown()
        create_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type["id"],
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "猫",
                    "Notes": "Nội dung markdown ban đầu",
                },
            },
        )
        self.assertEqual(create_note_resp.status_code, 201)
        note_id = create_note_resp.get_json()["id"]

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/markdown-media",
            data={
                "field_name": "Notes",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "inline.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        upload_payload = upload_resp.get_json() or {}
        first_asset_id = upload_payload.get("asset_id")
        self.assertTrue(first_asset_id)
        self.assertTrue(str(upload_payload.get("url") or "").startswith("/media/proxy/"))

        duplicate_resp = self.client.post(
            f"/api/notes/{note_id}/markdown-media",
            data={
                "field_name": "Notes",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "inline.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(duplicate_resp.status_code, 200)
        duplicate_payload = duplicate_resp.get_json() or {}
        self.assertEqual(duplicate_payload.get("asset_id"), first_asset_id)

        with self.app.app_context():
            note = Note.query.get(note_id)
            self.assertIsNotNone(note)
            self.assertEqual((note.field_values or {}).get("Notes"), "Nội dung markdown ban đầu")
            self.assertEqual(MediaAsset.query.filter_by(note_id=note_id, field_name="Notes").count(), 1)

        invalid_target_resp = self.client.post(
            f"/api/notes/{note_id}/markdown-media",
            data={
                "field_name": "Word",
                "file": (io.BytesIO(_MIN_PNG_BYTES), "inline.png", "image/png"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(invalid_target_resp.status_code, 400)
        invalid_payload = invalid_target_resp.get_json() or {}
        self.assertEqual(invalid_payload.get("field"), "field_name")

    def test_admin_users_api_rejects_sql_injection_probe_in_query(self):
        response = self.client.get("/admin/api/users?q=1 UNION SELECT")
        self.assertEqual(response.status_code, 400)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("field"), "q")

    def test_proxy_media_accessible_without_login(self):
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

        # Log out current user
        self.client.post("/logout")

        # Request media as anonymous/guest
        proxy_resp = self.client.get(f"/media/proxy/{asset_id}")
        self.assertEqual(proxy_resp.status_code, 200)
        self.assertEqual(
            proxy_resp.headers.get("Cache-Control"),
            "public, max-age=3600, s-maxage=86400",
        )
        self.assertNotIn("Vary", proxy_resp.headers)
        etag = proxy_resp.headers.get("ETag")
        self.assertTrue(etag)
        proxy_resp.close()

        conditional_resp = self.client.get(
            f"/media/proxy/{asset_id}",
            headers={"If-None-Match": etag},
        )
        self.assertEqual(conditional_resp.status_code, 304)

        self.app.config["MEDIA_PROXY_USE_XACCEL"] = True
        try:
            accel_resp = self.client.get(f"/media/proxy/{asset_id}")
            self.assertEqual(accel_resp.status_code, 200)
            self.assertTrue(
                accel_resp.headers.get("X-Accel-Redirect", "").startswith("/internal-media/")
            )
            self.assertEqual(
                accel_resp.headers.get("Cache-Control"),
                "public, max-age=3600, s-maxage=86400",
            )
        finally:
            self.app.config["MEDIA_PROXY_USE_XACCEL"] = False

    def test_proxy_media_accessible_by_other_user(self):
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

        # Create other user
        with self.app.app_context():
            other_user = User(username="other", email="other-security@example.com", is_admin=False)
            other_user.set_password("otherpassword")
            db.session.add(other_user)
            db.session.commit()

        # Log in as other user
        self.client.post("/logout")
        login_resp = self.client.post(
            "/login",
            data={"email": "other-security@example.com", "password": "otherpassword"},
            follow_redirects=True,
        )
        self.assertEqual(login_resp.status_code, 200)

        # Request media as the other user
        proxy_resp = self.client.get(f"/media/proxy/{asset_id}")
        self.assertEqual(proxy_resp.status_code, 200)
        proxy_resp.close()


if __name__ == "__main__":
    unittest.main()
