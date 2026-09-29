"""Bounded canonical JSON codecs for Phase 4 shadow progress.

The codec is deliberately independent from Flask, SQLAlchemy sessions and the
scheduler clock.  It preserves values already read from authority; it never
fills missing due anchors or substitutes scheduler defaults.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import math
import struct
from typing import Any, Callable, Mapping

from app.services.anki_scheduler import CardState, FsrsMemoryState
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    MAX_CANONICAL_PAYLOAD_BYTES,
    RAW_SCHEMA_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)


RAW_CARD_PROGRESS_FIELDS = (
    "id",
    "user_id",
    "card_id",
    "queue",
    "step_index",
    "due_at",
    "due_day",
    "interval_days",
    "interval_days_raw",
    "is_suspended",
    "is_buried",
    "buried_until_day",
    "review_kind",
    "scheduler_mode",
    "ease_factor",
    "memory_stability",
    "memory_difficulty",
    "suspension_reason",
    "last_leech_at",
    "last_leech_lapses",
    "last_review_event_id",
    "reps",
    "lapses",
    "last_reviewed_at",
    "revision",
    "created_at",
    "updated_at",
)

_RAW_INTEGER_FIELDS = frozenset(
    {
        "id",
        "user_id",
        "step_index",
        "due_day",
        "interval_days",
        "buried_until_day",
        "last_leech_lapses",
        "last_review_event_id",
        "reps",
        "lapses",
        "revision",
    }
)
_RAW_FLOAT_FIELDS = frozenset(
    {
        "interval_days_raw",
        "ease_factor",
        "memory_stability",
        "memory_difficulty",
    }
)
_RAW_BOOLEAN_FIELDS = frozenset({"is_suspended", "is_buried"})
_RAW_DATETIME_FIELDS = frozenset(
    {"due_at", "last_leech_at", "last_reviewed_at", "created_at", "updated_at"}
)
_RAW_STRING_FIELDS = frozenset(
    {"card_id", "queue", "review_kind", "scheduler_mode", "suspension_reason"}
)
_RAW_NONNULL_FIELDS = frozenset(
    {
        "id",
        "user_id",
        "queue",
        "step_index",
        "interval_days",
        "is_suspended",
        "is_buried",
        "review_kind",
        "scheduler_mode",
        "ease_factor",
        "last_leech_lapses",
        "reps",
        "lapses",
        "revision",
        "created_at",
        "updated_at",
    }
)


class StudyProgressCodecError(ValueError):
    """Expected, typed source-data or payload validation failure."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class CanonicalDocument:
    payload: dict[str, Any]
    encoded: bytes
    size: int
    digest: bytes


def encode_integer(value: Any, *, field_name: str) -> str:
    if isinstance(value, bool) or not isinstance(value, int):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be an integer."
        )
    return str(value)


def decode_integer(value: Any, *, field_name: str) -> int:
    if not isinstance(value, str) or not value:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has no canonical integer token."
        )
    if value == "-0" or (value.startswith("0") and value != "0"):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has a non-canonical integer token."
        )
    if value.startswith("-0") or value.startswith("+"):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has a non-canonical integer token."
        )
    try:
        decoded = int(value, 10)
    except ValueError as exc:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has an invalid integer token."
        ) from exc
    if str(decoded) != value:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has a non-canonical integer token."
        )
    return decoded


def encode_float(
    value: Any, *, field_name: str, normalize_zero: bool = False
) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be a number."
        )
    number = float(value)
    if not math.isfinite(number):
        raise StudyProgressCodecError(
            "NON_FINITE_STATE_NUMBER", f"{field_name} must be finite."
        )
    if normalize_zero and number == 0.0:
        number = 0.0
    return "f64:" + struct.pack(">d", number).hex()


def decode_float(value: Any, *, field_name: str) -> float:
    if (
        not isinstance(value, str)
        or len(value) != 20
        or not value.startswith("f64:")
    ):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has no canonical float token."
        )
    try:
        raw = bytes.fromhex(value[4:])
        number = struct.unpack(">d", raw)[0]
    except (ValueError, struct.error) as exc:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has an invalid float token."
        ) from exc
    if not math.isfinite(number):
        raise StudyProgressCodecError(
            "NON_FINITE_STATE_NUMBER", f"{field_name} must be finite."
        )
    if encode_float(number, field_name=field_name) != value:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has a non-canonical float token."
        )
    return number


def encode_datetime(value: Any, *, field_name: str) -> str:
    if not isinstance(value, datetime):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} must be a datetime."
        )
    moment = value
    if moment.tzinfo is not None:
        moment = moment.astimezone(timezone.utc).replace(tzinfo=None)
    return moment.isoformat(timespec="microseconds") + "Z"


def decode_datetime(value: Any, *, field_name: str) -> datetime:
    if not isinstance(value, str) or len(value) != 27 or not value.endswith("Z"):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has no canonical UTC timestamp."
        )
    try:
        moment = datetime.fromisoformat(value[:-1])
    except ValueError as exc:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has an invalid UTC timestamp."
        ) from exc
    if moment.tzinfo is not None or encode_datetime(moment, field_name=field_name) != value:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", f"{field_name} has a non-canonical UTC timestamp."
        )
    return moment


def canonical_json_bytes(payload: Mapping[str, Any]) -> bytes:
    try:
        return json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "Payload is not canonical-JSON serializable."
        ) from exc


def canonical_document(
    payload: Mapping[str, Any], *, too_large_code: str
) -> CanonicalDocument:
    encoded = canonical_json_bytes(payload)
    if len(encoded) > MAX_CANONICAL_PAYLOAD_BYTES:
        raise StudyProgressCodecError(
            too_large_code,
            f"Canonical payload is {len(encoded)} bytes; maximum is "
            f"{MAX_CANONICAL_PAYLOAD_BYTES} bytes.",
        )
    return CanonicalDocument(
        payload=dict(payload),
        encoded=encoded,
        size=len(encoded),
        digest=hashlib.sha256(encoded).digest(),
    )


def _canonicalize_typed(value: Any, *, field_name: str) -> Any:
    if value is None or isinstance(value, (bool, str)):
        return value
    if isinstance(value, int):
        return encode_integer(value, field_name=field_name)
    if isinstance(value, float):
        return encode_float(value, field_name=field_name)
    if isinstance(value, datetime):
        return encode_datetime(value, field_name=field_name)
    if isinstance(value, Mapping):
        result: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE", "Canonical JSON object keys must be strings."
                )
            result[key] = _canonicalize_typed(
                child, field_name=f"{field_name}.{key}"
            )
        return result
    if isinstance(value, (list, tuple)):
        return [
            _canonicalize_typed(child, field_name=f"{field_name}[{index}]")
            for index, child in enumerate(value)
        ]
    raise StudyProgressCodecError(
        "INVALID_STATE_VALUE", f"{field_name} has an unsupported canonical type."
    )


def canonical_typed_document(
    payload: Mapping[str, Any], *, too_large_code: str
) -> CanonicalDocument:
    """Encode bounded fact/lifecycle evidence with the shared scalar rules."""

    canonical = _canonicalize_typed(payload, field_name="payload")
    if not isinstance(canonical, dict):  # pragma: no cover - Mapping guarantees it
        raise StudyProgressCodecError("INVALID_STATE_VALUE", "Payload must be an object.")
    return canonical_document(canonical, too_large_code=too_large_code)


def _nullable(value: Any, encoder: Callable[..., Any], *, field_name: str) -> Any:
    if value is None:
        return None
    return encoder(value, field_name=field_name)


def serialize_raw_card_progress(progress: Any) -> CanonicalDocument:
    payload: dict[str, Any] = {}
    for field_name in RAW_CARD_PROGRESS_FIELDS:
        if not hasattr(progress, field_name):
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE",
                f"CardProgress is missing classified field {field_name}.",
            )
        value = getattr(progress, field_name)
        if field_name in _RAW_INTEGER_FIELDS:
            payload[field_name] = _nullable(
                value, encode_integer, field_name=field_name
            )
        elif field_name in _RAW_FLOAT_FIELDS:
            payload[field_name] = _nullable(value, encode_float, field_name=field_name)
        elif field_name in _RAW_DATETIME_FIELDS:
            payload[field_name] = _nullable(
                value, encode_datetime, field_name=field_name
            )
        elif field_name in _RAW_BOOLEAN_FIELDS:
            if not isinstance(value, bool):
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE", f"{field_name} must be a boolean."
                )
            payload[field_name] = value
        elif field_name in _RAW_STRING_FIELDS:
            if value is not None and not isinstance(value, str):
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE", f"{field_name} must be a string or null."
                )
            payload[field_name] = value
        else:  # pragma: no cover - inventory tests make this impossible
            raise RuntimeError(f"Unclassified CardProgress field: {field_name}")
    return canonical_document(
        payload, too_large_code="RAW_PROGRESS_PAYLOAD_TOO_LARGE"
    )


def decode_raw_card_progress(
    payload: Mapping[str, Any],
    *,
    schema_version: str = RAW_SCHEMA_VERSION,
    storage_codec: str = STORAGE_CODEC,
    expected_size: int | None = None,
    expected_hash: bytes | None = None,
) -> dict[str, Any]:
    if schema_version != RAW_SCHEMA_VERSION or storage_codec != STORAGE_CODEC:
        raise StudyProgressCodecError(
            "UNSUPPORTED_STATE_SCHEMA", "Raw schema or storage codec is unavailable."
        )
    if set(payload) != set(RAW_CARD_PROGRESS_FIELDS):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "Raw CardProgress field inventory does not match."
        )
    document = canonical_document(
        payload, too_large_code="RAW_PROGRESS_PAYLOAD_TOO_LARGE"
    )
    _verify_document(document, expected_size=expected_size, expected_hash=expected_hash)
    decoded: dict[str, Any] = {}
    for field_name in RAW_CARD_PROGRESS_FIELDS:
        value = payload[field_name]
        if value is None:
            if field_name in _RAW_NONNULL_FIELDS:
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE", f"{field_name} must not be null."
                )
            decoded[field_name] = None
        elif field_name in _RAW_INTEGER_FIELDS:
            decoded[field_name] = decode_integer(value, field_name=field_name)
        elif field_name in _RAW_FLOAT_FIELDS:
            decoded[field_name] = decode_float(value, field_name=field_name)
        elif field_name in _RAW_DATETIME_FIELDS:
            decoded[field_name] = decode_datetime(value, field_name=field_name)
        elif field_name in _RAW_BOOLEAN_FIELDS:
            if not isinstance(value, bool):
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE", f"{field_name} must be a boolean."
                )
            decoded[field_name] = value
        else:
            if not isinstance(value, str):
                raise StudyProgressCodecError(
                    "INVALID_STATE_VALUE", f"{field_name} must be a string."
                )
            decoded[field_name] = value
    return decoded


def _verify_document(
    document: CanonicalDocument,
    *,
    expected_size: int | None,
    expected_hash: bytes | None,
) -> None:
    if expected_size is not None and document.size != expected_size:
        raise StudyProgressCodecError(
            "STATE_HASH_MISMATCH", "Canonical payload size does not match."
        )
    if expected_hash is not None and document.digest != expected_hash:
        raise StudyProgressCodecError(
            "STATE_HASH_MISMATCH", "Canonical payload digest does not match."
        )


def state_document(payload: Mapping[str, Any]) -> CanonicalDocument:
    return canonical_document(payload, too_large_code="STATE_PAYLOAD_TOO_LARGE")


def algorithm_state_hash(
    payload: Mapping[str, Any],
    *,
    algorithm_key: str = ALGORITHM_KEY,
    algorithm_version: str = ALGORITHM_VERSION,
    state_schema_version: str = STATE_SCHEMA_VERSION,
    storage_codec: str = STORAGE_CODEC,
) -> bytes:
    envelope = {
        "algorithm_key": algorithm_key,
        "algorithm_version": algorithm_version,
        "payload": dict(payload),
        "state_schema_version": state_schema_version,
        "storage_codec": storage_codec,
    }
    return canonical_document(
        envelope, too_large_code="STATE_PAYLOAD_TOO_LARGE"
    ).digest


def serialize_card_state(state: CardState) -> CanonicalDocument:
    """Encode one scheduler CardState with the registered legacy state codec."""

    if not isinstance(state, CardState):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "Algorithm State must be a CardState."
        )
    memory_payload = None
    if state.memoryState is not None:
        if not isinstance(state.memoryState, FsrsMemoryState):
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE", "memory_state must be an FsrsMemoryState."
            )
        memory_payload = {
            "difficulty": encode_float(
                state.memoryState.difficulty,
                field_name="memory_state.difficulty",
                normalize_zero=True,
            ),
            "stability": encode_float(
                state.memoryState.stability,
                field_name="memory_state.stability",
                normalize_zero=True,
            ),
        }
    document = state_document(
        {
            "due_at": (
                encode_datetime(state.due, field_name="due_at")
                if state.due is not None
                else None
            ),
            "due_day": (
                encode_integer(state.dueDay, field_name="due_day")
                if state.dueDay is not None
                else None
            ),
            "ease": encode_float(state.ease, field_name="ease", normalize_zero=True),
            "interval_days": encode_float(
                state.intervalDays,
                field_name="interval_days",
                normalize_zero=True,
            ),
            "lapses": encode_integer(state.lapses, field_name="lapses"),
            "last_review_at": (
                encode_datetime(state.lastReviewAt, field_name="last_review_at")
                if state.lastReviewAt is not None
                else None
            ),
            "leeched": state.leeched,
            "memory_state": memory_payload,
            "reps": encode_integer(state.reps, field_name="reps"),
            "review_kind": state.reviewKind,
            "scheduler_mode": state.schedulerMode,
            "step_index": encode_integer(state.stepIndex, field_name="step_index"),
            "suspended": state.suspended,
            "suspension_reason": state.suspensionReason,
            "type": state.type,
        }
    )
    # Decode before returning so type, bounds and field vocabulary are checked
    # by the same registered contract used for persisted authority state.
    _decode_legacy_anki_state(document.payload)
    return document


def _decode_legacy_anki_state(payload: Mapping[str, Any]) -> CardState:
    expected_fields = {
        "type",
        "step_index",
        "due_at",
        "due_day",
        "interval_days",
        "ease",
        "reps",
        "lapses",
        "last_review_at",
        "review_kind",
        "scheduler_mode",
        "suspended",
        "suspension_reason",
        "leeched",
        "memory_state",
    }
    if set(payload) != expected_fields:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "Algorithm State field inventory does not match."
        )
    queue = payload["type"]
    if queue not in {"new", "learning", "relearning", "review"}:
        raise StudyProgressCodecError("UNSUPPORTED_QUEUE", "Unsupported state queue.")
    for boolean_field in ("suspended", "leeched"):
        if not isinstance(payload[boolean_field], bool):
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE", f"{boolean_field} must be a boolean."
            )
    memory_payload = payload["memory_state"]
    memory = None
    if memory_payload is not None:
        if not isinstance(memory_payload, Mapping) or set(memory_payload) != {
            "stability",
            "difficulty",
        }:
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE", "memory_state is invalid."
            )
        memory = FsrsMemoryState(
            stability=decode_float(
                memory_payload["stability"], field_name="memory_state.stability"
            ),
            difficulty=decode_float(
                memory_payload["difficulty"], field_name="memory_state.difficulty"
            ),
        )
    suspension_reason = payload["suspension_reason"]
    if suspension_reason is not None and not isinstance(suspension_reason, str):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "suspension_reason must be a string or null."
        )
    for string_field in ("review_kind", "scheduler_mode"):
        if not isinstance(payload[string_field], str):
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE", f"{string_field} must be a string."
            )
    state = CardState(
        type=queue,
        stepIndex=decode_integer(payload["step_index"], field_name="step_index"),
        due=(
            decode_datetime(payload["due_at"], field_name="due_at")
            if payload["due_at"] is not None
            else None
        ),
        dueDay=(
            decode_integer(payload["due_day"], field_name="due_day")
            if payload["due_day"] is not None
            else None
        ),
        intervalDays=decode_float(payload["interval_days"], field_name="interval_days"),
        ease=decode_float(payload["ease"], field_name="ease"),
        reps=decode_integer(payload["reps"], field_name="reps"),
        lapses=decode_integer(payload["lapses"], field_name="lapses"),
        lastReviewAt=(
            decode_datetime(payload["last_review_at"], field_name="last_review_at")
            if payload["last_review_at"] is not None
            else None
        ),
        reviewKind=payload["review_kind"],
        schedulerMode=payload["scheduler_mode"],
        suspended=payload["suspended"],
        suspensionReason=suspension_reason,
        leeched=payload["leeched"],
        memoryState=memory,
    )
    for field_name, value in (
        ("step_index", state.stepIndex),
        ("due_day", state.dueDay),
        ("interval_days", state.intervalDays),
        ("reps", state.reps),
        ("lapses", state.lapses),
    ):
        if value is not None and value < 0:
            raise StudyProgressCodecError(
                "INVALID_STATE_VALUE", f"{field_name} must be non-negative."
            )
    # 0 means "not assigned yet" (Anki factor 0), which the scheduler accepts.
    if state.ease < 0:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "ease must be non-negative."
        )
    return state


class StateDecoderRegistry:
    def __init__(self) -> None:
        self._decoders: dict[tuple[str, str, str, str], Callable[[Mapping[str, Any]], CardState]] = {}

    def register(
        self,
        identity: tuple[str, str, str, str],
        decoder: Callable[[Mapping[str, Any]], CardState],
    ) -> None:
        if identity in self._decoders:
            raise ValueError(f"State decoder {identity!r} is already registered.")
        self._decoders[identity] = decoder

    def has_decoder(
        self, identity: tuple[str, str, str, str]
    ) -> bool:
        """Check an exact persisted Algorithm/state/codec identity."""

        return identity in self._decoders

    def decode(
        self,
        *,
        algorithm_key: str,
        algorithm_version: str,
        state_schema_version: str,
        storage_codec: str,
        payload: Mapping[str, Any],
        expected_size: int | None = None,
        expected_hash: bytes | None = None,
    ) -> CardState:
        identity = (
            algorithm_key,
            algorithm_version,
            state_schema_version,
            storage_codec,
        )
        decoder = self._decoders.get(identity)
        if decoder is None:
            raise StudyProgressCodecError(
                "STATE_DECODER_UNAVAILABLE", f"No decoder is registered for {identity!r}."
            )
        document = state_document(payload)
        _verify_document(document, expected_size=expected_size, expected_hash=None)
        if expected_hash is not None and algorithm_state_hash(
            payload,
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
            state_schema_version=state_schema_version,
            storage_codec=storage_codec,
        ) != expected_hash:
            raise StudyProgressCodecError(
                "STATE_HASH_MISMATCH", "Algorithm State digest does not match."
            )
        return decoder(payload)


STATE_DECODERS = StateDecoderRegistry()
STATE_DECODERS.register(
    (ALGORITHM_KEY, ALGORITHM_VERSION, STATE_SCHEMA_VERSION, STORAGE_CODEC),
    _decode_legacy_anki_state,
)
