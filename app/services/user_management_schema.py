"""Schema safety helpers for user management features."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from models.user_permission_audit_log import UserPermissionAuditLog


def ensure_user_management_schema(session) -> None:
    """Ensure user status column and audit table exist for legacy databases."""
    bind = session.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_disabled" not in user_columns:
            session.execute(
                text("ALTER TABLE users ADD COLUMN is_disabled BOOLEAN NOT NULL DEFAULT 0")
            )
            session.flush()

    try:
        UserPermissionAuditLog.__table__.create(bind=bind, checkfirst=True)
    except SQLAlchemyError:
        session.rollback()
        raise
