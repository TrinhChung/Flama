"""add image_assets and admin_security_alerts tables

Revision ID: 20260831_000028
Revises: 20260831_000027
Create Date: 2026-08-31 00:00:28
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260831_000028"
down_revision = "20260831_000027"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "image_assets" not in tables:
        op.create_table(
            "image_assets",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("owner_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("source_type", sa.String(32), nullable=False, server_default="upload"),
            sa.Column("source_url", sa.String(2048), nullable=True),
            sa.Column("display_url", sa.String(2048), nullable=False),
            sa.Column("managed_url", sa.String(2048), nullable=True),
            sa.Column("storage_path", sa.String(1024), nullable=True),
            sa.Column("original_filename", sa.String(255), nullable=True),
            sa.Column("original_mime_type", sa.String(120), nullable=True),
            sa.Column("output_mime_type", sa.String(120), nullable=True, server_default="image/webp"),
            sa.Column("original_width", sa.Integer(), nullable=True),
            sa.Column("original_height", sa.Integer(), nullable=True),
            sa.Column("output_width", sa.Integer(), nullable=True),
            sa.Column("output_height", sa.Integer(), nullable=True),
            sa.Column("original_size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("output_size_bytes", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("usage_type", sa.String(50), nullable=False, server_default="general"),
            sa.Column("preset", sa.String(50), nullable=True),
            sa.Column("processing_status", sa.String(32), nullable=False, server_default="pending"),
            sa.Column("security_status", sa.String(32), nullable=False, server_default="safe"),
            sa.Column("security_reason", sa.String(255), nullable=True),
            sa.Column("sha256", sa.String(64), nullable=True),
            sa.Column("retry_count", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("last_error", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            sa.Column("processed_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_image_assets_owner_user_id", "image_assets", ["owner_user_id"])
        op.create_index("ix_image_assets_source_type", "image_assets", ["source_type"])
        op.create_index("ix_image_assets_usage_type", "image_assets", ["usage_type"])
        op.create_index("ix_image_assets_processing_status", "image_assets", ["processing_status"])
        op.create_index("ix_image_assets_security_status", "image_assets", ["security_status"])
        op.create_index("ix_image_assets_sha256", "image_assets", ["sha256"])
        op.create_index("ix_image_assets_created_at", "image_assets", ["created_at"])
        op.create_index("ix_image_assets_owner_status", "image_assets", ["owner_user_id", "processing_status"])
        op.create_index("ix_image_assets_usage_status", "image_assets", ["usage_type", "processing_status"])

    if "admin_security_alerts" not in tables:
        op.create_table(
            "admin_security_alerts",
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("severity", sa.String(20), nullable=False, server_default="warning"),
            sa.Column("threat_type", sa.String(60), nullable=False),
            sa.Column("source_ip", sa.String(64), nullable=True),
            sa.Column("source_url", sa.String(2048), nullable=True),
            sa.Column("message", sa.Text(), nullable=False),
            sa.Column("details", sa.JSON(), nullable=False),
            sa.Column("is_resolved", sa.Boolean(), nullable=False, server_default=sa.text("0")),
            sa.Column("resolved_by_user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("resolved_at", sa.DateTime(), nullable=True),
        )
        op.create_index("ix_admin_security_alerts_user_id", "admin_security_alerts", ["user_id"])
        op.create_index("ix_admin_security_alerts_severity", "admin_security_alerts", ["severity"])
        op.create_index("ix_admin_security_alerts_threat_type", "admin_security_alerts", ["threat_type"])
        op.create_index("ix_admin_security_alerts_is_resolved", "admin_security_alerts", ["is_resolved"])
        op.create_index("ix_admin_security_alerts_created_at", "admin_security_alerts", ["created_at"])
        op.create_index("ix_admin_security_alerts_threat_resolved", "admin_security_alerts", ["threat_type", "is_resolved"])


def downgrade():
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    if "admin_security_alerts" in tables:
        op.drop_table("admin_security_alerts")
    if "image_assets" in tables:
        op.drop_table("image_assets")
