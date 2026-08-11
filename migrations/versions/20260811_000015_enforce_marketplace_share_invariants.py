"""enforce marketplace share invariants

Revision ID: 20260811_000015
Revises: 20260809_000014
Create Date: 2026-08-11 00:00:15
"""

from alembic import op
import sqlalchemy as sa


revision = "20260811_000015"
down_revision = "20260809_000014"
branch_labels = None
depends_on = None


INDEX_NAME = "uq_deck_marketplace_items_source_deck"


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("deck_marketplace_items"):
        return

    duplicate_source_ids = bind.execute(
        sa.text(
            """
            SELECT source_deck_id
            FROM deck_marketplace_items
            WHERE source_deck_id IS NOT NULL
            GROUP BY source_deck_id
            HAVING COUNT(*) > 1
            """
        )
    ).scalars().all()
    if duplicate_source_ids:
        sample = ", ".join(str(value) for value in duplicate_source_ids[:10])
        raise RuntimeError(
            "Cannot enforce unique shared-deck sources: duplicate source_deck_id "
            f"values exist ({sample}). Archive or merge duplicate listings, then rerun migration."
        )

    index_names = {
        row["name"]
        for row in inspector.get_indexes("deck_marketplace_items")
        if row.get("name")
    }
    if INDEX_NAME not in index_names:
        op.create_index(
            INDEX_NAME,
            "deck_marketplace_items",
            ["source_deck_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("deck_marketplace_items"):
        return
    index_names = {
        row["name"]
        for row in inspector.get_indexes("deck_marketplace_items")
        if row.get("name")
    }
    if INDEX_NAME in index_names:
        op.drop_index(INDEX_NAME, table_name="deck_marketplace_items")
