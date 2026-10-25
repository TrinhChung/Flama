"""Admin quota screen API: policies, per-user overrides, usage and search."""

from __future__ import annotations

from datetime import date, timedelta
import unittest

from app import create_app
from app.services import quota_service
from models import db
from models.quota import QuotaPolicy, UserQuotaOverride
from models.user import User
from models.user_role import UserRole
from tests.study_note_fixtures import create_note_user


class AdminQuotasApiTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "RATE_LIMIT_DAILY_ENABLED": True,
                "RATE_LIMIT_BACKEND": "local",
                "QUOTA_CACHE_TTL_SECONDS": 0,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            role_ids = {role.code: role.id for role in UserRole.query.all()}
            admin = create_note_user(
                db.session, username="quota_boss", email="boss@example.com", role_id=role_ids.get("admin"), is_admin=True
            )
            member = create_note_user(
                db.session, username="quota_member", email="member@example.com", role_id=role_ids.get("regular")
            )
            db.session.add_all([admin, member])
            db.session.commit()
            self.admin_id, self.member_id = admin.id, member.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self, user_id: int) -> None:
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(user_id)
            sess["_fresh"] = True

    def test_requires_admin(self):
        self._login(self.member_id)
        self.assertEqual(self.client.get("/api/admin/quotas").status_code, 403)
        self.assertEqual(
            self.client.put(f"/api/admin/quotas/users/{self.member_id}/api", json={"limit_value": 5}).status_code, 403
        )

    def test_overview_lists_policies_roles_usage_and_overrides(self):
        with self.app.app_context():
            member = db.session.get(User, self.member_id)
            quota_service.consume(member, "mcp")
            quota_service.consume_media(self.member_id, 3 * 1024 * 1024)
        self._login(self.admin_id)
        response = self.client.get("/api/admin/quotas?period=day")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual([p["kind"] for p in data["policies"]], ["api", "mcp", "media"])
        self.assertTrue(all(p["enforce"] is False for p in data["policies"]))
        self.assertEqual(data["policies"][2]["unit"], "MB")
        self.assertNotIn("admin", [role["code"] for role in data["roles"]])
        self.assertEqual(data["usage"]["mcp"]["total"], 1)
        self.assertEqual(data["usage"]["mcp"]["top"][0]["user"]["username"], "quota_member")
        self.assertEqual(data["usage"]["mcp"]["top"][0]["effective"]["source"], "role")
        self.assertEqual(data["usage"]["media"]["total"], 3.0)
        self.assertEqual(data["settings"]["backend"], "local")
        self.assertEqual(self.client.get("/api/admin/quotas?period=week").status_code, 400)

    def test_update_policy_and_validation(self):
        self._login(self.admin_id)
        response = self.client.put(
            "/api/admin/quotas/policies/api",
            json={"enforce": True, "period": "month", "role_limits": {"regular": 50, "creator": -1}},
        )
        self.assertEqual(response.status_code, 200)
        policy = response.get_json()["policy"]
        self.assertEqual((policy["enforce"], policy["period"]), (True, "month"))
        self.assertEqual(policy["role_limits"]["regular"], 50)
        self.assertEqual(policy["role_limits"]["creator"], -1)
        self.assertEqual(policy["role_limits"]["enterprise"], 10000)
        with self.app.app_context():
            row = db.session.get(QuotaPolicy, "api")
            self.assertEqual(row.updated_by_user_id, self.admin_id)
            member = db.session.get(User, self.member_id)
            self.assertEqual(quota_service.resolve_limit(member, "api").limit, 50)

        bad_payloads = [
            ({"period": "week"}, "period"),
            ({"enforce": "yes"}, "enforce"),
            ({"role_limits": {"regular": -5}}, "role_limits.regular"),
            ({"role_limits": {"regular": 1.5}}, "role_limits.regular"),
            ({"role_limits": {"admin": 10}}, "role_limits"),
            ({"role_limits": []}, "role_limits"),
        ]
        for payload, field in bad_payloads:
            with self.subTest(payload=payload):
                bad = self.client.put("/api/admin/quotas/policies/api", json=payload)
                self.assertEqual(bad.status_code, 400)
                self.assertEqual(bad.get_json()["field"], field)
        self.assertEqual(self.client.put("/api/admin/quotas/policies/sms", json={}).status_code, 404)

    def test_override_lifecycle(self):
        self._login(self.admin_id)
        last_day = (date.today() + timedelta(days=30)).isoformat()
        response = self.client.put(
            f"/api/admin/quotas/users/{self.member_id}/media",
            json={"limit_value": 500, "period": "month", "expires_on": last_day, "note": "Lớp học thử"},
        )
        self.assertEqual(response.status_code, 200)
        media = next(q for q in response.get_json()["quotas"] if q["kind"] == "media")
        self.assertEqual(media["override"]["limit_value"], 500)
        self.assertEqual(media["override"]["expires_on"], last_day)
        self.assertEqual(media["effective"]["source"], "override")
        self.assertEqual(media["effective"]["limit_value"], 500)
        self.assertEqual(media["effective"]["period"], "month")

        overview = self.client.get("/api/admin/quotas").get_json()
        self.assertEqual(len(overview["overrides"]), 1)
        self.assertEqual(overview["overrides"][0]["user"]["username"], "quota_member")
        self.assertTrue(overview["overrides"][0]["is_active"])

        deleted = self.client.delete(f"/api/admin/quotas/users/{self.member_id}/media")
        self.assertEqual(deleted.status_code, 200)
        media = next(q for q in deleted.get_json()["quotas"] if q["kind"] == "media")
        self.assertIsNone(media["override"])
        self.assertEqual(media["effective"]["source"], "role")
        with self.app.app_context():
            self.assertIsNone(db.session.get(UserQuotaOverride, (self.member_id, "media")))

    def test_override_validation(self):
        self._login(self.admin_id)
        url = f"/api/admin/quotas/users/{self.member_id}/api"
        yesterday = (date.today() - timedelta(days=2)).isoformat()
        cases = [
            ({}, "limit_value"),
            ({"limit_value": -2}, "limit_value"),
            ({"limit_value": "abc"}, "limit_value"),
            ({"limit_value": 10, "period": "hour"}, "period"),
            ({"limit_value": 10, "expires_on": "31/12/2026"}, "expires_on"),
            ({"limit_value": 10, "expires_on": yesterday}, "expires_on"),
            ({"limit_value": 10, "note": "x" * 256}, "note"),
        ]
        for payload, field in cases:
            with self.subTest(payload=payload):
                bad = self.client.put(url, json=payload)
                self.assertEqual(bad.status_code, 400)
                self.assertEqual(bad.get_json()["field"], field)
        self.assertEqual(self.client.put("/api/admin/quotas/users/999999/api", json={"limit_value": 1}).status_code, 404)

    def test_user_detail_and_search(self):
        with self.app.app_context():
            member = db.session.get(User, self.member_id)
            quota_service.consume(member, "api", 3)
        self._login(self.admin_id)
        detail = self.client.get(f"/api/admin/quotas/users/{self.member_id}").get_json()
        api = next(q for q in detail["quotas"] if q["kind"] == "api")
        self.assertEqual(api["usage"], {"day": 3, "month": 3, "year": 3})
        self.assertEqual(api["role_limit"], 300)
        found = self.client.get("/api/admin/quotas/users/search?q=member").get_json()["items"]
        self.assertEqual([item["id"] for item in found], [self.member_id])
        self.assertEqual(self.client.get("/api/admin/quotas/users/search?q=").get_json()["items"], [])


if __name__ == "__main__":
    unittest.main()
