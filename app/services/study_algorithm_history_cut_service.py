"""Read-only, fail-closed history evidence cut for a future Algorithm switch.

The caller owns the transaction and must already hold the learner route,
subject/token/state, sibling CardProgress and compatibility locks in canonical
order. This service locks the remaining history/lifecycle rows, copies their
bytes into an immutable cut and never initializes state or commits a switch.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import hashlib
import json

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.repositories.study_authority_repository import (
    LockedStudyAuthorityCompatibility,
    LockedStudyAuthoritySiblings,
    LockedStudyAuthoritySubject,
    StudyAuthorityRoute,
)
from app.services.study_authority_cas_service import (
    StudyAuthorityCASExpectation,
    verify_study_authority_cas,
)
from app.services.study_algorithm_registry import get_study_algorithm_support
from app.services.study_progress_contract import HISTORY_SCHEMA_VERSION, STORAGE_CODEC
from app.services.study_progress_history_service import (
    native_review_fact_document,
    native_review_fact_operation_key,
)
from app.services.study_progress_shadow_codec import (
    CanonicalDocument,
    STATE_DECODERS,
    StudyProgressCodecError,
    canonical_document,
    canonical_typed_document,
    state_document,
)
from app.validators.review_event import classify_review_event_payload
from models.review_event import ReviewEvent
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent


_CUT_SCHEMA = "study-algorithm-history-cut.v1"
_NATIVE_PROVENANCE = frozenset(
    {"NATIVE_DIRECT", "NATIVE_MCP", "NATIVE_SESSION", "NATIVE_ASYNC_BATCH"}
)
_NATIVE_SOURCE_CODES = {
    "native.rest": "NATIVE_DIRECT",
    "native.mcp": "NATIVE_MCP",
    "native.session.commit": "NATIVE_SESSION",
    "native.session.worker": "NATIVE_ASYNC_BATCH",
}


class StudyAlgorithmHistoryCutError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class FrozenStudyHistoryFact:
    id: int
    learner_user_id: int
    subject_id: int | None
    subject_generation: int | None
    contributor_id: int | None
    review_event_id: int | None
    fact_identity_hash: bytes
    history_schema_version: str
    storage_codec: str
    occurred_at: datetime
    ingested_at: datetime
    created_at: datetime
    logical_note_key: bytes | None
    logical_card_key: bytes
    source_operation_key: bytes | None
    provenance_code: str
    action_key: str | None
    action_version: str | None
    review_kind: str | None
    history_completeness_code: str
    gap_reason_code: str | None
    algorithm_key: str | None
    algorithm_version: str | None
    state_schema_version: str | None
    scheduler_config_hash: bytes | None
    before_state_hash: bytes | None
    after_state_hash: bytes | None
    payload_bytes: bytes
    payload_hash: bytes


@dataclass(frozen=True)
class FrozenStudyReviewEvent:
    id: int
    card_id: str
    reviewed_at: datetime
    payload_bytes: bytes
    payload_hash: bytes
    row_bytes: bytes
    row_hash: bytes


@dataclass(frozen=True)
class FrozenStudyAlgorithmHistoryCut:
    schema_version: str
    learner_user_id: int
    enrollment_epoch: int
    subject_id: int
    subject_generation: int
    authority_revision: int
    semantic_state_hash: bytes | None
    current_algorithm_key: str | None
    current_algorithm_version: str | None
    current_state_schema_version: str | None
    current_storage_codec: str | None
    current_state_payload_bytes: bytes | None
    current_state_payload_hash: bytes | None
    current_algorithm_state_hash: bytes | None
    logical_note_key: bytes
    facts: tuple[FrozenStudyHistoryFact, ...]
    review_events: tuple[FrozenStudyReviewEvent, ...]
    blocker_codes: tuple[str, ...]
    cut_hash: bytes

    @property
    def native_complete(self) -> bool:
        return not self.blocker_codes


def _digest(value: object, *, field_name: str) -> bytes:
    if isinstance(value, (bytearray, memoryview)):
        value = bytes(value)
    if not isinstance(value, bytes) or len(value) != 32:
        raise StudyAlgorithmHistoryCutError(
            "CORRUPT_HISTORY_FACT", f"{field_name} is not a 32-byte hash."
        )
    return value


def _nullable_digest(value: object, *, field_name: str) -> bytes | None:
    return None if value is None else _digest(value, field_name=field_name)


def _append_cut_material(digest: object, payload: dict[str, object]) -> None:
    document = canonical_document(payload, too_large_code="HISTORY_CUT_TOO_LARGE")
    encoded = document.encoded
    digest.update(len(encoded).to_bytes(4, "big"))
    digest.update(encoded)


def _freeze_row(row: object, *, field_name: str) -> CanonicalDocument:
    """Bind every persisted column, including metadata outside scheduler facts."""

    material: dict[str, object] = {}
    for column in row.__table__.columns:
        value = getattr(row, column.name)
        if isinstance(value, (bytes, bytearray, memoryview)):
            value = {"binary_hex": bytes(value).hex()}
        material[column.name] = value
    try:
        return canonical_typed_document(
            material, too_large_code="HISTORY_CUT_TOO_LARGE"
        )
    except StudyProgressCodecError as exc:
        raise StudyAlgorithmHistoryCutError(
            "CORRUPT_HISTORY_CUT_ROW",
            f"{field_name} cannot be frozen into canonical evidence.",
        ) from exc


def freeze_study_algorithm_history_cut(
    session: Session,
    *,
    route: StudyAuthorityRoute,
    locked: LockedStudyAuthoritySubject,
    expected: StudyAuthorityCASExpectation,
    siblings: LockedStudyAuthoritySiblings,
    compatibility: LockedStudyAuthorityCompatibility,
) -> FrozenStudyAlgorithmHistoryCut:
    """Freeze current subject history under existing authority locks.

    ``native_complete`` is deliberately conservative. Incomplete evidence is
    retained with blocker codes for an explicitly approved initializer policy;
    it is never silently promoted to complete or used to reconstruct state.
    """

    verified = verify_study_authority_cas(
        route=route, locked=locked, expected=expected
    )
    subject = locked.subject
    subject_id = verified.subject_id
    generation = verified.subject_generation
    # ADR P10: no contributors; the row carries history completeness.
    if (
        not isinstance(siblings, LockedStudyAuthoritySiblings)
        or not isinstance(compatibility, LockedStudyAuthorityCompatibility)
        or siblings.learner_user_id != verified.learner_user_id
        or compatibility.learner_user_id != verified.learner_user_id
        or siblings.subject_id != subject_id
        or compatibility.subject_id != subject_id
        or siblings.subject_generation != generation
        or compatibility.subject_generation != generation
    ):
        raise StudyAlgorithmHistoryCutError(
            "INCOMPLETE_HISTORY_CUT_LOCKS",
            "History cut requires the full locked sibling and compatibility vectors.",
        )

    # Keep both predicates: the subject branch catches facts whose stored
    # logical key was corrupted, while the learner/key branch catches detached
    # or wrongly linked facts. Separate indexed lock ranges avoid the broad
    # learner-row scan an OR predicate can induce on InnoDB.
    subject_fact_rows = tuple(
        session.execute(
            select(StudyProgressHistoryFact)
            .with_hint(
                StudyProgressHistoryFact,
                "FORCE INDEX (ix_sp_history_subject_order)",
                dialect_name="mysql",
            )
            .where(StudyProgressHistoryFact.subject_id == subject_id)
            .order_by(
                StudyProgressHistoryFact.subject_generation.asc(),
                StudyProgressHistoryFact.occurred_at.asc(),
                StudyProgressHistoryFact.id.asc(),
            )
            .with_for_update()
        ).scalars()
    )
    note_fact_rows = tuple(
        session.execute(
            select(StudyProgressHistoryFact)
            .with_hint(
                StudyProgressHistoryFact,
                "FORCE INDEX (ix_sp_history_learner_note_order)",
                dialect_name="mysql",
            )
            .where(
                StudyProgressHistoryFact.learner_user_id
                == verified.learner_user_id,
                StudyProgressHistoryFact.logical_note_key
                == bytes(subject.logical_note_key),
            )
            .order_by(
                StudyProgressHistoryFact.occurred_at.asc(),
                StudyProgressHistoryFact.id.asc(),
            )
            .with_for_update()
        ).scalars()
    )
    fact_rows = tuple(
        sorted(
            {int(row.id): row for row in (*subject_fact_rows, *note_fact_rows)}.values(),
            key=lambda row: (row.occurred_at, int(row.id)),
        )
    )
    lifecycle_rows = tuple(
        session.execute(
            select(StudyProgressLifecycleEvent.id)
            .where(
                or_(
                    StudyProgressLifecycleEvent.subject_id == subject_id,
                    StudyProgressLifecycleEvent.related_subject_id == subject_id,
                )
            )
            .order_by(StudyProgressLifecycleEvent.id.asc())
            .with_for_update()
        ).scalars()
    )
    review_event_rows = tuple(
        session.execute(
            select(ReviewEvent)
            .where(
                ReviewEvent.user_id == verified.learner_user_id,
                ReviewEvent.card_id.in_(siblings.card_ids),
            )
            .order_by(ReviewEvent.id.asc())
            .with_for_update()
        ).scalars()
    ) if siblings.card_ids else ()
    review_event_ids = frozenset(int(row.id) for row in review_event_rows)

    blockers: set[str] = set()
    if not str(subject.status_code or "").startswith("MIRRORED_"):
        blockers.add("SUBJECT_STATUS_UNSAFE")
    if not verified.has_current_state:
        blockers.add("NO_CURRENT_STATE")
    elif int(locked.state.subject_generation) != generation:
        blockers.add("STATE_GENERATION_MISMATCH")
    if generation != 1 or lifecycle_rows:
        blockers.add("LIFECYCLE_HISTORY_UNPROVEN")

    # Same blocker code as the contributor era: initializer policies key on it.
    if subject.history_completeness_code != "HISTORY_NATIVE_COMPLETE":
        blockers.add("CONTRIBUTOR_HISTORY_INCOMPLETE")

    frozen_events: list[FrozenStudyReviewEvent] = []
    runtime_by_event_id: dict[int, dict[str, object]] = {}
    provenance_by_event: dict[int, dict[str, object]] = {}
    provenance_by_event_id: dict[int, str] = {}
    for event in review_event_rows:
        payload_bytes = str(event.payload_json).encode("utf-8")
        row_document = _freeze_row(event, field_name="ReviewEvent")
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
            blockers.add("REVIEW_EVENT_PROVENANCE_UNPROVEN")
        else:
            decoded_event = json.loads(event.payload_json)
            runtime = decoded_event.get("_study_runtime")
            if isinstance(runtime, dict):
                runtime_by_event_id[int(event.id)] = runtime
            provenance = decoded_event.get("provenance")
            if isinstance(provenance, dict):
                provenance_by_event[int(event.id)] = provenance
                provenance_by_event_id[int(event.id)] = str(
                    _NATIVE_SOURCE_CODES.get(str(provenance.get("source_path") or ""))
                    or ""
                )
        frozen_events.append(
            FrozenStudyReviewEvent(
                id=int(event.id),
                card_id=str(event.card_id),
                reviewed_at=event.reviewed_at,
                payload_bytes=payload_bytes,
                payload_hash=hashlib.sha256(payload_bytes).digest(),
                row_bytes=row_document.encoded,
                row_hash=row_document.digest,
            )
        )

    frozen_facts: list[FrozenStudyHistoryFact] = []
    fact_event_ids: list[int] = []
    previous_after: bytes | None = None
    card_key_bytes = {card_id.encode("utf-8") for card_id in siblings.card_ids}
    event_by_id = {int(row.id): row for row in review_event_rows}
    for row in fact_rows:
        try:
            document = canonical_document(
                row.fact_payload, too_large_code="HISTORY_CUT_TOO_LARGE"
            )
        except (StudyProgressCodecError, TypeError) as exc:
            raise StudyAlgorithmHistoryCutError(
                "CORRUPT_HISTORY_FACT", "History fact payload cannot be decoded."
            ) from exc
        payload_hash = _digest(row.fact_payload_hash, field_name="fact_payload_hash")
        if document.size != int(row.fact_payload_size) or document.digest != payload_hash:
            raise StudyAlgorithmHistoryCutError(
                "CORRUPT_HISTORY_FACT", "History fact payload size/hash differs."
            )
        identity_hash = _digest(row.fact_identity_hash, field_name="fact_identity_hash")
        before_hash = _nullable_digest(row.before_state_hash, field_name="before_state_hash")
        after_hash = _nullable_digest(row.after_state_hash, field_name="after_state_hash")
        config_hash = _nullable_digest(
            row.scheduler_config_hash, field_name="scheduler_config_hash"
        )
        event_id = int(row.review_event_id) if row.review_event_id is not None else None
        if event_id is not None:
            expected_identity = canonical_document(
                {"review_event_id": str(event_id), "source": "review_events"},
                too_large_code="HISTORY_CUT_TOO_LARGE",
            ).digest
            if identity_hash != expected_identity:
                blockers.add("FACT_IDENTITY_MISMATCH")
        if event_id is not None:
            fact_event_ids.append(event_id)
        if (
            int(row.learner_user_id) != verified.learner_user_id
            or row.subject_id != subject_id
            or row.subject_generation != generation
            or bytes(row.logical_note_key or b"") != bytes(subject.logical_note_key)
            # A fact written before P10 kept its contributor id: history only.
            or bytes(row.logical_card_key) not in card_key_bytes
            or event_id is None
        ):
            blockers.add("FACT_LINKAGE_INCOMPLETE")
        linked_event = event_by_id.get(event_id)
        if linked_event is None or (
            str(linked_event.card_id).encode("utf-8") != bytes(row.logical_card_key)
            or str(linked_event.scheduler_algorithm or "") != str(row.algorithm_key or "")
            or str(linked_event.algorithm_version or "")
            != str(row.algorithm_version or "")
            or linked_event.reviewed_at != row.occurred_at
        ):
            blockers.add("FACT_LINKAGE_INCOMPLETE")
        if linked_event is not None:
            try:
                rebuilt = native_review_fact_document(linked_event)
            except (StudyProgressCodecError, TypeError):
                blockers.add("FACT_EVENT_PAYLOAD_MISMATCH")
            else:
                if rebuilt.digest != payload_hash:
                    blockers.add("FACT_EVENT_PAYLOAD_MISMATCH")
            provenance = provenance_by_event.get(event_id)
            if provenance is None:
                blockers.add("FACT_OPERATION_MISMATCH")
            else:
                try:
                    expected_operation_key = native_review_fact_operation_key(
                        linked_event, provenance
                    )
                except (StudyProgressCodecError, TypeError, ValueError):
                    blockers.add("FACT_OPERATION_MISMATCH")
                else:
                    if bytes(row.source_operation_key or b"") != expected_operation_key:
                        blockers.add("FACT_OPERATION_MISMATCH")
        runtime = runtime_by_event_id.get(event_id)
        event_config_hash = str(
            linked_event.scheduler_config_hash or ""
        ) if linked_event is not None else ""
        if event_config_hash.startswith(("sha256-", "sha256:")):
            event_config_hash = event_config_hash[7:]
        if runtime is None or (
            str(runtime.get("action_key") or "") != str(row.action_key or "")
            or str(runtime.get("action_contract_version") or "")
            != str(row.action_version or "")
            or str(runtime.get("algorithm_key") or "")
            != str(row.algorithm_key or "")
            or str(runtime.get("algorithm_version") or "")
            != str(row.algorithm_version or "")
            or str(runtime.get("state_schema_version") or "")
            != str(row.state_schema_version or "")
            or not runtime.get("trigger_key")
            or not runtime.get("trigger_contract_version")
            or provenance_by_event_id.get(event_id) != row.provenance_code
            or config_hash is None
            or event_config_hash.lower() != config_hash.hex()
        ):
            blockers.add("FACT_RUNTIME_MISMATCH")
        if (
            row.history_schema_version != HISTORY_SCHEMA_VERSION
            or row.storage_codec != STORAGE_CODEC
            or row.history_completeness_code != "HISTORY_NATIVE_COMPLETE"
            or row.gap_reason_code is not None
            or row.provenance_code not in _NATIVE_PROVENANCE
            or not row.action_key
            or not row.action_version
            or not row.algorithm_key
            or not row.algorithm_version
            or not row.state_schema_version
            or config_hash is None
            or before_hash is None
            or after_hash is None
        ):
            blockers.add("FACT_HISTORY_INCOMPLETE")
        source_support = get_study_algorithm_support(
            str(row.algorithm_key or ""), str(row.algorithm_version or "")
        )
        if (
            source_support is None
            or not source_support.history_read_allowed
            or source_support.identity.state_schema_version
            != str(row.state_schema_version or "")
        ):
            blockers.add("SOURCE_HISTORY_DECODER_UNAVAILABLE")
        if previous_after is not None and before_hash != previous_after:
            blockers.add("STATE_HASH_CHAIN_GAP")
        previous_after = after_hash
        frozen_facts.append(
            FrozenStudyHistoryFact(
                id=int(row.id),
                learner_user_id=int(row.learner_user_id),
                subject_id=int(row.subject_id) if row.subject_id is not None else None,
                subject_generation=(
                    int(row.subject_generation)
                    if row.subject_generation is not None else None
                ),
                contributor_id=(
                    int(row.contributor_id) if row.contributor_id is not None else None
                ),
                review_event_id=event_id,
                fact_identity_hash=identity_hash,
                history_schema_version=str(row.history_schema_version),
                storage_codec=str(row.storage_codec),
                occurred_at=row.occurred_at,
                ingested_at=row.ingested_at,
                created_at=row.created_at,
                logical_note_key=(
                    bytes(row.logical_note_key)
                    if row.logical_note_key is not None else None
                ),
                logical_card_key=bytes(row.logical_card_key),
                source_operation_key=(
                    bytes(row.source_operation_key)
                    if row.source_operation_key is not None else None
                ),
                provenance_code=str(row.provenance_code),
                action_key=row.action_key,
                action_version=row.action_version,
                review_kind=row.review_kind,
                history_completeness_code=str(row.history_completeness_code),
                gap_reason_code=row.gap_reason_code,
                algorithm_key=row.algorithm_key,
                algorithm_version=row.algorithm_version,
                state_schema_version=row.state_schema_version,
                scheduler_config_hash=config_hash,
                before_state_hash=before_hash,
                after_state_hash=after_hash,
                payload_bytes=document.encoded,
                payload_hash=payload_hash,
            )
        )

    if set(fact_event_ids) != review_event_ids or len(fact_event_ids) != len(review_event_ids):
        blockers.add("REVIEW_EVENT_COVERAGE_UNPROVEN")
    if frozen_facts:
        if previous_after != verified.semantic_state_hash:
            blockers.add("STATE_HASH_CHAIN_GAP")
    elif verified.authority_revision != 0 or review_event_ids:
        blockers.add("STATE_HASH_CHAIN_GAP")
    current_state_document = None
    if locked.state is not None:
        current_state_document = state_document(locked.state.state_payload)
        state = STATE_DECODERS.decode(
            algorithm_key=str(locked.state.algorithm_key),
            algorithm_version=str(locked.state.algorithm_version),
            state_schema_version=str(locked.state.state_schema_version),
            storage_codec=str(locked.state.storage_codec),
            payload=locked.state.state_payload,
            expected_size=int(locked.state.state_payload_size),
            expected_hash=bytes(locked.state.algorithm_state_hash),
        )
        if int(state.reps or 0) != len(frozen_facts):
            blockers.add("STATE_REVIEW_COUNT_UNPROVEN")
        if frozen_facts and state.lastReviewAt != frozen_facts[-1].occurred_at:
            blockers.add("STATE_LAST_REVIEW_UNPROVEN")
        if not frozen_facts and state.lastReviewAt is not None:
            blockers.add("STATE_LAST_REVIEW_UNPROVEN")

    digest = hashlib.sha256()
    # The subject row binds token and state too (ADR P10 §2.4).
    subject_row = _freeze_row(subject, field_name="StudyProgressSubject")
    _append_cut_material(
        digest,
        {
            "schema_version": _CUT_SCHEMA,
            "learner_user_id": str(verified.learner_user_id),
            "enrollment_epoch": str(verified.enrollment_epoch),
            "subject_id": str(subject_id),
            "subject_generation": str(generation),
            "authority_revision": str(verified.authority_revision),
            "semantic_state_hash": (
                verified.semantic_state_hash.hex()
                if verified.semantic_state_hash is not None else None
            ),
            "logical_note_key": bytes(subject.logical_note_key).hex(),
            "current_algorithm_key": (
                str(locked.state.algorithm_key) if locked.state else None
            ),
            "current_algorithm_version": (
                str(locked.state.algorithm_version) if locked.state else None
            ),
            "current_state_schema_version": (
                str(locked.state.state_schema_version) if locked.state else None
            ),
            "current_storage_codec": (
                str(locked.state.storage_codec) if locked.state else None
            ),
            "current_algorithm_state_hash": (
                bytes(locked.state.algorithm_state_hash).hex()
                if locked.state else None
            ),
            "current_state_payload_hash": (
                current_state_document.digest.hex()
                if current_state_document is not None else None
            ),
            "subject_row_hash": subject_row.digest.hex(),
            "token_row_hash": None,
            "state_row_hash": None,
            "blocker_codes": sorted(blockers),
        },
    )
    for fact in frozen_facts:
        _append_cut_material(
            digest,
            {
                "kind": "fact",
                "id": str(fact.id),
                "learner_user_id": str(fact.learner_user_id),
                "subject_id": str(fact.subject_id),
                "subject_generation": str(fact.subject_generation),
                "contributor_id": str(fact.contributor_id),
                "review_event_id": str(fact.review_event_id),
                "identity_hash": fact.fact_identity_hash.hex(),
                "history_schema_version": fact.history_schema_version,
                "storage_codec": fact.storage_codec,
                "payload_hash": fact.payload_hash.hex(),
                "occurred_at": fact.occurred_at.isoformat(),
                "ingested_at": fact.ingested_at.isoformat(),
                "created_at": fact.created_at.isoformat(),
                "logical_note_key": (
                    fact.logical_note_key.hex() if fact.logical_note_key else None
                ),
                "logical_card_key": fact.logical_card_key.hex(),
                "source_operation_key": (
                    fact.source_operation_key.hex()
                    if fact.source_operation_key else None
                ),
                "provenance": fact.provenance_code,
                "action_key": fact.action_key,
                "action_version": fact.action_version,
                "review_kind": fact.review_kind,
                "history_completeness": fact.history_completeness_code,
                "gap_reason": fact.gap_reason_code,
                "algorithm_key": fact.algorithm_key,
                "algorithm_version": fact.algorithm_version,
                "state_schema_version": fact.state_schema_version,
                "scheduler_config_hash": (
                    fact.scheduler_config_hash.hex()
                    if fact.scheduler_config_hash else None
                ),
                "before_hash": (
                    fact.before_state_hash.hex() if fact.before_state_hash else None
                ),
                "after_hash": (
                    fact.after_state_hash.hex() if fact.after_state_hash else None
                ),
            },
        )
    for event in frozen_events:
        _append_cut_material(
            digest,
            {
                "kind": "review_event",
                "id": str(event.id),
                "card_id": event.card_id,
                "reviewed_at": event.reviewed_at.isoformat(),
                "payload_hash": event.payload_hash.hex(),
                "row_hash": event.row_hash.hex(),
            },
        )
    for lifecycle_id in lifecycle_rows:
        _append_cut_material(digest, {"kind": "lifecycle", "id": str(lifecycle_id)})
    return FrozenStudyAlgorithmHistoryCut(
        schema_version=_CUT_SCHEMA,
        learner_user_id=verified.learner_user_id,
        enrollment_epoch=verified.enrollment_epoch,
        subject_id=subject_id,
        subject_generation=generation,
        authority_revision=verified.authority_revision,
        semantic_state_hash=verified.semantic_state_hash,
        current_algorithm_key=(
            str(locked.state.algorithm_key) if locked.state else None
        ),
        current_algorithm_version=(
            str(locked.state.algorithm_version) if locked.state else None
        ),
        current_state_schema_version=(
            str(locked.state.state_schema_version) if locked.state else None
        ),
        current_storage_codec=(
            str(locked.state.storage_codec) if locked.state else None
        ),
        current_state_payload_bytes=(
            current_state_document.encoded
            if current_state_document is not None else None
        ),
        current_state_payload_hash=(
            current_state_document.digest
            if current_state_document is not None else None
        ),
        current_algorithm_state_hash=(
            bytes(locked.state.algorithm_state_hash) if locked.state else None
        ),
        logical_note_key=bytes(subject.logical_note_key),
        facts=tuple(frozen_facts),
        review_events=tuple(frozen_events),
        blocker_codes=tuple(sorted(blockers)),
        cut_hash=digest.digest(),
    )
