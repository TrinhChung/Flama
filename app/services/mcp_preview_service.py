"""Preview token and stale protection management for destructive or impactful MCP actions.

Architecture & Lifecycle:
-------------------------
1. Generation (`create_preview_token`):
   When a caller runs an impactful or destructive preview action (e.g. `preview_note_type_update`,
   `delete_note_type`, `delete_deck`), the service calculates a deterministic `resource_version`
   fingerprint of the target resource and generates a temporary `preview_id` with TTL.

2. Verification (`validate_preview_token`):
   Before executing the mutation, the caller passes `preview_id`. The service verifies:
   - Token existence and expiry (TTL).
   - Ownership matching (`user_id`).
   - Action matching (`action`).
   - Target resource matching (`resource_id`).
   - State freshness (`resource_version == current_resource_version`). If the resource
     was modified by another request in the interim, `STALE_PREVIEW_ERROR` (HTTP 409) is returned.

3. Consumption (`consume_preview_token`):
   Upon successful mutation, the preview token is immediately consumed (single-use).

Storage is selected with MCP_PREVIEW_BACKEND. Redis mode uses native TTL and
atomically validates/claims a token so it cannot execute in two workers.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import hashlib
import json
import secrets
import threading
from typing import Any

from flask import current_app

from app.services import redis_state_service


DEFAULT_PREVIEW_TTL_SECONDS = 600  # 10 minutes


class PreviewStoreUnavailable(RuntimeError):
    pass


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
    ttl_seconds: int | None = None,
) -> tuple[str, str]:
    """Create a temporary preview token with TTL and return (preview_id, expires_at_iso)."""
    effective_ttl = max(
        int(
            ttl_seconds
            if ttl_seconds is not None
            else current_app.config.get(
                "MCP_PREVIEW_TTL_SECONDS",
                DEFAULT_PREVIEW_TTL_SECONDS,
            )
        ),
        1,
    )
    now = _now_utc()
    preview_id = f"prev_{secrets.token_hex(12)}"
    expires_at = now + timedelta(seconds=effective_ttl)

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

    mode = redis_state_service.backend_mode("MCP_PREVIEW_BACKEND")
    with _LOCK:
        _cleanup_expired_tokens(now)
        _PREVIEW_TOKENS[preview_id] = record

    if mode != "local":
        payload = json.dumps(
            {
                "preview_id": record.preview_id,
                "user_id": record.user_id,
                "action": record.action,
                "resource_id": record.resource_id,
                "resource_version": record.resource_version,
                "impact_summary": record.impact_summary,
                "created_at": record.created_at.isoformat(),
                "expires_at": record.expires_at.isoformat(),
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
        try:
            redis_state_service.redis_client().set(
                _redis_key(preview_id),
                payload,
                ex=effective_ttl,
            )
        except Exception as exc:
            if mode == "redis":
                with _LOCK:
                    _PREVIEW_TOKENS.pop(preview_id, None)
                raise PreviewStoreUnavailable(
                    "MCP preview store is temporarily unavailable"
                ) from exc
            current_app.logger.warning("Redis MCP preview shadow write failed: %s", exc)

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

    mode = redis_state_service.backend_mode("MCP_PREVIEW_BACKEND")
    if mode == "redis":
        return _claim_redis_preview_token(
            preview_id=clean_preview_id,
            user_id=user_id,
            action=action,
            resource_id=str(resource_id),
            current_resource_version=current_resource_version,
        )

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
        # Redis-authoritative validation already atomically claims/deletes the
        # token before mutation. Only shadow mode needs post-mutation cleanup.
        if redis_state_service.backend_mode("MCP_PREVIEW_BACKEND") == "shadow_redis":
            try:
                redis_state_service.redis_client().delete(_redis_key(clean_preview_id))
            except Exception as exc:
                current_app.logger.warning("Redis MCP preview shadow delete failed: %s", exc)


def _redis_key(preview_id: str) -> str:
    return redis_state_service.private_key("mcp-preview", preview_id)


def _claim_redis_preview_token(
    *,
    preview_id: str,
    user_id: int,
    action: str,
    resource_id: str,
    current_resource_version: str,
) -> tuple[bool, str | None, str | None]:
    script = """
    local raw = redis.call('GET', KEYS[1])
    if not raw then return 'NOT_FOUND' end
    local item = cjson.decode(raw)
    if tostring(item.user_id) ~= ARGV[1] then return 'FORBIDDEN' end
    if tostring(item.action) ~= ARGV[2] then return 'ACTION_MISMATCH' end
    if tostring(item.resource_id) ~= ARGV[3] then return 'RESOURCE_MISMATCH' end
    if tostring(item.resource_version) ~= ARGV[4] then return 'STALE' end
    redis.call('DEL', KEYS[1])
    return 'OK'
    """
    try:
        result = str(
            redis_state_service.redis_client().eval(
                script,
                1,
                _redis_key(preview_id),
                str(user_id),
                str(action),
                str(resource_id),
                str(current_resource_version),
            )
        )
    except Exception as exc:
        current_app.logger.error("Redis MCP preview claim failed: %s", exc)
        return False, "PREVIEW_STORE_UNAVAILABLE", "Preview store is temporarily unavailable."

    errors = {
        "NOT_FOUND": ("PREVIEW_TOKEN_NOT_FOUND", "Preview token does not exist or has expired."),
        "FORBIDDEN": ("PREVIEW_TOKEN_FORBIDDEN", "Preview token belongs to another user."),
        "ACTION_MISMATCH": ("PREVIEW_ACTION_MISMATCH", "Preview token action does not match."),
        "RESOURCE_MISMATCH": ("PREVIEW_RESOURCE_MISMATCH", "Preview token resource does not match."),
        "STALE": ("STALE_PREVIEW_ERROR", "Resource changed after preview; create a new preview."),
    }
    if result == "OK":
        return True, None, None
    code, message = errors.get(
        result,
        ("PREVIEW_TOKEN_NOT_FOUND", "Preview token does not exist or has expired."),
    )
    return False, code, message
