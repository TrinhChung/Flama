"""Application service for marketplace shared note types and shared templates."""

from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from typing import Any

from sqlalchemy.exc import IntegrityError

from models import db
from models.flashcard import AuditLog
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note_type_review import NoteTypeReview
from models.template import Template

from app.services import (
    flashcards_share_service,
    marketplace_hub_service,
    marketplace_query_service,
    payment_service,
)
from app.repositories import flashcards_share_repository, template_release_repository
from app.services.flashcard_renderer import (
    PREVIEW_MEDIA_AUDIO_TOKEN,
    PREVIEW_MEDIA_DIAGRAM_TOKEN,
    PREVIEW_MEDIA_IMAGE_TOKEN,
    TemplateCompileError,
    render_template_pair,
)

UTC = timezone.utc
PUBLISH_STATUSES_VISIBLE = {"published", "unlisted"}
MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER = 2


class MarketplaceNoteTypeError(Exception):
    """Business logic error for marketplace note types."""

    def __init__(
        self,
        error: str,
        message: str,
        status: int = 400,
        field: str | None = None,
    ):
        super().__init__(message)
        self.error = error
        self.message = message
        self.status = status
        self.field = field


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _get_shared_note_type_for_view(note_type_id: str, user_id: int) -> NoteType | None:
    note_type = db.session.get(NoteType, note_type_id)
    if not note_type:
        return None

    status = str(note_type.publish_status or "").strip().lower()
    is_owner = note_type.user_id == user_id
    if status in ("private", "archived") and not is_owner:
        return None
    return note_type


def _is_note_type_visible_for_shared(note_type: NoteType, user_id: int) -> bool:
    status = str(note_type.publish_status or "").strip().lower()
    if status in PUBLISH_STATUSES_VISIBLE:
        return True
    return note_type.user_id == user_id


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


def _build_preview_sample_values(field_defs: list[Any]) -> dict[str, Any]:
    sample_values: dict[str, Any] = {}
    for field_def in field_defs:
        if field_def.field_type == "image":
            sample_values[field_def.name] = PREVIEW_MEDIA_IMAGE_TOKEN
        elif field_def.field_type == "audio":
            sample_values[field_def.name] = PREVIEW_MEDIA_AUDIO_TOKEN
        elif field_def.field_type == "diagram":
            sample_values[field_def.name] = PREVIEW_MEDIA_DIAGRAM_TOKEN
        else:
            sample_values[field_def.name] = field_def.name
    return sample_values


def get_note_types_hub(
    *,
    user_id: int,
    args: Any,
    compact: bool = False,
) -> dict[str, Any]:
    """Build the marketplace hub for shared note types."""
    filters = marketplace_hub_service.parse_marketplace_filters(args)
    return marketplace_hub_service.build_note_type_marketplace_hub(
        user_id=user_id,
        filters=filters,
        compact=compact,
    )


def list_shared_note_types(
    *,
    user_id: int,
    args: Any,
) -> dict[str, Any]:
    """List and filter shared note types in marketplace."""
    query_text = (args.get("q") or "").strip()
    category = (args.get("category") or "").strip()
    tags = {
        item.lower()
        for item in marketplace_query_service.normalize_marketplace_tags(
            args.get("tags")
        )
    }
    pricing_mode = (
        (args.get("pricing_mode") or args.get("pricing") or "")
        .strip()
        .lower()
    )
    sort_key = (args.get("sort") or "popular").strip().lower()
    min_price_amount_minor = (
        marketplace_query_service.parse_query_price_amount_minor(
            args.get("min_price")
        )
    )
    max_price_amount_minor = (
        marketplace_query_service.parse_query_price_amount_minor(
            args.get("max_price")
        )
    )
    domain = (args.get("domain") or "").strip()
    subject = (args.get("subject") or "").strip()
    framework = (args.get("framework") or "").strip()
    framework_level = (args.get("framework_level") or "").strip()
    difficulty_band = (args.get("difficulty_band") or args.get("level") or "").strip()
    learning_goals = {
        item.lower()
        for item in marketplace_query_service.normalize_marketplace_tags(
            args.get("learning_goals") or args.get("goal") or args.get("goals")
        )
    }
    primary_topics = {
        item.lower()
        for item in marketplace_query_service.normalize_marketplace_tags(
            args.get("primary_topics") or args.get("topic") or args.get("topics")
        )
    }
    format_features = {
        item.lower()
        for item in marketplace_query_service.normalize_marketplace_tags(
            args.get("format_features") or args.get("feature") or args.get("features")
        )
    }

    visible_note_types = [
        item
        for item in NoteType.query.order_by(NoteType.updated_at.desc()).all()
        if _is_note_type_visible_for_shared(item, user_id)
    ]
    filtered = marketplace_query_service.filter_note_type_items(
        visible_note_types,
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
    sorted_items = marketplace_query_service.sort_note_type_items(
        filtered, sort_key
    )

    installs = NoteTypeInstall.query.filter_by(user_id=user_id).all()
    install_map = {row.source_note_type_id: row for row in installs}
    payload_items = []
    for note_type in sorted_items:
        row = marketplace_query_service.serialize_note_type_marketplace_card(
            note_type
        )
        install = install_map.get(note_type.id)
        row["is_installed"] = install is not None
        row["installed_note_type_id"] = (
            install.installed_note_type_id if install else None
        )
        row["is_owner"] = note_type.user_id == user_id
        payload_items.append(row)

    return {"items": payload_items}


def get_shared_note_type_detail(
    *,
    user_id: int,
    note_type_id: str,
) -> dict[str, Any]:
    """Get detail information for a shared note type."""
    note_type = _get_shared_note_type_for_view(note_type_id, user_id)
    if not note_type:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Note type not found.", status=404
        )

    install = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id,
        user_id=user_id,
    ).first()
    review = NoteTypeReview.query.filter_by(
        note_type_id=note_type.id, user_id=user_id
    ).first()
    review_submission_count = _count_user_market_review_submissions(
        user_id=user_id,
        action="market.note_type.rate",
        payload_item_key="note_type_id",
        payload_item_value=note_type.id,
    )
    review_submissions_remaining = max(
        0,
        MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER - int(review_submission_count or 0),
    )
    payload = marketplace_query_service.serialize_note_type_marketplace_card(
        note_type
    )
    payload["is_installed"] = install is not None
    payload["installed_note_type_id"] = (
        install.installed_note_type_id if install else None
    )
    payload["is_owner"] = note_type.user_id == user_id
    payload["can_rate"] = (
        flashcards_share_service.can_user_rate_note_type(
            note_type, user_id=user_id
        )
        and review_submissions_remaining > 0
    )
    payload["review_submission_count"] = review_submission_count
    payload["review_submissions_remaining"] = review_submissions_remaining
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": (
                review.updated_at.isoformat() if review.updated_at else None
            ),
        }
        if review
        else None
    )
    payload.update(
        marketplace_hub_service.build_note_type_detail_extras(
            note_type=note_type,
            user_id=user_id,
        )
    )
    return payload


def save_shared_note_type(
    *,
    user_id: int,
    note_type_id: str,
    is_save: bool,
) -> dict[str, Any]:
    """Bookmark/save or remove bookmark for a shared note type."""
    note_type = _get_shared_note_type_for_view(note_type_id, user_id)
    if not note_type:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Note type not found.", status=404
        )
    if note_type.user_id == user_id:
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR", "Owner cannot save own note type.", status=409
        )

    if is_save:
        marketplace_hub_service.save_item_for_user(
            user_id=user_id,
            product_type="note_type",
            product_ref_id=note_type.id,
        )
        db.session.commit()
        return {"saved": True, "note_type_id": note_type.id}

    marketplace_hub_service.remove_saved_item_for_user(
        user_id=user_id,
        product_type="note_type",
        product_ref_id=note_type.id,
    )
    db.session.commit()
    return {"saved": False, "note_type_id": note_type.id}


def publish_note_type(
    *,
    user_id: int,
    is_admin: bool,
    note_type_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    """Publish or update publish settings for a note type."""
    note_type = db.session.get(NoteType, note_type_id)
    if not note_type or (note_type.user_id != user_id and not is_admin):
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Note type not found.", status=404
        )

    eligibility = flashcards_share_service.get_note_type_publish_eligibility(
        note_type=note_type,
        user_id=user_id,
        is_admin=is_admin,
    )
    if not eligibility["is_selectable"]:
        raise MarketplaceNoteTypeError(
            "CONFLICT",
            str(eligibility["block_reason"]),
            status=409,
            field="source_note_type_id",
        )

    payload.setdefault("publish_status", "published")
    validation_error = flashcards_share_service.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        raise MarketplaceNoteTypeError("VALIDATION_ERROR", validation_error)

    flashcards_share_service.recompute_note_type_market_stats(note_type)
    db.session.add(
        AuditLog(
            user_id=user_id,
            action="note_type.publish",
            payload={"note_type_id": note_type.id, "publish_status": note_type.publish_status},
        )
    )

    db.session.commit()
    return marketplace_query_service.serialize_note_type(note_type)


def preview_shared_note_type_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
) -> dict[str, Any]:
    """Compile and render preview HTML pair for a shared note type template."""
    note_type = _get_shared_note_type_for_view(note_type_id, user_id)
    if not note_type:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Note type not found.", status=404
        )

    attached = flashcards_share_repository.get_template_applications_by_note_type(note_type.id)
    application = next((app for template, app in attached if template.id == template_id), None)
    template = next((template for template, _app in attached if template.id == template_id), None)
    if template is None:
        template = next((row for row in flashcards_share_repository.get_templates_by_note_type(note_type.id) if row.id == template_id), None)
    if not template:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Template not found.", status=404
        )

    sample_field_values = _build_preview_sample_values(note_type.field_defs)
    publication = template_release_repository.publication(db.session, template.id)
    release = template_release_repository.release(db.session, publication["current_release_id"], template.id) if publication and publication["current_release_id"] else None
    content = template_release_repository.version(db.session, release["version_id"], template.id) if release else None
    preview_template = SimpleNamespace(
        id=template.id, input_bindings=application.input_bindings if application else None,
        input_schema=content["input_schema"] if content else template.input_schema,
        front_html=content["front_html"] if content else template.front_html,
        back_html=content["back_html"] if content else template.back_html,
        shared_css=content["shared_css"] if content else template.shared_css,
    )

    try:
        rendered = render_template_pair(
            template=preview_template,
            field_defs=note_type.field_defs,
            field_values=sample_field_values,
            media_assets=[],
            preview_note_key=f"shared-preview:{note_type.id}",
        )
    except TemplateCompileError as exc:
        raise MarketplaceNoteTypeError(
            "TEMPLATE_COMPILE_ERROR", str(exc), field="front_html"
        ) from exc

    return rendered


def install_shared_note_type(
    *,
    user_id: int,
    note_type_id: str,
    return_url: str | None = None,
    cancel_url: str | None = None,
) -> tuple[dict[str, Any], int]:
    """Install a shared note type into current user account."""
    source_note_type = db.session.get(NoteType, note_type_id)
    if not source_note_type:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Note type not found.", status=404
        )
    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in PUBLISH_STATUSES_VISIBLE:
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR",
            "This note type is not available for install.",
            status=409,
        )
    if source_note_type.user_id == user_id:
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR", "Owner cannot install own note type.", status=409
        )

    existing = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=user_id,
    ).first()
    if existing:
        return (
            {
                "installed_note_type_id": existing.installed_note_type_id,
                "source_note_type_id": source_note_type.id,
                "already_installed": True,
            },
            200,
        )

    if source_note_type.pricing_mode == "paid":
        if not payment_service.paid_install_interception_enabled():
            raise MarketplaceNoteTypeError(
                "PAYMENT_UNAVAILABLE",
                "Thanh toán cho nội dung trả phí chưa được bật trong môi trường này. Vui lòng thử lại sau.",
                status=503,
            )
        try:
            checkout = payment_service.prepare_checkout_for_product(
                user_id=user_id,
                product_type="note_type",
                product_ref_id=source_note_type.id,
                return_url=return_url,
                cancel_url=cancel_url,
            )
        except payment_service.PaymentServiceError as exc:
            raise MarketplaceNoteTypeError(
                exc.error,
                exc.message,
                status=exc.status,
                field=exc.field,
            ) from exc
        status_code = 202 if checkout.get("payment_required") else 200
        return checkout, status_code

    try:
        installed_copy, purchase_amount_minor = (
            flashcards_share_service.install_shared_note_type(
                source_note_type=source_note_type,
                user_id=user_id,
            )
        )
    except IntegrityError:
        db.session.rollback()
        concurrent_install = NoteTypeInstall.query.filter_by(
            source_note_type_id=note_type_id,
            user_id=user_id,
        ).first()
        if concurrent_install is None:
            raise
        return (
            {
                "installed_note_type_id": concurrent_install.installed_note_type_id,
                "source_note_type_id": note_type_id,
                "already_installed": True,
            },
            200,
        )
    if installed_copy is None:
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR", "Unable to install note type.", status=500
        )
    db.session.commit()
    return (
        {
            "installed_note_type_id": installed_copy.id,
            "source_note_type_id": source_note_type.id,
            "purchase_amount_minor": purchase_amount_minor,
            "purchase_price_cents": purchase_amount_minor,
        },
        201,
    )


def rate_shared_note_type(
    *,
    user_id: int,
    note_type_id: str,
    rating: int,
    comment: str | None = None,
) -> dict[str, Any]:
    """Rate a shared note type."""
    note_type = db.session.get(NoteType, note_type_id)
    if not note_type:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Note type not found.", status=404
        )
    if not flashcards_share_service.can_user_rate_note_type(
        note_type, user_id=user_id
    ):
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR", "You can only rate after real usage.", status=403
        )
    review_submission_count = _count_user_market_review_submissions(
        user_id=user_id,
        action="market.note_type.rate",
        payload_item_key="note_type_id",
        payload_item_value=note_type.id,
    )
    if review_submission_count >= MAX_MARKET_REVIEW_SUBMISSIONS_PER_USER:
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR",
            "You can submit at most 2 ratings for this item.",
            status=403,
        )

    if rating < 1 or rating > 5:
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR", "rating must be between 1 and 5.", field="rating"
        )
    clean_comment = (comment or "").strip() or None

    flashcards_share_service.rate_shared_note_type(
        note_type=note_type,
        user_id=user_id,
        rating=rating,
        comment=clean_comment,
    )
    db.session.commit()
    return {
        "note_type_id": note_type.id,
        "rating_avg": note_type.rating_avg,
        "rating_count": note_type.rating_count,
        "my_rating": rating,
    }


def get_recommendations(*, user_id: int) -> dict[str, Any]:
    """Get recommended shared note types."""
    visible_items = [
        item
        for item in NoteType.query.all()
        if _is_note_type_visible_for_shared(item, user_id)
    ]
    return marketplace_query_service.get_note_type_recommendations(
        user_id=user_id,
        visible_items=visible_items,
    )

