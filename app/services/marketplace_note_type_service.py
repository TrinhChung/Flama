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
from models.template_subscription import TemplateSubscription

from app.services import (
    flashcards_share_service,
    marketplace_hub_service,
    marketplace_query_service,
    payment,
    template_release_service,
)
from app.repositories import flashcards_share_repository, template_release_repository
from app.repositories.marketplace_list_repository import ordered_items_query, visible_items_query
from app.services.marketplace_list_service import enabled_arg, has_inferred_filters, list_page, pagination
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

    page = list_page(args)
    compact = enabled_arg(args.get("compact"))
    query = visible_items_query(
        NoteType, user_id=user_id, owner_column=NoteType.user_id,
    )
    query = ordered_items_query(query, NoteType, sort_key)
    filters = dict(
        query_text=query_text, category=category, tags=tags,
        pricing_mode="", min_price_amount_minor=None,
        max_price_amount_minor=None, domain=domain,
        subject=subject, framework=framework, framework_level=framework_level,
        difficulty_band=difficulty_band, learning_goals=learning_goals,
        primary_topics=primary_topics, format_features=format_features,
    )
    has_price_filter = pricing_mode in {"free", "paid"} or min_price_amount_minor is not None or max_price_amount_minor is not None
    if page is not None and not has_inferred_filters(filters) and not has_price_filter:
        total = query.order_by(None).count()
        number, size = page
        offset = (number - 1) * size
        sorted_items = query.offset(offset).limit(size).all() if offset < total else []
    else:
        filtered = marketplace_query_service.filter_note_type_items(query.all(), **filters)
        if has_price_filter:
            from app.services.note_type_bundle_pricing_service import pricing_breakdown
            amounts = {item.id: pricing_breakdown(db.session, note_type=item, user_id=user_id)["total_amount_minor"]
                for item in filtered}
            filtered = [item for item in filtered
                if (pricing_mode not in {"free", "paid"} or (amounts[item.id] > 0) == (pricing_mode == "paid"))
                and (min_price_amount_minor is None or amounts[item.id] >= min_price_amount_minor)
                and (max_price_amount_minor is None or amounts[item.id] <= max_price_amount_minor)]
        sorted_items = marketplace_query_service.sort_note_type_items(filtered, sort_key)
        total = len(sorted_items)
        if page is not None:
            number, size = page
            sorted_items = sorted_items[(number - 1) * size:number * size]

    ids = [item.id for item in sorted_items]
    installs = NoteTypeInstall.query.filter(
        NoteTypeInstall.user_id == user_id,
        NoteTypeInstall.source_note_type_id.in_(ids),
    ).all() if ids else []
    install_map = {row.source_note_type_id: row for row in installs}
    payload_items = []
    for note_type in sorted_items:
        row = marketplace_query_service.serialize_note_type_marketplace_card(
            note_type, include_definition=not compact, user_id=user_id
        )
        install = install_map.get(note_type.id)
        row["is_installed"] = bool(install and install.installed_note_type_id)
        row["installed_note_type_id"] = (
            install.installed_note_type_id if install else None
        )
        row["applied_release_id"] = install.applied_release_id if install else None
        row["legacy_installation"] = bool(install and not install.applied_release_id)
        row["is_owner"] = note_type.user_id == user_id
        payload_items.append(row)

    payload = {"items": payload_items}
    if page is not None:
        payload["pagination"] = pagination(page, total)
    return payload


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
        note_type, user_id=user_id
    )
    payload["is_installed"] = bool(install and install.installed_note_type_id)
    payload["installed_note_type_id"] = (
        install.installed_note_type_id if install else None
    )
    payload["applied_release_id"] = install.applied_release_id if install else None
    payload["legacy_installation"] = bool(install and not install.applied_release_id)
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
    templates = payload.get("templates") or []
    if templates:
        template_ids = [t["id"] for t in templates if "id" in t]
        subscriptions = {
            sub.source_template_id: sub.local_template_id
            for sub in TemplateSubscription.query.filter(
                TemplateSubscription.user_id == user_id,
                TemplateSubscription.source_template_id.in_(template_ids),
            ).all()
        }
        for tmpl in templates:
            tmpl["is_installed"] = tmpl.get("id") in subscriptions and tmpl.get("already_entitled", True)
            tmpl["installed_template_id"] = subscriptions.get(tmpl.get("id"))
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

    payload.setdefault("publish_status", "published")
    going_visible = str(payload.get("publish_status") or "").strip().lower() in PUBLISH_STATUSES_VISIBLE
    eligibility = flashcards_share_service.get_note_type_publish_eligibility(
        note_type=note_type,
        user_id=user_id,
        is_admin=is_admin,
    )
    # A referenced template losing its listing must not trap the author's
    # Note Type on the marketplace: withdrawing it stays possible.
    if not eligibility["is_selectable"] and (going_visible or eligibility["block_code"] != "marketplace_template"):
        raise MarketplaceNoteTypeError(
            "CONFLICT",
            str(eligibility["block_reason"]),
            status=409,
            field="source_note_type_id",
        )

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
    application_id: str | None = None,
) -> dict[str, Any]:
    """Compile and render preview HTML pair for a shared note type template."""
    if application_id is not None and (
        not isinstance(application_id, str) or not application_id.strip() or len(application_id) > 36
    ):
        raise MarketplaceNoteTypeError("VALIDATION_ERROR", "application_id must identify a published application.",
            status=400, field="application_id")
    note_type = _get_shared_note_type_for_view(note_type_id, user_id)
    if not note_type:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Note type not found.", status=404
        )

    from app.services.note_type_release_service import released_definition
    definition = released_definition(db.session, note_type)
    if not definition["release_available"]:
        raise MarketplaceNoteTypeError("NOTE_TYPE_RELEASE_NOT_READY",
            "The author must publish a complete Note Type release before preview is available.", status=409)
    candidates = [row for row in definition["templates"] if row["id"] == template_id]
    if application_id is not None:
        candidates = [row for row in candidates if row["application_id"] == application_id]
    if not candidates:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Template not found.", status=404
        )
    if len(candidates) > 1:
        raise MarketplaceNoteTypeError("APPLICATION_SELECTION_REQUIRED",
            "Choose the published application to preview this template mapping.",
            status=409, field="application_id")
    template = candidates[0]

    fields = [SimpleNamespace(**field) for field in definition["field_defs"]]
    sample_field_values = _build_preview_sample_values(fields)
    preview_template = SimpleNamespace(**template)

    try:
        rendered = render_template_pair(
            template=preview_template,
            field_defs=fields,
            field_values=sample_field_values,
            media_assets=[],
            preview_note_key=f"shared-preview:{note_type.id}:{template['application_id']}",
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
    if source_note_type.user_id == user_id:
        raise MarketplaceNoteTypeError(
            "VALIDATION_ERROR", "Owner cannot install own note type.", status=409
        )

    existing = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=user_id,
    ).first()
    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in PUBLISH_STATUSES_VISIBLE and existing is None:
        raise MarketplaceNoteTypeError("VALIDATION_ERROR", "This note type is not available for install.", status=409)
    # This also closes an obsolete payable quote when acquiring the last paid
    # dependency has made the requested bundle free.
    from app.services.payment.checkout import reconcile_stale_template_quotes
    try:
        reconcile_stale_template_quotes(user_id=user_id)
    except payment.PaymentServiceError as exc:
        raise MarketplaceNoteTypeError(exc.error, exc.message, status=exc.status, field=exc.field) from exc
    if existing and existing.installed_note_type_id and db.session.get(NoteType, existing.installed_note_type_id):
        return (
            {
                "installed_note_type_id": existing.installed_note_type_id,
                "source_note_type_id": source_note_type.id,
                "already_installed": True,
                "applied_release_id": existing.applied_release_id,
                "legacy_installation": not bool(existing.applied_release_id),
            },
            200,
        )

    from app.services.note_type_release_service import current_release, NoteTypeReleaseError
    from app.repositories import note_type_release_repository
    if existing and not existing.applied_release_id:
        raise MarketplaceNoteTypeError("NOTE_TYPE_LEGACY_RELEASE_UNKNOWN",
            "This legacy installation has no recorded historical release to restore.", status=409)
    target_release = (note_type_release_repository.release(db.session, existing.applied_release_id, source_note_type.id)
        if existing else current_release(db.session, source_note_type))
    if target_release is None:
        raise MarketplaceNoteTypeError("NOTE_TYPE_RELEASE_NOT_READY",
            "The author must publish a complete Note Type release before it can be installed.", status=409)

    from app.services.note_type_bundle_pricing_service import pricing_breakdown, require_available
    try:
        breakdown = pricing_breakdown(db.session, note_type=source_note_type, user_id=user_id, release=target_release)
        require_available(breakdown)
    except NoteTypeReleaseError as exc:
        raise MarketplaceNoteTypeError(exc.code, exc.message, status=exc.status) from exc
    if breakdown["payment_required"] and existing is None:
        if not payment.paid_install_interception_enabled():
            raise MarketplaceNoteTypeError(
                "PAYMENT_UNAVAILABLE",
                "Thanh toán cho nội dung trả phí chưa được bật trong môi trường này. Vui lòng thử lại sau.",
                status=503,
            )
        try:
            checkout = payment.prepare_checkout_for_product(
                user_id=user_id,
                product_type="note_type",
                product_ref_id=source_note_type.id,
                return_url=return_url,
                cancel_url=cancel_url,
            )
        except payment.PaymentServiceError as exc:
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
    except NoteTypeReleaseError as exc:
        db.session.rollback()
        raise MarketplaceNoteTypeError(exc.code, exc.message, status=exc.status) from exc
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
    installation = NoteTypeInstall.query.filter_by(source_note_type_id=source_note_type.id, user_id=user_id).one()
    from app.services.payment.checkout import reconcile_template_quotes_after_grant
    quote_reconciliation = reconcile_template_quotes_after_grant(user_id=user_id)
    return (
        {
            "installed_note_type_id": installed_copy.id,
            "source_note_type_id": source_note_type.id,
            "purchase_amount_minor": purchase_amount_minor,
            "purchase_price_cents": purchase_amount_minor,
            "applied_release_id": installation.applied_release_id,
            "legacy_installation": not bool(installation.applied_release_id),
            **quote_reconciliation,
        },
        201,
    )


def install_shared_note_type_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
    return_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    """Install an individual template from a shared note type into current user account."""
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
            "VALIDATION_ERROR", "Owner cannot install own template.", status=409
        )

    from app.services.note_type_release_service import current_release
    release = current_release(db.session, source_note_type)
    if release is None:
        raise MarketplaceNoteTypeError("NOTE_TYPE_RELEASE_NOT_READY",
            "The author must publish a complete Note Type release before it can be installed.", status=409)
    application = next((row for row in release.manifest_json["applications"] if row["template_id"] == template_id), None)
    if not application:
        raise MarketplaceNoteTypeError(
            "FIELD_NOT_FOUND", "Template not found in this note type.", status=404
        )

    existing = template_release_repository.subscription(
        db.session,
        user_id=user_id,
        source_template_id=template_id,
    )
    from app.services.note_type_bundle_pricing_service import has_template_access
    if existing and has_template_access(db.session, user_id=user_id, template_id=template_id):
        return {
            "local_template_id": existing["local_template_id"],
            "source_template_id": template_id,
            "already_installed": True,
        }

    # An individual download follows the original template's listing and
    # license, independently from the price/visibility of its containing bundle.
    from app.services import template_marketplace_service
    source = db.session.get(Template, template_id)
    if source and source.owner_user_id == user_id:
        return {"local_template_id": source.id, "source_template_id": source.id, "already_installed": True}
    try:
        response, _status = template_marketplace_service.install(user_id=user_id, template_id=template_id,
            return_url=return_url, cancel_url=cancel_url)
        return response
    except template_release_service.TemplateReleaseError as exc:
        raise MarketplaceNoteTypeError(exc.code, str(exc), status=exc.status, field=exc.field) from exc


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

