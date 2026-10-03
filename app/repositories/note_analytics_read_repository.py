"""Non-locking NOTE analytics reads over canonical availability.

Dashboard and overview counts read the ``study_progress_availability`` row of
each Card's ACTIVE contributor from one consistent snapshot. Nothing here
locks, creates tokens or materializes state, so these reads may run inside
``analytics_read_transaction()``.

Evidence integrity is checked set-wise with the locking reader's error codes,
so analytics routes keep answering 409 on divergent NOTE evidence. Two things
the locking reader does are deliberately left out:

* a missing token is not an error: the locking reader creates it from the
  current state, and the next writer does the same;
* the semantic hash of each ``CardProgress`` compatibility row is not
  recomputed: that content parity is ``study-authority-read-audit``'s job.
  Only the row linkage (row present, contributor id/revision) is checked.

Under the ``CANONICAL_V1`` storage profile (ADR P9-03) nothing here joins
``card_progress``: the projection is frozen, so neither its presence nor its
linkage is evidence any more.
"""

from __future__ import annotations

from sqlalchemy import LargeBinary, and_, case, cast, false, func, literal, not_, null, or_, select
from sqlalchemy.orm import Session, aliased

from app.services.study_progress_contract import (
    CONSOLIDATED_STORAGE_PROFILE,
    DEFAULT_STORAGE_PROFILE,
    PROJECTION_VERSION,
)
from models.card import Card
from models.card_progress import CardProgress
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
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


def reads_projection(storage_profile: str) -> bool:
    """Whether NOTE reads still verify the ``card_progress`` projection."""

    return storage_profile == DEFAULT_STORAGE_PROFILE


def note_card_rows(
    scope, *, learner_user_id: int, storage_profile: str = DEFAULT_STORAGE_PROFILE
):
    """Canonical availability plus a violation rank for each Card in ``scope``.

    ``scope`` is a subquery exposing ``deck_id``, ``card_id`` and ``note_id``.
    A Note without current state (pristine) yields NULL availability and reads
    as NEW, exactly like the locking reader.
    """

    subject = aliased(StudyProgressSubject)
    if storage_profile == CONSOLIDATED_STORAGE_PROFILE:
        # ADR P10 §2.7: the Note's row holds its availability; nothing to cross-check.
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
    state = aliased(StudyProgressState)
    token = aliased(StudyAuthoritySubjectToken)
    contributor = aliased(StudyProgressContributor)
    availability = aliased(StudyProgressAvailability)
    linked = reads_projection(storage_profile)
    progress = aliased(CardProgress)
    progress_present = progress.id.isnot(None) if linked else false()
    progress_missing = progress.id.is_(None) if linked else false()
    progress_unlinked = (
        or_(
            contributor.live_card_progress_id.is_(None),
            contributor.live_card_progress_id != progress.id,
            contributor.card_progress_revision != progress.revision,
        )
        if linked
        else false()
    )

    stateful = state.subject_id.isnot(None)
    has_token = token.subject_id.isnot(None)
    pristine_subject = and_(
        subject.status_code == "NO_CURRENT_PROGRESS",
        subject.contributor_count == 0,
        subject.authority_vector_hash.is_(None),
        subject.lineage_vector_hash.is_(None),
        subject.live_note_id == scope.c.note_id,
    )
    violation = case(
        # I9: a Note without state must carry no other NOTE or compatibility evidence.
        (and_(~stateful, subject.id.isnot(None), not_(pristine_subject)), 1),
        (and_(~stateful, or_(contributor.id.isnot(None), progress_present)), 1),
        # I3
        (and_(stateful, or_(subject.live_note_id.is_(None), subject.live_note_id != scope.c.note_id)), 2),
        # I1/I2 generation
        (and_(stateful, or_(
            state.subject_generation != subject.subject_generation,
            and_(has_token, token.subject_generation != subject.subject_generation),
        )), 3),
        # I1/I2 revision and token hash (a missing token is tolerated, see module doc)
        (and_(stateful, or_(
            state.mirror_revision != subject.mirror_revision,
            and_(has_token, or_(
                token.semantic_state_hash.is_(None),
                token.semantic_state_hash != state.semantic_state_hash,
            )),
        )), 4),
        # I4/I5/I6: every Card of a stateful Note has contributor, availability, projection
        (and_(stateful, or_(
            contributor.id.is_(None),
            availability.contributor_id.is_(None),
            progress_missing,
        )), 5),
        # I7/I8
        (and_(stateful, or_(
            contributor.subject_generation != subject.subject_generation,
            availability.subject_generation != subject.subject_generation,
            progress_unlinked,
            availability.projection_version != PROJECTION_VERSION,
            availability.state_schema_version != state.state_schema_version,
            availability.semantic_state_hash != state.semantic_state_hash,
        )), 6),
        else_=0,
    )
    statement = (
        select(
            scope.c.deck_id.label("deck_id"),
            scope.c.card_id.label("card_id"),
            scope.c.note_id.label("note_id"),
            state.subject_id.label("state_subject_id"),
            availability.normalized_queue.label("queue"),
            availability.due_day.label("due_day"),
            availability.due_at.label("due_at"),
            availability.is_suspended.label("is_suspended"),
            availability.is_buried.label("is_buried"),
            availability.buried_until_day.label("buried_until_day"),
            violation.label("violation"),
        )
        .select_from(scope)
        .outerjoin(subject, and_(
            subject.learner_user_id == int(learner_user_id),
            subject.logical_note_key == cast(scope.c.note_id, LargeBinary),
        ))
        .outerjoin(state, state.subject_id == subject.id)
        .outerjoin(token, token.subject_id == subject.id)
        .outerjoin(contributor, and_(
            contributor.subject_id == subject.id,
            contributor.live_card_id == scope.c.card_id,
            contributor.contributor_status == "ACTIVE",
        ))
        .outerjoin(availability, and_(
            availability.contributor_id == contributor.id,
            availability.subject_id == subject.id,
        ))
    )
    if not linked:
        return statement
    return statement.outerjoin(progress, and_(
        progress.card_id == scope.c.card_id,
        progress.user_id == int(learner_user_id),
    ))


def subject_vector_violation(
    session: Session,
    *,
    scope,
    learner_user_id: int,
    storage_profile: str = DEFAULT_STORAGE_PROFILE,
) -> int:
    """I5: each stateful subject covers exactly its live Cards with ACTIVE contributors.

    Under CONSOLIDATED_V1 there are no contributors: the invariant does not exist.
    """

    if storage_profile == CONSOLIDATED_STORAGE_PROFILE:
        return 0
    subject = aliased(StudyProgressSubject)
    active_contributors = (
        select(func.count(StudyProgressContributor.id))
        .where(
            StudyProgressContributor.subject_id == subject.id,
            StudyProgressContributor.contributor_status == "ACTIVE",
        )
        .scalar_subquery()
    )
    live_cards = (
        select(func.count(Card.id))
        .where(Card.note_id == subject.live_note_id)
        .scalar_subquery()
    )
    found = session.execute(
        select(subject.id)
        .join(StudyProgressState, StudyProgressState.subject_id == subject.id)
        .where(
            subject.learner_user_id == int(learner_user_id),
            subject.live_note_id.in_(select(scope.c.note_id)),
            or_(
                subject.contributor_count != active_contributors,
                subject.contributor_count != live_cards,
            ),
        )
        .limit(1)
    ).first()
    return 5 if found is not None else 0


def learner_note_scope(
    *, learner_user_id: int, storage_profile: str = DEFAULT_STORAGE_PROFILE
):
    """Every Card the learner's NOTE progress touches: stateful Notes plus projections.

    Mirrors the overview's former reader input (every learner ``CardProgress``
    Card) and adds Cards of stateful Notes, so a missing projection is caught.
    Under ``CANONICAL_V1`` only stateful Notes count.
    """

    stateful_cards = (
        select(
            Card.id.label("card_id"),
            Card.note_id.label("note_id"),
        )
        .join(StudyProgressSubject, and_(
            StudyProgressSubject.learner_user_id == int(learner_user_id),
            StudyProgressSubject.live_note_id == Card.note_id,
        ))
    )
    if storage_profile == CONSOLIDATED_STORAGE_PROFILE:
        stateful_cards = stateful_cards.where(StudyProgressSubject.semantic_state_hash.isnot(None))
    else:
        stateful_cards = stateful_cards.join(
            StudyProgressState, StudyProgressState.subject_id == StudyProgressSubject.id
        )
    projected_cards = (
        select(
            Card.id.label("card_id"),
            Card.note_id.label("note_id"),
        )
        .join(CardProgress, and_(
            CardProgress.card_id == Card.id,
            CardProgress.user_id == int(learner_user_id),
        ))
    )
    cards = (
        stateful_cards.union(projected_cards)
        if reads_projection(storage_profile)
        else stateful_cards
    ).subquery("learner_cards")
    return select(
        null().label("deck_id"),
        cards.c.card_id,
        cards.c.note_id,
    ).subquery("learner_note_scope")
