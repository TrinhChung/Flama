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

        kanji_field = _find_field(["expression", "kanji", "word", "vocab", "front", "hanzi"]) or (raw_fields[0] if raw_fields else "")
        reading_field = _find_field(["reading", "furigana", "kana", "pinyin", "pronunciation"]) or ""
        meaning_field = _find_field(["meaning", "definition", "vietnamese", "hanviet", "back", "nghia"]) or ""

        suggested_mappings = {
            "kanji": kanji_field,
            "reading": reading_field,
            "meaning": meaning_field,
            "word": kanji_field,
            "prompt_reading": reading_field,
            "prompt_meaning": meaning_field,
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
    options = dict(template.default_options)
    options.update(payload.get("options") or {})

    rows_per_page = max(1, min(int(options.get("rows_per_page") or template.default_rows_per_page), 30))
    options["rows_per_page"] = rows_per_page

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

            row_data: dict[str, str] = {}
            for col in custom_cols:
                row_data[col] = CjkExtractor.strip_html(str(fvals.get(col) or ""))

            raw_items.append({
                "type": "table_row",
                "note_id": note.id,
                "data": row_data,
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
        page_items = raw_items[start_idx:end_idx]

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
    size: int = 56,
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

    return (
        f'<svg width="{size}" height="{size}" viewBox="0 0 {size} {size}" class="worksheet-grid-box" xmlns="http://www.w3.org/2000/svg">'
        f'<rect x="0.5" y="0.5" width="{size - 1}" height="{size - 1}" fill="#ffffff" stroke="#94a3b8" stroke-width="1.2" rx="4" />'
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
    margin_mode = str(options.get("margin") or "standard").strip().lower()
    grid_style = str(options.get("grid_style") or "cross").strip().lower()
    trace_count = max(0, int(options.get("trace_count", 2)))
    practice_count = max(1, int(options.get("practice_count", 5)))

    margin_css = "10mm" if margin_mode == "compact" else ("18mm" if margin_mode == "wide" else "12mm")
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
            box_size = 48 if template_id == "kanji_compact" else 56
            for item in items:
                char = item.get("char", "")
                stroke_svg = item.get("stroke_svg") or ""
                reading = item.get("reading", "")
                meaning = item.get("meaning", "")
                source_word = item.get("source_word", "")

                # 1. Reference Kanji Box
                ref_box = _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=False, size=box_size)

                # 2. Stroke Order Box
                stroke_box = ""
                if stroke_svg and options.get("show_stroke_diagram", True):
                    stroke_box = f'<div class="stroke-diagram-wrapper" style="width: {box_size}px; height: {box_size}px;">{stroke_svg}</div>'
                else:
                    stroke_box = _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=False, size=box_size)

                # 3. Tracing Boxes
                trace_boxes = "".join(
                    _render_kanji_grid_svg(char, grid_style=grid_style, is_trace=True, size=box_size)
                    for _ in range(trace_count)
                )

                # 4. Blank Practice Boxes
                blank_boxes = "".join(
                    _render_kanji_grid_svg("", grid_style=grid_style, is_blank=True, size=box_size)
                    for _ in range(practice_count)
                )

                # Labels (Reading / Meaning)
                meta_labels: list[str] = []
                if reading and options.get("show_reading", True):
                    meta_labels.append(f'<span class="lbl-reading"><strong>Âm:</strong> {html.escape(reading)}</span>')
                if meaning and options.get("show_meaning", True):
                    meta_labels.append(f'<span class="lbl-meaning"><strong>Nghĩa:</strong> {html.escape(meaning)}</span>')
                if source_word and source_word != char:
                    meta_labels.append(f'<span class="lbl-word">({html.escape(source_word)})</span>')

                meta_html = f'<div class="kanji-row-meta">{" ".join(meta_labels)}</div>' if meta_labels else ""

                row_html = f"""
                <div class="kanji-practice-row">
                    <div class="kanji-boxes-container">
                        <div class="box-group ref-group">
                            <span class="group-label">Mẫu</span>
                            {ref_box}
                        </div>
                        {f'''<div class="box-group stroke-group">
                            <span class="group-label">Thứ tự nét</span>
                            {stroke_box}
                        </div>''' if options.get("show_stroke_diagram", True) else ''}
                        <div class="box-group trace-group">
                            <span class="group-label">Đồ chữ</span>
                            <div class="boxes-flex">{trace_boxes}</div>
                        </div>
                        <div class="box-group blank-group">
                            <span class="group-label">Tự viết</span>
                            <div class="boxes-flex">{blank_boxes}</div>
                        </div>
                    </div>
                    {meta_html}
                </div>
                """
                rows_html.append(row_html)

        elif template_id == "vocab_writing":
            practice_boxes_cnt = max(1, int(options.get("practice_boxes_count", 5)))
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
                    <td class="col-practice"><div class="vocab-boxes-flex">{boxes_html}</div></td>
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

            for item in items:
                row_data = item.get("data") or {}
                cols_td = "".join(
                    f'<td class="table-cell">{html.escape(str(row_data.get(c, "")))}</td>'
                    for c in custom_cols
                )
                practice_td = '<td class="col-practice"><div class="table-write-line"></div></td>' if options.get("include_practice_column", True) else ''

                rows_html.append(f'<tr class="deck-table-row">{cols_td}{practice_td}</tr>')

        # Combine page content
        body_content = ""
        if template_id in {"kanji_stroke", "kanji_compact"}:
            body_content = f'<div class="kanji-sheet-body">{"".join(rows_html)}</div>'
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

            headers_th = "".join(f'<th>{html.escape(c)}</th>' for c in custom_cols)
            practice_th = f'<th>{html.escape(str(options.get("practice_column_label") or "Ghi chú"))}</th>' if options.get("include_practice_column", True) else ''

            body_content = f"""
            <table class="deck-data-table">
                <thead>
                    <tr>{headers_th}{practice_th}</tr>
                </thead>
                <tbody>{"".join(rows_html)}</tbody>
            </table>
            """

        page_markup = f"""
        <div class="sheet-page">
            {header_html}
            <main class="sheet-main">{body_content}</main>
            <footer class="sheet-footer">
                <span>Flama Worksheet Generator &bull; flama.app</span>
                <span>Trang {page_num} / {total_p}</span>
            </footer>
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
            margin: {margin_css};
        }}
        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, "Hiragino Kaku Gothic ProN", "Yu Gothic", "Meiryo", "Noto Sans JP", "Segoe UI", Roboto, sans-serif;
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
            body {{
                background: transparent;
                padding: 0;
            }}
            .screen-toolbar {{
                display: none !important;
            }}
            .sheet-page {{
                background: #ffffff;
                width: 100%;
                height: 100%;
                padding: 0;
                page-break-after: always;
                break-after: page;
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
            gap: 10px;
        }}
        .kanji-practice-row {{
            border: 1px solid #e2e8f0;
            border-radius: 6px;
            padding: 8px 10px;
            background: #ffffff;
            page-break-inside: avoid;
            break-inside: avoid;
        }}
        .kanji-boxes-container {{
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .box-group {{
            display: flex;
            flex-direction: column;
            align-items: center;
            gap: 4px;
        }}
        .group-label {{
            font-size: 9px;
            font-weight: 600;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}
        .boxes-flex {{
            display: flex;
            gap: 4px;
        }}
        .worksheet-grid-box {{
            display: block;
        }}
        .stroke-diagram-wrapper svg {{
            width: 100%;
            height: 100%;
            display: block;
        }}
        .kanji-row-meta {{
            margin-top: 6px;
            font-size: 11px;
            color: #334155;
            display: flex;
            gap: 12px;
            border-top: 1px dashed #f1f5f9;
            padding-top: 4px;
        }}
        .lbl-reading strong, .lbl-meaning strong {{
            color: #64748b;
            font-size: 10px;
        }}
        .lbl-word {{
            color: #64748b;
            font-style: italic;
        }}

        /* Tables (Vocab & Recall & Deck) */
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 12px;
        }}
        th {{
            background: #f1f5f9;
            color: #1e293b;
            font-weight: 600;
            padding: 8px 10px;
            border: 1px solid #cbd5e1;
            text-align: left;
        }}
        td {{
            padding: 8px 10px;
            border: 1px solid #cbd5e1;
            vertical-align: middle;
        }}
        .col-word {{
            font-weight: 600;
            font-size: 14px;
            color: #0f172a;
        }}
        .vocab-boxes-flex {{
            display: flex;
            gap: 4px;
        }}
        .vocab-write-box {{
            width: 28px;
            height: 28px;
            border: 1px dashed #cbd5e1;
            border-radius: 4px;
            background: #ffffff;
        }}
        .recall-answer-line, .table-write-line {{
            width: 100%;
            min-height: 24px;
            border-bottom: 1px dashed #94a3b8;
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
