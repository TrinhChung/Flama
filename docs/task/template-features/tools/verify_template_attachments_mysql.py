"""Rehearse revisions 53 -> 54 -> 55 in generated disposable MySQL schemas.

Configured application rows are never read or written. Only database collation
metadata is read; every write and cleanup target is a validated generated name.
"""

from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[4]
sys.path.insert(0, str(ROOT))

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

attachment = importlib.import_module("migrations.versions.20261007_000054_expand_template_attachments")
distribution = importlib.import_module("migrations.versions.20261007_000055_add_template_distribution")
PROBE_NAME = re.compile(r"^flama_attach_probe_[0-9a-f]{32}_(?:legacy|orm)$")
NOW = datetime(2026, 10, 7, 10, 11, 12)
FRONT = "\r\n {{単語}} — café &amp; 漢字 \n"


def require(value, message):
    if not value:
        raise AssertionError(message)


def reflect(connection, name):
    return sa.Table(name, sa.MetaData(), autoload_with=connection)


def bind_operations(connection):
    op._proxy = Operations(MigrationContext.configure(connection))


def legacy(uri):
    engine = sa.create_engine(uri, pool_pre_ping=True)
    try:
        require(bool(PROBE_NAME.fullmatch(engine.url.database or "")), "Unsafe legacy schema")
        users, nts, templates, versions = attachment.previous._tables()
        latest_templates, latest_apps, fields = attachment._tables()
        metadata = sa.MetaData()
        for table in (users, nts, templates, versions, fields):
            table.to_metadata(metadata)
        apps = sa.Table(
            "study_applications", metadata,
            *(column._copy() for column in latest_apps.c if column.name not in attachment.APPLICATION_COLUMNS),
            sa.ForeignKeyConstraint(["note_type_id"], ["note_types.id"], ondelete="CASCADE"),
            sa.ForeignKeyConstraint(["template_id"], ["templates.id"], ondelete="CASCADE"),
            sa.UniqueConstraint("template_id", "occurrence_key", name=attachment.OLD_UNIQUE),
            sa.CheckConstraint("status_code IN ('ACTIVE')", name="ck_study_applications_status"),
            sa.Index("ix_study_applications_note_type_ord", "note_type_id", "source_ord"),
        )
        cards = sa.Table("cards", metadata, sa.Column("id", sa.String(36), primary_key=True), sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False), sa.Column("application_id", sa.String(36), sa.ForeignKey("study_applications.id", ondelete="CASCADE"), nullable=False))
        progress = sa.Table("probe_progress", metadata, sa.Column("card_id", sa.String(36), sa.ForeignKey("cards.id", ondelete="CASCADE"), primary_key=True), sa.Column("revision", sa.Integer, nullable=False))
        sa.Table("decks", metadata, sa.Column("id", sa.Integer, primary_key=True))
        sa.Table("deck_releases", metadata, sa.Column("id", sa.String(36), primary_key=True))
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(metadata.tables["users"].insert(), [{"id": 1}, {"id": 2}])
            connection.execute(metadata.tables["note_types"].insert(), [{"id": "nt-1", "user_id": 1}, {"id": "nt-2", "user_id": 2}])
            connection.execute(metadata.tables["field_defs"].insert().values(id="field-word", note_type_id="nt-1", name="単語", position=0))
            connection.execute(metadata.tables["templates"].insert().values(id="template-probe", note_type_id="nt-1", name="Original", front_html=FRONT, back_html="{{単語}}", shared_css="\r\n.card {}", position=4, is_default=True, created_at=NOW, updated_at=NOW))
            connection.execute(apps.insert().values(id="application-probe", note_type_id="nt-1", template_id="template-probe", occurrence_key="compat", source_ord=4, status_code="ACTIVE", created_at=NOW, updated_at=NOW))
            connection.execute(cards.insert().values(id="card-probe", template_id="template-probe", application_id="application-probe"))
            connection.execute(progress.insert().values(card_id="card-probe", revision=37))
            connection.execute(metadata.tables["decks"].insert().values(id=1))
            connection.execute(metadata.tables["deck_releases"].insert().values(id="historical-deck-release"))
            bind_operations(connection)
            attachment.previous.upgrade()
        with engine.begin() as connection:
            bind_operations(connection)
            source_before = dict(connection.execute(sa.select(reflect(connection, "templates"))).mappings().one())
            version_before = dict(connection.execute(sa.select(reflect(connection, "template_versions"))).mappings().one())
            attachment.upgrade()
            attachment.upgrade()
            source = connection.execute(sa.select(reflect(connection, "templates"))).mappings().one()
            app = connection.execute(sa.select(reflect(connection, "study_applications"))).mappings().one()
            require(all(source[key] == value for key, value in source_before.items()), "Template source/identity/timestamps changed")
            require(dict(connection.execute(sa.select(reflect(connection, "template_versions"))).mappings().one()) == version_before, "Version history changed")
            require(app["id"] == "application-probe" and app["input_bindings"] == {"単語": "field-word"}, "Stable attachment binding differs")
            require(app["position"] == app["source_ord"] == 4 and app["is_default"] and app["updated_at"] == NOW, "Attachment metadata/timestamps changed")
            require(connection.execute(sa.select(reflect(connection, "probe_progress").c.revision)).scalar_one() == 37, "Progress changed")
            require(connection.execute(sa.text("SELECT id FROM cards")).scalar_one() == "card-probe", "Card identity changed")
            new_apps = reflect(connection, "study_applications")
            connection.execute(new_apps.insert().values(id="second-attachment", note_type_id="nt-2", template_id="template-probe", occurrence_key="compat", source_ord=None, status_code="RETIRED", created_at=NOW, updated_at=NOW))
            distribution.upgrade()
            distribution.upgrade()
            require(not bool(connection.execute(sa.select(reflect(connection, "deck_releases").c.template_pins_initialized)).scalar_one()), "Historical release received inferred pins")
            distribution.downgrade()
            distribution.upgrade()
            releases = reflect(connection, "template_releases")
            connection.execute(releases.insert().values(id="published-probe", template_id="template-probe", version_id=version_before["id"], sequence_no=1, version_label="1", created_by_user_id=1, published_at=NOW))
            require(connection.execute(sa.select(releases.c.publish_mode)).scalar_one() == "manual", "Publish mode default differs")
            try:
                distribution.downgrade()
            except RuntimeError as exc:
                require("downgrade refuses" in str(exc), "Wrong distribution downgrade guard")
            else:
                raise AssertionError("Published release was dropped")
            require(connection.execute(sa.select(releases.c.id)).scalar_one() == "published-probe", "Published history changed")
        return {"legacy_53_54_55": True, "exact_id_source_history_progress": True, "stable_bindings_and_scoped_occurrences": True, "historical_release_fallback": True, "distribution_empty_downgrade_reupgrade": True, "published_history_guard": True}
    finally:
        engine.dispose()


def orm(uri):
    from app import create_app
    from models import db
    from models.template_publication import TemplatePublication  # noqa: F401
    from models.template_release import TemplateRelease  # noqa: F401
    from models.template_subscription import TemplateSubscription  # noqa: F401
    from models.study_template_preset import StudyTemplatePreset  # noqa: F401
    from models.deck_release_template_pin import DeckReleaseTemplatePin  # noqa: F401
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri}, audit_mode=True)
    try:
        with app.app_context():
            require(set(db.engines) == {None} and db.engine.url.database == sa.engine.make_url(uri).database and bool(PROBE_NAME.fullmatch(db.engine.url.database or "")), "Unsafe ORM engine")
            db.create_all()
            with db.engine.begin() as connection:
                bind_operations(connection)
                attachment.upgrade()
                attachment.upgrade()
                distribution.upgrade()
                distribution.upgrade()
            return {"actual_create_all_54_55_parity": True}
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def main():
    load_dotenv(ROOT / ".env", override=False)
    nonce = uuid4().hex
    names = [f"flama_attach_probe_{nonce}_{kind}" for kind in ("legacy", "orm")]
    created = []
    admin = None
    report = {"ok": False, "cleanup_verified": False}
    original_op = getattr(op, "_proxy", None)
    try:
        settings = _connection_settings()
        admin = pymysql.connect(**settings, connect_timeout=5, read_timeout=30, write_timeout=30)
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
            for name in names:
                require(bool(PROBE_NAME.fullmatch(name)) and name != os.getenv("DB_NAME"), "Unsafe generated schema")
                cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
                created.append(name)
        report.update(legacy(_database_uri(settings, names[0])))
        report.update(orm(_database_uri(settings, names[1])))
        report["ok"] = True
    except Exception as exc:
        report["error_type"] = type(exc).__name__
        original = getattr(exc, "orig", exc)
        if getattr(original, "args", ()) and isinstance(original.args[0], int):
            report["mysql_error_code"] = original.args[0]
        if isinstance(exc, AssertionError):
            report["assertion"] = str(exc)
        elif isinstance(exc, RuntimeError) and str(exc).startswith(("Template attachment schema/data drift", "Template distribution schema drift", "Template version schema/data drift")):
            report["migration_drift"] = str(exc)
        elif isinstance(exc, sa.exc.CompileError):
            report["ddl_compile_error"] = str(exc)
    finally:
        op._proxy = original_op
        if admin is not None:
            try:
                with admin.cursor() as cursor:
                    for name in reversed(created):
                        require(name in names and bool(PROBE_NAME.fullmatch(name)) and name != os.getenv("DB_NAME"), "Unsafe cleanup target")
                        cursor.execute(f"DROP DATABASE `{name}`")
                    cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME IN (%s,%s)", tuple(names))
                    report["cleanup_verified"] = cursor.fetchone()[0] == 0
            except Exception as exc:
                report["cleanup_error_type"] = type(exc).__name__
            finally:
                admin.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] and report["cleanup_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
