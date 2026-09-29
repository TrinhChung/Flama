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
SESSION_SCHEMA_V4 = "study-session.v4"
COMMIT_SCHEMA_V1 = "study-commit.v1"
COMMIT_SCHEMA_V2 = "study-commit.v2"
COMMIT_SCHEMA_V3 = "study-commit.v3"
BATCH_SCHEMA_V1 = "study-batch.v1"
BATCH_SCHEMA_V2 = "study-batch.v2"
BATCH_SCHEMA_V3 = "study-batch.v3"

SUPPORTED_SESSION_SCHEMAS = (
    SESSION_SCHEMA_V2,
    SESSION_SCHEMA_V3,
    SESSION_SCHEMA_V4,
)


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
    requires_note_authority_identity: bool


@dataclass(frozen=True)
class StudyNoteAuthorityWireIdentity:
    enrollment_epoch: str
    logical_note_key: str
    subject_generation: str
    base_authority_revision: str
    base_authority_state_hash: str

    def event_fields(self, *, operation_key: str) -> dict[str, str]:
        return {
            "authority_mode": "NOTE",
            "enrollment_epoch": self.enrollment_epoch,
            "logical_note_key": self.logical_note_key,
            "subject_generation": self.subject_generation,
            "base_authority_revision": self.base_authority_revision,
            "base_authority_state_hash": self.base_authority_state_hash,
            "operation_key": operation_key,
        }


_ENVELOPE_CONTRACTS = {
    SESSION_SCHEMA_V2: StudyWireEnvelopeContract(
        session_schema=SESSION_SCHEMA_V2,
        commit_schema=COMMIT_SCHEMA_V1,
        batch_schema=BATCH_SCHEMA_V1,
        requires_semantic_identity=False,
        requires_note_authority_identity=False,
    ),
    SESSION_SCHEMA_V3: StudyWireEnvelopeContract(
        session_schema=SESSION_SCHEMA_V3,
        commit_schema=COMMIT_SCHEMA_V2,
        batch_schema=BATCH_SCHEMA_V2,
        requires_semantic_identity=True,
        requires_note_authority_identity=False,
    ),
    SESSION_SCHEMA_V4: StudyWireEnvelopeContract(
        session_schema=SESSION_SCHEMA_V4,
        commit_schema=COMMIT_SCHEMA_V3,
        batch_schema=BATCH_SCHEMA_V3,
        requires_semantic_identity=True,
        requires_note_authority_identity=True,
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
    v4_enabled: bool = False,
) -> str:
    """Negotiate a new snapshot without breaking clients that only know v2."""

    if not isinstance(accepted_versions, list):
        return SESSION_SCHEMA_V2
    for raw_version in accepted_versions:
        if not isinstance(raw_version, str):
            continue
        version = raw_version.strip()
        if version == SESSION_SCHEMA_V4 and v4_enabled:
            return SESSION_SCHEMA_V4
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
_V4_AUTHORITY_FIELDS = (
    "authority_mode",
    "enrollment_epoch",
    "logical_note_key",
    "subject_generation",
    "base_authority_revision",
    "base_authority_state_hash",
    "operation_key",
)
_V4_REQUIRED_FIELDS = (*_V3_REQUIRED_FIELDS, *_V4_AUTHORITY_FIELDS)


def _canonical_decimal(value: Any, *, field: str, minimum: int) -> str:
    if isinstance(value, bool):
        raise StudyWireContractError(
            "WIRE_CONTRACT_MISMATCH",
            f"NOTE authority {field} must be a canonical decimal string.",
        )
    text = "" if value is None else str(value)
    if not text.isascii() or not text.isdecimal() or str(int(text)) != text:
        raise StudyWireContractError(
            "WIRE_CONTRACT_MISMATCH",
            f"NOTE authority {field} must be a canonical decimal string.",
        )
    if int(text) < minimum:
        raise StudyWireContractError(
            "WIRE_CONTRACT_MISMATCH",
            f"NOTE authority {field} is below its allowed minimum.",
        )
    return text


def build_note_authority_wire_identity(
    *,
    enrollment_epoch: Any,
    logical_note_key: Any,
    subject_generation: Any,
    base_authority_revision: Any,
    base_authority_state_hash: Any,
) -> StudyNoteAuthorityWireIdentity:
    if isinstance(logical_note_key, bytes):
        try:
            note_key = logical_note_key.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise StudyWireContractError(
                "WIRE_CONTRACT_MISMATCH",
                "NOTE authority logical_note_key must be canonical UTF-8.",
            ) from exc
    else:
        note_key = logical_note_key
    if (
        not isinstance(note_key, str)
        or not note_key
        or note_key != note_key.strip()
        or len(note_key.encode("utf-8")) > 144
    ):
        raise StudyWireContractError(
            "WIRE_CONTRACT_MISMATCH",
            "NOTE authority logical_note_key is invalid.",
        )
    if isinstance(base_authority_state_hash, bytes):
        state_hash = base_authority_state_hash.hex()
    else:
        state_hash = str(base_authority_state_hash or "")
    if (
        len(state_hash) != 64
        or state_hash.lower() != state_hash
        or any(char not in "0123456789abcdef" for char in state_hash)
    ):
        raise StudyWireContractError(
            "WIRE_CONTRACT_MISMATCH",
            "NOTE authority state hash must be 32-byte lowercase hex.",
        )
    return StudyNoteAuthorityWireIdentity(
        enrollment_epoch=_canonical_decimal(
            enrollment_epoch,
            field="enrollment_epoch",
            minimum=1,
        ),
        logical_note_key=note_key,
        subject_generation=_canonical_decimal(
            subject_generation,
            field="subject_generation",
            minimum=1,
        ),
        base_authority_revision=_canonical_decimal(
            base_authority_revision,
            field="base_authority_revision",
            minimum=0,
        ),
        base_authority_state_hash=state_hash,
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
    note_authority: StudyNoteAuthorityWireIdentity | None = None,
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
        if any(
            field in raw_event
            for field in (*_V3_ONLY_FIELDS, *_V4_AUTHORITY_FIELDS)
        ):
            raise StudyWireContractError(
                "WIRE_CONTRACT_MISMATCH",
                f"Event {event_index} mixes v3/v4 identity fields into a v2 session.",
            )
        if not present:
            return action
    else:
        required_fields = (
            _V4_REQUIRED_FIELDS
            if contract.requires_note_authority_identity
            else _V3_REQUIRED_FIELDS
        )
        for field in required_fields:
            _required_string(raw_event, field, event_index=event_index)
        if (
            not contract.requires_note_authority_identity
            and any(field in raw_event for field in _V4_AUTHORITY_FIELDS)
        ):
            raise StudyWireContractError(
                "WIRE_CONTRACT_MISMATCH",
                f"Event {event_index} mixes v4 authority fields into a v3 session.",
            )

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
    if contract.requires_note_authority_identity:
        if not isinstance(note_authority, StudyNoteAuthorityWireIdentity):
            raise StudyWireContractError(
                "WIRE_CONTRACT_MISMATCH",
                f"Event {event_index} has no server-pinned NOTE authority identity.",
            )
        operation_key = _required_string(
            raw_event,
            "event_id",
            event_index=event_index,
        )
        expected.update(note_authority.event_fields(operation_key=operation_key))

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
