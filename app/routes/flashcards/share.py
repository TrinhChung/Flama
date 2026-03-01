"""Sub-module for flashcard routes."""

from __future__ import annotations

import logging
from datetime import datetime
import time

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

from app.routes.flashcards import (
    _api_error,
    _build_preview_sample_values,
    _get_note_type_or_404,
)

from app.services import flashcards_share_service as share_ctrl
from app.services import marketplace_query_service as marketplace_query_service

@flashcards_bp.route("/flashcards/shared-note-types")
@login_required
def shared_note_types_page():
    return render_template("flashcards/shared_note_types.html")


@flashcards_bp.route("/flashcards/shared-note-types/<note_type_id>")
@login_required
def shared_note_type_detail_page(note_type_id: str):
    return render_template("flashcards/shared_note_type_detail.html", note_type_id=note_type_id)


@flashcards_bp.route("/flashcards/shared-decks")
@login_required
def shared_decks_page():
    return render_template("flashcards/shared_decks.html")


@flashcards_bp.route("/flashcards/shared-decks/<deck_item_id>")
@login_required
def shared_deck_detail_page(deck_item_id: str):
    return render_template("flashcards/shared_deck_detail.html", deck_item_id=deck_item_id)


@flashcards_bp.route("/api/note-types", methods=["POST"])
@login_required
def create_note_type():
    payload = request.get_json(silent=True) or {}
    from app.services.flashcards_share_service import create_note_type as svc_create_note_type
    note_type, validation_error, error_field = svc_create_note_type(
        user_id=current_user.id,
        payload=payload,
        is_admin=is_admin_user(current_user)
    )
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error, field=error_field)
    return jsonify(marketplace_query_service.serialize_note_type(note_type)), 201


@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["POST"])
@login_required
def create_template(note_type_id: str):
    from app.services.flashcards_share_service import create_template as svc_create_template
    payload = request.get_json(silent=True) or {}
    template, validation_error = svc_create_template(
        note_type_id=note_type_id,
        user_id=current_user.id,
        payload=payload
    )
    if validation_error:
        return _api_error("FIELD_NOT_FOUND", validation_error, status=404)
    return jsonify(marketplace_query_service.serialize_template(template)), 201


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["PATCH"])
@login_required
def patch_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        template.name = (payload.get("name") or "").strip() or template.name
    if "front_html" in payload:
        template.front_html = str(payload.get("front_html") or "")
    if "back_html" in payload:
        template.back_html = str(payload.get("back_html") or "")
    if "shared_css" in payload:
        template.shared_css = str(payload.get("shared_css") or "")

    try:
        render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values={},
            media_assets=[],
            preview_note_key="validation",
        )
    except TemplateCompileError as exc:
        db.session.rollback()
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    from app.services.flashcards_share_service import update_template as svc_update_template
    svc_update_template(template, user_id=current_user.id)
    return jsonify(marketplace_query_service.serialize_template(template))


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/reset", methods=["POST"])
@login_required
def reset_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    from app.services.flashcards_share_service import reset_template as svc_reset_template
    svc_reset_template(
        template,
        default_front=LEGACY_FRONT_TEMPLATE.strip(),
        default_back=LEGACY_BACK_TEMPLATE.strip(),
        default_css=LEGACY_SHARED_CSS.strip()
    )
    return jsonify(marketplace_query_service.serialize_template(template))


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    payload = request.get_json(silent=True) or {}
    note_id = (payload.get("note_id") or "").strip()
    raw_use_sample_data = payload.get("use_sample_data", False)
    use_sample_data = bool(raw_use_sample_data)
    if isinstance(raw_use_sample_data, str):
        use_sample_data = raw_use_sample_data.strip().lower() in {"1", "true", "yes", "on"}

    preview_front_html = template.front_html
    preview_back_html = template.back_html
    preview_shared_css = template.shared_css
    if "front_html" in payload:
        preview_front_html = str(payload.get("front_html") or "")
    if "back_html" in payload:
        preview_back_html = str(payload.get("back_html") or "")
    if "shared_css" in payload:
        preview_shared_css = str(payload.get("shared_css") or "")

    preview_template_obj = SimpleNamespace(
        id=template.id,
        front_html=preview_front_html,
        back_html=preview_back_html,
        shared_css=preview_shared_css,
        updated_at=template.updated_at,
    )

    sample_field_values: dict[str, Any]
    sample_media_assets: list[MediaAsset]
    preview_note_key: str

    if use_sample_data:
        sample_field_values = _build_preview_sample_values(note_type.field_defs)
        sample_media_assets = []
        preview_note_key = f"sample:{note_type.id}"
    else:
        note = None
        if note_id:
            note = Note.query.filter_by(id=note_id, user_id=current_user.id, note_type_id=note_type.id).first()
        if note is None:
            note = (
                Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id)
                .order_by(Note.created_at.asc())
                .first()
            )

        sample_field_values = {}
        sample_media_assets = []
        preview_note_key = note.id if note else "empty-note"
        if note:
            sample_field_values = note.field_values or {}
            sample_media_assets = note.media_assets

    try:
        rendered = render_template_pair(
            template=preview_template_obj,
            field_defs=note_type.field_defs,
            field_values=sample_field_values,
            media_assets=sample_media_assets,
            preview_note_key=preview_note_key,
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)


@flashcards_bp.route("/api/note-types/<note_type_id>/publish", methods=["POST"])
@login_required
def publish_note_type(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    payload = request.get_json(silent=True) or {}
    from app.services.flashcards_share_service import publish_note_type as svc_publish_note_type
    
    success, validation_error = svc_publish_note_type(
        note_type=note_type,
        user_id=current_user.id,
        payload=payload,
        is_admin=is_admin_user(current_user)
    )
    if not success:
        return _api_error("VALIDATION_ERROR", validation_error)

    return jsonify(marketplace_query_service.serialize_note_type(note_type))


@flashcards_bp.route("/api/shared/note-types", methods=["GET"])
@login_required
def list_shared_note_types():
    query_text = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    tags = {item.lower() for item in marketplace_query_service.normalize_marketplace_tags(request.args.get("tags"))}
    pricing_mode = (request.args.get("pricing_mode") or request.args.get("pricing") or "").strip().lower()
    sort_key = (request.args.get("sort") or "popular").strip().lower()

    min_price_cents = marketplace_query_service.parse_query_price_cents(request.args.get("min_price"))
    max_price_cents = marketplace_query_service.parse_query_price_cents(request.args.get("max_price"))

    visible_note_types = marketplace_query_service.get_visible_note_types(current_user.id)

    filtered = marketplace_query_service.filter_note_type_items(
        visible_note_types,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )
    sorted_items = marketplace_query_service.sort_note_type_items(filtered, sort_key)

    installs = NoteTypeInstall.query.filter_by(user_id=current_user.id).all()
    install_map = {row.source_note_type_id: row for row in installs}

    payload_items = []
    for note_type in sorted_items:
        row = marketplace_query_service.serialize_note_type_marketplace_card(note_type)
        install = install_map.get(note_type.id)
        row["is_installed"] = install is not None
        row["installed_note_type_id"] = install.installed_note_type_id if install else None
        row["is_owner"] = note_type.user_id == current_user.id
        payload_items.append(row)

    return jsonify({"items": payload_items})


@flashcards_bp.route("/api/shared/note-types/<note_type_id>", methods=["GET"])
@login_required
def get_shared_note_type_detail(note_type_id: str):
    note_type = share_ctrl.get_shared_note_type_for_view(note_type_id, current_user.id, share_ctrl.PUBLISH_STATUSES_VISIBLE)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    install = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id,
        user_id=current_user.id,
    ).first()
    review = NoteTypeReview.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).first()

    payload = marketplace_query_service.serialize_note_type_marketplace_card(note_type)
    payload["is_installed"] = install is not None
    payload["installed_note_type_id"] = install.installed_note_type_id if install else None
    payload["is_owner"] = note_type.user_id == current_user.id
    payload["can_rate"] = share_ctrl.can_user_rate_note_type(note_type, user_id=current_user.id)
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }
        if review
        else None
    )
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_note_type_template(note_type_id: str, template_id: str):
    note_type = share_ctrl.get_shared_note_type_for_view(note_type_id, current_user.id, share_ctrl.PUBLISH_STATUSES_VISIBLE)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    sample_field_values = _build_preview_sample_values(note_type.field_defs)

    try:
        rendered = render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values=sample_field_values,
            media_assets=[],
            preview_note_key=f"shared-preview:{note_type.id}",
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/install", methods=["POST"])
@login_required
def install_shared_note_type(note_type_id: str):
    source_note_type = NoteType.query.get(note_type_id)
    if not source_note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in share_ctrl.PUBLISH_STATUSES_VISIBLE:
        return _api_error("VALIDATION_ERROR", "This note type is not available for install.", status=409)

    if source_note_type.user_id == current_user.id:
        return _api_error("VALIDATION_ERROR", "Owner cannot install own note type.", status=409)

    existing = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=current_user.id,
    ).first()

    if existing:
        return jsonify(
            {
                "installed_note_type_id": existing.installed_note_type_id,
                "source_note_type_id": source_note_type.id,
                "already_installed": True,
            }
        )

    from app.services.flashcards_share_service import install_shared_note_type as svc_install_shared_note_type
    installed_copy, purchase_price_cents = svc_install_shared_note_type(
        source_note_type=source_note_type,
        user_id=current_user.id,
    )

    return jsonify(
        {
            "installed_note_type_id": installed_copy.id,
            "source_note_type_id": source_note_type.id,
            "purchase_price_cents": purchase_price_cents,
        }
    ), 201


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/rate", methods=["POST"])
@login_required
def rate_shared_note_type(note_type_id: str):
    note_type = NoteType.query.get(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    if not share_ctrl.can_user_rate_note_type(note_type, user_id=current_user.id):
        return _api_error("VALIDATION_ERROR", "You can only rate after real usage.", status=403)

    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating"))
    except (TypeError, ValueError):
        return _api_error("VALIDATION_ERROR", "rating must be an integer 1-5.", field="rating")

    if rating < 1 or rating > 5:
        return _api_error("VALIDATION_ERROR", "rating must be between 1 and 5.", field="rating")

    comment = (payload.get("comment") or "").strip() or None

    from app.services.flashcards_share_service import rate_shared_note_type as svc_rate_shared_note_type
    svc_rate_shared_note_type(
        note_type=note_type,
        user_id=current_user.id,
        rating=rating,
        comment=comment,
    )

    return jsonify(
        {
            "note_type_id": note_type.id,
            "rating_avg": note_type.rating_avg,
            "rating_count": note_type.rating_count,
            "my_rating": rating,
        }
    )


@flashcards_bp.route("/api/shared/note-types/recommendations", methods=["GET"])
@login_required
def shared_note_type_recommendations():
    visible_items = marketplace_query_service.get_visible_note_types(current_user.id)
    return jsonify(marketplace_query_service.get_note_type_recommendations(current_user.id, visible_items))


@flashcards_bp.route("/api/shared/decks", methods=["GET"])
@login_required
def list_shared_decks():
    query_text = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    tags = {item.lower() for item in marketplace_query_service.normalize_marketplace_tags(request.args.get("tags"))}
    pricing_mode = (request.args.get("pricing_mode") or request.args.get("pricing") or "").strip().lower()
    sort_key = (request.args.get("sort") or "popular").strip().lower()

    min_price_cents = marketplace_query_service.parse_query_price_cents(request.args.get("min_price"))
    max_price_cents = marketplace_query_service.parse_query_price_cents(request.args.get("max_price"))

    visible_items = marketplace_query_service.get_visible_deck_items(current_user.id)

    filtered = marketplace_query_service.filter_deck_items(
        visible_items,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )
    sorted_items = marketplace_query_service.sort_deck_items(filtered, sort_key)

    installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
    install_map = {row.deck_item_id: row for row in installs}

    payload_items = []
    for item in sorted_items:
        row = marketplace_query_service.serialize_deck_marketplace_item(item)
        install = install_map.get(item.id)
        row["is_installed"] = install is not None
        row["installed_deck_id"] = install.local_deck_id if install else None
        row["is_owner"] = item.owner_user_id == current_user.id
        payload_items.append(row)

    return jsonify({"items": payload_items})


@flashcards_bp.route("/api/shared/decks", methods=["POST"])
@login_required
def create_shared_deck_item():
    payload = request.get_json(silent=True) or {}
    from app.services.flashcards_share_service import create_shared_deck_item as svc_create_shared_deck_item
    
    deck_item, validation_error, error_field = svc_create_shared_deck_item(
        user_id=current_user.id,
        payload=payload,
        is_admin=is_admin_user(current_user),
        require_source_note_type=True
    )
    if validation_error:
        return _api_error(
            "FIELD_NOT_FOUND" if error_field == "source_deck_id" else "VALIDATION_ERROR", 
            validation_error, 
            field=error_field,
            status=404 if error_field == "source_deck_id" else 400
        )

    return jsonify(marketplace_query_service.serialize_deck_marketplace_item(deck_item)), 201


@flashcards_bp.route("/api/shared/decks/<deck_item_id>", methods=["GET"])
@login_required
def get_shared_deck_item(deck_item_id: str):
    deck_item = share_ctrl.get_shared_deck_item_for_view(
        deck_item_id, current_user.id, share_ctrl.PUBLISH_STATUSES_VISIBLE
    )
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    from app.services.flashcards_share_service import sync_deck_item_source_note_type_and_commit
    bind_error, changed = sync_deck_item_source_note_type_and_commit(
        deck_item,
        require_source_note_type=False,
    )

    payload = share_ctrl.build_shared_deck_item_payload(
        deck_item,
        user_id=current_user.id,
        sample_limit=share_ctrl.SHARED_DECK_TEST_SAMPLE_LIMIT,
        deck_active_review_threshold=share_ctrl.DECK_ACTIVE_REVIEW_THRESHOLD,
    )

    return jsonify(payload)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_deck_template(deck_item_id: str, template_id: str):
    deck_item = share_ctrl.get_shared_deck_item_for_view(deck_item_id, current_user.id, share_ctrl.PUBLISH_STATUSES_VISIBLE)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    from app.services.flashcards_share_service import sync_deck_item_source_note_type_and_commit
    bind_error, changed = sync_deck_item_source_note_type_and_commit(
        deck_item,
        require_source_note_type=True,
    )
    if bind_error:
        return _api_error("VALIDATION_ERROR", bind_error, status=409)

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        return _api_error("VALIDATION_ERROR", "Deck item has no source note type.", status=409)

    note_type = NoteType.query.get(source_note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    payload = request.get_json(silent=True) or {}
    requested_note_id = (payload.get("note_id") or "").strip() or None

    preview_note = share_ctrl.select_preview_note_for_shared_deck(
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
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>", methods=["PATCH"])
@login_required
def patch_shared_deck_item(deck_item_id: str):
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    if deck_item.owner_user_id != current_user.id and not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Only owner can edit deck item.", status=403)

    payload = request.get_json(silent=True) or {}
    
    from app.services.flashcards_share_service import update_shared_deck_item as svc_update_shared_deck_item
    success, validation_error, error_field = svc_update_shared_deck_item(
        deck_item=deck_item,
        user_id=current_user.id,
        payload=payload,
        is_admin=is_admin_user(current_user),
        require_source_note_type=True
    )
    if not success:
        return _api_error(
            "FIELD_NOT_FOUND" if error_field == "source_deck_id" else "VALIDATION_ERROR", 
            validation_error, 
            field=error_field,
            status=404 if error_field == "source_deck_id" else 400
        )

    return jsonify(marketplace_query_service.serialize_deck_marketplace_item(deck_item))


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/install", methods=["POST"])
@login_required
def install_shared_deck_item(deck_item_id: str):
    from app.services.flashcards_share_service import install_shared_deck_item as svc_install_shared_deck_item
    response, validation_error, error_field, status = svc_install_shared_deck_item(
        deck_item_id=deck_item_id,
        user_id=current_user.id,
        publish_statuses_visible=share_ctrl.PUBLISH_STATUSES_VISIBLE
    )
    if validation_error:
        return _api_error(
            "VALIDATION_ERROR", 
            validation_error, 
            field=error_field,
            status=status
        )
    
    return jsonify(response), status


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/clone/overlay", methods=["POST"])
@login_required
def upsert_shared_deck_clone_overlay(deck_item_id: str):
    install = share_ctrl.get_user_deck_install_for_item(
        user_id=current_user.id,
        deck_item_id=deck_item_id,
    )
    if not install:
        return _api_error("FIELD_NOT_FOUND", "Deck must be installed first.", status=404)

    payload = request.get_json(silent=True) or {}
    from app.services.flashcards_share_service import upsert_shared_deck_clone_overlay as svc_upsert_shared_deck_clone_overlay
    
    counters, validation_error = svc_upsert_shared_deck_clone_overlay(
        deck_item_id=deck_item_id,
        install=install,
        user_id=current_user.id,
        payload=payload
    )
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)

    response_payload = {"success": True, "changes": counters or {}}
    if counters:
        response_payload.update(counters)
    return jsonify(response_payload)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/rate", methods=["POST"])
@login_required
def rate_shared_deck_item(deck_item_id: str):
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    if not share_ctrl.can_user_rate_deck_item(deck_item, user_id=current_user.id):
        return _api_error("VALIDATION_ERROR", "You can only rate after real usage.", status=403)

    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating"))
    except (TypeError, ValueError):
        return _api_error("VALIDATION_ERROR", "rating must be an integer 1-5.", field="rating")

    if rating < 1 or rating > 5:
        return _api_error("VALIDATION_ERROR", "rating must be between 1 and 5.", field="rating")

    comment = (payload.get("comment") or "").strip() or None

    from app.services.flashcards_share_service import rate_shared_deck_item as svc_rate_shared_deck_item
    svc_rate_shared_deck_item(
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
    visible_items = marketplace_query_service.get_visible_deck_items(current_user.id)
    return jsonify(marketplace_query_service.get_deck_recommendations(current_user.id, visible_items))
