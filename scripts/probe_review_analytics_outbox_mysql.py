"""Qualify async history feed in generated loopback MySQL; source DB is untouched."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
import io
import json
import os
from pathlib import Path
import re
import secrets
import sys
import threading
import time
import unittest
from unittest.mock import patch
from uuid import uuid4

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app import create_audit_app
from app.repositories.study_authority_repository import lock_study_authority_route
from app.services.review_analytics_projection_service import flush_review_analytics_deltas
from app.services.review_analytics_outbox_service import process_review_analytics_outbox
from models import db
from models.review_analytics import ReviewAnalyticsHead
from models.review_analytics_outbox import ReviewAnalyticsOutbox
from models.review_event import ReviewEvent
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation
from tests import test_review_analytics_outbox as fixtures
from tests import test_review_analytics_projection as projection_fixture

FAIRNESS_EVIDENCE = {}

PROBE_NAME = re.compile(r"^flama_history_outbox_probe_[0-9]+_[a-f0-9]{12}$")


class OutboxMySQLContracts(fixtures.ReviewAnalyticsOutboxTests):
    def test_atomic_head_statement_returns_revision_for_new_existing_and_rolled_back_head(self):
        from app.repositories.review_analytics_outbox_repository import advance_async_head
        from tests.study_note_fixtures import create_note_user
        user = create_note_user(db.session, username="atomic-head", email="atomic-head@example.invalid")
        db.session.commit()
        user_id = int(user.id)
        db.session.remove()
        self.assertEqual(advance_async_head(db.session(), user_id=user_id), 1)
        db.session.rollback()
        self.assertIsNone(db.session.get(ReviewAnalyticsHead, user_id))
        self.assertEqual(advance_async_head(db.session(), user_id=user_id), 1)
        db.session.commit()
        loaded = db.session.get(ReviewAnalyticsHead, user_id)
        statements = []
        def capture(_connection, _cursor, sql, _params, _context, _many):
            statements.append(sql.upper())
        sa.event.listen(db.engine, "before_cursor_execute", capture)
        try:
            self.assertEqual(advance_async_head(db.session(), user_id=user_id), 2)
            self.assertEqual(loaded.source_revision, 2)
            db.session.flush()
        finally:
            sa.event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(len(statements), 1)
        self.assertTrue(statements[0].startswith("INSERT INTO REVIEW_ANALYTICS_HEADS"))
        self.assertIn("LAST_INSERT_ID", statements[0])
        db.session.rollback()
        self.assertEqual(db.session.get(ReviewAnalyticsHead, user_id).source_revision, 1)
        self.assertEqual(advance_async_head(db.session(), user_id=user_id), 2)
        db.session.commit()
        db.session.remove()
        self.assertEqual(db.session.get(ReviewAnalyticsHead, user_id).source_revision, 2)

    def test_mysql_binary_unsigned_precision_and_payload_round_trip(self):
        self._append(duration_ms=700, rating="GOOD", deck_id=12)
        columns = {column["name"]: column for column in sa.inspect(db.engine).get_columns("review_analytics_outbox")}
        self.assertEqual(str(columns["payload_hash"]["type"]), "BINARY(32)")
        self.assertTrue(columns["source_revision"]["type"].unsigned)
        self.assertEqual(columns["created_at"]["type"].fsp, 6)
        self.assertEqual(columns["applied_at"]["type"].fsp, 6)
        row = db.session.get(ReviewAnalyticsOutbox, (self.user_id, 1))
        self.assertEqual(row.events_payload[0]["passed_sql"], 1)
        self.assertEqual(len(bytes(row.payload_hash)), 32)
        self.assertTrue(self._drain()["ok"])
        self.assertEqual(self.fixture._counts(), (1, 700, 1))

    def test_oldest_pending_selection_uses_covering_index(self):
        from app.repositories.review_analytics_outbox_repository import pending_users_statement
        self._append()
        statement = pending_users_statement(limit=10)
        sql = str(statement.compile(db.engine, compile_kwargs={"literal_binds": True}))
        plan = db.session.execute(sa.text("EXPLAIN " + sql)).mappings().all()
        details = [dict(row) for row in plan]
        self.assertEqual(len(details), 1)
        self.assertEqual(details[0]["table"], "review_analytics_outbox")
        self.assertEqual(details[0]["key"], "ix_review_analytics_outbox_pending_age")
        self.assertIn("Using index", details[0]["Extra"])
        self.assertIn("min(review_analytics_outbox.created_at)", sql)
        FAIRNESS_EVIDENCE.update(query=sql, explain=details,
            limitation="Pending age aggregation/sort can scan pending feed rows and sort eligible learners; fixture proves covering access, not production latency or a constant-cost discovery bound.")

    def test_concurrent_same_learner_writers_allocate_commit_revisions_without_loss(self):
        db.session.remove()
        barrier = threading.Barrier(2)
        def writer(index):
            with self.app.app_context(), Session(bind=db.engine) as session:
                lock_study_authority_route(session, learner_user_id=self.user_id, allow_note_authority=True)
                session.add(ReviewEvent(user_id=self.user_id, card_id=f"outbox-thread-{index}",
                    client_event_id=str(uuid4()), reviewed_at=datetime(2026, 10, 5, 12),
                    rating="good", mode="review", duration_ms=100))
                session.flush()
                barrier.wait(timeout=10)
                flush_review_analytics_deltas(session)
                session.commit()
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(writer, index) for index in range(2)]
            for future in futures:
                future.result(timeout=30)
        rows = ReviewAnalyticsOutbox.query.order_by(ReviewAnalyticsOutbox.source_revision).all()
        self.assertEqual([row.source_revision for row in rows], [1, 2])
        self.assertEqual([row.event_count for row in rows], [1, 1])
        self.assertEqual(self._drain()["applied_revisions"], [1, 2])
        self.assertEqual(self.fixture._counts(), (2, 200, 2))

    def test_concurrent_workers_serialize_head_and_do_not_double_apply(self):
        self._append()
        self._append()
        barrier = threading.Barrier(2)
        def worker():
            with self.app.app_context():
                barrier.wait(timeout=10)
                return process_review_analytics_outbox(user_id=self.user_id)
        with ThreadPoolExecutor(max_workers=2) as pool:
            futures = [pool.submit(worker) for _ in range(2)]
            reports = [future.result(timeout=30) for future in futures]
        self.assertEqual(sorted(report["applied_revisions"] for report in reports), [[], [1, 2]])
        self.assertEqual(self.fixture._counts(), (2, 2000, 2))


EXTRA_CASES = (
    "test_oldest_pending_selection_uses_covering_index",
    "test_atomic_head_statement_returns_revision_for_new_existing_and_rolled_back_head",
    "test_mysql_binary_unsigned_precision_and_payload_round_trip",
    "test_concurrent_same_learner_writers_allocate_commit_revisions_without_loss",
    "test_concurrent_workers_serialize_head_and_do_not_double_apply",
)


def run(env_file=ROOT / ".env", *, selected_cases=None):
    FAIRNESS_EVIDENCE.clear()
    load_dotenv(env_file, override=False)
    settings = _connection_settings()
    name = f"flama_history_outbox_probe_{os.getpid()}_{secrets.token_hex(6)}"
    source = os.getenv("DB_NAME", "").strip()
    def guard():
        if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME.fullmatch(name) or name == source:
            raise RuntimeError("History outbox probe requires a unique generated loopback schema.")
    guard()
    admin = pymysql.connect(**settings)
    apps, created = [], False
    report = {"status": "FAIL", "generated_schema": name, "configured_database_modified": False}
    started = time.monotonic()
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
            if cursor.fetchone():
                raise RuntimeError("Generated outbox schema exists; refusing overwrite.")
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        def factory(config):
            app = create_audit_app({**config, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
                "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})
            with app.app_context():
                if db.engine.url.database != name:
                    raise RuntimeError("Outbox fixture engine is not bound to the generated schema.")
            apps.append(app)
            return app
        cases = unittest.defaultTestLoader.getTestCaseNames(fixtures.ReviewAnalyticsOutboxTests)
        if selected_cases:
            unknown = set(selected_cases) - set(cases) - set(EXTRA_CASES)
            if unknown:
                raise ValueError("Unknown outbox probe case.")
            cases = [case for case in cases if case in selected_cases]
        extra_cases = [case for case in EXTRA_CASES if not selected_cases or case in selected_cases]
        suite = unittest.TestSuite(fixtures.ReviewAnalyticsOutboxTests(case) for case in cases)
        suite.addTests(OutboxMySQLContracts(case) for case in extra_cases)
        with patch.object(projection_fixture, "create_audit_app", side_effect=factory):
            result = unittest.TextTestRunner(stream=io.StringIO(), verbosity=0).run(suite)
        report.update(tests_run=result.testsRun, failures=len(result.failures), errors=len(result.errors),
            fixture_cases=cases, mysql_specific_cases=extra_cases, fairness_index_evidence=dict(FAIRNESS_EVIDENCE), status="PASS" if result.wasSuccessful() else "FAIL")
        if not result.wasSuccessful():
            report["failed_cases"] = [test.id() for test, _ in result.failures + result.errors]
            report["failure_summaries"] = [next((line[:200] for line in trace.splitlines()
                if line.startswith("AssertionError")), "Non-assertion fixture error; inspect locally.")
                for _, trace in result.failures + result.errors]
        return report
    finally:
        for app in apps:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            guard()
            if name == os.getenv("DB_NAME", "").strip():
                raise RuntimeError("Generated probe now overlaps configured schema; refusing removal.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
                if cursor.fetchone()[0]:
                    raise RuntimeError("History outbox probe cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--case", action="append", help="Run a narrow named fixture or MySQL contract case.")
    args = parser.parse_args()
    try:
        report = run(args.env_file, selected_cases=args.case)
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
