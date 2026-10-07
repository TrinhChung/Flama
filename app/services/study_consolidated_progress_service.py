"""Writes of the consolidated NOTE progress row (ADR P10 §2.4, §2.5).

Under ``CONSOLIDATED_V1`` one ``study_progress_subjects`` row holds a
learner/Note's state, authority revision and availability. The state and
revision are written through the row views of ``study_authority_repository``
(the existing CAS and state-write code runs unchanged); this module writes the
rest of the same row: the Note's availability anchors, history completeness
and provenance, and the bookkeeping counter echoed in receipts. Callers hold
the learner fence and the subject row ``FOR UPDATE`` and own the transaction.
"""

from __future__ import annotations

from datetime import datetime
from dataclasses import dataclass
from types import MappingProxyType

from app.repositories.study_authority_repository import (
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
    is_consolidated,
)
from app.services.study_authority_evidence_service import StudyAuthorityEvidenceResult
from app.services.study_authority_write_service import StudyAuthorityWriteResult
from app.services.study_note_card_projection import (
    NoteCardBurial,
    NoteStateProjection,
    project_note_state,
)
from app.services.study_progress_history_service import (
    StudyProgressHistoryError,
    native_review_event_provenance,
)
from app.services.study_progress_shadow_codec import StudyProgressCodecError
from models.review_event import ReviewEvent
from models.study_progress_subject import StudyProgressSubject

_MYSQL_SIGNED_BIGINT_MAX = 9_223_372_036_854_775_807
NATIVE_COMPLETE = "HISTORY_NATIVE_COMPLETE"
MIXED_PARTIAL = "HISTORY_MIXED_PARTIAL"


class StudyConsolidatedProgressError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


def _fail(code: str, message: str) -> StudyConsolidatedProgressError:
    return StudyConsolidatedProgressError(code, message)


def note_burial(subject: StudyProgressSubject) -> NoteCardBurial:
    """Burial is bound by the semantic hash but is not Algorithm State (P9-03 §2.8)."""

    return NoteCardBurial(
        is_buried=bool(subject.is_buried),
        buried_until_day=(
            int(subject.buried_until_day) if subject.buried_until_day is not None else None
        ),
    )


def project_subject_state(
    state_payload, *, burial: NoteCardBurial
) -> NoteStateProjection:
    try:
        return project_note_state(state_payload, burial=burial)
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc


def apply_note_availability(
    subject: StudyProgressSubject,
    projection: NoteStateProjection,
    *,
    now_utc: datetime,
) -> None:
    """Write the Note's availability anchors onto its row."""

    subject.projection_version = projection.projection_version
    subject.normalized_queue = projection.normalized_queue
    subject.due_at = projection.due_at
    subject.due_day = projection.due_day
    subject.is_suspended = projection.is_suspended
    subject.is_buried = projection.is_buried
    subject.buried_until_day = projection.buried_until_day
    subject.updated_at = now_utc


def clear_note_progress(subject: StudyProgressSubject, *, now_utc: datetime) -> None:
    """Remove current progress from a row (all-or-nothing CHECK group)."""

    for name in (
        "algorithm_key", "algorithm_version", "state_schema_version", "storage_codec",
        "state_payload", "state_payload_size", "algorithm_state_hash", "semantic_state_hash",
        "projection_version", "normalized_queue", "due_at", "due_day", "is_suspended",
        "is_buried", "buried_until_day", "history_completeness_code", "current_provenance_code",
    ):
        setattr(subject, name, None)
    subject.updated_at = now_utc


def advance_mirror_revision(subject: StudyProgressSubject) -> int:
    """The receipt-visible bookkeeping counter; not authority CAS."""

    current = int(subject.mirror_revision or 0)
    if current >= _MYSQL_SIGNED_BIGINT_MAX:
        raise _fail("MIRROR_REVISION_EXHAUSTED", "Derived mirror revision cannot advance.")
    subject.mirror_revision = current + 1
    return current + 1


def evidence_result(subject: StudyProgressSubject) -> StudyAuthorityEvidenceResult:
    return StudyAuthorityEvidenceResult(
        mirror_revision=int(subject.mirror_revision),
        subject_status=str(subject.status_code),
        contributor_count=int(subject.contributor_count or 0),
        authority_vector_hash=b"",
        lineage_vector_hash=b"",
        contributor_by_card_id=MappingProxyType({}),
    )


def finalize_consolidated_review(
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    write_result: StudyAuthorityWriteResult,
    projection: NoteStateProjection,
    review_event: ReviewEvent,
    now_utc: datetime,
) -> StudyAuthorityEvidenceResult:
    """Availability, provenance and completeness of one native review, on its row."""

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE" or not is_consolidated(route):
        raise _fail(
            "AUTHORITY_MODE_CONFLICT",
            "Consolidated review finalization requires a CONSOLIDATED_V1 NOTE route.",
        )
    if not isinstance(now_utc, datetime) or now_utc.tzinfo is not None:
        raise _fail("INVALID_AUTHORITY_TIME", "Authority evidence time must be naive UTC.")
    subject = locked.subject
    if subject.id is None or locked.state is None or review_event.id is None:
        raise _fail(
            "UNFLUSHED_AUTHORITY_EVIDENCE",
            "Subject state and ReviewEvent must be persisted before finalization.",
        )
    if int(subject.learner_user_id) != route.learner_user_id or int(review_event.user_id) != route.learner_user_id:
        raise _fail("HISTORY_LEARNER_MISMATCH", "Review belongs to another learner.")
    if (
        int(subject.authority_revision) != int(write_result.authority_revision)
        or bytes(subject.semantic_state_hash or b"") != write_result.semantic_state_hash
        or projection.semantic_state_hash != write_result.semantic_state_hash
        or write_result.projected_progress
    ):
        raise _fail(
            "AUTHORITY_STATE_DIVERGED",
            "Consolidated row differs from the material-write result.",
        )
    try:
        provenance_code, _provenance, _runtime = native_review_event_provenance(review_event)
    except StudyProgressHistoryError as exc:
        raise _fail(exc.code, str(exc)) from exc
    inherited = str(subject.history_completeness_code or "")
    subject.history_completeness_code = NATIVE_COMPLETE if inherited == NATIVE_COMPLETE else MIXED_PARTIAL
    subject.current_provenance_code = provenance_code
    apply_note_availability(subject, projection, now_utc=now_utc)
    advance_mirror_revision(subject)
    return evidence_result(subject)


def finalize_consolidated_rewrite(
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    write_result: StudyAuthorityWriteResult,
    projection: NoteStateProjection,
    now_utc: datetime,
) -> StudyAuthorityEvidenceResult:
    """Availability of a state rewrite without a ReviewEvent (Algorithm switch).

    Provenance and history completeness are preserved, as the canonical
    evidence refresh preserved them on every contributor.
    """

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE" or not is_consolidated(route):
        raise _fail(
            "AUTHORITY_MODE_CONFLICT",
            "Consolidated rewrite finalization requires a CONSOLIDATED_V1 NOTE route.",
        )
    subject = locked.subject
    if (
        locked.state is None
        or int(subject.authority_revision) != int(write_result.authority_revision)
        or bytes(subject.semantic_state_hash or b"") != write_result.semantic_state_hash
        or projection.semantic_state_hash != write_result.semantic_state_hash
        or write_result.projected_progress
    ):
        raise _fail(
            "AUTHORITY_STATE_DIVERGED",
            "Consolidated row differs from the material-write result.",
        )
    apply_note_availability(subject, projection, now_utc=now_utc)
    advance_mirror_revision(subject)
    return evidence_result(subject)


def finalize_consolidated_external(
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    context,
    projection: NoteStateProjection | None,
    now_utc: datetime,
) -> StudyAuthorityEvidenceResult:
    """An applied external snapshot's provenance and availability, on its row.

    ``projection`` is None when the snapshot only confirmed the current state.
    Completeness follows the per-contributor rule of the canonical path.
    """

    if not isinstance(route, StudyAuthorityRoute) or route.mode_code != "NOTE" or not is_consolidated(route):
        raise _fail(
            "AUTHORITY_MODE_CONFLICT",
            "Consolidated external evidence requires a CONSOLIDATED_V1 NOTE route.",
        )
    subject = locked.subject
    if locked.state is None or (
        projection is not None
        and projection.semantic_state_hash != bytes(subject.semantic_state_hash or b"")
    ):
        raise _fail(
            "AUTHORITY_STATE_DIVERGED",
            "Consolidated row differs from the applied external snapshot.",
        )
    inherited = str(subject.history_completeness_code or "")
    requested = str(context.history_completeness_code)
    subject.history_completeness_code = (
        MIXED_PARTIAL
        if requested == "HISTORY_SNAPSHOT_ONLY"
        and inherited not in {"HISTORY_UNKNOWN", "HISTORY_SNAPSHOT_ONLY"}
        else requested
    )
    subject.current_provenance_code = str(context.provenance_code)
    if projection is not None:
        apply_note_availability(subject, projection, now_utc=now_utc)
    subject.updated_at = now_utc
    advance_mirror_revision(subject)
    return evidence_result(subject)


def materialize_consolidated_pristine(
    *,
    items,
    provenance_code: str,
    now_utc: datetime,
) -> None:
    """First state of never-studied Notes, written onto their locked rows.

    ``items`` are ``(note_id, subject, cards, starting_ease)``; the subjects are
    locked pristine rows. The revision stays 0, as a new token's did.
    """

    state_by_ease = {}
    for note_id, subject, cards, starting_ease in items:
        if not cards:
            raise _fail("INCOMPLETE_AUTHORITY_COVERAGE", "A Note without Cards cannot be studied.")
        ease = float(starting_ease)
        state = state_by_ease.get(ease) or state_by_ease.setdefault(ease, pristine_state(ease))
        projection = project_subject_state(state.state.payload, burial=NoteCardBurial())
        if projection.semantic_state_hash != state.semantic_state_hash:
            raise _fail(
                "AUTHORITY_MATERIALIZATION_INCOMPLETE",
                "New Note authority did not build complete canonical state.",
            )
        subject.algorithm_key = state.algorithm_key
        subject.algorithm_version = state.algorithm_version
        subject.state_schema_version = state.state_schema_version
        subject.storage_codec = state.storage_codec
        subject.state_payload = state.state.payload
        subject.state_payload_size = state.state.size
        subject.algorithm_state_hash = state.algorithm_state_hash
        subject.semantic_state_hash = state.semantic_state_hash
        subject.history_completeness_code = NATIVE_COMPLETE
        subject.current_provenance_code = provenance_code
        apply_note_availability(subject, projection, now_utc=now_utc)
        subject.live_note_id = note_id
        subject.status_code = "MIRRORED_SINGLE" if len(cards) == 1 else "MIRRORED_EQUIVALENT_FANIN"
        advance_mirror_revision(subject)


def is_pristine_row(subject: StudyProgressSubject, *, starting_ease: float) -> bool:
    """Never answered since (re)materialization: the pristine state, unburied."""

    return bool(
        subject.state_payload is not None
        and dict(subject.state_payload) == dict(pristine_state(starting_ease).state.payload)
        and not bool(subject.is_buried)
    )


def _lifecycle_event(
    session,
    *,
    subject: StudyProgressSubject,
    learner_user_id: int,
    note_id: str,
    transition_code: str,
    source_path: str,
    operation_key: str,
    old_generation: int,
    old_hash: bytes | None,
    new_hash: bytes | None,
    removed_card_ids,
    deleted_note: bool,
    finalized_at: datetime,
) -> None:
    """The destructive-transition record the Algorithm history cut reads."""

    import hashlib

    from app.services.study_progress_contract import LIFECYCLE_EVIDENCE_SCHEMA_VERSION, MAPPER_VERSION
    from app.services.study_progress_shadow_codec import canonical_document, canonical_typed_document
    from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent

    removed = sorted(str(value) for value in removed_card_ids)
    evidence = canonical_typed_document(
        {
            "transition_code": transition_code,
            "source_path": source_path,
            "learner_user_id": int(learner_user_id),
            "logical_note_key": note_id,
            "removed_card_count": len(removed),
            "removed_card_vector_hash": (
                hashlib.sha256("\n".join(removed).encode("utf-8")).hexdigest() if removed else None
            ),
            "deleted_note": deleted_note,
            "old_contributor_count": len(removed),
            "new_contributor_count": 0 if deleted_note else len(removed),
            "mapper_version": MAPPER_VERSION,
        },
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    )
    session.add(StudyProgressLifecycleEvent(
        subject_id=int(subject.id),
        related_subject_id=None,
        old_generation=old_generation,
        new_generation=int(subject.subject_generation),
        transition_code=transition_code,
        occurred_at=finalized_at,
        source_path=source_path,
        operation_key_hash=canonical_document(
            {"source_path": source_path, "operation_key": operation_key},
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        ).digest,
        old_topology_hash=None,
        new_topology_hash=None,
        old_authority_hash=old_hash,
        new_authority_hash=new_hash,
        old_lineage_hash=None,
        new_lineage_hash=None,
        result_code=transition_code,
        reason_code=None,
        evidence_schema_version=LIFECYCLE_EVIDENCE_SCHEMA_VERSION,
        evidence_payload=evidence.payload,
        evidence_payload_size=evidence.size,
        evidence_payload_hash=evidence.digest,
        created_at=finalized_at,
    ))


def _advance_revision(subject: StudyProgressSubject) -> None:
    revision = int(subject.authority_revision or 0)
    if revision >= _MYSQL_SIGNED_BIGINT_MAX:
        raise _fail("AUTHORITY_REVISION_EXHAUSTED", "Authority revision cannot advance.")
    subject.authority_revision = revision + 1


def reset_consolidated_note(
    session,
    *,
    learner_user_id: int,
    subject: StudyProgressSubject,
    note_id: str,
    cards,
    starting_ease: float,
    source_path: str,
    operation_key: str,
    now_utc: datetime,
) -> None:
    """Fresh pristine state on the next generation, as the canonical reset does."""

    old_generation = int(subject.subject_generation)
    old_hash = bytes(subject.semantic_state_hash) if subject.semantic_state_hash is not None else None
    subject.subject_generation = old_generation + 1
    # The projection path re-mirrors reset rows without an external context
    # (UNKNOWN_LEGACY); CANONICAL_V1 kept the same evidence.
    materialize_consolidated_pristine(
        items=[(note_id, subject, tuple(cards), starting_ease)],
        provenance_code="UNKNOWN_LEGACY",
        now_utc=now_utc,
    )
    _advance_revision(subject)
    _lifecycle_event(
        session, subject=subject, learner_user_id=learner_user_id, note_id=note_id,
        transition_code="TOMBSTONED_RESET", source_path=source_path, operation_key=operation_key,
        old_generation=old_generation, old_hash=old_hash, new_hash=bytes(subject.semantic_state_hash),
        removed_card_ids=[card.id for card in cards], deleted_note=False, finalized_at=now_utc,
    )


def delete_consolidated_note(
    session,
    *,
    learner_user_id: int,
    subject: StudyProgressSubject,
    note_id: str,
    card_ids,
    source_path: str,
    operation_key: str,
    now_utc: datetime,
) -> None:
    """Tombstone a deleted Note's row; history and receipts stay."""

    old_generation = int(subject.subject_generation)
    old_hash = bytes(subject.semantic_state_hash) if subject.semantic_state_hash is not None else None
    clear_note_progress(subject, now_utc=now_utc)
    _advance_revision(subject)
    subject.subject_generation = old_generation + 1
    subject.live_note_id = None
    subject.status_code = "TOMBSTONED_SUBJECT_DELETED"
    advance_mirror_revision(subject)
    _lifecycle_event(
        session, subject=subject, learner_user_id=learner_user_id, note_id=note_id,
        transition_code="TOMBSTONED_SUBJECT_DELETED", source_path=source_path, operation_key=operation_key,
        old_generation=old_generation, old_hash=old_hash, new_hash=None,
        removed_card_ids=card_ids, deleted_note=True, finalized_at=now_utc,
    )


@dataclass(frozen=True)
class ExternalProgressContext:
    """Provenance of an applied external snapshot (Anki/Connect)."""

    provenance_code: str
    history_completeness_code: str


@dataclass(frozen=True)
class ExternalHistoryEvent:
    """One imported revlog review; never a current-state mutation."""

    review_event: ReviewEvent
    source_ref: object
    import_state: str


_REVLOG_PAYLOAD_FIELDS = (
    "rating",
    "mode",
    "review_kind",
    "queue_before",
    "queue_after",
    "interval_days_before",
    "interval_days_after",
    "due_day_before",
    "due_day_after",
    "days_late",
    "ease_factor_before",
    "ease_factor_after",
    "memory_stability_before",
    "memory_stability_after",
    "memory_difficulty_before",
    "memory_difficulty_after",
    "leeched_after",
    "suspended_after",
    "sequence_no",
)


def append_consolidated_external_history(
    session,
    *,
    learner_user_id: int,
    subject: StudyProgressSubject,
    cards,
    history_events,
    now_utc: datetime,
) -> int:
    """Append imported revlog facts for a locked row; its state is unchanged.

    The row's history completeness follows the rule the contributor rows used:
    native or snapshot history mixed with imported history is partial.
    """

    from sqlalchemy import select

    from app.services.study_progress_contract import HISTORY_SCHEMA_VERSION, STORAGE_CODEC
    from app.services.study_progress_history_service import _decode_digest
    from app.services.study_progress_shadow_codec import canonical_document, canonical_typed_document
    from app.services.study_progress_shadow_mapper import encode_identity
    from models.study_progress_history_fact import StudyProgressHistoryFact

    card_ids = {str(card.id) for card in cards}
    note_id = str(subject.live_note_id or "")
    session.flush()
    inserted = 0
    for supplied in history_events:
        event = supplied.review_event
        source_ref = supplied.source_ref
        if event.id is None or source_ref.id is None:
            raise _fail("UNFLUSHED_HISTORY_EVIDENCE", "External history requires flushed event/ref identities.")
        if int(event.user_id) != int(learner_user_id) or int(source_ref.user_id) != int(learner_user_id):
            raise _fail("HISTORY_LEARNER_MISMATCH", "External history belongs to another learner.")
        if source_ref.review_event_id != event.id:
            raise _fail("HISTORY_CARD_MISMATCH", "External history reference does not match its event.")
        if str(event.card_id) not in card_ids:
            raise _fail("HISTORY_CARD_MISMATCH", "External history Card is outside its locked Note.")
        fact_identity = canonical_document(
            {"connect_review_event_ref_id": str(source_ref.id), "source": "connect_review_event_refs"},
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        ).digest
        existing = session.execute(
            select(StudyProgressHistoryFact)
            .where(
                StudyProgressHistoryFact.learner_user_id == int(learner_user_id),
                StudyProgressHistoryFact.fact_identity_hash == fact_identity,
            )
            .with_for_update()
        ).scalar_one_or_none()
        material = {field: getattr(event, field) for field in _REVLOG_PAYLOAD_FIELDS}
        material.update({
            "connect_review_event_ref_id": str(source_ref.id),
            "source_key": str(source_ref.source_key),
            "external_review_id": str(source_ref.external_review_id),
            "external_card_id": str(source_ref.external_card_id),
            "source_payload_hash": str(source_ref.payload_hash),
            "source_status": str(source_ref.status),
        })
        fact = canonical_typed_document(material, too_large_code="STATE_PAYLOAD_TOO_LARGE")
        if existing is not None:
            if bytes(existing.fact_payload_hash) != fact.digest:
                raise _fail(
                    "HISTORY_FACT_CONFLICT", "External history identity was reused with different evidence."
                )
            continue
        repaired = supplied.import_state == "repaired"
        session.add(StudyProgressHistoryFact(
            learner_user_id=int(learner_user_id),
            subject_id=int(subject.id),
            logical_note_key=note_id.encode("utf-8"),
            subject_generation=int(subject.subject_generation),
            contributor_id=None,
            logical_card_key=encode_identity(str(event.card_id), max_bytes=256, field_name="logical_card_key"),
            review_event_id=int(event.id),
            fact_identity_hash=fact_identity,
            history_schema_version=HISTORY_SCHEMA_VERSION,
            storage_codec=STORAGE_CODEC,
            occurred_at=event.reviewed_at,
            ingested_at=now_utc,
            provenance_code="CONNECT_REVLOG",
            source_operation_key=encode_identity(
                f"{source_ref.source_key}:{source_ref.external_review_id}",
                max_bytes=512,
                field_name="source_operation_key",
            ),
            action_key="anki.revlog.rating",
            action_version="revlog-v1",
            review_kind=str(event.review_kind or "") or None,
            algorithm_key=str(event.scheduler_algorithm or "") or None,
            algorithm_version=str(event.algorithm_version or "") or None,
            state_schema_version=None,
            scheduler_config_hash=_decode_digest(event.scheduler_config_hash, field_name="scheduler_config_hash"),
            before_state_hash=None,
            after_state_hash=None,
            history_completeness_code="HISTORY_REPAIRED_PARTIAL" if repaired else "HISTORY_IMPORTED_PARTIAL",
            gap_reason_code="REPAIRED_EXTERNAL_PROJECTION" if repaired else "EXTERNAL_HISTORY_RANGE_UNPROVEN",
            fact_payload=fact.payload,
            fact_payload_size=fact.size,
            fact_payload_hash=fact.digest,
            created_at=now_utc,
        ))
        current = str(subject.history_completeness_code or "")
        if current in {"HISTORY_NATIVE_COMPLETE", "HISTORY_SNAPSHOT_ONLY", "HISTORY_MIXED_PARTIAL"}:
            subject.history_completeness_code = MIXED_PARTIAL
        elif current == "HISTORY_IMPORTED_PARTIAL" and repaired:
            subject.history_completeness_code = "HISTORY_REPAIRED_PARTIAL"
        subject.updated_at = now_utc
        inserted += 1
    session.flush()
    return inserted


_PRISTINE_CARD_KEY = "pristine-card"
_PRISTINE_TIME = datetime(2000, 1, 1)


def pristine_state(starting_ease: float):
    """The Algorithm State of a never-reviewed Note with this starting ease.

    It is exactly what ``map_card_progress`` derives from a ``new`` LEGACY row.
    Row identity (id, learner, Card, timestamps) is not part of Algorithm
    State, so this in-memory row is never persisted and its placeholder
    identity reaches no stored value.
    """

    from types import SimpleNamespace

    from app.repositories.study_authority_repository import StudyAuthorityFenceError
    from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress

    mapped = map_card_progress(
        SimpleNamespace(
            id=1, user_id=1, card_id=_PRISTINE_CARD_KEY, queue="new", step_index=0,
            due_at=None, due_day=None, interval_days=0, interval_days_raw=0.0,
            is_suspended=False, is_buried=False, buried_until_day=None,
            review_kind="review", scheduler_mode="legacy", ease_factor=float(starting_ease),
            memory_stability=None, memory_difficulty=None, suspension_reason=None,
            last_leech_at=None, last_leech_lapses=0, last_review_event_id=None,
            reps=0, lapses=0, last_reviewed_at=None, revision=0,
            created_at=_PRISTINE_TIME, updated_at=_PRISTINE_TIME,
        ),
        card_created_at=_PRISTINE_TIME,
        card_order_key=_PRISTINE_CARD_KEY,
    )
    if not isinstance(mapped, MappedCardProgress):
        raise StudyAuthorityFenceError(
            "AUTHORITY_MATERIALIZATION_INCOMPLETE",
            f"Pristine state cannot be built: {mapped.code}.",
        )
    return mapped
