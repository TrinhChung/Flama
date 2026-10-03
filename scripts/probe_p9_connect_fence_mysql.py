"""Exercise migration 48 (Connect authority fence) on a disposable MySQL database.

Builds current metadata, removes migration 48's artifacts with its own
downgrade, seeds Connect refs, then checks the real upgrade (one ALTER), its
idempotent re-run, the CHECK pairing, the downgrade guard and a clean round
trip. Only a generated local database is created and dropped.

    python scripts/probe_p9_connect_fence_mysql.py --refs 16000
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

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from models import db  # noqa: E402
from scripts.mysql_probe_db import (  # noqa: E402
    _connection_settings, _database_uri, _source_database_collation,
)

migration = importlib.import_module("migrations.versions.20261002_000048_add_connect_authority_fence")
PROBE_NAME_PATTERN = re.compile(r"^flama_p9_fence_probe_[0-9]+_[a-f0-9]{8}$")
NOW = datetime(2026, 10, 2, 12, 0, 0)


def _run(step) -> float:
    # A transaction left open by this probe would hold the table's metadata
    # lock; the migration's bounded lock_wait_timeout then fails it.
    db.session.remove()
    started = time.perf_counter()
    with db.engine.begin() as connection:
        op._proxy = Operations(MigrationContext.configure(connection))
        try:
            step()
        finally:
            op._proxy = None
    return round(time.perf_counter() - started, 2)


def _rejected(sql: str) -> str | None:
    try:
        db.session.execute(sa.text(sql))
        db.session.commit()
    except sa.exc.DBAPIError as exc:
        db.session.rollback()
        return str(exc.orig.args[0]) if exc.orig is not None and exc.orig.args else type(exc).__name__
    return None


def run_probe(refs: int) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p9_fence_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("P9 fence probe requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"schema_version": "p9-connect-fence-probe-mysql.v1", "configured_database_modified": False}
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {_source_database_collation(admin)}")
            created = True
        app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_RUN_DB_CREATE_ALL": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })
        with app.app_context():
            db.metadata.create_all(bind=db.engine)
            _run(migration.downgrade)
            columns = {c["name"] for c in sa.inspect(db.engine).get_columns(migration.TABLE)}
            report["head_47_reconstructed"] = "applied_authority_revision" not in columns
            from models.user import User

            # ORM bulk insert applies the model's Python-side defaults.
            db.session.execute(sa.insert(User), [{"id": 1, "username": "fence", "email": "fence@example.test"}])
            for start in range(0, refs, 2000):
                db.session.execute(sa.text(
                    "INSERT INTO connect_source_card_refs (id, user_id, source_key, external_card_id, "
                    "external_note_id, source_ord, snapshot_hash, applied_local_revision, created_at, updated_at) "
                    "VALUES (:id, 1, 'src', :ext, :note, 0, :hash, :rev, :now, :now)"),
                    [{"id": f"ref-{i}", "ext": str(i), "note": str(i), "hash": "a" * 64, "rev": i % 7, "now": NOW}
                     for i in range(start, min(refs, start + 2000))])
            db.session.commit()
            before = tuple(db.session.execute(sa.text(
                "SELECT COUNT(*), SUM(applied_local_revision), SUM(CRC32(snapshot_hash)) FROM connect_source_card_refs"
            )).one())
            report["upgrade_seconds"] = _run(migration.upgrade)
            report["second_upgrade_seconds"] = _run(migration.upgrade)
            after = tuple(db.session.execute(sa.text(
                "SELECT COUNT(*), SUM(applied_local_revision), SUM(CRC32(snapshot_hash)) FROM connect_source_card_refs"
            )).one())
            report["refs_unchanged"] = before == after
            report["authority_without_revision_rejected"] = _rejected(
                "UPDATE connect_source_card_refs SET applied_local_revision_state = 'AUTHORITY' WHERE id = 'ref-1'")
            report["unknown_state_rejected"] = _rejected(
                "UPDATE connect_source_card_refs SET applied_local_revision_state = 'OTHER' WHERE id = 'ref-1'")
            report["authority_accepted"] = _rejected(
                "UPDATE connect_source_card_refs SET applied_local_revision_state = 'AUTHORITY', "
                "applied_authority_revision = 3 WHERE id = 'ref-1'") is None
            try:
                _run(migration.downgrade)
                report["downgrade_refused_with_fence"] = False
            except RuntimeError:
                report["downgrade_refused_with_fence"] = True
            db.session.remove()
            db.session.execute(sa.text(
                "UPDATE connect_source_card_refs SET applied_local_revision_state = NULL, "
                "applied_authority_revision = NULL WHERE id = 'ref-1'"))
            db.session.commit()
            report["downgrade_seconds"] = _run(migration.downgrade)
            report["reupgrade_seconds"] = _run(migration.upgrade)
            problems = [key for key in ("head_47_reconstructed", "refs_unchanged", "authority_accepted",
                                        "downgrade_refused_with_fence") if not report[key]]
            problems += [key for key in ("authority_without_revision_rejected", "unknown_state_rejected")
                         if report[key] is None]
            report["problems"] = problems
            report["status"] = "PASS" if not problems else "FAIL"
        return report
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_dropped"] = True
        admin.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--refs", type=int, default=16000)
    args = parser.parse_args()
    result = run_probe(args.refs)
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result.get("status") == "PASS" else 1)
