"""Strict CardProgress compatibility mapper and availability evaluator.

This is pure mapping code.  It performs no SQL, owns no transaction and is not
wired into any production read or write path in P4-06.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

from app.services.anki_scheduler import _day_index
from app.services.stats_overview import normalize_timezone_name
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    CONTRIBUTOR_STATUSES,
    HISTORY_COMPLETENESS_CODES,
    MAPPER_VERSION,
    POINTER_STATUSES,
    PROJECTION_VERSION,
    PROVENANCE_CODES,
    RAW_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    CanonicalDocument,
    StudyProgressCodecError,
    algorithm_state_hash,
    canonical_document,
    decode_float,
    encode_datetime,
    encode_float,
    encode_integer,
    serialize_raw_card_progress,
    state_document,
)


@dataclass(frozen=True)
class AvailabilityProjection:
    projection_version: str
    normalized_queue: str
    due_at: datetime | None
    due_day: int | None
    is_suspended: bool
    is_buried: bool
    buried_until_day: int | None
    card_created_at: datetime
    card_order_key: bytes
    state_schema_version: str
    semantic_state_hash: bytes


@dataclass(frozen=True)
class MappedCardProgress:
    code: str
    mapper_version: str
    raw_schema_version: str
    storage_codec: str
    raw: CanonicalDocument
    state: CanonicalDocument
    algorithm_key: str
    algorithm_version: str
    state_schema_version: str
    algorithm_state_hash: bytes
    semantic_state_hash: bytes
    availability: AvailabilityProjection


@dataclass(frozen=True)
class ContributorEvidence:
    subject_generation: int
    source_progress_id: int
    live_card_progress_id: int
    logical_card_key: bytes
    live_card_id: str
    card_progress_revision: int
    raw_schema_version: str
    storage_codec: str
    raw: CanonicalDocument
    pointer_status: str
    history_completeness_code: str
    current_provenance_code: str
    lineage_vector_hash: bytes
    contributor_status: str


@dataclass(frozen=True)
class MappingFailure:
    code: str
    message: str
    raw: CanonicalDocument | None = None


@dataclass(frozen=True)
class AvailabilityContext:
    now_utc: datetime
    timezone_name: str
    day_boundary_hour_local: int
    learn_ahead_seconds: int
    effective_card_keys: tuple[bytes, ...]
    comparison_policy_version: str


@dataclass(frozen=True)
class AvailabilityDecision:
    today_day_index: int
    is_visible: bool
    is_due: bool
    is_learn_ahead: bool


def encode_identity(value: Any, *, max_bytes: int, field_name: str) -> bytes:
    if not isinstance(value, str) or not value:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be a non-empty string."
        )
    encoded = value.encode("utf-8")
    if len(encoded) > max_bytes:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} exceeds {max_bytes} UTF-8 bytes."
        )
    return encoded


def _required_nonnegative_integer(progress: Any, field_name: str) -> int:
    value = getattr(progress, field_name)
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be a non-negative integer."
        )
    return value


def _optional_nonnegative_integer(progress: Any, field_name: str) -> int | None:
    value = getattr(progress, field_name)
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be null or non-negative."
        )
    return value


def _required_positive_integer(progress: Any, field_name: str) -> int:
    value = _required_nonnegative_integer(progress, field_name)
    if value == 0:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be positive."
        )
    return value


def _bounded_text(
    value: Any,
    *,
    field_name: str,
    max_characters: int,
    nullable: bool = False,
) -> str | None:
    if value is None and nullable:
        return None
    if not isinstance(value, str) or not value or len(value) > max_characters:
        null_suffix = " or null" if nullable else ""
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE",
            f"{field_name} must be a non-empty string up to {max_characters} "
            f"characters{null_suffix}.",
        )
    return value


def _finite_float(
    value: Any, *, field_name: str, positive: bool = False, nonnegative: bool = False
) -> float:
    token = encode_float(value, field_name=field_name, normalize_zero=True)
    number = decode_float(token, field_name=field_name)
    if positive and number <= 0:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be positive."
        )
    if nonnegative and number < 0:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be non-negative."
        )
    return number


def map_card_progress(
    progress: Any,
    *,
    card_created_at: datetime,
    card_order_key: str | None = None,
) -> MappedCardProgress | MappingFailure:
    raw: CanonicalDocument | None = None
    try:
        raw = serialize_raw_card_progress(progress)
        _required_positive_integer(progress, "id")
        _required_positive_integer(progress, "user_id")
        _required_nonnegative_integer(progress, "revision")
        last_review_event_id = getattr(progress, "last_review_event_id")
        if last_review_event_id is not None:
            if (
                isinstance(last_review_event_id, bool)
                or not isinstance(last_review_event_id, int)
                or last_review_event_id <= 0
            ):
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE",
                    "last_review_event_id must be null or a positive integer.",
                )
        raw_queue = getattr(progress, "queue")
        if not isinstance(raw_queue, str):
            raise StudyProgressCodecError(
                "UNSUPPORTED_QUEUE", "Progress queue must be a string."
            )
        normalized_queue = "learning" if raw_queue == "learn" else raw_queue
        if normalized_queue not in {"new", "learning", "relearning", "review"}:
            raise StudyProgressCodecError(
                "UNSUPPORTED_QUEUE", f"Unsupported progress queue {raw_queue!r}."
            )

        step_index = _required_nonnegative_integer(progress, "step_index")
        due_day = _optional_nonnegative_integer(progress, "due_day")
        buried_until_day = _optional_nonnegative_integer(progress, "buried_until_day")
        reps = _required_nonnegative_integer(progress, "reps")
        lapses = _required_nonnegative_integer(progress, "lapses")
        last_leech_lapses = _required_nonnegative_integer(progress, "last_leech_lapses")

        interval_source = (
            getattr(progress, "interval_days_raw")
            if getattr(progress, "interval_days_raw") is not None
            else getattr(progress, "interval_days")
        )
        interval_days = _finite_float(
            interval_source, field_name="interval_days", nonnegative=True
        )
        ease = _finite_float(
            getattr(progress, "ease_factor"), field_name="ease_factor", positive=True
        )

        memory_stability = getattr(progress, "memory_stability")
        memory_difficulty = getattr(progress, "memory_difficulty")
        if (memory_stability is None) != (memory_difficulty is None):
            raise StudyProgressCodecError(
                "INCOMPLETE_MEMORY_STATE",
                "memory_stability and memory_difficulty must both be null or present.",
            )
        memory_payload = None
        if memory_stability is not None:
            memory_payload = {
                "difficulty": encode_float(
                    _finite_float(memory_difficulty, field_name="memory_difficulty"),
                    field_name="memory_difficulty",
                    normalize_zero=True,
                ),
                "stability": encode_float(
                    _finite_float(memory_stability, field_name="memory_stability"),
                    field_name="memory_stability",
                    normalize_zero=True,
                ),
            }

        due_at = getattr(progress, "due_at")
        last_reviewed_at = getattr(progress, "last_reviewed_at")
        for field_name, value in (
            ("due_at", due_at),
            ("last_reviewed_at", last_reviewed_at),
        ):
            if value is not None and not isinstance(value, datetime):
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE", f"{field_name} must be a datetime or null."
                )

        review_kind = _bounded_text(
            getattr(progress, "review_kind"),
            field_name="review_kind",
            max_characters=20,
        )
        scheduler_mode = _bounded_text(
            getattr(progress, "scheduler_mode"),
            field_name="scheduler_mode",
            max_characters=20,
        )
        suspension_reason = _bounded_text(
            getattr(progress, "suspension_reason"),
            field_name="suspension_reason",
            max_characters=32,
            nullable=True,
        )
        is_suspended = getattr(progress, "is_suspended")
        is_buried = getattr(progress, "is_buried")
        if not isinstance(is_suspended, bool) or not isinstance(is_buried, bool):
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE", "Suspension and burial flags must be booleans."
            )

        state_payload = {
            "due_at": (
                encode_datetime(due_at, field_name="due_at") if due_at is not None else None
            ),
            "due_day": (
                encode_integer(due_day, field_name="due_day")
                if due_day is not None
                else None
            ),
            "ease": encode_float(ease, field_name="ease", normalize_zero=True),
            "interval_days": encode_float(
                interval_days, field_name="interval_days", normalize_zero=True
            ),
            "lapses": encode_integer(lapses, field_name="lapses"),
            "last_review_at": (
                encode_datetime(last_reviewed_at, field_name="last_review_at")
                if last_reviewed_at is not None
                else None
            ),
            "leeched": bool(last_leech_lapses and lapses >= last_leech_lapses),
            "memory_state": memory_payload,
            "reps": encode_integer(reps, field_name="reps"),
            "review_kind": review_kind,
            "scheduler_mode": scheduler_mode,
            "step_index": encode_integer(step_index, field_name="step_index"),
            "suspended": is_suspended,
            "suspension_reason": suspension_reason,
            "type": normalized_queue,
        }
        state = state_document(state_payload)
        algorithm_hash = algorithm_state_hash(state.payload)

        progress_card_key = getattr(progress, "card_id")
        if progress_card_key is None:
            raise StudyProgressCodecError(
                "MISSING_CARD_IDENTITY", "A mapped contributor requires a Card identity."
            )
        if card_order_key is not None and card_order_key != progress_card_key:
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE",
                "Resolved Card identity does not match CardProgress.card_id.",
            )
        resolved_card_key = progress_card_key
        encoded_card_key = encode_identity(
            resolved_card_key, max_bytes=144, field_name="card_order_key"
        )
        if not isinstance(card_created_at, datetime):
            raise StudyProgressCodecError(
                "MISSING_CARD_CREATED_AT", "A mapped contributor requires Card.created_at."
            )

        semantic_anchors = {
            "algorithm_state_hash": algorithm_hash.hex(),
            "buried_until_day": (
                encode_integer(buried_until_day, field_name="buried_until_day")
                if buried_until_day is not None
                else None
            ),
            "due_at": (
                encode_datetime(due_at, field_name="due_at") if due_at is not None else None
            ),
            "due_day": (
                encode_integer(due_day, field_name="due_day")
                if due_day is not None
                else None
            ),
            "is_buried": is_buried,
            "is_suspended": is_suspended,
            "normalized_queue": normalized_queue,
        }
        semantic_hash = canonical_document(
            semantic_anchors, too_large_code="STATE_PAYLOAD_TOO_LARGE"
        ).digest
        availability = AvailabilityProjection(
            projection_version=PROJECTION_VERSION,
            normalized_queue=normalized_queue,
            due_at=due_at,
            due_day=due_day,
            is_suspended=is_suspended,
            is_buried=is_buried,
            buried_until_day=buried_until_day,
            card_created_at=card_created_at,
            card_order_key=encoded_card_key,
            state_schema_version=STATE_SCHEMA_VERSION,
            semantic_state_hash=semantic_hash,
        )
        return MappedCardProgress(
            code="STATE_MAPPED",
            mapper_version=MAPPER_VERSION,
            raw_schema_version=RAW_SCHEMA_VERSION,
            storage_codec=STORAGE_CODEC,
            raw=raw,
            state=state,
            algorithm_key=ALGORITHM_KEY,
            algorithm_version=ALGORITHM_VERSION,
            state_schema_version=STATE_SCHEMA_VERSION,
            algorithm_state_hash=algorithm_hash,
            semantic_state_hash=semantic_hash,
            availability=availability,
        )
    except StudyProgressCodecError as exc:
        return MappingFailure(code=exc.code, message=str(exc), raw=raw)


def build_contributor_evidence(
    mapped: MappedCardProgress,
    progress: Any,
    *,
    subject_generation: int,
    pointer_status: str,
    history_completeness_code: str,
    current_provenance_code: str,
    lineage_vector_hash: bytes,
    contributor_status: str = "ACTIVE",
) -> ContributorEvidence:
    """Validate identity/provenance material kept outside Algorithm State."""

    if not isinstance(subject_generation, int) or subject_generation < 1:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "subject_generation must be positive."
        )
    code_checks = (
        (pointer_status, POINTER_STATUSES, "pointer_status"),
        (
            history_completeness_code,
            HISTORY_COMPLETENESS_CODES,
            "history_completeness_code",
        ),
        (current_provenance_code, PROVENANCE_CODES, "current_provenance_code"),
        (contributor_status, CONTRIBUTOR_STATUSES, "contributor_status"),
    )
    for value, allowed, field_name in code_checks:
        if value not in allowed:
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE", f"{field_name} is not an accepted code."
            )
    if not isinstance(lineage_vector_hash, bytes) or len(lineage_vector_hash) != 32:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "lineage_vector_hash must contain 32 bytes."
        )

    progress_id = _required_positive_integer(progress, "id")
    revision = _required_nonnegative_integer(progress, "revision")
    card_id = getattr(progress, "card_id")
    if card_id is None:
        raise StudyProgressCodecError(
            "MISSING_CARD_IDENTITY", "Contributor evidence requires a Card identity."
        )
    logical_card_key = encode_identity(
        card_id, max_bytes=144, field_name="logical_card_key"
    )
    if mapped.raw.digest != serialize_raw_card_progress(progress).digest:
        raise StudyProgressCodecError(
            "STATE_HASH_MISMATCH", "Mapped raw evidence no longer matches authority."
        )
    return ContributorEvidence(
        subject_generation=subject_generation,
        source_progress_id=progress_id,
        live_card_progress_id=progress_id,
        logical_card_key=logical_card_key,
        live_card_id=card_id,
        card_progress_revision=revision,
        raw_schema_version=RAW_SCHEMA_VERSION,
        storage_codec=STORAGE_CODEC,
        raw=mapped.raw,
        pointer_status=pointer_status,
        history_completeness_code=history_completeness_code,
        current_provenance_code=current_provenance_code,
        lineage_vector_hash=lineage_vector_hash,
        contributor_status=contributor_status,
    )


def _normalize_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value
    return value.astimezone(timezone.utc).replace(tzinfo=None)


def evaluate_availability(
    projection: AvailabilityProjection, context: AvailabilityContext
) -> AvailabilityDecision:
    if not isinstance(context.now_utc, datetime):
        raise StudyProgressCodecError(
            "INVALID_AVAILABILITY_CONTEXT", "now_utc must be a datetime."
        )
    normalized_timezone = normalize_timezone_name(context.timezone_name)
    if normalized_timezone is None:
        raise StudyProgressCodecError(
            "INVALID_AVAILABILITY_CONTEXT", "timezone_name is unavailable."
        )
    if not 0 <= context.day_boundary_hour_local <= 23:
        raise StudyProgressCodecError(
            "INVALID_AVAILABILITY_CONTEXT", "day boundary must be between 0 and 23."
        )
    if context.learn_ahead_seconds < 0 or not context.comparison_policy_version:
        raise StudyProgressCodecError(
            "INVALID_AVAILABILITY_CONTEXT", "comparison policy inputs are invalid."
        )
    if (
        not isinstance(context.effective_card_keys, tuple)
        or any(
            not isinstance(key, bytes) or not key or len(key) > 144
            for key in context.effective_card_keys
        )
        or len(set(context.effective_card_keys)) != len(context.effective_card_keys)
    ):
        raise StudyProgressCodecError(
            "INVALID_AVAILABILITY_CONTEXT", "effective_card_keys is invalid."
        )

    now = _normalize_utc(context.now_utc)
    today = _day_index(
        now,
        context.day_boundary_hour_local,
        timezone_name=normalized_timezone,
    )
    buried = projection.is_buried and (
        projection.buried_until_day is None
        or projection.buried_until_day >= today
    )
    visible = (
        projection.card_order_key in context.effective_card_keys
        and not projection.is_suspended
        and not buried
    )
    if not visible:
        return AvailabilityDecision(today, False, False, False)

    queue = projection.normalized_queue
    due_at = _normalize_utc(projection.due_at) if projection.due_at else None
    due = False
    learn_ahead = False
    if queue == "new":
        due = True
    elif queue in {"learning", "relearning"}:
        if projection.due_day is not None:
            due = projection.due_day <= today
        else:
            due = due_at is None or due_at <= now
            learn_ahead = (
                not due
                and due_at is not None
                and due_at <= now + timedelta(seconds=context.learn_ahead_seconds)
            )
    elif queue == "review":
        due = (
            projection.due_day <= today
            if projection.due_day is not None
            else due_at is None or due_at <= now
        )
    else:
        raise StudyProgressCodecError(
            "UNSUPPORTED_QUEUE", f"Unsupported projected queue {queue!r}."
        )
    return AvailabilityDecision(today, True, due, learn_ahead)
