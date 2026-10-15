"""Optional public optimistic preconditions for Note and field-schema edits."""
from __future__ import annotations

from sqlalchemy import select

from app.validators.flashcard_input import RequestValidationError
from models import db
from models.note import Note
from models.note_type import NoteType


def check_note_write_preconditions(note: Note, payload) -> None:
    if not isinstance(payload, dict):
        return
    expected = {}
    for key in ("expected_content_revision", "expected_field_schema_revision"):
        if key not in payload:
            continue
        value = payload[key]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise RequestValidationError("Revision must be a non-negative integer.",
                status=400, code="INVALID_PARAMS", field=key)
        expected[key] = value
    if not expected:
        return
    # The same parent -> Note ordering is used by canonical flush and cutover.
    schema_revision = db.session.execute(select(NoteType.field_schema_revision)
        .where(NoteType.id == note.note_type_id).with_for_update()).scalar_one()
    content_revision = db.session.execute(select(Note.content_revision)
        .where(Note.id == note.id).with_for_update()).scalar_one()
    actual = {"expected_content_revision": int(content_revision or 0),
        "expected_field_schema_revision": int(schema_revision or 0)}
    for key, revision in expected.items():
        if revision != actual[key]:
            raise RequestValidationError("The note or field schema changed. Reload before saving.",
                status=409, code="FIELD_IDENTITY_CONFLICT", field=key)
    if "expected_field_schema_revision" in expected:
        note.__dict__["_client_field_schema_revision"] = expected["expected_field_schema_revision"]


def note_revision_payload(note: Note) -> dict[str, int]:
    return {"content_revision": int(note.content_revision or 0),
        "field_schema_revision": int(note.note_type.field_schema_revision or 0) if note.note_type else 0}
