"""Transactional reset/delete lifecycle projection for Phase 4 shadow progress.

This module discovers affected learner/Note identities without taking locks,
then delegates the global subject-before-CardProgress lock order to the shared
mirror coordinator.  It never commits or rolls back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
from typing import Iterable, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.study_progress_contract import (
    LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
    MAPPER_VERSION,
)
from app.services.study_progress_shadow_codec import (
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import MappingFailure, map_card_progress
from app.services import study_progress_shadow_mirror_service as mirror
from models.card import Card
from models.card_progress import CardProgress
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


def prepare_lifecycle_mirror(
    session: Session,
    *,
    removed_card_ids: Iterable[str],
    deleted_note_ids: Iterable[str] = (),
    learner_user_ids: Iterable[int] | None = None,
    now_utc: datetime | None = None,
) -> LifecycleMirrorPlan | None:
    """Lock every affected subject, then every sibling progress contributor."""

    if not mirror.shadow_writes_enabled():
        return None
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

    if not mirror.shadow_writes_enabled():
        return None
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
