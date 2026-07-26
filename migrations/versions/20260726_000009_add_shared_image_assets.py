"""add shared image asset library

Revision ID: 20260726_000009
Revises: 20260401_000008
Create Date: 2026-07-26 00:00:09
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260726_000009"
down_revision = "20260401_000008"
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


def _create_index_if_missing(
    index_name: str,
    table_name: str,
    columns: list[str],
) -> None:
    if index_name in _index_names(table_name):
        return
    op.create_index(index_name, table_name, columns, unique=False)


def upgrade() -> None:
    if not _table_exists("shared_image_assets"):
        op.create_table(
            "shared_image_assets",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("image_key", sa.String(length=120), nullable=False),
            sa.Column("description", sa.Text(), nullable=True),
            sa.Column("filename", sa.String(length=255), nullable=True),
            sa.Column("mime_type", sa.String(length=255), nullable=True),
            sa.Column("storage_path", sa.String(length=1024), nullable=True),
            sa.Column("sha256", sa.String(length=64), nullable=True),
            sa.Column("size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default=sa.true()),
            sa.Column(
                "created_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column(
                "updated_by_user_id",
                sa.Integer(),
                sa.ForeignKey("users.id", ondelete="SET NULL"),
                nullable=True,
            ),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "image_key",
                name="uq_shared_image_assets_image_key",
            ),
        )
    _create_index_if_missing(
        "ix_shared_image_assets_is_enabled",
        "shared_image_assets",
        ["is_enabled"],
    )
    _create_index_if_missing(
        "ix_shared_image_assets_updated_at",
        "shared_image_assets",
        ["updated_at"],
    )


def downgrade() -> None:
    if _table_exists("shared_image_assets"):
        op.drop_table("shared_image_assets")
