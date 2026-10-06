"""Add rebuildable historical review analytics generations and daily counts.

Revision ID: 20261005_000051
Revises: 20261003_000050
Create Date: 2026-10-05 00:00:51

Expand only: no raw ReviewEvent, progress, or existing analytics value changes.
Startup create_all may already have made these tables. Validate their complete
schema before accepting them, and preflight every existing table before DDL so
MySQL's implicit DDL commits cannot hide a partially accepted drifted schema.
Downgrade removes only the rebuildable projection; disable its readers first.
"""

from __future__ import annotations

import re

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql


revision = "20261005_000051"
down_revision = "20261003_000050"
branch_labels = None
depends_on = None

TABLE_NAMES = (
    "review_analytics_heads",
    "review_analytics_generations",
    "daily_review_counts",
)
MYSQL_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def _tables():
    """Freeze this revision's DDL rather than importing evolving ORM models."""
    metadata = sa.MetaData()
    sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    bigint = lambda: sa.BigInteger().with_variant(mysql.BIGINT(unsigned=True), "mysql")
    tinyint = lambda: sa.SmallInteger().with_variant(mysql.TINYINT(unsigned=True), "mysql")
    smallint = lambda: sa.SmallInteger().with_variant(mysql.SMALLINT(unsigned=True), "mysql")
    timestamp = lambda: sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    head = sa.Table(
        TABLE_NAMES[0], metadata,
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False),
        sa.Column("next_generation", bigint(), nullable=False, server_default=sa.text("1")),
        sa.Column("active_generation", bigint(), nullable=True),
        sa.Column("building_generation", bigint(), nullable=True),
        sa.Column("source_revision", bigint(), nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", timestamp(), nullable=False),
        **MYSQL_OPTIONS,
    )
    generation = sa.Table(
        TABLE_NAMES[1], metadata,
        sa.Column("user_id", sa.Integer, sa.ForeignKey("review_analytics_heads.user_id", ondelete="CASCADE"), primary_key=True, autoincrement=False),
        sa.Column("generation", bigint(), primary_key=True, autoincrement=False),
        sa.Column("policy_hash", sa.LargeBinary(32).with_variant(mysql.BINARY(32), "mysql"), nullable=False),
        sa.Column("timezone_name", sa.String(64).with_variant(mysql.VARCHAR(64, charset="ascii", collation="ascii_bin"), "mysql"), nullable=False),
        sa.Column("day_boundary_hour", tinyint(), nullable=False),
        sa.Column("grouping_version", smallint(), nullable=False),
        sa.Column("timezone_rules_version", sa.String(64), nullable=False),
        sa.Column("status", tinyint(), nullable=False),
        sa.Column("baseline_high_water_id", bigint(), nullable=False, server_default=sa.text("0")),
        sa.Column("backfill_cursor_id", bigint(), nullable=False, server_default=sa.text("0")),
        sa.Column("applied_source_revision", bigint(), nullable=True),
        sa.Column("verified_source_revision", bigint(), nullable=True),
        sa.Column("verification_contract_version", smallint(), nullable=True),
        sa.Column("verified_at", timestamp(), nullable=True),
        sa.Column("created_at", timestamp(), nullable=False),
        sa.Column("published_at", timestamp(), nullable=True),
        sa.Column("last_error_code", sa.String(64), nullable=True),
        sa.CheckConstraint("day_boundary_hour BETWEEN 0 AND 23", name="ck_review_analytics_day_boundary"),
        sa.CheckConstraint("status BETWEEN 0 AND 4", name="ck_review_analytics_status"),
        sa.CheckConstraint("backfill_cursor_id <= baseline_high_water_id", name="ck_review_analytics_cursor"),
        **MYSQL_OPTIONS,
    )
    counts = sa.Table(
        TABLE_NAMES[2], metadata,
        sa.Column("user_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("generation", bigint(), primary_key=True, autoincrement=False),
        sa.Column("scope_kind", tinyint(), primary_key=True, autoincrement=False),
        sa.Column("scope_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("study_day", sa.Date, primary_key=True),
        sa.Column("review_event_count", sa.BigInteger, nullable=False),
        sa.Column("positive_duration_ms", sa.BigInteger, nullable=False),
        sa.Column("passed_review_count", sa.BigInteger, nullable=False),
        sa.ForeignKeyConstraint(
            ("user_id", "generation"),
            ("review_analytics_generations.user_id", "review_analytics_generations.generation"),
            name="fk_daily_review_count_generation", ondelete="CASCADE",
        ),
        sa.CheckConstraint("(scope_kind = 0 AND scope_id = 0) OR (scope_kind = 1 AND scope_id > 0)", name="ck_daily_review_count_scope"),
        sa.CheckConstraint("review_event_count >= 0", name="ck_daily_review_count_events"),
        sa.CheckConstraint("positive_duration_ms >= 0", name="ck_daily_review_count_duration"),
        sa.CheckConstraint("passed_review_count >= 0 AND passed_review_count <= review_event_count", name="ck_daily_review_count_passed"),
        **MYSQL_OPTIONS,
    )
    return head, generation, counts


def _type_sql(column_type, dialect):
    value = str(column_type.compile(dialect=dialect)).upper()
    value = re.sub(r"\b(?:CHARACTER SET|COLLATE)\s+\w+", "", value)
    value = re.sub(r"\b(TINYINT|SMALLINT|INTEGER|INT|BIGINT)\(\d+\)", r"\1", value)
    return " ".join(re.sub(r"\bINT\b", "INTEGER", value).split())


def _default(value):
    if value is None:
        return None
    return str(value).strip().strip("()'\"").lower()


def _check_sql(value):
    value = re.sub(r"\s+", " ", str(value).replace("`", "").strip().lower())
    # MySQL adds parentheses around each comparison and the whole CHECK.
    # Preserve compound groups: removing all parentheses could accept a
    # semantically different scope constraint after an unexpected schema edit.
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        closes_early = False
        for index, char in enumerate(value):
            depth += (char == "(") - (char == ")")
            if depth == 0 and index < len(value) - 1:
                closes_early = True
                break
        if closes_early:
            break
        value = value[1:-1].strip()
    atom = r"\(([a-z_][a-z_0-9]*\s*(?:>=|<=|>|=)\s*(?:[a-z_][a-z_0-9]*|\d+))\)"
    while re.search(atom, value):
        value = re.sub(atom, r"\1", value)
    return re.sub(r"\s+", "", value)


def _schema_error(table, detail):
    raise RuntimeError(f"Review analytics schema drift in {table}: {detail}; inspect before migrating.")


def _assert_compatible(bind, table):
    inspector = sa.inspect(bind)
    actual = {column["name"]: column for column in inspector.get_columns(table.name)}
    if set(actual) != set(table.c.keys()):
        _schema_error(table.name, "column set does not match revision 51")
    for expected in table.c:
        column = actual[expected.name]
        if _type_sql(column["type"], bind.dialect) != _type_sql(expected.type, bind.dialect):
            _schema_error(table.name, f"{expected.name} type differs")
        if bool(column["nullable"]) != bool(expected.nullable):
            _schema_error(table.name, f"{expected.name} nullability differs")
        default = expected.server_default.arg if expected.server_default is not None else None
        if _default(column.get("default")) != _default(default):
            _schema_error(table.name, f"{expected.name} default differs")
        if column.get("autoincrement") is True:
            _schema_error(table.name, f"{expected.name} must not autoincrement")
    primary = inspector.get_pk_constraint(table.name).get("constrained_columns", [])
    if list(primary) != [column.name for column in table.primary_key]:
        _schema_error(table.name, "primary key differs")
    expected_fks = {
        (tuple(fk.column_keys), fk.referred_table.name,
         tuple(element.column.name for element in fk.elements), fk.ondelete)
        for fk in table.foreign_key_constraints
    }
    actual_fks = {
        (tuple(fk["constrained_columns"]), fk["referred_table"],
         tuple(fk["referred_columns"]), str(fk.get("options", {}).get("ondelete", "")).upper() or None)
        for fk in inspector.get_foreign_keys(table.name)
    }
    if expected_fks != actual_fks:
        _schema_error(table.name, "foreign keys or delete behavior differ")
    expected_checks = {c.name: _check_sql(c.sqltext) for c in table.constraints if isinstance(c, sa.CheckConstraint)}
    actual_checks = {c["name"]: _check_sql(c["sqltext"]) for c in inspector.get_check_constraints(table.name)}
    if expected_checks != actual_checks:
        _schema_error(table.name, "CHECK constraints differ")
    if inspector.get_indexes(table.name) or inspector.get_unique_constraints(table.name):
        _schema_error(table.name, "unexpected secondary or unique indexes")
    if bind.dialect.name == "mysql":
        options = inspector.get_table_options(table.name)
        if str(options.get("mysql_engine", "")).lower() != "innodb":
            _schema_error(table.name, "engine must be InnoDB")
        if options.get("mysql_collate") != "utf8mb4_unicode_ci":
            _schema_error(table.name, "table collation differs")
        if table.name == "review_analytics_generations":
            charset, collation = bind.execute(sa.text(
                "SELECT CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name AND COLUMN_NAME = 'timezone_name'"
            ), {"table_name": table.name}).one()
            if (charset, collation) != ("ascii", "ascii_bin"):
                _schema_error(table.name, "timezone_name must use ascii/ascii_bin")


def _preflight(bind, tables):
    present = set(sa.inspect(bind).get_table_names())
    for table in tables:
        if table.name in present:
            _assert_compatible(bind, table)
    return present


def upgrade():
    bind = op.get_bind()
    tables = _tables()
    present = _preflight(bind, tables)
    if "users" not in present:
        _schema_error("users", "required signed INT user primary key table is absent")
    users = sa.inspect(bind)
    user_id = next((column for column in users.get_columns("users") if column["name"] == "id"), None)
    if (
        user_id is None
        or _type_sql(user_id["type"], bind.dialect) != _type_sql(sa.Integer(), bind.dialect)
        or users.get_pk_constraint("users").get("constrained_columns") != ["id"]
    ):
        _schema_error("users", "id must remain the signed INT primary key")
    for table in tables:
        if table.name not in present:
            table.create(bind=bind)


def downgrade():
    bind = op.get_bind()
    tables = _tables()
    present = _preflight(bind, tables)
    for table in reversed(tables):
        if table.name in present:
            table.drop(bind=bind)
