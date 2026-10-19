"""Lossless versioned Field identity codecs for runtime and retained archives."""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any, Iterable

FIELD_VALUE_CODEC = "field-id.v1"


class FieldIdentityError(ValueError):
    """Invalid or ambiguous scope; no identity may be guessed."""


class FieldIdentityConflict(FieldIdentityError):
    """A source row or its captured schema changed; retry the batch."""


@dataclass(frozen=True)
class CapturedFieldSchema:
    note_type_id: str
    revision: int
    fields: tuple[tuple[str, str], ...]

    @property
    def names(self) -> dict[str, str]:
        return {name: field_id for field_id, name in self.fields}

    @property
    def ids(self) -> dict[str, str]:
        return dict(self.fields)


@dataclass(frozen=True)
class EncodedFieldValues:
    by_id: dict[str, Any]
    extras: dict[str, Any]
    codec: str = FIELD_VALUE_CODEC


def capture_field_schema(note_type_id: str, revision: int, field_defs: Iterable[Any]) -> CapturedFieldSchema:
    """Capture exact labels and owned IDs, rejecting duplicate identities."""
    if not isinstance(note_type_id, str) or not note_type_id:
        raise FieldIdentityError("An explicit NoteType scope is required")
    fields, names, ids = [], set(), set()
    for field in field_defs:
        get = field.get if isinstance(field, dict) else lambda key: getattr(field, key)
        field_id, name, scope = get("id"), get("name"), get("note_type_id")
        if scope != note_type_id or not isinstance(field_id, str) or not field_id or not isinstance(name, str):
            raise FieldIdentityError("Field identity does not belong to the captured NoteType")
        if name in names or field_id in ids:
            raise FieldIdentityError("Duplicate name or Field ID in captured schema")
        names.add(name)
        ids.add(field_id)
        fields.append((field_id, name))
    return CapturedFieldSchema(note_type_id, int(revision), tuple(sorted(fields)))


def _json_object(values: Any, label: str) -> dict:
    if not isinstance(values, dict) or any(not isinstance(key, str) for key in values):
        raise FieldIdentityError(f"{label} must be a JSON object with string keys")
    def valid(value):
        if isinstance(value, dict):
            return all(isinstance(key, str) and valid(item) for key, item in value.items())
        if isinstance(value, list):
            return all(valid(item) for item in value)
        return type(value) in (str, int, float, bool, type(None))
    if not valid(values):
        raise FieldIdentityError(f"{label} contains a non-JSON value")
    try:
        json.dumps(values, allow_nan=False)
    except (TypeError, ValueError) as exc:
        raise FieldIdentityError(f"{label} contains a non-JSON value") from exc
    return values


def encode_named_values(schema: CapturedFieldSchema, named_values: Any) -> EncodedFieldValues:
    named_values = _json_object(named_values, "Named values")
    by_id, extras, names = {}, {}, schema.names
    for name, value in named_values.items():
        if name in names:
            by_id[names[name]] = deepcopy(value)
        else:
            extras[name] = deepcopy(value)
    return EncodedFieldValues(by_id, extras)


def project_named_values(schema: CapturedFieldSchema, by_id: Any, extras: Any, codec: str) -> dict:
    if codec != FIELD_VALUE_CODEC:
        raise FieldIdentityError(f"Unsupported field-values codec: {codec!r}")
    by_id = _json_object(by_id, "ID values")
    extras = _json_object(extras, "Retained extras")
    names, result = schema.ids, deepcopy(extras)
    for field_id, value in by_id.items():
        if field_id not in names:
            raise FieldIdentityError("Field ID is outside the captured NoteType schema")
        name = names[field_id]
        if name in result:
            raise FieldIdentityError("Retained extra collides with a declared field label")
        result[name] = deepcopy(value)
    return result


def typed_value_equal(left: Any, right: Any) -> bool:
    """Compare JSON including presence and scalar type (True is not 1)."""
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return left.keys() == right.keys() and all(typed_value_equal(left[key], right[key]) for key in left)
    if isinstance(left, list):
        return len(left) == len(right) and all(typed_value_equal(a, b) for a, b in zip(left, right))
    return left == right


def typed_payload_hash(value: Any) -> str:
    return hashlib.sha256(json.dumps(value, ensure_ascii=False, sort_keys=True,
        separators=(",", ":"), allow_nan=False).encode("utf-8")).hexdigest()
