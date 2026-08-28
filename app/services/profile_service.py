"""Application service for User Profile and Account Management."""

from __future__ import annotations

from typing import Any

from sqlalchemy.exc import SQLAlchemyError

from app.services import email_verification_service, wallet_service
from app.services.student_verification_service import (
    normalize_email,
    serialize_student_profile,
)
from app.validators.password import validate_password_policy
from models import db
from models.user import User


class ProfileServiceError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.field = field


def _iso(dt) -> str | None:
    return dt.isoformat() if dt is not None else None


def get_profile_payload(user: User) -> dict[str, Any]:
    role = getattr(user, "role", None)
    wallet_summary = wallet_service.get_user_wallet_summary(user)
    from app.services.student_verification_service import serialize_student_profile

    student_data = serialize_student_profile(user)

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "timezone": getattr(user, "timezone", "UTC") or "UTC",
            "is_admin": bool(user.is_admin),
            "is_disabled": bool(getattr(user, "is_disabled", False)),
            "created_at": _iso(getattr(user, "created_at", None)),
            "email_verified": bool(student_data["email_verified"]),
            "email_verified_at": student_data["email_verified_at"],
            "email_verification_source": student_data["email_verification_source"],
            "student_status": student_data["student_status"],
            "is_verified_student": bool(student_data["is_verified_student"]),
            "is_edu_email": bool(student_data["is_edu_email"]),
            "institution_domain": student_data["institution_domain"],
            "role": (
                {
                    "id": role.id,
                    "code": role.code,
                    "name": role.name,
                    "description": role.description,
                    "is_admin": bool(role.is_admin),
                }
                if role is not None
                else None
            ),
        },
        "wallet": wallet_summary,
    }


def update_profile(user: User, payload: dict[str, Any]) -> dict[str, Any]:
    """Update profile attributes like timezone and password."""
    next_timezone: str | None = None
    next_password: str | None = None
    next_email: str | None = None

    if "email" in payload:
        raw_email = normalize_email(payload.get("email"))
        if raw_email and raw_email != normalize_email(user.email):
            existing = User.query.filter(User.email == raw_email, User.id != user.id).first()
            if existing is not None:
                raise ProfileServiceError(
                    "CONFLICT",
                    "Địa chỉ email này đã được sử dụng bởi một tài khoản khác.",
                    status=409,
                    field="email",
                )
            next_email = raw_email

    if "timezone" in payload:
        tz = str(payload.get("timezone") or "").strip()
        if tz:
            if len(tz) > 64:
                raise ProfileServiceError(
                    "VALIDATION_ERROR",
                    "Timezone must not exceed 64 characters.",
                    status=400,
                    field="timezone",
                )
            next_timezone = tz

    if (
        "current_password" in payload
        or "new_password" in payload
        or "confirm_password" in payload
    ):
        current_pw = str(payload.get("current_password") or "")
        new_pw = str(payload.get("new_password") or "")
        confirm_pw = str(payload.get("confirm_password") or "")

        if not current_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "Current password is required.",
                status=400,
                field="current_password",
            )
        if not new_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "New password is required.",
                status=400,
                field="new_password",
            )
        if not confirm_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "Password confirmation is required.",
                status=400,
                field="confirm_password",
            )

        if not getattr(user, "password_hash", None):
            raise ProfileServiceError(
                "PASSWORD_NOT_SET",
                "This account does not have a password configured.",
                status=400,
            )

        if not user.check_password(current_pw):
            raise ProfileServiceError(
                "INVALID_CURRENT_PASSWORD",
                "Current password is incorrect.",
                status=400,
                field="current_password",
            )

        policy_error = validate_password_policy(new_pw)
        if policy_error:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                policy_error,
                status=400,
                field="new_password",
            )

        if new_pw != confirm_pw:
            raise ProfileServiceError(
                "VALIDATION_ERROR",
                "Password confirmation does not match.",
                status=400,
                field="confirm_password",
            )

        if current_pw == new_pw:
            raise ProfileServiceError(
                "PASSWORD_REUSED",
                "New password must be different from current password.",
                status=400,
                field="new_password",
            )

        next_password = new_pw

    if next_timezone is not None or next_password is not None or next_email is not None:
        try:
            if next_email is not None:
                user.email = next_email
                email_verification_service.invalidate_user_email_verification(user)
            if next_timezone is not None:
                user.timezone = next_timezone
            if next_password is not None:
                user.set_password(next_password)
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise ProfileServiceError(
                "DB_ERROR",
                "Could not update profile.",
                status=500,
            ) from exc

    return get_profile_payload(user)


def list_profile_transactions(
    user_id: int,
    *,
    page: int = 1,
    per_page: int = 10,
    transaction_type: str | None = None,
) -> dict[str, Any]:
    return wallet_service.list_user_transactions(
        user_id=user_id,
        page=page,
        per_page=per_page,
        transaction_type=transaction_type,
    )
