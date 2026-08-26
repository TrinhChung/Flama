"""Multi-worker shared-state regression tests without an external Redis."""

from __future__ import annotations

import json
import os
import time
import unittest
import uuid
from unittest.mock import patch

from flask import Flask

from app.services import (
    login_rate_limit_service,
    mcp_access_token_service,
    mcp_preview_service,
    redis_state_service,
)


class _FakeRedis:
    def __init__(self):
        self.values: dict[str, str] = {}
        self.counters: dict[str, int] = {}
        self.attempts: dict[str, list[float]] = {}
        self.expiries: dict[str, float] = {}

    def set(self, key, value, ex=None):
        self.values[str(key)] = str(value)
        if ex:
            self.expiries[str(key)] = time.time() + int(ex)
        return True

    def delete(self, *keys):
        for key in keys:
            self.values.pop(str(key), None)
            self.attempts.pop(str(key), None)
            self.expiries.pop(str(key), None)
        return len(keys)

    def ttl(self, key):
        expires_at = self.expiries.get(str(key))
        if expires_at is None:
            return -2
        return max(int(expires_at - time.time()), 0)

    def eval(self, script, numkeys, *values):
        key = str(values[0])
        args = values[int(numkeys):]
        if "cjson.decode" in script:
            raw = self.values.get(key)
            if raw is None:
                return "NOT_FOUND"
            item = json.loads(raw)
            checks = (
                (str(item["user_id"]), str(args[0]), "FORBIDDEN"),
                (str(item["action"]), str(args[1]), "ACTION_MISMATCH"),
                (str(item["resource_id"]), str(args[2]), "RESOURCE_MISMATCH"),
                (str(item["resource_version"]), str(args[3]), "STALE"),
            )
            for actual, expected, error in checks:
                if actual != expected:
                    return error
            self.delete(key)
            return "OK"
        if "ZREMRANGEBYSCORE" in script:
            attempts_key = key
            lock_key = str(values[1])
            window = float(args[0])
            now = time.time()
            cutoff = now - window
            attempts = [value for value in self.attempts.get(attempts_key, []) if value > cutoff]
            attempts.append(now)
            self.attempts[attempts_key] = attempts
            if len(attempts) >= int(args[2]):
                self.values[lock_key] = "1"
                self.expiries[lock_key] = time.time() + int(args[3])
                self.attempts.pop(attempts_key, None)
            return len(attempts)
        if "INCR" in script:
            count = self.counters.get(key, 0) + 1
            self.counters[key] = count
            return count
        raise AssertionError("Unexpected Redis script")


class SharedStateServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="shared-state-test",
            RATE_LIMIT_KEY_PREFIX="test:v1",
            RATE_LIMIT_BACKEND="redis",
            MCP_PREVIEW_BACKEND="redis",
            LOGIN_RATE_LIMIT_ENABLED=True,
            LOGIN_RATE_LIMIT_MAX_ATTEMPTS=3,
            LOGIN_RATE_LIMIT_WINDOW_SECONDS=60,
            LOGIN_RATE_LIMIT_LOCKOUT_SECONDS=60,
            MCP_TOKEN_RATE_LIMIT_ENABLED=True,
            MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS=2,
            MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS=60,
        )
        self.redis = _FakeRedis()
        login_rate_limit_service.reset_state()
        mcp_access_token_service.reset_rate_limit_state()
        mcp_preview_service._PREVIEW_TOKENS.clear()

    def test_preview_token_can_cross_workers_and_is_claimed_once(self):
        with self.app.app_context(), patch.object(
            redis_state_service,
            "redis_client",
            return_value=self.redis,
        ):
            preview_id, _ = mcp_preview_service.create_preview_token(
                user_id=7,
                action="delete_note_type",
                resource_id="nt-1",
                resource_version="v1",
                impact_summary={"notes": 0},
            )
            mcp_preview_service._PREVIEW_TOKENS.clear()
            first = mcp_preview_service.validate_preview_token(
                preview_id=preview_id,
                user_id=7,
                action="delete_note_type",
                resource_id="nt-1",
                current_resource_version="v1",
            )
            second = mcp_preview_service.validate_preview_token(
                preview_id=preview_id,
                user_id=7,
                action="delete_note_type",
                resource_id="nt-1",
                current_resource_version="v1",
            )
        self.assertTrue(first[0])
        self.assertEqual(second[1], "PREVIEW_TOKEN_NOT_FOUND")

    def test_redis_preview_cleanup_does_not_touch_redis_after_claim(self):
        with self.app.app_context(), patch.object(
            redis_state_service,
            "redis_client",
            return_value=self.redis,
        ):
            preview_id, _ = mcp_preview_service.create_preview_token(
                user_id=7,
                action="delete_note_type",
                resource_id="nt-2",
                resource_version="v1",
                impact_summary={"notes": 0},
            )
            valid, _, _ = mcp_preview_service.validate_preview_token(
                preview_id=preview_id,
                user_id=7,
                action="delete_note_type",
                resource_id="nt-2",
                current_resource_version="v1",
            )
            self.assertTrue(valid)

        with self.app.app_context(), patch.object(
            redis_state_service,
            "redis_client",
            side_effect=RuntimeError("redis dropped after claim"),
        ):
            mcp_preview_service.consume_preview_token(preview_id)

    def test_login_lockout_survives_process_local_reset(self):
        with self.app.app_context(), patch.object(
            redis_state_service,
            "redis_client",
            return_value=self.redis,
        ):
            for _ in range(3):
                login_rate_limit_service.register_failure(
                    email="user@example.com",
                    remote_addr="203.0.113.10",
                )
                login_rate_limit_service.reset_state()
            remaining = login_rate_limit_service.get_lockout_remaining(
                email="user@example.com",
                remote_addr="203.0.113.10",
            )
        self.assertGreater(remaining, 0)

    def test_mcp_short_window_limit_is_shared(self):
        with self.app.app_context(), patch.object(
            redis_state_service,
            "redis_client",
            return_value=self.redis,
        ):
            mcp_access_token_service.enforce_rate_limit(bucket_key="token-1")
            mcp_access_token_service.reset_rate_limit_state()
            mcp_access_token_service.enforce_rate_limit(bucket_key="token-1")
            mcp_access_token_service.reset_rate_limit_state()
            with self.assertRaises(mcp_access_token_service.McpAccessTokenError) as context:
                mcp_access_token_service.enforce_rate_limit(bucket_key="token-1")
        self.assertEqual(context.exception.code, "MCP_RATE_LIMIT_EXCEEDED")


@unittest.skipUnless(os.getenv("REDIS_URL"), "REDIS_URL is not configured")
class RedisSharedStateIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.prefix = f"flama:test:{uuid.uuid4().hex}"
        self.app = Flask(__name__)
        self.app.config.update(
            SECRET_KEY="redis-integration-test",
            REDIS_URL=os.environ["REDIS_URL"],
            RATE_LIMIT_KEY_PREFIX=self.prefix,
            RATE_LIMIT_BACKEND="redis",
            MCP_PREVIEW_BACKEND="redis",
            LOGIN_RATE_LIMIT_ENABLED=True,
            LOGIN_RATE_LIMIT_MAX_ATTEMPTS=3,
            LOGIN_RATE_LIMIT_WINDOW_SECONDS=60,
            LOGIN_RATE_LIMIT_LOCKOUT_SECONDS=60,
        )
        redis_state_service.clear_client_cache()
        with self.app.app_context():
            try:
                self.client = redis_state_service.redis_client()
                self.client.ping()
            except Exception as exc:
                self.skipTest(f"Redis is unavailable: {exc}")

    def tearDown(self):
        client = getattr(self, "client", None)
        if client is not None:
            keys = list(client.scan_iter(match=f"{self.prefix}:*"))
            if keys:
                client.delete(*keys)
        redis_state_service.clear_client_cache()

    def test_real_redis_login_window_and_preview_claim(self):
        email = "redis-user@example.com"
        remote_addr = "203.0.113.99"
        with self.app.app_context():
            for _ in range(3):
                login_rate_limit_service.register_failure(
                    email=email,
                    remote_addr=remote_addr,
                )
            remaining = login_rate_limit_service.get_lockout_remaining(
                email=email,
                remote_addr=remote_addr,
            )
            preview_id, _ = mcp_preview_service.create_preview_token(
                user_id=17,
                action="delete_note_type",
                resource_id="nt-real-redis",
                resource_version="v1",
                impact_summary={"notes": 0},
            )
            first = mcp_preview_service.validate_preview_token(
                preview_id=preview_id,
                user_id=17,
                action="delete_note_type",
                resource_id="nt-real-redis",
                current_resource_version="v1",
            )
            second = mcp_preview_service.validate_preview_token(
                preview_id=preview_id,
                user_id=17,
                action="delete_note_type",
                resource_id="nt-real-redis",
                current_resource_version="v1",
            )
            keys = [str(key) for key in self.client.scan_iter(match=f"{self.prefix}:*")]

        self.assertGreater(remaining, 0)
        self.assertTrue(first[0])
        self.assertEqual(second[1], "PREVIEW_TOKEN_NOT_FOUND")
        self.assertTrue(all(email not in key and remote_addr not in key for key in keys))


if __name__ == "__main__":
    unittest.main()
