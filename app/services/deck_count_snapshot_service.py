"""Exact direct-deck cache reads and optimistic, separately transacted prewarm.

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
from app.services.analytics_summary_readiness import require_ready_summary
from models.deck_count_snapshot import CARD_UNIT, DASHBOARD_CONTRACT, NOTE_UNIT


COUNT_IMPLEMENTATION_VERSION = "dashboard-direct-counts.v2"
DEFAULT_PREWARM_MAX_DECKS = 100


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _utc_naive(value):
    return value.astimezone(timezone.utc).replace(tzinfo=None) if value.tzinfo is not None else value


def _prewarmed_learner(user_id):
    configured = current_app.config.get("DECK_COUNT_PREWARM_USER_IDS", ())
    configured = configured.split(",") if isinstance(configured, str) else configured
    return str(int(user_id)) in {str(value).strip() for value in configured}


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


def _owned_metadata(session, user_id, deck_ids):
    """The requested owned decks, and every owned ancestor by ID."""
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
    return rows, by_id


def _owned_eligible_scope(session, rows, by_id):
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


def _installed_eligible_scope(session, user_id, rows, by_id):
    """Only well-formed release scopes can acquire cache stamps.

    Legacy timestamp scopes, unmapped descendants, foreign installs, cycles
    and incomplete release metadata keep the exact raw fallback. This reads
    deck/map/release metadata only; source Note membership remains shared.
    A release published before template pins reads the live ACTIVE
    occurrences, and an occurrence change bumps the global content epoch.
    """
    ancestor_dependencies = repository.read_installed_scope_dependencies(session, deck_ids=by_id)
    dependencies = {int(row.id): ancestor_dependencies[int(row.id)] for row in rows
                    if int(row.id) in ancestor_dependencies}
    if not dependencies:
        return {}
    allowed = {}
    for deck_id, vector in dependencies.items():
        if (vector["install_user_id"] != int(user_id)
                or vector["clone_mode"] != "logical_overlay"
                or vector["version_mode"] != "release"
                or not vector["source_owner_user_id"]
                or not vector["install_source_deck_id"]
                or not vector["install_local_deck_id"]
                or vector["release_id"] != vector["applied_release_id"]
                or vector["release_deck_item_id"] != vector["deck_item_id"]
                or vector["release_status"] != "published"):
            continue
        root_id = int(vector["install_local_deck_id"])
        root = ancestor_dependencies.get(root_id)
        if (root is None or root["install_id"] != vector["install_id"]
                or root["map_source_deck_id"] != vector["install_source_deck_id"]):
            continue
        current, seen = deck_id, set()
        while current not in seen:
            seen.add(current)
            metadata = by_id.get(current)
            mapping = ancestor_dependencies.get(current)
            if metadata is None or (mapping and mapping["install_id"] != vector["install_id"]):
                break
            if current == root_id:
                allowed[deck_id] = vector
                break
            if metadata.parent_id is None:
                break
            current = int(metadata.parent_id)
    return allowed


def _context(session, *, user_id, deck_ids, policy, day_index, cutoff,
             is_note_mode, admin_mode, count_by_note, authority_route=None):
    route = authority_route or read_study_authority_route(session, learner_user_id=int(user_id))
    if bool(is_note_mode) != (route.mode_code == "NOTE"):
        return None
    rows, by_id = _owned_metadata(session, int(user_id), deck_ids)
    owned = _owned_eligible_scope(session, rows, by_id)
    installed = {} if admin_mode else _installed_eligible_scope(session, int(user_id), rows, by_id)
    eligible = tuple(sorted({*owned, *installed}))
    revision_ids = {*eligible, *(int(vector["map_source_deck_id"]) for vector in installed.values())}
    vectors = repository.read_revision_vectors(session, user_id=user_id, deck_ids=revision_ids)
    unit_code = NOTE_UNIT if is_note_mode and count_by_note else CARD_UNIT
    hashes = {}
    for deck_id in eligible:
        vector = {
            "user_id": int(user_id), "effective_deck_id": deck_id,
            "content_and_learner_revisions": vectors[deck_id],
            "mode": route.mode_code, "epoch": route.epoch,
            "persisted_authority": route.persisted, "storage_profile": route.storage_profile,
            "contract": DASHBOARD_CONTRACT, "unit": unit_code,
            "admin_mode": bool(admin_mode), "owned_notes_only": deck_id not in installed,
            "implementation": COUNT_IMPLEMENTATION_VERSION,
            "policy_hash": policy.policy_hash.hex(), "study_day": int(day_index),
            "cutoff": _utc_naive(cutoff).isoformat(),
        }
        if deck_id in installed:
            dependency = installed[deck_id]
            vector["installed_scope"] = dependency
            # A learner's source-Note progress is invalidated at the physical
            # source deck, while local-added Notes use the local deck token.
            vector["mapped_source_revisions"] = vectors[int(dependency["map_source_deck_id"])]
        hashes[deck_id] = hashlib.sha256(json.dumps(
            vector, sort_keys=True, separators=(",", ":"), ensure_ascii=True,
            default=lambda value: value.isoformat(),
        ).encode("utf-8")).digest()
    return _Context(
        int(user_id), eligible, policy, int(day_index), _utc_naive(cutoff),
        unit_code, bool(is_note_mode), bool(admin_mode), hashes,
    )


def resolve_cached_owned_deck_counts(
    session, *, learner_user_id, visible_deck_ids, today_day_index,
    day_cutoff_utc, timezone_name, day_boundary_hour_local, is_note_mode,
    admin_mode=False, count_by_note=False, now_utc=None, authority_route=None,
):
    """Return valid cached counts and all remaining raw IDs, with no DML.

    The caller owns its coherent snapshot (Dashboard uses fresh read-only RR).
    Non-owned and unqualified installed scopes remain on the raw aggregator.
    Only the prewarm worker publishes snapshots, so a learner outside
    ``DECK_COUNT_PREWARM_USER_IDS`` has none and skips the stamp reads.
    """
    session = session if isinstance(session, Session) else session()
    requested = sorted({int(value) for value in visible_deck_ids})
    if (not requested or not current_app.config.get("DECK_COUNT_WRITE_ENABLED", False)
            or current_app.config.get("DECK_COUNT_READ_MODE", "raw") != "summary"
            or not _prewarmed_learner(learner_user_id)):
        if requested and current_app.config.get("DECK_COUNT_READ_MODE", "raw") == "summary":
            require_ready_summary(user_id=learner_user_id, metric="dashboard")
        return {}, requested
    now = _utc_naive(now_utc or _utcnow())
    policy = ReviewAnalyticsPolicy(timezone_name, int(day_boundary_hour_local))
    expected_day = policy.study_day(now).toordinal()
    expected_cutoff = _day_index_to_datetime(expected_day + 1, policy.day_boundary_hour,
                                           timezone_name=policy.timezone_name)
    if today_day_index != expected_day or _utc_naive(day_cutoff_utc) != expected_cutoff:
        require_ready_summary(user_id=learner_user_id, metric="dashboard")
        return {}, requested
    with session.no_autoflush:
        context = _context(
            session, user_id=learner_user_id, deck_ids=requested, policy=policy,
            day_index=today_day_index, cutoff=day_cutoff_utc, is_note_mode=is_note_mode,
            admin_mode=admin_mode, count_by_note=count_by_note,
            authority_route=authority_route,
        )
        if context is None:
            require_ready_summary(user_id=learner_user_id, metric="dashboard")
            return {}, requested
        snapshots = repository.read_snapshots(
            session, user_id=learner_user_id, deck_ids=context.deck_ids,
            contract_code=DASHBOARD_CONTRACT, unit_code=context.unit_code,
        )
    cached = _valid_counts(context, snapshots, now)
    missing = [deck_id for deck_id in requested if deck_id not in cached]
    if missing:
        require_ready_summary(user_id=learner_user_id, metric="dashboard")
    return cached, missing


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


def prewarm_owned_deck_counts(*, user_id, deck_ids=None, now_utc=None, session_factory=None,
                             force=False, max_decks=DEFAULT_PREWARM_MAX_DECKS, after_deck_id=0):
    """Compute raw counts in RR, then publish matching captured stamps in RC.

    A race may publish an already stale vector. Readers still reject it; cache
    publication does not advance or clear any canonical invalidation token.
    """
    if not current_app.config.get("DECK_COUNT_WRITE_ENABLED", False):
        return {"ok": False, "error": "WRITER_COVERAGE_DISABLED", "computed": 0, "published": 0}
    user_id = int(user_id)
    max_decks, after_deck_id = int(max_decks), int(after_deck_id)
    if not 1 <= max_decks <= 1000 or after_deck_id < 0:
        raise ValueError("Prewarm requires 1..1000 max_decks and a nonnegative deck cursor")
    with _fresh_session(session_factory) as session, _snapshot(session):
        now = _utc_naive(now_utc or _utcnow())
        captured = _worker_context(session, user_id, deck_ids, now)
        if captured is None:
            return {"ok": False, "error": "AUTHORITY_SCOPE_UNQUALIFIED", "computed": 0, "published": 0,
                    "has_more": False, "next_after_deck_id": after_deck_id}
        eligible = len(captured.deck_ids)
        snapshots = repository.read_snapshots(
            session, user_id=user_id, deck_ids=captured.deck_ids,
            contract_code=DASHBOARD_CONTRACT, unit_code=captured.unit_code,
        ) if not force else {}
        cached = _valid_counts(captured, snapshots, now)
        dirty = tuple(deck_id for deck_id in captured.deck_ids
                      if deck_id > after_deck_id and deck_id not in cached)
        has_more = len(dirty) > max_decks
        dirty = dirty[:max_decks]
        captured = replace(captured, deck_ids=dirty, hashes={key: captured.hashes[key] for key in dirty})
        if not dirty:
            return {"ok": True, "user_id": user_id, "eligible": eligible, "cached": len(cached),
                    "computed": 0, "published": 0, "discarded": 0,
                    "has_more": False, "next_after_deck_id": after_deck_id,
                    "study_day": date.fromordinal(captured.day_index).isoformat(), "unit_code": captured.unit_code}
        raw, _metadata = aggregate_deck_study_counts(
            session, learner_user_id=user_id, visible_deck_ids=list(captured.deck_ids),
            today_day_index=captured.day_index, day_cutoff_utc=captured.cutoff,
            admin_mode=captured.admin_mode,
            count_by_note=captured.unit_code == NOTE_UNIT, include_note_types=False,
            # A batch reads only its own decks' Notes, not the learner's whole collection.
            scope_to_decks=True,
        )
        counts = _ComputedCounts(raw)
        counts.computed_at = now
    published = _publish_count_snapshots(captured, counts, session_factory=session_factory, now_utc=now_utc)
    return {"ok": True, "user_id": user_id, "computed": len(captured.deck_ids),
            "eligible": eligible, "cached": len(cached),
            "published": published, "discarded": len(captured.deck_ids) - published,
            "has_more": has_more, "next_after_deck_id": captured.deck_ids[-1],
            "study_day": date.fromordinal(captured.day_index).isoformat(),
            "unit_code": captured.unit_code}
