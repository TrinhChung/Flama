"""Add isolated template publishers, releases, user subscriptions and presets.

Revision ID: 20261007_000055
Revises: 20261007_000054

Historical deck releases remain explicitly uninitialized: no presentation pin
is inferred from today's mutable sources. New releases freeze their pins and
attachment state atomically. Existing source rows/history are not rewritten.
"""

from __future__ import annotations

import importlib

from alembic import op
import sqlalchemy as sa

revision = "20261007_000055"
down_revision = "20261007_000054"
branch_labels = None
depends_on = None

attachments = importlib.import_module("migrations.versions.20261007_000054_expand_template_attachments")
previous = attachments.previous
TABLE_NAMES = ("template_publications", "template_releases", "template_subscriptions", "study_template_presets", "deck_release_template_pins")


def _tables():
    metadata = sa.MetaData()
    for name, type_ in (("users", sa.Integer), ("decks", sa.Integer), ("templates", sa.String(36)), ("template_versions", sa.String(36)), ("deck_releases", sa.String(36))):
        sa.Table(name, metadata, sa.Column("id", type_, primary_key=True))
    metadata.tables["template_versions"].append_column(sa.Column("template_id", sa.String(36), nullable=False))
    publisher = sa.Table(
        TABLE_NAMES[0], metadata,
        sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("current_release_id", sa.String(36), nullable=True),
        sa.Column("auto_publish_enabled", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("last_auto_published_at", sa.DateTime, nullable=True),
        sa.Column("last_auto_publish_error", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
    )
    release = sa.Table(
        TABLE_NAMES[1], metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("version_id", sa.String(36), sa.ForeignKey("template_versions.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sequence_no", sa.BigInteger, nullable=False),
        sa.Column("version_label", sa.String(50), nullable=False),
        sa.Column("parent_release_id", sa.String(36), sa.ForeignKey("template_releases.id", ondelete="SET NULL", name="fk_template_releases_parent"), nullable=True),
        sa.Column("publish_mode", sa.String(16), nullable=False, server_default="manual"),
        sa.Column("idempotency_key", sa.String(64), nullable=True),
        sa.Column("change_note", sa.Text, nullable=True),
        sa.Column("created_by_user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("published_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("template_id", "sequence_no", name="uq_template_releases_template_sequence"),
        sa.UniqueConstraint("template_id", "version_label", name="uq_template_releases_template_label"),
        sa.UniqueConstraint("template_id", "version_id", name="uq_template_releases_template_version"),
        sa.UniqueConstraint("template_id", "idempotency_key", name="uq_template_releases_template_idempotency"),
        sa.CheckConstraint("sequence_no > 0", name="ck_template_releases_sequence_positive"),
        sa.CheckConstraint("publish_mode IN ('manual', 'automatic')", name="ck_template_releases_publish_mode"),
        sa.Index("ix_template_releases_template_id", "template_id"),
        sa.Index("ix_template_releases_version_id", "version_id"),
    )
    subscription = sa.Table(
        TABLE_NAMES[2], metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("source_template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("local_template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
        sa.Column("applied_release_id", sa.String(36), sa.ForeignKey("template_releases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("seen_release_id", sa.String(36), sa.ForeignKey("template_releases.id", ondelete="SET NULL"), nullable=True),
        sa.Column("auto_update_enabled", sa.Boolean, nullable=False, server_default="0"),
        sa.Column("pending_update_json", sa.JSON, nullable=True),
        sa.Column("last_sync_status", sa.String(24), nullable=True),
        sa.Column("last_synced_at", sa.DateTime, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "source_template_id", name="uq_template_subscriptions_user_source"),
        sa.UniqueConstraint("local_template_id", name="uq_template_subscriptions_local_template"),
    )
    preset = sa.Table(
        TABLE_NAMES[3], metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deck_id", sa.Integer, sa.ForeignKey("decks.id", ondelete="CASCADE"), nullable=False),
        sa.Column("selected_compositions", sa.JSON, nullable=False),
        sa.Column("input_bindings", sa.JSON, nullable=False),
        sa.Column("ask_before_study", sa.Boolean, nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime, nullable=False),
        sa.Column("updated_at", sa.DateTime, nullable=False),
        sa.UniqueConstraint("user_id", "deck_id", name="uq_study_template_presets_user_deck"),
    )
    pin = sa.Table(
        TABLE_NAMES[4], metadata,
        sa.Column("deck_release_id", sa.String(36), sa.ForeignKey("deck_releases.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("source_template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="RESTRICT"), primary_key=True),
        sa.Column("template_release_id", sa.String(36), sa.ForeignKey("template_releases.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("applications_json", sa.JSON, nullable=False),
        sa.Index("ix_deck_release_template_pins_source_template_id", "source_template_id"),
        sa.Index("ix_deck_release_template_pins_template_release_id", "template_release_id"),
    )
    return publisher, release, subscription, preset, pin


def _error(table, detail):
    raise RuntimeError(f"Template distribution schema drift in {table}: {detail}; inspect before migrating.")


def _validate(bind, table):
    inspector = sa.inspect(bind)
    columns = {row["name"]: row for row in inspector.get_columns(table.name)}
    if set(columns) != set(table.c.keys()):
        _error(table.name, "column set differs")
    for expected in table.c:
        attachments._column(bind, table.name, columns[expected.name], expected)
    if inspector.get_pk_constraint(table.name).get("constrained_columns") != [column.name for column in table.primary_key]:
        _error(table.name, "primary key differs")
    fks = {(tuple(fk.column_keys), fk.referred_table.name, tuple(element.column.name for element in fk.elements), fk.ondelete) for fk in table.foreign_key_constraints}
    if previous._fks(inspector, table.name) != fks:
        _error(table.name, "foreign keys/delete behavior differ")
    unique = {(row["name"], tuple(row["column_names"])) for row in inspector.get_unique_constraints(table.name)}
    expected_unique = {(constraint.name, tuple(column.name for column in constraint.columns)) for constraint in table.constraints if isinstance(constraint, sa.UniqueConstraint)}
    if unique != expected_unique:
        _error(table.name, "unique constraints differ")
    checks = {row["name"]: attachments._check_sql(row["sqltext"]) for row in inspector.get_check_constraints(table.name)}
    expected_checks = {constraint.name: attachments._check_sql(constraint.sqltext) for constraint in table.constraints if isinstance(constraint, sa.CheckConstraint)}
    if checks != expected_checks:
        _error(table.name, "CHECK constraints differ")
    expected_indexes = {(index.name, tuple(column.name for column in index.columns), bool(index.unique)) for index in table.indexes}
    indexes = {(row["name"], tuple(row["column_names"]), bool(row["unique"])) for row in inspector.get_indexes(table.name) if not (bool(row["unique"]) and (row["name"], tuple(row["column_names"])) in unique)}
    if bind.dialect.name == "mysql":
        indexes = {row for row in indexes if row in expected_indexes or not (not row[2] and row[1] in {fk[0] for fk in fks})}
        if str(inspector.get_table_options(table.name).get("mysql_engine", "")).lower() != "innodb":
            _error(table.name, "engine must be InnoDB")
    if indexes != expected_indexes:
        _error(table.name, "indexes differ")


def _preflight(bind, tables):
    inspector = sa.inspect(bind)
    present = set(inspector.get_table_names())
    for table in tables:
        if table.name in present:
            _validate(bind, table)
    for name, type_ in (("users", sa.Integer()), ("decks", sa.Integer()), ("templates", sa.String(36)), ("template_versions", sa.String(36)), ("deck_releases", sa.String(36))):
        if name not in present:
            _error(name, "required parent is absent")
        primary = next((row for row in inspector.get_columns(name) if row["name"] == "id"), None)
        if primary is None or primary["nullable"] or previous._type_sql(primary["type"], bind.dialect) != previous._type_sql(type_, bind.dialect) or inspector.get_pk_constraint(name).get("constrained_columns") != ["id"]:
            _error(name, "parent primary key differs")
        if bind.dialect.name == "mysql" and str(inspector.get_table_options(name).get("mysql_engine", "")).lower() != "innodb":
            _error(name, "parent engine must be InnoDB")
    column = next((row for row in inspector.get_columns("deck_releases") if row["name"] == "template_pins_initialized"), None)
    if column is not None:
        attachments._column(bind, "deck_releases", column, sa.Column("template_pins_initialized", sa.Boolean, nullable=False, server_default="0"))
    if bind.dialect.name == "mysql":
        expected = bind.execute(sa.text("SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME = DATABASE()")).one()
        for name in ("templates", "template_versions", "deck_releases"):
            actual = bind.execute(sa.text("SELECT CHARACTER_SET_NAME, COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = :name AND COLUMN_NAME = 'id'"), {"name": name}).one()
            if tuple(actual) != tuple(expected):
                _error(name, "ID collation differs from inherited distribution FK DDL")
    _validate_pointers(bind, tables, present)
    return present, column


def _validate_pointers(bind, tables, present):
    publisher, release, subscription, _, pin = tables
    version_columns = {row["name"]: row for row in sa.inspect(bind).get_columns("template_versions")}
    if "template_id" not in version_columns:
        _error("template_versions", "required source identity column is absent")
    attachments._column(bind, "template_versions", version_columns["template_id"], release.metadata.tables["template_versions"].c.template_id)
    if release.name in present:
        version = release.metadata.tables["template_versions"]
        wrong = bind.execute(sa.select(release.c.id).select_from(release.outerjoin(version, release.c.version_id == version.c.id)).where(sa.or_(version.c.id.is_(None), version.c.template_id != release.c.template_id)).limit(1)).first()
        if wrong:
            _error(release.name, "published version does not belong to its source template")
    if publisher.name in present:
        pointers = publisher.c.current_release_id.is_not(None)
        if release.name not in present:
            wrong = bind.execute(sa.select(publisher.c.template_id).where(pointers).limit(1)).first()
        else:
            wrong = bind.execute(sa.select(publisher.c.template_id).select_from(publisher.outerjoin(release, publisher.c.current_release_id == release.c.id)).where(pointers, sa.or_(release.c.id.is_(None), release.c.template_id != publisher.c.template_id)).limit(1)).first()
        if wrong:
            _error(publisher.name, "current publication pointer is missing or belongs to another template")
    if subscription.name in present:
        for key in ("applied_release_id", "seen_release_id"):
            if release.name not in present:
                wrong = bind.execute(sa.select(subscription.c.id).where(subscription.c[key].is_not(None)).limit(1)).first()
            else:
                wrong = bind.execute(sa.select(subscription.c.id).select_from(subscription.outerjoin(release, subscription.c[key] == release.c.id)).where(subscription.c[key].is_not(None), sa.or_(release.c.id.is_(None), release.c.template_id != subscription.c.source_template_id)).limit(1)).first()
            if wrong:
                _error(subscription.name, f"{key} does not belong to its subscribed source")
    if pin.name in present:
        if release.name not in present:
            wrong = bind.execute(sa.select(pin.c.deck_release_id).limit(1)).first()
        else:
            wrong = bind.execute(sa.select(pin.c.deck_release_id).select_from(pin.outerjoin(release, pin.c.template_release_id == release.c.id)).where(sa.or_(release.c.id.is_(None), release.c.template_id != pin.c.source_template_id)).limit(1)).first()
        if wrong:
            _error(pin.name, "frozen release pin does not belong to its source template")


def upgrade():
    bind = op.get_bind()
    tables = _tables()
    present, initialized_column = _preflight(bind, tables)
    if initialized_column is None:
        op.add_column("deck_releases", sa.Column("template_pins_initialized", sa.Boolean, nullable=False, server_default="0"))
    for table in tables:
        if table.name not in present:
            table.create(bind)


def downgrade():
    bind = op.get_bind()
    tables = _tables()
    present, initialized_column = _preflight(bind, tables)
    for table in tables:
        if table.name in present and bind.execute(sa.select(sa.func.count()).select_from(table)).scalar_one():
            raise RuntimeError("Template distribution downgrade refuses published/subscriber/preset history; retain additive tables during application rollback.")
    if initialized_column is not None and bind.execute(sa.text("SELECT COUNT(*) FROM deck_releases WHERE template_pins_initialized <> 0")).scalar_one():
        raise RuntimeError("Template distribution downgrade refuses initialized release pins; an empty pinned release still carries presentation state.")
    for table in reversed(tables):
        if table.name in present:
            table.drop(bind)
    if initialized_column is not None:
        op.drop_column("deck_releases", "template_pins_initialized")
