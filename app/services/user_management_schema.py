"""Schema safety helpers for user management features."""

from __future__ import annotations

from sqlalchemy import inspect, text
from sqlalchemy.exc import SQLAlchemyError

from models.user_balance_transaction import UserBalanceTransaction
from models.user_permission_audit_log import UserPermissionAuditLog


def ensure_user_management_schema(session) -> None:
    """Ensure user status, balance, fee columns and ledger tables exist for legacy databases."""
    bind = session.get_bind()
    inspector = inspect(bind)

    if inspector.has_table("users"):
        user_columns = {column["name"] for column in inspector.get_columns("users")}
        if "is_disabled" not in user_columns:
            session.execute(
                text("ALTER TABLE users ADD COLUMN is_disabled BOOLEAN NOT NULL DEFAULT 0")
            )
            session.flush()
        if "balance_amount_minor" not in user_columns:
            session.execute(
                text("ALTER TABLE users ADD COLUMN balance_amount_minor INTEGER NOT NULL DEFAULT 0")
            )
            session.flush()
        if "custom_platform_fee_percent" not in user_columns:
            session.execute(
                text("ALTER TABLE users ADD COLUMN custom_platform_fee_percent FLOAT NULL")
            )
            session.flush()
        if "display_name" not in user_columns:
            session.execute(
                text("ALTER TABLE users ADD COLUMN display_name VARCHAR(150) NULL")
            )
            session.flush()
        if "avatar_url" not in user_columns:
            session.execute(
                text("ALTER TABLE users ADD COLUMN avatar_url VARCHAR(512) NULL")
            )
            session.flush()
        if "bio" not in user_columns:
            session.execute(
                text("ALTER TABLE users ADD COLUMN bio TEXT NULL")
            )
            session.flush()
        if "social_links" not in user_columns:
            is_mysql = str(bind.dialect.name).lower().startswith("mysql")
            ddl = (
                "ALTER TABLE users ADD COLUMN social_links JSON NULL"
                if is_mysql
                else "ALTER TABLE users ADD COLUMN social_links TEXT NULL"
            )
            session.execute(text(ddl))
            session.execute(
                text("UPDATE users SET social_links = '[]' WHERE social_links IS NULL OR social_links = ''")
            )
            session.flush()

    if inspector.has_table("user_roles"):
        role_columns = {column["name"] for column in inspector.get_columns("user_roles")}
        if "default_platform_fee_percent" not in role_columns:
            session.execute(
                text("ALTER TABLE user_roles ADD COLUMN default_platform_fee_percent FLOAT NOT NULL DEFAULT 10.0")
            )
            session.flush()

    try:
        UserPermissionAuditLog.__table__.create(bind=bind, checkfirst=True)
        UserBalanceTransaction.__table__.create(bind=bind, checkfirst=True)
    except SQLAlchemyError:
        session.rollback()
        raise
