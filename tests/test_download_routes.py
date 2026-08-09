"""Unit tests for desktop applications and tools download endpoints."""

from __future__ import annotations

import os
import tempfile
import unittest
from unittest.mock import patch

from app import create_app
from app.api.v1.download import DEFAULT_FLAMA_AUDIO_RELEASE_URL
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

    def test_download_flama_audio_default_redirect(self):
        """Test default redirect to GitHub release asset when no custom URL or local asset exists."""
        with patch.dict(os.environ, {}, clear=True):
            response = self.client.get("/api/download/flama-audio")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], DEFAULT_FLAMA_AUDIO_RELEASE_URL)

    def test_download_flama_audio_custom_env_url_redirect(self):
        """Test redirecting to custom FLAMA_AUDIO_DOWNLOAD_URL when set."""
        custom_url = "https://cdn.example.com/FlamaAudio-Setup.exe"
        with patch.dict(os.environ, {"FLAMA_AUDIO_DOWNLOAD_URL": custom_url}):
            response = self.client.get("/api/download/flama-audio")
            self.assertEqual(response.status_code, 302)
            self.assertEqual(response.headers["Location"], custom_url)

    def test_download_flama_audio_serves_local_file_if_present(self):
        """Test serving local static executable when present in static/downloads."""
        original_static = self.app.static_folder
        with tempfile.TemporaryDirectory() as temp_static:
            downloads_dir = os.path.join(temp_static, "downloads")
            os.makedirs(downloads_dir, exist_ok=True)
            installer_path = os.path.join(downloads_dir, "FlamaAudio-Setup.exe")
            with open(installer_path, "wb") as f:
                f.write(b"MZ-MOCK-EXE-CONTENT")

            self.app.static_folder = temp_static
            response = self.client.get("/api/download/flama-audio")
            self.assertEqual(response.status_code, 200)
            self.assertEqual(response.data, b"MZ-MOCK-EXE-CONTENT")
            self.assertIn("FlamaAudio-Setup.exe", response.headers.get("Content-Disposition", ""))
            response.close()
            self.app.static_folder = original_static


if __name__ == "__main__":
    unittest.main()
