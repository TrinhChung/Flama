"""Vocabulary management routes."""

from __future__ import annotations

import csv
import re
from datetime import datetime, timedelta
from io import StringIO
from types import SimpleNamespace
from typing import Dict, List, Optional

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
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.utils.permissions import is_admin_user
from app.services.anki_scheduler import (
    CardState,
    applyAnswer,
    computeAnswerPreview,
    default_deck_options,
)
from models import db
from models.column_preference import VocabularyColumnPreference
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_entry import VocabularyEntry
from models.vocabulary_progress import VocabularyProgress
from models.vocabulary_structure import VocabularyLevel, VocabularyTopic, VocabularyLesson

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

EDITABLE_FIELDS = [
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

MULTILINE_FIELDS = {
    "translation_vi",
    "meaning_jp",
    "meaning_vi",
    "usage_jp",
    "usage_vi",
    "example_jp",
    "example_vi",
    "additional_note_jp",
    "additional_note_vi",
}

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
COLUMN_TOTAL_DEFAULT_WIDTH = sum(
    int(value.replace("px", "").strip()) for value in COLUMN_DEFAULT_WIDTHS.values()
)

PLACEHOLDER_ROW_COUNT = 120

EXPORT_FORMATS = {
    "csv": {
        "label": "CSV (,)",
        "delimiter": ",",
        "extension": "csv",
        "content_type": "text/csv; charset=utf-8",
    },
    "scsv": {
        "label": "CSV (;)",
        "delimiter": ";",
        "extension": "csv",
        "content_type": "text/csv; charset=utf-8",
    },
    "tsv": {
        "label": "TSV",
        "delimiter": "\t",
        "extension": "tsv",
        "content_type": "text/tab-separated-values; charset=utf-8",
    },
}
DEFAULT_EXPORT_FORMAT = "csv"

_COLUMN_WIDTH_PATTERN = re.compile(r"^\s*(\d+(?:\.\d+)?)\s*(px)?\s*$")
_MIN_COLUMN_WIDTH = 60
_MAX_COLUMN_WIDTH = 1600
LEARN_QUEUE = "learn"
REVIEW_QUEUE = "review"
NEW_QUEUE = "new"
LEARNING_QUEUE = "learning"
RELEARNING_QUEUE = "relearning"


def _normalize_column_width(column_key: str, raw_width: str | None) -> str:
    """Ensure column widths are valid px values within allowed bounds."""
    default_value = COLUMN_DEFAULT_WIDTHS.get(column_key, f"{_MIN_COLUMN_WIDTH}px")
    default_px = int(default_value.replace("px", "").strip())
    min_px = max(_MIN_COLUMN_WIDTH, default_px // 2 or _MIN_COLUMN_WIDTH)

    if not raw_width:
        return default_value

    match = _COLUMN_WIDTH_PATTERN.match(raw_width)
    if not match:
        return default_value

    numeric_value = float(match.group(1))
    normalized = max(min_px, min(numeric_value, _MAX_COLUMN_WIDTH))

    if normalized.is_integer():
        return f"{int(normalized)}px"

    normalized_str = f"{normalized:.2f}".rstrip("0").rstrip(".")
    return f"{normalized_str}px"


def _compute_total_width(column_widths: Dict[str, str]) -> int:
    """Compute aggregate width in px, falling back to defaults for missing columns."""
    total = 0
    for key in COLUMN_KEYS:
        width_value = column_widths.get(key, COLUMN_DEFAULT_WIDTHS.get(key, f"{_MIN_COLUMN_WIDTH}px"))
        match = _COLUMN_WIDTH_PATTERN.match(width_value)
        if match:
            total += int(float(match.group(1)))
        else:
            default_px = int(COLUMN_DEFAULT_WIDTHS.get(key, f"{_MIN_COLUMN_WIDTH}px").replace("px", "").strip())
            total += default_px
    return total

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


@vocabulary_bp.before_request
def restrict_non_admin_routes():
    """Allow regular users to access only study mode endpoints."""
    if not current_user.is_authenticated:
        return None
    if is_admin_user(current_user):
        return None

    endpoint = request.endpoint or ""
    allowed_endpoints = {
        "vocabulary.lesson",  # route will redirect to study mode
        "vocabulary.study_deck",
        "vocabulary.study_topic",
        "vocabulary.study_lesson",
        "vocabulary.study_answer",
    }
    if endpoint in allowed_endpoints:
        return None
    return redirect(url_for("main.dashboard"))


def _normalize_header(value: str) -> str:
    return value.strip().lower().replace(" ", "_") if value else ""


def _get_levels_hierarchy() -> List[VocabularyLevel]:
    return (
        VocabularyLevel.query.options(
            selectinload(VocabularyLevel.topics).selectinload(VocabularyTopic.lessons)
        )
        .order_by(VocabularyLevel.position, VocabularyLevel.created_at)
        .all()
    )


def _next_level_position() -> int:
    max_pos = db.session.query(func.max(VocabularyLevel.position)).scalar()
    return (max_pos or 0) + 1


def _next_topic_position(level_id: int) -> int:
    max_pos = (
        db.session.query(func.max(VocabularyTopic.position))
        .filter(VocabularyTopic.level_id == level_id)
        .scalar()
    )
    return (max_pos or 0) + 1


def _next_lesson_position(topic_id: int) -> int:
    max_pos = (
        db.session.query(func.max(VocabularyLesson.position))
        .filter(VocabularyLesson.topic_id == topic_id)
        .scalar()
    )
    return (max_pos or 0) + 1


def _sorted_lessons(topic: VocabularyTopic) -> List[VocabularyLesson]:
    return sorted(
        topic.lessons,
        key=lambda lesson: ((lesson.position or 0), lesson.created_at or datetime.min),
    )


def _create_topic_lesson(
    topic: VocabularyTopic,
    *,
    title: str | None = None,
    description: str | None = None,
    page_size: int | None = None,
    commit: bool = True,
) -> VocabularyLesson:
    lessons = _sorted_lessons(topic)
    next_position = (lessons[-1].position if lessons else 0) + 1
    lesson = VocabularyLesson(
        topic=topic,
        title=title or f"Lesson {next_position}",
        description=description,
        position=next_position,
        page_size=page_size or VOCABULARY_PAGE_SIZE,
    )
    db.session.add(lesson)
    if commit:
        db.session.commit()
    return lesson


def _ensure_first_lesson(topic: VocabularyTopic) -> VocabularyLesson:
    lessons = _sorted_lessons(topic)
    if lessons:
        return lessons[0]
    return _create_topic_lesson(topic, commit=True)


def _lesson_entry_count(lesson: VocabularyLesson) -> int:
    if "entries" in lesson.__dict__:
        try:
            return len(lesson.entries)
        except TypeError:
            pass
    return (
        db.session.query(func.count(VocabularyEntry.id))
        .filter(VocabularyEntry.lesson_id == lesson.id)
        .scalar()
        or 0
    )


def _select_lesson_for_append(
    topic: VocabularyTopic, *, default_page_size: int
) -> tuple[VocabularyLesson, int]:
    lessons = _sorted_lessons(topic)
    if not lessons:
        lesson = _create_topic_lesson(topic, page_size=default_page_size, commit=False)
        return lesson, 0

    lesson = lessons[-1]
    entry_count = _lesson_entry_count(lesson)
    capacity = lesson.page_size or default_page_size
    if entry_count >= capacity:
        lesson = _create_topic_lesson(topic, page_size=default_page_size, commit=False)
        return lesson, 0
    return lesson, entry_count


def _normalize_progress_queue(value: str | None) -> str:
    normalized = (value or NEW_QUEUE).strip().lower()
    if normalized == LEARN_QUEUE:
        return LEARNING_QUEUE
    if normalized in {NEW_QUEUE, LEARNING_QUEUE, REVIEW_QUEUE, RELEARNING_QUEUE}:
        return normalized
    return NEW_QUEUE


def _card_state_from_progress(progress: VocabularyProgress | None, now: datetime) -> CardState:
    options = default_deck_options()
    if not progress:
        return CardState(
            type=NEW_QUEUE,
            stepIndex=0,
            due=now,
            dueDay=None,
            intervalDays=0,
            ease=options.startingEase,
            reps=0,
            lapses=0,
            lastReviewAt=None,
        )

    queue = _normalize_progress_queue(progress.queue)
    due_at = progress.due_at or now
    due_day = progress.due_day
    
    # Backward compatibility: if due_day not stored but queue=review, recalculate it
    if due_day is None and queue == REVIEW_QUEUE:
        shifted = due_at - timedelta(hours=options.dayBoundaryHourLocal)
        due_day = shifted.date().toordinal()

    return CardState(
        type=queue,  # type: ignore[arg-type]
        stepIndex=int(progress.step_index or 0),
        due=due_at,
        dueDay=due_day,
        intervalDays=float(progress.interval_days or 0),
        ease=float(progress.ease_factor or options.startingEase),
        reps=int(progress.reps or 0),
        lapses=int(progress.lapses or 0),
        lastReviewAt=progress.last_reviewed_at,
    )


def _apply_card_state_to_progress(
    progress: VocabularyProgress, card_state: CardState, now: datetime
) -> VocabularyProgress:
    options = default_deck_options()
    queue = _normalize_progress_queue(card_state.type)
    due_at = card_state.due
    due_day = card_state.dueDay
    
    if card_state.dueDay is not None:
        day_date = datetime.fromordinal(int(card_state.dueDay)).date()
        due_at = datetime.combine(day_date, datetime.min.time()) + timedelta(
            hours=options.dayBoundaryHourLocal
        )
    progress.queue = queue
    progress.step_index = int(card_state.stepIndex or 0)
    progress.due_at = due_at
    progress.due_day = due_day
    progress.interval_days = int(round(float(card_state.intervalDays or 0)))
    progress.ease_factor = float(card_state.ease or options.startingEase)
    progress.reps = int(card_state.reps or 0)
    progress.lapses = int(card_state.lapses or 0)
    progress.last_reviewed_at = card_state.lastReviewAt or now
    return progress


def _next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(func.max(VocabularyDeck.position))
    if parent_deck_id is None:
        max_pos = query.filter(VocabularyDeck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(VocabularyDeck.parent_id == parent_deck_id).scalar()
    return (max_pos or 0) + 1


def _get_or_create_deck(*, parent_id: int | None, name: str, description: str | None, position: int | None):
    query = VocabularyDeck.query.filter(
        VocabularyDeck.parent_id == parent_id,
        VocabularyDeck.name == name,
    )
    deck_node = query.order_by(VocabularyDeck.id.asc()).first()
    if deck_node:
        return deck_node

    deck_node = VocabularyDeck(
        parent_id=parent_id,
        name=name,
        description=description,
        position=position or 0,
    )
    db.session.add(deck_node)
    db.session.flush()
    return deck_node


def _ensure_deck_path_for_lesson(lesson: VocabularyLesson | None):
    if not lesson:
        return None
    topic_obj = lesson.topic
    if not topic_obj:
        return None
    level_obj = topic_obj.level
    if not level_obj:
        return None

    level_deck = _get_or_create_deck(
        parent_id=None,
        name=level_obj.name,
        description=level_obj.description,
        position=level_obj.position,
    )
    topic_deck = _get_or_create_deck(
        parent_id=level_deck.id,
        name=topic_obj.name,
        description=topic_obj.description,
        position=topic_obj.position,
    )
    lesson_deck = _get_or_create_deck(
        parent_id=topic_deck.id,
        name=lesson.title,
        description=lesson.description,
        position=lesson.position,
    )
    return lesson_deck


def _ensure_deck_for_topic(topic_obj: VocabularyTopic | None):
    if not topic_obj:
        return None
    level_obj = topic_obj.level
    if not level_obj:
        return None
    level_deck = _get_or_create_deck(
        parent_id=None,
        name=level_obj.name,
        description=level_obj.description,
        position=level_obj.position,
    )
    return _get_or_create_deck(
        parent_id=level_deck.id,
        name=topic_obj.name,
        description=topic_obj.description,
        position=topic_obj.position,
    )


def _is_due(progress: VocabularyProgress | None, now: datetime) -> bool:
    if progress is None:
        return True
    queue = _normalize_progress_queue(progress.queue)
    if queue == NEW_QUEUE:
        return True
    if progress.due_at is None:
        return True
    return progress.due_at <= now


def _select_next_card(entries: List[VocabularyEntry], progress_map: Dict[int, VocabularyProgress], now: datetime):
    due_learn = []
    due_relearn = []
    due_review = []
    due_new = []
    for entry in entries:
        progress = progress_map.get(entry.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue == LEARNING_QUEUE:
            due_learn.append(entry)
        elif queue == RELEARNING_QUEUE:
            due_relearn.append(entry)
        elif queue == REVIEW_QUEUE:
            due_review.append(entry)
        else:
            due_new.append(entry)

    if due_relearn:
        return due_relearn[0]
    if due_learn:
        return due_learn[0]
    if due_review:
        return due_review[0]
    if due_new:
        return due_new[0]
    return None


@vocabulary_bp.route("/")
@login_required
def index():
    """Overview of vocabulary hierarchy (levels -> topics -> lessons)."""
    levels = _get_levels_hierarchy()
    total_entries = db.session.query(func.count(VocabularyEntry.id)).scalar() or 0
    return render_template(
        "vocabulary_index.html",
        levels=levels,
        total_entries=total_entries,
        page_size=VOCABULARY_PAGE_SIZE,
        column_keys=COLUMN_KEYS,
        export_formats=EXPORT_FORMATS,
        default_export_format=DEFAULT_EXPORT_FORMAT,
    )


@vocabulary_bp.route("/levels/new", methods=["POST"])
@login_required
def create_level():
    """Create a new vocabulary level."""

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None

    if not name:
        flash("Level name cannot be empty.", "warning")
        return redirect(url_for("vocabulary.index"))

    level = VocabularyLevel(
        name=name,
        description=description,
        position=_next_level_position(),
    )


@vocabulary_bp.route("/decks/create", methods=["POST"])
@login_required
def create_deck():
    """Create deck(s) from path, auto-creating missing parents."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))

    parent_id_raw = (request.form.get("parent_id") or "").strip()
    deck_path_raw = (request.form.get("deck_path") or "").strip()
    deck_name = (request.form.get("name") or "").strip() or "New Deck"
    next_url = (request.form.get("next") or "").strip() or url_for("main.dashboard")

    tokens = [item.strip() for item in deck_path_raw.split("::") if item.strip()]
    if not tokens:
        if parent_id_raw:
            try:
                parent_id = int(parent_id_raw)
            except ValueError:
                flash("Invalid parent deck.", "danger")
                return redirect(next_url)
            parent_deck = VocabularyDeck.query.get(parent_id)
            if not parent_deck:
                flash("Parent deck not found.", "danger")
                return redirect(next_url)
            tokens = [parent_deck.name, deck_name]
        else:
            tokens = [deck_name]

    parent_id = None
    created_count = 0
    created_names: List[str] = []
    final_deck = None
    for token in tokens:
        existing = (
            VocabularyDeck.query.filter(
                VocabularyDeck.parent_id == parent_id,
                VocabularyDeck.name == token,
            )
            .order_by(VocabularyDeck.id.asc())
            .first()
        )
        if existing:
            final_deck = existing
            parent_id = existing.id
            continue

        node = VocabularyDeck(
            parent_id=parent_id,
            name=token,
            position=_next_deck_position(parent_id),
        )
        db.session.add(node)
        db.session.flush()
        created_count += 1
        created_names.append(token)
        final_deck = node
        parent_id = node.id

    db.session.commit()
    if created_count == 0 and final_deck:
        flash(f"Deck already exists: {'::'.join(tokens)}", "info")
    elif created_count == 1 and final_deck:
        flash(f"Created deck: {final_deck.name}", "success")
    else:
        flash(f"Created {created_count} decks: {'::'.join(created_names)}", "success")
    return redirect(next_url)
    db.session.add(level)
    db.session.commit()
    _get_or_create_deck(
        parent_id=None,
        name=level.name,
        description=level.description,
        position=level.position,
    )
    db.session.commit()
    flash("Level created.", "success")
    return redirect(url_for("vocabulary.index"))


@vocabulary_bp.route("/topics/new", methods=["POST"])
@login_required
def create_topic():
    """Create a new topic within a level."""

    name = (request.form.get("name") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    level_id_raw = request.form.get("level_id")

    try:
        level_id = int(level_id_raw or 0)
    except ValueError:
        level_id = 0

    level = VocabularyLevel.query.get(level_id)
    if not level:
        flash("Level not found.", "danger")
        return redirect(url_for("vocabulary.index"))

    if not name:
        flash("Topic name cannot be empty.", "warning")
        return redirect(url_for("vocabulary.index"))

    topic = VocabularyTopic(
        level=level,
        name=name,
        description=description,
        position=_next_topic_position(level.id),
    )
    db.session.add(topic)
    db.session.commit()
    _ensure_deck_for_topic(topic)
    db.session.commit()
    flash("Topic created.", "success")
    return redirect(url_for("vocabulary.index"))


@vocabulary_bp.route("/lessons/new", methods=["POST"])
@login_required
def create_lesson():
    """Manually create a new lesson under an existing topic."""

    title = (request.form.get("title") or "").strip()
    description = (request.form.get("description") or "").strip() or None
    topic_id_raw = request.form.get("topic_id")
    page_size_raw = request.form.get("page_size")

    try:
        topic_id = int(topic_id_raw or 0)
    except ValueError:
        topic_id = 0

    topic = VocabularyTopic.query.options(selectinload(VocabularyTopic.level)).get(topic_id)
    if not topic:
        flash("Topic not found.", "danger")
        return redirect(url_for("vocabulary.index"))

    if not title:
        flash("Lesson name cannot be empty.", "warning")
        return redirect(url_for("vocabulary.index"))

    try:
        page_size = int(page_size_raw) if page_size_raw else VOCABULARY_PAGE_SIZE
        if page_size <= 0:
            raise ValueError
    except ValueError:
        page_size = VOCABULARY_PAGE_SIZE

    lesson = _create_topic_lesson(
        topic,
        title=title,
        description=description,
        page_size=page_size,
        commit=True,
    )
    _ensure_deck_path_for_lesson(lesson)
    db.session.commit()
    flash("Lesson created.", "success")
    return redirect(url_for("vocabulary.lesson", lesson_id=lesson.id))


@vocabulary_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required
def delete_lesson(lesson_id: int):
    """Delete a lesson and all of its vocabulary entries."""

    lesson = VocabularyLesson.query.options(selectinload(VocabularyLesson.topic)).get_or_404(lesson_id)
    lesson_title = lesson.title
    next_url = (request.form.get("next") or "").strip()
    topic = lesson.topic
    topic_id = topic.id
    db.session.delete(lesson)
    db.session.commit()

    flash(f"Deleted lesson: {lesson_title}", "success")
    if next_url:
        return redirect(next_url)
    remaining_lessons = (
        VocabularyLesson.query.filter_by(topic_id=topic_id)
        .order_by(VocabularyLesson.position, VocabularyLesson.created_at)
        .all()
    )
    if remaining_lessons:
        return redirect(url_for("vocabulary.lesson", lesson_id=remaining_lessons[0].id))
    return redirect(url_for("vocabulary.index"))


@vocabulary_bp.route("/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete_topic(topic_id: int):
    """Delete a topic and all nested lessons/entries."""

    topic = VocabularyTopic.query.get_or_404(topic_id)
    topic_name = topic.name
    next_url = (request.form.get("next") or "").strip()
    db.session.delete(topic)
    db.session.commit()
    flash(f"Deleted topic: {topic_name}", "success")
    if next_url:
        return redirect(next_url)
    return redirect(url_for("vocabulary.index"))


@vocabulary_bp.route("/topic/<int:topic_id>/open")
@login_required
def open_topic(topic_id: int):
    """Open the topic editor, auto-creating the first lesson if needed."""

    topic = VocabularyTopic.query.options(
        selectinload(VocabularyTopic.level),
        selectinload(VocabularyTopic.lessons).selectinload(VocabularyLesson.entries),
    ).get_or_404(topic_id)
    lesson = _ensure_first_lesson(topic)
    return redirect(url_for("vocabulary.lesson", lesson_id=lesson.id))


@vocabulary_bp.route("/topic/<int:topic_id>")
@login_required
def topic(topic_id: int):
    """Display a topic page with lesson list and management actions."""

    selected_topic = VocabularyTopic.query.options(
        selectinload(VocabularyTopic.level).selectinload(VocabularyLevel.topics),
        selectinload(VocabularyTopic.lessons).selectinload(VocabularyLesson.entries),
    ).get_or_404(topic_id)
    selected_level = selected_topic.level
    sibling_topics = sorted(
        selected_level.topics,
        key=lambda item: ((item.position or 0), item.created_at or datetime.min),
    )
    topic_lessons = _sorted_lessons(selected_topic)
    return render_template(
        "vocabulary_topic.html",
        selected_level=selected_level,
        selected_topic=selected_topic,
        sibling_topics=sibling_topics,
        lessons=topic_lessons,
        page_size=VOCABULARY_PAGE_SIZE,
    )


@vocabulary_bp.route("/study/topic/<int:topic_id>")
@login_required
def study_topic(topic_id: int):
    """Render topic-wide study mode across all lessons in the topic."""

    topic_obj = VocabularyTopic.query.options(
        selectinload(VocabularyTopic.level),
        selectinload(VocabularyTopic.lessons).selectinload(VocabularyLesson.entries),
    ).get_or_404(topic_id)
    lessons = _sorted_lessons(topic_obj)
    entries: List[VocabularyEntry] = []
    for lesson_obj in lessons:
        lesson_entries = sorted(lesson_obj.entries, key=lambda item: item.id)
        entries.extend(lesson_entries)

    now = datetime.utcnow()
    entry_ids = [entry.id for entry in entries]
    progress_map: Dict[int, VocabularyProgress] = {}
    if entry_ids:
        rows = VocabularyProgress.query.filter(
            VocabularyProgress.user_id == current_user.id,
            VocabularyProgress.entry_id.in_(entry_ids),
        ).all()
        progress_map = {row.entry_id: row for row in rows}

    card = _select_next_card(entries, progress_map, now)
    due_new = 0
    due_learn = 0
    due_review = 0
    for entry in entries:
        progress = progress_map.get(entry.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue in {LEARNING_QUEUE, RELEARNING_QUEUE}:
            due_learn += 1
        elif queue == REVIEW_QUEUE:
            due_review += 1
        else:
            due_new += 1

    next_intervals_preview = None
    if card:
        card_state = _card_state_from_progress(progress_map.get(card.id), now)
        next_intervals_preview = computeAnswerPreview(card_state, default_deck_options(), now)

    return render_template(
        "vocabulary_study.html",
        selected_level=topic_obj.level,
        selected_topic=topic_obj,
        selected_lesson=None,
        card=card,
        due_new=due_new,
        due_learn=due_learn,
        due_review=due_review,
        due_total=due_new + due_learn + due_review,
        admin_mode=is_admin_user(current_user),
        study_scope="topic",
        study_scope_id=topic_obj.id,
        study_root_name=topic_obj.name,
        study_root_url=url_for("vocabulary.study_topic", topic_id=topic_obj.id),
        next_study_url=url_for("vocabulary.study_topic", topic_id=topic_obj.id),
        next_intervals_preview=next_intervals_preview,
    )


@vocabulary_bp.route("/study/deck/<int:deck_id>")
@login_required
def study_deck(deck_id: int):
    """Study cards across an arbitrary deck subtree (parent/child model)."""
    all_decks = VocabularyDeck.query.order_by(
        VocabularyDeck.parent_id.isnot(None),
        VocabularyDeck.position,
        VocabularyDeck.created_at,
        VocabularyDeck.id,
    ).all()
    deck_map = {deck.id: deck for deck in all_decks}
    root_deck = deck_map.get(deck_id)
    if not root_deck:
        abort(404)

    children_by_parent: Dict[int | None, List[VocabularyDeck]] = {}
    for deck in all_decks:
        children_by_parent.setdefault(deck.parent_id, []).append(deck)

    subtree_ids: List[int] = []

    def _collect(deck_node_id: int):
        subtree_ids.append(deck_node_id)
        for child in children_by_parent.get(deck_node_id, []):
            _collect(child.id)

    _collect(root_deck.id)

    entries = (
        VocabularyEntry.query.filter(VocabularyEntry.deck_id.in_(subtree_ids))
        .order_by(VocabularyEntry.id)
        .all()
    )
    now = datetime.utcnow()
    entry_ids = [entry.id for entry in entries]
    progress_map: Dict[int, VocabularyProgress] = {}
    if entry_ids:
        rows = VocabularyProgress.query.filter(
            VocabularyProgress.user_id == current_user.id,
            VocabularyProgress.entry_id.in_(entry_ids),
        ).all()
        progress_map = {row.entry_id: row for row in rows}

    card = _select_next_card(entries, progress_map, now)
    due_new = 0
    due_learn = 0
    due_review = 0
    for entry in entries:
        progress = progress_map.get(entry.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue in {LEARNING_QUEUE, RELEARNING_QUEUE}:
            due_learn += 1
        elif queue == REVIEW_QUEUE:
            due_review += 1
        else:
            due_new += 1

    next_intervals_preview = None
    if card:
        card_state = _card_state_from_progress(progress_map.get(card.id), now)
        next_intervals_preview = computeAnswerPreview(card_state, default_deck_options(), now)

    return render_template(
        "vocabulary_study.html",
        selected_level=None,
        selected_topic=SimpleNamespace(id=root_deck.id, name=root_deck.name),
        selected_lesson=None,
        card=card,
        due_new=due_new,
        due_learn=due_learn,
        due_review=due_review,
        due_total=due_new + due_learn + due_review,
        admin_mode=is_admin_user(current_user),
        study_scope="deck",
        study_scope_id=root_deck.id,
        study_root_name=root_deck.name,
        study_root_url=url_for("vocabulary.study_deck", deck_id=root_deck.id),
        next_study_url=url_for("vocabulary.study_deck", deck_id=root_deck.id),
        next_intervals_preview=next_intervals_preview,
    )


@vocabulary_bp.route("/study/lesson/<int:lesson_id>")
@login_required
def study_lesson(lesson_id: int):
    """Render flashcard-style study mode for non-admin users."""

    lesson_obj = VocabularyLesson.query.options(
        selectinload(VocabularyLesson.topic).selectinload(VocabularyTopic.level),
        selectinload(VocabularyLesson.entries),
    ).get_or_404(lesson_id)
    topic_obj = lesson_obj.topic
    level_obj = topic_obj.level
    entries = sorted(lesson_obj.entries, key=lambda item: item.id)
    now = datetime.utcnow()

    progress_map: Dict[int, VocabularyProgress] = {}
    entry_ids = [entry.id for entry in entries]
    if entry_ids:
        rows = VocabularyProgress.query.filter(
            VocabularyProgress.user_id == current_user.id,
            VocabularyProgress.entry_id.in_(entry_ids),
        ).all()
        progress_map = {row.entry_id: row for row in rows}

    card = _select_next_card(entries, progress_map, now)
    due_new = 0
    due_learn = 0
    due_review = 0
    for entry in entries:
        progress = progress_map.get(entry.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue in {LEARNING_QUEUE, RELEARNING_QUEUE}:
            due_learn += 1
        elif queue == REVIEW_QUEUE:
            due_review += 1
        else:
            due_new += 1

    next_intervals_preview = None
    if card:
        card_state = _card_state_from_progress(progress_map.get(card.id), now)
        next_intervals_preview = computeAnswerPreview(card_state, default_deck_options(), now)

    return render_template(
        "vocabulary_study.html",
        selected_level=level_obj,
        selected_topic=topic_obj,
        selected_lesson=lesson_obj,
        card=card,
        due_new=due_new,
        due_learn=due_learn,
        due_review=due_review,
        due_total=due_new + due_learn + due_review,
        admin_mode=is_admin_user(current_user),
        study_scope="lesson",
        study_scope_id=lesson_obj.id,
        study_root_name=topic_obj.name,
        study_root_url=url_for("vocabulary.study_topic", topic_id=topic_obj.id),
        next_study_url=url_for("vocabulary.study_lesson", lesson_id=lesson_obj.id),
        next_intervals_preview=next_intervals_preview,
    )


@vocabulary_bp.route("/study/entry/<int:entry_id>/answer", methods=["POST"])
@login_required
def study_answer(entry_id: int):
    """Apply a flashcard rating and update spaced-repetition progress."""
    if not request.is_json:
        return jsonify({"success": False, "message": "Invalid payload."}), 400

    data = request.get_json(silent=True) or {}
    rating = str(data.get("rating", "")).strip().lower()
    scope = str(data.get("scope", "lesson")).strip().lower()
    scope_id_raw = data.get("scope_id")
    if rating not in {"again", "hard", "good", "easy"}:
        return jsonify({"success": False, "message": "Invalid rating."}), 400

    entry = VocabularyEntry.query.options(selectinload(VocabularyEntry.lesson)).get_or_404(entry_id)
    progress = VocabularyProgress.query.filter_by(
        user_id=current_user.id, entry_id=entry.id
    ).first()
    now = datetime.utcnow()

    if not progress:
        progress = VocabularyProgress(
            user_id=current_user.id,
            entry_id=entry.id,
            queue=NEW_QUEUE,
            step_index=0,
            due_at=None,
            interval_days=0,
            ease_factor=default_deck_options().startingEase,
            reps=0,
            lapses=0,
        )
        db.session.add(progress)

    options = default_deck_options()
    current_state = _card_state_from_progress(progress, now)
    updated_state = applyAnswer(current_state, options, now, rating)  # type: ignore[arg-type]
    _apply_card_state_to_progress(progress, updated_state, now)

    next_url = None
    if entry.lesson_id:
        next_url = url_for("vocabulary.study_lesson", lesson_id=entry.lesson_id)
    
    if scope == "topic":
        try:
            topic_id = int(scope_id_raw or 0)
        except (TypeError, ValueError):
            topic_id = 0
        if topic_id:
            next_url = url_for("vocabulary.study_topic", topic_id=topic_id)
    elif scope == "deck":
        try:
            deck_id = int(scope_id_raw or 0)
        except (TypeError, ValueError):
            deck_id = 0
        if deck_id:
            next_url = url_for("vocabulary.study_deck", deck_id=deck_id)

    # Fallback to dashboard if no valid URL could be built
    if not next_url:
        next_url = url_for("main.dashboard")

    db.session.commit()
    return jsonify(
        {
            "success": True,
            "lesson_id": entry.lesson_id,
            "next_url": next_url,
        }
    )


@vocabulary_bp.route("/lesson/<int:lesson_id>")
@login_required
def lesson(lesson_id: int):
    """Display the editable grid for a specific lesson."""
    if not is_admin_user(current_user):
        return redirect(url_for("vocabulary.study_lesson", lesson_id=lesson_id))

    selected_lesson = (
        VocabularyLesson.query.options(
            selectinload(VocabularyLesson.topic)
            .selectinload(VocabularyTopic.level),
            selectinload(VocabularyLesson.topic)
            .selectinload(VocabularyTopic.lessons),
            selectinload(VocabularyLesson.entries),
        )
        .get_or_404(lesson_id)
    )

    topic = selected_lesson.topic
    level = topic.level
    topic_lessons = _sorted_lessons(topic)
    try:
        lesson_index = topic_lessons.index(selected_lesson) + 1
    except ValueError:
        lesson_index = 1

    if selected_lesson.position:
        lesson_index = selected_lesson.position

    entries = sorted(selected_lesson.entries, key=lambda entry: entry.id)

    page_size = selected_lesson.page_size or VOCABULARY_PAGE_SIZE
    placeholder_rows = max(PLACEHOLDER_ROW_COUNT, page_size - len(entries))
    total_lessons = len(topic_lessons)

    column_widths: Dict[str, str] = {}
    if current_user.is_authenticated:
        prefs = VocabularyColumnPreference.query.filter_by(user_id=current_user.id).all()
        column_widths = {}
        updated = False
        for pref in prefs:
            normalized_width = _normalize_column_width(pref.column_key, pref.width)
            column_widths[pref.column_key] = normalized_width
            if normalized_width != pref.width:
                pref.width = normalized_width
                updated = True
        if updated:
            db.session.commit()

    effective_total_width = max(
        COLUMN_TOTAL_DEFAULT_WIDTH,
        _compute_total_width(column_widths),
    )

    return render_template(
        "vocabulary_lesson.html",
        initial_lesson=lesson_index,
        total_lessons=total_lessons,
        entries=entries,
        page_size=page_size,
        start_index=1,
        column_widths=column_widths,
        column_keys=COLUMN_KEYS,
        column_default_widths=COLUMN_DEFAULT_WIDTHS,
        column_total_default_width=effective_total_width,
        multiline_fields=MULTILINE_FIELDS,
        editable_fields=EDITABLE_FIELDS,
        page_size_constant=page_size,
        placeholder_rows=placeholder_rows,
        export_formats=EXPORT_FORMATS,
        selected_level=level,
        selected_topic=topic,
        selected_lesson=selected_lesson,
        lesson_title=selected_lesson.title,
        sibling_lessons=topic_lessons,
    )


@vocabulary_bp.route("/lesson/<int:lesson_id>/download")
@login_required
def download_lesson_csv(lesson_id: int):
    """Provide vocabulary lesson export in the requested delimiter format."""
    lesson = (
        VocabularyLesson.query.options(selectinload(VocabularyLesson.entries))
        .get_or_404(lesson_id)
    )

    format_key = request.args.get("format", DEFAULT_EXPORT_FORMAT).lower()
    export_config = EXPORT_FORMATS.get(format_key)
    if not export_config:
        abort(400)

    entries = sorted(lesson.entries, key=lambda entry: entry.id)

    if not entries:
        flash("No data available for export.", "warning")
        return redirect(url_for("vocabulary.lesson", lesson_id=lesson.id))

    fieldnames = list(EXPECTED_HEADERS.values())
    buffer = StringIO()
    writer = csv.DictWriter(
        buffer,
        fieldnames=fieldnames,
        delimiter=export_config["delimiter"],
        quoting=csv.QUOTE_MINIMAL,
        lineterminator="\n",
    )
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
    safe_title = re.sub(r"[^A-Za-z0-9_-]+", "_", lesson.title).strip("_") or f"lesson_{lesson.id}"
    filename = f"lesson-{safe_title}.{export_config['extension']}"
    response.headers["Content-Disposition"] = f"attachment; filename={filename}"
    response.headers["Content-Type"] = export_config["content_type"]
    return response


@vocabulary_bp.route("/column-widths", methods=["POST"])
@login_required
def save_column_width():
    """Persist column width adjustments for the authenticated user."""
    data = request.get_json(silent=True) or {}
    column = data.get("column")
    width = data.get("width")

    if column not in COLUMN_KEYS:
        return jsonify({"success": False, "message": "D liu khng hp l."}), 400

    width_str = str(width) if width is not None else ""
    normalized_width = _normalize_column_width(column, width_str)
    pref = VocabularyColumnPreference.query.filter_by(
        user_id=current_user.id, column_key=column
    ).first()

    if pref:
        pref.width = normalized_width
    else:
        pref = VocabularyColumnPreference(
            user_id=current_user.id, column_key=column, width=normalized_width
        )
        db.session.add(pref)

    db.session.commit()
    return jsonify({"success": True, "width": normalized_width})


@vocabulary_bp.route("/entry", methods=["POST"])
@login_required
def create_entry():
    """Create a new vocabulary entry from pasted or inline data."""
    if not request.is_json:
        return jsonify({"success": False, "message": "D liu khng hp l."}), 400

    data = request.get_json(silent=True) or {}
    raw_values = data.get("values")
    if not isinstance(raw_values, dict):
        return jsonify({"success": False, "message": "Thiu d liu ct."}), 400

    lesson_id_raw = data.get("lesson_id")
    try:
        lesson_id = int(lesson_id_raw)
    except (TypeError, ValueError):
        lesson_id = 0

    lesson = VocabularyLesson.query.get(lesson_id) if lesson_id else None
    if not lesson:
        topic_id_raw = data.get("topic_id")
        try:
            topic_id = int(topic_id_raw or 0)
        except (TypeError, ValueError):
            topic_id = 0

        if topic_id:
            topic = (
                VocabularyTopic.query.options(
                    selectinload(VocabularyTopic.lessons).selectinload(VocabularyLesson.entries)
                ).get(topic_id)
            )
        else:
            topic = None

        if topic:
            lesson, _ = _select_lesson_for_append(topic, default_page_size=VOCABULARY_PAGE_SIZE)
        else:
            return jsonify({"success": False, "message": "Lesson not found."}), 400

    cleaned: Dict[str, str] = {}
    for field in EDITABLE_FIELDS:
        raw_val = raw_values.get(field, "")
        value = "" if raw_val is None else str(raw_val)
        cleaned[field] = value.replace("\r", "").strip()

    deck = cleaned.get("deck", "")
    word = cleaned.get("word", "")
    if not deck or not word:
        return jsonify({"success": False, "message": "Deck and Word cannot be empty."}), 400

    entry_kwargs = {field: (cleaned_val or None) for field, cleaned_val in cleaned.items()}
    entry_kwargs["lesson"] = lesson
    lesson_deck = _ensure_deck_path_for_lesson(lesson)
    if lesson_deck:
        entry_kwargs["deck_id"] = lesson_deck.id
    entry = VocabularyEntry(**entry_kwargs)
    db.session.add(entry)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Unable to save new entry."}), 500

    response_values = {field: getattr(entry, field) or "" for field in EDITABLE_FIELDS}
    return jsonify(
        {
            "success": True,
            "entry_id": entry.id,
            "lesson_id": lesson.id,
            "values": response_values,
        }
    )


@vocabulary_bp.route("/entry/<int:entry_id>/field", methods=["POST"])
@login_required
def update_entry_field(entry_id: int):
    """Update a specific field on a vocabulary entry."""
    if request.is_json:
        data = request.get_json(silent=True) or {}
        field = str(data.get("field", "")).strip()
        raw_value = data.get("value", "")
    else:
        field = request.form.get("field", "").strip()
        raw_value = request.form.get("value", "")
    if field not in EDITABLE_FIELDS:
        if request.is_json:
            return jsonify({"success": False, "message": "Trng khng hp l."}), 400
        return redirect(request.form.get("next") or url_for("vocabulary.index"))

    entry = VocabularyEntry.query.get_or_404(entry_id)

    value = "" if raw_value is None else str(raw_value)
    cleaned = value.strip()
    if request.is_json and field in {"deck", "word"} and not cleaned:
        return jsonify({"success": False, "message": "Deck and Word cannot be empty."}), 400
    setattr(entry, field, cleaned or None)
    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        if request.is_json:
            return jsonify({"success": False, "message": "Unable to update entry."}), 500
        flash("Unable to update entry.", "danger")
        return redirect(request.form.get("next") or url_for("vocabulary.index"))

    if request.is_json:
        return jsonify({"success": True, "field": field, "value": cleaned})

    next_url = request.form.get("next") or url_for("vocabulary.index")
    return redirect(next_url)


@vocabulary_bp.route("/entry/<int:entry_id>/fields", methods=["POST"])
@login_required
def update_entry_fields(entry_id: int):
    """Update multiple fields on a vocabulary entry in one request."""
    if not request.is_json:
        return jsonify({"success": False, "message": "Du lieu khong hop le."}), 400

    data = request.get_json(silent=True) or {}
    raw_updates = data.get("values")
    if not isinstance(raw_updates, dict):
        return jsonify({"success": False, "message": "Thieu truong cap nhat."}), 400

    entry = VocabularyEntry.query.get_or_404(entry_id)

    cleaned_updates: Dict[str, str] = {}
    for field, raw_value in raw_updates.items():
        field_name = str(field).strip()
        if field_name not in EDITABLE_FIELDS:
            continue
        value = "" if raw_value is None else str(raw_value)
        cleaned_updates[field_name] = value.replace("\r", "").strip()

    if not cleaned_updates:
        return jsonify({"success": False, "message": "Khong co truong hop le."}), 400

    if "deck" in cleaned_updates and not cleaned_updates["deck"]:
        return jsonify({"success": False, "message": "Deck cannot be empty."}), 400
    if "word" in cleaned_updates and not cleaned_updates["word"]:
        return jsonify({"success": False, "message": "Word cannot be empty."}), 400

    for field, cleaned in cleaned_updates.items():
        setattr(entry, field, cleaned or None)

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Unable to update entry."}), 500

    response_values = {field: getattr(entry, field) or "" for field in cleaned_updates}
    return jsonify({"success": True, "values": response_values})


@vocabulary_bp.route("/entries/bulk", methods=["POST"])
@login_required
def bulk_update_entries():
    """Update multiple entries/fields in a single request."""
    if not request.is_json:
        return jsonify({"success": False, "message": "Du lieu khong hop le."}), 400

    data = request.get_json(silent=True) or {}
    updates = data.get("updates")
    if not isinstance(updates, list) or not updates:
        return jsonify({"success": False, "message": "Thieu du lieu cap nhat."}), 400

    lesson_id_raw = data.get("lesson_id")
    try:
        lesson_id = int(lesson_id_raw or 0)
    except (TypeError, ValueError):
        lesson_id = 0

    lesson: Optional[VocabularyLesson] = None
    if lesson_id:
        lesson = VocabularyLesson.query.get(lesson_id)

    normalized_updates = []
    entry_ids = set()
    for item in updates:
        if not isinstance(item, dict):
            return jsonify({"success": False, "message": "Du lieu cap nhat khong hop le."}), 400
        entry_id_raw = item.get("entry_id")
        if entry_id_raw in (None, ""):
            entry_id = None
        else:
            try:
                entry_id = int(entry_id_raw)
            except (TypeError, ValueError):
                return jsonify({"success": False, "message": "Ma ban ghi khong hop le."}), 400
        raw_values = item.get("values")
        if not isinstance(raw_values, dict):
            return jsonify({"success": False, "message": "Thieu gia tri cap nhat."}), 400
        normalized_updates.append((entry_id, raw_values))
        if entry_id:
            entry_ids.add(entry_id)

    entry_map = {}
    if entry_ids:
        existing_entries = VocabularyEntry.query.filter(VocabularyEntry.id.in_(entry_ids)).all()
        entry_map = {entry.id: entry for entry in existing_entries}

    results = []
    try:
        for entry_id, raw_values in normalized_updates:
            cleaned = {}
            for field, raw_value in raw_values.items():
                field_name = str(field).strip()
                if field_name not in EDITABLE_FIELDS:
                    continue
                value = "" if raw_value is None else str(raw_value)
                cleaned[field_name] = value.replace("\r", "").strip()

            if entry_id:
                entry = entry_map.get(entry_id)
                if not entry:
                    return jsonify({"success": False, "message": f"Entry {entry_id} not found."}), 404
                if not cleaned:
                    results.append({"entry_id": entry.id, "values": {}})
                    continue
                if "deck" in cleaned and not cleaned["deck"]:
                    return jsonify({"success": False, "message": "Deck cannot be empty."}), 400
                if "word" in cleaned and not cleaned["word"]:
                    return jsonify({"success": False, "message": "Word cannot be empty."}), 400
                for field_name, cleaned_value in cleaned.items():
                    setattr(entry, field_name, cleaned_value or None)
                result_values = {field_name: getattr(entry, field_name) or "" for field_name in cleaned}
                results.append({"entry_id": entry.id, "values": result_values})
            else:
                if lesson is None:
                    if not lesson_id:
                        return jsonify({"success": False, "message": "Lesson id is required for new entries."}), 400
                    lesson = VocabularyLesson.query.get(lesson_id)
                    if not lesson:
                        return jsonify({"success": False, "message": "Lesson not found."}), 404
                deck = cleaned.get("deck", "")
                word = cleaned.get("word", "")
                if not deck or not word:
                    return jsonify({"success": False, "message": "Deck and Word cannot be empty."}), 400
                entry_kwargs = {field: (cleaned.get(field) or None) for field in EDITABLE_FIELDS}
                entry_kwargs["lesson"] = lesson
                lesson_deck = _ensure_deck_path_for_lesson(lesson)
                if lesson_deck:
                    entry_kwargs["deck_id"] = lesson_deck.id
                entry = VocabularyEntry(**entry_kwargs)
                db.session.add(entry)
                db.session.flush()
                entry_map[entry.id] = entry
                result_values = {field: getattr(entry, field) or "" for field in EDITABLE_FIELDS}
                results.append({"entry_id": entry.id, "values": result_values})

        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"success": False, "message": "Unable to update entries."}), 500

    return jsonify({"success": True, "results": results})


@vocabulary_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    """Allow users to paste CSV data to populate the vocabulary table."""
    levels = _get_levels_hierarchy()
    if request.method == "POST":
        csv_content = request.form.get("csv_content", "").strip()
        topic_id_raw = request.form.get("topic_id")

        try:
            topic_id = int(topic_id_raw or 0)
        except ValueError:
            topic_id = 0

        topic = (
            VocabularyTopic.query.options(
                selectinload(VocabularyTopic.level),
                selectinload(VocabularyTopic.lessons).selectinload(VocabularyLesson.entries),
            ).get(topic_id)
        )
        if not topic:
            flash("Please choose a valid topic before importing.", "warning")
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                csv_content=csv_content,
                levels=levels,
                selected_topic_id=topic_id,
            )

        if not csv_content:
            flash("Paste CSV content before importing.", "warning")
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                levels=levels,
                selected_topic_id=topic_id,
            )

        buffer = StringIO(csv_content)
        reader = csv.DictReader(buffer)

        if not reader.fieldnames:
            flash("CSV must include a header row.", "danger")
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                csv_content=csv_content,
                levels=levels,
                selected_topic_id=topic_id,
            )

        normalized_headers = [_normalize_header(h) for h in reader.fieldnames]
        mapping: Dict[str, str] = {}

        for original, normalized in zip(reader.fieldnames, normalized_headers):
            if normalized in EXPECTED_HEADERS:
                mapping[EXPECTED_HEADERS[normalized]] = original

        missing_core = [field for field in ("deck", "word") if field not in mapping]
        if missing_core:
            flash(
                "Missing required columns in CSV: " + ", ".join(missing_core),
                "danger",
            )
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                csv_content=csv_content,
                levels=levels,
                selected_topic_id=topic_id,
            )

        lessons_sorted = _sorted_lessons(topic)
        if lessons_sorted:
            current_lesson = lessons_sorted[-1]
            entries_in_current = _lesson_entry_count(current_lesson)
        else:
            current_lesson = _create_topic_lesson(topic, commit=False)
            entries_in_current = 0

        default_page_size = current_lesson.page_size or VOCABULARY_PAGE_SIZE
        last_lesson = current_lesson
        inserted = 0
        try:
            for row in reader:
                if not row:
                    continue

                deck = row.get(mapping["deck"], "").strip()
                word = row.get(mapping["word"], "").strip()
                if not deck or not word:
                    continue

                if entries_in_current >= (current_lesson.page_size or default_page_size):
                    current_lesson = _create_topic_lesson(topic, commit=False)
                    entries_in_current = 0
                    default_page_size = current_lesson.page_size or VOCABULARY_PAGE_SIZE
                last_lesson = current_lesson
                current_lesson_deck = _ensure_deck_path_for_lesson(current_lesson)

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
                    lesson=current_lesson,
                    deck_id=current_lesson_deck.id if current_lesson_deck else None,
                )

                db.session.add(entry)
                entries_in_current += 1
                inserted += 1

            db.session.commit()
        except Exception as exc:  # pragma: no cover
            db.session.rollback()
            flash(f"Failed to import CSV: {exc}", "danger")
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                csv_content=csv_content,
                levels=levels,
                selected_topic_id=topic_id,
            )

        if inserted == 0:
            flash("No rows were imported.", "warning")
            return render_template(
                "vocabulary_import.html",
                sample_headers=EXPECTED_HEADERS.keys(),
                levels=levels,
                selected_topic_id=topic_id,
            )

        flash(f"Imported {inserted} rows.", "success")
        return redirect(url_for("vocabulary.lesson", lesson_id=last_lesson.id))

    return render_template(
        "vocabulary_import.html",
        sample_headers=EXPECTED_HEADERS.keys(),
        levels=levels,
    )
