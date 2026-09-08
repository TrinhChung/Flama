"""Strict, versioned Study Session wire contracts.

Snapshot, commit, and batch envelopes evolve independently.  Callers select
the decoder from the server-pinned ``StudySession.wire_schema_version``; this
module never guesses a newer contract from fields supplied by the client.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from app.services.study_action_runtime import (
    REVIEW_ACTION_CONTRACT_VERSION,
    ReviewActionContract,
    StudyActionValidationError,
    StudyTriggerValidationError,
    resolve_review_action,
    verify_review_trigger,
)


SESSION_SCHEMA_V2 = "study-session.v2"
SESSION_SCHEMA_V3 = "study-session.v3"
COMMIT_SCHEMA_V1 = "study-commit.v1"
COMMIT_SCHEMA_V2 = "study-commit.v2"
BATCH_SCHEMA_V1 = "study-batch.v1"
BATCH_SCHEMA_V2 = "study-batch.v2"

SUPPORTED_SESSION_SCHEMAS = (SESSION_SCHEMA_V2, SESSION_SCHEMA_V3)


class StudyWireContractError(ValueError):
    """Fail-closed error raised before a wire event reaches mutation code."""

    def __init__(self, code: str, message: str, *, status: int = 422) -> None:
        super().__init__(message)
        self.code = code
        self.status = status


@dataclass(frozen=True)
class StudyWireEnvelopeContract:
    session_schema: str
    commit_schema: str
    batch_schema: str
    requires_semantic_identity: bool


_ENVELOPE_CONTRACTS = {
    SESSION_SCHEMA_V2: StudyWireEnvelopeContract(
        session_schema=SESSION_SCHEMA_V2,
        commit_schema=COMMIT_SCHEMA_V1,
        batch_schema=BATCH_SCHEMA_V1,
        requires_semantic_identity=False,
    ),
    SESSION_SCHEMA_V3: StudyWireEnvelopeContract(
        session_schema=SESSION_SCHEMA_V3,
        commit_schema=COMMIT_SCHEMA_V2,
        batch_schema=BATCH_SCHEMA_V2,
        requires_semantic_identity=True,
    ),
}


def resolve_wire_envelope_contract(
    session_schema: Any,
) -> StudyWireEnvelopeContract:
    normalized = str(session_schema or "").strip()
    contract = _ENVELOPE_CONTRACTS.get(normalized)
    if contract is None:
        raise StudyWireContractError(
            "UNSUPPORTED_SESSION_SCHEMA",
            f"Study Session schema '{normalized or '<missing>'}' is unsupported.",
            status=409,
        )
    return contract


def select_session_schema(
    accepted_versions: Any,
    *,
    v3_enabled: bool,
) -> str:
    """Negotiate a new snapshot without breaking clients that only know v2."""

    if not isinstance(accepted_versions, list):
        return SESSION_SCHEMA_V2
    for raw_version in accepted_versions:
        if not isinstance(raw_version, str):
            continue
        version = raw_version.strip()
        if version == SESSION_SCHEMA_V3 and v3_enabled:
            return SESSION_SCHEMA_V3
        if version == SESSION_SCHEMA_V2:
            return SESSION_SCHEMA_V2
    raise StudyWireContractError(
        "UNSUPPORTED_SESSION_SCHEMA",
        "Client and server do not share a supported Study Session schema.",
    )


def validate_envelope_schema(
    payload_schema: Any,
    *,
    session_schema: str,
    envelope_kind: str,
) -> StudyWireEnvelopeContract:
    """Require the envelope paired with the server-pinned session decoder."""

    contract = resolve_wire_envelope_contract(session_schema)
    expected = {
        "commit": contract.commit_schema,
        "batch": contract.batch_schema,
    }.get(str(envelope_kind or "").strip())
    if expected is None:
        raise ValueError("envelope_kind must be commit or batch")
    supplied = str(payload_schema or "").strip()
    if supplied != expected:
        raise StudyWireContractError(
            f"UNSUPPORTED_{envelope_kind.upper()}_SCHEMA",
            (
                f"{envelope_kind} schema '{supplied or '<missing>'}' does not "
                f"match pinned session schema {session_schema}; expected {expected}."
            ),
        )
    return contract


_V2_SEMANTIC_FIELDS = (
    "action_key",
    "trigger_key",
    "trigger_contract_version",
)
_V3_REQUIRED_FIELDS = (
    "action_key",
    "action_contract_version",
    "trigger_key",
    "trigger_contract_version",
    "algorithm_key",
    "algorithm_version",
    "config_schema_version",
    "config_hash",
    "study_session_id",
)
_V3_ONLY_FIELDS = tuple(
    field for field in _V3_REQUIRED_FIELDS if field not in _V2_SEMANTIC_FIELDS
)


def _required_string(
    raw_event: Mapping[str, Any],
    field: str,
    *,
    event_index: int,
) -> str:
    value = raw_event.get(field)
    if not isinstance(value, str) or not value.strip():
        raise StudyWireContractError(
            "WIRE_CONTRACT_MISMATCH",
            f"Event {event_index} requires non-empty {field}.",
        )
    return value.strip()


def _resolve_action(raw_event: Mapping[str, Any], event_index: int) -> ReviewActionContract:
    rating = raw_event.get("rating")
    if not isinstance(rating, str):
        raise StudyWireContractError(
            "INVALID_RATING",
            f"Event {event_index} has an invalid rating.",
        )
    try:
        return resolve_review_action(rating)
    except StudyActionValidationError as exc:
        raise StudyWireContractError(
            "INVALID_RATING",
            f"Event {event_index} has an invalid rating.",
        ) from exc


def validate_review_event_wire_contract(
    raw_event: Mapping[str, Any],
    *,
    session_schema: str,
    session_id: str,
    algorithm_key: str,
    algorithm_version: str,
    policy: Mapping[str, Any],
    event_index: int,
) -> ReviewActionContract:
    """Validate one event against an explicitly selected v2 or v3 decoder."""

    contract = resolve_wire_envelope_contract(session_schema)
    action = _resolve_action(raw_event, event_index)

    if not contract.requires_semantic_identity:
        present = [field for field in _V2_SEMANTIC_FIELDS if field in raw_event]
        if present and len(present) != len(_V2_SEMANTIC_FIELDS):
            raise StudyWireContractError(
                "ACTION_CONTRACT_MISMATCH",
                f"Event {event_index} has partial v2 semantic metadata.",
            )
        if any(field in raw_event for field in _V3_ONLY_FIELDS):
            raise StudyWireContractError(
                "WIRE_CONTRACT_MISMATCH",
                f"Event {event_index} mixes v3 identity fields into a v2 session.",
            )
        if not present:
            return action
    else:
        for field in _V3_REQUIRED_FIELDS:
            _required_string(raw_event, field, event_index=event_index)

    expected = {
        "action_key": action.action_key,
        "trigger_key": action.trigger_key,
        "trigger_contract_version": action.trigger_contract_version,
    }
    if contract.requires_semantic_identity:
        expected.update(
            {
                "action_contract_version": REVIEW_ACTION_CONTRACT_VERSION,
                "algorithm_key": str(algorithm_key),
                "algorithm_version": str(algorithm_version),
                "config_schema_version": str(policy.get("config_schema_version") or ""),
                "config_hash": str(policy.get("config_hash") or ""),
                "study_session_id": str(session_id),
            }
        )

    for field, expected_value in expected.items():
        supplied = raw_event.get(field)
        if not isinstance(supplied, str) or supplied.strip() != expected_value:
            raise StudyWireContractError(
                "ACTION_CONTRACT_MISMATCH"
                if field.startswith(("action_", "trigger_"))
                else "WIRE_CONTRACT_MISMATCH",
                f"Event {event_index} has inconsistent {field}.",
            )
    try:
        verify_review_trigger(
            action,
            trigger_key=str(raw_event.get("trigger_key") or ""),
            trigger_contract_version=str(
                raw_event.get("trigger_contract_version") or ""
            ),
        )
    except StudyTriggerValidationError as exc:
        raise StudyWireContractError(exc.code, str(exc)) from exc
    return action
