"""Persistence helpers for MCP access tokens."""

from __future__ import annotations

from models import db
from models.mcp_access_token import McpAccessToken
from models.user import User
from sqlalchemy import or_


def create_access_token(
    *,
    user_id: int,
    name: str | None = None,
    token_hash: str,
    scopes: str,
    expires_at,
    max_requests: int = 1000000,
) -> McpAccessToken:
    row = McpAccessToken(
        user_id=user_id,
        name=str(name or "MCP Token").strip() or "MCP Token",
        token_hash=token_hash,
        scopes=scopes,
        expires_at=expires_at,
        max_requests=max_requests,
        used_requests=0,
        revoked=False,
    )
    db.session.add(row)
    db.session.flush()
    return row


def list_tokens_for_user(*, user_id: int, limit: int = 50) -> list[McpAccessToken]:
    return (
        McpAccessToken.query.filter(McpAccessToken.user_id == user_id)
        .order_by(McpAccessToken.created_at.desc(), McpAccessToken.id.desc())
        .limit(limit)
        .all()
    )


def get_token_by_hash(token_hash: str) -> McpAccessToken | None:
    return McpAccessToken.query.filter_by(token_hash=token_hash).first()


def get_token_for_user(*, token_id: int, user_id: int) -> McpAccessToken | None:
    return McpAccessToken.query.filter_by(id=token_id, user_id=user_id).first()


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, int(user_id)) if user_id else None


def consume_request_quota(*, token_id: int, now) -> bool:
    """Atomically consume one lifetime request slot for an active token."""
    updated = (
        McpAccessToken.query.filter(
            McpAccessToken.id == int(token_id),
            McpAccessToken.revoked.is_(False),
            or_(
                McpAccessToken.expires_at.is_(None),
                McpAccessToken.expires_at > now,
            ),
            McpAccessToken.used_requests < McpAccessToken.max_requests,
        )
        .update(
            {
                McpAccessToken.used_requests: McpAccessToken.used_requests + 1,
                McpAccessToken.last_used_at: now,
            },
            synchronize_session=False,
        )
    )
    return int(updated or 0) == 1


def update_token(
    row: McpAccessToken,
    *,
    name: str | None = None,
    scopes: str | None = None,
    expires_at: object = ...,
    token_hash: str | None = None,
    revoked: bool | None = None,
) -> McpAccessToken:
    if name is not None:
        row.name = str(name).strip() or "MCP Token"
    if scopes is not None:
        row.scopes = scopes
    if expires_at is not ...:
        row.expires_at = expires_at
    if token_hash is not None:
        row.token_hash = token_hash
    if revoked is not None:
        row.revoked = revoked
    db.session.add(row)
    return row


def delete_token(row: McpAccessToken) -> None:
    db.session.delete(row)


def purge_revoked_and_expired_tokens(user_id: int, now) -> int:
    from sqlalchemy import or_

    deleted_count = (
        McpAccessToken.query.filter(
            McpAccessToken.user_id == user_id,
            or_(
                McpAccessToken.revoked.is_(True),
                (McpAccessToken.expires_at.isnot(None) & (McpAccessToken.expires_at <= now)),
            ),
        )
        .delete(synchronize_session=False)
    )
    return deleted_count

