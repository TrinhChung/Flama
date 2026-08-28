"""Google OAuth 2.0 / OpenID Connect authentication service."""

from __future__ import annotations

import base64
from datetime import datetime, timezone
import json
import logging
import os
import re
import secrets
from typing import Any
import urllib.parse
import urllib.request

from flask import current_app, request, url_for
from sqlalchemy.exc import IntegrityError

from app.services.user_roles import ensure_default_user_roles
from models import db
from models.user import User
from models.user_identity import UserIdentity

logger = logging.getLogger(__name__)

GOOGLE_DISCOVERY_URL = "https://accounts.google.com/.well-known/openid-configuration"
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"


class GoogleAuthError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        extras: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.extras = extras or {}


def get_google_client_config() -> tuple[str, str]:
    """Retrieve Client ID and Client Secret from Flask app config or environment."""
    client_id = (
        current_app.config.get("GOOGLE_OAUTH_CLIENT_ID")
        or os.environ.get("GOOGLE_OAUTH_CLIENT_ID")
        or ""
    ).strip()
    client_secret = (
        current_app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
        or os.environ.get("GOOGLE_OAUTH_CLIENT_SECRET")
        or ""
    ).strip()
    return client_id, client_secret


def get_redirect_uri() -> str:
    """Determine the Google OAuth redirect URI."""
    configured = (
        current_app.config.get("GOOGLE_OAUTH_REDIRECT_URI")
        or os.environ.get("GOOGLE_OAUTH_REDIRECT_URI")
        or ""
    ).strip()
    if configured:
        return configured
    return url_for("auth.google_callback", _external=True)


def build_google_auth_url(next_url: str | None = None) -> tuple[str, str, str]:
    """Generate state, nonce, and authorization URL for Google Sign-In.

    Returns:
        tuple[str, str, str]: (auth_url, state, nonce)
    """
    client_id, _ = get_google_client_config()
    if not client_id:
        raise GoogleAuthError(
            "CONFIG_ERROR",
            "Google OAuth Client ID is not configured on the server.",
            status=500,
        )

    state = secrets.token_urlsafe(32)
    nonce = secrets.token_urlsafe(32)
    redirect_uri = get_redirect_uri()

    params = {
        "client_id": client_id,
        "response_type": "code",
        "scope": "openid email profile",
        "redirect_uri": redirect_uri,
        "state": state,
        "nonce": nonce,
        "prompt": "select_account",
    }
    auth_url = f"{GOOGLE_AUTH_ENDPOINT}?{urllib.parse.urlencode(params)}"
    return auth_url, state, nonce


def exchange_code_for_tokens(code: str, redirect_uri: str) -> dict[str, Any]:
    """Exchange authorization code for tokens via Google OAuth token endpoint."""
    client_id, client_secret = get_google_client_config()
    if not client_id or not client_secret:
        raise GoogleAuthError(
            "CONFIG_ERROR",
            "Google OAuth credentials are not properly configured.",
            status=500,
        )

    data = urllib.parse.urlencode(
        {
            "code": code,
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "grant_type": "authorization_code",
        }
    ).encode("utf-8")

    req = urllib.request.Request(
        GOOGLE_TOKEN_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/x-www-form-urlencoded"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read().decode("utf-8")
            return json.loads(body)
    except urllib.error.HTTPError as err:
        error_body = ""
        try:
            error_body = err.read().decode("utf-8")
        except Exception:
            pass
        logger.error("Google token exchange failed: HTTP %s - %s", err.code, error_body)
        raise GoogleAuthError(
            "TOKEN_EXCHANGE_FAILED",
            "Failed to exchange authorization code with Google.",
            status=400,
        ) from err
    except Exception as exc:
        logger.exception("Google token exchange request failed: %s", exc)
        raise GoogleAuthError(
            "NETWORK_ERROR",
            "Failed to communicate with Google authentication servers.",
            status=502,
        ) from exc


def parse_unverified_jwt(id_token: str) -> tuple[dict[str, Any], dict[str, Any]]:
    """Decode JWT header and payload without signature verification."""
    try:
        parts = id_token.split(".")
        if len(parts) != 3:
            raise ValueError("Invalid JWT format.")

        def _b64_decode(data: str) -> bytes:
            padding = "=" * (4 - len(data) % 4)
            return base64.urlsafe_b64decode(data + padding)

        header = json.loads(_b64_decode(parts[0]).decode("utf-8"))
        payload = json.loads(_b64_decode(parts[1]).decode("utf-8"))
        return header, payload
    except Exception as exc:
        raise GoogleAuthError(
            "INVALID_TOKEN",
            "Malformed ID token received from provider.",
            status=400,
        ) from exc


def verify_id_token(
    id_token: str,
    *,
    expected_nonce: str | None = None,
    clock_skew_seconds: int = 60,
) -> dict[str, Any]:
    """Verify Google OIDC ID token claims.

    Claims checked:
    - iss in ["https://accounts.google.com", "accounts.google.com"]
    - aud matches configured GOOGLE_OAUTH_CLIENT_ID
    - exp > current_time
    - nonce matches expected_nonce if provided
    - sub is present
    - email_verified is true
    """
    client_id, _ = get_google_client_config()
    _, payload = parse_unverified_jwt(id_token)

    # 1. Issuer check
    iss = payload.get("iss")
    if iss not in ("https://accounts.google.com", "accounts.google.com"):
        raise GoogleAuthError(
            "INVALID_ISSUER",
            "ID token issuer does not match Google.",
            status=400,
        )

    # 2. Audience check
    aud = payload.get("aud")
    if aud != client_id and client_id:
        raise GoogleAuthError(
            "INVALID_AUDIENCE",
            "ID token audience does not match application client ID.",
            status=400,
        )

    # 3. Expiration check
    exp = payload.get("exp")
    if not exp or not isinstance(exp, (int, float)):
        raise GoogleAuthError(
            "INVALID_EXPIRATION",
            "ID token is missing expiration claim.",
            status=400,
        )

    now = datetime.now(timezone.utc).timestamp()
    if now > exp + clock_skew_seconds:
        raise GoogleAuthError(
            "EXPIRED_TOKEN",
            "ID token has expired.",
            status=400,
        )

    # 4. Nonce check
    if expected_nonce:
        token_nonce = payload.get("nonce")
        if token_nonce != expected_nonce:
            raise GoogleAuthError(
                "INVALID_NONCE",
                "ID token nonce mismatch.",
                status=400,
            )

    # 5. Subject check
    sub = payload.get("sub")
    if not sub:
        raise GoogleAuthError(
            "MISSING_SUB",
            "ID token subject claim is missing.",
            status=400,
        )

    # 6. Email verified check
    email_verified = payload.get("email_verified")
    if email_verified is not True and str(email_verified).lower() != "true":
        raise GoogleAuthError(
            "EMAIL_NOT_VERIFIED",
            "Google account email is not verified.",
            status=400,
        )

    return payload


def _generate_unique_username(base_name: str) -> str:
    """Generate a valid, unique username based on the Google user's name or email."""
    cleaned = re.sub(r"[^a-zA-Z0-9_]", "_", base_name).strip("_")
    if not cleaned or len(cleaned) < 2:
        cleaned = f"user_{secrets.token_hex(4)}"

    cleaned = cleaned[:130]

    candidate = cleaned
    counter = 1
    while User.query.filter_by(username=candidate).first() is not None:
        candidate = f"{cleaned}_{counter}"
        counter += 1

    return candidate


def resolve_or_create_user(id_token_claims: dict[str, Any]) -> tuple[User, str]:
    """Resolve Flama User from Google ID token claims or provision new user.

    Returns:
        tuple[User, str]: (user, action_taken) where action_taken is 'login', 'linked', or 'created'.
    """
    sub = str(id_token_claims.get("sub") or "").strip()
    email = str(id_token_claims.get("email") or "").strip().lower()
    name = str(id_token_claims.get("name") or "").strip()
    picture = str(id_token_claims.get("picture") or "").strip()

    if not sub:
        raise GoogleAuthError("MISSING_SUB", "Identity sub is missing.", status=400)
    if not email:
        raise GoogleAuthError("MISSING_EMAIL", "Identity email is missing.", status=400)

    # Step 1: Check existing UserIdentity mapping by (provider='google', sub)
    identity = UserIdentity.query.filter_by(provider="google", provider_sub=sub).first()
    if identity and identity.user:
        user = identity.user
        if user.is_disabled:
            logger.warning("Google login attempt for disabled user_id=%s", user.id)
            raise GoogleAuthError(
                "DISABLED_ACCOUNT",
                "Tài khoản của bạn đã bị vô hiệu hóa.",
                status=403,
            )
        # Update provider_email if changed
        if identity.provider_email != email:
            identity.provider_email = email
            db.session.commit()
        return user, "login"

    # Step 2: Account linking - Check if user exists by exact email match
    user = User.query.filter_by(email=email).first()
    if user:
        if user.is_disabled:
            logger.warning("Google login attempt to link to disabled user_id=%s", user.id)
            raise GoogleAuthError(
                "DISABLED_ACCOUNT",
                "Tài khoản của bạn đã bị vô hiệu hóa.",
                status=403,
            )

        # Create identity mapping
        new_identity = UserIdentity(
            user_id=user.id,
            provider="google",
            provider_sub=sub,
            provider_email=email,
        )
        db.session.add(new_identity)

        if not user.email_verified_at:
            user.email_verified_at = datetime.now(timezone.utc)
            user.email_verification_source = "google"

        try:
            db.session.commit()
        except IntegrityError:
            db.session.rollback()
            # Retry fetching identity in case of race condition
            identity = UserIdentity.query.filter_by(provider="google", provider_sub=sub).first()
            if identity and identity.user:
                return identity.user, "login"
            raise GoogleAuthError(
                "CONCURRENCY_ERROR",
                "Dữ liệu liên kết tài khoản bị xung đột, vui lòng thử lại.",
                status=409,
            )

        logger.info("Linked Google sub=%s to existing user_id=%s email=%s", sub, user.id, email)
        return user, "linked"

    # Step 3: Account provisioning - Create new user
    base_name = name or email.split("@")[0]
    username = _generate_unique_username(base_name)

    existing_user_count = User.query.count()
    roles = ensure_default_user_roles(db.session)

    user = User(
        email=email,
        username=username,
        display_name=name or username,
        avatar_url=picture or None,
        password_hash=None,  # Social-only user
        email_verified_at=datetime.now(timezone.utc),
        email_verification_source="google",
    )
    if existing_user_count == 0 and roles.get("admin"):
        user.role_id = roles["admin"].id
        user.is_admin = True
    elif roles.get("regular"):
        user.role_id = roles["regular"].id
        user.is_admin = bool(roles["regular"].is_admin)
    else:
        user.is_admin = existing_user_count == 0

    db.session.add(user)

    try:
        db.session.flush()

        new_identity = UserIdentity(
            user_id=user.id,
            provider="google",
            provider_sub=sub,
            provider_email=email,
        )
        db.session.add(new_identity)
        db.session.commit()
    except IntegrityError as exc:
        db.session.rollback()
        logger.exception("Race condition provisioning user via Google: %s", exc)
        # Check if user was created concurrently
        user = User.query.filter_by(email=email).first()
        if user:
            return user, "login"
        raise GoogleAuthError(
            "REGISTRATION_FAILED",
            "Không thể tạo tài khoản người dùng mới.",
            status=500,
        ) from exc
    except Exception as exc:
        db.session.rollback()
        logger.exception("Failed to provision Google user: %s", exc)
        raise GoogleAuthError(
            "SERVER_ERROR",
            "Đã xảy ra lỗi khi khởi tạo tài khoản.",
            status=500,
        ) from exc

    logger.info("Provisioned new Google user_id=%s email=%s username=%s", user.id, email, username)
    return user, "created"
