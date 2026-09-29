"""Transactional reset/delete lifecycle projection for Phase 4 shadow progress.

This module discovers affected learner/Note identities without taking locks,
then delegates the global subject-before-CardProgress lock order to the shared
mirror coordinator.  It never commits or rolls back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Iterable, Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityFenceError,
    StudyAuthorityRoute,
    lock_study_authority_compatibility,
    lock_study_authority_siblings,
    lock_study_authority_subject,
)
from app.services.study_progress_contract import (
    LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
    MAPPER_VERSION,
)
from app.services.study_progress_shadow_codec import (
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    MappingFailure,
    map_card_progress,
)
from app.services import study_progress_shadow_mirror_service as mirror
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject


_TRANSITION_PROVENANCE = {
    "TOMBSTONED_RESET": "PROGRESS_RESET",
    "TOMBSTONED_SUBJECT_DELETED": "CONTENT_DELETE",
    "DETACHED_CONTRIBUTOR_DELETED": "CONTENT_DELETE",
    "REKEYED_CLONE_CUTOVER": "CLONE_CUTOVER",
}


@dataclass(frozen=True)
class _OldVectors:
    topology_hash: bytes | None
    authority_hash: bytes | None
    lineage_hash: bytes | None
    contributor_count: int


@dataclass
class LifecycleMirrorPlan:
    session: Session
    prepared_plans: tuple[mirror.NativeMirrorPlan, ...]
    removed_card_ids: frozenset[str]
    deleted_note_ids: frozenset[str]
    learner_user_ids: frozenset[int] | None
    old_vectors_by_subject_id: dict[int, _OldVectors]
    finalized: bool = False


@dataclass(frozen=True)
class LifecycleMirrorResult:
    subject_count: int
    lifecycle_event_count: int
    statuses: tuple[str, ...]


@dataclass
class NoteAuthorityResetPlan:
    """Fully locked NOTE-authority reset staged in the caller transaction."""

    session: Session
    route: StudyAuthorityRoute
    removed_card_ids: frozenset[str]
    locked_by_note_id: dict[str, LockedStudyAuthoritySubject]
    siblings_by_note_id: dict[str, LockedStudyAuthoritySiblings]
    compatibility_by_note_id: dict[str, LockedStudyAuthorityCompatibility]
    mirror_plans_by_note_id: dict[str, mirror.NativeMirrorPlan]
    starting_ease_by_note_id: dict[str, float]
    old_vectors_by_subject_id: dict[int, _OldVectors]
    finalized: bool = False


@dataclass
class NoteAuthoritySiblingExpansionPlan:
    """Locked NOTE subjects awaiting one newly generated Card sibling each."""

    session: Session
    route: StudyAuthorityRoute
    locked_by_note_id: dict[str, LockedStudyAuthoritySubject]
    siblings_by_note_id: dict[str, LockedStudyAuthoritySiblings]
    compatibility_by_note_id: dict[str, LockedStudyAuthorityCompatibility]
    prepared_at: datetime
    finalized: bool = False


@dataclass
class NoteAuthoritySiblingRemovalPlan:
    """Locked NOTE topology and legacy lifecycle plan for Card removal."""

    session: Session
    route: StudyAuthorityRoute
    locked_by_note_id: dict[str, LockedStudyAuthoritySubject]
    lifecycle_plan: LifecycleMirrorPlan
    expected_hash_by_note_id: dict[str, bytes]
    finalized: bool = False


@dataclass(frozen=True)
class CloneProgressRekey:
    old_note_id: str
    new_note_id: str
    card_id_map: dict[str, str]


@dataclass
class RekeyMirrorPlan:
    session: Session
    learner_user_id: int
    rekeys: tuple[CloneProgressRekey, ...]
    prepared_plans: tuple[mirror.NativeMirrorPlan, ...]
    old_vectors_by_subject_id: dict[int, _OldVectors]
    finalized: bool = False


def _utc_naive(value: datetime | None = None) -> datetime:
    moment = value or datetime.now(timezone.utc)
    if moment.tzinfo is not None:
        return moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment


def _actual_authority_hash(
    progress_rows: Sequence[CardProgress], cards_by_id: dict[str, Card]
) -> bytes | None:
    if not progress_rows:
        return None
    contributors = []
    for progress in sorted(
        progress_rows, key=lambda row: (str(row.card_id).encode("utf-8"), int(row.id))
    ):
        card = cards_by_id.get(str(progress.card_id))
        if card is None:
            raise mirror.StudyProgressMirrorError(
                "Lifecycle authority snapshot cannot resolve its Card."
            )
        mapped = map_card_progress(
            progress,
            card_created_at=card.created_at,
            card_order_key=str(card.id),
        )
        raw = mapped.raw
        if isinstance(mapped, MappingFailure) and raw is None:
            raise mirror.StudyProgressMirrorError(
                "Lifecycle authority snapshot cannot retain bounded raw evidence."
            )
        contributors.append(
            {
                "card_id": str(progress.card_id),
                "progress_id": str(progress.id),
                "raw_progress_hash": raw.digest.hex(),
                "revision": str(progress.revision),
            }
        )
    return canonical_document(
        {"contributors": contributors},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _topology_hash(progress_rows: Sequence[CardProgress]) -> bytes | None:
    if not progress_rows:
        return None
    return canonical_document(
        {
            "contributors": [
                {
                    "card_id": str(row.card_id),
                    "progress_id": str(row.id),
                }
                for row in sorted(
                    progress_rows,
                    key=lambda item: (
                        str(item.card_id).encode("utf-8"),
                        int(item.id),
                    ),
                )
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _verify_note_authority_projection(
    *,
    locked: LockedStudyAuthoritySubject,
    siblings: LockedStudyAuthoritySiblings,
    compatibility: LockedStudyAuthorityCompatibility,
) -> None:
    if locked.state is None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_STATE_REQUIRED",
            "NOTE reset requires the current canonical state.",
        )
    for card in siblings.cards:
        card_id = str(card.id)
        progress = siblings.progress_by_card_id[card_id]
        mapped = map_card_progress(
            progress,
            card_created_at=card.created_at,
            card_order_key=card_id,
        )
        if (
            not isinstance(mapped, MappedCardProgress)
            or mapped.semantic_state_hash != bytes(locked.state.semantic_state_hash)
        ):
            raise StudyAuthorityFenceError(
                "LOSSY_LEGACY_PROJECTION",
                f"Card {card_id} does not encode the canonical NOTE state.",
            )
        contributor = compatibility.contributor_by_card_id[card_id]
        availability = compatibility.availability_by_contributor_id[
            int(contributor.id)
        ]
        projected = mapped.availability
        if (
            availability.projection_version != projected.projection_version
            or availability.normalized_queue != projected.normalized_queue
            or availability.due_at != projected.due_at
            or availability.due_day != projected.due_day
            or bool(availability.is_suspended) != projected.is_suspended
            or bool(availability.is_buried) != projected.is_buried
            or availability.buried_until_day != projected.buried_until_day
            or availability.card_created_at != projected.card_created_at
            or bytes(availability.card_order_key) != projected.card_order_key
            or availability.state_schema_version != projected.state_schema_version
            or bytes(availability.semantic_state_hash)
            != projected.semantic_state_hash
        ):
            raise StudyAuthorityFenceError(
                "STALE_AUTHORITY_AVAILABILITY",
                f"Card {card_id} availability differs from its rollback projection.",
            )


def _is_pristine_reset_progress(
    progress: CardProgress,
    *,
    starting_ease: float,
) -> bool:
    return bool(
        str(progress.queue) == "new"
        and int(progress.step_index or 0) == 0
        and progress.due_at is None
        and progress.due_day is None
        and int(progress.interval_days or 0) == 0
        and float(progress.interval_days_raw or 0.0) == 0.0
        and not bool(progress.is_suspended)
        and not bool(progress.is_buried)
        and progress.buried_until_day is None
        and str(progress.review_kind or "review") == "review"
        and str(progress.scheduler_mode or "legacy") == "legacy"
        and float(progress.ease_factor) == float(starting_ease)
        and progress.memory_stability is None
        and progress.memory_difficulty is None
        and progress.suspension_reason is None
        and progress.last_leech_at is None
        and int(progress.last_leech_lapses or 0) == 0
        and progress.last_review_event_id is None
        and int(progress.reps or 0) == 0
        and int(progress.lapses or 0) == 0
        and progress.last_reviewed_at is None
        and int(progress.revision or 0) == 0
    )


def prepare_note_authority_reset(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    removed_card_ids: Iterable[str],
    skip_pristine: bool = True,
    now_utc: datetime | None = None,
    starting_ease_by_note_id: Mapping[str, float] | None = None,
) -> NoteAuthorityResetPlan | None:
    """Lock a NOTE reset without depending on the Phase 4 flag.

    ``starting_ease_by_note_id`` supplies the deck options LEGACY would use
    for a logical-overlay source Note (the learner's mapped local deck).
    """

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT",
            "NOTE reset requires a fenced NOTE authority route.",
        )
    card_ids = frozenset(str(value) for value in removed_card_ids if str(value))
    if not card_ids:
        return None
    prepared_at = _utc_naive(now_utc)
    card_rows = tuple(
        session.execute(
            select(Card)
            .where(Card.id.in_(sorted(card_ids)))
            .order_by(Card.note_id, Card.id)
        ).scalars()
    )
    card_by_id = {str(card.id): card for card in card_rows}
    if set(card_by_id) != set(card_ids):
        raise StudyAuthorityFenceError(
            "AUTHORITY_CARD_MISSING",
            "NOTE reset contains a Card that no longer exists.",
        )
    note_ids = sorted(
        {str(card.note_id) for card in card_rows},
        key=lambda value: value.encode("utf-8"),
    )
    progress_card_ids = {
        str(card_id)
        for card_id, in session.execute(
            select(CardProgress.card_id).where(
                CardProgress.user_id == route.learner_user_id,
                CardProgress.card_id.in_(sorted(card_ids)),
            )
        ).all()
    }
    subjects = tuple(
        session.execute(
            select(StudyProgressSubject)
            .where(
                StudyProgressSubject.learner_user_id == route.learner_user_id,
                StudyProgressSubject.logical_note_key.in_(
                    [note_id.encode("utf-8") for note_id in note_ids]
                ),
            )
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
        ).scalars()
    )
    subject_by_note_id = {
        bytes(subject.logical_note_key).decode("utf-8"): subject for subject in subjects
    }
    progress_note_ids = {
        str(card_by_id[card_id].note_id) for card_id in progress_card_ids
    }
    missing_subjects = progress_note_ids - set(subject_by_note_id)
    if missing_subjects:
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "NOTE reset found compatibility progress without an authority subject.",
        )

    locked_by_note_id: dict[str, LockedStudyAuthoritySubject] = {}
    for note_id in note_ids:
        subject = subject_by_note_id.get(note_id)
        if subject is None:
            continue
        locked_by_note_id[note_id] = lock_study_authority_subject(
            session,
            route=route,
            subject=subject,
            now_utc=prepared_at,
        )

    siblings_by_note_id: dict[str, LockedStudyAuthoritySiblings] = {}
    compatibility_by_note_id: dict[str, LockedStudyAuthorityCompatibility] = {}
    mirror_plans_by_note_id: dict[str, mirror.NativeMirrorPlan] = {}
    starting_ease_by_note_id: dict[str, float] = {}
    old_vectors: dict[int, _OldVectors] = {}
    for note_id in note_ids:
        locked = locked_by_note_id.get(note_id)
        note_progress_ids = {
            card_id
            for card_id in progress_card_ids
            if str(card_by_id[card_id].note_id) == note_id
        }
        if locked is None:
            continue
        if not note_progress_ids:
            active_contributor = session.execute(
                select(StudyProgressContributor.id)
                .where(
                    StudyProgressContributor.subject_id == int(locked.subject.id),
                    StudyProgressContributor.contributor_status == "ACTIVE",
                )
                .limit(1)
                .with_for_update()
            ).scalar_one_or_none()
            if locked.state is not None or active_contributor is not None:
                raise StudyAuthorityFenceError(
                    "INCOMPLETE_AUTHORITY_COMPATIBILITY",
                    "NOTE reset found canonical state without rollback progress.",
                )
            continue
        if locked.state is None:
            raise StudyAuthorityFenceError(
                "AUTHORITY_STATE_REQUIRED",
                "NOTE reset requires the current canonical state.",
            )
        siblings = lock_study_authority_siblings(
            session,
            route=route,
            locked=locked,
        )
        sibling_card_ids = set(siblings.card_ids)
        if not sibling_card_ids.issubset(card_ids):
            raise StudyAuthorityFenceError(
                "PARTIAL_AUTHORITY_SUBJECT_RESET",
                "A NOTE reset must include every Card sibling of the authority Note.",
            )
        compatibility = lock_study_authority_compatibility(
            session,
            route=route,
            locked=locked,
            siblings=siblings,
        )
        _verify_note_authority_projection(
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
        )
        progress_rows = tuple(siblings.progress_by_card_id.values())
        from app.services.scheduler_config_service import resolve_deck_options

        note_deck_id = siblings.cards[0].note.deck_id
        if starting_ease_by_note_id is not None and note_id in starting_ease_by_note_id:
            starting_ease = float(starting_ease_by_note_id[note_id])
        else:
            starting_ease = float(
                resolve_deck_options(
                    user_id=route.learner_user_id,
                    deck_id=note_deck_id,
                ).startingEase
            )
        if skip_pristine and all(
            _is_pristine_reset_progress(row, starting_ease=starting_ease)
            for row in progress_rows
        ):
            continue
        cards = {str(card.id): card for card in siblings.cards}
        old_vectors[int(locked.subject.id)] = _OldVectors(
            topology_hash=_topology_hash(progress_rows),
            authority_hash=_actual_authority_hash(progress_rows, cards),
            lineage_hash=(
                bytes(locked.subject.lineage_vector_hash)
                if locked.subject.lineage_vector_hash is not None
                else None
            ),
            contributor_count=len(progress_rows),
        )
        siblings_by_note_id[note_id] = siblings
        compatibility_by_note_id[note_id] = compatibility
        mirror_plans_by_note_id[note_id] = mirror.compose_locked_lifecycle_plan(
            session,
            learner_user_id=route.learner_user_id,
            note_id=note_id,
            subject=locked.subject,
            cards=siblings.cards,
            progress_rows=progress_rows,
            prepared_at=prepared_at,
        )
        starting_ease_by_note_id[note_id] = starting_ease

    if not siblings_by_note_id:
        return None
    return NoteAuthorityResetPlan(
        session=session,
        route=route,
        removed_card_ids=frozenset(
            card_id
            for siblings in siblings_by_note_id.values()
            for card_id in siblings.card_ids
        ),
        locked_by_note_id=locked_by_note_id,
        siblings_by_note_id=siblings_by_note_id,
        compatibility_by_note_id=compatibility_by_note_id,
        mirror_plans_by_note_id=mirror_plans_by_note_id,
        starting_ease_by_note_id=starting_ease_by_note_id,
        old_vectors_by_subject_id=old_vectors,
    )


def finalize_note_authority_reset(
    plan: NoteAuthorityResetPlan | None,
    *,
    source_path: str,
    operation_key: str,
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """Replace reset rows with a fresh fenced NOTE state and projection."""

    if plan is None:
        return None
    if plan.finalized:
        raise StudyAuthorityFenceError(
            "AUTHORITY_LIFECYCLE_REPLAY",
            "A NOTE reset plan may be finalized only once.",
        )
    if not source_path or len(source_path.encode("ascii", "strict")) > 128:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_SOURCE", "NOTE reset source path is invalid."
        )
    plan.finalized = True
    session = plan.session
    finalized_at = _utc_naive(now_utc)
    remaining = session.execute(
        select(CardProgress.id)
        .where(
            CardProgress.user_id == plan.route.learner_user_id,
            CardProgress.card_id.in_(sorted(plan.removed_card_ids)),
        )
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if remaining is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_RESET_INCOMPLETE",
            "NOTE reset left compatibility progress on a removed Card.",
        )

    # Bulk deletion leaves the locked ORM instances in the identity map. Detach
    # them before replacement rows are flushed (SQLite may reuse integer ids).
    for siblings in plan.siblings_by_note_id.values():
        for progress in siblings.progress_by_card_id.values():
            if progress in session:
                session.expunge(progress)

    for compatibility in plan.compatibility_by_note_id.values():
        for contributor in compatibility.contributor_by_card_id.values():
            availability = compatibility.availability_by_contributor_id[
                int(contributor.id)
            ]
            session.delete(availability)
            contributor.live_card_progress_id = None
            contributor.history_completeness_code = "HISTORY_DETACHED"
            contributor.current_provenance_code = "PROGRESS_RESET"
            contributor.contributor_status = "TOMBSTONED"
            contributor.detached_at = finalized_at
            contributor.updated_at = finalized_at
    session.flush()

    for note_id, siblings in plan.siblings_by_note_id.items():
        starting_ease = plan.starting_ease_by_note_id[note_id]
        for card_id in siblings.card_ids:
            session.add(
                CardProgress(
                    user_id=plan.route.learner_user_id,
                    card_id=card_id,
                    queue="new",
                    step_index=0,
                    due_at=None,
                    due_day=None,
                    interval_days=0,
                    interval_days_raw=0.0,
                    is_suspended=False,
                    is_buried=False,
                    buried_until_day=None,
                    review_kind="review",
                    scheduler_mode="legacy",
                    ease_factor=starting_ease,
                    memory_stability=None,
                    memory_difficulty=None,
                    suspension_reason=None,
                    last_leech_at=None,
                    last_leech_lapses=0,
                    last_review_event_id=None,
                    reps=0,
                    lapses=0,
                    last_reviewed_at=None,
                    revision=0,
                    created_at=finalized_at,
                    updated_at=finalized_at,
                )
            )
    session.flush()

    operation_hash = canonical_document(
        {"source_path": source_path, "operation_key": operation_key},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    statuses: list[str] = []
    for note_id in sorted(
        plan.siblings_by_note_id,
        key=lambda value: value.encode("utf-8"),
    ):
        locked = plan.locked_by_note_id[note_id]
        siblings = plan.siblings_by_note_id[note_id]
        subject = locked.subject
        old_vectors = plan.old_vectors_by_subject_id[int(subject.id)]
        old_generation = int(subject.subject_generation)

        result = mirror.finalize_native_mirror(
            plan.mirror_plans_by_note_id[note_id],
            review_events=(),
            force_generation_advance=True,
            now_utc=finalized_at,
        )
        if result is None or len(result.statuses) != 1:
            raise StudyAuthorityFenceError(
                "AUTHORITY_RESET_INCOMPLETE",
                "NOTE reset did not rebuild one canonical subject.",
            )
        state = session.get(StudyProgressState, int(subject.id))
        if state is None:
            raise StudyAuthorityFenceError(
                "AUTHORITY_RESET_INCOMPLETE",
                "NOTE reset did not rebuild canonical state.",
            )
        locked.token.subject_generation = int(subject.subject_generation)
        locked.token.authority_revision = int(locked.token.authority_revision) + 1
        locked.token.semantic_state_hash = bytes(state.semantic_state_hash)
        locked.token.updated_at = finalized_at

        new_progress_rows = tuple(
            session.execute(
                select(CardProgress)
                .where(
                    CardProgress.user_id == plan.route.learner_user_id,
                    CardProgress.card_id.in_(sorted(siblings.card_ids)),
                )
                .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
                .with_for_update()
            ).scalars()
        )
        cards = {str(card.id): card for card in siblings.cards}
        removed_card_ids = sorted(siblings.card_ids)
        evidence = canonical_typed_document(
            {
                "transition_code": "TOMBSTONED_RESET",
                "source_path": source_path,
                "learner_user_id": plan.route.learner_user_id,
                "logical_note_key": note_id,
                "removed_card_count": len(removed_card_ids),
                "removed_card_vector_hash": hashlib.sha256(
                    "\n".join(removed_card_ids).encode("utf-8")
                ).hexdigest(),
                "deleted_note": False,
                "old_contributor_count": old_vectors.contributor_count,
                "new_contributor_count": len(new_progress_rows),
                "mapper_version": MAPPER_VERSION,
            },
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        )
        session.add(
            StudyProgressLifecycleEvent(
                subject_id=int(subject.id),
                related_subject_id=None,
                old_generation=old_generation,
                new_generation=int(subject.subject_generation),
                transition_code="TOMBSTONED_RESET",
                occurred_at=finalized_at,
                source_path=source_path,
                operation_key_hash=operation_hash,
                old_topology_hash=old_vectors.topology_hash,
                new_topology_hash=_topology_hash(new_progress_rows),
                old_authority_hash=old_vectors.authority_hash,
                new_authority_hash=_actual_authority_hash(new_progress_rows, cards),
                old_lineage_hash=old_vectors.lineage_hash,
                new_lineage_hash=subject.lineage_vector_hash,
                result_code="TOMBSTONED_RESET",
                reason_code=None,
                evidence_schema_version=LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
                evidence_payload=evidence.payload,
                evidence_payload_size=evidence.size,
                evidence_payload_hash=evidence.digest,
                created_at=finalized_at,
            )
        )
        statuses.append(str(subject.status_code))
    session.flush()
    return LifecycleMirrorResult(
        subject_count=len(statuses),
        lifecycle_event_count=len(statuses),
        statuses=tuple(statuses),
    )


def finalize_note_authority_delete(
    plan: NoteAuthorityResetPlan | None,
    *,
    source_path: str,
    operation_key: str,
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult:
    """Tombstone an owned-local NOTE subject after compatibility deletion."""

    if plan is None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_DELETE_INCOMPLETE",
            "NOTE delete has no complete authority subject.",
        )
    if plan.finalized:
        raise StudyAuthorityFenceError(
            "AUTHORITY_LIFECYCLE_REPLAY",
            "A NOTE delete plan may be finalized only once.",
        )
    if not source_path or len(source_path.encode("ascii", "strict")) > 128:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_SOURCE", "NOTE delete source path is invalid."
        )
    plan.finalized = True
    session = plan.session
    finalized_at = _utc_naive(now_utc)
    remaining = session.execute(
        select(CardProgress.id)
        .where(CardProgress.card_id.in_(sorted(plan.removed_card_ids)))
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if remaining is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_DELETE_INCOMPLETE",
            "NOTE delete left compatibility progress on a removed Card.",
        )

    operation_hash = canonical_document(
        {"source_path": source_path, "operation_key": operation_key},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    statuses: list[str] = []
    for note_id in sorted(
        plan.siblings_by_note_id,
        key=lambda value: value.encode("utf-8"),
    ):
        locked = plan.locked_by_note_id[note_id]
        siblings = plan.siblings_by_note_id[note_id]
        compatibility = plan.compatibility_by_note_id[note_id]
        subject = locked.subject
        old_vectors = plan.old_vectors_by_subject_id[int(subject.id)]
        old_generation = int(subject.subject_generation)
        new_generation = old_generation + 1

        for contributor in compatibility.contributor_by_card_id.values():
            availability = compatibility.availability_by_contributor_id[
                int(contributor.id)
            ]
            session.delete(availability)
            contributor.live_card_progress_id = None
            contributor.live_card_id = None
            contributor.history_completeness_code = "HISTORY_DETACHED"
            contributor.current_provenance_code = "CONTENT_DELETE"
            contributor.contributor_status = "TOMBSTONED"
            contributor.detached_at = finalized_at
            contributor.updated_at = finalized_at

        if locked.state is not None:
            session.delete(locked.state)
        locked.token.subject_generation = new_generation
        locked.token.authority_revision = int(locked.token.authority_revision) + 1
        locked.token.semantic_state_hash = None
        locked.token.updated_at = finalized_at
        subject.live_note_id = None
        subject.subject_generation = new_generation
        subject.mirror_revision = int(subject.mirror_revision) + 1
        subject.status_code = "TOMBSTONED_SUBJECT_DELETED"
        subject.contributor_count = 0
        subject.authority_vector_hash = None
        subject.lineage_vector_hash = None
        subject.last_mirrored_at = finalized_at
        subject.updated_at = finalized_at

        removed_card_ids = sorted(siblings.card_ids)
        evidence = canonical_typed_document(
            {
                "transition_code": "TOMBSTONED_SUBJECT_DELETED",
                "source_path": source_path,
                "learner_user_id": plan.route.learner_user_id,
                "logical_note_key": note_id,
                "removed_card_count": len(removed_card_ids),
                "removed_card_vector_hash": hashlib.sha256(
                    "\n".join(removed_card_ids).encode("utf-8")
                ).hexdigest(),
                "deleted_note": True,
                "old_contributor_count": old_vectors.contributor_count,
                "new_contributor_count": 0,
                "mapper_version": MAPPER_VERSION,
            },
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        )
        session.add(
            StudyProgressLifecycleEvent(
                subject_id=int(subject.id),
                related_subject_id=None,
                old_generation=old_generation,
                new_generation=new_generation,
                transition_code="TOMBSTONED_SUBJECT_DELETED",
                occurred_at=finalized_at,
                source_path=source_path,
                operation_key_hash=operation_hash,
                old_topology_hash=old_vectors.topology_hash,
                new_topology_hash=None,
                old_authority_hash=old_vectors.authority_hash,
                new_authority_hash=None,
                old_lineage_hash=old_vectors.lineage_hash,
                new_lineage_hash=None,
                result_code="TOMBSTONED_SUBJECT_DELETED",
                reason_code=None,
                evidence_schema_version=LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
                evidence_payload=evidence.payload,
                evidence_payload_size=evidence.size,
                evidence_payload_hash=evidence.digest,
                created_at=finalized_at,
            )
        )
        statuses.append("TOMBSTONED_SUBJECT_DELETED")
    session.flush()
    return LifecycleMirrorResult(
        subject_count=len(statuses),
        lifecycle_event_count=len(statuses),
        statuses=tuple(statuses),
    )


def materialize_new_note_authority(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note: Note,
    cards: Iterable[Card],
    provenance_code: str = "NATIVE_DIRECT",
    now_utc: datetime | None = None,
) -> mirror.NativeMirrorResult | None:
    """Materialize a new or previously pristine owned-local NOTE subject."""

    if route.mode_code == "LEGACY":
        return None
    if route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT", "New Note authority route is invalid."
        )
    if provenance_code not in {
        "NATIVE_DIRECT",
        "NATIVE_MCP",
        "UNKNOWN_LEGACY",
    }:
        raise StudyAuthorityFenceError(
            "INVALID_AUTHORITY_SOURCE",
            "New Note authority provenance is not supported.",
        )
    if int(note.user_id) != route.learner_user_id or note.id is None:
        raise StudyAuthorityFenceError(
            "WRONG_LEARNER", "New Note is outside the fenced learner scope."
        )
    return _materialize_note_authority(
        session,
        route=route,
        note=note,
        cards=cards,
        provenance_code=provenance_code,
        now_utc=now_utc,
        starting_ease=None,
    )


def materialize_pristine_note_authority(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note: Note,
    cards: Iterable[Card],
    starting_ease: float,
    provenance_code: str = "NATIVE_DIRECT",
    now_utc: datetime | None = None,
) -> mirror.NativeMirrorResult | None:
    """First-state materialization of a pristine Note on its first write.

    The caller authorizes the learner's access context (owned Note or a
    logical-overlay source Note) and supplies the starting ease of the deck
    options that LEGACY would have used for the first review.
    """

    if route.mode_code != "NOTE" or note.id is None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT", "First-state materialization requires NOTE."
        )
    materialized_at = _utc_naive(now_utc)
    from app.repositories.study_progress_shadow_repository import ensure_and_lock_subject

    # Idempotent create-or-lock closes the concurrent first-state key race.
    ensure_and_lock_subject(
        session,
        learner_user_id=route.learner_user_id,
        logical_note_key=str(note.id),
        live_note_id=str(note.id),
        now_utc=materialized_at,
    )
    return _materialize_note_authority(
        session,
        route=route,
        note=note,
        cards=cards,
        provenance_code=provenance_code,
        now_utc=materialized_at,
        starting_ease=float(starting_ease),
    )


def _materialize_note_authority(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note: Note,
    cards: Iterable[Card],
    provenance_code: str,
    now_utc: datetime | None,
    starting_ease: float | None,
) -> mirror.NativeMirrorResult:
    card_rows = tuple(sorted(cards, key=lambda card: str(card.id).encode("utf-8")))
    if not card_rows or any(
        card.id is None or str(card.note_id) != str(note.id) for card in card_rows
    ):
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "New Note authority requires every generated Card.",
        )
    materialized_at = _utc_naive(now_utc)
    logical_note_key = str(note.id).encode("utf-8")
    existing_subject = session.execute(
        select(StudyProgressSubject)
        .where(
            StudyProgressSubject.learner_user_id == route.learner_user_id,
            StudyProgressSubject.logical_note_key == logical_note_key,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if existing_subject is not None:
        if (
            str(existing_subject.live_note_id or "") != str(note.id)
            or str(existing_subject.status_code or "") != "NO_CURRENT_PROGRESS"
            or int(existing_subject.contributor_count) != 0
            or existing_subject.authority_vector_hash is not None
            or existing_subject.lineage_vector_hash is not None
        ):
            raise StudyAuthorityFenceError(
                "AUTHORITY_SUBJECT_EXISTS",
                "Note already has non-pristine authority evidence.",
            )

    if existing_subject is None:
        subject = StudyProgressSubject(
            learner_user_id=route.learner_user_id,
            logical_note_key=logical_note_key,
            live_note_id=str(note.id),
            subject_generation=1,
            mirror_revision=0,
            status_code="NO_CURRENT_PROGRESS",
            contributor_count=0,
            authority_vector_hash=None,
            lineage_vector_hash=None,
            mapper_version=MAPPER_VERSION,
            created_at=materialized_at,
            updated_at=materialized_at,
        )
        session.add(subject)
        session.flush()
    else:
        subject = existing_subject
    locked = lock_study_authority_subject(
        session,
        route=route,
        subject=subject,
        now_utc=materialized_at,
    )
    if locked.state is not None or locked.token.semantic_state_hash is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_STATE_DIVERGED",
            "New Note authority unexpectedly has current state.",
        )
    card_ids = tuple(str(card.id) for card in card_rows)
    existing_progress = session.execute(
        select(CardProgress.id)
        .where(
            CardProgress.user_id == route.learner_user_id,
            CardProgress.card_id.in_(card_ids),
        )
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if existing_progress is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_PROGRESS_EXISTS",
            "New Note already has compatibility progress.",
        )
    existing_contributor = session.execute(
        select(StudyProgressContributor.id)
        .where(StudyProgressContributor.subject_id == int(subject.id))
        .limit(1)
        .with_for_update()
    ).scalar_one_or_none()
    if existing_contributor is not None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_SUBJECT_EXISTS",
            "Pristine Note authority subject has contributor evidence.",
        )

    if starting_ease is None:
        from app.services.scheduler_config_service import resolve_deck_options

        starting_ease = float(
            resolve_deck_options(
                user_id=route.learner_user_id,
                deck_id=note.deck_id,
            ).startingEase
        )
    for card in card_rows:
        session.add(
            CardProgress(
                user_id=route.learner_user_id,
                card_id=str(card.id),
                queue="new",
                step_index=0,
                due_at=None,
                due_day=None,
                interval_days=0,
                interval_days_raw=0.0,
                is_suspended=False,
                is_buried=False,
                buried_until_day=None,
                review_kind="review",
                scheduler_mode="legacy",
                ease_factor=starting_ease,
                memory_stability=None,
                memory_difficulty=None,
                suspension_reason=None,
                last_leech_at=None,
                last_leech_lapses=0,
                last_review_event_id=None,
                reps=0,
                lapses=0,
                last_reviewed_at=None,
                revision=0,
                created_at=materialized_at,
                updated_at=materialized_at,
            )
        )
    session.flush()
    mirror_plan = mirror.compose_locked_lifecycle_plan(
        session,
        learner_user_id=route.learner_user_id,
        note_id=str(note.id),
        subject=subject,
        cards=card_rows,
        progress_rows=(),
        prepared_at=materialized_at,
    )
    result = mirror.finalize_native_mirror(
        mirror_plan,
        review_events=(),
        external_contexts={
            str(card.id): mirror.ExternalProgressMirrorContext(
                provenance_code=provenance_code,
                history_completeness_code="HISTORY_NATIVE_COMPLETE",
            )
            for card in card_rows
        },
        force_generation_advance=False,
        now_utc=materialized_at,
    )
    state = session.get(StudyProgressState, int(subject.id))
    if result is None or state is None or not str(subject.status_code).startswith(
        "MIRRORED_"
    ):
        raise StudyAuthorityFenceError(
            "AUTHORITY_MATERIALIZATION_INCOMPLETE",
            "New Note authority did not build complete canonical state.",
        )
    locked.token.subject_generation = int(subject.subject_generation)
    locked.token.semantic_state_hash = bytes(state.semantic_state_hash)
    locked.token.updated_at = materialized_at
    session.flush()
    return result


def prepare_note_authority_sibling_expansion(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    note_ids: Iterable[str],
    now_utc: datetime | None = None,
) -> NoteAuthoritySiblingExpansionPlan | None:
    """Lock and verify every NOTE subject before adding a Template sibling."""

    if route.mode_code == "LEGACY":
        return None
    if route.mode_code != "NOTE":
        raise StudyAuthorityFenceError(
            "AUTHORITY_MODE_CONFLICT",
            "Sibling expansion requires a fenced NOTE authority route.",
        )
    ordered_note_ids = tuple(
        sorted(
            {str(value) for value in note_ids if str(value)},
            key=lambda value: value.encode("utf-8"),
        )
    )
    if not ordered_note_ids:
        return None
    prepared_at = _utc_naive(now_utc)
    subjects = tuple(
        session.execute(
            select(StudyProgressSubject)
            .where(
                StudyProgressSubject.learner_user_id == route.learner_user_id,
                StudyProgressSubject.logical_note_key.in_(
                    [note_id.encode("utf-8") for note_id in ordered_note_ids]
                ),
            )
            .order_by(StudyProgressSubject.logical_note_key.asc())
            .with_for_update()
        ).scalars()
    )
    subject_by_note_id = {
        bytes(subject.logical_note_key).decode("utf-8"): subject
        for subject in subjects
    }
    if set(subject_by_note_id) != set(ordered_note_ids):
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "Template creation found a learner Note without an authority subject.",
        )

    locked_by_note_id: dict[str, LockedStudyAuthoritySubject] = {}
    for note_id in ordered_note_ids:
        subject = subject_by_note_id[note_id]
        if (
            str(subject.live_note_id or "") != note_id
            or not str(subject.status_code or "").startswith("MIRRORED_")
        ):
            raise StudyAuthorityFenceError(
                "AUTHORITY_SUBJECT_NOT_READY",
                "Template creation requires a live mirrored authority subject.",
            )
        locked = lock_study_authority_subject(
            session,
            route=route,
            subject=subject,
            now_utc=prepared_at,
        )
        if locked.state is None:
            raise StudyAuthorityFenceError(
                "AUTHORITY_STATE_REQUIRED",
                "Template creation requires the current canonical Note state.",
            )
        locked_by_note_id[note_id] = locked

    siblings_by_note_id: dict[str, LockedStudyAuthoritySiblings] = {}
    compatibility_by_note_id: dict[str, LockedStudyAuthorityCompatibility] = {}
    for note_id in ordered_note_ids:
        locked = locked_by_note_id[note_id]
        siblings = lock_study_authority_siblings(
            session,
            route=route,
            locked=locked,
        )
        compatibility = lock_study_authority_compatibility(
            session,
            route=route,
            locked=locked,
            siblings=siblings,
        )
        _verify_note_authority_projection(
            locked=locked,
            siblings=siblings,
            compatibility=compatibility,
        )
        siblings_by_note_id[note_id] = siblings
        compatibility_by_note_id[note_id] = compatibility

    from models.study_session import StudySession
    from models.study_session_card import StudySessionCard

    affected_card_ids = tuple(
        card_id
        for note_id in ordered_note_ids
        for card_id in siblings_by_note_id[note_id].card_ids
    )
    affected_session_ids = select(StudySessionCard.session_id).where(
        StudySessionCard.card_id.in_(affected_card_ids)
    )
    open_sessions = tuple(
        session.execute(
            select(StudySession)
            .where(
                StudySession.user_id == route.learner_user_id,
                StudySession.status == "open",
                StudySession.id.in_(affected_session_ids),
            )
            .order_by(StudySession.id.asc())
            .with_for_update()
        ).scalars()
    )
    for study_session in open_sessions:
        study_session.status = "cancelled"

    return NoteAuthoritySiblingExpansionPlan(
        session=session,
        route=route,
        locked_by_note_id=locked_by_note_id,
        siblings_by_note_id=siblings_by_note_id,
        compatibility_by_note_id=compatibility_by_note_id,
        prepared_at=prepared_at,
    )


def _copy_progress_for_new_sibling(
    source: CardProgress,
    *,
    learner_user_id: int,
    card_id: str,
    created_at: datetime,
) -> CardProgress:
    """Create a pointer-free compatibility row encoding the same Note state."""

    return CardProgress(
        user_id=learner_user_id,
        card_id=card_id,
        queue=source.queue,
        step_index=source.step_index,
        due_at=source.due_at,
        due_day=source.due_day,
        interval_days=source.interval_days,
        interval_days_raw=source.interval_days_raw,
        is_suspended=source.is_suspended,
        is_buried=source.is_buried,
        buried_until_day=source.buried_until_day,
        review_kind=source.review_kind,
        scheduler_mode=source.scheduler_mode,
        ease_factor=source.ease_factor,
        memory_stability=source.memory_stability,
        memory_difficulty=source.memory_difficulty,
        suspension_reason=source.suspension_reason,
        last_leech_at=source.last_leech_at,
        last_leech_lapses=source.last_leech_lapses,
        last_review_event_id=None,
        reps=source.reps,
        lapses=source.lapses,
        last_reviewed_at=source.last_reviewed_at,
        revision=0,
        created_at=created_at,
        updated_at=created_at,
    )


def finalize_note_authority_sibling_expansion(
    plan: NoteAuthoritySiblingExpansionPlan | None,
    *,
    new_cards: Iterable[Card],
    now_utc: datetime | None = None,
    provenance_code: str = "NATIVE_DIRECT",
) -> mirror.NativeMirrorResult | None:
    """Attach one exact compatibility sibling per prepared Note and fence pins."""

    card_rows = tuple(new_cards)
    if provenance_code not in {"NATIVE_DIRECT", "NATIVE_MCP"}:
        raise StudyAuthorityFenceError("INVALID_AUTHORITY_SOURCE", "Sibling creation provenance is invalid.")
    if plan is None:
        if card_rows:
            return None
        return None
    if plan.finalized:
        raise StudyAuthorityFenceError(
            "AUTHORITY_LIFECYCLE_REPLAY",
            "A NOTE sibling expansion plan may be finalized only once.",
        )
    plan.finalized = True
    finalized_at = _utc_naive(now_utc or plan.prepared_at)
    new_card_by_note_id: dict[str, Card] = {}
    for card in card_rows:
        note_id = str(card.note_id or "")
        if (
            not note_id
            or card.id is None
            or note_id in new_card_by_note_id
            or note_id not in plan.locked_by_note_id
        ):
            raise StudyAuthorityFenceError(
                "INVALID_SIBLING_EXPANSION",
                "Template creation did not generate exactly one Card per fenced Note.",
            )
        new_card_by_note_id[note_id] = card
    if set(new_card_by_note_id) != set(plan.locked_by_note_id):
        raise StudyAuthorityFenceError(
            "INCOMPLETE_SIBLING_EXPANSION",
            "Template creation did not generate a Card for every fenced Note.",
        )

    for note_id in sorted(
        plan.locked_by_note_id,
        key=lambda value: value.encode("utf-8"),
    ):
        siblings = plan.siblings_by_note_id[note_id]
        source = siblings.progress_by_card_id[siblings.card_ids[0]]
        plan.session.add(
            _copy_progress_for_new_sibling(
                source,
                learner_user_id=plan.route.learner_user_id,
                card_id=str(new_card_by_note_id[note_id].id),
                created_at=finalized_at,
            )
        )
    plan.session.flush()

    statuses: list[str] = []
    contributor_count = 0
    for note_id in sorted(
        plan.locked_by_note_id,
        key=lambda value: value.encode("utf-8"),
    ):
        locked = plan.locked_by_note_id[note_id]
        old_siblings = plan.siblings_by_note_id[note_id]
        new_card = new_card_by_note_id[note_id]
        cards = tuple(old_siblings.cards) + (new_card,)
        card_ids = [str(card.id) for card in cards]
        progress_rows = tuple(
            plan.session.execute(
                select(CardProgress)
                .where(
                    CardProgress.user_id == plan.route.learner_user_id,
                    CardProgress.card_id.in_(card_ids),
                )
                .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
                .with_for_update()
            ).scalars()
        )
        if len(progress_rows) != len(cards):
            raise StudyAuthorityFenceError(
                "INCOMPLETE_SIBLING_EXPANSION",
                "Template creation did not materialize complete compatibility rows.",
            )
        mirror_plan = mirror.compose_locked_lifecycle_plan(
            plan.session,
            learner_user_id=plan.route.learner_user_id,
            note_id=note_id,
            subject=locked.subject,
            cards=cards,
            progress_rows=progress_rows,
            prepared_at=plan.prepared_at,
        )
        old_hash = bytes(locked.state.semantic_state_hash)
        result = mirror.finalize_native_mirror(
            mirror_plan,
            review_events=(),
            external_contexts={
                str(new_card.id): mirror.ExternalProgressMirrorContext(
                    provenance_code=provenance_code,
                    history_completeness_code="HISTORY_NATIVE_COMPLETE",
                )
            },
            force_generation_advance=True,
            now_utc=finalized_at,
        )
        state = plan.session.get(StudyProgressState, int(locked.subject.id))
        if (
            result is None
            or len(result.statuses) != 1
            or state is None
            or bytes(state.semantic_state_hash) != old_hash
            or not str(locked.subject.status_code).startswith("MIRRORED_")
        ):
            raise StudyAuthorityFenceError(
                "AUTHORITY_SIBLING_MATERIALIZATION_INCOMPLETE",
                "New sibling did not preserve the canonical Note state.",
            )
        locked.token.subject_generation = int(locked.subject.subject_generation)
        locked.token.semantic_state_hash = old_hash
        locked.token.updated_at = finalized_at
        statuses.extend(result.statuses)
        contributor_count += int(result.contributor_count)

    plan.session.flush()
    return mirror.NativeMirrorResult(
        subject_count=len(statuses),
        contributor_count=contributor_count,
        history_fact_count=0,
        quarantine_count=0,
        statuses=tuple(statuses),
    )


def prepare_note_authority_sibling_removal(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    removed_card_ids: Iterable[str],
    now_utc: datetime | None = None,
) -> NoteAuthoritySiblingRemovalPlan | None:
    """Lock and verify a partial sibling removal without deleting Note state."""

    if route.mode_code == "LEGACY":
        return None
    card_ids = frozenset(str(value) for value in removed_card_ids if str(value))
    if not card_ids:
        return None
    card_rows = tuple(
        session.execute(
            select(Card)
            .where(Card.id.in_(sorted(card_ids)))
            .order_by(Card.note_id.asc(), Card.id.asc())
        ).scalars()
    )
    if {str(card.id) for card in card_rows} != set(card_ids):
        raise StudyAuthorityFenceError(
            "AUTHORITY_CARD_MISSING",
            "Template deletion contains a Card that no longer exists.",
        )
    note_ids = tuple(
        sorted(
            {str(card.note_id) for card in card_rows},
            key=lambda value: value.encode("utf-8"),
        )
    )
    locked = prepare_note_authority_sibling_expansion(
        session,
        route=route,
        note_ids=note_ids,
        now_utc=now_utc,
    )
    if locked is None:
        raise StudyAuthorityFenceError(
            "INCOMPLETE_AUTHORITY_COVERAGE",
            "Template deletion could not lock its authority subjects.",
        )

    prepared_plans: list[mirror.NativeMirrorPlan] = []
    old_vectors: dict[int, _OldVectors] = {}
    expected_hash_by_note_id: dict[str, bytes] = {}
    for note_id in note_ids:
        siblings = locked.siblings_by_note_id[note_id]
        removed_for_note = set(siblings.card_ids) & set(card_ids)
        if not removed_for_note:
            raise StudyAuthorityFenceError(
                "CARD_OUTSIDE_AUTHORITY_SUBJECT",
                "Template deletion Card is outside its authority subject.",
            )
        if len(removed_for_note) >= len(siblings.card_ids):
            raise StudyAuthorityFenceError(
                "EMPTY_AUTHORITY_SIBLINGS",
                "Template deletion must leave at least one Card sibling per Note.",
            )
        progress_rows = tuple(siblings.progress_by_card_id.values())
        cards_by_id = {str(card.id): card for card in siblings.cards}
        subject = locked.locked_by_note_id[note_id].subject
        old_vectors[int(subject.id)] = _OldVectors(
            topology_hash=_topology_hash(progress_rows),
            authority_hash=_actual_authority_hash(progress_rows, cards_by_id),
            lineage_hash=(
                bytes(subject.lineage_vector_hash)
                if subject.lineage_vector_hash is not None
                else None
            ),
            contributor_count=len(progress_rows),
        )
        expected_hash_by_note_id[note_id] = bytes(
            locked.locked_by_note_id[note_id].state.semantic_state_hash
        )
        prepared_plans.append(
            mirror.compose_locked_lifecycle_plan(
                session,
                learner_user_id=route.learner_user_id,
                note_id=note_id,
                subject=subject,
                cards=siblings.cards,
                progress_rows=progress_rows,
                prepared_at=locked.prepared_at,
            )
        )

    lifecycle_plan = LifecycleMirrorPlan(
        session=session,
        prepared_plans=tuple(prepared_plans),
        removed_card_ids=card_ids,
        deleted_note_ids=frozenset(),
        learner_user_ids=frozenset((route.learner_user_id,)),
        old_vectors_by_subject_id=old_vectors,
    )
    return NoteAuthoritySiblingRemovalPlan(
        session=session,
        route=route,
        locked_by_note_id=locked.locked_by_note_id,
        lifecycle_plan=lifecycle_plan,
        expected_hash_by_note_id=expected_hash_by_note_id,
    )


def finalize_note_authority_sibling_removal(
    plan: NoteAuthoritySiblingRemovalPlan | None,
    *,
    source_path: str,
    operation_key: str,
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """Detach deleted sibling evidence and advance the NOTE topology fence."""

    if plan is None:
        return None
    if plan.finalized:
        raise StudyAuthorityFenceError(
            "AUTHORITY_LIFECYCLE_REPLAY",
            "A NOTE sibling removal plan may be finalized only once.",
        )
    plan.finalized = True
    result = finalize_lifecycle_mirror(
        plan.lifecycle_plan,
        transition_code="DETACHED_CONTRIBUTOR_DELETED",
        source_path=source_path,
        operation_key=operation_key,
        now_utc=now_utc,
    )
    if result is None or result.subject_count != len(plan.locked_by_note_id):
        raise StudyAuthorityFenceError(
            "AUTHORITY_SIBLING_REMOVAL_INCOMPLETE",
            "Template deletion did not rebuild every authority subject.",
        )
    finalized_at = _utc_naive(now_utc)
    for note_id, locked in plan.locked_by_note_id.items():
        expected_hash = plan.expected_hash_by_note_id[note_id]
        state = plan.session.get(StudyProgressState, int(locked.subject.id))
        if (
            state is None
            or bytes(state.semantic_state_hash) != expected_hash
            or not str(locked.subject.status_code).startswith("MIRRORED_")
        ):
            raise StudyAuthorityFenceError(
                "AUTHORITY_SIBLING_REMOVAL_INCOMPLETE",
                "Template deletion changed or removed canonical Note state.",
            )
        locked.token.subject_generation = int(locked.subject.subject_generation)
        locked.token.semantic_state_hash = expected_hash
        locked.token.updated_at = finalized_at
    plan.session.flush()
    return result


def prepare_lifecycle_mirror(
    session: Session,
    *,
    removed_card_ids: Iterable[str],
    deleted_note_ids: Iterable[str] = (),
    learner_user_ids: Iterable[int] | None = None,
    now_utc: datetime | None = None,
) -> LifecycleMirrorPlan | None:
    """Lock every affected subject, then every sibling progress contributor."""

    card_ids = frozenset(str(value) for value in removed_card_ids if str(value))
    note_ids = frozenset(str(value) for value in deleted_note_ids if str(value))
    if not card_ids and not note_ids:
        return None
    learner_filter = (
        frozenset(int(value) for value in learner_user_ids)
        if learner_user_ids is not None
        else None
    )

    card_rows = tuple(
        session.execute(
            select(Card.id, Card.note_id).where(Card.id.in_(sorted(card_ids)))
        ).all()
    ) if card_ids else ()
    card_to_note = {str(row.id): str(row.note_id) for row in card_rows}
    affected_note_ids = set(note_ids) | set(card_to_note.values())
    if not affected_note_ids:
        return None

    subject_keys: set[tuple[int, str]] = set()
    if card_ids:
        progress_statement = select(CardProgress.user_id, Card.note_id).join(
            Card, CardProgress.card_id == Card.id
        ).where(CardProgress.card_id.in_(sorted(card_ids)))
        if learner_filter is not None:
            progress_statement = progress_statement.where(
                CardProgress.user_id.in_(sorted(learner_filter))
            )
        for user_id, note_id in session.execute(progress_statement).all():
            subject_keys.add((int(user_id), str(note_id)))

        shadow_statement = (
            select(
                StudyProgressSubject.learner_user_id,
                StudyProgressSubject.logical_note_key,
            )
            .join(
                StudyProgressContributor,
                StudyProgressContributor.subject_id == StudyProgressSubject.id,
            )
            .where(
                StudyProgressContributor.live_card_id.in_(sorted(card_ids)),
                StudyProgressContributor.contributor_status == "ACTIVE",
            )
        )
        if learner_filter is not None:
            shadow_statement = shadow_statement.where(
                StudyProgressSubject.learner_user_id.in_(sorted(learner_filter))
            )
        for user_id, logical_note_key in session.execute(shadow_statement).all():
            subject_keys.add((int(user_id), bytes(logical_note_key).decode("utf-8")))

    if note_ids:
        subject_statement = select(
            StudyProgressSubject.learner_user_id,
            StudyProgressSubject.logical_note_key,
        ).where(StudyProgressSubject.logical_note_key.in_([v.encode("utf-8") for v in sorted(note_ids)]))
        if learner_filter is not None:
            subject_statement = subject_statement.where(
                StudyProgressSubject.learner_user_id.in_(sorted(learner_filter))
            )
        for user_id, logical_note_key in session.execute(subject_statement).all():
            subject_keys.add((int(user_id), bytes(logical_note_key).decode("utf-8")))

    prepared = mirror.prepare_mirror_scopes(
        session,
        subject_keys=subject_keys,
        now_utc=now_utc,
    )
    if not prepared:
        return None

    old_vectors: dict[int, _OldVectors] = {}
    for item in prepared:
        prepared_subject = next(iter(item.subjects_by_note_id.values()))
        progress_rows = tuple(item.locked_progress_by_card_id.values())
        old_vectors[int(prepared_subject.subject.id)] = _OldVectors(
            topology_hash=_topology_hash(progress_rows),
            authority_hash=_actual_authority_hash(progress_rows, item.cards_by_id),
            lineage_hash=(
                bytes(prepared_subject.subject.lineage_vector_hash)
                if prepared_subject.subject.lineage_vector_hash is not None
                else None
            ),
            contributor_count=len(progress_rows),
        )
    return LifecycleMirrorPlan(
        session=session,
        prepared_plans=prepared,
        removed_card_ids=card_ids,
        deleted_note_ids=note_ids,
        learner_user_ids=learner_filter,
        old_vectors_by_subject_id=old_vectors,
    )


def prepare_clone_rekey_mirror(
    session: Session,
    *,
    learner_user_id: int,
    rekeys: Iterable[CloneProgressRekey],
    now_utc: datetime | None = None,
) -> RekeyMirrorPlan | None:
    """Prepare old/new clone subjects before P1-02 contributor merge locks."""

    normalized = tuple(
        CloneProgressRekey(
            old_note_id=str(item.old_note_id),
            new_note_id=str(item.new_note_id),
            card_id_map={str(old): str(new) for old, new in item.card_id_map.items()},
        )
        for item in rekeys
        if item.old_note_id and item.new_note_id and item.card_id_map
    )
    if not normalized:
        return None
    old_note_ids = [item.old_note_id for item in normalized]
    new_note_ids = [item.new_note_id for item in normalized]
    if (
        len(set(old_note_ids)) != len(old_note_ids)
        or len(set(new_note_ids)) != len(new_note_ids)
        or set(old_note_ids) & set(new_note_ids)
    ):
        raise mirror.StudyProgressMirrorError(
            "Clone rekey contains an ambiguous old/new Note mapping."
        )
    candidate_card_ids = sorted(
        {
            card_id
            for item in normalized
            for card_id in (*item.card_id_map.keys(), *item.card_id_map.values())
        }
    )
    authority_note_ids = {
        str(note_id)
        for note_id, in session.execute(
            select(Card.note_id)
            .join(CardProgress, CardProgress.card_id == Card.id)
            .where(
                CardProgress.user_id == int(learner_user_id),
                CardProgress.card_id.in_(candidate_card_ids),
            )
        ).all()
    }
    candidate_note_ids = sorted(
        {value for item in normalized for value in (item.old_note_id, item.new_note_id)}
    )
    materialized_note_ids = {
        bytes(value).decode("utf-8")
        for value, in session.execute(
            select(StudyProgressSubject.logical_note_key).where(
                StudyProgressSubject.learner_user_id == int(learner_user_id),
                StudyProgressSubject.logical_note_key.in_(
                    [value.encode("utf-8") for value in candidate_note_ids]
                ),
                StudyProgressSubject.mirror_revision > 0,
            )
        ).all()
    }
    impacted = tuple(
        item
        for item in normalized
        if item.old_note_id in authority_note_ids
        or item.new_note_id in authority_note_ids
        or item.old_note_id in materialized_note_ids
        or item.new_note_id in materialized_note_ids
    )
    if not impacted:
        return None
    subject_keys = {
        (int(learner_user_id), note_id)
        for item in impacted
        for note_id in (item.old_note_id, item.new_note_id)
    }
    prepared = mirror.prepare_mirror_scopes(
        session,
        subject_keys=subject_keys,
        now_utc=now_utc,
    )
    if not prepared:
        return None
    old_vectors: dict[int, _OldVectors] = {}
    for item in prepared:
        prepared_subject = next(iter(item.subjects_by_note_id.values()))
        progress_rows = tuple(item.locked_progress_by_card_id.values())
        old_vectors[int(prepared_subject.subject.id)] = _OldVectors(
            topology_hash=_topology_hash(progress_rows),
            authority_hash=_actual_authority_hash(progress_rows, item.cards_by_id),
            lineage_hash=(
                bytes(prepared_subject.subject.lineage_vector_hash)
                if prepared_subject.subject.lineage_vector_hash is not None
                else None
            ),
            contributor_count=len(progress_rows),
        )
    return RekeyMirrorPlan(
        session=session,
        learner_user_id=int(learner_user_id),
        rekeys=impacted,
        prepared_plans=prepared,
        old_vectors_by_subject_id=old_vectors,
    )


def _detach_removed_contributors(
    plan: mirror.NativeMirrorPlan,
    *,
    transition_code: str,
    removed_card_ids: frozenset[str],
    deleted_note_ids: frozenset[str],
    now_utc: datetime,
) -> None:
    session = plan.session
    prepared = next(iter(plan.subjects_by_note_id.values()))
    rows = tuple(
        session.execute(
            select(StudyProgressContributor)
            .where(
                StudyProgressContributor.subject_id == prepared.subject.id,
                StudyProgressContributor.contributor_status == "ACTIVE",
            )
            .order_by(
                StudyProgressContributor.logical_card_key.asc(),
                StudyProgressContributor.id.asc(),
            )
            .with_for_update()
        ).scalars()
    )
    final_progress_ids = {
        int(row.id)
        for row in session.execute(
            select(CardProgress)
            .where(
                CardProgress.user_id == plan.learner_user_id,
                CardProgress.card_id.in_(sorted(plan.cards_by_id)),
            )
            .with_for_update()
        ).scalars()
    }
    note_id = next(iter(plan.subjects_by_note_id))
    clear_live_card = note_id in deleted_note_ids
    for contributor in rows:
        progress_id = contributor.live_card_progress_id
        card_id = str(contributor.live_card_id or "")
        if (
            progress_id is not None
            and int(progress_id) in final_progress_ids
            and card_id not in removed_card_ids
        ):
            continue
        contributor.live_card_progress_id = None
        if clear_live_card or card_id in removed_card_ids:
            contributor.live_card_id = None
        contributor.history_completeness_code = "HISTORY_DETACHED"
        contributor.current_provenance_code = _TRANSITION_PROVENANCE[transition_code]
        contributor.contributor_status = (
            "TOMBSTONED"
            if transition_code
            in {"TOMBSTONED_RESET", "TOMBSTONED_SUBJECT_DELETED"}
            else "DETACHED"
        )
        contributor.detached_at = now_utc
        contributor.updated_at = now_utc
        availability = session.get(StudyProgressAvailability, int(contributor.id))
        if availability is not None:
            session.delete(availability)


def finalize_lifecycle_mirror(
    plan: LifecycleMirrorPlan | None,
    *,
    transition_code: str,
    source_path: str,
    operation_key: str,
    transition_by_note_id: dict[str, str] | None = None,
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """Finalize one reset/delete generation fence without committing."""

    if plan is None:
        return None
    if plan.finalized:
        raise mirror.StudyProgressMirrorError(
            "A lifecycle mirror plan may be finalized only once."
        )
    transition_map = {
        str(note_id): str(code)
        for note_id, code in (transition_by_note_id or {}).items()
    }
    supplied_transitions = {transition_code, *transition_map.values()}
    if any(code not in _TRANSITION_PROVENANCE for code in supplied_transitions):
        raise mirror.StudyProgressMirrorError(
            f"Unsupported lifecycle transition: {transition_code}."
        )
    if not source_path or len(source_path.encode("ascii", "strict")) > 128:
        raise mirror.StudyProgressMirrorError("Lifecycle source path is invalid.")
    plan.finalized = True
    session = plan.session
    finalized_at = _utc_naive(now_utc)
    session.flush()
    if plan.removed_card_ids:
        remaining_statement = select(
            CardProgress.id,
            CardProgress.user_id,
            CardProgress.card_id,
        ).where(CardProgress.card_id.in_(sorted(plan.removed_card_ids)))
        if plan.learner_user_ids is not None:
            remaining_statement = remaining_statement.where(
                CardProgress.user_id.in_(sorted(plan.learner_user_ids))
            )
        remaining_rows = tuple(
            session.execute(remaining_statement.with_for_update()).all()
        )
        if remaining_rows:
            raise mirror.StudyProgressMirrorError(
                "Lifecycle mutation left authoritative progress on a removed Card."
            )
        prepared_subject_ids = {
            int(next(iter(item.subjects_by_note_id.values())).subject.id)
            for item in plan.prepared_plans
        }
        unexpected_subject_statement = (
            select(StudyProgressContributor.id)
            .join(
                StudyProgressSubject,
                StudyProgressSubject.id == StudyProgressContributor.subject_id,
            )
            .where(
                StudyProgressContributor.live_card_id.in_(
                    sorted(plan.removed_card_ids)
                ),
                StudyProgressContributor.contributor_status == "ACTIVE",
            )
        )
        if prepared_subject_ids:
            unexpected_subject_statement = unexpected_subject_statement.where(
                StudyProgressContributor.subject_id.notin_(
                    sorted(prepared_subject_ids)
                )
            )
        if plan.learner_user_ids is not None:
            unexpected_subject_statement = unexpected_subject_statement.where(
                StudyProgressSubject.learner_user_id.in_(
                    sorted(plan.learner_user_ids)
                )
            )
        unexpected_subject = session.execute(
            unexpected_subject_statement.with_for_update()
        ).first()
        if unexpected_subject is not None:
            raise mirror.StudyProgressMirrorError(
                "Lifecycle subject discovery became stale during progress deletion."
            )
    statuses: list[str] = []
    event_count = 0

    for prepared_plan in plan.prepared_plans:
        prepared = next(iter(prepared_plan.subjects_by_note_id.values()))
        subject = prepared.subject
        note_id = next(iter(prepared_plan.subjects_by_note_id))
        subject_transition = transition_map.get(note_id, transition_code)
        old_vectors = plan.old_vectors_by_subject_id[int(subject.id)]
        subject_removed_card_ids = sorted(
            set(prepared_plan.cards_by_id) & plan.removed_card_ids
        )
        _detach_removed_contributors(
            prepared_plan,
            transition_code=subject_transition,
            removed_card_ids=plan.removed_card_ids,
            deleted_note_ids=plan.deleted_note_ids,
            now_utc=finalized_at,
        )
        session.flush()
        mirror.finalize_native_mirror(
            prepared_plan,
            review_events=(),
            force_generation_advance=True,
            now_utc=finalized_at,
        )

        if subject_transition in {"TOMBSTONED_RESET", "TOMBSTONED_SUBJECT_DELETED"}:
            current_count = int(subject.contributor_count)
            if current_count:
                raise mirror.StudyProgressMirrorError(
                    "A tombstone transition retained authoritative contributors."
                )
            state = session.get(StudyProgressState, int(subject.id))
            if state is not None:
                session.delete(state)
            subject.status_code = subject_transition
            subject.authority_vector_hash = None
            subject.lineage_vector_hash = None
            if subject_transition == "TOMBSTONED_SUBJECT_DELETED":
                subject.live_note_id = None

        final_rows = tuple(
            session.execute(
                select(CardProgress)
                .where(
                    CardProgress.user_id == prepared_plan.learner_user_id,
                    CardProgress.card_id.in_(sorted(prepared_plan.cards_by_id)),
                )
                .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
                .with_for_update()
            ).scalars()
        )
        new_topology_hash = _topology_hash(final_rows)
        evidence = canonical_typed_document(
            {
                "transition_code": subject_transition,
                "source_path": source_path,
                "learner_user_id": int(prepared_plan.learner_user_id),
                "logical_note_key": note_id,
                "removed_card_count": len(subject_removed_card_ids),
                "removed_card_vector_hash": (
                    hashlib.sha256(
                        "\n".join(subject_removed_card_ids).encode("utf-8")
                    ).hexdigest()
                    if subject_removed_card_ids
                    else None
                ),
                "deleted_note": note_id in plan.deleted_note_ids,
                "old_contributor_count": old_vectors.contributor_count,
                "new_contributor_count": len(final_rows),
                "mapper_version": MAPPER_VERSION,
            },
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        )
        operation_hash = canonical_document(
            {"source_path": source_path, "operation_key": operation_key},
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        ).digest
        lifecycle = StudyProgressLifecycleEvent(
            subject_id=int(subject.id),
            related_subject_id=None,
            old_generation=int(prepared.expected_generation),
            new_generation=int(subject.subject_generation),
            transition_code=subject_transition,
            occurred_at=finalized_at,
            source_path=source_path,
            operation_key_hash=operation_hash,
            old_topology_hash=old_vectors.topology_hash,
            new_topology_hash=new_topology_hash,
            old_authority_hash=old_vectors.authority_hash,
            new_authority_hash=subject.authority_vector_hash,
            old_lineage_hash=old_vectors.lineage_hash,
            new_lineage_hash=subject.lineage_vector_hash,
            result_code=subject_transition,
            reason_code=(
                str(subject.status_code)
                if str(subject.status_code).startswith("QUARANTINED_")
                else None
            ),
            evidence_schema_version=LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
            evidence_payload=evidence.payload,
            evidence_payload_size=evidence.size,
            evidence_payload_hash=evidence.digest,
            created_at=finalized_at,
        )
        session.add(lifecycle)
        subject.last_mirrored_at = finalized_at
        subject.updated_at = finalized_at
        statuses.append(str(subject.status_code))
        event_count += 1

    session.flush()
    return LifecycleMirrorResult(
        subject_count=len(statuses),
        lifecycle_event_count=event_count,
        statuses=tuple(statuses),
    )


def finalize_clone_rekey_mirror(
    plan: RekeyMirrorPlan | None,
    *,
    source_path: str,
    operation_key: str,
    now_utc: datetime | None = None,
) -> LifecycleMirrorResult | None:
    """Record only the authoritative post-cutover P1-02 merge result."""

    if plan is None:
        return None
    if plan.finalized:
        raise mirror.StudyProgressMirrorError(
            "A clone rekey mirror plan may be finalized only once."
        )
    if not source_path or len(source_path.encode("ascii", "strict")) > 128:
        raise mirror.StudyProgressMirrorError("Clone rekey source path is invalid.")
    plan.finalized = True
    session = plan.session
    finalized_at = _utc_naive(now_utc)
    session.flush()
    plans_by_note = {
        next(iter(item.subjects_by_note_id)): item for item in plan.prepared_plans
    }
    old_note_ids = {item.old_note_id for item in plan.rekeys}
    related_note = {
        item.old_note_id: item.new_note_id for item in plan.rekeys
    }
    related_note.update({item.new_note_id: item.old_note_id for item in plan.rekeys})

    # Release all old live-progress identities before destination contributors
    # are created.  The unique live-progress FK then proves one current owner.
    for old_note_id in sorted(old_note_ids, key=lambda value: value.encode("utf-8")):
        old_plan = plans_by_note[old_note_id]
        subject = next(iter(old_plan.subjects_by_note_id.values())).subject
        contributors = tuple(
            session.execute(
                select(StudyProgressContributor)
                .where(
                    StudyProgressContributor.subject_id == subject.id,
                    StudyProgressContributor.contributor_status == "ACTIVE",
                )
                .order_by(
                    StudyProgressContributor.logical_card_key.asc(),
                    StudyProgressContributor.id.asc(),
                )
                .with_for_update()
            ).scalars()
        )
        for contributor in contributors:
            contributor.live_card_progress_id = None
            contributor.live_card_id = None
            contributor.history_completeness_code = "HISTORY_DETACHED"
            contributor.current_provenance_code = "CLONE_CUTOVER"
            contributor.contributor_status = "REKEYED"
            contributor.detached_at = finalized_at
            contributor.updated_at = finalized_at
            availability = session.get(
                StudyProgressAvailability, int(contributor.id)
            )
            if availability is not None:
                session.delete(availability)
    session.flush()

    statuses: list[str] = []
    event_count = 0
    operation_hash = canonical_document(
        {"source_path": source_path, "operation_key": operation_key},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    mapping_hash = hashlib.sha256(
        "\n".join(
            f"{old}>{new}"
            for item in sorted(plan.rekeys, key=lambda row: row.old_note_id.encode("utf-8"))
            for old, new in sorted(item.card_id_map.items())
        ).encode("utf-8")
    ).hexdigest()

    for prepared_plan in plan.prepared_plans:
        note_id = next(iter(prepared_plan.subjects_by_note_id))
        prepared = next(iter(prepared_plan.subjects_by_note_id.values()))
        subject = prepared.subject
        old_vectors = plan.old_vectors_by_subject_id[int(subject.id)]
        external_contexts: dict[str, mirror.ExternalProgressMirrorContext] = {}
        if note_id not in old_note_ids:
            session.flush()
            final_progress = tuple(
                session.execute(
                    select(CardProgress)
                    .where(
                        CardProgress.user_id == plan.learner_user_id,
                        CardProgress.card_id.in_(sorted(prepared_plan.cards_by_id)),
                    )
                    .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
                    .with_for_update()
                ).scalars()
            )
            external_contexts = {
                str(row.card_id): mirror.ExternalProgressMirrorContext(
                    provenance_code="CLONE_CUTOVER",
                    history_completeness_code="HISTORY_MIXED_PARTIAL",
                )
                for row in final_progress
            }
        mirror.finalize_native_mirror(
            prepared_plan,
            review_events=(),
            external_contexts=external_contexts,
            force_generation_advance=True,
            now_utc=finalized_at,
        )
        if note_id in old_note_ids:
            state = session.get(StudyProgressState, int(subject.id))
            if state is not None:
                session.delete(state)
            subject.status_code = "REKEYED_CLONE_CUTOVER"
            subject.contributor_count = 0
            subject.authority_vector_hash = None
            subject.lineage_vector_hash = None
            subject.live_note_id = None

        final_rows = tuple(
            session.execute(
                select(CardProgress)
                .where(
                    CardProgress.user_id == plan.learner_user_id,
                    CardProgress.card_id.in_(sorted(prepared_plan.cards_by_id)),
                )
                .order_by(CardProgress.card_id.asc(), CardProgress.id.asc())
                .with_for_update()
            ).scalars()
        )
        related_plan = plans_by_note[related_note[note_id]]
        related_subject = next(
            iter(related_plan.subjects_by_note_id.values())
        ).subject
        evidence = canonical_typed_document(
            {
                "transition_code": "REKEYED_CLONE_CUTOVER",
                "source_path": source_path,
                "direction": "old" if note_id in old_note_ids else "destination",
                "logical_note_key": note_id,
                "related_logical_note_key": related_note[note_id],
                "card_mapping_count": sum(
                    len(item.card_id_map)
                    for item in plan.rekeys
                    if note_id in {item.old_note_id, item.new_note_id}
                ),
                "card_mapping_hash": mapping_hash,
                "old_contributor_count": old_vectors.contributor_count,
                "new_contributor_count": len(final_rows),
                "mapper_version": MAPPER_VERSION,
            },
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        )
        session.add(
            StudyProgressLifecycleEvent(
                subject_id=int(subject.id),
                related_subject_id=int(related_subject.id),
                old_generation=int(prepared.expected_generation),
                new_generation=int(subject.subject_generation),
                transition_code="REKEYED_CLONE_CUTOVER",
                occurred_at=finalized_at,
                source_path=source_path,
                operation_key_hash=operation_hash,
                old_topology_hash=old_vectors.topology_hash,
                new_topology_hash=_topology_hash(final_rows),
                old_authority_hash=old_vectors.authority_hash,
                new_authority_hash=subject.authority_vector_hash,
                old_lineage_hash=old_vectors.lineage_hash,
                new_lineage_hash=subject.lineage_vector_hash,
                result_code="REKEYED_CLONE_CUTOVER",
                reason_code=None,
                evidence_schema_version=LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
                evidence_payload=evidence.payload,
                evidence_payload_size=evidence.size,
                evidence_payload_hash=evidence.digest,
                created_at=finalized_at,
            )
        )
        subject.last_mirrored_at = finalized_at
        subject.updated_at = finalized_at
        statuses.append(str(subject.status_code))
        event_count += 1

    session.flush()
    return LifecycleMirrorResult(
        subject_count=len(statuses),
        lifecycle_event_count=event_count,
        statuses=tuple(statuses),
    )
