"""Primary navigation routes."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

from app.utils.permissions import is_admin_user
from models.vocabulary_progress import VocabularyProgress
from models.vocabulary_structure import VocabularyLevel, VocabularyTopic, VocabularyLesson

main_bp = Blueprint("main", __name__)


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    admin_mode = is_admin_user(current_user)
    levels = (
        VocabularyLevel.query.options(
            selectinload(VocabularyLevel.topics).selectinload(VocabularyTopic.lessons).selectinload(
                VocabularyLesson.entries
            )
        )
        .order_by(VocabularyLevel.position, VocabularyLevel.created_at)
        .all()
    )

    @dataclass
    class DeckNode:
        label: str
        href: str
        depth: int
        new_count: int
        learn_count: int
        due_count: int
        children: List["DeckNode"] = field(default_factory=list)

    entry_ids: List[int] = []
    for level in levels:
        for topic in level.topics:
            for lesson in topic.lessons:
                for entry in lesson.entries:
                    if entry.id:
                        entry_ids.append(entry.id)

    progress_map = {}
    if entry_ids:
        progress_rows = VocabularyProgress.query.filter(
            VocabularyProgress.user_id == current_user.id,
            VocabularyProgress.entry_id.in_(entry_ids),
        ).all()
        progress_map = {row.entry_id: row for row in progress_rows}

    now = datetime.utcnow()

    def _stats_from_entries(entries) -> tuple[int, int, int]:
        new_count = 0
        learn_count = 0
        due_count = 0
        for entry in entries:
            progress = progress_map.get(entry.id)
            if progress is None or progress.queue == "new":
                new_count += 1
                continue

            due_at = progress.due_at
            is_due = due_at is None or due_at <= now

            if progress.queue == "learn":
                if is_due:
                    learn_count += 1
                    due_count += 1
                continue

            if progress.queue == "review":
                if is_due:
                    due_count += 1
                continue

        return new_count, learn_count, due_count

    rows: List[DeckNode] = []
    total_new = 0
    total_learn = 0
    total_due = 0

    for level in levels:
        topic_nodes: List[DeckNode] = []
        level_new = 0
        level_learn = 0
        level_due = 0
        for topic in sorted(level.topics, key=lambda t: ((t.position or 0), t.created_at)):
            lesson_nodes: List[DeckNode] = []
            topic_new = 0
            topic_learn = 0
            topic_due = 0
            for lesson in sorted(topic.lessons, key=lambda ls: ((ls.position or 0), ls.created_at)):
                lesson_new, lesson_learn, lesson_due = _stats_from_entries(lesson.entries)
                topic_new += lesson_new
                topic_learn += lesson_learn
                topic_due += lesson_due
                lesson_nodes.append(
                    DeckNode(
                        label=lesson.title,
                        href=url_for("vocabulary.study_lesson", lesson_id=lesson.id),
                        depth=2,
                        new_count=lesson_new,
                        learn_count=lesson_learn,
                        due_count=lesson_due,
                    )
                )

            level_new += topic_new
            level_learn += topic_learn
            level_due += topic_due
            topic_nodes.append(
                DeckNode(
                    label=topic.name,
                    href=url_for("vocabulary.study_topic", topic_id=topic.id),
                    depth=1,
                    new_count=topic_new,
                    learn_count=topic_learn,
                    due_count=topic_due,
                    children=lesson_nodes,
                )
            )

        level_node = DeckNode(
            label=level.name,
            href=url_for("vocabulary.index"),
            depth=0,
            new_count=level_new,
            learn_count=level_learn,
            due_count=level_due,
            children=topic_nodes,
        )
        rows.append(level_node)
        total_new += level_new
        total_learn += level_learn
        total_due += level_due

    return render_template(
        "dashboard.html",
        deck_rows=rows,
        total_new=total_new,
        total_learn=total_learn,
        total_due=total_due,
        admin_mode=admin_mode,
    )
