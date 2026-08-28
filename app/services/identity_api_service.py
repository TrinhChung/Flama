"""Application service for REST session and identity use cases."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import secrets
from typing import Any

from flask_login import current_user, login_user, logout_user
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.email import (
    EmailCategory,
    TemplateKey,
    TransactionalEmailRequest,
    get_email_service,
    mask_email,
)
from app.services import login_rate_limit_service, password_reset_rate_limit_service
from app.services.auth_service import register_user_and_commit
from app.services.rest_api_service import build_session_payload
from app.utils.redirects import resolve_safe_next_url
from app.validators.password import validate_password_policy
from models import db
from models.password_reset_token import PasswordResetToken
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
    policy_error = validate_password_policy(password)
    if policy_error:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            policy_error,
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


PASSWORD_RESET_GENERIC_MESSAGE = (
    "Nếu địa chỉ email tồn tại trong hệ thống, chúng tôi đã gửi liên kết "
    "hướng dẫn đặt lại mật khẩu đến hộp thư của bạn."
)
UTC = timezone.utc


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def request_password_reset(
    *, payload: dict[str, Any], remote_addr: str | None = None
) -> dict[str, Any]:
    from flask import current_app

    email = str(payload.get("email") or "").strip().lower()
    if not email:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Email is required.",
            status=400,
            field="email",
        )

    allowed, retry_after = password_reset_rate_limit_service.consume(
        email=email,
        remote_addr=remote_addr,
    )
    if not allowed:
        raise IdentityApiError(
            "PASSWORD_RESET_RATE_LIMITED",
            "Too many password reset requests. Please try again later.",
            status=429,
            extras={"retry_after_seconds": retry_after},
        )

    user = User.query.filter_by(email=email).first()
    if user is not None and getattr(user, "is_disabled", False) is False:
        ttl_minutes = max(
            int(current_app.config.get("PASSWORD_RESET_TOKEN_TTL_MINUTES", 30)),
            1,
        )
        now = _utcnow()
        token = secrets.token_urlsafe(32)
        token_row = PasswordResetToken(
            user_id=int(user.id),
            token_hash=_token_digest(token),
            created_at=now,
            expires_at=now + timedelta(minutes=ttl_minutes),
        )
        try:
            PasswordResetToken.query.filter(
                PasswordResetToken.user_id == int(user.id),
                PasswordResetToken.used_at.is_(None),
                PasswordResetToken.revoked_at.is_(None),
            ).update({PasswordResetToken.revoked_at: now}, synchronize_session=False)
            db.session.add(token_row)
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            current_app.logger.error(
                "Failed to persist password reset request for recipient=%s: %s",
                mask_email(email),
                exc,
            )
            return {"success": True, "message": PASSWORD_RESET_GENERIC_MESSAGE}

        public_url = str(current_app.config.get("PUBLIC_APP_URL") or "").rstrip("/")
        if not public_url:
            current_app.logger.error(
                "Password reset email skipped because PUBLIC_APP_URL is not configured; recipient=%s",
                mask_email(email),
            )
            return {"success": True, "message": PASSWORD_RESET_GENERIC_MESSAGE}
        reset_url = f"{public_url}/reset-password?token={token}"
        current_app.logger.info("\n=======================================================\n[LOCAL DEV] PASSWORD RESET LINK FOR %s:\n%s\n=======================================================", user.email, reset_url)


        try:
            get_email_service().send(
                TransactionalEmailRequest(
                    recipient=str(user.email),
                    template_key=TemplateKey.SECURITY_PASSWORD_RESET,
                    category=EmailCategory.SECURITY_PASSWORD_RESET,
                    variables={
                        "reset_url": reset_url,
                        "recipient_name": str(user.username),
                        "expires_in_minutes": ttl_minutes,
                    },
                    correlation_id=f"password-reset:{token_row.id}",
                )
            )
        except Exception as exc:
            current_app.logger.error(
                "Failed to send password reset email to recipient=%s: %s",
                mask_email(email),
                exc,
            )

    return {"success": True, "message": PASSWORD_RESET_GENERIC_MESSAGE}


def reset_password_with_token(*, payload: dict[str, Any]) -> dict[str, Any]:
    from flask import current_app

    token = str(payload.get("token") or "").strip()
    new_password = str(payload.get("new_password") or payload.get("password") or "")
    confirm_password = str(payload.get("confirm_password") or "")

    if not token:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Token is required.",
            status=400,
            field="token",
        )
    if not new_password:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "New password is required.",
            status=400,
            field="new_password",
        )
    policy_error = validate_password_policy(new_password)
    if policy_error:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            policy_error,
            status=400,
            field="new_password",
        )
    if not confirm_password:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Password confirmation is required.",
            status=400,
            field="confirm_password",
        )
    if new_password != confirm_password:
        raise IdentityApiError(
            "VALIDATION_ERROR",
            "Password confirmation does not match.",
            status=400,
            field="confirm_password",
        )

    token_row = PasswordResetToken.query.filter_by(token_hash=_token_digest(token)).with_for_update().first()
    if token_row is None or token_row.revoked_at is not None:
        raise IdentityApiError(
            "INVALID_TOKEN",
            "Liên kết đặt lại mật khẩu không hợp lệ hoặc đã bị thay đổi.",
            status=400,
        )
    if token_row.used_at is not None:
        raise IdentityApiError(
            "TOKEN_USED",
            "Liên kết đặt lại mật khẩu đã được sử dụng.",
            status=400,
        )
    now = _utcnow()
    if token_row.expires_at <= now:
        raise IdentityApiError(
            "TOKEN_EXPIRED",
            "Liên kết đặt lại mật khẩu đã hết hạn. Vui lòng gửi lại yêu cầu mới.",
            status=400,
        )

    user = db.session.get(User, token_row.user_id)
    if user is None:
        raise IdentityApiError(
            "USER_NOT_FOUND",
            "Không tìm thấy tài khoản liên quan.",
            status=404,
        )

    try:
        user.set_password(new_password)
        token_row.used_at = now
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise IdentityApiError(
            "DB_ERROR",
            "Không thể cập nhật mật khẩu.",
            status=500,
        ) from exc

    try:
        get_email_service().send(
            TransactionalEmailRequest(
                recipient=str(user.email),
                template_key=TemplateKey.SECURITY_PASSWORD_CHANGED,
                category=EmailCategory.SECURITY_PASSWORD_CHANGED,
                variables={
                    "recipient_name": str(user.username),
                },
            )
        )
    except Exception as exc:
        current_app.logger.warning(
            "Failed to send password_changed email to recipient=%s: %s",
            mask_email(user.email),
            exc,
        )

    return {
        "success": True,
        "message": "Đặt lại mật khẩu thành công. Bạn có thể đăng nhập ngay bây giờ.",
    }

