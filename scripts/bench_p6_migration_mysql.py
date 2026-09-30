"""Measure migration 46 and the Phase 6 backfill at production scale on MySQL.

The deploy runs ``flask db upgrade`` while the previous release still serves
requests. This bench seeds a disposable head-45 database at roughly production
size, keeps an "old release" writer running (review events, new Notes with
Cards, Connect ref updates) during the upgrade and during
``study-phase6-attribution-backfill``, and reports how long each step took,
the writer's worst statement latency, and whether any row was lost or left
unattributed. Only a generated local database is created and dropped.

    python scripts/bench_p6_migration_mysql.py --notes 20000 --events 130000 --refs 16000
"""

from __future__ import annotations

import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import random
import secrets
import sys
import threading
import time

from dotenv import load_dotenv
from flask_migrate import stamp, upgrade
import pymysql

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app.services.study_note_attribution_service import backfill_phase6_attribution
from models import db
from scripts.probe_p6_application_schema_mysql import (
    PROBE_NAME_PATTERN, _exec, _probe_app, _reconstruct_head_45,
)
from scripts.probe_phase4_shadow_schema_mysql import (
    _connection_settings, _database_uri, _source_database_collation,
)

NOTE_TYPES = 9
LEARNERS = 50
_CHUNK = 2000


def _insert_many(sql: str, rows: list[dict]) -> None:
    for start in range(0, len(rows), _CHUNK):
        _exec_many(sql, rows[start:start + _CHUNK])


def _exec_many(sql: str, rows: list[dict]) -> None:
    import sqlalchemy as sa

    db.session.execute(sa.text(sql), rows)
    db.session.commit()


def _seed(notes: int, events: int, refs: int) -> dict:
    from sqlalchemy import insert

    from models.deck import Deck
    from models.note_type import NoteType
    from models.user import User

    now = datetime(2026, 9, 30, 12, 0, 0)
    # ORM bulk inserts apply model defaults without the flush-time seams.
    db.session.execute(insert(User), [
        {"id": index, "username": f"bench{index}", "email": f"bench{index}@example.test"}
        for index in range(1, LEARNERS + 1)
    ])
    db.session.execute(insert(Deck), [
        {"id": index, "name": f"Deck {index}", "owner_user_id": index} for index in range(1, LEARNERS + 1)
    ])
    db.session.execute(insert(NoteType), [
        {"id": f"nt-{index}", "name": f"nt-{index}", "user_id": index + 1} for index in range(NOTE_TYPES)
    ])
    db.session.commit()
    _insert_many("INSERT INTO templates (id, note_type_id, name, front_html, back_html, shared_css, "
                 "position, is_default, created_at, updated_at) VALUES (:id, :nt, :id, '', '', '', "
                 ":position, :is_default, :now, :now)", [
                     {"id": f"t-{index}-{position}", "nt": f"nt-{index}", "position": position,
                      "is_default": position == 0, "now": now}
                     for index in range(NOTE_TYPES) for position in range(2)
                 ])
    note_rows, card_rows = [], []
    for index in range(notes):
        note_type = index % NOTE_TYPES
        user = note_type + 1
        note_rows.append({"id": f"n-{index}", "nt": f"nt-{note_type}", "user": user, "deck": user,
                          "fields": json.dumps({"Word": f"word {index}", "Meaning": "x" * 200}),
                          "now": now})
        for position in range(2):
            card_rows.append({"id": f"c-{index}-{position}", "note": f"n-{index}",
                              "template": f"t-{note_type}-{position}", "now": now})
    _insert_many("INSERT INTO notes (id, note_type_id, user_id, deck_id, field_values, tags, created_at, "
                 "updated_at) VALUES (:id, :nt, :user, :deck, :fields, '[]', :now, :now)", note_rows)
    _insert_many("INSERT INTO cards (id, note_id, template_id, created_at, updated_at) "
                 "VALUES (:id, :note, :template, :now, :now)", card_rows)
    rng = random.Random(46)
    payload = json.dumps({"pad": "p" * 480})
    event_rows = []
    for _index in range(events):
        card = card_rows[rng.randrange(len(card_rows))]["id"] if rng.random() > 0.02 else "gone-card"
        event_rows.append({"user": rng.randint(1, LEARNERS), "card": card, "now": now, "payload": payload})
    _insert_many("INSERT INTO review_events (user_id, card_id, reviewed_at, rating, mode, scheduler_mode, "
                 "review_kind, leeched_after, suspended_after, payload_json, created_at) VALUES "
                 "(:user, :card, :now, 'good', 'review', 'legacy', 'review', 0, 0, :payload, :now)", event_rows)
    _insert_many("INSERT INTO connect_source_card_refs (id, user_id, source_key, external_card_id, "
                 "external_note_id, source_ord, card_id, snapshot_hash, created_at, updated_at) VALUES "
                 "(:id, 1, 'src', :ext, :ext_note, :ord, :card, :hash, :now, :now)", [
                     {"id": f"ref-{index}", "ext": f"ec-{index}", "ext_note": f"en-{index // 2}",
                      "ord": index % 2, "card": card_rows[index % len(card_rows)]["id"],
                      "hash": "h" * 64, "now": now}
                     for index in range(refs)
                 ])
    return {"notes": notes, "cards": len(card_rows), "events": events, "refs": refs}


class OldReleaseWriter(threading.Thread):
    """Writes the way the serving (pre-Phase-6) release does: no new columns."""

    def __init__(self, settings: dict, database: str, notes: int, refs: int, prefix: str):
        super().__init__(daemon=True)
        self.prefix = prefix
        self.connection = pymysql.connect(**{**settings, "database": database, "autocommit": True})
        self.notes, self.refs = notes, refs
        self.stop_event = threading.Event()
        self.latencies: list[float] = []
        self.errors: list[str] = []
        self.events_written = 0
        self.cards_written = 0
        self.rng = random.Random(7)

    def _timed(self, sql: str, params: tuple) -> bool:
        started = time.perf_counter()
        try:
            with self.connection.cursor() as cursor:
                cursor.execute(sql, params)
            return True
        except pymysql.MySQLError as exc:
            self.errors.append(f"{type(exc).__name__}: {exc.args[:2]}")
            return False
        finally:
            self.latencies.append(time.perf_counter() - started)

    def run(self) -> None:
        sequence = 0
        while not self.stop_event.is_set():
            sequence += 1
            now = datetime.utcnow().replace(microsecond=0)
            index = self.rng.randrange(self.notes)
            self.events_written += self._timed(
                "INSERT INTO review_events (user_id, card_id, reviewed_at, rating, mode, scheduler_mode, "
                "review_kind, leeched_after, suspended_after, payload_json, created_at) VALUES "
                "(%s, %s, %s, 'good', 'review', 'legacy', 'review', 0, 0, '{}', %s)",
                (1 + index % LEARNERS, f"c-{index}-0", now, now),
            )
            if sequence % 5 == 0:
                note_type = sequence % NOTE_TYPES
                note_id = f"{self.prefix}-{sequence}"
                self._timed(
                    "INSERT INTO notes (id, note_type_id, user_id, deck_id, field_values, tags, created_at, "
                    "updated_at) VALUES (%s, %s, %s, %s, '{}', '[]', %s, %s)",
                    (note_id, f"nt-{note_type}", note_type + 1, note_type + 1, now, now),
                )
                for position in range(2):
                    self.cards_written += self._timed(
                        "INSERT INTO cards (id, note_id, template_id, created_at, updated_at) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (f"{note_id}-{position}", note_id, f"t-{note_type}-{position}", now, now),
                    )
            if sequence % 3 == 0:
                self._timed(
                    "UPDATE connect_source_card_refs SET review_cursor = %s, updated_at = %s WHERE id = %s",
                    (sequence, now, f"ref-{self.rng.randrange(self.refs)}"),
                )
            time.sleep(0.005)

    def finish(self) -> dict:
        self.stop_event.set()
        self.join(timeout=60)
        self.connection.close()
        ordered = sorted(self.latencies)
        return {
            "statements": len(ordered),
            "max_ms": round(ordered[-1] * 1000, 1) if ordered else None,
            "p99_ms": round(ordered[int(len(ordered) * 0.99) - 1] * 1000, 1) if ordered else None,
            "errors": self.errors[:5],
            "error_count": len(self.errors),
            "events_written": self.events_written,
            "cards_written": self.cards_written,
        }


def _writer_during(settings, database, notes, refs, prefix, operation):
    writer = OldReleaseWriter(settings, database, notes, refs, prefix)
    writer.start()
    time.sleep(0.5)
    started = time.perf_counter()
    try:
        result = operation()
    finally:
        seconds = round(time.perf_counter() - started, 2)
        time.sleep(0.5)
        stats = writer.finish()
    return result, seconds, stats


def run_bench(notes: int, events: int, refs: int) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p6_schema_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("P6 migration bench requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"schema_version": "p6-migration-bench-mysql.v1", "configured_database_modified": False}
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 "
                           f"COLLATE {_source_database_collation(admin)}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        app = _probe_app(_database_uri(settings, name))
        with app.app_context():
            _reconstruct_head_45()
            started = time.perf_counter()
            report["seed"] = _seed(notes, events, refs)
            report["seed_seconds"] = round(time.perf_counter() - started, 1)
            stamp(revision="20260925_000045", directory="migrations")
            db.session.remove()

            _result, seconds, writer = _writer_during(
                settings, name, notes, refs, "wu", lambda: upgrade(directory="migrations")
            )
            report["upgrade"] = {"seconds": seconds, "old_release_writer": writer}
            db.session.remove()
            left = _exec("SELECT COUNT(*) FROM cards WHERE application_id IS NULL").scalar_one()
            report["upgrade"]["cards_left_for_backfill"] = int(left)

            backfill, seconds, writer = _writer_during(
                settings, name, notes, refs, "wb", lambda: backfill_phase6_attribution(apply=True)
            )
            report["backfill"] = {"seconds": seconds, "report": backfill.to_dict(), "old_release_writer": writer}
            # The writer kept going after the backfill: bind its last rows.
            final = backfill_phase6_attribution(apply=True)
            db.session.remove()
            counts = {
                "cards": _exec("SELECT COUNT(*) FROM cards").scalar_one(),
                "cards_unbound": _exec("SELECT COUNT(*) FROM cards WHERE application_id IS NULL").scalar_one(),
                "events": _exec("SELECT COUNT(*) FROM review_events").scalar_one(),
                "events_unattributed_with_card": _exec(
                    "SELECT COUNT(*) FROM review_events e JOIN cards c ON c.id = e.card_id "
                    "WHERE e.note_id IS NULL OR e.note_id <> c.note_id").scalar_one(),
                "refs_wrong_note": _exec(
                    "SELECT COUNT(*) FROM connect_source_card_refs r JOIN cards c ON c.id = r.card_id "
                    "WHERE r.note_id IS NULL OR r.note_id <> c.note_id").scalar_one(),
            }
            report["final"] = {key: int(value) for key, value in counts.items()}
            report["final"]["duplicate_cards"] = final.duplicate_cards
            expected_cards = notes * 2 + report["upgrade"]["old_release_writer"]["cards_written"] \
                + report["backfill"]["old_release_writer"]["cards_written"]
            expected_events = events + report["upgrade"]["old_release_writer"]["events_written"] \
                + report["backfill"]["old_release_writer"]["events_written"]
            problems = []
            if report["final"]["cards"] != expected_cards or report["final"]["events"] != expected_events:
                problems.append("row count changed")
            if report["final"]["cards_unbound"] or report["final"]["events_unattributed_with_card"]:
                problems.append("rows left unattributed")
            if report["final"]["refs_wrong_note"] or final.duplicate_cards:
                problems.append("ref or card attribution inconsistent")
            for step in ("upgrade", "backfill"):
                if report[step]["old_release_writer"]["error_count"]:
                    problems.append(f"old release writes failed during {step}")
            report["problems"] = problems
            report["status"] = "PASS" if not problems else "FAIL"
        return report
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_dropped"] = True
        admin.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--notes", type=int, default=20000)
    parser.add_argument("--events", type=int, default=130000)
    parser.add_argument("--refs", type=int, default=16000)
    args = parser.parse_args()
    outcome = run_bench(args.notes, args.events, args.refs)
    print(json.dumps(outcome, indent=1, sort_keys=True))
    raise SystemExit(0 if outcome.get("status") == "PASS" else 1)
