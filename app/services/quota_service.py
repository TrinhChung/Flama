"""Usage quotas for Flama Connect API calls, MCP tool calls and media uploads.

Web app requests (study, browse, dashboard, settings...) are never metered.

Hot path: one Redis EVAL per metered request checks the effective limit and
increments the day, month and year counters together, so switching a period
later keeps its history. Limits come from ``quota_policies`` and
``user_quota_overrides`` through a short per-process cache, so the database is
read at most once per user per cache TTL in each worker.

A policy in monitor mode (``enforce = False``) never blocks; requests above the
configured limit are recorded in an "over" ranking instead, which shows who
would have been blocked before an admin turns enforcement on.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time as dt_time, timedelta, timezone
import logging
import threading
import time
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from flask import current_app

from app.repositories import quota_repository
from app.services import redis_state_service
from app.utils.permissions import is_admin_user
from models import db
from models.quota import QUOTA_KINDS, QUOTA_PERIODS, UNLIMITED
from models.user import User

logger = logging.getLogger(__name__)

KIND_API = "api"
KIND_MCP = "mcp"
KIND_MEDIA = "media"
MEDIA_UNIT_BYTES = 1024 * 1024
HISTORY_DAYS = 400
DEFAULT_CACHE_TTL_SECONDS = 30
DEFAULT_ROLE = "regular"

# Used only when a policy row is missing (fresh test schemas); the migration
# seeds the same values. API/MCP count requests, media counts MB.
DEFAULT_ROLE_LIMITS: dict[str, dict[str, int]] = {
    KIND_API: {"regular": 300, "creator": 2000, "enterprise": 10000},
    KIND_MCP: {"regular": 300, "creator": 2000, "enterprise": 10000},
    KIND_MEDIA: {"regular": 100, "creator": 500, "enterprise": 2000},
}

_PERIOD_CODES = {"day": "d", "month": "m", "year": "y"}
_PERIOD_LABELS = {"day": "ngày", "month": "tháng", "year": "năm"}
_KIND_LABELS = {KIND_API: "API", KIND_MCP: "MCP", KIND_MEDIA: "upload media"}

# KEYS[1..3] user counters, [4..6] totals, [7..9] usage ranking, [10..12]
# over-limit ranking, each ordered day, month, year.
# ARGV: amount, limit (-1 unlimited), period index (1..3), enforce (1/0),
# member, user counter EXPIREAT x3, history EXPIREAT x3.
_CONSUME_LUA = """
local amount = tonumber(ARGV[1])
local limit = tonumber(ARGV[2])
local idx = tonumber(ARGV[3])
local current = tonumber(redis.call('GET', KEYS[idx]) or '0')
if limit >= 0 and current + amount > limit then
  for i = 1, 3 do
    redis.call('ZINCRBY', KEYS[9 + i], amount, ARGV[5])
    redis.call('EXPIREAT', KEYS[9 + i], ARGV[8 + i])
  end
  if ARGV[4] == '1' then
    return {0, current}
  end
end
local used = current
for i = 1, 3 do
  local value = redis.call('INCRBY', KEYS[i], amount)
  if value == amount then
    redis.call('EXPIREAT', KEYS[i], ARGV[5 + i])
  end
  if i == idx then
    used = value
  end
  redis.call('INCRBY', KEYS[3 + i], amount)
  redis.call('EXPIREAT', KEYS[3 + i], ARGV[8 + i])
  redis.call('ZINCRBY', KEYS[6 + i], amount, ARGV[5])
  redis.call('EXPIREAT', KEYS[6 + i], ARGV[8 + i])
end
return {1, used}
"""


@dataclass(frozen=True)
class PolicySnapshot:
    kind: str
    enforce: bool
    period: str
    role_limits: dict[str, int]


@dataclass(frozen=True)
class OverrideSnapshot:
    kind: str
    limit_value: int
    period: str | None
    expires_at: datetime | None

    def is_active(self, now: datetime) -> bool:
        return self.expires_at is None or self.expires_at > now


@dataclass(frozen=True)
class EffectiveLimit:
    kind: str
    # Requests for API/MCP, bytes for media; None means unlimited.
    limit: int | None
    period: str
    enforce: bool
    source: str  # "admin", "override" or "role"
    expires_at: datetime | None = None


@dataclass(frozen=True)
class PeriodWindow:
    period: str
    token: str
    start: datetime
    end: datetime

    @property
    def reset_epoch(self) -> int:
        return int(self.end.timestamp())


@dataclass(frozen=True)
class QuotaDecision:
    allowed: bool
    kind: str
    used: int
    limit: int | None
    period: str
    enforce: bool
    reset_epoch: int

    @property
    def message(self) -> str:
        return (
            f"Bạn đã dùng hết hạn mức {_KIND_LABELS.get(self.kind, self.kind)} "
            f"theo {_PERIOD_LABELS.get(self.period, self.period)}. "
            "Hạn mức sẽ được làm mới ở chu kỳ tiếp theo."
        )


class _QuotaState:
    """Per-app, per-process caches and the local counter backend."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.policies: tuple[float, dict[str, PolicySnapshot]] | None = None
        self.overrides: dict[int, tuple[float, dict[str, OverrideSnapshot]]] = {}
        self.counters: dict[str, tuple[int, int]] = {}
        self.rankings: dict[str, tuple[dict[str, int], int]] = {}
        self.last_cleanup = 0.0
        self.script: Any = None
        self.script_client: Any = None


def _state() -> _QuotaState:
    state = current_app.extensions.get("quota_state")
    if state is None:
        state = current_app.extensions.setdefault("quota_state", _QuotaState())
    return state


def metering_enabled() -> bool:
    return bool(current_app.config.get("RATE_LIMIT_DAILY_ENABLED", True))


def cache_ttl_seconds() -> float:
    try:
        return max(float(current_app.config.get("QUOTA_CACHE_TTL_SECONDS", DEFAULT_CACHE_TTL_SECONDS)), 0.0)
    except (TypeError, ValueError):
        return float(DEFAULT_CACHE_TTL_SECONDS)


def utcnow_naive() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def reset_local_state() -> None:
    """Drop caches and local counters of the current app (tests, admin saves)."""
    current_app.extensions["quota_state"] = _QuotaState()


def invalidate_cache(*, user_id: int | None = None) -> None:
    """Make this worker re-read limits now; other workers follow within the TTL."""
    state = _state()
    with state.lock:
        if user_id is None:
            state.policies = None
            state.overrides.clear()
        else:
            state.overrides.pop(int(user_id), None)


# --------------------------------------------------------------------------
# Periods
# --------------------------------------------------------------------------


def get_configured_timezone() -> timezone | ZoneInfo:
    tz_name = str(current_app.config.get("RATE_LIMIT_DAILY_TIMEZONE") or "").strip() or "Asia/Ho_Chi_Minh"
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, ValueError):
        return timezone(timedelta(hours=7))


def _local_midnight(day: date, tz) -> datetime:
    return datetime.combine(day, dt_time.min, tzinfo=tz)


def period_windows(now: datetime | None = None) -> dict[str, PeriodWindow]:
    tz = get_configured_timezone()
    local_now = (now or datetime.now(timezone.utc)).astimezone(tz)
    today = local_now.date()
    month_start = today.replace(day=1)
    next_month = (month_start + timedelta(days=32)).replace(day=1)
    year_start = today.replace(month=1, day=1)
    return {
        "day": PeriodWindow(
            "day", today.isoformat(), _local_midnight(today, tz), _local_midnight(today + timedelta(days=1), tz)
        ),
        "month": PeriodWindow(
            "month", month_start.strftime("%Y-%m"), _local_midnight(month_start, tz), _local_midnight(next_month, tz)
        ),
        "year": PeriodWindow(
            "year",
            str(year_start.year),
            _local_midnight(year_start, tz),
            _local_midnight(year_start.replace(year=year_start.year + 1), tz),
        ),
    }


# --------------------------------------------------------------------------
# Limits
# --------------------------------------------------------------------------


def snapshot_policy(row) -> PolicySnapshot:
    limits: dict[str, int] = {}
    for code, raw in dict(row.role_limits or {}).items():
        try:
            limits[str(code)] = int(raw)
        except (TypeError, ValueError):
            continue
    period = row.period if row.period in QUOTA_PERIODS else "day"
    return PolicySnapshot(row.quota_kind, bool(row.enforce), period, limits)


def default_policy(kind: str) -> PolicySnapshot:
    return PolicySnapshot(kind, False, "day", dict(DEFAULT_ROLE_LIMITS.get(kind, {})))


def get_policies() -> dict[str, PolicySnapshot]:
    state = _state()
    now = time.monotonic()
    with state.lock:
        cached = state.policies
        if cached is not None and now - cached[0] < cache_ttl_seconds():
            return cached[1]
    loaded = {kind: default_policy(kind) for kind in QUOTA_KINDS}
    for row in quota_repository.list_policies():
        if row.quota_kind in loaded:
            loaded[row.quota_kind] = snapshot_policy(row)
    with state.lock:
        state.policies = (now, loaded)
    return loaded


def _snapshot_override(row) -> OverrideSnapshot:
    return OverrideSnapshot(
        row.quota_kind,
        int(row.limit_value),
        row.period if row.period in QUOTA_PERIODS else None,
        row.expires_at,
    )


def prime_user_overrides(user_ids: list[int], rows: list[Any]) -> None:
    """Cache overrides for many users from rows already loaded (users without rows get none)."""
    loaded: dict[int, dict[str, OverrideSnapshot]] = {int(uid): {} for uid in user_ids}
    for row in rows:
        if int(row.user_id) in loaded:
            loaded[int(row.user_id)][row.quota_kind] = _snapshot_override(row)
    now = time.monotonic()
    state = _state()
    with state.lock:
        for uid, overrides in loaded.items():
            state.overrides[uid] = (now, overrides)


def get_user_overrides(user_id: int) -> dict[str, OverrideSnapshot]:
    state = _state()
    now = time.monotonic()
    key = int(user_id)
    with state.lock:
        cached = state.overrides.get(key)
        if cached is not None and now - cached[0] < cache_ttl_seconds():
            return cached[1]
    loaded = {row.quota_kind: _snapshot_override(row) for row in quota_repository.list_overrides_for_user(key)}
    with state.lock:
        if len(state.overrides) > 10_000:
            state.overrides.clear()
        state.overrides[key] = (now, loaded)
    return loaded


def role_code(user: Any) -> str:
    role = getattr(user, "role", None)
    return str(getattr(role, "code", "") or "").strip().lower() or DEFAULT_ROLE


def to_units(kind: str, limit_value: int | None) -> int | None:
    """Convert a configured limit (MB for media) into counted units."""
    if limit_value is None or int(limit_value) < 0:
        return None
    return int(limit_value) * MEDIA_UNIT_BYTES if kind == KIND_MEDIA else int(limit_value)


def resolve_limit(user: Any, kind: str, *, now: datetime | None = None) -> EffectiveLimit:
    policy = get_policies()[kind]
    if is_admin_user(user):
        return EffectiveLimit(kind, None, policy.period, False, "admin")
    override = get_user_overrides(int(user.id)).get(kind)
    if override is not None and override.is_active(now or utcnow_naive()):
        return EffectiveLimit(
            kind,
            to_units(kind, override.limit_value),
            override.period or policy.period,
            policy.enforce,
            "override",
            override.expires_at,
        )
    raw = policy.role_limits.get(role_code(user), UNLIMITED)
    return EffectiveLimit(kind, to_units(kind, raw), policy.period, policy.enforce, "role")


# --------------------------------------------------------------------------
# Counters
# --------------------------------------------------------------------------


def _key(*parts: object) -> str:
    prefix = str(current_app.config.get("RATE_LIMIT_KEY_PREFIX", "flama:v1")).strip(":")
    return ":".join([prefix, "quota", *(str(part) for part in parts)])


def _user_key(kind: str, user_id: int, window: PeriodWindow) -> str:
    return _key(kind, "u", user_id, _PERIOD_CODES[window.period], window.token)


def _history_key(kind: str, scope: str, window: PeriodWindow) -> str:
    return _key(kind, scope, _PERIOD_CODES[window.period], window.token)


def _consume_keys(kind: str, user_id: int, windows: dict[str, PeriodWindow]) -> list[str]:
    ordered = [windows[period] for period in QUOTA_PERIODS]
    return (
        [_user_key(kind, user_id, w) for w in ordered]
        + [_history_key(kind, "t", w) for w in ordered]
        + [_history_key(kind, "top", w) for w in ordered]
        + [_history_key(kind, "over", w) for w in ordered]
    )


def _expiries(windows: dict[str, PeriodWindow]) -> tuple[list[int], list[int]]:
    ordered = [windows[period] for period in QUOTA_PERIODS]
    counter_expiry = [w.reset_epoch + 86_400 for w in ordered]
    history_expiry = [w.reset_epoch + HISTORY_DAYS * 86_400 for w in ordered]
    return counter_expiry, history_expiry


def uses_redis() -> bool:
    return redis_state_service.backend_mode("RATE_LIMIT_BACKEND") == "redis"


def _redis_script(state: _QuotaState):
    client = redis_state_service.redis_client()
    with state.lock:
        if state.script is None or state.script_client is not client:
            state.script = client.register_script(_CONSUME_LUA)
            state.script_client = client
        return state.script


def _cleanup_local(state: _QuotaState, now_epoch: int) -> None:
    if now_epoch - state.last_cleanup < 300:
        return
    state.last_cleanup = now_epoch
    for store in (state.counters, state.rankings):
        for key in [k for k, (_, expiry) in store.items() if expiry <= now_epoch]:
            store.pop(key, None)


def _local_get(state: _QuotaState, key: str, now_epoch: int) -> int:
    value = state.counters.get(key)
    return value[0] if value and value[1] > now_epoch else 0


def _local_incr(state: _QuotaState, key: str, amount: int, expiry: int, now_epoch: int) -> int:
    value = _local_get(state, key, now_epoch) + amount
    previous = state.counters.get(key)
    keep_expiry = previous[1] if previous and previous[1] > now_epoch else expiry
    state.counters[key] = (value, keep_expiry)
    return value


def _local_rank(state: _QuotaState, key: str, member: str, amount: int, expiry: int, now_epoch: int) -> None:
    entry = state.rankings.get(key)
    scores = entry[0] if entry and entry[1] > now_epoch else {}
    scores[member] = scores.get(member, 0) + amount
    state.rankings[key] = (scores, expiry)


def _consume_local(keys: list[str], args: list[int | str]) -> tuple[bool, int]:
    state = _state()
    amount, limit, idx, enforce, member = int(args[0]), int(args[1]), int(args[2]), args[3] == 1, str(args[4])
    counter_expiry, history_expiry = [int(v) for v in args[5:8]], [int(v) for v in args[8:11]]
    now_epoch = int(time.time())
    with state.lock:
        _cleanup_local(state, now_epoch)
        current = _local_get(state, keys[idx - 1], now_epoch)
        if limit >= 0 and current + amount > limit:
            for i in range(3):
                _local_rank(state, keys[9 + i], member, amount, history_expiry[i], now_epoch)
            if enforce:
                return False, current
        used = current
        for i in range(3):
            value = _local_incr(state, keys[i], amount, counter_expiry[i], now_epoch)
            if i == idx - 1:
                used = value
            _local_incr(state, keys[3 + i], amount, history_expiry[i], now_epoch)
            _local_rank(state, keys[6 + i], member, amount, history_expiry[i], now_epoch)
        return True, used


def _consume_counters(
    kind: str, user_id: int, amount: int, limit: EffectiveLimit, windows: dict[str, PeriodWindow]
) -> tuple[bool, int]:
    keys = _consume_keys(kind, user_id, windows)
    counter_expiry, history_expiry = _expiries(windows)
    args: list[int | str] = [
        amount,
        UNLIMITED if limit.limit is None else limit.limit,
        QUOTA_PERIODS.index(limit.period) + 1,
        1 if limit.enforce else 0,
        str(user_id),
        *counter_expiry,
        *history_expiry,
    ]
    if uses_redis():
        try:
            allowed, used = _redis_script(_state())(keys=keys, args=args)
            return bool(int(allowed)), int(used)
        except Exception as exc:  # noqa: BLE001 - quota must never take the request down
            logger.warning("Redis quota counter failed kind=%s user_id=%s: %s", kind, user_id, exc)
    return _consume_local(keys, args)


def consume(user: Any, kind: str, amount: int = 1) -> QuotaDecision:
    """Count ``amount`` units for ``user`` and say whether the request may run."""
    if user is None or not metering_enabled() or int(amount) <= 0:
        return QuotaDecision(True, kind, 0, None, "day", False, 0)
    limit = resolve_limit(user, kind)
    windows = period_windows()
    allowed, used = _consume_counters(kind, int(user.id), int(amount), limit, windows)
    reset_epoch = windows[limit.period].reset_epoch
    return QuotaDecision(allowed, kind, used, limit.limit, limit.period, limit.enforce, reset_epoch)


def consume_media(user_id: int | None, size_bytes: int) -> QuotaDecision:
    """Count bytes a user is about to store; callers raise their own error if blocked."""
    if user_id is None or not metering_enabled():
        return QuotaDecision(True, KIND_MEDIA, 0, None, "day", False, 0)
    return consume(db.session.get(User, int(user_id)), KIND_MEDIA, int(size_bytes))


# --------------------------------------------------------------------------
# Reads for the admin screen
# --------------------------------------------------------------------------


def _read_values(keys: list[str]) -> list[int]:
    if uses_redis():
        try:
            return [int(v or 0) for v in redis_state_service.redis_client().mget(keys)]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis quota read failed: %s", exc)
    state = _state()
    now_epoch = int(time.time())
    with state.lock:
        return [_local_get(state, key, now_epoch) for key in keys]


def _read_ranking(key: str, limit: int) -> list[tuple[int, int]]:
    if uses_redis():
        try:
            rows = redis_state_service.redis_client().zrevrange(key, 0, max(limit - 1, 0), withscores=True)
            return [(int(member), int(score)) for member, score in rows]
        except Exception as exc:  # noqa: BLE001
            logger.warning("Redis quota ranking read failed: %s", exc)
    state = _state()
    now_epoch = int(time.time())
    with state.lock:
        entry = state.rankings.get(key)
        scores = dict(entry[0]) if entry and entry[1] > now_epoch else {}
    ordered = sorted(scores.items(), key=lambda item: (-item[1], int(item[0])))[:limit]
    return [(int(member), int(score)) for member, score in ordered]


def get_users_usage(user_ids: list[int], kinds: tuple[str, ...] = QUOTA_KINDS) -> dict[int, dict[str, dict[str, int]]]:
    """Return ``{user_id: {kind: {period: used}}}`` for the current periods."""
    windows = period_windows()
    plan = [(uid, kind, period) for uid in user_ids for kind in kinds for period in QUOTA_PERIODS]
    values = _read_values([_user_key(kind, uid, windows[period]) for uid, kind, period in plan]) if plan else []
    usage: dict[int, dict[str, dict[str, int]]] = {}
    for (uid, kind, period), value in zip(plan, values):
        usage.setdefault(uid, {}).setdefault(kind, {})[period] = value
    return usage


def get_usage_overview(kind: str, period: str, *, limit: int = 10) -> dict[str, Any]:
    window = period_windows()[period]
    total = _read_values([_history_key(kind, "t", window)])[0]
    return {
        "kind": kind,
        "period": period,
        "period_token": window.token,
        "reset_epoch": window.reset_epoch,
        "total": total,
        "top": _read_ranking(_history_key(kind, "top", window), limit),
        "over": _read_ranking(_history_key(kind, "over", window), limit),
    }
