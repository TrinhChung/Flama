"""add deck access keys and creator feature policies

Revision ID: 20260829_000024
Revises: 20260828_000023
Create Date: 2026-08-29 00:00:24
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260829_000024"
down_revision = "20260828_000023"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    inspector = _inspector()
    return table_name in inspector.get_table_names()


def _has_column(table_name: str, column_name: str) -> bool:
    inspector = _inspector()
    if table_name not in inspector.get_table_names():
        return False
    columns = inspector.get_columns(table_name)
    return any(c.get("name") == column_name for c in columns)


def upgrade():
    # 1. creator_feature_policies table
    if not _has_table("creator_feature_policies"):
        op.create_table(
            "creator_feature_policies",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column("feature_code", sa.String(64), unique=True, nullable=False),
            sa.Column("is_monetized", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("free_quota_per_creator", sa.Integer(), nullable=False, server_default=sa.text("-1")),
            sa.Column("price_per_key_minor", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("requires_pro_role", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        # Seed default policy row for deck_access_keys
        op.execute(
            "INSERT INTO creator_feature_policies (feature_code, is_monetized, free_quota_per_creator, price_per_key_minor, requires_pro_role, updated_at) "
            "VALUES ('deck_access_keys', 0, -1, 0, 0, CURRENT_TIMESTAMP)"
        )

    # 2. deck_access_keys table
    if not _has_table("deck_access_keys"):
        op.create_table(
            "deck_access_keys",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("deck_item_id", sa.String(36), sa.ForeignKey("deck_marketplace_items.id", ondelete="CASCADE"), nullable=False),
            sa.Column("creator_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("key_code", sa.String(64), unique=True, nullable=False),
            sa.Column("label", sa.String(150), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
            sa.Column("max_uses", sa.Integer(), nullable=True),
            sa.Column("used_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("access_duration_days", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        op.create_index("ix_deck_access_keys_deck_item_id", "deck_access_keys", ["deck_item_id"])
        op.create_index("ix_deck_access_keys_creator_user_id", "deck_access_keys", ["creator_user_id"])
        op.create_index("ix_deck_access_keys_key_code", "deck_access_keys", ["key_code"])
        op.create_index("ix_deck_access_keys_status", "deck_access_keys", ["status"])
        op.create_index("ix_deck_access_keys_expires_at", "deck_access_keys", ["expires_at"])

    # 3. deck_access_key_redemptions table
    if not _has_table("deck_access_key_redemptions"):
        op.create_table(
            "deck_access_key_redemptions",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("key_id", sa.String(36), sa.ForeignKey("deck_access_keys.id", ondelete="CASCADE"), nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("deck_install_id", sa.String(36), sa.ForeignKey("deck_installs.id", ondelete="CASCADE"), nullable=False),
            sa.Column("redeemed_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("access_expires_at", sa.DateTime(), nullable=True),
            sa.Column("status", sa.String(32), nullable=False, server_default="active"),
        )
        op.create_index("ix_deck_access_key_redemptions_key_id", "deck_access_key_redemptions", ["key_id"])
        op.create_index("ix_deck_access_key_redemptions_user_id", "deck_access_key_redemptions", ["user_id"])
        op.create_index("ix_deck_access_key_redemptions_deck_install_id", "deck_access_key_redemptions", ["deck_install_id"])
        op.create_index("ix_deck_access_key_redemptions_access_expires_at", "deck_access_key_redemptions", ["access_expires_at"])
        op.create_index("ix_deck_access_key_redemptions_status", "deck_access_key_redemptions", ["status"])
        op.create_unique_constraint("uq_deck_key_user_redemption", "deck_access_key_redemptions", ["key_id", "user_id"])


def downgrade():
    if _has_table("deck_access_key_redemptions"):
        op.drop_table("deck_access_key_redemptions")
    if _has_table("deck_access_keys"):
        op.drop_table("deck_access_keys")
    if _has_table("creator_feature_policies"):
        op.drop_table("creator_feature_policies")
