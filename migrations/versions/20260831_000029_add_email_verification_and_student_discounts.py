"""add email verification and student discounts schema

Revision ID: 20260831_000029
Revises: 20260831_000028
Create Date: 2026-08-31 00:00:29
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260831_000029"
down_revision = "20260831_000028"
branch_labels = None
depends_on = None


def _get_column_names(table_name: str) -> set[str]:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table(table_name):
        return set()
    return {col["name"] for col in inspector.get_columns(table_name)}


def _has_table(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def upgrade():
    # 1. users: add email_verified_at and email_verification_source
    user_cols = _get_column_names("users")
    if "email_verified_at" not in user_cols:
        op.add_column(
            "users",
            sa.Column("email_verified_at", sa.DateTime(), nullable=True),
        )
    if "email_verification_source" not in user_cols:
        op.add_column(
            "users",
            sa.Column("email_verification_source", sa.String(32), nullable=True),
        )

    # Backfill legacy accounts as verified
    op.execute(
        sa.text(
            "UPDATE users SET "
            "email_verified_at = COALESCE(created_at, NOW()), "
            "email_verification_source = 'legacy' "
            "WHERE email_verified_at IS NULL"
        )
    )

    # 2. email_verification_tokens
    if not _has_table("email_verification_tokens"):
        op.create_table(
            "email_verification_tokens",
            sa.Column("id", sa.Integer(), primary_key=True),
            sa.Column(
                "user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("email", sa.String(255), nullable=False),
            sa.Column("token_hash", sa.String(64), nullable=False),
            sa.Column("token_type", sa.String(16), nullable=False, server_default="code"),
            sa.Column("attempts_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("used_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint("token_hash", name="uq_email_verification_tokens_token_hash"),
        )
        op.create_index(
            "ix_email_verification_tokens_user_id",
            "email_verification_tokens",
            ["user_id"],
        )
        op.create_index(
            "ix_email_verification_tokens_token_hash",
            "email_verification_tokens",
            ["token_hash"],
        )
        op.create_index(
            "ix_email_verification_tokens_email",
            "email_verification_tokens",
            ["email"],
        )
        op.create_index(
            "ix_email_verification_tokens_expires_at",
            "email_verification_tokens",
            ["expires_at"],
        )
        op.create_index(
            "ix_email_verification_tokens_user_active",
            "email_verification_tokens",
            ["user_id", "used_at", "revoked_at"],
        )

    # 3. deck_marketplace_items: student_offer_mode, student_discount_percent
    item_cols = _get_column_names("deck_marketplace_items")
    if "student_offer_mode" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("student_offer_mode", sa.String(32), nullable=False, server_default="none"),
        )
    if "student_discount_percent" not in item_cols:
        op.add_column(
            "deck_marketplace_items",
            sa.Column("student_discount_percent", sa.Integer(), nullable=True),
        )


def downgrade():
    item_cols = _get_column_names("deck_marketplace_items")
    if "student_discount_percent" in item_cols:
        op.drop_column("deck_marketplace_items", "student_discount_percent")
    if "student_offer_mode" in item_cols:
        op.drop_column("deck_marketplace_items", "student_offer_mode")

    if _has_table("email_verification_tokens"):
        op.drop_table("email_verification_tokens")

    user_cols = _get_column_names("users")
    if "email_verification_source" in user_cols:
        op.drop_column("users", "email_verification_source")
    if "email_verified_at" in user_cols:
        op.drop_column("users", "email_verified_at")
