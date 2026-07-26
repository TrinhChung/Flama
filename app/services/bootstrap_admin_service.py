"""Idempotent synchronization of the environment-managed admin account."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.user_roles import ensure_default_user_roles
from app.utils.bootstrap_admin import BootstrapAdminCredentials
from models.user import User


class BootstrapAdminConflictError(RuntimeError):
    """Raised when the configured email and username belong to different users."""


@dataclass(frozen=True)
class BootstrapAdminSyncResult:
    user_id: int
    created: bool
    changed_fields: tuple[str, ...]


def sync_bootstrap_admin(
    session,
    *,
    credentials: BootstrapAdminCredentials,
) -> BootstrapAdminSyncResult:
    email = credentials.email.strip().lower()
    username = credentials.username.strip()
    password = credentials.password

    roles = ensure_default_user_roles(session)
    admin_role = roles.get("admin")
    if admin_role is None:
        raise RuntimeError("Default admin role is unavailable.")

    email_user = User.query.filter_by(email=email).first()
    username_user = User.query.filter_by(username=username).first()
    if email_user is not None and username_user is not None and email_user.id != username_user.id:
        raise BootstrapAdminConflictError(
            "Configured admin email and username belong to different existing users."
        )

    user = email_user or username_user
    created = user is None
    changed_fields: list[str] = []
    if user is None:
        user = User(
            email=email,
            username=username,
            is_admin=True,
            is_disabled=False,
            role_id=admin_role.id,
        )
        user.set_password(password)
        session.add(user)
        changed_fields.extend(("password", "is_admin", "is_disabled", "role"))
    else:
        if user.email != email:
            user.email = email
            changed_fields.append("email")
        if user.username != username:
            user.username = username
            changed_fields.append("username")
        if not user.password_hash or not user.check_password(password):
            user.set_password(password)
            changed_fields.append("password")
        if not user.is_admin:
            user.is_admin = True
            changed_fields.append("is_admin")
        if user.is_disabled:
            user.is_disabled = False
            changed_fields.append("is_disabled")
        if user.role_id != admin_role.id:
            user.role_id = admin_role.id
            changed_fields.append("role")

    session.flush()
    return BootstrapAdminSyncResult(
        user_id=user.id,
        created=created,
        changed_fields=tuple(changed_fields),
    )
