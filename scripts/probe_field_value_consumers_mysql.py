"""Run canonical reader/writer/media/search contracts in disposable MySQL."""
from __future__ import annotations

import argparse
import io
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time
import unittest
from unittest.mock import patch

from dotenv import load_dotenv
import pymysql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_audit_app
from models import db
from scripts.mysql_probe_db import (
    _connection_settings, _database_uri, _source_database_collation, reuse_generated_schema,
)
from tests import test_field_value_consumers as fixtures

NAME = re.compile(r"^flama_field_consumer_probe_[0-9]+_[a-f0-9]{12}$")


def run(env_file=ROOT / ".env", *, selected_cases=None):
    load_dotenv(env_file, override=False)
    settings = _connection_settings()
    name = f"flama_field_consumer_probe_{os.getpid()}_{secrets.token_hex(6)}"
    def guard():
        if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not NAME.fullmatch(name) or name == os.getenv("DB_NAME"):
            raise RuntimeError("Field consumer qualification requires generated loopback MySQL.")
    guard()
    admin, apps, created = pymysql.connect(**settings), [], False
    report = {"status": "FAIL", "generated_schema": name, "configured_database_modified": False}
    started = time.monotonic()
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
            if cursor.fetchone():
                raise RuntimeError("Generated consumer schema already exists.")
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        def factory(config, **_kwargs):
            app = create_audit_app({**config, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
                "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})
            with app.app_context():
                if db.engine.url.database != name:
                    raise RuntimeError("Consumer fixture is not attached to generated schema.")
            apps.append(app)
            return app
        cases = unittest.defaultTestLoader.getTestCaseNames(fixtures.FieldValueConsumerTests)
        if selected_cases:
            if set(selected_cases) - set(cases):
                raise ValueError("Unknown consumer fixture case.")
            cases = [case for case in cases if case in selected_cases]
        suite = unittest.TestSuite(fixtures.FieldValueConsumerTests(case) for case in cases)
        with reuse_generated_schema(name) as schema_reuse, patch.object(fixtures, "create_app", side_effect=factory):
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        report.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors), fixture_cases=cases,
            schema_reuse=schema_reuse, status="PASS" if result.wasSuccessful() else "FAIL")
        if not result.wasSuccessful():
            report["failed_cases"] = [test.id() for test, _ in result.failures + result.errors]
            report["failure_summaries"] = [next((line[:300] for line in trace.splitlines() if line.startswith("AssertionError")),
                "Non-assertion fixture error; inspect locally.") for _, trace in result.failures + result.errors]
        return report
    finally:
        for app in apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            guard()
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
                if cursor.fetchone()[0]:
                    raise RuntimeError("Generated consumer schema cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", action="append", dest="cases", help="Run only named unittest methods; default all consumer cases")
    args = parser.parse_args()
    try:
        report = run(args.env_file, selected_cases=args.cases)
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
