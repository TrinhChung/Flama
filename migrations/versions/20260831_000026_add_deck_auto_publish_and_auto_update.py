"""add deck auto-publish and subscriber auto-update schema

Revision ID: 20260831_000026
Revises: 20260830_000025
Create Date: 2026-08-31 00:00:26
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260831_000026"
down_revision = "20260830_000025"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def upgrade():
    # 1. deck_marketplace_items
    item_cols = _get_column_names("deck_marketplace_items")
    if "auto_publish_enabled" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("auto_publish_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        op.create_index(
            "ix_deck_marketplace_items_auto_publish_enabled",
            "deck_marketplace_items",
            ["auto_publish_enabled"],
        )
    if "last_auto_published_at" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("last_auto_published_at", sa.DateTime(), nullable=True),
        )
    if "last_auto_publish_error" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("last_auto_publish_error", sa.Text(), nullable=True),
        )

    # 2. deck_installs
    install_cols = _get_column_names("deck_installs")
    if "auto_update_enabled" not in install_cols:
        op.add_column(
            "deck_installs",
            sa.Column("auto_update_enabled", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        )
        op.create_index(
            "ix_deck_installs_auto_update_enabled",
            "deck_installs",
            ["auto_update_enabled"],
        )
    if "sync_mode" not in install_cols:
        op.add_column(
            "deck_installs",
            sa.Column("sync_mode", sa.String(32), nullable=False, server_default="manual"),
        )
        op.create_index(
            "ix_deck_installs_sync_mode",
            "deck_installs",
            ["sync_mode"],
        )
    if "last_auto_updated_at" not in install_cols:
        op.add_column(
            "deck_installs",
            sa.Column("last_auto_updated_at", sa.DateTime(), nullable=True),
        )
        op.create_index(
            "ix_deck_installs_last_auto_updated_at",
            "deck_installs",
            ["last_auto_updated_at"],
        )
    if "pending_conflict_count" not in install_cols:
        op.add_column(
            "deck_installs",
            sa.Column("pending_conflict_count", sa.Integer(), nullable=False, server_default="0"),
        )

    # 3. deck_install_rebases
    rebase_cols = _get_column_names("deck_install_rebases")
    if "mode" not in rebase_cols:
        op.add_column(
            "deck_install_rebases",
            sa.Column("mode", sa.String(32), nullable=False, server_default="manual"),
        )
        op.create_index(
            "ix_deck_install_rebases_mode",
            "deck_install_rebases",
            ["mode"],
        )

    # 4. deck_releases
    release_cols = _get_column_names("deck_releases")
    if "publish_mode" not in release_cols:
        op.add_column(
            "deck_releases",
            sa.Column("publish_mode", sa.String(32), nullable=False, server_default="manual"),
        )
        op.create_index(
            "ix_deck_releases_publish_mode",
            "deck_releases",
            ["publish_mode"],
        )


def downgrade():
    # Releases
    release_cols = _get_column_names("deck_releases")
    if "publish_mode" in release_cols:
        op.drop_column("deck_releases", "publish_mode")

    # Rebases
    rebase_cols = _get_column_names("deck_install_rebases")
    if "mode" in rebase_cols:
        op.drop_column("deck_install_rebases", "mode")

    # Installs
    install_cols = _get_column_names("deck_installs")
    if "pending_conflict_count" in install_cols:
        op.drop_column("deck_installs", "pending_conflict_count")
    if "last_auto_updated_at" in install_cols:
        op.drop_column("deck_installs", "last_auto_updated_at")
    if "sync_mode" in install_cols:
        op.drop_column("deck_installs", "sync_mode")
    if "auto_update_enabled" in install_cols:
        op.drop_column("deck_installs", "auto_update_enabled")

    # Marketplace Items
    item_cols = _get_column_names("deck_marketplace_items")
    if "last_auto_publish_error" in item_cols:
        op.drop_column("deck_marketplace_items", "last_auto_publish_error")
    if "last_auto_published_at" in item_cols:
        op.drop_column("deck_marketplace_items", "last_auto_published_at")
    if "auto_publish_enabled" in item_cols:
        op.drop_column("deck_marketplace_items", "auto_publish_enabled")
