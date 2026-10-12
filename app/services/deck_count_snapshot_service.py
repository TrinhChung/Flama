"""Owned direct-deck cache reads and optimistic, separately transacted prewarm.

Readers never write or repair a cache. A publisher always stamps the vector
that produced the raw counts, even if domain changes race its final commit.
"""

from contextlib import contextmanager
from dataclasses import dataclass
from dataclasses import replace
from datetime import date, datetime, timezone
import hashlib
import json

from flask import current_app
from sqlalchemy.orm import Session

from app.repositories import deck_count_snapshot_repository as repository
from app.repositories.study_authority_repository import read_study_authority_route
from app.services.anki_scheduler import _day_index_to_datetime
from app.services.deck_aggregation_service import aggregate_deck_study_counts
from app.services.review_analytics_policy import ReviewAnalyticsPolicy, resolve_review_analytics_policy
from models.deck_count_snapshot import CARD_UNIT, DASHBOARD_CONTRACT, NOTE_UNIT


COUNT_IMPLEMENTATION_VERSION = "dashboard-direct-counts.v1"


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo is not None else value


@dataclass(frozen=True)
class _Context:
    user_id: int
    deck_ids: tuple[int, ...]
    policy: ReviewAnalyticsPolicy
    day_index: int
    cutoff: datetime
    unit_code: int
    is_note_mode: bool
    admin_mode: bool
    hashes: dict[int, bytes]


def _owned_eligible_scope(session, user_id, deck_ids):
    rows = repository.owned_scope_rows(session, user_id=user_id, deck_ids=deck_ids)
    by_id = {int(row.id): row for row in rows}
    # Load ancestor metadata in batches, so an unmapped branch under an
    # installed root stays raw even when the caller requested only that branch.
    ancestors = {int(row.parent_id) for row in rows if row.parent_id is not None} - set(by_id)
    while ancestors:
        parents = repository.owned_scope_rows(session, user_id=user_id, deck_ids=ancestors)
        if not parents:
            break
        by_id.update({int(row.id): row for row in parents})
        ancestors = {int(row.parent_id) for row in parents if row.parent_id is not None} - set(by_id)
    overlays = repository.overlay_local_deck_ids(session, by_id)
    resolved = {}
    for row in rows:
        current = int(row.id)
        path = []
        seen = set()
        while current not in resolved:
            if current in seen:
                # The cycle and every branch that reaches it stay raw.
                allowed = False
                break
            seen.add(current)
            path.append(current)
            if current in overlays:
                allowed = False
                break
            metadata = by_id.get(current)
            if metadata is None:
                # Unresolved ownership/ancestor scope is conservatively raw.
                allowed = False
                break
            if metadata.parent_id is None:
                allowed = True
                break
            current = int(metadata.parent_id)
        else:
            allowed = resolved[current]
        # Each ancestor is classified once, without recursive Python calls.
        resolved.update((deck_id, allowed) for deck_id in path)
    return tuple(sorted(int(row.id) for row in rows if resolved[int(row.id)]))


def _context(session, *, user_id, deck_ids, policy, day_index, cutoff,
             is_note_mode, admin_mode, count_by_note, authority_route=None):
    route = authority_route or read_study_authority_route(session, learner_user_id=int(user_id))
    if bool(is_note_mode) != (route.mode_code == "NOTE"):
        return None
    eligible = _owned_eligible_scope(session, int(user_id), deck_ids)
    vectors = repository.read_revision_vectors(session, user_id=user_id, deck_ids=eligible)
    unit_code = NOTE_UNIT if is_note_mode and count_by_note else CARD_UNIT
    hashes = {}
    for deck_id in eligible:
        vector = {
            "user_id": int(user_id), "effective_deck_id": deck_id,
            "content_and_learner_revisions": vectors[deck_id],
            "mode": route.mode_code, "epoch": route.epoch,
            "persisted_authority": route.persisted, "storage_profile": route.storage_profile,
            "contract": DASHBOARD_CONTRACT, "unit": unit_code,
            "admin_mode": bool(admin_mode), "owned_notes_only": True,
            "implementation": COUNT_IMPLEMENTATION_VERSION,
            "policy_hash": policy.policy_hash.hex(), "study_day": int(day_index),
            "cutoff": _utc_naive(cutoff).isoformat(),
        }
        hashes[deck_id] = hashlib.sha256(json.dumps(
            vector, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
        ).encode("utf-8")).digest()
    return _Context(
        int(user_id), eligible, policy, int(day_index), _utc_naive(cutoff),
        unit_code, bool(is_note_mode), bool(admin_mode), hashes,
    )


def resolve_cached_owned_deck_counts(
    session, *, learner_user_id, visible_deck_ids, today_day_index,
    day_cutoff_utc, timezone_name, day_boundary_hour_local, is_note_mode,
    admin_mode=False, count_by_note=False, now_utc=None,
):
    """Return valid cached counts and all remaining raw IDs, with no DML.

    The caller owns its coherent snapshot (Dashboard uses fresh read-only RR).
    Non-owned decks and every install/mapped scope remain on the raw aggregator.
    """
    session = session if isinstance(session, Session) else session()
    requested = sorted({int(value) for value in visible_deck_ids})
    if (not requested or not current_app.config.get("DECK_COUNT_WRITE_ENABLED", False)
            or current_app.config.get("DECK_COUNT_READ_MODE", "raw") != "summary"):
        return {}, requested
    now = _utc_naive(now_utc or _utcnow())
    policy = ReviewAnalyticsPolicy(timezone_name, int(day_boundary_hour_local))
    expected_day = policy.study_day(now).toordinal()
    expected_cutoff = _day_index_to_datetime(expected_day + 1, policy.day_boundary_hour,
                                           timezone_name=policy.timezone_name)
    if today_day_index != expected_day or _utc_naive(day_cutoff_utc) != expected_cutoff:
        return {}, requested
    with session.no_autoflush:
        context = _context(
            session, user_id=learner_user_id, deck_ids=requested, policy=policy,
            day_index=today_day_index, cutoff=day_cutoff_utc, is_note_mode=is_note_mode,
            admin_mode=admin_mode, count_by_note=count_by_note,
        )
        if context is None:
            return {}, requested
        snapshots = repository.read_snapshots(
            session, user_id=learner_user_id, deck_ids=context.deck_ids,
            contract_code=DASHBOARD_CONTRACT, unit_code=context.unit_code,
        )
    cached = _valid_counts(context, snapshots, now)
    return cached, [deck_id for deck_id in requested if deck_id not in cached]


def _valid_counts(context, snapshots, now):
    cached = {}
    for deck_id, row in snapshots.items():
        if (
            row["study_day"] != date.fromordinal(context.day_index)
            or row["valid_until_utc"] != context.cutoff
            or row["valid_until_utc"] <= now
            or bytes(row["policy_hash"]) != context.policy.policy_hash
            or bytes(row["dependency_hash"]) != context.hashes[deck_id]
        ):
            continue
        cached[deck_id] = {
            "total": int(row["total_count"]), "new": int(row["new_count"]),
            "learn": int(row["learn_count"]), "due": int(row["due_count"]),
        }
    return cached


@contextmanager
def _fresh_session(factory):
    if factory is None:
        from models import db
        session = Session(db.engine, expire_on_commit=False)
    else:
        session = factory()
    if session.in_transaction() or session.new or session.dirty or session.deleted:
        raise RuntimeError("Deck prewarm requires a fresh Session, never a request transaction")
    try:
        yield session
    finally:
        session.close()


@contextmanager
def _snapshot(session):
    if session.get_bind().dialect.name == "mysql":
        connection = session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
    else:
        session.begin()
    try:
        yield
    finally:
        session.rollback()


def _worker_context(session, user_id, deck_ids, now):
    policy = resolve_review_analytics_policy(session, user_id)
    route = read_study_authority_route(session, learner_user_id=user_id)
    day_index = policy.study_day(now).toordinal()
    cutoff = _day_index_to_datetime(day_index + 1, policy.day_boundary_hour,
                                    timezone_name=policy.timezone_name)
    return _context(
        session, user_id=user_id, deck_ids=deck_ids, policy=policy, day_index=day_index,
        cutoff=cutoff, is_note_mode=route.mode_code == "NOTE",
        admin_mode=repository.read_admin_mode(session, user_id),
        count_by_note=bool(current_app.config.get("STUDY_NOTE_COUNT_ENABLED", False)),
        authority_route=route,
    )


def _publish_count_snapshots(captured, counts, *, session_factory, now_utc):
    with _fresh_session(session_factory) as session:
        if session.get_bind().dialect.name == "mysql":
            session.connection(execution_options={"isolation_level": "READ COMMITTED"})
        else:
            session.begin()
        try:
            now = _utc_naive(now_utc or _utcnow())
            current = _worker_context(session, captured.user_id, captured.deck_ids, now)
            if current is None:
                session.rollback()
                return 0
            valid = []
            for deck_id in captured.deck_ids:
                if (
                    deck_id not in current.hashes or current.hashes[deck_id] != captured.hashes[deck_id]
                    or current.policy.policy_hash != captured.policy.policy_hash
                    or current.day_index != captured.day_index or current.cutoff != captured.cutoff
                    or now >= captured.cutoff
                ):
                    continue
                vector = counts[deck_id]
                valid.append({
                    "user_id": captured.user_id, "effective_deck_id": deck_id,
                    "contract_code": DASHBOARD_CONTRACT, "unit_code": captured.unit_code,
                    "total_count": vector["total"], "new_count": vector["new"],
                    "learn_count": vector["learn"], "due_count": vector["due"],
                    "study_day": date.fromordinal(captured.day_index),
                    "valid_until_utc": captured.cutoff, "policy_hash": captured.policy.policy_hash,
                    "dependency_hash": captured.hashes[deck_id], "computed_at": counts.computed_at,
                })
            repository.upsert_snapshots(session, valid)
            session.commit()
            return len(valid)
        except Exception:
            session.rollback()
            raise


class _ComputedCounts(dict):
    """Keep the computation time separate from the later publisher's clock."""
    computed_at: datetime


def prewarm_owned_deck_counts(*, user_id, deck_ids=None, now_utc=None, session_factory=None, force=False):
    """Compute raw counts in RR, then publish matching captured stamps in RC.

    A race may publish an already stale vector. Readers still reject it; cache
    publication does not advance or clear any canonical invalidation token.
    """
    if not current_app.config.get("DECK_COUNT_WRITE_ENABLED", False):
        return {"ok": False, "error": "WRITER_COVERAGE_DISABLED", "computed": 0, "published": 0}
    user_id = int(user_id)
    with _fresh_session(session_factory) as session, _snapshot(session):
        now = _utc_naive(now_utc or _utcnow())
        captured = _worker_context(session, user_id, deck_ids, now)
        eligible = len(captured.deck_ids)
        snapshots = repository.read_snapshots(
            session, user_id=user_id, deck_ids=captured.deck_ids,
            contract_code=DASHBOARD_CONTRACT, unit_code=captured.unit_code,
        ) if not force else {}
        cached = _valid_counts(captured, snapshots, now)
        dirty = tuple(deck_id for deck_id in captured.deck_ids if deck_id not in cached)
        captured = replace(captured, deck_ids=dirty, hashes={key: captured.hashes[key] for key in dirty})
        if not dirty:
            return {"ok": True, "user_id": user_id, "eligible": eligible, "cached": len(cached),
                    "computed": 0, "published": 0, "discarded": 0,
                    "study_day": date.fromordinal(captured.day_index).isoformat(), "unit_code": captured.unit_code}
        raw, _metadata = aggregate_deck_study_counts(
            session, learner_user_id=user_id, visible_deck_ids=list(captured.deck_ids),
            today_day_index=captured.day_index, day_cutoff_utc=captured.cutoff,
            admin_mode=captured.admin_mode,
            count_by_note=captured.unit_code == NOTE_UNIT, include_note_types=False,
        )
        counts = _ComputedCounts(raw)
        counts.computed_at = now
    published = _publish_count_snapshots(captured, counts, session_factory=session_factory, now_utc=now_utc)
    return {"ok": True, "user_id": user_id, "computed": len(captured.deck_ids),
            "eligible": eligible, "cached": len(cached),
            "published": published, "discarded": len(captured.deck_ids) - published,
            "study_day": date.fromordinal(captured.day_index).isoformat(),
            "unit_code": captured.unit_code}
