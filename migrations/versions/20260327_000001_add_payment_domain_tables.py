"""add payment domain tables

Revision ID: 20260327_000001
Revises:
Create Date: 2026-03-27 00:00:01
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260327_000001"
down_revision = None
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _table_exists(table_name: str) -> bool:
    return _inspector().has_table(table_name)


def _index_names(table_name: str) -> set[str]:
    if not _table_exists(table_name):
        return set()
    return {row["name"] for row in _inspector().get_indexes(table_name)}


def _create_index_if_missing(index_name: str, table_name: str, columns: list[str], *, unique: bool = False) -> None:
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=unique)


def upgrade() -> None:
    if not _table_exists("payment_orders"):
        op.create_table(
            "payment_orders",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column("merchant_order_code", sa.String(length=64), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "pending_payment",
                    "paid",
                    "under_review",
                    "expired",
                    "canceled",
                    "failed",
                    "refunded",
                    name="payment_order_status_enum",
                    native_enum=False,
                ),
                nullable=False,
            ),
            sa.Column(
                "grant_status",
                sa.Enum(
                    "pending",
                    "completed",
                    "failed",
                    name="payment_order_grant_status_enum",
                    native_enum=False,
                ),
                nullable=False,
            ),
            sa.Column("currency_code", sa.String(length=8), nullable=False),
            sa.Column("subtotal_amount_minor", sa.Integer(), nullable=False),
            sa.Column("discount_amount_minor", sa.Integer(), nullable=False),
            sa.Column("total_amount_minor", sa.Integer(), nullable=False),
            sa.Column("paid_at", sa.DateTime(), nullable=True),
            sa.Column("closed_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("merchant_order_code", name="uq_payment_orders_merchant_order_code"),
        )
    _create_index_if_missing("ix_payment_orders_user_id", "payment_orders", ["user_id"])
    _create_index_if_missing("ix_payment_orders_status", "payment_orders", ["status"])
    _create_index_if_missing("ix_payment_orders_grant_status", "payment_orders", ["grant_status"])
    _create_index_if_missing("ix_payment_orders_user_created_at", "payment_orders", ["user_id", "created_at"])
    _create_index_if_missing("ix_payment_orders_status_created_at", "payment_orders", ["status", "created_at"])
    _create_index_if_missing(
        "ix_payment_orders_grant_status_created_at",
        "payment_orders",
        ["grant_status", "created_at"],
    )

    if not _table_exists("payment_order_items"):
        op.create_table(
            "payment_order_items",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "order_id",
                sa.String(length=36),
                sa.ForeignKey("payment_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("product_type", sa.String(length=64), nullable=False),
            sa.Column("product_ref_id", sa.String(length=36), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("unit_amount_minor", sa.Integer(), nullable=False),
            sa.Column("line_total_amount_minor", sa.Integer(), nullable=False),
            sa.Column("title_snapshot", sa.String(length=255), nullable=False),
            sa.Column("product_snapshot_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "order_id",
                "product_type",
                "product_ref_id",
                name="uq_payment_order_items_order_product",
            ),
        )
    _create_index_if_missing("ix_payment_order_items_order_id", "payment_order_items", ["order_id"])
    _create_index_if_missing(
        "ix_payment_order_items_product_ref",
        "payment_order_items",
        ["product_type", "product_ref_id"],
    )

    if not _table_exists("payment_attempts"):
        op.create_table(
            "payment_attempts",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column(
                "order_id",
                sa.String(length=36),
                sa.ForeignKey("payment_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("provider_code", sa.String(length=64), nullable=False),
            sa.Column("payment_method_code", sa.String(length=64), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "created",
                    "pending",
                    "confirmed",
                    "manual_review",
                    "expired",
                    "canceled",
                    "failed",
                    "refunded",
                    name="payment_attempt_status_enum",
                    native_enum=False,
                ),
                nullable=False,
            ),
            sa.Column("amount_minor", sa.Integer(), nullable=False),
            sa.Column("currency_code", sa.String(length=8), nullable=False),
            sa.Column("provider_payment_id", sa.String(length=255), nullable=True),
            sa.Column("provider_order_code", sa.String(length=255), nullable=True),
            sa.Column("expected_payment_reference", sa.String(length=255), nullable=True),
            sa.Column("checkout_url", sa.Text(), nullable=True),
            sa.Column("provider_metadata_json", sa.JSON(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("confirmed_at", sa.DateTime(), nullable=True),
            sa.Column("failed_at", sa.DateTime(), nullable=True),
            sa.Column("failure_code", sa.String(length=120), nullable=True),
            sa.Column("failure_message", sa.Text(), nullable=True),
            sa.Column("manual_review_reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint(
                "provider_code",
                "provider_payment_id",
                name="uq_payment_attempts_provider_payment_id",
            ),
            sa.UniqueConstraint(
                "provider_code",
                "provider_order_code",
                name="uq_payment_attempts_provider_order_code",
            ),
        )
    _create_index_if_missing("ix_payment_attempts_order_id", "payment_attempts", ["order_id"])
    _create_index_if_missing("ix_payment_attempts_status", "payment_attempts", ["status"])
    _create_index_if_missing(
        "ix_payment_attempts_expected_payment_reference",
        "payment_attempts",
        ["expected_payment_reference"],
    )
    _create_index_if_missing("ix_payment_attempts_expires_at", "payment_attempts", ["expires_at"])
    _create_index_if_missing("ix_payment_attempts_order_created_at", "payment_attempts", ["order_id", "created_at"])
    _create_index_if_missing(
        "ix_payment_attempts_status_expires_at",
        "payment_attempts",
        ["status", "expires_at"],
    )

    if not _table_exists("payment_webhook_events"):
        op.create_table(
            "payment_webhook_events",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("provider_code", sa.String(length=64), nullable=False),
            sa.Column("event_key", sa.String(length=255), nullable=False),
            sa.Column("event_type", sa.String(length=120), nullable=False),
            sa.Column(
                "payment_attempt_id",
                sa.String(length=36),
                sa.ForeignKey("payment_attempts.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "payment_order_id",
                sa.String(length=36),
                sa.ForeignKey("payment_orders.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("signature_valid", sa.Boolean(), nullable=False),
            sa.Column(
                "processing_status",
                sa.Enum(
                    "received",
                    "processed",
                    "ignored",
                    "failed",
                    name="payment_webhook_processing_status_enum",
                    native_enum=False,
                ),
                nullable=False,
            ),
            sa.Column("error_message", sa.Text(), nullable=True),
            sa.Column("payload_json", sa.JSON(), nullable=False),
            sa.Column("received_at", sa.DateTime(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
            sa.UniqueConstraint(
                "provider_code",
                "event_key",
                name="uq_payment_webhook_events_provider_event",
            ),
        )
    _create_index_if_missing("ix_payment_webhook_events_payment_attempt_id", "payment_webhook_events", ["payment_attempt_id"])
    _create_index_if_missing("ix_payment_webhook_events_payment_order_id", "payment_webhook_events", ["payment_order_id"])
    _create_index_if_missing("ix_payment_webhook_events_processing_status", "payment_webhook_events", ["processing_status"])
    _create_index_if_missing(
        "ix_payment_webhook_events_processing_status_received_at",
        "payment_webhook_events",
        ["processing_status", "received_at"],
    )
    _create_index_if_missing(
        "ix_payment_webhook_events_payment_attempt_received_at",
        "payment_webhook_events",
        ["payment_attempt_id", "received_at"],
    )
    _create_index_if_missing(
        "ix_payment_webhook_events_payment_order_received_at",
        "payment_webhook_events",
        ["payment_order_id", "received_at"],
    )

    if not _table_exists("payment_entitlements"):
        op.create_table(
            "payment_entitlements",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
            sa.Column(
                "payment_order_id",
                sa.String(length=36),
                sa.ForeignKey("payment_orders.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "payment_order_item_id",
                sa.String(length=36),
                sa.ForeignKey("payment_order_items.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column(
                "payment_attempt_id",
                sa.String(length=36),
                sa.ForeignKey("payment_attempts.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("entitlement_type", sa.String(length=64), nullable=False),
            sa.Column("resource_type", sa.String(length=64), nullable=False),
            sa.Column("resource_ref_id", sa.String(length=36), nullable=False),
            sa.Column(
                "status",
                sa.Enum(
                    "pending",
                    "active",
                    "revoked",
                    "expired",
                    "refunded",
                    name="payment_entitlement_status_enum",
                    native_enum=False,
                ),
                nullable=False,
            ),
            sa.Column("granted_at", sa.DateTime(), nullable=True),
            sa.Column("effective_from", sa.DateTime(), nullable=True),
            sa.Column("expires_at", sa.DateTime(), nullable=True),
            sa.Column("revoked_at", sa.DateTime(), nullable=True),
            sa.Column("grant_data_json", sa.JSON(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("payment_order_item_id", name="uq_payment_entitlements_order_item"),
        )
    _create_index_if_missing("ix_payment_entitlements_user_id", "payment_entitlements", ["user_id"])
    _create_index_if_missing("ix_payment_entitlements_payment_order_id", "payment_entitlements", ["payment_order_id"])
    _create_index_if_missing(
        "ix_payment_entitlements_payment_order_item_id",
        "payment_entitlements",
        ["payment_order_item_id"],
    )
    _create_index_if_missing("ix_payment_entitlements_payment_attempt_id", "payment_entitlements", ["payment_attempt_id"])
    _create_index_if_missing("ix_payment_entitlements_status", "payment_entitlements", ["status"])
    _create_index_if_missing(
        "ix_payment_entitlements_user_status",
        "payment_entitlements",
        ["user_id", "status"],
    )
    _create_index_if_missing(
        "ix_payment_entitlements_resource_ref",
        "payment_entitlements",
        ["resource_type", "resource_ref_id"],
    )


def downgrade() -> None:
    pass
