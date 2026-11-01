"""Application service for editing the current study card."""

from __future__ import annotations

from typing import Any, Mapping

from app.repositories import study_card_editor_repository as study_edit_repo
from app.repositories.vocabulary_repository import note_display_triplet, note_field_values_as_strings
from app.services import deck_working_tree_service
from app.services.note_draft_service import effective_note_metadata
from app.services.effective_template_service import resolve_effective_template
from app.services.flashcard_renderer import (
    TemplateCompileError,
    render_template_pair,
)
from app.services.media_field_codec import build_media_reference_lookup
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
    render_result: bool = True,
    template_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Validate and persist edited note fields for the active study card."""
    card = study_edit_repo.load_owned_card_for_study_edit(user_id=user_id, card_id=card_id)
    if not card or not card.note:
        raise StudyCardEditError("Card not found or not editable.", status=404, code="FIELD_NOT_FOUND")

    note = card.note
    note_type = note.note_type
    if note_type is None:
        raise StudyCardEditError("Note type not found.", status=404, code="FIELD_NOT_FOUND")

    note_media_ids = build_media_reference_lookup(note.media_assets or [])
    try:
        from app.services.note_value_precondition_service import check_note_write_preconditions
        check_note_write_preconditions(note, payload)
        validated = validate_study_card_edit_request(
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

    original_values = dict(note.field_values or {})
    metadata = effective_note_metadata(note)
    original_deck_id = metadata["deck_id"]
    next_values = dict(original_values)
    for key_name, value in validated.field_updates.items():
        next_values[key_name] = value
    changed_field_names = {
        key_name
        for key_name in validated.field_updates
        if original_values.get(key_name) != next_values.get(key_name)
    }
    tags_changed = bool(
        validated.update_tags
        and list(metadata["tags"] or []) != list(validated.tags or [])
    )
    deck_changed = bool(
        validated.update_deck and original_deck_id != validated.deck_id
    )
    if deck_changed and deck_working_tree_service.note_has_shared_release_dependents(note):
        raise StudyCardEditError(
            "Released shared notes cannot move between decks; retire the note and add a replacement in a new release.",
            status=409,
            field="deck_id",
            code="SHARED_ENTITY_RETIRE_REQUIRED",
        )
    if tags_changed and deck_working_tree_service.note_has_shared_release_dependents(note):
        raise StudyCardEditError(
            "Tags on a released shared note cannot change until note metadata is versioned.",
            status=409,
            field="tags",
            code="SHARED_NOTE_METADATA_VERSIONING_REQUIRED",
        )

    if changed_field_names:
        from app.services import media_staging_service
        try:
            next_values = media_staging_service.commit_all_staged_urls_in_field_values(
                user_id=user_id, note_id=note.id, field_values=next_values,
            )
        except RequestValidationError as exc:
            from models import db
            db.session.rollback()
            raise StudyCardEditError(str(exc), status=exc.status, field=exc.field, code=exc.code) from exc
        note.field_values = next_values
    if tags_changed:
        note.tags = validated.tags
    if validated.update_deck:
        note.deck_id = validated.deck_id

    dirty_mutations: list[dict[str, Any]] = []
    if deck_changed:
        all_field_names = {
            str(field_def.name)
            for field_def in note_type.field_defs
            if str(field_def.name or "").strip()
        } | set(original_values) | set(note.field_values or {})
        dirty_mutations.extend(
            [
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "remove",
                    "deck_id": original_deck_id,
                },
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "add",
                    "deck_id": note.deck_id,
                },
            ]
        )
    elif changed_field_names:
        dirty_mutations.append(
            {
                "note": note,
                "field_names": changed_field_names,
                "operation": "set",
            }
        )
    if dirty_mutations:
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=dirty_mutations,
        )

    if changed_field_names or tags_changed or deck_changed:
        study_edit_repo.commit_note_edit()

    rendered_front_html = ""
    rendered_back_html = ""
    rendered_front_payload = None
    rendered_back_payload = None
    if render_result and card.template:
        template = resolve_effective_template(card, template_overrides=template_overrides)
        try:
            rendered = render_template_pair(
                template=template,
                field_defs=note_type.field_defs,
                field_values=note.field_values or {},
                media_assets=note.media_assets,
            )
            rendered_front_html = rendered.get("front_html", "")
            rendered_back_html = rendered.get("back_html", "")
            rendered_front_payload = rendered.get("front_renderer_payload")
            rendered_back_payload = rendered.get("back_renderer_payload")
        except TemplateCompileError as exc:
            rendered_front_html = f"<div class='text-danger'>Error rendering front: {exc}</div>"
            rendered_back_html = f"<div class='text-danger'>Error rendering back: {exc}</div>"

    display_triplet = note_display_triplet(note)
    from app.services.note_value_precondition_service import note_revision_payload
    result = {
        "success": True,
        "card_id": card.id,
        "note_id": note.id,
        "deck_id": effective_note_metadata(note)["deck_id"],
        "tags": effective_note_metadata(note)["tags"] or [],
        "field_values": note_field_values_as_strings(note),
        **note_revision_payload(note),
        "word": display_triplet.get("word", ""),
        "reading": display_triplet.get("reading", ""),
        "meaning": display_triplet.get("meaning", ""),
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }
    if render_result:
        result.update(
            {
                "rendered_front_html": rendered_front_html,
                "rendered_back_html": rendered_back_html,
                "rendered_front_payload": rendered_front_payload,
                "rendered_back_payload": rendered_back_payload,
            }
        )
    return result
