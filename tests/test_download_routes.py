"""Unit tests for desktop applications and tools download endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from app.api.v1.download import FLAMA_AUDIO_FILENAME
from models import db


class TestDownloadRoutes(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_download_flama_audio_returns_unavailable_without_release(self):
        """Return a clear failure instead of redirecting to a missing release asset."""
        with (
            patch.dict(os.environ, {}, clear=True),
            patch("app.api.v1.download.os.path.isfile", return_value=False),
        ):
            response = self.client.get("/api/download/flama-audio")
            self.assertEqual(response.status_code, 503)

    def test_download_flama_audio_custom_env_url_redirect(self):
        """Test redirecting to custom FLAMA_AUDIO_DOWNLOAD_URL when set."""
        custom_url = f"https://cdn.example.com/{FLAMA_AUDIO_FILENAME}"
        with (
            patch.dict(os.environ, {"FLAMA_AUDIO_DOWNLOAD_URL": custom_url}),
            patch("app.api.v1.download.os.path.isfile", return_value=False),
        ):
            response = self.client.get("/api/download/flama-audio")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], custom_url)

    def test_download_flama_audio_serves_local_file_if_present(self):
        """Test serving local static executable when present in static/downloads."""
        original_static = self.app.static_folder
        with tempfile.TemporaryDirectory() as temp_static:
            downloads_dir = os.path.join(temp_static, "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            executable_path = os.path.join(downloads_dir, FLAMA_AUDIO_FILENAME)
            with open(executable_path, "wb") as f:
                f.write(b"MZ-MOCK-EXE-CONTENT")

            self.app.static_folder = temp_static
            response = self.client.get("/api/download/flama-audio")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"MZ-MOCK-EXE-CONTENT")
            self.assertIn(FLAMA_AUDIO_FILENAME, response.headers.get("Content-Disposition", ""))
            response.close()
            self.app.static_folder = original_static

    def test_download_flama_audio_serves_persistent_server_file(self):
        """Serve the portable executable from the persistent VPS download path."""
        original_static = self.app.static_folder
        with tempfile.TemporaryDirectory() as temp_dir:
            executable_path = os.path.join(temp_dir, FLAMA_AUDIO_FILENAME)
            with open(executable_path, "wb") as executable:
                executable.write(b"MZ-PERSISTENT-EXE-CONTENT")

            self.app.static_folder = None
            with patch(
                "app.api.v1.download.SYSTEM_FLAMA_AUDIO_PATH",
                executable_path,
            ):
                response = self.client.get("/api/download/flama-audio")

            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"MZ-PERSISTENT-EXE-CONTENT")
            self.assertIn(FLAMA_AUDIO_FILENAME, response.headers.get("Content-Disposition", ""))
            response.close()
            self.app.static_folder = original_static


if __name__ == "__main__":
    unittest.main()
