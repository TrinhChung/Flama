"""Pure, lossless P5-03 encoder from Note authority to legacy Card rows.

This module owns no SQL and is intentionally absent from product routing.  It
requires a verified raw baseline for every existing sibling Card because the
Algorithm State alone cannot reconstruct Card-specific compatibility fields.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import struct
from types import MappingProxyType
from typing import Any, Mapping, Sequence

from app.services.study_authority_projection_comparator import (
    ProjectionCandidate,
    ProjectionComparison,
    ProjectionComparisonError,
    compare_note_legacy_projection,
)
from app.services.study_progress_contract import RAW_SCHEMA_VERSION, STORAGE_CODEC
from app.services.study_note_storage_precision import (
    StudyStoragePrecisionError,
    legacy_float_round_trip,
)
from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    CanonicalDocument,
    StudyProgressCodecError,
    algorithm_state_hash,
    decode_raw_card_progress,
    serialize_raw_card_progress,
    state_document,
)
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress


class LegacyProjectionEncodingError(ValueError):
    """Typed, fail-closed validation failure for a proposed projection."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


APPLY_NOTE_STATE = "APPLY_NOTE_STATE"
PRESERVE_MATCHING_STATE = "PRESERVE_MATCHING_STATE"
_SIBLING_DISPOSITIONS = frozenset({APPLY_NOTE_STATE, PRESERVE_MATCHING_STATE})
_MYSQL_SIGNED_INT_MAX = (1 << 31) - 1
_MYSQL_SIGNED_BIGINT_MAX = (1 << 63) - 1


@dataclass(frozen=True)
class LegacySiblingBaseline:
    """Exact locked baseline and Card-specific metadata for one sibling."""

    card_id: str
    expected_base_revision: int
    card_created_at: datetime
    raw_payload: Mapping[str, Any]
    raw_payload_size: int
    raw_payload_hash: bytes
    projected_last_review_event_id: int | None
    disposition_code: str = APPLY_NOTE_STATE
    raw_schema_version: str = RAW_SCHEMA_VERSION
    storage_codec: str = STORAGE_CODEC


@dataclass(frozen=True)
class LegacyProjectionMetadata:
    """Compatibility values deliberately omitted from Algorithm State."""

    interval_days_rounded: int
    is_buried: bool
    buried_until_day: int | None
    last_leech_at: datetime | None
    last_leech_lapses: int
    projected_at: datetime


@dataclass(frozen=True)
class ProjectedCardProgress:
    """Read-only attribute view shaped like ``CardProgress`` for persistence."""

    _values: Mapping[str, Any]

    @classmethod
    def from_values(cls, values: Mapping[str, Any]) -> "ProjectedCardProgress":
        return cls(MappingProxyType(dict(values)))

    def __getattr__(self, name: str) -> Any:
        try:
            return self._values[name]
        except KeyError as exc:
            raise AttributeError(name) from exc

    def as_dict(self) -> dict[str, Any]:
        return dict(self._values)


@dataclass(frozen=True)
class EncodedLegacySibling:
    card_id: str
    expected_base_revision: int
    baseline_raw_size: int
    baseline_raw_hash: bytes
    progress: ProjectedCardProgress
    card_created_at: datetime
    raw: CanonicalDocument


@dataclass(frozen=True)
class EncodedLegacyProjection:
    siblings: tuple[EncodedLegacySibling, ...]
    comparison: ProjectionComparison

    @property
    def raw_digest_by_card(self) -> dict[str, bytes]:
        return {sibling.card_id: sibling.raw.digest for sibling in self.siblings}


def _fail(code: str, message: str) -> LegacyProjectionEncodingError:
    return LegacyProjectionEncodingError(code, message)


def _nonnegative_integer(
    value: Any,
    *,
    field_name: str,
    maximum: int = _MYSQL_SIGNED_INT_MAX,
) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 0
        or value > maximum
    ):
        raise _fail(
            "INVALID_PROJECTION_METADATA",
            f"{field_name} must fit a non-negative legacy integer.",
        )
    return value


def _positive_integer_or_none(value: Any, *, field_name: str) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise _fail(
            "INVALID_PROJECTION_METADATA",
            f"{field_name} must be null or a positive integer.",
        )
    if value > _MYSQL_SIGNED_INT_MAX:
        raise _fail(
            "INVALID_PROJECTION_METADATA",
            f"{field_name} must fit a positive legacy integer.",
        )
    return value


def _naive_datetime_or_none(value: Any, *, field_name: str) -> datetime | None:
    if value is None:
        return None
    if not isinstance(value, datetime) or value.tzinfo is not None:
        raise _fail(
            "INVALID_PROJECTION_METADATA",
            f"{field_name} must be a naive UTC datetime or null.",
        )
    if value.microsecond != 0:
        raise _fail(
            "UNPROJECTABLE_LEGACY_TIMESTAMP",
            f"{field_name} exceeds legacy MySQL DATETIME(0) precision.",
        )
    if value.year < 1000:
        raise _fail(
            "UNPROJECTABLE_LEGACY_TIMESTAMP",
            f"{field_name} is outside the legacy MySQL DATETIME range.",
        )
    return value


def _require_exact_legacy_float(value: float, *, field_name: str) -> None:
    """Reject f64 state that cannot survive the legacy MySQL FLOAT columns."""

    try:
        stored = legacy_float_round_trip(value)
    except StudyStoragePrecisionError as exc:
        raise _fail(
            "UNPROJECTABLE_LEGACY_FLOAT",
            f"{field_name} exceeds legacy MySQL FLOAT range.",
        ) from exc
    if struct.pack(">d", stored) != struct.pack(">d", value):
        raise _fail(
            "UNPROJECTABLE_LEGACY_FLOAT",
            f"{field_name} cannot round-trip exactly through legacy MySQL FLOAT.",
        )


def _validate_metadata(metadata: LegacyProjectionMetadata) -> None:
    if not isinstance(metadata, LegacyProjectionMetadata):
        raise _fail(
            "INVALID_PROJECTION_METADATA",
            "Projection metadata must use the registered contract.",
        )
    _nonnegative_integer(
        metadata.interval_days_rounded, field_name="interval_days_rounded"
    )
    if not isinstance(metadata.is_buried, bool):
        raise _fail(
            "INVALID_PROJECTION_METADATA", "is_buried must be a boolean."
        )
    if metadata.buried_until_day is not None:
        _nonnegative_integer(
            metadata.buried_until_day, field_name="buried_until_day"
        )
    _naive_datetime_or_none(metadata.last_leech_at, field_name="last_leech_at")
    _nonnegative_integer(
        metadata.last_leech_lapses, field_name="last_leech_lapses"
    )
    if (
        not isinstance(metadata.projected_at, datetime)
        or metadata.projected_at.tzinfo is not None
    ):
        raise _fail(
            "INVALID_PROJECTION_METADATA",
            "projected_at must be a naive UTC datetime.",
        )
    _naive_datetime_or_none(metadata.projected_at, field_name="projected_at")


def _decode_state(
    *,
    algorithm_key: str,
    algorithm_version: str,
    state_schema_version: str,
    storage_codec: str,
    state_payload: Mapping[str, Any],
    expected_state_payload_size: int,
    expected_algorithm_state_hash: bytes,
):
    if (
        isinstance(expected_state_payload_size, bool)
        or not isinstance(expected_state_payload_size, int)
        or expected_state_payload_size < 0
    ):
        raise _fail("INVALID_EXPECTATION", "State payload size is invalid.")
    if not isinstance(expected_algorithm_state_hash, bytes) or len(
        expected_algorithm_state_hash
    ) != 32:
        raise _fail("INVALID_EXPECTATION", "Algorithm hash must contain 32 bytes.")
    try:
        document = state_document(state_payload)
        if document.size != expected_state_payload_size:
            raise StudyProgressCodecError(
                "STATE_HASH_MISMATCH", "Stored Algorithm State size does not match."
            )
        identity = (algorithm_key, algorithm_version, state_schema_version, storage_codec)
        # An unknown identity is reported as such before its hash is checked.
        if not STATE_DECODERS.has_decoder(identity):
            raise StudyProgressCodecError(
                "STATE_DECODER_UNAVAILABLE", f"No decoder is registered for {identity!r}."
            )
        if algorithm_state_hash(
            document.payload,
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
            state_schema_version=state_schema_version,
            storage_codec=storage_codec,
        ) != expected_algorithm_state_hash:
            raise StudyProgressCodecError(
                "STATE_HASH_MISMATCH", "Stored Algorithm State hash does not match."
            )
        state = STATE_DECODERS.decode(
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
            state_schema_version=state_schema_version,
            storage_codec=storage_codec,
            payload=document.payload,
            expected_size=expected_state_payload_size,
            expected_hash=expected_algorithm_state_hash,
        )
    except StudyProgressCodecError as exc:
        raise _fail(exc.code, str(exc)) from exc
    _require_exact_legacy_float(state.intervalDays, field_name="interval_days")
    _require_exact_legacy_float(state.ease, field_name="ease")
    if state.memoryState is not None:
        _require_exact_legacy_float(
            state.memoryState.stability, field_name="memory_state.stability"
        )
        _require_exact_legacy_float(
            state.memoryState.difficulty, field_name="memory_state.difficulty"
        )
    _naive_datetime_or_none(state.due, field_name="due_at")
    _naive_datetime_or_none(state.lastReviewAt, field_name="last_review_at")
    for field_name, value in (
        ("step_index", state.stepIndex),
        ("due_day", state.dueDay),
        ("reps", state.reps),
        ("lapses", state.lapses),
    ):
        if value is not None:
            _nonnegative_integer(value, field_name=field_name)
    return document, state


def _decode_baseline(
    baseline: LegacySiblingBaseline, *, expected_learner_user_id: int
) -> dict[str, Any]:
    if not isinstance(baseline.card_id, str) or not baseline.card_id:
        raise _fail("INVALID_CARD_IDENTITY", "Baseline Card ID is missing.")
    expected_revision = _nonnegative_integer(
        baseline.expected_base_revision,
        field_name="expected_base_revision",
        maximum=_MYSQL_SIGNED_BIGINT_MAX - 1,
    )
    if (
        not isinstance(baseline.card_created_at, datetime)
        or baseline.card_created_at.tzinfo is not None
    ):
        raise _fail(
            "INVALID_PROJECTION_METADATA",
            "card_created_at must be a naive UTC datetime.",
        )
    _positive_integer_or_none(
        baseline.projected_last_review_event_id,
        field_name="projected_last_review_event_id",
    )
    if (
        isinstance(baseline.raw_payload_size, bool)
        or not isinstance(baseline.raw_payload_size, int)
        or baseline.raw_payload_size < 0
    ):
        raise _fail("INVALID_EXPECTATION", "Raw baseline size is invalid.")
    if not isinstance(baseline.raw_payload_hash, bytes) or len(
        baseline.raw_payload_hash
    ) != 32:
        raise _fail("INVALID_EXPECTATION", "Raw baseline hash must contain 32 bytes.")
    if baseline.disposition_code not in _SIBLING_DISPOSITIONS:
        raise _fail(
            "INVALID_SIBLING_DISPOSITION",
            f"Unknown sibling disposition {baseline.disposition_code!r}.",
        )
    try:
        values = decode_raw_card_progress(
            baseline.raw_payload,
            schema_version=baseline.raw_schema_version,
            storage_codec=baseline.storage_codec,
            expected_size=baseline.raw_payload_size,
            expected_hash=baseline.raw_payload_hash,
        )
    except StudyProgressCodecError as exc:
        code = (
            "BASELINE_HASH_MISMATCH"
            if exc.code == "STATE_HASH_MISMATCH"
            else exc.code
        )
        raise _fail(code, str(exc)) from exc
    if values["card_id"] != baseline.card_id:
        raise _fail(
            "INVALID_CARD_IDENTITY",
            f"Raw baseline does not belong to Card {baseline.card_id}.",
        )
    if values["user_id"] != expected_learner_user_id:
        raise _fail(
            "WRONG_LEARNER", f"Card {baseline.card_id} belongs to another learner."
        )
    if values["revision"] != expected_revision:
        raise _fail(
            "STALE_BASELINE",
            f"Card {baseline.card_id} baseline revision is stale.",
        )
    return values


def encode_note_state_to_legacy_cards(
    *,
    expected_learner_user_id: int,
    algorithm_key: str,
    algorithm_version: str,
    state_schema_version: str,
    storage_codec: str,
    state_payload: Mapping[str, Any],
    expected_state_payload_size: int,
    expected_algorithm_state_hash: bytes,
    metadata: LegacyProjectionMetadata,
    siblings: Sequence[LegacySiblingBaseline],
) -> EncodedLegacyProjection:
    """Encode and self-verify one Note state across all existing sibling Cards.

    The caller must supply the complete active sibling set resolved under the
    learner fence.  Every baseline is hash-verified and revision-checked before
    a candidate is built.  This function performs no writes.
    """

    if (
        isinstance(expected_learner_user_id, bool)
        or not isinstance(expected_learner_user_id, int)
        or expected_learner_user_id <= 0
    ):
        raise _fail("INVALID_EXPECTATION", "Expected learner ID must be positive.")
    if not siblings:
        raise _fail("MISSING_SIBLING", "At least one sibling baseline is required.")
    _validate_metadata(metadata)
    state_document_value, state = _decode_state(
        algorithm_key=algorithm_key,
        algorithm_version=algorithm_version,
        state_schema_version=state_schema_version,
        storage_codec=storage_codec,
        state_payload=state_payload,
        expected_state_payload_size=expected_state_payload_size,
        expected_algorithm_state_hash=expected_algorithm_state_hash,
    )

    encoded: list[EncodedLegacySibling] = []
    expected_raw: dict[str, bytes] = {}
    semantic_state_hash: bytes | None = None
    for baseline in siblings:
        if baseline.card_id in expected_raw:
            raise _fail(
                "DUPLICATE_SIBLING", f"Duplicate Card baseline: {baseline.card_id}."
            )
        values = _decode_baseline(
            baseline, expected_learner_user_id=expected_learner_user_id
        )
        if baseline.disposition_code == APPLY_NOTE_STATE:
            memory = state.memoryState
            values.update(
                {
                    "queue": state.type,
                    "step_index": state.stepIndex,
                    "due_at": state.due,
                    "due_day": state.dueDay,
                    "interval_days": metadata.interval_days_rounded,
                    "interval_days_raw": state.intervalDays,
                    "is_suspended": state.suspended,
                    "is_buried": metadata.is_buried,
                    "buried_until_day": metadata.buried_until_day,
                    "review_kind": state.reviewKind,
                    "scheduler_mode": state.schedulerMode,
                    "ease_factor": state.ease,
                    "memory_stability": (
                        memory.stability if memory is not None else None
                    ),
                    "memory_difficulty": (
                        memory.difficulty if memory is not None else None
                    ),
                    "suspension_reason": state.suspensionReason,
                    "last_leech_at": metadata.last_leech_at,
                    "last_leech_lapses": metadata.last_leech_lapses,
                    "last_review_event_id": baseline.projected_last_review_event_id,
                    "reps": state.reps,
                    "lapses": state.lapses,
                    "last_reviewed_at": state.lastReviewAt,
                    "revision": baseline.expected_base_revision + 1,
                    "updated_at": metadata.projected_at,
                }
            )
        elif baseline.projected_last_review_event_id != values["last_review_event_id"]:
            raise _fail(
                "PRESERVED_METADATA_MISMATCH",
                f"Card {baseline.card_id} preserve disposition changed its event pointer.",
            )
        progress = ProjectedCardProgress.from_values(values)
        try:
            raw = serialize_raw_card_progress(progress)
            mapped = map_card_progress(
                progress,
                card_created_at=baseline.card_created_at,
                card_order_key=baseline.card_id,
            )
        except StudyProgressCodecError as exc:
            raise _fail(exc.code, str(exc)) from exc
        if not isinstance(mapped, MappedCardProgress):
            raise _fail(
                mapped.code,
                f"Card {baseline.card_id} cannot be projected: {mapped.message}",
            )
        if mapped.state.digest != state_document_value.digest:
            raise _fail(
                "UNPROJECTABLE_STATE",
                f"Metadata cannot reproduce Algorithm State for Card {baseline.card_id}.",
            )
        if semantic_state_hash is None:
            semantic_state_hash = mapped.semantic_state_hash
        elif mapped.semantic_state_hash != semantic_state_hash:
            raise _fail(
                "SEMANTIC_MISMATCH",
                "Sibling projection does not share one semantic Note state.",
            )
        expected_raw[baseline.card_id] = raw.digest
        encoded.append(
            EncodedLegacySibling(
                card_id=baseline.card_id,
                expected_base_revision=baseline.expected_base_revision,
                baseline_raw_size=baseline.raw_payload_size,
                baseline_raw_hash=baseline.raw_payload_hash,
                progress=progress,
                card_created_at=baseline.card_created_at,
                raw=raw,
            )
        )

    if semantic_state_hash is None:  # pragma: no cover - guarded by siblings
        raise _fail("MISSING_SIBLING", "At least one sibling baseline is required.")
    try:
        comparison = compare_note_legacy_projection(
            expected_learner_user_id=expected_learner_user_id,
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
            state_schema_version=state_schema_version,
            storage_codec=storage_codec,
            state_payload=state_document_value.payload,
            expected_state_payload_size=expected_state_payload_size,
            expected_algorithm_state_hash=expected_algorithm_state_hash,
            expected_semantic_state_hash=semantic_state_hash,
            expected_raw_digest_by_card=expected_raw,
            candidates=tuple(
                ProjectionCandidate(
                    progress=sibling.progress,
                    card_created_at=sibling.card_created_at,
                )
                for sibling in encoded
            ),
        )
    except ProjectionComparisonError as exc:
        raise _fail(exc.code, str(exc)) from exc
    return EncodedLegacyProjection(siblings=tuple(encoded), comparison=comparison)
