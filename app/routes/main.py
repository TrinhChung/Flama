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
    from app.services.dashboard_service import build_dashboard_data
    rows, total_new, total_learn, total_due, admin_mode = build_dashboard_data(current_user)

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
