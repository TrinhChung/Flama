"""Persist asynchronous study-batch retry attempts.

Revision ID: 20260925_000045
Revises: 20260924_000044
Create Date: 2026-09-25 00:00:45

This additive column makes the existing admission row the retry-budget source
after Redis loss or a worker restart. Existing admissions begin at zero.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260925_000045"
down_revision = "20260924_000044"
branch_labels = None
depends_on = None

TABLE_NAME = "study_session_batches"
COLUMN_NAME = "attempt_count"


def _column(bind: sa.engine.Connection) -> dict[str, object] | None:
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE_NAME):
        raise RuntimeError("Cannot extend study batches: admission table is missing.")
    return next(
        (row for row in inspector.get_columns(TABLE_NAME) if row["name"] == COLUMN_NAME),
        None,
    )


def _verify(column: dict[str, object] | None) -> None:
    if column is None:
        raise RuntimeError("Study batch attempt counter was not created.")
    if (
        not isinstance(column["type"], sa.Integer)
        or bool(column["nullable"])
        or str(column.get("default")).strip("()'\" ") != "0"
    ):
        raise RuntimeError("Study batch attempt counter has an incompatible contract.")


def upgrade() -> None:
    bind = op.get_bind()
    if _column(bind) is None:
        op.add_column(
            TABLE_NAME,
            sa.Column(COLUMN_NAME, sa.Integer(), nullable=False, server_default="0"),
        )
    _verify(_column(bind))


def downgrade() -> None:
    bind = op.get_bind()
    column = _column(bind)
    if column is None:
        return
    _verify(column)
    in_flight = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM study_session_batches "
            "WHERE status = 'enqueued' OR attempt_count <> 0"
        )
    ).scalar_one()
    if in_flight:
        raise RuntimeError(
            "Cannot discard study-batch retry state while admissions or attempts remain."
        )
    op.drop_column(TABLE_NAME, COLUMN_NAME)
