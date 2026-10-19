"""Vocabulary management routes."""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    request,
    url_for,
)
from flask_login import current_user, login_required
from app.spa import serve_react_spa
from app.utils.permissions import is_admin_user
from app.utils.redirects import resolve_safe_next_url
from models.deck import Deck

vocabulary_bp = Blueprint("vocabulary", __name__, url_prefix="/vocabulary")


def _utcnow() -> datetime:
    return datetime.utcnow()


@vocabulary_bp.before_request
def restrict_non_admin_routes():
    """Allow regular users to access only study mode endpoints."""
    if not current_user.is_authenticated:
        return None
    if is_admin_user(current_user):
        return None

    endpoint = request.endpoint or ""
    allowed_endpoints = {
        "vocabulary.index",
        "vocabulary.study_deck",
        "vocabulary.browse",
        "vocabulary.legacy_structure_removed",
    }
    if endpoint in allowed_endpoints:
        return None
    return redirect(url_for("main.dashboard"))


def _legacy_structure_removed_response():
    message = (
        "Legacy Level/Topic/Lesson/Entry workflow has been removed. "
        "Use Deck + NoteType + Note + Card schema only."
    )
    if request.is_json:
        return jsonify({"success": False, "error": "LEGACY_STRUCTURE_REMOVED", "message": message}), 410
    if request.method == "GET":
        return message, 410
    flash(message, "warning")
    next_url = resolve_safe_next_url(
        request.form.get("next") or request.args.get("next"),
        default_endpoint="vocabulary.browse",
    )
    return redirect(next_url)


@vocabulary_bp.route("/")
@login_required
def index():
    """Legacy hierarchy index removed; redirect to browse."""
    return redirect(url_for("vocabulary.browse"))


@vocabulary_bp.route("/browse")
@login_required
def browse():
    """Anki-like browser interface."""
    return serve_react_spa()


@vocabulary_bp.route("/study/deck/<int:deck_id>")
@login_required
def study_deck(deck_id: int):
    """Serve the React Study page for a deck subtree.

    ``serve_react_spa`` ignores template context: the SPA loads its queue,
    card and counts from ``/api/study/*``. Building them here (a full locking
    read of every Card of the subtree) only delayed the page.
    """
    root_deck = Deck.query.get(deck_id)
    if not root_deck:
        abort(404)
    return serve_react_spa("vocabulary_study.html")


@vocabulary_bp.route("/levels/new", methods=["POST"])
@vocabulary_bp.route("/topics/new", methods=["POST"])
@vocabulary_bp.route("/lessons/new", methods=["POST"])
@vocabulary_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@vocabulary_bp.route("/topics/<int:topic_id>/delete", methods=["POST"])
@vocabulary_bp.route("/topic/<int:topic_id>/open")
@vocabulary_bp.route("/topic/<int:topic_id>")
@vocabulary_bp.route("/study/topic/<int:topic_id>")
@vocabulary_bp.route("/study/lesson/<int:lesson_id>")
@vocabulary_bp.route("/lesson/<int:lesson_id>")
@vocabulary_bp.route("/lesson/<int:lesson_id>/download")
@vocabulary_bp.route("/column-widths", methods=["POST"])
@vocabulary_bp.route("/entry", methods=["POST"])
@vocabulary_bp.route("/entry/<int:legacy_entry_id>/field", methods=["POST"])
@vocabulary_bp.route("/entry/<int:legacy_entry_id>/fields", methods=["POST"])
@vocabulary_bp.route("/entries/bulk", methods=["POST"])
@vocabulary_bp.route("/import", methods=["GET", "POST"])
@login_required
def legacy_structure_removed(**_kwargs):
    return _legacy_structure_removed_response()
