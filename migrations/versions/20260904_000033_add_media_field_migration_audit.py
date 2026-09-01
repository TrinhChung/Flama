"""add typed media-field migration audit tables

Revision ID: 20260904_000033
Revises: 20260903_000032
Create Date: 2026-09-04 00:00:33
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260904_000033"
down_revision = "20260903_000032"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("media_field_migration_runs"):
        op.create_table(
            "media_field_migration_runs",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("mode", sa.String(32), nullable=False),
            sa.Column("status", sa.String(32), nullable=False),
            sa.Column("scope_user_id", sa.Integer(), nullable=True),
            sa.Column("scope_deck_id", sa.Integer(), nullable=True),
            sa.Column("stats", sa.JSON(), nullable=False),
            sa.Column("started_at", sa.DateTime(), nullable=False),
            sa.Column("finished_at", sa.DateTime(), nullable=True),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_media_field_migration_runs_status", "media_field_migration_runs", ["status"])
        op.create_index("ix_media_field_migration_runs_scope_user_id", "media_field_migration_runs", ["scope_user_id"])
        op.create_index("ix_media_field_migration_runs_scope_deck_id", "media_field_migration_runs", ["scope_deck_id"])

    inspector = sa.inspect(bind)
    if not inspector.has_table("media_field_migration_items"):
        op.create_table(
            "media_field_migration_items",
            sa.Column("id", sa.String(36), nullable=False),
            sa.Column("run_id", sa.String(36), nullable=False),
            sa.Column("entity_type", sa.String(32), nullable=False),
            sa.Column("entity_id", sa.String(36), nullable=False),
            sa.Column("field_name", sa.String(255), nullable=False),
            sa.Column("field_type", sa.String(32), nullable=True),
            sa.Column("action", sa.String(32), nullable=False),
            sa.Column("reason", sa.String(64), nullable=False),
            sa.Column("old_value", sa.Text(), nullable=True),
            sa.Column("new_value", sa.Text(), nullable=True),
            sa.Column("semantic_change", sa.Boolean(), nullable=False),
            sa.Column("user_id", sa.Integer(), nullable=True),
            sa.Column("deck_id", sa.Integer(), nullable=True),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.ForeignKeyConstraint(
                ["run_id"],
                ["media_field_migration_runs.id"],
                name="fk_media_field_migration_items_run",
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
        )
        for column in ("run_id", "entity_type", "entity_id", "action", "reason", "user_id", "deck_id"):
            op.create_index(
                f"ix_media_field_migration_items_{column}",
                "media_field_migration_items",
                [column],
            )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table("media_field_migration_items"):
        op.drop_table("media_field_migration_items")
    inspector = sa.inspect(bind)
    if inspector.has_table("media_field_migration_runs"):
        op.drop_table("media_field_migration_runs")
