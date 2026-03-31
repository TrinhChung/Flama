"""Authentication resolver for MCP requests."""

from __future__ import annotations

from dataclasses import dataclass

from flask import Request

from app.services import mcp_access_token_service
from models.user import User


@dataclass(frozen=True)
class McpRequestAuthContext:
    user: User
    auth_type: str
    token_id: int | None
    scopes: tuple[str, ...]


def authenticate_mcp_request(
    *,
    request: Request,
    session_user,
    required_scope: str | None = None,
) -> McpRequestAuthContext:
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header:
        scheme, _, credentials = auth_header.partition(" ")
        if scheme.lower() != "bearer" or not credentials.strip():
            raise mcp_access_token_service.McpAccessTokenError(
                "Authorization header must use Bearer <token>.",
                status=401,
                code="INVALID_AUTHORIZATION_HEADER",
            )

        token_auth = mcp_access_token_service.authenticate_bearer_token(
            raw_token=credentials.strip(),
            required_scope=required_scope,
        )
        return McpRequestAuthContext(
            user=token_auth.user,
            auth_type="bearer",
            token_id=token_auth.token_row.id,
            scopes=token_auth.scopes,
        )

    if not getattr(session_user, "is_authenticated", False):
        raise mcp_access_token_service.McpAccessTokenError(
            "Authentication required.",
            status=401,
            code="AUTH_REQUIRED",
        )
    if not bool(getattr(session_user, "is_active", True)):
        raise mcp_access_token_service.McpAccessTokenError(
            "User account is disabled.",
            status=403,
            code="USER_DISABLED",
        )

    mcp_access_token_service.enforce_rate_limit(bucket_key=f"mcp-user:{int(session_user.id)}")
    return McpRequestAuthContext(
        user=session_user,
        auth_type="session",
        token_id=None,
        scopes=("*",),
    )
