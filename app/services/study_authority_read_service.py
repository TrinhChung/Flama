"""Mode-aware Card study-state reads during the Phase 5 reversible window."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from types import MappingProxyType
from typing import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    StudyAuthorityRoute,
    lock_study_authority_route,
)
from app.repositories.study_repository import card_state_from_progress
from app.repositories import study_repository
from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
from app.services.anki_scheduler import CardState, DeckOptions
from app.services.study_artifact_service import (
    note_authority_review_state_version,
    review_state_version,
)
from app.services.study_session_authority_pin_service import (
    lock_study_session_authority_subjects,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    map_card_progress,
)
from models.card import Card
from models.card_progress import CardProgress
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor


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
    progress: CardProgress | None
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


def _availability_from_legacy(
    *,
    card: Card,
    progress: CardProgress | None,
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
        card_order_key=str(card.id).encode("utf-8"),
    )


def _availability_from_canonical(
    row: StudyProgressAvailability,
) -> StudyAuthorityAvailabilityRead:
    return StudyAuthorityAvailabilityRead(
        normalized_queue=str(row.normalized_queue),
        due_at=row.due_at,
        due_day=int(row.due_day) if row.due_day is not None else None,
        is_suspended=bool(row.is_suspended),
        is_buried=bool(row.is_buried),
        buried_until_day=(
            int(row.buried_until_day)
            if row.buried_until_day is not None
            else None
        ),
        card_created_at=row.card_created_at,
        card_order_key=bytes(row.card_order_key),
    )


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
    card_by_id = {str(item.id): item for item in cards}
    if not card_by_id:
        return MappingProxyType({})
    if set(card_by_id) != set(deck_options_by_card_id):
        raise ValueError("Every authority read Card requires frozen deck options.")
    if route.mode_code == "LEGACY":
        progress_by_card_id = {
            str(row.card_id): row
            for row in session.query(CardProgress)
            .filter(
                CardProgress.user_id == learner_user_id,
                CardProgress.card_id.in_(sorted(card_by_id)),
            )
            .all()
        }
        return MappingProxyType(
            {
                card_id: StudyAuthorityCardRead(
                    route=route,
                    state=card_state_from_progress(
                        progress_by_card_id.get(card_id),
                        now_utc,
                        timezone_name=timezone_name,
                        user_id=learner_user_id,
                        options=deck_options_by_card_id[card_id],
                    ),
                    state_version=review_state_version(
                        progress=progress_by_card_id.get(card_id),
                        deck_options=deck_options_by_card_id[card_id],
                        timezone_name=timezone_name,
                    ),
                    progress=progress_by_card_id.get(card_id),
                    authority_revision=None,
                    availability=_availability_from_legacy(
                        card=card_by_id[card_id],
                        progress=progress_by_card_id.get(card_id),
                        now_utc=now_utc,
                    ),
                )
                for card_id in sorted(card_by_id)
            }
        )

    logical_note_keys = sorted({str(card.note_id) for card in card_by_id.values()})
    subjects = lock_study_session_authority_subjects(
        session,
        route=route,
        logical_note_keys=logical_note_keys,
        now_utc=now_utc,
    )
    progress_by_card_id = {
        str(row.card_id): row
        for row in session.query(CardProgress)
        .filter(
            CardProgress.user_id == learner_user_id,
            CardProgress.card_id.in_(sorted(card_by_id)),
        )
        .all()
    }
    if set(progress_by_card_id) != set(card_by_id):
        raise StudyAuthorityReadError(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "NOTE read has no complete legacy compatibility projection.",
        )
    subject_by_id = {
        int(locked.subject.id): locked
        for locked in subjects.locked_by_logical_note_key.values()
    }
    contributors = tuple(
        session.execute(
            select(StudyProgressContributor)
            .where(
                StudyProgressContributor.subject_id.in_(sorted(subject_by_id)),
                StudyProgressContributor.live_card_id.in_(sorted(card_by_id)),
                StudyProgressContributor.contributor_status == "ACTIVE",
            )
            .order_by(StudyProgressContributor.id.asc())
            .with_for_update()
        ).scalars()
    )
    contributor_by_card_id = {
        str(row.live_card_id): row
        for row in contributors
        if row.live_card_id is not None
    }
    if (
        len(contributors) != len(card_by_id)
        or set(contributor_by_card_id) != set(card_by_id)
    ):
        raise StudyAuthorityReadError(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "NOTE read has no complete canonical contributor vector.",
        )
    contributor_ids = tuple(
        sorted(int(row.id) for row in contributor_by_card_id.values())
    )
    availability_rows = tuple(
        session.execute(
            select(StudyProgressAvailability)
            .where(
                StudyProgressAvailability.contributor_id.in_(contributor_ids)
            )
            .order_by(StudyProgressAvailability.contributor_id.asc())
            .with_for_update()
        ).scalars()
    )
    availability_by_contributor_id = {
        int(row.contributor_id): row for row in availability_rows
    }
    if (
        len(availability_rows) != len(contributor_ids)
        or set(availability_by_contributor_id) != set(contributor_ids)
    ):
        raise StudyAuthorityReadError(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "NOTE read has no complete canonical availability vector.",
        )
    result: dict[str, StudyAuthorityCardRead] = {}
    for card_id in sorted(card_by_id):
        card = card_by_id[card_id]
        logical_note_key = str(card.note_id)
        locked = subjects.locked_by_logical_note_key[logical_note_key]
        progress = progress_by_card_id[card_id]
        contributor = contributor_by_card_id[card_id]
        availability_row = availability_by_contributor_id[int(contributor.id)]
        mapped = map_card_progress(
            progress,
            card_created_at=card.created_at,
            card_order_key=card_id,
        )
        if (
            not isinstance(mapped, MappedCardProgress)
            or mapped.semantic_state_hash
            != bytes(locked.state.semantic_state_hash)
        ):
            raise StudyAuthorityReadError(
                "AUTHORITY_READ_PARITY_DIVERGED",
                f"Card {card_id} compatibility projection differs from NOTE state.",
            )
        projected = mapped.availability
        if (
            int(contributor.subject_id) != int(locked.subject.id)
            or int(contributor.subject_generation)
            != int(locked.subject.subject_generation)
            or int(contributor.live_card_progress_id or 0) != int(progress.id or 0)
            or int(contributor.card_progress_revision) != int(progress.revision)
            or int(availability_row.subject_id) != int(locked.subject.id)
            or int(availability_row.subject_generation)
            != int(locked.subject.subject_generation)
            or availability_row.projection_version != projected.projection_version
            or availability_row.normalized_queue != projected.normalized_queue
            or availability_row.due_at != projected.due_at
            or availability_row.due_day != projected.due_day
            or bool(availability_row.is_suspended) != projected.is_suspended
            or bool(availability_row.is_buried) != projected.is_buried
            or availability_row.buried_until_day != projected.buried_until_day
            or availability_row.card_created_at != projected.card_created_at
            or bytes(availability_row.card_order_key) != projected.card_order_key
            or availability_row.state_schema_version
            != projected.state_schema_version
            or bytes(availability_row.semantic_state_hash)
            != projected.semantic_state_hash
        ):
            raise StudyAuthorityReadError(
                "AUTHORITY_READ_PARITY_DIVERGED",
                f"Card {card_id} canonical availability evidence is stale.",
            )
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
            availability=_availability_from_canonical(availability_row),
        )
    return MappingProxyType(result)


def summarize_study_authority_queue(
    *,
    cards: Sequence[Card],
    reads_by_card_id: Mapping[str, StudyAuthorityCardRead],
    learner_user_id: int,
    now_utc: datetime,
    timezone_name: str,
) -> StudyAuthorityQueueSummary:
    """Count and order a fenced Card vector from canonical availability values."""

    card_by_id = {str(card.id): card for card in cards}
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
        if bucket == study_repository.NEW_QUEUE:
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
        return (
            study_repository._resolve_review_due_day(
                due_at=availability.due_at,
                due_day=availability.due_day,
                now=now_utc,
                timezone_name=timezone_name,
                day_boundary_hour_local=boundary_hour,
            ),
            availability.due_at or datetime.max,
            availability.card_created_at,
            availability.card_order_key,
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
