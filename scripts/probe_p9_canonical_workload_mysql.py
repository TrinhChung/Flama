"""Replay a NOTE workload on a restored production dump after the P9-06 switch.

The P9-06 postflight only counted surviving ``card_progress`` rows. This
probe restores a pre-switch dump into a generated LOCAL database, measures the
learners' readers under ``PROJECTION_V1``, applies the same one-way switch as
production, measures the readers again, then runs writes through the real
HTTP/MCP entrypoints with a SQL trace: a v4 session open/commit on owned and
installed decks, direct REST and MCP answers, a new Note studied after the
switch and a deck progress reset. It reports every statement that names
``card_progress`` (DELETE is lifecycle cleanup and reported separately), the
canonical read audit of each learner, the integrity checks of the restore
rehearsal and the reader A/B. The generated database is dropped in ``finally``;
DB_NAME is never touched.

    python scripts/probe_p9_canonical_workload_mysql.py --backup output/p9-restore/pre-p906.sql.gz \
        --output output/p9-restore/canonical-workload.json
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import statistics
import sys
import time
from uuid import uuid4

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from sqlalchemy import event as sql_event

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.probe_p9_backup_restore_mysql import inspect_dump, restore_dump, validate_target  # noqa: E402
from scripts.probe_phase4_shadow_schema_mysql import (  # noqa: E402
    _connection_settings, _database_uri, _source_database_collation,
)

CARD_PROGRESS = re.compile(r"\bcard_progress\b", re.IGNORECASE)
READ_RUNS = 3
INTEGRITY = {
    "state_token_mismatches": (
        "SELECT COUNT(*) FROM study_progress_states s LEFT JOIN study_progress_subjects p ON p.id=s.subject_id "
        "LEFT JOIN study_authority_subject_tokens t ON t.subject_id=s.subject_id WHERE p.id IS NULL OR "
        "t.subject_id IS NULL OR s.subject_generation<>p.subject_generation OR "
        "t.subject_generation<>s.subject_generation OR NOT (t.semantic_state_hash <=> s.semantic_state_hash)"),
    "availability_mismatches": (
        "SELECT COUNT(*) FROM study_progress_contributors c LEFT JOIN study_progress_availability a "
        "ON a.contributor_id=c.id LEFT JOIN study_progress_states s ON s.subject_id=c.subject_id "
        "WHERE c.contributor_status='ACTIVE' AND (a.contributor_id IS NULL OR s.subject_id IS NULL OR "
        "a.subject_generation<>s.subject_generation OR a.semantic_state_hash<>s.semantic_state_hash)"),
    "receipt_orphans": (
        "SELECT COUNT(*) FROM study_authority_command_receipts r LEFT JOIN review_events e "
        "ON e.id=r.review_event_id LEFT JOIN study_progress_history_facts h ON h.id=r.history_fact_id "
        "WHERE (r.review_event_id IS NOT NULL AND e.id IS NULL) OR "
        "(r.history_fact_id IS NOT NULL AND h.id IS NULL)"),
}
PROJECTION_FINGERPRINT = (
    "SELECT COUNT(*), COALESCE(SUM(revision), 0), COALESCE(SUM(CRC32(CONCAT_WS('|', id, card_id, "
    "queue, due_day, interval_days, reps, lapses, updated_at))), 0), MAX(updated_at) FROM card_progress"
)


class _Trace:
    def __init__(self, engine):
        self.engine = engine
        self.step = "setup"
        self.statements = Counter()
        self.card_progress = Counter()

    def __enter__(self):
        sql_event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *_exc):
        sql_event.remove(self.engine, "before_cursor_execute", self._on)

    def _on(self, _conn, _cursor, statement, *_args):
        self.statements[self.step] += 1
        if CARD_PROGRESS.search(statement):
            self.card_progress[(self.step, statement.split()[0].upper())] += 1


def _probe_app(uri: str):
    from app import create_app

    url = sa.engine.make_url(uri)
    if url.host not in {"localhost", "127.0.0.1", "::1"} or not (url.database or "").startswith("flama_p9_restore_"):
        raise ValueError("The workload probe requires a generated local restore database.")
    return create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": uri,
        "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
        "REDIS_URL": "", "STUDY_QUEUE_NAMESPACE": "",
        "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": True,
        "STUDY_WIRE_V4_ENABLED": True, "STUDY_NEW_LEARNER_NOTE_ENABLED": True,
        "STUDY_NOTE_COUNT_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False,
    })


def _client(app, user_id: int):
    client = app.test_client()
    with client.session_transaction() as login:
        login["_user_id"], login["_fresh"] = str(user_id), True
    return client


def _scalar(app, sql: str, **params):
    from models import db

    with app.app_context():
        try:
            return db.session.execute(sa.text(sql), params).scalar()
        finally:
            db.session.rollback()


def _rows(app, sql: str, **params):
    from models import db

    with app.app_context():
        try:
            return [tuple(row) for row in db.session.execute(sa.text(sql), params).all()]
        finally:
            db.session.rollback()


def _learners(app) -> dict[str, int]:
    owned = _rows(app, """
        SELECT e.user_id FROM review_events e LEFT JOIN deck_installs i ON i.user_id = e.user_id
        WHERE i.id IS NULL GROUP BY e.user_id ORDER BY COUNT(*) DESC LIMIT 1""")
    installed = _rows(app, """
        SELECT e.user_id FROM review_events e JOIN deck_installs i ON i.user_id = e.user_id
        GROUP BY e.user_id ORDER BY COUNT(*) DESC LIMIT 1""")
    return {"owned": int(owned[0][0]), "installed": int(installed[0][0])}


def _open_v4(client, deck_id: int, note_type_id: str | None = None):
    groups = client.get(f"/api/study/scopes/deck/{deck_id}/compositions")
    compositions = [
        item["composition_id"] for item in (groups.get_json() or {}).get("compositions", [])
        if note_type_id is None or f"notetype:{note_type_id}:" in item["composition_id"]
    ] if groups.status_code == 200 else []
    if not compositions:
        return None
    response = client.post("/api/study/sessions", json={
        "scope": "deck", "scope_id": deck_id,
        "composition_id": compositions[0],
        "accepted_session_schema_versions": ["study-session.v4"],
        "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
    })
    return response.get_json() if response.status_code == 201 else None


def _study_deck(app, client, user_id: int, *, minimum_cards: int = 30):
    """The learner's most recently studied deck whose v4 open has enough Cards."""

    for (deck_id,) in _rows(app, """
            SELECT CAST(scope_id AS UNSIGNED) FROM study_sessions
            WHERE user_id = :user_id AND scope_type = 'deck'
            GROUP BY scope_id ORDER BY MAX(opened_at) DESC LIMIT 30""", user_id=user_id):
        snapshot = _open_v4(client, int(deck_id))
        if snapshot is not None and len(snapshot["cards"]) >= minimum_cards:
            return int(deck_id), snapshot
    raise RuntimeError(f"No studied deck of learner {user_id} opens a v4 session.")


def _commit_events(snapshot: dict, cards: list[dict]) -> dict:
    events = []
    for sequence, card in enumerate(cards, start=1):
        policy = snapshot["policies"][card["policy_key"]]
        event_id = str(uuid4())
        events.append({
            "event_id": event_id, "sequence": sequence, "card_id": card["card_id"], "rating": "good",
            "policy_key": card["policy_key"], "scheduler_offset_ms": 2000 * sequence, "duration_ms": 3000,
            "action_key": "review.good", "action_contract_version": "1",
            "trigger_key": "scheduler.review.good", "trigger_contract_version": "1",
            "algorithm_key": snapshot["scheduler_algorithm"], "algorithm_version": snapshot["algorithm_version"],
            "config_schema_version": policy["config_schema_version"], "config_hash": policy["config_hash"],
            "study_session_id": snapshot["session_id"], "operation_key": event_id,
            **{key: value for key, value in card["authority_pin"].items() if key != "schema_version"},
        })
    return {"schema_version": "study-commit.v3", "commit_id": str(uuid4()),
            "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
            "commit_reason": "rollover", "events": events, "final_states": []}


def _pick_cards(snapshot: dict, count: int) -> list[dict]:
    cards = sorted(snapshot["cards"], key=lambda card: card["state"].get("type") != "new")
    return cards[:count]


def _read_urls(deck_id: int) -> tuple[tuple[str, str], ...]:
    return (
        ("dashboard", "/api/dashboard"),
        ("overview", "/api/statistics/overview?year=2026&timezone=Asia/Tokyo"),
        ("study_next", f"/api/study/next?scope=deck&scope_id={deck_id}"),
        ("browse_tree", "/api/browse/decks/tree"),
        ("browse_cards", f"/api/browse/cards?deck_id={deck_id}&page=1&per_page=50"),
    )


def _measure_reads(app, learners: dict[str, int], decks: dict[str, int]) -> dict:
    result: dict = {}
    for role, user_id in learners.items():
        client = _client(app, user_id)
        for label, url in _read_urls(decks[role]):
            client.get(url)  # warm-up
            samples, statuses = [], set()
            for _ in range(READ_RUNS):
                started = time.perf_counter()
                statuses.add(client.get(url).status_code)
                samples.append(time.perf_counter() - started)
            result[f"{role}.{label}"] = {"statuses": sorted(statuses),
                                         "seconds_median": round(statistics.median(samples), 4),
                                         "seconds_max": round(max(samples), 4)}
    return result


def _read_audit(app, user_id: int) -> dict:
    output = app.test_cli_runner().invoke(args=["study-authority-read-audit", "--user-id", str(user_id)])
    try:
        payload = json.loads(output.output.strip().splitlines()[-1])
    except (IndexError, json.JSONDecodeError):
        return {"status": "ERROR", "output": output.output[-500:]}
    return {key: payload.get(key) for key in (
        "status", "storage_profile", "compared_with_projection", "card_count", "mismatches", "canonical")}


def _workload(app, trace: _Trace, learners: dict[str, int], decks: dict[str, int], report: dict) -> None:
    from app.services.mcp import study_tools
    from models import db

    steps = report["workload"] = {}

    def step(name, fn):
        trace.step = name
        started = time.perf_counter()
        try:
            outcome = fn()
        except Exception as exc:  # recorded, the probe keeps going
            outcome = {"error": f"{type(exc).__name__}: {exc}"[:300]}
        steps[name] = {"outcome": outcome, "seconds": round(time.perf_counter() - started, 3)}
        trace.step = "between"

    for role, user_id in learners.items():
        client = _client(app, user_id)
        trace.step = f"{role}.open"
        snapshot = _open_v4(client, decks[role])
        trace.step = "between"
        steps[f"{role}.open"] = {"cards": len(snapshot["cards"]) if snapshot else None}
        chosen = _pick_cards(snapshot, min(20, len(snapshot["cards"]) - 5))
        payload = _commit_events(snapshot, chosen)
        step(f"{role}.commit_{len(chosen)}", lambda: client.post(
            f"/api/study/sessions/{snapshot['session_id']}/commit", json=payload).status_code)
        others = [card["card_id"] for card in snapshot["cards"] if card not in chosen]
        step(f"{role}.direct_3", lambda: [client.post(f"/api/study/{card_id}/answer", json={
            "rating": "good", "operation_key": str(uuid4()), "duration_ms": 900,
            "scope": "deck", "scope_id": decks[role]}).status_code for card_id in others[:3]])

        def mcp_reviews(user_id=user_id, cards=others[3:5]):
            with app.app_context():
                try:
                    return [bool(study_tools.submit_review(user_id=user_id, card_id=card_id, rating="good",
                                                           operation_key=str(uuid4()))) for card_id in cards]
                finally:
                    db.session.remove()

        if role == "owned":  # MCP reviews only the learner's own Cards, never overlay source Cards.
            step(f"{role}.mcp_2", mcp_reviews)

    owner = learners["owned"]
    client = _client(app, owner)
    # A single-NoteType deck whose fields are all plain text, so the API accepts made-up values.
    target = _rows(app, """
        SELECT n.deck_id, MIN(n.note_type_id) FROM notes n
        WHERE n.user_id = :user_id AND n.deck_id IS NOT NULL
        GROUP BY n.deck_id HAVING COUNT(DISTINCT n.note_type_id) = 1 AND COUNT(*) BETWEEN 5 AND 400
           AND MIN(n.note_type_id) IN (
               SELECT t.id FROM note_types t WHERE t.user_id = :user_id AND NOT EXISTS (
                   SELECT 1 FROM field_defs f WHERE f.note_type_id = t.id AND f.field_type <> 'text'))
        ORDER BY COUNT(*) DESC LIMIT 1""", user_id=owner)
    if target:
        deck_id, note_type_id = int(target[0][0]), str(target[0][1])
        field_names = [row[0] for row in _rows(app, "SELECT name FROM field_defs WHERE note_type_id = :id "
                                               "ORDER BY position", id=note_type_id)]

        def create_and_study():
            created = client.post("/api/notes", json={
                "note_type_id": note_type_id, "deck_id": deck_id,
                "field_values": {name: f"p9 workload {name}" for name in field_names}})
            if created.status_code != 201:
                return {"create": created.status_code, "body": str(created.get_json())[:200]}
            note_id = created.get_json().get("id") or created.get_json().get("note", {}).get("id")
            opened = _open_v4(client, deck_id, note_type_id)
            new_cards = [card for card in (opened or {}).get("cards", []) if card["note_id"] == note_id]
            committed = client.post(f"/api/study/sessions/{opened['session_id']}/commit",
                                    json=_commit_events(opened, new_cards[:1])) if new_cards else None
            return {"create": 201, "note_in_snapshot": bool(new_cards),
                    "commit": committed.status_code if committed is not None else None}

        step("owned.new_note_studied", create_and_study)
        steps["owned.new_note_studied"]["deck_id"] = deck_id
    reset_deck = _rows(app, """
        SELECT n.deck_id FROM notes n JOIN cards c ON c.note_id = n.id
        JOIN study_progress_subjects s ON s.learner_user_id = :user_id AND s.live_note_id = n.id
        WHERE n.user_id = :user_id AND n.deck_id <> :studied
        GROUP BY n.deck_id HAVING COUNT(*) BETWEEN 3 AND 60 ORDER BY COUNT(*) DESC LIMIT 1""",
                       user_id=owner, studied=decks["owned"])
    if reset_deck:
        step("owned.deck_reset", lambda: client.post(f"/api/decks/{int(reset_deck[0][0])}/progress-reset").status_code)
        steps["owned.deck_reset"]["deck_id"] = int(reset_deck[0][0])
    for role, user_id in learners.items():
        reader = _client(app, user_id)
        step(f"{role}.reads_after", lambda reader=reader, role=role: {
            label: reader.get(url).status_code for label, url in _read_urls(decks[role])})


def run(backup: Path, *, mysql_binary: str) -> dict:
    load_dotenv(ROOT / ".env")
    settings = _connection_settings()
    target = f"flama_p9_restore_{os.getpid()}_{secrets.token_hex(4)}"
    validate_target(settings, target)
    executable = shutil.which(mysql_binary)
    if not executable:
        raise ValueError("mysql client executable is required")
    report: dict = {"schema_version": "p9-canonical-workload.v1", **inspect_dump(backup),
                    "observed_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                    "configured_database_modified": False}
    admin = pymysql.connect(**settings)
    created = False
    app = None
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{target}` CHARACTER SET utf8mb4 "
                           f"COLLATE {_source_database_collation(admin)}")
            created = True
        report["restore_seconds"] = restore_dump(settings, target, backup, executable)
        app = _probe_app(_database_uri(settings, target))
        from app.services.study_storage_profile_service import apply_storage_profile_switch
        from models import db

        learners = _learners(app)
        decks = {}
        for role, user_id in learners.items():
            deck_id, _snapshot = _study_deck(app, _client(app, user_id), user_id)
            decks[role] = deck_id
        report.update({"learners": learners, "decks": decks})
        report["reads_projection_v1"] = _measure_reads(app, learners, decks)
        report["projection_before"] = list(_rows(app, PROJECTION_FINGERPRINT)[0])
        with app.app_context():
            report["switch"] = apply_storage_profile_switch(db.session, now_utc=datetime.utcnow())
            db.session.commit()
        report["reads_canonical_v1"] = _measure_reads(app, learners, decks)
        with app.app_context():
            engine = db.engine
        with _Trace(engine) as trace:
            _workload(app, trace, learners, decks, report)
        report["statements_by_step"] = dict(trace.statements)
        report["card_progress_statements"] = {f"{step}:{verb}": count
                                              for (step, verb), count in sorted(trace.card_progress.items())}
        writes = sum(count for (_step, verb), count in trace.card_progress.items() if verb in {"INSERT", "UPDATE"})
        reads = sum(count for (_step, verb), count in trace.card_progress.items() if verb == "SELECT")
        report["projection_after"] = list(_rows(app, PROJECTION_FINGERPRINT)[0])
        report["projection_rows_written_since_switch"] = int(_scalar(
            app, "SELECT COUNT(*) FROM card_progress WHERE updated_at >= :t0",
            t0=report["switch"]["switched_at_utc"].rstrip("Z").replace("T", " ")))
        report["canonical_contributors"] = int(_scalar(
            app, "SELECT COUNT(*) FROM study_progress_contributors WHERE evidence_kind = 'CANONICAL'"))
        report["integrity"] = {name: int(_scalar(app, sql)) for name, sql in INTEGRITY.items()}
        report["read_audit"] = {role: _read_audit(app, user_id) for role, user_id in learners.items()}
        report["status"] = "PASS" if (
            writes == 0 and reads == 0
            and report["projection_rows_written_since_switch"] == 0
            and not any(report["integrity"].values())
            and all(audit.get("status") == "PASS" and audit.get("compared_with_projection") is False
                    for audit in report["read_audit"].values())
            and not any("error" in str(step.get("outcome")) for step in report["workload"].values())
        ) else "FAIL"
        report["card_progress_writes"] = writes
        report["card_progress_reads"] = reads
        return report
    finally:
        if app is not None:
            from models import db

            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            validate_target(settings, target)
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{target}`")
            report["probe_database_removed"] = True
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--mysql-binary", default="mysql")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run(args.backup, mysql_binary=args.mysql_binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=1, sort_keys=True, default=str), encoding="utf-8")
    print(json.dumps({key: result.get(key) for key in (
        "status", "card_progress_writes", "card_progress_reads", "projection_rows_written_since_switch",
        "integrity", "probe_database_removed")}, indent=1, default=str))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
