"""add inert Phase 5 learner authority fence and subject CAS token

Revision ID: 20260921_000040
Revises: 20260913_000039
Create Date: 2026-09-21 00:00:40

The database permits only LEGACY enrollment at this stage.  In particular,
deploying this revision cannot switch any learner to Note authority.  The
Phase 4 schema and its historical migration are left untouched.
"""

from __future__ import annotations

from importlib import import_module

from alembic import op
import sqlalchemy as sa

from models.study_authority_enrollment import StudyAuthorityEnrollment
# Retired by P10-09 (migration 50 drops it); frozen for a fresh chain.
from migrations.retired_note_progress_tables import StudyAuthoritySubjectToken


revision = "20260921_000040"
down_revision = "20260913_000039"
branch_labels = None
depends_on = None

def _historical_legacy_enrollment_table() -> sa.Table:
    """Freeze revision 40 even after the runtime model admits NOTE."""

    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    table = StudyAuthorityEnrollment.__table__.to_metadata(metadata)
    for constraint in tuple(table.constraints):
        if isinstance(constraint, sa.CheckConstraint):
            table.constraints.remove(constraint)
    table.append_constraint(
        sa.CheckConstraint(
            "mode_code = 'LEGACY'",
            name="ck_study_authority_legacy_only",
        )
    )
    table.append_constraint(
        sa.CheckConstraint("epoch >= 0", name="ck_study_authority_epoch")
    )
    return table


LEGACY_ENROLLMENT_TABLE = _historical_legacy_enrollment_table()

TARGET_TABLES = (
    LEGACY_ENROLLMENT_TABLE,
    StudyAuthoritySubjectToken.__table__,
)
REQUIRED_PARENT_TABLES = {"users", "study_progress_subjects", "study_progress_states"}


def _assert_table_contract(bind: sa.engine.Connection, table: sa.Table) -> None:
    # Reuse the Phase 4 physical comparator for create_all history, MySQL
    # collation, defaults, checks, FKs and indexes. MySQL reflection adds a
    # charset introducer to string literals in CHECK SQL; normalize only that
    # harmless representation difference, not the constraint itself.
    predecessor = import_module(
        "migrations.versions.20260913_000039_add_study_progress_shadow_schema"
    )
    inspector = sa.inspect(bind)
    issues = predecessor._table_contract_issues(inspector, table, bind.dialect)
    if bind.dialect.name == "mysql" and any(
        issue.startswith("checks are ") for issue in issues
    ):
        def normalized_checks(values: dict[str, str]) -> dict[str, str]:
            return {
                name: predecessor._normalize_sql(value).replace("_utf8mb4", "")
                for name, value in values.items()
            }

        expected = normalized_checks(
            {
                str(constraint.name or ""): str(constraint.sqltext)
                for constraint in table.constraints
                if isinstance(constraint, sa.CheckConstraint)
            }
        )
        actual = normalized_checks(
            {
                str(row.get("name") or ""): str(row.get("sqltext") or "")
                for row in inspector.get_check_constraints(table.name)
            }
        )
        if actual == expected:
            issues = [issue for issue in issues if not issue.startswith("checks are ")]
    if issues:
        raise RuntimeError(
            f"Existing {table.name} table does not match the Phase 5 contract: "
            + "; ".join(issues)
        )


REVISION_43_CHECKS = {"ck_study_authority_mode", "ck_study_authority_mode_epoch"}


def _created_from_revision_43_metadata(bind: sa.engine.Connection, table: sa.Table) -> bool:
    """Detect `db.create_all()` from newer model metadata (revision 43 checks)."""

    if table is not LEGACY_ENROLLMENT_TABLE:
        return False
    names = {
        str(row.get("name") or "")
        for row in sa.inspect(bind).get_check_constraints(table.name)
    }
    return REVISION_43_CHECKS.issubset(names)


def upgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    missing = sorted(REQUIRED_PARENT_TABLES - existing)
    if missing:
        raise RuntimeError(
            "Cannot add Phase 5 authority fence: missing parent tables "
            + ", ".join(missing)
            + "."
        )

    for table in TARGET_TABLES:
        if table.name not in existing:
            table.create(bind=bind, checkfirst=False)
            existing.add(table.name)
        elif _created_from_revision_43_metadata(bind, table):
            # Startup create_all ran before Alembic and built the current
            # model. Accept only that exact known shape; revision 43 then
            # re-verifies it and keeps its checks unchanged.
            _assert_table_contract(bind, StudyAuthorityEnrollment.__table__)
            continue
        _assert_table_contract(bind, table)


def downgrade() -> None:
    bind = op.get_bind()
    existing = set(sa.inspect(bind).get_table_names())
    nonempty = [
        f"{table.name}={count}"
        for table in TARGET_TABLES
        if table.name in existing
        if (count := bind.execute(sa.select(sa.func.count()).select_from(table)).scalar_one())
    ]
    if nonempty:
        raise RuntimeError(
            "Phase 5 authority-fence downgrade is prohibited while tables contain "
            "rows: " + ", ".join(nonempty) + ". Use forward repair."
        )
    for table in reversed(TARGET_TABLES):
        if table.name in existing:
            table.drop(bind=bind, checkfirst=False)
