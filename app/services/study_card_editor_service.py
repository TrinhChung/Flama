"""Application service for editing the current study card."""

from __future__ import annotations

from typing import Any

from app.repositories import study_card_editor_repository as study_edit_repo
from app.repositories.vocabulary_repository import note_display_triplet, note_field_values_as_strings
from app.services.flashcard_renderer import (
    TemplateCompileError,
    is_field_empty,
    render_template_pair,
    sanitize_richtext,
)

MEDIA_ALLOWED_PREFIX = "/media/proxy/"
MEDIA_FIELD_TYPES = {"image", "audio", "diagram"}


class StudyCardEditError(ValueError):
    """Typed error for study-card edit API responses."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        code: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.status = int(status)
        self.field = field
        self.code = code


def _clean_incoming_field_value(*, field_type: str, raw_value: Any, note_media_ids: set[str]) -> str:
    if field_type == "richtext":
        return sanitize_richtext("" if raw_value is None else str(raw_value))

    if field_type in MEDIA_FIELD_TYPES:
        candidate = "" if raw_value is None else str(raw_value).strip()
        if not candidate:
            return ""
        if candidate.startswith(MEDIA_ALLOWED_PREFIX):
            return candidate
        if candidate in note_media_ids:
            return candidate
        return ""

    return "" if raw_value is None else str(raw_value).strip()


def update_study_card_note(
    *,
    user_id: int,
    card_id: str,
    payload: dict[str, Any] | None,
) -> dict[str, Any]:
    """Validate and persist edited note fields for the active study card."""
    card = study_edit_repo.load_owned_card_for_study_edit(user_id=user_id, card_id=card_id)
    if not card or not card.note:
        raise StudyCardEditError("Card not found or not editable.", status=404, code="FIELD_NOT_FOUND")

    note = card.note
    note_type = note.note_type
    if note_type is None:
        raise StudyCardEditError("Note type not found.", status=404, code="FIELD_NOT_FOUND")

    body = payload or {}
    raw_field_values = body.get("field_values")
    if not isinstance(raw_field_values, dict):
        raise StudyCardEditError("field_values must be an object.", field="field_values")

    field_defs = sorted(note_type.field_defs, key=lambda item: item.position or 0)
    field_map = {field_def.name: field_def for field_def in field_defs}
    unknown_fields = [key for key in raw_field_values.keys() if key not in field_map]
    if unknown_fields:
        raise StudyCardEditError(
            f"Unknown fields: {', '.join(str(item) for item in unknown_fields)}",
            field="field_values",
        )

    note_media_ids = {asset.id for asset in (note.media_assets or []) if asset.id}
    next_values = dict(note.field_values or {})
    for field_name, raw_value in raw_field_values.items():
        field_def = field_map[field_name]
        next_values[field_name] = _clean_incoming_field_value(
            field_type=str(field_def.field_type or "text"),
            raw_value=raw_value,
            note_media_ids=note_media_ids,
        )

    for field_def in field_defs:
        if field_def.required and is_field_empty(next_values.get(field_def.name)):
            raise StudyCardEditError(
                f"Field '{field_def.name}' is required.",
                field=field_def.name,
            )

    note.field_values = next_values
    study_edit_repo.commit_note_edit()

    rendered_front_html = ""
    rendered_back_html = ""
    if card.template:
        try:
            rendered = render_template_pair(
                template=card.template,
                field_defs=note_type.field_defs,
                field_values=note.field_values or {},
                media_assets=note.media_assets,
                allow_inline_script=True,
            )
            rendered_front_html = rendered.get("front_html", "")
            rendered_back_html = rendered.get("back_html", "")
        except TemplateCompileError as exc:
            rendered_front_html = f"<div class='text-danger'>Error rendering front: {exc}</div>"
            rendered_back_html = f"<div class='text-danger'>Error rendering back: {exc}</div>"

    display_triplet = note_display_triplet(note)
    return {
        "success": True,
        "card_id": card.id,
        "note_id": note.id,
        "field_values": note_field_values_as_strings(note),
        "word": display_triplet.get("word", ""),
        "reading": display_triplet.get("reading", ""),
        "meaning": display_triplet.get("meaning", ""),
        "rendered_front_html": rendered_front_html,
        "rendered_back_html": rendered_back_html,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }
