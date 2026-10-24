"""Non-locking NOTE analytics reads over the consolidated progress rows (ADR P10).

Dashboard, overview and queue counts read each Note's availability from its
``study_progress_subjects`` row in one consistent snapshot. Nothing here
locks, writes or materializes state, so these reads may run inside
``analytics_read_transaction()``. Cheap envelope identity and presence checks
can share required aggregates. The offline audit re-derives whole-store
availability and hashes from state; Browse validates its returned page fully.
"""

from __future__ import annotations

from sqlalchemy import LargeBinary, and_, case, cast, literal, null, or_, select
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


def learner_live_identity_drift(session: Session, *, learner_user_id: int) -> bool:
    """Whether any of the learner's rows points its live Note at another logical key.

    A learner-wide superset of the per-Note ``wrong_live_identity`` probe in
    :func:`subject_integrity_violation`: a row with ``live_note_id = n`` and a
    logical key other than ``n`` is exactly what that probe finds for Note
    ``n``. When this is False the per-Note probe is false for every Note, so a
    caller that only needs the worst violation may drop it (one learner scan
    instead of one probe per Note). Run it in the same read snapshot.
    """

    live = StudyProgressSubject
    return session.execute(select(literal(1)).where(
        live.learner_user_id == int(learner_user_id),
        live.live_note_id.isnot(None),
        live.logical_note_key != cast(live.live_note_id, LargeBinary),
    ).limit(1)).first() is not None


def subject_integrity_violation(subject, *, note_id, learner_user_id: int,
                                check_live_identity: bool = True):
    """Cheap identity/presence guard folded into an existing aggregate.

    This does not re-decode every state payload or recompute hashes. The
    canonical writer owns availability; full state/hash validation is bounded
    to returned rows, and the read-only retirement audit checks whole stores.
    A detached or partial envelope must never silently count as pristine.
    ``check_live_identity=False`` omits the per-Note live-pointer probe; only
    pass it after :func:`learner_live_identity_drift` returned False.
    """

    from app.services.study_progress_contract import (
        SUBJECT_AVAILABILITY_NULLABLE_COLUMNS, SUBJECT_PROGRESS_COLUMNS,
    )

    present = and_(*(getattr(subject, key).isnot(None) for key in SUBJECT_PROGRESS_COLUMNS))
    absent = and_(*(getattr(subject, key).is_(None) for key in (
        *SUBJECT_PROGRESS_COLUMNS, *SUBJECT_AVAILABILITY_NULLABLE_COLUMNS,
    )))
    live_identity_case = ()
    if check_live_identity:
        # The canonical logical-key join cannot see a row whose key was damaged.
        # A second indexed live-Note probe catches that relevant evidence even
        # when the canonical envelope is absent, without an OR join/full scan.
        live = aliased(StudyProgressSubject)
        wrong_live_identity = select(literal(1)).where(
            live.learner_user_id == int(learner_user_id), live.live_note_id == note_id,
            live.logical_note_key != cast(note_id, LargeBinary),
        ).correlate_except(live).exists()
        live_identity_case = ((wrong_live_identity, 2),)
    return case(
        *live_identity_case,
        (subject.id.is_(None), 0),
        (or_(subject.live_note_id.is_(None), subject.live_note_id != note_id,
             subject.logical_note_key != cast(note_id, LargeBinary),
             subject.status_code.in_(['TOMBSTONED_RESET', 'TOMBSTONED_SUBJECT_DELETED',
                                     'REKEYED_CLONE_CUTOVER'])), 2),
        (or_(and_(subject.semantic_state_hash.isnot(None), ~present),
             and_(subject.semantic_state_hash.is_(None),
                  or_(~absent, subject.status_code != 'NO_CURRENT_PROGRESS'))), 1),
        else_=0,
    )


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
            subject_integrity_violation(subject, note_id=scope.c.note_id,
                                        learner_user_id=learner_user_id).label("violation"),
        )
        .select_from(scope)
        .outerjoin(subject, and_(
            subject.learner_user_id == int(learner_user_id),
            subject.logical_note_key == cast(scope.c.note_id, LargeBinary),
        ))
    )


def note_rows(scope, *, learner_user_id: int, include_state: bool = False,
              include_violation: bool = True, check_live_identity: bool = True):
    """Availability once per scoped Note; Card metrics carry a multiplicity.

    Both identity probes are retained. A live-key match alone is not equivalent
    to the canonical logical-key join when historical evidence is damaged.
    Callers that never read ``violation`` should set ``include_violation=False``:
    MySQL materializes the derived rows and would still evaluate it per Note.
    See :func:`subject_integrity_violation` for ``check_live_identity``.
    """
    subject = aliased(StudyProgressSubject)
    columns = [
        scope.c.deck_id, scope.c.note_id, scope.c.card_count,
        subject.normalized_queue.label("queue"), subject.due_day, subject.due_at,
        subject.is_suspended, subject.is_buried, subject.buried_until_day,
    ]
    if include_violation:
        columns.append(subject_integrity_violation(
            subject, note_id=scope.c.note_id, learner_user_id=learner_user_id,
            check_live_identity=check_live_identity,
        ).label("violation"))
    if include_state:
        columns.extend([
            subject.state_payload["type"].as_string().label("state_type"),
            subject.state_payload["interval_days"].as_string().label("interval_token"),
        ])
    return select(*columns).select_from(scope).outerjoin(subject, and_(
        subject.learner_user_id == int(learner_user_id),
        subject.logical_note_key == cast(scope.c.note_id, LargeBinary),
    ))


def subject_vector_violation(session: Session, *, scope, learner_user_id: int, storage_profile: str | None = None) -> int:
    """Former I5 (contributor coverage): Cards carry no progress any more."""

    return 0


def learner_note_scope(*, learner_user_id: int, storage_profile: str | None = None):
    """Visible owned/install Notes whose live Note holds current state.

    The shared scope preserves release-pinned retired applications and local
    added Notes. An outer ORM statement embedding this scope must retain
    ``include_retired_cards=True``; its owned branch explicitly selects ACTIVE
    applications, while the overlay branch enforces its release pin.
    """

    from models import db
    from app.repositories.note_analytics_scope_repository import collection_note_scope

    scope = collection_note_scope(db.session, learner_user_id=learner_user_id)
    # A bounded scalar presence probe has the same semantics as EXISTS. It
    # prevents MySQL's semijoin rewrite from placing application counts before
    # the Note join (measured 31 x 39k intermediate rows on the production set).
    state = select(literal(1)).where(
        StudyProgressSubject.learner_user_id == int(learner_user_id),
        StudyProgressSubject.live_note_id == scope.c.note_id,
        StudyProgressSubject.semantic_state_hash.isnot(None),
    ).correlate(scope).limit(1).scalar_subquery().isnot(None)
    return select(scope.c.deck_id, scope.c.note_id, scope.c.card_count).where(state).subquery("learner_note_scope")


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

