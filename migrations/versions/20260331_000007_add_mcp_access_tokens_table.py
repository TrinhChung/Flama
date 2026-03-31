"""add mcp access tokens table

Revision ID: 20260331_000007
Revises: 20260330_000006
Create Date: 2026-03-31 00:00:07
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260331_000007"
down_revision = "20260330_000006"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {row["name"] for row in _inspector().get_indexes(table_name)}


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str], *, unique: bool = False) -> None:
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if index_name not in _index_names(table_name):
        return
    op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    if not _table_exists("mcp_access_tokens"):
        op.create_table(
            "mcp_access_tokens",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("token_hash", sa.String(length=64), nullable=False),
            sa.Column("scopes", sa.Text(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("max_requests", sa.Integer(), nullable=False),
            sa.Column("used_requests", sa.Integer(), nullable=False),
            sa.Column("revoked", sa.Boolean(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("last_used_at", sa.DateTime(), nullable=True),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("token_hash", name="uq_mcp_access_tokens_token_hash"),
        )

    _create_index_if_missing("mcp_access_tokens", "ix_mcp_access_tokens_user_id", ["user_id"])
    _create_index_if_missing("mcp_access_tokens", "ix_mcp_access_tokens_token_hash", ["token_hash"], unique=True)
    _create_index_if_missing("mcp_access_tokens", "ix_mcp_access_tokens_expires_at", ["expires_at"])
    _create_index_if_missing("mcp_access_tokens", "ix_mcp_access_tokens_revoked", ["revoked"])
    _create_index_if_missing(
        "mcp_access_tokens",
        "ix_mcp_access_tokens_user_revoked_created_at",
        ["user_id", "revoked", "created_at"],
    )


def downgrade() -> None:
    _drop_index_if_exists("mcp_access_tokens", "ix_mcp_access_tokens_user_revoked_created_at")
    _drop_index_if_exists("mcp_access_tokens", "ix_mcp_access_tokens_revoked")
    _drop_index_if_exists("mcp_access_tokens", "ix_mcp_access_tokens_expires_at")
    _drop_index_if_exists("mcp_access_tokens", "ix_mcp_access_tokens_token_hash")
    _drop_index_if_exists("mcp_access_tokens", "ix_mcp_access_tokens_user_id")

    if _table_exists("mcp_access_tokens"):
        op.drop_table("mcp_access_tokens")
