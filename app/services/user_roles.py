"""User role seed and synchronization helpers."""

from __future__ import annotations

from typing import Any

from models.user import User
from models.user_role import UserRole

DEFAULT_USER_ROLES: tuple[dict[str, Any], ...] = (
    {
        "code": "regular",
        "name": "User thong thuong",
        "description": "Tai khoan hoc vien co quyen hoc tap co ban.",
        "is_admin": False,
        "position": 1,
    },
    {
        "code": "creator",
        "name": "Nha sang tao",
        "description": "Tai khoan duoc mo rong quyen tao noi dung.",
        "is_admin": False,
        "position": 2,
    },
    {
        "code": "enterprise",
        "name": "Doanh nghiep",
        "description": "Tai khoan danh cho to chuc/doanh nghiep.",
        "is_admin": False,
        "position": 3,
    },
    {
        "code": "admin",
        "name": "Admin",
        "description": "Toan quyen quan tri he thong.",
        "is_admin": True,
        "position": 4,
    },
)


def ensure_default_user_roles(session) -> dict[str, UserRole]:
    """Create/update default roles and backfill users missing role mapping."""
    existing = {role.code: role for role in UserRole.query.all()}
    for row in DEFAULT_USER_ROLES:
        role = existing.get(row["code"])
        if role is None:
            role = UserRole(
                code=row["code"],
                name=row["name"],
                description=row["description"],
                is_admin=bool(row["is_admin"]),
                position=int(row["position"]),
            )
            session.add(role)
            existing[row["code"]] = role
        else:
            role.name = row["name"]
            role.description = row["description"]
            role.is_admin = bool(row["is_admin"])
            role.position = int(row["position"])

    session.flush()

    regular_role = existing.get("regular")
    admin_role = existing.get("admin")
    if regular_role is None or admin_role is None:
        return existing

    role_by_id = {role.id: role for role in existing.values() if role.id is not None}
    users = User.query.all()
    for user in users:
        assigned_role = role_by_id.get(user.role_id)
        if assigned_role is None:
            assigned_role = admin_role if bool(user.is_admin) else regular_role
            user.role_id = assigned_role.id

        target_admin_flag = bool(assigned_role.is_admin)
        if bool(user.is_admin) != target_admin_flag:
            user.is_admin = target_admin_flag

    return existing
