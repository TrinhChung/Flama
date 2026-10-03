"""Drop the NOTE progress tables the consolidated row retired (P10-09).

Revision ID: 20261003_000050
Revises: 20261003_000049
Create Date: 2026-10-03 00:00:50

Since the P10-08 switch NOTE progress lives on one ``study_progress_subjects``
row per learner and Note, and no release code reads or writes
``study_progress_lineage_refs``, ``study_progress_availability``,
``study_progress_contributors``, ``study_progress_states`` or
``study_authority_subject_tokens`` (P10-09 PR-A). This drops them, children
first, and the ``study_progress_history_facts.contributor_id`` foreign key
with the index MySQL created for it (nothing filters on the column). The
column stays: facts written before P10 keep their contributor id.

Run only after the tables are dumped (P10-09 runbook). Upgrade refuses a
database on an older NOTE storage profile while these tables hold rows: its
progress still lives there, and only an older release's switch can move it. A
fresh chain seeds ``PROJECTION_V1`` (migration 47) with the tables empty; that
is a ``CONSOLIDATED_V1`` install, so the profile is promoted, as is a database
without a profile row. Downgrade cannot recreate rows: restore the P10-09 dump
first (it recreates the tables with their rows), then downgrade re-adds the
foreign key.
"""

from __future__ import annotations

from datetime import datetime, timezone

from alembic import op
import sqlalchemy as sa


revision = "20261003_000050"
down_revision = "20261003_000049"
branch_labels = None
depends_on = None

# Children before parents: availability and lineage refs reference contributors.
TABLES = (
    "study_progress_lineage_refs",
    "study_progress_availability",
    "study_progress_contributors",
    "study_progress_states",
    "study_authority_subject_tokens",
)
FACTS = "study_progress_history_facts"
CONTRIBUTORS = "study_progress_contributors"
FACT_CONTRIBUTOR_FK = "fk_sp_history_fact_contributor"
FACT_CONTRIBUTOR_INDEX = "ix_sp_history_contributor"
PROFILE_TABLE = "study_authority_storage_profile"
_LOCK_WAIT_SECONDS = 30


def _contributor_fks(bind) -> list[str]:
    return [
        str(fk["name"])
        for fk in sa.inspect(bind).get_foreign_keys(FACTS)
        if fk.get("referred_table") == CONTRIBUTORS and fk.get("name")
    ]


def _contributor_indexes(bind) -> list[str]:
    """Indexes on exactly ``(contributor_id)``: the one the FK required."""

    return [
        str(index["name"])
        for index in sa.inspect(bind).get_indexes(FACTS)
        if list(index.get("column_names") or ()) == ["contributor_id"] and not index.get("unique")
    ]


def _execute(bind, statement: str) -> None:
    if bind.dialect.name != "mysql":
        bind.execute(sa.text(statement))
        return
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {_LOCK_WAIT_SECONDS}"))
    try:
        bind.execute(sa.text(statement))
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def _promote_empty_profile(bind, tables: set[str], present: list[str]) -> None:
    if PROFILE_TABLE not in tables:
        return
    profile = bind.execute(sa.text(f"SELECT profile_code FROM {PROFILE_TABLE} WHERE id = 1")).scalar()
    if profile in (None, "CONSOLIDATED_V1"):
        return
    held = sum(int(bind.execute(sa.text(f"SELECT COUNT(*) FROM {table}")).scalar_one()) for table in present)
    if held:
        raise RuntimeError(
            f"Refusing to drop the retired NOTE progress tables: the storage profile is {profile} "
            f"and they hold {held} rows; switch to CONSOLIDATED_V1 on a release that still can."
        )
    bind.execute(sa.text(
        f"UPDATE {PROFILE_TABLE} SET profile_code = 'CONSOLIDATED_V1', epoch = epoch + 1, "
        "switched_at = :now, updated_at = :now WHERE id = 1"
    ), {"now": datetime.now(timezone.utc).replace(tzinfo=None)})


def upgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    present = [table for table in TABLES if table in tables]
    fact_fks = _contributor_fks(bind) if FACTS in tables else []
    # Fresh installs reach this revision with every retired table empty.
    _promote_empty_profile(bind, tables, present)
    if not present and not fact_fks:
        return
    # SQLite (tests) keeps unnamed foreign keys; only MySQL names and drops them.
    if bind.dialect.name == "mysql" and fact_fks:
        for name in fact_fks:
            _execute(bind, f"ALTER TABLE {FACTS} DROP FOREIGN KEY {name}")
        for name in _contributor_indexes(bind):
            _execute(bind, f"ALTER TABLE {FACTS} DROP INDEX {name}")
    for table in present:
        _execute(bind, f"DROP TABLE {table}")


def downgrade() -> None:
    bind = op.get_bind()
    tables = set(sa.inspect(bind).get_table_names())
    missing = [table for table in TABLES if table not in tables]
    if missing:
        raise RuntimeError(
            "Refusing downgrade: restore the P10-09 dump of the retired NOTE progress tables "
            f"first (missing: {', '.join(missing)})."
        )
    if bind.dialect.name == "mysql" and FACTS in tables and not _contributor_fks(bind):
        clauses = [] if _contributor_indexes(bind) else [f"ADD INDEX {FACT_CONTRIBUTOR_INDEX} (contributor_id)"]
        clauses.append(
            f"ADD CONSTRAINT {FACT_CONTRIBUTOR_FK} FOREIGN KEY (contributor_id) "
            f"REFERENCES {CONTRIBUTORS} (id) ON DELETE SET NULL"
        )
        _execute(bind, f"ALTER TABLE {FACTS} " + ", ".join(clauses))
