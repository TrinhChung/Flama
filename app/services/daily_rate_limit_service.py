"""Daily request rate limiting service based on user roles (Regular, Creator, Admin).

Enforces configurable daily quotas:
- Regular users: 300 requests / day
- Creator users: 2,000 requests / day
- Admin users: Unlimited (bypassed)
"""

from __future__ import annotations

from datetime import datetime, time as dt_time, timedelta, timezone
import logging
import threading
import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

from app.services import redis_state_service
from app.utils.permissions import is_admin_user, is_creator_user

logger = logging.getLogger(__name__)

_LOCAL_LOCK = threading.Lock()
_LOCAL_DAILY_COUNTS: dict[str, int] = {}
_LOCAL_LAST_CLEANUP: float = 0.0

UTC = timezone.utc
FALLBACK_OFFSET_HOURS = 7  # Asia/Ho_Chi_Minh default fallback (+07:00)


def _config_int(name: str, default: int, *, minimum: int = 0) -> int:
    try:
        raw = current_app.config.get(name, default)
        return max(int(raw), minimum)
    except (RuntimeError, TypeError, ValueError):
        return max(default, minimum)


def _config_bool(name: str, default: bool = True) -> bool:
    try:
        return bool(current_app.config.get(name, default))
    except RuntimeError:
        return default


def is_daily_rate_limit_enabled() -> bool:
    """Return whether daily role-based rate limiting is enabled."""
    return _config_bool("RATE_LIMIT_DAILY_ENABLED", default=True)


def get_regular_daily_max() -> int:
    """Return daily request quota for regular users (default: 300)."""
    return _config_int("RATE_LIMIT_REGULAR_DAILY_MAX", default=300, minimum=1)


def get_creator_daily_max() -> int:
    """Return daily request quota for creator users (default: 2000)."""
    return _config_int("RATE_LIMIT_CREATOR_DAILY_MAX", default=2000, minimum=1)


def get_enterprise_daily_max() -> int:
    """Return daily request quota for enterprise users (default: 10000)."""
    return _config_int("RATE_LIMIT_ENTERPRISE_DAILY_MAX", default=10000, minimum=1)


def get_configured_timezone() -> timezone | ZoneInfo:
    """Resolve configured timezone for daily bucket boundary."""
    try:
        tz_name = str(current_app.config.get("RATE_LIMIT_DAILY_TIMEZONE") or "").strip()
    except RuntimeError:
        tz_name = ""

    if not tz_name:
        tz_name = "Asia/Ho_Chi_Minh"

    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        if tz_name.upper() in {"UTC", "GMT"}:
            return UTC
        return timezone(timedelta(hours=FALLBACK_OFFSET_HOURS))


def get_current_day_bucket() -> tuple[str, int]:
    """
    Get current date string (YYYY-MM-DD) and next midnight epoch timestamp in UTC.
    
    Returns:
        (date_str, reset_epoch_timestamp)
    """
    tz = get_configured_timezone()
    now = datetime.now(tz)
    date_str = now.strftime("%Y-%m-%d")
    
    # Calculate midnight of the next day
    tomorrow = now.date() + timedelta(days=1)
    next_midnight = datetime.combine(tomorrow, dt_time.min, tzinfo=tz)
    reset_epoch = int(next_midnight.astimezone(UTC).timestamp())
    
    return date_str, reset_epoch


def resolve_user_daily_quota(user: Any) -> int | None:
    """
    Resolve the daily request quota for a given user.
    
    Returns:
        int: Maximum allowed requests per day (e.g. 300 or 2000).
        None: Unlimited quota (Admin or rate limiting disabled).
    """
    if not is_daily_rate_limit_enabled():
        return None

    if user is None:
        return None

    if is_admin_user(user):
        return None

    if is_creator_user(user):
        return get_creator_daily_max()

    role = getattr(user, "role", None)
    role_code = str(getattr(role, "code", "") or "").strip().lower()

    if role_code == "creator":
        return get_creator_daily_max()
    elif role_code == "enterprise":
        return get_enterprise_daily_max()
    elif role_code == "admin":
        return None
    else:
        # Default regular user
        return get_regular_daily_max()


def _cleanup_stale_local_buckets(current_date_str: str) -> None:
    global _LOCAL_LAST_CLEANUP
    now_mono = time.monotonic()
    if now_mono - _LOCAL_LAST_CLEANUP < 300.0:  # cleanup at most once per 5 minutes
        return
    _LOCAL_LAST_CLEANUP = now_mono
    stale_keys = [
        key for key in _LOCAL_DAILY_COUNTS.keys()
        if not key.endswith(f":{current_date_str}")
    ]
    for key in stale_keys:
        _LOCAL_DAILY_COUNTS.pop(key, None)


def _consume_local(bucket_key: str, date_str: str) -> int:
    with _LOCAL_LOCK:
        _cleanup_stale_local_buckets(date_str)
        count = _LOCAL_DAILY_COUNTS.get(bucket_key, 0) + 1
        _LOCAL_DAILY_COUNTS[bucket_key] = count
        return count


def _get_local_usage(bucket_key: str) -> int:
    with _LOCAL_LOCK:
        return _LOCAL_DAILY_COUNTS.get(bucket_key, 0)


def consume_daily_quota(user_id: int, quota: int) -> tuple[bool, int, int, int]:
    """
    Atomically increment and check daily usage for user_id against quota.
    
    Returns:
        (allowed: bool, current_usage: int, remaining: int, reset_epoch: int)
    """
    date_str, reset_epoch = get_current_day_bucket()
    bucket_identity = f"{user_id}:{date_str}"
    
    mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
    
    local_count = _consume_local(bucket_identity, date_str)
    
    if mode == "local":
        allowed = local_count <= quota
        remaining = max(0, quota - local_count)
        return allowed, local_count, remaining, reset_epoch

    redis_count = None
    try:
        client = redis_state_service.redis_client()
        redis_key = redis_state_service.private_key("daily-quota", bucket_identity)
        # Lua script: increment and set expireat on first touch (with 1-hour grace)
        expire_target = reset_epoch + 3600
        count = int(
            client.eval(
                """
                local count = redis.call('INCR', KEYS[1])
                if count == 1 then
                    redis.call('EXPIREAT', KEYS[1], ARGV[1])
                end
                return count
                """,
                1,
                redis_key,
                expire_target,
            )
        )
        redis_count = count
    except Exception as exc:
        logger.warning("Redis daily rate limit failed for user_id=%s: %s", user_id, exc)
        if mode == "redis":
            # Fallback to local count when Redis fails to avoid hard outage
            logger.info("Falling back to local rate limiter for user_id=%s", user_id)
            redis_count = local_count

    effective_count = redis_count if (mode == "redis" and redis_count is not None) else local_count
    allowed = effective_count <= quota
    remaining = max(0, quota - effective_count)
    
    return allowed, effective_count, remaining, reset_epoch


def get_daily_usage(user_id: int, quota: int | None = None) -> tuple[int, int, int]:
    """
    Query current daily usage and remaining quota without incrementing.
    
    Returns:
        (current_usage: int, remaining: int, reset_epoch: int)
    """
    date_str, reset_epoch = get_current_day_bucket()
    bucket_identity = f"{user_id}:{date_str}"
    
    mode = redis_state_service.backend_mode("RATE_LIMIT_BACKEND")
    usage = 0
    
    if mode == "redis":
        try:
            client = redis_state_service.redis_client()
            redis_key = redis_state_service.private_key("daily-quota", bucket_identity)
            val = client.get(redis_key)
            usage = int(val) if val is not None else 0
        except Exception as exc:
            logger.warning("Redis get daily usage failed: %s", exc)
            usage = _get_local_usage(bucket_identity)
    else:
        usage = _get_local_usage(bucket_identity)
        
    remaining = max(0, (quota - usage)) if quota is not None else -1
    return usage, remaining, reset_epoch


def build_rate_limit_headers(quota: int | None, remaining: int, reset_epoch: int) -> dict[str, str]:
    """Build standard X-RateLimit-* response headers."""
    remaining_str = "-1" if quota is None or remaining < 0 else str(max(0, remaining))
    return {
        "X-RateLimit-Limit": str(quota) if quota is not None else "-1",
        "X-RateLimit-Remaining": remaining_str,
        "X-RateLimit-Reset": str(reset_epoch),
    }


def reset_local_rate_limit_state() -> None:
    """Reset in-memory rate limit state (useful in tests)."""
    with _LOCAL_LOCK:
        _LOCAL_DAILY_COUNTS.clear()
