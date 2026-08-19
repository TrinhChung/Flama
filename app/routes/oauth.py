"""OAuth 2.1 routes and discovery endpoints for Flama Remote MCP."""

from __future__ import annotations

import base64
import html
import logging
from typing import Any
from urllib.parse import quote, unquote

from flask import Blueprint, Response, jsonify, redirect, request, url_for
from flask_login import current_user, login_required

from models import db
from app.repositories import oauth_repository
from app.services import mcp_scope_service, oauth_service
from app.services.oauth_service import OAuthError

logger = logging.getLogger(__name__)

oauth_bp = Blueprint("oauth", __name__)


def _extract_client_credentials() -> tuple[str, str | None]:
    """Extract client_id and client_secret from Authorization header or body."""
    auth_header = request.headers.get("Authorization", "").strip()
    if auth_header.lower().startswith("basic "):
        try:
            b64_creds = auth_header[6:].strip()
            decoded = base64.b64decode(b64_creds).decode("utf-8")
            client_id, _, client_secret = decoded.partition(":")
            return client_id.strip(), client_secret.strip() if client_secret else None
        except Exception:
            pass

    # Fallback to POST body form/json
    body = request.form or request.get_json(silent=True) or {}
    client_id = str(body.get("client_id") or "").strip()
    client_secret = body.get("client_secret")
    if client_secret is not None:
        client_secret = str(client_secret).strip()
    return client_id, client_secret


# --- Discovery Endpoints ---


@oauth_bp.get("/.well-known/oauth-protected-resource")
def oauth_protected_resource():
    """RFC 9728 Protected Resource Metadata."""
    return jsonify(oauth_service.get_protected_resource_metadata(request))


@oauth_bp.get("/.well-known/oauth-authorization-server")
@oauth_bp.get("/.well-known/openid-configuration")
def oauth_authorization_server_metadata():
    """RFC 8414 Authorization Server Metadata."""
    return jsonify(oauth_service.get_authorization_server_metadata(request))


# --- Consent API Endpoints for React SPA ---

SCOPE_METADATA = mcp_scope_service.SCOPE_METADATA


@oauth_bp.get("/api/oauth/consent-info")
def consent_info():
    """Return metadata for the React SPA OAuth Consent screen."""
    client_id = str(request.args.get("client_id") or "").strip()
    scope_str = request.args.get("scope")

    client = oauth_repository.get_client_by_client_id(client_id)
    if not client:
        return (
            jsonify({"error": "invalid_client", "error_description": "Unknown client_id"}),
            400,
        )

    try:
        requested_scopes = list(oauth_service.normalize_scopes(scope_str))
    except ValueError as err:
        return (
            jsonify({"error": "invalid_scope", "error_description": str(err)}),
            400,
        )

    scopes_data = []
    for sc in requested_scopes:
        info = SCOPE_METADATA.get(
            sc,
            {
                "id": sc,
                "title": sc,
                "desc": f"Quyền truy cập API: {sc}",
                "category": "Tùy chỉnh",
                "icon": "key",
            },
        )
        scopes_data.append(info)

    user_data = None
    if current_user.is_authenticated:
        user_data = {
            "id": current_user.id,
            "username": getattr(current_user, "username", "Tài khoản Flama"),
            "email": getattr(current_user, "email", "") or "",
        }

    return jsonify(
        {
            "client": {
                "client_id": client.client_id,
                "client_name": client.client_name,
                "client_uri": client.client_uri,
                "is_confidential": bool(client.is_confidential),
            },
            "scopes": scopes_data,
            "user": user_data,
        }
    )


@oauth_bp.post("/api/oauth/consent-decision")
def consent_decision():
    """Handle user approval or denial from the React SPA Consent UI."""
    if not current_user.is_authenticated:
        return (
            jsonify({"error": "unauthorized", "error_description": "User must be logged in"}),
            401,
        )

    if not bool(getattr(current_user, "is_active", True)):
        return (
            jsonify({"error": "access_denied", "error_description": "User account is disabled"}),
            403,
        )

    body = request.get_json(silent=True) or request.form or {}
    client_id = str(body.get("client_id") or "").strip()
    redirect_uri = str(body.get("redirect_uri") or "").strip()
    response_type = str(body.get("response_type") or "code").strip()
    scope = body.get("scope")
    state = body.get("state")
    code_challenge = body.get("code_challenge")
    code_challenge_method = body.get("code_challenge_method") or "S256"
    action = str(body.get("action") or "deny").strip().lower()

    try:
        client, scopes = oauth_service.validate_authorize_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            scope=scope,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
    except OAuthError as err:
        redirect_target = err.to_redirect_url()
        if redirect_target:
            return jsonify({"redirect_url": redirect_target}), 200
        return jsonify(err.to_dict()), err.status

    if action != "approve":
        err = OAuthError(
            "access_denied",
            "The user denied the authorization request.",
            redirect_uri=redirect_uri,
            state=state,
        )
        return jsonify({"redirect_url": err.to_redirect_url()}), 200

    try:
        raw_code = oauth_service.issue_authorization_code(
            client=client,
            user=current_user,
            redirect_uri=redirect_uri,
            scopes=scopes,
            code_challenge=code_challenge or "",
            code_challenge_method=code_challenge_method,
        )
        redirect_success = oauth_service.build_redirect_url(
            redirect_uri,
            {"code": raw_code},
            state=state,
        )
        return jsonify({"redirect_url": redirect_success}), 200
    except Exception as exc:
        logger.exception("Failed to issue authorization code via consent API: %s", exc)
        err = OAuthError(
            "server_error",
            "Internal server error issuing authorization code.",
            redirect_uri=redirect_uri,
            state=state,
        )
        return jsonify({"redirect_url": err.to_redirect_url()}), 200


# --- Core OAuth Endpoints ---


@oauth_bp.route("/oauth/authorize", methods=["GET", "POST"])
def authorize():
    """OAuth 2.1 Authorization Endpoint (with PKCE)."""
    params = request.args if request.method == "GET" else request.form

    client_id = str(params.get("client_id") or "").strip()
    redirect_uri = str(params.get("redirect_uri") or "").strip()
    response_type = str(params.get("response_type") or "code").strip()
    scope = params.get("scope")
    state = params.get("state")
    code_challenge = params.get("code_challenge")
    code_challenge_method = params.get("code_challenge_method") or "S256"

    try:
        client, scopes = oauth_service.validate_authorize_request(
            client_id=client_id,
            redirect_uri=redirect_uri,
            response_type=response_type,
            scope=scope,
            state=state,
            code_challenge=code_challenge,
            code_challenge_method=code_challenge_method,
        )
    except OAuthError as err:
        redirect_target = err.to_redirect_url()
        if redirect_target:
            return redirect(redirect_target)
        return jsonify(err.to_dict()), err.status

    # Require user authentication
    if not current_user.is_authenticated:
        # Redirect to login page and preserve the full authorization URL in 'next'
        auth_url = request.full_path
        login_url = f"/login?next={quote(auth_url, safe='')}"
        return redirect(login_url)

    if not bool(getattr(current_user, "is_active", True)):
        err = OAuthError("access_denied", "User account is disabled.", redirect_uri=redirect_uri, state=state)
        return redirect(err.to_redirect_url())

    if request.method == "GET":
        query_string = request.query_string.decode("utf-8") if request.query_string else ""
        consent_spa_url = f"/oauth/consent?{query_string}" if query_string else "/oauth/consent"
        return redirect(consent_spa_url)


    # POST: User Decision
    action = request.form.get("action", "deny").strip().lower()
    if action != "approve":
        err = OAuthError("access_denied", "The user denied the authorization request.", redirect_uri=redirect_uri, state=state)
        return redirect(err.to_redirect_url())

    # Issue Authorization Code
    try:
        raw_code = oauth_service.issue_authorization_code(
            client=client,
            user=current_user,
            redirect_uri=redirect_uri,
            scopes=scopes,
            code_challenge=code_challenge or "",
            code_challenge_method=code_challenge_method,
        )
        redirect_success = oauth_service.build_redirect_url(
            redirect_uri,
            {"code": raw_code},
            state=state,
        )
        return redirect(redirect_success)
    except Exception as exc:
        logger.exception("Failed to issue authorization code: %s", exc)
        err = OAuthError("server_error", "Internal server error issuing authorization code.", redirect_uri=redirect_uri, state=state)
        return redirect(err.to_redirect_url())


@oauth_bp.post("/oauth/token")
def token():
    """OAuth 2.1 Token Endpoint."""
    body = request.form if request.form else (request.get_json(silent=True) or {})
    grant_type = str(body.get("grant_type") or "").strip()
    client_id, client_secret = _extract_client_credentials()

    try:
        if grant_type == "authorization_code":
            code = str(body.get("code") or "").strip()
            code_verifier = str(body.get("code_verifier") or "").strip()
            redirect_uri = str(body.get("redirect_uri") or "").strip()

            issued = oauth_service.exchange_code_for_token(
                client_id=client_id,
                client_secret=client_secret,
                code=code,
                code_verifier=code_verifier,
                redirect_uri=redirect_uri,
            )
            resp = jsonify(issued.to_token_response())
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["Pragma"] = "no-cache"
            return resp

        if grant_type == "refresh_token":
            refresh_token = str(body.get("refresh_token") or "").strip()
            scope = body.get("scope")

            refreshed = oauth_service.refresh_access_token(
                client_id=client_id,
                client_secret=client_secret,
                refresh_token=refresh_token,
                scope=scope,
            )
            resp = jsonify(refreshed.to_token_response())
            resp.headers["Cache-Control"] = "no-store"
            resp.headers["Pragma"] = "no-cache"
            return resp

        raise OAuthError("unsupported_grant_type", f"Unsupported grant_type: {grant_type}")

    except OAuthError as err:
        resp = jsonify(err.to_dict())
        resp.status_code = err.status
        resp.headers["Cache-Control"] = "no-store"
        return resp


@oauth_bp.post("/oauth/revoke")
def revoke():
    """RFC 7009 Token Revocation Endpoint."""
    body = request.form if request.form else (request.get_json(silent=True) or {})
    token = str(body.get("token") or "").strip()
    token_type_hint = body.get("token_type_hint")
    client_id, client_secret = _extract_client_credentials()

    try:
        oauth_service.revoke_token(
            client_id=client_id,
            client_secret=client_secret,
            token=token,
            token_type_hint=token_type_hint,
        )
        return jsonify({}), 200
    except OAuthError as err:
        resp = jsonify(err.to_dict())
        resp.status_code = err.status
        return resp


@oauth_bp.get("/oauth/userinfo")
def userinfo():
    """OIDC UserInfo Endpoint."""
    from app.services import mcp_access_token_service, mcp_auth_service

    raw_token = mcp_auth_service.extract_raw_token(request=request)
    if not raw_token:
        return (
            jsonify(
                {
                    "error": "unauthorized",
                    "error_description": "Bearer token required",
                }
            ),
            401,
        )
    try:
        token_auth = mcp_access_token_service.authenticate_bearer_token(
            raw_token=raw_token
        )
        user = token_auth.user
        return jsonify(
            {
                "sub": str(user.id),
                "id": user.id,
                "username": user.username,
                "preferred_username": user.username,
                "email": user.email,
                "email_verified": True,
            }
        )
    except Exception as exc:
        return jsonify({"error": "invalid_token", "error_description": str(exc)}), 401


# --- Connected Apps & OAuth Management API ---


@oauth_bp.get("/api/oauth/endpoints-info")
def get_endpoints_info():
    """Return discovered URLs and suggested config for AI client setup."""
    base_url = oauth_service.get_base_url(request)
    return jsonify(
        {
            "base_url": base_url,
            "auth_url": f"{base_url}/oauth/authorize",
            "token_url": f"{base_url}/oauth/token",
            "resource_url": f"{base_url}/api/mcp",
            "userinfo_url": f"{base_url}/oauth/userinfo",
            "openid_config_url": f"{base_url}/.well-known/openid-configuration",
            "scopes": list(oauth_service.ALLOWED_SCOPES),
            "scopes_string": " ".join(sorted(oauth_service.ALLOWED_SCOPES)),
        }
    )


@oauth_bp.get("/api/oauth/clients")
@login_required
def list_oauth_clients():
    """List registered OAuth 2.1 clients."""
    try:
        clients = oauth_repository.list_clients(limit=50)
        return jsonify({"items": [c.to_dict() for c in clients]})
    except Exception as exc:
        logger.exception("Failed to list OAuth clients: %s", exc)
        db.session.rollback()
        return jsonify({"items": []})


@oauth_bp.post("/api/oauth/clients")
@login_required
def create_oauth_client():
    """Create or update a registered OAuth 2.1 client from UI."""
    payload = request.get_json(silent=True) or request.form or {}
    client_id = str(payload.get("client_id") or "").strip()
    client_name = str(payload.get("client_name") or "").strip()
    client_secret = payload.get("client_secret")
    raw_redirect_uris = payload.get("redirect_uris") or []

    if isinstance(raw_redirect_uris, str):
        redirect_uris = [
            u.strip() for u in raw_redirect_uris.splitlines() if u.strip()
        ]
    elif isinstance(raw_redirect_uris, list):
        redirect_uris = [str(u).strip() for u in raw_redirect_uris if str(u).strip()]
    else:
        redirect_uris = []

    if not client_id or not client_name:
        return (
            jsonify(
                {
                    "error": "VALIDATION_ERROR",
                    "message": "Client ID và Tên ứng dụng là bắt buộc.",
                }
            ),
            400,
        )

    if not redirect_uris:
        return (
            jsonify(
                {
                    "error": "VALIDATION_ERROR",
                    "message": "Cần ít nhất một Callback / Redirect URL do ứng dụng cung cấp.",
                }
            ),
            400,
        )

    try:
        client = oauth_service.register_oauth_client(
            client_id=client_id,
            client_name=client_name,
            client_secret=str(client_secret).strip() if client_secret else None,
            redirect_uris=redirect_uris,
            is_confidential=bool(client_secret and str(client_secret).strip()),
        )
        return jsonify({"success": True, "client": client.to_dict()}), 201
    except Exception as exc:
        logger.exception("Failed to create OAuth client: %s", exc)
        db.session.rollback()
        return (
            jsonify(
                {
                    "error": "DATABASE_ERROR",
                    "message": f"Không thể lưu OAuth Client: {exc}",
                }
            ),
            500,
        )


@oauth_bp.delete("/api/oauth/clients/<int:client_pk>")
@login_required
def delete_oauth_client(client_pk: int):
    """Delete a registered OAuth 2.1 client."""
    try:
        client = oauth_repository.get_client_by_id(client_pk)
        if not client:
            return jsonify({"error": "NOT_FOUND", "message": "Client không tồn tại."}), 404
        db.session.delete(client)
        db.session.commit()
        return jsonify({"success": True})
    except Exception as exc:
        logger.exception("Failed to delete OAuth client: %s", exc)
        db.session.rollback()
        return jsonify({"error": "DATABASE_ERROR", "message": str(exc)}), 500



@oauth_bp.get("/api/oauth/connected-apps")
@login_required
def list_connected_apps():
    """List OAuth applications authorized by the current user."""
    items = oauth_repository.list_connected_apps_for_user(current_user.id)
    return jsonify({"items": items})


@oauth_bp.post("/api/oauth/connected-apps/<client_id>/revoke")
@login_required
def revoke_connected_app(client_id: str):
    """Revoke all tokens issued for a specific client for the current user."""
    count = oauth_repository.revoke_tokens_for_user_client(
        user_id=current_user.id,
        client_id=client_id,
    )
    return jsonify({"success": True, "revoked_count": count})

