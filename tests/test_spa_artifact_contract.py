"""Contract between Flask SPA delivery and the real Vite build artifact."""

from __future__ import annotations

import os
from pathlib import Path
import unittest

from app import create_app
from models import db


ROOT = Path(__file__).resolve().parents[1]
SPA_INDEX = ROOT / "frontend" / "dist" / "index.html"


@unittest.skipUnless(
    os.getenv("FLAMA_REQUIRE_REAL_SPA_ARTIFACT") == "1",
    "real SPA artifact contract runs in its dedicated CI tier",
)
class SpaArtifactContractTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "SPA_TEST_SHELL_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_real_vite_index_is_served_by_flask(self):
        self.assertTrue(SPA_INDEX.is_file(), "frontend/dist/index.html is missing")
        artifact = SPA_INDEX.read_text(encoding="utf-8")
        self.assertIn('id="root"', artifact)

        response = self.client.get("/dashboard")
        try:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'id="root"', response.data)
        finally:
            response.close()

    def test_real_vite_root_assets_are_served_with_their_original_bytes(self):
        for name, content_types in (
            ("favicon.svg", {"image/svg+xml"}),
            ("favicon.ico", {"image/x-icon", "image/vnd.microsoft.icon"}),
            ("logo.png", {"image/png"}),
        ):
            with self.subTest(name=name):
                artifact = SPA_INDEX.parent / name
                self.assertTrue(artifact.is_file(), f"Vite did not copy {name}")
                for method in ("GET", "HEAD"):
                    with self.subTest(method=method):
                        with self.client.open(f"/{name}", method=method) as response:
                            self.assertEqual(response.status_code, 200)
                            self.assertIn(response.mimetype, content_types)
                            self.assertEqual(
                                response.data,
                                artifact.read_bytes() if method == "GET" else b"",
                            )


if __name__ == "__main__":
    unittest.main()
