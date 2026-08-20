"""Repository for OAuth 2.1 clients, authorization codes, and tokens."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Iterable
import json

from models import db
from models.mcp_access_token import McpAccessToken
from models.oauth_authorization_code import OAuthAuthorizationCode
from models.oauth_client import OAuthClient
from models.user import User


def get_client_by_client_id(client_id: str) -> OAuthClient | None:
    norm_id = str(client_id or "").strip()
    if not norm_id:
        return None
    return OAuthClient.query.filter_by(client_id=norm_id, is_active=True).first()


def get_client_by_id(client_pk: int) -> OAuthClient | None:
    return db.session.get(OAuthClient, client_pk)


def list_clients(*, limit: int = 50) -> list[OAuthClient]:
    return OAuthClient.query.order_by(OAuthClient.created_at.desc()).limit(limit).all()


def create_client(
    *,
    client_id: str,
    client_name: str,
    client_secret_hash: str | None = None,
    client_uri: str | None = None,
    redirect_uris: Iterable[str] | None = None,
    is_confidential: bool = True,
    is_active: bool = True,
) -> OAuthClient:
    uris = [str(u).strip() for u in (redirect_uris or []) if str(u).strip()]
    client = OAuthClient(
        client_id=client_id.strip(),
        client_name=client_name.strip(),
        client_secret_hash=client_secret_hash,
        client_uri=client_uri.strip() if client_uri else None,
        redirect_uris=json.dumps(uris, ensure_ascii=False),
        is_confidential=is_confidential,
        is_active=is_active,
    )
    db.session.add(client)
    return client


def update_client(
    client: OAuthClient,
    *,
    client_name: str | None = None,
    client_secret_hash: object = ...,
    client_uri: object = ...,
    redirect_uris: Iterable[str] | None = None,
    is_confidential: bool | None = None,
    is_active: bool | None = None,
) -> OAuthClient:
    if client_name is not None:
        client.client_name = client_name.strip()
    if client_secret_hash is not ...:
        client.client_secret_hash = client_secret_hash
    if client_uri is not ...:
        client.client_uri = str(client_uri).strip() if client_uri else None
    if redirect_uris is not None:
        uris = [str(u).strip() for u in redirect_uris if str(u).strip()]
        client.redirect_uris = json.dumps(uris, ensure_ascii=False)
    if is_confidential is not None:
        client.is_confidential = is_confidential
    if is_active is not None:
        client.is_active = is_active
    db.session.add(client)
    return client



def create_authorization_code(
    *,
    code_hash: str,
    client_id: int,
    user_id: int,
    redirect_uri: str,
    scopes: Iterable[str],
    code_challenge: str,
    code_challenge_method: str = "S256",
    expires_at: datetime,
) -> OAuthAuthorizationCode:
    norm_scopes = [str(s).strip() for s in scopes if str(s).strip()]
    auth_code = OAuthAuthorizationCode(
        code_hash=code_hash,
        client_id=client_id,
        user_id=user_id,
        redirect_uri=redirect_uri.strip(),
        scopes=json.dumps(norm_scopes, ensure_ascii=False),
        code_challenge=code_challenge.strip(),
        code_challenge_method=code_challenge_method.strip(),
        expires_at=expires_at,
        is_used=False,
    )
    db.session.add(auth_code)
    return auth_code


def get_authorization_code_by_hash(code_hash: str) -> OAuthAuthorizationCode | None:
    return OAuthAuthorizationCode.query.filter_by(code_hash=code_hash).first()


def mark_authorization_code_used(code: OAuthAuthorizationCode) -> None:
    code.is_used = True
    db.session.add(code)


def create_oauth_access_token(
    *,
    user_id: int,
    client_id: int | None,
    name: str,
    token_hash: str,
    refresh_token_hash: str | None,
    scopes: Iterable[str],
    expires_at: datetime | None,
    refresh_token_expires_at: datetime | None,
    max_requests: int = 1_000_000,
) -> McpAccessToken:
    norm_scopes = [str(s).strip() for s in scopes if str(s).strip()]
    token_row = McpAccessToken(
        user_id=user_id,
        client_id=client_id,
        name=name.strip() or "OAuth MCP Token",
        token_hash=token_hash,
        refresh_token_hash=refresh_token_hash,
        scopes=json.dumps(norm_scopes, ensure_ascii=False),
        expires_at=expires_at,
        refresh_token_expires_at=refresh_token_expires_at,
        max_requests=max_requests,
        used_requests=0,
        revoked=False,
    )
    db.session.add(token_row)
    return token_row


def get_token_by_refresh_token_hash(refresh_token_hash: str) -> McpAccessToken | None:
    return McpAccessToken.query.filter_by(refresh_token_hash=refresh_token_hash).first()


def get_token_by_hash(token_hash: str) -> McpAccessToken | None:
    return McpAccessToken.query.filter_by(token_hash=token_hash).first()


def get_user_by_id(user_id: int) -> User | None:
    return db.session.get(User, user_id)


def list_connected_apps_for_user(user_id: int) -> list[dict[str, Any]]:
    tokens = (
        McpAccessToken.query.filter(
            McpAccessToken.user_id == user_id,
            McpAccessToken.client_id.isnot(None),
            McpAccessToken.revoked.is_(False),
        )
        .order_by(McpAccessToken.created_at.desc())
        .all()
    )
    results: list[dict[str, Any]] = []
    seen_client_ids: set[int] = set()

    now = datetime.utcnow()
    for token in tokens:
        if token.client_id in seen_client_ids:
            continue
        if token.expires_at is not None and token.expires_at <= now:
            continue
        client = token.client
        if client:
            seen_client_ids.add(token.client_id)
            results.append(
                {
                    "client_id": client.client_id,
                    "client_name": client.client_name,
                    "client_uri": client.client_uri,
                    "authorized_at": token.created_at.isoformat() if token.created_at else None,
                    "last_used_at": token.last_used_at.isoformat() if token.last_used_at else None,
                    "token_id": token.id,
                }
            )
    return results


def revoke_tokens_for_user_client(*, user_id: int, client_id: str) -> int:
    client = get_client_by_client_id(client_id)
    if not client:
        return 0
    tokens = McpAccessToken.query.filter_by(
        user_id=user_id,
        client_id=client.id,
        revoked=False,
    ).all()
    for t in tokens:
        t.revoked = True
        db.session.add(t)
    db.session.commit()
    return len(tokens)

