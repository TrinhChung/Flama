"""Non-locking NOTE analytics reads over the consolidated progress rows (ADR P10).

Dashboard, overview and queue counts read each Note's availability from its
``study_progress_subjects`` row in one consistent snapshot. Nothing here
locks, writes or materializes state, so these reads may run inside
``analytics_read_transaction()``. There is no cross-table evidence left to
check on the read path: the offline audit re-derives availability from state.
"""

from __future__ import annotations

from sqlalchemy import LargeBinary, and_, case, cast, literal, null, select
from sqlalchemy.orm import Session, aliased

from models.card import Card
from models.study_progress_subject import StudyProgressSubject

# Index = violation rank carried in SQL; 0 means consistent evidence.
VIOLATION_CODES = (
    None,
    "INCOMPLETE_AUTHORITY_COVERAGE",
    "DETACHED_AUTHORITY_SUBJECT",
    "AUTHORITY_GENERATION_DIVERGED",
    "AUTHORITY_STATE_DIVERGED",
    "INCOMPLETE_AUTHORITY_COMPATIBILITY",
    "AUTHORITY_READ_PARITY_DIVERGED",
)
_VIOLATION_MESSAGES = {
    "INCOMPLETE_AUTHORITY_COVERAGE": "A Note has NOTE evidence without current NOTE state.",
    "DETACHED_AUTHORITY_SUBJECT": "A NOTE authority subject is detached from its live Note.",
    "AUTHORITY_GENERATION_DIVERGED": "NOTE state or token generation differs from its subject.",
    "AUTHORITY_STATE_DIVERGED": "NOTE state revision or token hash differs from its subject.",
    "INCOMPLETE_AUTHORITY_COMPATIBILITY": "NOTE analytics has no complete contributor/availability/compatibility vector.",
    "AUTHORITY_READ_PARITY_DIVERGED": "NOTE availability or compatibility linkage differs from current state.",
}


def violation_error(rank: int | None) -> tuple[str, str] | None:
    """Return ``(code, message)`` for a violation rank, or None when clean."""

    if not rank:
        return None
    code = VIOLATION_CODES[int(rank)]
    return code, _VIOLATION_MESSAGES[code]


def note_card_rows(scope, *, learner_user_id: int, storage_profile: str | None = None):
    """Each Note row's availability for each Card in ``scope``.

    ``scope`` is a subquery exposing ``deck_id``, ``card_id`` and ``note_id``.
    A Note without current state (pristine) yields NULL availability and reads
    as NEW, exactly like the locking reader.
    """

    subject = aliased(StudyProgressSubject)
    stateful = subject.semantic_state_hash.isnot(None)
    return (
        select(
            scope.c.deck_id.label("deck_id"),
            scope.c.card_id.label("card_id"),
            scope.c.note_id.label("note_id"),
            case((stateful, subject.id), else_=null()).label("state_subject_id"),
            subject.normalized_queue.label("queue"),
            subject.due_day.label("due_day"),
            subject.due_at.label("due_at"),
            subject.is_suspended.label("is_suspended"),
            subject.is_buried.label("is_buried"),
            subject.buried_until_day.label("buried_until_day"),
            literal(0).label("violation"),
        )
        .select_from(scope)
        .outerjoin(subject, and_(
            subject.learner_user_id == int(learner_user_id),
            subject.logical_note_key == cast(scope.c.note_id, LargeBinary),
        ))
    )


def subject_vector_violation(session: Session, *, scope, learner_user_id: int, storage_profile: str | None = None) -> int:
    """Former I5 (contributor coverage): Cards carry no progress any more."""

    return 0


def learner_note_scope(*, learner_user_id: int, storage_profile: str | None = None):
    """Every Card of a Note the learner holds current NOTE state on."""

    cards = (
        select(
            Card.id.label("card_id"),
            Card.note_id.label("note_id"),
        )
        .join(StudyProgressSubject, and_(
            StudyProgressSubject.learner_user_id == int(learner_user_id),
            StudyProgressSubject.live_note_id == Card.note_id,
        ))
        .where(StudyProgressSubject.semantic_state_hash.isnot(None))
    ).subquery("learner_cards")
    return select(
        null().label("deck_id"),
        cards.c.card_id,
        cards.c.note_id,
    ).subquery("learner_note_scope")


def consolidated_card_rows(card_query, *, learner_user_id: int):
    """Per Card of ``card_query``: its Note row's availability, state type and interval.

    CONSOLIDATED_V1 only (ADR P10 §2.7): one non-locking SELECT over the rows of
    Notes with current state, for analytics that need no full state read.
    Yields ``(card_id, queue, due_at, due_day, is_suspended, state_type,
    interval_token)``; decode the interval with :func:`state_interval_days`.
    """

    subject = StudyProgressSubject
    return (
        card_query.join(subject, and_(
            subject.learner_user_id == int(learner_user_id),
            subject.live_note_id == Card.note_id,
        ))
        .filter(subject.semantic_state_hash.isnot(None))
        .with_entities(
            Card.id,
            subject.normalized_queue,
            subject.due_at,
            subject.due_day,
            subject.is_suspended,
            subject.state_payload["type"].as_string(),
            subject.state_payload["interval_days"].as_string(),
        )
    )


def state_interval_days(token) -> float:
    """``interval_days`` of a canonical state payload (MySQL unquotes JSON null as 'null')."""

    from app.services.study_progress_shadow_codec import decode_float

    if token is None or token == "null":
        return 0.0
    return float(decode_float(token, field_name="interval_days") or 0.0)

