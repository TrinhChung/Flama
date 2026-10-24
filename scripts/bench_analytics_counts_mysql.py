"""Compare canonical and derived analytics on an explicitly local MySQL dump.

The only persistent changes permitted here are new derived counts when --apply
is requested. User 1's source rows are fingerprinted before and after the run.
"""

import argparse
from datetime import datetime
import json
import math
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


def _percentile(values, percentile):
    ordered = sorted(values)
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _session_work():
    """Connection-local MySQL work counters; these are not rows examined."""
    return {name: int(value) for name, value in db.session.connection().exec_driver_sql(
        "SHOW SESSION STATUS WHERE Variable_name IN "
        "('Handler_read_key','Handler_read_next','Handler_read_rnd_next',"
        "'Created_tmp_tables','Created_tmp_disk_tables')"
    ).all()}


def drain_deck_prewarm(prewarm, *, now, max_decks, max_batches):
    """Drain bounded chunks, confirm coverage and retry discarded publications."""
    batches, cursor, cap = [], 0, max_batches
    for _batch in range(max_batches):
        result = prewarm(user_id=1, now_utc=now, max_decks=max_decks, after_deck_id=cursor)
        batches.append(result)
        if not result.get("ok"):
            break
        if len(batches) == 1:
            cap = min(max_batches, math.ceil(result.get("eligible", 0) / max_decks) + 3)
        if not result.get("computed") and result.get("cached", 0) == result.get("eligible", 0):
            break
        if len(batches) >= cap:
            break
        cursor = result["next_after_deck_id"] if result.get("has_more") else 0
    final = batches[-1]
    return {"batches": batches, "batch_cap": cap,
        "ready": bool(final.get("ok") and not final.get("computed")
                      and final.get("cached", 0) == final.get("eligible", 0)),
        "eligible": final.get("eligible"), "cached": final.get("cached"),
        "has_more": bool(final.get("has_more"))}


def parent_closed_selection(parent_by_id, eligible_ids, ranked_ids, limit):
    """Choose real content-heavy nodes and their ancestors, without cycles."""
    selected, eligible = set(), set(eligible_ids)
    for candidate in list(ranked_ids) + sorted(eligible):
        path, visited, current = set(), set(), candidate
        while current is not None and current not in selected:
            if current not in eligible or current in visited:
                path = set()
                break
            visited.add(current)
            path.add(current)
            current = parent_by_id[current]
        if len(selected | path) <= limit:
            selected.update(path)
        if len(selected) == limit:
            break
    return sorted(selected)


def dashboard_node_count(payload):
    pending, count = list(payload["items"]), 0
    while pending:
        node = pending.pop()
        count += 1
        pending.extend(node["children"])
    return count


def _dashboard_fixture_scope(now, limit):
    from app.repositories.deck_count_snapshot_repository import read_admin_mode
    from app.repositories.deck_tree_query import collect_accessible_decks
    from app.services.deck_count_snapshot_service import _worker_context
    from models.note import Note
    with analytics_read_transaction():
        admin = read_admin_mode(db.session, 1)
        visible = collect_accessible_decks(user_id=1, admin_mode=admin)
        context = _worker_context(db.session(), 1, None, now)
        eligible = set(context.deck_ids if context else ())
        parents = {int(row.id): row.parent_id for row in visible}
        qualified = eligible & set(parents)
        ranked = db.session.execute(select(Note.deck_id, func.count()).where(
            Note.user_id == 1, Note.deck_id.in_(qualified)).group_by(Note.deck_id)
            .order_by(func.count().desc(), Note.deck_id)).all() if limit else []
        selected = parent_closed_selection(parents, qualified, [row[0] for row in ranked], limit) if limit else []
    return {"visible_nodes": len(parents), "eligible_visible_nodes": len(qualified),
            "excluded_visible_nodes": len(set(parents) - eligible), "admin_mode": admin,
            "bounded": {"requested_nodes": limit, "selected_nodes": len(selected),
                "selected_deck_ids": selected, "parent_closed": True,
                "fixture_contract": "synthetic visibility override in benchmark only; content-heavy owned scopes with complete ancestry"}}


def run(arguments):
    url = local_url(arguments.env_file.resolve())
    app = create_audit_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
        "REVIEW_ANALYTICS_WRITE_ENABLED": not arguments.deck_only,
        "ANALYTICS_REQUIRE_READY_USER_IDS": [],
        "REVIEW_ANALYTICS_READ_USER_IDS": [], "REDIS_URL": "",
        "DECK_COUNT_WRITE_ENABLED": not arguments.history_only,
        "DECK_COUNT_READ_MODE": "raw",
        "FORECAST_SUMMARY_READ_MODE": "raw", "FORECAST_SUMMARY_READ_USER_IDS": [],
    })
    now = datetime.fromisoformat(arguments.now)
    report = {"host": url.host, "database": url.database, "user_id": 1,
              "now_utc": now.isoformat(), "repetitions": arguments.repetitions,
              "comparison_snapshot": "same read-only REPEATABLE READ snapshot per operation/repetition",
              "work_counter_contract": "MySQL session Handler reads and temp-table deltas; not rows examined",
              "cache_condition": "warm local fixture, one discarded warmup per operation; raw mode runs first",
              "projection_write_mode": "sync",
              "concurrency": 1, "production_qualified": False}
    with app.app_context():
        before = _fingerprint(db.engine)["source"]
        report["source_before"] = before
        if arguments.apply and not arguments.deck_only:
            started = time.perf_counter()
            result = run_review_analytics_backfill(user_id=1, writer_coverage_enabled=True, chunk_size=500)
            report["history_backfill"] = {**result, "elapsed_ms": round((time.perf_counter()-started)*1000, 2)}
            print(json.dumps({"history_backfill": result.get("status"), "elapsed_ms": report["history_backfill"]["elapsed_ms"]}), flush=True)
            if not result["ok"]:
                raise RuntimeError("History backfill was not verified and published")
        if arguments.apply and not arguments.history_only:
            from app.services.deck_count_snapshot_service import prewarm_owned_deck_counts
            started = time.perf_counter()
            drained = drain_deck_prewarm(prewarm_owned_deck_counts, now=now,
                max_decks=arguments.prewarm_max_decks, max_batches=arguments.prewarm_max_batches)
            report["deck_prewarm"] = {**drained,
                "elapsed_ms": round((time.perf_counter()-started)*1000, 2)}
            print(json.dumps({"deck_prewarm": report["deck_prewarm"]}), flush=True)
            from app.services.forecast_snapshot_service import prewarm_forecast_summary
            started = time.perf_counter()
            forecast = prewarm_forecast_summary(user_id=1, now_utc=now,
                max_buckets=arguments.forecast_max_buckets)
            report["forecast_prewarm"] = {**forecast, "elapsed_ms": round((time.perf_counter()-started)*1000, 2)}
            print(json.dumps({"forecast_prewarm": report["forecast_prewarm"]}), flush=True)
        def overview():
            return build_stats_overview(user_id=1, year=now.year, timezone_name=user.timezone, now_utc=now)
        def today():
            return build_today_future_stats(user_id=1, timezone_name=user.timezone, scope="collection",
                deck_id=None, history_range="30d", future_range="30d", backlog=True, now_utc=now)
        def study_time():
            return build_user_study_time_stats(user_id=1, timezone_name=user.timezone, scope="collection",
                                                range_preset="all", now_utc=now)
        owned_limit = getattr(arguments, "dashboard_owned_limit", 0)
        if not arguments.history_only:
            report["dashboard_scope"] = _dashboard_fixture_scope(now, owned_limit)
        def dashboard(*, bounded=False):
            from models.deck import Deck
            with patch("app.services.dashboard_service._utcnow", return_value=now):
                if bounded:
                    selected = report["dashboard_scope"]["bounded"]["selected_deck_ids"]
                    def visible(**_kwargs):
                        return db.session.execute(select(Deck).where(Deck.id.in_(selected))).scalars().all()
                    with patch("app.repositories.deck_tree_query.collect_accessible_decks", side_effect=visible):
                        return build_dashboard_payload(user)
                return build_dashboard_payload(user)
        operations = {"overview": overview, "today_future": today, "study_time_all": study_time}
        if not arguments.history_only:
            operations["dashboard_compact"] = dashboard
            if owned_limit:
                operations[f"dashboard_compact_owned_{owned_limit}"] = lambda: dashboard(bounded=True)
        if getattr(arguments, "dashboard_only", False):
            operation_name = f"dashboard_compact_owned_{owned_limit}" if owned_limit else "dashboard_compact"
            operations = {operation_name: operations[operation_name]}
        metrics = {}
        modes = {"raw": ("raw", "raw")}
        if not arguments.deck_only:
            modes["history_only"] = ("summary", "raw")
        if not arguments.history_only:
            modes["deck_only"] = ("raw", "summary")
        if not arguments.history_only and not arguments.deck_only:
            modes["summary"] = ("summary", "summary")
        report["read_matrices"] = {mode: {"history": history, "deck_counts": decks, "forecast": decks}
                                   for mode, (history, decks) in modes.items()}
        for name, operation in operations.items():
            detail = {mode: {"samples_ms": [], "same_snapshot_parity": True} for mode in modes}
            for iteration in range(arguments.repetitions + 1):
                db.session.remove()
                with analytics_read_transaction():
                    user = db.session.get(User, 1)
                    values = {}
                    for mode, (history_mode, deck_mode) in modes.items():
                        app.config["REVIEW_ANALYTICS_READ_MODE"] = history_mode
                        app.config["DECK_COUNT_READ_MODE"] = deck_mode
                        app.config["FORECAST_SUMMARY_READ_MODE"] = deck_mode
                        sql, profiles, outcomes, cache_coverage, forecast_coverage = [], [], [], [], []
                        from app.services.deck_count_snapshot_service import resolve_cached_owned_deck_counts
                        from app.services.forecast_snapshot_service import resolve_forecast_summary, resolve_overview_due_counts
                        from app.repositories.review_analytics_read_repository import _observe
                        def observe(metric, user_id, read_mode, outcome):
                            outcomes.append({"metric": metric, "outcome": outcome})
                            return _observe(metric, user_id, read_mode, outcome)
                        def cached(*args, **kwargs):
                            hits, misses = resolve_cached_owned_deck_counts(*args, **kwargs)
                            cache_coverage.append({"hits": len(hits), "misses": len(misses)})
                            return hits, misses
                        def forecast_cached(resolver, *args, **kwargs):
                            result = resolver(*args, **kwargs)
                            forecast_coverage.append({"resolver": resolver.__name__,
                                "outcome": "hit" if result is not None else "miss"})
                            return result
                        def capture(_conn, _cursor, statement, _parameters, _context, _many):
                            _context._analytics_bench_started = time.perf_counter()
                            sql.append(statement)
                        def finished(_conn, _cursor, statement, _parameters, _context, _many):
                            profiles.append({"cursor_ms": round((time.perf_counter()-_context._analytics_bench_started)*1000, 2),
                                             "sql_prefix": " ".join(statement.split())[:180]})
                        work_before = _session_work()
                        event.listen(db.engine, "before_cursor_execute", capture)
                        event.listen(db.engine, "after_cursor_execute", finished)
                        try:
                            started = time.perf_counter()
                            with patch("app.repositories.review_analytics_read_repository._observe", side_effect=observe), \
                                 patch("app.services.dashboard_service.resolve_cached_owned_deck_counts", side_effect=cached), \
                                 patch("app.services.forecast_snapshot_service.resolve_forecast_summary", side_effect=lambda *a, **kw: forecast_cached(resolve_forecast_summary, *a, **kw)), \
                                 patch("app.services.forecast_snapshot_service.resolve_overview_due_counts", side_effect=lambda *a, **kw: forecast_cached(resolve_overview_due_counts, *a, **kw)):
                                result = operation()
                            elapsed = (time.perf_counter()-started)*1000
                        finally:
                            event.remove(db.engine, "before_cursor_execute", capture)
                            event.remove(db.engine, "after_cursor_execute", finished)
                        work_after = _session_work()
                        values[mode] = result
                        measured = detail[mode]
                        if iteration:
                            measured["samples_ms"].append(round(elapsed, 2))
                        measured["same_snapshot_parity"] &= values["raw"] == result
                        measured.update({
                            "statements": len(sql),
                            "raw_history_selects": sum("review_events" in query.lower() for query in sql),
                            "note_count_scans": sum("analytics_note" in query.lower() for query in sql),
                            "progress_source_selects": sum("study_progress_subjects" in query.lower() for query in sql),
                            "projection_selects": sum(any(table in query.lower() for table in (
                                "daily_review_counts", "deck_study_count_snapshots", "study_forecast")) for query in sql),
                            "locking_selects": sum(any(token in query.lower() for token in ("for share", "for update", "lock in share mode")) for query in sql),
                            "dml_statements": sum(query.lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE", "REPLACE")) for query in sql),
                            "last_sample_query_profile": profiles,
                            "history_projection_outcomes": outcomes,
                            "deck_cache_coverage": cache_coverage,
                            "forecast_cache_coverage": forecast_coverage,
                            "session_work_delta": {key: work_after[key] - work_before[key] for key in work_before},
                        })
                        if name.startswith("dashboard"):
                            measured["returned_dashboard_nodes"] = dashboard_node_count(result)
                            if "owned_" in name and measured["returned_dashboard_nodes"] != report["dashboard_scope"]["bounded"]["selected_nodes"]:
                                raise RuntimeError("Bounded dashboard did not return its complete parent-closed node set")
            for mode in modes:
                durations = detail[mode]["samples_ms"]
                detail[mode].update({"median_ms": round(statistics.median(durations), 2),
                    "p95_ms": round(_percentile(durations, 95), 2),
                    "p99_ms": round(_percentile(durations, 99), 2), "max_ms": max(durations)})
            detail["exact_payload_parity"] = all(detail[mode]["same_snapshot_parity"] for mode in modes)
            metrics[name] = detail
            print(json.dumps({name: detail}), flush=True)
        report["metrics"] = metrics
        with analytics_read_transaction():
            report["history_bucket_rows"] = int(db.session.execute(select(func.count()).select_from(DailyReviewCount).where(DailyReviewCount.user_id == 1)).scalar_one())
        after = _fingerprint(db.engine)["source"]
        report["source_after"] = after
        report["source_preserved"] = before == after
        report["passed"] = before == after and all(item["exact_payload_parity"]
            and all(not item[mode]["locking_selects"] and not item[mode]["dml_statements"] for mode in modes)
            for item in metrics.values())
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    return report["passed"]


def bounded_integer(minimum, maximum):
    def parse(value):
        try:
            number = int(value)
        except ValueError as error:
            raise argparse.ArgumentTypeError("expected an integer") from error
        if not minimum <= number <= maximum:
            raise argparse.ArgumentTypeError(f"expected an integer between {minimum} and {maximum}")
        return number
    return parse


def parser():
    command = argparse.ArgumentParser(description=__doc__)
    command.add_argument("--env-file", type=Path, required=True)
    command.add_argument("--output", type=Path, default=ROOT / "output/analytics_counts_benchmark_20261006.json")
    command.add_argument("--apply", action="store_true", help="Build derived history and deck counts; source is read only")
    scope = command.add_mutually_exclusive_group()
    scope.add_argument("--history-only", action="store_true")
    scope.add_argument("--deck-only", action="store_true")
    command.add_argument("--prewarm-max-decks", type=bounded_integer(1, 1000), metavar="1..1000", default=100)
    command.add_argument("--prewarm-max-batches", type=bounded_integer(1, 100), metavar="1..100", default=10)
    command.add_argument("--forecast-max-buckets", type=bounded_integer(1, 65536), metavar="1..65536", default=4096)
    command.add_argument("--dashboard-owned-limit", type=bounded_integer(0, 100), metavar="0..100", default=0,
                        help="Also measure a parent-closed owned-deck fixture visibility scope (benchmark only)")
    command.add_argument("--dashboard-only", action="store_true", help="Measure only the selected dashboard scope")
    command.add_argument("--now", default="2026-10-06T03:00:00")
    command.add_argument("--repetitions", type=bounded_integer(1, 20), metavar="1..20", default=5)
    return command


if __name__ == "__main__":
    raise SystemExit(0 if run(parser().parse_args()) else 1)
