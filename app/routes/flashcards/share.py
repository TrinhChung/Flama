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
from app.services import flashcards_share
from app.services import marketplace_hub_service
from app.services import payment_service
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

# Backward-compatible alias used by tests and legacy patch targets.
share_ctrl = flashcards_share

MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER = 2


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


@flashcards_bp.route("/api/shared/note-types/hub", methods=["GET"])
@login_required
def shared_note_types_hub():
    filters = marketplace_hub_service.parse_marketplace_filters(request.args)
    payload = marketplace_hub_service.build_note_type_marketplace_hub(
        user_id=current_user.id,
        filters=filters,
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
    note_type = _get_shared_note_type_for_view(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    if note_type.user_id == current_user.id:
        return _api_error("VALIDATION_ERROR", "Owner cannot save own note type.", status=409)
    if request.method == "POST":
        marketplace_hub_service.save_item_for_user(
            user_id=current_user.id,
            product_type="note_type",
            product_ref_id=note_type.id,
        )
        db.session.commit()
        return jsonify({"saved": True, "note_type_id": note_type.id})
    marketplace_hub_service.remove_saved_item_for_user(
        user_id=current_user.id,
        product_type="note_type",
        product_ref_id=note_type.id,
    )
    db.session.commit()
    return jsonify({"saved": False, "note_type_id": note_type.id})


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
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or payload.get("title") or "").strip()
    if not name:
        return _api_error("VALIDATION_ERROR", "Note type name is required.", field="name")

    if NoteType.query.filter_by(user_id=current_user.id, name=name).first():
        return _api_error("VALIDATION_ERROR", "Note type already exists.", field="name")

    note_type = NoteType(user_id=current_user.id, name=name)
    db.session.add(note_type)
    db.session.flush()

    input_fields = payload.get("field_defs")
    if not isinstance(input_fields, list) or not input_fields:
        input_fields = [{"name": "Word", "field_type": "text", "position": 0, "required": True}]

    for idx, row in enumerate(input_fields):
        field_name = (row.get("name") or "").strip()
        field_type = (row.get("field_type") or "text").strip()
        required = bool(row.get("required", False))
        if not field_name:
            return _api_error("VALIDATION_ERROR", "Field name is required.", field="field_defs")
        if field_type not in FIELD_TYPES:
            return _api_error("VALIDATION_ERROR", f"Unsupported field_type: {field_type}", field="field_defs")
        db.session.add(
            FieldDef(
                note_type_id=note_type.id,
                name=field_name,
                field_type=field_type,
                position=int(row.get("position", idx)),
                required=required,
            )
        )

    template_payload = payload.get("template") or {}
    front_html = (template_payload.get("front_html") or "{{Word}}").strip()
    back_html = (template_payload.get("back_html") or "{{Word}}").strip()
    shared_css = (template_payload.get("shared_css") or "").strip()
    template = Template(
        note_type_id=note_type.id,
        name=(template_payload.get("name") or "Card 1").strip() or "Card 1",
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=0,
        is_default=True,
    )
    db.session.add(template)
    metadata_error = _apply_note_type_marketplace_payload(note_type, payload)
    if metadata_error:
        db.session.rollback()
        return _api_error("VALIDATION_ERROR", metadata_error)
    _audit("note_type.create", {"note_type_id": note_type.id, "name": note_type.name})
    db.session.commit()
    return jsonify(_serialize_note_type(note_type)), 201

@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["POST"])
@login_required
def create_template(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip() or f"Card {Template.query.filter_by(note_type_id=note_type.id).count() + 1}"
    front_html = (payload.get("front_html") or "{{Word}}").strip()
    back_html = (payload.get("back_html") or "{{Word}}").strip()
    shared_css = (payload.get("shared_css") or "").strip()
    max_pos = db.session.query(db.func.max(Template.position)).filter_by(note_type_id=note_type.id).scalar() or -1
    template = Template(
        note_type_id=note_type.id,
        name=name,
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=max_pos + 1,
        is_default=False,
    )
    db.session.add(template)
    db.session.flush()
    notes = Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).all()
    for note in notes:
        db.session.add(Card(note_id=note.id, template_id=template.id))
    _audit("template.create", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify(_serialize_template(template)), 201

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

    _audit("template.update", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify(_serialize_template(template))

@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/reset", methods=["POST"])
@login_required
def reset_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    template.front_html = LEGACY_FRONT_TEMPLATE.strip()
    template.back_html = LEGACY_BACK_TEMPLATE.strip()
    template.shared_css = LEGACY_SHARED_CSS.strip()
    db.session.commit()
    return jsonify(_serialize_template(template))

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
    
    # Cho phép ghi đè nội dung HTML/CSS thông qua payload (phục vụ Live Preview chưa lưu)
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
    payload.setdefault("publish_status", "published")
    validation_error = _apply_note_type_marketplace_payload(note_type, payload)
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)
    _recompute_note_type_market_stats(note_type)
    _audit("note_type.publish", {"note_type_id": note_type.id, "publish_status": note_type.publish_status})
    db.session.commit()
    return jsonify(_serialize_note_type(note_type))

@flashcards_bp.route("/api/shared/note-types", methods=["GET"])
@login_required
def list_shared_note_types():
    query_text = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    tags = {item.lower() for item in _normalize_marketplace_tags(request.args.get("tags"))}
    pricing_mode = (request.args.get("pricing_mode") or request.args.get("pricing") or "").strip().lower()
    sort_key = (request.args.get("sort") or "popular").strip().lower()
    min_price_amount_minor = _parse_query_price_amount_minor("min_price")
    max_price_amount_minor = _parse_query_price_amount_minor("max_price")

    visible_note_types = [
        item for item in NoteType.query.order_by(NoteType.updated_at.desc()).all()
        if _is_note_type_visible_for_shared(item)
    ]
    filtered = _filter_note_type_items(
        visible_note_types,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_amount_minor=min_price_amount_minor,
        max_price_amount_minor=max_price_amount_minor,
    )
    sorted_items = _sort_note_type_items(filtered, sort_key)

    installs = NoteTypeInstall.query.filter_by(user_id=current_user.id).all()
    install_map = {row.source_note_type_id: row for row in installs}
    payload_items = []
    for note_type in sorted_items:
        row = _serialize_note_type_marketplace_card(note_type)
        install = install_map.get(note_type.id)
        row["is_installed"] = install is not None
        row["installed_note_type_id"] = install.installed_note_type_id if install else None
        row["is_owner"] = note_type.user_id == current_user.id
        payload_items.append(row)
    return jsonify({"items": payload_items})

@flashcards_bp.route("/api/shared/note-types/<note_type_id>", methods=["GET"])
@login_required
def get_shared_note_type_detail(note_type_id: str):
    note_type = _get_shared_note_type_for_view(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    install = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id,
        user_id=current_user.id,
    ).first()
    review = NoteTypeReview.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).first()
    review_submission_count = _count_user_market_review_submissions(
        user_id=current_user.id,
        action="market.note_type.rate",
        payload_item_key="note_type_id",
        payload_item_value=note_type.id,
    )
    review_submissions_remaining = max(
        0, MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER - int(review_submission_count or 0)
    )
    payload = _serialize_note_type_marketplace_card(note_type)
    payload["is_installed"] = install is not None
    payload["installed_note_type_id"] = install.installed_note_type_id if install else None
    payload["is_owner"] = note_type.user_id == current_user.id
    payload["can_rate"] = _can_user_rate_note_type(note_type, user_id=current_user.id) and review_submissions_remaining > 0
    payload["review_submission_count"] = review_submission_count
    payload["review_submissions_remaining"] = review_submissions_remaining
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }
        if review
        else None
    )
    payload.update(
        marketplace_hub_service.build_note_type_detail_extras(
            note_type=note_type,
            user_id=current_user.id,
        )
    )
    return jsonify(payload)

@flashcards_bp.route("/api/shared/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_note_type_template(note_type_id: str, template_id: str):
    note_type = _get_shared_note_type_for_view(note_type_id)
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
    if status not in PUBLISH_STATUSES_VISIBLE:
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
    if source_note_type.pricing_mode == "paid":
        if not payment_service.paid_install_interception_enabled():
            return _api_error(
                "PAYMENT_UNAVAILABLE",
                "Thanh toán cho nội dung trả phí chưa được bật trong môi trường này. Vui lòng thử lại sau.",
                status=503,
            )
        try:
            checkout = payment_service.prepare_checkout_for_product(
                user_id=current_user.id,
                product_type="note_type",
                product_ref_id=source_note_type.id,
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

    installed_copy = _clone_note_type_for_user(source_note_type, current_user.id)
    now = datetime.utcnow()
    purchase_amount_minor = int(source_note_type.price_amount_minor or 0) if source_note_type.pricing_mode == "paid" else 0
    install_row = NoteTypeInstall(
        source_note_type_id=source_note_type.id,
        installed_note_type_id=installed_copy.id,
        user_id=current_user.id,
        purchase_amount_minor=purchase_amount_minor,
        installed_at=now,
        purchased_at=now if source_note_type.pricing_mode == "paid" else None,
    )
    db.session.add(install_row)
    _recompute_note_type_market_stats(source_note_type)
    _audit(
        "market.note_type.install",
        {
            "source_note_type_id": source_note_type.id,
            "installed_note_type_id": installed_copy.id,
            "price_amount_minor": purchase_amount_minor,
        },
    )
    db.session.commit()
    return jsonify(
        {
            "installed_note_type_id": installed_copy.id,
            "source_note_type_id": source_note_type.id,
            "purchase_amount_minor": purchase_amount_minor,
            "purchase_price_cents": purchase_amount_minor,
        }
    ), 201

@flashcards_bp.route("/api/shared/note-types/<note_type_id>/rate", methods=["POST"])
@login_required
def rate_shared_note_type(note_type_id: str):
    note_type = NoteType.query.get(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    if not _can_user_rate_note_type(note_type, user_id=current_user.id):
        return _api_error("VALIDATION_ERROR", "You can only rate after real usage.", status=403)
    review_submission_count = _count_user_market_review_submissions(
        user_id=current_user.id,
        action="market.note_type.rate",
        payload_item_key="note_type_id",
        payload_item_value=note_type.id,
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

    review = NoteTypeReview.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).first()
    if review is None:
        review = NoteTypeReview(note_type_id=note_type.id, user_id=current_user.id, rating=rating, comment=comment)
        db.session.add(review)
    else:
        review.rating = rating
        review.comment = comment

    _recompute_note_type_market_stats(note_type)
    _audit("market.note_type.rate", {"note_type_id": note_type.id, "rating": rating})
    db.session.commit()
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
    visible_items = [item for item in NoteType.query.all() if _is_note_type_visible_for_shared(item)]
    interests_categories, interests_tags = _collect_user_market_interests(current_user.id)
    cold_start = not interests_categories and not interests_tags

    scored: list[tuple[float, NoteType]] = []
    for item in visible_items:
        if item.user_id == current_user.id:
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
        _serialize_note_type_marketplace_card(item)
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:12]
    ]

    trending_cutoff = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
    trending_counts_raw = (
        db.session.query(NoteTypeInstall.source_note_type_id, db.func.count(NoteTypeInstall.id))
        .filter(NoteTypeInstall.installed_at >= trending_cutoff)
        .group_by(NoteTypeInstall.source_note_type_id)
        .all()
    )
    trending_counts = {row[0]: int(row[1] or 0) for row in trending_counts_raw}
    trending = sorted(
        visible_items,
        key=lambda item: (trending_counts.get(item.id, 0), int(item.active_usage_count or 0), int(item.install_count or 0)),
        reverse=True,
    )[:12]
    new_and_updated = _sort_note_type_items(visible_items, "recently_updated")[:12]
    return jsonify(
        {
            "recommended_for_you": recommended,
            "top_by_category": _top_items_by_category_note_types(visible_items),
            "trending": [_serialize_note_type_marketplace_card(item) for item in trending],
            "new_and_updated": [_serialize_note_type_marketplace_card(item) for item in new_and_updated],
        }
    )

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

    visible_items = [
        item for item in DeckMarketplaceItem.query.order_by(DeckMarketplaceItem.updated_at.desc()).all()
        if _is_deck_item_visible_for_shared(item)
    ]
    filtered = _filter_deck_items(
        visible_items,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_amount_minor=min_price_amount_minor,
        max_price_amount_minor=max_price_amount_minor,
    )
    sorted_items = _sort_deck_items(filtered, sort_key)
    installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
    install_map = {row.deck_item_id: row for row in installs}
    payload_items = []
    for item in sorted_items:
        row = _serialize_deck_marketplace_item(item)
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
    title = (payload.get("title") or "").strip()
    if not title:
        return _api_error("VALIDATION_ERROR", "title is required.", field="title")

    deck_item = DeckMarketplaceItem(
        owner_user_id=current_user.id,
        title=title,
        description=(payload.get("description") or "").strip(),
        primary_category=(payload.get("primary_category") or "General").strip() or "General",
        tags=_normalize_marketplace_tags(payload.get("tags")),
        preview_text=(payload.get("preview_text") or "").strip() or None,
        sample_cards_count=0,
        pricing_mode="free",
        price_amount_minor=0,
        version="1.0.0",
        publish_status="private",
        is_official=False,
    )
    db.session.add(deck_item)
    validation_error = _apply_deck_marketplace_payload(deck_item, payload)
    if validation_error:
        db.session.rollback()
        return _api_error("VALIDATION_ERROR", validation_error)
    if deck_item.source_deck_id is not None and not Deck.query.get(deck_item.source_deck_id):
        db.session.rollback()
        return _api_error("FIELD_NOT_FOUND", "source_deck_id not found.", field="source_deck_id", status=404)
    bind_error = _bind_deck_item_source_note_type(deck_item, require_source_note_type=True)
    if bind_error:
        db.session.rollback()
        return _api_error("VALIDATION_ERROR", bind_error, field="source_note_type_id")
    _recompute_deck_item_market_stats(deck_item)
    _audit("market.deck_item.create", {"deck_item_id": deck_item.id})
    db.session.commit()
    return jsonify(_serialize_deck_marketplace_item(deck_item)), 201

@flashcards_bp.route("/api/shared/decks/<deck_item_id>", methods=["GET"])
@login_required
def get_shared_deck_item(deck_item_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    _, changed = flashcards_share.sync_deck_item_source_note_type(
        deck_item,
        require_source_note_type=False,
    )
    if changed:
        db.session.commit()

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

    return jsonify(payload)

@flashcards_bp.route("/api/shared/decks/<deck_item_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_deck_template(deck_item_id: str, template_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    bind_error, changed = flashcards_share.sync_deck_item_source_note_type(
        deck_item,
        require_source_note_type=True,
    )
    if bind_error:
        return _api_error("VALIDATION_ERROR", bind_error, status=409)
    if changed:
        db.session.commit()

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
    validation_error = _apply_deck_marketplace_payload(deck_item, payload)
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)
    if deck_item.source_deck_id is not None and not Deck.query.get(deck_item.source_deck_id):
        return _api_error("FIELD_NOT_FOUND", "source_deck_id not found.", field="source_deck_id", status=404)
    bind_error = _bind_deck_item_source_note_type(deck_item, require_source_note_type=True)
    if bind_error:
        return _api_error("VALIDATION_ERROR", bind_error, field="source_note_type_id")
    _recompute_deck_item_market_stats(deck_item)
    _audit("market.deck_item.update", {"deck_item_id": deck_item.id})
    db.session.commit()
    return jsonify(_serialize_deck_marketplace_item(deck_item))

@flashcards_bp.route("/api/shared/decks/<deck_item_id>/install", methods=["POST"])
@login_required
def install_shared_deck_item(deck_item_id: str):
    for attempt in range(1, SHARED_DECK_INSTALL_MAX_RETRIES + 1):
        deck_item = DeckMarketplaceItem.query.get(deck_item_id)
        if not deck_item:
            return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

        bind_error, changed = flashcards_share.sync_deck_item_source_note_type(
            deck_item,
            require_source_note_type=True,
        )
        if bind_error:
            return _api_error("VALIDATION_ERROR", bind_error, status=409)

        if changed:
            try:
                db.session.commit()
            except OperationalError as exc:
                db.session.rollback()
                if _is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                    logger.warning(
                        "Deadlock while syncing source note type for shared deck install "
                        "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                        deck_item_id,
                        current_user.id,
                        attempt,
                        SHARED_DECK_INSTALL_MAX_RETRIES,
                    )
                    time.sleep(0.05 * attempt)
                    continue
                raise

        if deck_item.pricing_mode == "paid":
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

        try:
            install_result = flashcards_share.install_shared_deck_item_for_user(
                deck_item,
                user_id=current_user.id,
                publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
            )
        except flashcards_share.ShareControllerError as exc:
            db.session.rollback()
            return _api_error(
                exc.error,
                exc.message,
                status=exc.status,
                field=exc.field,
            )
        except OperationalError as exc:
            db.session.rollback()
            if _is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while installing shared deck "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    current_user.id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if _is_mysql_deadlock(exc):
                return _api_error(
                    "DEADLOCK_RETRY_EXCEEDED",
                    "Hệ thống đang bận khi cài deck này. Vui lòng thử lại sau vài giây.",
                    status=409,
                )
            raise

        if not install_result.get("created"):
            return jsonify(install_result.get("response") or {})

        _audit("market.deck_item.install", install_result.get("audit") or {})
        try:
            db.session.commit()
        except OperationalError as exc:
            db.session.rollback()
            if _is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while committing shared deck install "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    current_user.id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if _is_mysql_deadlock(exc):
                return _api_error(
                    "DEADLOCK_RETRY_EXCEEDED",
                    "Hệ thống đang bận khi cài deck này. Vui lòng thử lại sau vài giây.",
                    status=409,
                )
            raise

        return jsonify(install_result.get("response") or {}), 201

    return _api_error(
        "DEADLOCK_RETRY_EXCEEDED",
        "Hệ thống đang bận khi cài deck này. Vui lòng thử lại sau vài giây.",
        status=409,
    )

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
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
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

    review = DeckReview.query.filter_by(deck_item_id=deck_item.id, user_id=current_user.id).first()
    if review is None:
        review = DeckReview(deck_item_id=deck_item.id, user_id=current_user.id, rating=rating, comment=comment)
        db.session.add(review)
    else:
        review.rating = rating
        review.comment = comment

    _recompute_deck_item_market_stats(deck_item)
    _audit("market.deck_item.rate", {"deck_item_id": deck_item.id, "rating": rating})
    db.session.commit()
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

    trending_cutoff = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
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
