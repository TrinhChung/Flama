"""Short-lived MCP access token lifecycle and token-based auth."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import secrets
import threading
import time
from typing import Any, Iterable

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.repositories import mcp_access_token_repository
from models import db
from models.mcp_access_token import McpAccessToken
from models.user import User

ALLOWED_SCOPES = frozenset({"deck:read"})
DEFAULT_SCOPES = ("deck:read",)
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}


class McpAccessTokenError(RuntimeError):
    def __init__(self, message: str, *, status: int, code: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = str(code)


@dataclass(frozen=True)
class IssuedMcpAccessToken:
    token: str
    scopes: tuple[str, ...]
    expires_at: datetime
    max_requests: int

    def to_display_payload(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "scopes": list(self.scopes),
            "expires_at": self.expires_at.isoformat(),
            "remaining_requests": int(self.max_requests),
            "max_requests": int(self.max_requests),
        }


@dataclass(frozen=True)
class AuthenticatedMcpToken:
    user: User
    token_row: McpAccessToken
    scopes: tuple[str, ...]


def _config_int(name: str, default: int, *, minimum: int = 1) -> int:
    raw_value = current_app.config.get(name, default)
    try:
        value = int(raw_value)
    except (TypeError, ValueError):
        value = int(default)
    return max(value, minimum)


def get_token_policy() -> dict[str, Any]:
    ttl_seconds = _config_int("MCP_TOKEN_TTL_SECONDS", 10 * 60, minimum=60)
    max_requests = _config_int("MCP_TOKEN_MAX_REQUESTS", 30, minimum=1)
    return {
        "ttl_seconds": ttl_seconds,
        "ttl_minutes": max(ttl_seconds // 60, 1),
        "max_requests": max_requests,
        "scopes": list(DEFAULT_SCOPES),
    }


def _rate_limit_window_seconds() -> int:
    return _config_int("MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS", 60, minimum=1)


def _rate_limit_max_requests() -> int:
    return _config_int("MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS", 20, minimum=1)


def reset_rate_limit_state() -> None:
    with _RATE_LIMIT_LOCK:
        _RATE_LIMIT_BUCKETS.clear()


def _hash_token(raw_token: str) -> str:
    return hashlib.sha256(raw_token.encode("utf-8")).hexdigest()


def _normalize_scopes(raw_scopes: Any) -> tuple[str, ...]:
    if raw_scopes is None:
        return ()

    parsed_value = raw_scopes
    if isinstance(raw_scopes, str):
        text = raw_scopes.strip()
        if not text:
            return ()
        try:
            parsed_value = json.loads(text)
        except ValueError:
            parsed_value = [item.strip() for item in text.split(",") if item and item.strip()]

    if not isinstance(parsed_value, (list, tuple, set)):
        return ()

    normalized: list[str] = []
    for item in parsed_value:
        scope = str(item or "").strip().lower()
        if scope in ALLOWED_SCOPES and scope not in normalized:
            normalized.append(scope)
    return tuple(normalized)


def _dump_scopes(scopes: Iterable[str]) -> str:
    normalized = [scope for scope in _normalize_scopes(list(scopes)) if scope in ALLOWED_SCOPES]
    return json.dumps(normalized, ensure_ascii=False)


def _resolve_status(*, row: McpAccessToken, now: datetime) -> str:
    if bool(row.revoked):
        return "revoked"
    if row.expires_at <= now:
        return "expired"
    if int(row.used_requests or 0) >= int(row.max_requests or 0):
        return "exhausted"
    return "active"


def list_token_summaries(*, user_id: int, limit: int = 10) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    items: list[dict[str, Any]] = []
    for row in mcp_access_token_repository.list_tokens_for_user(user_id=user_id, limit=limit):
        max_requests = int(row.max_requests or 0)
        used_requests = int(row.used_requests or 0)
        remaining_requests = max(max_requests - used_requests, 0)
        items.append(
            {
                "id": int(row.id),
                "status": _resolve_status(row=row, now=now),
                "scopes": list(_normalize_scopes(row.scopes)),
                "expires_at": row.expires_at.isoformat() if row.expires_at else None,
                "max_requests": max_requests,
                "used_requests": used_requests,
                "remaining_requests": remaining_requests,
                "created_at": row.created_at.isoformat() if row.created_at else None,
                "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
                "revoked": bool(row.revoked),
            }
        )
    return items


def issue_short_lived_token(*, user_id: int) -> IssuedMcpAccessToken:
    policy = get_token_policy()
    raw_token = f"flama_mcp_{secrets.token_urlsafe(32)}"
    expires_at = datetime.utcnow() + timedelta(seconds=int(policy["ttl_seconds"]))
    row = mcp_access_token_repository.create_access_token(
        user_id=user_id,
        token_hash=_hash_token(raw_token),
        scopes=_dump_scopes(DEFAULT_SCOPES),
        expires_at=expires_at,
        max_requests=int(policy["max_requests"]),
    )
    current_app.logger.info(
        "Issued short-lived MCP token token_id=%s user_id=%s expires_at=%s max_requests=%s",
        row.id,
        user_id,
        expires_at.isoformat(),
        int(policy["max_requests"]),
    )
    return IssuedMcpAccessToken(
        token=raw_token,
        scopes=DEFAULT_SCOPES,
        expires_at=expires_at,
        max_requests=int(policy["max_requests"]),
    )


def revoke_token(*, user_id: int, token_id: int) -> bool:
    row = mcp_access_token_repository.get_token_for_user(token_id=token_id, user_id=user_id)
    if row is None or bool(row.revoked):
        return False
    row.revoked = True
    db.session.add(row)
    current_app.logger.info("Revoked MCP token token_id=%s user_id=%s", token_id, user_id)
    return True


def enforce_rate_limit(*, bucket_key: str) -> None:
    max_requests = _rate_limit_max_requests()
    window_seconds = _rate_limit_window_seconds()
    now_ts = time.monotonic()

    with _RATE_LIMIT_LOCK:
        bucket = _RATE_LIMIT_BUCKETS.setdefault(bucket_key, deque())
        cutoff = now_ts - window_seconds
        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= max_requests:
            raise McpAccessTokenError(
                "Too many MCP requests. Please wait a moment and try again.",
                status=429,
                code="MCP_RATE_LIMIT_EXCEEDED",
            )
        bucket.append(now_ts)


def authenticate_bearer_token(
    *,
    raw_token: str,
    required_scope: str | None = None,
) -> AuthenticatedMcpToken:
    token_value = str(raw_token or "").strip()
    if not token_value:
        raise McpAccessTokenError(
            "Bearer token is required.",
            status=401,
            code="MCP_TOKEN_MISSING",
        )

    row = mcp_access_token_repository.get_token_by_hash(_hash_token(token_value))
    if row is None:
        raise McpAccessTokenError(
            "MCP token is invalid.",
            status=401,
            code="MCP_TOKEN_INVALID",
        )

    now = datetime.utcnow()
    if bool(row.revoked):
        raise McpAccessTokenError(
            "MCP token has been revoked.",
            status=401,
            code="MCP_TOKEN_REVOKED",
        )
    if row.expires_at <= now:
        raise McpAccessTokenError(
            "MCP token has expired.",
            status=401,
            code="MCP_TOKEN_EXPIRED",
        )
    if int(row.used_requests or 0) >= int(row.max_requests or 0):
        raise McpAccessTokenError(
            "MCP token request limit has been reached.",
            status=429,
            code="MCP_TOKEN_REQUEST_LIMIT_EXCEEDED",
        )

    scopes = _normalize_scopes(row.scopes)
    if required_scope and required_scope not in scopes:
        raise McpAccessTokenError(
            "MCP token does not grant the required scope.",
            status=403,
            code="MCP_SCOPE_FORBIDDEN",
        )

    user = mcp_access_token_repository.get_user_by_id(int(row.user_id))
    if user is None:
        raise McpAccessTokenError(
            "MCP token owner does not exist.",
            status=401,
            code="MCP_TOKEN_INVALID_OWNER",
        )
    if not bool(getattr(user, "is_active", True)):
        raise McpAccessTokenError(
            "User account is disabled.",
            status=403,
            code="USER_DISABLED",
        )

    enforce_rate_limit(bucket_key=f"mcp-token:{row.id}")

    row.used_requests = int(row.used_requests or 0) + 1
    row.last_used_at = now
    db.session.add(row)
    try:
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise McpAccessTokenError(
            "Could not update MCP token usage.",
            status=500,
            code="MCP_TOKEN_USAGE_UPDATE_FAILED",
        ) from exc

    return AuthenticatedMcpToken(user=user, token_row=row, scopes=scopes)
