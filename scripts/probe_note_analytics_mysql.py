"""Verify Note-grain analytics membership on a disposable local MySQL schema.

Uses the existing retirement fixtures and the original presentation query as
an independent membership oracle. Never writes configured application rows.
"""

from __future__ import annotations

import io
import json
import os
from pathlib import Path
import re
import secrets
import sys
import unittest
from unittest.mock import patch

from dotenv import load_dotenv
import pymysql

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_audit_app
from models import db
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation
from tests import test_note_stats_retirement as fixture

PROBE_NAME = re.compile(r"^flama_note_analytics_probe_[0-9]+_[a-f0-9]{8}$")
CASES = (
    "test_note_scope_preserves_original_absent_pairs_and_new_applications",
    "test_note_scope_ignores_aliases_for_a_different_application_note_type",
    "test_forecast_reads_one_row_for_many_occurrences_and_preserves_card_units",
    "test_collection_unions_disjoint_release_pins_instead_of_max_or_sum",
    "test_collection_deduplicates_owned_and_installed_active_presentations",
    "test_empty_deck_scope_and_notes_without_applications_have_no_weight",
    "test_pinned_retired_source_and_local_added_note_both_count_in_local_deck",
    "test_multiple_installs_count_per_local_deck_but_collection_forecast_deduplicates",
    "test_overview_includes_pinned_retired_source_once",
    "test_forecast_identity_drift_fails_closed_and_no_retired_table_is_queried",
)


def run():
    load_dotenv(ROOT / ".env")
    settings = _connection_settings()
    name = f"flama_note_analytics_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME.fullmatch(name):
        raise RuntimeError("This probe requires loopback MySQL and a generated schema.")
    if name == os.getenv("DB_NAME"):
        raise RuntimeError("Generated schema overlaps the configured application schema.")
    admin = pymysql.connect(**settings)
    created = False
    apps = []
    report = {"configured_database_modified": False, "generated_schema": name}
    try:
        with admin.cursor() as cursor:
            collation = _source_database_collation(admin)
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]

        def factory(config):
            config = {**config, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
                      "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False}
            app = create_audit_app(config)
            with app.app_context():
                if db.engine.url.database != name:
                    raise RuntimeError("Fixture engine did not bind the disposable schema.")
            apps.append(app)
            return app

        suite = unittest.TestSuite(fixture.NoteStatsRetirementTests(case) for case in CASES)
        with patch.object(fixture, "create_audit_app", side_effect=factory):
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        report.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
                      status="PASS" if result.wasSuccessful() else "FAIL")
        if not result.wasSuccessful():
            report["failed_cases"] = [test.id() for test, _ in result.failures + result.errors]
            # Fixtures contain synthetic data only; retain useful final error
            # types without credentials, SQL parameter dumps, or full traces.
            report["failure_summaries"] = [trace.splitlines()[-1][:160] for _, trace in result.failures + result.errors]
        return report
    finally:
        for app in apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            if not PROBE_NAME.fullmatch(name) or name == os.getenv("DB_NAME"):
                raise RuntimeError("Refusing to remove a non-probe schema.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
                if cursor.fetchone()[0] != 0:
                    raise RuntimeError("Disposable schema cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result.get("status") == "PASS" else 1)
