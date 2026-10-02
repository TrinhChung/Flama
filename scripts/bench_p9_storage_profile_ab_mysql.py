"""A/B the NOTE storage profiles on disposable local MySQL (P9-C evidence).

Runs the same seeded workload under ``PROJECTION_V1`` (NOTE writes still
maintain the ``card_progress`` projection) and ``CANONICAL_V1`` (ADR P9-03:
no projection), each run on its own generated database: first session open
(pristine materialization), a 50-answer v4 commit, direct REST answers, a
second open, then the dashboard/overview/queue readers. For every step it
records wall time, SQL statements, statements that name ``card_progress`` and
rows written per table (INSERT/UPDATE/DELETE ``rowcount``). Profiles are
interleaved run by run; the summary reports medians. Flags match production
(wire v4, new learner NOTE, Note counts, shadow write on; async batch off).

Only a generated local database is created and dropped; the configured
application database is untouched.

    python scripts/bench_p9_storage_profile_ab_mysql.py --notes 2000 --runs 3
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import statistics
import subprocess
import sys
import time
from uuid import uuid4

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from sqlalchemy import event as sql_event

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from app.services.study_storage_profile_service import apply_storage_profile_switch  # noqa: E402
from models import db  # noqa: E402
from scripts.bench_p5_session_open_mysql import _seed, _seed_overlay  # noqa: E402
from scripts.probe_p5_concurrency_mysql import _client, _commit_payload  # noqa: E402
from scripts.probe_phase4_shadow_schema_mysql import (  # noqa: E402
    _connection_settings, _database_uri, _source_database_collation,
)

PROFILES = ("PROJECTION_V1", "CANONICAL_V1")
PROBE_NAME_PATTERN = re.compile(r"^flama_p9_ab_probe_[0-9]+_[a-f0-9]{8}$")
CARD_PROGRESS = re.compile(r"\bcard_progress\b", re.IGNORECASE)
WRITE_VERBS = {"INSERT", "UPDATE", "DELETE"}


def _ab_app(uri: str):
    url = sa.engine.make_url(uri)
    if (
        url.get_backend_name() != "mysql"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not PROBE_NAME_PATTERN.fullmatch(url.database or "")
    ):
        raise ValueError("The A/B bench requires a generated local MySQL database.")
    return create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": uri,
        "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
        "REDIS_URL": "", "STUDY_QUEUE_NAMESPACE": "",
        "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": True,
        "STUDY_WIRE_V4_ENABLED": True, "STUDY_NEW_LEARNER_NOTE_ENABLED": True,
        "STUDY_NOTE_COUNT_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False,
    })


def _statement_table(verb: str, words: list[str]) -> str:
    keyword = {"INSERT": "INTO", "UPDATE": "UPDATE", "DELETE": "FROM"}.get(verb, "FROM")
    upper = [word.upper() for word in words]
    if keyword in upper:
        index = upper.index(keyword)
        if index + 1 < len(words):
            return words[index + 1].strip("`")
    return ""


class _Counter:
    """Statements, ``card_progress`` statements and rows written, per table."""

    def __init__(self, engine):
        self.engine = engine
        self.statements = 0
        self.card_progress = Counter()
        self.rows_written = Counter()

    def __enter__(self):
        sql_event.listen(self.engine, "after_cursor_execute", self._on)
        return self

    def __exit__(self, *_exc):
        sql_event.remove(self.engine, "after_cursor_execute", self._on)

    def _on(self, _conn, cursor, statement, _params, _context, _many):
        self.statements += 1
        words = statement.split()
        verb = words[0].upper() if words else "?"
        if CARD_PROGRESS.search(statement):
            self.card_progress[verb] += 1
        if verb in WRITE_VERBS and cursor.rowcount and cursor.rowcount > 0:
            self.rows_written[_statement_table(verb, words)] += int(cursor.rowcount)


def _measure(app, report: dict, name: str, fn):
    with app.app_context():
        engine = db.engine
    with _Counter(engine) as counter:
        started = time.perf_counter()
        status = fn()
        elapsed = time.perf_counter() - started
    report[name] = {
        "status": status,
        "seconds": round(elapsed, 4),
        "statements": counter.statements,
        "card_progress_statements": dict(counter.card_progress),
        "rows_written": sum(counter.rows_written.values()),
        "rows_written_by_table": dict(counter.rows_written.most_common()),
    }


def _one_run(*, profile: str, notes: int, answers: int, direct: int, child_decks: int, overlay: int) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p9_ab_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("The A/B bench requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"profile": profile}
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
        app = _ab_app(_database_uri(settings, name))
        learner = _seed(app, notes=notes, child_decks=child_decks)
        if profile == "CANONICAL_V1":
            with app.app_context():
                apply_storage_profile_switch(db.session, now_utc=datetime.utcnow())
                db.session.commit()
        client = _client(app, learner["user_id"])
        open_body = {
            "scope": "deck", "scope_id": learner["deck_id"], "composition_id": learner["composition_id"],
            "accepted_session_schema_versions": ["study-session.v4"],
            "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
        }
        snapshots = []

        def open_session():
            response = client.post("/api/study/sessions", json=open_body)
            snapshots.append(response.get_json())
            report.setdefault("snapshot_bytes", len(response.data))
            return response.status_code

        _measure(app, report, "open_first", open_session)
        snapshot = snapshots[-1]
        payload = _commit_payload(snapshot, answers)
        committed = {event["card_id"] for event in payload["events"]}
        _measure(app, report, f"commit_{answers}", lambda: client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit", json=payload).status_code)
        direct_cards = [
            card["card_id"] for card in snapshot["cards"]
            if card["state"].get("type") == "new" and card["card_id"] not in committed
        ][:direct]

        def answer_directly():
            statuses = Counter()
            for card_id in direct_cards:
                statuses[client.post(f"/api/study/{card_id}/answer", json={
                    "rating": "good", "operation_key": str(uuid4()), "duration_ms": 400,
                    "scope": "deck", "scope_id": learner["deck_id"],
                }).status_code] += 1
            return dict(statuses)

        _measure(app, report, f"direct_{len(direct_cards)}", answer_directly)
        _measure(app, report, "open_second", open_session)
        if overlay:
            local_deck_id = _seed_overlay(app, learner, overlay)
            groups = client.get(f"/api/study/scopes/deck/{local_deck_id}/compositions").get_json()
            overlay_body = {**open_body, "scope_id": local_deck_id,
                            "composition_id": groups["compositions"][0]["composition_id"]}
            overlay_snapshots = []

            def open_overlay():
                response = client.post("/api/study/sessions", json=overlay_body)
                overlay_snapshots.append(response.get_json())
                return response.status_code

            _measure(app, report, "overlay_open_first", open_overlay)
            overlay_payload = _commit_payload(overlay_snapshots[-1], answers)
            _measure(app, report, f"overlay_commit_{len(overlay_payload['events'])}", lambda: client.post(
                f"/api/study/sessions/{overlay_snapshots[-1]['session_id']}/commit",
                json=overlay_payload).status_code)
        deck = learner["deck_id"]
        for label, url in (
            ("dashboard", "/api/dashboard"),
            ("overview", "/api/statistics/overview?year=2026&timezone=Asia/Tokyo"),
            ("study_next", f"/api/study/next?scope=deck&scope_id={deck}"),
            ("stats_today_future", "/api/statistics/today-future?timezone=Asia/Tokyo"),
        ):
            _measure(app, report, label, lambda url=url: client.get(url).status_code)
        with app.app_context():
            report["card_progress_rows"] = int(db.session.execute(
                sa.text("SELECT COUNT(*) FROM card_progress")).scalar_one())
            report["canonical_contributors"] = int(db.session.execute(sa.text(
                "SELECT COUNT(*) FROM study_progress_contributors WHERE evidence_kind = 'CANONICAL'"
            )).scalar_one())
            db.session.rollback()
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
        admin.close()
    return report


def _source_commit() -> str | None:
    """HEAD of the measured checkout, marked when the working tree differs."""

    try:
        head = subprocess.run(["git", "-C", str(ROOT_DIR), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT_DIR), "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return None
    return f"{head}+dirty" if dirty else head


def _summary(runs: list[dict]) -> dict:
    by_profile: dict[str, list[dict]] = defaultdict(list)
    for run in runs:
        by_profile[run["profile"]].append(run)
    steps = [key for key, value in runs[0].items() if isinstance(value, dict) and "seconds" in value]
    summary: dict = {}
    for step in steps:
        row: dict = {}
        for profile in PROFILES:
            samples = [run[step] for run in by_profile.get(profile, []) if step in run]
            if not samples:
                continue
            row[profile] = {
                "seconds_median": round(statistics.median(s["seconds"] for s in samples), 4),
                "seconds_max": max(s["seconds"] for s in samples),
                "statements_median": statistics.median(s["statements"] for s in samples),
                "rows_written_median": statistics.median(s["rows_written"] for s in samples),
                "card_progress_statements_max": max(
                    sum(s["card_progress_statements"].values()) for s in samples),
            }
        if len(row) == 2:
            old, new = row["PROJECTION_V1"], row["CANONICAL_V1"]

            def change(key):
                return None if not old[key] else round((new[key] - old[key]) / old[key] * 100, 1)

            row["change_pct"] = {
                "seconds": change("seconds_median"),
                "statements": change("statements_median"),
                "rows_written": change("rows_written_median"),
            }
        summary[step] = row
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notes", type=int, default=2000)
    parser.add_argument("--answers", type=int, default=50)
    parser.add_argument("--direct", type=int, default=20)
    parser.add_argument("--runs", type=int, default=3)
    parser.add_argument("--child-decks", type=int, default=1,
                        help="Owned Notes are spread over this many child decks of the opened root.")
    parser.add_argument("--overlay", type=int, default=0,
                        help="Also open and commit a session on an installed overlay deck of this many Notes.")
    parser.add_argument("--profiles", default=",".join(PROFILES),
                        help="Comma-separated profiles to run (a pre-P9 baseline checkout runs PROJECTION_V1).")
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()
    profiles = [value for value in args.profiles.split(",") if value]
    if not profiles or set(profiles) - set(PROFILES):
        parser.error(f"--profiles must name {', '.join(PROFILES)}")
    runs = []
    for _ in range(args.runs):
        for profile in profiles:
            runs.append(_one_run(profile=profile, notes=args.notes, answers=args.answers, direct=args.direct,
                                 child_decks=args.child_decks, overlay=args.overlay))
    result = {
        "measured_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
        "notes": args.notes, "answers": args.answers, "direct": args.direct, "runs": args.runs,
        "child_decks": args.child_decks, "overlay": args.overlay, "profiles": profiles,
        "source_commit": _source_commit(),
        "summary": _summary(runs), "samples": runs,
    }
    text = json.dumps(result, indent=1)
    if args.output is not None:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(text, encoding="utf-8")
    print(json.dumps({"summary": result["summary"]}, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
