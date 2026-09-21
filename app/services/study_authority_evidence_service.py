"""Finalize derived compatibility evidence after one NOTE material write.

The caller must already hold the learner, subject/token/state, complete sibling
CardProgress and contributor/availability locks.  This module refreshes the
Phase 4-derived evidence and mirror bookkeeping without touching the independent
NOTE authority revision.  It never commits or rolls back.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime
import hashlib
import json
from typing import Any, Mapping

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
)
from app.services.study_authority_write_service import StudyAuthorityWriteResult
from app.services.study_progress_contract import MAPPER_VERSION
from app.services.study_progress_history_service import (
    StudyProgressHistoryError,
    native_review_event_provenance,
)
from app.services.study_progress_shadow_codec import (
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    MappingFailure,
    build_contributor_evidence,
    encode_identity,
    map_card_progress,
)
from app.validators.review_event import classify_review_event_payload
from models.card_progress import CardProgress
from models.review_event import ReviewEvent
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_lineage_ref import StudyProgressLineageRef


_MYSQL_SIGNED_BIGINT_MAX = (1 << 63) - 1


class StudyAuthorityEvidenceError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class StudyAuthorityEvidenceResult:
    mirror_revision: int
    subject_status: str
    contributor_count: int
    authority_vector_hash: bytes
    lineage_vector_hash: bytes
    contributor_by_card_id: Mapping[str, StudyProgressContributor]


def _fail(code: str, message: str) -> StudyAuthorityEvidenceError:
    return StudyAuthorityEvidenceError(code, message)


def _lineage_material(row: StudyProgressLineageRef) -> dict[str, Any]:
    return {
        "ref_kind": row.ref_kind,
        "source_row_key": bytes(row.source_row_key).hex(),
        "source_key": bytes(row.source_key).hex() if row.source_key is not None else None,
        "external_card_id": (
            bytes(row.external_card_id).hex()
            if row.external_card_id is not None
            else None
        ),
        "external_note_id": (
            bytes(row.external_note_id).hex()
            if row.external_note_id is not None
            else None
        ),
        "source_snapshot_hash": (
            bytes(row.source_snapshot_hash).hex()
            if row.source_snapshot_hash is not None
            else None
        ),
        "source_payload_hash": (
            bytes(row.source_payload_hash).hex()
            if row.source_payload_hash is not None
            else None
        ),
        "ref_status": row.ref_status,
        "occurred_at": row.occurred_at,
    }


def _pointer_evidence(
    progress: CardProgress,
    event_by_id: Mapping[int, ReviewEvent],
) -> tuple[str, dict[str, Any]]:
    event_id = progress.last_review_event_id
    if event_id is None:
        return "ABSENT", {
            "ref_kind": "LAST_REVIEW_EVENT",
            "source_row_key": None,
            "ref_status": "ABSENT",
        }
    event = event_by_id.get(int(event_id))
    status = "VALID"
    if event is None:
        status = "MISSING_EVENT"
    elif int(event.user_id) != int(progress.user_id):
        status = "LEARNER_MISMATCH"
    elif str(event.card_id) != str(progress.card_id):
        status = "CARD_MISMATCH"
    else:
        disposition = classify_review_event_payload(
            event.payload_json,
            scheduler_algorithm=event.scheduler_algorithm,
            algorithm_version=event.algorithm_version,
            scheduler_config_hash=event.scheduler_config_hash,
            study_session_id=event.study_session_id,
            client_event_id=event.client_event_id,
            sequence_no=event.sequence_no,
        )
        if disposition.category == "complete":
            try:
                parsed = json.loads(event.payload_json)
            except (TypeError, ValueError):  # pragma: no cover - classifier covers it
                parsed = {}
            provenance = parsed.get("provenance") if isinstance(parsed, dict) else None
            if isinstance(provenance, dict) and provenance.get("kind") == "external":
                status = "EXTERNAL_POINTED"
        elif disposition.category != "legacy_unknown":
            status = "PAYLOAD_MISMATCH"
    return status, {
        "ref_kind": "LAST_REVIEW_EVENT",
        "source_row_key": str(event_id),
        "ref_status": status,
        "occurred_at": event.reviewed_at if event is not None else None,
        "source_payload_hash": (
            hashlib.sha256(str(event.payload_json).encode("utf-8")).digest()
            if event is not None
            else None
        ),
    }


def _sync_pointer_lineage(
    session: Session,
    *,
    contributor: StudyProgressContributor,
    generation: int,
    pointer: dict[str, Any],
    existing: tuple[StudyProgressLineageRef, ...],
    now_utc: datetime,
) -> bytes:
    pointer_rows = [row for row in existing if row.ref_kind == "LAST_REVIEW_EVENT"]
    external_rows = [row for row in existing if row.ref_kind != "LAST_REVIEW_EVENT"]
    for row in external_rows:
        row.subject_generation = generation

    desired_key = pointer.get("source_row_key")
    if desired_key is None:
        for row in pointer_rows:
            session.delete(row)
        lineage_payload = [
            {
                "ref_kind": "LAST_REVIEW_EVENT",
                "source_row_key": None,
                "ref_status": "ABSENT",
            },
            *[_lineage_material(row) for row in external_rows],
        ]
    else:
        encoded_key = encode_identity(
            str(desired_key), max_bytes=144, field_name="source_row_key"
        )
        selected = next(
            (row for row in pointer_rows if bytes(row.source_row_key) == encoded_key),
            None,
        )
        for row in pointer_rows:
            if row is not selected:
                session.delete(row)
        if selected is None:
            selected = StudyProgressLineageRef(
                contributor_id=int(contributor.id),
                subject_generation=generation,
                ref_kind="LAST_REVIEW_EVENT",
                source_row_key=encoded_key,
                ref_status=str(pointer["ref_status"]),
                ingested_at=now_utc,
            )
            session.add(selected)
        selected.subject_generation = generation
        selected.ref_status = str(pointer["ref_status"])
        selected.occurred_at = pointer.get("occurred_at")
        selected.source_payload_hash = pointer.get("source_payload_hash")
        selected.ingested_at = now_utc
        lineage_payload = [
            _lineage_material(selected),
            *[_lineage_material(row) for row in external_rows],
        ]

    lineage_payload.sort(
        key=lambda value: (
            str(value.get("ref_kind") or ""),
            str(value.get("source_row_key") or ""),
        )
    )
    return canonical_typed_document(
        {"references": lineage_payload},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest


def finalize_study_authority_evidence(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    siblings: LockedStudyAuthoritySiblings,
    compatibility: LockedStudyAuthorityCompatibility,
    write_result: StudyAuthorityWriteResult,
    review_event: ReviewEvent,
    now_utc: datetime,
) -> StudyAuthorityEvidenceResult:
    """Refresh all existing compatibility evidence after a NOTE material write."""

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE":
        raise _fail(
            "AUTHORITY_MODE_CONFLICT",
            "Evidence finalization is available only for NOTE authority.",
        )
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail(
            "INVALID_AUTHORITY_TIME", "Authority evidence time must be naive UTC."
        )
    subject = locked.subject
    state = locked.state
    if subject.id is None or state is None or review_event.id is None:
        raise _fail(
            "UNFLUSHED_AUTHORITY_EVIDENCE",
            "Subject, state and ReviewEvent must be persisted before finalization.",
        )
    subject_id = int(subject.id)
    generation = int(subject.subject_generation)
    if (
        int(subject.learner_user_id) != route.learner_user_id
        or int(siblings.subject_id) != subject_id
        or int(compatibility.subject_id) != subject_id
        or int(siblings.subject_generation) != generation
        or int(compatibility.subject_generation) != generation
        or siblings.learner_user_id != route.learner_user_id
        or compatibility.learner_user_id != route.learner_user_id
    ):
        raise _fail(
            "AUTHORITY_CONTEXT_DIVERGED",
            "Evidence inputs do not describe one fenced learner/Note subject.",
        )
    if int(review_event.user_id) != route.learner_user_id:
        raise _fail(
            "HISTORY_LEARNER_MISMATCH",
            "ReviewEvent belongs to another learner.",
        )
    event_card_id = str(review_event.card_id or "")
    if event_card_id not in siblings.progress_by_card_id:
        raise _fail(
            "CARD_OUTSIDE_AUTHORITY_SUBJECT",
            "ReviewEvent Card is outside the locked authority subject.",
        )
    if int(locked.token.authority_revision) != int(write_result.authority_revision):
        raise _fail(
            "AUTHORITY_REVISION_DIVERGED",
            "Authority token changed after the material write.",
        )
    if (
        bytes(locked.token.semantic_state_hash or b"")
        != write_result.semantic_state_hash
        or bytes(state.semantic_state_hash) != write_result.semantic_state_hash
        or write_result.state is not state
    ):
        raise _fail(
            "AUTHORITY_STATE_DIVERGED",
            "Authority state/token differs from the material-write result.",
        )
    if int(subject.mirror_revision) >= _MYSQL_SIGNED_BIGINT_MAX:
        raise _fail(
            "MIRROR_REVISION_EXHAUSTED",
            "Derived mirror revision cannot advance.",
        )
    if (
        int(subject.mirror_revision) != compatibility.expected_mirror_revision
        or int(state.mirror_revision) != compatibility.expected_mirror_revision
    ):
        raise _fail(
            "STALE_AUTHORITY_EVIDENCE",
            "Derived mirror evidence was already finalized or changed after locking.",
        )

    progress_by_card_id = dict(siblings.progress_by_card_id)
    projected_by_card_id = {
        str(row.card_id): row for row in write_result.projected_progress
    }
    card_by_id = {str(card.id): card for card in siblings.cards}
    expected_cards = set(card_by_id)
    if (
        set(progress_by_card_id) != expected_cards
        or set(projected_by_card_id) != expected_cards
        or set(compatibility.contributor_by_card_id) != expected_cards
    ):
        raise _fail(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "Evidence finalization requires the complete projected sibling vector.",
        )
    if any(projected_by_card_id[key] is not progress_by_card_id[key] for key in expected_cards):
        raise _fail(
            "AUTHORITY_CONTEXT_DIVERGED",
            "Material-write result does not contain the locked sibling rows.",
        )
    if progress_by_card_id[event_card_id].last_review_event_id != int(review_event.id):
        raise _fail(
            "AUTHORITY_EVENT_POINTER_MISMATCH",
            "The reviewed Card projection does not point to its ReviewEvent.",
        )
    try:
        new_provenance_code, _provenance, _runtime = native_review_event_provenance(
            review_event
        )
    except StudyProgressHistoryError as exc:
        raise _fail(exc.code, str(exc)) from exc

    pointer_ids = sorted(
        {
            int(row.last_review_event_id)
            for row in progress_by_card_id.values()
            if row.last_review_event_id is not None
        }
    )
    event_by_id = (
        {
            int(row.id): row
            for row in session.execute(
                select(ReviewEvent)
                .where(ReviewEvent.id.in_(pointer_ids))
                .order_by(ReviewEvent.id.asc())
                .with_for_update()
            ).scalars()
        }
        if pointer_ids
        else {}
    )
    if event_by_id.get(int(review_event.id)) is not review_event:
        raise _fail(
            "AUTHORITY_EVENT_DIVERGED",
            "ReviewEvent identity changed before evidence finalization.",
        )

    contributor_ids = tuple(
        sorted(
            int(row.id)
            for row in compatibility.contributor_by_card_id.values()
            if row.id is not None
        )
    )
    lineage_rows = tuple(
        session.execute(
            select(StudyProgressLineageRef)
            .where(StudyProgressLineageRef.contributor_id.in_(contributor_ids))
            .order_by(
                StudyProgressLineageRef.contributor_id.asc(),
                StudyProgressLineageRef.ref_kind.asc(),
                StudyProgressLineageRef.source_row_key.asc(),
                StudyProgressLineageRef.id.asc(),
            )
            .with_for_update()
        ).scalars()
    )
    lineage_by_contributor_id: dict[int, list[StudyProgressLineageRef]] = defaultdict(list)
    for row in lineage_rows:
        lineage_by_contributor_id[int(row.contributor_id)].append(row)

    authority_material: list[dict[str, str]] = []
    lineage_material: list[dict[str, str]] = []
    lineage_hashes: list[bytes] = []
    for card_id in sorted(expected_cards, key=lambda value: value.encode("utf-8")):
        progress = progress_by_card_id[card_id]
        contributor = compatibility.contributor_by_card_id[card_id]
        availability = compatibility.availability_by_contributor_id.get(
            int(contributor.id)
        )
        if availability is None:
            raise _fail(
                "INCOMPLETE_AUTHORITY_COMPATIBILITY",
                f"Card {card_id} has no locked availability evidence.",
            )
        expected_contributor_revision = (
            compatibility.contributor_revision_by_card_id[card_id]
        )
        expected_contributor_hash = compatibility.contributor_raw_hash_by_card_id[
            card_id
        ]
        if (
            int(contributor.card_progress_revision)
            != expected_contributor_revision
            or bytes(contributor.raw_progress_hash) != expected_contributor_hash
            or int(progress.revision) != expected_contributor_revision + 1
        ):
            raise _fail(
                "STALE_AUTHORITY_EVIDENCE",
                f"Card {card_id} evidence changed outside the material write.",
            )
        mapped = map_card_progress(
            progress,
            card_created_at=card_by_id[card_id].created_at,
            card_order_key=card_id,
        )
        if isinstance(mapped, MappingFailure):
            raise _fail(
                "UNPROJECTABLE_AUTHORITY_EVIDENCE",
                f"Card {card_id} cannot refresh compatibility evidence: {mapped.code}.",
            )
        if not isinstance(mapped, MappedCardProgress):  # pragma: no cover
            raise _fail(
                "UNPROJECTABLE_AUTHORITY_EVIDENCE",
                f"Card {card_id} produced no compatibility mapping.",
            )
        if mapped.semantic_state_hash != write_result.semantic_state_hash:
            raise _fail(
                "AUTHORITY_PROJECTION_DIVERGED",
                f"Card {card_id} differs from the authoritative Note state.",
            )

        pointer_status, pointer = _pointer_evidence(progress, event_by_id)
        lineage_hash = _sync_pointer_lineage(
            session,
            contributor=contributor,
            generation=generation,
            pointer=pointer,
            existing=tuple(lineage_by_contributor_id.get(int(contributor.id), ())),
            now_utc=now_utc,
        )
        inherited_completeness = str(contributor.history_completeness_code)
        if card_id == event_card_id:
            provenance_code = new_provenance_code
            completeness = (
                "HISTORY_NATIVE_COMPLETE"
                if inherited_completeness == "HISTORY_NATIVE_COMPLETE"
                else "HISTORY_MIXED_PARTIAL"
            )
        else:
            provenance_code = str(contributor.current_provenance_code)
            completeness = inherited_completeness
        try:
            evidence = build_contributor_evidence(
                mapped,
                progress,
                subject_generation=generation,
                pointer_status=pointer_status,
                history_completeness_code=completeness,
                current_provenance_code=provenance_code,
                lineage_vector_hash=lineage_hash,
            )
        except StudyProgressCodecError as exc:
            raise _fail(exc.code, str(exc)) from exc

        contributor.subject_generation = evidence.subject_generation
        contributor.source_progress_id = evidence.source_progress_id
        contributor.live_card_progress_id = evidence.live_card_progress_id
        contributor.logical_card_key = evidence.logical_card_key
        contributor.live_card_id = evidence.live_card_id
        contributor.card_progress_revision = evidence.card_progress_revision
        contributor.raw_schema_version = evidence.raw_schema_version
        contributor.storage_codec = evidence.storage_codec
        contributor.raw_payload = evidence.raw.payload
        contributor.raw_payload_size = evidence.raw.size
        contributor.raw_progress_hash = evidence.raw.digest
        contributor.pointer_status = evidence.pointer_status
        contributor.history_completeness_code = evidence.history_completeness_code
        contributor.current_provenance_code = evidence.current_provenance_code
        contributor.lineage_vector_hash = evidence.lineage_vector_hash
        contributor.contributor_status = evidence.contributor_status
        contributor.detached_at = None
        contributor.updated_at = now_utc

        projection = mapped.availability
        availability.subject_generation = generation
        availability.projection_version = projection.projection_version
        availability.normalized_queue = projection.normalized_queue
        availability.due_at = projection.due_at
        availability.due_day = projection.due_day
        availability.is_suspended = projection.is_suspended
        availability.is_buried = projection.is_buried
        availability.buried_until_day = projection.buried_until_day
        availability.card_created_at = projection.card_created_at
        availability.card_order_key = projection.card_order_key
        availability.state_schema_version = projection.state_schema_version
        availability.semantic_state_hash = projection.semantic_state_hash
        availability.updated_at = now_utc

        authority_material.append(
            {
                "card_id": card_id,
                "progress_id": str(progress.id),
                "raw_progress_hash": mapped.raw.digest.hex(),
                "revision": str(progress.revision),
            }
        )
        lineage_material.append(
            {
                "card_id": card_id,
                "lineage_vector_hash": lineage_hash.hex(),
                "progress_id": str(progress.id),
            }
        )
        lineage_hashes.append(lineage_hash)

    authority_vector_hash = canonical_document(
        {"contributors": authority_material},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    lineage_vector_hash = canonical_document(
        {"contributors": lineage_material},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    if len(expected_cards) == 1:
        status = "MIRRORED_SINGLE"
    elif len(set(lineage_hashes)) == 1:
        status = "MIRRORED_EQUIVALENT_FANIN"
    else:
        status = "MIRRORED_EQUIVALENT_FANIN_DISTINCT_LINEAGE"

    next_mirror_revision = int(subject.mirror_revision) + 1
    subject.mirror_revision = next_mirror_revision
    subject.status_code = status
    subject.contributor_count = len(expected_cards)
    subject.authority_vector_hash = authority_vector_hash
    subject.lineage_vector_hash = lineage_vector_hash
    subject.mapper_version = MAPPER_VERSION
    subject.last_mirrored_at = now_utc
    subject.updated_at = now_utc
    state.mirror_revision = next_mirror_revision
    state.updated_at = now_utc

    return StudyAuthorityEvidenceResult(
        mirror_revision=next_mirror_revision,
        subject_status=status,
        contributor_count=len(expected_cards),
        authority_vector_hash=authority_vector_hash,
        lineage_vector_hash=lineage_vector_hash,
        contributor_by_card_id=compatibility.contributor_by_card_id,
    )
