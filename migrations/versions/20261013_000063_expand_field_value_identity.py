"""Expand stable field identity without changing named values or media links.

Revision ID: 20261013_000063
Revises: 20261012_000062

Nullable sidecars are unused for existing rows until explicit dual-write or
offline backfill. NULL codec denotes legacy storage; adapters use field-id.v1.
No content backfill, scheduler mutation, index, FK, or name-key contraction.
Media field_def_id is scoped by its Note, deliberately retaining historical
identity when a FieldDef is deleted; existing field_name uniqueness remains.

MySQL appends columns using ALGORITHM=INSTANT, LOCK=DEFAULT (the only LOCK
option supported with INSTANT), with bounded metadata-lock waiting. Unsupported
tables/versions fail instead of silently rebuilding. Rehearse on the deployment
engine before rollout. Dropping on MySQL requires INSTANT DROP (8.0.29+).
Downgrade requires writers stopped and refuses any populated identity state.
"""

from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa


revision = "20261013_000063"
down_revision = "20261012_000062"
branch_labels = None
depends_on = None

LOCK_WAIT_SECONDS = 30


def _columns():
    return {
        "notes": (
            sa.Column("field_values_by_id", sa.JSON(), nullable=True),
            sa.Column("field_values_codec", sa.String(32), nullable=True),
            sa.Column("field_values_extras", sa.JSON(), nullable=True),
            sa.Column("content_revision", sa.BigInteger(), nullable=False, server_default="0"),
        ),
        "note_types": (
            sa.Column("field_schema_revision", sa.BigInteger(), nullable=False, server_default="0"),
        ),
        "media_assets": (
            sa.Column("field_def_id", sa.String(36), nullable=True),
        ),
    }


def _inspect_contract(bind):
    """Validate every existing sidecar before any nontransactional MySQL DDL."""
    inspector = sa.inspect(bind)
    present = {}
    for table, columns in _columns().items():
        if not inspector.has_table(table):
            raise RuntimeError(f"Field identity expansion requires existing {table} table.")
        actual = {column["name"]: column for column in inspector.get_columns(table)}
        present[table] = actual
        for column in columns:
            found = actual.get(column.name)
            if found is None:
                continue
            # MySQL reflects the inherited table collation onto VARCHAR;
            # comparing compiled strings would reject our own valid DDL.
            actual_type = found["type"].as_generic()
            type_matches = (type(actual_type) is type(column.type)
                            and getattr(actual_type, "length", None) == getattr(column.type, "length", None)
                            and not getattr(found["type"], "unsigned", False))
            default = found.get("default")
            # SQLite reflection may parenthesize/quote a scalar server default.
            default = str(default).strip("() '\"") if default is not None else None
            expected_default = "0" if column.server_default is not None else None
            if (not type_matches or found["nullable"] != column.nullable
                    or default != expected_default):
                raise RuntimeError(f"Existing {table}.{column.name} differs from field identity contract.")
    return present


@contextmanager
def _bounded_mysql_ddl(bind):
    previous = int(bind.execute(sa.text("SELECT @@SESSION.lock_wait_timeout")).scalar_one())
    bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {LOCK_WAIT_SECONDS}"))
    try:
        yield
    finally:
        bind.execute(sa.text(f"SET SESSION lock_wait_timeout = {previous}"))


def _mysql_alter(bind, table, clauses):
    if clauses:
        bind.execute(sa.text(f"ALTER TABLE `{table}` " + ", ".join(clauses)
                             + ", ALGORITHM=INSTANT, LOCK=DEFAULT"))


def upgrade():
    bind = op.get_bind()
    present = _inspect_contract(bind)
    missing = {table: [column for column in columns if column.name not in present[table]]
               for table, columns in _columns().items()}
    if not any(missing.values()):
        return
    if bind.dialect.name == "mysql":
        with _bounded_mysql_ddl(bind):
            for table, columns in missing.items():
                clauses = ["ADD COLUMN " + str(sa.schema.CreateColumn(column).compile(dialect=bind.dialect))
                           for column in columns]
                _mysql_alter(bind, table, clauses)
    else:
        for table, columns in missing.items():
            for column in columns:
                op.add_column(table, column)


def downgrade():
    bind = op.get_bind()
    present = _inspect_contract(bind)
    existing = {table: [column for column in columns if column.name in present[table]]
                for table, columns in _columns().items()}
    # Do not discard mapped values, orphan payloads, or revision evidence.
    # Preflight all tables first; MySQL DDL is not transactionally reversible.
    for table, columns in existing.items():
        conditions = [f"`{column.name}` <> 0" if column.server_default is not None
                      else f"`{column.name}` IS NOT NULL" for column in columns]
        if conditions and bind.execute(sa.text(
                f"SELECT 1 FROM `{table}` WHERE " + " OR ".join(conditions) + " LIMIT 1")).first():
            raise RuntimeError("Field identity downgrade refused: populated values/revisions require "
                               "verified archive and reverse projection with writers stopped.")
    if bind.dialect.name == "mysql":
        with _bounded_mysql_ddl(bind):
            for table, columns in reversed(list(existing.items())):
                _mysql_alter(bind, table, [f"DROP COLUMN `{column.name}`" for column in reversed(columns)])
    else:
        for table, columns in reversed(list(existing.items())):
            for column in reversed(columns):
                op.drop_column(table, column.name)
