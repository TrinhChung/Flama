"""Order fulfillment, entitlement granting, and failure/manual-review transitions."""

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
from app.services import flashcards_share_service, support_donation_service, wallet_service
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
    _iso,
    _utcnow,
)
from app.services.payment.orders import serialize_order

def _fulfill_order_item(*, order: PaymentOrder, order_item: PaymentOrderItem, attempt: PaymentAttempt, now: datetime) -> dict[str, Any]:
    if order_item.product_type == "note_type":
        source_note_type = db.session.get(NoteType, order_item.product_ref_id)
        if source_note_type is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Template da thanh toan khong con ton tai de cap quyen.", status=404)
        install_row = flashcards_share_service.ensure_note_type_install_for_user(
            source_note_type=source_note_type,
            user_id=order.user_id,
            installed_at=now,
        )
        return {
            "source_note_type_id": source_note_type.id,
            "note_type_install_id": install_row.id,
            "installed_note_type_id": install_row.installed_note_type_id,
        }

    if order_item.product_type == "deck_marketplace_item":
        deck_item = db.session.get(DeckMarketplaceItem, order_item.product_ref_id)
        if deck_item is None:
            raise PaymentServiceError("FIELD_NOT_FOUND", "Deck da thanh toan khong con ton tai de cap quyen.", status=404)
        install_result = flashcards_share_service.install_shared_deck_item_for_user(
            deck_item,
            user_id=order.user_id,
            publish_statuses_visible=DEFAULT_VISIBLE_PUBLISH_STATUSES,
        )
        deck_install = payment_repository.get_deck_install(
            user_id=order.user_id,
            deck_item_id=deck_item.id,
        )
        grant_data: dict[str, Any] = {
            "deck_item_id": deck_item.id,
            "deck_install_id": deck_install.id if deck_install is not None else None,
            "local_deck_id": (
                deck_install.local_deck_id
                if deck_install is not None
                else (install_result.get("response") or {}).get("installed_deck_id")
            ),
            "install_created": bool(install_result.get("created")),
        }
        source_note_type_id = str(deck_item.source_note_type_id or "").strip()
        if source_note_type_id:
            note_type_install = payment_repository.get_note_type_install(
                user_id=order.user_id,
                source_note_type_id=source_note_type_id,
            )
            if note_type_install is not None:
                grant_data["note_type_install_id"] = note_type_install.id
                grant_data["installed_note_type_id"] = note_type_install.installed_note_type_id
        return grant_data

    if order_item.product_type == support_donation_service.DONATION_PRODUCT_TYPE:
        return {
            "donation_amount_minor": int(order_item.line_total_amount_minor or order_item.unit_amount_minor or 0),
            "recorded_at": _iso(now),
            "seller_name": support_donation_service.DONATION_SELLER_NAME,
        }

    if order_item.product_type == "template":
        from app.services import template_marketplace_service

        try:
            return template_marketplace_service.fulfill_purchase(user_id=order.user_id, template_id=order_item.product_ref_id)
        except template_marketplace_service.TemplateCheckoutError as exc:
            raise PaymentServiceError(exc.code, exc.message, status=exc.status) from exc

    raise PaymentServiceError("VALIDATION_ERROR", "Don hang chua loai san pham khong duoc ho tro.", status=400)


def _ensure_entitlements_for_confirmed_order(order: PaymentOrder, attempt: PaymentAttempt, *, now: datetime) -> None:
    existing_by_item_id = {row.payment_order_item_id: row for row in order.entitlements}
    for order_item in order.items:
        if order.user_id is None:
            if order_item.product_type == support_donation_service.DONATION_PRODUCT_TYPE:
                continue
            raise PaymentServiceError("VALIDATION_ERROR", "Đơn hàng này không gắn với người dùng hợp lệ để cấp quyền.")
        entitlement = existing_by_item_id.get(order_item.id)
        if entitlement is None:
            entitlement_type = "shared_note_type_install"
            if order_item.product_type == "deck_marketplace_item":
                entitlement_type = "shared_deck_install"
            elif order_item.product_type == "template":
                entitlement_type = "shared_template_install"
            elif order_item.product_type == support_donation_service.DONATION_PRODUCT_TYPE:
                entitlement_type = "support_donation_record"
            entitlement = PaymentEntitlement(
                user_id=order.user_id,
                payment_order_id=order.id,
                payment_order_item_id=order_item.id,
                payment_attempt_id=attempt.id,
                entitlement_type=entitlement_type,
                resource_type=order_item.product_type,
                resource_ref_id=order_item.product_ref_id,
                status="pending",
                grant_data_json={},
            )
            db.session.add(entitlement)
            db.session.flush()

        if entitlement.status == "active":
            continue

        entitlement.payment_attempt_id = attempt.id
        entitlement.status = "pending"
        entitlement.grant_data_json = _fulfill_order_item(
            order=order,
            order_item=order_item,
            attempt=attempt,
            now=now,
        )
        entitlement.status = "active"
        entitlement.granted_at = now
        entitlement.effective_from = now

        # Credit creator/author wallet for marketplace sales
        wallet_service.credit_creator_for_deck_sale(
            order=order,
            order_item=order_item,
            now=now,
        )

    order.grant_status = "completed"


def _mark_manual_review(
    *,
    order: PaymentOrder,
    attempt: PaymentAttempt,
    event: PaymentWebhookEvent,
    reason: str,
    now: datetime,
) -> None:
    attempt.status = "manual_review"
    attempt.manual_review_reason = reason
    order.status = "under_review"
    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id
    event.processing_status = "processed"
    event.error_message = reason
    event.processed_at = now


def _mark_failed_attempt(
    *,
    order: PaymentOrder,
    attempt: PaymentAttempt,
    event: PaymentWebhookEvent,
    reason: str,
    now: datetime,
) -> None:
    attempt.status = "failed"
    attempt.failed_at = now
    attempt.failure_code = "provider_failed"
    attempt.failure_message = reason
    order.status = "failed"
    order.closed_at = now
    event.payment_attempt_id = attempt.id
    event.payment_order_id = order.id
    event.processing_status = "processed"
    event.error_message = reason
    event.processed_at = now



