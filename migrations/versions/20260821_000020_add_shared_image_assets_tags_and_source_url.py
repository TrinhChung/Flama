"""add source_url, tags, and sha256 index to shared_image_assets

Revision ID: 20260821_000020
Revises: 20260820_000019
Create Date: 2026-08-21 00:00:20
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260821_000020"
down_revision = "20260820_000019"
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


def upgrade() -> None:
    inspector = _inspector()
    if inspector.has_table("shared_image_assets"):
        columns = _columns("shared_image_assets")
        with op.batch_alter_table("shared_image_assets") as batch_op:
            if "source_url" not in columns:
                batch_op.add_column(
                    sa.Column("source_url", sa.String(length=2048), nullable=True)
                )
            if "tags" not in columns:
                batch_op.add_column(
                    sa.Column("tags", sa.JSON(), nullable=True)
                )

        op.get_bind().execute(
            sa.text(
                "UPDATE shared_image_assets SET tags = '[]' WHERE tags IS NULL"
            )
        )

        indexes = _indexes("shared_image_assets")
        if "ix_shared_image_assets_sha256" not in indexes:
            op.create_index(
                "ix_shared_image_assets_sha256",
                "shared_image_assets",
                ["sha256"],
                unique=False,
            )


def downgrade() -> None:
    inspector = _inspector()
    if inspector.has_table("shared_image_assets"):
        indexes = _indexes("shared_image_assets")
        if "ix_shared_image_assets_sha256" in indexes:
            op.drop_index("ix_shared_image_assets_sha256", table_name="shared_image_assets")

        columns = _columns("shared_image_assets")
        with op.batch_alter_table("shared_image_assets") as batch_op:
            if "tags" in columns:
                batch_op.drop_column("tags")
            if "source_url" in columns:
                batch_op.drop_column("source_url")
