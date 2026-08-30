"""Vocabulary management routes."""

from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List

UTC = timezone.utc

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    send_file,
    request,
    url_for,
)
from flask_login import current_user, login_required
from app.spa import serve_react_spa
from sqlalchemy.exc import SQLAlchemyError

from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.deck_tree_query import collect_subtree_ids as _collect_deck_subtree_ids
from app.repositories.study_repository import (
    apply_card_state_to_progress as _apply_card_state_to_progress,
    card_state_from_progress as _card_state_from_progress,
    load_card_progress_map as _load_card_progress_map_for_user,
    select_next_due_card_from_loaded as _select_next_due_card_from_loaded,
    summarize_pending_learning_from_loaded as _summarize_pending_learning_from_loaded,
)
from app.utils.deck_move_token import parse_deck_move_token
from app.utils.permissions import is_admin_user
from app.utils.redirects import resolve_safe_next_url
from app.services import deck_management_service, flashcards_share_service
from app.services.study_action_runtime import compute_review_previews
from app.services.scheduler_config_service import resolve_deck_options
from app.services.flashcard_renderer import TemplateCompileError, render_template_pair
from app.services.stats_overview import get_effective_timezone_name
from models import db
from models.flashcard import Card, Note
from models.deck import Deck
from models.card_progress import CardProgress

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
        "vocabulary.create_deck",
        "vocabulary.browse_api_decks_tree",
        "vocabulary.browse_api_cards",
        "vocabulary.browse_api_card_detail",
        "vocabulary.browse_api_card_update",
        "vocabulary.browse_api_card_delete",
        "vocabulary.browse_api_decks",
        "vocabulary.browse_api_notes",
        "vocabulary.browse_api_update_note",
        "vocabulary.browse_api_voicevox_preview",
        "vocabulary.browse_api_voicevox_precheck",
        "vocabulary.browse_api_voicevox_generate",
        "vocabulary.delete_deck",
        "vocabulary.reset_deck",
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




def _resolve_next_url(default_endpoint: str = "main.dashboard") -> str:
    """Return a safe in-app redirect target from `next` form value."""
    return resolve_safe_next_url(
        request.form.get("next"),
        default_endpoint=default_endpoint,
    )




@vocabulary_bp.route("/")
@login_required
def index():
    """Legacy hierarchy index removed; redirect to browse."""
    return redirect(url_for("vocabulary.browse"))


@vocabulary_bp.route("/browse")
@login_required
def browse():
    """Anki-like browser interface."""
    from app.spa import serve_react_spa
    return serve_react_spa()



























@vocabulary_bp.route("/api/browse/decks/tree", methods=["GET"])
@login_required
def browse_api_decks_tree():
    """Returns deck tree with aggregate card counts."""
    from app.services import browse_card_service

    return jsonify(
        browse_card_service.build_browse_deck_tree(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            timezone_name=get_effective_timezone_name(
                getattr(current_user, "timezone", "UTC")
            ),
        )
    )


@vocabulary_bp.route("/api/browse/decks", methods=["GET"])
@login_required
def browse_api_decks():
    """Backward-compatible flat deck list endpoint."""
    from app.services import browse_card_service

    return jsonify(
        browse_card_service.build_browse_decks(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            timezone_name=get_effective_timezone_name(
                getattr(current_user, "timezone", "UTC")
            ),
        )
    )


@vocabulary_bp.route("/api/browse/cards", methods=["GET"])
@login_required
def browse_api_cards():
    """List cards for Browse modal with deck/filter/sort/paging."""
    from app.services import browse_card_service

    try:
        payload = browse_card_service.list_browse_cards(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            timezone_name=get_effective_timezone_name(
                getattr(current_user, "timezone", "UTC")
            ),
            query_args=request.args,
        )
    except browse_card_service.BrowseApiError as exc:
        error_payload = {"error": str(exc)}
        if exc.field is not None:
            error_payload["field"] = exc.field
        if exc.code is not None:
            error_payload["code"] = exc.code
        return jsonify(error_payload), exc.status
    return jsonify(payload)
@vocabulary_bp.route("/api/browse/cards/<card_id>", methods=["GET"])
@login_required
def browse_api_card_detail(card_id: str):
    """Get full card detail for right editor panel."""
    from app.services import browse_card_service

    try:
        payload = browse_card_service.get_browse_card_detail(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            timezone_name=get_effective_timezone_name(
                getattr(current_user, "timezone", "UTC")
            ),
            card_id=card_id,
        )
    except browse_card_service.BrowseApiError as exc:
        return jsonify({"error": str(exc)}), exc.status
    return jsonify(payload)

@vocabulary_bp.route("/api/browse/cards/<card_id>", methods=["PATCH"])
@login_required
def browse_api_card_update(card_id: str):
    """Update card note fields/deck/tags from Browse editor."""
    from app.services import browse_card_service

    admin_mode = is_admin_user(current_user)
    payload = request.get_json(silent=True) or {}
    try:
        result = browse_card_service.update_browse_card(
            user_id=current_user.id,
            admin_mode=admin_mode,
            timezone_name=get_effective_timezone_name(getattr(current_user, "timezone", "UTC")),
            card_id=card_id,
            payload=payload,
        )
    except browse_card_service.BrowseCardUpdateError as exc:
        response = {"error": str(exc)}
        if exc.include_details:
            response["field"] = exc.field
            response["code"] = exc.code
        return jsonify(response), exc.status
    return jsonify(result)

@vocabulary_bp.route("/api/browse/voicevox/preview", methods=["POST"])
@login_required
def browse_api_voicevox_preview():
    from app.services import browse_voicevox_service

    body = request.get_json(silent=True) or {}
    try:
        result = browse_voicevox_service.preview_voicevox(
            user_id=current_user.id,
            payload=body,
        )
    except browse_voicevox_service.BrowseVoiceVoxError as exc:
        error_payload = {"error": str(exc)}
        if exc.code is not None:
            error_payload["code"] = exc.code
        return jsonify(error_payload), exc.status
    response = send_file(
        io.BytesIO(result.content),
        mimetype=result.mime_type,
        as_attachment=False,
        download_name=f"voicevox-preview.{result.extension}",
        max_age=0,
    )
    if result.warnings:
        response.headers["X-VoiceVox-Warnings"] = " | ".join(result.warnings)[:500]
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response
@vocabulary_bp.route("/api/browse/voicevox/precheck", methods=["POST"])
@login_required
def browse_api_voicevox_precheck():
    from app.services import browse_voicevox_service

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Payload phải là JSON object."}), 400
    try:
        payload = browse_voicevox_service.precheck_voicevox(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=body,
        )
    except browse_voicevox_service.BrowseVoiceVoxError as exc:
        error_payload = {"error": str(exc)}
        if exc.code is not None:
            error_payload["code"] = exc.code
        return jsonify(error_payload), exc.status
    return jsonify(payload)
@vocabulary_bp.route("/api/browse/voicevox/generate", methods=["POST"])
@login_required
def browse_api_voicevox_generate():
    from app.services import browse_voicevox_service

    body = request.get_json(silent=True) or {}
    try:
        payload = browse_voicevox_service.generate_voicevox(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=body,
            upload_root=Path(
                current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]
            ),
        )
    except browse_voicevox_service.BrowseVoiceVoxError as exc:
        error_payload = {"error": str(exc)}
        if exc.code is not None:
            error_payload["code"] = exc.code
        return jsonify(error_payload), exc.status
    return jsonify(payload)
@vocabulary_bp.route("/api/browse/cards/<card_id>", methods=["DELETE"])
@login_required
def browse_api_card_delete(card_id: str):
    """Delete one card (and delete its note if last card)."""
    from app.services import browse_card_service

    try:
        payload = browse_card_service.delete_browse_card(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            card_id=card_id,
        )
    except browse_card_service.BrowseApiError as exc:
        return jsonify({"error": str(exc)}), exc.status
    return jsonify(payload)

@vocabulary_bp.route("/api/browse/notes", methods=["GET"])
@login_required
def browse_api_notes():
    """Backward-compatible endpoint for legacy browse page."""
    from app.services import browse_card_service

    result = browse_api_cards()
    if isinstance(result, tuple):
        return result
    payload = result.get_json(silent=True) or {}
    return jsonify(browse_card_service.build_legacy_notes_payload(payload))

@vocabulary_bp.route("/api/browse/notes/<note_id>", methods=["PATCH"])
@login_required
def browse_api_update_note(note_id: str):
    """Backward-compatible note update endpoint."""
    from app.services import browse_card_service

    try:
        payload = browse_card_service.update_legacy_browse_note(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            note_id=note_id,
            payload=request.get_json(silent=True) or {},
        )
    except browse_card_service.BrowseApiError as exc:
        error_payload = {"error": str(exc)}
        if exc.field is not None:
            error_payload["field"] = exc.field
        if exc.code is not None:
            error_payload["code"] = exc.code
        return jsonify(error_payload), exc.status
    return jsonify(payload)

@vocabulary_bp.route("/levels/new", methods=["POST"])
@login_required
def create_level():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/decks/create", methods=["POST"])
@login_required
def create_deck():
    """Create deck(s) from path, auto-creating missing parents."""
    parent_id_raw = (request.form.get("parent_id") or "").strip()
    deck_path_raw = (request.form.get("deck_path") or "").strip()
    deck_name = (request.form.get("name") or "").strip() or "New Deck"
    next_url = _resolve_next_url()
    admin_mode = is_admin_user(current_user)
    parent_resolution = vocabulary_ctrl.resolve_create_deck_parent(
        parent_id_raw=parent_id_raw,
        user_id=current_user.id,
        admin_mode=admin_mode,
    )
    if parent_resolution.error:
        flash(parent_resolution.error, "danger")
        return redirect(next_url)

    path_tokens = vocabulary_ctrl.parse_create_deck_tokens(
        deck_path_raw=deck_path_raw,
        fallback_name=deck_name,
    )
    path_tokens = vocabulary_ctrl.normalize_create_deck_tokens_for_parent(
        path_tokens=path_tokens,
        parent_path_tokens=vocabulary_ctrl.deck_name_path_tokens(parent_resolution.parent_deck),
        fallback_name=deck_name,
    )

    try:
        upsert_result = vocabulary_ctrl.upsert_deck_path(
            parent_id=parent_resolution.parent_id,
            path_tokens=path_tokens,
            owner_user_id=getattr(current_user, "id", None),
            admin_mode=admin_mode,
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not create deck. Please try again.", "danger")
        return redirect(next_url)

    if upsert_result.created_count == 0 and upsert_result.final_deck:
        flash(f"Deck already exists: {'::'.join(upsert_result.path_tokens)}", "info")
    elif upsert_result.created_count == 1 and upsert_result.final_deck:
        flash(f"Created deck: {upsert_result.final_deck.name}", "success")
    else:
        flash(f"Created {upsert_result.created_count} decks: {'::'.join(upsert_result.created_names)}", "success")
    return redirect(next_url)


@vocabulary_bp.route("/decks/<int:deck_id>/rename", methods=["POST"])
@login_required
def rename_deck(deck_id: int):
    """Rename an existing deck."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
        
    deck = Deck.query.get_or_404(deck_id)
    new_name = (request.form.get("name") or "").strip()
    next_url = _resolve_next_url()

    if not new_name:
        flash("Deck name cannot be empty.", "warning")
        return redirect(next_url)
    if new_name == deck.name:
        flash("Deck name is unchanged.", "info")
        return redirect(next_url)
    if vocabulary_ctrl.deck_name_exists_under_parent(parent_id=deck.parent_id, name=new_name, exclude_deck_id=deck.id):
        flash(f"Deck '{new_name}' already exists at this level.", "danger")
        return redirect(next_url)

    deck.name = new_name
    try:
        db.session.commit()
        flash(f"Deck renamed to: {new_name}", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Failed to rename deck. Please try again.", "danger")
    return redirect(next_url)


@vocabulary_bp.route("/decks/move", methods=["POST"])
@vocabulary_bp.route("/decks/<int:deck_id>/move", methods=["POST"])
@login_required
def move_deck(deck_id: int | None = None):
    """Move a deck to a new parent deck."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    
    next_url = _resolve_next_url()
    if deck_id is None:
        deck_token = (request.form.get("deck_token") or "").strip()
        deck_id = parse_deck_move_token(deck_token, user_id=current_user.id)
        if deck_id is None:
            flash("Move token is invalid or expired. Please reopen Deck Settings.", "danger")
            return redirect(next_url)

    deck = Deck.query.get_or_404(deck_id)
    parent_token_raw = (request.form.get("parent_token") or "").strip()
    parent_id_raw = (request.form.get("parent_id") or "").strip()

    new_parent_id = None
    new_parent = None
    if parent_token_raw:
        parsed_parent_id = parse_deck_move_token(parent_token_raw, user_id=current_user.id)
        if parsed_parent_id is None:
            flash("Parent move token is invalid or expired.", "danger")
            return redirect(next_url)
        new_parent_id = parsed_parent_id
    elif parent_id_raw:
        try:
            new_parent_id = int(parent_id_raw)
        except ValueError:
            flash("Invalid parent deck.", "danger")
            return redirect(next_url)

    if new_parent_id is not None:
        new_parent = Deck.query.get(new_parent_id)
        if not new_parent:
            flash("Parent deck not found.", "danger")
            return redirect(next_url)

        # Prevent moving into itself or its own descendants
        curr = new_parent
        while curr:
            if curr.id == deck.id:
                flash("Cannot move a deck into itself or its descendants.", "danger")
                return redirect(next_url)
            curr = curr.parent

    if deck.parent_id == new_parent_id:
        flash("Deck is already in the selected location.", "info")
        return redirect(next_url)
    if vocabulary_ctrl.deck_name_exists_under_parent(parent_id=new_parent_id, name=deck.name, exclude_deck_id=deck.id):
        parent_label = new_parent.name if new_parent else "Root"
        flash(f"Parent '{parent_label}' already has a deck named '{deck.name}'.", "danger")
        return redirect(next_url)

    guard_error = flashcards_share_service.validate_deck_subtree_move_to_parent(
        deck_id=deck.id,
        new_parent_id=new_parent_id,
        user_id=deck.owner_user_id,
    )
    if guard_error:
        flash(guard_error, "danger")
        return redirect(next_url)

    deck.parent_id = new_parent_id
    deck.position = vocabulary_ctrl.next_deck_position(new_parent_id)
    try:
        db.session.commit()
        flash(f"Deck '{deck.name}' moved successfully.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Failed to move deck. Please try again.", "danger")
    
    return redirect(next_url)


def _can_current_user_delete_cloned_deck(deck_obj: Deck) -> bool:
    return vocabulary_ctrl.can_user_delete_cloned_deck(
        deck_obj=deck_obj,
        user_id=current_user.id,
    )


@vocabulary_bp.route("/decks/<int:deck_id>/delete", methods=["POST"])
@login_required
def delete_deck(deck_id: int):
    """Delete a local deck or archive a shared source deck."""
    deck = Deck.query.get_or_404(deck_id)
    if (
        not is_admin_user(current_user)
        and deck.owner_user_id != current_user.id
        and not _can_current_user_delete_cloned_deck(deck)
    ):
        flash("You do not have permission to delete this deck.", "danger")
        return redirect(url_for("main.dashboard"))

    deck_name = deck.name
    next_url = _resolve_next_url()
    deletion_mode = deck_management_service.delete_deck_subtree(
        deck_obj=deck,
        user_id=current_user.id,
        is_admin=is_admin_user(current_user),
    )
    if deletion_mode == "archived":
        flash(
            f"Archived deck '{deck_name}'. Existing installs keep their cards and progress.",
            "success",
        )
    else:
        flash(f"Deleted deck '{deck_name}' and all its contents.", "success")
    return redirect(next_url)


@vocabulary_bp.route("/decks/<int:deck_id>/reset", methods=["POST"])
@login_required
def reset_deck(deck_id: int):
    """Reset current-user progress for cards within a deck subtree."""
    deck = Deck.query.get_or_404(deck_id)
    if (
        not is_admin_user(current_user)
        and deck.owner_user_id != current_user.id
        and not _can_current_user_delete_cloned_deck(deck)
    ):
        return redirect(url_for("main.dashboard"))

    next_url = _resolve_next_url()
    deleted_count = deck_management_service.reset_deck_progress(
        deck_obj=deck,
        user_id=current_user.id,
    )
    if deleted_count:
        flash(f"Reset progress for {deleted_count} cards in '{deck.name}' (your account).", "success")
    else:
        flash(f"No cards to reset in '{deck.name}'.", "info")

    return redirect(next_url)


@vocabulary_bp.route("/topics/new", methods=["POST"])
@login_required
def create_topic():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lessons/new", methods=["POST"])
@login_required
def create_lesson():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required
def delete_lesson(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete_topic(topic_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/topic/<int:topic_id>/open")
@login_required
def open_topic(topic_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/topic/<int:topic_id>")
@login_required
def topic(topic_id: int):
    return _legacy_structure_removed_response()


def _select_next_note_card(
    cards: List[Card],
    progress_map: Dict[str, CardProgress],
    now: datetime,
    *,
    timezone_name: str,
):
    return _select_next_due_card_from_loaded(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
        user_id=current_user.id,
    )


def _build_note_study_card_payload(card_obj: Card | None) -> SimpleNamespace | None:
    return vocabulary_ctrl.build_note_study_card_payload(card_obj)


def _render_note_study_flashcard(card_obj: Card | None) -> dict:
    return vocabulary_ctrl.render_note_study_flashcard(card_obj)


def _query_study_cards_for_deck_ids(deck_ids: list[int]) -> list[Card]:
    return vocabulary_ctrl.query_study_cards_for_deck_ids(
        user_id=current_user.id,
        deck_ids=deck_ids,
    )


def _load_card_progress_map(card_ids: list[str]) -> dict[str, CardProgress]:
    return _load_card_progress_map_for_user(user_id=current_user.id, card_ids=card_ids)


def _count_due_note_cards(
    cards: list[Card],
    progress_map: dict[str, CardProgress],
    *,
    now: datetime,
    timezone_name: str,
) -> tuple[int, int, int]:
    return vocabulary_ctrl.count_due_note_cards(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
    )


def _summarize_pending_learning_cards(
    cards: list[Card],
    progress_map: dict[str, CardProgress],
    *,
    now: datetime,
    timezone_name: str,
) -> tuple[int, datetime | None]:
    return _summarize_pending_learning_from_loaded(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
        user_id=current_user.id,
    )


@vocabulary_bp.route("/study/topic/<int:topic_id>")
@login_required
def study_topic(topic_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/study/deck/<int:deck_id>")
@login_required
def study_deck(deck_id: int):
    """Study cards across a deck subtree using Note/Card as the source of truth."""
    root_deck = Deck.query.get(deck_id)
    if not root_deck:
        abort(404)
    subtree_ids = _collect_deck_subtree_ids(root_deck.id)

    cards = _query_study_cards_for_deck_ids(subtree_ids)
    now = _utcnow()
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    card_ids = [card_obj.id for card_obj in cards]
    progress_map = _load_card_progress_map(card_ids)

    selected_card = _select_next_note_card(
        cards,
        progress_map,
        now,
        timezone_name=timezone_name,
    )
    due_new, due_learn, due_review = _count_due_note_cards(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
    )
    pending_learning_count, next_learning_due_at = _summarize_pending_learning_cards(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
    )

    next_intervals_preview = None
    if selected_card:
        deck_options = resolve_deck_options(
            user_id=current_user.id,
            deck_id=getattr(selected_card.note, "deck_id", None),
        )
        card_state = _card_state_from_progress(
            progress_map.get(selected_card.id),
            now,
            timezone_name=timezone_name,
            user_id=current_user.id,
            options=deck_options,
        )
        next_intervals_preview = compute_review_previews(
            state=card_state,
            options=deck_options,
            now=now,
            timezone_name=timezone_name,
        )

    rendered_data = _render_note_study_flashcard(selected_card)
    card_payload = _build_note_study_card_payload(selected_card)
    from app.services import flashcards_share as share_ctrl

    can_edit_current_card = bool(
        selected_card
        and selected_card.note
        and selected_card.note.user_id == current_user.id
    )

    clone_scope = share_ctrl.resolve_clone_scope_for_local_deck(
        user_id=current_user.id,
        local_deck_id=root_deck.id,
    )
    if (
        clone_scope is not None
        and selected_card is not None
        and share_ctrl.is_card_visible_in_clone_scope(scope=clone_scope, card_obj=selected_card)
    ):
        source_note_type_id = (clone_scope.install.source_note_type_id or selected_card.note.note_type_id or "").strip()
        if source_note_type_id:
            schema_view = share_ctrl.build_clone_schema_view(
                install=clone_scope.install,
                source_note_type_id=source_note_type_id,
            )
            overlay_field_defs = schema_view.field_defs or selected_card.note.note_type.field_defs
            overlay_field_values = share_ctrl.apply_clone_note_field_overrides(
                install=clone_scope.install,
                source_note=selected_card.note,
                schema_view=schema_view,
            )
            try:
                rendered = render_template_pair(
                    template=selected_card.template,
                    field_defs=overlay_field_defs,
                    field_values=overlay_field_values,
                    media_assets=selected_card.note.media_assets,
                )
                rendered_data = {
                    "front": rendered.get("front_html", ""),
                    "back": rendered.get("back_html", ""),
                    "front_payload": rendered.get("front_renderer_payload"),
                    "back_payload": rendered.get("back_renderer_payload"),
                }
                if card_payload is not None:
                    card_payload.field_values = {
                        str(key): "" if value is None else str(value)
                        for key, value in overlay_field_values.items()
                    }
                    card_payload.field_defs = [
                        {
                            "name": field_def.name,
                            "field_type": field_def.field_type,
                            "required": bool(field_def.required),
                            "position": int(field_def.position or 0),
                        }
                        for field_def in overlay_field_defs
                    ]
            except TemplateCompileError:
                pass

    user_decks = Deck.query.filter(Deck.deleted_at.is_(None)).order_by(Deck.name.asc()).all()
    user_decks_payload = [{"id": d.id, "name": d.name} for d in user_decks]
    return serve_react_spa(
        "vocabulary_study.html",
        selected_deck=root_deck,
        user_decks=user_decks,
        user_decks_payload=user_decks_payload,
        card=card_payload,
        rendered_front=rendered_data.get("front"),
        rendered_back=rendered_data.get("back"),
        rendered_front_payload=rendered_data.get("front_payload"),
        rendered_back_payload=rendered_data.get("back_payload"),
        due_new=due_new,
        due_learn=due_learn,
        due_review=due_review,
        due_total=due_new + due_learn + due_review,
        is_waiting_session=bool(pending_learning_count and next_learning_due_at is not None),
        next_learning_due_at_iso=(
            f"{next_learning_due_at.isoformat(timespec='seconds')}Z"
            if next_learning_due_at is not None
            else None
        ),
        study_scope="deck",
        study_scope_id=root_deck.id,
        next_study_url=url_for("vocabulary.study_deck", deck_id=root_deck.id),
        next_intervals_preview=next_intervals_preview,
        answer_url=(url_for("flashcards.study_answer", card_id=selected_card.id) if selected_card else None),
        can_edit_current_card=can_edit_current_card,
        edit_card_api_url=(
            url_for("flashcards.study_edit_card", card_id=selected_card.id)
            if can_edit_current_card and selected_card
            else None
        ),
    )


@vocabulary_bp.route("/study/lesson/<int:lesson_id>")
@login_required
def study_lesson(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lesson/<int:lesson_id>")
@login_required
def lesson(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lesson/<int:lesson_id>/download")
@login_required
def download_lesson_csv(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/column-widths", methods=["POST"])
@login_required
def save_column_width():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entry", methods=["POST"])
@login_required
def create_entry():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entry/<int:legacy_entry_id>/field", methods=["POST"])
@login_required
def update_entry_field(legacy_entry_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entry/<int:legacy_entry_id>/fields", methods=["POST"])
@login_required
def update_entry_fields(legacy_entry_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entries/bulk", methods=["POST"])
@login_required
def bulk_update_entries():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    return _legacy_structure_removed_response()
