"""Card study-state reads from the canonical NOTE progress row."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    StudyAuthorityRoute,
    lock_study_authority_route,
)
from app.repositories.study_repository import card_state_from_progress
from app.repositories import study_repository
from app.repositories.study_queue_repository import StudyQueueCardRef
from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
from app.services.anki_scheduler import CardState, DeckOptions
from app.services.study_artifact_service import (
    note_authority_review_state_version,
    review_state_version,
)
from app.services.study_session_authority_pin_service import (
    lock_study_session_authority_subjects,
)
from app.services.study_note_card_projection import NoteCardBurial
from app.services.study_progress_shadow_codec import StudyProgressCodecError
from models.card import Card


@dataclass(frozen=True)
class StudyAuthorityAvailabilityRead:
    normalized_queue: str
    due_at: datetime | None
    due_day: int | None
    is_suspended: bool
    is_buried: bool
    buried_until_day: int | None
    card_created_at: datetime
    card_order_key: bytes


@dataclass(frozen=True)
class StudyAuthorityCardRead:
    route: StudyAuthorityRoute
    state: CardState
    state_version: str
    progress: Any | None
    authority_revision: int | None
    availability: StudyAuthorityAvailabilityRead


@dataclass(frozen=True)
class StudyAuthorityQueueSummary:
    new_count: int
    learn_count: int
    due_count: int
    due_card_ids: tuple[str, ...]
    learn_ahead_card_ids: tuple[str, ...]
    selected_card_id: str | None
    pending_learning_count: int
    next_due_at: datetime | None


class StudyAuthorityReadError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


def _pristine_availability(
    *,
    card: Card,
    progress: Any | None,
    now_utc: datetime,
) -> StudyAuthorityAvailabilityRead:
    return StudyAuthorityAvailabilityRead(
        normalized_queue=study_repository.normalize_progress_queue(
            progress.queue if progress is not None else None
        ),
        due_at=progress.due_at if progress is not None else None,
        due_day=progress.due_day if progress is not None else None,
        is_suspended=bool(progress.is_suspended) if progress is not None else False,
        is_buried=bool(progress.is_buried) if progress is not None else False,
        buried_until_day=(
            progress.buried_until_day if progress is not None else None
        ),
        card_created_at=card.created_at or now_utc,
        card_order_key=str(getattr(card, "order_key", card.id)).encode("utf-8"),
    )


def _availability_from_subject(subject, *, card) -> StudyAuthorityAvailabilityRead:
    return StudyAuthorityAvailabilityRead(
        normalized_queue=str(subject.normalized_queue),
        due_at=subject.due_at,
        due_day=int(subject.due_day) if subject.due_day is not None else None,
        is_suspended=bool(subject.is_suspended),
        is_buried=bool(subject.is_buried),
        buried_until_day=(
            int(subject.buried_until_day) if subject.buried_until_day is not None else None
        ),
        card_created_at=card.created_at,
        card_order_key=str(getattr(card, "order_key", card.id)).encode("utf-8"),
    )


def validate_consolidated_subject_state(*, subject, note_id: str) -> None:
    """A locked consolidated row must agree with its own state (ADR P10 §2.7).

    In memory only: the row's availability and semantic hash are recomputed
    from its state and burial. Readers that do not lock skip this check.
    """

    from app.services.study_note_card_projection import project_note_state

    try:
        projected = project_note_state(
            subject.state_payload,
            burial=NoteCardBurial(
                is_buried=bool(subject.is_buried),
                buried_until_day=(
                    int(subject.buried_until_day) if subject.buried_until_day is not None else None
                ),
            ),
        )
    except StudyProgressCodecError as exc:
        raise StudyAuthorityReadError(
            "AUTHORITY_READ_PARITY_DIVERGED",
            f"Note {note_id} NOTE state cannot be projected: {exc}",
        ) from exc
    if (
        projected.semantic_state_hash != bytes(subject.semantic_state_hash)
        or projected.normalized_queue != subject.normalized_queue
        or projected.due_at != subject.due_at
        or projected.due_day != subject.due_day
        or projected.is_suspended != bool(subject.is_suspended)
        or projected.projection_version != subject.projection_version
    ):
        raise StudyAuthorityReadError(
            "AUTHORITY_READ_PARITY_DIVERGED",
            f"Note {note_id} availability differs from its NOTE state.",
        )



def validate_consolidated_subject(*, card, subject) -> StudyAuthorityAvailabilityRead:
    """Validate a locked Note state, then attach presentation ordering metadata."""
    validate_consolidated_subject_state(subject=subject, note_id=str(card.note_id))
    return _availability_from_subject(subject, card=card)


@dataclass(frozen=True)
class StudyAuthorityAvailabilitySnapshot:
    """Canonical availability of one Card, enough for queue counts and order."""

    availability: StudyAuthorityAvailabilityRead


def load_study_authority_availability_snapshot(
    session: Session,
    *,
    learner_user_id: int,
    cards: Sequence[Card | StudyQueueCardRef],
    scope,
    now_utc: datetime,
    scope_options: Mapping | None = None,
) -> Mapping[str, StudyAuthorityAvailabilitySnapshot]:
    """Non-locking canonical availability for a whole NOTE queue (P5-11e).

    ``summarize_study_authority_queue`` reads nothing but availability, which
    ``load_study_authority_card_reads`` takes verbatim from the canonical row
    (Notes with state) or derives from the Card (never-studied Notes). This
    reads the same values set-wise, without locks or per-Card verification,
    and checks evidence integrity with the dashboard's set-wise rules and the
    locking reader's error codes. ``scope`` is a subquery with ``deck_id``,
    ``card_id`` and ``note_id`` covering ``cards``; ``scope_options`` are the
    execution options it was built under (``card_scope_options``). Callers
    still take a full locking read of the Cards they return or answer.
    """

    from sqlalchemy import LargeBinary, and_, cast

    from models.study_progress_subject import StudyProgressSubject

    # ADR P10 §2.7: one row per Note, no cross-table evidence to check.
    # Only the availability columns: the state payload is not needed here.
    stateful = {
        str(row.card_id): row
        for row in session.execute(
            select(
                scope.c.card_id,
                StudyProgressSubject.normalized_queue,
                StudyProgressSubject.due_at,
                StudyProgressSubject.due_day,
                StudyProgressSubject.is_suspended,
                StudyProgressSubject.is_buried,
                StudyProgressSubject.buried_until_day,
            )
            .select_from(scope)
            .join(StudyProgressSubject, and_(
                StudyProgressSubject.learner_user_id == int(learner_user_id),
                StudyProgressSubject.logical_note_key == cast(scope.c.note_id, LargeBinary),
            ))
            .where(StudyProgressSubject.semantic_state_hash.isnot(None))
            .execution_options(**dict(scope_options or {}))
        ).all()
    }
    return MappingProxyType({
        str(card.id): StudyAuthorityAvailabilitySnapshot(
            availability=(
                _availability_from_subject(stateful[str(card.id)], card=card)
                if str(card.id) in stateful
                else _pristine_availability(card=card, progress=None, now_utc=now_utc)
            )
        )
        for card in cards
    })


def load_study_authority_card_read(
    session: Session,
    *,
    learner_user_id: int,
    card: Card,
    now_utc: datetime,
    timezone_name: str,
    deck_options: DeckOptions,
) -> StudyAuthorityCardRead:
    """Resolve LEGACY or NOTE state under one stable learner authority fence."""

    return load_study_authority_card_reads(
        session,
        learner_user_id=learner_user_id,
        cards=(card,),
        now_utc=now_utc,
        timezone_name=timezone_name,
        deck_options_by_card_id={str(card.id): deck_options},
    )[str(card.id)]


def load_study_authority_card_reads(
    session: Session,
    *,
    learner_user_id: int,
    cards: Sequence[Card],
    now_utc: datetime,
    timezone_name: str,
    deck_options_by_card_id: Mapping[str, DeckOptions],
) -> Mapping[str, StudyAuthorityCardRead]:
    """Resolve a complete Card vector with canonical NOTE subject lock order."""

    route = lock_study_authority_route(
        session,
        learner_user_id=learner_user_id,
        allow_note_authority=True,
    )
    requested_card_by_id = {str(item.id): item for item in cards}
    if not requested_card_by_id:
        return MappingProxyType({})
    if set(requested_card_by_id) != set(deck_options_by_card_id):
        raise ValueError("Every authority read Card requires frozen deck options.")
    from app.repositories.study_authority_repository import StudyAuthorityFenceError
    from app.services.study_artifact_service import pristine_note_review_state_version
    from app.services.study_note_pristine_service import classify_note_authority_keys

    try:
        stateful_keys, pristine_keys = classify_note_authority_keys(
            session,
            learner_user_id=learner_user_id,
            note_ids={str(card.note_id) for card in requested_card_by_id.values()},
            storage_profile=route.storage_profile,
        )
    except StudyAuthorityFenceError as exc:
        raise StudyAuthorityReadError(exc.code, str(exc)) from exc
    # Never-studied Notes read exactly like LEGACY Cards without progress.
    result: dict[str, StudyAuthorityCardRead] = {
        card_id: StudyAuthorityCardRead(
            route=route,
            state=card_state_from_progress(
                None,
                now_utc,
                timezone_name=timezone_name,
                user_id=learner_user_id,
                options=deck_options_by_card_id[card_id],
            ),
            state_version=pristine_note_review_state_version(
                enrollment_epoch=route.epoch,
                logical_note_key=str(card.note_id),
                deck_options=deck_options_by_card_id[card_id],
                timezone_name=timezone_name,
            ),
            progress=None,
            authority_revision=0,
            availability=_pristine_availability(
                card=card,
                progress=None,
                now_utc=now_utc,
            ),
        )
        for card_id, card in sorted(requested_card_by_id.items())
        if str(card.note_id) in pristine_keys
    }
    requested_card_by_id = {
        card_id: card
        for card_id, card in requested_card_by_id.items()
        if str(card.note_id) in stateful_keys
    }
    if not requested_card_by_id:
        return MappingProxyType(result)
    logical_note_keys = sorted(stateful_keys)
    subjects = lock_study_session_authority_subjects(
        session,
        route=route,
        logical_note_keys=logical_note_keys,
        now_utc=now_utc,
    )
    # Caller supplies authorized presentations; validate each requested Note once.
    card_by_id = requested_card_by_id
    validated_note_keys: set[str] = set()
    for card_id in sorted(card_by_id):
        if card_id not in requested_card_by_id:
            continue
        card = card_by_id[card_id]
        logical_note_key = str(card.note_id)
        locked = subjects.locked_by_logical_note_key[logical_note_key]
        if logical_note_key not in validated_note_keys:
            validate_consolidated_subject(card=card, subject=locked.subject)
            validated_note_keys.add(logical_note_key)
        result[card_id] = StudyAuthorityCardRead(
            route=route,
            state=subjects.state_by_logical_note_key[logical_note_key],
            state_version=note_authority_review_state_version(
                enrollment_epoch=route.epoch,
                logical_note_key=logical_note_key,
                subject_generation=int(locked.subject.subject_generation),
                authority_revision=int(locked.token.authority_revision),
                semantic_state_hash=bytes(locked.token.semantic_state_hash),
                deck_options=deck_options_by_card_id[card_id],
                timezone_name=timezone_name,
            ),
            progress=None,
            authority_revision=int(locked.token.authority_revision),
            availability=_availability_from_subject(locked.subject, card=card),
        )
    return MappingProxyType(dict(sorted(result.items())))


def summarize_study_authority_queue(
    *,
    cards: Sequence[Card | StudyQueueCardRef],
    reads_by_card_id: Mapping[str, StudyAuthorityCardRead | StudyAuthorityAvailabilitySnapshot],
    learner_user_id: int,
    now_utc: datetime,
    timezone_name: str,
    count_by_note: bool | None = None,
) -> StudyAuthorityQueueSummary:
    """Count and order a fenced Card vector from canonical availability values.

    ``count_by_note`` (default: ``STUDY_NOTE_COUNT_ENABLED``) makes the new,
    learn and due counts count each Note once (Phase 6, D6-04); the queue
    order itself is unchanged.
    """

    if count_by_note is None:
        from flask import current_app, has_app_context

        count_by_note = has_app_context() and bool(
            current_app.config.get("STUDY_NOTE_COUNT_ENABLED", False)
        )
    card_by_id = {str(card.id): card for card in cards}
    counted_notes: set[str] = set()
    if set(card_by_id) != set(reads_by_card_id):
        raise ValueError("Authority queue summary requires one read per Card.")
    runtime = resolve_scheduler_runtime_settings(user_id=learner_user_id)
    boundary_hour = int(runtime.day_boundary_hour_local)
    learn_ahead_seconds = int(runtime.learn_ahead_seconds)

    due_relearn: list[str] = []
    due_learn: list[str] = []
    due_review: list[str] = []
    due_new: list[str] = []
    ahead_relearn: list[str] = []
    ahead_learn: list[str] = []
    pending_count = 0
    next_due_at: datetime | None = None
    new_count = 0
    learn_count = 0
    due_count = 0

    for card_id in sorted(card_by_id):
        availability = reads_by_card_id[card_id].availability
        bucket = study_repository.counter_bucket_for_progress_values(
            queue=availability.normalized_queue,
            due_at=availability.due_at,
            due_day=availability.due_day,
            is_suspended=availability.is_suspended,
            is_buried=availability.is_buried,
            buried_until_day=availability.buried_until_day,
            now=now_utc,
            timezone_name=timezone_name,
            day_boundary_hour_local=boundary_hour,
        )
        note_key = str(card_by_id[card_id].note_id)
        first_of_note = note_key not in counted_notes
        counted_notes.add(note_key)
        if count_by_note and not first_of_note:
            pass
        elif bucket == study_repository.NEW_QUEUE:
            new_count += 1
        elif bucket == study_repository.LEARNING_QUEUE:
            learn_count += 1
        elif bucket == study_repository.REVIEW_QUEUE:
            due_count += 1

        due_bucket = study_repository.study_bucket_for_progress_values(
            queue=availability.normalized_queue,
            due_at=availability.due_at,
            due_day=availability.due_day,
            is_suspended=availability.is_suspended,
            is_buried=availability.is_buried,
            buried_until_day=availability.buried_until_day,
            now=now_utc,
            timezone_name=timezone_name,
            day_boundary_hour_local=boundary_hour,
        )
        queue = study_repository.normalize_progress_queue(
            availability.normalized_queue
        )
        if due_bucket == study_repository.NEW_QUEUE:
            due_new.append(card_id)
            continue
        if due_bucket == study_repository.REVIEW_QUEUE:
            due_review.append(card_id)
            continue
        if due_bucket == study_repository.LEARNING_QUEUE:
            if queue == study_repository.RELEARNING_QUEUE:
                due_relearn.append(card_id)
            else:
                due_learn.append(card_id)
            continue
        if due_bucket == study_repository.LEARNING_LATER_BUCKET:
            within_learn_ahead = (
                availability.due_day is None
                and availability.due_at is not None
                and study_repository._is_learning_due_within_ahead_limit(
                    due_at=availability.due_at,
                    due_day=None,
                    now=now_utc,
                    learn_ahead_seconds=learn_ahead_seconds,
                )
            )
            if within_learn_ahead:
                if queue == study_repository.RELEARNING_QUEUE:
                    ahead_relearn.append(card_id)
                else:
                    ahead_learn.append(card_id)
            else:
                pending_count += 1
                effective_due_at = (
                    study_repository.effective_due_at_for_progress_values(
                        queue=queue,
                        due_at=availability.due_at,
                        due_day=availability.due_day,
                        now=now_utc,
                        timezone_name=timezone_name,
                        day_boundary_hour_local=boundary_hour,
                    )
                )
                if effective_due_at is not None and (
                    next_due_at is None or effective_due_at < next_due_at
                ):
                    next_due_at = effective_due_at

    def learning_key(card_id: str):
        availability = reads_by_card_id[card_id].availability
        return (
            availability.due_at or datetime.max,
            availability.card_created_at,
            availability.card_order_key,
        )

    def review_key(card_id: str):
        availability = reads_by_card_id[card_id].availability
        return study_repository.review_selection_order_key(
            due_day=availability.due_day,
            due_at=availability.due_at,
            card_created_at=availability.card_created_at,
            card_order_key=availability.card_order_key,
        )

    due_relearn.sort(key=learning_key)
    due_learn.sort(key=learning_key)
    due_review.sort(key=review_key)
    due_new.sort(
        key=lambda card_id: (
            reads_by_card_id[card_id].availability.card_created_at,
            reads_by_card_id[card_id].availability.card_order_key,
        )
    )
    ahead_relearn.sort(key=learning_key)
    ahead_learn.sort(key=learning_key)
    due_card_ids = tuple(due_relearn + due_learn + due_review + due_new)
    learn_ahead_card_ids = tuple(ahead_relearn + ahead_learn)
    selected_card_id = (
        due_card_ids[0]
        if due_card_ids
        else (
            learn_ahead_card_ids[0] if learn_ahead_card_ids else None
        )
    )
    return StudyAuthorityQueueSummary(
        new_count=new_count,
        learn_count=learn_count,
        due_count=due_count,
        due_card_ids=due_card_ids,
        learn_ahead_card_ids=learn_ahead_card_ids,
        selected_card_id=selected_card_id,
        pending_learning_count=pending_count,
        next_due_at=next_due_at,
    )
