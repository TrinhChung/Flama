"""Small in-memory login throttling helper."""

from __future__ import annotations

import math
import time
from collections import defaultdict
from threading import Lock

from flask import current_app

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


def _enabled() -> bool:
    return bool(current_app.config.get("LOGIN_RATE_LIMIT_ENABLED", True))


def _bucket_keys(*, email: str, remote_addr: str | None) -> tuple[str, str]:
    normalized_email = str(email or "").strip().lower() or "anonymous"
    normalized_ip = str(remote_addr or "").strip() or "unknown"
    return (f"ip:{normalized_ip}", f"email:{normalized_email}")


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
