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
from app.services import mcp_scope_service
from models import db
from models.mcp_access_token import McpAccessToken
from models.user import User

ALLOWED_SCOPES = mcp_scope_service.ALLOWED_MCP_SCOPES
DEFAULT_SCOPES = mcp_scope_service.DEFAULT_SCOPES
has_scope = mcp_scope_service.has_scope
_RATE_LIMIT_LOCK = threading.Lock()
_RATE_LIMIT_BUCKETS: dict[str, deque[float]] = {}


class McpAccessTokenError(RuntimeError):
    def __init__(self, message: str, *, status: int, code: str) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = str(code)


class McpAccessTokenPersistenceError(RuntimeError):
    """Raised when an MCP token mutation cannot be committed."""


@dataclass(frozen=True)
class IssuedMcpAccessToken:
    token: str
    name: str
    scopes: tuple[str, ...]
    expires_at: datetime | None
    max_requests: int

    def to_display_payload(self) -> dict[str, Any]:
        return {
            "token": self.token,
            "name": self.name,
            "scopes": list(self.scopes),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
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
    return {
        "default_expiry_days": 180,
        "allowed_expiry_days": [7, 30, 90, 180, 365],
        "allow_no_expiry": True,
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
    if row.expires_at is not None and row.expires_at <= now:
        return "expired"
    if int(row.used_requests or 0) >= int(row.max_requests or 0):
        return "exhausted"
    return "active"


def list_token_summaries(*, user_id: int, limit: int = 50) -> list[dict[str, Any]]:
    now = datetime.utcnow()
    items: list[dict[str, Any]] = []
    for row in mcp_access_token_repository.list_tokens_for_user(user_id=user_id, limit=limit):
        max_requests = int(row.max_requests or 0)
        used_requests = int(row.used_requests or 0)
        remaining_requests = max(max_requests - used_requests, 0)
        items.append(
            {
                "id": int(row.id),
                "name": getattr(row, "name", None) or "MCP Token",
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


def issue_token(
    *,
    user_id: int,
    name: str | None = None,
    expires_in_days: int | None = 180,
    scopes: Iterable[str] | None = None,
) -> IssuedMcpAccessToken:
    normalized_name = str(name or "").strip() or "MCP Token"
    if len(normalized_name) > 120:
        normalized_name = normalized_name[:120]

    if expires_in_days is not None:
        try:
            days = int(expires_in_days)
            if days <= 0:
                expires_in_days = None
            else:
                expires_in_days = days
        except (TypeError, ValueError):
            expires_in_days = 180

    token_scopes = _normalize_scopes(scopes) if scopes is not None else DEFAULT_SCOPES
    if not token_scopes:
        token_scopes = DEFAULT_SCOPES

    raw_token = f"flama_mcp_{secrets.token_urlsafe(32)}"
    now = datetime.utcnow()
    expires_at = (now + timedelta(days=expires_in_days)) if expires_in_days is not None else None
    max_requests = 1_000_000

    row = mcp_access_token_repository.create_access_token(
        user_id=user_id,
        name=normalized_name,
        token_hash=_hash_token(raw_token),
        scopes=_dump_scopes(token_scopes),
        expires_at=expires_at,
        max_requests=max_requests,
    )
    current_app.logger.info(
        "Issued MCP token token_id=%s user_id=%s name=%s expires_at=%s",
        row.id,
        user_id,
        normalized_name,
        expires_at.isoformat() if expires_at else "never",
    )
    return IssuedMcpAccessToken(
        token=raw_token,
        name=normalized_name,
        scopes=token_scopes,
        expires_at=expires_at,
        max_requests=max_requests,
    )


def issue_short_lived_token(*, user_id: int) -> IssuedMcpAccessToken:
    """Backward compatibility alias for tests and older callers."""
    return issue_token(user_id=user_id, expires_in_days=180)


def revoke_token(*, user_id: int, token_id: int) -> bool:
    row = mcp_access_token_repository.get_token_for_user(token_id=token_id, user_id=user_id)
    if row is None or bool(row.revoked):
        return False
    row.revoked = True
    db.session.add(row)
    current_app.logger.info("Revoked MCP token token_id=%s user_id=%s", token_id, user_id)
    return True


def issue_token_and_commit(
    *,
    user_id: int,
    name: str | None = None,
    expires_in_days: int | None = 180,
    scopes: Iterable[str] | None = None,
) -> IssuedMcpAccessToken:
    try:
        issued = issue_token(
            user_id=user_id,
            name=name,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
        db.session.commit()
        return issued
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise McpAccessTokenPersistenceError(
            "Could not create the MCP token."
        ) from exc


def revoke_token_and_commit(*, user_id: int, token_id: int) -> bool:
    try:
        revoked = revoke_token(user_id=user_id, token_id=token_id)
        if not revoked:
            db.session.rollback()
            return False
        db.session.commit()
        return True
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise McpAccessTokenPersistenceError(
            "Could not revoke the MCP token."
        ) from exc


def update_token(
    *,
    user_id: int,
    token_id: int,
    name: str | None = None,
    expires_in_days: object = ...,
    scopes: Iterable[str] | None = None,
) -> dict[str, Any] | None:
    row = mcp_access_token_repository.get_token_for_user(token_id=token_id, user_id=user_id)
    if row is None:
        return None

    normalized_name = None
    if name is not None:
        normalized_name = str(name).strip() or "MCP Token"
        if len(normalized_name) > 120:
            normalized_name = normalized_name[:120]

    expires_at = ...
    if expires_in_days is not ...:
        if expires_in_days is not None:
            try:
                days = int(expires_in_days)
                expires_at = (datetime.utcnow() + timedelta(days=days)) if days > 0 else None
            except (TypeError, ValueError):
                expires_at = ...
        else:
            expires_at = None

    token_scopes_json = None
    if scopes is not None:
        normalized_scopes = _normalize_scopes(scopes)
        if not normalized_scopes:
            normalized_scopes = DEFAULT_SCOPES
        token_scopes_json = _dump_scopes(normalized_scopes)

    updated_row = mcp_access_token_repository.update_token(
        row,
        name=normalized_name,
        scopes=token_scopes_json,
        expires_at=expires_at,
    )
    now = datetime.utcnow()
    max_requests = int(updated_row.max_requests or 0)
    used_requests = int(updated_row.used_requests or 0)
    return {
        "id": int(updated_row.id),
        "name": getattr(updated_row, "name", None) or "MCP Token",
        "status": _resolve_status(row=updated_row, now=now),
        "scopes": list(_normalize_scopes(updated_row.scopes)),
        "expires_at": updated_row.expires_at.isoformat() if updated_row.expires_at else None,
        "max_requests": max_requests,
        "used_requests": used_requests,
        "remaining_requests": max(max_requests - used_requests, 0),
        "created_at": updated_row.created_at.isoformat() if updated_row.created_at else None,
        "last_used_at": updated_row.last_used_at.isoformat() if updated_row.last_used_at else None,
        "revoked": bool(updated_row.revoked),
    }


def update_token_and_commit(
    *,
    user_id: int,
    token_id: int,
    name: str | None = None,
    expires_in_days: object = ...,
    scopes: Iterable[str] | None = None,
) -> dict[str, Any] | None:
    try:
        updated = update_token(
            user_id=user_id,
            token_id=token_id,
            name=name,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
        if updated is None:
            db.session.rollback()
            return None
        db.session.commit()
        return updated
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise McpAccessTokenPersistenceError("Could not update the MCP token.") from exc


def rotate_token(
    *,
    user_id: int,
    token_id: int,
    expires_in_days: object = ...,
    scopes: Iterable[str] | None = None,
) -> IssuedMcpAccessToken | None:
    row = mcp_access_token_repository.get_token_for_user(token_id=token_id, user_id=user_id)
    if row is None:
        return None

    raw_token = f"flama_mcp_{secrets.token_urlsafe(32)}"
    now = datetime.utcnow()

    expires_at = ...
    if expires_in_days is not ...:
        if expires_in_days is not None:
            try:
                days = int(expires_in_days)
                expires_at = (now + timedelta(days=days)) if days > 0 else None
            except (TypeError, ValueError):
                expires_at = ...
        else:
            expires_at = None

    token_scopes_json = None
    if scopes is not None:
        token_scopes = _normalize_scopes(scopes)
        if not token_scopes:
            token_scopes = DEFAULT_SCOPES
        token_scopes_json = _dump_scopes(token_scopes)
    else:
        token_scopes = _normalize_scopes(row.scopes)

    updated_row = mcp_access_token_repository.update_token(
        row,
        token_hash=_hash_token(raw_token),
        scopes=token_scopes_json,
        expires_at=expires_at,
        revoked=False,
    )
    current_app.logger.info(
        "Rotated MCP token token_id=%s user_id=%s expires_at=%s",
        token_id,
        user_id,
        updated_row.expires_at.isoformat() if updated_row.expires_at else "never",
    )
    return IssuedMcpAccessToken(
        token=raw_token,
        name=getattr(updated_row, "name", None) or "MCP Token",
        scopes=token_scopes,
        expires_at=updated_row.expires_at,
        max_requests=int(updated_row.max_requests or 1_000_000),
    )


def rotate_token_and_commit(
    *,
    user_id: int,
    token_id: int,
    expires_in_days: object = ...,
    scopes: Iterable[str] | None = None,
) -> IssuedMcpAccessToken | None:
    try:
        issued = rotate_token(
            user_id=user_id,
            token_id=token_id,
            expires_in_days=expires_in_days,
            scopes=scopes,
        )
        if issued is None:
            db.session.rollback()
            return None
        db.session.commit()
        return issued
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise McpAccessTokenPersistenceError("Could not rotate the MCP token.") from exc


def purge_token(*, user_id: int, token_id: int) -> bool:
    row = mcp_access_token_repository.get_token_for_user(token_id=token_id, user_id=user_id)
    if row is None:
        return False
    mcp_access_token_repository.delete_token(row)
    current_app.logger.info("Purged MCP token token_id=%s user_id=%s", token_id, user_id)
    return True


def purge_token_and_commit(*, user_id: int, token_id: int) -> bool:
    try:
        purged = purge_token(user_id=user_id, token_id=token_id)
        if not purged:
            db.session.rollback()
            return False
        db.session.commit()
        return True
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise McpAccessTokenPersistenceError("Could not permanently delete the MCP token.") from exc


def cleanup_tokens(*, user_id: int) -> int:
    now = datetime.utcnow()
    count = mcp_access_token_repository.purge_revoked_and_expired_tokens(user_id=user_id, now=now)
    current_app.logger.info("Cleaned up %s revoked/expired MCP tokens for user_id=%s", count, user_id)
    return count


def cleanup_tokens_and_commit(*, user_id: int) -> int:
    try:
        count = cleanup_tokens(user_id=user_id)
        db.session.commit()
        return count
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise McpAccessTokenPersistenceError("Could not cleanup expired MCP tokens.") from exc



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
    if row.expires_at is not None and row.expires_at <= now:
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
    if required_scope and not has_scope(scopes, required_scope):
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
