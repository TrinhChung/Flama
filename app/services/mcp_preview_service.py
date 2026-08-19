"""Preview token and stale protection management for destructive or impactful MCP actions."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import threading
from typing import Any


DEFAULT_PREVIEW_TTL_SECONDS = 600  # 10 minutes


@dataclass(frozen=True)
class PreviewTokenRecord:
    preview_id: str
    user_id: int
    action: str
    resource_id: str
    resource_version: str
    impact_summary: dict[str, Any]
    created_at: datetime
    expires_at: datetime


_LOCK = threading.Lock()
_PREVIEW_TOKENS: dict[str, PreviewTokenRecord] = {}


def _now_utc() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _cleanup_expired_tokens(now: datetime) -> None:
    expired_keys = [k for k, v in _PREVIEW_TOKENS.items() if v.expires_at <= now]
    for k in expired_keys:
        _PREVIEW_TOKENS.pop(k, None)


def compute_resource_version(*, resource_type: str, resource_id: str | int, **state_params: Any) -> str:
    """Generate a deterministic fingerprint hash of the resource's current state."""
    normalized_state = {
        "resource_type": str(resource_type),
        "resource_id": str(resource_id),
        **{k: (v.isoformat() if isinstance(v, datetime) else v) for k, v in sorted(state_params.items())},
    }
    raw_str = json.dumps(normalized_state, sort_keys=True, default=str)
    return hashlib.sha256(raw_str.encode("utf-8")).hexdigest()[:16]


def create_preview_token(
    *,
    user_id: int,
    action: str,
    resource_id: str | int,
    resource_version: str,
    impact_summary: dict[str, Any],
    ttl_seconds: int = DEFAULT_PREVIEW_TTL_SECONDS,
) -> tuple[str, str]:
    """Create a temporary preview token with TTL and return (preview_id, expires_at_iso)."""
    now = _now_utc()
    preview_id = f"prev_{secrets.token_hex(12)}"
    expires_at = now + timedelta(seconds=ttl_seconds)

    record = PreviewTokenRecord(
        preview_id=preview_id,
        user_id=user_id,
        action=action,
        resource_id=str(resource_id),
        resource_version=resource_version,
        impact_summary=impact_summary,
        created_at=now,
        expires_at=expires_at,
    )

    with _LOCK:
        _cleanup_expired_tokens(now)
        _PREVIEW_TOKENS[preview_id] = record

    return preview_id, expires_at.isoformat()


def validate_preview_token(
    *,
    preview_id: str | None,
    user_id: int,
    action: str,
    resource_id: str | int,
    current_resource_version: str,
) -> tuple[bool, str | None, str | None]:
    """Validate a preview token for a specific action and resource.
    
    Returns (is_valid, error_code, error_message).
    """
    if not preview_id or not str(preview_id).strip():
        return False, "PREVIEW_TOKEN_REQUIRED", "Thao tác này yêu cầu 'preview_id' đã được tạo từ bước preview."

    clean_preview_id = str(preview_id).strip()
    now = _now_utc()

    with _LOCK:
        _cleanup_expired_tokens(now)
        record = _PREVIEW_TOKENS.get(clean_preview_id)

    if record is None:
        return (
            False,
            "PREVIEW_TOKEN_NOT_FOUND",
            f"Preview token '{clean_preview_id}' không tồn tại hoặc đã hết hạn. Vui lòng thực hiện preview lại.",
        )

    if record.user_id != user_id:
        return (
            False,
            "PREVIEW_TOKEN_FORBIDDEN",
            "Preview token không thuộc quyền sở hữu của người dùng hiện tại.",
        )

    if record.action != action:
        return (
            False,
            "PREVIEW_ACTION_MISMATCH",
            f"Preview token này được tạo cho hành động '{record.action}', không khớp với '{action}'.",
        )

    if str(record.resource_id) != str(resource_id):
        return (
            False,
            "PREVIEW_RESOURCE_MISMATCH",
            f"Preview token này thuộc resource '{record.resource_id}', không khớp với '{resource_id}'.",
        )

    if record.resource_version != current_resource_version:
        return (
            False,
            "STALE_PREVIEW_ERROR",
            "Dữ liệu của resource đã thay đổi kể từ khi tạo preview (resource version mismatch). Vui lòng tạo preview mới để kiểm tra tác động trước khi xác nhận.",
        )

    return True, None, None


def consume_preview_token(preview_id: str) -> None:
    """Invalidate a preview token after successful execution."""
    clean_preview_id = str(preview_id or "").strip()
    if clean_preview_id:
        with _LOCK:
            _PREVIEW_TOKENS.pop(clean_preview_id, None)
