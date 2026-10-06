"""Compare canonical and derived analytics on an explicitly local MySQL dump.

The only persistent changes permitted here are new derived counts when --apply
is requested. User 1's source rows are fingerprinted before and after the run.
"""

import argparse
from datetime import datetime
import json
from pathlib import Path
import statistics
import sys
import time
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from sqlalchemy import event, func, select

from app import create_audit_app
from app.services.review_analytics_backfill_service import run_review_analytics_backfill
from app.services.study_analytics_read_service import analytics_read_transaction
from app.services.stats_overview import build_stats_overview
from app.services.stats_today_future import build_today_future_stats, build_user_study_time_stats
from app.services.rest_api_service import build_dashboard_payload
from models import db
from models.user import User
from models.review_analytics import DailyReviewCount
from scripts.probe_review_analytics_mysql import _fingerprint, local_url


def run(arguments):
    url = local_url(arguments.env_file.resolve())
    app = create_audit_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
        "REVIEW_ANALYTICS_WRITE_ENABLED": True,
        "REVIEW_ANALYTICS_READ_USER_IDS": [], "REDIS_URL": "",
        "DECK_COUNT_WRITE_ENABLED": not arguments.history_only,
        "DECK_COUNT_READ_MODE": "raw",
    })
    now = datetime.fromisoformat(arguments.now)
    report = {"host": url.host, "database": url.database, "user_id": 1,
              "now_utc": now.isoformat(), "repetitions": arguments.repetitions}
    with app.app_context():
        before = _fingerprint(db.engine)["source"]
        report["source_before"] = before
        if arguments.apply:
            started = time.perf_counter()
            result = run_review_analytics_backfill(user_id=1, writer_coverage_enabled=True, chunk_size=500)
            report["history_backfill"] = {**result, "elapsed_ms": round((time.perf_counter()-started)*1000, 2)}
            print(json.dumps({"history_backfill": result.get("status"), "elapsed_ms": report["history_backfill"]["elapsed_ms"]}), flush=True)
            if not result["ok"]:
                raise RuntimeError("History backfill was not verified and published")
            if not arguments.history_only:
                from app.services.deck_count_snapshot_service import prewarm_owned_deck_counts
                started = time.perf_counter()
                result = prewarm_owned_deck_counts(user_id=1, now_utc=now)
                report["deck_prewarm"] = {**result, "elapsed_ms": round((time.perf_counter()-started)*1000, 2)}
                print(json.dumps({"deck_prewarm": report["deck_prewarm"]}), flush=True)
        def overview():
            return build_stats_overview(user_id=1, year=now.year, timezone_name=user.timezone, now_utc=now)
        def today():
            return build_today_future_stats(user_id=1, timezone_name=user.timezone, scope="collection",
                deck_id=None, history_range="30d", future_range="30d", backlog=True, now_utc=now)
        def study_time():
            return build_user_study_time_stats(user_id=1, timezone_name=user.timezone, scope="collection",
                                                range_preset="all", now_utc=now)
        def dashboard():
            with patch("app.services.dashboard_service._utcnow", return_value=now):
                return build_dashboard_payload(user, compact=True)
        operations = {"overview": overview, "today_future": today, "study_time_all": study_time}
        if not arguments.history_only:
            operations["dashboard_compact"] = dashboard
        metrics = {}
        for name, operation in operations.items():
            values = {}
            detail = {}
            for mode in ("raw", "summary"):
                app.config["REVIEW_ANALYTICS_READ_MODE"] = mode
                app.config["DECK_COUNT_READ_MODE"] = mode
                durations = []
                sql = []
                profiles = []
                def capture(_conn, _cursor, statement, _parameters, _context, _many):
                    _context._analytics_bench_started = time.perf_counter()
                    sql.append(statement)
                def finished(_conn, _cursor, statement, _parameters, _context, _many):
                    profiles.append({"cursor_ms": round((time.perf_counter()-_context._analytics_bench_started)*1000, 2),
                                     "sql_prefix": " ".join(statement.split())[:180]})
                event.listen(db.engine, "before_cursor_execute", capture)
                event.listen(db.engine, "after_cursor_execute", finished)
                try:
                    for iteration in range(arguments.repetitions + 1):
                        db.session.remove()
                        with analytics_read_transaction():
                            user = db.session.get(User, 1)
                            sql.clear()
                            profiles.clear()
                            started = time.perf_counter()
                            result = operation()
                            elapsed = (time.perf_counter()-started)*1000
                        if iteration:
                            durations.append(elapsed)
                        values[mode] = result
                    detail[mode] = {
                        "median_ms": round(statistics.median(durations), 2),
                        "max_ms": round(max(durations), 2), "samples_ms": [round(x, 2) for x in durations],
                        "statements": len(sql),
                        "raw_history_selects": sum("review_events" in query.lower() for query in sql),
                        "card_count_scans": sum("count(" in query.lower() and "cards" in query.lower() for query in sql),
                        "projection_selects": sum("daily_review_counts" in query.lower() or "deck_study_count_snapshots" in query.lower() for query in sql),
                        "locking_selects": sum(any(token in query.lower() for token in ("for share", "for update", "lock in share mode")) for query in sql),
                        "last_sample_query_profile": profiles,
                    }
                finally:
                    event.remove(db.engine, "before_cursor_execute", capture)
                    event.remove(db.engine, "after_cursor_execute", finished)
            detail["exact_payload_parity"] = values["raw"] == values["summary"]
            metrics[name] = detail
            print(json.dumps({name: detail}), flush=True)
        report["metrics"] = metrics
        with analytics_read_transaction():
            report["history_bucket_rows"] = int(db.session.execute(select(func.count()).select_from(DailyReviewCount).where(DailyReviewCount.user_id == 1)).scalar_one())
        after = _fingerprint(db.engine)["source"]
        report["source_after"] = after
        report["source_preserved"] = before == after
        report["passed"] = before == after and all(item["exact_payload_parity"] and not item["summary"]["locking_selects"] for item in metrics.values())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=ROOT / "output/analytics_counts_benchmark_20261006.json")
    parser.add_argument("--apply", action="store_true", help="Build derived history and deck counts; source is read only")
    parser.add_argument("--history-only", action="store_true")
    parser.add_argument("--now", default="2026-10-06T03:00:00")
    parser.add_argument("--repetitions", type=int, choices=range(1, 21), default=5)
    raise SystemExit(0 if run(parser.parse_args()) else 1)
