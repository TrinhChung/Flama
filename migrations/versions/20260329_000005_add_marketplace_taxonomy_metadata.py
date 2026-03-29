"""add marketplace taxonomy metadata columns

Revision ID: 20260329_000005
Revises: 20260329_000004
Create Date: 2026-03-29 00:00:05
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260329_000005"
down_revision = "20260329_000004"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _column_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {row["name"] for row in _inspector().get_columns(table_name)}


def _add_json_column_if_missing(table_name: str, column_name: str) -> None:
    if column_name in _column_names(table_name):
        return
    op.add_column(table_name, sa.Column(column_name, sa.JSON(), nullable=True))
    op.execute(
        sa.text(
            f"UPDATE {table_name} SET {column_name} = '{{}}' "
            f"WHERE {column_name} IS NULL"
        )
    )


def upgrade() -> None:
    _add_json_column_if_missing("note_types", "taxonomy_metadata")
    _add_json_column_if_missing("deck_marketplace_items", "taxonomy_metadata")


def downgrade() -> None:
    pass
