"""add deck change request workflow tables

Revision ID: 20260330_000006
Revises: 20260329_000005
Create Date: 2026-03-30 00:00:06
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260330_000006"
down_revision = "20260329_000005"
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


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {row["name"] for row in _inspector().get_indexes(table_name)}


def _create_deck_change_requests_table() -> None:
    if _table_exists("deck_change_requests"):
        return
    op.create_table(
        "deck_change_requests",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("deck_install_id", sa.String(length=36), nullable=True),
        sa.Column("deck_item_id", sa.String(length=36), nullable=True),
        sa.Column("local_deck_id", sa.Integer(), nullable=True),
        sa.Column("source_deck_id", sa.Integer(), nullable=True),
        sa.Column("source_note_type_id", sa.String(length=36), nullable=True),
        sa.Column("requester_user_id", sa.Integer(), nullable=False),
        sa.Column("owner_user_id", sa.Integer(), nullable=False),
        sa.Column("reviewed_by_user_id", sa.Integer(), nullable=True),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("install_snapshot_at", sa.DateTime(), nullable=True),
        sa.Column("overlay_fingerprint", sa.String(length=64), nullable=False),
        sa.Column("last_synced_overlay_fingerprint", sa.String(length=64), nullable=True),
        sa.Column("last_sync_status", sa.String(length=32), nullable=True),
        sa.Column("last_synced_at", sa.DateTime(), nullable=True),
        sa.Column("submitted_at", sa.DateTime(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(), nullable=True),
        sa.Column("merged_at", sa.DateTime(), nullable=True),
        sa.Column("review_comment", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["deck_install_id"], ["deck_installs.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["deck_item_id"], ["deck_marketplace_items.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["local_deck_id"], ["decks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_deck_id"], ["decks.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["source_note_type_id"], ["note_types.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["requester_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_deck_change_request_items_table() -> None:
    if _table_exists("deck_change_request_items"):
        return
    op.create_table(
        "deck_change_request_items",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("change_type", sa.String(length=64), nullable=False),
        sa.Column("source_ref_id", sa.String(length=64), nullable=True),
        sa.Column("local_ref_id", sa.String(length=64), nullable=True),
        sa.Column("path_key", sa.String(length=255), nullable=True),
        sa.Column("path_label", sa.String(length=255), nullable=True),
        sa.Column("before_value", sa.JSON(), nullable=True),
        sa.Column("after_value", sa.JSON(), nullable=True),
        sa.Column("metadata_json", sa.JSON(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_conflict", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["change_request_id"], ["deck_change_requests.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )


def _create_deck_change_request_conflicts_table() -> None:
    if _table_exists("deck_change_request_conflicts"):
        return
    op.create_table(
        "deck_change_request_conflicts",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("change_request_id", sa.String(length=36), nullable=False),
        sa.Column("item_id", sa.String(length=36), nullable=False),
        sa.Column("conflict_type", sa.String(length=64), nullable=False),
        sa.Column("source_ref_id", sa.String(length=64), nullable=True),
        sa.Column("upstream_value", sa.JSON(), nullable=True),
        sa.Column("local_value", sa.JSON(), nullable=True),
        sa.Column("base_value", sa.JSON(), nullable=True),
        sa.Column("resolution_mode", sa.String(length=32), nullable=True),
        sa.Column("resolved_value", sa.JSON(), nullable=True),
        sa.Column("resolved_by_user_id", sa.Integer(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(["change_request_id"], ["deck_change_requests.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["item_id"], ["deck_change_request_items.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["resolved_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("item_id", name="uq_deck_change_request_conflicts_item"),
    )


def _create_index_if_missing(table_name: str, index_name: str, columns: list[str]) -> None:
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=False)


def _drop_index_if_exists(table_name: str, index_name: str) -> None:
    if index_name not in _index_names(table_name):
        return
    op.drop_index(index_name, table_name=table_name)


def upgrade() -> None:
    _create_deck_change_requests_table()
    _create_deck_change_request_items_table()
    _create_deck_change_request_conflicts_table()

    if "last_synced_at" not in _column_names("deck_installs"):
        op.add_column("deck_installs", sa.Column("last_synced_at", sa.DateTime(), nullable=True))
    if "last_sync_status" not in _column_names("deck_installs"):
        op.add_column("deck_installs", sa.Column("last_sync_status", sa.String(length=32), nullable=True))

    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_deck_install_id", ["deck_install_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_deck_item_id", ["deck_item_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_local_deck_id", ["local_deck_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_source_deck_id", ["source_deck_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_source_note_type_id", ["source_note_type_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_requester_user_id", ["requester_user_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_owner_user_id", ["owner_user_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_reviewed_by_user_id", ["reviewed_by_user_id"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_status", ["status"])
    _create_index_if_missing("deck_change_requests", "ix_deck_change_requests_last_sync_status", ["last_sync_status"])
    _create_index_if_missing(
        "deck_change_requests",
        "ix_deck_change_requests_owner_status_updated_at",
        ["owner_user_id", "status", "updated_at"],
    )
    _create_index_if_missing(
        "deck_change_requests",
        "ix_deck_change_requests_requester_status_updated_at",
        ["requester_user_id", "status", "updated_at"],
    )

    _create_index_if_missing("deck_change_request_items", "ix_deck_change_request_items_change_request_id", ["change_request_id"])
    _create_index_if_missing("deck_change_request_items", "ix_deck_change_request_items_change_type", ["change_type"])
    _create_index_if_missing("deck_change_request_items", "ix_deck_change_request_items_source_ref_id", ["source_ref_id"])
    _create_index_if_missing("deck_change_request_items", "ix_deck_change_request_items_local_ref_id", ["local_ref_id"])
    _create_index_if_missing("deck_change_request_items", "ix_deck_change_request_items_is_conflict", ["is_conflict"])
    _create_index_if_missing(
        "deck_change_request_items",
        "ix_deck_change_request_items_request_sort",
        ["change_request_id", "sort_order"],
    )
    _create_index_if_missing(
        "deck_change_request_items",
        "ix_deck_change_request_items_request_type",
        ["change_request_id", "change_type"],
    )

    _create_index_if_missing("deck_change_request_conflicts", "ix_deck_change_request_conflicts_change_request_id", ["change_request_id"])
    _create_index_if_missing("deck_change_request_conflicts", "ix_deck_change_request_conflicts_item_id", ["item_id"])
    _create_index_if_missing("deck_change_request_conflicts", "ix_deck_change_request_conflicts_conflict_type", ["conflict_type"])
    _create_index_if_missing("deck_change_request_conflicts", "ix_deck_change_request_conflicts_source_ref_id", ["source_ref_id"])
    _create_index_if_missing("deck_change_request_conflicts", "ix_deck_change_request_conflicts_resolution_mode", ["resolution_mode"])
    _create_index_if_missing("deck_change_request_conflicts", "ix_deck_change_request_conflicts_resolved_by_user_id", ["resolved_by_user_id"])
    _create_index_if_missing(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_request_resolved_at",
        ["change_request_id", "resolved_at"],
    )
    _create_index_if_missing(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_request_type",
        ["change_request_id", "conflict_type"],
    )

    _create_index_if_missing("deck_installs", "ix_deck_installs_last_synced_at", ["last_synced_at"])
    _create_index_if_missing("deck_installs", "ix_deck_installs_last_sync_status", ["last_sync_status"])


def downgrade() -> None:
    _drop_index_if_exists("deck_installs", "ix_deck_installs_last_sync_status")
    _drop_index_if_exists("deck_installs", "ix_deck_installs_last_synced_at")

    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_request_type",
    )
    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_request_resolved_at",
    )
    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_resolved_by_user_id",
    )
    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_resolution_mode",
    )
    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_source_ref_id",
    )
    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_conflict_type",
    )
    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_item_id",
    )
    _drop_index_if_exists(
        "deck_change_request_conflicts",
        "ix_deck_change_request_conflicts_change_request_id",
    )

    _drop_index_if_exists(
        "deck_change_request_items",
        "ix_deck_change_request_items_request_type",
    )
    _drop_index_if_exists(
        "deck_change_request_items",
        "ix_deck_change_request_items_request_sort",
    )
    _drop_index_if_exists(
        "deck_change_request_items",
        "ix_deck_change_request_items_is_conflict",
    )
    _drop_index_if_exists(
        "deck_change_request_items",
        "ix_deck_change_request_items_local_ref_id",
    )
    _drop_index_if_exists(
        "deck_change_request_items",
        "ix_deck_change_request_items_source_ref_id",
    )
    _drop_index_if_exists(
        "deck_change_request_items",
        "ix_deck_change_request_items_change_type",
    )
    _drop_index_if_exists(
        "deck_change_request_items",
        "ix_deck_change_request_items_change_request_id",
    )

    _drop_index_if_exists(
        "deck_change_requests",
        "ix_deck_change_requests_requester_status_updated_at",
    )
    _drop_index_if_exists(
        "deck_change_requests",
        "ix_deck_change_requests_owner_status_updated_at",
    )
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_last_sync_status")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_status")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_reviewed_by_user_id")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_owner_user_id")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_requester_user_id")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_source_note_type_id")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_source_deck_id")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_local_deck_id")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_deck_item_id")
    _drop_index_if_exists("deck_change_requests", "ix_deck_change_requests_deck_install_id")

    if _table_exists("deck_change_request_conflicts"):
        op.drop_table("deck_change_request_conflicts")
    if _table_exists("deck_change_request_items"):
        op.drop_table("deck_change_request_items")
    if _table_exists("deck_change_requests"):
        op.drop_table("deck_change_requests")

    existing_columns = _column_names("deck_installs")
    if "last_sync_status" in existing_columns:
        op.drop_column("deck_installs", "last_sync_status")
    if "last_synced_at" in existing_columns:
        op.drop_column("deck_installs", "last_synced_at")
