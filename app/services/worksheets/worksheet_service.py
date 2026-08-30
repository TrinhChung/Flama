"""Worksheet Service - Orchestrates deck note querying, CJK extraction, stroke resolution, layout pagination, and printable HTML rendering."""

from __future__ import annotations

import html
import random
from typing import Any

from flask import current_app, has_app_context
from sqlalchemy.orm import selectinload

from app.services.strokes.cjk_extractor import CjkExtractor
from app.services.strokes.stroke_service import (
    _get_static_root,
    check_stroke_svg_exists,
    normalize_locale,
)
from app.services.worksheets.template_catalog import (
    WorksheetTemplate,
    calculate_optimal_rows_per_page,
    get_template,
    list_templates,
)
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_install import DeckInstall
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


def get_deck_worksheet_meta(user_id: int, deck_id: int, admin_mode: bool = False) -> dict[str, Any]:
    """Retrieve note types, fields, and stats for a deck to configure worksheet generation."""
    deck = _check_deck_access(user_id, deck_id, admin_mode)

    # Query all notes in this deck to inspect note types and field definitions
    notes_query = (
        Note.query.filter(Note.deck_id == deck_id)
        .options(selectinload(Note.note_type).selectinload(NoteType.field_defs))
    )
    if not admin_mode and deck.owner_user_id != user_id:
        # If installed, notes belong to deck owner
        notes = notes_query.all()
    else:
        notes = notes_query.all()

    total_notes = len(notes)

    # Collect distinct NoteTypes and their field definitions
    note_types_map: dict[int, dict[str, Any]] = {}
    for n in notes:
        nt = n.note_type
        if nt and nt.id not in note_types_map:
            field_names = [f.name for f in sorted(nt.field_defs, key=lambda x: getattr(x, "position", 0))]
            note_types_map[nt.id] = {
                "id": nt.id,
                "name": nt.name,
                "fields": field_names,
                "note_count": 0,
            }
        if nt:
            note_types_map[nt.id]["note_count"] += 1

    note_types_list = list(note_types_map.values())

    # Build suggested field mappings based on field names
    suggested_mappings: dict[str, dict[str, str]] = {}
    if note_types_list:
        primary_fields = [f.lower() for f in note_types_list[0]["fields"]]
        raw_fields = note_types_list[0]["fields"]

        def _find_field(candidates: list[str]) -> str | None:
            for cand in candidates:
                cand_lower = cand.lower()
                for idx, f in enumerate(primary_fields):
                    if cand_lower == f or cand_lower in f:
                        return raw_fields[idx]
            return None

        kanji_field = _find_field(["expression", "kanji", "word", "vocab", "front", "hanzi", "sentence", "grammar"]) or (raw_fields[0] if raw_fields else "")
        reading_field = _find_field(["reading", "furigana", "kana", "pinyin", "pronunciation"]) or ""
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

    return {
        "deck_id": deck.id,
        "deck_name": deck.name,
        "total_notes": total_notes,
        "note_types": note_types_list,
        "suggested_mappings": suggested_mappings,
        "templates": list_templates(),
    }


def _get_stroke_svg_content(locale: str, hex_code: str) -> str | None:
    """Read the raw SVG file content for inlining into print/HTML documents."""
    static_root = _get_static_root()
    folder = normalize_locale(locale)

    candidates = [
        static_root / "strokes" / folder / f"{hex_code}.svg",
        static_root / "strokes" / folder / f"{hex_code.zfill(5)}.svg",
    ]
    if folder == "zh-hant":
        candidates.append(static_root / "strokes" / "zh" / f"{hex_code}.svg")

    for path in candidates:
        if path.exists():
            try:
                return path.read_text(encoding="utf-8")
            except Exception:
                pass
    return None


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
    if deck_id is None:
        raise WorksheetServiceError("deck_id là bắt buộc.", code="MISSING_DECK_ID")
    deck_id_int = int(deck_id)

    deck = _check_deck_access(user_id, deck_id_int, admin_mode)

    # Options and mappings
    field_mapping = payload.get("field_mapping") or {}
    payload_options = payload.get("options") or {}
    options = dict(template.default_options)
    options.update(payload_options)

    orientation = str(options.get("orientation") or template.default_orientation).strip().lower()
    margin = str(options.get("margin") or "compact").strip().lower()
    box_size = max(10, min(int(options.get("box_size") or (30 if template.id == "kanji_compact" else 36)), 120))
    extra_blank_rows = max(0, min(int(options.get("extra_blank_rows") or 0), 3))

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
        )
    else:
        rows_per_page = max(1, min(int(options.get("rows_per_page") or template.default_rows_per_page), 30))

    options["rows_per_page"] = rows_per_page
    options["auto_fit_page"] = auto_fit_page
    options["box_size"] = box_size
    options["extra_blank_rows"] = extra_blank_rows
    options["fill_blank_rows"] = fill_blank_rows

    locale = normalize_locale(options.get("locale") or "ja")
    options["locale"] = locale

    # Scope & Selection
    scope = str(payload.get("scope") or "all").strip().lower()
    card_ids = payload.get("card_ids")
    note_ids = payload.get("note_ids")
    note_type_id = payload.get("note_type_id")
    limit_n = int(payload.get("limit") or 0)

    # 1. Query Notes
    notes: list[Note] = []
    if card_ids and isinstance(card_ids, list):
        cards = (
            Card.query.filter(Card.id.in_([str(cid) for cid in card_ids]))
            .options(selectinload(Card.note))
            .all()
        )
        seen_nids = set()
        for c in cards:
            if c.note and c.note.id not in seen_nids:
                seen_nids.add(c.note.id)
                notes.append(c.note)
    elif note_ids and isinstance(note_ids, list):
        notes = (
            Note.query.filter(Note.id.in_([str(nid) for nid in note_ids]))
            .all()
        )
    else:
        query = Note.query.filter(Note.deck_id == deck_id_int)
        if note_type_id:
            query = query.filter(Note.note_type_id == int(note_type_id))
        notes = query.all()

    if not notes:
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
        sample_size = min(limit_n, len(notes))
        notes = random.sample(notes, sample_size)

    # Safety ceiling
    max_process_limit = 500
    if len(notes) > max_process_limit:
        notes = notes[:max_process_limit]

    # 2. Extract & Format Items based on template category
    raw_items: list[dict[str, Any]] = []
    warnings: list[str] = []
    missing_stroke_chars: set[str] = set()

    for idx, note in enumerate(notes):
        fvals = note.field_values or {}

        if template.category == "kanji":
            kanji_field_name = str(field_mapping.get("kanji") or "Expression").strip()
            reading_field_name = str(field_mapping.get("reading") or "").strip()
            meaning_field_name = str(field_mapping.get("meaning") or "").strip()

            raw_kanji_text = str(fvals.get(kanji_field_name) or "").strip()
            raw_reading = str(fvals.get(reading_field_name) or "").strip() if reading_field_name else ""
            raw_meaning = str(fvals.get(meaning_field_name) or "").strip() if meaning_field_name else ""

            reading_text = CjkExtractor.strip_html(raw_reading)
            meaning_text = CjkExtractor.strip_html(raw_meaning)
            source_word = CjkExtractor.strip_html(raw_kanji_text)

            extracted_chars = CjkExtractor.extract_characters(raw_kanji_text, deduplicate=True, max_limit=10)
            if not extracted_chars:
                continue

            for char in extracted_chars:
                hex_code = CjkExtractor.char_to_hex(char)
                has_stroke = check_stroke_svg_exists(locale, hex_code)
                stroke_svg = _get_stroke_svg_content(locale, hex_code) if has_stroke else None

                if not has_stroke:
                    missing_stroke_chars.add(char)

                raw_items.append({
                    "type": "kanji",
                    "note_id": note.id,
                    "char": char,
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
            word_field = str(field_mapping.get("word") or "Expression").strip()
            reading_field = str(field_mapping.get("prompt_reading") or field_mapping.get("reading") or "").strip()
            meaning_field = str(field_mapping.get("prompt_meaning") or field_mapping.get("meaning") or "Meaning").strip()

            word_val = CjkExtractor.strip_html(str(fvals.get(word_field) or ""))
            reading_val = CjkExtractor.strip_html(str(fvals.get(reading_field) or "")) if reading_field else ""
            meaning_val = CjkExtractor.strip_html(str(fvals.get(meaning_field) or "")) if meaning_field else ""

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
            word_field = str(field_mapping.get("word") or "Expression").strip()
            reading_field = str(field_mapping.get("reading") or "").strip()
            meaning_field = str(field_mapping.get("meaning") or "").strip()

            word_val = CjkExtractor.strip_html(str(fvals.get(word_field) or ""))
            reading_val = CjkExtractor.strip_html(str(fvals.get(reading_field) or "")) if reading_field else ""
            meaning_val = CjkExtractor.strip_html(str(fvals.get(meaning_field) or "")) if meaning_field else ""

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
                row_data[col] = CjkExtractor.strip_html(str(fvals.get(col) or ""))

            raw_items.append({
                "type": "table_row",
                "note_id": note.id,
                "data": row_data,
            })

        elif template.id == "sentence_writing":
            sentence_field = str(field_mapping.get("sentence") or field_mapping.get("word") or "Example").strip()
            reading_field = str(field_mapping.get("reading") or "").strip()
            meaning_field = str(field_mapping.get("meaning") or "").strip()

            sentence_val = CjkExtractor.strip_html(str(fvals.get(sentence_field) or ""))
            reading_val = CjkExtractor.strip_html(str(fvals.get(reading_field) or "")) if reading_field else ""
            meaning_val = CjkExtractor.strip_html(str(fvals.get(meaning_field) or "")) if meaning_field else ""

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

            grammar_val = CjkExtractor.strip_html(str(fvals.get(grammar_field) or ""))
            meaning_val = CjkExtractor.strip_html(str(fvals.get(meaning_field) or "")) if meaning_field else ""
            example_val = CjkExtractor.strip_html(str(fvals.get(example_field) or "")) if example_field else ""

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
                if template.category == "kanji":
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
            f'<text x="{half}" y="{y_pos}" font-family="\'Hiragino Kaku Gothic ProN\', \'Yu Gothic\', \'Meiryo\', \'Noto Sans JP\', sans-serif" '
            f'font-size="{font_size}" text-anchor="middle" fill="#cbd5e1" font-weight="300">{html.escape(char)}</text>'
        )
    elif not is_blank and char:
        char_svg = (
            f'<text x="{half}" y="{y_pos}" font-family="\'Hiragino Kaku Gothic ProN\', \'Yu Gothic\', \'Meiryo\', \'Noto Sans JP\', sans-serif" '
            f'font-size="{font_size}" text-anchor="middle" fill="#0f172a" font-weight="500">{html.escape(char)}</text>'
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

    # Generate Pages HTML
    pages_html: list[str] = []

    for page in pages:
        page_num = page.get("page_number", 1)
        total_p = page.get("total_pages", 1)
        hdr = page.get("header") or {}
        items = page.get("items") or []

        # Header Block
        header_html = f"""
        <header class="sheet-header">
            <div class="header-main">
                <h1 class="sheet-title">{html.escape(hdr.get("title") or "")}</h1>
                <p class="sheet-subtitle">{html.escape(hdr.get("subtitle") or "")}</p>
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

                # 1. Reference Kanji Box
                ref_box = _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=False, size=box_size, rounded=True, stroke_color="#0f172a")

                # 2. Stroke Order Box
                stroke_box = ""
                if stroke_svg and options.get("show_stroke_diagram", True):
                    stroke_box = f'<div class="stroke-diagram-wrapper" style="width: {box_size}px; height: {box_size}px;">{stroke_svg}</div>'
                elif options.get("show_stroke_diagram", True):
                    stroke_box = _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=False, size=box_size, rounded=True, stroke_color="#475569")

                # 3. Tracing Boxes
                trace_boxes = "".join(
                    _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                    for _ in range(trace_count)
                )

                # 4. Blank Practice Boxes
                blank_boxes = "".join(
                    _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size, rounded=False, stroke_color="#cbd5e1")
                    for _ in range(row_practice_count)
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

                # Labels (Reading / Meaning)
                meta_labels: list[str] = []
                if reading and options.get("show_reading", True):
                    meta_labels.append(f'<span class="lbl-reading">{html.escape(reading)}</span>')
                if meaning and options.get("show_meaning", True):
                    meta_labels.append(f'<span class="lbl-meaning">{html.escape(meaning)}</span>')
                if source_word and source_word != char:
                    meta_labels.append(f'<span class="lbl-word">({html.escape(source_word)})</span>')

                meta_html = f'<div class="kanji-info-pill">{" ".join(meta_labels)}</div>' if meta_labels else ""

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

        elif template_id == "vocab_writing":
            practice_boxes_cnt = max(1, int(options.get("practice_boxes_count", 6 if orientation == "portrait" else 10)))
            for item in items:
                word = item.get("word", "")
                reading = item.get("reading", "")
                meaning = item.get("meaning", "")

                boxes_html = "".join(
                    '<div class="vocab-write-box"></div>'
                    for _ in range(practice_boxes_cnt)
                )

                row_html = f"""
                <tr class="vocab-row">
                    <td class="col-word">{html.escape(word)}</td>
                    <td class="col-reading">{html.escape(reading)}</td>
                    <td class="col-meaning">{html.escape(meaning)}</td>
                    <td class="col-practice"><div class="vocab-boxes-strip">{boxes_html}</div></td>
                </tr>
                """
                rows_html.append(row_html)

        elif template_id == "vocab_recall":
            for item in items:
                reading = item.get("reading", "")
                meaning = item.get("meaning", "")

                row_html = f"""
                <tr class="recall-row">
                    <td class="col-prompt">
                        <div class="prompt-meaning">{html.escape(meaning)}</div>
                        {f'<div class="prompt-reading">{html.escape(reading)}</div>' if reading and options.get("show_reading_hint", True) else ''}
                    </td>
                    <td class="col-answer">
                        <div class="recall-answer-line"></div>
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

        # Combine page content
        body_content = ""
        if template_id in {"kanji_stroke", "kanji_compact"}:
            body_content = f'<div class="kanji-sheet-body">{"".join(rows_html)}</div>'
        elif template_id == "sentence_writing":
            body_content = f'<div class="sentences-sheet-body">{"".join(rows_html)}</div>'
        elif template_id == "grammar_practice":
            body_content = f'{top_prompt_html}<div class="sentences-sheet-body">{"".join(rows_html)}</div>'
        elif template_id == "vocab_writing":
            body_content = f"""
            <table class="vocab-table">
                <thead>
                    <tr>
                        <th style="width: 22%;">Từ vựng</th>
                        <th style="width: 20%;">Cách đọc</th>
                        <th style="width: 28%;">Ý nghĩa</th>
                        <th style="width: 30%;">Luyện viết</th>
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

        page_markup = f"""
        <div class="sheet-page">
            {watermark_html}
            <div class="sheet-content">
                {header_html}
                {prompt_html}
                <main class="sheet-main">{body_content}</main>
                <footer class="sheet-footer">
                    <span>Flama Worksheet Generator &bull; flama.app</span>
                    <span>Trang {page_num} / {total_p}</span>
                </footer>
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
                padding: {margin_css};
                border-radius: 4px;
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
        }}
        @media print {{
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
                height: {'210mm' if orientation == 'landscape' else '297mm'} !important;
                box-sizing: border-box !important;
                padding: {margin_css} !important;
                page-break-after: always !important;
                break-after: page !important;
                display: flex !important;
                flex-direction: column !important;
                justify-content: space-between !important;
                overflow: hidden !important;
            }}
        }}

        /* Header */
        .sheet-header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-end;
            border-bottom: 2px solid #0f172a;
            padding-bottom: 8px;
            margin-bottom: 14px;
        }}
        .sheet-title {{
            font-size: 18px;
            font-weight: 700;
            color: #0f172a;
            letter-spacing: -0.01em;
        }}
        .sheet-subtitle {{
            font-size: 11px;
            color: #64748b;
            margin-top: 2px;
        }}
        .header-meta {{
            display: flex;
            gap: 16px;
            font-size: 11px;
            color: #334155;
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
            margin-top: 14px;
            border-top: 1px solid #e2e8f0;
            padding-top: 6px;
        }}

        /* Kanji Rows */
        .kanji-sheet-body {{
            display: flex;
            flex-direction: column;
            gap: 6px;
        }}
        .kanji-practice-row {{
            border: 1px solid #e2e8f0;
            border-radius: 4px;
            padding: 4px 6px;
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
        .stroke-diagram-wrapper svg {{
            width: 100%;
            height: 100%;
            display: block;
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
        .recall-answer-line, .table-write-line {{
            width: 100%;
            min-height: 24px;
            border-bottom: 1px dashed #94a3b8;
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
