"""Add the Note authority fence to Connect source Card refs.

Revision ID: 20261002_000048
Revises: 20261001_000047
Create Date: 2026-10-02 00:00:48

Expand only (ADR P9-03 §2.6); no existing value changes:

* ``connect_source_card_refs.applied_authority_revision`` (NULL): the Note
  authority revision a ref last applied or confirmed under ``CANONICAL_V1``.
* ``connect_source_card_refs.applied_local_revision_state`` (NULL):
  ``LEGACY_CARD_PROGRESS`` | ``AUTHORITY`` | ``NEEDS_CONFIRMATION``, with a
  CHECK that ``AUTHORITY`` carries a revision.

Nothing writes them while the profile is ``PROJECTION_V1``; the P9-06 switch
maps each existing ref under the write freeze. MySQL applies both columns
and the CHECK in one ALTER TABLE under a bounded ``lock_wait_timeout``.
Downgrade refuses once any ref holds an authority revision or state.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from models.connect_source_card_ref import APPLIED_STATE_CHECK


revision = "20261002_000048"
down_revision = "20261001_000047"
branch_labels = None
depends_on = None

TABLE = "connect_source_card_refs"
CHECK_NAME = "ck_connect_source_card_refs_applied_state"
_LOCK_WAIT_SECONDS = 30


def _columns(bind) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(TABLE)}


def _checks(bind) -> set[str]:
    return {row["name"] for row in sa.inspect(bind).get_check_constraints(TABLE)}


def _alter(bind, clauses: list[str]) -> None:
    if not clauses:
        return
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {_LOCK_WAIT_SECONDS}"))
    try:
        bind.execute(sa.text(f"ALTER TABLE {TABLE} " + ", ".join(clauses)))
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def upgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind)
    if bind.dialect.name != "mysql":
        # SQLite schemas come from model metadata in tests; add only columns.
        with op.batch_alter_table(TABLE) as batch:
            if "applied_authority_revision" not in columns:
                batch.add_column(sa.Column("applied_authority_revision", sa.BigInteger(), nullable=True))
            if "applied_local_revision_state" not in columns:
                batch.add_column(sa.Column("applied_local_revision_state", sa.String(32), nullable=True))
        return
    clauses = []
    if "applied_authority_revision" not in columns:
        clauses.append("ADD COLUMN applied_authority_revision BIGINT NULL AFTER applied_local_revision")
    if "applied_local_revision_state" not in columns:
        clauses.append("ADD COLUMN applied_local_revision_state VARCHAR(32) NULL AFTER applied_authority_revision")
    if CHECK_NAME not in _checks(bind):
        clauses.append(f"ADD CONSTRAINT {CHECK_NAME} CHECK ({APPLIED_STATE_CHECK})")
    _alter(bind, clauses)


def downgrade() -> None:
    bind = op.get_bind()
    columns = _columns(bind)
    if {"applied_authority_revision", "applied_local_revision_state"} & columns:
        used = bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {TABLE} WHERE applied_authority_revision IS NOT NULL "
            "OR applied_local_revision_state IS NOT NULL"
        )).scalar_one()
        if used:
            raise RuntimeError(f"Refusing downgrade: {used} Connect refs hold a Note authority fence.")
    if bind.dialect.name != "mysql":
        checks = _checks(bind)
        with op.batch_alter_table(TABLE) as batch:
            if CHECK_NAME in checks:
                batch.drop_constraint(CHECK_NAME, type_="check")
            for name in ("applied_local_revision_state", "applied_authority_revision"):
                if name in columns:
                    batch.drop_column(name)
        return
    clauses = []
    if CHECK_NAME in _checks(bind):
        clauses.append(f"DROP CHECK {CHECK_NAME}")
    for name in ("applied_local_revision_state", "applied_authority_revision"):
        if name in columns:
            clauses.append(f"DROP COLUMN {name}")
    _alter(bind, clauses)
