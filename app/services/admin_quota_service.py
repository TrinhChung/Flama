"""Admin configuration of usage quotas: policies, per-user overrides and usage."""

from __future__ import annotations

from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any

from sqlalchemy import func

from app.repositories import quota_repository
from app.services import admin_service, quota_service
from app.utils.permissions import is_admin_user
from models import db
from models.quota import QUOTA_KINDS, QUOTA_PERIODS, UNLIMITED, QuotaPolicy, UserQuotaOverride
from models.user import User
from models.user_role import UserRole

MAX_LIMIT_VALUE = 1_000_000_000_000
MAX_NOTE_LENGTH = 255
UNITS = {quota_service.KIND_API: "requests", quota_service.KIND_MCP: "requests", quota_service.KIND_MEDIA: "MB"}


class AdminQuotaServiceError(RuntimeError):
    def __init__(self, code: str, message: str, *, status: int = 400, field: str | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field


def _validation(message: str, field: str) -> AdminQuotaServiceError:
    return AdminQuotaServiceError("VALIDATION_ERROR", message, field=field)


def _require_kind(kind: str) -> str:
    if kind not in QUOTA_KINDS:
        raise AdminQuotaServiceError("NOT_FOUND", "Loại quota không tồn tại.", status=404)
    return kind


def _require_period(value: Any, *, field: str = "period", allow_none: bool = False) -> str | None:
    if value is None and allow_none:
        return None
    period = str(value or "").strip().lower()
    if period not in QUOTA_PERIODS:
        raise _validation("Chu kỳ phải là day, month hoặc year.", field)
    return period


def _require_limit(value: Any, *, field: str) -> int:
    if isinstance(value, bool):
        raise _validation("Hạn mức phải là số nguyên.", field)
    try:
        limit = int(value)
    except (TypeError, ValueError) as exc:
        raise _validation("Hạn mức phải là số nguyên.", field) from exc
    if isinstance(value, float) and value != limit:
        raise _validation("Hạn mức phải là số nguyên.", field)
    if limit < UNLIMITED or limit > MAX_LIMIT_VALUE:
        raise _validation("Hạn mức phải từ -1 (không giới hạn) trở lên.", field)
    return limit


def _quota_roles() -> list[UserRole]:
    # Admins are never limited, so their role has no configurable quota.
    return [
        role
        for role in UserRole.query.order_by(UserRole.position.asc(), UserRole.id.asc()).all()
        if not role.is_admin
    ]


def _local_tz():
    return quota_service.get_configured_timezone()


def _expires_on(expires_at: datetime | None) -> str | None:
    """Last valid local day of an override stored as the following UTC midnight."""
    if expires_at is None:
        return None
    local = expires_at.replace(tzinfo=timezone.utc).astimezone(_local_tz())
    return (local - timedelta(microseconds=1)).date().isoformat()


def _parse_expires_on(value: Any) -> datetime | None:
    """Turn an inclusive local date into the UTC instant the override stops applying."""
    if value is None or value == "":
        return None
    try:
        last_day = date.fromisoformat(str(value).strip()[:10])
    except ValueError as exc:
        raise _validation("Ngày hết hạn phải có dạng YYYY-MM-DD.", "expires_on") from exc
    tz = _local_tz()
    if last_day < datetime.now(timezone.utc).astimezone(tz).date():
        raise _validation("Ngày hết hạn không được ở quá khứ.", "expires_on")
    stop = datetime.combine(last_day + timedelta(days=1), dt_time.min, tzinfo=tz)
    return stop.astimezone(timezone.utc).replace(tzinfo=None)


def _serialize_user(user: User | None, user_id: int) -> dict[str, Any]:
    if user is None:
        return {"id": int(user_id), "username": f"#{user_id}", "missing": True}
    return {
        "id": int(user.id),
        "username": str(user.username or ""),
        "display_name": str(user.display_name or ""),
        "account_name": admin_service.resolve_account_name(user),
        "email": str(user.email or ""),
        "role_code": quota_service.role_code(user),
        "role_name": user.role.name if user.role else None,
        "is_admin": is_admin_user(user),
        "is_disabled": bool(user.is_disabled),
        "avatar_url": user.avatar_url,
    }


def _serialize_policy(policy: quota_service.PolicySnapshot, row: QuotaPolicy | None) -> dict[str, Any]:
    return {
        "kind": policy.kind,
        "unit": UNITS[policy.kind],
        "enforce": policy.enforce,
        "period": policy.period,
        "role_limits": dict(policy.role_limits),
        "is_default": row is None,
        "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
        "updated_by_user_id": row.updated_by_user_id if row is not None else None,
    }


def _serialize_override(row: UserQuotaOverride, *, policy_period: str) -> dict[str, Any]:
    now = quota_service.utcnow_naive()
    return {
        "user_id": int(row.user_id),
        "kind": row.quota_kind,
        "unit": UNITS.get(row.quota_kind, "requests"),
        "limit_value": int(row.limit_value),
        "period": row.period,
        "effective_period": row.period or policy_period,
        "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        "expires_on": _expires_on(row.expires_at),
        "is_active": row.expires_at is None or row.expires_at > now,
        "note": row.note or "",
        "updated_by_user_id": row.updated_by_user_id,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def _usage_amount(kind: str, units: int) -> int | float:
    """Counters store bytes for media; the screen shows MB like the limits."""
    if kind == quota_service.KIND_MEDIA:
        return round(units / quota_service.MEDIA_UNIT_BYTES, 2)
    return int(units)


def _effective_payload(user: User, kind: str) -> dict[str, Any]:
    limit = quota_service.resolve_limit(user, kind)
    configured = limit.limit
    if configured is not None and kind == quota_service.KIND_MEDIA:
        configured = configured // quota_service.MEDIA_UNIT_BYTES
    return {
        "limit_value": UNLIMITED if configured is None else int(configured),
        "period": limit.period,
        "enforce": limit.enforce,
        "source": limit.source,
        "expires_on": _expires_on(limit.expires_at),
    }


def _ranking_rows(kind: str, rows: list[tuple[int, int]], users: dict[int, User]) -> list[dict[str, Any]]:
    result = []
    for user_id, units in rows:
        user = users.get(user_id)
        item = {"user": _serialize_user(user, user_id), "used": _usage_amount(kind, units)}
        if user is not None:
            item["effective"] = _effective_payload(user, kind)
        result.append(item)
    return result


def get_overview(*, period: str = "day", top_limit: int = 10) -> dict[str, Any]:
    stats_period = _require_period(period)
    policies = quota_service.get_policies()
    rows = {row.quota_kind: row for row in quota_repository.list_policies()}

    usage_raw = {kind: quota_service.get_usage_overview(kind, stats_period, limit=top_limit) for kind in QUOTA_KINDS}
    overrides = quota_repository.list_all_overrides()

    user_ids = {row.user_id for row in overrides}
    for data in usage_raw.values():
        user_ids.update(uid for uid, _ in data["top"])
        user_ids.update(uid for uid, _ in data["over"])
    users = quota_repository.get_users_by_ids(sorted(user_ids))
    # Every override is already loaded, so ranking rows need no per-user lookup.
    quota_service.prime_user_overrides(sorted(user_ids), overrides)

    override_usage = quota_service.get_users_usage(sorted({row.user_id for row in overrides}))
    override_items = []
    for row in overrides:
        payload = _serialize_override(row, policy_period=policies[row.quota_kind].period)
        used_units = override_usage.get(row.user_id, {}).get(row.quota_kind, {}).get(payload["effective_period"], 0)
        payload["used"] = _usage_amount(row.quota_kind, used_units)
        payload["user"] = _serialize_user(users.get(row.user_id), row.user_id)
        override_items.append(payload)

    role_counts = dict(
        db.session.query(User.role_id, func.count(User.id)).filter(User.role_id.isnot(None)).group_by(User.role_id).all()
    )
    roles = [
        {"id": int(role.id), "code": role.code, "name": role.name, "user_count": int(role_counts.get(role.id, 0))}
        for role in _quota_roles()
    ]

    usage = {}
    for kind, data in usage_raw.items():
        usage[kind] = {
            "period": data["period"],
            "period_token": data["period_token"],
            "reset_epoch": data["reset_epoch"],
            "total": _usage_amount(kind, data["total"]),
            "top": _ranking_rows(kind, data["top"], users),
            "over": _ranking_rows(kind, data["over"], users),
        }

    return {
        "settings": {
            "metering_enabled": quota_service.metering_enabled(),
            "backend": "redis" if quota_service.uses_redis() else "local",
            "timezone": str(_local_tz()),
            "cache_ttl_seconds": quota_service.cache_ttl_seconds(),
            "stats_period": stats_period,
        },
        "roles": roles,
        "policies": [_serialize_policy(policies[kind], rows.get(kind)) for kind in QUOTA_KINDS],
        "usage": usage,
        "overrides": override_items,
    }


def update_policy(*, kind: str, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
    _require_kind(kind)
    row = quota_repository.get_policy(kind)
    current = quota_service.snapshot_policy(row) if row is not None else quota_service.default_policy(kind)

    enforce = current.enforce
    if "enforce" in payload:
        if not isinstance(payload["enforce"], bool):
            raise _validation("enforce phải là true hoặc false.", "enforce")
        enforce = payload["enforce"]
    period = _require_period(payload["period"]) if "period" in payload else current.period

    role_limits = dict(current.role_limits)
    if "role_limits" in payload:
        raw_limits = payload["role_limits"]
        if not isinstance(raw_limits, dict):
            raise _validation("role_limits phải là object role_code -> hạn mức.", "role_limits")
        allowed_codes = {role.code for role in _quota_roles()}
        for code, raw in raw_limits.items():
            if code not in allowed_codes:
                raise _validation(f"Vai trò '{code}' không cấu hình được quota.", "role_limits")
            role_limits[code] = _require_limit(raw, field=f"role_limits.{code}")

    if row is None:
        row = quota_repository.add_policy(QuotaPolicy(quota_kind=kind))
    row.enforce = enforce
    row.period = period
    row.role_limits = role_limits
    row.updated_by_user_id = int(actor_user_id)
    row.updated_at = datetime.utcnow()
    db.session.commit()
    quota_service.invalidate_cache()
    return _serialize_policy(quota_service.snapshot_policy(row), row)


def _require_user(user_id: int) -> User:
    user = db.session.get(User, int(user_id))
    if user is None:
        raise AdminQuotaServiceError("NOT_FOUND", "Người dùng không tồn tại.", status=404)
    return user


def get_user_detail(user_id: int) -> dict[str, Any]:
    user = _require_user(user_id)
    policies = quota_service.get_policies()
    overrides = {row.quota_kind: row for row in quota_repository.list_overrides_for_user(user.id)}
    usage = quota_service.get_users_usage([int(user.id)]).get(int(user.id), {})
    quotas = []
    for kind in QUOTA_KINDS:
        row = overrides.get(kind)
        quotas.append(
            {
                "kind": kind,
                "unit": UNITS[kind],
                "effective": _effective_payload(user, kind),
                "role_limit": policies[kind].role_limits.get(quota_service.role_code(user), UNLIMITED),
                "override": _serialize_override(row, policy_period=policies[kind].period) if row else None,
                "usage": {p: _usage_amount(kind, usage.get(kind, {}).get(p, 0)) for p in QUOTA_PERIODS},
            }
        )
    return {"user": _serialize_user(user, user.id), "quotas": quotas}


def upsert_override(*, user_id: int, kind: str, payload: dict[str, Any], actor_user_id: int) -> dict[str, Any]:
    _require_kind(kind)
    user = _require_user(user_id)
    if "limit_value" not in payload:
        raise _validation("limit_value là bắt buộc (-1 là không giới hạn).", "limit_value")
    limit_value = _require_limit(payload.get("limit_value"), field="limit_value")
    period = _require_period(payload.get("period") or None, allow_none=True)
    expires_at = _parse_expires_on(payload.get("expires_on"))
    note = str(payload.get("note") or "").strip()
    if len(note) > MAX_NOTE_LENGTH:
        raise _validation(f"Ghi chú tối đa {MAX_NOTE_LENGTH} ký tự.", "note")

    row = quota_repository.get_override(user_id=user.id, quota_kind=kind)
    if row is None:
        row = quota_repository.add_override(UserQuotaOverride(user_id=int(user.id), quota_kind=kind))
    row.limit_value = limit_value
    row.period = period
    row.expires_at = expires_at
    row.note = note or None
    row.updated_by_user_id = int(actor_user_id)
    row.updated_at = datetime.utcnow()
    db.session.commit()
    quota_service.invalidate_cache(user_id=user.id)
    return get_user_detail(user.id)


def delete_override(*, user_id: int, kind: str) -> dict[str, Any]:
    _require_kind(kind)
    user = _require_user(user_id)
    row = quota_repository.get_override(user_id=user.id, quota_kind=kind)
    if row is not None:
        quota_repository.delete_override(row)
        db.session.commit()
        quota_service.invalidate_cache(user_id=user.id)
    return get_user_detail(user.id)


def search_users(*, query_text: str, limit: int = 10) -> list[dict[str, Any]]:
    term = query_text.strip()
    if not term:
        return []
    users = quota_repository.search_users(query_text=term, limit=min(max(1, limit), 20))
    return [_serialize_user(user, user.id) for user in users]
