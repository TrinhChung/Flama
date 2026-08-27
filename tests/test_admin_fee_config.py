"""Integration tests for Admin Platform Fee Configuration."""

from __future__ import annotations

import unittest

from app import create_app
from app.services import user_roles
from models import db
from models.user import User
from models.user_role import UserRole


class AdminFeeConfigTests(unittest.TestCase):
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

            admin_role = UserRole.query.filter_by(code="admin").first()
            regular_role = UserRole.query.filter_by(code="regular").first()

            admin = User(
                username="admin_user",
                email="admin@flama.local",
                is_admin=True,
                role_id=admin_role.id if admin_role else None,
            )
            admin.set_password("admin_pass")

            target_user = User(
                username="target_user",
                email="target@flama.local",
                is_admin=False,
                role_id=regular_role.id if regular_role else None,
                balance_amount_minor=50000,
            )
            target_user.set_password("user_pass")

            db.session.add_all([admin, target_user])
            db.session.commit()

            self.admin_id = admin.id
            self.target_user_id = target_user.id

    def _login_admin(self):
        resp = self.client.post(
            "/api/auth/login",
            json={"email": "admin@flama.local", "password": "admin_pass"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp

    def _login_regular(self):
        resp = self.client.post(
            "/api/auth/login",
            json={"email": "target@flama.local", "password": "user_pass"},
        )
        self.assertEqual(resp.status_code, 200)
        return resp

    def test_list_users_includes_fee_and_balance(self):
        self._login_admin()
        resp = self.client.get("/api/admin/users")
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("items", data)
        target_item = next(
            (u for u in data["items"] if u["id"] == self.target_user_id), None
        )
        self.assertIsNotNone(target_item)
        self.assertEqual(target_item["balance_amount_minor"], 50000)
        self.assertIsNone(target_item["custom_platform_fee_percent"])
        self.assertEqual(target_item["effective_platform_fee_percent"], 10.0)

    def test_admin_update_custom_platform_fee(self):
        self._login_admin()

        # Set custom fee to 7.5%
        resp = self.client.patch(
            f"/api/admin/users/{self.target_user_id}",
            json={"custom_platform_fee_percent": 7.5},
        )
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertEqual(data["item"]["custom_platform_fee_percent"], 7.5)
        self.assertEqual(data["item"]["effective_platform_fee_percent"], 7.5)

        with self.app.app_context():
            u = db.session.get(User, self.target_user_id)
            self.assertEqual(u.custom_platform_fee_percent, 7.5)

        # Reset custom fee to role default (None)
        resp2 = self.client.patch(
            f"/api/admin/users/{self.target_user_id}",
            json={"custom_platform_fee_percent": None},
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()
        self.assertIsNone(data2["item"]["custom_platform_fee_percent"])
        self.assertEqual(data2["item"]["effective_platform_fee_percent"], 10.0)

    def test_non_admin_cannot_update_fee(self):
        self._login_regular()
        resp = self.client.patch(
            f"/api/admin/users/{self.target_user_id}",
            json={"custom_platform_fee_percent": 0.0},
        )
        self.assertEqual(resp.status_code, 403)


if __name__ == "__main__":
    unittest.main()
