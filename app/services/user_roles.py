"""User role seed and synchronization helpers."""

from __future__ import annotations

from typing import Any

from sqlalchemy import inspect
from sqlalchemy.exc import SQLAlchemyError

from models.user import User
from models.user_role import UserRole

DEFAULT_USER_ROLES: tuple[dict[str, Any], ...] = (
    {
        "code": "regular",
        "name": "Người dùng thông thường",
        "description": "Tài khoản học viên với các quyền học tập cơ bản.",
        "is_admin": False,
        "position": 1,
        "default_platform_fee_percent": 10.0,
    },
    {
        "code": "creator",
        "name": "Nhà sáng tạo",
        "description": "Tài khoản được mở rộng quyền tạo và chia sẻ nội dung.",
        "is_admin": False,
        "position": 2,
        "default_platform_fee_percent": 5.0,
    },
    {
        "code": "enterprise",
        "name": "Doanh nghiệp",
        "description": "Tài khoản dành cho tổ chức hoặc doanh nghiệp.",
        "is_admin": False,
        "position": 3,
        "default_platform_fee_percent": 10.0,
    },
    {
        "code": "admin",
        "name": "Admin",
        "description": "Toàn quyền quản trị hệ thống.",
        "is_admin": True,
        "position": 4,
        "default_platform_fee_percent": 0.0,
    },
)


def _role_schema_ready(session) -> bool:
    """Return True only when required tables/columns already exist."""
    try:
        bind = session.get_bind()
        inspector = inspect(bind)
        if not inspector.has_table("users"):
            return False
        if not inspector.has_table("user_roles"):
            return False

        user_columns = {column["name"] for column in inspector.get_columns("users")}
        role_columns = {column["name"] for column in inspector.get_columns("user_roles")}
        required_user_columns = {"id", "is_admin", "role_id"}
        required_role_columns = {"id", "code", "name", "is_admin", "position"}
        return required_user_columns.issubset(user_columns) and required_role_columns.issubset(role_columns)
    except SQLAlchemyError:
        return False


def ensure_default_user_roles(session) -> dict[str, UserRole]:
    """Create/update default roles and backfill users missing role mapping."""
    if not _role_schema_ready(session):
        return {}

    bind = session.get_bind()
    inspector = inspect(bind)
    role_columns = {column["name"] for column in inspector.get_columns("user_roles")}
    has_fee_col = "default_platform_fee_percent" in role_columns

    existing = {role.code: role for role in UserRole.query.all()}
    for row in DEFAULT_USER_ROLES:
        role = existing.get(row["code"])
        fee_percent = float(row.get("default_platform_fee_percent", 10.0))
        if role is None:
            role = UserRole(
                code=row["code"],
                name=row["name"],
                description=row["description"],
                is_admin=bool(row["is_admin"]),
                position=int(row["position"]),
                default_platform_fee_percent=fee_percent,
            )
            session.add(role)
            existing[row["code"]] = role
        else:
            role.name = row["name"]
            role.description = row["description"]
            role.is_admin = bool(row["is_admin"])
            role.position = int(row["position"])
            if has_fee_col and getattr(role, "default_platform_fee_percent", None) is None:
                role.default_platform_fee_percent = fee_percent

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
