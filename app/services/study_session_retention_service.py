"""Bounded, resumable retention of membership; learner facts stay intact."""
from __future__ import annotations

from dataclasses import dataclass, field
from contextlib import contextmanager
from datetime import datetime, timedelta
import hashlib
import time

from sqlalchemy import and_, delete, exists, or_, select, text, update
from models import db
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_batch import StudySessionBatch
from models.study_session_card import StudySessionCard

TERMINAL_STATUSES = ("committed", "cancelled", "expired")
TERMINAL_BATCH_STATUSES = ("completed", "failed")
DEFAULT_RETENTION_DAYS = 30
DEFAULT_EXPIRY_GRACE = timedelta(hours=24)
DEFAULT_BATCH_SESSIONS = 200
DEFAULT_BATCH_MEMBERSHIPS = 1000
DEFAULT_MAX_MEMBERSHIPS = 10000
DEFAULT_MAX_SECONDS = 60.0


@contextmanager
def _runner_lease(apply):
    if not apply or db.engine.dialect.name != "mysql":
        yield
        return
    # Keep the named lock on a separate connection: per-chunk commits and
    # rollbacks must not release it. CLI and timer share the same lease.
    with db.engine.connect() as connection:
        database = str(connection.execute(text("SELECT DATABASE()")).scalar_one())
        key = "flama:study-retention:" + hashlib.sha256(database.encode()).hexdigest()[:24]
        acquired = connection.execute(text("SELECT GET_LOCK(:key, 0)"), {"key": key}).scalar_one()
        if acquired != 1:
            raise RuntimeError("Another Study retention runner holds the database lease.")
        try:
            yield
        finally:
            connection.execute(text("SELECT RELEASE_LOCK(:key)"), {"key": key})


@dataclass
class SessionRetentionReport:
    applied: bool
    now_utc: str
    expired_sessions: int = 0
    purge_candidate_sessions: int = 0
    purged_sessions: int = 0
    purged_session_cards: int = 0
    purged_pins: int = 0
    batches: int = 0
    expiry_batches: int = 0
    cutoff_utc: str = ""
    samples: list[str] = field(default_factory=list)
    batch_memberships: int = DEFAULT_BATCH_MEMBERSHIPS
    max_memberships: int = DEFAULT_MAX_MEMBERSHIPS
    max_seconds: float = DEFAULT_MAX_SECONDS
    elapsed_seconds: float = 0
    scan_complete: bool = True
    stop_reason: str | None = None

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _pending_batch_exists():
    # Unknown statuses are recoverable until explicitly disposed of.
    return exists().where(
        StudySessionBatch.session_id == StudySession.id,
        or_(StudySessionBatch.status.notin_(TERMINAL_BATCH_STATUSES),
            StudySessionBatch.status.is_(None)),
    )


def _after_cursor(column, cursor):
    timestamp, identifier = cursor
    return or_(column > timestamp, and_(column == timestamp, StudySession.id > identifier))


def _time_available(report, started):
    if time.monotonic() - started < report.max_seconds:
        return True
    report.scan_complete, report.stop_reason = False, "time_budget"
    return False


def _expire(*, now, grace, page_size, apply, report, started, max_expired_sessions):
    condition = and_(StudySession.status == "open", StudySession.expires_at < now - grace,
                     ~_pending_batch_exists())
    cursor = None
    while _time_available(report, started):
        remaining = max_expired_sessions - report.expired_sessions
        if remaining <= 0:
            report.scan_complete, report.stop_reason = False, "expiry_budget"
            return
        statement = select(StudySession.id, StudySession.expires_at).where(condition)
        if cursor:
            statement = statement.where(_after_cursor(StudySession.expires_at, cursor))
        rows = db.session.execute(statement.order_by(StudySession.expires_at, StudySession.id)
                                  .limit(min(page_size, remaining))).all()
        db.session.rollback()
        if not rows:
            return
        cursor = (rows[-1].expires_at, rows[-1].id)
        if apply:
            # Bounded primary keys; recheck work under the session fence used
            # by admission and worker transactions.
            locked = list(db.session.execute(
                select(StudySession.id).where(StudySession.id.in_([row.id for row in rows]))
                .order_by(StudySession.id).with_for_update()
            ).scalars())
            eligible = list(db.session.execute(select(StudySession.id)
                                               .where(StudySession.id.in_(locked), condition)
                                               .with_for_update()).scalars())
            if eligible:
                db.session.execute(update(StudySession).where(StudySession.id.in_(eligible))
                                   .values(status="expired", updated_at=now)
                                   .execution_options(synchronize_session=False))
            db.session.commit()
            report.expired_sessions += len(eligible)
            report.expiry_batches += 1
        else:
            report.expired_sessions += len(rows)


def _purge(*, cutoff, page_size, apply, report, started):
    has_cards = exists().where(StudySessionCard.session_id == StudySession.id)
    condition = and_(StudySession.status.in_(TERMINAL_STATUSES), StudySession.opened_at < cutoff,
                     StudySession.expires_at < cutoff, has_cards, ~_pending_batch_exists())
    cursor = None
    while _time_available(report, started):
        if report.purged_session_cards >= report.max_memberships:
            report.scan_complete, report.stop_reason = False, "membership_budget"
            return
        statement = select(StudySession.id, StudySession.opened_at).where(condition)
        if cursor:
            statement = statement.where(_after_cursor(StudySession.opened_at, cursor))
        rows = db.session.execute(statement.order_by(StudySession.opened_at, StudySession.id)
                                  .limit(page_size)).all()
        db.session.rollback()
        if not rows:
            return
        cursor = (rows[-1].opened_at, rows[-1].id)
        for row in rows:
            if not _time_available(report, started):
                return
            report.purge_candidate_sessions += 1
            if len(report.samples) < 5:
                report.samples.append(str(row.id))
            member_cursor = 0
            while _time_available(report, started):
                remaining = report.max_memberships - report.purged_session_cards
                if remaining <= 0:
                    report.scan_complete, report.stop_reason = False, "membership_budget"
                    return
                if apply:
                    db.session.execute(select(StudySession.id).where(StudySession.id == row.id)
                                       .with_for_update()).scalar_one_or_none()
                    eligible = db.session.execute(select(StudySession.id)
                                                  .where(StudySession.id == row.id, condition)
                                                  .with_for_update()).scalar_one_or_none()
                    if eligible is None:
                        db.session.rollback()
                        break
                ids = list(db.session.execute(
                    select(StudySessionCard.id).where(StudySessionCard.session_id == row.id,
                                                     StudySessionCard.id > member_cursor)
                    .order_by(StudySessionCard.id).limit(min(report.batch_memberships, remaining))
                ).scalars())
                if not ids:
                    db.session.rollback()
                    break
                member_cursor = ids[-1]
                if apply:
                    pins = db.session.execute(delete(StudySessionAuthorityPin)
                                              .where(StudySessionAuthorityPin.session_card_id.in_(ids))
                                              .execution_options(synchronize_session=False))
                    cards = db.session.execute(delete(StudySessionCard).where(StudySessionCard.id.in_(ids))
                                               .execution_options(synchronize_session=False))
                    removed_pins, removed_cards = int(pins.rowcount or 0), int(cards.rowcount or 0)
                    exhausted = not db.session.execute(select(StudySessionCard.id)
                                                       .where(StudySessionCard.session_id == row.id)
                                                       .limit(1)).first()
                    db.session.commit()
                    report.batches += 1
                    report.purged_pins += removed_pins
                    report.purged_session_cards += removed_cards
                    if exhausted:
                        report.purged_sessions += 1
                        break
                else:
                    report.purged_pins += int(db.session.execute(
                        select(db.func.count()).select_from(StudySessionAuthorityPin)
                        .where(StudySessionAuthorityPin.session_card_id.in_(ids))
                    ).scalar_one())
                    report.purged_session_cards += len(ids)
                    db.session.rollback()


def run_session_retention(
    *, now_utc: datetime | None = None, older_than_days: int = DEFAULT_RETENTION_DAYS,
    grace: timedelta = DEFAULT_EXPIRY_GRACE, batch_sessions: int = DEFAULT_BATCH_SESSIONS,
    batch_memberships: int = DEFAULT_BATCH_MEMBERSHIPS, max_memberships: int = DEFAULT_MAX_MEMBERSHIPS,
    max_expired_sessions: int = 1000, max_seconds: float = DEFAULT_MAX_SECONDS, apply: bool = False,
) -> SessionRetentionReport:
    if int(older_than_days) < DEFAULT_RETENTION_DAYS:
        raise ValueError("Session detail must be kept at least 30 days.")
    if grace < timedelta(0) or min(batch_sessions, batch_memberships, max_memberships,
                                  max_expired_sessions, max_seconds) <= 0:
        raise ValueError("Retention budgets must be positive and expiry grace nonnegative.")
    now = (now_utc or datetime.utcnow()).replace(microsecond=0)
    started = time.monotonic()
    report = SessionRetentionReport(applied=bool(apply), now_utc=now.isoformat() + "Z",
                                    batch_memberships=int(batch_memberships),
                                    max_memberships=int(max_memberships), max_seconds=float(max_seconds))
    cutoff = now - timedelta(days=int(older_than_days))
    report.cutoff_utc = cutoff.isoformat() + "Z"
    try:
        with _runner_lease(apply):
            _expire(now=now, grace=grace, page_size=int(batch_sessions), apply=apply, report=report,
                    started=started, max_expired_sessions=int(max_expired_sessions))
            if report.stop_reason != "time_budget":
                _purge(cutoff=cutoff, page_size=int(batch_sessions), apply=apply, report=report, started=started)
        return report
    finally:
        db.session.rollback()
        report.elapsed_seconds = round(time.monotonic() - started, 3)
