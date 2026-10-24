"""Qualify forecast snapshots with real sessions in a disposable local MySQL DB.

Runs the repository's exact-summary fixtures plus MySQL binary/date/precision,
timestamp anchors, timezone boundary and suspended/pristine-state contracts.
Never writes the configured DB or invokes startup maintenance.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta
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
import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_audit_app
from app.services import forecast_snapshot_service as service
from app.services.stats_today_future import build_today_future_stats
from models import db
from models.forecast_snapshot import StudyForecastSnapshot
from models.study_progress_subject import StudyProgressSubject
from models.user import User
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation
from tests import test_forecast_snapshots as forecast_fixture
from tests import test_note_stats_retirement as note_fixture

PROBE_NAME = re.compile(r"^flama_forecast_snapshot_probe_[0-9]+_[a-f0-9]{12}$")


class ForecastMySQLContracts(forecast_fixture.ForecastSnapshotTests):
    def test_mysql_types_double_load_binary_hash_and_datetime_round_trip(self):
        raw = self._payload("raw")
        self._prewarm()
        self.assertEqual(self._payload(), raw)
        columns = {column["name"]: column for column in sa.inspect(db.engine).get_columns("study_forecast_snapshots")}
        self.assertEqual(str(columns["daily_load"]["type"]), "DOUBLE")
        for name in ("scope_hash", "policy_hash", "dependency_hash"):
            self.assertEqual(str(columns[name]["type"]), "BINARY(32)")
        self.assertEqual(columns["valid_until_utc"]["type"].fsp, 6)
        header = db.session.execute(sa.select(StudyForecastSnapshot.__table__)).mappings().one()
        self.assertEqual(header["daily_load"], 0.1)
        self.assertEqual(header["valid_until_utc"], datetime(2026, 10, 12, 4))
        self.assertTrue(all(isinstance(header[name], bytes) and len(header[name]) == 32
                            for name in ("scope_hash", "policy_hash", "dependency_hash")))

    def test_due_at_timezone_boundary_and_suspended_pristine_card_buckets(self):
        user = db.session.get(User, 1)
        user.timezone = "Asia/Tokyo"
        # Two presentation applications should contribute two Cards per Note.
        self.fixture._application(1, self.fixture.own_type)
        subject = db.session.execute(sa.select(StudyProgressSubject)).scalar_one()
        subject.due_day = note_fixture.DAY + 1
        subject.due_at = note_fixture.NOW + timedelta(days=100)
        for moment, queue in ((datetime(2026, 10, 12, 18), "learning"),
                              (datetime(2026, 10, 12, 19), "relearning")):
            note = self.fixture._note(1, self.fixture.own_type, 1)
            self.fixture._state(note, due_day=None, due_at=moment, queue=queue)
        suspended = self.fixture._note(1, self.fixture.own_type, 1)
        self.fixture._state(suspended, due_day=note_fixture.DAY + 2, suspended=True)
        self.fixture._note(1, self.fixture.own_type, 1)  # Pristine, no subject state.
        db.session.commit()

        def payload(mode, backlog):
            self.app.config["FORECAST_SUMMARY_READ_MODE"] = mode
            return build_today_future_stats(user_id=1, timezone_name="Asia/Tokyo", scope="collection",
                deck_id=None, history_range="12m", future_range="all", backlog=backlog,
                now_utc=note_fixture.NOW)

        # Card units count both presentations; Note units (D6-04) count each Note once.
        for by_note, weight in ((False, 2), (True, 1)):
            with self.subTest(by_note=by_note):
                self.app.config["STUDY_NOTE_COUNT_ENABLED"] = by_note
                raw = [payload("raw", backlog) for backlog in (False, True)]
                self.assertTrue(self._prewarm()["published"])
                self.assertEqual([payload("summary", backlog) for backlog in (False, True)], raw)
                buckets, minimum, load = service.resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
                    timezone_name="Asia/Tokyo", day_boundary_hour=4, now_utc=note_fixture.NOW,
                    backlog=True, end_offset=None)
                self.assertEqual(buckets[0]["learning"], weight)
                self.assertEqual(buckets[1]["review"], weight)
                self.assertEqual(buckets[1]["relearning"], weight)
                self.assertEqual(sum(bucket["due_count"] for bucket in buckets.values()), 3 * weight)
                self.assertAlmostEqual(load, 0.1 * weight)
                self.assertEqual(minimum, 0)

    def test_capture_uses_readonly_repeatable_snapshot_before_publication(self):
        self.fixture.trace.clear()
        self.assertTrue(self._prewarm()["published"])
        statements = [statement.upper() for statement in self.fixture.trace]
        snapshot = next(index for index, sql in enumerate(statements)
                        if "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY" in sql)
        insert = next(index for index, sql in enumerate(statements)
                      if "INSERT INTO STUDY_FORECAST_SNAPSHOTS" in sql)
        self.assertLess(snapshot, insert)
        self.assertFalse(any(sql.startswith(("UPDATE ", "DELETE ", "INSERT "))
                             for sql in statements[snapshot + 1:insert]))


EXTRA_CASES = (
    "test_mysql_types_double_load_binary_hash_and_datetime_round_trip",
    "test_due_at_timezone_boundary_and_suspended_pristine_card_buckets",
    "test_capture_uses_readonly_repeatable_snapshot_before_publication",
)


def run(env_file=ROOT / ".env"):
    load_dotenv(env_file, override=False)
    settings = _connection_settings()
    name = f"flama_forecast_snapshot_probe_{os.getpid()}_{secrets.token_hex(6)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME.fullmatch(name):
        raise RuntimeError("Forecast probe requires loopback MySQL and a generated schema.")
    if name == os.getenv("DB_NAME", "").strip():
        raise RuntimeError("Generated schema overlaps the configured application schema.")
    admin = pymysql.connect(**settings)
    created = False
    apps = []
    report = {"status": "FAIL", "configured_database_modified": False, "generated_schema": name}
    started = time.monotonic()
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
            if cursor.fetchone():
                raise RuntimeError("Generated forecast schema exists; refusing to overwrite.")
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]

        def factory(config):
            app = create_audit_app({**config, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
                "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})
            with app.app_context():
                if db.engine.url.database != name:
                    raise RuntimeError("Forecast fixture engine is not bound to the generated schema.")
            apps.append(app)
            return app

        cases = unittest.defaultTestLoader.getTestCaseNames(forecast_fixture.ForecastSnapshotTests)
        suite = unittest.TestSuite(forecast_fixture.ForecastSnapshotTests(case) for case in cases)
        suite.addTests(ForecastMySQLContracts(case) for case in EXTRA_CASES)
        with patch.object(note_fixture, "create_audit_app", side_effect=factory):
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        report.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                      fixture_cases=cases, mysql_specific_cases=list(EXTRA_CASES),
                      status="PASS" if result.wasSuccessful() else "FAIL")
        if not result.wasSuccessful():
            report["failed_cases"] = [test.id() for test, _ in result.failures + result.errors]
            # Exclude driver exception/SQLAlchemy traces that can contain
            # connection parameters. Assertion summaries use synthetic data.
            report["failure_summaries"] = [trace.splitlines()[-1][:200]
                if trace.splitlines()[-1].startswith("AssertionError") else "Non-assertion fixture error; inspect locally."
                for _, trace in result.failures + result.errors]
        return report
    finally:
        for app in apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            if not PROBE_NAME.fullmatch(name) or name == os.getenv("DB_NAME", "").strip():
                raise RuntimeError("Refusing to remove a non-probe schema.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
                if cursor.fetchone()[0]:
                    raise RuntimeError("Forecast probe schema cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        report = run(args.env_file)
    except Exception as error:
        report = {"status": "FAIL", "error_type": type(error).__name__, "configured_database_modified": False}
    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(serialized)
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
