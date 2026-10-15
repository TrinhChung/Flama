"""Qualify field identity migration63 in a generated loopback MySQL database.

Only source collation metadata is read from the configured DB. Application
startup is never invoked; fixture DDL/data and cleanup target one unpredictable
probe-owned database. Connection credentials are never included in output.
"""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
from unittest.mock import patch

from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

PROBE_NAME = re.compile(r"^flama_field_identity_probe_[0-9]+_[a-f0-9]{12}$")
MIGRATION = importlib.import_module("migrations.versions.20261013_000063_expand_field_value_identity")
VALUES = {"Word": "猫", "literal.dot": ["one", ["two", "<b>three</b>"]],
          "Null": None, "Empty": [], "Undeclared": "retained",
          "Typed": [True, False, 0, 1, 1.0, "1", None, ["duplicate", "duplicate"]]}


def _fixture(connection):
    metadata = sa.MetaData()
    users = sa.Table("users", metadata, sa.Column("id", sa.Integer, primary_key=True))
    note_types = sa.Table("note_types", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("name", sa.String(255), nullable=False))
    notes = sa.Table("notes", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_type_id", sa.String(36), sa.ForeignKey("note_types.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Integer, sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("deck_id", sa.Integer, nullable=True),
        sa.Column("field_values", sa.JSON, nullable=False), sa.Column("updated_at", sa.DateTime, nullable=False))
    media = sa.Table("media_assets", metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_id", sa.String(36), sa.ForeignKey("notes.id", ondelete="CASCADE"), nullable=False),
        sa.Column("field_name", sa.String(255), nullable=False), sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_path", sa.String(1024), nullable=False),
        sa.UniqueConstraint("note_id", "sha256", "field_name", name="uq_media_assets_note_sha_field"))
    # Empty synthetic exclusion tables let the real scoped runtime CAS run
    # without booting the application or inspecting source database content.
    sa.Table("deck_clone_added_notes", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_id", sa.String(36), nullable=False))
    sa.Table("deck_clone_deck_maps", metadata, sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("local_deck_id", sa.Integer, nullable=False))
    metadata.create_all(connection)
    connection.execute(users.insert().values(id=1))
    connection.execute(note_types.insert().values(id="schema", user_id=1, name="Words"))
    connection.execute(notes.insert().values(id="note", note_type_id="schema", user_id=1,
        field_values=VALUES, updated_at=datetime(2026, 10, 13, 1, 2, 3)))
    connection.execute(media.insert().values(id="asset", note_id="note", field_name="Audio",
        sha256="a" * 64, storage_path="synthetic/probe/audio.mp3"))
    connection.commit()
    return notes, media


def _run_migration(connection, step):
    with patch.object(MIGRATION, "op", Operations(MigrationContext.configure(connection))):
        getattr(MIGRATION, step)()
    connection.commit()


def _qualify(connection):
    notes, media = _fixture(connection)
    before_note = connection.execute(notes.select()).mappings().one()
    before_media = connection.execute(media.select()).mappings().one()
    raw_before = connection.exec_driver_sql("SELECT field_values FROM notes").scalar_one()
    unique_before = sa.inspect(connection).get_unique_constraints("media_assets")
    fk_before = sa.inspect(connection).get_foreign_keys("media_assets")
    lock_timeout = connection.exec_driver_sql("SELECT @@SESSION.lock_wait_timeout").scalar_one()
    _run_migration(connection, "upgrade")
    _run_migration(connection, "upgrade")
    if connection.exec_driver_sql("SELECT @@SESSION.lock_wait_timeout").scalar_one() != lock_timeout:
        raise RuntimeError("Migration did not restore the metadata lock timeout.")
    if connection.execute(notes.select()).mappings().one() != before_note:
        raise RuntimeError("Migration changed legacy note values or timestamps.")
    if connection.execute(media.select()).mappings().one() != before_media:
        raise RuntimeError("Migration changed legacy media references.")
    if connection.exec_driver_sql("SELECT field_values FROM notes").scalar_one() != raw_before:
        raise RuntimeError("Migration changed raw named JSON payload.")
    inspector = sa.inspect(connection)
    if inspector.get_unique_constraints("media_assets") != unique_before or inspector.get_foreign_keys("media_assets") != fk_before:
        raise RuntimeError("Media legacy uniqueness or FK contract changed.")
    if connection.exec_driver_sql(
        "SELECT field_values_by_id, field_values_codec, field_values_extras, content_revision FROM notes"
    ).one() != (None, None, None, 0):
        raise RuntimeError("Legacy expansion defaults are not SQL NULL and revision zero.")
    # Use the real dialect reflection to verify the idempotency preflight.
    MIGRATION._inspect_contract(connection)
    reflected = sa.Table("notes", sa.MetaData(), autoload_with=connection, resolve_fks=False)
    mapped = {"field-1": VALUES["literal.dot"], "field-null": None, "field-empty": []}
    connection.execute(reflected.update().values(field_values_by_id=mapped, field_values_codec="field-id.v1",
        field_values_extras={"Undeclared": VALUES["Undeclared"]}, content_revision=1))
    connection.execute(sa.text("UPDATE media_assets SET field_def_id='removed-field-id'"))
    connection.commit()
    row = connection.execute(reflected.select()).mappings().one()
    if row["field_values_by_id"] != mapped or row["field_values"] != VALUES:
        raise RuntimeError("Native typed field values failed the MySQL JSON round trip.")
    try:
        _run_migration(connection, "downgrade")
    except RuntimeError as error:
        if "populated values/revisions" not in str(error):
            raise
    else:
        raise RuntimeError("Populated identity downgrade was not refused.")
    MIGRATION._inspect_contract(connection)
    # Clear only synthetic probe rows to rehearse an unused-expand rollback.
    connection.exec_driver_sql("UPDATE notes SET field_values_by_id=NULL, field_values_codec=NULL, "
                               "field_values_extras=NULL, content_revision=0")
    connection.exec_driver_sql("UPDATE media_assets SET field_def_id=NULL")
    connection.commit()
    _run_migration(connection, "downgrade")
    _run_migration(connection, "downgrade")
    if connection.execute(notes.select()).mappings().one() != before_note:
        raise RuntimeError("Unused-expand rollback changed legacy named values.")
    _run_migration(connection, "upgrade")
    MIGRATION._inspect_contract(connection)
    result = {
        "raw_named_json_preserved": True, "nested_arrays_and_null_preserved": True,
        "legacy_note_media_rows_preserved": True, "media_fk_uniqueness_preserved": True,
        "upgrade_repeatable": True, "populated_downgrade_refused": True,
        "unused_expand_downgrade_and_reupgrade": True, "metadata_lock_timeout_restored": True,
    }
    return result


def run(env_file=ROOT / ".env"):
    load_dotenv(env_file, override=False)
    settings = _connection_settings()
    name = f"flama_field_identity_probe_{os.getpid()}_{secrets.token_hex(6)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME.fullmatch(name):
        raise RuntimeError("Field identity probe requires loopback MySQL and a generated schema.")
    if name == os.getenv("DB_NAME"):
        raise RuntimeError("Generated schema overlaps the configured application schema.")
    admin = pymysql.connect(**settings)
    created = False
    engine = None
    report = {"status": "FAIL", "migration": MIGRATION.revision, "generated_schema": name,
              "configured_database_modified": False}
    started = time.monotonic()
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
            if cursor.fetchone():
                raise RuntimeError("Generated probe schema already exists; refusing to overwrite.")
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        engine = sa.create_engine(_database_uri(settings, name))
        if engine.url.database != name:
            raise RuntimeError("Field identity fixture engine is not bound to the generated schema.")
        with engine.connect() as connection:
            if connection.exec_driver_sql("SELECT DATABASE()").scalar_one() != name or sa.inspect(connection).get_table_names():
                raise RuntimeError("Field identity fixture database is not the expected empty generated schema.")
            report.update(_qualify(connection))
        report["status"] = "PASS"
    except Exception as error:
        report["error_type"] = type(error).__name__
        # Operational/driver traces can contain connection credentials or SQL
        # parameters. Report only our controlled contract errors in full.
        if isinstance(error, RuntimeError):
            report["contract_error"] = str(error)
    finally:
        if engine is not None:
            engine.dispose()
        if created:
            if not PROBE_NAME.fullmatch(name) or name == os.getenv("DB_NAME"):
                raise RuntimeError("Refusing to clean up a non-probe schema.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
                if cursor.fetchone()[0]:
                    raise RuntimeError("Disposable field identity schema cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = run(args.env_file)
    except Exception as error:
        # Even connection/setup failures must not expose credentials.
        report = {"status": "FAIL", "error_type": type(error).__name__, "configured_database_modified": False}
    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
