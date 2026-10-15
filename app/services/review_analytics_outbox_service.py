"""Atomic durable capture and idempotent async application of history revisions.

The learner head serializes commit revisions. Workers never acquire learner or
domain locks after that head; source rows are not replayed or hydrated. Readers
retain their existing applied/source equality and fall back while lagging.
"""

from collections import defaultdict
from contextlib import contextmanager
from datetime import datetime, timezone
import hashlib
import json

from sqlalchemy.orm import Session

from app.repositories import review_analytics_outbox_repository as repository
from app.repositories.review_analytics_repository import add_grouped_deltas, lock_generations, lock_head
from app.services.review_analytics_policy import passed_count_for_policy, policy_from_generation
from models.review_analytics import BUILDING, DIRTY, READY
from models.review_analytics_outbox import ReviewAnalyticsOutbox

PAYLOAD_VERSION = "review-outbox-v1"
MAX_PAYLOAD_BYTES = 2097152
WORKER_PAYLOAD_BUDGET = 524288


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _document(payload):
    encoded = json.dumps(payload, ensure_ascii=True, allow_nan=False,
                         sort_keys=True, separators=(",", ":")).encode("utf-8")
    if not 2 <= len(encoded) <= MAX_PAYLOAD_BYTES:
        raise ValueError("History outbox payload exceeds the bounded transaction contract.")
    return len(encoded), hashlib.sha256(encoded).digest()


def _envelope(*, user_id, source_revision, version, events, event_count, dirty, created_at):
    return {"user_id": int(user_id), "source_revision": int(source_revision), "version": version,
            "events": events, "event_count": int(event_count), "dirty": bool(dirty),
            "created_at": created_at.isoformat(timespec="microseconds")}


def stage_review_analytics_outbox(session, *, user_id, source_revision, rows, dirty, now_utc=None):
    """Stage one immutable revision snapshot inside the source transaction."""
    events = [{"id": int(row.id), "reviewed_at": row.reviewed_at.isoformat(timespec="microseconds"),
        "deck_id": int(row.deck_id) if row.deck_id is not None else None,
        "duration_ms": int(row.duration_ms) if row.duration_ms is not None else None,
        "rating": row.rating, "passed_sql": int(row.passed or 0)} for row in rows]
    created_at = now_utc or _utcnow()
    size, digest = _document(_envelope(user_id=user_id, source_revision=source_revision,
        version=PAYLOAD_VERSION, events=events, event_count=len(events), dirty=dirty, created_at=created_at))
    repository.insert_outbox_revision(session, {"user_id": int(user_id), "source_revision": int(source_revision),
        "payload_version": PAYLOAD_VERSION, "events_payload": events, "payload_size": size, "payload_hash": digest,
        "event_count": len(events), "is_dirty": bool(dirty), "created_at": created_at,
        "applied_at": None, "last_error_code": None})


def invalidate_generation(generation, reason):
    generation.status = DIRTY
    generation.verified_source_revision = None
    generation.verification_contract_version = None
    generation.verified_at = None
    generation.last_error_code = reason


def _decode(row):
    if row.payload_version != PAYLOAD_VERSION or not isinstance(row.events_payload, list):
        raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
    size, digest = _document(_envelope(user_id=row.user_id, source_revision=row.source_revision,
        version=row.payload_version, events=row.events_payload, event_count=row.event_count,
        dirty=row.is_dirty, created_at=row.created_at))
    if size != row.payload_size or digest != bytes(row.payload_hash) or len(row.events_payload) != row.event_count:
        raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
    events, identities = [], set()
    for value in row.events_payload:
        if not isinstance(value, dict) or set(value) != {"id", "reviewed_at", "deck_id", "duration_ms", "rating", "passed_sql"}:
            raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
        if type(value["id"]) is not int or value["id"] <= 0 or value["id"] in identities:
            raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
        if value["deck_id"] is not None and (type(value["deck_id"]) is not int or value["deck_id"] <= 0):
            raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
        if value["duration_ms"] is not None and type(value["duration_ms"]) is not int:
            raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
        if type(value["passed_sql"]) is not int or value["passed_sql"] not in (0, 1) \
                or not isinstance(value["rating"], str) or len(value["rating"]) > 20:
            raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
        moment = datetime.fromisoformat(value["reviewed_at"])
        if moment.tzinfo is not None:
            raise ValueError("OUTBOX_PAYLOAD_CORRUPT")
        identities.add(value["id"])
        events.append({**value, "reviewed_at": moment})
    return events


def _deltas(events, generation, dialect_name):
    policy = policy_from_generation(generation)
    deltas = defaultdict(lambda: [0, 0, 0])
    for event in events:
        # Per-learner commit revision is the sole coverage checkpoint. Global
        # event IDs may have been reserved before another transaction commits.
        day = policy.study_day(event["reviewed_at"])
        vector = (1, max(int(event["duration_ms"] or 0), 0),
                  passed_count_for_policy(policy, event["rating"], event["passed_sql"], dialect_name))
        keys = [(0, 0, day)]
        if event["deck_id"] is not None:
            keys.append((1, event["deck_id"], day))
        for key in keys:
            for index, value in enumerate(vector):
                deltas[key][index] += value
    return {key: tuple(vector) for key, vector in deltas.items()}


@contextmanager
def _fresh_session(session_factory=None):
    if session_factory is None:
        from models import db
        session = Session(bind=db.engine, expire_on_commit=False)
    else:
        session = session_factory()
    if session.in_transaction() or session.new or session.dirty or session.deleted:
        raise RuntimeError("History outbox requires a fresh worker Session.")
    try:
        yield session
    finally:
        session.close()


def _limit(value):
    if type(value) is not int or not 1 <= value <= 100:
        raise ValueError("Outbox limit must be an integer between 1 and 100.")
    return value


def pending_review_analytics_outbox_users(*, limit=100, session_factory=None):
    with _fresh_session(session_factory) as session:
        return repository.pending_user_ids(session, limit=_limit(limit))


def process_review_analytics_outbox(*, user_id, limit=100, session_factory=None):
    """Apply pending revisions in one fresh, head-serialized transaction.

    Bound work by 100 revisions and 512 KiB of envelope data. The first single
    revision may use its admitted 2 MiB cap so a large revision can make progress.
    """
    if type(user_id) is not int or user_id <= 0:
        raise ValueError("Outbox user_id must be a positive integer.")
    limit = _limit(limit)
    report = {"ok": True, "user_id": user_id, "applied_revisions": [], "pending": False,
              "invalidated_generations": 0, "payload_bytes": 0, "error": None}
    with _fresh_session(session_factory) as session, session.begin():
        # No learner/User or domain locks may be acquired after this head lock.
        head = lock_head(session, user_id, create=False)
        if head is None:
            return report
        generations = lock_generations(session, user_id, [head.active_generation, head.building_generation])
        after_revision = 0
        for _ in range(limit):
            row = repository.next_pending_revision(session, user_id=user_id, after_revision=after_revision)
            if row is None:
                break
            revision = int(row.source_revision)
            if report["applied_revisions"] and report["payload_bytes"] + row.payload_size > WORKER_PAYLOAD_BUDGET:
                break
            after_revision = revision
            error = "OUTBOX_REVISION_AHEAD" if revision > int(head.source_revision) else None
            try:
                events = _decode(row) if error is None else []
            except (ValueError, TypeError, OverflowError):
                error, events = "OUTBOX_PAYLOAD_CORRUPT", []
            for generation in generations:
                if generation.status not in (BUILDING, READY):
                    continue
                covered = int(generation.applied_source_revision) if generation.applied_source_revision is not None else -1
                if revision <= covered:
                    continue
                reason = error or ("OUTBOX_REVISION_GAP" if revision != covered + 1 else None)
                reason = reason or ("SOURCE_INVALIDATED" if row.is_dirty else None)
                if reason:
                    invalidate_generation(generation, reason)
                    report["invalidated_generations"] += 1
                    if reason != "SOURCE_INVALIDATED":
                        report.update(ok=False, error=reason)
                    continue
                try:
                    deltas = _deltas(events, generation, session.get_bind().dialect.name)
                except (ValueError, TypeError, OverflowError):
                    invalidate_generation(generation, "OUTBOX_POLICY_INVALID")
                    report["invalidated_generations"] += 1
                    report.update(ok=False, error="OUTBOX_POLICY_INVALID")
                    continue
                add_grouped_deltas(session, user_id, int(generation.generation), deltas)
                generation.applied_source_revision = revision
            row.applied_at = _utcnow()
            row.last_error_code = error or report["error"]
            report["applied_revisions"].append(revision)
            report["payload_bytes"] += int(row.payload_size)
            session.flush()
        report["pending"] = repository.has_pending(session, user_id=user_id)
        if not report["pending"]:
            for generation in generations:
                if generation.status in (BUILDING, READY) and generation.applied_source_revision != head.source_revision:
                    invalidate_generation(generation, "OUTBOX_REVISION_GAP")
                    report["invalidated_generations"] += 1
                    report.update(ok=False, error="OUTBOX_REVISION_GAP")
    return report
