"""add marketplace taxonomy tables

Revision ID: 20260827_000022
Revises: 20260826_000021
Create Date: 2026-08-27 00:00:22
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260827_000022"
down_revision = "20260826_000021"
branch_labels = None
depends_on = None


def _inspector():
    return sa.inspect(op.get_bind())


def _has_table(table_name: str) -> bool:
    inspector = _inspector()
    return inspector.has_table(table_name)


def _columns(table_name: str) -> set[str]:
    inspector = _inspector()
    if not inspector.has_table(table_name):
        return set()
    return {str(row["name"]) for row in inspector.get_columns(table_name)}


def upgrade() -> None:
    # 1. taxonomy_domains
    if not _has_table("taxonomy_domains"):
        op.create_table(
            "taxonomy_domains",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id"),
        )

    # 2. taxonomy_subjects
    if not _has_table("taxonomy_subjects"):
        op.create_table(
            "taxonomy_subjects",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("domain_id", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["domain_id"], ["taxonomy_domains.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_taxonomy_subjects_domain_id", "taxonomy_subjects", ["domain_id"], unique=False)

    # 3. taxonomy_frameworks
    if not _has_table("taxonomy_frameworks"):
        op.create_table(
            "taxonomy_frameworks",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("subject_id", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["subject_id"], ["taxonomy_subjects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_taxonomy_frameworks_subject_id", "taxonomy_frameworks", ["subject_id"], unique=False)

    # 4. taxonomy_framework_levels
    if not _has_table("taxonomy_framework_levels"):
        op.create_table(
            "taxonomy_framework_levels",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("framework_id", sa.String(length=64), nullable=False),
            sa.Column("subject_id", sa.String(length=64), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("difficulty_band", sa.String(length=32), nullable=False, server_default="beginner"),
            sa.Column("suggested_tags", sa.JSON(), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(["framework_id"], ["taxonomy_frameworks.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["subject_id"], ["taxonomy_subjects.id"], ondelete="CASCADE"),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_taxonomy_framework_levels_framework_id", "taxonomy_framework_levels", ["framework_id"], unique=False)
        op.create_index("ix_taxonomy_framework_levels_subject_id", "taxonomy_framework_levels", ["subject_id"], unique=False)

    # 5. taxonomy_options
    if not _has_table("taxonomy_options"):
        op.create_table(
            "taxonomy_options",
            sa.Column("id", sa.String(length=64), nullable=False),
            sa.Column("option_type", sa.String(length=32), nullable=False),
            sa.Column("label", sa.String(length=128), nullable=False),
            sa.Column("sub_label", sa.String(length=255), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("1")),
            sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.PrimaryKeyConstraint("id", "option_type"),
        )

    # 6. taxonomy_subject_option_maps
    if not _has_table("taxonomy_subject_option_maps"):
        op.create_table(
            "taxonomy_subject_option_maps",
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("subject_id", sa.String(length=64), nullable=False),
            sa.Column("option_id", sa.String(length=64), nullable=False),
            sa.Column("option_type", sa.String(length=32), nullable=False),
            sa.ForeignKeyConstraint(["subject_id"], ["taxonomy_subjects.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(
                ["option_id", "option_type"],
                ["taxonomy_options.id", "taxonomy_options.option_type"],
                ondelete="CASCADE",
            ),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("subject_id", "option_id", "option_type", name="uq_taxonomy_sub_opt_map"),
        )
        op.create_index("ix_taxonomy_subject_option_maps_subject_id", "taxonomy_subject_option_maps", ["subject_id"], unique=False)
        op.create_index("ix_taxonomy_subject_option_maps_option_id", "taxonomy_subject_option_maps", ["option_id"], unique=False)
        op.create_index("ix_taxonomy_subject_option_maps_option_type", "taxonomy_subject_option_maps", ["option_type"], unique=False)


def downgrade() -> None:
    # Drop tables in reverse topological order
    for table_name in (
        "taxonomy_subject_option_maps",
        "taxonomy_options",
        "taxonomy_framework_levels",
        "taxonomy_frameworks",
        "taxonomy_subjects",
        "taxonomy_domains",
    ):
        if _has_table(table_name):
            op.drop_table(table_name)
