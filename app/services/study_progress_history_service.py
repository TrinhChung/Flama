"""Shared append-only native study history fact writer.

The caller owns the surrounding transaction and all authority/current-state
locks.  This module validates immutable ReviewEvent evidence and stages at most
one scheduler-grade history fact; it never commits or rolls back.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.services.study_progress_contract import (
    HISTORY_COMPLETENESS_CODES,
    HISTORY_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    CanonicalDocument,
    canonical_document,
    canonical_typed_document,
    StudyProgressCodecError,
)
from app.services.study_progress_shadow_mapper import encode_identity
from app.validators.review_event import (
    REVIEW_EVENT_PAYLOAD_SCHEMA,
    classify_review_event_payload,
)
from models.review_event import ReviewEvent
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_subject import StudyProgressSubject


_SOURCE_PROVENANCE = {
    "native.rest": "NATIVE_DIRECT",
    "native.mcp": "NATIVE_MCP",
    "native.session.commit": "NATIVE_SESSION",
    "native.session.worker": "NATIVE_ASYNC_BATCH",
}
_HISTORY_PAYLOAD_FIELDS = (
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


class StudyProgressHistoryError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = str(code)


@dataclass(frozen=True)
class NativeHistoryFactInput:
    learner_user_id: int
    subject: StudyProgressSubject
    contributor: StudyProgressContributor
    review_event: ReviewEvent
    history_completeness_code: str
    before_state_hash: str | bytes | None = None
    after_state_hash: str | bytes | None = None
    require_scheduler_grade: bool = False


@dataclass(frozen=True)
class NativeHistoryFactResult:
    fact: StudyProgressHistoryFact
    inserted: bool


def _fail(code: str, message: str) -> StudyProgressHistoryError:
    return StudyProgressHistoryError(code, message)


def _utc_naive(value: datetime) -> datetime:
    if not isinstance(value, datetime):
        raise _fail("INVALID_HISTORY_TIME", "History time must be a datetime.")
    if value.tzinfo is not None:
        return value.astimezone(timezone.utc).replace(tzinfo=None)
    return value


def _decode_digest(value: str | bytes | None, *, field_name: str) -> bytes | None:
    if value is None:
        return None
    if isinstance(value, bytes):
        if len(value) != 32:
            raise _fail("INVALID_HISTORY_HASH", f"{field_name} must contain 32 bytes.")
        return value
    token = str(value).strip()
    for prefix in ("sha256-", "sha256:"):
        if token.startswith(prefix):
            token = token[len(prefix) :]
            break
    if len(token) != 64:
        raise _fail(
            "INVALID_HISTORY_HASH",
            f"{field_name} must be a canonical SHA-256 digest.",
        )
    try:
        decoded = bytes.fromhex(token)
    except ValueError as exc:
        raise _fail(
            "INVALID_HISTORY_HASH", f"{field_name} must be hexadecimal."
        ) from exc
    if len(decoded) != 32:  # pragma: no cover - guarded by token length
        raise _fail("INVALID_HISTORY_HASH", f"{field_name} must contain 32 bytes.")
    return decoded


def native_review_event_provenance(
    event: ReviewEvent,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    """Validate and decode one canonical native ReviewEvent envelope."""

    disposition = classify_review_event_payload(
        event.payload_json,
        scheduler_algorithm=event.scheduler_algorithm,
        algorithm_version=event.algorithm_version,
        scheduler_config_hash=event.scheduler_config_hash,
        study_session_id=event.study_session_id,
        client_event_id=event.client_event_id,
        sequence_no=event.sequence_no,
    )
    if disposition.category != "complete":
        raise _fail(
            "INVALID_REVIEW_EVENT_PROVENANCE",
            "Native ReviewEvent provenance is invalid: "
            f"{disposition.reason}.",
        )
    try:
        payload = json.loads(event.payload_json)
    except (TypeError, ValueError) as exc:  # pragma: no cover - classifier covers it
        raise _fail(
            "INVALID_REVIEW_EVENT_PROVENANCE",
            "Native ReviewEvent payload cannot be decoded.",
        ) from exc
    if (
        not isinstance(payload, dict)
        or payload.get("schema_version") != REVIEW_EVENT_PAYLOAD_SCHEMA
    ):
        raise _fail(
            "INVALID_REVIEW_EVENT_PROVENANCE",
            "Native ReviewEvent payload has no schema identity.",
        )
    provenance = payload.get("provenance")
    runtime = payload.get("_study_runtime")
    if not isinstance(provenance, dict) or not isinstance(runtime, dict):
        raise _fail(
            "INVALID_REVIEW_EVENT_PROVENANCE",
            "Native ReviewEvent lacks runtime provenance.",
        )
    source_path = str(provenance.get("source_path") or "")
    provenance_code = _SOURCE_PROVENANCE.get(source_path)
    if provenance_code is None:
        raise _fail(
            "UNSUPPORTED_REVIEW_EVENT_SOURCE",
            f"Unsupported native history source path: {source_path!r}.",
        )
    return provenance_code, provenance, runtime


def native_review_fact_document(event: ReviewEvent) -> CanonicalDocument:
    """Rebuild the exact v1 fact payload from immutable ReviewEvent columns."""

    if event.id is None:
        raise _fail(
            "UNFLUSHED_REVIEW_EVENT", "ReviewEvent needs an ID for history evidence."
        )
    material = {field: getattr(event, field) for field in _HISTORY_PAYLOAD_FIELDS}
    material["review_event_id"] = int(event.id)
    return canonical_typed_document(
        material, too_large_code="STATE_PAYLOAD_TOO_LARGE"
    )


def native_review_fact_operation_key(
    event: ReviewEvent, provenance: dict[str, Any]
) -> bytes:
    """Rebuild the persisted source operation identity for one native fact."""

    operation_key = (
        provenance.get("request_id")
        or provenance.get("client_event_id")
        or provenance.get("study_session_id")
        or f"review-event:{event.id}"
    )
    return encode_identity(
        str(operation_key),
        max_bytes=512,
        field_name="source_operation_key",
    )


def append_native_history_fact(
    session: Session,
    *,
    command: NativeHistoryFactInput,
    now_utc: datetime,
) -> NativeHistoryFactResult:
    """Stage one immutable native history fact, or return its exact replay.

    The subject and contributor must already be locked by the caller.  An
    existing fact is accepted only when it points to the same ReviewEvent and
    has the same canonical evidence payload.
    """

    learner_user_id = command.learner_user_id
    if (
        isinstance(learner_user_id, bool)
        or not isinstance(learner_user_id, int)
        or learner_user_id <= 0
    ):
        raise _fail("INVALID_HISTORY_CONTEXT", "Learner ID must be positive.")
    subject = command.subject
    contributor = command.contributor
    event = command.review_event
    if subject.id is None or contributor.id is None or event.id is None:
        raise _fail(
            "UNFLUSHED_HISTORY_EVIDENCE",
            "Subject, contributor and ReviewEvent must be persisted before history append.",
        )
    if int(subject.learner_user_id) != learner_user_id:
        raise _fail(
            "HISTORY_LEARNER_MISMATCH",
            "History subject belongs to another learner.",
        )
    if int(event.user_id) != learner_user_id:
        raise _fail(
            "HISTORY_LEARNER_MISMATCH",
            "ReviewEvent belongs to another learner.",
        )
    generation = int(subject.subject_generation)
    if generation < 1 or int(contributor.subject_generation) != generation:
        raise _fail(
            "HISTORY_GENERATION_MISMATCH",
            "History contributor generation differs from its subject.",
        )
    if int(contributor.subject_id) != int(subject.id):
        raise _fail(
            "HISTORY_CONTRIBUTOR_MISMATCH",
            "History contributor belongs to another subject.",
        )
    if str(contributor.contributor_status) != "ACTIVE":
        raise _fail(
            "HISTORY_CONTRIBUTOR_INACTIVE",
            "History contributor is not active.",
        )
    logical_card_key = str(event.card_id or "").strip()
    if not logical_card_key:
        raise _fail("INVALID_HISTORY_CONTEXT", "ReviewEvent has no Card identity.")
    if (
        bytes(contributor.logical_card_key) != logical_card_key.encode("utf-8")
        or str(contributor.live_card_id or "") != logical_card_key
    ):
        raise _fail(
            "HISTORY_CARD_MISMATCH",
            "ReviewEvent Card differs from its active contributor.",
        )
    completeness = str(command.history_completeness_code or "")
    if completeness not in HISTORY_COMPLETENESS_CODES:
        raise _fail(
            "INVALID_HISTORY_COMPLETENESS",
            "History completeness code is invalid.",
        )

    provenance_code, provenance, runtime = native_review_event_provenance(event)
    fact_identity = canonical_document(
        {"review_event_id": str(event.id), "source": "review_events"},
        too_large_code="STATE_PAYLOAD_TOO_LARGE",
    ).digest
    fact_document = native_review_fact_document(event)
    scheduler_config_hash = _decode_digest(
        event.scheduler_config_hash,
        field_name="scheduler_config_hash",
    )
    before_state_hash = _decode_digest(
        command.before_state_hash,
        field_name="before_state_hash",
    )
    after_state_hash = _decode_digest(
        command.after_state_hash,
        field_name="after_state_hash",
    )
    if command.require_scheduler_grade:
        if not all(
            (
                before_state_hash,
                after_state_hash,
                scheduler_config_hash,
                runtime.get("action_key"),
                runtime.get("action_contract_version"),
                runtime.get("trigger_key"),
                runtime.get("trigger_contract_version"),
                runtime.get("algorithm_key"),
                runtime.get("algorithm_version"),
                runtime.get("state_schema_version"),
            )
        ):
            raise _fail(
                "INCOMPLETE_SCHEDULER_HISTORY",
                "NOTE authority history requires before/after hashes and exact runtime identities.",
            )
    logical_note_key = bytes(subject.logical_note_key)
    if not logical_note_key:
        raise _fail("INVALID_HISTORY_CONTEXT", "Subject has no logical Note identity.")
    encoded_card_key = encode_identity(
        logical_card_key,
        max_bytes=256,
        field_name="logical_card_key",
    )
    source_operation_key = native_review_fact_operation_key(event, provenance)
    occurred_at = _utc_naive(event.reviewed_at)
    action_key = str(runtime.get("action_key") or "") or None
    action_version = str(runtime.get("action_contract_version") or "") or None
    review_kind = str(event.review_kind or "") or None
    algorithm_key = str(runtime.get("algorithm_key") or "") or None
    algorithm_version = str(runtime.get("algorithm_version") or "") or None
    state_schema_version = str(runtime.get("state_schema_version") or "") or None
    gap_reason_code = (
        None if completeness == "HISTORY_NATIVE_COMPLETE" else "LEGACY_GAP"
    )
    existing = session.execute(
        select(StudyProgressHistoryFact)
        .where(
            StudyProgressHistoryFact.learner_user_id == learner_user_id,
            StudyProgressHistoryFact.fact_identity_hash == fact_identity,
        )
        .with_for_update()
    ).scalar_one_or_none()
    if existing is not None:
        try:
            stored_document = canonical_document(
                existing.fact_payload,
                too_large_code="STATE_PAYLOAD_TOO_LARGE",
            )
        except (StudyProgressCodecError, TypeError) as exc:
            raise _fail(
                "CORRUPT_HISTORY_FACT",
                "Stored history fact payload cannot be verified.",
            ) from exc
        if (
            stored_document.size != int(existing.fact_payload_size)
            or stored_document.digest != bytes(existing.fact_payload_hash)
        ):
            raise _fail(
                "CORRUPT_HISTORY_FACT",
                "Stored history fact payload differs from its persisted digest.",
            )
        if (
            existing.review_event_id != int(event.id)
            or bytes(existing.fact_payload_hash) != fact_document.digest
            or existing.subject_id != int(subject.id)
            or existing.subject_generation != generation
            or existing.contributor_id != int(contributor.id)
            or bytes(existing.logical_note_key or b"") != logical_note_key
            or bytes(existing.logical_card_key) != encoded_card_key
            or existing.history_completeness_code != completeness
            or existing.provenance_code != provenance_code
            or bytes(existing.source_operation_key or b"") != source_operation_key
            or existing.action_key != action_key
            or existing.action_version != action_version
            or existing.review_kind != review_kind
            or existing.algorithm_key != algorithm_key
            or existing.algorithm_version != algorithm_version
            or existing.state_schema_version != state_schema_version
            or existing.gap_reason_code != gap_reason_code
            or existing.history_schema_version != HISTORY_SCHEMA_VERSION
            or existing.storage_codec != STORAGE_CODEC
            or _utc_naive(existing.occurred_at) != occurred_at
            or (
                bytes(existing.scheduler_config_hash)
                if existing.scheduler_config_hash is not None
                else None
            )
            != scheduler_config_hash
            or (
                bytes(existing.before_state_hash)
                if existing.before_state_hash is not None
                else None
            )
            != before_state_hash
            or (
                bytes(existing.after_state_hash)
                if existing.after_state_hash is not None
                else None
            )
            != after_state_hash
        ):
            raise _fail(
                "HISTORY_IDENTITY_REUSED",
                "History fact identity was reused with different evidence.",
            )
        return NativeHistoryFactResult(fact=existing, inserted=False)

    ingested_at = _utc_naive(now_utc)
    fact = StudyProgressHistoryFact(
        learner_user_id=learner_user_id,
        subject_id=int(subject.id),
        logical_note_key=logical_note_key,
        subject_generation=generation,
        contributor_id=int(contributor.id),
        logical_card_key=encoded_card_key,
        review_event_id=int(event.id),
        fact_identity_hash=fact_identity,
        history_schema_version=HISTORY_SCHEMA_VERSION,
        storage_codec=STORAGE_CODEC,
        occurred_at=occurred_at,
        ingested_at=ingested_at,
        provenance_code=provenance_code,
        source_operation_key=source_operation_key,
        action_key=action_key,
        action_version=action_version,
        review_kind=review_kind,
        algorithm_key=algorithm_key,
        algorithm_version=algorithm_version,
        state_schema_version=state_schema_version,
        scheduler_config_hash=scheduler_config_hash,
        before_state_hash=before_state_hash,
        after_state_hash=after_state_hash,
        history_completeness_code=completeness,
        gap_reason_code=gap_reason_code,
        fact_payload=fact_document.payload,
        fact_payload_size=fact_document.size,
        fact_payload_hash=fact_document.digest,
        created_at=ingested_at,
    )
    session.add(fact)
    return NativeHistoryFactResult(fact=fact, inserted=True)
