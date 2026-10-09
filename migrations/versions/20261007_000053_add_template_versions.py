"""Expand Template ownership and immutable version history without changing IDs.

Revision ID: 20261007_000053
Revises: 20261006_000052
Create Date: 2026-10-07 00:00:53

Deploy this revision before code selecting the new Template columns. Existing
sources and required NoteType attachments remain authoritative in this phase.
Startup create_all schemas are accepted only after complete preflight. Backfill
uses deterministic UUIDs and bounded batches, so an interrupted run can resume.
"""

from __future__ import annotations

from datetime import datetime
import hashlib
import importlib
import json
import re
from uuid import NAMESPACE_URL, uuid5

from alembic import op
import sqlalchemy as sa


revision = "20261007_000053"
down_revision = "20261006_000052"
branch_labels = None
depends_on = None

BATCH_SIZE = 500
ADDED_COLUMNS = ("owner_user_id", "input_schema", "current_version_id")
VERSION_TABLE = "template_versions"


def _tables():
    """Freeze this revision's contract; never import mutable application code."""
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    note_types = sa.Table(
        "note_types", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, nullable=False),
    )
    templates = sa.Table(
        "templates", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_type_id", sa.String(36), sa.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("front_html", sa.Text, nullable=False),
        sa.Column("back_html", sa.Text, nullable=False),
        sa.Column("shared_css", sa.Text, nullable=False),
        sa.Column("position", sa.Integer, nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.Column("owner_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_templates_owner_user"), nullable=True),
        sa.Column("input_schema", sa.JSON, nullable=True),
        sa.Column("current_version_id", sa.String(36), nullable=True),
        sa.Index("ix_templates_note_type_id", "note_type_id"),
    )
    versions = sa.Table(
        VERSION_TABLE, metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("version_no", sa.Integer, nullable=False),
        sa.Column("front_html", sa.Text, nullable=False),
        sa.Column("back_html", sa.Text, nullable=False),
        sa.Column("shared_css", sa.Text, nullable=False),
        sa.Column("input_schema", sa.JSON, nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("origin", sa.String(24), nullable=False),
        sa.Column("change_note", sa.Text, nullable=True),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("template_id", "version_no", name="uq_template_versions_template_no"),
        sa.CheckConstraint("version_no > 0", name="ck_template_versions_version_no_positive"),
        sa.Index("ix_template_versions_template_id", "template_id"),
    )
    return users, note_types, templates, versions


def _content_hash(front_html, back_html, shared_css):
    # Frozen GT-08 contract: byte-preserving JSON, never normalize whitespace.
    payload = {"front_html": front_html or "", "back_html": back_html or "", "shared_css": shared_css or ""}
    encoded = json.dumps(payload, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _initial_version_id(template_id):
    return str(uuid5(NAMESPACE_URL, f"flama:template-version:{template_id}:1"))


def _drift(table_name, detail):
    raise RuntimeError(f"Template version schema/data drift in {table_name}: {detail}; inspect before migrating.")


def _type_sql(column_type, dialect):
    value = str(column_type.compile(dialect=dialect)).upper()
    if dialect.name == "mysql" and value in ("BOOL", "BOOLEAN", "TINYINT(1)"):
        return "BOOLEAN"
    value = re.sub(r"\b(?:CHARACTER SET|COLLATE)\s+\w+", "", value)
    value = re.sub(r"\b(TINYINT|SMALLINT|INTEGER|INT|BIGINT)\(\d+\)", r"\1", value)
    return " ".join(re.sub(r"\bINT\b", "INTEGER", value).split())


def _check_sql(value):
    return re.sub(r"[\s()`]", "", str(value)).lower()


def _validate_column(bind, table_name, actual, expected):
    if (
        _type_sql(actual["type"], bind.dialect) != _type_sql(expected.type, bind.dialect)
        or bool(actual["nullable"]) != bool(expected.nullable)
        or actual.get("default") is not None
    ):
        _drift(table_name, f"{expected.name} type/nullability/default differs")


def _fks(inspector, table_name):
    if inspector.bind.dialect.name == "sqlite":
        # SQLAlchemy's SQLite parser can omit ON DELETE from a column-level
        # FK introduced by ADD COLUMN. PRAGMA reports the enforced contract.
        groups = {}
        for row in inspector.bind.exec_driver_sql(f"PRAGMA foreign_key_list({table_name})").mappings():
            groups.setdefault(row["id"], []).append(row)
        return {
            (tuple(row["from"] for row in sorted(rows, key=lambda item: item["seq"])),
             rows[0]["table"], tuple(row["to"] for row in sorted(rows, key=lambda item: item["seq"])),
             rows[0]["on_delete"] if rows[0]["on_delete"] != "NO ACTION" else None)
            for rows in groups.values()
        }
    return {
        (tuple(fk["constrained_columns"]), fk["referred_table"], tuple(fk["referred_columns"]), str(fk.get("options", {}).get("ondelete", "")).upper() or None)
        for fk in inspector.get_foreign_keys(table_name)
    }


def _validate_versions(bind, versions):
    inspector = sa.inspect(bind)
    actual = {column["name"]: column for column in inspector.get_columns(VERSION_TABLE)}
    if set(actual) != set(versions.c.keys()):
        _drift(VERSION_TABLE, "column set differs")
    for expected in versions.c:
        _validate_column(bind, VERSION_TABLE, actual[expected.name], expected)
    if inspector.get_pk_constraint(VERSION_TABLE).get("constrained_columns") != ["id"]:
        _drift(VERSION_TABLE, "primary key differs")
    expected_fks = {
        (("template_id",), "templates", ("id",), "CASCADE"),
        (("created_by_user_id",), "users", ("id",), "SET NULL"),
    }
    if _fks(inspector, VERSION_TABLE) != expected_fks:
        _drift(VERSION_TABLE, "foreign keys/delete behavior differ")
    unique = {(row["name"], tuple(row["column_names"])) for row in inspector.get_unique_constraints(VERSION_TABLE)}
    if unique != {("uq_template_versions_template_no", ("template_id", "version_no"))}:
        _drift(VERSION_TABLE, "unique version sequence differs")
    checks = {row["name"]: _check_sql(row["sqltext"]) for row in inspector.get_check_constraints(VERSION_TABLE)}
    if checks != {"ck_template_versions_version_no_positive": "version_no>0"}:
        _drift(VERSION_TABLE, "positive version CHECK differs")
    indexes = {
        (row["name"], tuple(row["column_names"]), bool(row["unique"]))
        for row in inspector.get_indexes(VERSION_TABLE)
        if not row.get("duplicates_constraint")
        and not (bool(row["unique"]) and (row["name"], tuple(row["column_names"])) in unique)
    }
    # MySQL materializes the SET NULL FK's supporting index automatically.
    if bind.dialect.name == "mysql":
        indexes = {row for row in indexes if row[1:] != (("created_by_user_id",), False)}
    if indexes != {("ix_template_versions_template_id", ("template_id",), False)}:
        _drift(VERSION_TABLE, "indexes differ")
    if bind.dialect.name == "mysql" and str(inspector.get_table_options(VERSION_TABLE).get("mysql_engine", "")).lower() != "innodb":
        _drift(VERSION_TABLE, "engine must be InnoDB")


def _validate_template_indexes(bind):
    inspector = sa.inspect(bind)
    indexes = {
        (row["name"], tuple(row["column_names"]), bool(row["unique"]))
        for row in inspector.get_indexes("templates")
    }
    if bind.dialect.name == "mysql":
        indexes = {row for row in indexes if row[1:] != (("owner_user_id",), False)}
    if indexes != {("ix_templates_note_type_id", ("note_type_id",), False)} or inspector.get_unique_constraints("templates") or inspector.get_check_constraints("templates"):
        _drift("templates", "indexes/unique/CHECK constraints differ")


def _validate_mysql_collations(bind, version_table_present):
    if bind.dialect.name != "mysql":
        return
    # Both migration DDL and ORM create_all inherit database defaults. Refuse
    # historical ID collation drift before a FK ALTER implicitly commits DDL.
    expected = bind.execute(sa.text(
        "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
        "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()"
    )).one()
    targets = [("templates", "id"), ("note_types", "id")]
    if version_table_present:
        targets.extend(((VERSION_TABLE, "id"), (VERSION_TABLE, "template_id")))
    for table_name, column_name in targets:
        actual = bind.execute(sa.text(
            "SELECT CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS "
            "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :table_name AND COLUMN_NAME = :column_name"
        ), {"table_name": table_name, "column_name": column_name}).one()
        if tuple(actual) != tuple(expected):
            _drift(table_name, f"{column_name} charset/collation differs from inherited version FK DDL")


def _preflight(bind):
    users, note_types, templates, versions = _tables()
    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())
    if "templates" in present:
        actual = {column["name"]: column for column in inspector.get_columns("templates")}
        if "origin" in actual:
            # A fresh wsgi/create_all bootstrap creates the later attachment
            # schema before Alembic runs. Adopt only its fully validated empty
            # shape; never reinterpret populated later ownership/history as 53.
            attachments = importlib.import_module("migrations.versions.20261007_000054_expand_template_attachments")
            later_templates, applications, _, template_state, application_state = attachments._preflight(bind)
            if not template_state[1] or not application_state[1]:
                _drift("templates", "incomplete later attachment bootstrap schema")
            for table in (later_templates, applications, versions):
                if bind.execute(sa.select(table.c.id).limit(1)).first():
                    _drift(table.name, "cannot adopt populated later attachment schema before revision 53")
            return set(actual), present, templates, versions
    for parent in (users, note_types, templates):
        if parent.name not in present:
            _drift(parent.name, "required parent table is absent")
        actual = {column["name"]: column for column in inspector.get_columns(parent.name)}
        expected_columns = parent.c if parent.name == "templates" else (parent.c.id,)
        for expected in expected_columns:
            if expected.name not in actual:
                if parent.name == "templates" and expected.name in ADDED_COLUMNS:
                    continue
                _drift(parent.name, f"required {expected.name} column is absent")
            _validate_column(bind, parent.name, actual[expected.name], expected)
        if inspector.get_pk_constraint(parent.name).get("constrained_columns") != ["id"]:
            _drift(parent.name, "primary key differs")
        if bind.dialect.name == "mysql":
            if str(inspector.get_table_options(parent.name).get("mysql_engine", "")).lower() != "innodb":
                _drift(parent.name, "parent engine must be InnoDB")
    nt_columns = {column["name"]: column for column in inspector.get_columns("note_types")}
    if "user_id" not in nt_columns:
        _drift("note_types", "required ownership column is absent")
    _validate_column(bind, "note_types", nt_columns["user_id"], note_types.c.user_id)
    columns = {column["name"] for column in inspector.get_columns("templates")}
    if columns - set(templates.c.keys()):
        _drift("templates", "unexpected columns differ from the expand contract")
    expected_fks = {(("note_type_id",), "note_types", ("id",), "CASCADE")}
    if "owner_user_id" in columns:
        expected_fks.add((("owner_user_id",), "users", ("id",), "CASCADE"))
    if _fks(inspector, "templates") != expected_fks:
        _drift("templates", "foreign keys differ; current_version_id must remain application-managed")
    _validate_template_indexes(bind)
    if VERSION_TABLE in present:
        _validate_versions(bind, versions)
    _validate_mysql_collations(bind, VERSION_TABLE in present)
    # Reflected legacy columns avoid selecting additions before their DDL.
    legacy = sa.Table("templates", sa.MetaData(), autoload_with=bind)
    bad_owner = bind.execute(sa.select(legacy.c.id).select_from(
        legacy.outerjoin(note_types, legacy.c.note_type_id == note_types.c.id)
        .outerjoin(users, note_types.c.user_id == users.c.id)
    ).where(users.c.id.is_(None)).limit(1)).first()
    if bad_owner:
        _drift("templates", f"{bad_owner[0]} has no existing NoteType owner")
    for row, history in _rows(bind, legacy, note_types, versions if VERSION_TABLE in present else None):
        _matching_version(row, history)
    return columns, present, templates, versions


def _rows(bind, templates, note_types, versions):
    cursor = None
    while True:
        query = sa.select(templates, note_types.c.user_id.label("note_type_owner")).join(
            note_types, templates.c.note_type_id == note_types.c.id,
        ).order_by(templates.c.id).limit(BATCH_SIZE)
        if cursor is not None:
            query = query.where(templates.c.id > cursor)
        batch = bind.execute(query).mappings().all()
        if not batch:
            return
        history_by_template = {}
        if versions is not None:
            histories = bind.execute(sa.select(versions).where(
                versions.c.template_id.in_([row["id"] for row in batch]),
            ).order_by(versions.c.version_no)).mappings().all()
            for version in histories:
                history_by_template.setdefault(version["template_id"], []).append(version)
        for row in batch:
            yield row, history_by_template.get(row["id"], [])
        cursor = batch[-1]["id"]


def _matching_version(row, history):
    schema = row.get("input_schema") if row.get("input_schema") is not None else []
    if not isinstance(schema, list):
        _drift("templates", f"{row['id']} input_schema must be a JSON list")
    if row.get("owner_user_id") not in (None, row["note_type_owner"]):
        _drift("templates", f"{row['id']} owner differs from its required NoteType attachment")
    pointer = row.get("current_version_id")
    if not history:
        if pointer is not None:
            _drift("templates", f"{row['id']} has a dangling current version")
        return None
    current = next((version for version in history if version["id"] == pointer), None) if pointer else history[-1]
    if current is None or any(current[key] != row[key] for key in ("front_html", "back_html", "shared_css")) or current["input_schema"] != schema:
        _drift("templates", f"{row['id']} current snapshot differs from source")
    if current["content_hash"] != _content_hash(row["front_html"], row["back_html"], row["shared_css"]):
        _drift(VERSION_TABLE, f"{current['id']} content hash differs")
    return current


def _backfill(bind, templates, versions):
    _, note_types, _, _ = _tables()
    for row, history in _rows(bind, templates, note_types, versions):
        current = _matching_version(row, history)
        if current is None:
            version_id = _initial_version_id(row["id"])
            bind.execute(versions.insert().values(
                id=version_id, template_id=row["id"], version_no=1,
                front_html=row["front_html"], back_html=row["back_html"], shared_css=row["shared_css"],
                input_schema=row["input_schema"] if row["input_schema"] is not None else [],
                content_hash=_content_hash(row["front_html"], row["back_html"], row["shared_css"]),
                origin="backfill", change_note=None, created_by_user_id=row["note_type_owner"],
                created_at=row["updated_at"] or row["created_at"] or datetime.utcnow(),
            ))
        else:
            version_id = current["id"]
        changes = {}
        if row["owner_user_id"] is None:
            changes["owner_user_id"] = row["note_type_owner"]
        if row["current_version_id"] is None:
            changes["current_version_id"] = version_id
        if changes:
            # Frozen Core table has no onupdate: preserve source updated_at.
            bind.execute(templates.update().where(templates.c.id == row["id"]).values(**changes))


def upgrade():
    bind = op.get_bind()
    columns, present, templates, versions = _preflight(bind)
    for name in ADDED_COLUMNS:
        if name in columns:
            continue
        if name == "owner_user_id" and bind.dialect.name == "sqlite":
            # Native addition preserves Card rows even with SQLite FK checks
            # enabled; a batch rebuild of the parent could cascade-delete them.
            bind.exec_driver_sql("ALTER TABLE templates ADD COLUMN owner_user_id INTEGER CONSTRAINT fk_templates_owner_user REFERENCES users (id) ON DELETE CASCADE")
        elif name == "owner_user_id":
            op.add_column("templates", sa.Column(
                "owner_user_id", sa.Integer,
                sa.ForeignKey("users.id", ondelete="CASCADE", name="fk_templates_owner_user"),
                nullable=True,
            ))
        else:
            op.add_column("templates", templates.c[name]._copy())
    if VERSION_TABLE not in present:
        versions.create(bind=bind)
    _backfill(bind, templates, versions)


def downgrade():
    bind = op.get_bind()
    columns, present, templates, versions = _preflight(bind)
    if "origin" in columns:
        _drift("templates", "cannot downgrade later attachment schema through revision 53")
    if VERSION_TABLE in present:
        history_exists = bind.execute(sa.select(versions.c.template_id).group_by(versions.c.template_id).having(
            sa.or_(sa.func.count() > 1, sa.func.max(versions.c.version_no) > 1),
        ).limit(1)).first()
        if history_exists:
            raise RuntimeError("Template version downgrade refuses version history; retain the additive schema during application rollback.")
        # Only migration-created, unchanged initial history is a reversible
        # rehearsal. A sole authored snapshot also deserves retention.
        authored = bind.execute(sa.select(versions.c.id).where(versions.c.origin != "backfill").limit(1)).first()
        if authored:
            raise RuntimeError("Template version downgrade refuses authored history; retain the additive schema during application rollback.")
        versions.drop(bind=bind)
    for name in reversed(ADDED_COLUMNS):
        if name not in columns:
            continue
        if name == "owner_user_id" and bind.dialect.name != "sqlite":
            owner_fk = next(fk for fk in sa.inspect(bind).get_foreign_keys("templates") if fk["constrained_columns"] == [name])
            op.drop_constraint(owner_fk["name"], "templates", type_="foreignkey")
        op.drop_column("templates", name)
