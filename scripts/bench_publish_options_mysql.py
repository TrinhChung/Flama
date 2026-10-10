"""Read-only HTTP/service benchmark against an explicitly local MySQL dump.

Runs the current working copy on an isolated loopback WSGI server. No login,
startup maintenance, seed, schema change or fixture write is performed. Report
contains aggregate counts and timings, never credentials or note/deck content.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import statistics
import subprocess
import sys
import threading
import time
import tracemalloc
from urllib.request import ProxyHandler, Request, build_opener

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from sqlalchemy import event, text
from werkzeug.serving import WSGIRequestHandler, make_server

from app import create_audit_app
from app.routes import register_blueprints
from app.services import flashcards_share_service
from app.services.share import publish as modular_publish
from models import db
from scripts.probe_review_analytics_mysql import local_url


def digest(payload):
    return hashlib.sha256(json.dumps(payload, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def summary(samples):
    values = sorted(samples)
    return {
        "samples": len(values),
        "median_ms": round(statistics.median(values), 3),
        "p95_ms": round(values[max(0, math.ceil(len(values) * .95) - 1)], 3),
        "min_ms": round(values[0], 3),
        "max_ms": round(values[-1], 3),
    }


def sql_variants(engine, user_id, repetitions):
    """Compare query shapes in one read-only snapshot, rotating run order."""
    with engine.connect() as connection:
        ids = list(connection.execute(text(
            "SELECT id FROM decks WHERE owner_user_id=:uid AND deleted_at IS NULL"
        ), {"uid": user_id}).scalars())
        if not ids:
            raise ValueError("SQL comparison requires a user with visible decks")
        placeholders = ",".join(["%s"] * len(ids))
        scope = f"n.user_id=%s AND n.deck_id IN ({placeholders})"
        args = (user_id, *ids)
        visible = "n.user_id=%s AND d.owner_user_id=%s AND d.deleted_at IS NULL"
        queries = {
            "baseline_count": (f"SELECT n.deck_id,COUNT(c.id) FROM cards c JOIN notes n ON c.note_id=n.id WHERE {scope} GROUP BY n.deck_id", args),
            "baseline_note_types": (f"SELECT DISTINCT n.deck_id,n.note_type_id FROM notes n WHERE {scope}", args),
            "combined_in": (f"SELECT n.deck_id,n.note_type_id,COUNT(c.id) FROM notes n LEFT JOIN cards c ON c.note_id=n.id WHERE {scope} GROUP BY n.deck_id,n.note_type_id", args),
            "combined_visible_join": (f"SELECT n.deck_id,n.note_type_id,COUNT(c.id) FROM notes n JOIN decks d ON d.id=n.deck_id LEFT JOIN cards c ON c.note_id=n.id WHERE {visible} GROUP BY n.deck_id,n.note_type_id", (user_id, user_id)),
            "count_visible_join": (f"SELECT n.deck_id,COUNT(c.id) FROM notes n JOIN decks d ON d.id=n.deck_id JOIN cards c ON c.note_id=n.id WHERE {visible} GROUP BY n.deck_id", (user_id, user_id)),
            "note_types_visible_join": (f"SELECT DISTINCT n.deck_id,n.note_type_id FROM notes n JOIN decks d ON d.id=n.deck_id WHERE {visible}", (user_id, user_id)),
        }
        names = list(queries)
        durations = {name: [] for name in names}
        rows = {}
        for iteration in range(repetitions + 2):
            order = names[iteration % len(names):] + names[:iteration % len(names)]
            for name in order:
                sql, params = queries[name]
                started = time.perf_counter()
                rows[name] = connection.exec_driver_sql(sql, params).all()
                elapsed = (time.perf_counter() - started) * 1000
                if iteration >= 2:
                    durations[name].append(elapsed)
        baseline_counts = dict(rows["baseline_count"])
        baseline_types = set(tuple(row) for row in rows["baseline_note_types"])
        result = {}
        for name, (sql, params) in queries.items():
            if name.startswith("combined"):
                counts, types = {}, set()
                for deck, note_type, total in rows[name]:
                    if total:
                        counts[deck] = counts.get(deck, 0) + int(total)
                    types.add((deck, note_type))
                parity = counts == baseline_counts and types == baseline_types
            elif name == "count_visible_join":
                parity = dict(rows[name]) == baseline_counts
            elif name == "note_types_visible_join":
                parity = set(tuple(row) for row in rows[name]) == baseline_types
            else:
                parity = True
            plan = "\n".join(row[0] for row in connection.exec_driver_sql("EXPLAIN ANALYZE " + sql, params))
            result[name] = {**summary(durations[name]), "rows": len(rows[name]),
                            "payload_parity": parity, "explain_analyze": plan,
                            "sql_shape": sql.replace(placeholders, "<live deck ids>")}
            print(json.dumps({"variant": name, **{key: value for key, value in result[name].items()
                              if key not in {"explain_analyze", "sql_shape"}}}), flush=True)
    return {"user_id": user_id, "read_only": True, "repetitions": repetitions,
            "queries": result, "passed": all(row["payload_parity"] for row in result.values())}


class QuietHandler(WSGIRequestHandler):
    def log(self, _type, _message, *args):
        pass


def run(arguments):
    url = local_url(arguments.env_file.resolve())
    source_paths = ["app/services/flashcards_share_service.py", "app/services/share/publish.py",
                    "app/repositories/flashcards_share_repository.py", "app/services/share/helpers.py",
                    "app/services/deck_publish_index.py"]
    source_before = {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_paths}
    app = create_audit_app({
        "SQLALCHEMY_DATABASE_URI": url.render_as_string(hide_password=False),
        "REDIS_URL": "", "RATE_LIMIT_DAILY_ENABLED": False,
        "SESSION_COOKIE_SECURE": False,
    })
    # Audit bootstrap deliberately omits HTTP routes. Attach the same routes as
    # wsgi.py without invoking the normal factory's startup maintenance.
    register_blueprints(app)
    state = {"queries": [], "capture": False}

    def readonly_connection(connection, _record):
        with connection.cursor() as cursor:
            cursor.execute("SET SESSION TRANSACTION READ ONLY")

    def before(_conn, _cursor, statement, parameters, context, _many):
        verb = statement.lstrip().split(None, 1)[0].upper()
        if verb not in {"SELECT", "SHOW", "EXPLAIN"}:
            raise RuntimeError(f"Benchmark refused SQL verb {verb}")
        context._publish_bench_started = time.perf_counter()

    def after(_conn, _cursor, statement, parameters, context, _many):
        if state["capture"]:
            state["queries"].append({
                "statement": statement, "parameters": parameters,
                "cursor_ms": (time.perf_counter() - context._publish_bench_started) * 1000,
            })

    with app.app_context():
        engine = db.engine
        event.listen(engine, "connect", readonly_connection)
        event.listen(engine, "before_cursor_execute", before)
        event.listen(engine, "after_cursor_execute", after)
        with engine.connect() as connection:
            server_info = connection.execute(text(
                "SELECT VERSION() AS version, @@innodb_buffer_pool_size AS buffer_pool_bytes"
            )).mappings().one()
            top_users = connection.execute(text(
                "SELECT owner_user_id AS user_id, COUNT(*) AS decks FROM decks "
                "WHERE deleted_at IS NULL AND owner_user_id IS NOT NULL "
                "GROUP BY owner_user_id ORDER BY decks DESC LIMIT 3"
            )).mappings().all()
        user_ids = arguments.users or [int(row["user_id"]) for row in top_users]
        if arguments.sql_variants_only:
            result = sql_variants(engine, user_ids[0], arguments.repetitions)
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
            db.session.remove()
            engine.dispose()
            return result["passed"]

    original = flashcards_share_service.build_deck_publish_options

    def timed_service(*, user_id):
        start = time.perf_counter()
        payload = original(user_id=user_id)
        state["service_ms"] = (time.perf_counter() - start) * 1000
        return payload

    # Legacy compatibility shim copied this function during import, so wrap the
    # actual route consumer without changing the implementation or payload.
    from app.services import flashcards_share
    serializer = app.session_interface.get_signing_serializer(app)
    if serializer is None:
        raise RuntimeError("No local session serializer is configured")
    original_shim = flashcards_share.build_deck_publish_options
    flashcards_share.build_deck_publish_options = timed_service
    server = make_server("127.0.0.1", 0, app, request_handler=QuietHandler)
    worker = threading.Thread(target=server.serve_forever, daemon=True)
    worker.start()
    endpoint = f"http://127.0.0.1:{server.server_port}/api/shared/decks/publish-options"
    opener = build_opener(ProxyHandler({}))

    report = {
        "measured_at_utc": datetime.now(timezone.utc).isoformat(),
        "git_head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "code_state": "working_copy",
        "source_sha256": source_before,
        "mysql": {"host": url.host, "database": url.database,
                  "version": server_info["version"],
                  "buffer_pool_MiB": int(server_info["buffer_pool_bytes"]) / 1024**2},
        "runtime": {"python": platform.python_version(), "platform": platform.platform(),
                    "http_server": "isolated single-thread Werkzeug WSGI, loopback",
                    "endpoint": "/api/shared/decks/publish-options"},
        "method": {"warmups": arguments.warmups, "repetitions": arguments.repetitions,
                   "db_transactions_read_only": True, "startup_maintenance": False,
                   "latency_tracemalloc_enabled": False,
                   "first_request_is_cold_buffer_pool": False,
                   "sql_cursor_ms_includes_fetch_and_server_execution": True,
                   "http_ms_includes_auth_json_and_transfer": True},
        "users": [],
    }
    try:
        for user_id in user_ids:
            with app.app_context():
                parents = dict(db.session.execute(text(
                    "SELECT id, parent_id FROM decks WHERE owner_user_id=:uid AND deleted_at IS NULL"
                ), {"uid": user_id}).all())
                cards = int(db.session.execute(text(
                    "SELECT COUNT(*) FROM cards JOIN notes ON cards.note_id=notes.id WHERE notes.user_id=:uid"
                ), {"uid": user_id}).scalar_one())
                depths, cycle_paths = [], 0
                for root in parents:
                    node, seen = root, set()
                    while node in parents and node not in seen:
                        seen.add(node)
                        node = parents[node]
                    cycle_paths += int(node in seen)
                    depths.append(len(seen))
                db.session.remove()
            cookie = serializer.dumps({"_user_id": str(user_id), "_fresh": True})
            request = Request(endpoint, headers={
                "Cookie": f"{app.config['SESSION_COOKIE_NAME']}={cookie}",
                "Accept": "application/json",
            })
            samples, hashes, profile = [], set(), []
            for iteration in range(arguments.warmups + arguments.repetitions):
                state["queries"], state["capture"], state["service_ms"] = [], True, None
                started = time.perf_counter()
                with opener.open(request, timeout=60) as response:
                    body = response.read()
                    status = response.status
                elapsed = (time.perf_counter() - started) * 1000
                state["capture"] = False
                payload = json.loads(body)
                if status != 200 or not isinstance(payload.get("items"), list):
                    raise RuntimeError(f"Unexpected endpoint response for user {user_id}")
                hashes.add(digest(payload))
                sample = {"http_ms": elapsed, "service_ms": state["service_ms"],
                          "sql_cursor_ms": sum(q["cursor_ms"] for q in state["queries"]),
                          "sql_statements": len(state["queries"])}
                if iteration == 0:
                    first = sample
                if iteration >= arguments.warmups:
                    samples.append(sample)
                profile = list(state["queries"])

            # Measure allocations separately; tracing overhead is excluded from
            # every HTTP latency sample above.
            with app.app_context():
                db.session.remove()
                tracemalloc.start()
                memory_payload = original(user_id=user_id)
                peak_mib = tracemalloc.get_traced_memory()[1] / 1024**2
                tracemalloc.stop()
                db.session.remove()
                modular_payload = modular_publish.build_deck_publish_options(user_id=user_id)
                db.session.remove()
                explains = []
                with engine.connect() as connection:
                    for query in profile:
                        sql = query["statement"]
                        lowered = sql.lower()
                        if not any(token in lowered for token in ("count(", "group by", "distinct")):
                            continue
                        plan = connection.exec_driver_sql("EXPLAIN FORMAT=JSON " + sql, query["parameters"]).scalar_one()
                        explains.append({"sql": sql, "plan": json.loads(plan)})

            result = {
                "user_id": user_id, "live_decks": len(parents), "owned_cards": cards,
                "max_depth_nodes": max(depths, default=0), "subtree_id_entries": sum(depths),
                "paths_entering_cycle": cycle_paths,
                "first_http_request_ms": round(first["http_ms"], 3),
                "first_request": {key: round(value, 3) for key, value in first.items()},
                "warm_http": summary([s["http_ms"] for s in samples]),
                "warm_service": summary([s["service_ms"] for s in samples]),
                "warm_sql_cursor": summary([s["sql_cursor_ms"] for s in samples]),
                "sql_statements_range": [min(s["sql_statements"] for s in samples), max(s["sql_statements"] for s in samples)],
                "service_peak_allocations_MiB": round(peak_mib, 3),
                "payload_bytes": len(body), "stable_payload": len(hashes) == 1,
                "payload_sha256": next(iter(hashes)),
                "modular_payload_parity": digest(modular_payload) == digest(memory_payload) == next(iter(hashes)),
                "block_code_counts": dict(Counter(row["block_code"] or "selectable" for row in payload["items"])),
                "last_request_query_profile": [{"sql": q["statement"], "cursor_ms": round(q["cursor_ms"], 3)} for q in profile],
                "explain_json": explains,
                "samples": [{key: round(value, 3) for key, value in sample.items()} for sample in samples],
            }
            report["users"].append(result)
            print(json.dumps({key: value for key, value in result.items() if key not in {"samples", "explain_json", "last_request_query_profile"}}), flush=True)
    finally:
        state["capture"] = False
        flashcards_share.build_deck_publish_options = original_shim
        server.shutdown()
        server.server_close()
        worker.join(timeout=5)
        with app.app_context():
            db.session.remove()
            engine.dispose()
    report["source_unchanged_during_measurement"] = source_before == {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in source_paths
    }
    report["passed"] = report["source_unchanged_during_measurement"] and all(
        user["stable_payload"] and user["modular_payload_parity"] for user in report["users"])
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"passed": report["passed"], "output": str(arguments.output.resolve())}), flush=True)
    return report["passed"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--users", type=int, nargs="+")
    parser.add_argument("--sql-variants-only", action="store_true", help="Compare SQL variants for the first selected user; no HTTP server")
    parser.add_argument("--warmups", type=int, choices=range(1, 11), default=3)
    parser.add_argument("--repetitions", type=int, choices=range(5, 101), default=30)
    parser.add_argument("--output", type=Path, default=ROOT / "output/publish_options_mysql_20261009.json")
    raise SystemExit(0 if run(parser.parse_args()) else 1)
