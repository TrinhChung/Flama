"""Persistence helpers for MCP access tokens."""

from __future__ import annotations

from models import db
from models.mcp_access_token import McpAccessToken
from models.user import User


def create_access_token(
    *,
    user_id: int,
    token_hash: str,
    scopes: str,
    expires_at,
    max_requests: int,
) -> McpAccessToken:
    row = McpAccessToken(
        user_id=user_id,
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


def list_tokens_for_user(*, user_id: int, limit: int = 10) -> list[McpAccessToken]:
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
    return User.query.get(int(user_id)) if user_id else None
