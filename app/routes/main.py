"""Primary navigation routes."""

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List

from flask import Blueprint, jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services.anki_scheduler import (
    _day_index as scheduler_day_index,
    _day_index_to_datetime as scheduler_day_index_to_datetime,
)
from app.services.stats_overview import build_stats_overview
from app.services.stats_today_future import build_today_future_stats, list_stats_decks
from app.utils.deck_move_token import create_deck_move_token
from app.utils.permissions import is_admin_user
from models import db
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, Note
from models.deck import Deck
from models.card_progress import CardProgress

main_bp = Blueprint("main", __name__)


def _day_index(moment: datetime, boundary_hour: int) -> int:
    return scheduler_day_index(moment, boundary_hour)


def _day_index_to_datetime(day_index: int, boundary_hour: int) -> datetime:
    return scheduler_day_index_to_datetime(day_index, boundary_hour)


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

    # Admin sees own/source decks only (exclude decks cloned for other users)
    if admin_mode:
        decks = (
            Deck.query.filter(
                db.or_(
                    Deck.owner_user_id == current_user.id,
                    Deck.owner_user_id.is_(None),
                )
            )
            .order_by(
                Deck.parent_id.isnot(None),
                Deck.position,
                Deck.created_at,
                Deck.id,
            )
            .all()
        )
    else:
        # Get only decks installed by this user
        installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
        installed_root_ids = {inst.local_deck_id for inst in installs if inst.local_deck_id}
        if installed_root_ids:
            visible_ids: set[int] = set()
            frontier: set[int] = {int(deck_id) for deck_id in installed_root_ids}
            while frontier:
                current_ids = {deck_id for deck_id in frontier if deck_id not in visible_ids}
                if not current_ids:
                    break
                visible_ids.update(current_ids)
                child_rows = (
                    db.session.query(Deck.id)
                    .filter(Deck.parent_id.in_(current_ids))
                    .all()
                )
                frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}

            decks = (
                Deck.query.filter(Deck.id.in_(visible_ids))
                .order_by(
                    Deck.parent_id.isnot(None),
                    Deck.position,
                    Deck.created_at,
                    Deck.id,
                )
                .all()
            )
        else:
            decks = []

    @dataclass
    class DeckNode:
        deck_id: int
        parent_id: int | None
        move_alias: str
        move_token: str
        parent_move_alias: str | None
        parent_move_token: str | None
        label: str
        href: str
        depth: int
        new_count: int
        learn_count: int
        due_count: int
        children: List["DeckNode"] = field(default_factory=list)

    now = datetime.utcnow()

    visible_deck_ids = [deck.id for deck in decks if deck.id is not None]
    card_counts_by_deck: Dict[int, Dict[str, int]] = {
        int(deck_id): {"total": 0, "new": 0, "learn": 0, "due": 0}
        for deck_id in visible_deck_ids
    }
    if visible_deck_ids:
        progress_join = db.and_(
            CardProgress.card_id == Card.id,
            CardProgress.user_id == current_user.id,
        )
        state_rows = (
            db.session.query(
                Note.deck_id,
                CardProgress.queue,
                CardProgress.due_at,
            )
            .select_from(Card)
            .join(Note, Card.note_id == Note.id)
            .outerjoin(CardProgress, progress_join)
            .filter(
                Note.user_id == current_user.id,
                Note.deck_id.in_(visible_deck_ids),
            )
            .all()
        )
        for deck_id, progress_queue, progress_due_at in state_rows:
            if not deck_id:
                continue
            bucket = card_counts_by_deck.setdefault(
                int(deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
            )
            bucket["total"] += 1

            queue_value = progress_queue
            due_at_value = progress_due_at
            queue_norm = (queue_value or "new").strip().lower()
            if queue_norm == "learn":
                queue_norm = "learning"

            if queue_norm == "new":
                bucket["new"] += 1
            elif queue_norm in {"learning", "relearning"}:
                bucket["learn"] += 1
            elif queue_norm == "review" and (due_at_value is None or due_at_value <= now):
                bucket["due"] += 1

        if not admin_mode:
            logical_installs = [
                install
                for install in installs
                if install.clone_mode == "logical_overlay" and install.id and install.local_deck_id
            ]
            for install in logical_installs:
                map_rows = (
                    DeckCloneDeckMap.query.filter_by(deck_install_id=install.id)
                    .order_by(DeckCloneDeckMap.local_deck_id.asc(), DeckCloneDeckMap.source_deck_id.asc())
                    .all()
                )
                source_to_local = {
                    int(row.source_deck_id): int(row.local_deck_id)
                    for row in map_rows
                    if row.source_deck_id is not None
                    and row.local_deck_id is not None
                    and int(row.local_deck_id) in card_counts_by_deck
                }
                if not source_to_local:
                    continue

                clone_query = (
                    db.session.query(
                        Note.deck_id,
                        CardProgress.queue,
                        CardProgress.due_at,
                    )
                    .select_from(Card)
                    .join(Note, Card.note_id == Note.id)
                    .outerjoin(CardProgress, progress_join)
                    .filter(Note.deck_id.in_(source_to_local.keys()))
                )
                if install.source_owner_user_id is not None:
                    clone_query = clone_query.filter(Note.user_id == install.source_owner_user_id)
                snapshot_at = install.base_snapshot_at or install.installed_at
                if snapshot_at is not None:
                    clone_query = clone_query.filter(
                        Note.created_at <= snapshot_at,
                        Card.created_at <= snapshot_at,
                    )

                for source_deck_id, progress_queue, progress_due_at in clone_query.all():
                    if source_deck_id is None:
                        continue
                    local_deck_id = source_to_local.get(int(source_deck_id))
                    if local_deck_id is None:
                        continue
                    bucket = card_counts_by_deck.setdefault(
                        int(local_deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
                    )
                    bucket["total"] += 1

                    queue_value = progress_queue
                    due_at_value = progress_due_at
                    queue_norm = (queue_value or "new").strip().lower()
                    if queue_norm == "learn":
                        queue_norm = "learning"

                    if queue_norm == "new":
                        bucket["new"] += 1
                    elif queue_norm in {"learning", "relearning"}:
                        bucket["learn"] += 1
                    elif queue_norm == "review" and (due_at_value is None or due_at_value <= now):
                        bucket["due"] += 1
    
    by_parent: Dict[int | None, List[Deck]] = {}
    for deck in decks:
        by_parent.setdefault(deck.parent_id, []).append(deck)

    for children in by_parent.values():
        children.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    move_alias_by_deck_id: Dict[int, str] = {}
    move_token_by_deck_id: Dict[int, str] = {}
    used_move_aliases: set[str] = set()
    for deck in decks:
        move_token = create_deck_move_token(deck.id, current_user.id)
        digest = hashlib.sha256(move_token.encode("utf-8")).hexdigest().upper()
        alias_len = 10
        move_alias = f"MID-{digest[:alias_len]}"
        while move_alias in used_move_aliases and alias_len < len(digest):
            alias_len += 2
            move_alias = f"MID-{digest[:alias_len]}"
        if move_alias in used_move_aliases:
            move_alias = f"MID-{digest}"

        used_move_aliases.add(move_alias)
        move_alias_by_deck_id[deck.id] = move_alias
        move_token_by_deck_id[deck.id] = move_token

    subtree_card_counts_cache: Dict[int, Dict[str, int]] = {}

    def _collect_subtree_card_counts(deck_id: int) -> Dict[str, int]:
        cached = subtree_card_counts_cache.get(deck_id)
        if cached is not None:
            return cached

        base = card_counts_by_deck.get(
            deck_id, {"total": 0, "new": 0, "learn": 0, "due": 0}
        )
        collected = {
            "total": int(base["total"]),
            "new": int(base["new"]),
            "learn": int(base["learn"]),
            "due": int(base["due"]),
        }
        for child in by_parent.get(deck_id, []):
            child_counts = _collect_subtree_card_counts(child.id)
            collected["total"] += int(child_counts["total"])
            collected["new"] += int(child_counts["new"])
            collected["learn"] += int(child_counts["learn"])
            collected["due"] += int(child_counts["due"])

        subtree_card_counts_cache[deck_id] = collected
        return collected

    def _build_nodes(parent_id: int | None, depth: int) -> List[DeckNode]:
        nodes: List[DeckNode] = []
        for deck in by_parent.get(parent_id, []):
            card_counts = _collect_subtree_card_counts(deck.id)
            deck_new = int(card_counts["new"])
            deck_learn = int(card_counts["learn"])
            deck_due = int(card_counts["due"])
            nodes.append(
                DeckNode(
                    deck_id=deck.id,
                    parent_id=deck.parent_id,
                    move_alias=move_alias_by_deck_id.get(deck.id, ""),
                    move_token=move_token_by_deck_id.get(deck.id, ""),
                    parent_move_alias=move_alias_by_deck_id.get(deck.parent_id) if deck.parent_id else None,
                    parent_move_token=move_token_by_deck_id.get(deck.parent_id) if deck.parent_id else None,
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
        stats_initial_year=datetime.utcnow().year,
    )


@main_bp.route("/statistics", methods=["GET"])
@login_required
def statistics_page():
    decks = list_stats_decks(current_user.id)
    deck_id_raw = (request.args.get("deck_id") or "").strip()
    initial_deck_id = None
    if deck_id_raw:
        try:
            initial_deck_id = int(deck_id_raw)
        except ValueError:
            initial_deck_id = None

    deck_ids = {int(deck["id"]) for deck in decks}
    if initial_deck_id not in deck_ids:
        initial_deck_id = int(decks[0]["id"]) if decks else None

    return render_template(
        "statistics.html",
        stats_decks=decks,
        stats_initial_deck_id=initial_deck_id,
    )


@main_bp.route("/api/stats/overview", methods=["GET"])
@login_required
def stats_overview():
    year_raw = (request.args.get("year") or "").strip()
    year: int | None = None
    if year_raw:
        try:
            year = int(year_raw)
        except ValueError:
            return jsonify({"error": "VALIDATION_ERROR", "message": "year must be an integer."}), 400
        if year < 1970 or year > 2100:
            return jsonify({"error": "VALIDATION_ERROR", "message": "year must be between 1970 and 2100."}), 400

    payload = build_stats_overview(
        user_id=current_user.id,
        year=year,
        timezone_name=getattr(current_user, "timezone", "UTC"),
    )
    return jsonify(payload)


@main_bp.route("/api/stats/today-future", methods=["GET"])
@login_required
def stats_today_future():
    scope = (request.args.get("scope") or "deck").strip().lower()
    history_range = (request.args.get("history_range") or "12m").strip().lower()
    future_range = (request.args.get("future_range") or "30").strip().lower()
    backlog = (request.args.get("backlog") or "false").strip().lower()

    deck_id_raw = (request.args.get("deck_id") or "").strip()
    deck_id = None
    if deck_id_raw:
        try:
            deck_id = int(deck_id_raw)
        except ValueError:
            return jsonify({"error": "VALIDATION_ERROR", "message": "deck_id must be an integer."}), 400

    if scope not in {"deck", "collection"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "scope must be deck or collection."}), 400
    if history_range not in {"12m", "all"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "history_range must be 12m or all."}), 400
    if future_range not in {"30", "90", "365", "all"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "future_range must be 30, 90, 365, or all."}), 400
    if backlog not in {"0", "1", "true", "false", "yes", "no", "on", "off"}:
        return jsonify({"error": "VALIDATION_ERROR", "message": "backlog must be a boolean-like value."}), 400

    payload = build_today_future_stats(
        user_id=current_user.id,
        timezone_name=getattr(current_user, "timezone", "UTC"),
        scope=scope,
        deck_id=deck_id,
        history_range=history_range,
        future_range=future_range,
        backlog=backlog,
    )
    return jsonify(payload)
