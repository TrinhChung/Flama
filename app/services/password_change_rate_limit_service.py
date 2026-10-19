"""Brute-force protection and rate limiting for password change operations."""

from __future__ import annotations

from flask import current_app

from app.services import redis_state_service
from app.services.rate_limiter_engine import LockoutRateLimiter

_engine = LockoutRateLimiter(name="PasswordChange")


def reset_state() -> None:
    """Clear in-memory rate limiting state (used in testing)."""
    _engine.reset_state()


def get_lockout_remaining(*, user_id: int | str, remote_addr: str | None) -> int:
    """Return remaining lockout duration in seconds if rate limit is active, 0 otherwise."""
    if not _enabled():
        return 0

    window = int(current_app.config.get("PASSWORD_CHANGE_RATE_LIMIT_WINDOW_SECONDS", 60))
    lockout = int(current_app.config.get("PASSWORD_CHANGE_RATE_LIMIT_LOCKOUT_SECONDS", 300))
    bucket_keys = _bucket_keys(user_id=user_id, remote_addr=remote_addr)
    return _engine.get_lockout_remaining(
        bucket_keys=bucket_keys,
        window=window,
        lockout=lockout,
    )


def register_failure(*, user_id: int | str, remote_addr: str | None) -> None:
    """Record a failed password change attempt."""
    if not _enabled():
        return

    window = int(current_app.config.get("PASSWORD_CHANGE_RATE_LIMIT_WINDOW_SECONDS", 60))
    max_attempts = int(current_app.config.get("PASSWORD_CHANGE_RATE_LIMIT_MAX_ATTEMPTS", 5))
    lockout = int(current_app.config.get("PASSWORD_CHANGE_RATE_LIMIT_LOCKOUT_SECONDS", 300))
    bucket_keys = _bucket_keys(user_id=user_id, remote_addr=remote_addr)
    _engine.register_failure(
        bucket_keys=bucket_keys,
        window=window,
        max_attempts=max_attempts,
        lockout=lockout,
    )


def register_success(*, user_id: int | str, remote_addr: str | None) -> None:
    """Reset rate limiting counters upon successful password change."""
    bucket_keys = _bucket_keys(user_id=user_id, remote_addr=remote_addr)
    _engine.register_success(bucket_keys=bucket_keys)


def _enabled() -> bool:
    return bool(current_app.config.get("PASSWORD_CHANGE_RATE_LIMIT_ENABLED", True))


def _bucket_keys(*, user_id: int | str, remote_addr: str | None) -> tuple[str, str]:
    normalized_user = str(user_id or "").strip() or "anonymous"
    normalized_ip = str(remote_addr or "").strip() or "unknown"
    return (
        redis_state_service.private_key("password-change-ip", normalized_ip),
        redis_state_service.private_key("password-change-user", normalized_user),
    )
