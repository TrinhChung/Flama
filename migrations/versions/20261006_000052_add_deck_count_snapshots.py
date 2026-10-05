"""Add monotonic deck count tokens and rebuildable owned-deck snapshots.

Revision ID: 20261006_000052
Revises: 20261005_000051
Create Date: 2026-10-06 00:00:52

Expand only. Accept exactly matching startup create_all tables without touching
rows; reject drift before any DDL. Token rows deliberately have no Deck FK:
zero is a global invalidation sentinel and deleted-deck tokens must not reset.
"""

from __future__ import annotations

import importlib

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import mysql

revision = "20261006_000052"
down_revision = "20261005_000051"
branch_labels = None
depends_on = None

TABLE_NAMES = ("deck_count_content_revisions", "deck_count_learner_revisions", "deck_study_count_snapshots")
_normalization = importlib.import_module("migrations.versions.20261005_000051_add_review_analytics_counts")
_OPTIONS = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4", "mysql_collate": "utf8mb4_unicode_ci"}


def _tables():
    metadata = sa.MetaData()
    for name in ("users", "decks"):
        sa.Table(name, metadata, sa.Column("id", sa.Integer, primary_key=True))
    def timestamp():
        return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")
    def hash_type():
        return sa.LargeBinary(32).with_variant(mysql.BINARY(32), "mysql")
    content = sa.Table(
        TABLE_NAMES[0], metadata,
        sa.Column("physical_deck_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("revision", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", timestamp(), nullable=False),
        sa.CheckConstraint("physical_deck_id >= 0", name="ck_deck_count_content_id"),
        sa.CheckConstraint("revision >= 0", name="ck_deck_count_content_revision"),
        **_OPTIONS,
    )
    learner = sa.Table(
        TABLE_NAMES[1], metadata,
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False),
        sa.Column("effective_deck_id", sa.Integer, primary_key=True, autoincrement=False),
        sa.Column("revision", sa.BigInteger, nullable=False, server_default=sa.text("0")),
        sa.Column("updated_at", timestamp(), nullable=False),
        sa.CheckConstraint("effective_deck_id >= 0", name="ck_deck_count_learner_id"),
        sa.CheckConstraint("revision >= 0", name="ck_deck_count_learner_revision"),
        **_OPTIONS,
    )
    snapshot = sa.Table(
        TABLE_NAMES[2], metadata,
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, autoincrement=False),
        sa.Column("effective_deck_id", sa.Integer, sa.ForeignKey("decks.id", ondelete="CASCADE"), primary_key=True, autoincrement=False),
        sa.Column("contract_code", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("unit_code", sa.SmallInteger, primary_key=True, autoincrement=False),
        sa.Column("total_count", sa.BigInteger, nullable=False),
        sa.Column("new_count", sa.BigInteger, nullable=False),
        sa.Column("learn_count", sa.BigInteger, nullable=False),
        sa.Column("due_count", sa.BigInteger, nullable=False),
        sa.Column("study_day", sa.Date, nullable=False),
        sa.Column("valid_until_utc", timestamp(), nullable=False),
        sa.Column("policy_hash", hash_type(), nullable=False),
        sa.Column("dependency_hash", hash_type(), nullable=False),
        sa.Column("computed_at", timestamp(), nullable=False),
        sa.Index("ix_deck_count_snapshot_deck", "effective_deck_id"),
        sa.CheckConstraint("effective_deck_id > 0", name="ck_deck_count_snapshot_id"),
        sa.CheckConstraint("contract_code = 1", name="ck_deck_count_snapshot_contract"),
        sa.CheckConstraint("unit_code IN (1, 2)", name="ck_deck_count_snapshot_unit"),
        sa.CheckConstraint("total_count >= 0", name="ck_deck_count_snapshot_total"),
        sa.CheckConstraint("new_count >= 0 AND new_count <= total_count", name="ck_deck_count_snapshot_new"),
        sa.CheckConstraint("learn_count >= 0 AND learn_count <= total_count", name="ck_deck_count_snapshot_learn"),
        sa.CheckConstraint("due_count >= 0 AND due_count <= total_count", name="ck_deck_count_snapshot_due"),
        **_OPTIONS,
    )
    return content, learner, snapshot


def _drift(name, detail):
    raise RuntimeError(f"Deck count schema drift in {name}: {detail}; inspect before migrating.")


def _validate(bind, table):
    inspector = sa.inspect(bind)
    actual = {column["name"]: column for column in inspector.get_columns(table.name)}
    if set(actual) != set(table.c.keys()):
        _drift(table.name, "column set differs")
    for expected in table.c:
        column = actual[expected.name]
        default = expected.server_default.arg if expected.server_default is not None else None
        if (
            _normalization._type_sql(column["type"], bind.dialect) != _normalization._type_sql(expected.type, bind.dialect)
            or bool(column["nullable"]) != bool(expected.nullable)
            or _normalization._default(column.get("default")) != _normalization._default(default)
            or column.get("autoincrement") is True
        ):
            _drift(table.name, f"{expected.name} type/nullability/default/autoincrement differs")
    if inspector.get_pk_constraint(table.name).get("constrained_columns") != [column.name for column in table.primary_key]:
        _drift(table.name, "primary key differs")
    expected_fks = {
        (tuple(fk.column_keys), fk.referred_table.name, tuple(element.column.name for element in fk.elements), fk.ondelete)
        for fk in table.foreign_key_constraints
    }
    actual_fks = {
        (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]), fk.get("options", {}).get("ondelete"))
        for fk in inspector.get_foreign_keys(table.name)
    }
    if actual_fks != expected_fks:
        _drift(table.name, "foreign keys differ")
    expected_checks = {c.name: _normalization._check_sql(c.sqltext) for c in table.constraints if isinstance(c, sa.CheckConstraint)}
    actual_checks = {c["name"]: _normalization._check_sql(c["sqltext"]) for c in inspector.get_check_constraints(table.name)}
    if actual_checks != expected_checks:
        _drift(table.name, "CHECK constraints differ")
    expected_indexes = {(index.name, tuple(column.name for column in index.columns), bool(index.unique)) for index in table.indexes}
    actual_indexes = {(index["name"], tuple(index["column_names"]), bool(index["unique"])) for index in inspector.get_indexes(table.name)}
    if expected_indexes != actual_indexes or inspector.get_unique_constraints(table.name):
        _drift(table.name, "secondary indexes differ")
    if bind.dialect.name == "mysql":
        options = inspector.get_table_options(table.name)
        if str(options.get("mysql_engine", "")).lower() != "innodb" or options.get("mysql_collate") != "utf8mb4_unicode_ci":
            _drift(table.name, "engine/collation differs")


def _preflight(bind, tables):
    present = set(sa.inspect(bind).get_table_names())
    for table in tables:
        if table.name in present:
            _validate(bind, table)
    return present


def upgrade():
    bind = op.get_bind()
    tables = _tables()
    present = _preflight(bind, tables)
    inspector = sa.inspect(bind)
    for name in ("users", "decks"):
        if name not in present:
            _drift(name, "required parent table is absent")
        parent = next((column for column in inspector.get_columns(name) if column["name"] == "id"), None)
        if parent is None or _normalization._type_sql(parent["type"], bind.dialect) != "INTEGER" or inspector.get_pk_constraint(name).get("constrained_columns") != ["id"]:
            _drift(name, "id must remain the signed INT primary key")
    for table in tables:
        if table.name not in present:
            table.create(bind=bind)


def downgrade():
    bind = op.get_bind()
    tables = _tables()
    present = _preflight(bind, tables)
    # Token reset is an ABA hazard. A database with admitted state must retain
    # these tables during application rollback (flags raw/off), not drop them.
    for table in tables:
        if table.name in present and bind.execute(sa.select(sa.func.count()).select_from(table)).scalar_one():
            raise RuntimeError("Deck count downgrade refuses populated tokens/snapshots; disable readers and retain monotonic tokens.")
    for table in reversed(tables):
        if table.name in present:
            table.drop(bind=bind)
