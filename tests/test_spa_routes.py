"""Routing coverage for canonical React deep links."""

import unittest
from unittest.mock import patch

from flask import Response

from app import create_app
from models import db
from models.user import User


class SpaRouteTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            user = User(
                username="spa-user",
                email="spa@example.com",
                is_admin=False,
            )
            user.set_password("password")
            db.session.add(user)
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    @staticmethod
    def _shell():
        return Response("react-shell", content_type="text/html")

    def _login(self):
        response = self.client.post(
            "/api/v1/auth/login",
            json={"email": "spa@example.com", "password": "password"},
        )
        self.assertEqual(response.status_code, 200)

    def test_public_support_deep_link_serves_spa(self):
        with patch(
            "app.routes.spa_routes.serve_react_spa",
            side_effect=self._shell,
        ):
            response = self.client.get("/support")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, b"react-shell")

    def test_private_canonical_deep_links_require_login_then_serve_spa(self):
        for path in (
            "/browse",
            "/study",
            "/installed-decks",
            "/import",
            "/marketplace/decks",
            "/marketplace/note-types",
        ):
            with self.subTest(path=path):
                response = self.client.get(path)
                self.assertEqual(response.status_code, 302)
                self.assertIn("/login", response.headers["Location"])

        self._login()
        with patch(
            "app.routes.spa_routes.serve_react_spa",
            side_effect=self._shell,
        ):
            for path in (
                "/browse",
                "/study",
                "/installed-decks",
                "/import",
                "/marketplace/decks",
                "/marketplace/decks/deck-1",
                "/marketplace/note-types",
                "/marketplace/note-types/type-1",
            ):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, b"react-shell")

    def test_non_admin_cannot_open_admin_tts_deep_link(self):
        self._login()
        response = self.client.get("/admin/tts")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers["Location"])


if __name__ == "__main__":
    unittest.main()
