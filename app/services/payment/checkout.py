"""Checkout session validation, order persistence, and PayOS provider link generation."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import re
from secrets import randbelow
import time
from typing import Any, Callable, Dict, List, Optional, Set, Tuple
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit
from uuid import uuid4

from flask import current_app
from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

from app.repositories import payment_repository
from app.services import flashcards_share_service, support_donation_service
from app.services.payment import config as payment_config
from app.services.payment.provider import payos_provider
from models import db
from models.audit_log import AuditLog
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.payment_attempt import PaymentAttempt
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.payment_webhook_event import PaymentWebhookEvent
from models.user import User

logger = logging.getLogger(__name__)
UTC = timezone.utc

PAYMENT_PROVIDER_CODE = "payos"
PAYMENT_METHOD_CODE = "payos_checkout"
PAYOS_PROVIDER_REUSABLE_STATUSES = {"PENDING", "PROCESSING"}


from app.services.payment.base import (
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
from app.services.payment.status_display import (
    _build_order_status_display,
    _grant_status_display,
)

def _validate_note_type_for_checkout(source_note_type: NoteType, *, user_id: int) -> dict[str, Any]:
    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in DEFAULT_VISIBLE_PUBLISH_STATUSES:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Template này hiện không mở bán hoặc không còn khả dụng để thanh toán.",
            status=409,
        )
    if source_note_type.user_id == user_id:
        raise PaymentServiceError(
            "VALIDATION_ERROR",
            "Bạn không thể mua chính template do mình phát hành.",
            status=409,
        )
    if source_note_type.pricing_mode != "paid" or int(source_note_type.price_amount_minor or 0) <= 0:
        raise PaymentServiceError(
            "PAYMENT_NOT_REQUIRED",
            "Template này hiện không yêu cầu thanh toán.",
            status=409,
        )

    existing = payment_repository.get_note_type_install(
        user_id=user_id,
        source_note_type_id=source_note_type.id,
    )
    return {
        "product_type": "note_type",
        "product_ref_id": source_note_type.id,
        "title_snapshot": source_note_type.name,
        "amount_minor": int(source_note_type.price_amount_minor or 0),
        "subtotal_amount_minor": int(source_note_type.price_amount_minor or 0),
        "discount_amount_minor": 0,
        "product_snapshot": {
            "title": source_note_type.name,
            "pricing_mode": source_note_type.pricing_mode,
            "source_price_amount_minor": int(source_note_type.price_amount_minor or 0),
            "source_price_integer": int(source_note_type.price_amount_minor or 0),
            "version": source_note_type.version,
            "owner_user_id": source_note_type.user_id,
        },
        "existing_access": (
            {
                "already_installed": True,
                "source_note_type_id": source_note_type.id,
                "installed_note_type_id": existing.installed_note_type_id,
            }
            if existing is not None
            else None
        ),
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
        return {
            "already_installed": True,
            "source_note_type_id": product_ref_id,
            "installed_note_type_id": install.installed_note_type_id,
        }

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
            raise PaymentServiceError("FIELD_NOT_FOUND", "Không tìm thấy template cần thanh toán.", status=404)
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
            "Không thể tạo đơn thanh toán vì thiếu liên kết quay lại sau khi thanh toán.",
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
            attempt.failure_message = "Liên kết thanh toán cũ không còn khả dụng nên hệ thống sẽ tạo đơn mới."
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
        attempt.failure_message = "Lượt thanh toán cũ đã hết hạn."
        order.status = "expired"
        order.closed_at = now
        return "recreate"

    if provider_status == "CANCELLED":
        attempt.status = "canceled"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "canceled"
        attempt.failure_message = (
            _clean_text(provider_state.get("cancellation_reason"))
            or "Phiên thanh toán cũ đã bị hủy hoặc đóng."
        )
        order.status = "canceled"
        order.closed_at = now
        return "recreate"

    if provider_status == "FAILED":
        attempt.status = "failed"
        attempt.failed_at = attempt.failed_at or now
        attempt.failure_code = "provider_failed"
        attempt.failure_message = "Cổng thanh toán báo phiên giao dịch cũ không còn xử lý được."
        order.status = "failed"
        order.closed_at = now
        return "recreate"

    if provider_status == "UNDERPAID":
        attempt.status = "manual_review"
        attempt.manual_review_reason = "Giao dịch ghi nhận chưa đủ số tiền nên cần kiểm tra thủ công."
        order.status = "under_review"
        order.closed_at = None
        return "block"

    if provider_status == "PAID":
        provider_amount_minor = int(provider_state.get("amount_minor") or 0)
        provider_amount_paid_minor = int(provider_state.get("amount_paid_minor") or 0)
        if provider_amount_minor and provider_amount_minor != int(attempt.amount_minor or 0):
            attempt.status = "manual_review"
            attempt.manual_review_reason = (
                "Giao dịch thành công nhưng số tiền ghi nhận không khớp với đơn hàng."
            )
            order.status = "under_review"
            order.closed_at = None
            return "block"
        if provider_amount_paid_minor and provider_amount_paid_minor != int(attempt.amount_minor or 0):
            attempt.status = "manual_review"
            attempt.manual_review_reason = (
                "Giao dịch thành công nhưng số tiền thực nhận không khớp với đơn hàng."
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
        _ensure_entitlements_for_confirmed_order(order, attempt, now=now)
        return "completed"

    attempt.status = "manual_review"
    attempt.manual_review_reason = (
        f"Cổng thanh toán trả về trạng thái '{provider_status or 'UNKNOWN'}' nên hệ thống không tự động tái sử dụng lượt thanh toán này."
    )
    order.status = "under_review"
    order.closed_at = None
    return "block"


def _create_or_reuse_order_for_context(
    context: dict[str, Any],
    *,
    user_id: int,
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
        dirty = _maybe_expire_order(order, now=now) or dirty
        latest_attempt = _latest_attempt(order)
        if latest_attempt and latest_attempt.status in ACTIVE_ATTEMPT_STATUSES and order.status == "pending_payment":
            resolution = _sync_attempt_with_payos(order, latest_attempt, now=now)
            dirty = dirty or resolution != "reuse"
            if resolution == "reuse":
                db.session.commit()
                return order, False
            if resolution == "completed":
                db.session.commit()
                return order, False
            if resolution == "block":
                db.session.commit()
                return order, False
            if resolution == "recreate":
                continue

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

    order_item = PaymentOrderItem(
        order_id=order.id,
        product_type=context["product_type"],
        product_ref_id=context["product_ref_id"],
        quantity=1,
        unit_amount_minor=context["amount_minor"],
        line_total_amount_minor=context["amount_minor"],
        title_snapshot=context["title_snapshot"],
        product_snapshot_json=context["product_snapshot"],
    )
    db.session.add(order_item)
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
    context = _load_checkout_context(
        product_type=product_type,
        product_ref_id=product_ref_id,
        user_id=user_id,
    )
    existing_access = context.get("existing_access")
    if existing_access is not None:
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
    user_id: int,
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
    return {
        "checkout_mode": "saved",
        "payment_required": True,
        "created": created,
        "order": serialize_order(fresh_order),
    }



