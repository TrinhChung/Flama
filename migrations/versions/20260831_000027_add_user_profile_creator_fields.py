"""add user profile creator fields

Revision ID: 20260831_000027
Revises: 20260831_000026
Create Date: 2026-08-31 00:00:27
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260831_000027"
down_revision = "20260831_000026"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    user_cols = _get_column_names("users")
    if "display_name" not in user_cols:
        op.add_column(
            "users",
            sa.Column("display_name", sa.String(150), nullable=True),
        )
    if "avatar_url" not in user_cols:
        op.add_column(
            "users",
            sa.Column("avatar_url", sa.String(512), nullable=True),
        )
    if "bio" not in user_cols:
        op.add_column(
            "users",
            sa.Column("bio", sa.Text(), nullable=True),
        )
    if "social_links" not in user_cols:
        op.add_column(
            "users",
            sa.Column("social_links", sa.JSON(), nullable=True),
        )
        op.execute(
            sa.text("UPDATE users SET social_links = '[]' WHERE social_links IS NULL")
        )


def downgrade():
    user_cols = _get_column_names("users")
    if "social_links" in user_cols:
        op.drop_column("users", "social_links")
    if "bio" in user_cols:
        op.drop_column("users", "bio")
    if "avatar_url" in user_cols:
        op.drop_column("users", "avatar_url")
    if "display_name" in user_cols:
        op.drop_column("users", "display_name")
