"""harden sparse deck release tracking and clone field identity

Revision ID: 20260820_000019
Revises: 20260812_000016, 20260820_000018
Create Date: 2026-08-20 00:00:19
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260820_000019"
down_revision = ("20260812_000016", "20260820_000018")
branch_labels = None
depends_on = None


TRACKING_COLUMN = "dirty_tracking_revision"
STABLE_OVERRIDE_UNIQUE = "uq_clone_note_override_install_note_field_def"


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(row["name"]) for row in inspector.get_columns(table_name)}


def _unique_names(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {
        str(row["name"])
        for row in inspector.get_unique_constraints(table_name)
        if row.get("name")
    }


def _backfill_stable_field_identity() -> None:
    required_tables = {
        "deck_clone_note_field_overrides",
        "notes",
        "field_defs",
    }
    inspector = _inspector()
    if not all(inspector.has_table(table_name) for table_name in required_tables):
        return
    if "source_field_def_id" not in _columns("deck_clone_note_field_overrides"):
        return

    metadata = sa.MetaData()
    overrides = sa.Table(
        "deck_clone_note_field_overrides",
        metadata,
        autoload_with=op.get_bind(),
    )
    notes = sa.Table("notes", metadata, autoload_with=op.get_bind())
    field_defs = sa.Table("field_defs", metadata, autoload_with=op.get_bind())
    stable_field_id = (
        sa.select(field_defs.c.id)
        .select_from(
            notes.join(
                field_defs,
                field_defs.c.note_type_id == notes.c.note_type_id,
            )
        )
        .where(
            notes.c.id == overrides.c.source_note_id,
            field_defs.c.name == overrides.c.field_name,
        )
        .limit(1)
        .scalar_subquery()
    )
    op.get_bind().execute(
        sa.update(overrides)
        .where(overrides.c.source_field_def_id.is_(None))
        .values(source_field_def_id=stable_field_id)
    )


def upgrade() -> None:
    inspector = _inspector()
    if inspector.has_table("deck_marketplace_items") and TRACKING_COLUMN not in _columns(
        "deck_marketplace_items"
    ):
        with op.batch_alter_table("deck_marketplace_items") as batch_op:
            batch_op.add_column(
                sa.Column(
                    TRACKING_COLUMN,
                    sa.BigInteger(),
                    server_default="0",
                    nullable=False,
                )
            )

    _backfill_stable_field_identity()

    if (
        inspector.has_table("deck_clone_note_field_overrides")
        and STABLE_OVERRIDE_UNIQUE
        not in _unique_names("deck_clone_note_field_overrides")
    ):
        with op.batch_alter_table("deck_clone_note_field_overrides") as batch_op:
            batch_op.create_unique_constraint(
                STABLE_OVERRIDE_UNIQUE,
                ["deck_install_id", "source_note_id", "source_field_def_id"],
            )


def downgrade() -> None:
    inspector = _inspector()
    if (
        inspector.has_table("deck_clone_note_field_overrides")
        and STABLE_OVERRIDE_UNIQUE
        in _unique_names("deck_clone_note_field_overrides")
    ):
        with op.batch_alter_table("deck_clone_note_field_overrides") as batch_op:
            batch_op.drop_constraint(STABLE_OVERRIDE_UNIQUE, type_="unique")

    if inspector.has_table("deck_marketplace_items") and TRACKING_COLUMN in _columns(
        "deck_marketplace_items"
    ):
        with op.batch_alter_table("deck_marketplace_items") as batch_op:
            batch_op.drop_column(TRACKING_COLUMN)
