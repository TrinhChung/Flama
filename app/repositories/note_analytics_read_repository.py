"""Non-locking NOTE analytics reads over the consolidated progress rows (ADR P10).

Dashboard, overview and queue counts read each Note's availability from its
``study_progress_subjects`` row in one consistent snapshot. Nothing here
locks, writes or materializes state, so these reads may run inside
``analytics_read_transaction()``. Unreadable evidence fails closed through
:func:`guard_scope`, which the shared scope builders run before returning a
scope; metric queries carry no integrity column. The offline audit
re-derives whole-store availability and hashes from state; Browse validates
its returned page fully.
"""

from __future__ import annotations

from sqlalchemy import LargeBinary, and_, case, cast, func, literal, or_, select
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
_UNREADABLE_STATUSES = ("TOMBSTONED_RESET", "TOMBSTONED_SUBJECT_DELETED", "REKEYED_CLONE_CUTOVER")


def violation_error(rank: int | None) -> tuple[str, str] | None:
    """Return ``(code, message)`` for a violation rank, or None when clean."""

    if not rank:
        return None
    code = VIOLATION_CODES[int(rank)]
    return code, _VIOLATION_MESSAGES[code]


def raise_for_violation(rank: int | None) -> None:
    """Raise ``StudyAuthorityReadError`` for a non-zero violation rank."""

    error = violation_error(rank)
    if error is not None:
        from app.services.study_authority_read_service import StudyAuthorityReadError

        raise StudyAuthorityReadError(*error)


def _progress_shape_defect(subject):
    """Rank-1 shape: state without full progress, or progress/status without state."""

    from app.services.study_progress_contract import (
        SUBJECT_AVAILABILITY_NULLABLE_COLUMNS, SUBJECT_PROGRESS_COLUMNS,
    )

    present = and_(*(getattr(subject, key).isnot(None) for key in SUBJECT_PROGRESS_COLUMNS))
    absent = and_(*(getattr(subject, key).is_(None) for key in (
        *SUBJECT_PROGRESS_COLUMNS, *SUBJECT_AVAILABILITY_NULLABLE_COLUMNS,
    )))
    return or_(and_(subject.semantic_state_hash.isnot(None), ~present),
               and_(subject.semantic_state_hash.is_(None),
                    or_(~absent, subject.status_code != 'NO_CURRENT_PROGRESS')))


def subject_integrity_violation(subject, *, note_id, learner_user_id: int):
    """Cheap identity/presence check of one Note's evidence (the violation rank).

    This does not re-decode every state payload or recompute hashes. The
    canonical writer owns availability; full state/hash validation is bounded
    to returned rows, and the read-only retirement audit checks whole stores.
    A detached or partial envelope must never silently count as pristine.
    """

    # The canonical logical-key join cannot see a row whose key was damaged.
    # A second indexed live-Note probe catches that relevant evidence even
    # when the canonical envelope is absent, without an OR join/full scan.
    live = aliased(StudyProgressSubject)
    wrong_live_identity = select(literal(1)).where(
        live.learner_user_id == int(learner_user_id), live.live_note_id == note_id,
        live.logical_note_key != cast(note_id, LargeBinary),
    ).correlate_except(live).exists()
    return case(
        (wrong_live_identity, 2),
        (subject.id.is_(None), 0),
        (or_(subject.live_note_id.is_(None), subject.live_note_id != note_id,
             subject.logical_note_key != cast(note_id, LargeBinary),
             subject.status_code.in_(_UNREADABLE_STATUSES)), 2),
        (_progress_shape_defect(subject), 1),
        else_=0,
    )


def evidence_candidate_note_ids(session: Session, *, learner_user_id: int) -> list[str]:
    """Notes whose evidence :func:`subject_integrity_violation` could flag.

    One scan of the learner's rows, usually empty. Every row condition of the
    violation CASE is matched on the row itself; a row whose live pointer and
    logical key differ is the ``wrong_live_identity`` evidence of its live
    Note. Both keys of a matching row are candidates. A superset: the scope
    decides whether a candidate is read at all (a tombstone of a deleted Note
    is in no scope).
    """

    subject = StudyProgressSubject
    rows = session.execute(select(subject.logical_note_key, subject.live_note_id).where(
        subject.learner_user_id == int(learner_user_id),
        or_(
            subject.live_note_id.is_(None),
            subject.logical_note_key != cast(subject.live_note_id, LargeBinary),
            subject.status_code.in_(_UNREADABLE_STATUSES),
            _progress_shape_defect(subject),
        ),
    )).all()
    candidates = set()
    for logical_key, live_note_id in rows:
        if live_note_id:
            candidates.add(str(live_note_id))
        try:
            candidates.add(bytes(logical_key).decode("utf-8"))
        except UnicodeDecodeError:
            pass  # Not a Note ID; only its live pointer can be read.
    return sorted(candidates)


def guard_scope(session: Session, *, learner_user_id: int, build) -> None:
    """Fail closed when a Note of a scope has unreadable evidence.

    ``build(note_ids)`` returns the caller's scope, restricted to ``note_ids``
    when given. The worst rank over the candidate Notes inside that exact
    scope equals the per-Note rank of the whole scope, because every other
    Note is clean. Run it in the same read snapshot as the metric query.
    """

    note_ids = evidence_candidate_note_ids(session, learner_user_id=learner_user_id)
    if not note_ids:
        return
    scope = build(note_ids=note_ids)
    subject = aliased(StudyProgressSubject)
    worst = session.execute(
        select(func.max(subject_integrity_violation(
            subject, note_id=scope.c.note_id, learner_user_id=learner_user_id,
        )))
        .select_from(scope)
        .outerjoin(subject, and_(
            subject.learner_user_id == int(learner_user_id),
            subject.logical_note_key == cast(scope.c.note_id, LargeBinary),
        ))
        .execution_options(include_retired_cards=True)
    ).scalar()
    raise_for_violation(worst)


def note_rows(scope, *, learner_user_id: int, include_state: bool = False):
    """Availability once per scoped Note; Card metrics carry a multiplicity.

    ``scope`` must come from a guarded builder (``deck_note_scope``,
    ``collection_note_scope`` or :func:`learner_note_scope`), which already
    failed closed on unreadable evidence.
    """
    subject = aliased(StudyProgressSubject)
    columns = [
        scope.c.deck_id, scope.c.note_id, scope.c.card_count,
        subject.normalized_queue.label("queue"), subject.due_day, subject.due_at,
        subject.is_suspended, subject.is_buried, subject.buried_until_day,
    ]
    if include_state:
        columns.extend([
            subject.state_payload["type"].as_string().label("state_type"),
            subject.state_payload["interval_days"].as_string().label("interval_token"),
        ])
    return select(*columns).select_from(scope).outerjoin(subject, and_(
        subject.learner_user_id == int(learner_user_id),
        subject.logical_note_key == cast(scope.c.note_id, LargeBinary),
    ))


def learner_note_scope(*, learner_user_id: int, storage_profile: str | None = None):
    """Visible owned/install Notes whose live Note holds current state (guarded).

    The shared scope preserves release-pinned retired applications and local
    added Notes. An outer ORM statement embedding this scope must retain
    ``include_retired_cards=True``; its owned branch explicitly selects ACTIVE
    applications, while the overlay branch enforces its release pin. The guard
    covers this state-filtered scope: a detached subject's Note is not in it.
    """

    from models import db
    from app.repositories.note_analytics_scope_repository import collection_note_scope_query

    def build(note_ids=None):
        scope = collection_note_scope_query(db.session, learner_user_id=learner_user_id, note_ids=note_ids)
        # A bounded scalar presence probe has the same semantics as EXISTS. It
        # prevents MySQL's semijoin rewrite from placing application counts before
        # the Note join (measured 31 x 39k intermediate rows on the production set).
        state = select(literal(1)).where(
            StudyProgressSubject.learner_user_id == int(learner_user_id),
            StudyProgressSubject.live_note_id == scope.c.note_id,
            StudyProgressSubject.semantic_state_hash.isnot(None),
        ).correlate(scope).limit(1).scalar_subquery().isnot(None)
        return select(scope.c.deck_id, scope.c.note_id, scope.c.card_count).where(state).subquery("learner_note_scope")

    guard_scope(db.session, learner_user_id=learner_user_id, build=build)
    return build()


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

