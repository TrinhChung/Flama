"""Integration tests for standalone User Wallet REST API."""

from __future__ import annotations

from datetime import datetime, timezone
import unittest

from app import create_app
from app.services import user_roles
from models import db
from models.user import User
from models.user_balance_transaction import UserBalanceTransaction
from models.user_role import UserRole

UTC = timezone.utc


class WalletApiTests(unittest.TestCase):
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
                username="wallet_creator",
                email="wallet_creator@flama.local",
                timezone="Asia/Ho_Chi_Minh",
                role_id=creator_role.id if creator_role else None,
                balance_amount_minor=250000,
            )
            user.set_password("correct_password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

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
            json={"email": "wallet_creator@flama.local", "password": "correct_password"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_get_wallet_requires_auth(self):
        resp = self.client.get("/api/wallet")
        self.assertEqual(resp.status_code, 401)
        self.assertEqual(resp.get_json()["error"], "AUTHENTICATION_REQUIRED")

    def test_get_wallet_authenticated(self):
        self._login()
        resp = self.client.get("/api/wallet")
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data["balance_amount_minor"], 250000)
        self.assertEqual(data["balance_amount_display"], "250.000 ₫")
        self.assertEqual(data["currency_code"], "VND")
        self.assertEqual(data["platform_fee_percent"], 5.0)
        self.assertFalse(data["payout_enabled"])
        self.assertEqual(data["earnings"]["total_sales_count"], 2)
        self.assertEqual(data["earnings"]["total_gross_amount_minor"], 160000)
        self.assertEqual(data["earnings"]["total_platform_fee_amount_minor"], 8000)
        self.assertEqual(data["earnings"]["total_net_amount_minor"], 152000)

    def test_list_wallet_transactions_pagination(self):
        self._login()
        resp = self.client.get("/api/wallet/transactions?page=1&per_page=10")
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data["total"], 2)
        self.assertEqual(len(data["items"]), 2)
        self.assertEqual(data["items"][0]["gross_amount_minor"], 60000)
        self.assertEqual(data["items"][0]["net_amount_minor"], 57000)
        self.assertEqual(data["items"][0]["platform_fee_percent"], 5.0)


if __name__ == "__main__":
    unittest.main()
