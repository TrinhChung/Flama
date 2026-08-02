"""add staged media for Flama Connect

Revision ID: 20260802_000013
Revises: 20260802_000012
Create Date: 2026-08-02 00:00:13
"""

from alembic import op
import sqlalchemy as sa


revision = "20260802_000013"
down_revision = "20260802_000012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("connect_pending_media"):
        op.create_table(
            "connect_pending_media",
            sa.Column("id", sa.String(length=36), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=False),
            sa.Column("filename", sa.String(length=255), nullable=False),
            sa.Column("mime_type", sa.String(length=64), nullable=False),
            sa.Column("storage_path", sa.String(length=1024), nullable=False),
            sa.Column("sha256", sa.String(length=64), nullable=False),
            sa.Column("size_bytes", sa.Integer(), nullable=False),
            sa.Column("expires_at", sa.DateTime(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "user_id",
                "filename",
                name="uq_connect_pending_media_user_filename",
            ),
        )
    index_names = {
        row["name"]
        for row in sa.inspect(bind).get_indexes("connect_pending_media")
        if row.get("name")
    }
    if "ix_connect_pending_media_user_id" not in index_names:
        op.create_index(
            "ix_connect_pending_media_user_id",
            "connect_pending_media",
            ["user_id"],
        )
    if "ix_connect_pending_media_expires_at" not in index_names:
        op.create_index(
            "ix_connect_pending_media_expires_at",
            "connect_pending_media",
            ["expires_at"],
        )


def downgrade() -> None:
    op.drop_table("connect_pending_media")
