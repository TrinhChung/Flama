"""Usage quotas: limit resolution, counters, and the API / MCP / web gates."""

from __future__ import annotations

import base64
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from PIL import Image

from app import create_app
from app.connect import create_connect_app
from app.services import media_staging_service, mcp_access_token_service, quota_service, user_api_token_service
from app.validators import RequestValidationError
from models import db
from models.quota import QuotaPolicy, UserQuotaOverride
from models.user import User
from models.user_role import UserRole
from tests.study_note_fixtures import create_note_user

try:
    import fakeredis
except ImportError:  # pragma: no cover - optional local dependency
    fakeredis = None

QUOTA_CONFIG = {
    "TESTING": True,
    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
    "WTF_CSRF_ENABLED": False,
    "RATE_LIMIT_DAILY_ENABLED": True,
    "RATE_LIMIT_BACKEND": "local",
    "QUOTA_CACHE_TTL_SECONDS": 0,
}


def _role_id(code: str) -> int | None:
    role = UserRole.query.filter_by(code=code).first()
    return role.id if role else None


def _set_policy(kind: str, *, enforce: bool, period: str = "day", **role_limits: int) -> None:
    row = db.session.get(QuotaPolicy, kind) or QuotaPolicy(quota_kind=kind)
    row.enforce = enforce
    row.period = period
    row.role_limits = role_limits
    db.session.add(row)
    db.session.commit()


class QuotaServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(dict(QUOTA_CONFIG))
        self.client = self.app.test_client()
        with self.app.app_context():
            regular = create_note_user(
                db.session, username="quota_regular", email="quota_regular@example.com", role_id=_role_id("regular")
            )
            creator = create_note_user(
                db.session, username="quota_creator", email="quota_creator@example.com", role_id=_role_id("creator")
            )
            admin = create_note_user(
                db.session, username="quota_admin", email="quota_admin@example.com", role_id=_role_id("admin"), is_admin=True
            )
            db.session.add_all([regular, creator, admin])
            db.session.commit()
            self.regular_id, self.creator_id, self.admin_id = regular.id, creator.id, admin.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_role_defaults_apply_without_policy_rows(self):
        with self.app.app_context():
            regular = db.session.get(User, self.regular_id)
            creator = db.session.get(User, self.creator_id)
            admin = db.session.get(User, self.admin_id)
            self.assertEqual(quota_service.resolve_limit(regular, "api").limit, 300)
            self.assertEqual(quota_service.resolve_limit(creator, "mcp").limit, 2000)
            self.assertEqual(quota_service.resolve_limit(regular, "media").limit, 100 * 1024 * 1024)
            self.assertFalse(quota_service.resolve_limit(regular, "api").enforce)
            admin_limit = quota_service.resolve_limit(admin, "api")
            self.assertIsNone(admin_limit.limit)
            self.assertEqual(admin_limit.source, "admin")

    def test_active_override_wins_and_expired_override_falls_back(self):
        with self.app.app_context():
            _set_policy("api", enforce=True, regular=5)
            db.session.add(UserQuotaOverride(user_id=self.regular_id, quota_kind="api", limit_value=50, period="month"))
            db.session.commit()
            regular = db.session.get(User, self.regular_id)
            limit = quota_service.resolve_limit(regular, "api")
            self.assertEqual((limit.limit, limit.period, limit.source), (50, "month", "override"))

            row = db.session.get(UserQuotaOverride, (self.regular_id, "api"))
            row.expires_at = quota_service.utcnow_naive() - timedelta(minutes=1)
            db.session.commit()
            limit = quota_service.resolve_limit(regular, "api")
            self.assertEqual((limit.limit, limit.period, limit.source), (5, "day", "role"))

    def test_unlimited_override(self):
        with self.app.app_context():
            _set_policy("mcp", enforce=True, regular=1)
            db.session.add(UserQuotaOverride(user_id=self.regular_id, quota_kind="mcp", limit_value=-1))
            db.session.commit()
            regular = db.session.get(User, self.regular_id)
            for _ in range(5):
                self.assertTrue(quota_service.consume(regular, "mcp").allowed)

    def test_monitor_mode_counts_but_never_blocks(self):
        with self.app.app_context():
            _set_policy("api", enforce=False, regular=2)
            regular = db.session.get(User, self.regular_id)
            decisions = [quota_service.consume(regular, "api") for _ in range(4)]
            self.assertTrue(all(decision.allowed for decision in decisions))
            self.assertEqual(decisions[-1].used, 4)
            overview = quota_service.get_usage_overview("api", "day")
            self.assertEqual(overview["total"], 4)
            self.assertEqual(overview["top"], [(self.regular_id, 4)])
            # Requests 3 and 4 were above the limit: recorded as "would block".
            self.assertEqual(overview["over"], [(self.regular_id, 2)])

    def test_enforce_mode_blocks_without_counting_rejected_requests(self):
        with self.app.app_context():
            _set_policy("api", enforce=True, regular=2)
            regular = db.session.get(User, self.regular_id)
            self.assertTrue(quota_service.consume(regular, "api").allowed)
            self.assertTrue(quota_service.consume(regular, "api").allowed)
            blocked = quota_service.consume(regular, "api")
            self.assertFalse(blocked.allowed)
            self.assertEqual(blocked.used, 2)
            self.assertGreater(blocked.reset_epoch, 0)
            usage = quota_service.get_users_usage([self.regular_id], ("api",))[self.regular_id]["api"]
            self.assertEqual(usage, {"day": 2, "month": 2, "year": 2})

    def test_batch_cost_cannot_overshoot_limit(self):
        with self.app.app_context():
            _set_policy("api", enforce=True, regular=5)
            regular = db.session.get(User, self.regular_id)
            self.assertTrue(quota_service.consume(regular, "api", 4).allowed)
            self.assertFalse(quota_service.consume(regular, "api", 2).allowed)
            self.assertTrue(quota_service.consume(regular, "api", 1).allowed)

    def test_month_period_uses_month_counter(self):
        with self.app.app_context():
            _set_policy("mcp", enforce=True, period="month", regular=3)
            regular = db.session.get(User, self.regular_id)
            results = [quota_service.consume(regular, "mcp").allowed for _ in range(4)]
            self.assertEqual(results, [True, True, True, False])
            decision = quota_service.consume(regular, "mcp")
            self.assertEqual(decision.period, "month")

    def test_media_limit_is_megabytes(self):
        with self.app.app_context():
            _set_policy("media", enforce=True, regular=1)
            self.assertTrue(quota_service.consume_media(self.regular_id, 700 * 1024).allowed)
            self.assertFalse(quota_service.consume_media(self.regular_id, 400 * 1024).allowed)
            self.assertTrue(quota_service.consume_media(None, 10 * 1024 * 1024).allowed)

    def test_metering_switch_off_counts_nothing(self):
        with self.app.app_context():
            self.app.config["RATE_LIMIT_DAILY_ENABLED"] = False
            _set_policy("api", enforce=True, regular=1)
            regular = db.session.get(User, self.regular_id)
            for _ in range(3):
                self.assertTrue(quota_service.consume(regular, "api").allowed)
            self.assertEqual(quota_service.get_usage_overview("api", "day")["total"], 0)

    def test_cached_limits_refresh_after_invalidation(self):
        with self.app.app_context():
            self.app.config["QUOTA_CACHE_TTL_SECONDS"] = 3600
            _set_policy("api", enforce=True, regular=1)
            regular = db.session.get(User, self.regular_id)
            self.assertEqual(quota_service.resolve_limit(regular, "api").limit, 1)
            _set_policy("api", enforce=True, regular=9)
            self.assertEqual(quota_service.resolve_limit(regular, "api").limit, 1)
            quota_service.invalidate_cache()
            self.assertEqual(quota_service.resolve_limit(regular, "api").limit, 9)

    def test_period_windows_follow_configured_timezone(self):
        with self.app.app_context():
            # 2026-12-31 18:30 UTC is already 2027-01-01 01:30 in Asia/Ho_Chi_Minh.
            windows = quota_service.period_windows(datetime(2026, 12, 31, 18, 30, tzinfo=timezone.utc))
            self.assertEqual(windows["day"].token, "2027-01-01")
            self.assertEqual(windows["month"].token, "2027-01")
            self.assertEqual(windows["year"].token, "2027")
            self.assertEqual(
                windows["month"].end.astimezone(timezone.utc), datetime(2027, 1, 31, 17, 0, tzinfo=timezone.utc)
            )

    def test_web_requests_are_never_metered(self):
        with self.app.app_context():
            _set_policy("api", enforce=True, regular=1)
            _set_policy("mcp", enforce=True, regular=1)
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.regular_id)
            sess["_fresh"] = True
        for _ in range(5):
            response = self.client.get("/api/health")
            self.assertEqual(response.status_code, 200)
            self.assertNotIn("X-RateLimit-Limit", response.headers)
            self.assertEqual(self.client.get("/api/session").status_code, 200)
        with self.app.app_context():
            self.assertEqual(quota_service.get_usage_overview("api", "day")["total"], 0)

    def test_enforced_media_quota_blocks_paste_before_storing(self):
        with self.app.app_context(), tempfile.TemporaryDirectory() as upload_root:
            _set_policy("media", enforce=True, regular=0)
            image = BytesIO()
            Image.new("RGB", (40, 40), color=(0, 128, 255)).save(image, format="PNG")
            with self.assertRaises(RequestValidationError) as raised:
                media_staging_service.stage_pasted_image(
                    user_id=self.regular_id,
                    base64_data=base64.b64encode(image.getvalue()).decode("ascii"),
                    upload_root=Path(upload_root),
                )
            self.assertEqual((raised.exception.code, raised.exception.status), ("MEDIA_QUOTA_EXCEEDED", 429))
            self.assertEqual(list(Path(upload_root).rglob("*.webp")), [])

    def test_redis_failure_falls_back_to_local_counters(self):
        with self.app.app_context():
            self.app.config["RATE_LIMIT_BACKEND"] = "redis"
            _set_policy("api", enforce=True, regular=1)
            regular = db.session.get(User, self.regular_id)
            with mock.patch.object(
                quota_service.redis_state_service, "redis_client", side_effect=RuntimeError("redis down")
            ):
                self.assertTrue(quota_service.consume(regular, "api").allowed)
                self.assertFalse(quota_service.consume(regular, "api").allowed)


@unittest.skipIf(fakeredis is None, "fakeredis[lua] is not installed")
class QuotaRedisScriptTests(unittest.TestCase):
    """Run the production Lua script against fakeredis to pin its semantics."""

    def setUp(self):
        self.app = create_app({**QUOTA_CONFIG, "RATE_LIMIT_BACKEND": "redis"})
        self.fake = fakeredis.FakeRedis(decode_responses=True)
        self.patcher = mock.patch.object(quota_service.redis_state_service, "redis_client", return_value=self.fake)
        self.patcher.start()
        with self.app.app_context():
            user = create_note_user(db.session, username="quota_redis", email="quota_redis@example.com", role_id=_role_id("regular"))
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

    def tearDown(self):
        self.patcher.stop()
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_script_counts_ranks_and_blocks(self):
        with self.app.app_context():
            _set_policy("mcp", enforce=False, regular=2)
            user = db.session.get(User, self.user_id)
            for _ in range(3):
                self.assertTrue(quota_service.consume(user, "mcp").allowed)
            overview = quota_service.get_usage_overview("mcp", "day")
            self.assertEqual(overview["total"], 3)
            self.assertEqual(overview["top"], [(self.user_id, 3)])
            self.assertEqual(overview["over"], [(self.user_id, 1)])
            self.assertEqual(quota_service.get_users_usage([self.user_id], ("mcp",))[self.user_id]["mcp"]["year"], 3)

            _set_policy("mcp", enforce=True, regular=3)
            quota_service.invalidate_cache()
            blocked = quota_service.consume(user, "mcp")
            self.assertFalse(blocked.allowed)
            self.assertEqual(blocked.used, 3)
            self.assertEqual(quota_service.get_usage_overview("mcp", "day")["total"], 3)

    def test_keys_expire_after_their_period(self):
        with self.app.app_context():
            user = db.session.get(User, self.user_id)
            quota_service.consume(user, "api")
            windows = quota_service.period_windows()
            day_key = quota_service._user_key("api", self.user_id, windows["day"])
            ranking_key = quota_service._history_key("api", "top", windows["day"])
            now = int(datetime.now(timezone.utc).timestamp())
            self.assertLessEqual(self.fake.ttl(day_key), windows["day"].reset_epoch + 86_400 - now)
            self.assertGreater(self.fake.ttl(ranking_key), 399 * 86_400)


class QuotaGateIntegrationTests(unittest.TestCase):
    """Connect API and MCP requests go through the quota gate; web requests do not."""

    def setUp(self):
        self.app = create_connect_app(
            {
                **QUOTA_CONFIG,
                "CONNECT_CORS_ALLOWED_ORIGINS": (),
                "CONNECT_IP_RATE_LIMIT": 1000,
                "CONNECT_TOKEN_RATE_LIMIT": 1000,
                "CONNECT_USER_RATE_LIMIT": 1000,
                "CONNECT_LEGACY_WEB_ACTIONS_ENABLED": True,
            }
        )
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            role = UserRole(code="regular", name="Regular", is_admin=False, position=1)
            db.session.add(role)
            db.session.flush()
            user = create_note_user(db.session, username="gate_user", email="gate@example.com", role_id=role.id)
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id
            self.api_token = user_api_token_service.issue_token(user_id=user.id, name="Gate Token").plaintext
            self.mcp_token = mcp_access_token_service.issue_token(
                user_id=user.id, name="Gate MCP", scopes=["deck:read"]
            ).token
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            mcp_access_token_service.reset_rate_limit_state()
            db.session.remove()
            db.drop_all()

    def _mcp(self, method, params=None):
        return self.client.post(
            "/v1/mcp",
            json={"jsonrpc": "2.0", "id": 1, "method": method, "params": params or {}},
            headers={"Authorization": f"Bearer {self.mcp_token}"},
        )

    def test_mcp_counts_only_private_tool_calls(self):
        with self.app.app_context():
            _set_policy("mcp", enforce=True, regular=2)
        for _ in range(3):
            self.assertEqual(self._mcp("initialize").status_code, 200)
            self.assertEqual(self._mcp("tools/list").status_code, 200)
        call = {"name": "list_my_decks", "arguments": {}}
        self.assertEqual(self._mcp("tools/call", call).status_code, 200)
        self.assertEqual(self._mcp("tools/call", call).status_code, 200)
        blocked = self._mcp("tools/call", call)
        self.assertEqual(blocked.status_code, 429)
        body = blocked.get_json()
        self.assertEqual(body["error"]["code"], -32029)
        self.assertEqual(body["error"]["data"]["code"], "MCP_QUOTA_EXCEEDED")

    def test_connect_api_requests_are_counted_and_blocked(self):
        with self.app.app_context():
            _set_policy("api", enforce=True, regular=2)
        headers = {"Authorization": f"Bearer {self.api_token}"}
        for _ in range(2):
            ok = self.client.post("/v1/flama-connect", headers=headers, json={"action": "validateKey", "version": 6})
            self.assertEqual(ok.get_json().get("status"), "valid")
        blocked = self.client.post("/v1/flama-connect", headers=headers, json={"action": "validateKey", "version": 6})
        self.assertEqual(blocked.status_code, 429)
        self.assertEqual(blocked.get_json().get("error"), "API quota exceeded for this period")
        with self.app.app_context():
            self.assertEqual(quota_service.get_usage_overview("api", "day")["top"], [(self.user_id, 2)])


if __name__ == "__main__":
    unittest.main()
