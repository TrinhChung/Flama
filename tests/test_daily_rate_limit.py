"""Comprehensive tests for role-based daily rate limiting (API & MCP)."""

from __future__ import annotations

import unittest
from flask import json

from app import create_app
from app.connect import create_connect_app
from app.services import daily_rate_limit_service, mcp_access_token_service
from models import db
from models.user import User
from tests.study_note_fixtures import create_note_user
from models.user_role import UserRole


class DailyRateLimitUnitTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "RATE_LIMIT_DAILY_ENABLED": True,
                "RATE_LIMIT_REGULAR_DAILY_MAX": 300,
                "RATE_LIMIT_CREATOR_DAILY_MAX": 2000,
                "RATE_LIMIT_ENTERPRISE_DAILY_MAX": 10000,
                "RATE_LIMIT_BACKEND": "local",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            daily_rate_limit_service.reset_local_rate_limit_state()
            mcp_access_token_service.reset_rate_limit_state()

            regular_role = UserRole.query.filter_by(code="regular").first()
            creator_role = UserRole.query.filter_by(code="creator").first()
            admin_role = UserRole.query.filter_by(code="admin").first()
            enterprise_role = UserRole.query.filter_by(code="enterprise").first()

            regular_user = create_note_user(db.session,
                username="regular_student",
                email="regular@example.com",
                role_id=regular_role.id if regular_role else None,
                is_admin=False,
            )
            regular_user.set_password("password")

            creator_user = create_note_user(db.session,
                username="deck_creator",
                email="creator@example.com",
                role_id=creator_role.id if creator_role else None,
                is_admin=False,
            )
            creator_user.set_password("password")

            admin_user = create_note_user(db.session,
                username="sysadmin",
                email="admin@example.com",
                role_id=admin_role.id if admin_role else None,
                is_admin=True,
            )
            admin_user.set_password("password")

            enterprise_user = create_note_user(db.session,
                username="enterprise_user",
                email="enterprise@example.com",
                role_id=enterprise_role.id if enterprise_role else None,
                is_admin=False,
            )
            enterprise_user.set_password("password")

            db.session.add_all([regular_user, creator_user, admin_user, enterprise_user])
            db.session.commit()

            self.regular_id = regular_user.id
            self.creator_id = creator_user.id
            self.admin_id = admin_user.id
            self.enterprise_id = enterprise_user.id

    def tearDown(self):
        with self.app.app_context():
            daily_rate_limit_service.reset_local_rate_limit_state()
            mcp_access_token_service.reset_rate_limit_state()
            db.session.remove()
            db.drop_all()

    def test_role_quota_resolution(self):
        with self.app.app_context():
            regular = db.session.get(User, self.regular_id)
            creator = db.session.get(User, self.creator_id)
            admin = db.session.get(User, self.admin_id)
            enterprise = db.session.get(User, self.enterprise_id)

            self.assertEqual(daily_rate_limit_service.resolve_user_daily_quota(regular), 300)
            self.assertEqual(daily_rate_limit_service.resolve_user_daily_quota(creator), 2000)
            self.assertEqual(daily_rate_limit_service.resolve_user_daily_quota(enterprise), 10000)
            self.assertIsNone(daily_rate_limit_service.resolve_user_daily_quota(admin))

    def test_consume_quota_local_bucket(self):
        with self.app.app_context():
            user_id = 9999
            quota = 5

            for i in range(1, 6):
                allowed, count, remaining, reset_epoch = daily_rate_limit_service.consume_daily_quota(
                    user_id, quota
                )
                self.assertTrue(allowed)
                self.assertEqual(count, i)
                self.assertEqual(remaining, 5 - i)
                self.assertGreater(reset_epoch, 0)

            # 6th request must exceed quota
            allowed, count, remaining, reset_epoch = daily_rate_limit_service.consume_daily_quota(
                user_id, quota
            )
            self.assertFalse(allowed)
            self.assertEqual(count, 6)
            self.assertEqual(remaining, 0)

    def test_api_rate_limiting_for_regular_user(self):
        # Configure a small limit for testing
        self.app.config["RATE_LIMIT_REGULAR_DAILY_MAX"] = 3

        with self.app.app_context():
            regular = db.session.get(User, self.regular_id)

        # Login as regular user
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.regular_id)
            sess["_fresh"] = True

        # First 3 requests should pass (e.g. GET /api/dashboard)
        for i in range(1, 4):
            resp = self.client.get("/api/dashboard")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("X-RateLimit-Limit"), "3")
            self.assertEqual(resp.headers.get("X-RateLimit-Remaining"), str(3 - i))
            self.assertIsNotNone(resp.headers.get("X-RateLimit-Reset"))

        # 4th request should return 429
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 429)
        data = resp.get_json()
        self.assertEqual(data["error"], "RATE_LIMIT_EXCEEDED")
        self.assertEqual(data["limit"], 3)
        self.assertEqual(data["remaining"], 0)
        self.assertIn("3", data["message"])

    def test_api_rate_limiting_admin_unlimited(self):
        # Even with low regular limit, admin is unlimited
        self.app.config["RATE_LIMIT_REGULAR_DAILY_MAX"] = 2

        # Login as admin user
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.admin_id)
            sess["_fresh"] = True

        # Make 10 requests as admin -> all must succeed
        for _ in range(10):
            resp = self.client.get("/api/dashboard")
            self.assertEqual(resp.status_code, 200)
            self.assertEqual(resp.headers.get("X-RateLimit-Limit"), "-1")
            self.assertEqual(resp.headers.get("X-RateLimit-Remaining"), "-1")

    def test_exempt_endpoints_not_rate_limited(self):
        self.app.config["RATE_LIMIT_REGULAR_DAILY_MAX"] = 1

        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.regular_id)
            sess["_fresh"] = True

        # Consume quota
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 200)

        # /api/dashboard is now blocked
        resp = self.client.get("/api/dashboard")
        self.assertEqual(resp.status_code, 429)

        # But /api/health is exempt and still returns 200
        resp = self.client.get("/api/health")
        self.assertEqual(resp.status_code, 200)


class McpDailyRateLimitIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.app = create_connect_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "CONNECT_CORS_ALLOWED_ORIGINS": (),
                "RATE_LIMIT_DAILY_ENABLED": True,
                "RATE_LIMIT_REGULAR_DAILY_MAX": 2,
                "RATE_LIMIT_CREATOR_DAILY_MAX": 5,
                "RATE_LIMIT_BACKEND": "local",
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            daily_rate_limit_service.reset_local_rate_limit_state()
            mcp_access_token_service.reset_rate_limit_state()
            db.create_all()

            regular_role = UserRole(code="regular", name="Regular", is_admin=False, position=1)
            creator_role = UserRole(code="creator", name="Creator", is_admin=False, position=2)
            admin_role = UserRole(code="admin", name="Admin", is_admin=True, position=4)
            db.session.add_all([regular_role, creator_role, admin_role])
            db.session.flush()

            regular = create_note_user(db.session,
                username="mcp_regular",
                email="mcp_regular@example.com",
                role_id=regular_role.id,
                is_admin=False,
            )
            regular.set_password("password")

            creator = create_note_user(db.session,
                username="mcp_creator",
                email="mcp_creator@example.com",
                role_id=creator_role.id,
                is_admin=False,
            )
            creator.set_password("password")

            admin = create_note_user(db.session,
                username="mcp_admin",
                email="mcp_admin@example.com",
                role_id=admin_role.id,
                is_admin=True,
            )
            admin.set_password("password")

            db.session.add_all([regular, creator, admin])
            db.session.commit()

            # Issue tokens
            self.reg_token = mcp_access_token_service.issue_token(
                user_id=regular.id, name="Regular Token", scopes=["deck:read"]
            ).token

            self.creator_token = mcp_access_token_service.issue_token(
                user_id=creator.id, name="Creator Token", scopes=["deck:read"]
            ).token

            self.admin_token = mcp_access_token_service.issue_token(
                user_id=admin.id, name="Admin Token", scopes=["deck:read"]
            ).token

            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            daily_rate_limit_service.reset_local_rate_limit_state()
            mcp_access_token_service.reset_rate_limit_state()
            db.session.remove()
            db.drop_all()

    def test_mcp_regular_user_daily_rate_limit(self):
        # Regular quota is 2 in test setup
        headers = {"Authorization": f"Bearer {self.reg_token}", "Content-Type": "application/json"}
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        # Request 1: OK
        resp1 = self.client.post("/v1/mcp", json=payload, headers=headers)
        self.assertEqual(resp1.status_code, 200)

        # Request 2: OK
        resp2 = self.client.post("/v1/mcp", json=payload, headers=headers)
        self.assertEqual(resp2.status_code, 200)

        # Request 3: 429 Too Many Requests
        resp3 = self.client.post("/v1/mcp", json=payload, headers=headers)
        self.assertEqual(resp3.status_code, 429)
        data = resp3.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32029)
        self.assertIn("MCP_DAILY_RATE_LIMIT_EXCEEDED", data["error"]["data"]["code"])

    def test_mcp_admin_unlimited(self):
        # Admin is unlimited
        headers = {"Authorization": f"Bearer {self.admin_token}", "Content-Type": "application/json"}
        payload = {"jsonrpc": "2.0", "id": 1, "method": "tools/list", "params": {}}

        for i in range(10):
            resp = self.client.post("/v1/mcp", json=payload, headers=headers)
            self.assertEqual(resp.status_code, 200)


if __name__ == "__main__":
    unittest.main()
