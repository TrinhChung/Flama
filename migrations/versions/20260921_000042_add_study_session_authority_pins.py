"""add inert Study Session NOTE authority pins

Revision ID: 20260921_000042
Revises: 20260921_000041
Create Date: 2026-09-21 00:00:42

The new table is additive and empty. Existing v2/v3 sessions keep their
CardProgress CAS meaning and never acquire a row. Only a future v4 NOTE session
may write a pin. This migration does not admit NOTE enrollment.
"""

from __future__ import annotations

from importlib import import_module

from alembic import op
import sqlalchemy as sa

from models.study_session_authority_pin import StudySessionAuthorityPin


revision = "20260921_000042"
down_revision = "20260921_000041"
branch_labels = None
depends_on = None

TARGET_TABLES = (StudySessionAuthorityPin.__table__,)
REQUIRED_PARENT_TABLES = {
    "users",
    "study_session_cards",
    "study_progress_subjects",
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
            "Cannot add Study Session authority pins: missing parent tables "
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
            "Study Session authority-pin downgrade is prohibited while tables "
            "contain rows: " + ", ".join(nonempty) + ". Use forward repair."
        )
    for table in reversed(TARGET_TABLES):
        if table.name in existing:
            table.drop(bind=bind, checkfirst=False)
