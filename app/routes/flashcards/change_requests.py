"""Routes for deck change request workflow."""

from __future__ import annotations

from flask import jsonify, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from app.services import deck_change_request_service
from app.validators import (
    RequestValidationError,
    validate_change_request_conflict_resolution_request,
    validate_change_request_draft_request,
    validate_change_request_review_request,
)
from models import db

from . import (
    _api_error,
    _get_shared_deck_item_for_view,
    flashcards_bp,
)


def _change_request_response_payload(request_id: str) -> dict:
    request_obj = deck_change_request_service.get_request_detail_for_user(
        request_id=request_id,
        user_id=current_user.id,
    )
    return deck_change_request_service.serialize_request(
        request_obj,
        viewer_user_id=current_user.id,
    )


def _handle_change_request_error(exc: deck_change_request_service.ChangeRequestError):
    db.session.rollback()
    return _api_error(
        exc.error,
        exc.message,
        status=exc.status,
        field=exc.field,
    )


@flashcards_bp.route("/flashcards/shared-decks/<deck_item_id>/change-request")
@login_required
def shared_deck_change_request_page(deck_item_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if deck_item is None:
        return redirect(url_for("flashcards.shared_decks_page"))
    return render_template(
        "flashcards/shared_deck_change_request.html",
        deck_item_id=deck_item_id,
    )


@flashcards_bp.route("/flashcards/change-requests/incoming")
@login_required
def deck_change_request_inbox_page():
    return render_template(
        "flashcards/deck_change_request_inbox.html",
        deck_item_id=(request.args.get("deck_item_id") or "").strip(),
    )


@flashcards_bp.route("/flashcards/change-requests/<request_id>")
@login_required
def deck_change_request_detail_page(request_id: str):
    return render_template(
        "flashcards/deck_change_request_detail.html",
        request_id=request_id,
    )


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/change-requests/local-changes", methods=["GET"])
@login_required
def get_local_deck_change_preview(deck_item_id: str):
    try:
        install, _deck_item, _active_request = deck_change_request_service.get_request_for_update(
            user_id=current_user.id,
            deck_item_id=deck_item_id,
        )
        return jsonify(deck_change_request_service.preview_local_changes_for_install(install))
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/change-requests/active", methods=["GET"])
@login_required
def get_active_deck_change_request(deck_item_id: str):
    try:
        request_obj = deck_change_request_service.get_active_request_for_deck_item(
            user_id=current_user.id,
            deck_item_id=deck_item_id,
        )
        if request_obj is None:
            return jsonify({"request": None})
        return jsonify(
            {
                "request": deck_change_request_service.serialize_request(
                    request_obj,
                    viewer_user_id=current_user.id,
                )
            }
        )
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/change-requests/draft", methods=["POST"])
@login_required
def build_deck_change_request_draft(deck_item_id: str):
    try:
        draft_input = validate_change_request_draft_request(request.get_json(silent=True))
        request_obj = deck_change_request_service.build_or_refresh_draft_request(
            deck_item_id=deck_item_id,
            requester_user_id=current_user.id,
            title=draft_input.title,
            description=draft_input.description,
        )
        db.session.commit()
        return jsonify(
            deck_change_request_service.serialize_request(
                request_obj,
                viewer_user_id=current_user.id,
            )
        ), 201
    except RequestValidationError as exc:
        db.session.rollback()
        return _api_error(exc.code, str(exc), status=exc.status, field=exc.field)
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/change-requests/<request_id>/sync", methods=["POST"])
@login_required
def sync_deck_change_request(deck_item_id: str, request_id: str):
    try:
        request_obj = deck_change_request_service.get_request_detail_for_user(
            request_id=request_id,
            user_id=current_user.id,
        )
        if str(request_obj.deck_item_id or "") != str(deck_item_id):
            return _api_error("FIELD_NOT_FOUND", "Change request not found.", status=404)
        request_obj = deck_change_request_service.sync_request(
            request_obj,
            actor_user_id=current_user.id,
        )
        db.session.commit()
        return jsonify(
            deck_change_request_service.serialize_request(
                request_obj,
                viewer_user_id=current_user.id,
            )
        )
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route(
    "/api/shared/decks/<deck_item_id>/change-requests/<request_id>/conflicts/<conflict_id>/resolve",
    methods=["POST"],
)
@login_required
def resolve_deck_change_request_conflict(deck_item_id: str, request_id: str, conflict_id: str):
    try:
        resolution_input = validate_change_request_conflict_resolution_request(request.get_json(silent=True))
        request_obj = deck_change_request_service.get_request_detail_for_user(
            request_id=request_id,
            user_id=current_user.id,
        )
        if str(request_obj.deck_item_id or "") != str(deck_item_id):
            return _api_error("FIELD_NOT_FOUND", "Change request not found.", status=404)
        request_obj = deck_change_request_service.resolve_request_conflict(
            request_obj,
            conflict_id=conflict_id,
            actor_user_id=current_user.id,
            resolution_mode=resolution_input.resolution_mode,
            resolved_value=resolution_input.resolved_value,
        )
        db.session.commit()
        return jsonify(
            deck_change_request_service.serialize_request(
                request_obj,
                viewer_user_id=current_user.id,
            )
        )
    except RequestValidationError as exc:
        db.session.rollback()
        return _api_error(exc.code, str(exc), status=exc.status, field=exc.field)
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/change-requests/<request_id>/submit", methods=["POST"])
@login_required
def submit_deck_change_request(deck_item_id: str, request_id: str):
    try:
        request_obj = deck_change_request_service.get_request_detail_for_user(
            request_id=request_id,
            user_id=current_user.id,
        )
        if str(request_obj.deck_item_id or "") != str(deck_item_id):
            return _api_error("FIELD_NOT_FOUND", "Change request not found.", status=404)
        request_obj = deck_change_request_service.submit_request_for_review(
            request_obj,
            actor_user_id=current_user.id,
        )
        db.session.commit()
        return jsonify(
            deck_change_request_service.serialize_request(
                request_obj,
                viewer_user_id=current_user.id,
            )
        )
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/change-requests/incoming", methods=["GET"])
@login_required
def list_incoming_change_requests():
    try:
        deck_item_id = (request.args.get("deck_item_id") or "").strip() or None
        rows = deck_change_request_service.list_incoming_requests(
            owner_user_id=current_user.id,
            deck_item_id=deck_item_id,
        )
        return jsonify(
            {
                "items": [deck_change_request_service.serialize_request_summary(row) for row in rows]
            }
        )
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/change-requests/<request_id>", methods=["GET"])
@login_required
def get_change_request_detail(request_id: str):
    try:
        return jsonify(_change_request_response_payload(request_id))
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/change-requests/<request_id>/approve", methods=["POST"])
@login_required
def approve_change_request(request_id: str):
    try:
        review_input = validate_change_request_review_request(
            request.get_json(silent=True),
            require_reason=False,
        )
        request_obj = deck_change_request_service.get_request_detail_for_user(
            request_id=request_id,
            user_id=current_user.id,
        )
        request_obj = deck_change_request_service.approve_and_merge_request(
            request_obj,
            actor_user_id=current_user.id,
            review_comment=review_input.review_comment,
        )
        db.session.commit()
        return jsonify(
            deck_change_request_service.serialize_request(
                request_obj,
                viewer_user_id=current_user.id,
            )
        )
    except RequestValidationError as exc:
        db.session.rollback()
        return _api_error(exc.code, str(exc), status=exc.status, field=exc.field)
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)


@flashcards_bp.route("/api/change-requests/<request_id>/reject", methods=["POST"])
@login_required
def reject_change_request(request_id: str):
    try:
        review_input = validate_change_request_review_request(
            request.get_json(silent=True),
            require_reason=True,
        )
        request_obj = deck_change_request_service.get_request_detail_for_user(
            request_id=request_id,
            user_id=current_user.id,
        )
        request_obj = deck_change_request_service.reject_request(
            request_obj,
            actor_user_id=current_user.id,
            review_comment=review_input.review_comment,
        )
        db.session.commit()
        return jsonify(
            deck_change_request_service.serialize_request(
                request_obj,
                viewer_user_id=current_user.id,
            )
        )
    except RequestValidationError as exc:
        db.session.rollback()
        return _api_error(exc.code, str(exc), status=exc.status, field=exc.field)
    except deck_change_request_service.ChangeRequestError as exc:
        return _handle_change_request_error(exc)
