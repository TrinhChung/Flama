"""Tests for temporary media staging service and endpoints."""

from __future__ import annotations

import base64
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image
from werkzeug.datastructures import FileStorage

from app import create_app
from app.services import media_staging_service
from app.services.image_security_service import ImageSecurityError
from models import db
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from models.user import User


def _create_test_image_bytes(
    format_name: str = "PNG",
    size: tuple[int, int] = (100, 100),
    color: tuple[int, int, int] = (255, 0, 0),
) -> bytes:
    img = Image.new("RGB", size, color=color)
    buf = BytesIO()
    img.save(buf, format=format_name)
    return buf.getvalue()


class MediaStagingServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = Path(self.temp_dir.name)

        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "FLASHCARD_MEDIA_UPLOAD_ROOT": str(self.upload_root),
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "localhost",
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.user = User(
            email="testuser@example.com",
            username="testuser",
        )
        self.user.set_password("test-pass")
        db.session.add(self.user)
        db.session.flush()

        self.note_type = NoteType(
            user_id=self.user.id,
            name="Vocab Note",
        )
        db.session.add(self.note_type)
        db.session.flush()

        self.field_word = FieldDef(note_type_id=self.note_type.id, name="Word", position=0, field_type="text")
        self.field_img = FieldDef(note_type_id=self.note_type.id, name="Image", position=1, field_type="image")
        db.session.add_all([self.field_word, self.field_img])
        db.session.flush()

        self.note = Note(
            user_id=self.user.id,
            note_type_id=self.note_type.id,
            field_values={"Word": "Neko", "Image": ""},
        )
        db.session.add(self.note)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_stage_pasted_image_success(self):
        png_bytes = _create_test_image_bytes("PNG", size=(200, 150))
        file_storage = FileStorage(
            stream=BytesIO(png_bytes),
            filename="paste.png",
            content_type="image/png",
        )

        result = media_staging_service.stage_pasted_image(
            user_id=self.user.id,
            file=file_storage,
            upload_root=self.upload_root,
        )

        self.assertIn("stage_id", result)
        self.assertTrue(result["url"].startswith("/media/staged/stg_"))
        self.assertEqual(result["mime_type"], "image/webp")
        self.assertEqual(result["width"], 200)
        self.assertEqual(result["height"], 150)

        # Verify staged file exists
        staged_entry = media_staging_service.get_staged_media(
            result["stage_id"],
            upload_root=self.upload_root,
        )
        self.assertIsNotNone(staged_entry)
        path, mime = staged_entry
        self.assertTrue(path.exists())
        self.assertEqual(mime, "image/webp")

    def test_stage_pasted_image_from_base64(self):
        jpeg_bytes = _create_test_image_bytes("JPEG", size=(80, 80))
        b64_str = f"data:image/jpeg;base64,{base64.b64encode(jpeg_bytes).decode('ascii')}"

        result = media_staging_service.stage_pasted_image(
            user_id=self.user.id,
            base64_data=b64_str,
            upload_root=self.upload_root,
        )

        self.assertIn("stage_id", result)
        self.assertTrue(result["url"].startswith("/media/staged/"))

    def test_stage_pasted_image_blocks_malicious_payload(self):
        fake_image = b"<html><script>alert('xss')</script></html>"
        file_storage = FileStorage(
            stream=BytesIO(fake_image),
            filename="trojan.png",
            content_type="image/png",
        )

        with self.assertRaises(ImageSecurityError):
            media_staging_service.stage_pasted_image(
                user_id=self.user.id,
                file=file_storage,
                upload_root=self.upload_root,
            )

    def test_commit_staged_media_to_permanent_asset(self):
        png_bytes = _create_test_image_bytes("PNG", size=(100, 100))
        staged = media_staging_service.stage_pasted_image(
            user_id=self.user.id,
            base64_data=base64.b64encode(png_bytes).decode("ascii"),
            upload_root=self.upload_root,
        )

        stage_id = staged["stage_id"]
        committed_url = media_staging_service.commit_staged_media(
            stage_id,
            user_id=self.user.id,
            note_id=self.note.id,
            field_name="Image",
            upload_root=self.upload_root,
        )

        self.assertIsNotNone(committed_url)
        self.assertTrue(committed_url.startswith("/media/proxy/"))

        # Verify MediaAsset was created
        asset_id = committed_url.split("/")[-1]
        asset = db.session.get(MediaAsset, asset_id)
        self.assertIsNotNone(asset)
        self.assertEqual(asset.note_id, self.note.id)
        self.assertEqual(asset.field_name, "Image")
        self.assertEqual(asset.mime_type, "image/webp")

        # Staged file should no longer exist
        self.assertIsNone(media_staging_service.get_staged_media(stage_id, upload_root=self.upload_root))

    def test_commit_all_staged_urls_in_field_values(self):
        png_bytes = _create_test_image_bytes("PNG", size=(50, 50))
        staged = media_staging_service.stage_pasted_image(
            user_id=self.user.id,
            base64_data=base64.b64encode(png_bytes).decode("ascii"),
            upload_root=self.upload_root,
        )

        field_values = {
            "Word": "Inu",
            "Image": staged["url"],
        }

        updated = media_staging_service.commit_all_staged_urls_in_field_values(
            user_id=self.user.id,
            note_id=self.note.id,
            field_values=field_values,
            upload_root=self.upload_root,
        )

        self.assertEqual(updated["Word"], "Inu")
        self.assertTrue(updated["Image"].startswith("/media/proxy/"))

    def test_http_stage_paste_and_serve(self):
        client = self.app.test_client()

        with client.session_transaction() as sess:
            sess["_user_id"] = str(self.user.id)
            sess["_fresh"] = True

        png_bytes = _create_test_image_bytes("PNG", size=(64, 64))
        response = client.post(
            "/api/browse/media/stage-paste",
            data={
                "file": (BytesIO(png_bytes), "clipboard.png", "image/png"),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(response.status_code, 201)
        data = response.get_json()
        self.assertIn("stage_id", data)
        self.assertTrue(data["url"].startswith("/media/staged/"))

        # Test serving the staged image
        stage_id = data["stage_id"]
        serve_resp = client.get(f"/media/staged/{stage_id}")
        self.assertEqual(serve_resp.status_code, 200)
        self.assertEqual(serve_resp.mimetype, "image/webp")
        self.assertEqual(serve_resp.headers.get("X-Content-Type-Options"), "nosniff")
        serve_resp.close()
