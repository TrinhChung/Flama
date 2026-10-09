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
from models.card_progress import CardProgress
from models.flashcard import Card, Note


def browse_first_non_empty(field_values: dict | None) -> str:
    if not isinstance(field_values, dict):
        return ""
    for value in field_values.values():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def note_field_values_as_strings(note_obj: Note | None) -> dict[str, str]:
    if not note_obj or not isinstance(note_obj.field_values, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, value in note_obj.field_values.items():
        key_name = str(key).strip()
        if not key_name:
            continue
        normalized[key_name] = "" if value is None else str(value).strip()
    return normalized


def note_ordered_field_names(note_obj: Note | None, *, text_only: bool = False) -> list[str]:
    ordered_names: list[str] = []
    if not note_obj:
        return ordered_names

    note_type_obj = note_obj.note_type
    if note_type_obj:
        sorted_defs = sorted(
            note_type_obj.field_defs,
            key=lambda item: ((item.position or 0), item.name.lower()),
        )
        for field_def in sorted_defs:
            if text_only and field_def.field_type not in {"text", "richtext", "markdown"}:
                continue
            field_name = (field_def.name or "").strip()
            if field_name and field_name not in ordered_names:
                ordered_names.append(field_name)

    field_values = note_field_values_as_strings(note_obj)
    extra_names = sorted(key for key in field_values.keys() if key not in ordered_names)
    ordered_names.extend(extra_names)
    return ordered_names


def format_display_summary(
    raw: str | None,
    max_length: int = 200,
    is_reading: bool = False,
    is_word: bool = False,
) -> str:
    """Format and clean HTML content for compact Browse Table summaries.

    - Strips fallback <rp> tags.
    - For is_reading: extracts <rt> kana from <ruby>.
    - For is_word: extracts base text/kanji from <ruby>.
    - For other (e.g. meaning): converts <ol>/<li> to '1. item; 2. item; ...',
      <ul>/<li> to 'item; item; ...', and <br>/<p> to '; ' or space.
    - Strips remaining HTML tags.
    - Unescapes HTML entities.
    - Collapses consecutive whitespace into single spaces and cleans punctuation.
    - Gracefully bounds output to max_length.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""

    # Strip fallback <rp> tags
    text = re.sub(r"(?is)<rp>[^<]*</rp>", "", text)

    # Ruby handling based on role
    if is_reading:
        def _replace_ruby_reading(match: re.Match) -> str:
            inner = match.group(1)
            rt_matches = re.findall(r"(?is)<rt\b[^>]*>([^<]*)</rt>", inner)
            if rt_matches:
                return "".join(rt_matches)
            return re.sub(r"(?is)<[^>]+>", "", inner)

        text = re.sub(r"(?is)<ruby\b[^>]*>(.*?)</ruby>", _replace_ruby_reading, text)
    elif is_word:
        def _replace_ruby_word(match: re.Match) -> str:
            inner = match.group(1)
            inner_no_rt = re.sub(r"(?is)<rt\b[^>]*>.*?</rt>", "", inner)
            return re.sub(r"(?is)<[^>]+>", "", inner_no_rt)

        text = re.sub(r"(?is)<ruby\b[^>]*>(.*?)</ruby>", _replace_ruby_word, text)
    else:
        def _replace_ruby_other(match: re.Match) -> str:
            inner = match.group(1)
            inner_no_rt = re.sub(r"(?is)<rt\b[^>]*>.*?</rt>", "", inner)
            return re.sub(r"(?is)<[^>]+>", "", inner_no_rt)

        text = re.sub(r"(?is)<ruby\b[^>]*>(.*?)</ruby>", _replace_ruby_other, text)

    # Strip any dangling <rt> tags
    text = re.sub(r"(?is)<rt\b[^>]*>.*?</rt>", "", text)

    # Convert ordered lists: <ol><li>item</li></ol> -> 1. item; 2. item; ...
    def _replace_ol(match: re.Match) -> str:
        inner = match.group(1)
        items = re.findall(r"(?is)<li\b[^>]*>(.*?)</li>", inner)
        if items:
            formatted = []
            for idx, item in enumerate(items, 1):
                clean = re.sub(r"(?is)<[^>]+>", " ", item)
                clean = " ".join(clean.split()).strip()
                if clean:
                    formatted.append(f"{idx}. {clean}")
            return "; ".join(formatted)
        return inner

    # Convert unordered lists: <ul><li>item</li></ul> -> item; item; ...
    def _replace_ul(match: re.Match) -> str:
        inner = match.group(1)
        items = re.findall(r"(?is)<li\b[^>]*>(.*?)</li>", inner)
        if items:
            formatted = []
            for item in items:
                clean = re.sub(r"(?is)<[^>]+>", " ", item)
                clean = " ".join(clean.split()).strip()
                if clean:
                    formatted.append(clean)
            return "; ".join(formatted)
        return inner

    text = re.sub(r"(?is)<ol\b[^>]*>(.*?)</ol>", _replace_ol, text)
    text = re.sub(r"(?is)<ul\b[^>]*>(.*?)</ul\s*>", _replace_ul, text)
    text = re.sub(r"(?is)<li\b[^>]*>(.*?)</li>", r"; \1", text)
    text = re.sub(r"(?is)<br\s*/?>", "; ", text)
    text = re.sub(r"(?is)</p\s*>", "; ", text)
    text = re.sub(r"(?is)<p\b[^>]*>", " ", text)

    # Strip remaining HTML tags
    text = re.sub(r"(?is)<[^>]+>", " ", text)

    # Unescape HTML entities
    text = html.unescape(text).replace("\xa0", " ")

    # Collapse consecutive whitespace into single spaces and clean punctuation
    text = " ".join(text.split()).strip()
    text = re.sub(r"\s*;\s*(?:;\s*)+", "; ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = text.strip(" ;,\t\r\n")

    if max_length > 0 and len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."

    return text


def note_display_triplet(note_obj: Note | None) -> dict[str, str]:
    field_values = note_field_values_as_strings(note_obj)
    if not field_values:
        return {"word": "", "reading": "", "meaning": ""}

    ordered_text_names = note_ordered_field_names(note_obj, text_only=True)
    non_empty_values: list[str] = []
    for field_name in ordered_text_names:
        text = field_values.get(field_name, "").strip()
        if text:
            non_empty_values.append(text)

    if not non_empty_values:
        fallback = browse_first_non_empty(field_values)
        return {
            "word": format_display_summary(fallback, is_word=True),
            "reading": "",
            "meaning": "",
        }

    return {
        "word": format_display_summary(non_empty_values[0], is_word=True) if len(non_empty_values) >= 1 else "",
        "reading": format_display_summary(non_empty_values[1], is_reading=True) if len(non_empty_values) >= 2 else "",
        "meaning": format_display_summary(non_empty_values[2], is_reading=False, is_word=False) if len(non_empty_values) >= 3 else "",
    }


def browse_due_label(*, queue: str | None, due_at: datetime | None) -> str:
    queue_norm = (queue or NEW_QUEUE).strip().lower()
    if queue_norm == NEW_QUEUE:
        return "New"
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE, LEARN_QUEUE}:
        return "Learn"
    if due_at:
        return due_at.strftime("%Y-%m-%d %H:%M")
    return "Due"


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
    progress_obj: CardProgress | None,
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
    progress_obj: CardProgress | None = None,
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
    progress_obj: CardProgress | None = None,
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
                "url": f"/media/proxy/{asset.id}",
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
