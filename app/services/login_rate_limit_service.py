"""Small in-memory login throttling helper."""

from __future__ import annotations

import math
import secrets
import time
from collections import defaultdict
from threading import Lock

from flask import current_app

from app.services import redis_state_service

_attempts: dict[str, list[float]] = defaultdict(list)
_lockouts: dict[str, float] = {}
_state_lock = Lock()


def reset_state() -> None:
    with _state_lock:
        _attempts.clear()
        _lockouts.clear()


def get_lockout_remaining(*, email: str, remote_addr: str | None) -> int:
    if not _enabled():
        return 0

    now = time.time()
    window = int(current_app.config.get("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60))
    lockout = int(current_app.config.get("LOGIN_RATE_LIMIT_LOCKOUT_SECONDS", 300))
    bucket_keys = _bucket_keys(email=email, remote_addr=remote_addr)
    local_remaining = _get_local_lockout_remaining(
        bucket_keys=bucket_keys,
        now=now,
        window=window,
        lockout=lockout,
    )
    mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
    if mode == "local":
        return local_remaining
    try:
        client = redis_state_service.redis_client()
        redis_remaining = max(
            (
                max(int(client.ttl(f"{bucket_key}:lock") or 0), 0)
                for bucket_key in bucket_keys
            ),
            default=0,
        )
        if mode == "shadow_redis" and bool(redis_remaining) != bool(local_remaining):
            current_app.logger.info(
                "Login limiter shadow mismatch local_locked=%s redis_locked=%s",
                bool(local_remaining),
                bool(redis_remaining),
            )
        return redis_remaining if mode == "redis" else local_remaining
    except Exception as exc:
        current_app.logger.warning("Redis login limiter read failed; using local fallback: %s", exc)
        return local_remaining


def _get_local_lockout_remaining(
    *, bucket_keys: tuple[str, str], now: float, window: int, lockout: int
) -> int:
    with _state_lock:
        _prune_state(now=now, window=window, lockout=lockout)
        remaining = 0
        for bucket_key in bucket_keys:
            unlock_at = float(_lockouts.get(bucket_key) or 0)
            if unlock_at > now:
                remaining = max(remaining, math.ceil(unlock_at - now))
        return remaining


def register_failure(*, email: str, remote_addr: str | None) -> None:
    if not _enabled():
        return

    now = time.time()
    window = int(current_app.config.get("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60))
    max_attempts = int(current_app.config.get("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 5))
    lockout = int(current_app.config.get("LOGIN_RATE_LIMIT_LOCKOUT_SECONDS", 300))
    bucket_keys = _bucket_keys(email=email, remote_addr=remote_addr)
    _register_local_failure(
        bucket_keys=bucket_keys,
        now=now,
        window=window,
        max_attempts=max_attempts,
        lockout=lockout,
    )
    mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
    if mode == "local":
        return
    script = """
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
    try:
        client = redis_state_service.redis_client()
        for bucket_key in bucket_keys:
            client.eval(
                script,
                2,
                f"{bucket_key}:attempts",
                f"{bucket_key}:lock",
                max(window, 1),
                f"{now}:{secrets.token_hex(4)}",
                max(max_attempts, 1),
                max(lockout, 1),
            )
    except Exception as exc:
        current_app.logger.warning("Redis login limiter write failed; local fallback remains active: %s", exc)


def _register_local_failure(
    *,
    bucket_keys: tuple[str, str],
    now: float,
    window: int,
    max_attempts: int,
    lockout: int,
) -> None:
    with _state_lock:
        _prune_state(now=now, window=window, lockout=lockout)
        for bucket_key in bucket_keys:
            attempts = _attempts[bucket_key]
            attempts.append(now)
            attempts[:] = [value for value in attempts if value >= now - window]
            if len(attempts) >= max_attempts:
                _lockouts[bucket_key] = now + lockout
                _attempts[bucket_key] = []


def register_success(*, email: str, remote_addr: str | None) -> None:
    bucket_keys = _bucket_keys(email=email, remote_addr=remote_addr)
    with _state_lock:
        for bucket_key in bucket_keys:
            _attempts.pop(bucket_key, None)
            _lockouts.pop(bucket_key, None)
    if redis_state_service.backend_mode("RATE_LIMIT_BACKEND") == "local":
        return
    try:
        client = redis_state_service.redis_client()
        keys = [key for bucket_key in bucket_keys for key in (f"{bucket_key}:attempts", f"{bucket_key}:lock")]
        if keys:
            client.delete(*keys)
    except Exception as exc:
        current_app.logger.warning("Redis login limiter reset failed: %s", exc)


def _enabled() -> bool:
    return bool(current_app.config.get("LOGIN_RATE_LIMIT_ENABLED", True))


def _bucket_keys(*, email: str, remote_addr: str | None) -> tuple[str, str]:
    normalized_email = str(email or "").strip().lower() or "anonymous"
    normalized_ip = str(remote_addr or "").strip() or "unknown"
    return (
        redis_state_service.private_key("login-ip", normalized_ip),
        redis_state_service.private_key("login-email", normalized_email),
    )


def _prune_state(*, now: float, window: int, lockout: int) -> None:
    oldest_attempt = now - max(window, 1)
    for bucket_key, attempts in list(_attempts.items()):
        kept = [value for value in attempts if value >= oldest_attempt]
        if kept:
            _attempts[bucket_key] = kept
        else:
            _attempts.pop(bucket_key, None)

    oldest_lockout = now - max(lockout, 1)
    for bucket_key, unlock_at in list(_lockouts.items()):
        if unlock_at <= now or unlock_at < oldest_lockout:
            _lockouts.pop(bucket_key, None)
