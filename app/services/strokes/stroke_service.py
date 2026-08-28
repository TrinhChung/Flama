"""Stroke service for resolving Kanji & Hanzi SVG stroke diagrams and batch note updates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.services import deck_working_tree_service
from app.services.strokes.cjk_extractor import CjkExtractor
from models import db
from models.flashcard import Card, Note, NoteType


class StrokeServiceError(ValueError):
    """Stroke generation validation or processing error."""

    def __init__(self, message: str, *, status: int = 400, code: str | None = None) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = code


def normalize_locale(locale: str | None) -> str:
    """Normalize locale string to standard folder name ('ja', 'zh', 'zh-hant')."""
    loc = str(locale or "ja").strip().lower().replace("_", "-")
    if loc in {"ja", "ja-jp", "japanese", "jp"}:
        return "ja"
    if loc in {"zh-tw", "zh-hant", "zh-hk", "traditional", "zh-mo"}:
        return "zh-hant"
    if loc in {"zh", "zh-cn", "zh-hans", "chinese", "zh-sg"}:
        return "zh"
    return "ja"


def _get_static_root() -> Path:
    """Resolve static root directory."""
    if has_app_context():
        static_folder = current_app.static_folder
        if static_folder:
            return Path(static_folder)
    return Path("static")


def check_stroke_svg_exists(locale: str, hex_code: str, static_root: Path | None = None) -> bool:
    """Check if static stroke SVG exists on disk."""
    root = static_root or _get_static_root()
    folder = normalize_locale(locale)
    
    # Check primary folder
    svg_file = root / "strokes" / folder / f"{hex_code}.svg"
    if svg_file.exists():
        return True
    
    # Check 5-digit padded
    if len(hex_code) < 5:
        padded_file = root / "strokes" / folder / f"{hex_code.zfill(5)}.svg"
        if padded_file.exists():
            return True

    # Fallback from zh-hant to zh
    if folder == "zh-hant":
        fallback_file = root / "strokes" / "zh" / f"{hex_code}.svg"
        if fallback_file.exists():
            return True

    return False


def resolve_stroke_items(
    text: str | None,
    *,
    locale: str = "ja",
    deduplicate: bool = True,
    max_characters: int = 15,
    output_format: str = "html",
) -> dict[str, Any]:
    """Extract CJK characters from input text/HTML and resolve static SVG URLs and snippets."""
    characters = CjkExtractor.extract_characters(
        text,
        deduplicate=deduplicate,
        max_limit=max_characters,
    )
    norm_locale = normalize_locale(locale)
    static_root = _get_static_root()

    items: list[dict[str, Any]] = []
    missing: list[str] = []

    for char in characters:
        hex_code = CjkExtractor.char_to_hex(char)
        folder = norm_locale
        # If zh-hant requested but file only exists in zh, resolve zh folder
        if folder == "zh-hant" and not (static_root / "strokes" / "zh-hant" / f"{hex_code}.svg").exists():
            if (static_root / "strokes" / "zh" / f"{hex_code}.svg").exists():
                folder = "zh"

        is_avail = check_stroke_svg_exists(norm_locale, hex_code, static_root)
        url = f"/static/strokes/{folder}/{hex_code}.svg"
        if not is_avail:
            missing.append(char)

        items.append({
            "char": char,
            "hex": hex_code,
            "url": url,
            "available": is_avail,
        })

    # Render formatted output
    fmt = str(output_format or "html").strip().lower()
    if fmt == "urls":
        output_str = json.dumps([item["url"] for item in items], ensure_ascii=False)
    elif fmt == "raw":
        output_str = json.dumps(items, ensure_ascii=False)
    else:  # html embed
        if not items:
            output_str = ""
        else:
            img_tags = "".join(
                f'<img src="{item["url"]}" alt="{item["char"]}" title="{item["char"]}" class="stroke-svg" loading="lazy" />'
                for item in items
            )
            output_str = f'<div class="flama-stroke-diagram" data-locale="{norm_locale}">{img_tags}</div>'

    return {
        "locale": norm_locale,
        "characters": characters,
        "items": items,
        "output": output_str,
        "missing_count": len(missing),
        "missing_characters": missing,
    }


def batch_generate_strokes(
    *,
    user_id: int,
    admin_mode: bool,
    source_field: str,
    target_field: str,
    locale: str = "ja",
    deck_id: int | None = None,
    note_ids: list[str] | None = None,
    card_ids: list[str] | None = None,
    output_format: str = "html",
    overwrite: bool = False,
    max_characters: int = 15,
) -> dict[str, Any]:
    """Batch generate stroke diagrams across notes in a deck or specified notes/cards."""
    source_field = str(source_field or "").strip()
    target_field = str(target_field or "").strip()
    if not source_field:
        raise StrokeServiceError("source_field là bắt buộc.")
    if not target_field:
        raise StrokeServiceError("target_field là bắt buộc.")

    # 1. Collect target notes
    notes: list[Note] = []
    if card_ids:
        card_query = (
            Card.query.filter(Card.id.in_(card_ids))
            .options(
                selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
            )
        )
        if not admin_mode:
            card_query = card_query.join(Note, Card.note_id == Note.id).filter(Note.user_id == user_id)
        cards = card_query.all()
        seen_note_ids: set[str] = set()
        for c in cards:
            if c.note and c.note.id not in seen_note_ids:
                seen_note_ids.add(c.note.id)
                notes.append(c.note)
    elif note_ids:
        note_query = (
            Note.query.filter(Note.id.in_(note_ids))
            .options(selectinload(Note.note_type).selectinload(NoteType.field_defs))
        )
        if not admin_mode:
            note_query = note_query.filter(Note.user_id == user_id)
        notes = note_query.all()
    elif deck_id is not None:
        note_query = (
            Note.query.filter(Note.deck_id == deck_id)
            .options(selectinload(Note.note_type).selectinload(NoteType.field_defs))
        )
        if not admin_mode:
            note_query = note_query.filter(Note.user_id == user_id)
        notes = note_query.all()
    else:
        raise StrokeServiceError("Phải cung cấp deck_id, note_ids hoặc card_ids.")

    if not notes:
        return {
            "total_processed": 0,
            "updated": 0,
            "skipped": 0,
            "missing_characters": [],
        }

    updated_count = 0
    skipped_count = 0
    missing_all: set[str] = set()
    dirty_mutations: list[dict[str, Any]] = []

    for note in notes:
        field_values = dict(note.field_values or {})
        existing_val = str(field_values.get(target_field) or "").strip()

        if not overwrite and existing_val:
            skipped_count += 1
            continue

        source_val = str(field_values.get(source_field) or "").strip()
        if not source_val:
            skipped_count += 1
            continue

        res = resolve_stroke_items(
            source_val,
            locale=locale,
            output_format=output_format,
            max_characters=max_characters,
        )

        missing_all.update(res.get("missing_characters") or [])
        output_content = res.get("output", "")

        if not output_content:
            skipped_count += 1
            continue

        if field_values.get(target_field) != output_content:
            field_values[target_field] = output_content
            note.field_values = field_values
            dirty_mutations.append({
                "note": note,
                "field_names": {target_field},
                "operation": "set",
            })
            updated_count += 1
        else:
            skipped_count += 1

    if dirty_mutations:
        try:
            deck_working_tree_service.mark_note_field_batches_changed(
                mutations=dirty_mutations,
            )
            db.session.commit()
        except SQLAlchemyError as exc:
            db.session.rollback()
            raise StrokeServiceError(
                "Không thể lưu sơ đồ nét vào database.",
                status=500,
            ) from exc

    return {
        "total_processed": len(notes),
        "updated": updated_count,
        "skipped": skipped_count,
        "missing_characters": sorted(list(missing_all)),
    }
