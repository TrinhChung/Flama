"""Presenter layer for vocabulary routes, turning domain models into View payloads."""

from __future__ import annotations

from datetime import datetime
import html
import re
from types import SimpleNamespace
from typing import Any, Mapping

from app.repositories.study_repository import (
    LEARNING_QUEUE,
    LEARN_QUEUE,
    NEW_QUEUE,
    RELEARNING_QUEUE,
    REVIEW_QUEUE,
    effective_due_at_for_progress_values,
    normalize_progress_queue as _normalize_progress_queue,
)
from app.repositories.vocabulary_repository import (
    browse_due_label,
    browse_first_non_empty,
    format_display_summary,
    note_display_triplet,
    note_field_values_as_strings,
    note_ordered_field_names,
)
from app.services.media_field_codec import store_media_url




def browse_status_code(*, queue: str | None, due_at: datetime | None, now: datetime) -> str:
    queue_norm = (queue or NEW_QUEUE).strip().lower()
    if queue_norm == NEW_QUEUE:
        return NEW_QUEUE
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE, LEARN_QUEUE}:
        return LEARNING_QUEUE
    if queue_norm == REVIEW_QUEUE and (due_at is None or due_at <= now):
        return REVIEW_QUEUE
    return queue_norm


def resolve_browse_queue_due(
    *,
    progress_obj: Any | None,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[str, datetime | None]:
    if progress_obj is not None:
        return (
            _normalize_progress_queue(progress_obj.queue),
            effective_due_at_for_progress_values(
                queue=progress_obj.queue,
                due_at=progress_obj.due_at,
                due_day=progress_obj.due_day,
                now=now,
                timezone_name=timezone_name,
            ),
        )
    return NEW_QUEUE, None


def build_browse_row(
    card_obj: Card,
    deck_name_lookup: dict[int, str],
    now: datetime,
    progress_obj: Any | None = None,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    note_obj = card_obj.note
    display_triplet = note_display_triplet(note_obj)
    word = display_triplet["word"]
    reading = display_triplet["reading"]
    meaning = display_triplet["meaning"]

    note_type_name = note_obj.note_type.name if note_obj and note_obj.note_type else "Unknown"
    template_name = card_obj.template.name if card_obj.template else "Card"
    card_type = f"{note_type_name} / {template_name}" if template_name else note_type_name
    deck_name = deck_name_lookup.get((note_obj.deck_id or 0) if note_obj else 0, "")
    queue_value, due_at_value = resolve_browse_queue_due(
        progress_obj=progress_obj,
        now=now,
        timezone_name=timezone_name,
    )
    status_code = browse_status_code(queue=queue_value, due_at=due_at_value, now=now)

    return {
        "card_id": card_obj.id,
        "note_id": note_obj.id if note_obj else None,
        "note_type_id": note_obj.note_type_id if note_obj else None,
        "card_type": card_type,
        "note_type": note_type_name,
        "template": template_name,
        "queue": queue_value,
        "status": status_code,
        "due_at": due_at_value.isoformat() if due_at_value else None,
        "due_label": browse_due_label(queue=queue_value, due_at=due_at_value),
        "deck_id": note_obj.deck_id if note_obj else None,
        "deck_name": deck_name,
        "word": word,
        "reading": reading,
        "meaning": meaning,
        "tags": (note_obj.tags or []) if note_obj else [],
        "updated_at": note_obj.updated_at.isoformat() if note_obj and note_obj.updated_at else None,
    }


def build_browse_card_detail(
    card_obj: Card,
    deck_name_lookup: dict[int, str],
    now: datetime,
    progress_obj: Any | None = None,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    note_obj = card_obj.note
    note_type_obj = note_obj.note_type if note_obj else None
    field_values = note_obj.field_values if note_obj and isinstance(note_obj.field_values, dict) else {}
    field_defs = (
        sorted(note_type_obj.field_defs, key=lambda fd: int(fd.position or 0))
        if note_type_obj
        else []
    )

    fields = [
        {
            "id": field_def.id,
            "name": field_def.name,
            "field_type": field_def.field_type,
            "required": bool(field_def.required),
            "position": field_def.position,
        }
        for field_def in field_defs
    ]
    existing_names = {field_def["name"] for field_def in fields}
    for key in field_values.keys():
        key_str = str(key)
        if key_str in existing_names:
            continue
        fields.append(
            {
                "name": key_str,
                "field_type": "text",
                "required": False,
                "position": 9999,
            }
        )
    fields.sort(key=lambda item: (int(item["position"]), item["name"].lower()))

    media_assets = []
    if note_obj:
        media_assets = [
            {
                "id": asset.id,
                "field_name": asset.field_name,
                "filename": asset.filename,
                "mime_type": asset.mime_type,
                "url": store_media_url(asset.id),
            }
            for asset in note_obj.media_assets
        ]

    return {
        "card": build_browse_row(
            card_obj,
            deck_name_lookup,
            now,
            progress_obj=progress_obj,
            timezone_name=timezone_name,
        ),
        "note": {
            "id": note_obj.id if note_obj else None,
            "note_type_id": note_obj.note_type_id if note_obj else None,
            "deck_id": note_obj.deck_id if note_obj else None,
            "deck_name": deck_name_lookup.get((note_obj.deck_id or 0) if note_obj else 0, ""),
            "field_values": field_values,
            "content_revision": int(note_obj.content_revision or 0) if note_obj else 0,
            "field_schema_revision": int(note_type_obj.field_schema_revision or 0) if note_type_obj else 0,
            "tags": (note_obj.tags or []) if note_obj else [],
            "updated_at": note_obj.updated_at.isoformat() if note_obj and note_obj.updated_at else None,
        },
        "fields": fields,
        "media_assets": media_assets,
    }


def build_note_study_card_payload(card_obj: Card | None) -> SimpleNamespace | None:
    if not card_obj or not card_obj.note:
        return None

    note_obj = card_obj.note
    field_values = note_field_values_as_strings(note_obj)
    display_triplet = note_display_triplet(note_obj)
    note_type_obj = note_obj.note_type
    field_defs = sorted(note_type_obj.field_defs, key=lambda item: item.position) if note_type_obj else []

    payload = {
        "id": card_obj.id,
        "word": display_triplet["word"],
        "reading": display_triplet["reading"],
        "meaning": display_triplet["meaning"],
        "field_values": field_values,
        "field_defs": [
            {
                "name": field_def.name,
                "field_type": field_def.field_type,
                "required": bool(field_def.required),
                "position": int(field_def.position or 0),
            }
            for field_def in field_defs
        ],
    }
    return SimpleNamespace(**payload)


def render_note_study_flashcard(
    card_obj: Card | None,
    *,
    clone_scope: Any = None,
    template_overrides: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    from app.services.effective_template_service import resolve_effective_template
    from app.services.flashcard_renderer import TemplateCompileError, render_template_pair

    ret: dict[str, Any] = {"front": "", "back": "", "front_payload": None, "back_payload": None}
    if not card_obj or not card_obj.note or not card_obj.template:
        return ret
    template = resolve_effective_template(card_obj, clone_scope, template_overrides=template_overrides)

    note_obj = card_obj.note
    note_type = note_obj.note_type
    if not note_type:
        return ret

    try:
        rendered = render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values=note_obj.field_values or {},
            media_assets=note_obj.media_assets,
            preview_note_key=note_obj.id,
        )
        ret["front"] = rendered.get("front_html", "")
        ret["back"] = rendered.get("back_html", "")
        ret["front_payload"] = rendered.get("front_renderer_payload")
        ret["back_payload"] = rendered.get("back_renderer_payload")
    except TemplateCompileError as exc:
        ret["front"] = f"<div class='text-danger'>Error rendering front: {exc}</div>"
        ret["back"] = f"<div class='text-danger'>Error rendering back: {exc}</div>"

    return ret
