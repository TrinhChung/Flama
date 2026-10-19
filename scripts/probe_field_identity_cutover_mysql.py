"""Rehearse Field-ID revision66/67 plus real archive restore in generated MySQL.

Only configured source collation metadata is read. Two unpredictable loopback
schemas hold synthetic fixtures and are dropped after qualification.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from migrations.field_identity_contract import ARCHIVE, CODEC, reflected, verify_prepared
from scripts.cutover_field_value_identity import prepare_cutover, restore_archived_note_values
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation

NAME = re.compile(r"^flama_field_cutover_(?:probe|restore)_[0-9]+_[a-f0-9]{12}$")


def fixture_module():
    spec = importlib.util.spec_from_file_location("field_cutover_fixture", ROOT / "tests/test_field_identity_cutover.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def run(env_file=ROOT / ".env"):
    load_dotenv(env_file, override=False)
    settings = _connection_settings()
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("Field cutover probe requires loopback MySQL.")
    suffix = f"{os.getpid()}_{secrets.token_hex(6)}"
    names = [f"flama_field_cutover_probe_{suffix}", f"flama_field_cutover_restore_{suffix}"]
    if any(not NAME.fullmatch(name) or name == os.getenv("DB_NAME") for name in names):
        raise RuntimeError("Generated probe schema is unsafe.")
    admin, created, engines = pymysql.connect(**settings), [], []
    report = {"status": "FAIL", "configured_database_modified": False, "generated_schemas": names,
              "revisions": ["20261014_000066", "20261014_000067"]}
    started = time.monotonic()
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
            for name in names:
                cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
                if cursor.fetchone():
                    raise RuntimeError("Generated field probe schema already exists.")
                cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
                created.append(name)
        engines = [sa.create_engine(_database_uri(settings, name)) for name in names]
        source, restore = engines
        module = fixture_module()
        with source.begin() as connection:
            if connection.exec_driver_sql("SELECT DATABASE()").scalar_one() != names[0]:
                raise RuntimeError("Synthetic fixture target differs from generated schema.")
            source_tables = module.fixture(connection)
            connection.execute(source_tables[0].insert().values(id="json-null-note", note_type_id="schema", user_id=1,
                field_values=module.VALUES, field_values_by_id=sa.JSON.NULL, field_values_extras=sa.JSON.NULL,
                updated_at=module.NOW))
            module.fixture_overrides(connection, with_data=True)
            timeout = connection.exec_driver_sql("SELECT @@SESSION.lock_wait_timeout").scalar_one()
            module.FieldIdentityCutoverTests.run_migration(connection, module.EXPAND)
            if connection.exec_driver_sql("SELECT @@SESSION.lock_wait_timeout").scalar_one() != timeout:
                raise RuntimeError("Expansion did not restore metadata lock wait timeout.")
        result = prepare_cutover(source, apply=False)
        report["read_only_dry_run"] = result["state"] == "dry_run"
        bounded = prepare_cutover(source, apply=True, writers_quiesced=True, batch_size=1, max_batches=1)
        if bounded["state"] != "preparing":
            raise RuntimeError("Bounded cutover did not stop at a resumable batch boundary.")
        prepared = prepare_cutover(source, apply=True, writers_quiesced=True, batch_size=1)
        if prepared["state"] != "verified":
            raise RuntimeError("Resumed cutover did not verify full archive coverage.")
        report["bounded_resume_and_verified_archive"] = True
        report["source_and_added_overrides_archived"] = prepared["total_overrides"] == 2
        with source.connect() as connection:
            verify_prepared(connection)
        with source.begin() as connection:
            module.FieldIdentityCutoverTests.run_migration(connection, module.CONTRACT)
            notes = reflected(connection, "notes")
            if "field_values" in notes.c or sa.inspect(connection).has_table("field_rename_jobs"):
                raise RuntimeError("Field contraction retained live named storage/rename jobs.")
            row = connection.execute(notes.select().where(notes.c.id == "note")).mappings().one()
            if row["field_values_by_id"] != {"word-id": module.VALUES["Word"], "dot-id": module.VALUES["literal.dot"]} \
                    or row["field_values_extras"] != {"MissingExtra": []} or row["updated_at"] != module.NOW:
                raise RuntimeError("Canonical migration changed JSON types/presence or source timestamp.")
            if any(column["nullable"] for column in sa.inspect(connection).get_columns("notes")
                    if column["name"] in {"field_values_by_id", "field_values_codec", "field_values_extras"}):
                raise RuntimeError("Canonical Note fields are unexpectedly nullable.")
            if connection.exec_driver_sql("SELECT field_identity_key FROM media_assets WHERE id='media'").scalar_one() != "word-id":
                raise RuntimeError("Media stable reference failed to survive contraction.")
            report.update(native_types_presence_and_timestamp_preserved=True, name_column_and_rewrite_jobs_retired=True,
                canonical_nonnullable_v1=True, media_identity_uniqueness=True)
            overrides = connection.exec_driver_sql("SELECT id,field_identity_key FROM deck_clone_note_field_overrides ORDER BY id").all()
            if overrides != [("ov-added", "added:install:added-id"), ("ov-source", "word-id")]:
                raise RuntimeError("Source/clone-added override identities failed canonical migration.")
            report["override_identity_uniqueness_and_namespaces"] = True
        # Real restore into a separate pre-cutover fixture schema; the source
        # remains contracted and is only read by archive restoration.
        with restore.begin() as connection:
            target_tables = module.fixture(connection)
            connection.execute(target_tables[0].insert().values(id="json-null-note", note_type_id="schema", user_id=1,
                field_values={}, updated_at=module.NOW))
            connection.exec_driver_sql("UPDATE notes SET field_values='{}'")
        with source.connect() as source_connection, restore.begin() as target_connection:
            report["isolated_archive_restore"] = restore_archived_note_values(source_connection, target_connection)
            if target_connection.exec_driver_sql("SELECT field_values_codec FROM notes WHERE id='note'").scalar_one() is not None:
                raise RuntimeError("Restore did not preserve original SQL NULL codec state.")
            state = target_connection.exec_driver_sql("SELECT CAST(field_values_by_id AS CHAR),CAST(field_values_extras AS CHAR) "
                "FROM notes WHERE id='json-null-note'").one()
            if state != ("null", "null"):
                raise RuntimeError("Archive restore failed to distinguish JSON null from SQL NULL.")
            report["sql_null_and_json_null_shadow_state_restored"] = True
        # Register actual runtime mappings in an isolated audit app. Audit
        # bootstrap performs no schema maintenance/seed/backfill; configured
        # MySQL is never attached to this application instance.
        from app import create_audit_app
        create_audit_app({"SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "TESTING": True})
        report["runtime_mapping_registration"] = "isolated SQLite audit app; no startup maintenance"
        from models.note import Note
        from models.note_type import NoteType
        from models.field_def import FieldDef
        parent = NoteType(id="schema", user_id=1, name="Synthetic", field_schema_revision=0)
        parent.field_defs = [FieldDef(id="word-id", note_type_id="schema", name="Word"),
                             FieldDef(id="dot-id", note_type_id="schema", name="literal.dot")]
        note = Note(id="note", note_type_id="schema", user_id=1, note_type=parent,
            field_values_by_id=row["field_values_by_id"], field_values_codec=CODEC, field_values_extras=row["field_values_extras"])
        if note.field_values != module.VALUES:
            raise RuntimeError("Current canonical Python name projection differs from legacy values.")
        parent.field_defs[0].name = "Renamed"
        projected = note.field_values
        if projected.get("Renamed") != module.VALUES["Word"] or "Word" in projected or note.field_values_by_id != row["field_values_by_id"]:
            raise RuntimeError("Canonical field rename rewrote values or failed current label projection.")
        report["runtime_name_projection_and_no_value_rename_rewrite"] = True
        report["status"] = "PASS"
    except Exception as error:
        report["error_type"] = type(error).__name__
        if isinstance(error, RuntimeError):
            report["contract_error"] = str(error)
    finally:
        for engine in engines:
            engine.dispose()
        for name in reversed(created):
            if not NAME.fullmatch(name) or name == os.getenv("DB_NAME"):
                raise RuntimeError("Refusing cleanup of a non-probe schema.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
        report["probe_databases_dropped"] = len(created) == len(names)
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
        report = {"status": "FAIL", "error_type": type(error).__name__, "configured_database_modified": False}
    output = json.dumps(report, ensure_ascii=False, sort_keys=True, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(output + "\n", encoding="utf-8")
    print(output)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
