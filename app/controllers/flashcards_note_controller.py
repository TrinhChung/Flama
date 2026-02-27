"""Note-focused controllers extracted from flashcards routes."""

from __future__ import annotations

from typing import Any

from app.services.flashcard_renderer import is_field_empty, sanitize_richtext
from models import db
from models.flashcard import Card, FieldDef, MediaAsset, Note, NoteType, Template

DEFAULT_MEDIA_ALLOWED_PREFIX = "/media/proxy/"


def clean_field_value(
    field_def: FieldDef,
    raw_value: Any,
    *,
    media_allowed_prefix: str = DEFAULT_MEDIA_ALLOWED_PREFIX,
) -> Any:
    if field_def.field_type == "richtext":
        return sanitize_richtext("" if raw_value is None else str(raw_value))
    if field_def.field_type in {"image", "audio", "diagram"}:
        if raw_value is None:
            return ""
        candidate = str(raw_value).strip()
        if candidate.startswith(media_allowed_prefix):
            return candidate
        if MediaAsset.query.get(candidate):
            return candidate
        return ""
    return "" if raw_value is None else str(raw_value).strip()


def validate_note_payload(
    note_type: NoteType,
    payload: dict[str, Any],
    *,
    partial: bool,
    media_allowed_prefix: str = DEFAULT_MEDIA_ALLOWED_PREFIX,
) -> tuple[dict[str, Any], str | None]:
    field_map = {field.name: field for field in note_type.field_defs}
    field_values = payload.get("field_values")
    if field_values is None:
        field_values = {}
    if not isinstance(field_values, dict):
        return {}, "field_values must be an object."

    unknown = [key for key in field_values.keys() if key not in field_map]
    if unknown:
        return {}, f"Unknown fields: {', '.join(unknown)}"

    cleaned: dict[str, Any] = {}
    for name, field_def in field_map.items():
        if name in field_values:
            cleaned[name] = clean_field_value(
                field_def,
                field_values.get(name),
                media_allowed_prefix=media_allowed_prefix,
            )

    if not partial:
        for name, field_def in field_map.items():
            if name not in cleaned:
                cleaned[name] = ""
            if field_def.required and is_field_empty(cleaned[name]):
                return {}, f"Field '{name}' is required."
    return cleaned, None


def create_cards_for_note(note: Note) -> None:
    templates = (
        Template.query.filter_by(note_type_id=note.note_type_id)
        .order_by(Template.position.asc())
        .all()
    )
    existing_template_ids = {card.template_id for card in note.cards}
    for template in templates:
        if template.id in existing_template_ids:
            continue
        db.session.add(
            Card(
                note_id=note.id,
                template_id=template.id,
            )
        )
