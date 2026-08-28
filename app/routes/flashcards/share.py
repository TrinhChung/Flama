"""Sub-module for flashcard routes."""

from __future__ import annotations

from datetime import datetime, timezone

UTC = timezone.utc
from flask import jsonify, request, url_for
from flask_login import current_user, login_required
from app.spa import serve_react_spa
from models import db
from models.flashcard import *
from app.services import flashcards_share
from app.services import marketplace_hub_service
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

# Backward-compatible alias used by tests and legacy patch targets.
share_ctrl = flashcards_share

MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER = 2


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _count_user_market_review_submissions(
    *,
    user_id: int,
    action: str,
    payload_item_key: str,
    payload_item_value: str,
) -> int:
    rows = AuditLog.query.filter_by(user_id=user_id, action=action).all()
    total = 0
    expected = str(payload_item_value or "").strip()
    for row in rows:
        payload = row.payload if isinstance(row.payload, dict) else {}
        if str(payload.get(payload_item_key) or "").strip() == expected:
            total += 1
    return total


def _marketplace_payment_redirect_url(endpoint: str, **values: object) -> str:
    return url_for(endpoint, _external=True, **values)


@flashcards_bp.route("/flashcards/shared-note-types")
@login_required
def shared_note_types_page():
    return serve_react_spa()

@flashcards_bp.route("/flashcards/shared-note-types/<note_type_id>")
@login_required
def shared_note_type_detail_page(note_type_id: str):
    return serve_react_spa()

@flashcards_bp.route("/flashcards/shared-decks")
@login_required
def shared_decks_page():
    return serve_react_spa()

@flashcards_bp.route("/flashcards/installed-decks")
@login_required
def installed_decks_page():
    workspace = marketplace_hub_service.build_installed_deck_workspace(user_id=current_user.id)
    return serve_react_spa(
        "flashcards/installed_decks.html",
        installed_workspace=workspace,
    )

@flashcards_bp.route("/flashcards/shared-decks/<deck_item_id>")
@login_required
def shared_deck_detail_page(deck_item_id: str):
    return serve_react_spa()


@flashcards_bp.route("/api/shared/note-types/hub", methods=["GET"])
@login_required
def shared_note_types_hub():
    from app.services import marketplace_note_type_service
    payload = marketplace_note_type_service.get_note_types_hub(
        user_id=current_user.id,
        args=request.args,
        compact=request.args.get("compact") == "1",
    )
    return jsonify(payload)


@flashcards_bp.route("/api/shared/decks/hub", methods=["GET"])
@login_required
def shared_decks_hub():
    filters = marketplace_hub_service.parse_marketplace_filters(request.args)
    payload = marketplace_hub_service.build_deck_marketplace_hub(
        user_id=current_user.id,
        filters=filters,
    )
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/save", methods=["POST", "DELETE"])
@login_required
def save_shared_note_type(note_type_id: str):
    from app.services import marketplace_note_type_service
    try:
        payload = marketplace_note_type_service.save_shared_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
            is_save=(request.method == "POST"),
        )
    except marketplace_note_type_service.MarketplaceNoteTypeError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(payload)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/save", methods=["POST", "DELETE"])
@login_required
def save_shared_deck_item(deck_item_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)
    if deck_item.owner_user_id == current_user.id:
        return _api_error("VALIDATION_ERROR", "Owner cannot save own deck item.", status=409)
    if request.method == "POST":
        marketplace_hub_service.save_item_for_user(
            user_id=current_user.id,
            product_type="deck_marketplace_item",
            product_ref_id=deck_item.id,
        )
        db.session.commit()
        return jsonify({"saved": True, "deck_item_id": deck_item.id})
    marketplace_hub_service.remove_saved_item_for_user(
        user_id=current_user.id,
        product_type="deck_marketplace_item",
        product_ref_id=deck_item.id,
    )
    db.session.commit()
    return jsonify({"saved": False, "deck_item_id": deck_item.id})

@flashcards_bp.route("/api/note-types", methods=["POST"])
@login_required
def create_note_type():
    from app.services import flashcard_content_service

    try:
        payload = flashcard_content_service.create_note_type(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload), 201

@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["POST"])
@login_required
def create_template(note_type_id: str):
    from app.services import flashcard_content_service

    try:
        payload = flashcard_content_service.create_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload), 201

@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["PATCH"])
@login_required
def patch_template(note_type_id: str, template_id: str):
    from app.services import flashcard_content_service

    try:
        payload = flashcard_content_service.update_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload)

@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/reset", methods=["POST"])
@login_required
def reset_template(note_type_id: str, template_id: str):
    from app.services import flashcard_content_service

    try:
        payload = flashcard_content_service.reset_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload)

@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_template(note_type_id: str, template_id: str):
    from app.services import flashcard_content_service

    try:
        payload = flashcard_content_service.preview_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
            payload=request.get_json(silent=True) or {},
        )
    except flashcard_content_service.ContentApiError as exc:
        return _api_error(
            exc.error,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    return jsonify(payload)


@flashcards_bp.route("/api/note-types/<note_type_id>/publish", methods=["POST"])
@login_required
def publish_note_type(note_type_id: str):
    from app.services import marketplace_note_type_service
    try:
        payload = marketplace_note_type_service.publish_note_type(
            user_id=current_user.id,
            is_admin=is_admin_user(current_user),
            note_type_id=note_type_id,
            payload=request.get_json(silent=True) or {},
        )
    except marketplace_note_type_service.MarketplaceNoteTypeError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types", methods=["GET"])
@login_required
def list_shared_note_types():
    from app.services import marketplace_note_type_service
    payload = marketplace_note_type_service.list_shared_note_types(
        user_id=current_user.id,
        args=request.args,
    )
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>", methods=["GET"])
@login_required
def get_shared_note_type_detail(note_type_id: str):
    from app.services import marketplace_note_type_service
    try:
        payload = marketplace_note_type_service.get_shared_note_type_detail(
            user_id=current_user.id,
            note_type_id=note_type_id,
        )
    except marketplace_note_type_service.MarketplaceNoteTypeError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_note_type_template(note_type_id: str, template_id: str):
    from app.services import marketplace_note_type_service
    try:
        payload = marketplace_note_type_service.preview_shared_note_type_template(
            user_id=current_user.id,
            note_type_id=note_type_id,
            template_id=template_id,
        )
    except marketplace_note_type_service.MarketplaceNoteTypeError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/install", methods=["POST"])
@login_required
def install_shared_note_type(note_type_id: str):
    from app.services import marketplace_note_type_service
    try:
        payload, status_code = marketplace_note_type_service.install_shared_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
            return_url=_marketplace_payment_redirect_url(
                "payments.marketplace_payment_result_page",
            ),
            cancel_url=_marketplace_payment_redirect_url(
                "payments.marketplace_payment_result_page",
            ),
        )
    except marketplace_note_type_service.MarketplaceNoteTypeError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(payload), status_code


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/rate", methods=["POST"])
@login_required
def rate_shared_note_type(note_type_id: str):
    from app.services import marketplace_note_type_service
    req_json = request.get_json(silent=True) or {}
    try:
        rating = int(req_json.get("rating"))
    except (TypeError, ValueError):
        return _api_error("VALIDATION_ERROR", "rating must be an integer 1-5.", field="rating")

    try:
        payload = marketplace_note_type_service.rate_shared_note_type(
            user_id=current_user.id,
            note_type_id=note_type_id,
            rating=rating,
            comment=req_json.get("comment"),
        )
    except marketplace_note_type_service.MarketplaceNoteTypeError as exc:
        return _api_error(exc.error, exc.message, status=exc.status, field=exc.field)
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types/recommendations", methods=["GET"])
@login_required
def shared_note_type_recommendations():
    from app.services import marketplace_note_type_service
    payload = marketplace_note_type_service.get_recommendations(
        user_id=current_user.id
    )
    return jsonify(payload)


@flashcards_bp.route("/api/shared/decks", methods=["GET"])
@login_required
def list_shared_decks():

    query_text = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    tags = {item.lower() for item in _normalize_marketplace_tags(request.args.get("tags"))}
    pricing_mode = (request.args.get("pricing_mode") or request.args.get("pricing") or "").strip().lower()
    sort_key = (request.args.get("sort") or "popular").strip().lower()
    min_price_amount_minor = _parse_query_price_amount_minor("min_price")
    max_price_amount_minor = _parse_query_price_amount_minor("max_price")
    domain = (request.args.get("domain") or "").strip()
    subject = (request.args.get("subject") or "").strip()
    framework = (request.args.get("framework") or "").strip()
    framework_level = (request.args.get("framework_level") or "").strip()
    difficulty_band = (request.args.get("difficulty_band") or request.args.get("level") or "").strip()
    learning_goals = {item.lower() for item in _normalize_marketplace_tags(request.args.get("learning_goals") or request.args.get("goal") or request.args.get("goals"))}
    primary_topics = {item.lower() for item in _normalize_marketplace_tags(request.args.get("primary_topics") or request.args.get("topic") or request.args.get("topics"))}
    format_features = {item.lower() for item in _normalize_marketplace_tags(request.args.get("format_features") or request.args.get("feature") or request.args.get("features"))}

    visible_items = [
        item for item in DeckMarketplaceItem.query.order_by(DeckMarketplaceItem.updated_at.desc()).all()
        if _is_deck_item_visible_for_shared(item, current_user.id)
    ]
    filtered = _filter_deck_items(
        visible_items,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_amount_minor=min_price_amount_minor,
        max_price_amount_minor=max_price_amount_minor,
        domain=domain,
        subject=subject,
        framework=framework,
        framework_level=framework_level,
        difficulty_band=difficulty_band,
        learning_goals=learning_goals,
        primary_topics=primary_topics,
        format_features=format_features,
    )
    sorted_items = _sort_deck_items(filtered, sort_key)
    installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
    install_map = {row.deck_item_id: row for row in installs}
    stats_map = marketplace_query_service.batch_compute_deck_items_stats(sorted_items)
    payload_items = []
    for item in sorted_items:
        row = _serialize_deck_marketplace_item(item, stats=stats_map.get(item.id))
        install = install_map.get(item.id)
        row["is_installed"] = install is not None
        row["installed_deck_id"] = install.local_deck_id if install else None
        row["is_owner"] = item.owner_user_id == current_user.id
        payload_items.append(row)
    return jsonify({"items": payload_items})


@flashcards_bp.route("/api/shared/decks/publish-options", methods=["GET"])
@login_required
def shared_deck_publish_options():
    return jsonify(
        flashcards_share.build_deck_publish_options(user_id=current_user.id)
    )

@flashcards_bp.route("/api/shared/decks", methods=["POST"])
@login_required
def create_shared_deck_item():
    payload = request.get_json(silent=True) or {}
    deck_item, validation_error, error_field = flashcards_share.create_shared_deck_item(
        user_id=current_user.id,
        payload=payload,
        is_admin=is_admin_user(current_user),
        require_source_note_type=True,
    )
    if validation_error:
        if error_field == "source_note_type_id" and validation_error == "source_note_type_id not found.":
            return _api_error("FIELD_NOT_FOUND", validation_error, field=error_field, status=404)
        if error_field == "source_note_type_id" and "Marketplace" in validation_error:
            return _api_error("CONFLICT", validation_error, field=error_field, status=409)
        if error_field == "source_deck_id":
            source_not_found = validation_error == "source_deck_id not found."
            invalid_source_id = validation_error == "source_deck_id must be an integer."
            return _api_error(
                (
                    "FIELD_NOT_FOUND"
                    if source_not_found
                    else "VALIDATION_ERROR"
                    if invalid_source_id
                    else "CONFLICT"
                ),
                validation_error,
                field=error_field,
                status=404 if source_not_found else 400 if invalid_source_id else 409,
            )
        return _api_error("VALIDATION_ERROR", validation_error, field=error_field)
    if deck_item is None:
        return _api_error("VALIDATION_ERROR", "Failed to create deck item.")
    return jsonify(_serialize_deck_marketplace_item(deck_item)), 201

@flashcards_bp.route("/api/shared/decks/<deck_item_id>", methods=["GET"])
@login_required
def get_shared_deck_item(deck_item_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    payload = flashcards_share.build_shared_deck_item_payload(
        deck_item,
        user_id=current_user.id,
        sample_limit=SHARED_DECK_TEST_SAMPLE_LIMIT,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
        review_preview_limit=20,
    )
    review_submission_count = _count_user_market_review_submissions(
        user_id=current_user.id,
        action="market.deck_item.rate",
        payload_item_key="deck_item_id",
        payload_item_value=deck_item.id,
    )
    review_submissions_remaining = max(
        0, MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER - int(review_submission_count or 0)
    )
    payload["review_submission_count"] = review_submission_count
    payload["review_submissions_remaining"] = review_submissions_remaining
    payload["can_rate"] = bool(payload.get("can_rate")) and review_submissions_remaining > 0
    payload.update(
        marketplace_hub_service.build_deck_detail_extras(
            deck_item=deck_item,
            user_id=current_user.id,
        )
    )
    from app.services.marketplace_pricing_service import serialize_item_student_offer

    payload.update(serialize_item_student_offer(deck_item, current_user))
    payload["lessons"] = marketplace_query_service.build_shared_deck_lessons_structure(deck_item)

    return jsonify(payload)

@flashcards_bp.route("/api/shared/decks/<deck_item_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_deck_template(deck_item_id: str, template_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        return _api_error("VALIDATION_ERROR", "Deck item has no source note type.", status=409)

    note_type = db.session.get(NoteType, source_note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    payload = request.get_json(silent=True) or {}
    requested_note_id = (payload.get("note_id") or "").strip() or None
    preview_note = flashcards_share.select_preview_note_for_shared_deck(
        deck_item,
        note_type_id=note_type.id,
        requested_note_id=requested_note_id,
    )

    if preview_note:
        preview_field_values = preview_note.field_values or {}
        preview_media_assets = preview_note.media_assets
        preview_note_key = f"shared-deck-preview:{deck_item.id}:{preview_note.id}"
    else:
        preview_field_values = _build_preview_sample_values(note_type.field_defs)
        preview_media_assets = []
        preview_note_key = f"shared-deck-preview:{deck_item.id}:sample"

    try:
        rendered = render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values=preview_field_values,
            media_assets=preview_media_assets,
            preview_note_key=preview_note_key,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)

@flashcards_bp.route("/api/shared/decks/<deck_item_id>", methods=["PATCH"])
@login_required
def patch_shared_deck_item(deck_item_id: str):
    deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)
    if deck_item.owner_user_id != current_user.id and not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Only owner can edit deck item.", status=403)

    payload = request.get_json(silent=True) or {}
    _, validation_error, error_field = flashcards_share.update_shared_deck_item(
        deck_item=deck_item,
        user_id=current_user.id,
        payload=payload,
        is_admin=is_admin_user(current_user),
        require_source_note_type=True,
    )
    if validation_error:
        if error_field in {"version", "changelog"} and "managed by immutable deck releases" in validation_error:
            return _api_error("CONFLICT", validation_error, field=error_field, status=409)
        if error_field in {"source_deck_id", "source_note_type_id"} and "cannot be changed" in validation_error:
            return _api_error("CONFLICT", validation_error, field=error_field, status=409)
        if error_field == "source_deck_id" and validation_error == "source_deck_id not found.":
            return _api_error("FIELD_NOT_FOUND", validation_error, field=error_field, status=404)
        if error_field == "source_note_type_id" and validation_error == "source_note_type_id not found.":
            return _api_error("FIELD_NOT_FOUND", validation_error, field=error_field, status=404)
        return _api_error("VALIDATION_ERROR", validation_error, field=error_field)
    return jsonify(_serialize_deck_marketplace_item(deck_item))

@flashcards_bp.route("/api/shared/decks/<deck_item_id>/install", methods=["POST"])
@login_required
def install_shared_deck_item(deck_item_id: str):
    deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    from app.services.marketplace_pricing_service import calculate_pricing_breakdown

    pricing_breakdown = calculate_pricing_breakdown(deck_item, current_user)
    if deck_item.pricing_mode == "paid" and pricing_breakdown.is_payment_required:
        for attempt in range(1, SHARED_DECK_INSTALL_MAX_RETRIES + 1):
            if not str(deck_item.source_note_type_id or "").strip():
                return _api_error(
                    "VALIDATION_ERROR",
                    "source_note_type_id is required for install.",
                    status=409,
                    field="source_note_type_id",
                )

            from app.services import payment_service

            if not payment_service.paid_install_interception_enabled():
                return _api_error(
                    "PAYMENT_UNAVAILABLE",
                    "Thanh toán cho nội dung trả phí chưa được bật trong môi trường này. Vui lòng thử lại sau.",
                    status=503,
                )
            try:
                checkout = payment_service.prepare_checkout_for_product(
                    user_id=current_user.id,
                    product_type="deck_marketplace_item",
                    product_ref_id=deck_item.id,
                    return_url=_marketplace_payment_redirect_url(
                        "payments.marketplace_payment_result_page",
                    ),
                    cancel_url=_marketplace_payment_redirect_url(
                        "payments.marketplace_payment_result_page",
                    ),
                )
            except payment_service.PaymentServiceError as exc:
                return _api_error(
                    exc.error,
                    exc.message,
                    status=exc.status,
                    field=exc.field,
                )
            return jsonify(checkout), 202 if checkout.get("payment_required") else 200

        return _api_error(
            "DEADLOCK_RETRY_EXCEEDED",
            flashcards_share.SHARED_DECK_INSTALL_DEADLOCK_MESSAGE,
            status=409,
        )

    response_payload, error_message, error_field, status_code = flashcards_share.install_shared_deck_item(
        deck_item_id=deck_item_id,
        user_id=current_user.id,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if error_message:
        if status_code == 503:
            error_code = "DECK_RELEASE_NOT_READY"
        elif error_message == flashcards_share.SHARED_DECK_INSTALL_DEADLOCK_MESSAGE:
            error_code = "DEADLOCK_RETRY_EXCEEDED"
        elif status_code == 404:
            error_code = "FIELD_NOT_FOUND"
        else:
            error_code = "VALIDATION_ERROR"
        return _api_error(
            error_code,
            error_message,
            status=status_code,
            field=error_field,
        )
    return jsonify(response_payload or {}), status_code

@flashcards_bp.route("/api/shared/decks/<deck_item_id>/clone/overlay", methods=["POST"])
@login_required
def upsert_shared_deck_clone_overlay(deck_item_id: str):
    install = _get_user_deck_install_for_item(
        user_id=current_user.id,
        deck_item_id=deck_item_id,
    )
    if install is None:
        return _api_error("FIELD_NOT_FOUND", "Installed clone deck not found.", status=404)

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _api_error("VALIDATION_ERROR", "Payload must be an object.")

    counters, validation_error = _upsert_clone_overlay(
        deck_install=install,
        payload=payload,
    )
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)

    _audit(
        "market.deck_item.clone_overlay.upsert",
        {
            "deck_item_id": deck_item_id,
            "deck_install_id": install.id,
            "changes": counters,
        },
    )
    db.session.commit()
    return jsonify(
        {
            "deck_item_id": deck_item_id,
            "deck_install_id": install.id,
            "installed_deck_id": install.local_deck_id,
            "changes": counters,
        }
    )

@flashcards_bp.route("/api/shared/decks/<deck_item_id>/rate", methods=["POST"])
@login_required
def rate_shared_deck_item(deck_item_id: str):
    deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)
    if not _can_user_rate_deck(deck_item, user_id=current_user.id):
        return _api_error("VALIDATION_ERROR", "You can only rate after real usage.", status=403)
    review_submission_count = _count_user_market_review_submissions(
        user_id=current_user.id,
        action="market.deck_item.rate",
        payload_item_key="deck_item_id",
        payload_item_value=deck_item.id,
    )
    if review_submission_count >= MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER:
        return _api_error(
            "VALIDATION_ERROR",
            "You can submit at most 2 ratings for this item.",
            status=403,
        )

    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating"))
    except (TypeError, ValueError):
        return _api_error("VALIDATION_ERROR", "rating must be an integer 1-5.", field="rating")
    if rating < 1 or rating > 5:
        return _api_error("VALIDATION_ERROR", "rating must be between 1 and 5.", field="rating")
    comment = (payload.get("comment") or "").strip() or None

    flashcards_share.rate_shared_deck_item(
        deck_item=deck_item,
        user_id=current_user.id,
        rating=rating,
        comment=comment,
    )
    return jsonify(
        {
            "deck_item_id": deck_item.id,
            "rating_avg": deck_item.rating_avg,
            "rating_count": deck_item.rating_count,
            "my_rating": rating,
        }
    )

@flashcards_bp.route("/api/shared/decks/recommendations", methods=["GET"])
@login_required
def shared_deck_recommendations():
    visible_items = [item for item in DeckMarketplaceItem.query.all() if _is_deck_item_visible_for_shared(item)]
    interests_categories, interests_tags = _collect_user_market_interests(current_user.id)
    cold_start = not interests_categories and not interests_tags

    scored: list[tuple[float, DeckMarketplaceItem]] = []
    for item in visible_items:
        if item.owner_user_id == current_user.id:
            continue
        score = _score_market_item(
            item_category=item.primary_category,
            item_tags=item.tags or [],
            rating_avg=float(item.rating_avg or 0.0),
            rating_count=int(item.rating_count or 0),
            active_usage_count=int(item.active_usage_count or 0),
            install_count=int(item.install_count or 0),
            updated_at=item.updated_at,
            interests_categories=interests_categories,
            interests_tags=interests_tags,
            is_official=bool(item.is_official),
            cold_start=cold_start,
        )
        scored.append((score, item))

    recommended = [
        _serialize_deck_marketplace_item(item)
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:12]
    ]

    trending_cutoff = _utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
    trending_counts_raw = (
        db.session.query(DeckInstall.deck_item_id, db.func.count(DeckInstall.id))
        .filter(DeckInstall.installed_at >= trending_cutoff)
        .group_by(DeckInstall.deck_item_id)
        .all()
    )
    trending_counts = {row[0]: int(row[1] or 0) for row in trending_counts_raw}
    trending = sorted(
        visible_items,
        key=lambda item: (trending_counts.get(item.id, 0), int(item.active_usage_count or 0), int(item.install_count or 0)),
        reverse=True,
    )[:12]
    new_and_updated = _sort_deck_items(visible_items, "recently_updated")[:12]
    return jsonify(
        {
            "recommended_for_you": recommended,
            "top_by_category": _top_items_by_category_decks(visible_items),
            "trending": [_serialize_deck_marketplace_item(item) for item in trending],
            "new_and_updated": [_serialize_deck_marketplace_item(item) for item in new_and_updated],
        }
    )
