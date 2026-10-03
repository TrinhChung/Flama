"""Add the consolidated NOTE progress columns to study_progress_subjects.

Revision ID: 20261003_000049
Revises: 20261002_000048
Create Date: 2026-10-03 00:00:49

Expand only (ADR P10 §2.1); no existing value changes:

* state: ``algorithm_key``, ``algorithm_version``, ``state_schema_version``,
  ``storage_codec``, ``state_payload``, ``state_payload_size``,
  ``algorithm_state_hash``, ``semantic_state_hash``;
* CAS: ``authority_revision`` (NOT NULL DEFAULT 0);
* availability of the Note: ``projection_version``, ``normalized_queue``,
  ``due_at``, ``due_day``, ``is_suspended``, ``is_buried``,
  ``buried_until_day``;
* ``history_completeness_code``, ``current_provenance_code``;

plus the row CHECKs of ``subject_progress_checks`` (the progress group is all
present or all NULL) and ``CONSOLIDATED_V1`` in the storage profile allowlist.

Nothing reads or writes the columns while the profile is ``CANONICAL_V1``;
the P10 switch fills them in a write freeze. MySQL adds every column and
CHECK in one ALTER TABLE (CHECKs copy the table) under a bounded
``lock_wait_timeout``. Downgrade refuses once a row holds consolidated
progress or the profile is ``CONSOLIDATED_V1``.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from app.services.study_progress_contract import (
    STORAGE_PROFILES,
    sql_allowlist,
    subject_progress_checks,
)


revision = "20261003_000049"
down_revision = "20261002_000048"
branch_labels = None
depends_on = None

TABLE = "study_progress_subjects"
PROFILE_TABLE = "study_authority_storage_profile"
PROFILE_CHECK = "ck_study_storage_profile_code"
PREVIOUS_PROFILES = ("PROJECTION_V1", "CANONICAL_V1")
_LOCK_WAIT_SECONDS = 30
_ASCII = "CHARACTER SET ascii COLLATE ascii_bin"

# (name, MySQL DDL, portable type for SQLite) in table order.
COLUMNS = (
    ("algorithm_key", f"VARCHAR(64) {_ASCII} NULL", sa.String(64)),
    ("algorithm_version", f"VARCHAR(32) {_ASCII} NULL", sa.String(32)),
    ("state_schema_version", f"VARCHAR(64) {_ASCII} NULL", sa.String(64)),
    ("storage_codec", f"VARCHAR(64) {_ASCII} NULL", sa.String(64)),
    ("state_payload", "JSON NULL", sa.JSON()),
    ("state_payload_size", "SMALLINT NULL", sa.SmallInteger()),
    ("algorithm_state_hash", "BINARY(32) NULL", sa.LargeBinary(32)),
    ("semantic_state_hash", "BINARY(32) NULL", sa.LargeBinary(32)),
    ("authority_revision", "BIGINT NOT NULL DEFAULT 0", sa.BigInteger()),
    ("projection_version", f"VARCHAR(32) {_ASCII} NULL", sa.String(32)),
    ("normalized_queue", f"VARCHAR(20) {_ASCII} NULL", sa.String(20)),
    ("due_at", "DATETIME(6) NULL", sa.DateTime()),
    ("due_day", "INT NULL", sa.Integer()),
    ("is_suspended", "TINYINT(1) NULL", sa.Boolean()),
    ("is_buried", "TINYINT(1) NULL", sa.Boolean()),
    ("buried_until_day", "INT NULL", sa.Integer()),
    ("history_completeness_code", f"VARCHAR(64) {_ASCII} NULL", sa.String(64)),
    ("current_provenance_code", f"VARCHAR(64) {_ASCII} NULL", sa.String(64)),
)


def _columns(bind, table: str) -> set[str]:
    return {column["name"] for column in sa.inspect(bind).get_columns(table)}


def _checks(bind, table: str) -> dict[str, str]:
    return {
        row["name"]: str(row.get("sqltext") or "")
        for row in sa.inspect(bind).get_check_constraints(table)
    }


def _alter(bind, table: str, clauses: list[str]) -> None:
    if not clauses:
        return
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {_LOCK_WAIT_SECONDS}"))
    try:
        bind.execute(sa.text(f"ALTER TABLE {table} " + ", ".join(clauses)))
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def _set_profile_check(bind, profiles: tuple[str, ...]) -> None:
    expression = sql_allowlist("profile_code", profiles)
    checks = _checks(bind, PROFILE_TABLE)
    current = checks.get(PROFILE_CHECK)
    if current is not None and {
        value for value in STORAGE_PROFILES if f"'{value}'" in current
    } == set(profiles):
        return
    # One ALTER cannot drop and re-add a CHECK of the same name; the table is a singleton.
    if current is not None:
        _alter(bind, PROFILE_TABLE, [f"DROP CHECK {PROFILE_CHECK}"])
    _alter(bind, PROFILE_TABLE, [f"ADD CONSTRAINT {PROFILE_CHECK} CHECK ({expression})"])


def upgrade() -> None:
    bind = op.get_bind()
    present = _columns(bind, TABLE)
    if bind.dialect.name != "mysql":
        # SQLite schemas come from model metadata in tests; add only columns.
        with op.batch_alter_table(TABLE) as batch:
            for name, _ddl, portable in COLUMNS:
                if name in present:
                    continue
                if name == "authority_revision":
                    batch.add_column(sa.Column(name, portable, nullable=False, server_default=sa.text("0")))
                else:
                    batch.add_column(sa.Column(name, portable, nullable=True))
        return
    clauses = []
    previous = "last_mirrored_at"
    for name, ddl, _portable in COLUMNS:
        if name not in present:
            clauses.append(f"ADD COLUMN {name} {ddl} AFTER {previous}")
        previous = name
    existing_checks = _checks(bind, TABLE)
    for name, expression in subject_progress_checks().items():
        if name not in existing_checks:
            clauses.append(f"ADD CONSTRAINT {name} CHECK ({expression})")
    _alter(bind, TABLE, clauses)
    _set_profile_check(bind, STORAGE_PROFILES)


def downgrade() -> None:
    bind = op.get_bind()
    present = _columns(bind, TABLE)
    if {"state_payload", "authority_revision"} <= present:
        used = bind.execute(sa.text(
            f"SELECT COUNT(*) FROM {TABLE} WHERE state_payload IS NOT NULL OR authority_revision <> 0"
        )).scalar_one()
        if used:
            raise RuntimeError(f"Refusing downgrade: {used} subjects hold consolidated NOTE progress.")
    if PROFILE_TABLE in sa.inspect(bind).get_table_names():
        profile = bind.execute(sa.text(f"SELECT profile_code FROM {PROFILE_TABLE} WHERE id = 1")).scalar()
        if profile not in (None, *PREVIOUS_PROFILES):
            raise RuntimeError(f"Refusing downgrade: the NOTE storage profile is {profile}.")
    names = [name for name, _ddl, _portable in COLUMNS if name in present]
    if bind.dialect.name != "mysql":
        checks = _checks(bind, TABLE)
        with op.batch_alter_table(TABLE) as batch:
            for name in subject_progress_checks():
                if name in checks:
                    batch.drop_constraint(name, type_="check")
            for name in reversed(names):
                batch.drop_column(name)
        return
    checks = _checks(bind, TABLE)
    clauses = [f"DROP CHECK {name}" for name in subject_progress_checks() if name in checks]
    clauses += [f"DROP COLUMN {name}" for name in reversed(names)]
    _alter(bind, TABLE, clauses)
    _set_profile_check(bind, PREVIOUS_PROFILES)
