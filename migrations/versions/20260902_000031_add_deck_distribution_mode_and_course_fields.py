"""add deck distribution mode and course fields

Revision ID: 20260902_000031
Revises: 20260901_000030
Create Date: 2026-09-02 00:00:31
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260902_000031"
down_revision = "20260901_000030"
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


def upgrade():
    item_cols = _get_column_names("deck_marketplace_items")
    item_idxs = _get_index_names("deck_marketplace_items")

    if "distribution_mode" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("distribution_mode", sa.String(32), nullable=False, server_default="free"),
        )
    if "ix_deck_marketplace_items_distribution_mode" not in item_idxs:
        op.create_index(
            "ix_deck_marketplace_items_distribution_mode",
            "deck_marketplace_items",
            ["distribution_mode"],
        )
    if "course_title" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("course_title", sa.String(255), nullable=True),
        )
    if "course_description" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("course_description", sa.Text(), nullable=True),
        )
    if "course_url" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("course_url", sa.String(500), nullable=True),
        )
    if "course_instructions" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("course_instructions", sa.Text(), nullable=True),
        )


def downgrade():
    item_cols = _get_column_names("deck_marketplace_items")
    item_idxs = _get_index_names("deck_marketplace_items")

    if "course_instructions" in item_cols:
        op.drop_column("deck_marketplace_items", "course_instructions")
    if "course_url" in item_cols:
        op.drop_column("deck_marketplace_items", "course_url")
    if "course_description" in item_cols:
        op.drop_column("deck_marketplace_items", "course_description")
    if "course_title" in item_cols:
        op.drop_column("deck_marketplace_items", "course_title")
    if "ix_deck_marketplace_items_distribution_mode" in item_idxs:
        op.drop_index("ix_deck_marketplace_items_distribution_mode", table_name="deck_marketplace_items")
    if "distribution_mode" in item_cols:
        op.drop_column("deck_marketplace_items", "distribution_mode")
