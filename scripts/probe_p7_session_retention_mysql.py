"""Run the Phase 7 session-retention contract on disposable local MySQL.

Real InnoDB foreign keys and locking reads apply here (SQLite tests do not
enforce them). Only a generated database is created and dropped.
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
from scripts.probe_phase4_shadow_schema_mysql import (
    _connection_settings, _database_uri, _source_database_collation,
)
from tests.test_study_session_retention import StudySessionRetentionTests

PROBE_NAME_PATTERN = re.compile(r"^flama_p5_direct_probe_[0-9]+_[a-f0-9]{8}$")


def run_probe() -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p5_direct_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("Retention probe requires a generated local MySQL database.")
    connection = pymysql.connect(**settings)
    created = False
    app = None
    report = {"schema_version": "p7-session-retention-mysql.v1", "configured_database_modified": False}
    try:
        collation = _source_database_collation(connection)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        app = _probe_app(_database_uri(settings, name))

        class MySQLSessionRetentionTests(StudySessionRetentionTests):
            @classmethod
            def setUpClass(cls):
                cls.app = app

        suite = unittest.defaultTestLoader.loadTestsFromTestCase(MySQLSessionRetentionTests)
        result = unittest.TextTestRunner(verbosity=2).run(suite)
        report.update({"tests_run": result.testsRun, "failures": len(result.failures),
                       "errors": len(result.errors), "status": "PASS" if result.wasSuccessful() else "FAIL"})
        return report
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_removed"] = True
        connection.close()


if __name__ == "__main__":
    outcome = run_probe()
    print(json.dumps(outcome, sort_keys=True))
    raise SystemExit(0 if outcome.get("status") == "PASS" else 1)
