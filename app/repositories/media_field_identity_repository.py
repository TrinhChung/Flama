"""Media deduplication by the same scoped identity as canonical Note values."""
from __future__ import annotations

from models import db
from models.media_asset import MediaAsset
from models.note import Note


def media_identity_for_label(note: Note, field_name: str) -> str:
    from app.services.field_value_runtime_service import (
        canonical_field_schema_for_note, extra_field_identity_key,
    )
    schema = canonical_field_schema_for_note(note)
    identity = schema.names.get(field_name)
    if identity is not None:
        return identity
    return extra_field_identity_key(note.note_type_id, field_name)


def find_note_field_media(*, note_id: str, field_name: str, sha256: str, note: Note | None = None):
    note = note or db.session.get(Note, note_id)
    if note is None:
        return None
    identity = media_identity_for_label(note, field_name)
    return MediaAsset.query.filter_by(note_id=note_id, sha256=sha256,
        field_identity_key=identity).first()
