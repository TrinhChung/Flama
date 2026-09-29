"""add inert NOTE authority command receipts

Revision ID: 20260921_000041
Revises: 20260921_000040
Create Date: 2026-09-21 00:00:41

This additive receipt table is unreachable from product routes while revision
40 still permits only LEGACY enrollment. It does not widen the authority mode
constraint or backfill any rows.
"""

from __future__ import annotations

from importlib import import_module

from alembic import op
import sqlalchemy as sa

from models.study_authority_command_receipt import StudyAuthorityCommandReceipt


revision = "20260921_000041"
down_revision = "20260921_000040"
branch_labels = None
depends_on = None

TARGET_TABLES = (StudyAuthorityCommandReceipt.__table__,)
REQUIRED_PARENT_TABLES = {
    "users",
    "study_progress_subjects",
    "study_progress_history_facts",
    "review_events",
}


def _assert_table_contract(bind: sa.engine.Connection, table: sa.Table) -> None:
    foundation = import_module(
        "migrations.versions.20260921_000040_add_study_authority_fence"
    )
    foundation._assert_table_contract(bind, table)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    missing = sorted(REQUIRED_PARENT_TABLES - existing)
    if missing:
        raise RuntimeError(
            "Cannot add NOTE authority receipts: missing parent tables "
            + ", ".join(missing)
            + "."
        )
    for table in TARGET_TABLES:
        if table.name not in existing:
            table.create(bind=bind, checkfirst=False)
            existing.add(table.name)
        _assert_table_contract(bind, table)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    nonempty = [
        f"{table.name}={count}"
        for table in TARGET_TABLES
        if table.name in existing
        if (
            count := bind.execute(
                sa.select(sa.func.count()).select_from(table)
            ).scalar_one()
        )
    ]
    if nonempty:
        raise RuntimeError(
            "NOTE authority receipt downgrade is prohibited while tables contain "
            "rows: " + ", ".join(nonempty) + ". Use forward repair."
        )
    for table in reversed(TARGET_TABLES):
        if table.name in existing:
            table.drop(bind=bind, checkfirst=False)
