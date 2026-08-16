"""CORS contract for the separately deployed React frontend."""

from __future__ import annotations

import unittest

from app import create_app
from models import db


class CorsTests(unittest.TestCase):
    def setUp(self):
        self.allowed_origin = "https://flama.stmtp.com"
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "STARTUP_RUN_MAINTENANCE": False,
                "WTF_CSRF_ENABLED": False,
                "CORS_ALLOWED_ORIGINS": (f"{self.allowed_origin}/",),
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_allowed_origin_receives_credentialed_cors_headers(self):
        response = self.client.get(
            "/api/session",
            headers={"Origin": self.allowed_origin},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Origin"),
            self.allowed_origin,
        )
        self.assertEqual(
            response.headers.get("Access-Control-Allow-Credentials"),
            "true",
        )
        self.assertIn("Origin", response.headers.get("Vary", ""))

    def test_allowed_preflight_exposes_api_methods_and_csrf_headers(self):
        response = self.client.options(
            "/api/auth/login",
            headers={
                "Origin": self.allowed_origin,
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-csrf-token",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertIn(
            "POST",
            response.headers.get("Access-Control-Allow-Methods", ""),
        )
        self.assertIn(
            "X-CSRF-Token",
            response.headers.get("Access-Control-Allow-Headers", ""),
        )
        self.assertIn(
            "X-Timezone",
            response.headers.get("Access-Control-Allow-Headers", ""),
        )

    def test_unconfigured_origin_receives_no_cors_permission(self):
        response = self.client.get(
            "/api/session",
            headers={"Origin": "https://example.com"},
        )

        self.assertIsNone(response.headers.get("Access-Control-Allow-Origin"))
        self.assertIsNone(
            response.headers.get("Access-Control-Allow-Credentials")
        )


if __name__ == "__main__":
    unittest.main()
