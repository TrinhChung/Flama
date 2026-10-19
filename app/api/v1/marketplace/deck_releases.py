"""Canonical REST resources for immutable shared-deck releases."""

from __future__ import annotations

from flask import Blueprint, jsonify, request
from flask_login import current_user, login_required
from sqlalchemy.exc import IntegrityError

from app.api.common.responses import error_response
from app.services import deck_auto_publish_service, deck_release_service
from app.services.deck_release_service import DeckReleaseError


marketplace_deck_releases_bp = Blueprint(
    "api_v1_marketplace_deck_releases",
    __name__,
)


def _handle_release_error(exc: DeckReleaseError):
    return error_response(
        exc.error,
        exc.message,
        status=exc.status,
        field=exc.field,
    )


def _read_diff_query() -> dict[str, object]:
    raw_type = (request.args.get("type") or "").strip()
    entity_kind = request.args.get("entity_kind") or request.args.get("entity_type")
    operation = request.args.get("operation")
    if raw_type in deck_release_service.VISIBLE_ENTITY_KINDS:
        entity_kind = raw_type
    elif raw_type:
        operation = raw_type
    return {
        "cursor": request.args.get("cursor"),
        "limit": request.args.get("limit"),
        "entity_kind": entity_kind,
        "operation": operation,
        "source_deck_id": request.args.get("deck_id"),
        "query_text": request.args.get("q"),
    }


@marketplace_deck_releases_bp.get(
    "/marketplace/decks/<deck_item_id>/releases"
)
@login_required
def list_deck_releases(deck_item_id: str):
    try:
        payload = deck_release_service.list_deck_releases(
            deck_item_id=deck_item_id,
            user_id=current_user.id,
            cursor=request.args.get("cursor"),
            limit=request.args.get("limit"),
        )
    except DeckReleaseError as exc:
        return _handle_release_error(exc)
    return jsonify(payload)


@marketplace_deck_releases_bp.get(
    "/marketplace/decks/<deck_item_id>/releases/preview"
)
@login_required
def preview_deck_release(deck_item_id: str):
    try:
        payload = deck_release_service.preview_release(
            deck_item_id=deck_item_id,
            user_id=current_user.id,
            **_read_diff_query(),
        )
    except DeckReleaseError as exc:
        return _handle_release_error(exc)
    return jsonify(payload)


@marketplace_deck_releases_bp.post(
    "/marketplace/decks/<deck_item_id>/releases"
)
@login_required
def publish_deck_release(deck_item_id: str):
    request_payload = request.get_json(silent=True)
    if not isinstance(request_payload, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    if "expected_current_release_id" not in request_payload:
        return error_response(
            "VALIDATION_ERROR",
            "expected_current_release_id is required (use null for the initial release).",
            status=400,
            field="expected_current_release_id",
        )

    try:
        result = deck_release_service.publish_release_and_commit(
            deck_item_id=deck_item_id,
            user_id=current_user.id,
            version_label=(
                request_payload.get("version_label")
                if "version_label" in request_payload
                else request_payload.get("version")
            ),
            changelog=request_payload.get("changelog"),
            expected_current_release_id=request_payload.get(
                "expected_current_release_id"
            ),
            expected_working_revision=request_payload.get(
                "expected_working_revision"
            ),
            idempotency_key=(
                request.headers.get("Idempotency-Key")
                or request_payload.get("idempotency_key")
            ),
        )
    except DeckReleaseError as exc:
        return _handle_release_error(exc)
    except IntegrityError:
        return error_response(
            "RELEASE_CONFLICT",
            "The release conflicted with another publish. Refresh and retry.",
            status=409,
        )

    return (
        jsonify(
            {
                "release": deck_release_service.serialize_release(result.release),
                "replayed": result.replayed,
            }
        ),
        200 if result.replayed else 201,
    )


@marketplace_deck_releases_bp.get(
    "/marketplace/decks/<deck_item_id>/releases/<release_id>"
)
@login_required
def get_deck_release(deck_item_id: str, release_id: str):
    try:
        payload = deck_release_service.get_deck_release_detail(
            deck_item_id=deck_item_id,
            release_id=release_id,
            user_id=current_user.id,
        )
    except DeckReleaseError as exc:
        return _handle_release_error(exc)
    return jsonify(payload)


@marketplace_deck_releases_bp.get(
    "/marketplace/decks/<deck_item_id>/releases/<release_id>/changes"
)
@login_required
def list_deck_release_changes(deck_item_id: str, release_id: str):
    try:
        payload = deck_release_service.list_deck_release_changes(
            deck_item_id=deck_item_id,
            release_id=release_id,
            user_id=current_user.id,
            **_read_diff_query(),
        )
    except DeckReleaseError as exc:
        return _handle_release_error(exc)
    return jsonify(payload)


@marketplace_deck_releases_bp.get(
    "/marketplace/decks/<deck_item_id>/auto-publish"
)
@login_required
def get_deck_auto_publish_status(deck_item_id: str):
    from app.services import deck_auto_publish_service

    try:
        payload = deck_auto_publish_service.get_auto_publish_status(
            deck_item_id=deck_item_id,
            user_id=current_user.id,
        )
    except DeckReleaseError as exc:
        return _handle_release_error(exc)
    return jsonify(payload)


@marketplace_deck_releases_bp.post(
    "/marketplace/decks/<deck_item_id>/auto-publish"
)
@login_required
def update_deck_auto_publish_setting(deck_item_id: str):
    from app.services import deck_auto_publish_service

    request_payload = request.get_json(silent=True)
    if not isinstance(request_payload, dict):
        return error_response(
            "VALIDATION_ERROR",
            "Payload must be a JSON object.",
            status=400,
        )
    if "auto_publish_enabled" not in request_payload:
        return error_response(
            "VALIDATION_ERROR",
            "auto_publish_enabled is required.",
            status=400,
            field="auto_publish_enabled",
        )

    try:
        payload = deck_auto_publish_service.update_auto_publish_setting_and_commit(
            deck_item_id=deck_item_id,
            user_id=current_user.id,
            auto_publish_enabled=bool(request_payload.get("auto_publish_enabled")),
        )
    except DeckReleaseError as exc:
        return _handle_release_error(exc)

    return jsonify(payload)

