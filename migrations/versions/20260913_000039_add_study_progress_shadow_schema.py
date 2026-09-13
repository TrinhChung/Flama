"""add Phase 4 learner/Note shadow-progress schema

Revision ID: 20260913_000039
Revises: 20260913_000038
Create Date: 2026-09-13 00:00:39

This revision is additive and data-inert.  It creates no mirror/backfill rows,
does not alter authoritative tables and accepts historical ``db.create_all``
tables only after a fail-closed complete contract comparison.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa

from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_backfill_checkpoint import StudyProgressBackfillCheckpoint
from models.study_progress_backfill_disposition import StudyProgressBackfillDisposition
from models.study_progress_backfill_run import StudyProgressBackfillRun
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject


revision = "20260913_000039"
down_revision = "20260913_000038"
branch_labels = None
depends_on = None


TARGET_TABLES = (
    StudyProgressBackfillRun.__table__,
    StudyProgressSubject.__table__,
    StudyProgressState.__table__,
    StudyProgressContributor.__table__,
    StudyProgressAvailability.__table__,
    StudyProgressLineageRef.__table__,
    StudyProgressHistoryFact.__table__,
    StudyProgressLifecycleEvent.__table__,
    StudyProgressBackfillCheckpoint.__table__,
    StudyProgressBackfillDisposition.__table__,
)

REQUIRED_PARENT_TABLES = {
    "users",
    "notes",
    "cards",
    "card_progress",
    "review_events",
}


def _normalized_default(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip()
    while normalized.startswith("(") and normalized.endswith(")"):
        normalized = normalized[1:-1].strip()
    if len(normalized) >= 2 and normalized[0] == normalized[-1] == "'":
        normalized = normalized[1:-1]
    return "".join(normalized.split()).lower()


def _expected_default(column: sa.Column, dialect: sa.engine.Dialect) -> str | None:
    if column.server_default is None:
        return None
    argument = column.server_default.arg
    if hasattr(argument, "compile"):
        return _normalized_default(
            argument.compile(dialect=dialect, compile_kwargs={"literal_binds": True})
        )
    return _normalized_default(argument)


def _type_signature(
    column_type: sa.types.TypeEngine, dialect: sa.engine.Dialect
) -> tuple[str, int | None, int | None, str | None]:
    resolved = column_type.dialect_impl(dialect)
    type_name = resolved.__class__.__name__.lower()
    display_width = getattr(resolved, "display_width", None)
    if isinstance(resolved, sa.Boolean) or (
        type_name == "tinyint" and display_width == 1
    ):
        return ("boolean", None, None, None)
    if isinstance(resolved, sa.JSON) or type_name == "json":
        return ("json", None, None, None)
    if isinstance(resolved, sa.Text):
        return ("text", None, None, None)
    if isinstance(resolved, sa.LargeBinary) or type_name in {
        "binary",
        "varbinary",
        "blob",
        "largebinary",
    }:
        if dialect.name == "sqlite":
            return ("blob", None, None, None)
        return (
            type_name,
            getattr(resolved, "length", None),
            None,
            None,
        )
    if isinstance(resolved, sa.DateTime):
        return ("datetime", None, getattr(resolved, "fsp", None), None)
    if isinstance(resolved, sa.BigInteger):
        return ("bigint", None, None, None)
    if isinstance(resolved, sa.SmallInteger):
        return ("smallint", None, None, None)
    if isinstance(resolved, sa.Integer):
        return ("integer", None, None, None)
    if isinstance(resolved, sa.String):
        collation = getattr(resolved, "collation", None)
        if dialect.name == "mysql" and collation is None:
            # Reflection reports the effective table collation on an otherwise
            # unqualified VARCHAR/CHAR declaration.
            collation = "utf8mb4_unicode_ci"
        return (
            "char" if isinstance(resolved, sa.CHAR) else "varchar",
            getattr(resolved, "length", None),
            None,
            collation,
        )
    return (type_name, getattr(resolved, "length", None), None, None)


def _normalize_sql(value: object) -> str:
    normalized = (
        str("" if value is None else value)
        .lower()
        .replace("`", "")
        .replace('"', "")
        .replace("_ascii", "")
        .replace("(", "")
        .replace(")", "")
    )
    return "".join(normalized.split())


def _fk_signature_from_constraint(
    constraint: sa.ForeignKeyConstraint,
) -> tuple[tuple[str, ...], str, tuple[str, ...], str]:
    elements = tuple(constraint.elements)
    return (
        tuple(element.parent.name for element in elements),
        elements[0].column.table.name,
        tuple(element.column.name for element in elements),
        str(constraint.ondelete or "").upper(),
    )


def _fk_signature_from_reflection(
    row: dict,
) -> tuple[tuple[str, ...], str, tuple[str, ...], str]:
    options = row.get("options") or {}
    return (
        tuple(row.get("constrained_columns") or ()),
        str(row.get("referred_table") or ""),
        tuple(row.get("referred_columns") or ()),
        str(options.get("ondelete") or "").upper(),
    )


def _table_contract_issues(
    inspector: sa.Inspector, table: sa.Table, dialect: sa.engine.Dialect
) -> list[str]:
    issues: list[str] = []
    table_name = table.name
    actual_columns = {
        str(row["name"]): row for row in inspector.get_columns(table_name)
    }
    expected_columns = {column.name: column for column in table.columns}
    if missing := sorted(set(expected_columns) - set(actual_columns)):
        issues.append(f"missing columns: {', '.join(missing)}")
    if unexpected := sorted(set(actual_columns) - set(expected_columns)):
        issues.append(f"unexpected columns: {', '.join(unexpected)}")
    for name in sorted(set(expected_columns) & set(actual_columns)):
        expected = expected_columns[name]
        actual = actual_columns[name]
        expected_type = _type_signature(expected.type, dialect)
        actual_type = _type_signature(actual["type"], dialect)
        if expected_type != actual_type:
            issues.append(
                f"column {name} type is {actual_type!r}, expected {expected_type!r}"
            )
        if bool(actual.get("nullable")) != bool(expected.nullable):
            issues.append(
                f"column {name} nullable={bool(actual.get('nullable'))}, "
                f"expected {bool(expected.nullable)}"
            )
        actual_default = _normalized_default(actual.get("default"))
        expected_default = _expected_default(expected, dialect)
        if actual_default != expected_default:
            issues.append(
                f"column {name} default is {actual_default!r}, expected {expected_default!r}"
            )

    actual_pk = tuple(
        (inspector.get_pk_constraint(table_name) or {}).get("constrained_columns") or ()
    )
    expected_pk = tuple(column.name for column in table.primary_key.columns)
    if actual_pk != expected_pk:
        issues.append(f"primary key is {actual_pk!r}, expected {expected_pk!r}")

    expected_uniques = {
        str(constraint.name or ""): tuple(column.name for column in constraint.columns)
        for constraint in table.constraints
        if isinstance(constraint, sa.UniqueConstraint)
    }
    actual_uniques = {
        str(row.get("name") or ""): tuple(row.get("column_names") or ())
        for row in inspector.get_unique_constraints(table_name)
    }
    actual_uniques.update(
        {
        str(row.get("name") or ""): tuple(row.get("column_names") or ())
        for row in inspector.get_indexes(table_name)
        if row.get("unique")
        }
    )
    if actual_uniques != expected_uniques:
        issues.append(
            f"unique constraints are {sorted(actual_uniques.items())!r}, "
            f"expected {sorted(expected_uniques.items())!r}"
        )

    expected_indexes = {
        str(index.name): tuple(column.name for column in index.columns)
        for index in table.indexes
        if not index.unique
    }
    actual_indexes = {
        str(row.get("name") or ""): tuple(row.get("column_names") or ())
        for row in inspector.get_indexes(table_name)
        if not row.get("unique")
    }
    # InnoDB synthesizes a non-unique backing index when no declared key has
    # the complete constrained-column prefix.  It is a derived part of the FK
    # contract, not an independently declared access-path index.
    if dialect.name == "mysql":
        fk_column_sets = {
            tuple(row.get("constrained_columns") or ())
            for row in inspector.get_foreign_keys(table_name)
        }
        actual_indexes = {
            name: columns
            for name, columns in actual_indexes.items()
            if name in expected_indexes or columns not in fk_column_sets
        }
    if actual_indexes != expected_indexes:
        issues.append(
            f"indexes are {sorted(actual_indexes.items())!r}, "
            f"expected {sorted(expected_indexes.items())!r}"
        )

    expected_fks = {
        _fk_signature_from_constraint(constraint)
        for constraint in table.foreign_key_constraints
    }
    actual_fks = {
        _fk_signature_from_reflection(row)
        for row in inspector.get_foreign_keys(table_name)
    }
    if actual_fks != expected_fks:
        issues.append(
            f"foreign keys are {sorted(actual_fks)!r}, expected {sorted(expected_fks)!r}"
        )

    expected_checks = {
        str(constraint.name or ""): _normalize_sql(constraint.sqltext)
        for constraint in table.constraints
        if isinstance(constraint, sa.CheckConstraint)
    }
    actual_checks = {
        str(row.get("name") or ""): _normalize_sql(row.get("sqltext"))
        for row in inspector.get_check_constraints(table_name)
    }
    if actual_checks != expected_checks:
        issues.append(
            f"checks are {actual_checks!r}, expected {expected_checks!r}"
        )

    if dialect.name == "mysql":
        options = inspector.get_table_options(table_name)
        engine = str(options.get("mysql_engine") or "").lower()
        collation = str(options.get("mysql_collate") or "").lower()
        charset = str(
            options.get("mysql_default charset")
            or options.get("mysql_charset")
            or ""
        ).lower()
        if engine != "innodb":
            issues.append(f"engine is {engine!r}, expected 'innodb'")
        if collation != "utf8mb4_unicode_ci":
            issues.append(
                f"collation is {collation!r}, expected 'utf8mb4_unicode_ci'"
            )
        if charset and charset != "utf8mb4":
            issues.append(f"charset is {charset!r}, expected 'utf8mb4'")
    return issues


def _assert_table_contract(bind, table: sa.Table) -> None:
    inspector = sa.inspect(bind)
    issues = _table_contract_issues(inspector, table, bind.dialect)
    if issues:
        raise RuntimeError(
            f"Existing {table.name} table does not match the Phase 4 contract: "
            + "; ".join(issues)
        )


def upgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    missing_parents = sorted(REQUIRED_PARENT_TABLES - existing_tables)
    if missing_parents:
        raise RuntimeError(
            "Cannot create Phase 4 shadow schema: missing parent tables "
            + ", ".join(missing_parents)
            + "."
        )

    for table in TARGET_TABLES:
        if table.name in existing_tables:
            _assert_table_contract(bind, table)
            continue
        table.create(bind=bind, checkfirst=False)
        existing_tables.add(table.name)
        _assert_table_contract(bind, table)


def downgrade() -> None:
    bind = op.get_bind()
    existing_tables = set(sa.inspect(bind).get_table_names())
    nonempty: list[str] = []
    for table in TARGET_TABLES:
        if table.name not in existing_tables:
            continue
        count = bind.execute(
            sa.select(sa.func.count()).select_from(table)
        ).scalar_one()
        if int(count) > 0:
            nonempty.append(f"{table.name}={count}")
    if nonempty:
        raise RuntimeError(
            "Phase 4 shadow downgrade is prohibited while additive tables contain "
            "rows: " + ", ".join(nonempty) + ". Disable flags and use forward repair."
        )

    for table in reversed(TARGET_TABLES):
        if table.name in existing_tables:
            table.drop(bind=bind, checkfirst=False)
