"""add durable study session batch tracking

Revision ID: 20260913_000037
Revises: 20260910_000036
Create Date: 2026-09-13 00:00:37

This revision repairs the migration gap introduced when StudySessionBatch was
added to the runtime model.  Some development databases may already contain
the table because startup historically called ``db.create_all()``.  Those
databases are accepted only when the existing table satisfies the complete
runtime contract; an incompatible table fails closed instead of being altered
speculatively.
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20260913_000037"
down_revision = "20260910_000036"
branch_labels = None
depends_on = None


TABLE_NAME = "study_session_batches"
REQUIRED_PARENT_TABLES = {"study_sessions", "users"}

EXPECTED_COLUMNS: dict[str, tuple[str, int | None, bool]] = {
    "id": ("string", 36, False),
    "session_id": ("string", 36, False),
    "user_id": ("integer", None, False),
    "batch_id": ("string", 64, False),
    "batch_sequence": ("integer", None, False),
    "event_count": ("integer", None, False),
    "status": ("string", 20, False),
    "commit_reason": ("string", 32, True),
    "is_final": ("boolean", None, False),
    "request_hash": ("string", 80, False),
    "payload_json": ("text", None, True),
    "response_json": ("text", None, True),
    "error_message": ("text", None, True),
    "enqueued_at": ("datetime", None, False),
    "processed_at": ("datetime", None, True),
    "created_at": ("datetime", None, False),
    "updated_at": ("datetime", None, False),
}

# New installations may run create_all() from a newer model before traversing
# this historical repair. Accept only this exact, known additive extension;
# revision 45 still owns adding it to an older table.
FORWARD_COMPATIBLE_COLUMNS = {"attempt_count"}

EXPECTED_INDEXES: dict[str, tuple[str, ...]] = {
    "ix_study_session_batches_session_id": ("session_id",),
    "ix_study_session_batches_user_id": ("user_id",),
    "ix_study_session_batches_batch_id": ("batch_id",),
    "ix_study_session_batches_status": ("status",),
    "ix_study_session_batches_status_enqueued": ("status", "enqueued_at"),
}

EXPECTED_UNIQUES = {
    ("session_id", "batch_id"),
}

EXPECTED_FOREIGN_KEYS = {
    (("session_id",), "study_sessions", ("id",), "CASCADE"),
    (("user_id",), "users", ("id",), "CASCADE"),
}


def _type_signature(column_type: sa.types.TypeEngine) -> tuple[str, int | None]:
    type_name = column_type.__class__.__name__.lower()
    display_width = getattr(column_type, "display_width", None)
    if isinstance(column_type, sa.Boolean) or (
        type_name == "tinyint" and display_width == 1
    ):
        return "boolean", None
    if isinstance(column_type, sa.Text):
        return "text", None
    if isinstance(column_type, sa.DateTime):
        return "datetime", None
    if isinstance(column_type, sa.Integer):
        return "integer", None
    if isinstance(column_type, sa.String):
        return "string", getattr(column_type, "length", None)
    return type_name, getattr(column_type, "length", None)


def _foreign_key_signature(row: dict) -> tuple[tuple[str, ...], str, tuple[str, ...], str]:
    options = row.get("options") or {}
    return (
        tuple(row.get("constrained_columns") or ()),
        str(row.get("referred_table") or ""),
        tuple(row.get("referred_columns") or ()),
        str(options.get("ondelete") or "").upper(),
    )


def _existing_contract_issues(inspector: sa.Inspector) -> list[str]:
    issues: list[str] = []
    reflected_columns = {
        str(row["name"]): row for row in inspector.get_columns(TABLE_NAME)
    }
    expected_names = set(EXPECTED_COLUMNS)
    actual_names = set(reflected_columns)
    if missing := sorted(expected_names - actual_names):
        issues.append(f"missing columns: {', '.join(missing)}")
    if unexpected := sorted(actual_names - expected_names - FORWARD_COMPATIBLE_COLUMNS):
        issues.append(f"unexpected columns: {', '.join(unexpected)}")

    for name in sorted(expected_names & actual_names):
        expected_kind, expected_length, expected_nullable = EXPECTED_COLUMNS[name]
        row = reflected_columns[name]
        actual_kind, actual_length = _type_signature(row["type"])
        if (actual_kind, actual_length) != (expected_kind, expected_length):
            issues.append(
                f"column {name} type is {actual_kind}({actual_length}), "
                f"expected {expected_kind}({expected_length})"
            )
        if bool(row.get("nullable")) != expected_nullable:
            issues.append(
                f"column {name} nullable={bool(row.get('nullable'))}, "
                f"expected {expected_nullable}"
            )
        if row.get("default") is not None:
            issues.append(f"column {name} has unexpected server default")

    if "attempt_count" in reflected_columns:
        row = reflected_columns["attempt_count"]
        if (
            _type_signature(row["type"]) != ("integer", None)
            or bool(row.get("nullable"))
            or str(row.get("default")).strip("()'\" ") != "0"
        ):
            issues.append("column attempt_count is not INTEGER NOT NULL DEFAULT 0")

    primary_key = tuple(
        (inspector.get_pk_constraint(TABLE_NAME) or {}).get(
            "constrained_columns"
        )
        or ()
    )
    if primary_key != ("id",):
        issues.append(f"primary key is {primary_key!r}, expected ('id',)")

    unique_sets = {
        tuple(row.get("column_names") or ())
        for row in inspector.get_unique_constraints(TABLE_NAME)
    }
    unique_sets.update(
        tuple(row.get("column_names") or ())
        for row in inspector.get_indexes(TABLE_NAME)
        if row.get("unique")
    )
    if unique_sets != EXPECTED_UNIQUES:
        issues.append(
            f"unique column sets are {sorted(unique_sets)!r}, "
            f"expected {sorted(EXPECTED_UNIQUES)!r}"
        )

    indexes = {
        str(row.get("name") or ""): tuple(row.get("column_names") or ())
        for row in inspector.get_indexes(TABLE_NAME)
        if not row.get("unique")
    }
    for name, columns in EXPECTED_INDEXES.items():
        if indexes.get(name) != columns:
            issues.append(
                f"index {name} is {indexes.get(name)!r}, expected {columns!r}"
            )

    foreign_keys = {
        _foreign_key_signature(row)
        for row in inspector.get_foreign_keys(TABLE_NAME)
    }
    if foreign_keys != EXPECTED_FOREIGN_KEYS:
        issues.append(
            f"foreign key contract is {sorted(foreign_keys)!r}, "
            f"expected {sorted(EXPECTED_FOREIGN_KEYS)!r}"
        )
    return issues


def _assert_existing_contract(bind) -> None:
    inspector = sa.inspect(bind)
    issues = _existing_contract_issues(inspector)
    if issues:
        detail = "; ".join(issues)
        raise RuntimeError(
            f"Existing {TABLE_NAME} table does not match the runtime contract: "
            f"{detail}. Repair or remove the empty incompatible table, then rerun migration."
        )


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())

    missing_parents = sorted(REQUIRED_PARENT_TABLES - tables)
    if missing_parents:
        raise RuntimeError(
            f"Cannot create {TABLE_NAME}: missing parent tables "
            f"{', '.join(missing_parents)}."
        )

    if TABLE_NAME in tables:
        _assert_existing_contract(bind)
        return

    op.create_table(
        TABLE_NAME,
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("session_id", sa.String(length=36), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("batch_id", sa.String(length=64), nullable=False),
        sa.Column("batch_sequence", sa.Integer(), nullable=False),
        sa.Column("event_count", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("commit_reason", sa.String(length=32), nullable=True),
        sa.Column("is_final", sa.Boolean(), nullable=False),
        sa.Column("request_hash", sa.String(length=80), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=True),
        sa.Column("response_json", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("enqueued_at", sa.DateTime(), nullable=False),
        sa.Column("processed_at", sa.DateTime(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.ForeignKeyConstraint(
            ["session_id"],
            ["study_sessions.id"],
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "session_id",
            "batch_id",
            name="uq_study_session_batches_batch_id",
        ),
    )
    for index_name, columns in EXPECTED_INDEXES.items():
        op.create_index(
            index_name,
            TABLE_NAME,
            list(columns),
            unique=False,
        )

    _assert_existing_contract(bind)


def downgrade() -> None:
    # Intentionally non-destructive.  This revision repairs schema provenance
    # for a runtime table and cannot know whether a pre-existing table came
    # from db.create_all().  Runtime rollback keeps async admission disabled;
    # a later upgrade safely revalidates and reuses this table.
    return None
