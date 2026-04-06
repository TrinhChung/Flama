"""Integration tests for user role seeding and admin user management."""

import unittest

from app import create_app
from models import db
from models.user import User
from models.user_role import UserRole


class AdminUserRoleTests(unittest.TestCase):
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
            admin_role = UserRole.query.filter_by(code="admin").first()
            regular_role = UserRole.query.filter_by(code="regular").first()
            assert admin_role is not None
            assert regular_role is not None

            admin = User(
                username="admin",
                email="admin@example.com",
                is_admin=True,
                role_id=admin_role.id,
                is_disabled=False,
            )
            admin.set_password("password")
            normal = User(
                username="normal",
                email="normal@example.com",
                is_admin=False,
                role_id=regular_role.id,
                is_disabled=False,
            )
            normal.set_password("password")
            db.session.add_all([admin, normal])
            db.session.commit()
            self.admin_id = admin.id
            self.normal_id = normal.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, email: str, password: str = "password"):
        return self.client.post(
            "/login",
            data={"email": email, "password": password},
            follow_redirects=True,
        )

    def _post_json(self, path: str, payload: dict):
        return self.client.post(path, json=payload, follow_redirects=False)

    def test_default_roles_are_seeded(self):
        with self.app.app_context():
            roles = UserRole.query.order_by(UserRole.position.asc()).all()
            self.assertEqual([role.code for role in roles], ["regular", "creator", "enterprise", "admin"])

    def test_admin_can_assign_user_role_batch(self):
        self._login("admin@example.com")

        with self.app.app_context():
            creator_role = UserRole.query.filter_by(code="creator").first()
            self.assertIsNotNone(creator_role)
            creator_role_id = creator_role.id

        response = self._post_json(
            "/admin/api/users/roles/batch",
            {
                "user_ids": [self.normal_id],
                "target_role_id": creator_role_id,
                "mode": "replace",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["success_count"], 1)
        self.assertEqual(payload["fail_count"], 0)

        with self.app.app_context():
            user = User.query.get(self.normal_id)
            self.assertIsNotNone(user)
            self.assertEqual(user.role.code, "creator")
            self.assertFalse(user.is_admin)

    def test_cannot_demote_last_admin_batch(self):
        self._login("admin@example.com")

        with self.app.app_context():
            regular_role = UserRole.query.filter_by(code="regular").first()
            self.assertIsNotNone(regular_role)
            regular_role_id = regular_role.id

        response = self._post_json(
            "/admin/api/users/roles/batch",
            {
                "user_ids": [self.admin_id],
                "target_role_id": regular_role_id,
                "mode": "replace",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["success_count"], 0)
        self.assertEqual(payload["fail_count"], 1)

        with self.app.app_context():
            user = User.query.get(self.admin_id)
            self.assertIsNotNone(user)
            self.assertTrue(user.is_admin)
            self.assertEqual(user.role.code, "admin")

    def test_cannot_self_demote(self):
        self._login("admin@example.com")
        with self.app.app_context():
            regular_role = UserRole.query.filter_by(code="regular").first()
            self.assertIsNotNone(regular_role)
            regular_role_id = regular_role.id

        response = self._post_json(
            "/admin/api/users/roles/batch",
            {
                "user_ids": [self.admin_id, self.normal_id],
                "target_role_id": regular_role_id,
                "mode": "replace",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["success_count"], 1)
        self.assertEqual(payload["fail_count"], 1)

        with self.app.app_context():
            admin_user = User.query.get(self.admin_id)
            normal_user = User.query.get(self.normal_id)
            self.assertTrue(admin_user.is_admin)
            self.assertFalse(normal_user.is_admin)

    def test_cannot_disable_last_admin(self):
        self._login("admin@example.com")
        response = self._post_json(
            "/admin/api/users/status/batch",
            {
                "user_ids": [self.admin_id],
                "action": "disable",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["success_count"], 0)
        self.assertEqual(payload["fail_count"], 1)

        with self.app.app_context():
            user = User.query.get(self.admin_id)
            self.assertFalse(user.is_disabled)

    def test_admin_can_disable_non_admin(self):
        self._login("admin@example.com")
        response = self._post_json(
            "/admin/api/users/status/batch",
            {
                "user_ids": [self.normal_id],
                "action": "disable",
            },
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["success_count"], 1)
        self.assertEqual(payload["fail_count"], 0)

        with self.app.app_context():
            user = User.query.get(self.normal_id)
            self.assertTrue(user.is_disabled)

    def test_disabled_user_cannot_login(self):
        with self.app.app_context():
            user = User.query.get(self.normal_id)
            user.is_disabled = True
            db.session.commit()

        response = self._login("normal@example.com")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Tài khoản của bạn đã bị vô hiệu hóa.", response.get_data(as_text=True))

    def test_list_users_api_supports_filters(self):
        self._login("admin@example.com")
        response = self.client.get(
            "/admin/api/users?q=normal&status=active&page=1&per_page=10",
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["page"], 1)
        self.assertEqual(payload["per_page"], 10)
        self.assertGreaterEqual(payload["total"], 1)
        self.assertEqual(len(payload["items"]), 1)
        self.assertEqual(payload["items"][0]["username"], "normal")

    def test_non_admin_cannot_open_management_page(self):
        self._login("normal@example.com")
        response = self.client.get("/admin/users", follow_redirects=False)
        self.assertEqual(response.status_code, 302)
        self.assertIn("/dashboard", response.headers.get("Location", ""))


if __name__ == "__main__":
    unittest.main()
