"""add client_secret and is_default to oauth_clients

Revision ID: 20260910_000036
Revises: 20260910_000035
Create Date: 2026-09-10 00:00:36
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260910_000036"
down_revision = "20260910_000035"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _get_index_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {idx["name"] for idx in inspector.get_indexes(table_name)}


def upgrade() -> None:
    cols = _get_column_names("oauth_clients")
    if not cols:
        return

    if "client_secret" not in cols:
        op.add_column(
            "oauth_clients",
            sa.Column("client_secret", sa.String(length=255), nullable=True),
        )

    if "is_default" not in cols:
        op.add_column(
            "oauth_clients",
            sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )

    indexes = _get_index_names("oauth_clients")
    if "ix_oauth_clients_is_default" not in indexes:
        op.create_index(
            "ix_oauth_clients_is_default",
            "oauth_clients",
            ["is_default"],
            unique=False,
        )

    bind = op.get_bind()
    try:
        bind.execute(
            sa.text(
                "UPDATE oauth_clients SET is_default = 1 "
                "WHERE client_id = 'chatgpt_flama' AND NOT EXISTS ("
                "    SELECT 1 FROM (SELECT id FROM oauth_clients WHERE is_default = 1) AS t"
                ")"
            )
        )
    except Exception:
        pass


def downgrade() -> None:
    indexes = _get_index_names("oauth_clients")
    if "ix_oauth_clients_is_default" in indexes:
        op.drop_index("ix_oauth_clients_is_default", table_name="oauth_clients")

    cols = _get_column_names("oauth_clients")
    if "is_default" in cols:
        op.drop_column("oauth_clients", "is_default")
    if "client_secret" in cols:
        op.drop_column("oauth_clients", "client_secret")
