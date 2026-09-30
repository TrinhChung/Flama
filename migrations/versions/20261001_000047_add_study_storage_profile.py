"""Add the NOTE storage profile and CardProgress-free contributor evidence.

Revision ID: 20261001_000047
Revises: 20260930_000046
Create Date: 2026-10-01 00:00:47

Expand only (ADR P9-03 §2.1, §2.3); no existing value changes:

* ``study_authority_storage_profile``: one row, ``PROJECTION_V1``, epoch 1.
  Nothing reads another profile yet; the switch is P9-06.
* ``study_progress_contributors``: ``evidence_kind`` (every existing row is
  ``LEGACY_PROJECTION``), unique ``(subject_id, subject_generation,
  logical_card_key)``, nullable raw CardProgress evidence and CHECKs that
  pair ``evidence_kind`` with it (``LEGACY_PROJECTION`` ⇒ all present,
  ``CANONICAL`` ⇒ all absent). The unique key replaces
  ``uq_sp_contributor_generation_source`` for rows without a
  ``source_progress_id``, and lands in the same statement that relaxes it.

MySQL adds CHECK constraints only by copying the table, so every
contributor change is one ALTER TABLE (one copy). ``lock_wait_timeout``
bounds the wait for the metadata lock, so a long transaction of the serving
release makes the deploy fail instead of queueing study writes behind it.
SQLite schemas come from model metadata in tests; only MySQL contributors
are altered.

Downgrade refuses while the profile is not ``PROJECTION_V1`` or any
contributor has ``CANONICAL`` evidence: those rows have no CardProgress
evidence to restore.
"""

from __future__ import annotations

from datetime import datetime, timezone
import re

from alembic import op
import sqlalchemy as sa

from app.services.study_progress_contract import (
    CONTRIBUTOR_RAW_EVIDENCE_COLUMNS,
    EVIDENCE_KINDS,
    STORAGE_PROFILES,
    contributor_evidence_check,
    sql_allowlist,
)
from models.study_progress_types import MYSQL_TABLE_OPTIONS, ascii_string, datetime6


revision = "20261001_000047"
down_revision = "20260930_000046"
branch_labels = None
depends_on = None

PROFILE_TABLE = "study_authority_storage_profile"
CONTRIBUTORS = "study_progress_contributors"
EVIDENCE_COLUMN = "evidence_kind"
GENERATION_CARD_UNIQUE = "uq_sp_contributor_generation_card"
EVIDENCE_KIND_CHECK = "ck_sp_contributor_evidence_kind"
EVIDENCE_CHECK = "ck_sp_contributor_evidence"
_LOCK_WAIT_SECONDS = 30


def _create_profile_table(bind) -> None:
    if not sa.inspect(bind).has_table(PROFILE_TABLE):
        op.create_table(
            PROFILE_TABLE,
            sa.Column("id", sa.SmallInteger(), primary_key=True, autoincrement=False),
            sa.Column(
                "profile_code",
                ascii_string(32),
                nullable=False,
                server_default=sa.text("'PROJECTION_V1'"),
            ),
            sa.Column("epoch", sa.BigInteger(), nullable=False, server_default=sa.text("1")),
            sa.Column("switched_at", datetime6(), nullable=True),
            sa.Column("created_at", datetime6(), nullable=False),
            sa.Column("updated_at", datetime6(), nullable=False),
            sa.CheckConstraint("id = 1", name="ck_study_storage_profile_singleton"),
            sa.CheckConstraint(
                sql_allowlist("profile_code", STORAGE_PROFILES),
                name="ck_study_storage_profile_code",
            ),
            sa.CheckConstraint("epoch >= 1", name="ck_study_storage_profile_epoch"),
            **MYSQL_TABLE_OPTIONS,
        )
    present = bind.execute(sa.text(f"SELECT COUNT(*) FROM {PROFILE_TABLE}")).scalar_one()
    if not present:
        now = datetime.now(timezone.utc).replace(tzinfo=None)
        bind.execute(
            sa.text(
                f"INSERT INTO {PROFILE_TABLE} (id, profile_code, epoch, switched_at, created_at, updated_at) "
                "VALUES (1, 'PROJECTION_V1', 1, NULL, :now, :now)"
            ),
            {"now": now},
        )


def _column_definitions(bind) -> dict[str, str]:
    """Column name -> its exact MySQL definition from SHOW CREATE TABLE."""

    ddl = bind.execute(sa.text(f"SHOW CREATE TABLE {CONTRIBUTORS}")).one()[1]
    definitions = {}
    for line in ddl.splitlines():
        match = re.match(r"\s*`([^`]+)`\s+(.*?),?\s*$", line)
        if match:
            definitions[match.group(1)] = match.group(2)
    return definitions


def _constraint_names(bind) -> set[str]:
    inspector = sa.inspect(bind)
    names = {row["name"] for row in inspector.get_check_constraints(CONTRIBUTORS)}
    names.update(row["name"] for row in inspector.get_unique_constraints(CONTRIBUTORS))
    names.update(row["name"] for row in inspector.get_indexes(CONTRIBUTORS))
    return names


def _duplicate_generation_cards(bind) -> int:
    return int(
        bind.execute(
            sa.text(
                "SELECT COUNT(*) FROM (SELECT 1 FROM study_progress_contributors "
                "GROUP BY subject_id, subject_generation, logical_card_key "
                "HAVING COUNT(*) > 1) AS duplicates"
            )
        ).scalar_one()
    )


def _set_lock_wait(bind) -> int:
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {_LOCK_WAIT_SECONDS}"))
    return previous


def _expand_contributors(bind) -> None:
    if bind.dialect.name != "mysql":
        return
    definitions = _column_definitions(bind)
    names = _constraint_names(bind)
    clauses = []
    if EVIDENCE_COLUMN not in definitions:
        clauses.append(
            f"ADD COLUMN {EVIDENCE_COLUMN} VARCHAR(32) CHARACTER SET ascii COLLATE ascii_bin "
            "NOT NULL DEFAULT 'LEGACY_PROJECTION' AFTER subject_generation"
        )
    for column in CONTRIBUTOR_RAW_EVIDENCE_COLUMNS:
        definition = definitions[column]
        if " NOT NULL" in definition:
            clauses.append(f"MODIFY `{column}` {definition.replace(' NOT NULL', ' NULL', 1)}")
    if GENERATION_CARD_UNIQUE not in names:
        if _duplicate_generation_cards(bind):
            raise RuntimeError(
                "Two contributors share a subject generation and Card; "
                f"{GENERATION_CARD_UNIQUE} cannot be added."
            )
        clauses.append(
            f"ADD CONSTRAINT {GENERATION_CARD_UNIQUE} "
            "UNIQUE (subject_id, subject_generation, logical_card_key)"
        )
    if EVIDENCE_KIND_CHECK not in names:
        clauses.append(
            f"ADD CONSTRAINT {EVIDENCE_KIND_CHECK} "
            f"CHECK ({sql_allowlist(EVIDENCE_COLUMN, EVIDENCE_KINDS)})"
        )
    if EVIDENCE_CHECK not in names:
        clauses.append(f"ADD CONSTRAINT {EVIDENCE_CHECK} CHECK ({contributor_evidence_check()})")
    if not clauses:
        return
    previous = _set_lock_wait(bind)
    try:
        bind.execute(sa.text(f"ALTER TABLE {CONTRIBUTORS} " + ", ".join(clauses)))
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def _verify(bind) -> None:
    profile = bind.execute(
        sa.text(f"SELECT profile_code FROM {PROFILE_TABLE} WHERE id = 1")
    ).scalar_one_or_none()
    if profile is None:
        raise RuntimeError("Migration 47 left no storage profile row.")
    if bind.dialect.name != "mysql":
        return
    columns = {column["name"]: column for column in sa.inspect(bind).get_columns(CONTRIBUTORS)}
    if EVIDENCE_COLUMN not in columns or any(
        not columns[name]["nullable"] for name in CONTRIBUTOR_RAW_EVIDENCE_COLUMNS
    ):
        raise RuntimeError("Migration 47 did not expand study_progress_contributors.")
    missing = {GENERATION_CARD_UNIQUE, EVIDENCE_KIND_CHECK, EVIDENCE_CHECK} - _constraint_names(bind)
    if missing:
        raise RuntimeError(f"Migration 47 constraints are missing: {sorted(missing)}")


def upgrade() -> None:
    bind = op.get_bind()
    _create_profile_table(bind)
    _expand_contributors(bind)
    _verify(bind)


def _refuse_lossy_downgrade(bind) -> None:
    inspector = sa.inspect(bind)
    if inspector.has_table(PROFILE_TABLE):
        profile = bind.execute(
            sa.text(f"SELECT profile_code FROM {PROFILE_TABLE} WHERE id = 1")
        ).scalar_one_or_none()
        if profile not in {None, "PROJECTION_V1"}:
            raise RuntimeError(
                f"Refusing downgrade: the NOTE storage profile is {profile}, not PROJECTION_V1."
            )
    if EVIDENCE_COLUMN in {column["name"] for column in inspector.get_columns(CONTRIBUTORS)}:
        canonical = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {CONTRIBUTORS} WHERE {EVIDENCE_COLUMN} <> 'LEGACY_PROJECTION'")
        ).scalar_one()
        if canonical:
            raise RuntimeError(
                f"Refusing downgrade: {canonical} contributors have no CardProgress evidence."
            )


def downgrade() -> None:
    bind = op.get_bind()
    _refuse_lossy_downgrade(bind)
    if bind.dialect.name == "mysql":
        definitions = _column_definitions(bind)
        names = _constraint_names(bind)
        clauses = [
            f"DROP CHECK {name}" for name in (EVIDENCE_CHECK, EVIDENCE_KIND_CHECK) if name in names
        ]
        if GENERATION_CARD_UNIQUE in names:
            clauses.append(f"DROP INDEX {GENERATION_CARD_UNIQUE}")
        for column in CONTRIBUTOR_RAW_EVIDENCE_COLUMNS:
            definition = definitions[column]
            if " NOT NULL" not in definition:
                # A nullable column reads "<type> DEFAULT NULL" or "<type> NULL".
                required = re.sub(r" (DEFAULT )?NULL$", "", definition) + " NOT NULL"
                clauses.append(f"MODIFY `{column}` {required}")
        if EVIDENCE_COLUMN in definitions:
            clauses.append(f"DROP COLUMN {EVIDENCE_COLUMN}")
        if clauses:
            previous = _set_lock_wait(bind)
            try:
                bind.execute(sa.text(f"ALTER TABLE {CONTRIBUTORS} " + ", ".join(clauses)))
            finally:
                bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))
    if sa.inspect(bind).has_table(PROFILE_TABLE):
        op.drop_table(PROFILE_TABLE)
