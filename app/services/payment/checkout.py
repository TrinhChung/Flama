"""Checkout session validation, order persistence, and PayOS provider link generation."""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any

from app.repositories import payment_repository
from app.services import support_donation_service
from app.services.share.constants import DEFAULT_VISIBLE_PUBLISH_STATUSES
from app.services.payment import config as payment_config
from app.services.payment.provider import payos_provider
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.payment_attempt import PaymentAttempt
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.user import User

from app.services.payment.base import (
    PAYMENT_PROVIDER_CODE,
    PAYMENT_METHOD_CODE,
    PAYOS_PROVIDER_REUSABLE_STATUSES,
    ACTIVE_ATTEMPT_STATUSES,
    DEFAULT_ORDER_EXPIRY_SECONDS,
    PaymentServiceError,
    _clean_text,
    _iso,
    _require_payments_enabled,
    _require_supported_provider,
    _utcnow,
)
from app.services.payment.orders import (
    _append_payment_context,
    _build_merchant_order_code,
    _build_payment_reference,
    _build_provider_order_code,
    _latest_attempt,
    _maybe_expire_order,
    serialize_order,
)

def _validate_note_type_for_checkout(source_note_type: NoteType, *, user_id: int) -> dict[str, Any]:
    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in DEFAULT_VISIBLE_PUBLISH_STATUSES:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Note Type này hiện không mở bán hoặc không còn khả dụng để thanh toán.",
            status=409,
        )
    if source_note_type.user_id == user_id:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Bạn không thể mua Note Type do chính mình phát hành.",
            status=409,
        )
    existing = payment_repository.get_note_type_install(
        user_id=user_id,
        source_note_type_id=source_note_type.id,
    )
    from app.services.note_type_release_service import current_release
    release = current_release(db.session, source_note_type)
    existing_access = _resolve_existing_access_for_product(product_type="note_type",
        product_ref_id=source_note_type.id, user_id=user_id) if existing else None
    if release is None and existing_access is None:
        raise PaymentServiceError("NOTE_TYPE_RELEASE_NOT_READY",
            "The author must publish a complete Note Type release before purchase.", status=409)
    from app.services.note_type_bundle_pricing_service import (
        order_items_for_bundle, pricing_breakdown, require_available,
    )
    from app.services.note_type_release_service import NoteTypeReleaseError
    try:
        breakdown = pricing_breakdown(db.session, note_type=source_note_type, user_id=user_id, release=release)
        if existing_access is None:
            require_available(breakdown)
            if not breakdown["payment_required"]:
                raise PaymentServiceError("PAYMENT_NOT_REQUIRED", "Gói này hiện không yêu cầu thanh toán.", status=409)
    except NoteTypeReleaseError as exc:
        raise PaymentServiceError(exc.code, exc.message, status=exc.status) from exc
    # Existing legacy access remains usable without inventing a release. No
    # payable order is created when existing_access is present.
    title = release.manifest_json["metadata"]["name"] if release else source_note_type.name
    return {
        "product_type": "note_type",
        "product_ref_id": source_note_type.id,
        "title_snapshot": title,
        "amount_minor": breakdown["total_amount_minor"],
        "subtotal_amount_minor": breakdown["total_amount_minor"],
        "discount_amount_minor": 0,
        "product_snapshot": {
            "title": title,
            "pricing_mode": source_note_type.pricing_mode,
            "source_price_amount_minor": int(source_note_type.price_amount_minor or 0),
            "source_price_integer": int(source_note_type.price_amount_minor or 0),
            "version": release.version_label if release else source_note_type.version,
            "note_type_release_id": release.id if release else None,
            "owner_user_id": source_note_type.user_id,
        },
        "existing_access": existing_access,
        "order_items": order_items_for_bundle(note_type=source_note_type, release=release,
            breakdown=breakdown) if release else [],
    }


def _validate_deck_item_for_checkout(deck_item: DeckMarketplaceItem, *, user_id: int) -> dict[str, Any]:
    if not str(deck_item.source_note_type_id or "").strip():
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "source_note_type_id is required for checkout.",
            status=409,
            field="source_note_type_id",
        )

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in DEFAULT_VISIBLE_PUBLISH_STATUSES:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Deck này hiện không mở bán hoặc không còn khả dụng để thanh toán.",
            status=409,
        )
    if deck_item.owner_user_id == user_id:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Bạn không thể mua chính deck do mình phát hành.",
            status=409,
        )
    # Apply the same learner guard used by fulfillment before creating a
    # payable order or contacting the provider.
    from app.services.share.helpers import (
        ShareControllerError,
        _fence_overlay_install_route,
    )

    try:
        _fence_overlay_install_route(user_id=user_id)
    except ShareControllerError as exc:
        raise PaymentServiceError(exc.error, exc.message, status=exc.status) from exc

    user = db.session.get(User, user_id)
    from app.services.marketplace_pricing_service import calculate_pricing_breakdown

    pricing_breakdown = calculate_pricing_breakdown(deck_item, user)
    if not pricing_breakdown.is_payment_required:
        raise PaymentServiceError(
            "PAYMENT_NOT_REQUIRED",
            "Deck này hiện không yêu cầu thanh toán đối với tài khoản của bạn.",
            status=409,
        )

    existing = payment_repository.get_deck_install(user_id=user_id, deck_item_id=deck_item.id)
    return {
        "product_type": "deck_marketplace_item",
        "product_ref_id": deck_item.id,
        "title_snapshot": deck_item.title,
        "amount_minor": pricing_breakdown.effective_price_minor,
        "subtotal_amount_minor": pricing_breakdown.base_price_minor,
        "discount_amount_minor": pricing_breakdown.discount_amount_minor,
        "product_snapshot": {
            "title": deck_item.title,
            "pricing_mode": deck_item.pricing_mode,
            "source_price_amount_minor": int(deck_item.price_amount_minor or 0),
            "source_price_integer": int(deck_item.price_amount_minor or 0),
            "student_offer_mode": str(deck_item.student_offer_mode or "none"),
            "student_discount_percent": deck_item.student_discount_percent,
            "student_discount_applied": pricing_breakdown.student_discount_applied,
            "discount_amount_minor": pricing_breakdown.discount_amount_minor,
            "version": deck_item.version,
            "owner_user_id": deck_item.owner_user_id,
            "source_deck_id": deck_item.source_deck_id,
            "source_note_type_id": deck_item.source_note_type_id,
        },
        "existing_access": (
            {
                "already_installed": True,
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
            }
            if existing is not None
            else None
        ),
    }


def _resolve_existing_access_for_product(*, product_type: str, product_ref_id: str, user_id: int) -> dict[str, Any] | None:
    if product_type == "note_type":
        install = payment_repository.get_note_type_install(
            user_id=user_id,
            source_note_type_id=product_ref_id,
        )
        if install is None:
            return None
        if not install.installed_note_type_id or db.session.get(NoteType, install.installed_note_type_id) is None:
            from app.services.note_type_release_service import stage_receipt, NoteTypeReleaseError
            source = db.session.get(NoteType, product_ref_id)
            if source is None:
                return None
            try:
                install, _created = stage_receipt(db.session, source_note_type=source, user_id=user_id)
                db.session.commit()
            except NoteTypeReleaseError as exc:
                db.session.rollback()
                raise PaymentServiceError(exc.code, exc.message, status=exc.status) from exc
        return {
            "already_installed": True,
            "source_note_type_id": product_ref_id,
            "installed_note_type_id": install.installed_note_type_id,
            "applied_release_id": install.applied_release_id,
            "legacy_installation": not bool(install.applied_release_id),
        }

    if product_type == "template":
        from app.services import template_marketplace_service

        return template_marketplace_service.existing_access(user_id=user_id, template_id=product_ref_id)

    if product_type == "deck_marketplace_item":
        install = payment_repository.get_deck_install(
            user_id=user_id,
            deck_item_id=product_ref_id,
        )
        if install is None:
            return None
        return {
            "already_installed": True,
            "deck_item_id": product_ref_id,
            "installed_deck_id": install.local_deck_id,
        }

    return None


def _load_checkout_context(*, product_type: str, product_ref_id: str, user_id: int) -> dict[str, Any]:
    if product_type == "note_type":
        source_note_type = db.session.get(NoteType, product_ref_id)
        if source_note_type is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy Note Type cần thanh toán.", status=404)
        context = _validate_note_type_for_checkout(source_note_type, user_id=user_id)
        context["product"] = source_note_type
        return context

    if product_type == "deck_marketplace_item":
        deck_item = db.session.get(DeckMarketplaceItem, product_ref_id)
        if deck_item is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy deck cần thanh toán.", status=404)
        context = _validate_deck_item_for_checkout(deck_item, user_id=user_id)
        context["product"] = deck_item
        return context

    if product_type == "template":
        from app.services import template_marketplace_service

        try:
            context = template_marketplace_service.checkout_context(template_id=product_ref_id, user_id=user_id)
        except template_marketplace_service.TemplateCheckoutError as exc:
            raise PaymentServiceError(exc.code, exc.message, status=exc.status) from exc
        context["product"] = None
        return context

    raise PaymentServiceError(
        "VALIDATION_ERROR",
        "Loại sản phẩm thanh toán không hợp lệ.",
        status=400,
        field="product_type",
    )


def _build_checkout_attempt(
    order: PaymentOrder,
    *,
    amount_minor: int,
    title_snapshot: str,
    product_type: str,
    product_ref_id: str,
    return_url: str,
    cancel_url: str,
    buyer_email: str | None = None,
) -> PaymentAttempt:
    _require_supported_provider()
    if not return_url or not cancel_url:
        raise PaymentServiceError(
            "PAYMENT_RETURN_URL_REQUIRED",
            "Không thể tạo đơn thanh toán vì thiếu liên kết quay lại sau khi rời PayOS.",
            status=400,
        )
    now = _utcnow()
    reference = _build_payment_reference()
    expires_at = now + timedelta(seconds=payment_config.order_expiry_seconds(default=DEFAULT_ORDER_EXPIRY_SECONDS))
    provider_order_code = _build_provider_order_code()
    resolved_return_url = _append_payment_context(
        return_url,
        order_id=order.id,
        product_type=product_type,
        product_ref_id=product_ref_id,
    )
    resolved_cancel_url = _append_payment_context(
        cancel_url,
        order_id=order.id,
        product_type=product_type,
        product_ref_id=product_ref_id,
    )
    try:
        checkout_session = payos_provider.create_checkout_session(
            provider_order_code=provider_order_code,
            amount_minor=int(amount_minor or 0),
            title_snapshot=title_snapshot,
            payment_reference=reference,
            return_url=resolved_return_url,
            cancel_url=resolved_cancel_url,
            expires_at=expires_at,
            buyer_email=buyer_email,
        )
    except payos_provider.PayOSProviderError as exc:
        raise PaymentServiceError(exc.code, str(exc), status=exc.status) from exc
    provider_metadata = dict(checkout_session.get("provider_metadata") or {})
    provider_metadata.update(
        {
            "merchant_order_code": order.merchant_order_code,
            "title_snapshot": title_snapshot,
            "amount_minor": int(amount_minor or 0),
            "currency_code": checkout_session.get("currency_code") or "VND",
            "payment_reference": reference,
            "return_url": resolved_return_url,
            "cancel_url": resolved_cancel_url,
            "provider_raw_response": checkout_session.get("raw_response") or {},
        }
    )
    return PaymentAttempt(
        order_id=order.id,
        provider_code=PAYMENT_PROVIDER_CODE,
        payment_method_code=PAYMENT_METHOD_CODE,
        status="pending",
        amount_minor=int(amount_minor or 0),
        currency_code=str(checkout_session.get("currency_code") or "VND"),
        provider_payment_id=str(checkout_session.get("provider_payment_id") or "") or None,
        provider_order_code=str(checkout_session.get("provider_order_code") or provider_order_code),
        expected_payment_reference=reference,
        checkout_url=str(checkout_session.get("checkout_url") or "") or None,
        provider_metadata_json=provider_metadata,
        expires_at=checkout_session.get("expires_at") or expires_at,
    )


def _sync_attempt_with_payos(order: PaymentOrder, attempt: PaymentAttempt, *, now: datetime) -> str:
    # Fulfillment serializes orders; keep this edge lazy to avoid an import cycle.
    from app.services.payment.fulfillment import _ensure_entitlements_for_confirmed_order
    payment_repository.lock_buyer_for_payment(order.user_id)
    order, attempt = payment_repository.get_order_and_latest_attempt_for_update(order_id=order.id, attempt_id=attempt.id)
    if order.status == "paid" and order.grant_status == "completed":
        return "completed"
    if order.status == "under_review":
        return "block"

    if attempt.provider_code != PAYMENT_PROVIDER_CODE or not attempt.checkout_url:
        attempt.status = "failed"
        attempt.failed_at = now
        attempt.failure_code = "superseded"
        attempt.failure_message = "Lượt thanh toán cũ không còn đủ dữ liệu để tiếp tục nên hệ thống sẽ tạo lượt mới."
        order.status = "failed"
        order.closed_at = now
        return "recreate"

    provider_payment_id = _clean_text(attempt.provider_payment_id)
    provider_order_code = _clean_text(attempt.provider_order_code)
    if not provider_payment_id and not provider_order_code:
        return "reuse"

    try:
        provider_state = payos_provider.get_payment_link_state(
            provider_payment_id=provider_payment_id or None,
            provider_order_code=provider_order_code or None,
        )
    except payos_provider.PayOSProviderError as exc:
        if exc.status in {400, 404, 409}:
            attempt.status = "failed"
            attempt.failed_at = now
            attempt.failure_code = "provider_link_unavailable"
            attempt.failure_message = "Liên kết thanh toán cũ không còn khả dụng trên PayOS nên hệ thống sẽ tạo đơn mới."
            order.status = "failed"
            order.closed_at = now
            return "recreate"
        return "reuse"

    provider_status = _clean_text(provider_state.get("status")).upper()
    provider_metadata = dict(attempt.provider_metadata_json or {})
    provider_metadata["provider_status"] = provider_status or provider_metadata.get("provider_status")
    provider_metadata["payment_link_state"] = provider_state.get("raw_response") or {}
    provider_metadata["amount_paid_minor"] = int(provider_state.get("amount_paid_minor") or 0)
    provider_metadata["amount_remaining_minor"] = int(provider_state.get("amount_remaining_minor") or 0)
    provider_metadata["provider_state_checked_at"] = _iso(now)
    if provider_state.get("cancellation_reason"):
        provider_metadata["provider_cancellation_reason"] = provider_state["cancellation_reason"]
    if provider_state.get("canceled_at"):
        provider_metadata["provider_canceled_at"] = provider_state["canceled_at"]
    attempt.provider_metadata_json = provider_metadata

    if provider_status in PAYOS_PROVIDER_REUSABLE_STATUSES:
        attempt.status = "pending"
        return "reuse"

    if provider_status == "EXPIRED":
        attempt.status = "expired"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "expired"
        attempt.failure_message = "Lượt thanh toán cũ đã hết hạn trên PayOS."
        order.status = "expired"
        order.closed_at = now
        return "recreate"

    if provider_status == "CANCELLED":
        attempt.status = "canceled"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "canceled"
        attempt.failure_message = (
            _clean_text(provider_state.get("cancellation_reason"))
            or "Phiên thanh toán cũ đã bị hủy hoặc đóng trên PayOS."
        )
        order.status = "canceled"
        order.closed_at = now
        return "recreate"

    if provider_status == "FAILED":
        attempt.status = "failed"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "provider_failed"
        attempt.failure_message = "PayOS báo phiên thanh toán cũ không còn xử lý được."
        order.status = "failed"
        order.closed_at = now
        return "recreate"

    if provider_status == "UNDERPAID":
        attempt.status = "manual_review"
        attempt.manual_review_reason = "PayOS ghi nhận giao dịch chưa đủ số tiền nên cần kiểm tra thủ công."
        order.status = "under_review"
        order.closed_at = None
        return "block"

    if provider_status == "PAID":
        provider_amount_minor = int(provider_state.get("amount_minor") or 0)
        provider_amount_paid_minor = int(provider_state.get("amount_paid_minor") or 0)
        if provider_amount_minor and provider_amount_minor != int(attempt.amount_minor or 0):
            attempt.status = "manual_review"
            attempt.manual_review_reason = (
                "PayOS xác nhận thanh toán thành công nhưng số tiền trên PayOS không khớp với đơn hàng."
            )
            order.status = "under_review"
            order.closed_at = None
            return "block"
        if provider_amount_paid_minor and provider_amount_paid_minor != int(attempt.amount_minor or 0):
            attempt.status = "manual_review"
            attempt.manual_review_reason = (
                "PayOS xác nhận thanh toán thành công nhưng số tiền thực nhận không khớp với đơn hàng."
            )
            order.status = "under_review"
            order.closed_at = None
            return "block"

        attempt.status = "confirmed"
        attempt.confirmed_at = attempt.confirmed_at or now
        attempt.failed_at = None
        attempt.failure_code = None
        attempt.failure_message = None
        attempt.manual_review_reason = None
        order.status = "paid"
        order.paid_at = order.paid_at or now
        order.closed_at = now
        try:
            _ensure_entitlements_for_confirmed_order(order, attempt, now=now)
        except PaymentServiceError as exc:
            from app.services.payment.template_quotes import DUPLICATE_TEMPLATE_PAYMENT, mark_duplicate_payment_for_review
            if exc.code != DUPLICATE_TEMPLATE_PAYMENT:
                raise
            mark_duplicate_payment_for_review(order, attempt, exc, now=now, source="provider_state")
            return "block"
        return "completed"

    attempt.status = "manual_review"
    attempt.manual_review_reason = (
        f"PayOS trả về trạng thái '{provider_status or 'UNKNOWN'}' nên hệ thống không tự động tái sử dụng lượt thanh toán này."
    )
    order.status = "under_review"
    order.closed_at = None
    return "block"


def _quote_signature(lines):
    return sorted((line["product_type"], line["product_ref_id"], int(line["amount_minor"]),
        str(line["product_snapshot"].get("note_type_release_id") or ""),
        str(line["product_snapshot"].get("release_id") or ""),
        str(line["product_snapshot"].get("owner_user_id") or "")) for line in lines)


def _same_quote(order, context):
    previous = [{"product_type": item.product_type, "product_ref_id": item.product_ref_id,
        "amount_minor": item.line_total_amount_minor, "product_snapshot": item.product_snapshot_json or {}}
        for item in order.items]
    return int(order.total_amount_minor) == int(context["amount_minor"]) and _quote_signature(previous) == _quote_signature(context.get("order_items") or [context])


def _cancel_replaced_quote(order, attempt, *, now):
    try:
        state = payos_provider.cancel_checkout_session(provider_payment_id=attempt.provider_payment_id,
            provider_order_code=attempt.provider_order_code)
    except payos_provider.PayOSProviderError as exc:
        # Payment may have won the race with cancellation. Reconcile it before
        # allowing a new payable quote to be created.
        resolution = _sync_attempt_with_payos(order, attempt, now=now)
        if resolution in {"completed", "block"}:
            return resolution
        raise PaymentServiceError(exc.code, str(exc), status=exc.status) from exc
    if state.get("status") not in {"CANCELLED", "CANCELED", "EXPIRED"}:
        resolution = _sync_attempt_with_payos(order, attempt, now=now)
        if resolution in {"completed", "block", "recreate"}:
            return resolution
        raise PaymentServiceError("CHECKOUT_QUOTE_CHANGED", "Giá đã thay đổi; chưa thể đóng phiên thanh toán cũ. Vui lòng thử lại.", status=409)
    attempt.status = "canceled"
    attempt.failed_at = now
    attempt.failure_code = "quote_replaced"
    attempt.failure_message = "Phiên thanh toán đã được thay thế để dùng giá và quyền template hiện tại."
    order.status = "canceled"
    order.closed_at = now
    return "recreate"


def reconcile_stale_template_quotes(*, user_id: int, product_type=None, product_ref_id=None) -> dict[str, Any]:
    """Close all independently issued quotes invalidated by acquired licenses.

    Owns a short transaction so provider cancellations/review evidence survive
    a later failed install. Callers acquire the buyer lock again before writes.
    """
    from app.services.payment.template_quotes import duplicate_template_charge_ids
    payment_repository.lock_buyer_for_payment(user_id)
    closed, review = [], []
    try:
        for order in payment_repository.list_pending_template_orders(user_id=user_id):
            attempt = _latest_attempt(order)
            if attempt is None:
                continue
            if order.status == "under_review":
                if (attempt.provider_metadata_json or {}).get("duplicate_license_review"):
                    review.append(order.id)
                continue
            if not duplicate_template_charge_ids(order):
                continue
            if attempt.status not in ACTIVE_ATTEMPT_STATUSES:
                continue
            resolution = _cancel_replaced_quote(order, attempt, now=_utcnow())
            if resolution == "block":
                review.append(order.id)
            elif resolution == "recreate":
                closed.append(order.id)
        db.session.commit()
    except PaymentServiceError:
        # Do not lose already confirmed cancellations if another provider link
        # cannot be reconciled in this pass.
        db.session.commit()
        raise
    if review:
        raise PaymentServiceError("PAYMENT_REQUIRES_REVIEW",
            "An earlier template quote was paid after its license was acquired. The payment needs review before continuing.",
            status=409, extra={"order_ids": review})
    return {"invalidated_order_ids": closed}


def reconcile_template_quotes_after_grant(*, user_id: int) -> dict[str, Any]:
    """Best-effort cleanup after the receipt is committed and cannot be undone."""
    try:
        result = reconcile_stale_template_quotes(user_id=user_id)
        if result["invalidated_order_ids"]:
            return {"quote_reconciliation": {"status": "complete", **result}}
        return {}
    except PaymentServiceError as exc:
        from flask import current_app
        current_app.logger.warning("Template quote reconciliation requires attention user_id=%s error=%s", user_id, exc.code)
        return {"quote_reconciliation": {"status": "requires_review" if exc.code == "PAYMENT_REQUIRES_REVIEW" else "retry_required",
            "error": exc.code, "order_ids": list(exc.extra.get("order_ids") or [])}}


def _create_or_reuse_order_for_context(
    context: dict[str, Any],
    *,
    user_id: int | None,
    return_url: str,
    cancel_url: str,
    buyer_email: str | None = None,
) -> tuple[PaymentOrder, bool]:
    now = _utcnow()
    pending_orders = payment_repository.list_reusable_orders_for_product(
        user_id=user_id,
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
    )
    dirty = False
    for order in pending_orders:
        # A standalone template must not reuse an entire bundle order merely
        # because it appears as a dependency line in that order.
        primary = order.items[0] if order.items else None
        if primary is None or primary.product_type != context["product_type"] or primary.product_ref_id != context["product_ref_id"]:
            continue
        latest_attempt = _latest_attempt(order)
        if latest_attempt and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES and order.status == "pending_payment":
            resolution = _sync_attempt_with_payos(order, latest_attempt, now=now)
            if resolution == "reuse" and not _same_quote(order, context):
                resolution = _cancel_replaced_quote(order, latest_attempt, now=now)
            dirty = dirty or resolution != "reuse"
            if resolution in {"reuse", "completed", "block"}:
                db.session.commit()
                return order, False
            if resolution == "recreate":
                continue
        dirty = _maybe_expire_order(order, now=now) or dirty

    order = PaymentOrder(
        user_id=user_id,
        merchant_order_code=_build_merchant_order_code(),
        status="pending_payment",
        grant_status="pending",
        currency_code="VND",
        subtotal_amount_minor=int(context.get("subtotal_amount_minor", context["amount_minor"])),
        discount_amount_minor=int(context.get("discount_amount_minor", 0)),
        total_amount_minor=context["amount_minor"],
    )
    db.session.add(order)
    db.session.flush()

    for line in context.get("order_items") or [context]:
        db.session.add(PaymentOrderItem(
            order_id=order.id,
            product_type=line["product_type"],
            product_ref_id=line["product_ref_id"],
            quantity=1,
            unit_amount_minor=line["amount_minor"],
            line_total_amount_minor=line["amount_minor"],
            title_snapshot=line["title_snapshot"],
            product_snapshot_json=line["product_snapshot"],
        ))
    db.session.flush()

    attempt = _build_checkout_attempt(
        order,
        amount_minor=context["amount_minor"],
        title_snapshot=context["title_snapshot"],
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
        return_url=return_url,
        cancel_url=cancel_url,
        buyer_email=buyer_email,
    )
    db.session.add(attempt)
    db.session.commit()
    return order, True


def prepare_checkout_for_product(
    *,
    user_id: int,
    product_type: str,
    product_ref_id: str,
    return_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    _require_payments_enabled()
    reconcile_stale_template_quotes(user_id=user_id, product_type=product_type, product_ref_id=product_ref_id)
    payment_repository.lock_buyer_for_payment(user_id)
    context = _load_checkout_context(
        product_type=product_type,
        product_ref_id=product_ref_id,
        user_id=user_id,
    )
    existing_access = context.get("existing_access")
    if existing_access is not None:
        db.session.commit()
        return {
            "payment_required": False,
            **existing_access,
        }

    buyer_email = None
    product = context.get("product")
    if product_type == "note_type" and product is not None:
        buyer_email = None
    order, created = _create_or_reuse_order_for_context(
        context,
        user_id=user_id,
        return_url=str(return_url or "").strip(),
        cancel_url=str(cancel_url or return_url or "").strip(),
        buyer_email=buyer_email,
    )
    fresh_order = payment_repository.get_order_by_id(order.id) or order
    if fresh_order.status == "paid" and fresh_order.grant_status == "completed":
        existing_access = _resolve_existing_access_for_product(
            product_type=product_type,
            product_ref_id=product_ref_id,
            user_id=user_id,
        )
        if existing_access is not None:
            return {
                "payment_required": False,
                **existing_access,
            }
    return {
        "payment_required": True,
        "created": created,
        "order": serialize_order(fresh_order),
    }


def prepare_support_donation_checkout(
    *,
    user_id: int | None,
    amount_minor: int,
    return_url: str | None = None,
    cancel_url: str | None = None,
) -> dict[str, Any]:
    _require_payments_enabled()
    context = support_donation_service.build_saved_donation_checkout_context(amount_minor=amount_minor)
    order, created = _create_or_reuse_order_for_context(
        context,
        user_id=user_id,
        return_url=str(return_url or "").strip(),
        cancel_url=str(cancel_url or return_url or "").strip(),
        buyer_email=None,
    )
    fresh_order = payment_repository.get_order_by_id(order.id) or order
    latest_attempt = _latest_attempt(fresh_order)
    provider_metadata = dict(latest_attempt.provider_metadata_json or {}) if latest_attempt else {}
    serialized = serialize_order(fresh_order)
    mode = "saved" if user_id is not None else "anonymous"
    return {
        "checkout_mode": mode,
        "payment_required": True,
        "created": created,
        "order": serialized,
        "checkout_url": latest_attempt.checkout_url if latest_attempt else None,
        "payment_link_id": latest_attempt.provider_payment_id if latest_attempt else None,
        "provider_order_code": latest_attempt.provider_order_code if latest_attempt else None,
        "checkout": {
            "provider": latest_attempt.provider_code if latest_attempt else "payos",
            "checkout_url": latest_attempt.checkout_url if latest_attempt else None,
            "payment_link_id": latest_attempt.provider_payment_id if latest_attempt else None,
            "provider_order_code": latest_attempt.provider_order_code if latest_attempt else None,
            "bank_bin": provider_metadata.get("bank_bin"),
            "account_no": provider_metadata.get("account_no"),
            "account_name": provider_metadata.get("account_name"),
            "qr_code": provider_metadata.get("qr_code"),
            "provider_status": provider_metadata.get("provider_status"),
            "amount_minor": int(fresh_order.total_amount_minor or amount_minor or 0),
            "currency_code": fresh_order.currency_code or "VND",
            "payment_reference": latest_attempt.expected_payment_reference if latest_attempt else None,
            "merchant_order_code": fresh_order.merchant_order_code,
            "expires_at": _iso(latest_attempt.expires_at) if latest_attempt else None,
            "provider_metadata": provider_metadata,
        },
    }


