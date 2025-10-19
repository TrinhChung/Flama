"""Vocabulary management routes."""

from __future__ import annotations

import csv
import math
from io import StringIO
from typing import Dict, List, Tuple

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    make_response,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func

from models import db
from models.vocabulary_entry import VocabularyEntry
from models.column_preference import VocabularyColumnPreference

VOCABULARY_PAGE_SIZE = 60

COLUMN_KEYS = [
    "idx",
    "deck",
    "word",
    "hanviet",
    "reading",
    "translation_vi",
    "meaning_jp",
    "meaning_vi",
    "usage_jp",
    "usage_vi",
    "example_jp",
    "example_vi",
    "additional_note_jp",
    "additional_note_vi",
    "image",
    "diagram",
    "word_audio",
    "example_audio",
]

COLUMN_DEFAULT_WIDTHS = {
    "idx": "72px",
    "deck": "220px",
    "word": "200px",
    "hanviet": "180px",
    "reading": "180px",
    "translation_vi": "240px",
    "meaning_jp": "240px",
    "meaning_vi": "240px",
    "usage_jp": "260px",
    "usage_vi": "260px",
    "example_jp": "280px",
    "example_vi": "280px",
    "additional_note_jp": "240px",
    "additional_note_vi": "240px",
    "image": "180px",
    "diagram": "180px",
    "word_audio": "160px",
    "example_audio": "160px",
}

EXPECTED_HEADERS = {
    "deck": "deck",
    "word": "word",
    "hanviet": "hanviet",
    "reading": "reading",
    "translation_vi": "translation_vi",
    "meaning_jp": "meaning_jp",
    "meaning_vi": "meaning_vi",
    "usage_jp": "usage_jp",
    "usage_vi": "usage_vi",
    "example_jp": "example_jp",
    "example_vi": "example_vi",
    "additional_note_jp": "additional_note_jp",
    "additional_note_vi": "additional_note_vi",
    "image": "image",
    "diagram": "diagram",
    "word_audio": "word_audio",
    "example_audio": "example_audio",
}

vocabulary_bp = Blueprint("vocabulary", __name__, url_prefix="/vocabulary")


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_") if value else ""


def _build_lesson_summary() -> Tuple[List[Dict[str, int]], int]:
    total_entries = db.session.query(func.count(VocabularyEntry.id)).scalar() or 0
    total_lessons = (
        math.ceil(total_entries / VOCABULARY_PAGE_SIZE) if total_entries else 0
    )

    summary: List[Dict[str, int]] = []
    for lesson in range(1, total_lessons + 1):
        start_index = (lesson - 1) * VOCABULARY_PAGE_SIZE + 1
        end_index = min(lesson * VOCABULARY_PAGE_SIZE, total_entries)
        count = end_index - start_index + 1
        summary.append(
            {
                "lesson": lesson,
                "start_index": start_index,
                "end_index": end_index,
                "count": count,
            }
        )

    return summary, total_entries


@vocabulary_bp.route("/")
@login_required
def index():
    """Overview of lessons divided into 60-word chunks."""
    lesson_summary, total_entries = _build_lesson_summary()
    return render_template(
        "vocabulary_index.html",
        lessons=lesson_summary,
        total_entries=total_entries,
        page_size=VOCABULARY_PAGE_SIZE,
        column_keys=COLUMN_KEYS,
    )


@vocabulary_bp.route("/lesson/<int:lesson>")
@login_required
def lesson(lesson: int):
    """Display one lesson (chunk of entries) across all vocabulary."""
    if lesson < 1:
        abort(404)

    offset = (lesson - 1) * VOCABULARY_PAGE_SIZE
    entries = (
        VocabularyEntry.query.order_by(VocabularyEntry.id)
        .offset(offset)
        .limit(VOCABULARY_PAGE_SIZE)
        .all()
    )

    if not entries:
        flash("Không tìm thấy bài học hoặc bài không có dữ liệu.", "warning")
        return redirect(url_for("vocabulary.index"))

    total_entries = (
        db.session.query(func.count(VocabularyEntry.id)).scalar()
    )
    total_lessons = math.ceil(total_entries / VOCABULARY_PAGE_SIZE) if total_entries else 0

    column_widths: Dict[str, str] = {}
    if current_user.is_authenticated:
        prefs = VocabularyColumnPreference.query.filter_by(
            user_id=current_user.id
        ).all()
        column_widths = {pref.column_key: pref.width for pref in prefs}

    return render_template(
        "vocabulary_lesson.html",
        lesson=lesson,
        total_lessons=total_lessons,
        entries=entries,
        page_size=VOCABULARY_PAGE_SIZE,
        start_index=offset + 1,
        column_widths=column_widths,
        column_keys=COLUMN_KEYS,
        column_default_widths=COLUMN_DEFAULT_WIDTHS,
    )


@vocabulary_bp.route("/lesson/<int:lesson>/download")
@login_required
def download_lesson_csv(lesson: int):
    """Provide CSV download for a specific lesson."""
    if lesson < 1:
        abort(404)

    offset = (lesson - 1) * VOCABULARY_PAGE_SIZE
    entries = (
        VocabularyEntry.query.order_by(VocabularyEntry.id)
        .offset(offset)
        .limit(VOCABULARY_PAGE_SIZE)
        .all()
    )

    if not entries:
        flash("Không tìm thấy dữ liệu để tải.", "warning")
        return redirect(url_for("vocabulary.lesson", lesson=lesson))

    fieldnames = list(EXPECTED_HEADERS.values())
    buffer = StringIO()
    writer = csv.DictWriter(buffer, fieldnames=fieldnames)
    writer.writeheader()
    for entry in entries:
        writer.writerow(
            {
                "deck": entry.deck,
                "word": entry.word,
                "hanviet": entry.hanviet or "",
                "reading": entry.reading or "",
                "translation_vi": entry.translation_vi or "",
                "meaning_jp": entry.meaning_jp or "",
                "meaning_vi": entry.meaning_vi or "",
                "usage_jp": entry.usage_jp or "",
                "usage_vi": entry.usage_vi or "",
                "example_jp": entry.example_jp or "",
                "example_vi": entry.example_vi or "",
                "additional_note_jp": entry.additional_note_jp or "",
                "additional_note_vi": entry.additional_note_vi or "",
                "image": entry.image or "",
                "diagram": entry.diagram or "",
                "word_audio": entry.word_audio or "",
                "example_audio": entry.example_audio or "",
            }
        )

    csv_data = buffer.getvalue()
    response = make_response(csv_data)
    filename = f"lesson-{lesson}.csv".replace(" ", "_")
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = "text/csv; charset=utf-8"
    return response


@vocabulary_bp.route("/column-widths", methods=["POST"])
@login_required
def save_column_width():
    """Persist column width adjustments for the authenticated user."""
    data = request.get_json(silent=True) or {}
    column = data.get("column")
    width = data.get("width")

    if column not in COLUMN_KEYS or not width:
        return jsonify({"success": False, "message": "Dữ liệu không hợp lệ."}), 400

    width_str = str(width)
    pref = VocabularyColumnPreference.query.filter_by(
        user_id=current_user.id, column_key=column
    ).first()

    if pref:
        pref.width = width_str
    else:
        pref = VocabularyColumnPreference(
            user_id=current_user.id, column_key=column, width=width_str
        )
        db.session.add(pref)

    db.session.commit()
    return jsonify({"success": True})


@vocabulary_bp.route("/entry/<int:entry_id>/deck", methods=["POST"])
@login_required
def update_deck(entry_id: int):
    """Update the deck label for a vocabulary entry."""
    entry = VocabularyEntry.query.get_or_404(entry_id)
    new_deck = request.form.get("deck", "").strip()

    if not new_deck:
        flash("Deck không được để trống.", "danger")
        return redirect(request.form.get("next") or url_for("vocabulary.index"))

    entry.deck = new_deck
    db.session.commit()
    flash("Cập nhật deck thành công.", "success")

    next_url = request.form.get("next") or url_for("vocabulary.index")
    return redirect(next_url)


@vocabulary_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    """Allow users to paste CSV data to populate the vocabulary table."""
    if request.method == "POST":
        csv_content = request.form.get("csv_content", "").strip()
        if not csv_content:
            flash("Vui lòng dán nội dung CSV.", "warning")
            return render_template("vocabulary_import.html")

        buffer = StringIO(csv_content)
        reader = csv.DictReader(buffer)

        if not reader.fieldnames:
            flash("CSV phải chứa dòng tiêu đề.", "danger")
            return render_template("vocabulary_import.html", sample_headers=EXPECTED_HEADERS.keys())

        normalized_headers = [_normalize_header(h) for h in reader.fieldnames]
        mapping: Dict[str, str] = {}

        for original, normalized in zip(reader.fieldnames, normalized_headers):
            if normalized in EXPECTED_HEADERS:
                mapping[EXPECTED_HEADERS[normalized]] = original

        missing_core = [field for field in ("deck", "word") if field not in mapping]
        if missing_core:
            flash(
                "Thiếu cột bắt buộc trong CSV: " + ", ".join(missing_core),
                "danger",
            )
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                csv_content=csv_content,
            )

        inserted = 0
        try:
            for row in reader:
                if not row:
                    continue

                deck = row.get(mapping["deck"], "").strip()
                word = row.get(mapping["word"], "").strip()
                if not deck or not word:
                    continue

                entry = VocabularyEntry(
                    deck=deck,
                    word=word,
                    hanviet=row.get(mapping.get("hanviet", ""), "").strip()
                    if mapping.get("hanviet")
                    else None,
                    reading=row.get(mapping.get("reading", ""), "").strip()
                    if mapping.get("reading")
                    else None,
                    translation_vi=row.get(mapping.get("translation_vi", ""), "").strip()
                    if mapping.get("translation_vi")
                    else None,
                    meaning_jp=row.get(mapping.get("meaning_jp", ""), "").strip()
                    if mapping.get("meaning_jp")
                    else None,
                    meaning_vi=row.get(mapping.get("meaning_vi", ""), "").strip()
                    if mapping.get("meaning_vi")
                    else None,
                    usage_jp=row.get(mapping.get("usage_jp", ""), "").strip()
                    if mapping.get("usage_jp")
                    else None,
                    usage_vi=row.get(mapping.get("usage_vi", ""), "").strip()
                    if mapping.get("usage_vi")
                    else None,
                    example_jp=row.get(mapping.get("example_jp", ""), "").strip()
                    if mapping.get("example_jp")
                    else None,
                    example_vi=row.get(mapping.get("example_vi", ""), "").strip()
                    if mapping.get("example_vi")
                    else None,
                    additional_note_jp=row.get(mapping.get("additional_note_jp", ""), "").strip()
                    if mapping.get("additional_note_jp")
                    else None,
                    additional_note_vi=row.get(mapping.get("additional_note_vi", ""), "").strip()
                    if mapping.get("additional_note_vi")
                    else None,
                    image=row.get(mapping.get("image", ""), "").strip()
                    if mapping.get("image")
                    else None,
                    diagram=row.get(mapping.get("diagram", ""), "").strip()
                    if mapping.get("diagram")
                    else None,
                    word_audio=row.get(mapping.get("word_audio", ""), "").strip()
                    if mapping.get("word_audio")
                    else None,
                    example_audio=row.get(mapping.get("example_audio", ""), "").strip()
                    if mapping.get("example_audio")
                    else None,
                )

                db.session.add(entry)
                inserted += 1

            db.session.commit()
        except Exception as exc:  # pragma: no cover
            db.session.rollback()
            flash(f"Lỗi khi nhập CSV: {exc}", "danger")
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                csv_content=csv_content,
            )

        flash(f"Nhập thành công {inserted} dòng.", "success")
        return redirect(url_for("vocabulary.index"))

    return render_template(
        "vocabulary_import.html",
        sample_headers=EXPECTED_HEADERS.keys(),
    )
