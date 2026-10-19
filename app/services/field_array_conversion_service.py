"""Convert an owned NoteType field to or from ``array`` in one transaction.

The frontend fetches every Note value of the field, splits it into one item
per line and sends the complete result back. This service only enforces the
preconditions (owner, field kind, no concurrent change, every Note covered),
checks the shape of the new values and applies type and values atomically, so
a NoteType is never left half converted. Only the owner's own Notes are read or
written; Notes other users added to an installed copy are never touched.
"""

from __future__ import annotations

from typing import Any

from app.services import deck_working_tree_service, marketplace_query_service
from app.validators.field_array_conversion import (
    RESTORABLE_FIELD_TYPES,
    ArrayConversionError,
    array_value_problem,
    parse_conversion_request,
)
from app.validators.flashcard_input import (
    RequestValidationError,
    sanitize_markdown_text,
    sanitize_plain_text,
    sanitize_rich_text,
)
from models import db
from models.audit_log import AuditLog
from models.field_def import FieldDef
from models.field_types import ARRAY_FIELD_TYPE, field_value_text
from models.note import Note
from models.note_type import NoteType

SCHEMA_VERSION = "field-array-conversion.v1"
_CONFLICT_SAMPLE = 20
_RESTORE_SANITIZERS = {
    "text": sanitize_plain_text,
    "richtext": sanitize_rich_text,
    "markdown": sanitize_markdown_text,
}


def _owned_field(*, user_id: int, note_type_id: str, field_id: str, lock: bool = False) -> tuple[NoteType, FieldDef]:
    note_type = NoteType.query.filter_by(id=note_type_id, user_id=user_id).first()
    if note_type is None:
        raise ArrayConversionError("NOTE_TYPE_NOT_FOUND", "Note type not found.", status=404)
    query = FieldDef.query.filter_by(id=field_id, note_type_id=note_type.id)
    if lock:
        query = query.with_for_update()
    field = query.first()
    if field is None:
        raise ArrayConversionError("FIELD_NOT_FOUND", "Field not found.", status=404)
    return note_type, field


def _blocked_reason(field: FieldDef) -> str | None:
    if field.identity_role == "primary":
        return "PRIMARY_FIELD"
    if field.field_type not in (*RESTORABLE_FIELD_TYPES, ARRAY_FIELD_TYPE):
        return "UNSUPPORTED_FIELD_TYPE"
    return None


def _owner_notes(*, user_id: int, note_type_id: str, lock: bool = False) -> list[Note]:
    query = Note.query.filter_by(note_type_id=note_type_id, user_id=user_id).order_by(Note.created_at.asc(), Note.id.asc())
    if lock:
        query = query.with_for_update()
    return query.all()


def _value(note: Note, field_name: str) -> str:
    return field_value_text((note.field_values or {}).get(field_name))


def get_conversion_source(*, user_id: int, note_type_id: str, field_id: str) -> dict[str, Any]:
    note_type, field = _owned_field(user_id=user_id, note_type_id=note_type_id, field_id=field_id)
    blocked = _blocked_reason(field)
    return {
        "schema_version": SCHEMA_VERSION,
        "field": marketplace_query_service.serialize_field(field),
        "convertible": blocked is None,
        "blocked_reason": blocked,
        "notes": [
            {"note_id": str(note.id), "value": _value(note, field.name)}
            for note in _owner_notes(user_id=user_id, note_type_id=note_type.id)
        ],
    }


def _new_value(request, field: FieldDef, item) -> Any:
    if request.to_array:
        problem = array_value_problem(item.value)
        if problem:
            raise ArrayConversionError(
                "INVALID_ARRAY_VALUE",
                "Array values must be plain text with one non-empty item per line.",
                details={"note_id": item.note_id, "problem": problem},
            )
        # A clean value is already one trimmed item per line.
        return item.value.split("\n") if item.value else []
    try:
        return _RESTORE_SANITIZERS[request.target_type](item.value, field_name=field.name)
    except RequestValidationError as exc:
        raise ArrayConversionError("INVALID_FIELD_VALUE", str(exc), details={"note_id": item.note_id}) from exc


def apply_conversion(*, user_id: int, note_type_id: str, field_id: str, payload: Any) -> dict[str, Any]:
    request = parse_conversion_request(payload)
    try:
        note_type, field = _owned_field(user_id=user_id, note_type_id=note_type_id, field_id=field_id, lock=True)
        blocked = _blocked_reason(field)
        if blocked:
            raise ArrayConversionError("FIELD_NOT_CONVERTIBLE", "This field cannot be converted.", status=409, details={"reason": blocked})
        if field.field_type != request.expected_field_type:
            raise ArrayConversionError(
                "FIELD_CHANGED", "The field type changed since the preview.", status=409,
                details={"field_type": field.field_type},
            )

        notes = _owner_notes(user_id=user_id, note_type_id=note_type.id, lock=True)
        by_id = {str(note.id): note for note in notes}
        requested = {item.note_id for item in request.notes}
        missing = sorted(set(by_id) - requested)
        extra = sorted(requested - set(by_id))
        changed = [
            item.note_id for item in request.notes
            if item.note_id in by_id and _value(by_id[item.note_id], field.name) != item.expected
        ]
        if missing or extra or changed:
            raise ArrayConversionError(
                "NOTES_CHANGED",
                "Notes changed since the preview. Reload the preview and try again.",
                status=409,
                details={
                    "missing_count": len(missing),
                    "extra_count": len(extra),
                    "changed_count": len(changed),
                    "changed_note_ids": changed[:_CONFLICT_SAMPLE],
                },
            )

        previous_type = field.field_type
        mutations = []
        for item in request.notes:
            note = by_id[item.note_id]
            value = _new_value(request, field, item)
            if value == (note.field_values or {}).get(field.name):
                continue
            next_values = dict(note.field_values or {})
            next_values[field.name] = value
            note.field_values = next_values
            mutations.append({"note": note, "field_names": [field.name], "operation": "set"})

        field.field_type = request.target_type
        db.session.flush()
        deck_working_tree_service.mark_field_def_changed(
            field_def=field,
            owner_user_id=user_id,
            property_keys={"field_type"},
        )
        if mutations:
            deck_working_tree_service.mark_note_field_batches_changed(mutations=mutations)
        db.session.add(AuditLog(
            user_id=user_id,
            action="field.convert_array",
            payload={
                "note_type_id": note_type.id,
                "field_id": field.id,
                "from_type": previous_type,
                "to_type": field.field_type,
                "note_count": len(notes),
                "changed_note_count": len(mutations),
            },
        ))
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return {
        "schema_version": SCHEMA_VERSION,
        "field": marketplace_query_service.serialize_field(field),
        "note_count": len(notes),
        "changed_note_count": len(mutations),
    }
