"""Sub-module for flashcard routes."""

from __future__ import annotations

import logging
from datetime import datetime
from flask import jsonify, request, redirect, url_for, flash, render_template, send_file, current_app
from flask_login import current_user, login_required
from sqlalchemy.exc import OperationalError
from models import db
from models.flashcard import *
from models.deck import Deck
from models.card_progress import CardProgress
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

from app.repositories.study_repository import (
    card_state_from_progress as _card_state_from_progress,
    apply_card_state_to_progress as _apply_card_state_to_progress,
    is_progress_suspended as _is_progress_suspended,
    query_pending_learning_summary as _query_pending_learning_summary,
    query_next_due_card_id as _query_next_due_card_id,
    query_study_queue_counts as _query_study_queue_counts,
)

from app.routes.flashcards import (
    _api_error,
    _resolve_clone_scope_for_local_deck,
    _query_clone_scope_cards,
    _collect_deck_subtree_ids,
    _is_card_visible_in_clone_scope,
    _build_clone_schema_view,
    _apply_clone_note_field_overrides,
    _resolve_clone_scope_for_card,
    _touch_note_type_install_usage,
    _resolve_local_clone_deck_id_for_source_deck,
    _touch_deck_install_usage,
    _audit,
)
from app.validators import (
    RequestValidationError,
    validate_study_answer_request,
    validate_study_next_query,
)
from app.services.stats_overview import get_effective_timezone_name
from app.services.scheduler_config_service import resolve_deck_options
from app.presenters.vocabulary_presenter import note_field_values_as_strings



@flashcards_bp.route("/flashcards/study")
@login_required
def flashcard_study_page():
    decks = Deck.query.order_by(Deck.name.asc()).all()
    return render_template("flashcards/study.html", decks=decks)

@flashcards_bp.route("/api/study/next", methods=["GET"])
@login_required
def study_next():
    try:
        validated_query = validate_study_next_query(request.args)
    except RequestValidationError as exc:
        return _api_error(exc.code, str(exc), status=exc.status, field=exc.field)

    scope = validated_query.scope
    scope_id_raw = validated_query.scope_id_raw

    clone_scope: flashcards_share.CloneDeckScope | None = None
    query = None
    if scope == "deck":
        scope_id = int(validated_query.scope_id_int)
        clone_scope = _resolve_clone_scope_for_local_deck(
            user_id=current_user.id,
            local_deck_id=scope_id,
        )
        if clone_scope is not None:
            query = _query_clone_scope_cards(clone_scope)
        else:
            scope_deck_ids = _collect_deck_subtree_ids(scope_id)
            if not scope_deck_ids:
                return jsonify({"card_id": None, "message": "No cards found for selected scope."})
            query = Card.query.join(Note, Card.note_id == Note.id).filter(
                Note.user_id == current_user.id,
                Note.deck_id.in_(scope_deck_ids),
            )
    elif scope == "note_type":
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == current_user.id,
            Note.note_type_id == scope_id_raw,
        )

    if query is None:
        return jsonify({"card_id": None, "message": "No cards found for selected scope."})
    if not query.with_entities(Card.id).first():
        return jsonify({"card_id": None, "message": "No cards found for selected scope."})

    now = datetime.utcnow()
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    new_count, learn_count, due_count = _query_study_queue_counts(
        query,
        user_id=current_user.id,
        now=now,
        timezone_name=timezone_name,
    )
    selected_card_id = _query_next_due_card_id(
        query,
        user_id=current_user.id,
        now=now,
        timezone_name=timezone_name,
    )
    if not selected_card_id:
        pending_learning_count, next_due_at = _query_pending_learning_summary(
            query,
            user_id=current_user.id,
            now=now,
            timezone_name=timezone_name,
        )
        if pending_learning_count > 0:
            return jsonify(
                {
                    "card_id": None,
                    "message": "Learning is still in progress.",
                    "session_state": "waiting",
                    "new_count": new_count,
                    "learn_count": learn_count,
                    "due_count": due_count,
                    "next_due_at": (
                        f"{next_due_at.isoformat(timespec='seconds')}Z"
                        if next_due_at is not None
                        else None
                    ),
                }
            )
        return jsonify(
            {
                "card_id": None,
                "message": "No due cards.",
                "session_state": "complete",
                "new_count": new_count,
                "learn_count": learn_count,
                "due_count": due_count,
            }
        )

    selected_card = query.filter(Card.id == selected_card_id).first()
    if not selected_card:
        return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)
    if clone_scope is not None and not _is_card_visible_in_clone_scope(scope=clone_scope, card_obj=selected_card):
        return jsonify({"card_id": None, "message": "No due cards."})

    note = selected_card.note
    progress = CardProgress.query.filter_by(user_id=current_user.id, card_id=selected_card.id).first()
    deck_options = resolve_deck_options(
        user_id=current_user.id,
        deck_id=getattr(note, "deck_id", None),
    )
    card_state = _card_state_from_progress(
        progress,
        now,
        timezone_name=timezone_name,
        user_id=current_user.id,
        options=deck_options,
    )
    interval_preview = computeAnswerPreview(
        card_state,
        deck_options,
        now,
        timezone_name=timezone_name,
    )
    template = selected_card.template
    render_field_defs = note.note_type.field_defs
    render_field_values = note.field_values or {}
    if clone_scope is not None:
        source_note_type_id = (clone_scope.install.source_note_type_id or note.note_type_id or "").strip()
        if source_note_type_id:
            schema_view = _build_clone_schema_view(
                install=clone_scope.install,
                source_note_type_id=source_note_type_id,
            )
            if schema_view.field_defs:
                render_field_defs = schema_view.field_defs
            render_field_values = _apply_clone_note_field_overrides(
                install=clone_scope.install,
                source_note=note,
                schema_view=schema_view,
            )
    try:
        rendered = render_template_pair(
            template=template,
            field_defs=render_field_defs,
            field_values=render_field_values,
            media_assets=note.media_assets,
            allow_inline_script=True,
            defer_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc))

    return jsonify(
        {
            "card_id": selected_card.id,
            "note_id": note.id,
            "template_id": template.id,
            "rendered_front_html": rendered["front_html"],
            "rendered_back_html": rendered["back_html"],
            "intervals_preview": interval_preview,
            "new_count": new_count,
            "learn_count": learn_count,
            "due_count": due_count,
            "can_edit_card": bool(note and note.user_id == current_user.id),
            "save_card_url": (
                url_for("flashcards.study_edit_card", card_id=selected_card.id)
                if note and note.user_id == current_user.id
                else None
            ),
            "load_note_url": (
                url_for("flashcards.get_note", note_id=note.id)
                if note and note.user_id == current_user.id
                else None
            ),
            "field_values": note_field_values_as_strings(note),
            "field_defs": [
                {
                    "name": field_def.name,
                    "field_type": field_def.field_type,
                    "required": bool(field_def.required),
                    "position": int(field_def.position or 0),
                }
                for field_def in sorted(note.note_type.field_defs, key=lambda item: item.position)
            ] if note and note.note_type else [],
        }
    )

@flashcards_bp.route("/api/study/<card_id>/answer", methods=["POST"])
@login_required
def study_answer(card_id: str):
    payload = request.get_json(silent=True) or {}
    try:
        validated_answer = validate_study_answer_request(payload)
    except RequestValidationError as exc:
        return _api_error(exc.code, str(exc), status=exc.status, field=exc.field)

    rating = validated_answer.rating
    scope = validated_answer.scope
    requested_scope_id = validated_answer.requested_scope_id
    service_payload = dict(payload)
    service_payload["timezone"] = validated_answer.timezone
    service_payload["duration_ms"] = validated_answer.duration_ms

    card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id).first()
    if not card:
        return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)
    clone_scope: flashcards_share.CloneDeckScope | None = None
    if card.note.user_id != current_user.id:
        clone_scope = _resolve_clone_scope_for_card(user_id=current_user.id, card_obj=card)
        if clone_scope is None:
            return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)
        if not _is_card_visible_in_clone_scope(scope=clone_scope, card_obj=card):
            return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)

    progress = CardProgress.query.filter_by(user_id=current_user.id, card_id=card.id).first()
    deck_options = resolve_deck_options(
        user_id=current_user.id,
        deck_id=getattr(card.note, "deck_id", None),
    )
    if progress is None:
        progress = CardProgress(
            user_id=current_user.id,
            card_id=card.id,
            queue="new",
            step_index=0,
            due_at=None,
            due_day=None,
            interval_days=0,
            ease_factor=deck_options.startingEase,
            reps=0,
            lapses=0,
        )
        db.session.add(progress)
        db.session.flush()
    elif _is_progress_suspended(progress):
        return _api_error("CARD_SUSPENDED", "Card is suspended.", status=409)

    # Capture for optimistic locking (detect concurrent reviews)
    expected_last_reviewed_at = progress.last_reviewed_at

    now = datetime.utcnow()
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    current_state = _card_state_from_progress(
        progress,
        now,
        timezone_name=timezone_name,
        user_id=current_user.id,
        options=deck_options,
    )
    answer_preview = computeAnswerPreview(
        current_state,
        deck_options,
        now,
        timezone_name=timezone_name,
    )
    review_mode = normalize_review_mode(current_state.type)
    updated_state = applyAnswer(  # type: ignore[arg-type]
        current_state,
        deck_options,
        now,
        rating,
        timezone_name=timezone_name,
    )
    from app.services.study_service import apply_study_answer_and_commit, ConcurrentReviewError

    try:
        local_deck_id_for_usage = apply_study_answer_and_commit(
            user=current_user,
            card=card,
            progress=progress,
            expected_last_reviewed_at=expected_last_reviewed_at,
            current_state=current_state,
            updated_state=updated_state,
            now=now,
            rating=rating,
            review_mode=review_mode,
            payload=service_payload,
            clone_scope=clone_scope,
            requested_scope_id=requested_scope_id,
            timezone_name=timezone_name,
            deck_options=deck_options,
        )
    except ConcurrentReviewError as exc:
        return _api_error("CONCURRENT_REVIEW", str(exc), status=409)

    next_scope_id = requested_scope_id if requested_scope_id is not None else local_deck_id_for_usage
    next_card_url = url_for("flashcards.study_next", scope="deck", scope_id=next_scope_id) if next_scope_id else None

    next_url = None
    if scope == "deck":
        if requested_scope_id is not None:
            next_url = url_for("vocabulary.study_deck", deck_id=requested_scope_id)
    return jsonify(
        {
            "success": True,
            "next_url": next_url,
            "next_card_url": next_card_url,
            "intervals_preview": answer_preview,
            "applied_interval": answer_preview.get(rating),
        }
    )


@flashcards_bp.route("/api/study/cards/<card_id>/edit", methods=["PATCH"])
@login_required
def study_edit_card(card_id: str):
    payload = request.get_json(silent=True) or {}
    from app.services.study_card_editor_service import StudyCardEditError, update_study_card_note

    try:
        result = update_study_card_note(
            user_id=current_user.id,
            card_id=card_id,
            payload=payload,
        )
    except StudyCardEditError as exc:
        return _api_error(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(result)
