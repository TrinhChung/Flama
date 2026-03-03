"""Application service for editing the current study card."""

from __future__ import annotations

from typing import Any

from app.repositories import study_card_editor_repository as study_edit_repo
from app.repositories.vocabulary_repository import note_display_triplet, note_field_values_as_strings
from app.services.flashcard_renderer import (
    TemplateCompileError,
    render_template_pair,
)
from app.validators import RequestValidationError, validate_study_card_edit_request


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

    note_media_ids = {asset.id for asset in (note.media_assets or []) if asset.id}
    try:
        next_values = validate_study_card_edit_request(
            note_type=note_type,
            payload=payload,
            current_values=dict(note.field_values or {}),
            note_media_ids=note_media_ids,
        )
    except RequestValidationError as exc:
        raise StudyCardEditError(
            str(exc),
            status=exc.status,
            field=exc.field,
            code=exc.code,
        ) from exc

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
