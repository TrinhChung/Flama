"""Stroke service for resolving Kanji & Hanzi SVG stroke diagrams and batch note updates."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

from flask import current_app, has_app_context
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.services import deck_working_tree_service
from app.services.strokes.cjk_extractor import CjkExtractor
from app.services.strokes.dataset_builder import (
    fetch_authentic_stroke_svg,
    generate_kanji_placeholder_svg,
)
from models import db
from models.field_types import field_value_text
from models.card import card_id_clause
from models.flashcard import Card, Note, NoteType
from models.shared_image_asset import SharedImageAsset


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


def _get_upload_root() -> Path:
    """Resolve media upload root directory."""
    if has_app_context():
        upload_root = current_app.config.get("FLASHCARD_MEDIA_UPLOAD_ROOT")
        if upload_root:
            return Path(upload_root).resolve()
    return Path("media").resolve()


def ensure_stroke_shared_asset(image_key: str, upload_root: Path | None = None) -> SharedImageAsset | None:
    """Ensure a stroke diagram exists in SharedImageAsset and physical media storage."""
    m = re.match(r"^stroke_([a-z0-9_]+)_([a-f0-9]{4,6})$", image_key.lower())
    if not m:
        return None

    raw_folder, hex_code = m.group(1), m.group(2)
    locale_norm = raw_folder.replace("_", "-")
    try:
        char = chr(int(hex_code, 16))
    except ValueError:
        return None

    root = upload_root or _get_upload_root()
    storage_path = f"library/strokes/{raw_folder}/{hex_code}.svg"
    full_path = root / storage_path
    
    existing = SharedImageAsset.query.filter_by(image_key=image_key).first()

    if not full_path.exists():
        full_path.parent.mkdir(parents=True, exist_ok=True)
        # Check if static fallback exists first
        static_file = _get_static_root() / "strokes" / locale_norm / f"{hex_code}.svg"
        if static_file.exists():
            svg_content = static_file.read_text(encoding="utf-8")
        else:
            svg_content = fetch_authentic_stroke_svg(char, locale=locale_norm) or generate_kanji_placeholder_svg(char, locale=locale_norm)
            try:
                static_file.parent.mkdir(parents=True, exist_ok=True)
                static_file.write_text(svg_content, encoding="utf-8")
            except Exception:
                pass
        
        full_path.write_text(svg_content, encoding="utf-8")

    svg_bytes = full_path.read_bytes() if full_path.exists() else b""
    sha256 = hashlib.sha256(svg_bytes).hexdigest() if svg_bytes else ""
    size_bytes = len(svg_bytes)

    if not existing:
        asset = SharedImageAsset(
            image_key=image_key,
            filename=f"{hex_code}.svg",
            mime_type="image/svg+xml",
            storage_path=storage_path,
            sha256=sha256,
            size_bytes=size_bytes,
            description=f"Sơ đồ nét: {char} ({locale_norm})",
            tags=["stroke", locale_norm, char, hex_code],
            is_enabled=True,
        )
        db.session.add(asset)
        try:
            db.session.commit()
            return asset
        except Exception:
            db.session.rollback()
            return SharedImageAsset.query.filter_by(image_key=image_key).first()
    else:
        if existing.storage_path != storage_path or not existing.is_enabled:
            existing.storage_path = storage_path
            existing.mime_type = "image/svg+xml"
            existing.is_enabled = True
            existing.size_bytes = size_bytes
            existing.sha256 = sha256
            try:
                db.session.commit()
            except Exception:
                db.session.rollback()
        return existing


def check_stroke_svg_exists(locale: str, hex_code: str, static_root: Path | None = None) -> bool:
    """Check if stroke SVG exists on disk (media library or static)."""
    # The bundled dataset is the common case. Avoid resolving the upload root
    # once per character when a static SVG already answers this existence check.
    root = static_root or _get_static_root()
    folder_static = normalize_locale(locale)
    svg_file = root / "strokes" / folder_static / f"{hex_code}.svg"
    if svg_file.exists():
        return True
    
    if len(hex_code) < 5:
        padded_file = root / "strokes" / folder_static / f"{hex_code.zfill(5)}.svg"
        if padded_file.exists():
            return True

    upload_root = _get_upload_root()
    folder = normalize_locale(locale).replace("-", "_")
    return (upload_root / "library" / "strokes" / folder / f"{hex_code}.svg").exists()


def resolve_stroke_items(
    text: str | None,
    *,
    locale: str = "ja",
    deduplicate: bool = True,
    max_characters: int = 15,
    output_format: str = "html",
) -> dict[str, Any]:
    """Extract CJK characters from input text/HTML and resolve Image Library SVG URLs and snippets."""
    characters = CjkExtractor.extract_characters(
        text,
        deduplicate=deduplicate,
        max_limit=max_characters,
    )
    norm_locale = normalize_locale(locale)
    raw_folder = norm_locale.replace("-", "_")

    items: list[dict[str, Any]] = []

    for char in characters:
        hex_code = CjkExtractor.char_to_hex(char)
        image_key = f"stroke_{raw_folder}_{hex_code}"
        
        # Ensure exists in SharedImageAsset & media library storage
        ensure_stroke_shared_asset(image_key)
        url = f"/media/library/{image_key}.svg"

        items.append({
            "char": char,
            "hex": hex_code,
            "image_key": image_key,
            "url": url,
            "available": True,
        })

    # Render formatted output
    fmt = str(output_format or "html").strip().lower()
    if fmt in {"urls", "urls_json", "json"}:
        output_str = json.dumps([item["url"] for item in items], ensure_ascii=False)
    elif fmt in {"raw", "raw_urls", "raw_url", "plain", "text"}:
        output_str = "\n".join(item["url"] for item in items)
    else:  # html embed
        if not items:
            output_str = ""
        else:
            img_tags = "".join(
                f'<img src="{item["url"]}" class="flama-stroke-char" alt="{item["char"]}" />'
                for item in items
            )
            output_str = f'<div class="flama-stroke-diagram" data-locale="{norm_locale}">{img_tags}</div>'

    return {
        "text": text or "",
        "characters": characters,
        "items": items,
        "output": output_str,
        "format": fmt,
        "locale": norm_locale,
        "missing_count": 0,
        "missing_characters": [],
    }


def _collect_notes(
    *,
    user_id: int,
    admin_mode: bool,
    deck_id: int | None = None,
    note_ids: list[str] | None = None,
    card_ids: list[str] | None = None,
) -> list[Note]:
    """Collect target notes based on card_ids, note_ids, or deck_id."""
    notes: list[Note] = []
    if card_ids:
        card_query = (
            Card.query.filter(card_id_clause(db.session, card_ids))
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
        from app.repositories.deck_tree_query import collect_subtree_ids
        subtree_ids = collect_subtree_ids(deck_id) or [deck_id]
        note_query = (
            Note.query.filter(Note.deck_id.in_(subtree_ids))
            .options(selectinload(Note.note_type).selectinload(NoteType.field_defs))
        )
        if not admin_mode:
            note_query = note_query.filter(Note.user_id == user_id)
        notes = note_query.all()
    else:
        raise StrokeServiceError("Phải cung cấp deck_id, note_ids hoặc card_ids.")
    return notes


def estimate_batch_strokes(
    *,
    user_id: int,
    admin_mode: bool,
    source_field: str,
    target_field: str,
    locale: str = "ja",
    deck_id: int | None = None,
    note_ids: list[str] | None = None,
    card_ids: list[str] | None = None,
    overwrite: bool = False,
    max_characters: int = 15,
) -> dict[str, Any]:
    """Estimate time and workload for batch stroke generation without blocking network calls."""
    source_field = str(source_field or "").strip()
    target_field = str(target_field or "").strip()
    if not source_field or not target_field:
        return {
            "total_notes": 0,
            "notes_to_update": 0,
            "notes_skipped": 0,
            "unique_characters": 0,
            "cached_characters": 0,
            "new_characters": 0,
            "estimated_seconds": 0,
            "estimated_human": "0 giây",
            "is_heavy_task": False,
            "friendly_summary": "Vui lòng chọn trường nguồn và trường lưu kết quả.",
        }

    try:
        notes = _collect_notes(
            user_id=user_id,
            admin_mode=admin_mode,
            deck_id=deck_id,
            note_ids=note_ids,
            card_ids=card_ids,
        )
    except StrokeServiceError:
        return {
            "total_notes": 0,
            "notes_to_update": 0,
            "notes_skipped": 0,
            "unique_characters": 0,
            "cached_characters": 0,
            "new_characters": 0,
            "estimated_seconds": 0,
            "estimated_human": "0 giây",
            "is_heavy_task": False,
            "friendly_summary": "Không tìm thấy thẻ nào phù hợp.",
        }

    if not notes:
        return {
            "total_notes": 0,
            "notes_to_update": 0,
            "notes_skipped": 0,
            "unique_characters": 0,
            "cached_characters": 0,
            "new_characters": 0,
            "estimated_seconds": 0,
            "estimated_human": "0 giây",
            "is_heavy_task": False,
            "friendly_summary": "Không tìm thấy thẻ nào phù hợp.",
        }

    note_types = {str(note.note_type_id) for note in notes if note.note_type_id}
    if len(note_types) > 1:
        return {
            "total_notes": len(notes),
            "notes_to_update": 0,
            "notes_skipped": len(notes),
            "unique_characters": 0,
            "cached_characters": 0,
            "new_characters": 0,
            "estimated_seconds": 0,
            "estimated_human": "0 giây",
            "is_heavy_task": False,
            "has_mixed_note_types": True,
            "friendly_summary": "Bộ deck đang chọn chứa nhiều note type nên không thể thực hiện thao tác.",
        }

    notes_to_update = 0
    notes_skipped = 0
    unique_chars: set[str] = set()

    for note in notes:
        field_values = dict(note.field_values or {})
        existing_val = str(field_values.get(target_field) or "").strip()

        if not overwrite and existing_val:
            notes_skipped += 1
            continue

        source_val = field_value_text(field_values.get(source_field)).strip()
        if not source_val:
            notes_skipped += 1
            continue

        chars = CjkExtractor.extract_characters(
            source_val,
            deduplicate=True,
            max_limit=max_characters,
        )
        if not chars:
            notes_skipped += 1
            continue

        notes_to_update += 1
        unique_chars.update(chars)

    cached_count = 0
    missing_count = 0

    for char in unique_chars:
        hex_code = CjkExtractor.char_to_hex(char)
        if check_stroke_svg_exists(locale, hex_code):
            cached_count += 1
        else:
            missing_count += 1

    # Calculation:
    # Reading local cached svg: ~0.005s per character
    # Fetching & generating missing svg: ~0.25s per character
    # DB update per note: ~0.008s
    est_sec = round((cached_count * 0.005) + (missing_count * 0.25) + (notes_to_update * 0.008) + 0.5)
    estimated_seconds = max(1, est_sec) if notes_to_update > 0 else 0

    if estimated_seconds <= 0:
        estimated_human = "ngay lập tức"
    elif estimated_seconds < 60:
        estimated_human = f"khoảng {estimated_seconds} giây"
    else:
        mins = round(estimated_seconds / 60, 1)
        estimated_human = f"khoảng {mins} phút"

    is_heavy_task = estimated_seconds >= 15 or missing_count >= 30

    if notes_to_update == 0:
        friendly_summary = "Tất cả các thẻ đã có sẵn nét vẽ hoặc không có chữ Hán."
    elif missing_count == 0:
        friendly_summary = f"Tất cả {len(unique_chars)} chữ Hán đã có sẵn nét vẽ. Xử lý rất nhanh!"
    else:
        friendly_summary = f"Cần chuẩn bị nét vẽ mới cho {missing_count} chữ Hán."

    return {
        "total_notes": len(notes),
        "notes_to_update": notes_to_update,
        "notes_skipped": notes_skipped,
        "unique_characters": len(unique_chars),
        "cached_characters": cached_count,
        "new_characters": missing_count,
        "estimated_seconds": estimated_seconds,
        "estimated_human": estimated_human,
        "is_heavy_task": is_heavy_task,
        "friendly_summary": friendly_summary,
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
    notes = _collect_notes(
        user_id=user_id,
        admin_mode=admin_mode,
        deck_id=deck_id,
        note_ids=note_ids,
        card_ids=card_ids,
    )

    if not notes:
        return {
            "total_processed": 0,
            "updated": 0,
            "skipped": 0,
            "missing_characters": [],
        }

    note_types = {str(note.note_type_id) for note in notes if note.note_type_id}
    if len(note_types) > 1:
        raise StrokeServiceError("Bộ deck đang chọn chứa nhiều note type nên không thể thực hiện thao tác.")

    invalid_targets: list[str] = []
    missing_sources: list[str] = []
    for note in notes:
        defs_by_name = {
            str(field_def.name or ""): field_def
            for field_def in (note.note_type.field_defs if note.note_type else [])
        }
        target_def = defs_by_name.get(target_field)
        if target_def is None or str(target_def.field_type or "").strip().lower() not in {"image", "diagram"}:
            invalid_targets.append(str(note.id))
        if source_field not in defs_by_name:
            missing_sources.append(str(note.id))
    if invalid_targets:
        raise StrokeServiceError(
            f"Trường đích '{target_field}' phải tồn tại và có kiểu image/diagram "
            f"(sai ở {len(invalid_targets)} note)."
        )
    if missing_sources:
        raise StrokeServiceError(
            f"Trường nguồn '{source_field}' không tồn tại ở {len(missing_sources)} note."
        )

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

        source_val = field_value_text(field_values.get(source_field)).strip()
        if not source_val:
            skipped_count += 1
            continue

        res = resolve_stroke_items(
            source_val,
            locale=locale,
            output_format="raw",
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
