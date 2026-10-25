"""Run the NOTE dashboard/overview contracts on disposable local MySQL.

On MySQL the analytics routes run inside START TRANSACTION ... READ ONLY, so a
locking read or write in those paths fails with error 1792 here while SQLite
passes. Creation and cleanup touch only a generated database on loopback.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import secrets
import sys
import unittest

from dotenv import load_dotenv
import pymysql

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from models import db
from scripts.probe_p5_direct_replay_mysql import _probe_app
from scripts.mysql_probe_db import (
    _connection_settings, _database_uri, _source_database_collation, reuse_generated_schema,
)
from tests.test_note_analytics_read import NoteAnalyticsReadTests

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_direct_probe_[0-9]+_[a-f0-9]{8}$")


def run_probe():
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    # Reuses the direct-replay probe's local-only name guard in _probe_app.
    name = f"flama_p5_direct_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("Analytics probe requires a generated local MySQL database.")
    connection = pymysql.connect(**settings)
    created = False
    app = None
    report = {"schema_version": "p5-analytics-mysql.v1", "configured_database_modified": False}
    try:
        collation = _source_database_collation(connection)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        app = _probe_app(_database_uri(settings, name))

        class MySQLNoteAnalyticsReadTests(NoteAnalyticsReadTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app
                cls.app.config["STUDY_NOTE_COUNT_ENABLED"] = False

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(MySQLNoteAnalyticsReadTests)
        with reuse_generated_schema(name) as schema_reuse:
            result = unittest.TextTestRunner(verbosity=2).run(suite)
        report.update({"tests_run": result.testsRun, "failures": len(result.failures),
            "errors": len(result.errors), "schema_reuse": schema_reuse,
            "status": "PASS" if result.wasSuccessful() else "FAIL"})
        return report
    finally:
        try:
            if app is not None:
                with app.app_context():
                    db.session.remove()
                    db.engine.dispose()
        finally:
            try:
                if created:
                    if not PROBE_NAME_PATTERN.fullmatch(name):
                        raise RuntimeError("Refusing an unsafe analytics probe cleanup target.")
                    with connection.cursor() as cursor:
                        cursor.execute(f"DROP DATABASE `{name}`")
                    report["probe_database_removed"] = True
            finally:
                connection.close()


if __name__ == "__main__":
    report = run_probe()
    print(json.dumps(report, sort_keys=True))
    if report["status"] != "PASS":
        raise SystemExit(1)
