"""Rehearse template version expansion only in generated disposable MySQL DBs.

Run from the repository root:
    python scripts/tools/verify_template_versions_mysql.py
Add --runtime to verify two ORM editors under MySQL REPEATABLE READ.
Configured application rows are never read or written; only the configured
database's default collation is read from information_schema.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import sys
from threading import Barrier
from uuid import uuid4


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from sqlalchemy.orm import Session

from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation


migration = importlib.import_module("migrations.versions.20261007_000053_add_template_versions")
attachment = importlib.import_module("migrations.versions.20261007_000054_expand_template_attachments")
distribution = importlib.import_module("migrations.versions.20261007_000055_add_template_distribution")
PROBE_NAME = re.compile(r"^flama_template_probe_[0-9a-f]{32}_(?:legacy|orm)$")
NOW = datetime(2026, 10, 7, 4, 5, 6)
FRONT = "\r\n  {{単語}}\n<div>café &amp; 漢字</div>  "
BACK = "{{FrontSide}}\r\n{{意味}}"
CSS = "\n.card { color: #123; }\n"


def _require(condition, message):
    if not condition:
        raise AssertionError(message)


def _bind(connection):
    op._proxy = Operations(MigrationContext.configure(connection))


def _reflect(connection, name):
    return sa.Table(name, sa.MetaData(), autoload_with=connection)


def _assert_initial(connection, template_id, card_id, *, schema=None, legacy=True):
    templates = _reflect(connection, "templates")
    versions = _reflect(connection, "template_versions")
    template = connection.execute(sa.select(templates).where(templates.c.id == template_id)).mappings().one()
    version = connection.execute(sa.select(versions).where(versions.c.template_id == template_id)).mappings().one()
    _require(template["id"] == template_id, "Template ID changed")
    _require(template["owner_user_id"] == 1, "Owner backfill differs")
    _require(template["note_type_id"] == "note-type-probe", "NoteType attachment changed")
    _require(template["current_version_id"] == version["id"], "Initial pointer differs")
    if legacy:
        _require(version["id"] == migration._initial_version_id(template_id), "Migration initial identity differs")
    _require(template["updated_at"] == template["created_at"] == NOW, "Source timestamp changed")
    _require(version["version_no"] == 1 and version["origin"] == "backfill", "Initial version differs")
    _require(version["input_schema"] == (schema or []), "Initial input schema differs")
    for key, value in (("front_html", FRONT), ("back_html", BACK), ("shared_css", CSS)):
        _require(template[key] == version[key] == value, "Source bytes differ")
    _require(version["content_hash"] == migration._content_hash(FRONT, BACK, CSS), "Content hash differs")
    _require(connection.execute(sa.text("SELECT id FROM cards WHERE template_id = :template"), {"template": template_id}).scalar_one() == card_id, "Card identity changed")
    nullable = next(column for column in sa.inspect(connection).get_columns("templates") if column["name"] == "note_type_id")["nullable"]
    _require(bool(nullable) == (not legacy), "Origin NoteType nullability differs from the rehearsed schema")
    _require(not any(fk["constrained_columns"] == ["current_version_id"] for fk in sa.inspect(connection).get_foreign_keys("templates")), "Version pointer acquired FK")


def _legacy_probe(uri):
    engine = sa.create_engine(uri, pool_pre_ping=True)
    try:
        _require(bool(PROBE_NAME.fullmatch(engine.url.database or "")), "Legacy engine is outside generated schemas")
        users, note_types, expected, _ = migration._tables()
        metadata = sa.MetaData()
        users = users.to_metadata(metadata)
        note_types = note_types.to_metadata(metadata)
        templates = sa.Table(
            "templates", metadata,
            *(column._copy() for column in expected.c if column.name not in migration.ADDED_COLUMNS),
            sa.ForeignKeyConstraint(["note_type_id"], ["note_types.id"], ondelete="CASCADE"),
            sa.Index("ix_templates_note_type_id", "note_type_id"),
        )
        cards = sa.Table(
            "cards", metadata,
            sa.Column("id", sa.String(36), primary_key=True),
            sa.Column("template_id", sa.String(36), sa.ForeignKey("templates.id", ondelete="CASCADE"), nullable=False),
        )
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(users.insert().values(id=1))
            connection.execute(note_types.insert().values(id="note-type-probe", user_id=1))
            connection.execute(templates.insert().values(
                id="template-probe", note_type_id="note-type-probe", name="Original",
                front_html=FRONT, back_html=BACK, shared_css=CSS, position=4,
                is_default=True, created_at=NOW, updated_at=NOW,
            ))
            connection.execute(cards.insert().values(id="card-probe", template_id="template-probe"))
        with engine.begin() as connection:
            _bind(connection)
            migration.upgrade()
            migration.upgrade()
            _assert_initial(connection, "template-probe", "card-probe")
            migration.downgrade()
            _require(not sa.inspect(connection).has_table("template_versions"), "Downgrade retained rehearsal history")
            source = connection.execute(sa.select(_reflect(connection, "templates"))).mappings().one()
            _require(source["front_html"] == FRONT and source["updated_at"] == NOW, "Downgrade changed sources")
            _require(connection.execute(sa.text("SELECT id FROM cards")).scalar_one() == "card-probe", "Downgrade changed cards")
            migration.upgrade()
            _assert_initial(connection, "template-probe", "card-probe")
            versions = _reflect(connection, "template_versions")
            initial = dict(connection.execute(sa.select(versions)).mappings().one())
            initial.update(id="version-probe-2", version_no=2, origin="edit")
            connection.execute(versions.insert().values(**initial))
            connection.execute(sa.text("UPDATE templates SET current_version_id = 'version-probe-2'"))
            try:
                migration.downgrade()
            except RuntimeError as exc:
                _require("refuses version history" in str(exc), "Wrong downgrade refusal")
            else:
                raise AssertionError("Downgrade discarded populated history")
            _require(connection.execute(sa.select(sa.func.count()).select_from(versions)).scalar_one() == 2, "History guard changed rows")
        return {"legacy_upgrade_idempotent": True, "exact_sources_and_ids": True, "downgrade_reupgrade": True, "history_guard": True}
    finally:
        engine.dispose()


def _orm_probe(uri, *, runtime):
    from app import create_app
    from models import db
    from models.card import Card
    from models.deck import Deck
    from models.note import Note
    from models.note_type import NoteType
    from models.template import Template
    from models.template_version import TemplateVersion
    from models.user import User
    from app.services.template_version_service import backfill_versions

    # Explicit generated URI, audit boot: no maintenance, cutover or seed writes.
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": uri}, audit_mode=True)
    try:
        with app.app_context():
            _require(set(db.engines) == {None} and db.engine.url.database == sa.engine.make_url(uri).database, "ORM engine is outside generated schemas")
            _require(bool(PROBE_NAME.fullmatch(db.engine.url.database or "")), "Unsafe ORM schema target")
            db.create_all()
            user_table, nt_table = User.__table__, NoteType.__table__
            deck_table, note_table, card_table = Deck.__table__, Note.__table__, Card.__table__
            schema = [{"key": "単語", "type": "text", "label": "Word", "required": True}]
            with db.engine.begin() as connection:
                # Core inserts exercise migration against create_all without
                # invoking the runtime history listener during fixture setup.
                connection.execute(user_table.insert().values(id=1, username="probe-user", email="probe@example.test"))
                connection.execute(nt_table.insert().values(id="note-type-probe", user_id=1, name="Probe NoteType"))
                connection.execute(deck_table.insert().values(id=1, owner_user_id=1, name="Probe Deck"))
                connection.execute(note_table.insert().values(id="note-probe", user_id=1, note_type_id="note-type-probe", deck_id=1))
                connection.execute(Template.__table__.insert().values(
                    id="template-probe", note_type_id="note-type-probe", name="Original",
                    front_html=FRONT, back_html=BACK, shared_css=CSS, input_schema=schema,
                    position=4, is_default=True, created_at=NOW, updated_at=NOW,
                ))
                connection.execute(card_table.insert().values(id="card-probe", note_id="note-probe", template_id="template-probe"))
                _bind(connection)
                # The historical 52->53 contract is rehearsed separately in
                # _legacy_probe. Current models already contain 54/55, so
                # validate the current schema instead of applying revision 53
                # backwards to its now-nullable origin NoteType column.
                attachment.upgrade()
                attachment.upgrade()
                distribution.upgrade()
                distribution.upgrade()
            _require(backfill_versions() == 1, "Current ORM initial backfill differs")
            _require(backfill_versions() == 0, "Current ORM backfill is not idempotent")
            db.session.commit()
            with db.engine.connect() as connection:
                _assert_initial(connection, "template-probe", "card-probe", schema=schema, legacy=False)
            result = {"actual_create_all_parity": True, "actual_create_all_54_55_parity": True, "current_orm_backfill_idempotent": True}
            if runtime:
                with Session(db.engine) as first, Session(db.engine) as second:
                    # First nonlocking read establishes an old RR snapshot.
                    first.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                    stale = first.get(Template, "template-probe")
                    second_template = second.get(Template, "template-probe")
                    second_template.front_html = "new front from session B"
                    second.commit()
                    stale.back_html = "new back from session A"
                    first.commit()
                with db.engine.connect() as connection:
                    versions = connection.execute(sa.select(TemplateVersion.__table__).where(
                        TemplateVersion.template_id == "template-probe",
                    ).order_by(TemplateVersion.version_no)).mappings().all()
                    head = connection.execute(sa.select(Template.__table__).where(Template.id == "template-probe")).mappings().one()
                    _require([version["version_no"] for version in versions] == [1, 2, 3], "RR sequence did not reach version 3")
                    _require(head["current_version_id"] == versions[-1]["id"], "RR history pointer differs")
                    _require(head["front_html"] == versions[-1]["front_html"] == "new front from session B", "RR lost session B edit")
                    _require(head["back_html"] == versions[-1]["back_html"] == "new back from session A", "RR lost session A edit")
                result["repeatable_read_stale_editor_version_3"] = True
                result["parallel_initial_versions"] = _parallel_initial_probe(db.engine, Template, TemplateVersion)
            return result
    finally:
        with app.app_context():
            db.session.remove()
            db.engine.dispose()


def _parallel_initial_probe(engine, template_model, version_model):
    before_insert = Barrier(2, timeout=15)

    class CoordinatedSession(Session):
        def execute(self, statement, *args, **kwargs):
            if isinstance(statement, sa.sql.dml.Insert) and statement.table.name == "template_versions":
                # Both writers finish history reads before either version
                # insertion. Any unnecessary empty-range gap locks now expose
                # the initial-version deadlock deterministically.
                before_insert.wait()
            return super().execute(statement, *args, **kwargs)

    def write_new(suffix):
        try:
            with CoordinatedSession(engine) as session:
                session.execute(sa.text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ"))
                session.add(template_model(
                    id=f"parallel-template-{suffix}", note_type_id="note-type-probe",
                    name=f"Parallel {suffix}", front_html=f"front {suffix}", back_html=f"back {suffix}",
                ))
                session.commit()
            return None
        except Exception as exc:
            original = getattr(exc, "orig", exc)
            code = original.args[0] if getattr(original, "args", ()) and isinstance(original.args[0], int) else None
            return {"error_type": type(exc).__name__, "mysql_error_code": code}

    with ThreadPoolExecutor(max_workers=2) as workers:
        outcomes = list(workers.map(write_new, ("a", "b")))
    _require(all(outcome is None for outcome in outcomes), f"Parallel initial versions failed: {outcomes}")
    with engine.connect() as connection:
        rows = connection.execute(sa.select(version_model.template_id, version_model.version_no).where(
            version_model.template_id.in_(["parallel-template-a", "parallel-template-b"]),
        ).order_by(version_model.template_id)).all()
        _require(rows == [("parallel-template-a", 1), ("parallel-template-b", 1)], "Parallel initial sequences differ")
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runtime", action="store_true")
    args = parser.parse_args()
    load_dotenv(ROOT / ".env", override=False)
    probe_token = uuid4().hex
    names = [f"flama_template_probe_{probe_token}_{stage}" for stage in ("legacy", "orm")]
    admin = None
    created = []
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
                _require(bool(PROBE_NAME.fullmatch(name)) and name != os.getenv("DB_NAME"), "Unsafe generated probe name")
                cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
                created.append(name)
        report.update(_legacy_probe(_database_uri(settings, names[0])))
        report.update(_orm_probe(_database_uri(settings, names[1]), runtime=args.runtime))
        report["ok"] = True
    except Exception as exc:
        # Exception text can contain connection settings or SQL; report only
        # class and DB error number, never credentials or arbitrary SQL.
        report["error_type"] = type(exc).__name__
        original = getattr(exc, "orig", exc)
        if getattr(original, "args", ()) and isinstance(original.args[0], int):
            report["mysql_error_code"] = original.args[0]
        if isinstance(exc, AssertionError):
            report["assertion"] = str(exc)
        elif isinstance(exc, RuntimeError) and str(exc).startswith("Template version schema/data drift in "):
            report["migration_drift"] = str(exc)
        elif isinstance(exc, sa.exc.CompileError):
            report["ddl_compile_error"] = str(exc)
    finally:
        op._proxy = original_op
        if admin is not None:
            try:
                with admin.cursor() as cursor:
                    for name in reversed(created):
                        _require(name in names and bool(PROBE_NAME.fullmatch(name)) and name != os.getenv("DB_NAME"), "Unsafe cleanup target")
                        cursor.execute(f"DROP DATABASE `{name}`")
                    cursor.execute(
                        "SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME IN (%s, %s)",
                        tuple(names),
                    )
                    report["cleanup_verified"] = cursor.fetchone()[0] == 0
            except Exception as exc:
                report["cleanup_error_type"] = type(exc).__name__
            finally:
                admin.close()
    print(json.dumps(report, sort_keys=True))
    return 0 if report["ok"] and report["cleanup_verified"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
