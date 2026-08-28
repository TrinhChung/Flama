"""Application service for email verification tokens, OTPs, and email dispatch."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import logging
import secrets
from typing import Any

from flask import current_app
from sqlalchemy.exc import SQLAlchemyError

from app.email import (
    EmailCategory,
    TemplateKey,
    TransactionalEmailRequest,
    get_email_service,
    mask_email,
)
from app.services import email_verification_rate_limit_service
from app.services.student_verification_service import (
    get_user_student_status,
    is_user_verified_student,
    normalize_email,
)
from models import db
from models.email_verification_token import EmailVerificationToken
from models.user import User

logger = logging.getLogger(__name__)
UTC = timezone.utc


class EmailVerificationError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        extras: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.field = field
        self.extras = extras or {}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _token_digest(token: str) -> str:
    return hashlib.sha256(token.strip().encode("utf-8")).hexdigest()


def request_email_verification(
    user: User,
    *,
    remote_addr: str | None = None,
) -> dict[str, Any]:
    """Generate a 6-digit OTP code and send a verification email to the user."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise EmailVerificationError(
            "AUTHENTICATION_REQUIRED",
            "Bạn cần đăng nhập để thực hiện thao tác này.",
            status=401,
        )

    if getattr(user, "is_disabled", False):
        raise EmailVerificationError(
            "USER_DISABLED",
            "Tài khoản của bạn đang bị vô hiệu hóa.",
            status=403,
        )

    user_email = normalize_email(user.email)
    if not user_email:
        raise EmailVerificationError(
            "EMAIL_REQUIRED",
            "Tài khoản chưa có địa chỉ email hợp lệ.",
            status=400,
            field="email",
        )

    # If email is already verified, inform the caller
    if user.email_verified_at is not None:
        student_status = get_user_student_status(user)
        return {
            "success": True,
            "already_verified": True,
            "message": "Địa chỉ email này đã được xác thực.",
            "student_status": student_status.value,
            "is_verified_student": is_user_verified_student(user),
        }

    # Rate limiting
    allowed, retry_after = email_verification_rate_limit_service.consume(
        email=user_email,
        remote_addr=remote_addr,
    )
    if not allowed:
        raise EmailVerificationError(
            "RATE_LIMITED",
            f"Vui lòng đợi {retry_after} giây trước khi yêu cầu gửi lại mã xác thực.",
            status=429,
            extras={"retry_after_seconds": retry_after},
        )

    ttl_minutes = max(
        int(current_app.config.get("EMAIL_VERIFICATION_TOKEN_TTL_MINUTES", 15)),
        1,
    )
    now = _utcnow()
    # Generate 6-digit secure numeric code
    otp_code = f"{secrets.randbelow(1000000):06d}"
    code_digest = _token_digest(otp_code)

    token_row = EmailVerificationToken(
        user_id=int(user.id),
        email=user_email,
        token_hash=code_digest,
        token_type="code",
        created_at=now,
        expires_at=now + timedelta(minutes=ttl_minutes),
    )

    try:
        # Revoke previous unused tokens for this user & email
        EmailVerificationToken.query.filter(
            EmailVerificationToken.user_id == int(user.id),
            EmailVerificationToken.used_at.is_(None),
            EmailVerificationToken.revoked_at.is_(None),
        ).update({EmailVerificationToken.revoked_at: now}, synchronize_session=False)

        db.session.add(token_row)
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error(
            "Failed to persist email verification token for user_id=%s recipient=%s: %s",
            user.id,
            mask_email(user_email),
            exc,
        )
        raise EmailVerificationError(
            "DB_ERROR",
            "Không thể khởi tạo mã xác thực. Vui lòng thử lại sau.",
            status=500,
        ) from exc

    current_app.logger.info(
        "\n=======================================================\n"
        "[LOCAL DEV] EMAIL VERIFICATION CODE FOR %s:\n%s\n"
        "=======================================================",
        user_email,
        otp_code,
    )

    try:
        get_email_service().send(
            TransactionalEmailRequest(
                recipient=user_email,
                template_key=TemplateKey.IDENTITY_EMAIL_VERIFICATION,
                category=EmailCategory.IDENTITY_EMAIL_VERIFICATION,
                variables={
                    "recipient_name": str(user.username or "bạn"),
                    "verification_code": otp_code,
                    "expires_in_minutes": ttl_minutes,
                },
                correlation_id=f"email-verify:{token_row.id}",
            )
        )
    except Exception as exc:
        logger.error(
            "Failed to send email verification message to recipient=%s: %s",
            mask_email(user_email),
            exc,
        )

    return {
        "success": True,
        "already_verified": False,
        "message": f"Mã xác thực 6 chữ số đã được gửi tới {mask_email(user_email)}.",
        "expires_in_minutes": ttl_minutes,
    }


def verify_email_with_code(
    user: User,
    code_or_token: str,
) -> dict[str, Any]:
    """Verify a user's email using the 6-digit code or URL token."""
    if user is None or not getattr(user, "is_authenticated", False):
        raise EmailVerificationError(
            "AUTHENTICATION_REQUIRED",
            "Bạn cần đăng nhập để thực hiện thao tác này.",
            status=401,
        )

    raw_code = str(code_or_token or "").strip()
    if not raw_code:
        raise EmailVerificationError(
            "VALIDATION_ERROR",
            "Mã xác thực không được để trống.",
            status=400,
            field="code",
        )

    user_email = normalize_email(user.email)
    now = _utcnow()
    digest = _token_digest(raw_code)

    token_row = (
        EmailVerificationToken.query.filter_by(
            user_id=int(user.id),
            token_hash=digest,
        )
        .with_for_update()
        .first()
    )

    if token_row is None or token_row.revoked_at is not None:
        # Increment attempt counter on latest active token if any
        latest_active = (
            EmailVerificationToken.query.filter(
                EmailVerificationToken.user_id == int(user.id),
                EmailVerificationToken.email == user_email,
                EmailVerificationToken.used_at.is_(None),
                EmailVerificationToken.revoked_at.is_(None),
            )
            .order_by(EmailVerificationToken.created_at.desc())
            .first()
        )
        if latest_active is not None:
            latest_active.attempts_count = (latest_active.attempts_count or 0) + 1
            if latest_active.attempts_count >= 5:
                latest_active.revoked_at = now
            db.session.commit()

        raise EmailVerificationError(
            "INVALID_CODE",
            "Mã xác thực không chính xác hoặc đã bị vô hiệu hóa.",
            status=400,
            field="code",
        )

    if token_row.used_at is not None:
        raise EmailVerificationError(
            "CODE_ALREADY_USED",
            "Mã xác thực này đã được sử dụng.",
            status=400,
            field="code",
        )

    if token_row.expires_at <= now:
        raise EmailVerificationError(
            "CODE_EXPIRED",
            "Mã xác thực đã hết hạn. Vui lòng yêu cầu gửi lại mã mới.",
            status=400,
            field="code",
        )

    if (token_row.attempts_count or 0) >= 5:
        token_row.revoked_at = now
        db.session.commit()
        raise EmailVerificationError(
            "TOO_MANY_ATTEMPTS",
            "Bạn đã nhập sai quá nhiều lần. Vui lòng yêu cầu mã xác thực mới.",
            status=400,
            field="code",
        )

    try:
        token_row.used_at = now
        user.email_verified_at = now
        user.email_verification_source = "email_code"
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        logger.error("Failed to mark email as verified for user_id=%s: %s", user.id, exc)
        raise EmailVerificationError(
            "DB_ERROR",
            "Không thể cập nhật trạng thái xác thực. Vui lòng thử lại.",
            status=500,
        ) from exc

    student_status = get_user_student_status(user)
    is_student = is_user_verified_student(user)

    return {
        "success": True,
        "message": "Xác thực địa chỉ email thành công!",
        "email_verified": True,
        "email_verified_at": now.isoformat(),
        "student_status": student_status.value,
        "is_verified_student": is_student,
    }


def invalidate_user_email_verification(user: User) -> None:
    """Invalidate email verification and active tokens when user email changes."""
    user.email_verified_at = None
    user.email_verification_source = None
    now = _utcnow()
    EmailVerificationToken.query.filter(
        EmailVerificationToken.user_id == int(user.id),
        EmailVerificationToken.used_at.is_(None),
        EmailVerificationToken.revoked_at.is_(None),
    ).update({EmailVerificationToken.revoked_at: now}, synchronize_session=False)
