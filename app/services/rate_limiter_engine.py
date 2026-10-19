"""Unified rate limiting and lockout engine supporting local in-memory and Redis backends."""

from __future__ import annotations

from collections import defaultdict
import logging
import math
import secrets
from threading import Lock
import time
from typing import Sequence

from flask import current_app

from app.services import redis_state_service

logger = logging.getLogger(__name__)

# Redis Lua script for registering failure in sliding window and establishing lockout
_FAILURE_LOCKOUT_SCRIPT = """
local clock = redis.call('TIME')
local now = tonumber(clock[1]) + (tonumber(clock[2]) / 1000000)
local window = math.max(tonumber(ARGV[1]), 1)
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
redis.call('ZADD', KEYS[1], now, ARGV[2])
redis.call('EXPIRE', KEYS[1], window)
local count = redis.call('ZCARD', KEYS[1])
if count >= tonumber(ARGV[3]) then
  redis.call('SET', KEYS[2], '1', 'EX', math.max(tonumber(ARGV[4]), 1))
  redis.call('DEL', KEYS[1])
end
return count
"""

# Redis Lua script for consuming requests with fixed/sliding counter
_COUNTER_CONSUME_SCRIPT = """
local count = redis.call('INCR', KEYS[1])
if count == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
return {count, redis.call('TTL', KEYS[1])}
"""


class LockoutRateLimiter:
    """Sliding-window lockout limiter (used for brute-force login and password protection)."""

    def __init__(self, name: str) -> None:
        self.name = name
        self._attempts: dict[str, list[float]] = defaultdict(list)
        self._lockouts: dict[str, float] = {}
        self._lock = Lock()

    def reset_state(self) -> None:
        """Clear local in-memory state."""
        with self._lock:
            self._attempts.clear()
            self._lockouts.clear()

    def _prune(self, *, now: float, window: int, lockout: int) -> None:
        stale_threshold = now - max(window, lockout) - 60
        for key in list(self._attempts.keys()):
            remaining = [v for v in self._attempts[key] if v >= now - window]
            if remaining:
                self._attempts[key] = remaining
            elif not self._attempts[key]:
                del self._attempts[key]

        for key, unlock_at in list(self._lockouts.items()):
            if unlock_at <= stale_threshold:
                del self._lockouts[key]

    def get_lockout_remaining(
        self,
        *,
        bucket_keys: Sequence[str],
        window: int,
        lockout: int,
    ) -> int:
        """Return remaining lockout duration in seconds if active, 0 otherwise."""
        now = time.time()
        with self._lock:
            self._prune(now=now, window=window, lockout=lockout)
            local_remaining = 0
            for bucket_key in bucket_keys:
                unlock_at = float(self._lockouts.get(bucket_key) or 0)
                if unlock_at > now:
                    local_remaining = max(local_remaining, math.ceil(unlock_at - now))

        mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
        if mode == "local":
            return local_remaining

        try:
            client = redis_state_service.redis_client()
            redis_remaining = max(
                (max(int(client.ttl(f"{k}:lock") or 0), 0) for k in bucket_keys),
                default=0,
            )
            if mode == "shadow_redis" and bool(redis_remaining) != bool(local_remaining):
                current_app.logger.info(
                    "%s limiter shadow mismatch local_locked=%s redis_locked=%s",
                    self.name,
                    bool(local_remaining),
                    bool(redis_remaining),
                )
            return redis_remaining if mode == "redis" else local_remaining
        except Exception as exc:
            current_app.logger.warning(
                "Redis %s limiter read failed; using local fallback: %s", self.name, exc
            )
            return local_remaining

    def register_failure(
        self,
        *,
        bucket_keys: Sequence[str],
        window: int,
        max_attempts: int,
        lockout: int,
    ) -> None:
        """Record a failed attempt across the specified bucket keys."""
        now = time.time()
        with self._lock:
            self._prune(now=now, window=window, lockout=lockout)
            for bucket_key in bucket_keys:
                attempts = self._attempts[bucket_key]
                attempts.append(now)
                attempts[:] = [v for v in attempts if v >= now - window]
                if len(attempts) >= max_attempts:
                    self._lockouts[bucket_key] = max(
                        self._lockouts.get(bucket_key, 0), now + lockout
                    )
                    attempts.clear()

        mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
        if mode == "local":
            return

        try:
            client = redis_state_service.redis_client()
            for bucket_key in bucket_keys:
                client.eval(
                    _FAILURE_LOCKOUT_SCRIPT,
                    2,
                    f"{bucket_key}:attempts",
                    f"{bucket_key}:lock",
                    max(window, 1),
                    f"{now}:{secrets.token_hex(4)}",
                    max(max_attempts, 1),
                    max(lockout, 1),
                )
        except Exception as exc:
            current_app.logger.warning(
                "Redis %s limiter write failed; local fallback remains active: %s",
                self.name,
                exc,
            )

    def register_success(self, *, bucket_keys: Sequence[str]) -> None:
        """Clear attempts for successful credentials."""
        with self._lock:
            for bucket_key in bucket_keys:
                self._attempts.pop(bucket_key, None)

        mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
        if mode == "local":
            return

        try:
            client = redis_state_service.redis_client()
            for bucket_key in bucket_keys:
                client.delete(f"{bucket_key}:attempts")
        except Exception as exc:
            current_app.logger.warning(
                "Redis %s limiter success clear failed: %s", self.name, exc
            )
