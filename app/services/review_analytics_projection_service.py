"""Capture immutable history revisions at the outer transaction boundary.

The buffer retains SAVEPOINT ancestry. Learner head locks are taken only after
all domain work has finished; root commits require a durable feed finalizer.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from flask import current_app, has_app_context
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session

from app.repositories.review_analytics_repository import load_inserted_events
from models.review_event import ReviewEvent

_KEY = "flama.review_analytics.transaction"
_PROJECTED_COLUMNS = ("user_id", "reviewed_at", "deck_id", "duration_ms", "rating", "id")


class ReviewAnalyticsFenceError(RuntimeError):
    pass


@dataclass
class _Frame:
    transaction: object
    event_ids: set[int] = field(default_factory=set)
    dirty_users: set[int] = field(default_factory=set)
    fenced_users: set[int] = field(default_factory=set)
    inserted: dict[int, object] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class _InsertedEvent:
    id: int
    user_id: int
    reviewed_at: datetime
    deck_id: int | None
    duration_ms: int | None
    rating: str
    passed: int | None


def _insert_snapshot(event):
    """Only bypass SQL when stored scalars and passed semantics are identical.

    Exotic/collated ratings, fractional timestamps and driver-coerced integers
    still use the existing SQL loader. Native ratings and timestamps are exact
    canonical scalars; there are no projected ReviewEvent triggers in the schema.
    """
    rating = event.rating
    canonical = rating in {"again", "hard", "good", "easy", "1", "2", "3", "4"}
    moment = event.reviewed_at
    equivalent = (canonical and type(event.user_id) is int
        and isinstance(moment, datetime) and moment.tzinfo is None and moment.microsecond == 0
        and (event.deck_id is None or type(event.deck_id) is int)
        and (event.duration_ms is None or type(event.duration_ms) is int))
    return _InsertedEvent(int(event.id), event.user_id, moment, event.deck_id,
                          event.duration_ms, rating,
                          int(rating in {"good", "easy", "3", "4"}) if equivalent else None)


@dataclass
class _Buffer:
    root: object
    frames: dict[object, _Frame] = field(default_factory=dict)
    finalized: bool = False
    finalizing: bool = False


def writes_enabled(session=None) -> bool:
    if session is not None and "review_analytics_write_enabled" in session.info:
        return bool(session.info["review_analytics_write_enabled"])
    return bool(has_app_context() and current_app.config.get("REVIEW_ANALYTICS_WRITE_ENABLED", False))


def _buffer(session: Session, *, create=False):
    root = session.get_transaction()
    stored = session.info.get(_KEY)
    if stored is not None and stored.root is not root:
        session.info.pop(_KEY, None)
        stored = None
    if create and stored is None:
        if root is None:
            raise ReviewAnalyticsFenceError("Review analytics requires an active outer transaction.")
        stored = session.info[_KEY] = _Buffer(root)
    return stored


def _frame(session: Session, buffer: _Buffer):
    transaction = session.get_nested_transaction() or session.get_transaction()
    return buffer.frames.setdefault(transaction, _Frame(transaction))


def record_review_analytics_fence(session: Session, user_id: int) -> None:
    session = session if isinstance(session, Session) else session()
    if writes_enabled(session):
        buffer = _buffer(session, create=True)
        _frame(session, buffer).fenced_users.add(int(user_id))


def _require_fences(session: Session, buffer: _Buffer, users) -> None:
    fenced = set().union(*(frame.fenced_users for frame in buffer.frames.values()))
    missing = set(users) - fenced
    if missing:
        raise ReviewAnalyticsFenceError(
            "ReviewEvent writers must acquire the learner fence before raw writes "
            f"(missing user IDs: {sorted(missing)})."
        )


def invalidate_review_analytics(session: Session, user_ids) -> None:
    """Bulk mutators queue DIRTY, without taking head locks during domain work."""
    session = session if isinstance(session, Session) else session()
    if not writes_enabled(session):
        return
    buffer = _buffer(session, create=True)
    if buffer.finalized:
        raise ReviewAnalyticsFenceError("History writes cannot follow analytics finalization; finalize once after all domain writes.")
    users = {int(value) for value in user_ids}
    _require_fences(session, buffer, users)
    _frame(session, buffer).dirty_users.update(users)
    buffer.finalized = False


@event.listens_for(Session, "before_flush")
def _guard_raw_writes(session, flush_context, instances):
    if not writes_enabled(session):
        return
    new = [obj for obj in session.new if isinstance(obj, ReviewEvent)]
    changed = [obj for obj in session.dirty if isinstance(obj, ReviewEvent)
               and any(inspect(obj).attrs[name].history.has_changes()
                       for name in _PROJECTED_COLUMNS)]
    deleted = [obj for obj in session.deleted if isinstance(obj, ReviewEvent)]
    if not new and not changed and not deleted:
        return
    buffer = _buffer(session, create=True)
    if buffer.finalized:
        raise ReviewAnalyticsFenceError("History writes cannot follow analytics finalization; finalize once after all domain writes.")
    users = {int(obj.user_id) for obj in new + changed + deleted}
    if any(inspect(obj).attrs.id.history.has_changes() for obj in changed):
        raise ReviewAnalyticsFenceError("ReviewEvent identities are immutable during covered writes.")
    previous_users = set()
    persisted_ids = [int(obj.id) for obj in changed + deleted if obj.id is not None]
    if persisted_ids:
        previous_users = set(session.execute(select(ReviewEvent.user_id).where(
            ReviewEvent.id.in_(persisted_ids))).scalars())
        users.update(previous_users)
    for obj in changed:
        users.update(int(value) for value in inspect(obj).attrs.user_id.history.deleted
                     if value is not None)
    _require_fences(session, buffer, users)
    if changed or deleted:
        invalidate_review_analytics(session, {int(obj.user_id) for obj in changed + deleted})
        invalidate_review_analytics(session, previous_users)
        for obj in changed:
            invalidate_review_analytics(session, inspect(obj).attrs.user_id.history.deleted)
    buffer.finalized = False


@event.listens_for(Session, "after_flush")
def _capture_inserted_events(session, flush_context):
    if not writes_enabled(session):
        return
    inserted = [obj for obj in session.new if isinstance(obj, ReviewEvent) and obj.id is not None]
    if inserted:
        buffer = _buffer(session, create=True)
        frame = _frame(session, buffer)
        for obj in inserted:
            identity = int(obj.id)
            frame.event_ids.add(identity)
            frame.inserted[identity] = _insert_snapshot(obj)
        buffer.finalized = False


def flush_review_analytics_deltas(session: Session) -> None:
    """Persist one feed revision after all domain writes, before outer commit."""
    session = session if isinstance(session, Session) else session()
    if not writes_enabled(session):
        return
    if session.in_nested_transaction():
        raise ReviewAnalyticsFenceError("History revisions cannot be finalized inside a SAVEPOINT.")
    session.flush()
    buffer = _buffer(session)
    if buffer is None or buffer.finalized:
        return
    event_ids = set().union(*(frame.event_ids for frame in buffer.frames.values()))
    dirty_users = set().union(*(frame.dirty_users for frame in buffer.frames.values()))
    if not event_ids and not dirty_users:
        buffer.finalized = True
        return
    captured = {identity: row for frame in buffer.frames.values() for identity, row in frame.inserted.items()}
    # Corrected/deleted facts require a rebuild. Their immutable dirty marker
    # must never replay a snapshot captured before the correction.
    relevant = {identity: row for identity, row in captured.items() if row.user_id not in dirty_users}
    rows = [row for row in relevant.values() if row.passed is not None]
    reload_ids = (event_ids - captured.keys()) | {identity for identity, row in relevant.items() if row.passed is None}
    if reload_ids:
        rows.extend(load_inserted_events(session, reload_ids))
    users = sorted(dirty_users | {int(row.user_id) for row in rows})
    _require_fences(session, buffer, users)
    from app.repositories.review_analytics_outbox_repository import advance_async_head
    from app.services.review_analytics_outbox_service import stage_review_analytics_outbox

    buffer.finalizing = True
    try:
        # Lock every learner head before feed writes. Applying daily counters
        # belongs exclusively to the worker; source commands never lock them.
        revisions = {user_id: advance_async_head(session, user_id=user_id) for user_id in users}
        rows_by_user = {user_id: [] for user_id in users}
        for row in rows:
            rows_by_user[int(row.user_id)].append(row)
        for user_id in users:
            stage_review_analytics_outbox(session, user_id=user_id, source_revision=revisions[user_id],
                rows=rows_by_user[user_id], dirty=user_id in dirty_users)
        buffer.finalized = True
    finally:
        buffer.finalizing = False


@event.listens_for(Session, "before_commit")
def _guard_outer_commit(session):
    if not writes_enabled(session) or session.in_nested_transaction():
        return
    # before_commit precedes the commit's implicit flush. Catch unflushed new facts too.
    pending = any(isinstance(obj, ReviewEvent) for obj in session.new | session.deleted)
    pending = pending or any(isinstance(obj, ReviewEvent) and any(
        inspect(obj).attrs[name].history.has_changes() for name in _PROJECTED_COLUMNS)
        for obj in session.dirty)
    buffer = _buffer(session)
    if pending or (buffer is not None and not buffer.finalized and any(
            frame.event_ids or frame.dirty_users for frame in buffer.frames.values())):
        raise ReviewAnalyticsFenceError("Review analytics was not finalized before the outer commit.")


def _is_descendant(transaction, ancestor):
    while transaction is not None:
        if transaction is ancestor:
            return True
        transaction = transaction.parent
    return False


@event.listens_for(Session, "do_orm_execute")
def _guard_bulk_raw_mutations(execute_state):
    """Bulk ORM SQL bypasses flush hooks; unintegrated history writers fail closed."""
    session = execute_state.session
    if not writes_enabled(session):
        return
    statement = execute_state.statement
    if getattr(statement, "text", None):
        import re
        if re.search(r"\breview_events\b", statement.text, re.IGNORECASE) and re.search(
                r"\b(insert|update|delete|replace)\b", statement.text, re.IGNORECASE):
            raise ReviewAnalyticsFenceError("Text history mutations require an explicit maintenance migration.")
    if not (
            execute_state.is_update or execute_state.is_delete or execute_state.is_insert):
        return
    table = getattr(statement, "table", None)
    if getattr(table, "name", None) != ReviewEvent.__tablename__:
        return
    if execute_state.is_insert:
        raise ReviewAnalyticsFenceError("Bulk ReviewEvent inserts must use the canonical writer.")
    if execute_state.is_update:
        values = getattr(statement, "_values", None)
        names = {getattr(key, "key", key) for key in (values or {})}
        if values and not names.intersection(_PROJECTED_COLUMNS):
            return
        if names.intersection(("user_id", "id")):
            raise ReviewAnalyticsFenceError("Bulk ReviewEvent identity changes require a dedicated migration.")
    buffer = _buffer(session)
    dirty = set().union(*(frame.dirty_users for frame in buffer.frames.values())) if buffer else set()
    if not dirty:
        raise ReviewAnalyticsFenceError(
            "Projected bulk ReviewEvent mutations must queue generation invalidation before SQL."
        )
    # The head buffer alone is not an affected-scope proof. Use a CURRENT read
    # (the purge admission may have established an older RR snapshot) and ensure
    # every affected learner is invalidated and already fenced.
    affected = select(ReviewEvent.user_id).distinct()
    if statement.whereclause is not None:
        affected = affected.where(statement.whereclause)
    affected_users = set(session.execute(affected.with_for_update(read=True)).scalars())
    if not affected_users.issubset(dirty):
        raise ReviewAnalyticsFenceError("Bulk ReviewEvent mutation exceeds its invalidated learner scope.")
    _require_fences(session, buffer, affected_users)


@event.listens_for(Session, "after_soft_rollback")
def _discard_rolled_back_frames(session, previous_transaction):
    buffer = session.info.get(_KEY)
    if buffer is None:
        return
    for transaction in list(buffer.frames):
        if _is_descendant(transaction, previous_transaction):
            del buffer.frames[transaction]
    # Finalization is prohibited within SAVEPOINTs. If a later SAVEPOINT is
    # rolled back, the already-finalized root writes/head locks still survive.
    # Reopening the buffer would allow recounts or domain writes after heads.
    if not (buffer.finalized and previous_transaction.nested):
        buffer.finalized = False


@event.listens_for(Session, "after_transaction_end")
def _clear_root_buffer(session, transaction):
    if transaction.parent is None:
        session.info.pop(_KEY, None)
