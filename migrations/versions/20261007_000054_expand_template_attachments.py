"""Expand reusable templates and NoteType-scoped presentation attachments.

Revision ID: 20261007_000054
Revises: 20261007_000053

No Template, application, Card, source, version or progress identity changes.
Run before deploying the new models. SQLite legacy-table rehearsal requires
foreign_keys=OFF before the migration transaction; this avoids parent rebuild
cascades. MySQL retains FK checks and alters the existing tables in place.
"""

from __future__ import annotations

import importlib
import re

from alembic import op
import sqlalchemy as sa

revision = "20261007_000054"
down_revision = "20261007_000053"
branch_labels = None
depends_on = None

previous = importlib.import_module("migrations.versions.20261007_000053_add_template_versions")
TEMPLATE_COLUMNS = ("description", "primary_category", "origin", "source_template_id", "source_version_id", "archived_at")
APPLICATION_COLUMNS = ("input_bindings", "display_name", "position", "is_default")
OLD_UNIQUE = "uq_study_applications_template_occurrence"
NEW_UNIQUE = "uq_study_applications_note_type_template_occurrence"


def _tables():
    users, note_types, old_templates, versions = previous._tables()
    metadata = sa.MetaData()
    users.to_metadata(metadata)
    note_types.to_metadata(metadata)
    templates = sa.Table(
        "templates", metadata,
        *(column._copy() for column in old_templates.c),
        sa.Column("description", sa.Text, nullable=True),
        sa.Column("primary_category", sa.String(120), nullable=True),
        sa.Column("origin", sa.String(24), nullable=False, server_default="authored"),
        sa.Column("source_template_id", sa.String(36), nullable=True),
        sa.Column("source_version_id", sa.String(36), nullable=True),
        sa.Column("archived_at", sa.DateTime, nullable=True),
        sa.ForeignKeyConstraint(["note_type_id"], ["note_types.id"], ondelete="SET NULL", name="fk_templates_origin_note_type"),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="CASCADE", name="fk_templates_owner_user"),
        sa.ForeignKeyConstraint(["source_template_id"], ["templates.id"], ondelete="SET NULL", name="fk_templates_source_template"),
        sa.ForeignKeyConstraint(["source_version_id"], ["template_versions.id"], ondelete="SET NULL", name="fk_templates_source_version", use_alter=True),
        sa.CheckConstraint("origin IN ('authored', 'market_copy')", name="ck_templates_origin"),
        *(sa.Index(f"ix_templates_{name}", name) for name in ("note_type_id", "owner_user_id", "primary_category", "source_template_id", "archived_at")),
    )
    templates.c.note_type_id.nullable = True
    versions.to_metadata(metadata)
    applications = sa.Table(
        "study_applications", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_type_id", sa.String(36), sa.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("occurrence_key", sa.String(64), nullable=False),
        sa.Column("source_ord", sa.Integer, nullable=True),
        sa.Column("status_code", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("input_bindings", sa.JSON, nullable=True),
        sa.Column("display_name", sa.String(255), nullable=True),
        sa.Column("position", sa.Integer, nullable=False, server_default="0"),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default="0"),
        sa.UniqueConstraint("note_type_id", "template_id", "occurrence_key", name=NEW_UNIQUE),
        sa.Index("ix_study_applications_note_type_ord", "note_type_id", "source_ord"),
        sa.CheckConstraint("status_code IN ('ACTIVE', 'RETIRED')", name="ck_study_applications_status"),
    )
    fields = sa.Table(
        "field_defs", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_type_id", sa.String(36), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
    )
    return templates, applications, fields


def _error(table, detail):
    raise RuntimeError(f"Template attachment schema/data drift in {table}: {detail}; inspect before migrating.")


def _default(value):
    return None if value is None else str(value).strip().strip("()'\"")


def _check_sql(value):
    # MySQL SHOW CREATE/inspection adds charset introducers to string CHECK
    # literals. They preserve the inherited column semantics, not schema drift.
    return previous._check_sql(re.sub(r"_[A-Za-z][A-Za-z0-9]*(?=['\"])", "", str(value)))


def _column(bind, name, actual, expected, *, legacy_note_type=False):
    nullable = False if legacy_note_type else expected.nullable
    default = expected.server_default.arg if expected.server_default is not None else None
    if previous._type_sql(actual["type"], bind.dialect) != previous._type_sql(expected.type, bind.dialect) or bool(actual["nullable"]) != bool(nullable) or _default(actual.get("default")) != _default(default):
        _error(name, f"{expected.name} type/nullability/default differs")


def _schema_state(bind, table, added):
    inspector = sa.inspect(bind)
    if not inspector.has_table(table.name):
        _error(table.name, "required table is absent")
    columns = {row["name"]: row for row in inspector.get_columns(table.name)}
    if set(columns) - set(table.c.keys()) or set(table.c.keys()) - set(added) - set(columns):
        _error(table.name, "column set differs")
    legacy_nt = table.name == "templates" and not bool(columns["note_type_id"]["nullable"])
    for name, actual in columns.items():
        _column(bind, table.name, actual, table.c[name], legacy_note_type=legacy_nt and name == "note_type_id")
    if inspector.get_pk_constraint(table.name).get("constrained_columns") != ["id"]:
        _error(table.name, "primary key differs")
    if bind.dialect.name == "mysql" and str(inspector.get_table_options(table.name).get("mysql_engine", "")).lower() != "innodb":
        _error(table.name, "engine must be InnoDB")
    fks = previous._fks(inspector, table.name)
    if table.name == "templates":
        expected = {(("note_type_id",), "note_types", ("id",), "CASCADE" if legacy_nt else "SET NULL"), (("owner_user_id",), "users", ("id",), "CASCADE")}
        for name, parent in (("source_template_id", "templates"), ("source_version_id", "template_versions")):
            if name in columns:
                expected.add(((name,), parent, ("id",), "SET NULL"))
        unique = inspector.get_unique_constraints(table.name)
        if unique:
            _error(table.name, "unexpected unique constraints")
    else:
        expected = {(("note_type_id",), "note_types", ("id",), "CASCADE"), (("template_id",), "templates", ("id",), "CASCADE")}
    if fks != expected:
        _error(table.name, "foreign keys/delete behavior differ")
    checks = {row["name"]: _check_sql(row["sqltext"]) for row in inspector.get_check_constraints(table.name)}
    if table.name == "templates":
        allowed_checks = {} if "origin" not in columns else {"ck_templates_origin": _check_sql("origin IN ('authored', 'market_copy')")}
        if checks != allowed_checks:
            _error(table.name, "origin CHECK differs")
        uniques = set()
    else:
        old_check = {"ck_study_applications_status": _check_sql("status_code IN ('ACTIVE')")}
        # MySQL canonicalizes a one-value IN into equality.
        old_equal = {"ck_study_applications_status": _check_sql("status_code = 'ACTIVE'")}
        new_check = {"ck_study_applications_status": _check_sql("status_code IN ('ACTIVE', 'RETIRED')")}
        if checks not in (old_check, old_equal, new_check):
            _error(table.name, "status CHECK differs")
        uniques = {(row["name"], tuple(row["column_names"])) for row in inspector.get_unique_constraints(table.name)}
        if uniques not in ({(OLD_UNIQUE, ("template_id", "occurrence_key"))}, {(NEW_UNIQUE, ("note_type_id", "template_id", "occurrence_key"))}):
            _error(table.name, "application occurrence unique differs")
    indexes = {(row["name"], tuple(row["column_names"]), bool(row["unique"])) for row in inspector.get_indexes(table.name) if not (bool(row["unique"]) and (row["name"], tuple(row["column_names"])) in uniques)}
    if bind.dialect.name == "mysql":
        indexes = {row for row in indexes if row[1:] not in ((("source_version_id",), False), (("template_id",), False))}
        # Prior MySQL FK supporting index may precede the declared owner index.
        indexes = {row for row in indexes if not (row[1:] == (("owner_user_id",), False) and row[0] != "ix_templates_owner_user_id")}
    expected_indexes = {(index.name, tuple(column.name for column in index.columns), bool(index.unique)) for index in table.indexes if all(column.name in columns for column in index.columns)}
    if table.name == "templates" and "ix_templates_owner_user_id" not in {row[0] for row in indexes}:
        expected_indexes.discard(("ix_templates_owner_user_id", ("owner_user_id",), False))
    if indexes != expected_indexes:
        _error(table.name, "indexes differ")
    current = set(columns) == set(table.c.keys()) and not legacy_nt
    if table.name == "study_applications":
        current = current and uniques == {(NEW_UNIQUE, ("note_type_id", "template_id", "occurrence_key"))} and checks == new_check
    else:
        current = current and "ix_templates_owner_user_id" in {row[0] for row in indexes}
    return columns, current


def _preflight(bind):
    templates, applications, fields = _tables()
    template_state = _schema_state(bind, templates, TEMPLATE_COLUMNS)
    application_state = _schema_state(bind, applications, APPLICATION_COLUMNS)
    previous._validate_versions(bind, templates.metadata.tables["template_versions"])
    inspector = sa.inspect(bind)
    if not inspector.has_table("field_defs"):
        _error("field_defs", "required binding identity table is absent")
    field_columns = {row["name"]: row for row in inspector.get_columns("field_defs")}
    for expected in fields.c:
        if expected.name not in field_columns:
            _error("field_defs", f"required {expected.name} is absent")
        _column(bind, "field_defs", field_columns[expected.name], expected)
    duplicate = bind.execute(sa.select(fields.c.note_type_id, fields.c.name).group_by(fields.c.note_type_id, fields.c.name).having(sa.func.count() > 1).limit(1)).first()
    if duplicate:
        _error("field_defs", "duplicate names cannot produce deterministic legacy bindings")
    previous._validate_mysql_collations(bind, True)
    return templates, applications, fields, template_state, application_state


def _rebuild_sqlite(bind, table):
    old = sa.Table(table.name, sa.MetaData(), autoload_with=bind)
    temporary = table.to_metadata(table.metadata, name=f"_flama_tmp_{table.name}")
    temporary.indexes.clear()
    temporary.create(bind)
    names = [name for name in old.c.keys() if name in temporary.c]
    bind.execute(temporary.insert().from_select(names, sa.select(*(old.c[name] for name in names))))
    old.drop(bind)
    op.rename_table(temporary.name, table.name)
    for index in table.indexes:
        index.create(bind)


def _alter_mysql(bind, templates, applications, template_columns, application_columns):
    for name in TEMPLATE_COLUMNS:
        if name not in template_columns:
            op.add_column("templates", templates.c[name]._copy())
            if name in ("source_template_id", "source_version_id"):
                parent = "templates" if name == "source_template_id" else "template_versions"
                op.create_foreign_key(f"fk_templates_{'source_template' if name == 'source_template_id' else 'source_version'}", "templates", parent, [name], ["id"], ondelete="SET NULL")
    if not template_columns["note_type_id"]["nullable"]:
        fk = next(row for row in sa.inspect(bind).get_foreign_keys("templates") if row["constrained_columns"] == ["note_type_id"])
        op.drop_constraint(fk["name"], "templates", type_="foreignkey")
        op.alter_column("templates", "note_type_id", existing_type=sa.String(36), nullable=True)
        op.create_foreign_key("fk_templates_origin_note_type", "templates", "note_types", ["note_type_id"], ["id"], ondelete="SET NULL")
    checks = {row["name"] for row in sa.inspect(bind).get_check_constraints("templates")}
    if "ck_templates_origin" not in checks:
        op.create_check_constraint("ck_templates_origin", "templates", "origin IN ('authored', 'market_copy')")
    for index in templates.indexes:
        if index.name not in {row["name"] for row in sa.inspect(bind).get_indexes("templates")}:
            index.create(bind)
    for name in APPLICATION_COLUMNS:
        if name not in application_columns:
            op.add_column("study_applications", applications.c[name]._copy())
    unique = {row["name"] for row in sa.inspect(bind).get_unique_constraints("study_applications")}
    if OLD_UNIQUE in unique:
        # Create the replacement first; it can support the template FK only
        # together with the explicitly retained supporting template index.
        indexes = sa.inspect(bind).get_indexes("study_applications")
        if not any(row["column_names"] == ["template_id"] and not row["unique"] for row in indexes):
            op.create_index("ix_study_applications_template_id", "study_applications", ["template_id"])
        op.create_unique_constraint(NEW_UNIQUE, "study_applications", ["note_type_id", "template_id", "occurrence_key"])
        op.drop_constraint(OLD_UNIQUE, "study_applications", type_="unique")
    check = sa.inspect(bind).get_check_constraints("study_applications")[0]
    if _check_sql(check["sqltext"]) != _check_sql("status_code IN ('ACTIVE', 'RETIRED')"):
        op.drop_constraint("ck_study_applications_status", "study_applications", type_="check")
        op.create_check_constraint("ck_study_applications_status", "study_applications", "status_code IN ('ACTIVE', 'RETIRED')")


def _backfill(bind, templates, applications, fields, *, derive_metadata):
    note_types = templates.metadata.tables["note_types"]
    owners = dict(bind.execute(sa.select(note_types.c.id, note_types.c.user_id)).all())
    for row in bind.execute(sa.select(templates.c.id, templates.c.note_type_id).where(templates.c.owner_user_id.is_(None))).mappings():
        owner = owners.get(row["note_type_id"])
        if owner is not None:
            bind.execute(templates.update().where(templates.c.id == row["id"]).values(owner_user_id=owner))
    cursor = None
    while True:
        query = sa.select(applications, templates.c.position.label("template_position"), templates.c.is_default.label("template_default")).join(templates, applications.c.template_id == templates.c.id).order_by(applications.c.id).limit(500)
        if cursor is not None:
            query = query.where(applications.c.id > cursor)
        rows = bind.execute(query).mappings().all()
        if not rows:
            return
        bindings = {}
        for field in bind.execute(sa.select(fields).where(fields.c.note_type_id.in_({row["note_type_id"] for row in rows})).order_by(fields.c.position, fields.c.id)).mappings():
            bindings.setdefault(field["note_type_id"], {})[field["name"]] = field["id"]
        for row in rows:
            changes = {}
            if row["input_bindings"] is None:
                changes["input_bindings"] = bindings.get(row["note_type_id"], {})
            if derive_metadata or (row["input_bindings"] is None and row["occurrence_key"] == "compat"):
                changes.update(position=row["template_position"], is_default=row["template_default"])
            if changes:
                bind.execute(applications.update().where(applications.c.id == row["id"]).values(**changes))
        cursor = rows[-1]["id"]


def upgrade():
    bind = op.get_bind()
    templates, applications, fields, template_state, application_state = _preflight(bind)
    if bind.dialect.name == "sqlite":
        if not all((template_state[1], application_state[1])) and bind.exec_driver_sql("PRAGMA foreign_keys").scalar():
            raise RuntimeError("SQLite attachment migration requires foreign_keys=OFF before its transaction; refusing a parent rebuild that could delete Cards.")
        if not template_state[1]:
            _rebuild_sqlite(bind, templates)
        if not application_state[1]:
            _rebuild_sqlite(bind, applications)
    else:
        _alter_mysql(bind, templates, applications, *[state[0] for state in (template_state, application_state)])
    _backfill(bind, templates, applications, fields, derive_metadata=any(name not in application_state[0] for name in ("position", "is_default")))


def downgrade():
    # Backward app rollback retains the expansion. Dropping stable bindings or
    # restoring parent-delete cascades could remove independently used content.
    raise RuntimeError("Template attachment downgrade refuses to discard reusable ownership and stable bindings; retain the expanded schema during application rollback.")
