"""Read-only evidence for the Phase 9 contraction gates.

Phase 9 removes old storage and compatibility code only after telemetry
proves nothing still uses it, and every destructive step needs a verified
backup and a separate approval. This report only counts; it never writes.
Each gate is ``ready`` when its evidence is empty over the observation window
and ``waiting`` otherwise, with ``blocking_reasons`` where the cause is not
plain usage. Owner decisions D9-01/D9-02 (docs/task/decoupling/
P9_EXECUTION_PLAN_2026-09-30.md) removed the former ``decision`` status.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, select

from app.validators.study_session_wire import SESSION_SCHEMA_V4
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.connect_source_card_ref import ConnectSourceCardRef
from models.study_application import StudyApplication
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_session import StudySession
from models.user import User

SCHEMA_VERSION = "study-phase9-readiness.v2"
PROJECTION_DEPENDENT_NOTE_CODE = "NOTE_STILL_DEPENDS_ON_PROJECTION"


def _count(statement) -> int:
    return int(db.session.execute(statement).scalar_one() or 0)


def build_phase9_readiness(*, now_utc: datetime | None = None, window_days: int = 30) -> dict:
    now = (now_utc or datetime.utcnow()).replace(microsecond=0)
    since = now - timedelta(days=int(window_days))

    legacy_learners = _count(
        select(func.count()).select_from(StudyAuthorityEnrollment)
        .where(StudyAuthorityEnrollment.mode_code == "LEGACY")
    )
    unenrolled_users = _count(
        select(func.count()).select_from(User).where(
            ~select(StudyAuthorityEnrollment.learner_user_id)
            .where(StudyAuthorityEnrollment.learner_user_id == User.id)
            .exists()
        )
    )
    old_wire_rows = db.session.execute(
        select(StudySession.wire_schema_version, func.count(), func.max(StudySession.opened_at))
        .where(
            StudySession.opened_at >= since,
            func.coalesce(StudySession.wire_schema_version, "") != SESSION_SCHEMA_V4,
        )
        .group_by(StudySession.wire_schema_version)
    ).all()
    old_wire_open = _count(
        select(func.count()).select_from(StudySession).where(
            StudySession.status == "open",
            func.coalesce(StudySession.wire_schema_version, "") != SESSION_SCHEMA_V4,
        )
    )
    unbound_cards = _count(select(func.count()).select_from(Card).where(Card.application_id.is_(None)))
    ordinal_less = _count(
        select(func.count()).select_from(StudyApplication).where(StudyApplication.source_ord.is_(None))
    )
    unbound_refs = _count(
        select(func.count()).select_from(ConnectSourceCardRef).where(ConnectSourceCardRef.card_id.is_(None))
    )
    card_progress_rows = _count(select(func.count()).select_from(CardProgress))
    db.session.rollback()

    old_wire = {
        str(version or "<none>"): {"sessions": int(count), "last_opened_utc": last.isoformat() + "Z"}
        for version, count, last in old_wire_rows
    }
    # D9-02 replaced D6-02: NOTE keeps new data and repairs come from backup,
    # so the projection gate is technical, not a product decision.
    projection_blockers = []
    if legacy_learners:
        projection_blockers.append("LEGACY_LEARNERS")
    if unenrolled_users:
        projection_blockers.append("UNENROLLED_USERS")
    # NOTE readers/writers still validate and write CardProgress until the
    # projection-independent contract (P9-03..P9-05b) ships.
    projection_blockers.append(PROJECTION_DEPENDENT_NOTE_CODE)
    gates = {
        "legacy_projection_writes": {
            "evidence": {"legacy_learners": legacy_learners, "unenrolled_users": unenrolled_users,
                         "card_progress_rows": card_progress_rows},
            "status": "waiting" if projection_blockers else "ready",
            "blocking_reasons": projection_blockers,
        },
        "old_session_wire_versions": {
            "evidence": {"sessions_in_window": old_wire, "open_sessions": old_wire_open},
            "status": "ready" if not old_wire and not old_wire_open else "waiting",
        },
        "positional_anki_ordinals": {
            "evidence": {"cards_without_occurrence": unbound_cards,
                         "occurrences_without_ordinal": ordinal_less,
                         "connect_refs_without_card": unbound_refs},
            "status": "ready" if not unbound_cards and not ordinal_less else "waiting",
        },
    }
    return {
        "schema_version": SCHEMA_VERSION,
        "observed_at_utc": now.isoformat() + "Z",
        "window_days": int(window_days),
        "gates": gates,
        "destructive_steps_allowed": False,
        "note": "Every removal still needs a verified backup, restore proof and a separate approval.",
    }
