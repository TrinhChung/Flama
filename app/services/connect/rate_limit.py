"""Connect rate budgets with the existing shared Redis connection."""

from collections import defaultdict, deque
from threading import Lock
import time
from uuid import uuid4

from flask import current_app
from app.services import redis_state_service as shared


class SlidingWindowLimiter:
    def __init__(self):
        self._events = defaultdict(deque)
        self._lock = Lock()

    def allow(self, key, *, maximum, window_seconds, cost=1):
        now = time.monotonic()
        cutoff = now - window_seconds
        with self._lock:
            if len(self._events) >= 10_000:
                for item in [key for key, events in self._events.items() if not events or events[-1] <= cutoff]:
                    self._events.pop(item, None)
            if key not in self._events and len(self._events) >= 20_000:
                return False
            events = self._events[key]
            while events and events[0] <= cutoff:
                events.popleft()
            if len(events) + cost > maximum:
                return False
            events.extend([now] * cost)
            return True


_limiter = SlidingWindowLimiter()
_LUA = """
local t = redis.call('TIME')
local now = tonumber(t[1]) * 1000 + tonumber(t[2]) / 1000
local window = tonumber(ARGV[1]) * 1000
local cost = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) + cost > tonumber(ARGV[2]) then return 0 end
for i = 1, cost do redis.call('ZADD', KEYS[1], now, ARGV[4] .. ':' .. i) end
redis.call('PEXPIRE', KEYS[1], window)
return 1
"""


def rate_allowed(key, config_name, default, *, cost=1):
    maximum = max(1, int(current_app.config.get(config_name, default)))
    window = max(1, int(current_app.config.get("CONNECT_RATE_LIMIT_WINDOW_SECONDS", 60)))
    mode = shared.backend_mode("CONNECT_RATE_LIMIT_BACKEND")
    if mode != "local":
        try:
            allowed = bool(shared.redis_client().eval(_LUA, 1, shared.private_key("connect-rate", key), window, maximum, cost, uuid4().hex))
            if mode == "redis":
                return allowed
        except Exception as exc:
            if mode == "redis":
                raise shared.SharedStateUnavailable("Connect rate limiter unavailable") from exc
            current_app.logger.warning("Connect shadow Redis limiter unavailable")
    limiter = current_app.extensions.get("connect_rate_limiter", _limiter)
    return limiter.allow(key, maximum=maximum, window_seconds=window, cost=cost)
