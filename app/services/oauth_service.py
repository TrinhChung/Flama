"""OAuth 2.1 service supporting PKCE, token lifecycle, and MCP metadata discovery."""

from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import re
import secrets
from typing import Any, Iterable
from urllib.parse import urlencode, urlparse, urlunparse, parse_qsl

from flask import Request, current_app
from werkzeug.security import check_password_hash, generate_password_hash

from app.repositories import oauth_repository
from app.services import mcp_scope_service
from models import db
from models.mcp_access_token import McpAccessToken
from models.oauth_authorization_code import OAuthAuthorizationCode
from models.oauth_client import OAuthClient
from models.user import User

ALLOWED_SCOPES = mcp_scope_service.ALLOWED_OAUTH_SCOPES
DEFAULT_SCOPES = mcp_scope_service.DEFAULT_SCOPES
AUTH_CODE_EXPIRY_SECONDS = 300  # 5 minutes
ACCESS_TOKEN_EXPIRY_SECONDS = 86400  # 24 hours
REFRESH_TOKEN_EXPIRY_DAYS = 90


class OAuthError(Exception):
    def __init__(
        self,
        error: str,
        description: str,
        *,
        status: int = 400,
        redirect_uri: str | None = None,
        state: str | None = None,
    ) -> None:
        super().__init__(description)
        self.error = str(error)
        self.description = str(description)
        self.status = int(status)
        self.redirect_uri = redirect_uri
        self.state = state

    def to_dict(self) -> dict[str, Any]:
        payload = {"error": self.error, "error_description": self.description}
        if self.state:
            payload["state"] = self.state
        return payload

    def to_redirect_url(self) -> str | None:
        if not self.redirect_uri:
            return None
        return build_redirect_url(
            self.redirect_uri,
            {"error": self.error, "error_description": self.description},
            state=self.state,
        )


@dataclass(frozen=True)
class IssuedOAuthToken:
    access_token: str
    token_type: str
    expires_in: int
    refresh_token: str | None
    scope: str

    def to_token_response(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "access_token": self.access_token,
            "token_type": self.token_type,
            "expires_in": self.expires_in,
            "scope": self.scope,
        }
        if self.refresh_token:
            payload["refresh_token"] = self.refresh_token
        return payload


def hash_secret(secret: str) -> str:
    return hashlib.sha256(secret.encode("utf-8")).hexdigest()


def normalize_scopes(raw_scopes: Any) -> tuple[str, ...]:
    return mcp_scope_service.validate_and_normalize_oauth_scopes(raw_scopes)


def verify_pkce(*, code_verifier: str, code_challenge: str, method: str = "S256") -> bool:
    if str(method or "").upper() != "S256":
        return False
    if not code_verifier or not code_challenge:
        return False
    try:
        digest = hashlib.sha256(code_verifier.encode("ascii")).digest()
        computed = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
        target = code_challenge.rstrip("=")
        return secrets.compare_digest(computed, target)
    except Exception:
        return False


def build_redirect_url(base_url: str, params: dict[str, Any], state: str | None = None) -> str:
    parsed = urlparse(base_url)
    query_dict = dict(parse_qsl(parsed.query))
    for k, v in params.items():
        if v is not None:
            query_dict[k] = str(v)
    if state is not None:
        query_dict["state"] = state
    new_query = urlencode(query_dict)
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, parsed.fragment))


def get_base_url(req: Request | None = None) -> str:
    if req:
        # Respect X-Forwarded-Proto and X-Forwarded-Host if present
        proto = req.headers.get("X-Forwarded-Proto") or req.scheme
        host = req.headers.get("X-Forwarded-Host") or req.host
        return f"{proto}://{host}".rstrip("/")
    return current_app.config.get("SERVER_NAME") or "http://localhost:4789"


def get_protected_resource_metadata(req: Request | None = None) -> dict[str, Any]:
    base_url = get_base_url(req)
    return {
        "resource": f"{base_url}/api/mcp",
        "authorization_servers": [base_url],
        "scopes_supported": sorted(mcp_scope_service.ALL_GRANULAR_SCOPES),
        "bearer_methods_supported": ["header"],
    }


def get_authorization_server_metadata(req: Request | None = None) -> dict[str, Any]:
    base_url = get_base_url(req)
    return {
        "issuer": base_url,
        "authorization_endpoint": f"{base_url}/oauth/authorize",
        "token_endpoint": f"{base_url}/oauth/token",
        "userinfo_endpoint": f"{base_url}/oauth/userinfo",
        "revocation_endpoint": f"{base_url}/oauth/revoke",
        "response_types_supported": ["code"],
        "grant_types_supported": ["authorization_code", "refresh_token"],
        "code_challenge_methods_supported": ["S256"],
        "token_endpoint_auth_methods_supported": ["client_secret_post", "client_secret_basic", "none"],
        "scopes_supported": sorted(mcp_scope_service.ALLOWED_OAUTH_SCOPES),
    }


CLIENT_ID_REGEX = re.compile(r"^[a-zA-Z0-9_\-]{3,64}$")
URI_SCHEME_REGEX = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*$")


def validate_client_metadata(
    *,
    client_id: str,
    client_name: str,
    redirect_uris: Iterable[str] | None,
    client_secret: str | None = None,
    client_uri: str | None = None,
) -> list[str]:
    """Validate OAuth 2.1 client registration metadata and return sanitized redirect URIs."""
    client_id_clean = str(client_id or "").strip()
    if not client_id_clean:
        raise OAuthError("invalid_client_metadata", "Client ID là bắt buộc.")
    if not CLIENT_ID_REGEX.match(client_id_clean):
        raise OAuthError(
            "invalid_client_metadata",
            "Client ID phải gồm từ 3 đến 64 ký tự chữ cái, chữ số, gạch dưới (_) hoặc gạch ngang (-).",
        )

    client_name_clean = str(client_name or "").strip()
    if not client_name_clean:
        raise OAuthError("invalid_client_metadata", "Tên ứng dụng là bắt buộc.")
    if len(client_name_clean) > 120:
        raise OAuthError("invalid_client_metadata", "Tên ứng dụng không được vượt quá 120 ký tự.")

    if client_secret and len(str(client_secret)) > 255:
        raise OAuthError("invalid_client_metadata", "Client Secret không được vượt quá 255 ký tự.")

    if client_uri:
        parsed_curi = urlparse(str(client_uri).strip())
        if parsed_curi.scheme not in ("http", "https") or not parsed_curi.netloc:
            raise OAuthError("invalid_client_metadata", "Client URI phải là URL hợp lệ (http/https).")

    raw_uris = [str(u).strip() for u in (redirect_uris or []) if str(u).strip()]
    if not raw_uris:
        raise OAuthError("invalid_client_metadata", "Cần ít nhất một Redirect URI hợp lệ.")
    if len(raw_uris) > 20:
        raise OAuthError("invalid_client_metadata", "Không được đăng ký quá 20 Redirect URIs.")

    sanitized_uris: list[str] = []
    for uri in raw_uris:
        if len(uri) > 500:
            raise OAuthError("invalid_client_metadata", f"Redirect URI vượt quá độ dài tối đa (500 ký tự): {uri[:50]}...")
        parsed = urlparse(uri)
        if not parsed.scheme or not URI_SCHEME_REGEX.match(parsed.scheme):
            raise OAuthError("invalid_client_metadata", f"Redirect URI có scheme không hợp lệ: {uri}")
        if parsed.fragment:
            raise OAuthError(
                "invalid_client_metadata",
                f"Redirect URI không được chứa fragment (#): {uri}",
            )
        scheme_lower = parsed.scheme.lower()
        if scheme_lower == "http":
            hostname = (parsed.hostname or "").lower()
            if hostname not in ("localhost", "127.0.0.1", "::1", "[::1]"):
                raise OAuthError(
                    "invalid_client_metadata",
                    f"Redirect URI qua HTTP chỉ được chấp nhận cho loopback (localhost/127.0.0.1). Hãy sử dụng HTTPS cho: {uri}",
                )
        if uri not in sanitized_uris:
            sanitized_uris.append(uri)

    return sanitized_uris


def register_oauth_client(
    *,
    client_id: str,
    client_name: str,
    client_secret: str | None = None,
    client_uri: str | None = None,
    redirect_uris: Iterable[str] | None = None,
    is_confidential: bool = True,
) -> OAuthClient:
    sanitized_uris = validate_client_metadata(
        client_id=client_id,
        client_name=client_name,
        redirect_uris=redirect_uris,
        client_secret=client_secret,
        client_uri=client_uri,
    )
    secret_hash = generate_password_hash(client_secret) if client_secret else None
    existing = oauth_repository.get_client_by_client_id(client_id.strip())
    if existing:
        existing.client_name = client_name.strip()
        if secret_hash:
            existing.client_secret_hash = secret_hash
        existing.client_uri = client_uri.strip() if client_uri else None
        existing.redirect_uris = json.dumps(sanitized_uris, ensure_ascii=False)
        existing.is_confidential = is_confidential
        db.session.add(existing)
        db.session.commit()
        return existing

    client = oauth_repository.create_client(
        client_id=client_id.strip(),
        client_name=client_name.strip(),
        client_secret_hash=secret_hash,
        client_uri=client_uri.strip() if client_uri else None,
        redirect_uris=sanitized_uris,
        is_confidential=is_confidential,
    )
    db.session.commit()
    return client


def validate_authorize_request(
    *,
    client_id: str,
    redirect_uri: str,
    response_type: str,
    scope: str | None = None,
    state: str | None = None,
    code_challenge: str | None = None,
    code_challenge_method: str | None = None,
) -> tuple[OAuthClient, list[str]]:
    if not client_id:
        raise OAuthError("invalid_request", "Missing client_id.")

    client = oauth_repository.get_client_by_client_id(client_id)
    if not client or not bool(client.is_active):
        raise OAuthError("unauthorized_client", f"Unknown or inactive client: {client_id}")

    if not redirect_uri:
        raise OAuthError("invalid_request", "Missing redirect_uri.")

    if not client.is_valid_redirect_uri(redirect_uri):
        raise OAuthError(
            "invalid_request",
            f"Invalid redirect_uri for client {client_id}.",
        )

    if response_type != "code":
        raise OAuthError(
            "unsupported_response_type",
            "Only response_type=code is supported.",
            redirect_uri=redirect_uri,
            state=state,
        )

    if not code_challenge:
        raise OAuthError(
            "invalid_request",
            "PKCE code_challenge is required (S256).",
            redirect_uri=redirect_uri,
            state=state,
        )

    challenge_method = str(code_challenge_method or "S256").upper()
    if challenge_method != "S256":
        raise OAuthError(
            "invalid_request",
            "Only S256 code_challenge_method is supported.",
            redirect_uri=redirect_uri,
            state=state,
        )

    try:
        normalized_scopes = list(mcp_scope_service.validate_and_normalize_oauth_scopes(scope))
    except ValueError as err:
        raise OAuthError(
            "invalid_scope",
            str(err),
            redirect_uri=redirect_uri,
            state=state,
        ) from err
    return client, normalized_scopes


def issue_authorization_code(
    *,
    client: OAuthClient,
    user: User,
    redirect_uri: str,
    scopes: list[str],
    code_challenge: str,
    code_challenge_method: str = "S256",
) -> str:
    raw_code = f"flama_ac_{secrets.token_urlsafe(32)}"
    code_hash = hash_secret(raw_code)
    expires_at = datetime.utcnow() + timedelta(seconds=AUTH_CODE_EXPIRY_SECONDS)

    oauth_repository.create_authorization_code(
        code_hash=code_hash,
        client_id=client.id,
        user_id=user.id,
        redirect_uri=redirect_uri,
        scopes=scopes,
        code_challenge=code_challenge,
        code_challenge_method=code_challenge_method,
        expires_at=expires_at,
    )
    db.session.commit()
    return raw_code


def authenticate_client_credentials(
    *,
    client_id: str,
    client_secret: str | None,
) -> OAuthClient:
    if not client_id:
        raise OAuthError("invalid_client", "Missing client_id.", status=401)
    client = oauth_repository.get_client_by_client_id(client_id)
    if not client or not bool(client.is_active):
        raise OAuthError("invalid_client", "Invalid or inactive client.", status=401)

    if client.is_confidential:
        if not client_secret or not client.client_secret_hash:
            raise OAuthError("invalid_client", "Client secret is required.", status=401)
        if not check_password_hash(client.client_secret_hash, client_secret):
            raise OAuthError("invalid_client", "Invalid client secret.", status=401)

    return client


def exchange_code_for_token(
    *,
    client_id: str,
    client_secret: str | None,
    code: str,
    code_verifier: str,
    redirect_uri: str,
) -> IssuedOAuthToken:
    client = authenticate_client_credentials(
        client_id=client_id,
        client_secret=client_secret,
    )

    if not code:
        raise OAuthError("invalid_request", "Missing authorization code.")
    if not code_verifier:
        raise OAuthError("invalid_request", "Missing PKCE code_verifier.")

    code_hash = hash_secret(code)
    auth_code = oauth_repository.get_authorization_code_by_hash(code_hash)
    if not auth_code:
        raise OAuthError("invalid_grant", "Authorization code is invalid.")

    if auth_code.client_id != client.id:
        raise OAuthError("invalid_grant", "Authorization code was issued to a different client.")

    if auth_code.is_used:
        # Potential code replay attack - revoke token family for safety
        db.session.rollback()
        raise OAuthError("invalid_grant", "Authorization code has already been used.")

    now = datetime.utcnow()
    if auth_code.is_expired(now):
        oauth_repository.mark_authorization_code_used(auth_code)
        db.session.commit()
        raise OAuthError("invalid_grant", "Authorization code has expired.")

    if auth_code.redirect_uri != redirect_uri.strip():
        raise OAuthError("invalid_grant", "redirect_uri does not match original authorization request.")

    if not verify_pkce(
        code_verifier=code_verifier,
        code_challenge=auth_code.code_challenge,
        method=auth_code.code_challenge_method,
    ):
        raise OAuthError("invalid_grant", "PKCE verification failed.")

    oauth_repository.mark_authorization_code_used(auth_code)

    raw_access_token = f"flama_mcp_oa_{secrets.token_urlsafe(32)}"
    raw_refresh_token = f"flama_mcp_rt_{secrets.token_urlsafe(32)}"
    access_token_hash = hash_secret(raw_access_token)
    refresh_token_hash = hash_secret(raw_refresh_token)

    access_expires_at = now + timedelta(seconds=ACCESS_TOKEN_EXPIRY_SECONDS)
    refresh_expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)
    scopes = auth_code.get_scopes()

    oauth_repository.create_oauth_access_token(
        user_id=auth_code.user_id,
        client_id=client.id,
        name=f"OAuth ({client.client_name})",
        token_hash=access_token_hash,
        refresh_token_hash=refresh_token_hash,
        scopes=scopes,
        expires_at=access_expires_at,
        refresh_token_expires_at=refresh_expires_at,
    )
    db.session.commit()

    return IssuedOAuthToken(
        access_token=raw_access_token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
        refresh_token=raw_refresh_token,
        scope=" ".join(scopes),
    )


def refresh_access_token(
    *,
    client_id: str,
    client_secret: str | None,
    refresh_token: str,
    scope: str | None = None,
) -> IssuedOAuthToken:
    client = authenticate_client_credentials(
        client_id=client_id,
        client_secret=client_secret,
    )

    if not refresh_token:
        raise OAuthError("invalid_request", "Missing refresh_token.")

    rt_hash = hash_secret(refresh_token)
    token_row = oauth_repository.get_token_by_refresh_token_hash(rt_hash)
    if not token_row:
        raise OAuthError("invalid_grant", "Invalid refresh token.")

    if token_row.client_id != client.id:
        raise OAuthError("invalid_grant", "Refresh token was issued to a different client.")

    if bool(token_row.revoked):
        raise OAuthError("invalid_grant", "Refresh token has been revoked.")

    now = datetime.utcnow()
    if token_row.refresh_token_expires_at is not None and token_row.refresh_token_expires_at <= now:
        raise OAuthError("invalid_grant", "Refresh token has expired.")

    # Generate new access token and rotate refresh token
    new_access_token = f"flama_mcp_oa_{secrets.token_urlsafe(32)}"
    new_refresh_token = f"flama_mcp_rt_{secrets.token_urlsafe(32)}"

    token_row.token_hash = hash_secret(new_access_token)
    token_row.refresh_token_hash = hash_secret(new_refresh_token)
    token_row.expires_at = now + timedelta(seconds=ACCESS_TOKEN_EXPIRY_SECONDS)
    token_row.refresh_token_expires_at = now + timedelta(days=REFRESH_TOKEN_EXPIRY_DAYS)
    token_row.last_used_at = now

    scopes = json.loads(token_row.scopes) if token_row.scopes else list(DEFAULT_SCOPES)
    db.session.add(token_row)
    db.session.commit()

    return IssuedOAuthToken(
        access_token=new_access_token,
        token_type="Bearer",
        expires_in=ACCESS_TOKEN_EXPIRY_SECONDS,
        refresh_token=new_refresh_token,
        scope=" ".join(scopes),
    )


def revoke_token(
    *,
    client_id: str,
    client_secret: str | None,
    token: str,
    token_type_hint: str | None = None,
) -> bool:
    client = authenticate_client_credentials(
        client_id=client_id,
        client_secret=client_secret,
    )
    if not token:
        return True

    thash = hash_secret(token)
    token_row = None
    if token_type_hint == "refresh_token":
        token_row = oauth_repository.get_token_by_refresh_token_hash(thash)
    elif token_type_hint == "access_token":
        token_row = oauth_repository.get_token_by_hash(thash)

    if not token_row:
        token_row = oauth_repository.get_token_by_hash(thash) or oauth_repository.get_token_by_refresh_token_hash(thash)

    if token_row and token_row.client_id == client.id:
        token_row.revoked = True
        db.session.add(token_row)
        db.session.commit()
    return True
