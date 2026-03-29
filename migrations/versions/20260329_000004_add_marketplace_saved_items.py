"""add marketplace saved items table

Revision ID: 20260329_000004
Revises: 20260327_000003
Create Date: 2026-03-29 00:00:04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_000004"
down_revision = "20260327_000003"
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


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _table_exists("marketplace_saved_items"):
        op.create_table(
            "marketplace_saved_items",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("product_type", sa.String(length=64), nullable=False),
            sa.Column("product_ref_id", sa.String(length=36), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "product_type",
                "product_ref_id",
                name="uq_marketplace_saved_items_user_product",
            ),
        )
    _create_index_if_missing("ix_marketplace_saved_items_user_id", "marketplace_saved_items", ["user_id"])
    _create_index_if_missing("ix_marketplace_saved_items_product_type", "marketplace_saved_items", ["product_type"])
    _create_index_if_missing("ix_marketplace_saved_items_product_ref_id", "marketplace_saved_items", ["product_ref_id"])


def downgrade() -> None:
    pass
