"""add user can_manage_mcp_tokens permission column

Revision ID: 20260910_000035
Revises: 20260910_000034
Create Date: 2026-09-10 00:00:35
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260910_000035"
down_revision = "20260910_000034"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade() -> None:
    user_cols = _get_column_names("users")
    if "can_manage_mcp_tokens" not in user_cols:
        op.add_column(
            "users",
            sa.Column("can_manage_mcp_tokens", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        if "can_use_mcp" in user_cols:
            bind = op.get_bind()
            bind.execute(sa.text("UPDATE users SET can_manage_mcp_tokens = can_use_mcp WHERE can_use_mcp = 1"))


def downgrade() -> None:
    user_cols = _get_column_names("users")
    if "can_manage_mcp_tokens" in user_cols:
        op.drop_column("users", "can_manage_mcp_tokens")
