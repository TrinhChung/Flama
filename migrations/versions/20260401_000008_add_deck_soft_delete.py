"""add deck soft delete marker

Revision ID: 20260401_000008
Revises: 20260331_000007
Create Date: 2026-04-01 00:00:08
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260401_000008"
down_revision = "20260331_000007"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _column_names(table_name: str) -> set[str]:
    if not _inspector().has_table(table_name):
        return set()
    return {row["name"] for row in _inspector().get_columns(table_name)}


def _index_names(table_name: str) -> set[str]:
    if not _inspector().has_table(table_name):
        return set()
    return {row["name"] for row in _inspector().get_indexes(table_name)}


def upgrade() -> None:
    if "deleted_at" not in _column_names("decks"):
        op.add_column("decks", sa.Column("deleted_at", sa.DateTime(), nullable=True))
    if "ix_decks_deleted_at" not in _index_names("decks"):
        op.create_index("ix_decks_deleted_at", "decks", ["deleted_at"], unique=False)


def downgrade() -> None:
    if "ix_decks_deleted_at" in _index_names("decks"):
        op.drop_index("ix_decks_deleted_at", table_name="decks")
    if "deleted_at" in _column_names("decks"):
        op.drop_column("decks", "deleted_at")
