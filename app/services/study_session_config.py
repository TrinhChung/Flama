"""Versioned durable metadata stored in StudySession.config_snapshot_json."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from app.services.study_note_storage_precision import NOTE_STORAGE_PROFILE


SESSION_CONFIG_SNAPSHOT_SCHEMA = "study-session-config.v2"
NOTE_SESSION_CONFIG_SNAPSHOT_SCHEMA = "study-session-config.v3"
_SESSION_CONFIG_SCHEMA_PREFIX = "study-session-config."
_CURRENT_WRAPPER_KEYS = {
    "policies",
    "selected_composition_id",
    "selected_composition",
    "composition_binding",
    "storage_profile",
}
_POLICY_MATERIAL_KEYS = (
    "algorithm_key",
    "algorithm_version",
    "config_schema_version",
    "timezone",
    "config",
)


class StudySessionConfigError(ValueError):
    pass


def _canonical_digest(payload: Any) -> str:
    encoded = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"sha256-{hashlib.sha256(encoded).hexdigest()}"


def _is_sha256_digest(value: Any) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 71
        and value.startswith("sha256-")
        and all(char in "0123456789abcdef" for char in value[7:])
    )


def _validate_policy_map(policies: Any) -> dict[str, Any]:
    if not isinstance(policies, dict) or not policies:
        raise StudySessionConfigError(
            "Stored study session policies must be a non-empty object."
        )
    for policy_key, policy in policies.items():
        if not isinstance(policy_key, str) or not policy_key.strip():
            raise StudySessionConfigError(
                "Stored study session policy key is malformed."
            )
        if not isinstance(policy, dict):
            raise StudySessionConfigError(
                "Stored study session policy must be an object."
            )
        if any(
            not isinstance(policy.get(key), str) or not policy[key].strip()
            for key in _POLICY_MATERIAL_KEYS[:-1]
        ) or not isinstance(policy.get("config"), dict):
            raise StudySessionConfigError(
                "Stored study session policy identity is malformed."
            )
        if not _is_sha256_digest(policy_key) or policy.get("config_hash") != policy_key:
            raise StudySessionConfigError(
                "Stored study session policy hash does not match its key."
            )
        material = {key: policy[key] for key in _POLICY_MATERIAL_KEYS}
        if _canonical_digest(material) != policy_key:
            raise StudySessionConfigError(
                "Stored study session policy hash is invalid."
            )
    return policies


def _validate_composition_material(
    *,
    selected_id: Any,
    selected: Any,
    binding: Any,
) -> tuple[str, dict[str, Any], dict[str, Any]]:
    if (
        not isinstance(selected_id, str)
        or not selected_id.strip()
        or not isinstance(selected, dict)
        or selected.get("composition_id") != selected_id
        or not isinstance(binding, dict)
        or binding.get("schema_version") != "study-composition-binding.v1"
        or binding.get("composition_id") != selected_id
    ):
        raise StudySessionConfigError(
            "Stored study session composition config is malformed."
        )

    template_id = selected.get("template_id")
    definition_id = selected.get("definition_id")
    application_id = selected.get("application_id")
    fingerprint = binding.get("binding_fingerprint")
    field_bindings = binding.get("field_bindings")
    if (
        not isinstance(template_id, str)
        or not template_id
        or definition_id != f"legacy-template:{template_id}"
        or binding.get("definition_id") != definition_id
        or not _is_sha256_digest(binding.get("definition_version"))
        or not isinstance(application_id, str)
        or not application_id
        or binding.get("application_id") != application_id
        or binding.get("application_occurrence_id") != application_id
        or binding.get("binding_kind") != "legacy-fielddef-direct"
        or not _is_sha256_digest(fingerprint)
        or not isinstance(field_bindings, list)
    ):
        raise StudySessionConfigError(
            "Stored study session composition binding is malformed."
        )

    input_ids: set[str] = set()
    field_def_ids: set[str] = set()
    for item in field_bindings:
        if not isinstance(item, dict):
            raise StudySessionConfigError(
                "Stored study session field binding is malformed."
            )
        input_id = item.get("input_id")
        field_def_id = item.get("field_def_id")
        if (
            not isinstance(input_id, str)
            or not isinstance(field_def_id, str)
            or not field_def_id
            or input_id != f"legacy-field:{field_def_id}"
            or input_id in input_ids
            or field_def_id in field_def_ids
            or not isinstance(item.get("field_name"), str)
            or not isinstance(item.get("field_type"), str)
            or not isinstance(item.get("required"), bool)
        ):
            raise StudySessionConfigError(
                "Stored study session field binding is malformed."
            )
        input_ids.add(input_id)
        field_def_ids.add(field_def_id)

    binding_material = dict(binding)
    binding_material.pop("binding_fingerprint", None)
    if _canonical_digest(binding_material) != fingerprint:
        raise StudySessionConfigError(
            "Stored study session composition binding hash is invalid."
        )
    return selected_id, selected, binding


@dataclass(frozen=True)
class DecodedStudySessionConfig:
    policies: dict[str, Any]
    selected_composition_id: str | None
    selected_composition: dict[str, Any] | None
    composition_binding: dict[str, Any] | None
    legacy: bool
    storage_profile: str | None = None


def encode_study_session_config(
    *,
    policies: dict[str, Any],
    selected_composition: dict[str, Any],
    composition_binding: dict[str, Any],
    storage_profile: str | None = None,
) -> str:
    if storage_profile not in (None, NOTE_STORAGE_PROFILE):
        raise StudySessionConfigError("Unsupported NOTE storage profile.")
    composition_id = str(selected_composition.get("composition_id") or "").strip()
    if not composition_id:
        raise StudySessionConfigError("Selected composition id is required.")
    _validate_policy_map(policies)
    _validate_composition_material(
        selected_id=composition_id,
        selected=selected_composition,
        binding=composition_binding,
    )
    payload = {
        "schema_version": SESSION_CONFIG_SNAPSHOT_SCHEMA,
        "policies": policies,
        "selected_composition_id": composition_id,
        "selected_composition": selected_composition,
        "composition_binding": composition_binding,
    }
    if storage_profile is not None:
        payload.update(schema_version=NOTE_SESSION_CONFIG_SNAPSHOT_SCHEMA, storage_profile=storage_profile)
    return json.dumps(
        payload,
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

    schema_version = parsed.get("schema_version")
    if schema_version is None:
        if any(key in parsed for key in _CURRENT_WRAPPER_KEYS):
            raise StudySessionConfigError(
                "Stored study session config has a partial versioned wrapper."
            )
        return DecodedStudySessionConfig(
            policies=_validate_policy_map(parsed),
            selected_composition_id=None,
            selected_composition=None,
            composition_binding=None,
            legacy=True,
        )
    if schema_version not in (SESSION_CONFIG_SNAPSHOT_SCHEMA, NOTE_SESSION_CONFIG_SNAPSHOT_SCHEMA):
        if isinstance(schema_version, str) and schema_version.startswith(
            _SESSION_CONFIG_SCHEMA_PREFIX
        ):
            raise StudySessionConfigError(
                "Stored study session config schema is unsupported."
            )
        raise StudySessionConfigError(
            "Stored study session config schema is malformed."
        )

    storage_profile = parsed.get("storage_profile")
    if (
        schema_version == NOTE_SESSION_CONFIG_SNAPSHOT_SCHEMA and storage_profile != NOTE_STORAGE_PROFILE
    ) or (schema_version == SESSION_CONFIG_SNAPSHOT_SCHEMA and "storage_profile" in parsed):
        raise StudySessionConfigError("Stored NOTE storage profile is missing or unsupported.")
    policies = _validate_policy_map(parsed.get("policies"))
    selected_id, selected, binding = _validate_composition_material(
        selected_id=parsed.get("selected_composition_id"),
        selected=parsed.get("selected_composition"),
        binding=parsed.get("composition_binding"),
    )
    return DecodedStudySessionConfig(
        policies=policies,
        selected_composition_id=selected_id,
        selected_composition=selected,
        composition_binding=binding,
        legacy=False,
        storage_profile=storage_profile,
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
