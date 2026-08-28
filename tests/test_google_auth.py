"""Unit and integration tests for Google OAuth 2.0 / OpenID Connect authentication."""

from __future__ import annotations

import base64
import json
import time
import unittest
from unittest.mock import patch

from app import create_app
from app.services import google_auth_service
from models import db
from models.user import User
from models.user_identity import UserIdentity


def _make_dummy_id_token(
    sub: str = "google-sub-12345",
    email: str = "googleuser@example.com",
    email_verified: bool = True,
    name: str = "Google User",
    picture: str = "https://example.com/avatar.jpg",
    aud: str = "test-google-client-id",
    iss: str = "https://accounts.google.com",
    nonce: str | None = None,
    exp: int | None = None,
) -> str:
    """Helper to generate an unverified JWT ID token for testing."""
    header = {"alg": "RS256", "typ": "JWT", "kid": "key-1"}
    payload = {
        "iss": iss,
        "aud": aud,
        "sub": sub,
        "email": email,
        "email_verified": email_verified,
        "name": name,
        "picture": picture,
        "exp": exp or int(time.time() + 3600),
        "iat": int(time.time()),
    }
    if nonce:
        payload["nonce"] = nonce

    def _b64(d: dict) -> str:
        s = json.dumps(d).encode("utf-8")
        return base64.urlsafe_b64encode(s).decode("utf-8").rstrip("=")

    return f"{_b64(header)}.{_b64(payload)}.fake_signature"


class GoogleAuthTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "GOOGLE_OAUTH_CLIENT_ID": "test-google-client-id",
                "GOOGLE_OAUTH_CLIENT_SECRET": "test-google-client-secret",
                "GOOGLE_OAUTH_REDIRECT_URI": "http://localhost:4789/auth/google/callback",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_build_google_auth_url(self):
        with self.app.app_context():
            auth_url, state, nonce = google_auth_service.build_google_auth_url(next_url="/oauth/authorize")
            self.assertIn("https://accounts.google.com/o/oauth2/v2/auth", auth_url)
            self.assertIn("client_id=test-google-client-id", auth_url)
            self.assertIn(f"state={state}", auth_url)
            self.assertIn(f"nonce={nonce}", auth_url)
            self.assertTrue(len(state) > 20)

    def test_initiate_google_login_redirect(self):
        response = self.client.get("/auth/google?next=/oauth/authorize")
        self.assertEqual(response.status_code, 302)
        self.assertIn("accounts.google.com", response.headers["Location"])

        with self.client.session_transaction() as session_data:
            self.assertTrue(session_data.get("google_auth_state"))
            self.assertTrue(session_data.get("google_auth_nonce"))
            self.assertEqual(session_data.get("google_auth_next"), "/oauth/authorize")

    def test_google_callback_state_mismatch(self):
        with self.client.session_transaction() as sess:
            sess["google_auth_state"] = "valid_state_123"

        response = self.client.get("/auth/google/callback?state=wrong_state&code=some_code")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    @patch("app.services.google_auth_service.exchange_code_for_tokens")
    def test_google_callback_provision_new_user(self, mock_exchange):
        id_token = _make_dummy_id_token(
            sub="g-sub-new-100",
            email="newgoogleuser@example.com",
            name="New User",
        )
        mock_exchange.return_value = {"id_token": id_token}

        with self.client.session_transaction() as sess:
            sess["google_auth_state"] = "state_123"
            sess["google_auth_nonce"] = None
            sess["google_auth_next"] = "/dashboard"

        response = self.client.get("/auth/google/callback?state=state_123&code=valid_code")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")

        with self.app.app_context():
            user = User.query.filter_by(email="newgoogleuser@example.com").first()
            self.assertIsNotNone(user)
            self.assertEqual(user.display_name, "New User")
            self.assertIsNone(user.password_hash)
            self.assertFalse(user.has_password)
            self.assertFalse(user.check_password("any_password"))

            identity = UserIdentity.query.filter_by(provider="google", provider_sub="g-sub-new-100").first()
            self.assertIsNotNone(identity)
            self.assertEqual(identity.user_id, user.id)

    @patch("app.services.google_auth_service.exchange_code_for_tokens")
    def test_google_callback_auto_link_existing_email(self, mock_exchange):
        with self.app.app_context():
            existing = User(username="existing_user", email="existing@example.com")
            existing.set_password("Secret123!")
            db.session.add(existing)
            db.session.commit()
            existing_id = existing.id

        id_token = _make_dummy_id_token(
            sub="g-sub-existing-200",
            email="existing@example.com",
            email_verified=True,
        )
        mock_exchange.return_value = {"id_token": id_token}

        with self.client.session_transaction() as sess:
            sess["google_auth_state"] = "state_link"

        response = self.client.get("/auth/google/callback?state=state_link&code=valid_code")
        self.assertEqual(response.status_code, 302)

        with self.app.app_context():
            identity = UserIdentity.query.filter_by(provider="google", provider_sub="g-sub-existing-200").first()
            self.assertIsNotNone(identity)
            self.assertEqual(identity.user_id, existing_id)

            user = User.query.get(existing_id)
            self.assertTrue(user.has_password)

    @patch("app.services.google_auth_service.exchange_code_for_tokens")
    def test_google_callback_disabled_user_rejected(self, mock_exchange):
        with self.app.app_context():
            disabled = User(username="disabled_user", email="disabled@example.com", is_disabled=True)
            db.session.add(disabled)
            db.session.commit()

        id_token = _make_dummy_id_token(
            sub="g-sub-disabled-300",
            email="disabled@example.com",
        )
        mock_exchange.return_value = {"id_token": id_token}

        with self.client.session_transaction() as sess:
            sess["google_auth_state"] = "state_disabled"

        response = self.client.get("/auth/google/callback?state=state_disabled&code=valid_code")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/login")

    @patch("app.services.google_auth_service.exchange_code_for_tokens")
    def test_google_callback_preserves_safe_next_url(self, mock_exchange):
        id_token = _make_dummy_id_token(sub="g-sub-next-400", email="nextuser@example.com")
        mock_exchange.return_value = {"id_token": id_token}

        with self.client.session_transaction() as sess:
            sess["google_auth_state"] = "state_next"
            sess["google_auth_next"] = "/oauth/authorize?client_id=mcp-chatgpt"

        response = self.client.get("/auth/google/callback?state=state_next&code=valid_code")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/oauth/authorize?client_id=mcp-chatgpt")

    @patch("app.services.google_auth_service.exchange_code_for_tokens")
    def test_google_callback_sanitizes_untrusted_next_url(self, mock_exchange):
        id_token = _make_dummy_id_token(sub="g-sub-phish-500", email="phishuser@example.com")
        mock_exchange.return_value = {"id_token": id_token}

        with self.client.session_transaction() as sess:
            sess["google_auth_state"] = "state_phish"
            sess["google_auth_next"] = "https://attacker.com/malicious"

        response = self.client.get("/auth/google/callback?state=state_phish&code=valid_code")
        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/dashboard")

    def test_api_google_auth_url_endpoint(self):
        response = self.client.get("/api/auth/google/url?next=/learning/study")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("url", data)
        self.assertIn("state", data)
        self.assertIn("accounts.google.com", data["url"])


if __name__ == "__main__":
    unittest.main()
