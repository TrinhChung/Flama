"""Rehearse Phase 6 migration 46 (application occurrences) on disposable MySQL.

Builds the head-45 schema in a generated database, seeds owned and Anki-like
content with review events and Connect card refs, then checks: upgrade and
backfill (review events via the batched CLI backfill), contract, idempotent
re-run, guarded downgrade, empty downgrade and re-upgrade, and a flags-off
``wsgi.py`` boot. Only the generated database is
created and dropped; the configured application database is untouched.
"""

from __future__ import annotations

from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys

from dotenv import load_dotenv
from flask_migrate import downgrade, stamp, upgrade
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.services.study_note_attribution_service import backfill_phase6_attribution
from models import db
from scripts.mysql_probe_db import (
    _connection_settings, _database_uri, _source_database_collation,
)

PROBE_NAME_PATTERN = re.compile(r"^flama_p6_schema_probe_[0-9]+_[a-f0-9]{8}$")
migration = importlib.import_module("migrations.versions.20260930_000046_add_study_applications")


def _probe_app(uri: str):
    url = sa.engine.make_url(uri)
    if (
        url.get_backend_name() != "mysql"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not PROBE_NAME_PATTERN.fullmatch(url.database or "")
    ):
        raise ValueError("P6 schema probe requires a generated local MySQL database.")
    return create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False, "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
    })


def _exec(sql: str, **params):
    return db.session.execute(sa.text(sql), params)


def _reconstruct_head_45() -> None:
    """Create the current metadata, then remove every migration-46 artifact."""

    db.metadata.create_all(bind=db.engine)
    inspector = sa.inspect(db.engine)
    for fk in inspector.get_foreign_keys("cards"):
        if fk.get("referred_table") == migration.APPLICATIONS:
            _exec(f"ALTER TABLE cards DROP FOREIGN KEY `{fk['name']}`")
    _exec(f"ALTER TABLE cards DROP INDEX `{migration.CARD_APPLICATION_UNIQUE}`")
    _exec(f"ALTER TABLE cards DROP INDEX `{migration.CARD_APPLICATION_INDEX}`")
    _exec("ALTER TABLE cards DROP COLUMN application_id")
    _exec(f"ALTER TABLE cards ADD CONSTRAINT `{migration.NOTE_TEMPLATE_UNIQUE}` UNIQUE (note_id, template_id)")
    _exec(f"ALTER TABLE review_events DROP INDEX `{migration.EVENT_NOTE_INDEX}`")
    _exec("ALTER TABLE review_events DROP COLUMN note_id")
    _exec(f"ALTER TABLE connect_source_card_refs DROP INDEX `{migration.REF_NOTE_INDEX}`")
    _exec("ALTER TABLE connect_source_card_refs DROP COLUMN note_id")
    ref_fk = migration._ref_card_fk(db.engine)
    _exec(f"ALTER TABLE connect_source_card_refs DROP FOREIGN KEY `{ref_fk['name']}`")
    _exec("ALTER TABLE connect_source_card_refs MODIFY card_id VARCHAR(36) NOT NULL")
    _exec("ALTER TABLE connect_source_card_refs ADD CONSTRAINT connect_source_card_refs_ibfk_card "
          "FOREIGN KEY (card_id) REFERENCES cards (id) ON DELETE CASCADE")
    _exec(f"DROP TABLE {migration.APPLICATIONS}")
    db.session.commit()


def _seed() -> dict:
    from models.deck import Deck
    from models.note import Note
    from models.note_type import NoteType
    from models.template import Template
    from models.user import User

    now = datetime(2026, 9, 30, 12, 0, 0)
    user = User(id=1, username="p6", email="p6@example.test")
    db.session.add(user)
    db.session.flush()
    db.session.add(Deck(id=1, name="P6", owner_user_id=1))
    db.session.add(NoteType(id="nt-1", name="Two templates", user_id=1))
    db.session.flush()
    # Raw SQL: the ORM seam would create occurrences, which head 45 lacks.
    for position, template_id in enumerate(("t-front", "t-back")):
        _exec("INSERT INTO templates (id, note_type_id, name, front_html, back_html, shared_css, "
              "position, is_default, created_at, updated_at) VALUES (:id, 'nt-1', :id, '', '', '', "
              ":position, :is_default, :now, :now)",
              id=template_id, position=position, is_default=position == 0, now=now)
    for note_index in range(3):
        db.session.add(Note(id=f"note-{note_index}", user_id=1, note_type_id="nt-1", deck_id=1,
                            field_values={}))
    db.session.flush()
    for note_index in range(3):
        note_id = f"note-{note_index}"
        for template_id in ("t-front", "t-back"):
            _exec("INSERT INTO cards (id, note_id, template_id, created_at, updated_at) "
                  "VALUES (:id, :note, :template, :now, :now)",
                  id=f"{note_id}-{template_id}", note=note_id, template=template_id, now=now)
    for index, card_id in enumerate(("note-0-t-front", "note-1-t-back", "deleted-card")):
        _exec("INSERT INTO review_events (user_id, card_id, reviewed_at, rating, mode, scheduler_mode, "
              "review_kind, leeched_after, suspended_after, payload_json, created_at) "
              "VALUES (1, :card, :now, 'good', 'review', 'legacy', 'review', 0, 0, '{}', :now)",
              card=card_id, now=now)
    _exec("INSERT INTO connect_source_card_refs (id, user_id, source_key, external_card_id, "
          "external_note_id, source_ord, card_id, created_at, updated_at) VALUES "
          "('ref-1', 1, 'src', 'ext-c', 'ext-n', 1, 'note-2-t-back', :now, :now)", now=now)
    db.session.commit()
    return {"templates": 2, "cards": 6, "events": 3}


def _check_upgraded() -> dict:
    apps = _exec("SELECT template_id, occurrence_key, source_ord, status_code FROM study_applications "
                 "ORDER BY template_id").all()
    expected_apps = [("t-back", "compat", 1, "ACTIVE"), ("t-front", "compat", 0, "ACTIVE")]
    if [tuple(row) for row in apps] != expected_apps:
        raise AssertionError(f"Unexpected compatibility occurrences: {apps}")
    bad_cards = _exec("SELECT COUNT(*) FROM cards c JOIN study_applications a ON a.id = c.application_id "
                      "WHERE a.template_id <> c.template_id").scalar_one()
    unmapped = _exec("SELECT COUNT(*) FROM cards WHERE application_id IS NULL").scalar_one()
    # Migration 46 leaves old events alone; the batched CLI backfill stamps them.
    if _exec("SELECT COUNT(*) FROM review_events WHERE note_id IS NOT NULL").scalar_one():
        raise AssertionError("Migration 46 rewrote review_events; it must stay an online column add.")
    backfill = backfill_phase6_attribution(apply=True, batch_size=1)
    if (backfill.attributed_events, backfill.unresolved_events, backfill.batches) != (2, 1, 3):
        raise AssertionError(f"Unexpected ReviewEvent Note backfill: {backfill.to_dict()}")
    events = dict(_exec("SELECT card_id, note_id FROM review_events").all())
    ref_note = _exec("SELECT note_id FROM connect_source_card_refs WHERE id = 'ref-1'").scalar_one()
    if bad_cards or unmapped:
        raise AssertionError("Cards were not mapped 1:1 to their Template occurrence.")
    if events != {"note-0-t-front": "note-0", "note-1-t-back": "note-1", "deleted-card": None}:
        raise AssertionError(f"Unexpected ReviewEvent Note snapshots: {events}")
    if ref_note != "note-2":
        raise AssertionError("Connect card ref Note snapshot was not backfilled.")
    card_ids = _exec("SELECT COUNT(*) FROM cards WHERE id LIKE 'note-%'").scalar_one()
    if card_ids != 6:
        raise AssertionError("Card identities changed during the migration.")
    if migration.NOTE_TEMPLATE_UNIQUE in migration._index_names(sa.inspect(db.engine), "cards"):
        raise AssertionError("(note_id, template_id) is still unique; repeated applications are blocked.")
    return {"applications": len(apps), "cards_mapped": 6, "events_attributed": 2, "events_unresolved": 1}


def run_probe() -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p6_schema_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("P6 schema probe requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"schema_version": "p6-application-schema-mysql.v1", "configured_database_modified": False}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        uri = _database_uri(settings, name)
        app = _probe_app(uri)
        with app.app_context():
            _reconstruct_head_45()
            report["seed"] = _seed()
            stamp(revision="20260925_000045", directory="migrations")
            # Only migration 46 is under test; later revisions have their own probes.
            upgrade(directory="migrations", revision=migration.revision)
            head = _exec("SELECT version_num FROM alembic_version").scalar_one()
            if head != migration.revision:
                raise AssertionError(f"Unexpected head: {head}")
            report["upgrade"] = _check_upgraded()
            fk = migration._ref_card_fk(db.engine)
            if str((fk.get("options") or {}).get("ondelete") or "").upper() != "SET NULL":
                raise AssertionError(f"Connect ref FK was not switched to SET NULL: {fk}")
            with db.engine.begin() as connection:
                migration.op._proxy = None
                from alembic.migration import MigrationContext
                from alembic.operations import Operations

                migration.op._proxy = Operations(MigrationContext.configure(connection))
                migration.upgrade()  # idempotent re-run
                migration.op._proxy = None
            report["idempotent_rerun"] = "PASS"

            # Guarded downgrade: an event whose Card is gone keeps its snapshot.
            _exec("UPDATE review_events SET note_id = 'note-9' WHERE card_id = 'deleted-card'")
            db.session.commit()
            try:
                downgrade(revision="20260925_000045", directory="migrations")
            except (RuntimeError, SystemExit) as exc:  # Flask-Migrate exits on errors
                report["guarded_downgrade"] = f"REFUSED ({type(exc).__name__})"
            else:
                raise AssertionError("Downgrade discarded non-derivable Note attribution.")
            db.session.rollback()
            _exec("UPDATE review_events SET note_id = NULL WHERE card_id = 'deleted-card'")
            db.session.commit()
            downgrade(revision="20260925_000045", directory="migrations")
            inspector = sa.inspect(db.engine)
            if inspector.has_table(migration.APPLICATIONS) or any(
                column["name"] == "application_id" for column in inspector.get_columns("cards")
            ):
                raise AssertionError("Downgrade left migration-46 artifacts.")
            report["derivable_downgrade"] = "PASS"
            upgrade(directory="migrations", revision=migration.revision)
            report["reupgrade"] = _check_upgraded()

            # Removing a Template's Cards keeps the Connect ref on its Note.
            _exec("DELETE FROM cards WHERE template_id = 't-back'")
            db.session.commit()
            ref = _exec("SELECT card_id, note_id, source_ord FROM connect_source_card_refs "
                        "WHERE id = 'ref-1'").one()
            if tuple(ref) != (None, "note-2", 1):
                raise AssertionError(f"Connect ref did not survive Card removal: {ref}")
            report["connect_ref_survives_card_delete"] = "PASS"
            try:
                downgrade(revision="20260925_000045", directory="migrations")
            except (RuntimeError, SystemExit):
                report["downgrade_refused_with_unbound_ref"] = "PASS"
            else:
                raise AssertionError("Downgrade restored NOT NULL over an unbound Connect ref.")
            db.session.rollback()

        boot_env = dict(os.environ)
        boot_env.update({
            "SQLALCHEMY_DATABASE_URI": uri, "STARTUP_RUN_MAINTENANCE": "0",
            "STARTUP_RUN_DB_CREATE_ALL": "0", "STARTUP_CHECK_DB_CONNECTIVITY": "0", "REDIS_URL": "",
        })
        boot = subprocess.run(
            [sys.executable, "-c", "import wsgi; assert wsgi.app is not None"],
            cwd=ROOT_DIR, env=boot_env, capture_output=True, text=True, check=False, timeout=60,
        )
        if boot.returncode:
            raise AssertionError(f"Flags-off wsgi.py boot failed: {boot.stderr[-400:]}")
        report["flags_off_wsgi_boot"] = "PASS"
        report["status"] = "PASS"
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
        admin.close()
    report["probe_database_dropped"] = created
    return report


if __name__ == "__main__":
    result = run_probe()
    print(json.dumps(result, indent=1, default=str))
    raise SystemExit(0 if result.get("status") == "PASS" else 1)
