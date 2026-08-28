"""add user_identities table and nullable password_hash

Revision ID: 20260901_000030
Revises: 20260831_000029
Create Date: 2026-09-01 00:00:30
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260901_000030"
down_revision = "20260831_000029"
branch_labels = None
depends_on = None


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade():
    # 1. Make users.password_hash nullable
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(255),
        nullable=True,
    )

    # 2. Create user_identities table
    if not _has_table("user_identities"):
        op.create_table(
            "user_identities",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("provider", sa.String(32), nullable=False, server_default="google"),
            sa.Column("provider_sub", sa.String(255), nullable=False),
            sa.Column("provider_email", sa.String(255), nullable=True),
            sa.Column(
                "created_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.Column(
                "updated_at",
                sa.DateTime(),
                nullable=False,
                server_default=sa.text("CURRENT_TIMESTAMP"),
            ),
            sa.UniqueConstraint(
                "provider", "provider_sub", name="uq_user_identity_provider_sub"
            ),
        )


def downgrade():
    if _has_table("user_identities"):
        op.drop_table("user_identities")
    op.alter_column(
        "users",
        "password_hash",
        existing_type=sa.String(255),
        nullable=False,
    )
