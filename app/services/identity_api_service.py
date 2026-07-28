"""Application service for REST session and identity use cases."""

from __future__ import annotations

from typing import Any

from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.services import login_rate_limit_service
from app.services.auth_service import register_user_and_commit
from app.services.rest_api_service import build_session_payload
from app.utils.redirects import resolve_safe_next_url
from models import db
from models.user import User


class IdentityApiError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int,
        field: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field
        self.extras = extras or {}


def session_payload() -> dict[str, Any]:
    return build_session_payload(current_user)


def logout_session() -> dict[str, Any]:
    logout_user()
    return build_session_payload(current_user)


def register_account(
    *,
    payload: dict[str, Any],
    authenticated: bool,
) -> tuple[dict[str, Any], int]:
    if authenticated:
        raise IdentityApiError(
            "ALREADY_AUTHENTICATED",
            "You are already signed in.",
            status=409,
        )

    email = str(payload.get("email") or "").strip().lower()
    username = str(payload.get("username") or "").strip()
    password = str(payload.get("password") or "")
    confirm_password = str(payload.get("confirm_password") or "")
    if not email:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Email is required.",
            status=400,
            field="email",
        )
    if not username:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Username is required.",
            status=400,
            field="username",
        )
    if not password:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Password is required.",
            status=400,
            field="password",
        )
    if password != confirm_password:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Password confirmation does not match.",
            status=400,
            field="confirm_password",
        )
    if username.lower() == email:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Username must not be the same as email.",
            status=400,
            field="username",
        )
    if User.query.filter(
        (User.email == email) | (User.username == username)
    ).first() is not None:
        raise IdentityApiError(
            "CONFLICT",
            "Email or username already exists.",
            status=409,
        )

    try:
        user = register_user_and_commit(email, username, password)
    except IntegrityError as exc:
        db.session.rollback()
        raise IdentityApiError(
            "CONFLICT",
            "Email or username already exists.",
            status=409,
        ) from exc
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise IdentityApiError(
            "DB_ERROR",
            "Could not create the user.",
            status=500,
        ) from exc

    return {
        "created": True,
        "user": {
            "id": int(user.id),
            "email": str(user.email),
            "username": str(user.username),
        },
    }, 201


def login_account(
    *,
    payload: dict[str, Any],
    authenticated: bool,
    remote_addr: str | None,
) -> dict[str, Any]:
    if authenticated:
        return {
            **build_session_payload(current_user),
            "next_url": resolve_safe_next_url(
                None,
                default_endpoint="main.dashboard",
            ),
        }

    email = str(payload.get("email") or "").strip().lower()
    password = str(payload.get("password") or "")
    if not email:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Email is required.",
            status=400,
            field="email",
        )
    if not password:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Password is required.",
            status=400,
            field="password",
        )

    lockout_remaining = login_rate_limit_service.get_lockout_remaining(
        email=email,
        remote_addr=remote_addr,
    )
    if lockout_remaining > 0:
        raise IdentityApiError(
            "LOGIN_RATE_LIMITED",
            "Too many login attempts. Please try again later.",
            status=429,
            extras={"retry_after_seconds": int(lockout_remaining)},
        )

    user = User.query.filter_by(email=email).first()
    if user is None or not user.check_password(password):
        login_rate_limit_service.register_failure(
            email=email,
            remote_addr=remote_addr,
        )
        raise IdentityApiError(
            "INVALID_CREDENTIALS",
            "Invalid email or password.",
            status=401,
        )
    if not login_user(user):
        login_rate_limit_service.register_failure(
            email=email,
            remote_addr=remote_addr,
        )
        raise IdentityApiError(
            "USER_DISABLED",
            "This account is disabled.",
            status=403,
        )

    login_rate_limit_service.register_success(
        email=email,
        remote_addr=remote_addr,
    )
    return {
        **build_session_payload(current_user),
        "next_url": resolve_safe_next_url(
            payload.get("next"),
            default_endpoint="main.dashboard",
        ),
    }
