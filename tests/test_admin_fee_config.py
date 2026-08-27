"""Integration tests for Admin Platform Fee Configuration."""

from __future__ import annotations

import unittest

from app import create_app
from app.services import user_roles
from models import db
from models.creator_feature_policy import CreatorFeaturePolicy
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
            creator_role = UserRole.query.filter_by(code="creator").first()

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

            creator_user = User(
                username="creator_user",
                email="creator@flama.local",
                is_admin=False,
                role_id=creator_role.id if creator_role else None,
                balance_amount_minor=120000,
            )
            creator_user.set_password("creator_pass")

            db.session.add_all([admin, target_user, creator_user])
            db.session.commit()

            self.admin_id = admin.id
            self.target_user_id = target_user.id
            self.creator_user_id = creator_user.id
            self.regular_role_id = regular_role.id if regular_role else 1
            self.creator_role_id = creator_role.id if creator_role else 2

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

    # --- NEW ADMIN FEES API TESTS ---

    def test_get_fee_overview(self):
        self._login_admin()
        resp = self.client.get("/api/admin/fees")
        self.assertEqual(resp.status_code, 200)

        data = resp.get_json()
        self.assertIn("summary", data)
        self.assertIn("roles", data)
        self.assertIn("creator_policy", data)
        self.assertIn("custom_fee_users", data)

        self.assertEqual(data["summary"]["global_default_fee_percent"], 10.0)
        self.assertGreaterEqual(len(data["roles"]), 2)
        self.assertFalse(data["creator_policy"]["is_monetized"])

    def test_update_role_default_fee(self):
        self._login_admin()
        resp = self.client.patch(
            f"/api/admin/fees/roles/{self.regular_role_id}",
            json={"default_platform_fee_percent": 8.5},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["role"]["default_platform_fee_percent"], 8.5)

        with self.app.app_context():
            role = db.session.get(UserRole, self.regular_role_id)
            self.assertEqual(role.default_platform_fee_percent, 8.5)

    def test_update_role_default_fee_invalid(self):
        self._login_admin()
        resp = self.client.patch(
            f"/api/admin/fees/roles/{self.regular_role_id}",
            json={"default_platform_fee_percent": 150.0},
        )
        self.assertEqual(resp.status_code, 400)

    def test_update_creator_policy(self):
        self._login_admin()
        resp = self.client.put(
            "/api/admin/fees/creator-policy",
            json={
                "feature_code": "deck_access_keys",
                "is_monetized": True,
                "free_quota_per_creator": 100,
                "price_per_key_minor": 2000,
                "requires_pro_role": True,
            },
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        policy = data["creator_policy"]
        self.assertTrue(policy["is_monetized"])
        self.assertEqual(policy["free_quota_per_creator"], 100)
        self.assertEqual(policy["price_per_key_minor"], 2000)
        self.assertTrue(policy["requires_pro_role"])

        with self.app.app_context():
            p = CreatorFeaturePolicy.query.filter_by(feature_code="deck_access_keys").first()
            self.assertIsNotNone(p)
            self.assertTrue(p.is_monetized)
            self.assertEqual(p.free_quota_per_creator, 100)
            self.assertEqual(p.price_per_key_minor, 2000)

    def test_update_user_custom_fee_via_fees_api(self):
        self._login_admin()

        # Set custom fee to 3.0%
        resp = self.client.patch(
            f"/api/admin/fees/users/{self.target_user_id}",
            json={"custom_platform_fee_percent": 3.0},
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["user"]["custom_platform_fee_percent"], 3.0)

        # Overview should now list 1 custom user
        resp_overview = self.client.get("/api/admin/fees")
        overview_data = resp_overview.get_json()
        self.assertEqual(overview_data["summary"]["custom_fee_users_count"], 1)
        self.assertEqual(len(overview_data["custom_fee_users"]), 1)
        self.assertEqual(overview_data["custom_fee_users"][0]["id"], self.target_user_id)

        # Reset fee
        resp_reset = self.client.patch(
            f"/api/admin/fees/users/{self.target_user_id}",
            json={"custom_platform_fee_percent": None},
        )
        self.assertEqual(resp_reset.status_code, 200)
        data_reset = resp_reset.get_json()
        self.assertIsNone(data_reset["user"]["custom_platform_fee_percent"])

    def test_search_users_for_custom_fee(self):
        self._login_admin()
        resp = self.client.get("/api/admin/fees/search-users?q=target")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertIn("items", data)
        self.assertEqual(len(data["items"]), 1)
        self.assertEqual(data["items"][0]["username"], "target_user")

    def test_non_admin_cannot_access_fees_api(self):
        self._login_regular()
        resp = self.client.get("/api/admin/fees")
        self.assertEqual(resp.status_code, 403)

        resp2 = self.client.patch(
            f"/api/admin/fees/roles/{self.regular_role_id}",
            json={"default_platform_fee_percent": 0.0},
        )
        self.assertEqual(resp2.status_code, 403)


if __name__ == "__main__":
    unittest.main()
