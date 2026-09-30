"""Phase 7 retention of Study Session execution detail.

Two idempotent steps, dry-run by default:

1. ``open`` sessions whose lease ended more than ``grace`` ago become
   ``expired``. Their commits and batches are already refused with
   ``SESSION_EXPIRED``; the status only stops them staying open forever.
2. Membership rows (``study_session_cards`` and their NOTE pins) of sessions
   that ended (``committed``/``cancelled``/``expired``) more than
   ``older_than_days`` ago are deleted in small batches.

Learner data is never touched: ``study_sessions`` rows (the provenance that
``review_events`` point to), commit receipts, review events, history facts
and every progress/authority table stay. No statistic reads the membership
rows, so dashboards and history are identical before and after.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta

from sqlalchemy import and_, delete, exists, select, update

from models import db
from models.study_session import StudySession
from models.study_session_authority_pin import StudySessionAuthorityPin
from models.study_session_batch import StudySessionBatch
from models.study_session_card import StudySessionCard

TERMINAL_STATUSES = ("committed", "cancelled", "expired")
DEFAULT_RETENTION_DAYS = 30
DEFAULT_EXPIRY_GRACE = timedelta(hours=24)
DEFAULT_BATCH_SESSIONS = 200


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
    cutoff_utc: str = ""
    samples: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dict(self.__dict__)


def _pending_batch_exists():
    return exists().where(
        StudySessionBatch.session_id == StudySession.id,
        StudySessionBatch.status == "enqueued",
    )


def close_expired_sessions(*, now_utc: datetime, grace: timedelta, apply: bool) -> int:
    """Mark open sessions whose lease ended before ``now - grace`` as expired."""

    limit = now_utc - grace
    condition = and_(
        StudySession.status == "open",
        StudySession.expires_at < limit,
        ~_pending_batch_exists(),
    )
    if not apply:
        return int(db.session.execute(
            select(db.func.count()).select_from(StudySession).where(condition)
        ).scalar_one())
    result = db.session.execute(
        update(StudySession)
        .where(condition)
        .values(status="expired", updated_at=now_utc)
        .execution_options(synchronize_session=False)
    )
    db.session.commit()
    return int(result.rowcount or 0)


def purge_session_detail(
    *,
    now_utc: datetime,
    older_than_days: int,
    batch_sessions: int,
    apply: bool,
    report: SessionRetentionReport,
) -> None:
    """Delete membership rows of long-finished sessions, one batch per transaction."""

    cutoff = now_utc - timedelta(days=int(older_than_days))
    report.cutoff_utc = cutoff.isoformat() + "Z"
    has_cards = exists().where(StudySessionCard.session_id == StudySession.id)
    candidates = (
        select(StudySession.id)
        .where(
            StudySession.status.in_(TERMINAL_STATUSES),
            StudySession.opened_at < cutoff,
            StudySession.expires_at < cutoff,
            has_cards,
            ~_pending_batch_exists(),
        )
        .order_by(StudySession.opened_at.asc(), StudySession.id.asc())
    )
    session_ids = [str(value) for value in db.session.execute(candidates).scalars()]
    report.purge_candidate_sessions = len(session_ids)
    report.samples = session_ids[:5]
    if not apply:
        report.purged_session_cards = int(db.session.execute(
            select(db.func.count()).select_from(StudySessionCard)
            .where(StudySessionCard.session_id.in_(session_ids))
        ).scalar_one()) if session_ids else 0
        db.session.rollback()
        return
    db.session.rollback()
    for start in range(0, len(session_ids), max(1, int(batch_sessions))):
        chunk = session_ids[start:start + max(1, int(batch_sessions))]
        # Re-check inside the batch transaction: the session may have changed.
        locked = [
            str(value)
            for value in db.session.execute(
                select(StudySession.id)
                .where(
                    StudySession.id.in_(chunk),
                    StudySession.status.in_(TERMINAL_STATUSES),
                    StudySession.opened_at < cutoff,
                    StudySession.expires_at < cutoff,
                    ~_pending_batch_exists(),
                )
                .with_for_update()
            ).scalars()
        ]
        if not locked:
            db.session.rollback()
            continue
        member_ids = select(StudySessionCard.id).where(StudySessionCard.session_id.in_(locked))
        pins = db.session.execute(
            delete(StudySessionAuthorityPin)
            .where(StudySessionAuthorityPin.session_card_id.in_(member_ids))
            .execution_options(synchronize_session=False)
        )
        cards = db.session.execute(
            delete(StudySessionCard)
            .where(StudySessionCard.session_id.in_(locked))
            .execution_options(synchronize_session=False)
        )
        db.session.commit()
        report.batches += 1
        report.purged_sessions += len(locked)
        report.purged_pins += int(pins.rowcount or 0)
        report.purged_session_cards += int(cards.rowcount or 0)


def run_session_retention(
    *,
    now_utc: datetime | None = None,
    older_than_days: int = DEFAULT_RETENTION_DAYS,
    grace: timedelta = DEFAULT_EXPIRY_GRACE,
    batch_sessions: int = DEFAULT_BATCH_SESSIONS,
    apply: bool = False,
) -> SessionRetentionReport:
    if int(older_than_days) < 2:
        raise ValueError("Session detail must be kept at least two days (the lease is 24 h).")
    now = (now_utc or datetime.utcnow()).replace(microsecond=0)
    report = SessionRetentionReport(applied=bool(apply), now_utc=now.isoformat() + "Z")
    report.expired_sessions = close_expired_sessions(now_utc=now, grace=grace, apply=apply)
    purge_session_detail(
        now_utc=now,
        older_than_days=older_than_days,
        batch_sessions=batch_sessions,
        apply=apply,
        report=report,
    )
    return report
