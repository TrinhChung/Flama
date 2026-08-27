"""Payment service base constants, error types, and basic utilities."""

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


class PaymentServiceError(RuntimeError):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        status: int = 400,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.extra = extra or {}


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def _iso(dt: datetime | None) -> str | None:
    return dt.isoformat() if dt is not None else None


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _product_type_label(product_type: str) -> str:
    return {
        "note_type": "template",
        "deck_marketplace_item": "deck",
        support_donation_service.DONATION_PRODUCT_TYPE: "ủng hộ",
    }.get(_clean_text(product_type), "sản phẩm")


def _order_is_support_donation(order: PaymentOrder) -> bool:
    for item in order.items:
        if str(item.product_type or "") == "support_donation":
            return True
    return False


def _product_title_from_order(order: PaymentOrder) -> str:
    if not order.items:
        return "Sản phẩm"
    titles = [_clean_text(item.title_snapshot) or _product_type_label(item.product_type) for item in order.items]
    if len(titles) == 1:
        return titles[0]
    return f"{titles[0]} và {len(titles) - 1} mục khác"


def _require_payments_enabled() -> None:
    if not payment_config.payments_enabled():
        raise PaymentServiceError(
            "PAYMENT_UNAVAILABLE",
            "Hệ thống thanh toán đang tạm thời không khả dụng. Vui lòng thử lại sau.",
            status=503,
        )


def _require_supported_provider() -> None:
    provider_code = payment_config.payment_provider_code()
    if provider_code != PAYMENT_PROVIDER_CODE:
        raise PaymentServiceError(
            "PROVIDER_UNSUPPORTED",
            f"Cổng thanh toán '{provider_code}' chưa được hỗ trợ trên môi trường này.",
            status=500,
            extra={"provider": provider_code},
        )
    payos_provider.assert_payos_provider_available()
