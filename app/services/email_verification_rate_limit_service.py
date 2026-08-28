"""Shared per-IP and per-email throttling for email verification requests."""

from __future__ import annotations

import logging
import math
import threading
import time

from flask import current_app

from app.services import redis_state_service

logger = logging.getLogger(__name__)
_LOCAL_LOCK = threading.Lock()
_LOCAL_EVENTS: dict[str, list[float]] = {}


def reset_state() -> None:
    with _LOCAL_LOCK:
        _LOCAL_EVENTS.clear()


def consume(*, email: str, remote_addr: str | None) -> tuple[bool, int]:
    """Consume one email verification request and return ``(allowed, retry_after_seconds)``.
    
    Default: cooldown window of 60 seconds per request, max 5 requests per 15 minutes.
    """
    cooldown_seconds = max(
        int(current_app.config.get("EMAIL_VERIFICATION_COOLDOWN_SECONDS", 60)),
        1,
    )
    window = max(
        int(current_app.config.get("EMAIL_VERIFICATION_RATE_LIMIT_WINDOW_SECONDS", 900)),
        1,
    )
    maximum = max(
        int(current_app.config.get("EMAIL_VERIFICATION_RATE_LIMIT_MAX_REQUESTS", 5)),
        1,
    )
    now = time.time()
    keys = _bucket_keys(email=email, remote_addr=remote_addr)
    cooldown_keys = _cooldown_keys(email=email)

    # Check 1: 60s cooldown per email
    local_cd_allowed, local_cd_retry = _consume_local(
        keys=cooldown_keys,
        now=now,
        window=cooldown_seconds,
        maximum=1,
    )
    if not local_cd_allowed:
        return False, local_cd_retry

    # Check 2: burst max requests per 15 min
    local_allowed, local_retry = _consume_local(
        keys=keys,
        now=now,
        window=window,
        maximum=maximum,
    )
    if not local_allowed:
        return False, local_retry

    mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
    if mode == "local":
        return True, 0

    try:
        client = redis_state_service.redis_client()
        # Evaluate burst keys
        results = [
            client.eval(
                """
                local count = redis.call('INCR', KEYS[1])
                if count == 1 then
                  redis.call('EXPIRE', KEYS[1], ARGV[1])
                end
                return {count, redis.call('TTL', KEYS[1])}
                """,
                1,
                key,
                window,
            )
            for key in keys
        ]
        redis_allowed = all(int(result[0]) <= maximum for result in results)
        redis_retry = max(
            (max(int(result[1]), 1) for result in results if int(result[0]) > maximum),
            default=0,
        )
        return (redis_allowed, redis_retry) if mode == "redis" else (True, 0)
    except Exception as exc:
        logger.warning("Redis email verification limiter failed; using local fallback: %s", exc)
        return True, 0


def _bucket_keys(*, email: str, remote_addr: str | None) -> tuple[str, str]:
    normalized_email = str(email or "").strip().lower() or "anonymous"
    normalized_ip = str(remote_addr or "").strip() or "unknown"
    return (
        redis_state_service.private_key("email-verification-email", normalized_email),
        redis_state_service.private_key("email-verification-ip", normalized_ip),
    )


def _cooldown_keys(*, email: str) -> tuple[str]:
    normalized_email = str(email or "").strip().lower() or "anonymous"
    return (redis_state_service.private_key("email-verification-cooldown", normalized_email),)


def _consume_local(
    *, keys: tuple[str, ...], now: float, window: int, maximum: int
) -> tuple[bool, int]:
    retry_after = 0
    allowed = True
    cutoff = now - window
    with _LOCAL_LOCK:
        for key in list(_LOCAL_EVENTS):
            kept = [event for event in _LOCAL_EVENTS[key] if event > cutoff]
            if kept:
                _LOCAL_EVENTS[key] = kept
            else:
                _LOCAL_EVENTS.pop(key, None)
        for key in keys:
            events = _LOCAL_EVENTS.setdefault(key, [])
            events.append(now)
            if len(events) > maximum:
                allowed = False
                retry_after = max(retry_after, math.ceil(events[0] + window - now))
    return allowed, max(retry_after, 0)
