"""Check grouped NOTE future-due counts on a disposable local MySQL schema.

Runs the SQL and Python paths over the same rows: siblings, publisher-owned
source Notes, Notes without Cards and date edges for count parity, and one
learner per evidence defect (detached subject, logical-identity drift) for
fail-closed parity through the shared guarded scope. Creates/drops only a generated schema; configured
application rows are untouched.
"""
from __future__ import annotations

from datetime import date, datetime
import json
import os
from pathlib import Path
import re
import secrets
import sys
from unittest.mock import patch

from dotenv import load_dotenv
import pymysql

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_audit_app
from app.repositories.stats_query_repository import MYSQL_FIXED_OFFSET_MINUTES
from app.services.study_authority_read_service import StudyAuthorityReadError
from app.services.study_consolidated_progress_service import clear_note_progress
from models import db
from models.deck import Deck
from models.user import User
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation
from tests.test_stats_overview import StatsOverviewTests

PROBE_NAME_PATTERN = re.compile(r"^flama_dashboard_due_probe_[0-9]+_[a-f0-9]{8}$")


def run() -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_dashboard_due_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("The future-due probe requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report = {"configured_database_modified": False, "parity_cases": 0, "problems": []}
    try:
        with admin.cursor() as cursor:
            collation = _source_database_collation(admin)
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        app = create_audit_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
            "REDIS_URL": "", "STARTUP_CHECK_DB_CONNECTIVITY": False,
        })
        with app.app_context():
            if db.engine.url.database != name:
                raise RuntimeError("Probe engine did not bind the generated schema.")
            db.create_all()
            learner = User(username="due-probe", email="due-probe@example.test")
            publisher = User(username="due-publisher", email="due-publisher@example.test")
            db.session.add_all([learner, publisher])
            db.session.flush()
            deck = Deck(name="Due Probe", owner_user_id=learner.id)
            db.session.add(deck)
            db.session.flush()
            fixture = StatsOverviewTests("test_streak_calculation")
            fixture.app, fixture.user_id, fixture.deck_id, fixture._card_seq = app, learner.id, deck.id, 0
            add = fixture._add_canonical_due
            add(due_at=datetime(2026, 1, 9), due_day=date(2026, 1, 12).toordinal(), siblings=2)
            add(due_day=date(2026, 1, 8).toordinal(), buried=True)
            add(due_at=datetime(2026, 1, 10, 18, 59), due_day=date(2026, 1, 12).toordinal(), queue="learning")
            add(due_at=datetime(2026, 1, 10, 19), queue="relearning")
            add(due_at=datetime(2026, 1, 12), due_day=0)
            add(due_at=datetime(2026, 1, 12), due_day=date.max.toordinal() + 1)
            add(due_at=datetime(2026, 1, 11), queue="new")
            add(due_day=date(2026, 1, 11).toordinal(), suspended=True)
            add(due_day=date(2026, 1, 11).toordinal(), siblings=2, owner_id=publisher.id)
            add(due_day=date(2026, 1, 11).toordinal(), learner_id=publisher.id)
            add()
            add(due_day=date(2026, 1, 11).toordinal(), queue="learning")  # due_day alone does not schedule learning.
            pristine = add(due_at=datetime(2026, 1, 11))
            clear_note_progress(pristine, now_utc=datetime(2026, 1, 1))
            add(due_at=datetime(2026, 1, 11), siblings=0)  # Note type without applications: no Cards.
            for timestamp in (
                datetime(2025, 12, 31, 18, 59), datetime(2025, 12, 31, 19),
                datetime(2026, 12, 31, 18, 59), datetime(2026, 12, 31, 19),
                datetime(2028, 2, 28, 18, 59), datetime(2028, 2, 28, 19),
                datetime(2026, 3, 9, 7, 59), datetime(2026, 3, 9, 8),
                datetime(2026, 11, 2, 8, 59), datetime(2026, 11, 2, 9),
            ):
                add(due_at=timestamp, queue="learning")
            add(due_day=date(2028, 2, 29).toordinal())
            # Damaged evidence fails closed, so each defect gets its own learner and the
            # clean learner above keeps a readable scope for count parity.
            defects = {}
            for kind, damage in (("detached", {"detached": True}),
                                 ("logical_identity_drift", {"logical_key": b"drifted-logical-key"})):
                owner = User(username=f"due-probe-{kind}", email=f"due-probe-{kind}@example.test")
                db.session.add(owner)
                db.session.flush()
                owner_deck = Deck(name=f"Due Probe {kind}", owner_user_id=owner.id)
                db.session.add(owner_deck)
                db.session.flush()
                damaged = StatsOverviewTests("test_streak_calculation")
                damaged.app, damaged.user_id, damaged.deck_id = app, owner.id, owner_deck.id
                damaged._card_seq = 1000 * (len(defects) + 1)
                damaged._add_canonical_due(due_day=date(2026, 1, 11).toordinal())
                damaged._add_canonical_due(due_day=date(2026, 1, 11).toordinal(), **damage)
                defects[kind] = damaged
            db.session.commit()
            windows = (
                (date(2026, 1, 10), date(2026, 1, 13)),
                (date(2026, 12, 31), date(2027, 1, 1)),
                (date(2028, 2, 28), date(2028, 3, 1)),
            )
            for timezone_name in MYSQL_FIXED_OFFSET_MINUTES:
                for boundary in (0, 4, 23):
                    for start, end in windows:
                        args = dict(timezone_name=timezone_name, boundary=boundary, start=start, end=end)
                        with patch("app.services.stats_overview.can_use_mysql_local_day_sql", return_value=False):
                            expected = fixture._canonical_day_counts(**args)
                        actual = fixture._canonical_day_counts(**args)
                        report["parity_cases"] += 1
                        if actual != expected:
                            report["problems"].append({
                                "timezone": timezone_name, "boundary": boundary,
                                "start": str(start), "end": str(end),
                                "expected": {str(day): count for day, count in expected.items()},
                                "actual": {str(day): count for day, count in actual.items()},
                            })
            with patch("app.services.stats_overview.query_canonical_future_due_day_counts_mysql", side_effect=AssertionError("DST routed to fixed-offset SQL")):
                for start, end in ((date(2026, 3, 8), date(2026, 3, 10)), (date(2026, 11, 1), date(2026, 11, 3))):
                    fixture._canonical_day_counts(timezone_name="America/New_York", start=start, end=end)
                    report["dst_fallback_cases"] = report.get("dst_fallback_cases", 0) + 1

            def read_error(damaged, *, sql):
                try:
                    if sql:
                        damaged._canonical_day_counts(timezone_name="Asia/Tokyo")
                    else:
                        with patch("app.services.stats_overview.can_use_mysql_local_day_sql", return_value=False):
                            damaged._canonical_day_counts(timezone_name="Asia/Tokyo")
                except StudyAuthorityReadError as error:
                    return error.code
                return None

            # Both paths share the guarded scope and must agree. A detached subject
            # leaves its Note outside the forecast scope (no live state), so
            # neither path fails for it; identity drift fails both.
            expected = {"detached": None, "logical_identity_drift": "DETACHED_AUTHORITY_SUBJECT"}
            report["fail_closed"] = {}
            for kind, damaged in defects.items():
                outcome = {"python": read_error(damaged, sql=False), "sql": read_error(damaged, sql=True)}
                report["fail_closed"][kind] = outcome
                if outcome != {"python": expected[kind], "sql": expected[kind]}:
                    report["problems"].append({"defect": kind, "fail_closed_mismatch": outcome})
            report["status"] = "FAIL" if report["problems"] else "PASS"
            return report
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            if not PROBE_NAME_PATTERN.fullmatch(name) or name == os.getenv("DB_NAME"):
                raise RuntimeError("Refusing to drop a non-probe schema.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_dropped"] = True
        admin.close()


if __name__ == "__main__":
    result = run()
    print(json.dumps(result, indent=2, sort_keys=True))
    sys.exit(0 if result.get("status") == "PASS" else 1)
