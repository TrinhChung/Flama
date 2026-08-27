"""Application service for User Profile and Account Management."""

from __future__ import annotations

from typing import Any

from app.services import wallet_service
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

    return {
        "user": {
            "id": user.id,
            "username": user.username,
            "email": user.email,
            "timezone": getattr(user, "timezone", "UTC") or "UTC",
            "is_admin": bool(user.is_admin),
            "is_disabled": bool(getattr(user, "is_disabled", False)),
            "created_at": _iso(getattr(user, "created_at", None)),
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
    updated = False

    if "timezone" in payload:
        tz = str(payload.get("timezone") or "").strip()
        if tz:
            if len(tz) > 64:
                raise ProfileServiceError("VALIDATION_ERROR", "Timezone must not exceed 64 characters.", field="timezone")
            user.timezone = tz
            updated = True

    if "new_password" in payload or "current_password" in payload:
        current_pw = str(payload.get("current_password") or "")
        new_pw = str(payload.get("new_password") or "")
        confirm_pw = str(payload.get("confirm_password") or "")

        if not current_pw:
            raise ProfileServiceError("VALIDATION_ERROR", "Mật khẩu hiện tại là bắt buộc.", field="current_password")
        if not user.check_password(current_pw):
            raise ProfileServiceError("INVALID_CREDENTIALS", "Mật khẩu hiện tại không chính xác.", status=401, field="current_password")
        if not new_pw:
            raise ProfileServiceError("VALIDATION_ERROR", "Mật khẩu mới là bắt buộc.", field="new_password")
        if len(new_pw) < 6:
            raise ProfileServiceError("VALIDATION_ERROR", "Mật khẩu mới phải có ít nhất 6 ký tự.", field="new_password")
        if new_pw != confirm_pw:
            raise ProfileServiceError("VALIDATION_ERROR", "Xác nhận mật khẩu mới không khớp.", field="confirm_password")

        user.set_password(new_pw)
        updated = True

    if updated:
        db.session.commit()

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
