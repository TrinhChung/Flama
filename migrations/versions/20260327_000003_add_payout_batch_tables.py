"""add payout batch tables

Revision ID: 20260327_000003
Revises: 20260327_000002
Create Date: 2026-03-27 00:00:03
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260327_000003"
down_revision = "20260327_000002"
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
    if not _table_exists("payout_batches"):
        op.create_table(
            "payout_batches",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column("reference_id", sa.String(length=96), nullable=False),
            sa.Column("client_reference_key", sa.String(length=96), nullable=False),
            sa.Column("request_fingerprint", sa.String(length=64), nullable=False),
            sa.Column("provider_payout_id", sa.String(length=128), nullable=True),
            sa.Column("internal_status", sa.String(length=32), nullable=False),
            sa.Column("provider_approval_state", sa.String(length=32), nullable=True),
            sa.Column("validate_destination", sa.Boolean(), nullable=False),
            sa.Column("item_count", sa.Integer(), nullable=False),
            sa.Column("category_json", sa.Text(), nullable=False),
            sa.Column("request_payload_json", sa.Text(), nullable=False),
            sa.Column("response_payload_json", sa.Text(), nullable=True),
            sa.Column("error_payload_json", sa.Text(), nullable=True),
            sa.Column(
                "created_by_admin_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("submitted_at", sa.DateTime(), nullable=True),
            sa.Column("last_synced_at", sa.DateTime(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("reference_id", name="uq_payout_batches_reference_id"),
            sa.UniqueConstraint("provider_payout_id", name="uq_payout_batches_provider_payout_id"),
        )
    _create_index_if_missing("ix_payout_batches_reference_id", "payout_batches", ["reference_id"], unique=True)
    _create_index_if_missing(
        "ix_payout_batches_client_reference_key",
        "payout_batches",
        ["client_reference_key"],
    )
    _create_index_if_missing(
        "ix_payout_batches_request_fingerprint",
        "payout_batches",
        ["request_fingerprint"],
    )
    _create_index_if_missing(
        "ix_payout_batches_provider_payout_id",
        "payout_batches",
        ["provider_payout_id"],
        unique=True,
    )
    _create_index_if_missing("ix_payout_batches_internal_status", "payout_batches", ["internal_status"])
    _create_index_if_missing(
        "ix_payout_batches_provider_approval_state",
        "payout_batches",
        ["provider_approval_state"],
    )
    _create_index_if_missing("ix_payout_batches_created_by_admin_id", "payout_batches", ["created_by_admin_id"])
    _create_index_if_missing("ix_payout_batches_submitted_at", "payout_batches", ["submitted_at"])
    _create_index_if_missing("ix_payout_batches_created_at", "payout_batches", ["created_at"])

    if not _table_exists("payout_batch_items"):
        op.create_table(
            "payout_batch_items",
            sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
            sa.Column(
                "batch_id",
                sa.Integer(),
                sa.ForeignKey("payout_batches.id", ondelete="CASCADE"),
                nullable=False,
            ),
            sa.Column("reference_id", sa.String(length=128), nullable=False),
            sa.Column("client_reference_key", sa.String(length=96), nullable=False),
            sa.Column("amount", sa.Integer(), nullable=False),
            sa.Column("description", sa.String(length=255), nullable=False),
            sa.Column("to_bin", sa.String(length=12), nullable=False),
            sa.Column("to_account_number", sa.String(length=64), nullable=False),
            sa.Column("internal_status", sa.String(length=32), nullable=False),
            sa.Column("provider_transaction_id", sa.String(length=128), nullable=True),
            sa.Column("provider_reference", sa.String(length=128), nullable=True),
            sa.Column("provider_state", sa.String(length=32), nullable=True),
            sa.Column("response_payload_json", sa.Text(), nullable=True),
            sa.Column("error_code", sa.String(length=64), nullable=True),
            sa.Column("error_message", sa.String(length=255), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.UniqueConstraint("reference_id", name="uq_payout_batch_items_reference_id"),
        )
    _create_index_if_missing("ix_payout_batch_items_batch_id", "payout_batch_items", ["batch_id"])
    _create_index_if_missing(
        "ix_payout_batch_items_reference_id",
        "payout_batch_items",
        ["reference_id"],
        unique=True,
    )
    _create_index_if_missing(
        "ix_payout_batch_items_client_reference_key",
        "payout_batch_items",
        ["client_reference_key"],
    )
    _create_index_if_missing(
        "ix_payout_batch_items_internal_status",
        "payout_batch_items",
        ["internal_status"],
    )
    _create_index_if_missing(
        "ix_payout_batch_items_provider_transaction_id",
        "payout_batch_items",
        ["provider_transaction_id"],
    )
    _create_index_if_missing(
        "ix_payout_batch_items_provider_reference",
        "payout_batch_items",
        ["provider_reference"],
    )
    _create_index_if_missing(
        "ix_payout_batch_items_provider_state",
        "payout_batch_items",
        ["provider_state"],
    )


def downgrade() -> None:
    pass
