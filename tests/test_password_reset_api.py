"""Unit and integration tests for Password Reset REST API."""

from __future__ import annotations

import re
import unittest
from unittest.mock import patch

from app import create_app
from app.email import (
    MemoryEmailProvider,
    RenderedEmailMessage,
    TransactionalEmailService,
    get_email_service,
)
from app.services import password_reset_rate_limit_service
from models import db
from models.user import User


class PasswordResetApiTests(unittest.TestCase):
    """Test suite for forgot password and reset password REST API flows."""

    def setUp(self):
        password_reset_rate_limit_service.reset_state()
        self.memory_provider = MemoryEmailProvider()
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SECRET_KEY": "test-secret-key-for-password-reset",
                "PUBLIC_APP_URL": "https://flama.vn",
                "EMAIL_ENABLED": True,
                "EMAIL_PROVIDER": "memory",
                "EMAIL_ENVIRONMENT": "test",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            user = User(username="testuser", email="testuser@example.com")
            user.set_password("OldPassword123")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_forgot_password_success(self):
        """Test requesting password reset for registered email dispatches email."""
        with self.app.app_context():
            with patch("app.services.identity_api_service.get_email_service") as mock_get_email:
                mock_service = TransactionalEmailService(
                    config=get_email_service(self.app.config).config,
                    provider=self.memory_provider,
                )
                mock_get_email.return_value = mock_service

                response = self.client.post(
                    "/api/auth/forgot-password",
                    json={"email": "testuser@example.com"},
                )
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertTrue(data.get("success"))

                sent = self.memory_provider.sent_messages
                self.assertEqual(len(sent), 1)
                self.assertEqual(sent[0].recipient, "testuser@example.com")
                self.assertIn("reset-password?token=", sent[0].html_body)

    def test_forgot_password_unknown_email_returns_success_preventing_enumeration(self):
        """Test unknown email address returns generic success response without dispatching email."""
        with self.app.app_context():
            with patch("app.services.identity_api_service.get_email_service") as mock_get_email:
                mock_service = TransactionalEmailService(
                    config=get_email_service(self.app.config).config,
                    provider=self.memory_provider,
                )
                mock_get_email.return_value = mock_service

                response = self.client.post(
                    "/api/auth/forgot-password",
                    json={"email": "unknown@example.com"},
                )
                self.assertEqual(response.status_code, 200)
                data = response.get_json()
                self.assertTrue(data.get("success"))
                self.assertEqual(len(self.memory_provider.sent_messages), 0)

    def test_reset_password_flow(self):
        """Test complete flow: request reset token, submit new password, verify update."""
        with self.app.app_context():
            with patch("app.services.identity_api_service.get_email_service") as mock_get_email:
                mock_service = TransactionalEmailService(
                    config=get_email_service(self.app.config).config,
                    provider=self.memory_provider,
                )
                mock_get_email.return_value = mock_service

                # 1. Request reset link
                self.client.post(
                    "/api/auth/forgot-password",
                    json={"email": "testuser@example.com"},
                )

                sent_msg = self.memory_provider.sent_messages[0]
                match = re.search(r"token=([A-Za-z0-9_\.\-]+)", sent_msg.html_body)
                self.assertIsNotNone(match)
                token = match.group(1)

                # 2. Reset password using extracted token
                reset_response = self.client.post(
                    "/api/auth/reset-password",
                    json={
                        "token": token,
                        "new_password": "NewPassword456",
                        "confirm_password": "NewPassword456",
                    },
                )
                self.assertEqual(reset_response.status_code, 200)

                # 3. Verify user can log in with new password
                user = db.session.get(User, self.user_id)
                self.assertTrue(user.check_password("NewPassword456"))
                self.assertFalse(user.check_password("OldPassword123"))

    def test_reset_password_invalid_token_returns_400(self):
        """Test tampered or invalid reset token returns HTTP 400."""
        with self.app.app_context():
            response = self.client.post(
                "/api/auth/reset-password",
                json={
                    "token": "invalid-tampered-token",
                    "new_password": "NewPassword456",
                    "confirm_password": "NewPassword456",
                },
            )
            self.assertEqual(response.status_code, 400)
            data = response.get_json()
            self.assertEqual(data.get("error"), "INVALID_TOKEN")

    def test_reset_token_is_one_time_use(self):
        with self.app.app_context():
            with patch("app.services.identity_api_service.get_email_service") as mock_get_email:
                mock_service = TransactionalEmailService(
                    config=get_email_service(self.app.config).config,
                    provider=self.memory_provider,
                )
                mock_get_email.return_value = mock_service
                self.client.post(
                    "/api/auth/forgot-password",
                    json={"email": "testuser@example.com"},
                )
                match = re.search(
                    r"token=([A-Za-z0-9_\.\-]+)",
                    self.memory_provider.sent_messages[0].html_body,
                )
                self.assertIsNotNone(match)
                token = match.group(1)
                payload = {
                    "token": token,
                    "new_password": "NewPassword456",
                    "confirm_password": "NewPassword456",
                }
                self.assertEqual(
                    self.client.post("/api/auth/reset-password", json=payload).status_code,
                    200,
                )
                response = self.client.post("/api/auth/reset-password", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json().get("error"), "TOKEN_USED")

    def test_new_reset_request_revokes_previous_token(self):
        with self.app.app_context():
            with patch("app.services.identity_api_service.get_email_service") as mock_get_email:
                mock_service = TransactionalEmailService(
                    config=get_email_service(self.app.config).config,
                    provider=self.memory_provider,
                )
                mock_get_email.return_value = mock_service
                for _ in range(2):
                    response = self.client.post(
                        "/api/auth/forgot-password",
                        json={"email": "testuser@example.com"},
                    )
                    self.assertEqual(response.status_code, 200)
                first_match = re.search(
                    r"token=([A-Za-z0-9_\.\-]+)",
                    self.memory_provider.sent_messages[0].html_body,
                )
                self.assertIsNotNone(first_match)
                response = self.client.post(
                    "/api/auth/reset-password",
                    json={
                        "token": first_match.group(1),
                        "new_password": "NewPassword456",
                        "confirm_password": "NewPassword456",
                    },
                )
                self.assertEqual(response.status_code, 400)
                self.assertEqual(response.get_json().get("error"), "INVALID_TOKEN")

    def test_forgot_password_rate_limit(self):
        self.app.config["PASSWORD_RESET_RATE_LIMIT_MAX_REQUESTS"] = 2
        for _ in range(2):
            response = self.client.post(
                "/api/auth/forgot-password",
                json={"email": "unknown@example.com"},
            )
            self.assertEqual(response.status_code, 200)
        response = self.client.post(
            "/api/auth/forgot-password",
            json={"email": "unknown@example.com"},
        )
        self.assertEqual(response.status_code, 429)
        self.assertEqual(response.get_json().get("error"), "PASSWORD_RESET_RATE_LIMITED")


if __name__ == "__main__":
    unittest.main()
