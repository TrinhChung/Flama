"""Versioned durable metadata stored in StudySession.config_snapshot_json."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any


SESSION_CONFIG_SNAPSHOT_SCHEMA = "study-session-config.v2"


class StudySessionConfigError(ValueError):
    pass


@dataclass(frozen=True)
class DecodedStudySessionConfig:
    policies: dict[str, Any]
    selected_composition_id: str | None
    selected_composition: dict[str, Any] | None
    composition_binding: dict[str, Any] | None
    legacy: bool


def encode_study_session_config(
    *,
    policies: dict[str, Any],
    selected_composition: dict[str, Any],
    composition_binding: dict[str, Any],
) -> str:
    composition_id = str(selected_composition.get("composition_id") or "").strip()
    if not composition_id:
        raise StudySessionConfigError("Selected composition id is required.")
    return json.dumps(
        {
            "schema_version": SESSION_CONFIG_SNAPSHOT_SCHEMA,
            "policies": policies,
            "selected_composition_id": composition_id,
            "selected_composition": selected_composition,
            "composition_binding": composition_binding,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def decode_study_session_config(raw: str | None) -> DecodedStudySessionConfig:
    try:
        parsed = json.loads(raw or "{}")
    except (TypeError, ValueError) as exc:
        raise StudySessionConfigError("Stored study session config is not JSON.") from exc
    if not isinstance(parsed, dict):
        raise StudySessionConfigError("Stored study session config must be an object.")

    if parsed.get("schema_version") != SESSION_CONFIG_SNAPSHOT_SCHEMA:
        return DecodedStudySessionConfig(
            policies=parsed,
            selected_composition_id=None,
            selected_composition=None,
            composition_binding=None,
            legacy=True,
        )

    policies = parsed.get("policies")
    selected_id = parsed.get("selected_composition_id")
    selected = parsed.get("selected_composition")
    binding = parsed.get("composition_binding")
    if (
        not isinstance(policies, dict)
        or not isinstance(selected_id, str)
        or not selected_id.strip()
        or not isinstance(selected, dict)
        or selected.get("composition_id") != selected_id
        or not isinstance(binding, dict)
        or binding.get("composition_id") != selected_id
    ):
        raise StudySessionConfigError(
            "Stored study session composition config is malformed."
        )
    return DecodedStudySessionConfig(
        policies=policies,
        selected_composition_id=selected_id,
        selected_composition=selected,
        composition_binding=binding,
        legacy=False,
    )


def validate_payload_composition(
    config: DecodedStudySessionConfig,
    payload: dict[str, Any],
) -> None:
    supplied = payload.get("composition_id")
    if supplied is None:
        return
    if not isinstance(supplied, str) or not supplied.strip():
        raise StudySessionConfigError("Commit composition_id is malformed.")
    if config.selected_composition_id is None:
        raise StudySessionConfigError(
            "Legacy session does not accept a newly supplied composition id."
        )
    if supplied.strip() != config.selected_composition_id:
        raise StudySessionConfigError(
            "Commit composition_id differs from the frozen session selection."
        )
