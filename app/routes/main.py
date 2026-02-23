"""Primary navigation routes."""

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from typing import Dict, List

from flask import Blueprint, redirect, render_template, url_for
from flask_login import current_user, login_required

from app.services.anki_scheduler import default_deck_options
from app.utils.permissions import is_admin_user
from models.flashcard import DeckInstall
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_entry import VocabularyEntry
from models.vocabulary_progress import VocabularyProgress

main_bp = Blueprint("main", __name__)


def _day_index(moment: datetime, boundary_hour: int) -> int:
    """Convert datetime to day index (ordinal) relative to boundary hour."""
    shifted = moment - timedelta(hours=boundary_hour)
    return shifted.date().toordinal()


def _day_index_to_datetime(day_index: int, boundary_hour: int) -> datetime:
    """Convert day index (ordinal) back to datetime at boundary hour."""
    day_date = date.fromordinal(day_index)
    return datetime.combine(day_date, time(hour=boundary_hour))


@main_bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for("main.dashboard"))
    return render_template("index.html")


@main_bp.route("/terms")
def terms():
    return render_template("terms.html")


@main_bp.route("/privacy")
def privacy():
    return render_template("privacy.html")


@main_bp.route("/cookies")
def cookies():
    return render_template("cookies.html")


@main_bp.route("/dashboard")
@login_required
def dashboard():
    admin_mode = is_admin_user(current_user)

    # Admin sees all decks; regular users only see decks they have installed
    if admin_mode:
        decks = (
            VocabularyDeck.query.order_by(
                VocabularyDeck.parent_id.isnot(None),
                VocabularyDeck.position,
                VocabularyDeck.created_at,
                VocabularyDeck.id,
            )
            .all()
        )
    else:
        # Get only decks installed by this user
        installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
        installed_deck_ids = {inst.local_deck_id for inst in installs if inst.local_deck_id}
        if installed_deck_ids:
            decks = (
                VocabularyDeck.query.filter(VocabularyDeck.id.in_(installed_deck_ids))
                .order_by(
                    VocabularyDeck.parent_id.isnot(None),
                    VocabularyDeck.position,
                    VocabularyDeck.created_at,
                    VocabularyDeck.id,
                )
                .all()
            )
        else:
            decks = []

    @dataclass
    class DeckNode:
        deck_id: int
        parent_id: int | None
        label: str
        href: str
        depth: int
        new_count: int
        learn_count: int
        due_count: int
        children: List["DeckNode"] = field(default_factory=list)

    entries = (
        VocabularyEntry.query.filter(VocabularyEntry.deck_id.isnot(None))
        .order_by(VocabularyEntry.id)
        .all()
    )
    entry_ids = [entry.id for entry in entries if entry.id]

    progress_map = {}
    if entry_ids:
        progress_rows = VocabularyProgress.query.filter(
            VocabularyProgress.user_id == current_user.id,
            VocabularyProgress.entry_id.in_(entry_ids),
        ).all()
        progress_map = {row.entry_id: row for row in progress_rows}

    now = datetime.utcnow()
    options = default_deck_options()
    
    # Calculate today's day index and next day boundary according to dayBoundaryHourLocal
    today_day_index = _day_index(now, options.dayBoundaryHourLocal)
    next_day_boundary = _day_index_to_datetime(today_day_index + 1, options.dayBoundaryHourLocal)

    def _normalize_queue(value: str | None) -> str:
        normalized = (value or "new").strip().lower()
        if normalized == "learn":
            return "learning"
        if normalized in {"new", "learning", "review", "relearning"}:
            return normalized
        return "new"

    def _stats_from_entry_ids(node_entry_ids: List[int]) -> tuple[int, int, int]:
        new_count = 0
        learn_count = 0
        due_count = 0
        for entry_id in node_entry_ids:
            progress = progress_map.get(entry_id)
            queue = _normalize_queue(progress.queue if progress else "new")
            if progress is None or queue == "new":
                new_count += 1
                continue

            due_at = progress.due_at
            due_day = progress.due_day

            # Learning/Relearning cards: count if due_at < nextDayBoundary
            # This ensures all learning cards scheduled for "today" appear in Learn count
            if queue in {"learning", "relearning"}:
                if due_at and due_at < next_day_boundary:
                    learn_count += 1
                continue

            # Review cards: count if due_day <= today_day_index
            # due_day is stored as ordinal int, today is also ordinal int
            if queue == "review":
                # Use stored due_day if available, otherwise calculate from due_at
                if due_day is not None:
                    card_due_day = due_day
                else:
                    # Backward compatibility: calculate from due_at
                    card_due_day = _day_index(due_at or now, options.dayBoundaryHourLocal)
                
                if card_due_day <= today_day_index:
                    due_count += 1
                continue

        return new_count, learn_count, due_count

    by_parent: Dict[int | None, List[VocabularyDeck]] = {}
    for deck in decks:
        by_parent.setdefault(deck.parent_id, []).append(deck)

    for children in by_parent.values():
        children.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    entries_by_deck: Dict[int, List[int]] = {}
    for entry in entries:
        if entry.deck_id is None:
            continue
        entries_by_deck.setdefault(entry.deck_id, []).append(entry.id)

    subtree_entry_ids_cache: Dict[int, List[int]] = {}

    def _collect_subtree_entry_ids(deck_id: int) -> List[int]:
        cached = subtree_entry_ids_cache.get(deck_id)
        if cached is not None:
            return cached
        collected = list(entries_by_deck.get(deck_id, []))
        for child in by_parent.get(deck_id, []):
            collected.extend(_collect_subtree_entry_ids(child.id))
        subtree_entry_ids_cache[deck_id] = collected
        return collected

    def _build_nodes(parent_id: int | None, depth: int) -> List[DeckNode]:
        nodes: List[DeckNode] = []
        for deck in by_parent.get(parent_id, []):
            subtree_ids = _collect_subtree_entry_ids(deck.id)
            deck_new, deck_learn, deck_due = _stats_from_entry_ids(subtree_ids)
            nodes.append(
                DeckNode(
                    deck_id=deck.id,
                    parent_id=deck.parent_id,
                    label=deck.name,
                    href=url_for("vocabulary.study_deck", deck_id=deck.id),
                    depth=depth,
                    new_count=deck_new,
                    learn_count=deck_learn,
                    due_count=deck_due,
                    children=_build_nodes(deck.id, depth + 1),
                )
            )
        return nodes

    rows = _build_nodes(None, 0)

    total_new = 0
    total_learn = 0
    total_due = 0
    for row in rows:
        total_new += row.new_count
        total_learn += row.learn_count
        total_due += row.due_count

    return render_template(
        "dashboard.html",
        deck_rows=rows,
        total_new=total_new,
        total_learn=total_learn,
        total_due=total_due,
        admin_mode=admin_mode,
    )
