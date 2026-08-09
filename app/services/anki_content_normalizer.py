"""Normalize safe text artifacts produced by Anki import sources."""

from __future__ import annotations

import re
from dataclasses import dataclass

from models import db
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.field_def import FieldDef
from models.note import Note


_ANKI_APOSTROPHE_ENTITY_RE = re.compile(
    r"&(?:apos|#0*39|#x0*27);",
    flags=re.IGNORECASE,
)
_NORMALIZABLE_FIELD_TYPES = {"text", "richtext", "markdown"}


def normalize_anki_text_entities(value: str) -> str:
    """Decode only apostrophe entities known to leak from Anki field text.

    This intentionally does not use ``html.unescape``. Decoding arbitrary HTML
    entities could turn inert text into markup before the normal field
    sanitizer has validated it.
    """

    if not value or "&" not in value:
        return value
    return _ANKI_APOSTROPHE_ENTITY_RE.sub("'", value)


def normalize_anki_field_values(
    raw_values: dict[str, str],
    field_defs: list[FieldDef] | tuple[FieldDef, ...],
) -> dict[str, str]:
    """Normalize imported text fields while leaving media references intact."""

    field_types = {
        field_def.name: str(field_def.field_type or "text").strip().lower()
        for field_def in field_defs
    }
    return {
        name: (
            normalize_anki_text_entities(value)
            if field_types.get(name) in _NORMALIZABLE_FIELD_TYPES
            else value
        )
        for name, value in raw_values.items()
    }


@dataclass(frozen=True)
class AnkiEntityBackfillResult:
    scanned: int
    changed: int


def backfill_anki_note_entities(
    *,
    user_id: int | None = None,
    deck_id: int | None = None,
) -> AnkiEntityBackfillResult:
    """Normalize existing notes that are known to originate from Anki sync.

    The caller owns the transaction so this can be used for a dry run via
    rollback or committed explicitly by the maintenance CLI.
    """

    tracked_note_exists = ConnectSourceNoteRef.query.filter(
        ConnectSourceNoteRef.note_id == Note.id
    ).exists()
    query = (
        Note.query.filter(tracked_note_exists)
        .filter(Note.field_values.isnot(None))
        .order_by(Note.id.asc())
    )
    if user_id is not None:
        query = query.filter(Note.user_id == user_id)
    if deck_id is not None:
        query = query.filter(Note.deck_id == deck_id)

    field_type_cache: dict[str, tuple[FieldDef, ...]] = {}
    scanned = 0
    changed = 0
    for note in query.yield_per(250):
        scanned += 1
        field_defs = field_type_cache.get(note.note_type_id)
        if field_defs is None:
            field_defs = tuple(
                FieldDef.query.filter_by(note_type_id=note.note_type_id)
                .order_by(FieldDef.position.asc(), FieldDef.id.asc())
                .all()
            )
            field_type_cache[note.note_type_id] = field_defs
        current = {
            str(name): "" if value is None else str(value)
            for name, value in dict(note.field_values or {}).items()
        }
        normalized = normalize_anki_field_values(current, field_defs)
        if normalized != current:
            note.field_values = normalized
            changed += 1

    db.session.flush()
    return AnkiEntityBackfillResult(scanned=scanned, changed=changed)
