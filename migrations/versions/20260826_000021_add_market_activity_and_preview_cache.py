"""add per-install market activity state and release-bound preview cache

Revision ID: 20260826_000021
Revises: 20260821_000020
Create Date: 2026-08-26 00:00:21
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260826_000021"
down_revision = "20260821_000020"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _columns(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(row["name"]) for row in inspector.get_columns(table_name)}


def _indexes(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(row["name"]) for row in inspector.get_indexes(table_name)}


def _foreign_keys(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(row.get("name") or "") for row in inspector.get_foreign_keys(table_name)}


def _add_activity_columns(table_name: str) -> None:
    columns = _columns(table_name)
    with op.batch_alter_table(table_name) as batch_op:
        if "market_active" not in columns:
            batch_op.add_column(sa.Column("market_active", sa.Boolean(), nullable=True))
        if "market_active_evaluated_at" not in columns:
            batch_op.add_column(sa.Column("market_active_evaluated_at", sa.DateTime(), nullable=True))
        if "market_active_policy_version" not in columns:
            batch_op.add_column(sa.Column("market_active_policy_version", sa.SmallInteger(), nullable=True))


def upgrade() -> None:
    inspector = _inspector()
    if inspector.has_table("deck_installs"):
        _add_activity_columns("deck_installs")
        indexes = _indexes("deck_installs")
        if "ix_deck_installs_item_market_active" not in indexes:
            op.create_index(
                "ix_deck_installs_item_market_active",
                "deck_installs",
                ["deck_item_id", "market_active"],
                unique=False,
            )

    if inspector.has_table("note_type_installs"):
        _add_activity_columns("note_type_installs")
        indexes = _indexes("note_type_installs")
        if "ix_note_type_installs_source_market_active" not in indexes:
            op.create_index(
                "ix_note_type_installs_source_market_active",
                "note_type_installs",
                ["source_note_type_id", "market_active"],
                unique=False,
            )
        if "ix_note_type_installs_user_installed" not in indexes:
            op.create_index(
                "ix_note_type_installs_user_installed",
                "note_type_installs",
                ["user_id", "installed_note_type_id"],
                unique=False,
            )

    if inspector.has_table("deck_marketplace_items"):
        columns = _columns("deck_marketplace_items")
        with op.batch_alter_table("deck_marketplace_items") as batch_op:
            if "preview_samples_release_id" not in columns:
                batch_op.add_column(sa.Column("preview_samples_release_id", sa.String(length=36), nullable=True))
            if "preview_samples_schema_version" not in columns:
                batch_op.add_column(sa.Column("preview_samples_schema_version", sa.SmallInteger(), nullable=True))
            if "preview_samples_json" not in columns:
                batch_op.add_column(sa.Column("preview_samples_json", sa.JSON(), nullable=True))

        indexes = _indexes("deck_marketplace_items")
        if "ix_deck_marketplace_items_preview_samples_release_id" not in indexes:
            op.create_index(
                "ix_deck_marketplace_items_preview_samples_release_id",
                "deck_marketplace_items",
                ["preview_samples_release_id"],
                unique=False,
            )
        foreign_keys = _foreign_keys("deck_marketplace_items")
        if "fk_deck_marketplace_items_preview_samples_release" not in foreign_keys:
            with op.batch_alter_table("deck_marketplace_items") as batch_op:
                batch_op.create_foreign_key(
                    "fk_deck_marketplace_items_preview_samples_release",
                    "deck_releases",
                    ["preview_samples_release_id"],
                    ["id"],
                    ondelete="SET NULL",
                )


def downgrade() -> None:
    inspector = _inspector()
    if inspector.has_table("deck_marketplace_items"):
        foreign_keys = _foreign_keys("deck_marketplace_items")
        if "fk_deck_marketplace_items_preview_samples_release" in foreign_keys:
            with op.batch_alter_table("deck_marketplace_items") as batch_op:
                batch_op.drop_constraint(
                    "fk_deck_marketplace_items_preview_samples_release",
                    type_="foreignkey",
                )
        indexes = _indexes("deck_marketplace_items")
        if "ix_deck_marketplace_items_preview_samples_release_id" in indexes:
            op.drop_index(
                "ix_deck_marketplace_items_preview_samples_release_id",
                table_name="deck_marketplace_items",
            )
        columns = _columns("deck_marketplace_items")
        with op.batch_alter_table("deck_marketplace_items") as batch_op:
            for column_name in (
                "preview_samples_json",
                "preview_samples_schema_version",
                "preview_samples_release_id",
            ):
                if column_name in columns:
                    batch_op.drop_column(column_name)

    for table_name, indexes_to_drop in (
        ("note_type_installs", ("ix_note_type_installs_user_installed", "ix_note_type_installs_source_market_active")),
        ("deck_installs", ("ix_deck_installs_item_market_active",)),
    ):
        if not inspector.has_table(table_name):
            continue
        indexes = _indexes(table_name)
        for index_name in indexes_to_drop:
            if index_name in indexes:
                op.drop_index(index_name, table_name=table_name)
        columns = _columns(table_name)
        with op.batch_alter_table(table_name) as batch_op:
            for column_name in (
                "market_active_policy_version",
                "market_active_evaluated_at",
                "market_active",
            ):
                if column_name in columns:
                    batch_op.drop_column(column_name)
