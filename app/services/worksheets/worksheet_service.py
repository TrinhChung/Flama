"""Worksheet Service - Orchestrates deck note querying, CJK extraction, stroke resolution, layout pagination, and printable HTML rendering."""

from __future__ import annotations

import concurrent.futures
import html
import logging
import re
from typing import Any
import xml.etree.ElementTree as ET

from flask import current_app, has_app_context
from sqlalchemy import func
from sqlalchemy.orm import selectinload

from app.services.strokes.cjk_extractor import CjkExtractor, is_cjk_ideograph, to_simplified_chinese
from app.services.strokes.dataset_builder import fetch_authentic_stroke_svg, generate_kanji_placeholder_svg
from app.services.strokes.stroke_service import (
    _get_static_root,
    _get_upload_root,
    check_stroke_svg_exists,
    ensure_stroke_shared_asset,
    normalize_locale,
)
from app.services.worksheets.template_catalog import (
    WorksheetTemplate,
    calculate_optimal_rows_per_page,
    get_template,
    list_templates,
)
from models import db
from models.card import Card, card_id_clause
from models.deck import Deck
from models.deck_install import DeckInstall
from models.field_types import field_value_text
from models.note import Note
from models.note_type import NoteType


class WorksheetServiceError(ValueError):
    """Worksheet service validation or processing error."""

    def __init__(self, message: str, *, status: int = 400, code: str | None = None) -> None:
        super().__init__(message)
        self.status = int(status)
        self.code = code or "WORKSHEET_ERROR"


def _check_deck_access(user_id: int, deck_id: int, admin_mode: bool = False) -> Deck:
    """Validate user has permission to access the deck (as owner, admin, or installer)."""
    deck = Deck.query.filter_by(id=deck_id).first()
    if deck is None:
        raise WorksheetServiceError(f"Bộ thẻ #{deck_id} không tồn tại.", status=404, code="DECK_NOT_FOUND")

    if admin_mode or deck.owner_user_id == user_id:
        return deck

    # Check if user installed this deck
    install = DeckInstall.query.filter(
        DeckInstall.user_id == user_id,
        (DeckInstall.local_deck_id == deck_id) | (DeckInstall.source_deck_id == deck_id),
    ).first()
    if install is not None:
        return deck

    raise WorksheetServiceError("Bạn không có quyền truy cập bộ thẻ này.", status=403, code="FORBIDDEN")


logger = logging.getLogger(__name__)


def detect_deck_language(deck: Deck | None, notes: list[Note] | None = None) -> str:
    """Detect target language/locale ('zh' or 'ja') from deck name, fields, and note content."""
    if deck is not None:
        text = f"{deck.name or ''} {deck.description or ''}".lower()
        curr_parent_id = getattr(deck, "parent_id", None)
        while curr_parent_id:
            try:
                parent_deck = Deck.query.get(curr_parent_id)
                if not parent_deck:
                    break
                text += f" {parent_deck.name or ''} {parent_deck.description or ''}".lower()
                curr_parent_id = getattr(parent_deck, "parent_id", None)
            except Exception:
                break

        if re.search(r"(hsk|hskk|tocfl|chinese|tiếng trung|trung|zh|hanzi|pinyin)", text):
            return "zh"
        if re.search(r"(jlpt|kanji|tiếng nhật|nhật|japanese|ja|\bn[1-5]\b|hiragana|katakana)", text):
            return "ja"

    if notes:
        # 1. Check note types and field definitions
        for n in notes[:15]:
            if n.note_type:
                nt_name = (n.note_type.name or "").lower()
                if any(k in nt_name for k in ("hsk", "chinese", "tiếng trung", "pinyin", "hanzi")):
                    return "zh"
                if any(k in nt_name for k in ("kanji", "japanese", "tiếng nhật", "kana")):
                    return "ja"
                for f in (n.note_type.field_defs or []):
                    fname = f.name.lower()
                    if "pinyin" in fname:
                        return "zh"
                    if any(k in fname for k in ("furigana", "kana", "hiragana", "katakana")):
                        return "ja"

        # 2. Inspect sample text values in notes
        has_kana = False
        has_simplified = False
        has_traditional = False
        for n in notes[:30]:
            fvals = n.field_values or {}
            for val in fvals.values():
                if not val or not isinstance(val, str):
                    continue
                val_str = str(val)
                # If distinctive simplified Chinese characters found
                if re.search(r"[们这谁时会现读写话书买卖关开门经难易动欢这为么国学汉语课练题鸟鸡车电红蓝绿颜宾馆银辆跑步跳飞站坐船票房医药病]", val_str):
                    has_simplified = True
                    break
                # If distinctive traditional Chinese characters found (繁體字)
                if re.search(r"[學語話書買賣門關開問題幫讓歲錢還過難練結發經動園歡館銀輛飛機電車紅藍綠認識邊遠進關開鐘點課運遊體國會讀寫聽說對應當從義號樣這裡頭視後廣風傳節個圖與計劃點網東長變報選請導應備準確龍鳳華歷歸業農種標環構營製質達議組務調設實導際處積極績術複雜職屬獨織類擴壓權歐穩齊]", val_str):
                    has_traditional = True
                    break
                # If Hiragana or Katakana found -> strictly Japanese
                if any('\u3040' <= ch <= '\u30ff' for ch in val_str):
                    has_kana = True
            if has_simplified:
                return "zh"
            if has_traditional:
                return "zh"

        if has_simplified:
            return "zh"
        if has_traditional:
            return "zh"
        if has_kana:
            return "ja"

    return "ja"


def get_deck_worksheet_meta(user_id: int, deck_id: int, admin_mode: bool = False) -> dict[str, Any]:
    """Retrieve note types, fields, and stats for a deck to configure worksheet generation."""
    deck = _check_deck_access(user_id, deck_id, admin_mode)

    # Query all notes in this deck and its subdecks to inspect note types and field definitions
    from app.repositories.deck_tree_query import collect_subtree_ids
    target_deck_id = deck_id
    if not admin_mode and deck.owner_user_id != user_id:
        install = DeckInstall.query.filter(
            DeckInstall.user_id == user_id,
            (DeckInstall.local_deck_id == deck_id) | (DeckInstall.source_deck_id == deck_id),
        ).first()
        if install and install.source_deck_id:
            target_deck_id = install.source_deck_id

    subtree_ids = collect_subtree_ids(target_deck_id) or [target_deck_id]
    notes_query = Note.query.filter(Note.deck_id.in_(subtree_ids))
    count_rows = (
        notes_query.with_entities(Note.note_type_id, func.count(Note.id))
        .group_by(Note.note_type_id)
        .all()
    )
    total_notes = sum(int(note_count or 0) for _, note_count in count_rows)

    # Metadata only needs a bounded content sample. Counting remains in SQL so a
    # large deck no longer hydrates every JSON field value into Python.
    note_type_ids = [note_type_id for note_type_id, _ in count_rows if note_type_id]
    note_types = (
        NoteType.query.filter(NoteType.id.in_(note_type_ids))
        .options(selectinload(NoteType.field_defs))
        .all()
        if note_type_ids
        else []
    )
    note_types_by_id = {str(note_type.id): note_type for note_type in note_types}
    sample_notes: list[Note] = []
    note_types_list: list[dict[str, Any]] = []
    for note_type_id, note_count in count_rows:
        note_type = note_types_by_id.get(str(note_type_id))
        if note_type is None:
            continue
        samples = (
            notes_query.filter(Note.note_type_id == note_type_id)
            .options(selectinload(Note.note_type).selectinload(NoteType.field_defs))
            .limit(20)
            .all()
        )
        sample_notes.extend(samples)
        sample_values: dict[str, Any] = {}
        for note in samples:
            for key, value in (note.field_values or {}).items():
                if key not in sample_values or not sample_values[key]:
                    sample_values[key] = field_value_text(value)

        note_types_list.append({
            "id": note_type.id,
            "name": note_type.name,
            "fields": [
                field.name
                for field in sorted(
                    note_type.field_defs,
                    key=lambda item: getattr(item, "position", 0),
                )
            ],
            "note_count": int(note_count or 0),
            "sample_values": sample_values,
        })

    # Build suggested field mappings based on field names (strictly excluding media/audio/id fields)
    suggested_mappings: dict[str, dict[str, str]] = {}
    if note_types_list:
        primary_fields = [f.lower() for f in note_types_list[0]["fields"]]
        raw_fields = note_types_list[0]["fields"]
        sample_vals = note_types_list[0].get("sample_values") or {}

        media_blacklist = (
            "audio", "sound", "voice", "mp3", "pronounce", "tts",
            "id", "guid", "deck", "tag", "interval", "factor", "ease", "lapses",
            "time", "date", "color", "style", "css"
        )

        def _is_blacklisted(f_lower: str) -> bool:
            return any(b in f_lower for b in media_blacklist)

        def _find_field(candidates: list[str]) -> str | None:
            # Pass 1: Exact match on non-blacklisted fields
            for cand in candidates:
                cand_lower = cand.lower()
                for idx, f in enumerate(primary_fields):
                    if cand_lower == f and not _is_blacklisted(f):
                        return raw_fields[idx]

            # Pass 2: Substring match on non-blacklisted fields
            for cand in candidates:
                cand_lower = cand.lower()
                for idx, f in enumerate(primary_fields):
                    if cand_lower in f and not _is_blacklisted(f):
                        return raw_fields[idx]
            return None

        def _fallback_kanji_field() -> str:
            # 1. First non-blacklisted field whose sample value has CJK or text
            for idx, f in enumerate(primary_fields):
                if not _is_blacklisted(f):
                    raw_name = raw_fields[idx]
                    sample_text = field_value_text(sample_vals.get(raw_name))
                    if any('\u4e00' <= ch <= '\u9fff' or '\u3040' <= ch <= '\u30ff' for ch in sample_text):
                        return raw_name
            # 2. First non-blacklisted field
            for idx, f in enumerate(primary_fields):
                if not _is_blacklisted(f):
                    return raw_fields[idx]
            # 3. Last resort
            return raw_fields[0] if raw_fields else ""

        detected_locale = detect_deck_language(deck, sample_notes)

        kanji_field = _find_field(["expression", "kanji", "word", "vocab", "front", "hanzi", "sentence", "grammar"]) or _fallback_kanji_field()
        reading_field = _find_field(["reading", "furigana", "kana", "pinyin", "pronunciation"]) or ""
        if detected_locale == "zh":
            meaning_field = _find_field(["meaning_vi", "translation_vi", "meaning", "definition", "vietnamese", "hanviet", "back", "nghia"]) or _find_field(["meaning_jp", "meaning"]) or ""
        else:
            meaning_field = _find_field(["meaning", "definition", "vietnamese", "hanviet", "back", "nghia", "usage", "explanation"]) or ""
        sentence_field = _find_field(["sentence", "example", "expression", "front", "word"]) or kanji_field
        grammar_field = _find_field(["grammar", "pattern", "expression", "word", "front"]) or kanji_field
        example_field = _find_field(["example", "sentence", "sample", "reading"]) or ""

        suggested_mappings = {
            "kanji": kanji_field,
            "reading": reading_field,
            "meaning": meaning_field,
            "word": kanji_field,
            "prompt_reading": reading_field,
            "prompt_meaning": meaning_field,
            "sentence": sentence_field,
            "grammar_point": grammar_field,
            "meaning_usage": meaning_field,
            "example": example_field,
        }
    else:
        detected_locale = detect_deck_language(deck, sample_notes)

    return {
        "deck_id": deck.id,
        "deck_name": deck.name,
        "total_notes": total_notes,
        "note_types": note_types_list,
        "has_mixed_note_types": len(note_types_list) > 1,
        "suggested_mappings": suggested_mappings,
        "templates": list_templates(),
        "detected_locale": detected_locale,
    }


def _get_stroke_svg_content(locale: str, hex_code: str, char: str | None = None) -> str | None:
    """Read the raw SVG file content for inlining into print/HTML documents.
    
    Checks static storage, media upload library storage, falls back to on-demand
    authentic stroke diagram fetching (KanjiVG for ja, MakeMeAHanzi for zh & zh-hant),
    and if not yet found, automatically generates a new vector SVG so characters are never blank.
    """
    static_root = _get_static_root()
    upload_root = _get_upload_root()
    folder = normalize_locale(locale)
    raw_folder = folder.replace("-", "_")

    # 1. Check static stroke storage
    candidates = [
        static_root / "strokes" / folder / f"{hex_code}.svg",
        static_root / "strokes" / folder / f"{hex_code.zfill(5)}.svg",
    ]
    if folder == "zh-hant":
        candidates.append(static_root / "strokes" / "zh" / f"{hex_code}.svg")
        candidates.append(static_root / "strokes" / "zh" / f"{hex_code.zfill(5)}.svg")
    elif folder == "zh":
        candidates.append(static_root / "strokes" / "zh-hant" / f"{hex_code}.svg")
        candidates.append(static_root / "strokes" / "zh-hant" / f"{hex_code.zfill(5)}.svg")

    for path in candidates:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                pass

    # 2. Check media upload library storage
    search_subs = [raw_folder]
    if "zh" in folder:
        # For Chinese locales, cross-check between zh and zh_hant but never fall back to ja
        if raw_folder != "zh_hant":
            search_subs.append("zh_hant")
        if raw_folder != "zh":
            search_subs.append("zh")
    for search_sub in search_subs:
        lib_path = upload_root / "library" / "strokes" / search_sub / f"{hex_code}.svg"
        if lib_path.exists():
            try:
                return lib_path.read_text(encoding="utf-8")
            except Exception:
                pass

    # 3. If char is provided, fetch authentic stroke SVG or auto-generate a new SVG
    if char:
        image_key = f"stroke_{raw_folder}_{hex_code}"
        try:
            asset = ensure_stroke_shared_asset(image_key, upload_root=upload_root)
            if asset:
                full_path = upload_root / asset.storage_path
                if full_path.exists():
                    return full_path.read_text(encoding="utf-8")
        except Exception as e:
            logger.debug("Could not ensure stroke asset for %s (%s): %s", char, locale, e)

        svg_content = None
        try:
            svg_content = fetch_authentic_stroke_svg(char, locale=folder)
        except Exception as e:
            logger.debug("Could not fetch authentic stroke svg for %s (%s): %s", char, locale, e)

        # 4. If authentic stroke SVG is not available upstream, generate a new SVG!
        if not svg_content:
            svg_content = generate_kanji_placeholder_svg(char, locale=folder)

        if svg_content:
            # Cache to static
            try:
                out_file = static_root / "strokes" / folder / f"{hex_code}.svg"
                out_file.parent.mkdir(parents=True, exist_ok=True)
                out_file.write_text(svg_content, encoding="utf-8")
                (static_root / "strokes" / folder / f"{hex_code.zfill(5)}.svg").write_text(svg_content, encoding="utf-8")
            except Exception:
                pass
            # Cache to upload library
            try:
                lib_out = upload_root / "library" / "strokes" / raw_folder / f"{hex_code}.svg"
                lib_out.parent.mkdir(parents=True, exist_ok=True)
                lib_out.write_text(svg_content, encoding="utf-8")
            except Exception:
                pass
            return svg_content

    return None


def _prefetch_missing_stroke_svgs(chars: list[str], locale: str) -> None:
    """Pre-fetch authentic stroke SVGs concurrently for characters not yet cached."""
    if not chars:
        return
    norm_locale = normalize_locale(locale)
    unique_chars = list(dict.fromkeys(chars))
    missing_chars = [
        c for c in unique_chars
        if not check_stroke_svg_exists(norm_locale, CjkExtractor.char_to_hex(c))
    ]
    if not missing_chars:
        return

    def _fetch_one(ch: str):
        h = CjkExtractor.char_to_hex(ch)
        _get_stroke_svg_content(norm_locale, h, char=ch)

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(8, len(missing_chars))) as executor:
        list(executor.map(_fetch_one, missing_chars))


def extract_cumulative_step_svgs(
    svg_content: str,
    highlight_color: str = "#e11d48",
    base_color: str = "#0f172a",
    show_step_numbers: bool = True,
    max_steps: int = 24,
) -> list[str]:
    """Extract individual cumulative stroke order step SVGs from KanjiVG or MakeMeAHanzi SVG."""
    if not svg_content or "<svg" not in svg_content:
        return []

    try:
        root = ET.fromstring(svg_content)
    except Exception:
        return []

    view_box = root.get("viewBox", "0 0 109 109")
    is_mmah = "1024" in view_box or "flama-grid-box" in svg_content

    step_svgs: list[str] = []

    if is_mmah:
        # MakeMeAHanzi: strokes are the lightgray filled paths
        lightgray_paths = [
            p for p in root.findall(".//{http://www.w3.org/2000/svg}path")
            if p.get("fill") == "lightgray"
        ]
        if not lightgray_paths:
            lightgray_paths = [
                p for p in root.iter()
                if p.tag.endswith("path") and p.get("fill") == "lightgray"
            ]

        total_strokes = min(len(lightgray_paths), max_steps)
        if total_strokes == 0:
            return []

        grid_xml = (
            '<rect x="8" y="8" width="1008" height="1008" stroke="#cbd5e1" stroke-width="3" stroke-opacity="0.7" rx="24" fill="none" />'
            '<path d="M 0 512 L 1024 512 M 512 0 L 512 1024 M 0 0 L 1024 1024 M 1024 0 L 0 1024" stroke="#e2e8f0" stroke-width="2.5" stroke-dasharray="10,10" stroke-opacity="0.8" fill="none" />'
        )

        for step_idx in range(1, total_strokes + 1):
            paths_xml = []
            for s in range(step_idx):
                d = lightgray_paths[s].get("d", "")
                is_new = (s == step_idx - 1)
                if is_new:
                    active_color = highlight_color or base_color
                    # Nét bước hiện tại: nét nhạt thanh mảnh để người dùng tô theo
                    paths_xml.append(
                        f'<path d="{d}" fill="{active_color}" fill-opacity="0.38" />'
                    )
                else:
                    # Các nét trước đó: mờ và nhạt làm nét hướng dẫn tô theo
                    paths_xml.append(f'<path d="{d}" fill="#cbd5e1" fill-opacity="0.38" />')

            badge_xml = (
                f'<text x="40" y="80" font-family="ui-monospace, monospace" font-size="64" font-weight="700" fill="#cbd5e1">{step_idx}</text>'
                if show_step_numbers else ""
            )

            step_svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="100%" height="100%" class="flama-stroke-step" preserveAspectRatio="xMidYMid meet">'
                f'{grid_xml}'
                f'<g transform="scale(1, -1) translate(0, -900)">{"".join(paths_xml)}</g>'
                f'{badge_xml}'
                f'</svg>'
            )
            step_svgs.append(step_svg)

    else:
        # KanjiVG: strokes are paths with class containing flama-kvg-stroke
        stroke_paths = [
            p for p in root.findall(".//{http://www.w3.org/2000/svg}path")
            if "flama-kvg-stroke" in (p.get("class") or "")
        ]
        if not stroke_paths:
            stroke_paths = [
                p for p in root.iter()
                if p.tag.endswith("path") and ("-s" in (p.get("id") or "") or "flama-kvg-stroke" in (p.get("class") or ""))
            ]

        total_strokes = min(len(stroke_paths), max_steps)
        if total_strokes == 0:
            return []

        grid_rect = '<rect x="2" y="2" width="105" height="105" stroke="#cbd5e1" stroke-width="0.8" stroke-opacity="0.7" rx="4" fill="none" />'
        grid_cross = '<path d="M 0 54.5 L 109 54.5 M 54.5 0 L 54.5 109 M 0 0 L 109 109 M 109 0 L 0 109" stroke="#e2e8f0" stroke-width="0.6" stroke-dasharray="2,2" stroke-opacity="0.8" fill="none" />'

        for step_idx in range(1, total_strokes + 1):
            paths_xml = []
            for s in range(step_idx):
                d = stroke_paths[s].get("d", "")
                is_new = (s == step_idx - 1)
                if is_new:
                    active_color = highlight_color or base_color
                    # Nét bước hiện tại: nét nhạt thanh mảnh để người dùng tô theo
                    paths_xml.append(
                        f'<path d="{d}" fill="none" stroke="{active_color}" stroke-width="2.2" stroke-opacity="0.38" stroke-linecap="round" stroke-linejoin="round" />'
                    )
                else:
                    # Các nét trước đó: nét mờ và nhạt làm nét hướng dẫn tô theo
                    paths_xml.append(
                        f'<path d="{d}" fill="none" stroke="#cbd5e1" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" />'
                    )

            badge_xml = (
                f'<text x="6" y="14" font-family="ui-monospace, monospace" font-size="8" font-weight="700" fill="#cbd5e1">{step_idx}</text>'
                if show_step_numbers else ""
            )

            step_svg = (
                f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109" width="100%" height="100%" class="flama-stroke-step" preserveAspectRatio="xMidYMid meet">'
                f'{grid_rect}{grid_cross}'
                f'{"".join(paths_xml)}'
                f'{badge_xml}'
                f'</svg>'
            )
            step_svgs.append(step_svg)

    return step_svgs


def extract_static_kanji_svg(
    svg_content: str,
    char_color: str = "#0f172a",
    is_trace: bool = False,
    grid_style: str = "cross",
    rounded: bool = False,
    stroke_color: str = "#64748b",
) -> str | None:
    """Extract a static, full-character vector SVG without animations or stroke numbers.

    Ideal for reference character display (ô đầu) or tracing practice (ô in mờ).
    """
    if not svg_content or "<svg" not in svg_content:
        return None

    try:
        root = ET.fromstring(svg_content)
    except Exception:
        return None

    view_box = root.get("viewBox", "0 0 109 109")
    is_mmah = "1024" in view_box or "flama-grid-box" in svg_content

    if is_mmah:
        lightgray_paths = [
            p for p in root.findall(".//{http://www.w3.org/2000/svg}path")
            if p.get("fill") == "lightgray"
        ]
        if not lightgray_paths:
            lightgray_paths = [
                p for p in root.iter()
                if p.tag.endswith("path") and p.get("fill") == "lightgray"
            ]

        if not lightgray_paths:
            return None

        rx_val = 24 if rounded else 0
        grid_xml = [
            f'<rect x="8" y="8" width="1008" height="1008" stroke="{stroke_color}" stroke-width="4" rx="{rx_val}" fill="#ffffff" />'
        ]
        if grid_style in ("cross", "diagonal"):
            grid_xml.append(
                '<line x1="512" y1="8" x2="512" y2="1016" stroke="#cbd5e1" stroke-width="4" stroke-dasharray="16,16" />'
                '<line x1="8" y1="512" x2="1016" y2="512" stroke="#cbd5e1" stroke-width="4" stroke-dasharray="16,16" />'
            )
        if grid_style == "diagonal":
            grid_xml.append(
                '<line x1="8" y1="8" x2="1016" y2="1016" stroke="#e2e8f0" stroke-width="3" stroke-dasharray="16,16" />'
                '<line x1="8" y1="1016" x2="1016" y2="8" stroke="#e2e8f0" stroke-width="3" stroke-dasharray="16,16" />'
            )

        paths_xml = []
        if is_trace:
            for p in lightgray_paths:
                d = p.get("d", "")
                paths_xml.append(
                    f'<path d="{d}" fill="#cbd5e1" stroke="#cbd5e1" stroke-width="4" stroke-linecap="round" stroke-linejoin="round" fill-opacity="0.85" stroke-opacity="0.85" />'
                )
        else:
            active_color = char_color or "#0f172a"
            for p in lightgray_paths:
                d = p.get("d", "")
                paths_xml.append(
                    f'<path d="{d}" fill="{active_color}" stroke="{active_color}" stroke-width="6" stroke-linecap="round" stroke-linejoin="round" />'
                )

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024" width="100%" height="100%" class="flama-static-kanji-box" preserveAspectRatio="xMidYMid meet">'
            f'{"".join(grid_xml)}'
            f'<g transform="scale(1, -1) translate(0, -900)">{"".join(paths_xml)}</g>'
            f'</svg>'
        )

    else:
        stroke_paths = [
            p for p in root.findall(".//{http://www.w3.org/2000/svg}path")
            if "flama-kvg-stroke" in (p.get("class") or "")
        ]
        if not stroke_paths:
            stroke_paths = [
                p for p in root.iter()
                if p.tag.endswith("path") and ("-s" in (p.get("id") or "") or "flama-kvg-stroke" in (p.get("class") or ""))
            ]

        if not stroke_paths:
            return None

        rx_val = 3 if rounded else 0
        grid_xml = [
            f'<rect x="0.5" y="0.5" width="108" height="108" stroke="{stroke_color}" stroke-width="1" rx="{rx_val}" fill="#ffffff" />'
        ]
        if grid_style in ("cross", "diagonal"):
            grid_xml.append(
                '<line x1="54.5" y1="1" x2="54.5" y2="108" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,2" />'
                '<line x1="1" y1="54.5" x2="108" y2="54.5" stroke="#cbd5e1" stroke-width="0.8" stroke-dasharray="2,2" />'
            )
        if grid_style == "diagonal":
            grid_xml.append(
                '<line x1="1" y1="1" x2="108" y2="108" stroke="#e2e8f0" stroke-width="0.6" stroke-dasharray="2,2" />'
                '<line x1="1" y1="108" x2="108" y2="1" stroke="#e2e8f0" stroke-width="0.6" stroke-dasharray="2,2" />'
            )

        paths_xml = []
        if is_trace:
            for p in stroke_paths:
                d = p.get("d", "")
                paths_xml.append(
                    f'<path d="{d}" fill="none" stroke="#cbd5e1" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" />'
                )
        else:
            active_color = char_color or "#0f172a"
            for p in stroke_paths:
                d = p.get("d", "")
                paths_xml.append(
                    f'<path d="{d}" fill="none" stroke="{active_color}" stroke-width="3.6" stroke-linecap="round" stroke-linejoin="round" />'
                )

        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109" width="100%" height="100%" class="flama-static-kanji-box" preserveAspectRatio="xMidYMid meet">'
            f'{"".join(grid_xml)}'
            f'{"".join(paths_xml)}'
            f'</svg>'
        )


def _generate_genkouyoushi_pages(
    deck: Deck,
    template: WorksheetTemplate,
    notes: list[Note],
    field_mapping: dict[str, Any],
    options: dict[str, Any],
) -> dict[str, Any]:
    """Generate pages for Japanese Genkouyoushi / Chinese essay writing paper."""
    grid_cols = max(10, min(30, int(options.get("grid_columns") or 20)))
    grid_rows = max(5, min(30, int(options.get("grid_rows") or 20)))
    total_cells_per_page = grid_cols * grid_rows

    content_mode = str(options.get("content_mode") or "blank").strip().lower()  # 'blank' | 'text' | 'trace'
    title_placement = str(options.get("title_placement") or "none").strip().lower()
    header_title = str(options.get("header_title") or "").strip()
    custom_text = str(options.get("custom_text") or "").strip()
    requested_pages = max(1, min(20, int(options.get("essay_page_count") or 1)))
    is_trace = content_mode == "trace"

    # If text/trace mode and no custom text provided, try to extract from deck notes
    if content_mode in ("text", "trace") and not custom_text and notes:
        text_field = str(
            field_mapping.get("custom_text")
            or field_mapping.get("sentence")
            or field_mapping.get("kanji")
            or field_mapping.get("word")
            or ""
        ).strip()
        collected = []
        for n in notes:
            fvals = n.field_values or {}
            val = ""
            if text_field and text_field in fvals:
                val = field_value_text(fvals[text_field]).strip()
            elif "Sentence" in fvals:
                val = field_value_text(fvals["Sentence"]).strip()
            elif "Example" in fvals:
                val = field_value_text(fvals["Example"]).strip()
            elif "Expression" in fvals:
                val = field_value_text(fvals["Expression"]).strip()
            if val:
                c_val = CjkExtractor.strip_html(val)
                if c_val:
                    collected.append(c_val)
        custom_text = "\n".join(collected)

    all_grid_pages: list[list[list[dict[str, Any]]]] = []

    def create_empty_page(p_idx: int) -> list[list[dict[str, Any]]]:
        page_rows = []
        for r in range(grid_rows):
            row_cells = []
            for c in range(grid_cols):
                is_title_cell = False
                char = ""
                if p_idx == 0 and r == 0 and title_placement == "first_row" and header_title and content_mode != "blank":
                    clean_title = CjkExtractor.strip_html(header_title).strip()
                    t_len = len(clean_title)
                    if t_len <= grid_cols:
                        start_c = (grid_cols - t_len) // 2
                        if start_c <= c < start_c + t_len:
                            char = clean_title[c - start_c]
                            is_title_cell = True
                row_cells.append({
                    "col_index": c,
                    "char": char,
                    "is_blank": not bool(char),
                    "is_title": is_title_cell,
                    "is_trace": False,
                })
            page_rows.append(row_cells)
        return page_rows

    if content_mode == "blank" or not custom_text.strip():
        for p_idx in range(requested_pages):
            all_grid_pages.append(create_empty_page(p_idx))
    else:
        # Layout text into cells
        current_page_idx = 0
        current_row_idx = 0
        current_col_idx = 0

        curr_page = create_empty_page(0)
        all_grid_pages.append(curr_page)

        if title_placement == "first_row" and header_title:
            current_row_idx = 1
            current_col_idx = 0

        paragraphs = [p.strip() for p in custom_text.split("\n") if p.strip()]
        for p in paragraphs:
            # Paragraph start: indent 2 spaces if standard CJK essay
            current_col_idx = min(2, grid_cols - 1)
            for ch in p:
                if ch in ("\r", "\t"):
                    continue
                if current_col_idx >= grid_cols:
                    current_col_idx = 0
                    current_row_idx += 1
                    if current_row_idx >= grid_rows:
                        current_row_idx = 0
                        current_page_idx += 1
                        curr_page = create_empty_page(current_page_idx)
                        all_grid_pages.append(curr_page)

                curr_page[current_row_idx][current_col_idx] = {
                    "col_index": current_col_idx,
                    "char": ch,
                    "is_blank": False,
                    "is_title": False,
                    "is_trace": is_trace,
                }
                current_col_idx += 1

            # End of paragraph: newline
            current_row_idx += 1
            current_col_idx = 0
            if current_row_idx >= grid_rows:
                current_row_idx = 0
                current_page_idx += 1
                curr_page = create_empty_page(current_page_idx)
                all_grid_pages.append(curr_page)

    total_pages = len(all_grid_pages)
    show_student_info = bool(options.get("show_student_info", True))
    show_date = bool(options.get("show_date", True))
    header_subtitle = str(options.get("header_subtitle") or "Luyện viết văn và tập làm văn mỗi ngày").strip()

    pages: list[dict[str, Any]] = []
    for p_idx, page_rows in enumerate(all_grid_pages):
        page_items = [
            {
                "type": "essay_row",
                "note_id": f"essay-row-{p_idx}-{r_idx}",
                "row_index": r_idx,
                "cells": row_cells,
            }
            for r_idx, row_cells in enumerate(page_rows)
        ]
        pages.append({
            "page_number": p_idx + 1,
            "total_pages": total_pages,
            "header": {
                "title": header_title,
                "subtitle": header_subtitle,
                "deck_name": deck.name,
                "show_student_info": show_student_info,
                "show_date": show_date,
                "header_student_style": options.get("header_student_style", "chinese"),
            },
            "items": page_items,
        })

    return {
        "template": template.to_dict(),
        "deck_id": deck.id,
        "deck_name": deck.name,
        "options": options,
        "field_mapping": field_mapping,
        "total_items": total_pages * total_cells_per_page,
        "total_pages": total_pages,
        "pages": pages,
        "warnings": [],
    }


def _generate_blank_grid_pages(
    deck: Any,
    template: Any,
    options: dict[str, Any],
    field_mapping: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Generate blank worksheet pages when in standalone mode or content_mode is 'blank'."""
    rows_per_page = int(options.get("rows_per_page") or template.default_rows_per_page or 6)
    extra_blank_rows = int(options.get("extra_blank_rows") or 0)
    page_count = max(1, min(int(options.get("blank_page_count") or 1), 20))

    header_title = str(options.get("header_title") or f"{deck.name} - {template.name_vi}").strip()
    header_subtitle = str(options.get("header_subtitle") or "Luyện viết và rèn luyện mỗi ngày").strip()
    show_student_info = bool(options.get("show_student_info", True))
    show_date = bool(options.get("show_date", True))

    pages: list[dict[str, Any]] = []
    for page_idx in range(page_count):
        page_items = []
        for d_idx in range(rows_per_page):
            note_id = f"blank-{page_idx}-{d_idx}"
            if template.id == "kanji_compound":
                page_items.append({
                    "type": "kanji_compound",
                    "note_id": note_id,
                    "word": "",
                    "characters": [],
                    "is_blank_filler": True,
                    "extra_blank_rows": extra_blank_rows,
                })
            elif template.id == "kanji_step_by_step":
                page_items.append({
                    "type": "kanji_step_by_step",
                    "note_id": note_id,
                    "char": "",
                    "step_svgs": [],
                    "is_blank_filler": True,
                    "extra_blank_rows": extra_blank_rows,
                })
            elif template.category == "kanji":
                page_items.append({
                    "type": "kanji",
                    "note_id": note_id,
                    "char": "",
                    "is_blank_filler": True,
                    "extra_blank_rows": extra_blank_rows,
                })
            elif template.id == "vocab_writing":
                page_items.append({
                    "type": "vocab",
                    "note_id": note_id,
                    "word": "",
                    "reading": "",
                    "meaning": "",
                    "is_blank_filler": True,
                })
            elif template.id == "vocab_recall":
                page_items.append({
                    "type": "recall",
                    "note_id": note_id,
                    "meaning": "",
                    "reading": "",
                    "is_blank_filler": True,
                })
            elif template.id == "sentence_writing":
                page_items.append({
                    "type": "sentence",
                    "note_id": note_id,
                    "sentence": "",
                    "reading": "",
                    "meaning": "",
                    "is_blank_filler": True,
                })
            elif template.id == "grammar_practice":
                page_items.append({
                    "type": "grammar",
                    "note_id": note_id,
                    "grammar_point": "",
                    "meaning_usage": "",
                    "example": "",
                    "is_blank_filler": True,
                })
            else:
                page_items.append({
                    "type": "kanji",
                    "note_id": note_id,
                    "char": "",
                    "is_blank_filler": True,
                    "extra_blank_rows": extra_blank_rows,
                })
        pages.append({
            "page_number": page_idx + 1,
            "total_pages": page_count,
            "header": {
                "title": header_title,
                "subtitle": header_subtitle,
                "deck_name": deck.name,
                "show_student_info": show_student_info,
                "show_date": show_date,
            },
            "items": page_items,
        })

    return {
        "template": template.to_dict(),
        "deck_id": deck.id,
        "deck_name": deck.name,
        "options": options,
        "field_mapping": field_mapping or {},
        "total_items": page_count * rows_per_page,
        "total_pages": page_count,
        "pages": pages,
        "warnings": [],
    }


def generate_worksheet_preview(
    user_id: int,
    payload: dict[str, Any],
    admin_mode: bool = False,
) -> dict[str, Any]:
    """Generate structured worksheet pages and preview data from deck notes."""
    template_id = str(payload.get("template_id") or "").strip()
    template = get_template(template_id)
    if template is None:
        raise WorksheetServiceError(f"Mẫu bài tập '{template_id}' không hợp lệ.", code="INVALID_TEMPLATE")

    deck_id = payload.get("deck_id")
    deck = None
    deck_id_int = 0
    if deck_id is not None:
        try:
            deck_id_int = int(deck_id)
            if deck_id_int > 0:
                deck = _check_deck_access(user_id, deck_id_int, admin_mode)
        except (ValueError, TypeError):
            deck = None

    if deck is None:
        if (
            template.id == "genkouyoushi"
            or template.category in ("essay", "kanji", "vocabulary", "blank")
            or str((payload.get("options") or {}).get("content_mode") or "").strip().lower() == "blank"
            or deck_id_int == 0
        ):
            deck = type("VirtualDeck", (), {"id": 0, "name": "Mẫu giấy luyện viết", "owner_user_id": user_id})()
        else:
            raise WorksheetServiceError("deck_id là bắt buộc để tạo bài tập từ thẻ học.", code="MISSING_DECK_ID")

    # Options and mappings
    field_mapping = payload.get("field_mapping") or {}
    payload_options = payload.get("options") or {}
    options = dict(template.default_options)
    options.update(payload_options)

    orientation = str(options.get("orientation") or template.default_orientation).strip().lower()
    margin = str(options.get("margin") or "compact").strip().lower()
    box_size = max(10, min(int(options.get("box_size") or (30 if template.id == "kanji_compact" else 36)), 120))
    extra_blank_rows = max(0, min(int(options.get("extra_blank_rows") or 0), 3))
    page_fill_mode = str(options.get("page_fill_mode") or "max_density").strip().lower()

    # If caller explicitly specified rows_per_page without auto_fit_page, respect explicit rows_per_page
    if "rows_per_page" in payload_options and "auto_fit_page" not in payload_options:
        auto_fit_page = False
    else:
        auto_fit_page = bool(options.get("auto_fit_page", True))

    fill_blank_rows = bool(options.get("fill_blank_rows", True))

    if auto_fit_page:
        writing_lines = int(options.get("writing_lines_count") or 0)
        blanks_param = writing_lines if template.id in {"sentence_writing", "grammar_practice"} else extra_blank_rows
        rows_per_page = calculate_optimal_rows_per_page(
            template.id,
            orientation=orientation,
            margin=margin,
            extra_blank_rows=blanks_param,
            box_size=box_size,
            page_fill_mode=page_fill_mode,
        )
    else:
        rows_per_page = max(1, min(int(options.get("rows_per_page") or template.default_rows_per_page), 30))

    options["rows_per_page"] = rows_per_page
    options["auto_fit_page"] = auto_fit_page
    options["page_fill_mode"] = page_fill_mode
    options["box_size"] = box_size
    options["extra_blank_rows"] = extra_blank_rows
    options["fill_blank_rows"] = fill_blank_rows

    # Scope & Selection
    scope = str(payload.get("scope") or "all").strip().lower()
    card_ids = payload.get("card_ids")
    note_ids = payload.get("note_ids")
    note_type_id = payload.get("note_type_id")
    limit_n = int(payload.get("limit") or 0)
    max_process_limit = 500

    # 1. Query Notes
    notes: list[Note] = []
    if getattr(deck, "id", 0) > 0:
        target_deck_id = deck.id
        if not admin_mode and getattr(deck, "owner_user_id", None) != user_id:
            install = DeckInstall.query.filter(
                DeckInstall.user_id == user_id,
                (DeckInstall.local_deck_id == deck.id) | (DeckInstall.source_deck_id == deck.id),
            ).first()
            if install and install.source_deck_id:
                target_deck_id = install.source_deck_id

        if card_ids and isinstance(card_ids, list):
            cards = (
                Card.query.filter(card_id_clause(db.session, [str(cid) for cid in card_ids[:max_process_limit]]))
                .options(selectinload(Card.note))
                .all()
            )
            seen_nids = set()
            for c in cards:
                if c.note and c.note.id not in seen_nids:
                    seen_nids.add(c.note.id)
                    notes.append(c.note)
        elif note_ids and isinstance(note_ids, list):
            # Explicit Note selections must use the same ownership/release
            # context as Browse, rather than reading author working values.
            from app.services import browse_note_service, browse_card_service
            try:
                notes = browse_note_service.selected_note_values(user_id=user_id, admin_mode=admin_mode,
                    timezone_name="UTC", note_ids=[str(nid) for nid in note_ids[:max_process_limit]])
            except browse_card_service.BrowseApiError as exc:
                raise WorksheetServiceError(str(exc), code="NOTE_NOT_ACCESSIBLE", status=exc.status) from exc
        else:
            from app.repositories.deck_tree_query import collect_subtree_ids
            subtree_ids = collect_subtree_ids(target_deck_id) or [target_deck_id]
            query = Note.query.filter(Note.deck_id.in_(subtree_ids))
            if note_type_id:
                query = query.filter(Note.note_type_id == str(note_type_id).strip())

            if scope == "all" and not note_type_id:
                distinct_note_types = (
                    query.with_entities(Note.note_type_id)
                    .filter(Note.note_type_id.isnot(None))
                    .distinct()
                    .limit(2)
                    .all()
                )
                if len(distinct_note_types) > 1:
                    raise WorksheetServiceError(
                        "Bộ deck đang chọn chứa nhiều note type nên không thể thực hiện thao tác in bài tập.",
                        code="MIXED_NOTE_TYPES",
                    )

            query_limit = max_process_limit
            if scope in {"first_n", "random_n"} and limit_n > 0:
                query_limit = min(limit_n, max_process_limit)
            if scope == "random_n" and limit_n > 0:
                dialect_name = db.session.get_bind().dialect.name
                query = query.order_by(func.rand() if dialect_name == "mysql" else func.random())
            notes = query.limit(query_limit).all()

    if template.id == "genkouyoushi":
        return _generate_genkouyoushi_pages(deck, template, notes, field_mapping, options)

    if not notes:
        if getattr(deck, "id", 0) == 0 or str(options.get("content_mode") or "").strip().lower() == "blank":
            return _generate_blank_grid_pages(deck, template, options, field_mapping)
        return {
            "template": template.to_dict(),
            "deck_id": deck.id,
            "deck_name": deck.name,
            "options": options,
            "total_items": 0,
            "total_pages": 0,
            "pages": [],
            "warnings": ["Không tìm thấy ghi chú nào trong bộ thẻ để tạo bài tập."],
        }

    # Apply scope filtering
    if scope == "first_n" and limit_n > 0:
        notes = notes[:limit_n]
    elif scope == "random_n" and limit_n > 0:
        notes = notes[:limit_n]

    # Safety ceiling
    if len(notes) > max_process_limit:
        notes = notes[:max_process_limit]

    # Resolve target locale: explicit payload option or auto-detected from deck and notes
    if payload_options.get("locale"):
        locale = normalize_locale(payload_options.get("locale"))
    else:
        locale = normalize_locale(detect_deck_language(deck, notes))
    options["locale"] = locale

    # 2. Extract & Format Items based on template category
    raw_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    missing_stroke_chars: set[str] = set()

    # Auto-resolve missing field mapping from actual note fields
    sample_fields: list[str] = []
    for n in notes[:5]:
        if n.field_values:
            sample_fields = list(n.field_values.keys())
            break
    sample_fields_lower = [f.lower() for f in sample_fields]

    def _resolve_field(key: str, candidates: list[str], default: str = "") -> str:
        explicit = str(field_mapping.get(key) or "").strip()
        if explicit and explicit in sample_fields:
            return explicit
        if explicit:
            for idx, sf in enumerate(sample_fields_lower):
                if explicit.lower() == sf:
                    return sample_fields[idx]
        for cand in candidates:
            cand_l = cand.lower()
            for idx, sf in enumerate(sample_fields_lower):
                if cand_l == sf or cand_l in sf:
                    return sample_fields[idx]
        return explicit or default

    kanji_field_name = _resolve_field("kanji", ["expression", "kanji", "word", "vocab", "front", "hanzi", "sentence"], default="Expression")
    reading_field_name = _resolve_field("reading", ["reading", "furigana", "pinyin", "kana", "pronunciation"])
    meaning_field_name = _resolve_field("meaning", ["meaning_vi", "translation_vi", "meaning", "definition", "vietnamese", "hanviet", "back", "nghia", "meaning_jp"])
    word_field_name = _resolve_field("word", ["word", "expression", "kanji", "vocab", "front", "hanzi"], default="Expression")

    if not field_mapping.get("kanji"):
        field_mapping["kanji"] = kanji_field_name
    if not field_mapping.get("reading"):
        field_mapping["reading"] = reading_field_name
    if not field_mapping.get("meaning"):
        field_mapping["meaning"] = meaning_field_name
    if not field_mapping.get("word"):
        field_mapping["word"] = word_field_name

    # Pre-fetch authentic SVGs concurrently if template requires stroke diagrams
    if template.id in ("kanji_compact", "kanji_stroke", "kanji_step_by_step") or (template.category == "kanji" and options.get("show_stroke_diagram", True) is not False):
        all_chars_to_prefetch: list[str] = []
        for n in notes:
            raw_text = field_value_text((n.field_values or {}).get(kanji_field_name)).strip()
            if raw_text:
                extracted = CjkExtractor.extract_characters(raw_text, deduplicate=True, max_limit=10)
                all_chars_to_prefetch.extend(extracted)
        if all_chars_to_prefetch:
            _prefetch_missing_stroke_svgs(all_chars_to_prefetch, locale)

    for idx, note in enumerate(notes):
        fvals = note.field_values or {}

        if template.id == "kanji_compound":
            raw_kanji_text = field_value_text(fvals.get(kanji_field_name)).strip()
            raw_reading = field_value_text(fvals.get(reading_field_name)).strip() if reading_field_name else ""
            raw_meaning = field_value_text(fvals.get(meaning_field_name)).strip() if meaning_field_name else ""

            reading_text = CjkExtractor.strip_html(raw_reading)
            meaning_text = CjkExtractor.strip_html(raw_meaning)
            source_word = CjkExtractor.strip_html(raw_kanji_text)

            # Preserve compound word characters in natural sequence (e.g. 勉強, 学校, 汉语)
            word_chars = [ch for ch in source_word if is_cjk_ideograph(ch)]
            if not word_chars:
                word_chars = CjkExtractor.extract_characters(source_word, deduplicate=False, max_limit=6)
            if not word_chars:
                continue

            characters_data = []
            for ch in word_chars[:6]:
                ch_hex = CjkExtractor.char_to_hex(ch)
                characters_data.append({
                    "char": ch,
                    "hex": ch_hex,
                    "has_stroke": False,
                    "stroke_svg": None,
                    "stroke_url": None,
                })

            raw_items.append({
                "type": "kanji_compound",
                "note_id": note.id,
                "word": source_word,
                "characters": characters_data,
                "reading": reading_text,
                "meaning": meaning_text,
                "extra_blank_rows": extra_blank_rows,
            })

        elif template.id == "kanji_step_by_step":
            raw_kanji_text = field_value_text(fvals.get(kanji_field_name)).strip()
            raw_reading = field_value_text(fvals.get(reading_field_name)).strip() if reading_field_name else ""
            raw_meaning = field_value_text(fvals.get(meaning_field_name)).strip() if meaning_field_name else ""

            reading_text = CjkExtractor.strip_html(raw_reading)
            meaning_text = CjkExtractor.strip_html(raw_meaning)
            source_word = CjkExtractor.strip_html(raw_kanji_text)

            extracted_chars = CjkExtractor.extract_characters(raw_kanji_text, deduplicate=True, max_limit=10)
            if not extracted_chars:
                continue

            step_hl_color = str(options.get("step_highlight_color") or "#e11d48").strip()
            show_step_nums = bool(options.get("show_step_numbers", False))
            ref_char_color = str(options.get("reference_char_color") or "#e11d48").strip()
            grid_style = str(options.get("grid_style") or "cross").strip().lower()

            for char in extracted_chars:
                display_char = char
                hex_code = CjkExtractor.char_to_hex(display_char)
                stroke_svg = _get_stroke_svg_content(locale, hex_code, char=display_char)
                has_stroke = bool(stroke_svg)

                if not has_stroke:
                    missing_stroke_chars.add(display_char)

                step_svgs = extract_cumulative_step_svgs(
                    stroke_svg or "",
                    highlight_color=step_hl_color,
                    show_step_numbers=show_step_nums,
                ) if has_stroke else []

                static_svg = extract_static_kanji_svg(
                    stroke_svg or "",
                    char_color=ref_char_color,
                    is_trace=False,
                    grid_style=grid_style,
                    rounded=True,
                    stroke_color="#0f172a",
                ) if has_stroke else None

                trace_svg = extract_static_kanji_svg(
                    stroke_svg or "",
                    char_color="#cbd5e1",
                    is_trace=True,
                    grid_style=grid_style,
                    rounded=False,
                    stroke_color="#cbd5e1",
                ) if has_stroke else None

                raw_items.append({
                    "type": "kanji_step_by_step",
                    "note_id": note.id,
                    "char": display_char,
                    "hex": hex_code,
                    "has_stroke": has_stroke,
                    "total_strokes": len(step_svgs) if step_svgs else 0,
                    "step_svgs": step_svgs,
                    "stroke_svg": stroke_svg,
                    "static_svg": static_svg,
                    "trace_svg": trace_svg,
                    "stroke_url": f"/static/strokes/{locale}/{hex_code}.svg" if has_stroke else None,
                    "reading": reading_text,
                    "meaning": meaning_text,
                    "source_word": source_word,
                    "extra_blank_rows": extra_blank_rows,
                })

        elif template.category == "kanji":
            raw_kanji_text = field_value_text(fvals.get(kanji_field_name)).strip()
            raw_reading = field_value_text(fvals.get(reading_field_name)).strip() if reading_field_name else ""
            raw_meaning = field_value_text(fvals.get(meaning_field_name)).strip() if meaning_field_name else ""

            reading_text = CjkExtractor.strip_html(raw_reading)
            meaning_text = CjkExtractor.strip_html(raw_meaning)
            source_word = CjkExtractor.strip_html(raw_kanji_text)

            extracted_chars = CjkExtractor.extract_characters(raw_kanji_text, deduplicate=True, max_limit=10)
            if not extracted_chars:
                continue

            for char in extracted_chars:
                display_char = char
                hex_code = CjkExtractor.char_to_hex(display_char)
                stroke_svg = _get_stroke_svg_content(locale, hex_code, char=display_char)
                has_stroke = bool(stroke_svg)

                if not has_stroke:
                    missing_stroke_chars.add(display_char)

                raw_items.append({
                    "type": "kanji",
                    "note_id": note.id,
                    "char": display_char,
                    "hex": hex_code,
                    "has_stroke": has_stroke,
                    "stroke_svg": stroke_svg,
                    "stroke_url": f"/static/strokes/{locale}/{hex_code}.svg" if has_stroke else None,
                    "reading": reading_text,
                    "meaning": meaning_text,
                    "source_word": source_word,
                    "extra_blank_rows": extra_blank_rows,
                })

        elif template.id == "vocab_recall":
            word_field = word_field_name
            reading_field = reading_field_name
            meaning_field = meaning_field_name

            word_val = CjkExtractor.strip_html(field_value_text(fvals.get(word_field)))
            reading_val = CjkExtractor.strip_html(field_value_text(fvals.get(reading_field))) if reading_field else ""
            meaning_val = CjkExtractor.strip_html(field_value_text(fvals.get(meaning_field))) if meaning_field else ""

            if not word_val and not meaning_val:
                continue

            raw_items.append({
                "type": "recall",
                "note_id": note.id,
                "word": word_val,
                "reading": reading_val,
                "meaning": meaning_val,
                "word_length": len(word_val),
            })

        elif template.id == "vocab_writing":
            word_field = word_field_name
            reading_field = reading_field_name
            meaning_field = meaning_field_name

            word_val = CjkExtractor.strip_html(field_value_text(fvals.get(word_field)))
            reading_val = CjkExtractor.strip_html(field_value_text(fvals.get(reading_field))) if reading_field else ""
            meaning_val = CjkExtractor.strip_html(field_value_text(fvals.get(meaning_field))) if meaning_field else ""

            if not word_val:
                continue

            raw_items.append({
                "type": "vocab",
                "note_id": note.id,
                "word": word_val,
                "reading": reading_val,
                "meaning": meaning_val,
            })

        elif template.id == "deck_table":
            custom_cols = field_mapping.get("custom_columns") or []
            if isinstance(custom_cols, str):
                custom_cols = [c.strip() for c in custom_cols.split(",") if c.strip()]
            if not isinstance(custom_cols, list):
                custom_cols = []

            row_data: dict[str, str] = {}
            for col in custom_cols:
                row_data[col] = CjkExtractor.strip_html(field_value_text(fvals.get(col)))

            raw_items.append({
                "type": "table_row",
                "note_id": note.id,
                "data": row_data,
            })

        elif template.id == "sentence_writing":
            sentence_field = str(field_mapping.get("sentence") or field_mapping.get("word") or "Example").strip()
            reading_field = str(field_mapping.get("reading") or "").strip()
            meaning_field = str(field_mapping.get("meaning") or "").strip()

            sentence_val = CjkExtractor.strip_html(field_value_text(fvals.get(sentence_field)))
            reading_val = CjkExtractor.strip_html(field_value_text(fvals.get(reading_field))) if reading_field else ""
            meaning_val = CjkExtractor.strip_html(field_value_text(fvals.get(meaning_field))) if meaning_field else ""

            if not sentence_val and not meaning_val:
                continue

            raw_items.append({
                "type": "sentence",
                "note_id": note.id,
                "sentence": sentence_val,
                "reading": reading_val,
                "meaning": meaning_val,
            })

        elif template.id == "grammar_practice":
            grammar_field = str(field_mapping.get("grammar_point") or field_mapping.get("word") or "Expression").strip()
            meaning_field = str(field_mapping.get("meaning_usage") or field_mapping.get("meaning") or "").strip()
            example_field = str(field_mapping.get("example") or "").strip()

            grammar_val = CjkExtractor.strip_html(field_value_text(fvals.get(grammar_field)))
            meaning_val = CjkExtractor.strip_html(field_value_text(fvals.get(meaning_field))) if meaning_field else ""
            example_val = CjkExtractor.strip_html(field_value_text(fvals.get(example_field))) if example_field else ""

            if not grammar_val:
                continue

            raw_items.append({
                "type": "grammar",
                "note_id": note.id,
                "grammar_point": grammar_val,
                "meaning_usage": meaning_val,
                "example": example_val,
            })

    if missing_stroke_chars:
        chars_preview = ", ".join(list(missing_stroke_chars)[:5])
        warnings.append(f"{len(missing_stroke_chars)} chữ Hán chưa có sơ đồ nét bút ({chars_preview}). Hệ thống sẽ tự động hiển thị chữ mẫu tiêu chuẩn.")

    if not raw_items:
        warnings.append("Không trích xuất được mục nào từ các trường đã ánh xạ. Vui lòng kiểm tra lại cấu hình trường nguồn.")

    # 3. Paginate Items
    total_items = len(raw_items)
    if auto_fit_page and total_items > 0:
        writing_lines = int(options.get("writing_lines_count") or 0)
        blanks_param = writing_lines if template.id in {"sentence_writing", "grammar_practice"} else extra_blank_rows
        rows_per_page = calculate_optimal_rows_per_page(
            template.id,
            orientation=orientation,
            margin=margin,
            extra_blank_rows=blanks_param,
            box_size=box_size,
            total_items=total_items,
            fill_blank_rows=fill_blank_rows,
            page_fill_mode=page_fill_mode,
        )
        options["rows_per_page"] = rows_per_page

    pages: list[dict[str, Any]] = []
    total_pages = max(1, (total_items + rows_per_page - 1) // rows_per_page) if total_items > 0 else 0

    header_title = str(options.get("header_title") or f"{deck.name} - {template.name_vi}").strip()
    header_subtitle = str(options.get("header_subtitle") or "Luyện viết từ vựng và chữ Hán mỗi ngày").strip()
    show_student_info = bool(options.get("show_student_info", True))
    show_date = bool(options.get("show_date", True))

    for page_idx in range(total_pages):
        start_idx = page_idx * rows_per_page
        end_idx = min(start_idx + rows_per_page, total_items)
        page_items = list(raw_items[start_idx:end_idx])

        # Fill remaining blank rows on the last page if requested
        if fill_blank_rows and len(page_items) < rows_per_page:
            deficit = rows_per_page - len(page_items)
            for d_idx in range(deficit):
                if template.id == "kanji_compound":
                    page_items.append({
                        "type": "kanji_compound",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "word": "",
                        "characters": [],
                        "is_blank_filler": True,
                        "extra_blank_rows": extra_blank_rows,
                    })
                elif template.id == "kanji_step_by_step":
                    page_items.append({
                        "type": "kanji_step_by_step",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "char": "",
                        "step_svgs": [],
                        "is_blank_filler": True,
                        "extra_blank_rows": extra_blank_rows,
                    })
                elif template.category == "kanji":
                    page_items.append({
                        "type": "kanji",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "char": "",
                        "is_blank_filler": True,
                        "extra_blank_rows": extra_blank_rows,
                    })
                elif template.id == "vocab_writing":
                    page_items.append({
                        "type": "vocab",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "word": "",
                        "reading": "",
                        "meaning": "",
                        "is_blank_filler": True,
                    })
                elif template.id == "vocab_recall":
                    page_items.append({
                        "type": "recall",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "meaning": "",
                        "reading": "",
                        "is_blank_filler": True,
                    })
                elif template.id == "deck_table":
                    page_items.append({
                        "type": "table_row",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "data": {},
                        "is_blank_filler": True,
                    })
                elif template.id == "sentence_writing":
                    page_items.append({
                        "type": "sentence",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "sentence": "",
                        "reading": "",
                        "meaning": "",
                        "is_blank_filler": True,
                    })
                elif template.id == "grammar_practice":
                    page_items.append({
                        "type": "grammar",
                        "note_id": f"blank-{page_idx}-{d_idx}",
                        "grammar_point": "",
                        "meaning_usage": "",
                        "example": "",
                        "is_blank_filler": True,
                    })

        pages.append({
            "page_number": page_idx + 1,
            "total_pages": total_pages,
            "header": {
                "title": header_title,
                "subtitle": header_subtitle,
                "deck_name": deck.name,
                "show_student_info": show_student_info,
                "show_date": show_date,
            },
            "items": page_items,
        })

    return {
        "template": template.to_dict(),
        "deck_id": deck.id,
        "deck_name": deck.name,
        "options": options,
        "field_mapping": field_mapping,
        "total_items": total_items,
        "total_pages": total_pages,
        "pages": pages,
        "warnings": warnings,
    }


def _render_kanji_grid_svg(
    char: str,
    grid_style: str = "cross",
    is_trace: bool = False,
    is_blank: bool = False,
    size: int = 38,
    rounded: bool = False,
    stroke_color: str = "#64748b",
    char_color: str = "#0f172a",
) -> str:
    """Render an inline SVG practice box with guide lines and optional tracing character."""
    half = size / 2

    # Guide lines based on style
    guidelines_svg = ""
    if grid_style == "cross":
        guidelines_svg = (
            f'<line x1="{half}" y1="1" x2="{half}" y2="{size - 1}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="2 2" />'
            f'<line x1="1" y1="{half}" x2="{size - 1}" y2="{half}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="2 2" />'
        )
    elif grid_style == "diagonal":
        guidelines_svg = (
            f'<line x1="{half}" y1="1" x2="{half}" y2="{size - 1}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="2 2" />'
            f'<line x1="1" y1="{half}" x2="{size - 1}" y2="{half}" stroke="#cbd5e1" stroke-width="1" stroke-dasharray="2 2" />'
            f'<line x1="1" y1="1" x2="{size - 1}" y2="{size - 1}" stroke="#e2e8f0" stroke-width="0.8" stroke-dasharray="2 2" />'
            f'<line x1="1" y1="{size - 1}" x2="{size - 1}" y2="1" stroke="#e2e8f0" stroke-width="0.8" stroke-dasharray="2 2" />'
        )

    # Character inside box
    char_svg = ""
    font_size = int(size * 0.72)
    y_pos = int(size * 0.76)

    if is_trace and char:
        char_svg = (
            f'<text x="{half}" y="{y_pos}" font-family="\'PingFang SC\', \'Microsoft YaHei\', \'PingFang TC\', \'Microsoft JhengHei\', \'SimHei\', \'Noto Sans SC\', \'Noto Sans TC\', \'Hiragino Kaku Gothic ProN\', \'Yu Gothic\', \'Meiryo\', \'Noto Sans JP\', sans-serif" '
            f'font-size="{font_size}" text-anchor="middle" fill="#cbd5e1" font-weight="300">{html.escape(char)}</text>'
        )
    elif not is_blank and char:
        char_svg = (
            f'<text x="{half}" y="{y_pos}" font-family="\'PingFang SC\', \'Microsoft YaHei\', \'PingFang TC\', \'Microsoft JhengHei\', \'SimHei\', \'Noto Sans SC\', \'Noto Sans TC\', \'Hiragino Kaku Gothic ProN\', \'Yu Gothic\', \'Meiryo\', \'Noto Sans JP\', sans-serif" '
            f'font-size="{font_size}" text-anchor="middle" fill="{char_color}" font-weight="500">{html.escape(char)}</text>'
        )

    rx_val = 3 if rounded else 0
    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" class="worksheet-grid-box" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="0.5" y="0.5" width="{size - 1}" height="{size - 1}" fill="#ffffff" stroke="{stroke_color}" stroke-width="1" rx="{rx_val}" />'
        f'{guidelines_svg}'
        f'{char_svg}'
        f'</svg>'
    )


def render_printable_html(preview_data: dict[str, Any]) -> str:
    """Generate a self-contained, standalone printable HTML document with embedded CSS and vector SVGs."""
    template = preview_data.get("template") or {}
    template_id = template.get("id") or "kanji_stroke"
    options = preview_data.get("options") or {}
    pages = preview_data.get("pages") or []

    orientation = str(options.get("orientation") or "portrait").strip().lower()
    margin_mode = str(options.get("margin") or "compact").strip().lower()
    margin_map = {
        "minimal": "4mm",
        "ultra_compact": "4mm",
        "compact": "6mm",
        "standard": "10mm",
        "wide": "14mm",
    }
    margin_css = margin_map.get(margin_mode, "6mm")

    grid_style = str(options.get("grid_style") or "cross")
    trace_count = max(0, int(options.get("trace_count", 2)))
    practice_count = max(1, int(options.get("practice_count", 6)))

    page_size_css = f"A4 {orientation}"

    # Extract current URL, domain and QR code
    current_url = str(options.get("current_url") or options.get("source_url") or "").strip()
    if not current_url:
        try:
            from flask import has_request_context, request
            if has_request_context():
                current_url = str(request.headers.get("Referer") or request.host_url or "").strip()
        except Exception:
            current_url = ""

    current_domain = ""
    if current_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(current_url)
            current_domain = parsed.netloc or current_url
        except Exception:
            current_domain = current_url
    if not current_domain:
        current_domain = "flama.app"

    # Synchronous QR Code generation for current URL
    qr_svg_html = ""
    if current_url:
        try:
            import qrcode
            import qrcode.image.svg
            qr = qrcode.QRCode(
                image_factory=qrcode.image.svg.SvgPathImage,
                box_size=1,
                border=1,
                error_correction=qrcode.constants.ERROR_CORRECT_M,
            )
            qr.add_data(current_url)
            img = qr.make_image()
            raw_svg = img.to_string().decode("utf-8")
            qr_svg_html = f'<a href="{html.escape(current_url)}" target="_blank" rel="noopener noreferrer" class="header-qr-code" title="Quét mã QR để mở trang: {html.escape(current_url)}" aria-label="Mã QR trang bài tập">{raw_svg}</a>'
        except Exception:
            qr_svg_html = ""

    # Generate Pages HTML
    pages_html: list[str] = []

    for page in pages:
        page_num = page.get("page_number", 1)
        total_p = page.get("total_pages", 1)
        hdr = page.get("header") or {}
        items = page.get("items") or []

        # Header Block
        if template_id == "genkouyoushi":
            hdr_style = str(options.get("header_student_style") or "chinese").strip().lower()
            title_placement = str(options.get("title_placement") or "first_row").strip().lower()
            header_title_text = html.escape(hdr.get("title") or "")

            title_html = f'<h1 class="genkou-header-title">{header_title_text}</h1>' if (title_placement == "header" and header_title_text) else ""

            student_bar_html = ""
            if hdr.get("show_student_info"):
                if hdr_style == "chinese":
                    student_bar_html = """
                    <div class="genkou-student-row">
                        <span>班级 ________________</span>
                        <span>姓名 ________________</span>
                        <span>学号 ________________</span>
                        <span>分数 ________________</span>
                    </div>
                    """
                elif hdr_style == "japanese":
                    student_bar_html = """
                    <div class="genkou-student-row">
                        <span>クラス ________________</span>
                        <span>氏名 ________________</span>
                        <span>学籍番号 ________________</span>
                        <span>得点 ________________</span>
                    </div>
                    """
                elif hdr_style == "vietnamese":
                    student_bar_html = """
                    <div class="genkou-student-row">
                        <span>Lớp: ________________</span>
                        <span>Họ tên: ________________</span>
                        <span>Mã số: ________________</span>
                        <span>Điểm: ________________</span>
                    </div>
                    """
                elif hdr_style != "none":
                    student_bar_html = """
                    <div class="genkou-student-row">
                        <span>Lớp: ________________</span>
                        <span>Họ tên: ________________</span>
                        <span>Điểm: ________________</span>
                    </div>
                    """

            header_html = f"""
            <header class="genkou-header">
                {title_html}
                {student_bar_html}
            </header>
            """
        else:
            qr_wrapper_html = f'<div class="header-qr-wrap">{qr_svg_html}</div>' if qr_svg_html else ""
            header_html = f"""
            <header class="sheet-header">
                <div style="display: flex; align-items: flex-end; gap: 10px;">
                    {qr_wrapper_html}
                    <div class="header-main">
                        <h1 class="sheet-title">{html.escape(hdr.get("title") or "")}</h1>
                        <p class="sheet-subtitle">{html.escape(hdr.get("subtitle") or "")}</p>
                    </div>
                </div>
                <div class="header-meta">
                    {f'<span class="meta-field"><strong>Họ tên:</strong> ____________________</span>' if hdr.get("show_student_info") else ''}
                    {f'<span class="meta-field"><strong>Ngày:</strong> ____/____/20___</span>' if hdr.get("show_date") else ''}
                    <span class="meta-page">Trang {page_num} / {total_p}</span>
                </div>
            </header>
            """

        # Content Blocks based on template
        rows_html: list[str] = []

        if template_id in {"kanji_stroke", "kanji_compact"}:
            box_size = max(10, min(int(options.get("box_size") or (30 if template_id == "kanji_compact" else 36)), 120))
            margin_mm_map = {
                "minimal": 8,
                "ultra_compact": 8,
                "compact": 12,
                "standard": 20,
                "wide": 28,
            }
            margin_mm = margin_mm_map.get(margin_mode, 12)
            page_w_mm = 297 if orientation == "landscape" else 210
            usable_w_mm = page_w_mm - margin_mm
            top_component_w = int(usable_w_mm * 3.7795)
            full_row_boxes_count = max(1, int(top_component_w // (box_size - 1)))

            # Practice count in main row
            show_stroke = options.get("show_stroke_diagram", True)
            stroke_w = box_size if show_stroke else 0
            pill_w = max(40, min(130, int(box_size * 2.8)))
            left_info_w = box_size + stroke_w + pill_w + 28
            remaining_w = max(80, top_component_w - left_info_w)
            default_practice_cnt = max(1, int(remaining_w // (box_size - 1)) - trace_count)
            row_practice_count = max(1, int(options.get("practice_count") or default_practice_cnt))

            for item in items:
                is_filler = bool(item.get("is_blank_filler"))
                char = item.get("char", "") if not is_filler else ""
                stroke_svg = item.get("stroke_svg") or "" if not is_filler else ""
                reading = item.get("reading", "") if not is_filler else ""
                meaning = item.get("meaning", "") if not is_filler else ""
                source_word = item.get("source_word", "") if not is_filler else ""
                extra_blanks = int(item.get("extra_blank_rows") or options.get("extra_blank_rows") or 0)

                # Blank filler row: 100% full-width guideline grid boxes
                if is_filler or (not char and not reading and not meaning):
                    filler_boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(full_row_boxes_count)
                    )
                    extra_strips = ""
                    if extra_blanks > 0:
                        extra_strips = "".join(
                            f'<div class="kanji-extra-blank-strip">{filler_boxes}</div>'
                            for _ in range(min(3, extra_blanks))
                        )
                    row_html = f"""
                    <div class="kanji-item-wrapper">
                        <div class="kanji-extra-blank-strip">{filler_boxes}</div>
                        {extra_strips}
                    </div>
                    """
                    rows_html.append(row_html)
                    continue

                # 1. Reference Kanji Box (Chữ mẫu đầu tiên có màu)
                ref_char_color = str(options.get("reference_char_color") or "#e11d48").strip()
                stroke_color_mode = str(options.get("stroke_color_mode") or "monochrome").strip().lower()
                ref_box = _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=False, size=box_size, rounded=True, stroke_color="#0f172a", char_color=ref_char_color)

                # 2. Stroke Order Box (Chữ thứ 2: Nét vẽ)
                stroke_box = ""
                show_numbers = options.get("show_stroke_numbers", True) is not False
                if stroke_svg and options.get("show_stroke_diagram", True):
                    stroke_box_class = (
                        "flama-stroke-monochrome" if stroke_color_mode == "monochrome"
                        else "flama-stroke-same-ref" if stroke_color_mode == "same_as_reference"
                        else "flama-stroke-multicolor"
                    )
                    if not show_numbers:
                        stroke_box_class += " flama-hide-stroke-numbers"
                    stroke_box = f'<div class="stroke-diagram-wrapper {stroke_box_class}" style="width: {box_size}px; height: {box_size}px; min-width: {box_size}px; min-height: {box_size}px; max-width: {box_size}px; max-height: {box_size}px; overflow: hidden; --ref-char-color: {ref_char_color};">{stroke_svg}</div>'
                elif options.get("show_stroke_diagram", True):
                    fallback_stroke_color = ref_char_color if stroke_color_mode == "same_as_reference" else "#0f172a"
                    stroke_box = _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=False, size=box_size, rounded=True, stroke_color="#475569", char_color=fallback_stroke_color)

                # 3. Tracing Boxes
                trace_boxes = "".join(
                    _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                    for _ in range(trace_count)
                )

                # Labels (Reading / Meaning / Example)
                meta_labels: list[str] = []
                if reading and options.get("show_reading", False):
                    meta_labels.append(f'<span class="lbl-reading">{html.escape(reading)}</span>')
                if meaning and options.get("show_meaning", False):
                    meta_labels.append(f'<span class="lbl-meaning">{html.escape(meaning)}</span>')
                if source_word and source_word != char and options.get("show_source_word", False):
                    meta_labels.append(f'<span class="lbl-word">({html.escape(source_word)})</span>')

                meta_html = f'<div class="kanji-info-pill">{" ".join(meta_labels)}</div>' if meta_labels else ""

                # Adaptive blank practice count to fill row
                item_stroke_w = box_size if stroke_box else 0
                item_pill_w = max(40, min(130, int(box_size * 2.8))) if meta_labels else 0
                item_info_w = box_size + item_stroke_w + item_pill_w + (6 if item_stroke_w else 0) + (6 if item_pill_w else 0)
                item_remaining_w = max(40, top_component_w - item_info_w - 28)
                item_boxes_fit = max(1, int(item_remaining_w // (box_size - 1)))
                user_req_practice = options.get("practice_count")
                if user_req_practice:
                    item_practice_cnt = int(user_req_practice)
                else:
                    item_practice_cnt = max(1, item_boxes_fit - trace_count)
                if trace_count + item_practice_cnt < item_boxes_fit:
                    item_practice_cnt = max(item_practice_cnt, item_boxes_fit - trace_count)

                # 4. Blank Practice Boxes
                blank_boxes = "".join(
                    _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                    for _ in range(item_practice_cnt)
                )

                # Extra blank practice strips underneath
                extra_strips_html = ""
                if extra_blanks > 0:
                    extra_boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(full_row_boxes_count)
                    )
                    extra_strips_html = "".join(
                        f'<div class="kanji-extra-blank-strip">{extra_boxes}</div>'
                        for _ in range(min(3, extra_blanks))
                    )

                row_html = f"""
                <div class="kanji-item-wrapper">
                    <div class="kanji-practice-row">
                        <div class="kanji-info-col">
                            <div class="ref-box-wrap">{ref_box}</div>
                            {f'<div class="stroke-box-wrap">{stroke_box}</div>' if stroke_box else ''}
                            {meta_html}
                        </div>
                        <div class="kanji-grid-strip">
                            {trace_boxes}
                            {blank_boxes}
                        </div>
                    </div>
                    {extra_strips_html}
                </div>
                """
                rows_html.append(row_html)

        elif template_id == "kanji_compound":
            box_size = max(10, min(int(options.get("box_size") or 36), 120))
            margin_mm_map = {"minimal": 8, "ultra_compact": 8, "compact": 12, "standard": 20, "wide": 28}
            margin_mm = margin_mm_map.get(margin_mode, 12)
            page_w_mm = 297 if orientation == "landscape" else 210
            usable_w_mm = page_w_mm - margin_mm
            top_component_w = int(usable_w_mm * 3.7795)
            full_row_boxes_count = max(1, int(top_component_w // (box_size - 1)))
            ref_char_color = str(options.get("reference_char_color") or "#e11d48").strip()
            stroke_color_mode = str(options.get("stroke_color_mode") or "monochrome").strip().lower()
            show_numbers = options.get("show_stroke_numbers", True) is not False
            show_stroke = options.get("show_stroke_diagram", True)

            for item in items:
                is_filler = bool(item.get("is_blank_filler"))
                characters = item.get("characters") or []
                reading = item.get("reading", "") if not is_filler else ""
                meaning = item.get("meaning", "") if not is_filler else ""
                word = item.get("word", "") if not is_filler else ""
                extra_blanks = int(item.get("extra_blank_rows") or options.get("extra_blank_rows") or 0)

                if is_filler or not characters:
                    filler_boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(full_row_boxes_count)
                    )
                    extra_strips = ""
                    if extra_blanks > 0:
                        extra_strips = "".join(
                            f'<div class="kanji-extra-blank-strip">{filler_boxes}</div>'
                            for _ in range(min(3, extra_blanks))
                        )
                    rows_html.append(f"""
                    <div class="kanji-item-wrapper">
                        <div class="kanji-extra-blank-strip">{filler_boxes}</div>
                        {extra_strips}
                    </div>
                    """)
                    continue

                ref_boxes = "".join(
                    _render_kanji_grid_svg(c.get("char", ""), grid_style=grid_style, is_trace=False, size=box_size, rounded=True, stroke_color="#0f172a", char_color=ref_char_color)
                    for c in characters
                )

                meta_labels: list[str] = []
                show_reading = bool(reading and options.get("show_reading", False))
                show_meaning = bool(meaning and options.get("show_meaning", False))
                if show_reading:
                    meta_labels.append(f'<span class="lbl-reading">{html.escape(reading)}</span>')
                if show_meaning:
                    meta_labels.append(f'<span class="lbl-meaning">{html.escape(meaning)}</span>')

                pill_w = 0
                if meta_labels:
                    reading_len = len(reading) * 8 if show_reading else 0
                    meaning_len = len(meaning) * 6 if show_meaning else 0
                    max_text_w = max(reading_len, meaning_len)
                    max_pill_w = max(45, min(120, int(box_size * 2.6)))
                    pill_w = max(38, min(max_pill_w, int(max_text_w + 10)))
                    meta_html = f'<div class="kanji-info-pill" style="width:{pill_w}px;min-width:{pill_w}px;max-width:{pill_w}px;">{" ".join(meta_labels)}</div>'
                else:
                    meta_html = ""

                # --- Optimized adaptive per-row trace/practice unit & fill boxes count ---
                char_count = len(characters)
                ref_boxes_w = char_count * box_size + (2 * (char_count - 1) if char_count > 1 else 0)
                pill_gap = 8 if meta_labels else 0
                left_col_w = ref_boxes_w + pill_gap + pill_w
                gap_between_cols = 8
                row_overhead = 14  # 12px padding + 2px border

                right_avail_w = max(0, top_component_w - row_overhead - left_col_w - gap_between_cols)
                unit_gap = 4
                single_unit_w = char_count * (box_size - 1) + 3
                max_units = max(0, int((right_avail_w + unit_gap) // (single_unit_w + unit_gap))) if single_unit_w > 0 else 0

                requested_trace = trace_count
                requested_practice = max(1, int(options.get("practice_count") or 4))
                total_requested = requested_trace + requested_practice

                if max_units >= total_requested:
                    actual_trace = requested_trace
                    actual_practice = max_units - actual_trace
                elif max_units >= requested_trace + 1:
                    actual_trace = requested_trace
                    actual_practice = max_units - actual_trace
                else:
                    actual_trace = max(1, min(requested_trace, max_units - 1)) if max_units > 1 else min(1, max_units)
                    actual_practice = max(0, max_units - actual_trace)

                trace_groups = []
                for _ in range(actual_trace):
                    group_html = "".join(
                        _render_kanji_grid_svg(c.get("char", ""), grid_style=grid_style, is_trace=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for c in characters
                    )
                    trace_groups.append(f'<div class="compound-unit-block" style="display:flex;margin-right:4px;flex-shrink:0;">{group_html}</div>')
                trace_html = "".join(trace_groups)

                practice_groups = []
                for _ in range(actual_practice):
                    group_html = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(char_count)
                    )
                    practice_groups.append(f'<div class="compound-unit-block" style="display:flex;margin-right:4px;flex-shrink:0;">{group_html}</div>')
                practice_html = "".join(practice_groups)

                # Fill remaining fractional space with individual blank boxes
                total_units = actual_trace + actual_practice
                units_used_w = total_units * single_unit_w + (total_units - 1) * unit_gap if total_units > 0 else 0
                rem_after_units = max(0, right_avail_w - units_used_w)
                avail_for_fill = rem_after_units - (unit_gap if total_units > 0 else 0)
                fill_count = max(0, int((avail_for_fill - 3) // (box_size - 1)))
                fill_html = ""
                if fill_count > 0:
                    fill_boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(fill_count)
                    )
                    fill_html = f'<div class="compound-fill-boxes" style="display:flex;flex-shrink:0;">{fill_boxes}</div>'

                extra_strips_html = ""
                if extra_blanks > 0:
                    extra_boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(full_row_boxes_count)
                    )
                    extra_strips_html = "".join(
                        f'<div class="kanji-extra-blank-strip">{extra_boxes}</div>'
                        for _ in range(min(3, extra_blanks))
                    )

                row_html = f"""
                <div class="kanji-item-wrapper">
                    <div class="kanji-practice-row" style="display:flex;align-items:center;gap:8px;border:1px solid #e2e8f0;border-radius:6px;padding:6px;background:#ffffff;">
                        <div class="kanji-info-col" style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
                            <div class="ref-box-wrap" style="display:flex;gap:2px;">{ref_boxes}</div>
                            {meta_html}
                        </div>
                        <div class="kanji-grid-strip" style="display:flex;align-items:center;flex:1;overflow:hidden;gap:4px;">
                            {trace_html}
                            {practice_html}
                            {fill_html}
                        </div>
                    </div>
                    {extra_strips_html}
                </div>
                """
                rows_html.append(row_html)

        elif template_id == "kanji_step_by_step":
            box_size = max(10, min(int(options.get("box_size") or 34), 120))
            margin_mm_map = {"minimal": 8, "ultra_compact": 8, "compact": 12, "standard": 20, "wide": 28}
            margin_mm = margin_mm_map.get(margin_mode, 12)
            page_w_mm = 297 if orientation == "landscape" else 210
            usable_w_mm = page_w_mm - margin_mm
            top_component_w = int(usable_w_mm * 3.7795)
            full_row_boxes_count = max(1, int(top_component_w // (box_size - 1)))
            ref_char_color = str(options.get("reference_char_color") or "#e11d48").strip()

            for item in items:
                is_filler = bool(item.get("is_blank_filler"))
                char = item.get("char", "") if not is_filler else ""
                step_svgs = item.get("step_svgs") or []
                reading = item.get("reading", "") if not is_filler else ""
                meaning = item.get("meaning", "") if not is_filler else ""
                source_word = item.get("source_word", "") if not is_filler else ""
                total_strokes = int(item.get("total_strokes") or len(step_svgs))
                extra_blanks = int(item.get("extra_blank_rows") or options.get("extra_blank_rows") or 0)

                if is_filler or (not char and not reading and not meaning):
                    filler_boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(full_row_boxes_count)
                    )
                    extra_strips = ""
                    if extra_blanks > 0:
                        extra_strips = "".join(
                            f'<div class="kanji-extra-blank-strip">{filler_boxes}</div>'
                            for _ in range(min(3, extra_blanks))
                        )
                    rows_html.append(f"""
                    <div class="kanji-item-wrapper">
                        <div class="kanji-extra-blank-strip">{filler_boxes}</div>
                        {extra_strips}
                    </div>
                    """)
                    continue

                static_svg = item.get("static_svg")
                trace_svg = item.get("trace_svg")
                stroke_svg = item.get("stroke_svg")
                if not static_svg and stroke_svg:
                    static_svg = extract_static_kanji_svg(
                        stroke_svg,
                        char_color=ref_char_color,
                        is_trace=False,
                        grid_style=grid_style,
                        rounded=True,
                        stroke_color="#0f172a",
                    )
                if not trace_svg and stroke_svg:
                    trace_svg = extract_static_kanji_svg(
                        stroke_svg,
                        char_color="#cbd5e1",
                        is_trace=True,
                        grid_style=grid_style,
                        rounded=False,
                        stroke_color="#cbd5e1",
                    )

                if static_svg:
                    ref_box = f'<div class="stroke-static-box" style="width:{box_size}px;height:{box_size}px;min-width:{box_size}px;min-height:{box_size}px;max-width:{box_size}px;max-height:{box_size}px;overflow:hidden;border-radius:3px;">{static_svg}</div>'
                else:
                    ref_box = _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=False, size=box_size, rounded=True, stroke_color="#0f172a", char_color=ref_char_color)

                step_boxes_html = "".join(
                    f'<div class="stroke-step-box" style="width:{box_size}px;height:{box_size}px;min-width:{box_size}px;min-height:{box_size}px;max-width:{box_size}px;max-height:{box_size}px;border:1px solid #cbd5e1;border-radius:2px;overflow:hidden;background:#ffffff;display:inline-flex;align-items:center;justify-content:center;">{s_svg}</div>'
                    for s_svg in step_svgs
                )

                meta_labels: list[str] = []
                if reading and options.get("show_reading", False):
                    meta_labels.append(f'<span class="lbl-reading">{html.escape(reading)}</span>')
                if meaning and options.get("show_meaning", False):
                    meta_labels.append(f'<span class="lbl-meaning">{html.escape(meaning)}</span>')
                elif source_word and source_word != char and options.get("show_source_word", False):
                    meta_labels.append(f'<span class="lbl-word">({html.escape(source_word)})</span>')
                meta_html = f'<div class="kanji-info-pill">{" ".join(meta_labels)}</div>' if meta_labels else ""

                # --- Adaptive per-row step/trace/practice count ---
                pill_w = max(40, min(120, int(box_size * 2.5))) if meta_labels else 0
                info_w = box_size + (pill_w + 6 if meta_labels else 0)
                row_padding_gap = 10 + 6 + 2  # padding (5*2=10) + gap (6) + border (2)
                available_w = max(0, top_component_w - info_w - row_padding_gap)
                box_slot_w = box_size + 2  # box width + gap(2px)
                boxes_per_line = max(1, int((available_w + 2) // box_slot_w))

                num_steps = len(step_svgs)
                requested_trace = trace_count
                requested_practice = max(1, int(options.get("practice_count") or 2))

                available_in_line1 = boxes_per_line - num_steps - requested_trace
                if available_in_line1 >= 1:
                    actual_practice = available_in_line1
                else:
                    actual_practice = requested_practice

                if trace_svg:
                    trace_boxes = "".join(
                        f'<div class="stroke-step-box" style="width:{box_size}px;height:{box_size}px;min-width:{box_size}px;min-height:{box_size}px;max-width:{box_size}px;max-height:{box_size}px;border:1px solid #cbd5e1;border-radius:2px;overflow:hidden;background:#ffffff;display:inline-flex;align-items:center;justify-content:center;">{trace_svg}</div>'
                        for _ in range(requested_trace)
                    )
                else:
                    trace_boxes = "".join(
                        f'<div class="stroke-step-box" style="width:{box_size}px;height:{box_size}px;min-width:{box_size}px;min-height:{box_size}px;max-width:{box_size}px;max-height:{box_size}px;border:1px solid #cbd5e1;border-radius:2px;overflow:hidden;background:#ffffff;display:inline-flex;align-items:center;justify-content:center;">'
                        f'{_render_kanji_grid_svg(char, grid_style=grid_style, is_trace=True, size=box_size, rounded=False, stroke_color="#cbd5e1")}'
                        f'</div>'
                        for _ in range(requested_trace)
                    )

                blank_boxes = "".join(
                    f'<div class="stroke-step-box" style="width:{box_size}px;height:{box_size}px;min-width:{box_size}px;min-height:{box_size}px;max-width:{box_size}px;max-height:{box_size}px;border:1px solid #cbd5e1;border-radius:2px;overflow:hidden;background:#ffffff;display:inline-flex;align-items:center;justify-content:center;">'
                    f'{_render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")}'
                    f'</div>'
                    for _ in range(actual_practice)
                )

                extra_strips_html = ""
                if extra_blanks > 0:
                    extra_boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(full_row_boxes_count)
                    )
                    extra_strips_html = "".join(
                        f'<div class="kanji-extra-blank-strip">{extra_boxes}</div>'
                        for _ in range(min(3, extra_blanks))
                    )

                row_html = f"""
                <div class="kanji-item-wrapper">
                    <div class="kanji-practice-row" style="display:flex;align-items:flex-start;gap:6px;border:1px solid #e2e8f0;border-radius:6px;padding:5px;background:#ffffff;">
                        <div class="kanji-info-col" style="display:flex;align-items:center;gap:6px;flex-shrink:0;">
                            <div class="ref-box-wrap">{ref_box}</div>
                            {meta_html}
                        </div>
                        <div class="kanji-step-strip" style="display:flex;align-items:center;flex:1;flex-wrap:wrap;gap:2px;">
                            {step_boxes_html}
                            {trace_boxes}
                            {blank_boxes}
                        </div>
                    </div>
                    {extra_strips_html}
                </div>
                """
                rows_html.append(row_html)

        elif template_id == "vocab_writing":
            show_reading = bool(options.get("show_reading", True))
            show_meaning = bool(options.get("show_meaning", True))
            practice_type = str(options.get("practice_type") or "boxes").strip().lower()
            practice_boxes_cnt = max(1, int(options.get("practice_boxes_count", 6 if orientation == "portrait" else 10)))

            for item in items:
                word = item.get("word", "")
                reading = item.get("reading", "")
                meaning = item.get("meaning", "")

                if practice_type == "lines":
                    practice_html = '<div class="vocab-lines-strip"></div>'
                elif practice_type == "grid":
                    boxes = "".join(
                        _render_kanji_grid_svg("", grid_style="cross", is_blank=True, size=24, rounded=False, stroke_color="#94a3b8")
                        for _ in range(practice_boxes_cnt)
                    )
                    practice_html = f'<div class="vocab-grid-strip">{boxes}</div>'
                else:
                    boxes_html = "".join(
                        '<div class="vocab-write-box"></div>'
                        for _ in range(practice_boxes_cnt)
                    )
                    practice_html = f'<div class="vocab-boxes-strip">{boxes_html}</div>'

                reading_td = f'<td class="col-reading">{html.escape(reading)}</td>' if show_reading else ""
                meaning_td = f'<td class="col-meaning">{html.escape(meaning)}</td>' if show_meaning else ""

                row_html = f"""
                <tr class="vocab-row">
                    <td class="col-word">{html.escape(word)}</td>
                    {reading_td}
                    {meaning_td}
                    <td class="col-practice">{practice_html}</td>
                </tr>
                """
                rows_html.append(row_html)

        elif template_id == "vocab_recall":
            show_reading_hint = bool(options.get("show_reading_hint", True))
            show_word_length_hint = bool(options.get("show_word_length_hint", False))
            recall_answer_style = str(options.get("recall_answer_style") or ("boxes" if show_word_length_hint else "line")).strip().lower()

            for item in items:
                reading = item.get("reading", "")
                meaning = item.get("meaning", "")
                word = item.get("word") or ""
                word_len = item.get("word_length") or len(word) or 4

                if recall_answer_style == "boxes" or show_word_length_hint:
                    boxes_html = "".join(
                        '<div class="recall-box"></div>'
                        for _ in range(max(1, min(12, word_len)))
                    )
                    answer_html = f'<div class="recall-boxes-strip">{boxes_html}</div>'
                else:
                    answer_html = '<div class="recall-answer-line"></div>'

                reading_hint_html = f'<div class="prompt-reading">{html.escape(reading)}</div>' if reading and show_reading_hint else ''

                row_html = f"""
                <tr class="recall-row">
                    <td class="col-prompt">
                        <div class="prompt-meaning">{html.escape(meaning)}</div>
                        {reading_hint_html}
                    </td>
                    <td class="col-answer">
                        {answer_html}
                    </td>
                </tr>
                """
                rows_html.append(row_html)

        elif template_id == "deck_table":
            custom_cols = preview_data.get("field_mapping", {}).get("custom_columns") or []
            if isinstance(custom_cols, str):
                custom_cols = [c.strip() for c in custom_cols.split(",") if c.strip()]
            if not isinstance(custom_cols, list):
                custom_cols = []

            col_widths = options.get("column_widths") or {}
            has_aux = options.get("auxiliary_column_enabled") if options.get("auxiliary_column_enabled") is not None else options.get("include_practice_column", True)
            aux_title = options.get("auxiliary_column_title") or options.get("practice_column_label") or "Ghi chú / Luyện viết"
            aux_type = str(options.get("auxiliary_column_type") or "dashed_line")
            aux_width = options.get("auxiliary_column_width")
            aux_boxes_cnt = int(options.get("auxiliary_column_boxes_count") or 4)

            def _render_aux_td() -> str:
                if aux_type == "grid_boxes":
                    boxes = "".join(
                        _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=22, rounded=False, stroke_color="#cbd5e1")
                        for _ in range(aux_boxes_cnt)
                    )
                    return f'<td class="col-aux-cell" style="text-align: center;"><div class="aux-boxes-strip">{boxes}</div></td>'
                elif aux_type == "checkboxes":
                    return '<td class="col-aux-cell"><div class="aux-checkboxes"><span><i class="cbox"></i> 1</span><span><i class="cbox"></i> 2</span><span><i class="cbox"></i> 3</span></div></td>'
                elif aux_type == "double_line":
                    return '<td class="col-aux-cell"><div class="aux-double-line"><div></div><div></div></div></td>'
                elif aux_type == "blank":
                    return '<td class="col-aux-cell"><div class="aux-blank" style="min-height: 20px;"></div></td>'
                # Default: dashed line
                return '<td class="col-aux-cell"><div class="table-write-line"></div></td>'

            for item in items:
                row_data = item.get("data") or {}
                cols_td = "".join(
                    f'<td class="table-cell">{html.escape(str(row_data.get(c, "")))}</td>'
                    for c in custom_cols
                )
                practice_td = _render_aux_td() if has_aux else ""

                rows_html.append(f'<tr class="deck-table-row">{cols_td}{practice_td}</tr>')

        elif template_id == "sentence_writing":
            lines_cnt = max(1, min(10, int(options.get("writing_lines_count") or 3)))
            line_style = str(options.get("writing_line_style") or "dashed")
            border_style = "dashed" if line_style == "dashed" else "solid"

            for s_idx, item in enumerate(items):
                sentence = item.get("sentence", "")
                reading = item.get("reading", "")
                meaning = item.get("meaning", "")

                lines_html = "".join(
                    f'<div class="sentence-write-line" style="border-bottom-style: {border_style};"></div>'
                    for _ in range(lines_cnt)
                )

                reading_html = f'<div class="sentence-reading">{html.escape(reading)}</div>' if reading and options.get("show_sample_reading", True) else ''
                meaning_html = f'<div class="sentence-meaning">{html.escape(meaning)}</div>' if meaning and options.get("show_sample_meaning", True) else ''
                sentence_html = f'<div class="sentence-text">{html.escape(sentence)}</div>' if sentence and options.get("show_sample_sentence", True) else ''

                rows_html.append(f"""
                <div class="sentence-card">
                    <div class="sentence-header">
                        <span class="sentence-num">#{s_idx + 1}</span>
                        <div class="sentence-content">
                            {sentence_html}
                            {reading_html}
                            {meaning_html}
                        </div>
                    </div>
                    <div class="sentence-lines-wrap">
                        {lines_html}
                    </div>
                </div>
                """)

        elif template_id == "grammar_practice":
            lines_cnt = max(1, min(10, int(options.get("writing_lines_count") or 3)))
            line_style = str(options.get("writing_line_style") or "dashed")
            border_style = "dashed" if line_style == "dashed" else "solid"
            prompt_text = str(options.get("exercise_prompt") or "Hãy đặt câu hoàn chỉnh sử dụng cấu trúc / từ vựng trên:").strip()

            top_prompt_html = f'<div class="grammar-global-prompt"><strong>Yêu cầu:</strong> {html.escape(prompt_text)}</div>' if prompt_text else ''

            for g_idx, item in enumerate(items):
                grammar = item.get("grammar_point", "")
                usage = item.get("meaning_usage", "")
                example = item.get("example", "")

                lines_html = "".join(
                    f'<div class="sentence-write-line" style="border-bottom-style: {border_style};"></div>'
                    for _ in range(lines_cnt)
                )

                usage_html = f'<div class="grammar-usage">{html.escape(usage)}</div>' if usage and options.get("show_explanation", True) else ''
                example_html = f'<div class="grammar-example"><em>Ví dụ:</em> {html.escape(example)}</div>' if example and options.get("show_example_hint", True) else ''

                rows_html.append(f"""
                <div class="grammar-card">
                    <div class="grammar-header">
                        <div class="grammar-badge">Cấu trúc #{g_idx + 1}</div>
                        <div class="grammar-title">{html.escape(grammar)}</div>
                        {usage_html}
                        {example_html}
                    </div>
                    <div class="sentence-lines-wrap">
                        {lines_html}
                    </div>
                </div>
                """)

        elif template_id == "genkouyoushi":
            grid_color = str(options.get("grid_color") or "#475569").strip()
            box_style = str(options.get("box_style") or "square").strip().lower()
            has_spacer = bool(options.get("has_spacer_band", True))
            spacer_height = max(4, min(24, int(options.get("spacer_height") or 10)))

            for r_idx, item in enumerate(items):
                cells = item.get("cells") or []
                cells_html = []
                for cell in cells:
                    char = str(cell.get("char") or "")
                    is_trace = bool(cell.get("is_trace"))
                    is_blank = bool(cell.get("is_blank")) or not char

                    cell_svg = _render_kanji_grid_svg(
                        char if not is_blank else "",
                        grid_style=box_style,
                        is_trace=is_trace,
                        is_blank=is_blank,
                        size=36,
                        rounded=False,
                        stroke_color=grid_color,
                        char_color="#0f172a" if not is_trace else "#94a3b8",
                    )
                    cells_html.append(f'<div class="genkou-cell">{cell_svg}</div>')

                spacer_html = (
                    f'<div class="genkou-spacer-band" style="height: {spacer_height}px; border-color: {grid_color};"></div>'
                    if (has_spacer and r_idx < len(items) - 1)
                    else ""
                )

                rows_html.append(f"""
                <div class="genkou-row-wrap">
                    <div class="genkou-grid-row">{"".join(cells_html)}</div>
                    {spacer_html}
                </div>
                """)

        # Combine page content
        body_content = ""
        if template_id in {"kanji_stroke", "kanji_compact", "kanji_compound", "kanji_step_by_step"}:
            body_content = f'<div class="kanji-sheet-body">{"".join(rows_html)}</div>'
        elif template_id == "genkouyoushi":
            body_content = f'<div class="genkou-sheet-body">{"".join(rows_html)}</div>'
        elif template_id == "sentence_writing":
            body_content = f'<div class="sentences-sheet-body">{"".join(rows_html)}</div>'
        elif template_id == "grammar_practice":
            body_content = f'{top_prompt_html}<div class="sentences-sheet-body">{"".join(rows_html)}</div>'
        elif template_id == "vocab_writing":
            show_reading = bool(options.get("show_reading", True))
            show_meaning = bool(options.get("show_meaning", True))
            if not show_reading and not show_meaning:
                w_word, w_read, w_mean, w_prac = "35%", "", "", "65%"
            elif not show_reading:
                w_word, w_read, w_mean, w_prac = "28%", "", "32%", "40%"
            elif not show_meaning:
                w_word, w_read, w_mean, w_prac = "28%", "32%", "", "40%"
            else:
                w_word, w_read, w_mean, w_prac = "22%", "20%", "28%", "30%"

            read_th = f'<th style="width: {w_read};">Cách đọc</th>' if show_reading else ''
            mean_th = f'<th style="width: {w_mean};">Ý nghĩa</th>' if show_meaning else ''

            body_content = f"""
            <table class="vocab-table">
                <thead>
                    <tr>
                        <th style="width: {w_word};">Từ vựng</th>
                        {read_th}
                        {mean_th}
                        <th style="width: {w_prac};">Luyện viết</th>
                    </tr>
                </thead>
                <tbody>{"".join(rows_html)}</tbody>
            </table>
            """
        elif template_id == "vocab_recall":
            body_content = f"""
            <table class="recall-table">
                <thead>
                    <tr>
                        <th style="width: 50%;">Gợi ý (Nghĩa / Âm đọc)</th>
                        <th style="width: 50%;">Từ vựng mục tiêu (Tự nhớ & Viết lại)</th>
                    </tr>
                </thead>
                <tbody>{"".join(rows_html)}</tbody>
            </table>
            """
        elif template_id == "deck_table":
            custom_cols = preview_data.get("field_mapping", {}).get("custom_columns") or []
            if isinstance(custom_cols, str):
                custom_cols = [c.strip() for c in custom_cols.split(",") if c.strip()]
            if not isinstance(custom_cols, list):
                custom_cols = []

            col_widths = options.get("column_widths") or {}
            has_aux = options.get("auxiliary_column_enabled") if options.get("auxiliary_column_enabled") is not None else options.get("include_practice_column", True)
            aux_title = options.get("auxiliary_column_title") or options.get("practice_column_label") or "Ghi chú / Luyện viết"
            aux_width = options.get("auxiliary_column_width")

            if not custom_cols:
                body_content = """
                <div style="border: 2px dashed #cbd5e1; border-radius: 8px; padding: 40px; text-align: center; color: #64748b; font-size: 13px; margin: 30px 0;">
                    <strong style="font-size: 15px; color: #334155;">Chưa chọn cột nào để hiển thị</strong>
                    <p style="margin: 8px 0 0 0; font-size: 12px; color: #94a3b8;">Vui lòng chọn các trường trong cấu hình để hiển thị bảng dữ liệu.</p>
                </div>
                """
            else:
                headers_th_list = []
                for c in custom_cols:
                    cw = col_widths.get(c)
                    w_style = f' style="width: {cw}%;"' if isinstance(cw, (int, float)) else (f' style="width: {cw};"' if cw else '')
                    headers_th_list.append(f'<th{w_style}>{html.escape(c)}</th>')

                headers_th = "".join(headers_th_list)
                if has_aux:
                    aux_w_style = f' style="width: {aux_width}%;"' if isinstance(aux_width, (int, float)) else (f' style="width: {aux_width};"' if aux_width else '')
                    practice_th = f'<th{aux_w_style}>{html.escape(aux_title)}</th>'
                else:
                    practice_th = ""

                body_content = f"""
                <table class="deck-data-table" style="table-layout: fixed; width: 100%;">
                    <thead>
                        <tr>{headers_th}{practice_th}</tr>
                    </thead>
                    <tbody>{"".join(rows_html)}</tbody>
                </table>
                """

        # Watermark overlay (Mandatory anti-theft diagonal pattern)
        watermark_text = str(options.get("watermark_text") or "flama.app").strip() or "flama.app"
        watermark_opacity = max(0.015, min(0.15, float(options.get("watermark_opacity") or 0.04)))
        watermark_layout = str(options.get("watermark_layout") or "diagonal_grid")

        if watermark_layout == "margin_bounds":
            watermark_html = f"""
            <div class="watermark-margin-overlay" style="opacity: {watermark_opacity * 1.5};">
                <div class="wm-margin-left"><span>{html.escape(watermark_text.upper())} &bull; FLAMA WORKSHEET &bull; {html.escape(watermark_text.upper())}</span></div>
                <div class="wm-margin-right"><span>{html.escape(watermark_text.upper())} &bull; FLAMA WORKSHEET &bull; {html.escape(watermark_text.upper())}</span></div>
            </div>
            """
        else:
            wm_rows = []
            for r_i in range(8):
                offset_style = "margin-left: -50px;" if r_i % 2 == 1 else ""
                wm_tokens = " &nbsp;&nbsp;&nbsp;&nbsp;&bull;&nbsp;&nbsp;&nbsp;&nbsp; ".join([html.escape(watermark_text.upper())] * 6)
                wm_rows.append(f'<div class="watermark-row" style="{offset_style}">{wm_tokens}</div>')
            watermark_html = f'<div class="watermark-overlay" style="opacity: {watermark_opacity};">{"".join(wm_rows)}</div>'

        prompt_text = str(options.get("exercise_prompt") or "").strip()
        prompt_html = ""
        if prompt_text and template_id in {"grammar_practice", "sentence_writing"}:
            prompt_html = f"""
            <div class="exercise-prompt-banner">
                <div class="prompt-icon">📝</div>
                <div class="prompt-body">
                    <span class="prompt-label">Đề bài / Yêu cầu:</span>
                    <span class="prompt-text">{html.escape(prompt_text)}</span>
                </div>
            </div>
            """

        if template_id == "genkouyoushi":
            brand_lbl = html.escape(str(options.get("footer_brand_label") or "Flama (400格)"))
            date_style = str(options.get("footer_date_format") or "chinese").strip().lower()
            date_lbl = "年 &nbsp;&nbsp;&nbsp;&nbsp; 月 &nbsp;&nbsp;&nbsp;&nbsp; 日" if date_style == "chinese" else ("Ngày ...... Tháng ...... Năm 20......" if date_style == "vietnamese" else "")
            sheet_footer_html = f"""
            <footer class="genkou-footer">
                <span class="genkou-footer-left">{brand_lbl}</span>
                <span class="genkou-footer-mid">Trang {page_num} / {total_p}</span>
                <span class="genkou-footer-right">{date_lbl}</span>
            </footer>
            """
        else:
            if current_url:
                footer_link_html = f'<a href="{html.escape(current_url)}" target="_blank" rel="noopener noreferrer" style="color: inherit; text-decoration: none;">{html.escape(current_domain)}</a>'
            else:
                footer_link_html = html.escape(current_domain)

            sheet_footer_html = f"""
            <footer class="sheet-footer">
                <span>Flama Worksheet Generator &bull; {footer_link_html}</span>
                <span>Trang {page_num} / {total_p}</span>
            </footer>
            """

        page_markup = f"""
        <div class="sheet-page">
            {watermark_html}
            <div class="sheet-content">
                {header_html}
                {prompt_html}
                <main class="sheet-main">{body_content}</main>
                {sheet_footer_html}
            </div>
        </div>
        """
        pages_html.append(page_markup)

    # Master Standalone HTML Document
    full_html = f"""<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{html.escape(options.get("header_title") or "Flama Worksheet")}</title>
    <style>
        @page {{
            size: {page_size_css};
            margin: 0;
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: "Segoe UI", -apple-system, BlinkMacSystemFont, Roboto, "Noto Sans", "Noto Sans JP", "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", sans-serif;
            color: #0f172a;
            background-color: #f8fafc;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
        }}
        @media screen {{
            body {{
                padding: 24px;
                display: flex;
                flex-direction: column;
                align-items: center;
                gap: 24px;
            }}
            .sheet-page {{
                background: #ffffff;
                box-shadow: 0 4px 20px rgba(0, 0, 0, 0.08);
                width: {'297mm' if orientation == 'landscape' else '210mm'};
                min-height: {'210mm' if orientation == 'landscape' else '297mm'};
                max-height: {'210mm' if orientation == 'landscape' else '297mm'};
                box-sizing: border-box;
                padding: {margin_css};
                border-radius: 4px;
                position: relative;
                overflow: hidden;
                display: flex;
                flex-direction: column;
                justify-content: space-between;
            }}
            .screen-toolbar {{
                position: sticky;
                top: 12px;
                z-index: 100;
                display: flex;
                gap: 12px;
                background: #1e293b;
                color: #ffffff;
                padding: 10px 20px;
                border-radius: 9999px;
                box-shadow: 0 4px 14px rgba(0,0,0,0.15);
            }}
            .screen-btn {{
                background: #ea580c;
                color: #ffffff;
                border: none;
                padding: 6px 16px;
                border-radius: 9999px;
                font-weight: 600;
                cursor: pointer;
                font-size: 13px;
            }}
            .screen-btn:hover {{
                background: #c2410c;
            }}
            @media (max-width: 820px) {{
                body {{
                    padding: 12px 6px;
                    gap: 16px;
                    overflow-x: auto;
                }}
                .screen-toolbar {{
                    width: calc(100% - 16px);
                    max-width: 420px;
                    justify-content: space-between;
                    align-items: center;
                    padding: 8px 16px;
                    font-size: 12px;
                }}
                .screen-btn {{
                    padding: 6px 14px;
                    font-size: 12px;
                }}
                .sheet-page {{
                    max-width: 100%;
                    overflow-x: auto;
                }}
            }}
        }}
        @media print {{
            * {{
                -webkit-print-color-adjust: exact !important;
                print-color-adjust: exact !important;
                color-adjust: exact !important;
            }}
            html, body {{
                width: {'297mm' if orientation == 'landscape' else '210mm'};
                height: {'210mm' if orientation == 'landscape' else '297mm'};
                margin: 0 !important;
                padding: 0 !important;
                background: transparent !important;
            }}
            .screen-toolbar {{
                display: none !important;
            }}
            .sheet-page {{
                background: #ffffff !important;
                width: {'297mm' if orientation == 'landscape' else '210mm'} !important;
                min-height: {'210mm' if orientation == 'landscape' else '297mm'} !important;
                max-height: {'210mm' if orientation == 'landscape' else '297mm'} !important;
                height: {'210mm' if orientation == 'landscape' else '297mm'} !important;
                box-sizing: border-box !important;
                padding: {margin_css} !important;
                page-break-after: always !important;
                break-after: page !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: space-between !important;
                overflow: hidden !important;
                position: relative !important;
            }}
            path[id^="make-me-a-hanzi-animation"] {{
                animation: none !important;
                stroke-dashoffset: 0 !important;
            }}
        }}

        /* Header */
        .sheet-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 2px solid #0f172a;
            padding-bottom: 6px;
            margin-bottom: 8px;
        }}
        .sheet-title {{
            font-size: 15px;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: -0.01em;
            line-height: 1.25;
        }}
        .sheet-subtitle {{
            font-size: 10px;
            color: #64748b;
            margin-top: 2px;
            line-height: 1.25;
        }}
        .header-meta {{
            display: flex;
            gap: 12px;
            font-size: 10px;
            color: #334155;
            white-space: nowrap;
        }}
        .header-qr-wrap {{
            position: relative;
            width: 44px;
            height: 0;
            flex-shrink: 0;
        }}
        .header-qr-code {{
            position: absolute;
            bottom: 0;
            left: -10px;
            width: 54px;
            height: 54px;
            padding: 4px;
            background: #ffffff;
            border: 1px solid #cbd5e1;
            border-radius: 4px;
            box-shadow: 0 1px 2px rgba(0, 0, 0, 0.05);
            flex-shrink: 0;
            display: inline-flex;
            align-items: center;
            justify-content: center;
            text-decoration: none;
            box-sizing: border-box;
            z-index: 20;
        }}
        .header-qr-code svg {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .meta-field strong {{
            color: #0f172a;
        }}

        /* Footer */
        .sheet-footer {{
            display: flex;
            justify-content: space-between;
            font-size: 9px;
            color: #94a3b8;
            margin-top: 8px;
            border-top: 1px solid #e2e8f0;
            padding-top: 4px;
        }}

        /* Kanji Rows */
        .kanji-sheet-body {{
            display: flex;
            flex-direction: column;
            gap: 4px;
        }}
        .kanji-practice-row {{
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 3px 6px;
            background: #ffffff;
            page-break-inside: avoid;
            break-inside: avoid;
            display: flex;
            align-items: center;
            justify-content: space-between;
            gap: 8px;
        }}
        .kanji-info-col {{
            display: flex;
            align-items: center;
            gap: 6px;
            flex-shrink: 0;
        }}
        .ref-box-wrap, .stroke-box-wrap {{
            display: flex;
            align-items: center;
        }}
        .stroke-diagram-wrapper {{
            box-sizing: border-box !important;
            overflow: hidden !important;
            flex-shrink: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border: 1px solid #334155;
            border-radius: 3px;
            background: #ffffff;
            padding: 2px;
        }}
        .stroke-diagram-wrapper svg,
        .stroke-step-box svg,
        .stroke-static-box svg,
        .stroke-trace-box svg,
        .flama-static-kanji-box,
        .flama-stroke-step {{
            width: 100% !important;
            height: 100% !important;
            max-width: 100% !important;
            max-height: 100% !important;
            display: block !important;
        }}
        .stroke-static-box,
        .stroke-trace-box {{
            box-sizing: border-box !important;
            overflow: hidden !important;
            flex-shrink: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            background: #ffffff;
        }}
        .flama-kvg-num {{
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
            font-size: 12px !important;
            font-weight: 800 !important;
            paint-order: stroke fill !important;
            stroke: #ffffff !important;
            stroke-width: 2px !important;
        }}
        .flama-mmah-numbers text,
        .flama-stroke-num {{
            font-family: ui-monospace, SFMono-Regular, Menlo, monospace !important;
            font-size: 56px !important;
            font-weight: 900 !important;
            paint-order: stroke fill !important;
            stroke: #ffffff !important;
            stroke-width: 10px !important;
        }}
        .stroke-diagram-wrapper .flama-grid-box rect {{
            stroke-width: 3 !important;
        }}
        .stroke-diagram-wrapper .flama-grid-box path {{
            stroke-width: 2.5 !important;
            stroke-dasharray: 10,10 !important;
        }}
        .stroke-step-box {{
            box-sizing: border-box !important;
            overflow: hidden !important;
            flex-shrink: 0 !important;
            display: flex !important;
            align-items: center !important;
            justify-content: center !important;
            border: 1px solid #cbd5e1;
            border-radius: 2px;
            background: #ffffff;
        }}
        .stroke-step-box svg,
        .flama-stroke-step {{
            width: 100% !important;
            height: 100% !important;
            max-width: 100% !important;
            max-height: 100% !important;
            display: block !important;
        }}
        .compound-unit-block,
        .compound-fill-boxes {{
            display: inline-flex;
            align-items: center;
            border: 1px solid #334155;
            border-radius: 3px;
            overflow: hidden;
            background: #ffffff;
            margin-right: 4px;
            flex-shrink: 0;
        }}
        .compound-unit-block svg,
        .compound-fill-boxes svg {{
            margin-left: -1px;
            display: block;
        }}
        .compound-unit-block svg:first-child,
        .compound-fill-boxes svg:first-child {{
            margin-left: 0;
        }}
        .lbl-strokes {{
            font-size: 9px;
            font-weight: 700;
            color: #e11d48;
        }}
        .flama-hide-stroke-numbers .flama-kvg-num,
        .flama-hide-stroke-numbers .flama-mmah-numbers,
        .flama-hide-stroke-numbers .flama-stroke-num {{
            display: none !important;
        }}
        .flama-stroke-monochrome .flama-stroke-char {{
            --flama-stroke-c1: #0f172a !important;
            --flama-stroke-c2: #0f172a !important;
            --flama-stroke-c3: #0f172a !important;
            --flama-stroke-c4: #0f172a !important;
            --flama-stroke-c5: #0f172a !important;
            --flama-stroke-c6: #0f172a !important;
            --flama-stroke-c7: #0f172a !important;
            --flama-stroke-c8: #0f172a !important;
            --flama-stroke-c9: #0f172a !important;
            --flama-stroke-c10: #0f172a !important;
        }}
        .flama-stroke-monochrome .flama-kvg-num,
        .flama-stroke-monochrome .flama-mmah-numbers text,
        .flama-stroke-monochrome .flama-stroke-num {{
            fill: #0f172a !important;
            stroke: #ffffff !important;
        }}
        .flama-stroke-monochrome .flama-kvg-stroke {{
            stroke: #0f172a !important;
        }}
        .flama-stroke-monochrome path[id^="make-me-a-hanzi-animation"] {{
            stroke: #0f172a !important;
        }}
        .flama-stroke-same-ref .flama-kvg-stroke {{
            stroke: var(--ref-char-color, #e11d48) !important;
        }}
        .flama-stroke-same-ref .flama-kvg-num,
        .flama-stroke-same-ref .flama-mmah-numbers text,
        .flama-stroke-same-ref .flama-stroke-num {{
            fill: var(--ref-char-color, #e11d48) !important;
            stroke: #ffffff !important;
        }}
        .flama-stroke-same-ref path[id^="make-me-a-hanzi-animation"] {{
            stroke: var(--ref-char-color, #e11d48) !important;
        }}
        .kanji-info-pill {{
            display: flex;
            flex-direction: column;
            justify-content: center;
            max-width: 120px;
            font-size: 10px;
            color: #334155;
            line-height: 1.15;
            padding-left: 2px;
            overflow: hidden;
        }}
        .lbl-reading {{
            font-weight: 600;
            color: #0f172a;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .lbl-meaning {{
            font-size: 9px;
            color: #64748b;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
        }}
        .lbl-word {{
            font-size: 9px;
            color: #94a3b8;
            font-style: italic;
        }}
        .kanji-item-wrapper {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .kanji-extra-blank-strip {{
            display: inline-flex;
            border: 1px solid #334155;
            border-radius: 3px;
            overflow: hidden;
            background: #ffffff;
            width: fit-content;
            max-width: 100%;
        }}
        .kanji-extra-blank-strip svg {{
            margin-left: -1px;
            display: block;
            flex-shrink: 0;
        }}
        .kanji-extra-blank-strip svg:first-child {{
            margin-left: 0;
        }}
        .kanji-grid-strip {{
            display: inline-flex;
            border: 1px solid #334155;
            border-radius: 3px;
            overflow: hidden;
            background: #ffffff;
            width: fit-content;
            flex-shrink: 0;
            margin-left: auto;
        }}
        .kanji-grid-strip svg {{
            margin-left: -1px;
            display: block;
        }}
        .kanji-grid-strip svg:first-child {{
            margin-left: 0;
        }}

        /* Tables (Vocab & Recall & Deck) */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 11px;
        }}
        th {{
            background: #f1f5f9;
            color: #1e293b;
            font-weight: 600;
            padding: 4px 6px;
            border: 1px solid #94a3b8;
            text-align: left;
        }}
        td {{
            padding: 4px 6px;
            border: 1px solid #cbd5e1;
            vertical-align: middle;
        }}
        .col-word {{
            font-weight: 600;
            font-size: 13px;
            color: #0f172a;
        }}
        .vocab-boxes-strip {{
            display: flex;
            border: 1px solid #64748b;
            border-radius: 2px;
            overflow: hidden;
            width: fit-content;
        }}
        .vocab-write-box {{
            width: 24px;
            height: 24px;
            border-right: 1px solid #cbd5e1;
            background: #ffffff;
        }}
        .vocab-write-box:last-child {{
            border-right: none;
        }}
        .recall-answer-line, .table-write-line, .vocab-lines-strip {{
            width: 100%;
            min-height: 24px;
            border-bottom: 1px dashed #94a3b8;
        }}
        .vocab-grid-strip {{
            display: inline-flex;
            border: 1px solid #475569;
            border-radius: 2px;
            overflow: hidden;
            background: #ffffff;
        }}
        .vocab-grid-strip svg {{
            margin-left: -1px;
            display: block;
        }}
        .vocab-grid-strip svg:first-child {{
            margin-left: 0;
        }}
        .recall-boxes-strip {{
            display: flex;
            gap: 4px;
            align-items: center;
        }}
        .recall-box {{
            width: 22px;
            height: 22px;
            border: 1px solid #94a3b8;
            border-radius: 2px;
            background: #ffffff;
        }}
        .aux-boxes-strip {{
            display: inline-flex;
            border: 1px solid #475569;
            border-radius: 2px;
            overflow: hidden;
            background: #ffffff;
            margin: 0 auto;
        }}
        .aux-boxes-strip svg {{
            margin-left: -1px;
            display: block;
        }}
        .aux-boxes-strip svg:first-child {{
            margin-left: 0;
        }}
        .aux-checkboxes {{
            display: flex;
            align-items: center;
            justify-content: space-around;
            font-size: 10px;
            color: #64748b;
        }}
        .aux-checkboxes .cbox {{
            display: inline-block;
            width: 11px;
            height: 11px;
            border: 1px solid #94a3b8;
            border-radius: 2px;
            background: #ffffff;
            vertical-align: middle;
            margin-right: 3px;
        }}
        .aux-double-line {{
            display: flex;
            flex-direction: column;
            gap: 6px;
            padding: 2px 0;
            width: 100%;
        }}
        .aux-double-line div {{
            border-bottom: 1px solid #cbd5e1;
            height: 8px;
            width: 100%;
        }}
        .prompt-meaning {{
            font-weight: 600;
            color: #0f172a;
        }}
        .prompt-reading {{
            font-size: 11px;
            color: #64748b;
            margin-top: 2px;
        }}

        /* Watermark */
        .sheet-page {{
            position: relative;
            overflow: hidden;
        }}
        .sheet-content {{
            position: relative;
            z-index: 1;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            min-height: 100%;
        }}
        .watermark-overlay {{
            position: absolute;
            top: -25%;
            left: -25%;
            width: 150%;
            height: 150%;
            pointer-events: none;
            user-select: none;
            z-index: 50;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            overflow: hidden;
            padding: 20px 0;
        }}
        .watermark-row {{
            display: flex;
            justify-content: space-around;
            white-space: nowrap;
            transform: rotate(-28deg);
            font-family: 'Hiragino Kaku Gothic ProN', 'Yu Gothic', 'Arial', sans-serif;
            font-size: 13px;
            font-weight: 500;
            color: #334155;
            letter-spacing: 6px;
        }}
        .watermark-margin-overlay {{
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            bottom: 0;
            pointer-events: none;
            user-select: none;
            z-index: 50;
            display: flex;
            justify-content: space-between;
            overflow: hidden;
            padding: 4px;
        }}
        .wm-margin-left, .wm-margin-right {{
            display: flex;
            flex-direction: column;
            justify-content: space-around;
            font-size: 9px;
            font-weight: 600;
            letter-spacing: 3px;
            color: #475569;
            writing-mode: vertical-rl;
        }}
        .wm-margin-left {{
            transform: rotate(180deg);
        }}

        /* Exercise Prompt Banner at Page Top */
        .exercise-prompt-banner {{
            background: #fef3c7;
            border: 1px solid #fde68a;
            border-radius: 6px;
            padding: 6px 12px;
            margin-bottom: 10px;
            display: flex;
            align-items: flex-start;
            gap: 8px;
            page-break-inside: avoid;
        }}
        .prompt-icon {{
            font-size: 14px;
            line-height: 1;
        }}
        .prompt-label {{
            font-size: 10px;
            font-weight: bold;
            text-transform: uppercase;
            color: #92400e;
            display: block;
            margin-bottom: 2px;
        }}
        .prompt-text {{
            font-size: 12px;
            font-weight: 500;
            color: #1e293b;
        }}
        .sentences-sheet-body {{
            display: flex;
            flex-direction: column;
            gap: 10px;
        }}
        .sentence-card, .grammar-card {{
            border: 1px solid #cbd5e1;
            border-radius: 6px;
            padding: 8px 12px;
            background: #ffffff;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .sentence-header, .grammar-header {{
            display: flex;
            align-items: flex-start;
            gap: 8px;
            margin-bottom: 6px;
        }}
        .sentence-num, .grammar-badge {{
            background: #f1f5f9;
            color: #475569;
            font-size: 10px;
            font-weight: bold;
            padding: 2px 6px;
            border-radius: 4px;
            border: 1px solid #e2e8f0;
            flex-shrink: 0;
        }}
        .sentence-content {{
            flex: 1;
        }}
        .sentence-text {{
            font-size: 13px;
            font-weight: bold;
            color: #0f172a;
        }}
        .sentence-reading {{
            font-size: 10px;
            color: #64748b;
            margin-top: 1px;
        }}
        .sentence-meaning {{
            font-size: 11px;
            color: #334155;
            margin-top: 2px;
        }}
        .sentence-lines-wrap {{
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-top: 6px;
        }}
        .sentence-write-line {{
            width: 100%;
            height: 18px;
            border-bottom-width: 1px;
            border-bottom-color: #94a3b8;
        }}
        .grammar-title {{
            font-size: 13px;
            font-weight: bold;
            color: #0f172a;
        }}
        .grammar-usage {{
            font-size: 11px;
            color: #475569;
            margin-top: 2px;
        }}
        .grammar-example {{
            font-size: 11px;
            color: #64748b;
            margin-top: 2px;
            background: #f8fafc;
            padding: 3px 6px;
            border-radius: 4px;
            border-left: 2px solid #94a3b8;
        }}
        .grammar-prompt {{
            font-size: 10px;
            font-weight: 600;
            color: #d97706;
            margin: 4px 0 2px 0;
        }}

        /* Genkouyoushi Styles */
        .genkou-header {{
            margin-bottom: 8px;
            width: 100%;
        }}
        .genkou-header-title {{
            font-size: 16px;
            font-weight: 700;
            text-align: center;
            margin-bottom: 6px;
            color: #0f172a;
        }}
        .genkou-student-row {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 11px;
            font-weight: 500;
            color: #334155;
            padding: 0 4px;
            margin-bottom: 4px;
        }}
        .genkou-sheet-body {{
            display: flex;
            flex-direction: column;
            width: 100%;
        }}
        .genkou-row-wrap {{
            display: flex;
            flex-direction: column;
            width: 100%;
        }}
        .genkou-grid-row {{
            display: flex;
            width: 100%;
        }}
        .genkou-grid-row > .genkou-cell {{
            flex: 1 1 0%;
            aspect-ratio: 1 / 1;
            display: flex;
            align-items: center;
            justify-content: center;
            margin-left: -1px;
            margin-top: -1px;
            overflow: hidden;
        }}
        .genkou-grid-row > .genkou-cell:first-child {{
            margin-left: 0;
        }}
        .genkou-grid-row > .genkou-cell svg {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .genkou-spacer-band {{
            width: 100%;
            border-left: 1px solid;
            border-right: 1px solid;
            border-bottom: 1px solid;
            margin-top: -1px;
            box-sizing: border-box;
        }}
        .genkou-footer {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 10px;
            color: #64748b;
            margin-top: 8px;
            padding: 0 4px;
        }}
        .genkou-footer-left {{
            font-weight: 600;
        }}
        .genkou-footer-right {{
            letter-spacing: 2px;
        }}
    </style>
</head>
<body>
    <div class="screen-toolbar">
        <span>Flama Printable Worksheet</span>
        <button class="screen-btn" onclick="window.print()">In ngay / Lưu PDF</button>
    </div>
    {"".join(pages_html)}
</body>
</html>"""
    return full_html
