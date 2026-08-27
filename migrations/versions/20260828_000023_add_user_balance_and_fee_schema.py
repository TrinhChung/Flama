"""add user balance and fee schema

Revision ID: 20260828_000023
Revises: 20260827_000022
Create Date: 2026-08-28 00:00:23
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260828_000023"
down_revision = "20260827_000022"
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
    if _has_table("users"):
        if not _has_column("users", "balance_amount_minor"):
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "balance_amount_minor",
                        sa.Integer(),
                        nullable=False,
                        server_default=sa.text("0"),
                    )
                )
        if not _has_column("users", "custom_platform_fee_percent"):
            with op.batch_alter_table("users") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "custom_platform_fee_percent",
                        sa.Float(),
                        nullable=True,
                    )
                )

    if _has_table("user_roles"):
        if not _has_column("user_roles", "default_platform_fee_percent"):
            with op.batch_alter_table("user_roles") as batch_op:
                batch_op.add_column(
                    sa.Column(
                        "default_platform_fee_percent",
                        sa.Float(),
                        nullable=False,
                        server_default=sa.text("10.0"),
                    )
                )

    if not _has_table("user_balance_transactions"):
        op.create_table(
            "user_balance_transactions",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("buyer_user_id", sa.Integer(), nullable=True),
            sa.Column("payment_order_id", sa.String(length=36), nullable=True),
            sa.Column("payment_order_item_id", sa.String(length=36), nullable=True),
            sa.Column("transaction_type", sa.String(length=50), nullable=False, server_default="deck_sale"),
            sa.Column("gross_amount_minor", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("platform_fee_percent", sa.Float(), nullable=False, server_default=sa.text("0.0")),
            sa.Column("platform_fee_amount_minor", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("net_amount_minor", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("balance_after_minor", sa.Integer(), nullable=False, server_default=sa.text("0")),
            sa.Column("description", sa.String(length=255), nullable=False, server_default=""),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["buyer_user_id"], ["users.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["payment_order_id"], ["payment_orders.id"], ondelete="SET NULL"),
            sa.ForeignKeyConstraint(["payment_order_item_id"], ["payment_order_items.id"], ondelete="SET NULL"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "payment_order_item_id",
                "user_id",
                "transaction_type",
                name="uq_user_balance_tx_order_item_user_type",
            ),
        )
        op.create_index("ix_user_balance_transactions_user_id", "user_balance_transactions", ["user_id"])
        op.create_index("ix_user_balance_transactions_buyer_user_id", "user_balance_transactions", ["buyer_user_id"])
        op.create_index("ix_user_balance_transactions_payment_order_id", "user_balance_transactions", ["payment_order_id"])
        op.create_index("ix_user_balance_transactions_payment_order_item_id", "user_balance_transactions", ["payment_order_item_id"])
        op.create_index("ix_user_balance_transactions_transaction_type", "user_balance_transactions", ["transaction_type"])
        op.create_index("ix_user_balance_tx_user_created", "user_balance_transactions", ["user_id", "created_at"])


def downgrade():
    if _has_table("user_balance_transactions"):
        op.drop_table("user_balance_transactions")

    if _has_table("user_roles"):
        if _has_column("user_roles", "default_platform_fee_percent"):
            with op.batch_alter_table("user_roles") as batch_op:
                batch_op.drop_column("default_platform_fee_percent")

    if _has_table("users"):
        if _has_column("users", "custom_platform_fee_percent"):
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("custom_platform_fee_percent")
        if _has_column("users", "balance_amount_minor"):
            with op.batch_alter_table("users") as batch_op:
                batch_op.drop_column("balance_amount_minor")
