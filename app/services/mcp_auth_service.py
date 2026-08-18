"""Authentication resolver for MCP requests on Flama Connect and web."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from flask import Request

from app.services import mcp_access_token_service, user_api_token_service
from app.services.mcp_access_token_service import McpAccessTokenError
from models import db
from models.user import User


@dataclass(frozen=True)
class McpRequestAuthContext:
    user: User
    auth_type: str
    token_id: int | None
    scopes: tuple[str, ...]


def extract_raw_token(
    *,
    request: Request,
    url_token: str | None = None,
    body_key: str | None = None,
) -> str | None:
    """Extract raw credential string from headers, URL path, or body."""
    auth_header = str(request.headers.get("Authorization") or "").strip()
    if auth_header:
        scheme, _, credentials = auth_header.partition(" ")
        if scheme.lower() == "bearer" and credentials.strip():
            return credentials.strip()

    header_key = request.headers.get("X-Flama-Connect-Key")
    if header_key and str(header_key).strip():
        return str(header_key).strip()

    if url_token and str(url_token).strip():
        return str(url_token).strip()

    if body_key and isinstance(body_key, str) and body_key.strip():
        return body_key.strip()

    return None


def authenticate_mcp_request(
    *,
    request: Request,
    session_user: Any = None,
    url_token: str | None = None,
    body_key: str | None = None,
    required_scope: str | None = None,
) -> McpRequestAuthContext:
    raw_token = extract_raw_token(
        request=request,
        url_token=url_token,
        body_key=body_key,
    )

    if raw_token:
        token_str = raw_token.strip()

        # Case 1: McpAccessToken format (flama_mcp_...)
        if token_str.startswith("flama_mcp_"):
            token_auth = mcp_access_token_service.authenticate_bearer_token(
                raw_token=token_str,
                required_scope=required_scope,
            )
            return McpRequestAuthContext(
                user=token_auth.user,
                auth_type="mcp_token",
                token_id=token_auth.token_row.id,
                scopes=token_auth.scopes,
            )

        # Case 2: UserApiToken format (flama_yt_... or standard API token)
        status, authenticated = user_api_token_service.authenticate_token_detailed(
            token_str,
            required_scope=required_scope,
        )
        if authenticated is not None:
            token_row, user = authenticated
            scopes_set = user_api_token_service.parse_scopes(token_row)
            return McpRequestAuthContext(
                user=user,
                auth_type="user_api_token",
                token_id=token_row.id,
                scopes=tuple(sorted(scopes_set)),
            )

        # Map detailed UserApiToken status to McpAccessTokenError for standard error response
        if status == "revoked":
            raise McpAccessTokenError("Token has been revoked.", status=401, code="TOKEN_REVOKED")
        if status == "expired":
            raise McpAccessTokenError("Token has expired.", status=401, code="TOKEN_EXPIRED")
        if status == "permission_denied":
            raise McpAccessTokenError("Token does not have required permissions.", status=403, code="PERMISSION_DENIED")
        if status == "user_disabled":
            raise McpAccessTokenError("User account is disabled.", status=403, code="USER_DISABLED")

        # Try McpAccessToken lookup just in case prefix is custom
        try:
            token_auth = mcp_access_token_service.authenticate_bearer_token(
                raw_token=token_str,
                required_scope=required_scope,
            )
            return McpRequestAuthContext(
                user=token_auth.user,
                auth_type="mcp_token",
                token_id=token_auth.token_row.id,
                scopes=token_auth.scopes,
            )
        except McpAccessTokenError:
            pass

        raise McpAccessTokenError(
            "Invalid or unknown authentication token.",
            status=401,
            code="MCP_TOKEN_INVALID",
        )

    # Fallback to session user if present (e.g. legacy web session)
    if session_user is not None and getattr(session_user, "is_authenticated", False):
        if not bool(getattr(session_user, "is_active", True)):
            raise McpAccessTokenError(
                "User account is disabled.",
                status=403,
                code="USER_DISABLED",
            )
        return McpRequestAuthContext(
            user=session_user,
            auth_type="session",
            token_id=None,
            scopes=("*",),
        )

    raise McpAccessTokenError(
        "Authentication required.",
        status=401,
        code="AUTH_REQUIRED",
    )


def authenticate_mcp_request_if_present(
    *,
    request: Request,
    session_user: Any = None,
    url_token: str | None = None,
    body_key: str | None = None,
    required_scope: str | None = None,
) -> McpRequestAuthContext | None:
    """Authenticate only when credentials (token or session) are actually present."""
    raw_token = extract_raw_token(
        request=request,
        url_token=url_token,
        body_key=body_key,
    )
    if raw_token or (session_user is not None and getattr(session_user, "is_authenticated", False)):
        return authenticate_mcp_request(
            request=request,
            session_user=session_user,
            url_token=url_token,
            body_key=body_key,
            required_scope=required_scope,
        )
    return None
