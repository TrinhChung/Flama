"""Security regression tests for auth, CSRF, and login throttling."""

from __future__ import annotations

import unittest

from app import create_app
from app.services import login_rate_limit_service
from models import db
from models.deck import Deck
from models.user import User


class AuthSecurityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": True,
                "LOGIN_RATE_LIMIT_ENABLED": True,
                "LOGIN_RATE_LIMIT_MAX_ATTEMPTS": 3,
                "LOGIN_RATE_LIMIT_WINDOW_SECONDS": 60,
                "LOGIN_RATE_LIMIT_LOCKOUT_SECONDS": 60,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    def setUp(self):
        self.client = self.app.test_client()
        login_rate_limit_service.reset_state()

        with self.app.app_context():
            db.create_all()
            user = User(username="secure-user", email="secure-user@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        login_rate_limit_service.reset_state()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _csrf_token(self, path: str = "/login") -> str:
        response = self.client.get(path)
        self.assertEqual(response.status_code, 200)
        with self.client.session_transaction() as session_state:
            token = str(session_state.get("_csrf_token") or "")
        self.assertTrue(token)
        return token

    def _login(self, *, password: str = "password", next_url: str | None = None):
        token = self._csrf_token("/login")
        return self.client.post(
            "/login",
            query_string={"next": next_url} if next_url else None,
            data={
                "email": "secure-user@example.com",
                "password": password,
                "_csrf_token": token,
            },
            follow_redirects=False,
        )

    def test_login_rejects_external_next_url(self):
        response = self._login(next_url="https://example.com/phish")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers.get("Location"), "/dashboard")

    def test_production_password_hash_default_still_verifies(self):
        with self.app.app_context():
            original_method = self.app.config["PASSWORD_HASH_METHOD"]
            try:
                self.app.config["PASSWORD_HASH_METHOD"] = ""
                user = User(username="production-hash", email="hash@example.com")
                user.set_password("production-password")
            finally:
                self.app.config["PASSWORD_HASH_METHOD"] = original_method

        self.assertTrue(user.check_password("production-password"))
        self.assertFalse(user.password_hash.startswith("pbkdf2:sha256:1000$"))

    def test_login_requires_csrf_token(self):
        response = self.client.post(
            "/login",
            data={"email": "secure-user@example.com", "password": "password"},
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn("CSRF validation failed.", response.get_data(as_text=True))

    def test_authenticated_form_post_requires_csrf_token(self):
        login_response = self._login()
        self.assertEqual(login_response.status_code, 302)

        blocked = self.client.post(
            "/vocabulary/decks/create",
            data={"name": "Secure Deck", "deck_path": "Secure Deck"},
            follow_redirects=False,
        )
        self.assertEqual(blocked.status_code, 400)

        with self.client.session_transaction() as session_state:
            token = str(session_state.get("_csrf_token") or "")
        allowed = self.client.post(
            "/vocabulary/decks/create",
            data={
                "name": "Secure Deck",
                "deck_path": "Secure Deck",
                "_csrf_token": token,
            },
            follow_redirects=False,
        )
        self.assertEqual(allowed.status_code, 302)

        with self.app.app_context():
            rows = Deck.query.filter_by(owner_user_id=self.user_id, name="Secure Deck").all()
            self.assertEqual(len(rows), 1)

    def test_same_origin_header_does_not_bypass_csrf_token_requirement(self):
        login_response = self._login()
        self.assertEqual(login_response.status_code, 302)

        blocked = self.client.post(
            "/vocabulary/decks/create",
            data={"name": "Origin Only Deck", "deck_path": "Origin Only Deck"},
            headers={"Origin": "http://localhost"},
            follow_redirects=False,
        )
        self.assertEqual(blocked.status_code, 400)

    def test_logout_get_is_safe_and_does_not_end_session(self):
        login_response = self._login()
        self.assertEqual(login_response.status_code, 302)

        response = self.client.get("/logout", follow_redirects=False)
        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.content_type)

        session_response = self.client.get("/api/session")
        self.assertTrue(session_response.get_json()["authenticated"])

    def test_login_rate_limit_locks_after_repeated_failures(self):
        token = self._csrf_token("/login")
        for _ in range(3):
            response = self.client.post(
                "/login",
                data={
                    "email": "secure-user@example.com",
                    "password": "wrong-password",
                    "_csrf_token": token,
                },
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 200)

        locked = self.client.post(
            "/login",
            data={
                "email": "secure-user@example.com",
                "password": "wrong-password",
                "_csrf_token": token,
            },
            follow_redirects=False,
        )
        self.assertEqual(locked.status_code, 429)

    def test_login_rate_limit_cannot_be_bypassed_via_x_forwarded_for(self):
        token = self._csrf_token("/login")
        # Attempt failures with rotating X-Forwarded-For headers
        for i in range(3):
            response = self.client.post(
                "/login",
                data={
                    "email": "secure-user@example.com",
                    "password": "wrong-password",
                    "_csrf_token": token,
                },
                headers={"X-Forwarded-For": f"198.51.100.{i + 1}"},
                follow_redirects=False,
            )
            self.assertEqual(response.status_code, 200)

        # 4th attempt with another spoofed IP must still be rate limited (429)
        locked = self.client.post(
            "/login",
            data={
                "email": "secure-user@example.com",
                "password": "wrong-password",
                "_csrf_token": token,
            },
            headers={"X-Forwarded-For": "203.0.113.99"},
            follow_redirects=False,
        )
        self.assertEqual(locked.status_code, 429)


if __name__ == "__main__":
    unittest.main()
