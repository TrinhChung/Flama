"""Regression test suite covering multipart image upload with CSRF enabled."""

from __future__ import annotations

from io import BytesIO
from pathlib import Path
import tempfile
import unittest

from PIL import Image

from app import create_app
from models import db
from models.user import User


def _create_sample_png() -> bytes:
    img = Image.new("RGB", (64, 64), color="blue")
    buf = BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


class ImageUploadCsrfTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.upload_root = Path(self.temp_dir.name)

        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "FLASHCARD_MEDIA_UPLOAD_ROOT": str(self.upload_root),
                "WTF_CSRF_ENABLED": True,
                "SERVER_NAME": "localhost",
            }
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        db.create_all()

        self.user = User(
            email="uploader@example.com",
            username="uploader",
            is_admin=False,
        )
        self.user.set_password("password123")
        db.session.add(self.user)
        db.session.commit()

        self.client = self.app.test_client()
        self.csrf_token = "valid-test-csrf-token"

        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user.id)
            sess["_fresh"] = True
            sess["_csrf_token"] = self.csrf_token

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.ctx.pop()
        self.temp_dir.cleanup()

    def test_authenticated_image_upload_with_csrf_header_succeeds(self):
        png_bytes = _create_sample_png()

        # 1. Avatar upload with X-CSRF-Token
        resp = self.client.post(
            "/api/profile/avatar",
            data={"file": (BytesIO(png_bytes), "avatar.png")},
            headers={"X-CSRF-Token": self.csrf_token},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsNotNone(data.get("avatar_url"))

        # 2. Stage-paste image with X-CSRF-Token
        resp = self.client.post(
            "/api/browse/media/stage-paste",
            data={"file": (BytesIO(png_bytes), "paste.png")},
            headers={"X-CSRF-Token": self.csrf_token},
        )
        self.assertEqual(resp.status_code, 201)
        data = resp.get_json()
        self.assertIsNotNone(data.get("url"))

        # 3. Ticket image attachment with X-CSRF-Token
        resp = self.client.post(
            "/api/tickets/upload-image",
            data={"file": (BytesIO(png_bytes), "ticket.png")},
            headers={"X-CSRF-Token": self.csrf_token},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIsNotNone(data.get("url"))

    def test_authenticated_image_upload_with_form_csrf_token_succeeds(self):
        png_bytes = _create_sample_png()

        # 1. Avatar upload with form csrf_token field
        resp = self.client.post(
            "/api/profile/avatar",
            data={
                "file": (BytesIO(png_bytes), "avatar.png"),
                "csrf_token": self.csrf_token,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.get_json().get("avatar_url"))

        # 2. Stage-paste image with form csrf_token field
        resp = self.client.post(
            "/api/browse/media/stage-paste",
            data={
                "file": (BytesIO(png_bytes), "paste.png"),
                "csrf_token": self.csrf_token,
            },
        )
        self.assertEqual(resp.status_code, 201)
        self.assertIsNotNone(resp.get_json().get("url"))

        # 3. Ticket image attachment with form csrf_token field
        resp = self.client.post(
            "/api/tickets/upload-image",
            data={
                "file": (BytesIO(png_bytes), "ticket.png"),
                "csrf_token": self.csrf_token,
            },
        )
        self.assertEqual(resp.status_code, 200)
        self.assertIsNotNone(resp.get_json().get("url"))

    def test_authenticated_image_upload_without_csrf_is_blocked(self):
        png_bytes = _create_sample_png()

        # 1. Avatar upload without CSRF token
        resp = self.client.post(
            "/api/profile/avatar",
            data={"file": (BytesIO(png_bytes), "avatar.png")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json().get("error"), "CSRF_FAILED")

        # 2. Stage-paste image without CSRF token
        resp = self.client.post(
            "/api/browse/media/stage-paste",
            data={"file": (BytesIO(png_bytes), "paste.png")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json().get("error"), "CSRF_FAILED")

        # 3. Ticket image attachment without CSRF token
        resp = self.client.post(
            "/api/tickets/upload-image",
            data={"file": (BytesIO(png_bytes), "ticket.png")},
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json().get("error"), "CSRF_FAILED")

    def test_csrf_cookie_is_injected_on_responses(self):
        # A request to any endpoint when session has _csrf_token should set csrf_token cookie
        resp = self.client.get("/api/session")
        self.assertEqual(resp.status_code, 200)

        # Check set-cookie header contains csrf_token
        set_cookie = resp.headers.get("Set-Cookie") or ""
        self.assertIn("csrf_token=", set_cookie)
        cookie = self.client.get_cookie("csrf_token")
        self.assertIsNotNone(cookie)
        self.assertEqual(cookie.value, self.csrf_token)

    def test_non_upload_requests_continue_to_work_with_csrf(self):
        # Non-upload request without token fails
        blocked = self.client.patch(
            "/api/profile",
            json={"display_name": "New Name"},
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(blocked.get_json().get("error"), "CSRF_FAILED")

        # Non-upload request with token succeeds
        allowed = self.client.patch(
            "/api/profile",
            json={"display_name": "New Name"},
            headers={"X-CSRF-Token": self.csrf_token},
        )
        self.assertEqual(allowed.status_code, 200)
        self.assertEqual(allowed.get_json()["user"]["display_name"], "New Name")
