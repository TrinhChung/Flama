"""Measure NOTE review projection cost using only a disposable loopback MySQL DB.

Each variant has equivalent owned content and fresh NEW subjects. Paired rounds
balance randomized execution order to reduce drift; fixture creation and verification are
outside timing. This is a bounded synthetic qualification, not a production SLO.
"""

from __future__ import annotations

import argparse
from contextlib import nullcontext
from datetime import datetime, timedelta, timezone
import json
import os
from pathlib import Path
import re
import random
import secrets
import sys
import threading
import time
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
from app.routes import register_blueprints
from app.services import study_service, deck_count_projection_service
from app.services.review_analytics_backfill_service import run_review_analytics_backfill
from app.services.review_analytics_outbox_service import process_review_analytics_outbox
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.deck import Deck
from models.deck_count_snapshot import DeckCountContentRevision, DeckCountLearnerRevision
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.review_analytics import DailyReviewCount, ReviewAnalyticsGeneration, ReviewAnalyticsHead
from models.review_analytics_outbox import ReviewAnalyticsOutbox
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_subject import StudyProgressSubject
from models.user import User
from scripts.mysql_probe_db import _connection_settings, _database_uri, _source_database_collation
from tests.note_progress_fixtures import decode_note_state, stage_note_state
from tests.study_note_fixtures import attach_template, enroll_note_user

PROBE_NAME = re.compile(r"^flama_review_projection_probe_[0-9]+_[a-f0-9]{12}$")
CASES = ("disabled", "history_only", "both")
FLAGS = {"disabled": (False, False), "history_only": (True, False), "both": (True, True)}
ORDER_SEED = 20261014
NOW = datetime(2026, 10, 14, 12, 0, 0, 987654)
SEED_TIME = NOW.replace(microsecond=0) - timedelta(seconds=1)
STATUS_NAMES = {"Bytes_received", "Bytes_sent", "Innodb_data_written", "Innodb_os_log_written",
                "Innodb_row_lock_waits", "Innodb_row_lock_time", "Innodb_buffer_pool_reads"}


class _FixedClock(datetime):
    @classmethod
    def utcnow(cls):
        return NOW


def _guard_target(settings, name, source_name):
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
        raise RuntimeError("The benchmark requires loopback MySQL.")
    if not PROBE_NAME.fullmatch(name) or name == source_name:
        raise RuntimeError("The benchmark requires a unique generated schema.")


def _round_order(round_number, cases=CASES):
    # Each randomized Latin block puts every mode in every execution position.
    # A fixed recorded seed makes order reproducible, without choosing an order
    # after observing timings. Each round still contains every paired workload.
    block, offset = divmod(round_number, len(cases))
    shuffled = list(cases)
    random.Random(ORDER_SEED + block).shuffle(shuffled)
    return tuple(shuffled[offset:] + shuffled[:offset])


def _percentile(values, percentile):
    ordered = sorted(values)
    if not ordered:
        raise ValueError("A percentile requires samples.")
    position = (len(ordered) - 1) * percentile / 100
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def _distribution(values):
    return {f"p{percentile}_ms": round(_percentile(values, percentile), 3)
            for percentile in (50, 95, 99)}


def _status(admin):
    if admin is None:
        return {}
    with admin.cursor() as cursor:
        cursor.execute("SHOW GLOBAL STATUS")
        return {name: int(value) for name, value in cursor.fetchall() if name in STATUS_NAMES}


def _flags(app, case):
    history, deck = FLAGS[case]
    app.config.update(REVIEW_ANALYTICS_WRITE_ENABLED=history, DECK_COUNT_WRITE_ENABLED=deck)


def _seed(app, count, cases=CASES, *, suffix=""):
    fixtures = {}
    app.config.update(REVIEW_ANALYTICS_WRITE_ENABLED=False, DECK_COUNT_WRITE_ENABLED=False)
    with app.app_context():
        for case in cases:
            user = User(username=f"projection-{case}{suffix}", email=f"{case}{suffix}@projection.invalid", timezone="UTC")
            db.session.add(user)
            db.session.flush()
            enroll_note_user(db.session, user)
            deck = Deck(name="Projection benchmark", owner_user_id=user.id)
            note_type = NoteType(name="Projection benchmark", user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            word_field = FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0)
            db.session.add(word_field)
            db.session.flush()
            # Two presentations share one NOTE state, as in canonical retry fixtures.
            for index in range(2):
                attach_template(db.session, note_type_id=note_type.id, owner_user_id=user.id,
                    name=f"Card {index}", front_html="{{Word}}", back_html="{{Word}}", is_default=index == 0)
            note_ids, card_ids = [], []
            for _ in range(count):
                note = Note(user_id=user.id, note_type_id=note_type.id, deck_id=deck.id,
                            field_values_by_id={str(word_field.id): "synthetic"},
                            field_values_codec="field-id.v1", field_values_extras={},
                            created_at=SEED_TIME, updated_at=SEED_TIME)
                db.session.add(note)
                db.session.flush()
                stage_note_state(db.session, user_id=user.id, note_id=note.id, now=SEED_TIME, queue="new")
                presentations = Card.query.filter_by(note_id=note.id).order_by(Card.template_id).all()
                if len(presentations) != 2:
                    raise RuntimeError("Synthetic NOTE must have two presentations.")
                note_ids.append(str(note.id))
                card_ids.append(str(presentations[0].id))
            fixtures[case] = {"user_id": int(user.id), "deck_id": int(deck.id),
                              "note_ids": note_ids, "card_ids": card_ids}
        db.session.commit()
        # Backfill/readiness is outside measured commands and only done for covered writers.
        for case in (case for case in cases if FLAGS[case][0]):
            _flags(app, case)
            outcome = run_review_analytics_backfill(user_id=fixtures[case]["user_id"], writer_coverage_enabled=True)
            if outcome.get("status") != "READY":
                raise RuntimeError("Synthetic analytics generation did not become READY.")
        db.session.remove()
    return fixtures


def _parity(app, fixtures, count):
    evidence = {}
    app.config.update(REVIEW_ANALYTICS_WRITE_ENABLED=False, DECK_COUNT_WRITE_ENABLED=False)
    with app.app_context():
        if DeckCountContentRevision.query.count() != 0:
            raise RuntimeError("NOTE review unexpectedly invalidated global content.")
        semantic_by_case = []
        for case, fixture in fixtures.items():
            user_id, deck_id = fixture["user_id"], fixture["deck_id"]
            receipts = StudyAuthorityCommandReceipt.query.filter_by(learner_user_id=user_id).all()
            facts = StudyProgressHistoryFact.query.filter_by(learner_user_id=user_id).filter(
                StudyProgressHistoryFact.review_event_id.isnot(None)).all()
            subjects = StudyProgressSubject.query.filter_by(learner_user_id=user_id).all()
            raw_events = ReviewEvent.query.filter_by(user_id=user_id).all()
            event_count = len(raw_events)
            canonical_event_times = all(row.reviewed_at.microsecond == 0
                and row.reviewed_at == NOW.replace(microsecond=0) for row in raw_events)
            if not canonical_event_times:
                raise RuntimeError("Native NOTE command did not normalize fractional input to canonical seconds.")
            audit_count = AuditLog.query.filter_by(user_id=user_id, action="study.answer").count()
            links = {row.review_event_id for row in receipts} == {row.review_event_id for row in facts}
            hashes = all(len(bytes(row.response_payload_hash)) == 32 and len(bytes(row.after_state_hash)) == 32
                         for row in receipts) and all(len(bytes(row.fact_payload_hash)) == 32 for row in facts)
            state_valid = all(row.authority_revision == 1 and decode_note_state(row) is not None for row in subjects)
            if not (len(receipts) == len(facts) == len(subjects) == event_count == audit_count == count
                    and links and hashes and state_valid):
                raise RuntimeError(f"Exactly-once NOTE evidence failed in {case}.")
            subject_by_note = {str(row.live_note_id): row for row in subjects}
            semantic_by_case.append([bytes(subject_by_note[note_id].semantic_state_hash).hex()
                                     for note_id in fixture["note_ids"]])
            bucket_totals = db.session.execute(sa.select(
                sa.func.coalesce(sa.func.sum(DailyReviewCount.review_event_count), 0),
                sa.func.coalesce(sa.func.sum(DailyReviewCount.positive_duration_ms), 0),
                sa.func.coalesce(sa.func.sum(DailyReviewCount.passed_review_count), 0)
            ).where(DailyReviewCount.user_id == user_id, DailyReviewCount.scope_kind == 0)).one()
            head = db.session.get(ReviewAnalyticsHead, user_id)
            revision = db.session.get(DeckCountLearnerRevision, (user_id, deck_id))
            expected_history = (count, count * 100, count) if FLAGS[case][0] else (0, 0, 0)
            expected_revision = count if FLAGS[case][1] else 0
            if tuple(bucket_totals) != expected_history or (int(revision.revision) if revision else 0) != expected_revision:
                raise RuntimeError(f"Projection counters failed in {case}.")
            if (int(head.source_revision) if head else 0) != (count if FLAGS[case][0] else 0):
                raise RuntimeError(f"History revision failed in {case}.")
            evidence[case] = {"events": event_count, "facts": len(facts), "receipts": len(receipts),
                "audits": audit_count, "authority_revision_per_subject": 1,
                "linked_event_ids_match": links, "binary_hashes_present": hashes,
                "state_codec_verified": state_valid, "fractional_native_input_normalized": canonical_event_times, "collection_daily_totals": [int(value) for value in bucket_totals],
                "deck_learner_revision": expected_revision,
                "receipt_payload_bytes": sum(row.response_payload_size for row in receipts),
                "history_fact_payload_bytes": sum(row.fact_payload_size for row in facts)}
        # Logical state excludes entity/event identity, so feature flags cannot change it.
        if any(hashes != semantic_by_case[0] for hashes in semantic_by_case[1:]):
            raise RuntimeError("Projection flags changed canonical semantic NOTE state.")
        db.session.remove()
    return {"exactly_once_and_projection_parity": True, "semantic_hashes_equal_across_cases": True,
            "global_content_revision_rows": 0, "cases": evidence}


def _benchmark(app, *, samples, warmup, admin=None, profile_spans=False):
    # Audit bootstrap suppresses all mutating startup tasks and HTTP routes.
    # Add the unchanged canonical handlers only after the generated DB is bound.
    if "flashcards" not in app.blueprints:
        register_blueprints(app)
    cases = CASES
    fixtures = _seed(app, samples + warmup, cases)
    clients = {}
    for case, fixture in fixtures.items():
        client = app.test_client()
        with client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(fixture["user_id"]), True
        clients[case] = client
    measured = {case: [] for case in cases}
    active = {}
    original_command, original_commit = study_service.execute_native_review_command, Session.commit
    original_finalizer, original_flush = study_service.flush_review_analytics_deltas, Session.flush
    original_deck_bump = deck_count_projection_service.bump_learner_revisions

    def command(*args, **kwargs):
        started = time.perf_counter()
        active["in_command"] = True
        try:
            return original_command(*args, **kwargs)
        finally:
            active["in_command"] = False
            active.setdefault("command_ms", []).append((time.perf_counter() - started) * 1000)

    def finalizer(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_finalizer(*args, **kwargs)
        finally:
            active["finalizer_ms"] = (time.perf_counter() - started) * 1000

    def deck_bump(*args, **kwargs):
        started = time.perf_counter()
        try:
            return original_deck_bump(*args, **kwargs)
        finally:
            if active.get("in_command"):
                active["deck_revision_ms"] += (time.perf_counter() - started) * 1000

    def flush(session, *args, **kwargs):
        started = time.perf_counter()
        try:
            return original_flush(session, *args, **kwargs)
        finally:
            if active.get("in_command"):
                active["flush_count"] += 1
                active["flush_total_ms"] += (time.perf_counter() - started) * 1000

    def commit(session):
        started = time.perf_counter()
        try:
            return original_commit(session)
        finally:
            active.setdefault("session_commit_ms", []).append((time.perf_counter() - started) * 1000)

    def capture(_conn, _cursor, statement, _parameters, _context, _many):
        active["sql_statements"] += 1
        normalized = statement.lstrip().upper()
        active["locking_reads"] += int("FOR UPDATE" in normalized or "LOCK IN SHARE MODE" in normalized)
        active["dml_statements"] += int(normalized.startswith(("INSERT ", "UPDATE ", "DELETE ")))
        if profile_spans:
            _context._flama_review_benchmark_started = time.perf_counter()
            _context._flama_review_benchmark_in_command = active.get("in_command", False)

    def after_capture(_conn, _cursor, statement, _parameters, context, _many):
        if getattr(context, "_flama_review_benchmark_in_command", False):
            active["command_sql_detail"].append({"sql": " ".join(statement.split())[:700],
                "elapsed_ms": (time.perf_counter() - context._flama_review_benchmark_started) * 1000})

    with app.app_context():
        engine = db.engine
    sa.event.listen(engine, "before_cursor_execute", capture)
    if profile_spans:
        sa.event.listen(engine, "after_cursor_execute", after_capture)
    try:
        with patch.object(study_service, "execute_native_review_command", side_effect=command), \
                patch.object(Session, "commit", commit), \
                patch.object(study_service, "flush_review_analytics_deltas", side_effect=finalizer) if profile_spans else nullcontext(), \
                patch.object(Session, "flush", flush) if profile_spans else nullcontext(), \
                patch.object(deck_count_projection_service, "bump_learner_revisions", deck_bump) if profile_spans else nullcontext(), \
                patch("app.routes.flashcards.study.datetime", _FixedClock):
            for round_number in range(samples + warmup):
                for case in _round_order(round_number, cases):
                    _flags(app, case)
                    fixture = fixtures[case]
                    active.clear()
                    active.update(sql_statements=0, locking_reads=0, dml_statements=0,
                                  finalizer_ms=0, deck_revision_ms=0, flush_count=0, flush_total_ms=0, command_sql_detail=[])
                    before = _status(admin) if round_number >= warmup else {}
                    started = time.perf_counter()
                    response = clients[case].post(f"/api/study/{fixture['card_ids'][round_number]}/answer", json={
                        "rating": "good", "operation_key": str(uuid4()), "duration_ms": 100,
                        "scope": "deck", "scope_id": fixture["deck_id"]})
                    api_ms = (time.perf_counter() - started) * 1000
                    after = _status(admin) if round_number >= warmup else {}
                    body = response.get_json()
                    if response.status_code != 200 or body.get("authority", {}).get("mode") != "NOTE" \
                            or body["authority"]["replayed"] or body["authority"]["authority_revision"] != 1:
                        raise RuntimeError(f"Canonical NOTE answer failed in {case}: HTTP {response.status_code}.")
                    if len(active.get("command_ms", [])) != 1 or len(active.get("session_commit_ms", [])) != 1:
                        raise RuntimeError("Expected one native NOTE command and outer commit per API call.")
                    if round_number >= warmup:
                        measured[case].append({"round": round_number - warmup, "api_ms": api_ms,
                            "command_ms": active["command_ms"][0],
                            "session_commit_ms": active["session_commit_ms"][0],
                            **{key: active[key] for key in ("sql_statements", "locking_reads", "dml_statements")},
                            **({key: active[key] for key in ("finalizer_ms", "deck_revision_ms", "flush_count", "flush_total_ms", "command_sql_detail")}
                               if profile_spans else {}),
                            "global_status_delta": {key: after[key] - before[key] for key in before}})
    finally:
        sa.event.remove(engine, "before_cursor_execute", capture)
        if profile_spans:
            sa.event.remove(engine, "after_cursor_execute", after_capture)

    async_evidence = {}
    for case in (case for case in cases if FLAGS[case][0]):
        _flags(app, case)
        user_id = fixtures[case]["user_id"]
        app.config.update(REVIEW_ANALYTICS_READ_MODE="raw", ANALYTICS_REQUIRE_READY_USER_IDS=[])
        raw = clients[case].get("/api/statistics/overview?year=2026")
        if raw.status_code != 200:
            raise RuntimeError("Async NOTE raw overview failed before worker.")
        app.config.update(REVIEW_ANALYTICS_READ_MODE="summary", ANALYTICS_REQUIRE_READY_USER_IDS=[user_id])
        pending = clients[case].get("/api/statistics/overview?year=2026")
        if pending.status_code != 409:
            raise RuntimeError("Lagging async NOTE strict summary must return HTTP 409.")
        with app.app_context():
            db.session.remove()
            queued = ReviewAnalyticsOutbox.query.filter_by(user_id=user_id, applied_at=None).all()
            pending_count = len(queued)
            queued_created = [row.created_at for row in queued]
            generation = db.session.get(ReviewAnalyticsGeneration, (user_id, 1))
            if pending_count != samples + warmup or generation.applied_source_revision != 0:
                raise RuntimeError("Async NOTE fixture must remain unapplied until explicit worker drain.")
            db.session.remove()
            started = time.perf_counter()
            worker_reports = []
            while True:
                worker = process_review_analytics_outbox(user_id=user_id)
                worker_reports.append(worker)
                if not worker["ok"] or not worker["pending"]:
                    break
            worker_ms = (time.perf_counter() - started) * 1000
            completed = datetime.now(timezone.utc).replace(tzinfo=None)
        if not worker["ok"] or worker["pending"] or sum(len(part["applied_revisions"]) for part in worker_reports) != samples + warmup:
            raise RuntimeError("Bounded async NOTE worker did not drain its independent fixture.")
        ready = clients[case].get("/api/statistics/overview?year=2026")
        if ready.status_code != 200 or ready.get_json() != raw.get_json():
            raise RuntimeError("Async NOTE overview must match exact raw output after worker.")
        async_evidence[case] = {"pending_rows_before_worker": pending_count,
            "strict_summary_before_worker_http": pending.status_code,
            "strict_summary_after_worker_http": ready.status_code,
            "post_worker_raw_summary_exact_parity": True, "worker_reports": worker_reports,
            "worker_transaction_ms": round(worker_ms, 3),
            "intentionally_held_feed_age_ms": _distribution([(completed - moment).total_seconds() * 1000
                                                             for moment in queued_created]),
            "lag_scope": "Explicit one-shot drain after measured answers; backlog was intentionally held. No timer or production lag SLO qualification."}
    app.config.update(REVIEW_ANALYTICS_READ_MODE="raw", ANALYTICS_REQUIRE_READY_USER_IDS=[])

    metrics = {}
    for case, rows in measured.items():
        metrics[case] = {"history_write_enabled": FLAGS[case][0], "deck_write_enabled": FLAGS[case][1],
            "history_writer": "durable_outbox" if FLAGS[case][0] else "disabled",
            "samples": len(rows), **{key: _distribution([row[key] for row in rows])
                for key in ("command_ms", "session_commit_ms", "api_ms")},
            "sql_statement_count": sorted({row["sql_statements"] for row in rows}),
            "locking_read_count": sorted({row["locking_reads"] for row in rows}),
            "dml_statement_count": sorted({row["dml_statements"] for row in rows}),
            "global_status_delta_total": {key: sum(row["global_status_delta"].get(key, 0) for row in rows)
                for key in sorted(STATUS_NAMES) if any(key in row["global_status_delta"] for row in rows)},
            "samples_detail": [{key: round(value, 3) if isinstance(value, float) else value
                                for key, value in row.items()} for row in rows]}
        if profile_spans:
            metrics[case]["diagnostic_spans"] = {key: _distribution([row[key] for row in rows])
                for key in ("finalizer_ms", "deck_revision_ms", "flush_total_ms")}
            metrics[case]["diagnostic_spans"]["command_sql_total_ms"] = _distribution([
                sum(statement["elapsed_ms"] for statement in row["command_sql_detail"]) for row in rows])
    baseline = metrics["disabled"]["command_ms"]["p95_ms"]
    for case, metric in metrics.items():
        added = metric["command_ms"]["p95_ms"] - baseline
        percent = added / baseline * 100
        paired = [row["command_ms"] - control["command_ms"]
                  for row, control in zip(measured[case], measured["disabled"])]
        metric["command_p95_added_ms"] = round(added, 3)
        metric["command_p95_added_percent"] = round(percent, 3)
        metric["paired_command_delta_ms"] = _distribution(paired)
        metric["b8_synthetic_budget_met"] = added <= 5 and percent <= 10
    return {"metrics": metrics, "parity": _parity(app, fixtures, samples + warmup),
        "async_worker_evidence": async_evidence,
        "diagnostic_spans_enabled": profile_spans,
        "order_protocol": {"kind": "randomized balanced Latin blocks", "seed": ORDER_SEED, "block_size": len(cases)},
        "sample_order": [list(_round_order(index, cases)) for index in range(warmup, samples + warmup)],
        "warmup_per_case": warmup, "samples_per_case": samples,
        "clock_contract": {"input_utc": NOW.isoformat(timespec="microseconds"), "fixture_created_utc": SEED_TIME.isoformat(),
            "native_command_normalizes_to_seconds": True,
            "evidence": "execute_native_review_command passes reviewed_at.replace(microsecond=0); every persisted fixture event verified against that canonical timestamp."},
        "b8_budget": {"metric": "native NOTE command including analytics finalization and outer commit",
                      "p95_added_ms_max": 5, "p95_added_percent_max": 10},
        "timing_scope": {"command_ms": "Canonical execute_native_review_command; includes locks, scheduler, facts, receipts, projections, commit.",
            "session_commit_ms": "Session.commit only; history counters are finalized before this, so this is not the B8 gate.",
            "api_ms": "Flask test-client POST /api/study/<id>/answer including real next-card prefetch; excludes network/proxy."},
        "limitations": [f"Synthetic sequential owned-deck learner workload; {len(cases)} independent equivalent learners, one active at a time.",
            "Fresh NEW Note per answer, two presentations per Note; fixed clock and legacy default scheduler; no installed clones.",
            "Warm local MySQL/Flask process; no concurrent learners, cold-cache qualification or production SLO claim.",
            "Global status deltas include observer queries and any unrelated server traffic; not per-command byte/lock attribution.",
            "Schema created from ORM metadata; migration-chain validation is a separate qualification.",
            "Forecast uses the deck revision hook and does not synchronously rebuild buckets on review."]}


def _worker_lag_probe(app, *, count=30, interval_seconds=1):
    """Exercise a one-second local worker loop concurrently with real NOTE POSTs.

    Completion uses worker transaction commit return, not its pre-commit marker.
    This models the unit's inactive interval; systemd/production scheduling is
    outside this disposable fixture's claim.
    """
    fixtures = _seed(app, count, cases=("both",), suffix="-lag")
    _flags(app, "both")
    fixture = fixtures["both"]
    user_id = fixture["user_id"]
    client = app.test_client()
    with client.session_transaction() as login:
        login["_user_id"], login["_fresh"] = str(user_id), True
    stop = threading.Event()
    completion, reports, failures = {}, [], []

    def worker_loop():
        try:
            while not stop.wait(interval_seconds):
                with app.app_context():
                    started = time.perf_counter()
                    result = process_review_analytics_outbox(user_id=user_id)
                    completed_at = datetime.now(timezone.utc).replace(tzinfo=None)
                    reports.append({"transaction_ms": (time.perf_counter() - started) * 1000, **result})
                    for revision in result["applied_revisions"]:
                        completion[revision] = completed_at
                    if not result["ok"]:
                        raise RuntimeError("One-second worker loop failed.")
        except Exception as error:
            failures.append(type(error).__name__)
            stop.set()

    thread = threading.Thread(target=worker_loop, name="review-analytics-local-lag", daemon=True)
    started = time.perf_counter()
    thread.start()
    try:
        with patch("app.routes.flashcards.study.datetime", _FixedClock):
            for card_id in fixture["card_ids"]:
                response = client.post(f"/api/study/{card_id}/answer", json={"rating": "good",
                    "operation_key": str(uuid4()), "duration_ms": 100,
                    "scope": "deck", "scope_id": fixture["deck_id"]})
                if response.status_code != 200:
                    raise RuntimeError("Concurrent worker NOTE answer failed.")
        deadline = time.monotonic() + 10
        while len(completion) != count and time.monotonic() < deadline and not failures:
            stop.wait(0.05)
        if failures or len(completion) != count:
            raise RuntimeError("One-second worker did not cover every committed NOTE revision.")
    finally:
        stop.set()
        thread.join(timeout=10)
    if thread.is_alive():
        raise RuntimeError("Local worker loop did not stop.")
    with app.app_context():
        db.session.remove()
        rows = ReviewAnalyticsOutbox.query.filter_by(user_id=user_id).all()
        lags = [(completion[row.source_revision] - row.created_at).total_seconds() * 1000 for row in rows]
        head = db.session.get(ReviewAnalyticsHead, user_id)
        generation = db.session.get(ReviewAnalyticsGeneration, (user_id, 1))
        if len(rows) != count or any(row.applied_at is None for row in rows) \
                or head.source_revision != count or generation.applied_source_revision != count:
            raise RuntimeError("Concurrent worker coverage is incomplete.")
        counters = db.session.execute(sa.select(sa.func.sum(DailyReviewCount.review_event_count)).where(
            DailyReviewCount.user_id == user_id, DailyReviewCount.scope_kind == 0)).scalar_one()
        if counters != count:
            raise RuntimeError("Concurrent worker did not apply exact history counts.")
        db.session.remove()
    app.config.update(REVIEW_ANALYTICS_READ_MODE="raw", ANALYTICS_REQUIRE_READY_USER_IDS=[])
    raw = client.get("/api/statistics/overview?year=2026")
    app.config.update(REVIEW_ANALYTICS_READ_MODE="summary", ANALYTICS_REQUIRE_READY_USER_IDS=[user_id])
    summary = client.get("/api/statistics/overview?year=2026")
    if raw.status_code != 200 or summary.status_code != 200 or raw.get_json() != summary.get_json():
        raise RuntimeError("Concurrent worker raw/summary parity failed.")
    return {"samples": count, "worker_inactive_interval_seconds": interval_seconds,
        "source_feed_created_to_worker_commit_ms": _distribution(lags), "max_lag_ms": round(max(lags), 3),
        "local_p95_two_second_budget_met": _percentile(lags, 95) <= 2000,
        "worker_transactions": reports, "elapsed_seconds": round(time.perf_counter() - started, 3),
        "exact_counter_and_revision_coverage": True, "post_worker_raw_summary_exact_parity": True,
        "limitations": "One local learner with sequential NOTE POSTs and a concurrent one-second worker loop; no deployed systemd timer, concurrent learner load, or production lag SLO claim."}


def run(env_file=ROOT / ".env", *, samples=240, warmup=6, profile_spans=False):
    if not 20 <= samples <= 500 or not 1 <= warmup <= 10:
        raise ValueError("Use 20..500 samples per case and 1..10 warmup rounds.")
    if samples % len(CASES) or warmup % len(CASES):
        raise ValueError("Samples and warmup must contain complete balanced execution-order blocks.")
    load_dotenv(env_file, override=False)
    settings = _connection_settings()
    source_name = os.getenv("DB_NAME", "").strip()
    name = f"flama_review_projection_probe_{os.getpid()}_{secrets.token_hex(6)}"
    _guard_target(settings, name, source_name)
    admin = pymysql.connect(**settings)
    app, created = None, False
    report = {"status": "FAIL", "configured_database_modified": False, "generated_schema": name}
    started = time.monotonic()
    try:
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute("SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
            if cursor.fetchone():
                raise RuntimeError("Generated benchmark schema already exists; refusing overwrite.")
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
            cursor.execute("SELECT VERSION(), @@innodb_buffer_pool_size, @@transaction_isolation")
            version, pool_size, isolation = cursor.fetchone()
            report.update(mysql_version=version, innodb_buffer_pool_bytes=int(pool_size), transaction_isolation=isolation)
        app = create_audit_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
            "WTF_CSRF_ENABLED": False, "REDIS_URL": "", "REVIEW_ANALYTICS_WRITE_ENABLED": False,
            "DECK_COUNT_WRITE_ENABLED": False, "DECK_COUNT_READ_MODE": "raw", "FORECAST_SUMMARY_READ_MODE": "raw",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})
        with app.app_context():
            if db.engine.url.database != name:
                raise RuntimeError("Benchmark engine is not bound to generated schema.")
            db.create_all()
        report.update(_benchmark(app, samples=samples, warmup=warmup, admin=admin,
                                 profile_spans=profile_spans))
        report["local_worker_lag_evidence"] = _worker_lag_probe(app)
        report["status"] = "PASS"
        report["all_enabled_cases_meet_b8_synthetic_budget"] = all(
            metric["b8_synthetic_budget_met"] for case, metric in report["metrics"].items() if case != "disabled")
        return report
    except Exception as error:
        report["error_type"] = type(error).__name__
        if isinstance(error, (RuntimeError, ValueError)):
            report["error"] = str(error)
        return report
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            _guard_target(settings, name, os.getenv("DB_NAME", "").strip())
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
                cursor.execute("SELECT COUNT(*) FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (name,))
                if cursor.fetchone()[0]:
                    raise RuntimeError("Generated benchmark schema cleanup failed.")
            report["probe_database_dropped"] = True
        admin.close()
        report["elapsed_seconds"] = round(time.monotonic() - started, 3)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--samples", type=int, default=240)
    parser.add_argument("--warmup", type=int, default=6)
    parser.add_argument("--profile-spans", action="store_true", help="Diagnostic SQL/finalizer/flush timing; retain separate evidence from acceptance benchmarks.")
    args = parser.parse_args()
    try:
        report = run(args.env_file, samples=args.samples, warmup=args.warmup,
                     profile_spans=args.profile_spans)
    except Exception as error:
        # Driver errors can embed credentials; detailed traces stay local.
        report = {"status": "FAIL", "error_type": type(error).__name__, "configured_database_modified": False}
        if isinstance(error, (RuntimeError, ValueError)):
            report["error"] = str(error)
    serialized = json.dumps(report, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(serialized + "\n", encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in ("status", "error_type", "error", "samples_per_case",
        "all_enabled_cases_meet_b8_synthetic_budget", "probe_database_dropped", "elapsed_seconds")}))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
