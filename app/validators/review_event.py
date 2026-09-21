"""Bounded, versioned payload contracts for immutable ReviewEvent facts."""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Mapping


REVIEW_EVENT_PAYLOAD_SCHEMA = "review-event-payload.v1"
ANKI_REVLOG_FACT_SCHEMA = "anki-revlog.v1"
MAX_REVIEW_EVENT_PAYLOAD_BYTES = 8 * 1024
MAX_REVIEW_EVENT_PAYLOAD_DEPTH = 5
MAX_REVIEW_EVENT_PAYLOAD_NODES = 96
MAX_REVIEW_EVENT_STRING_LENGTH = 512

NATIVE_REVIEW_SOURCE_PATHS = frozenset(
    {
        "native.rest",
        "native.mcp",
        "native.session.commit",
        "native.session.worker",
    }
)

NATIVE_CLIENT_PAYLOAD_FIELDS = frozenset(
    {
        "rating",
        "scope",
        "scope_id",
        "timezone",
        "duration_ms",
        "render_contract",
        "review_state_version",
        "selection_id",
        "install_id",
    }
)

SESSION_EVENT_FIELDS = frozenset(
    {
        "event_id",
        "sequence",
        "card_id",
        "rating",
        "action_key",
        "action_contract_version",
        "trigger_key",
        "trigger_contract_version",
        "algorithm_key",
        "algorithm_version",
        "config_schema_version",
        "config_hash",
        "study_session_id",
        "policy_key",
        "scheduler_offset_ms",
        "duration_ms",
        "before_state_hash",
        "after_state_hash",
        "authority_mode",
        "enrollment_epoch",
        "logical_note_key",
        "subject_generation",
        "base_authority_revision",
        "base_authority_state_hash",
        "operation_key",
    }
)

_PERSISTED_CLIENT_CONTEXT_FIELDS = frozenset(
    {
        "scope",
        "scope_id",
        "render_contract",
        "review_state_version",
        "selection_id",
        "install_id",
    }
)

_RUNTIME_FIELDS = frozenset(
    {
        "action_key",
        "action_contract_version",
        "trigger_key",
        "trigger_contract_version",
        "algorithm_key",
        "algorithm_version",
        "state_schema_version",
        "scheduler_config_hash",
    }
)


class ReviewEventPayloadError(ValueError):
    """Typed validation failure safe for REST, MCP and import adapters."""

    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 422,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.code = str(code)
        self.status = int(status)
        self.field = field


@dataclass(frozen=True)
class ReviewEventPayloadDisposition:
    category: str
    reason: str


def _payload_error(
    code: str,
    message: str,
    *,
    status: int = 422,
    field: str | None = None,
) -> ReviewEventPayloadError:
    return ReviewEventPayloadError(code, message, status=status, field=field)


def _validate_json_value(
    value: Any,
    *,
    path: str,
    depth: int,
    counter: list[int],
) -> None:
    counter[0] += 1
    if counter[0] > MAX_REVIEW_EVENT_PAYLOAD_NODES:
        raise _payload_error(
            "REVIEW_EVENT_PAYLOAD_TOO_COMPLEX",
            f"{path} contains too many values.",
            status=413,
            field=path,
        )
    if depth > MAX_REVIEW_EVENT_PAYLOAD_DEPTH:
        raise _payload_error(
            "REVIEW_EVENT_PAYLOAD_TOO_DEEP",
            f"{path} exceeds the supported nesting depth.",
            status=413,
            field=path,
        )
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, str):
        if len(value) > MAX_REVIEW_EVENT_STRING_LENGTH:
            raise _payload_error(
                "REVIEW_EVENT_PAYLOAD_STRING_TOO_LONG",
                f"{path} is too long.",
                status=413,
                field=path,
            )
        return
    if isinstance(value, int):
        if value < -(2**63) or value > 2**63 - 1:
            raise _payload_error(
                "REVIEW_EVENT_PAYLOAD_NUMBER_OUT_OF_RANGE",
                f"{path} is outside the supported integer range.",
                field=path,
            )
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise _payload_error(
                "REVIEW_EVENT_PAYLOAD_NUMBER_INVALID",
                f"{path} must be finite.",
                field=path,
            )
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(
                item,
                path=f"{path}[{index}]",
                depth=depth + 1,
                counter=counter,
            )
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str) or not key or len(key) > 64:
                raise _payload_error(
                    "REVIEW_EVENT_PAYLOAD_KEY_INVALID",
                    f"{path} contains an invalid object key.",
                    field=path,
                )
            _validate_json_value(
                item,
                path=f"{path}.{key}",
                depth=depth + 1,
                counter=counter,
            )
        return
    raise _payload_error(
        "REVIEW_EVENT_PAYLOAD_TYPE_INVALID",
        f"{path} contains a value that is not valid JSON.",
        field=path,
    )


def _canonical_json(payload: Mapping[str, Any]) -> str:
    material = dict(payload)
    _validate_json_value(material, path="payload", depth=0, counter=[0])
    try:
        encoded = json.dumps(
            material,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )
    except (TypeError, ValueError) as exc:
        raise _payload_error(
            "REVIEW_EVENT_PAYLOAD_INVALID",
            "Review event payload is not valid JSON.",
        ) from exc
    if len(encoded.encode("utf-8")) > MAX_REVIEW_EVENT_PAYLOAD_BYTES:
        raise _payload_error(
            "REVIEW_EVENT_PAYLOAD_TOO_LARGE",
            f"Review event payload exceeds {MAX_REVIEW_EVENT_PAYLOAD_BYTES} bytes.",
            status=413,
        )
    return encoded


def _validate_allowlist(
    payload: Mapping[str, Any],
    *,
    allowed_fields: frozenset[str],
    field_prefix: str,
) -> None:
    unexpected = sorted(set(payload) - allowed_fields)
    if unexpected:
        field = unexpected[0]
        raise _payload_error(
            "REVIEW_EVENT_PAYLOAD_FIELD_NOT_ALLOWED",
            f"{field_prefix} field '{field}' is not allowed.",
            field=field,
        )


def validate_review_duration(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise _payload_error(
            "INVALID_REVIEW_DURATION",
            "duration_ms must be an integer.",
            field="duration_ms",
        )
    if value < 0 or value > 3_600_000:
        raise _payload_error(
            "INVALID_REVIEW_DURATION",
            "duration_ms must be between 0 and 3600000.",
            field="duration_ms",
        )
    return value


def validate_native_client_payload(
    payload: Any,
    *,
    source_path: str,
) -> dict[str, Any]:
    if source_path not in NATIVE_REVIEW_SOURCE_PATHS:
        raise _payload_error(
            "INVALID_REVIEW_PROVENANCE",
            "Native review source path is not supported.",
            field="source_path",
        )
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise _payload_error(
            "INVALID_REVIEW_EVENT_PAYLOAD",
            "Review payload must be an object.",
        )
    _validate_json_value(payload, path="payload", depth=0, counter=[0])
    _validate_allowlist(
        payload,
        allowed_fields=NATIVE_CLIENT_PAYLOAD_FIELDS,
        field_prefix="Review payload",
    )
    validate_review_duration(payload.get("duration_ms"))
    for field in (
        "scope",
        "timezone",
        "render_contract",
        "review_state_version",
        "selection_id",
        "install_id",
    ):
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise _payload_error(
                "INVALID_REVIEW_EVENT_PAYLOAD",
                f"{field} must be a string.",
                field=field,
            )
    scope_id = payload.get("scope_id")
    if scope_id is not None and (
        isinstance(scope_id, bool) or not isinstance(scope_id, (str, int))
    ):
        raise _payload_error(
            "INVALID_REVIEW_EVENT_PAYLOAD",
            "scope_id must be a string or integer.",
            field="scope_id",
        )
    return dict(payload)


def validate_session_event_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise _payload_error(
            "INVALID_REVIEW_EVENT_PAYLOAD",
            "Session review event must be an object.",
        )
    _validate_json_value(payload, path="event", depth=0, counter=[0])
    _validate_allowlist(
        payload,
        allowed_fields=SESSION_EVENT_FIELDS,
        field_prefix="Session event",
    )
    validate_review_duration(payload.get("duration_ms"))
    for field in (
        "event_id",
        "card_id",
        "rating",
        "action_key",
        "action_contract_version",
        "trigger_key",
        "trigger_contract_version",
        "algorithm_key",
        "algorithm_version",
        "config_schema_version",
        "config_hash",
        "study_session_id",
        "policy_key",
        "before_state_hash",
        "after_state_hash",
    ):
        value = payload.get(field)
        if value is not None and not isinstance(value, str):
            raise _payload_error(
                "INVALID_REVIEW_EVENT_PAYLOAD",
                f"{field} must be a string.",
                field=field,
            )
    for field in ("sequence", "scheduler_offset_ms"):
        value = payload.get(field)
        if isinstance(value, bool) or not isinstance(value, int):
            raise _payload_error(
                "INVALID_REVIEW_EVENT_PAYLOAD",
                f"{field} must be an integer.",
                field=field,
            )
    return dict(payload)


def build_native_review_event_payload(
    *,
    source_path: str,
    runtime: Mapping[str, Any],
    scheduler_config_hash: str,
    client_payload: Any = None,
    study_session_id: str | None = None,
    client_event_id: str | None = None,
    sequence_no: int | None = None,
    request_id: str | None = None,
    wire_schema_version: str | None = None,
) -> str:
    normalized_client = validate_native_client_payload(
        client_payload,
        source_path=source_path,
    )
    runtime_payload = dict(runtime)
    runtime_payload.setdefault(
        "action_contract_version",
        runtime_payload.get("trigger_contract_version"),
    )
    runtime_payload["scheduler_config_hash"] = str(scheduler_config_hash or "")
    missing_runtime = sorted(_RUNTIME_FIELDS - set(runtime_payload))
    if missing_runtime or any(
        not isinstance(runtime_payload.get(field), str)
        or not str(runtime_payload.get(field)).strip()
        for field in _RUNTIME_FIELDS
    ):
        raise _payload_error(
            "INVALID_REVIEW_RUNTIME_PROVENANCE",
            "Native review runtime provenance is incomplete.",
        )

    provenance: dict[str, Any] = {
        "kind": "native",
        "source_path": source_path,
    }
    optional_strings = {
        "study_session_id": study_session_id,
        "client_event_id": client_event_id,
        "request_id": request_id,
        "wire_schema_version": wire_schema_version,
    }
    for field, value in optional_strings.items():
        if value is None:
            continue
        if not isinstance(value, str) or not value.strip() or len(value) > 128:
            raise _payload_error(
                "INVALID_REVIEW_PROVENANCE",
                f"{field} is invalid.",
                field=field,
            )
        provenance[field] = value.strip()
    if sequence_no is not None:
        if isinstance(sequence_no, bool) or not isinstance(sequence_no, int):
            raise _payload_error(
                "INVALID_REVIEW_PROVENANCE",
                "sequence_no must be an integer.",
                field="sequence_no",
            )
        if sequence_no < 1 or sequence_no > 5_000:
            raise _payload_error(
                "INVALID_REVIEW_PROVENANCE",
                "sequence_no is outside the supported range.",
                field="sequence_no",
            )
        provenance["sequence_no"] = sequence_no

    session_source = source_path in {
        "native.session.commit",
        "native.session.worker",
    }
    if session_source and (
        study_session_id is None
        or client_event_id is None
        or sequence_no is None
        or request_id is None
        or wire_schema_version is None
    ):
        raise _payload_error(
            "INVALID_REVIEW_PROVENANCE",
            "Session review provenance is incomplete.",
        )
    if not session_source and (study_session_id is not None or sequence_no is not None):
        raise _payload_error(
            "INVALID_REVIEW_PROVENANCE",
            "Non-session review provenance cannot claim session identity.",
        )
    if source_path == "native.mcp" and client_event_id is None:
        raise _payload_error(
            "INVALID_REVIEW_PROVENANCE",
            "MCP review provenance requires client_event_id.",
            field="client_event_id",
        )

    envelope: dict[str, Any] = {
        "schema_version": REVIEW_EVENT_PAYLOAD_SCHEMA,
        "provenance": provenance,
        "_study_runtime": runtime_payload,
    }
    context = {
        key: normalized_client[key]
        for key in sorted(_PERSISTED_CLIENT_CONTEXT_FIELDS)
        if key in normalized_client and normalized_client[key] is not None
    }
    if context:
        envelope["client_context"] = context

    # Compatibility keys remain reader-friendly, but their values are built
    # from trusted adapter input instead of copied from the caller payload.
    if source_path == "native.mcp":
        envelope["source"] = "mcp"
        if client_event_id is not None:
            envelope["client_event_id"] = client_event_id
    return _canonical_json(envelope)


def build_anki_revlog_review_event_payload(
    *,
    source_key: str,
    import_session_id: str,
    external_review_id: str,
    external_card_id: str,
    record: Mapping[str, Any],
) -> str:
    expected_record_fields = frozenset(
        {
            "sourceReviewId",
            "sourceCardId",
            "ease",
            "type",
            "ivl",
            "lastIvl",
            "factor",
            "time",
        }
    )
    _validate_allowlist(
        record,
        allowed_fields=expected_record_fields,
        field_prefix="Anki revlog",
    )
    for field, value, maximum in (
        ("source_key", source_key, 255),
        ("import_session_id", import_session_id, 36),
        ("external_review_id", external_review_id, 128),
        ("external_card_id", external_card_id, 128),
    ):
        if not isinstance(value, str) or not value.strip() or len(value) > maximum:
            raise _payload_error(
                "INVALID_EXTERNAL_REVIEW_PROVENANCE",
                f"{field} is invalid.",
                field=field,
            )
    return _canonical_json(
        {
            "schema_version": REVIEW_EVENT_PAYLOAD_SCHEMA,
            "provenance": {
                "kind": "external",
                "source_path": "external.anki.revlog",
                "source_key": source_key,
                "import_session_id": import_session_id,
                "external_review_id": external_review_id,
                "external_card_id": external_card_id,
            },
            "external_fact": {
                "schema_version": ANKI_REVLOG_FACT_SCHEMA,
                "record": dict(record),
            },
        }
    )


def classify_review_event_payload(
    payload_json: Any,
    *,
    scheduler_algorithm: str | None = None,
    algorithm_version: str | None = None,
    scheduler_config_hash: str | None = None,
    study_session_id: str | None = None,
    client_event_id: str | None = None,
    sequence_no: int | None = None,
) -> ReviewEventPayloadDisposition:
    """Classify canonical and legacy rows without inventing missing facts."""

    try:
        payload = json.loads(payload_json or "{}")
    except (TypeError, ValueError):
        return ReviewEventPayloadDisposition("legacy_unknown", "payload_not_json")
    if not isinstance(payload, dict):
        return ReviewEventPayloadDisposition("legacy_unknown", "payload_not_object")
    if payload.get("schema_version") != REVIEW_EVENT_PAYLOAD_SCHEMA:
        return ReviewEventPayloadDisposition("legacy_unknown", "unversioned_payload")
    provenance = payload.get("provenance")
    if not isinstance(provenance, dict):
        return ReviewEventPayloadDisposition(
            "missing_expected_field",
            "missing_provenance",
        )
    kind = provenance.get("kind")
    source_path = provenance.get("source_path")
    if kind == "native":
        if source_path not in NATIVE_REVIEW_SOURCE_PATHS:
            return ReviewEventPayloadDisposition("conflicting", "invalid_native_source")
        runtime = payload.get("_study_runtime")
        if not isinstance(runtime, dict):
            return ReviewEventPayloadDisposition(
                "missing_expected_field",
                "missing_native_runtime",
            )
        missing = sorted(_RUNTIME_FIELDS - set(runtime))
        if missing:
            return ReviewEventPayloadDisposition(
                "missing_expected_field",
                f"missing_runtime_{missing[0]}",
            )
        expected_pairs = (
            ("algorithm_key", scheduler_algorithm),
            ("algorithm_version", algorithm_version),
            ("scheduler_config_hash", scheduler_config_hash),
        )
        if any(
            expected is not None and runtime.get(field) != expected
            for field, expected in expected_pairs
        ):
            return ReviewEventPayloadDisposition(
                "conflicting",
                "runtime_column_mismatch",
            )
        action_key = str(runtime.get("action_key") or "")
        trigger_key = str(runtime.get("trigger_key") or "")
        if not action_key.startswith("review.") or trigger_key != (
            f"scheduler.{action_key}"
        ):
            return ReviewEventPayloadDisposition(
                "conflicting",
                "action_trigger_mismatch",
            )
        session_source = source_path in {
            "native.session.commit",
            "native.session.worker",
        }
        if session_source:
            if not provenance.get("request_id") or not provenance.get(
                "wire_schema_version"
            ):
                return ReviewEventPayloadDisposition(
                    "missing_expected_field",
                    "missing_session_request_identity",
                )
            session_pairs = (
                ("study_session_id", study_session_id),
                ("client_event_id", client_event_id),
                ("sequence_no", sequence_no),
            )
            if any(expected is None for _field, expected in session_pairs):
                return ReviewEventPayloadDisposition(
                    "missing_expected_field",
                    "missing_session_column",
                )
            if any(
                provenance.get(field) != expected
                for field, expected in session_pairs
            ):
                return ReviewEventPayloadDisposition(
                    "conflicting",
                    "session_column_mismatch",
                )
        elif study_session_id is not None or sequence_no is not None:
            return ReviewEventPayloadDisposition(
                "conflicting",
                "non_session_source_has_session_columns",
            )
        if source_path == "native.mcp" and (
            not client_event_id
            or provenance.get("client_event_id") != client_event_id
        ):
            return ReviewEventPayloadDisposition(
                "missing_expected_field" if not client_event_id else "conflicting",
                "missing_or_conflicting_mcp_event_identity",
            )
        return ReviewEventPayloadDisposition("complete", "canonical_native")
    if kind == "external":
        if source_path != "external.anki.revlog":
            return ReviewEventPayloadDisposition("conflicting", "invalid_external_source")
        required = {
            "source_key",
            "import_session_id",
            "external_review_id",
            "external_card_id",
        }
        if any(not provenance.get(field) for field in required):
            return ReviewEventPayloadDisposition(
                "missing_expected_field",
                "missing_external_identity",
            )
        external_fact = payload.get("external_fact")
        if (
            not isinstance(external_fact, dict)
            or external_fact.get("schema_version") != ANKI_REVLOG_FACT_SCHEMA
            or not isinstance(external_fact.get("record"), dict)
        ):
            return ReviewEventPayloadDisposition(
                "missing_expected_field",
                "missing_external_fact",
            )
        record = external_fact["record"]
        if (
            str(record.get("sourceReviewId") or "")
            != str(provenance.get("external_review_id") or "")
            or str(record.get("sourceCardId") or "")
            != str(provenance.get("external_card_id") or "")
        ):
            return ReviewEventPayloadDisposition(
                "conflicting",
                "external_fact_identity_mismatch",
            )
        if "_study_runtime" in payload:
            return ReviewEventPayloadDisposition(
                "conflicting",
                "external_event_has_native_runtime",
            )
        if scheduler_algorithm not in {None, "anki"} or algorithm_version not in {
            None,
            "revlog-v1",
        }:
            return ReviewEventPayloadDisposition(
                "conflicting",
                "external_algorithm_mismatch",
            )
        return ReviewEventPayloadDisposition("complete", "canonical_external")
    return ReviewEventPayloadDisposition("conflicting", "invalid_provenance_kind")
