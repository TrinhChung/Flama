"""Bounded, resumable historical projection backfill with exact verification.

Every barrier owns a fresh Session. It never upgrades a request's learner
shared fence, and exact verification never holds the learner-exclusive fence.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Callable

from sqlalchemy.orm import Session

from app.repositories import review_analytics_backfill_repository as source
from app.repositories.review_analytics_repository import add_grouped_deltas, lock_generations, lock_head
from app.services.review_analytics_policy import policy_from_generation, resolve_review_analytics_policy
from models.review_analytics import BUILDING, DIRTY, FAILED, READY, RETIRED, ReviewAnalyticsGeneration


STATUS_NAMES = {BUILDING: "BUILDING", READY: "READY", DIRTY: "DIRTY", FAILED: "FAILED", RETIRED: "RETIRED"}
VERIFICATION_CONTRACT_VERSION = 1


def _utcnow():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _user_id(value):
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError("user_id must be a positive integer")
    return value


def _require_covered_writers(enabled):
    if enabled is not True:
        raise RuntimeError("Backfill requires enabled, fully covered review analytics writers.")


@contextmanager
def _fresh_session(factory=None):
    if factory is None:
        from models import db
        session = Session(bind=db.engine, expire_on_commit=False)
    else:
        session = factory()
    if session.in_transaction() or session.new or session.dirty or session.deleted:
        raise RuntimeError("Backfill requires a fresh Session, never a request transaction.")
    try:
        yield session
    finally:
        session.close()


@contextmanager
def _readonly_snapshot(session):
    if session.get_bind().dialect.name == "mysql":
        connection = session.connection(execution_options={"isolation_level": "REPEATABLE READ"})
        connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
    else:
        session.begin()
    try:
        yield
    finally:
        session.rollback()


def _report(head, generation=None, **extra):
    result = {
        "user_id": int(head.user_id),
        "active_generation": int(head.active_generation) if head.active_generation is not None else None,
        "building_generation": int(head.building_generation) if head.building_generation is not None else None,
        "source_revision": int(head.source_revision),
    }
    if generation is not None:
        result.update({
            "generation": int(generation.generation),
            "status": STATUS_NAMES[int(generation.status)],
            "status_code": int(generation.status),
            "policy_hash": bytes(generation.policy_hash).hex(),
            "baseline_high_water_id": int(generation.baseline_high_water_id),
            "backfill_cursor_id": int(generation.backfill_cursor_id),
            "applied_source_revision": int(generation.applied_source_revision)
                if generation.applied_source_revision is not None else None,
            "complete": generation.backfill_cursor_id == generation.baseline_high_water_id,
        })
    result.update(extra)
    return result


def _locked_generation(session, head, requested=None, *, include_active=False):
    generation_id = head.building_generation if requested is None else int(requested)
    ids = [generation_id]
    if include_active:
        ids.append(head.active_generation)
    generations = lock_generations(session, int(head.user_id), ids)
    by_id = {int(item.generation): item for item in generations}
    return by_id.get(int(generation_id)) if generation_id is not None else None, by_id


def _building_error(head, generation):
    if generation is None or head.building_generation != generation.generation:
        return "BUILDING_POINTER_CHANGED"
    if generation.status != BUILDING:
        return "GENERATION_NOT_BUILDING"
    if generation.applied_source_revision != head.source_revision:
        return "SOURCE_REVISION_NOT_APPLIED"
    return None


def _clear_verification(generation):
    generation.verified_source_revision = None
    generation.verification_contract_version = None
    generation.verified_at = None


def _policy_error(session, head, generation):
    policy = policy_from_generation(generation)
    if policy.policy_hash != resolve_review_analytics_policy(session, int(head.user_id)).policy_hash:
        generation.status = DIRTY
        generation.last_error_code = "POLICY_CHANGED"
        _clear_verification(generation)
        return "POLICY_CHANGED"
    return None


def admit_review_analytics_backfill(
    *, user_id: int, writer_coverage_enabled: bool, session_factory: Callable[[], Session] | None = None,
    restart: bool = False,
):
    """Capture a safe ID high-water only after draining preexisting writers."""
    _require_covered_writers(writer_coverage_enabled)
    user_id = _user_id(user_id)
    with _fresh_session(session_factory) as session, session.begin():
        source.lock_backfill_user(session, user_id)
        invalid = source.invalid_deck_attribution_count(session, user_id)
        if invalid:
            return {"user_id": user_id, "ok": False, "error": "UNSUPPORTED_DECK_ATTRIBUTION",
                    "invalid_event_count": invalid}
        head = lock_head(session, user_id, create=True)
        policy = resolve_review_analytics_policy(session, user_id)
        existing, _ = _locked_generation(session, head)
        if existing is not None and not restart:
            error = _building_error(head, existing)
            if error is None:
                error = _policy_error(session, head, existing)
            return _report(head, existing, ok=error is None, resumed=error is None,
                           error=error, restart_required=error is not None)
        if head.building_generation is not None and existing is None and not restart:
            return _report(head, ok=False, error="BUILDING_POINTER_MISSING", restart_required=True)
        if existing is not None:
            existing.status = RETIRED
        generation_id = int(head.next_generation)
        generation = ReviewAnalyticsGeneration(
            user_id=user_id, generation=generation_id, policy_hash=policy.policy_hash,
            timezone_name=policy.timezone_name, day_boundary_hour=policy.day_boundary_hour,
            grouping_version=policy.grouping_version, timezone_rules_version=policy.timezone_rules_version,
            status=BUILDING, baseline_high_water_id=source.committed_high_water(session, user_id),
            backfill_cursor_id=0, applied_source_revision=int(head.source_revision), created_at=_utcnow(),
        )
        session.add(generation)
        head.next_generation = generation_id + 1
        head.building_generation = generation_id
        head.updated_at = _utcnow()
        session.flush()
        return _report(head, generation, ok=True, resumed=False, rows_copied=0)


def copy_review_analytics_backfill_chunk(
    *, user_id: int, writer_coverage_enabled: bool, generation: int | None = None,
    chunk_size: int = 500, session_factory: Callable[[], Session] | None = None,
):
    _require_covered_writers(writer_coverage_enabled)
    user_id = _user_id(user_id)
    if isinstance(chunk_size, bool) or not isinstance(chunk_size, int) or not 1 <= chunk_size <= 5000:
        raise ValueError("chunk_size must be an integer between 1 and 5000")
    with _fresh_session(session_factory) as session, session.begin():
        source.lock_backfill_user(session, user_id)
        head = lock_head(session, user_id, create=False)
        if head is None:
            return {"user_id": user_id, "ok": False, "error": "NOT_ADMITTED"}
        building, _ = _locked_generation(session, head, generation)
        error = _building_error(head, building)
        if error is None:
            error = _policy_error(session, head, building)
        if error:
            return _report(head, building, ok=False, error=error, rows_copied=0)
        rows = source.load_baseline_chunk(
            session, user_id=user_id, cursor=int(building.backfill_cursor_id),
            high_water=int(building.baseline_high_water_id), limit=chunk_size,
        )
        if rows:
            buckets = source.group_baseline_chunk(
                rows, policy=policy_from_generation(building), dialect_name=session.get_bind().dialect.name,
            )
            add_grouped_deltas(session, user_id, int(building.generation), buckets)
            building.backfill_cursor_id = int(rows[-1][0])
        else:
            # IDs are global and deletions/gaps do not imply missing user rows.
            building.backfill_cursor_id = int(building.baseline_high_water_id)
        _clear_verification(building)
        session.flush()
        return _report(head, building, ok=True, rows_copied=len(rows))


def review_analytics_backfill_status(*, user_id: int, session_factory=None):
    user_id = _user_id(user_id)
    with _fresh_session(session_factory) as session, _readonly_snapshot(session):
        head = source.read_head(session, user_id)
        if head is None:
            return {"user_id": user_id, "status": "NOT_ADMITTED", "ok": True}
        generation_id = head.building_generation if head.building_generation is not None else head.active_generation
        generation = source.read_generation(session, user_id, int(generation_id)) if generation_id is not None else None
        return _report(head, generation, ok=True)


def _verify_review_analytics_counts(*, user_id, generation=None, session_factory=None, allow_ready=False):
    """Compare every bucket/measure in one nonlocking read-only RR snapshot."""
    user_id = _user_id(user_id)
    with _fresh_session(session_factory) as session, _readonly_snapshot(session):
        head = source.read_head(session, user_id)
        if head is None:
            return {"user_id": user_id, "ok": False, "error": "NOT_ADMITTED"}
        if generation is None:
            generation_id = head.active_generation if allow_ready and head.active_generation is not None else head.building_generation
        else:
            generation_id = int(generation)
        building = source.read_generation(session, user_id, int(generation_id)) if generation_id is not None else None
        ready = (allow_ready and building is not None and building.status == READY
                 and head.active_generation == building.generation)
        error = None if ready else _building_error(head, building)
        if ready and building.applied_source_revision != head.source_revision:
            error = "SOURCE_REVISION_NOT_APPLIED"
        if error:
            return _report(head, building, ok=False, error=error)
        if building.backfill_cursor_id != building.baseline_high_water_id:
            return _report(head, building, ok=False, error="BASELINE_INCOMPLETE")
        policy = policy_from_generation(building)
        if policy.policy_hash != resolve_review_analytics_policy(session, user_id).policy_hash:
            return _report(head, building, ok=False, error="POLICY_CHANGED")
        if source.invalid_deck_attribution_count(session, user_id):
            return _report(head, building, ok=False, error="UNSUPPORTED_DECK_ATTRIBUTION")
        raw = source.raw_grouped_counts(session, user_id=user_id, policy=policy)
        projected = source.projected_grouped_counts(session, user_id=user_id, generation=int(building.generation))
        mismatch_keys = sorted(key for key in raw.keys() | projected.keys() if raw.get(key) != projected.get(key))
        mismatches = [
            {"scope_kind": key[0], "scope_id": key[1], "study_day": key[2].isoformat(),
             "raw": list(raw[key]) if key in raw else None,
             "projected": list(projected[key]) if key in projected else None}
            for key in mismatch_keys[:20]
        ]
        return _report(
            head, building, ok=not mismatch_keys,
            error="PARITY_MISMATCH" if mismatch_keys else None,
            raw_bucket_count=len(raw), projected_bucket_count=len(projected),
            mismatch_count=len(mismatch_keys), mismatches=mismatches,
            verified_source_revision=int(head.source_revision),
            verification_contract_version=VERIFICATION_CONTRACT_VERSION,
            verified_at=_utcnow().isoformat(),
        )


def verify_review_analytics_backfill(*, user_id: int, generation: int | None = None, session_factory=None):
    return _verify_review_analytics_counts(user_id=user_id, generation=generation, session_factory=session_factory)


def _invalidate_verified_drift(*, user_id, report, session_factory):
    """Invalidate only the exact generation/revision that failed the oracle."""
    with _fresh_session(session_factory) as session, session.begin():
        source.lock_backfill_user(session, user_id)
        head = lock_head(session, user_id, create=False)
        target = None
        if head is not None:
            targets = lock_generations(session, user_id, [report["generation"]])
            target = targets[0] if targets else None
        same_target = target is not None and (
            (target.status == READY and head.active_generation == target.generation)
            or (target.status == BUILDING and head.building_generation == target.generation)
        )
        exact_report = same_target and (
            int(target.status) == report["status_code"]
            and int(head.source_revision) == report["verified_source_revision"]
            and target.applied_source_revision == head.source_revision
            and bytes(target.policy_hash).hex() == report["policy_hash"]
            and int(target.baseline_high_water_id) == report["baseline_high_water_id"]
            and int(target.backfill_cursor_id) == report["backfill_cursor_id"]
        )
        if not exact_report:
            return {**report, "drift_invalidation": "SKIPPED", "invalidation_error": "STALE_DRIFT_REPORT"}
        target.status = DIRTY
        target.last_error_code = "PARITY_MISMATCH"
        _clear_verification(target)
        session.flush()
        # This mutates only the derived model, not the source revision.
        return _report(head, target, ok=False, error="PARITY_MISMATCH",
                       drift_invalidation="DIRTY", verification=report)


def reconcile_review_analytics_counts(
    *, user_id: int, generation: int | None = None, session_factory=None,
    invalidate_on_drift: bool = False, writer_coverage_enabled: bool = False,
):
    """Read-only all-history parity for the served generation or explicit build."""
    if invalidate_on_drift:
        _require_covered_writers(writer_coverage_enabled)
    report = _verify_review_analytics_counts(
        user_id=user_id, generation=generation, session_factory=session_factory, allow_ready=True,
    )
    if invalidate_on_drift and report.get("error") == "PARITY_MISMATCH":
        return _invalidate_verified_drift(user_id=_user_id(user_id), report=report, session_factory=session_factory)
    return report


def _publish_verified_report(*, user_id, report, session_factory):
    with _fresh_session(session_factory) as session, session.begin():
        source.lock_backfill_user(session, user_id)
        head = lock_head(session, user_id, create=False)
        if head is None:
            return {"user_id": user_id, "ok": False, "error": "NOT_ADMITTED"}
        building, generations = _locked_generation(session, head, report["generation"], include_active=True)
        error = _building_error(head, building)
        if error is None:
            error = _policy_error(session, head, building)
        if error:
            return _report(head, building, ok=False, error=error)
        same_baseline = (
            building.backfill_cursor_id == building.baseline_high_water_id
            and building.baseline_high_water_id == report["baseline_high_water_id"]
            and bytes(building.policy_hash).hex() == report["policy_hash"]
        )
        verified_revision = int(report["verified_source_revision"])
        if not same_baseline or verified_revision > int(head.source_revision):
            return _report(head, building, ok=False, error="VERIFICATION_STALE")
        # Since verification, certified insert-only finalizers maintain exact
        # raw/projection parity. Unsupported mutation must set DIRTY; the
        # BUILDING/applied-source guard above refuses its publication.
        previous = generations.get(int(head.active_generation)) if head.active_generation is not None else None
        if previous is not None and previous.generation != building.generation:
            previous.status = RETIRED
        building.verified_source_revision = verified_revision
        building.verification_contract_version = VERIFICATION_CONTRACT_VERSION
        building.verified_at = datetime.fromisoformat(report["verified_at"])
        building.status = READY
        building.published_at = _utcnow()
        building.last_error_code = None
        head.active_generation = int(building.generation)
        head.building_generation = None
        head.updated_at = _utcnow()
        session.flush()
        return _report(head, building, ok=True, verification=report)


def verify_and_publish_review_analytics_backfill(
    *, user_id: int, writer_coverage_enabled: bool, generation: int | None = None, session_factory=None,
):
    _require_covered_writers(writer_coverage_enabled)
    user_id = _user_id(user_id)
    report = verify_review_analytics_backfill(user_id=user_id, generation=generation, session_factory=session_factory)
    if not report["ok"]:
        return report
    return _publish_verified_report(user_id=user_id, report=report, session_factory=session_factory)


def run_review_analytics_backfill(
    *, user_id: int, writer_coverage_enabled: bool, chunk_size: int = 500,
    max_chunks: int | None = None, restart: bool = False, publish: bool = True, session_factory=None,
):
    if max_chunks is not None and (isinstance(max_chunks, bool) or not isinstance(max_chunks, int) or max_chunks < 1):
        raise ValueError("max_chunks must be a positive integer")
    report = admit_review_analytics_backfill(
        user_id=user_id, writer_coverage_enabled=writer_coverage_enabled,
        session_factory=session_factory, restart=restart,
    )
    if not report["ok"]:
        return report
    generation = report["generation"]
    chunks, rows = 0, 0
    while not report["complete"] and (max_chunks is None or chunks < max_chunks):
        report = copy_review_analytics_backfill_chunk(
            user_id=user_id, writer_coverage_enabled=writer_coverage_enabled, generation=generation,
            chunk_size=chunk_size, session_factory=session_factory,
        )
        chunks += 1
        rows += report.get("rows_copied", 0)
        if not report["ok"]:
            return {**report, "chunks_run": chunks, "rows_copied_run": rows}
    if report["complete"] and publish:
        report = verify_and_publish_review_analytics_backfill(
            user_id=user_id, writer_coverage_enabled=writer_coverage_enabled,
            generation=generation, session_factory=session_factory,
        )
    return {**report, "chunks_run": chunks, "rows_copied_run": rows}
