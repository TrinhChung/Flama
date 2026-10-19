"""Standalone template marketplace: listing, catalog, preview, receipt and sale.

A listing publishes the template's current content as an immutable release and
buyers receive their own ``market_copy`` through the canonical subscription.
Received copies keep provenance, so they can never be listed or sold again.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy.exc import IntegrityError

from app.repositories import template_marketplace_repository as market
from app.repositories import template_release_repository as releases
from app.services import template_release_service
from app.services.marketplace_query_service import _format_marketplace_price_display, normalize_pricing
from app.services.template_release_service import TemplateReleaseError
from models import db
from models.audit_log import AuditLog
from models.template_publication import TemplatePublication

PRODUCT_TYPE = market.PRODUCT_TYPE
STATUSES = {"private", market.LISTED}
LISTING_KEYS = {"marketplace_status", "pricing_mode", "price_amount_minor"}
DEFAULT_PAGE_SIZE = 24
MAX_PAGE_SIZE = 48
SAMPLE_TEXT_TYPES = {"text", "richtext", "markdown", "array"}


class TemplateCheckoutError(Exception):
    """Marketplace failure mapped to the canonical payment service error."""

    def __init__(self, code: str, message: str, *, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value):
    if not isinstance(value, datetime):
        return value
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)).isoformat()


def _received_block(row) -> tuple[str, str] | None:
    if row.get("origin") == "market_copy" or row.get("source_template_id"):
        return "MARKET_TEMPLATE_REPUBLISH_FORBIDDEN", "Giao diện thẻ tải từ chợ không thể đăng hoặc bán lại."
    return None


def _publish_block(row) -> tuple[str, str] | None:
    blocked = _received_block(row)
    if blocked:
        return blocked
    if row.get("archived_at") is not None:
        return "TEMPLATE_ARCHIVED", "Giao diện thẻ đã lưu trữ không thể đăng lên chợ."
    return None


def _missing_requirements(row) -> list[str]:
    return [key for key in ("description", "primary_category") if not str(row.get(key) or "").strip()]


def _is_listed(row) -> bool:
    return bool(
        row.get("marketplace_status") == market.LISTED and row.get("current_release_id")
        and row.get("archived_at") is None and _received_block(row) is None
    )


def _owned(user_id, template_id, *, lock=False):
    row = releases.template(db.session, template_id, lock=lock)
    if row is None or releases.template_owner(db.session, row) != int(user_id):
        raise TemplateReleaseError("TEMPLATE_NOT_FOUND", "Template not found.", status=404)
    return row


def _inputs(schema) -> list[dict[str, Any]]:
    return [
        {"key": item.get("key"), "label": item.get("label") or item.get("key"), "type": item.get("type", "text")}
        for item in (schema or []) if isinstance(item, dict) and item.get("key")
    ]


def _serialize_item(row, *, user_id, received, purchased) -> dict[str, Any]:
    inputs = _inputs(row.get("release_input_schema"))
    mode = row.get("pricing_mode") or "free"
    price = int(row.get("price_amount_minor") or 0)
    return {
        "id": row["id"], "name": row["name"], "description": row.get("description") or "",
        "primary_category": row.get("primary_category") or None,
        "pricing_mode": mode, "price_amount_minor": price, "price_display": _format_marketplace_price_display(mode, price),
        "install_count": int(row.get("install_count") or 0),
        "published_at": _iso(row.get("marketplace_published_at")),
        "version_label": row.get("version_label"), "release_published_at": _iso(row.get("release_published_at")),
        "inputs": inputs, "input_count": len(inputs),
        "author": {"id": row["owner_user_id"], "username": row.get("author_username")},
        "is_owner": row["owner_user_id"] == int(user_id),
        "is_installed": row["id"] in received, "installed_template_id": received.get(row["id"]),
        "is_purchased": row["id"] in purchased,
        "is_listed": _is_listed(row),
    }


def _page_arg(args, key, default, maximum):
    raw = args.get(key)
    if raw in (None, ""):
        return default
    text = str(raw)
    if len(text) > 10 or not text.isascii() or not text.isdigit() or int(text) < 1:
        raise TemplateReleaseError("VALIDATION_ERROR", f"{key} must be a positive integer.", field=key)
    return min(int(text), maximum)


def list_catalog(*, user_id: int, args) -> dict[str, Any]:
    sort = str(args.get("sort") or "newest").strip().lower()
    pricing_mode = str(args.get("pricing_mode") or "").strip().lower()
    page = _page_arg(args, "page", 1, 2_147_483_647)
    page_size = _page_arg(args, "page_size", DEFAULT_PAGE_SIZE, MAX_PAGE_SIZE)
    rows, total = market.catalog(
        db.session,
        search=str(args.get("q") or "").strip()[:100] or None,
        category=str(args.get("category") or "").strip()[:120] or None,
        pricing_mode=pricing_mode if pricing_mode in {"free", "paid"} else None,
        sort=sort if sort in market.SORTS else "newest",
        page=page, page_size=page_size,
    )
    ids = [row["id"] for row in rows]
    received = market.received(db.session, user_id=user_id, source_template_ids=ids)
    purchased = market.purchased(db.session, user_id=user_id, template_ids=ids)
    return {
        "items": [_serialize_item(row, user_id=user_id, received=received, purchased=purchased) for row in rows],
        "categories": market.categories(db.session),
        "pagination": {"page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total},
    }


def _visible_item(user_id, template_id):
    """Listed items are public; owners and past recipients still see delisted ones."""
    row = market.item(db.session, template_id)
    if row is None or _received_block(row):
        raise TemplateReleaseError("TEMPLATE_NOT_FOUND", "Không tìm thấy giao diện thẻ trên chợ.", status=404)
    received = market.received(db.session, user_id=user_id, source_template_ids=[row["id"]])
    purchased = market.purchased(db.session, user_id=user_id, template_ids=[row["id"]])
    if not (_is_listed(row) or row["owner_user_id"] == int(user_id) or received or purchased):
        raise TemplateReleaseError("TEMPLATE_NOT_FOUND", "Không tìm thấy giao diện thẻ trên chợ.", status=404)
    return row, received, purchased


def get_catalog_item(*, user_id: int, template_id: str) -> dict[str, Any]:
    row, received, purchased = _visible_item(user_id, template_id)
    payload = _serialize_item(row, user_id=user_id, received=received, purchased=purchased)
    payload["release_change_note"] = row.get("release_change_note")
    payload["updated_at"] = _iso(row.get("updated_at"))
    payload["recent_releases"] = [
        {**item, "published_at": _iso(item.get("published_at"))}
        for item in market.recent_releases(db.session, row["id"])
    ]
    return payload


def preview_catalog_item(*, user_id: int, template_id: str) -> dict[str, Any]:
    """Render the released content (what buyers receive) with input labels as sample data."""
    from app.services.flashcard_content_service import ContentApiError, preview_raw_template

    row, _, _ = _visible_item(user_id, template_id)
    content = releases.version(db.session, row["release_version_id"], row["id"]) if row.get("release_version_id") else None
    if content is None:
        if row["owner_user_id"] != int(user_id):
            raise TemplateReleaseError("TEMPLATE_RELEASE_NOT_READY", "Giao diện thẻ chưa có bản phát hành.", status=409)
        content = releases.template(db.session, row["id"])  # an owner previews the draft before listing
    schema = _inputs(content.get("input_schema"))
    try:
        return preview_raw_template(payload={
            "front_html": content.get("front_html") or "", "back_html": content.get("back_html") or "",
            "shared_css": content.get("shared_css") or "",
            "fields": [{"name": item["key"], "field_type": item["type"]} for item in schema],
            "field_values": {item["key"]: item["label"] for item in schema if item["type"] in SAMPLE_TEXT_TYPES},
        })
    except ContentApiError as exc:
        raise TemplateReleaseError(exc.error, exc.message, status=exc.status, field=exc.field) from exc


def get_listing(*, user_id: int, template_id: str) -> dict[str, Any]:
    row = _owned(user_id, template_id)
    publication = releases.publication(db.session, row["id"]) or {}
    head = releases.release(db.session, publication["current_release_id"], row["id"]) if publication.get("current_release_id") else None
    blocked = _publish_block(row)
    mode = publication.get("pricing_mode") or "free"
    price = int(publication.get("price_amount_minor") or 0)
    install_count = (market.item(db.session, row["id"]) or {}).get("install_count", 0)
    return {
        "template_id": row["id"],
        "can_publish": blocked is None, "block_code": blocked[0] if blocked else None,
        "block_reason": blocked[1] if blocked else None,
        "missing_requirements": _missing_requirements(row),
        "marketplace_status": publication.get("marketplace_status") or "private",
        "pricing_mode": mode, "price_amount_minor": price, "price_display": _format_marketplace_price_display(mode, price),
        "published_at": _iso(publication.get("marketplace_published_at")),
        "current_release": {key: _iso(head[key]) for key in ("id", "version_label", "published_at")} if head else None,
        "has_unpublished_changes": head is None or head["version_id"] != row.get("current_version_id"),
        "install_count": int(install_count or 0),
    }


def update_listing(*, user_id: int, template_id: str, payload) -> dict[str, Any]:
    """Publish, reprice or delist an authored template; listing also releases its content."""
    if not isinstance(payload, dict) or set(payload) - LISTING_KEYS:
        raise TemplateReleaseError("VALIDATION_ERROR", "Request body contains unsupported properties.")
    status = payload.get("marketplace_status")
    if status is not None and status not in STATUSES:
        raise TemplateReleaseError("VALIDATION_ERROR", "marketplace_status must be 'private' or 'published'.", field="marketplace_status")

    def operation():
        row = _owned(user_id, template_id, lock=True)
        blocked = _received_block(row)
        if blocked:
            raise TemplateReleaseError(blocked[0], blocked[1], status=403)
        publication = releases.ensure_publication(db.session, row["id"])
        target = status or publication["marketplace_status"] or "private"
        mode, price, error = normalize_pricing(
            payload, current_mode=publication["pricing_mode"] or "free",
            current_price_amount_minor=int(publication["price_amount_minor"] or 0),
        )
        if error:
            raise TemplateReleaseError("VALIDATION_ERROR", error, field="price_amount_minor")
        values = {"marketplace_status": target, "pricing_mode": mode, "price_amount_minor": price, "updated_at": _now()}
        if target == market.LISTED:
            blocked = _publish_block(row)
            if blocked:
                raise TemplateReleaseError(blocked[0], blocked[1], status=409)
            missing = _missing_requirements(row)
            if missing:
                raise TemplateReleaseError("VALIDATION_ERROR", f"{missing[0]} is required to publish.", field=missing[0])
            template_release_service.stage_marketplace_release(db.session, row, actor_user_id=user_id)
            if publication["marketplace_status"] != market.LISTED:
                values["marketplace_published_at"] = _now()
        releases.update_row(db.session, TemplatePublication, [TemplatePublication.template_id == row["id"]], values)
        db.session.add(AuditLog(user_id=user_id, action="template.marketplace", payload={
            "template_id": row["id"], "marketplace_status": target, "pricing_mode": mode, "price_amount_minor": price,
        }))

    try:
        operation()
        db.session.commit()
    except Exception:
        db.session.rollback()
        raise
    return get_listing(user_id=user_id, template_id=template_id)


def install(*, user_id: int, template_id: str, return_url: str | None = None, cancel_url: str | None = None):
    from app.services import payment

    row = market.item(db.session, template_id)
    if row is None or _received_block(row):
        raise TemplateReleaseError("TEMPLATE_NOT_FOUND", "Không tìm thấy giao diện thẻ trên chợ.", status=404)
    if row["owner_user_id"] == int(user_id):
        raise TemplateReleaseError("OWN_TEMPLATE", "Bạn không thể tải giao diện thẻ của chính mình.", status=409)
    existing = existing_access(user_id=user_id, template_id=row["id"])
    if existing:
        return existing, 200
    entitled = market.active_entitlement(db.session, user_id=user_id, template_id=row["id"])
    if not _is_listed(row) and not entitled:
        raise TemplateReleaseError("TEMPLATE_NOT_LISTED", "Giao diện thẻ này hiện không còn trên chợ.", status=409)
    if row.get("pricing_mode") == "paid" and not entitled:
        if not payment.paid_install_interception_enabled():
            raise TemplateReleaseError(
                "PAYMENT_UNAVAILABLE",
                "Thanh toán cho nội dung trả phí chưa được bật trong môi trường này. Vui lòng thử lại sau.",
                status=503,
            )
        try:
            checkout = payment.prepare_checkout_for_product(
                user_id=user_id, product_type=PRODUCT_TYPE, product_ref_id=row["id"],
                return_url=return_url, cancel_url=cancel_url,
            )
        except payment.PaymentServiceError as exc:
            raise TemplateReleaseError(exc.error, exc.message, status=exc.status, field=exc.field) from exc
        return checkout, 202 if checkout.get("payment_required") else 200
    try:
        subscription = template_release_service.ensure_subscription(db.session, user_id=user_id, source_template_id=row["id"])
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        concurrent = existing_access(user_id=user_id, template_id=row["id"])
        if concurrent is None:
            raise
        return concurrent, 200
    except Exception:
        db.session.rollback()
        raise
    return {"source_template_id": row["id"], "local_template_id": subscription["local_template_id"], "already_installed": False}, 201


# Payment integration: the checkout, fulfillment and wallet modules call these.

def existing_access(*, user_id: int, template_id: str) -> dict[str, Any] | None:
    subscription = releases.subscription(db.session, user_id=user_id, source_template_id=str(template_id))
    if subscription is None:
        return None
    return {"already_installed": True, "source_template_id": str(template_id), "local_template_id": subscription["local_template_id"]}


def checkout_context(*, template_id: str, user_id: int) -> dict[str, Any]:
    row = market.item(db.session, template_id)
    if row is None or _received_block(row):
        raise TemplateCheckoutError("FIELD_NOT_FOUND", "Không tìm thấy giao diện thẻ cần thanh toán.", status=404)
    if not _is_listed(row):
        raise TemplateCheckoutError("VALIDATION_ERROR", "Giao diện thẻ này hiện không mở bán hoặc không còn khả dụng để thanh toán.", status=409)
    if row["owner_user_id"] == int(user_id):
        raise TemplateCheckoutError("VALIDATION_ERROR", "Bạn không thể mua giao diện thẻ do chính mình đăng.", status=409)
    price = int(row.get("price_amount_minor") or 0)
    if row.get("pricing_mode") != "paid" or price <= 0:
        raise TemplateCheckoutError("PAYMENT_NOT_REQUIRED", "Giao diện thẻ này hiện không yêu cầu thanh toán.", status=409)
    return {
        "product_type": PRODUCT_TYPE, "product_ref_id": row["id"], "title_snapshot": row["name"],
        "amount_minor": price, "subtotal_amount_minor": price, "discount_amount_minor": 0,
        "product_snapshot": {
            "title": row["name"], "pricing_mode": "paid", "source_price_amount_minor": price,
            "source_price_integer": price, "version": row.get("version_label"),
            "release_id": row.get("current_release_id"), "owner_user_id": row["owner_user_id"],
        },
        "existing_access": existing_access(user_id=user_id, template_id=row["id"]),
    }


def fulfill_purchase(*, user_id: int, template_id: str) -> dict[str, Any]:
    if releases.template(db.session, template_id) is None:
        raise TemplateCheckoutError("FIELD_NOT_FOUND", "Giao diện thẻ đã thanh toán không còn tồn tại để cấp quyền.", status=404)
    try:
        subscription = template_release_service.ensure_subscription(
            db.session, user_id=user_id, source_template_id=str(template_id), access_granted=True,
        )
    except TemplateReleaseError as exc:
        raise TemplateCheckoutError(exc.code, str(exc), status=exc.status) from exc
    return {"source_template_id": str(template_id), "local_template_id": subscription["local_template_id"]}


def seller_user_id(template_id: str) -> int | None:
    row = releases.template(db.session, template_id)
    return row.get("owner_user_id") if row else None


def seller_label(template_id: str) -> str:
    row = market.item(db.session, template_id)
    return str((row or {}).get("author_username") or "")
