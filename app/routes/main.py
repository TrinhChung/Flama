"""Primary navigation routes."""

from dataclasses import dataclass, field
from typing import List

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required
from sqlalchemy.orm import selectinload

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

    def _stats_from_total(total: int) -> tuple[int, int, int]:
        # Keep a familiar Anki-like distribution while remaining deterministic.
        if total <= 0:
            return 0, 0, 0
        learn_count = min(30, max(0, total // 6))
        new_count = max(0, total - learn_count)
        due_count = total
        return new_count, learn_count, due_count

    rows: List[DeckNode] = []
    total_new = 0
    total_learn = 0
    total_due = 0

    for level in levels:
        topic_nodes: List[DeckNode] = []
        level_total_entries = 0
        for topic in sorted(level.topics, key=lambda t: ((t.position or 0), t.created_at)):
            lesson_nodes: List[DeckNode] = []
            topic_total_entries = 0
            for lesson in sorted(topic.lessons, key=lambda ls: ((ls.position or 0), ls.created_at)):
                lesson_entries = len(lesson.entries)
                topic_total_entries += lesson_entries
                lesson_new, lesson_learn, lesson_due = _stats_from_total(lesson_entries)
                lesson_nodes.append(
                    DeckNode(
                        label=lesson.title,
                        href=url_for("vocabulary.lesson", lesson_id=lesson.id),
                        depth=2,
                        new_count=lesson_new,
                        learn_count=lesson_learn,
                        due_count=lesson_due,
                    )
                )

            level_total_entries += topic_total_entries
            topic_new, topic_learn, topic_due = _stats_from_total(topic_total_entries)
            topic_nodes.append(
                DeckNode(
                    label=topic.name,
                    href=url_for("vocabulary.topic", topic_id=topic.id),
                    depth=1,
                    new_count=topic_new,
                    learn_count=topic_learn,
                    due_count=topic_due,
                    children=lesson_nodes,
                )
            )

        level_new, level_learn, level_due = _stats_from_total(level_total_entries)
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
    )
