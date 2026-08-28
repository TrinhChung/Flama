"""Integration tests for User Profile and Transaction History REST API."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from sqlalchemy.exc import SQLAlchemyError

from app import create_app
from app.services import user_roles
from models import db
from models.user import User
from models.user_balance_transaction import UserBalanceTransaction
from models.user_role import UserRole

UTC = timezone.utc


class ProfileApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": True,
                "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": True,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user_roles.ensure_default_user_roles(db.session)

            creator_role = UserRole.query.filter_by(code="creator").first()

            user = User(
                username="test_creator",
                email="creator@flama.local",
                timezone="Asia/Ho_Chi_Minh",
                role_id=creator_role.id if creator_role else None,
                balance_amount_minor=150000,
            )
            user.set_password("correct_password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

            # Add sample transactions
            tx1 = UserBalanceTransaction(
                user_id=user.id,
                transaction_type="deck_sale",
                gross_amount_minor=100000,
                platform_fee_percent=5.0,
                platform_fee_amount_minor=5000,
                net_amount_minor=95000,
                balance_after_minor=95000,
                description="Doanh thu từ bộ thẻ 'N5 Kanji'",
                created_at=datetime(2026, 8, 20, 10, 0, 0),
            )
            tx2 = UserBalanceTransaction(
                user_id=user.id,
                transaction_type="deck_sale",
                gross_amount_minor=60000,
                platform_fee_percent=5.0,
                platform_fee_amount_minor=3000,
                net_amount_minor=57000,
                balance_after_minor=152000,
                description="Doanh thu từ bộ thẻ 'N4 Grammar'",
                created_at=datetime(2026, 8, 21, 14, 30, 0),
            )
            db.session.add_all([tx1, tx2])
            db.session.commit()

    def _login(self):
        resp = self.client.post(
            "/api/auth/login",
            json={"email": "creator@flama.local", "password": "correct_password"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_get_profile_requires_auth(self):
        resp = self.client.get("/api/profile")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "AUTHENTICATION_REQUIRED")

    def test_update_profile_requires_auth(self):
        resp = self.client.patch(
            "/api/profile",
            json={"timezone": "Asia/Tokyo"},
        )
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "AUTHENTICATION_REQUIRED")

    def test_get_profile_authenticated(self):
        self._login()
        resp = self.client.get("/api/profile")
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("user", data)
        self.assertIn("wallet", data)

        self.assertEqual(data["user"]["username"], "test_creator")
        self.assertEqual(data["user"]["email"], "creator@flama.local")
        self.assertEqual(data["user"]["timezone"], "Asia/Ho_Chi_Minh")

        wallet = data["wallet"]
        self.assertEqual(wallet["balance_amount_minor"], 150000)
        self.assertEqual(wallet["balance_amount_display"], "150.000 ₫")
        self.assertEqual(wallet["platform_fee_percent"], 5.0)
        self.assertFalse(wallet["payout_enabled"])
        self.assertEqual(wallet["earnings"]["total_sales_count"], 2)
        self.assertEqual(wallet["earnings"]["total_gross_amount_minor"], 160000)
        self.assertEqual(wallet["earnings"]["total_platform_fee_amount_minor"], 8000)
        self.assertEqual(wallet["earnings"]["total_net_amount_minor"], 152000)

    def test_update_profile_timezone(self):
        self._login()
        resp = self.client.patch(
            "/api/profile",
            json={"timezone": "Asia/Tokyo"},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["user"]["timezone"], "Asia/Tokyo")

        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertEqual(user.timezone, "Asia/Tokyo")
            self.assertTrue(user.check_password("correct_password"))

    def test_update_profile_non_json_payload(self):
        self._login()
        resp = self.client.patch(
            "/api/profile",
            data="not-a-json-payload",
            content_type="text/plain",
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "VALIDATION_ERROR")

    def test_update_profile_password_validation_failures(self):
        self._login()

        # Missing current password
        missing_current = self.client.patch(
            "/api/profile",
            json={
                "current_password": "",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(missing_current.status_code, 400)
        self.assertEqual(missing_current.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(missing_current.get_json()["field"], "current_password")

        # Missing new password
        missing_new = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(missing_new.status_code, 400)
        self.assertEqual(missing_new.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(missing_new.get_json()["field"], "new_password")

        # Missing confirm password
        missing_confirm = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "new_secret_password",
                "confirm_password": "",
            },
        )
        self.assertEqual(missing_confirm.status_code, 400)
        self.assertEqual(missing_confirm.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(missing_confirm.get_json()["field"], "confirm_password")

        # Wrong current password
        wrong_current = self.client.patch(
            "/api/profile",
            json={
                "current_password": "wrong_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(wrong_current.status_code, 400)
        self.assertEqual(wrong_current.get_json()["error"], "INVALID_CURRENT_PASSWORD")
        self.assertEqual(wrong_current.get_json()["field"], "current_password")

        # Password confirmation mismatch
        mismatch = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "new_secret_password",
                "confirm_password": "mismatched_password",
            },
        )
        self.assertEqual(mismatch.status_code, 400)
        self.assertEqual(mismatch.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(mismatch.get_json()["field"], "confirm_password")

        # Password too short (< 8 chars)
        too_short = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "short",
                "confirm_password": "short",
            },
        )
        self.assertEqual(too_short.status_code, 400)
        self.assertEqual(too_short.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(too_short.get_json()["field"], "new_password")

        # Password too long (> 255 chars)
        too_long = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "a" * 256,
                "confirm_password": "a" * 256,
            },
        )
        self.assertEqual(too_long.status_code, 400)
        self.assertEqual(too_long.get_json()["error"], "VALIDATION_ERROR")
        self.assertEqual(too_long.get_json()["field"], "new_password")

        # Password reuse
        reuse = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "correct_password",
                "confirm_password": "correct_password",
            },
        )
        self.assertEqual(reuse.status_code, 400)
        self.assertEqual(reuse.get_json()["error"], "PASSWORD_REUSED")
        self.assertEqual(reuse.get_json()["field"], "new_password")

    def test_combined_profile_update_is_not_partially_applied_on_password_error(self):
        self._login()

        response = self.client.patch(
            "/api/profile",
            json={
                "timezone": "Asia/Tokyo",
                "current_password": "wrong_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "INVALID_CURRENT_PASSWORD")

        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertEqual(user.timezone, "Asia/Ho_Chi_Minh")
            self.assertTrue(user.check_password("correct_password"))

    def test_update_profile_password_oauth_account_without_hash(self):
        with self.app.app_context():
            oauth_user = User(
                username="oauth_user",
                email="oauth@flama.local",
                password_hash="",
            )
            db.session.add(oauth_user)
            db.session.commit()
            oauth_user_id = oauth_user.id

        with self.client.session_transaction() as session_state:
            session_state["_user_id"] = str(oauth_user_id)
            session_state["_fresh"] = True

        resp = self.client.patch(
            "/api/profile",
            json={
                "current_password": "any_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"], "PASSWORD_NOT_SET")

    def test_update_profile_password_db_error_with_rollback(self):
        self._login()

        with patch("models.db.session.commit", side_effect=SQLAlchemyError("DB write failed")):
            resp = self.client.patch(
                "/api/profile",
                json={
                    "current_password": "correct_password",
                    "new_password": "new_secret_password",
                    "confirm_password": "new_secret_password",
                },
            )
        self.assertEqual(resp.status_code, 500)
        self.assertEqual(resp.get_json()["error"], "DB_ERROR")

        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertTrue(user.check_password("correct_password"))
            self.assertFalse(user.check_password("new_secret_password"))

    def test_update_profile_password_success_hash_and_login_flow(self):
        self._login()

        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertIsNotNone(user)
            original_hash = user.password_hash

        resp = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("user", data)
        self.assertNotIn("password", data["user"])
        self.assertNotIn("password_hash", data["user"])

        # Session is preserved after successful password change
        session_resp = self.client.get("/api/session")
        self.assertEqual(session_resp.status_code, 200)
        self.assertTrue(session_resp.get_json()["authenticated"])
        self.assertEqual(session_resp.get_json()["user"]["username"], "test_creator")

        # Password hash is updated and not stored plaintext
        with self.app.app_context():
            updated_user = db.session.get(User, self.user_id)
            self.assertIsNotNone(updated_user)
            self.assertNotEqual(updated_user.password_hash, original_hash)
            self.assertNotEqual(updated_user.password_hash, "new_secret_password")
            self.assertFalse(updated_user.check_password("correct_password"))
            self.assertTrue(updated_user.check_password("new_secret_password"))

        # Logout and test login with old vs new password
        self.client.delete("/api/session")

        old_login = self.client.post(
            "/api/auth/login",
            json={"email": "creator@flama.local", "password": "correct_password"},
        )
        self.assertEqual(old_login.status_code, 401)
        self.assertEqual(old_login.get_json()["error"], "INVALID_CREDENTIALS")

        new_login = self.client.post(
            "/api/auth/login",
            json={"email": "creator@flama.local", "password": "new_secret_password"},
        )
        self.assertEqual(new_login.status_code, 200)
        self.assertTrue(new_login.get_json()["authenticated"])

    def test_update_profile_csrf_protection(self):
        csrf_app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": True,
                "STARTUP_RUN_MAINTENANCE": True,
                "STARTUP_RUN_DEFAULT_USER_ROLE_SEED": True,
            }
        )
        csrf_client = csrf_app.test_client()

        with csrf_app.app_context():
            db.create_all()
            user = User(
                username="csrf_user",
                email="csrf@flama.local",
            )
            user.set_password("correct_password")
            db.session.add(user)
            db.session.commit()
            csrf_user_id = user.id

        # Authenticate session with CSRF token
        with csrf_client.session_transaction() as session_state:
            session_state["_user_id"] = str(csrf_user_id)
            session_state["_fresh"] = True
            session_state["_csrf_token"] = "valid-csrf-token"

        # Request without CSRF token is rejected with 400 CSRF_FAILED
        blocked = csrf_client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(blocked.status_code, 400)
        self.assertEqual(blocked.get_json()["error"], "CSRF_FAILED")

        # Request with valid X-CSRF-Token header succeeds
        allowed = csrf_client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
            headers={"X-CSRF-Token": "valid-csrf-token"},
        )
        self.assertEqual(allowed.status_code, 200)

    def test_list_transactions_pagination(self):
        self._login()
        resp = self.client.get("/api/profile/transactions?page=1&per_page=10")
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["items"]), 2)

        # Check most recent transaction first (order_by created_at.desc())
        first = data["items"][0]
        self.assertEqual(first["gross_amount_minor"], 60000)
        self.assertEqual(first["net_amount_minor"], 57000)
        self.assertEqual(first["net_amount_display"], "+57.000 ₫")
        self.assertEqual(first["platform_fee_percent"], 5.0)


if __name__ == "__main__":
    unittest.main()
