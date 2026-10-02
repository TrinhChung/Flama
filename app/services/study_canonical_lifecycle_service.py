"""NOTE lifecycle steps under CANONICAL_V1, without ``card_progress`` (P9-05c).

Reset, delete and Template add/remove change a Note's topology. Under the
projection profile they re-derive evidence from CardProgress rows; under
``CANONICAL_V1`` the same outcome is built from state, contributors and
availability (ADR P9-03 §2.5, §2.9). Callers hold the learner fence and the
subject/contributor/availability locks and own the transaction.
"""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityFenceError,
)
from app.services.study_canonical_materialization_service import pristine_state
from app.services.study_note_card_projection import NoteCardBurial, project_note_card
from app.services.study_progress_contract import MAPPER_VERSION
from app.services.study_progress_shadow_codec import (
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import encode_identity
from models.card import Card
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_lineage_ref import StudyProgressLineageRef
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject

_AVAILABILITY_FIELDS = (
    "projection_version",
    "normalized_queue",
    "due_at",
    "due_day",
    "is_suspended",
    "is_buried",
    "buried_until_day",
    "card_created_at",
    "card_order_key",
    "state_schema_version",
    "semantic_state_hash",
)


def _stored(value):
    if isinstance(value, (bytearray, memoryview)):
        return bytes(value)
    return value


def burial_of(availability: StudyProgressAvailability) -> NoteCardBurial:
    return NoteCardBurial(
        is_buried=bool(availability.is_buried),
        buried_until_day=(
            int(availability.buried_until_day)
            if availability.buried_until_day is not None
            else None
        ),
    )


def verify_canonical_note(
    *,
    locked: LockedStudyAuthoritySubject,
    siblings: LockedStudyAuthoritySiblings,
    compatibility: LockedStudyAuthorityCompatibility,
) -> None:
    """Every live Card's availability is what the current state projects to."""

    if locked.state is None:
        raise StudyAuthorityFenceError(
            "AUTHORITY_STATE_REQUIRED", "NOTE lifecycle requires the current canonical state."
        )
    semantic = bytes(locked.state.semantic_state_hash)
    for card in siblings.cards:
        card_id = str(card.id)
        contributor = compatibility.contributor_by_card_id[card_id]
        availability = compatibility.availability_by_contributor_id[int(contributor.id)]
        try:
            projected = project_note_card(
                locked.state.state_payload,
                burial=burial_of(availability),
                card_id=card_id,
                card_created_at=card.created_at,
            )
        except StudyProgressCodecError as exc:
            raise StudyAuthorityFenceError("LOSSY_LEGACY_PROJECTION", str(exc)) from exc
        if projected.semantic_state_hash != semantic or any(
            _stored(getattr(availability, field)) != getattr(projected.availability, field)
            for field in _AVAILABILITY_FIELDS
        ):
            raise StudyAuthorityFenceError(
                "STALE_AUTHORITY_AVAILABILITY",
                f"Card {card_id} availability differs from the canonical Note state.",
            )


def is_pristine_note(
    *,
    locked: LockedStudyAuthoritySubject,
    compatibility: LockedStudyAuthorityCompatibility,
    starting_ease: float,
) -> bool:
    """Never answered since (re)materialization: pristine state, no event pointer."""

    return bool(
        locked.state is not None
        and dict(locked.state.state_payload) == dict(pristine_state(starting_ease).state.payload)
        and all(
            str(contributor.pointer_status) == "ABSENT"
            for contributor in compatibility.contributor_by_card_id.values()
        )
    )


def topology_hash(contributor_by_card_id: Mapping[str, StudyProgressContributor]) -> bytes | None:
    if not contributor_by_card_id:
        return None
    return canonical_document(
        {
            "contributors": [
                {"card_id": card_id, "contributor_id": str(contributor_by_card_id[card_id].id)}
                for card_id in sorted(contributor_by_card_id, key=lambda value: value.encode("utf-8"))
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def authority_hash(
    contributor_by_card_id: Mapping[str, StudyProgressContributor], semantic_state_hash: bytes | None
) -> bytes | None:
    """Same material as the canonical review writer (ADR P9-03 §2.9)."""

    if not contributor_by_card_id or semantic_state_hash is None:
        return None
    return canonical_document(
        {
            "contributors": [
                {
                    "card_id": card_id,
                    "contributor_id": str(contributor_by_card_id[card_id].id),
                    "evidence": "CANONICAL",
                    "semantic_state_hash": bytes(semantic_state_hash).hex(),
                }
                for card_id in sorted(contributor_by_card_id, key=lambda value: value.encode("utf-8"))
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def _lineage_vector(contributor_by_card_id: Mapping[str, StudyProgressContributor]) -> bytes:
    return canonical_document(
        {
            "contributors": [
                {
                    "card_id": card_id,
                    "contributor_id": str(contributor_by_card_id[card_id].id),
                    "lineage_vector_hash": bytes(contributor_by_card_id[card_id].lineage_vector_hash).hex(),
                }
                for card_id in sorted(contributor_by_card_id, key=lambda value: value.encode("utf-8"))
            ]
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def absent_lineage_hash() -> bytes:
    return canonical_typed_document(
        {"references": [{"ref_kind": "LAST_REVIEW_EVENT", "source_row_key": None, "ref_status": "ABSENT"}]},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def add_canonical_sibling(
    session: Session,
    *,
    subject: StudyProgressSubject,
    state: StudyProgressState,
    card: Card,
    burial: NoteCardBurial,
    generation: int,
    provenance_code: str,
    now_utc: datetime,
) -> tuple[StudyProgressContributor, StudyProgressAvailability]:
    """One ACTIVE CANONICAL contributor and availability for a new live Card."""

    try:
        projected = project_note_card(
            state.state_payload, burial=burial, card_id=str(card.id), card_created_at=card.created_at
        )
    except StudyProgressCodecError as exc:
        raise StudyAuthorityFenceError("AUTHORITY_SIBLING_MATERIALIZATION_INCOMPLETE", str(exc)) from exc
    if projected.semantic_state_hash != bytes(state.semantic_state_hash):
        raise StudyAuthorityFenceError(
            "AUTHORITY_SIBLING_MATERIALIZATION_INCOMPLETE",
            "New sibling did not preserve the canonical Note state.",
        )
    contributor = StudyProgressContributor(
        subject_id=int(subject.id),
        subject_generation=generation,
        evidence_kind="CANONICAL",
        logical_card_key=encode_identity(str(card.id), max_bytes=144, field_name="logical_card_key"),
        live_card_id=str(card.id),
        pointer_status="ABSENT",
        history_completeness_code="HISTORY_NATIVE_COMPLETE",
        current_provenance_code=provenance_code,
        lineage_vector_hash=absent_lineage_hash(),
        contributor_status="ACTIVE",
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(contributor)
    session.flush()
    expected = projected.availability
    availability = StudyProgressAvailability(
        contributor_id=int(contributor.id),
        subject_id=int(subject.id),
        subject_generation=generation,
        projection_version=expected.projection_version,
        normalized_queue=expected.normalized_queue,
        due_at=expected.due_at,
        due_day=expected.due_day,
        is_suspended=expected.is_suspended,
        is_buried=expected.is_buried,
        buried_until_day=expected.buried_until_day,
        card_created_at=expected.card_created_at,
        card_order_key=expected.card_order_key,
        state_schema_version=expected.state_schema_version,
        semantic_state_hash=expected.semantic_state_hash,
        created_at=now_utc,
        updated_at=now_utc,
    )
    session.add(availability)
    return contributor, availability


def rebase_to_next_generation(
    session: Session,
    *,
    locked: LockedStudyAuthoritySubject,
    contributor_by_card_id: Mapping[str, StudyProgressContributor],
    availability_by_contributor_id: Mapping[int, StudyProgressAvailability],
    now_utc: datetime,
) -> tuple[int, dict[str, StudyProgressContributor]]:
    """Retire this generation's live contributors and recreate them on the next.

    A generation is an immutable topology epoch: history facts point at the
    contributor rows of their epoch, so old rows stay (``DETACHED``, without
    availability) and the next generation gets new ``CANONICAL`` rows that
    carry the same pointer, provenance, history code and lineage references,
    exactly as the projection path's forced generation advance does.
    """

    generation = int(locked.subject.subject_generation) + 1
    old_ids = sorted(int(row.id) for row in contributor_by_card_id.values())
    refs_by_contributor: dict[int, list[StudyProgressLineageRef]] = {}
    if old_ids:
        for row in session.execute(
            select(StudyProgressLineageRef)
            .where(StudyProgressLineageRef.contributor_id.in_(old_ids))
            .order_by(StudyProgressLineageRef.id.asc())
            .with_for_update()
        ).scalars():
            refs_by_contributor.setdefault(int(row.contributor_id), []).append(row)
    rebased: dict[str, StudyProgressContributor] = {}
    pending_availability: list[tuple[StudyProgressContributor, StudyProgressAvailability]] = []
    for card_id in sorted(contributor_by_card_id, key=lambda value: value.encode("utf-8")):
        old = contributor_by_card_id[card_id]
        availability = availability_by_contributor_id[int(old.id)]
        new = StudyProgressContributor(
            subject_id=int(locked.subject.id),
            subject_generation=generation,
            evidence_kind="CANONICAL",
            logical_card_key=bytes(old.logical_card_key),
            live_card_id=old.live_card_id,
            pointer_status=old.pointer_status,
            history_completeness_code=old.history_completeness_code,
            current_provenance_code=old.current_provenance_code,
            lineage_vector_hash=bytes(old.lineage_vector_hash),
            contributor_status="ACTIVE",
            created_at=now_utc,
            updated_at=now_utc,
        )
        session.add(new)
        pending_availability.append((new, availability))
        rebased[card_id] = new
        old.live_card_progress_id = None
        old.contributor_status = "DETACHED"
        old.detached_at = now_utc
        old.updated_at = now_utc
    for _new, availability in pending_availability:
        session.delete(availability)
    session.flush()
    for card_id, new in rebased.items():
        old = contributor_by_card_id[card_id]
        for ref in refs_by_contributor.get(int(old.id), ()):
            session.add(StudyProgressLineageRef(
                contributor_id=int(new.id),
                subject_generation=generation,
                ref_kind=ref.ref_kind,
                source_row_key=bytes(ref.source_row_key),
                source_key=ref.source_key,
                external_card_id=ref.external_card_id,
                external_note_id=ref.external_note_id,
                source_snapshot_hash=ref.source_snapshot_hash,
                source_payload_hash=ref.source_payload_hash,
                ref_status=ref.ref_status,
                occurred_at=ref.occurred_at,
                ingested_at=now_utc,
            ))
    for new, availability in pending_availability:
        session.add(StudyProgressAvailability(
            contributor_id=int(new.id),
            subject_id=int(locked.subject.id),
            subject_generation=generation,
            projection_version=availability.projection_version,
            normalized_queue=availability.normalized_queue,
            due_at=availability.due_at,
            due_day=availability.due_day,
            is_suspended=availability.is_suspended,
            is_buried=availability.is_buried,
            buried_until_day=availability.buried_until_day,
            card_created_at=availability.card_created_at,
            card_order_key=bytes(availability.card_order_key),
            state_schema_version=availability.state_schema_version,
            semantic_state_hash=bytes(availability.semantic_state_hash),
            created_at=now_utc,
            updated_at=now_utc,
        ))
    locked.subject.subject_generation = generation
    return generation, rebased


def finish_canonical_topology(
    *,
    locked: LockedStudyAuthoritySubject,
    contributor_by_card_id: Mapping[str, StudyProgressContributor],
    now_utc: datetime,
) -> None:
    """Subject envelope, state and token bookkeeping for the current generation."""

    subject = locked.subject
    state = locked.state
    generation = int(subject.subject_generation)
    mirror_revision = int(subject.mirror_revision) + 1
    if state is not None:
        state.subject_generation = generation
        state.mirror_revision = mirror_revision
        state.updated_at = now_utc
    lineage_hashes = {bytes(row.lineage_vector_hash) for row in contributor_by_card_id.values()}
    subject.mirror_revision = mirror_revision
    subject.contributor_count = len(contributor_by_card_id)
    if len(contributor_by_card_id) == 1:
        subject.status_code = "MIRRORED_SINGLE"
    elif len(lineage_hashes) == 1:
        subject.status_code = "MIRRORED_EQUIVALENT_FANIN"
    else:
        subject.status_code = "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE"
    subject.authority_vector_hash = authority_hash(
        contributor_by_card_id, bytes(state.semantic_state_hash) if state is not None else None
    )
    subject.lineage_vector_hash = _lineage_vector(contributor_by_card_id) if contributor_by_card_id else None
    subject.mapper_version = MAPPER_VERSION
    subject.last_mirrored_at = now_utc
    subject.updated_at = now_utc
    locked.token.subject_generation = generation
    locked.token.updated_at = now_utc


def detach_contributors(
    session: Session,
    *,
    contributors,
    availability_by_contributor_id: Mapping[int, StudyProgressAvailability],
    status: str,
    provenance_code: str,
    clear_live_card: bool,
    now_utc: datetime,
) -> None:
    for contributor in contributors:
        availability = availability_by_contributor_id.get(int(contributor.id))
        if availability is not None:
            session.delete(availability)
        contributor.live_card_progress_id = None
        if clear_live_card:
            contributor.live_card_id = None
        contributor.history_completeness_code = "HISTORY_DETACHED"
        contributor.current_provenance_code = provenance_code
        contributor.contributor_status = status
        contributor.detached_at = now_utc
        contributor.updated_at = now_utc
