"""add narrow learner/Note history-cut index

Revision ID: 20260924_000044
Revises: 20260921_000043
Create Date: 2026-09-24 00:00:44

The index is additive. It lets the NOTE history cut lock detached and wrongly
linked facts for one learner/Note without scanning every fact for that learner.
No history row is rewritten or deleted.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260924_000044"
down_revision = "20260921_000043"
branch_labels = None
depends_on = None

TABLE_NAME = "study_progress_history_facts"
INDEX_NAME = "ix_sp_history_learner_note_order"
INDEX_COLUMNS = ["learner_user_id", "logical_note_key", "occurred_at", "id"]


def _existing_index(bind: sa.engine.Connection) -> dict[str, object] | None:
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE_NAME):
        raise RuntimeError("Cannot index NOTE history: history fact table is missing.")
    return next(
        (
            index
            for index in inspector.get_indexes(TABLE_NAME)
            if index.get("name") == INDEX_NAME
        ),
        None,
    )


def upgrade() -> None:
    bind = op.get_bind()
    existing = _existing_index(bind)
    if existing is None:
        op.create_index(INDEX_NAME, TABLE_NAME, INDEX_COLUMNS, unique=False)
        existing = _existing_index(bind)
    if existing is None or list(existing.get("column_names") or []) != INDEX_COLUMNS:
        raise RuntimeError("NOTE history-cut index does not match the required columns.")


def downgrade() -> None:
    bind = op.get_bind()
    existing = _existing_index(bind)
    if existing is None:
        return
    if list(existing.get("column_names") or []) != INDEX_COLUMNS:
        raise RuntimeError("Refusing to drop an unexpected NOTE history-cut index.")
    note_count = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM study_authority_enrollments "
            "WHERE mode_code = 'NOTE'"
        )
    ).scalar_one()
    if note_count:
        raise RuntimeError(
            "Cannot drop the NOTE history-cut index while NOTE learners exist: "
            f"{note_count}. Fence them back through forward repair."
        )
    op.drop_index(INDEX_NAME, table_name=TABLE_NAME)
