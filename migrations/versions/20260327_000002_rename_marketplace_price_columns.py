"""rename marketplace price columns to amount_minor

Revision ID: 20260327_000002
Revises: 20260327_000001
Create Date: 2026-03-27 00:00:02
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260327_000002"
down_revision = "20260327_000001"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _column_names(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {column["name"] for column in inspector.get_columns(table_name)}


def _rename_int_column_if_present(table_name: str, old_name: str, new_name: str) -> None:
    column_names = _column_names(table_name)
    if new_name in column_names or old_name not in column_names:
        return
    with op.batch_alter_table(table_name) as batch_op:
        batch_op.alter_column(
            old_name,
            new_column_name=new_name,
            existing_type=sa.Integer(),
            existing_nullable=False,
            existing_server_default=sa.text("0"),
        )


def upgrade() -> None:
    _rename_int_column_if_present("note_types", "price_cents", "price_amount_minor")
    _rename_int_column_if_present("deck_marketplace_items", "price_cents", "price_amount_minor")
    _rename_int_column_if_present("note_type_installs", "purchase_price_cents", "purchase_amount_minor")
    _rename_int_column_if_present("deck_installs", "purchase_price_cents", "purchase_amount_minor")


def downgrade() -> None:
    _rename_int_column_if_present("note_types", "price_amount_minor", "price_cents")
    _rename_int_column_if_present("deck_marketplace_items", "price_amount_minor", "price_cents")
    _rename_int_column_if_present("note_type_installs", "purchase_amount_minor", "purchase_price_cents")
    _rename_int_column_if_present("deck_installs", "purchase_amount_minor", "purchase_price_cents")
