"""Integration tests for User Profile and Transaction History REST API."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import unittest

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

    def test_update_profile_password(self):
        self._login()
        # Invalid current password
        resp = self.client.patch(
            "/api/profile",
            json={
                "current_password": "wrong_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(resp.status_code, 401)

        # Successful password update
        resp = self.client.patch(
            "/api/profile",
            json={
                "current_password": "correct_password",
                "new_password": "new_secret_password",
                "confirm_password": "new_secret_password",
            },
        )
        self.assertEqual(resp.status_code, 200)

        # Check login with new password
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            self.assertTrue(user.check_password("new_secret_password"))

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
