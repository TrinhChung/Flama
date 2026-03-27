from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from app.validators import RequestValidationError, sanitize_query_text


ORDER_STATUS_VALUES = {
    "all",
    "pending_payment",
    "paid",
    "under_review",
    "expired",
    "canceled",
    "failed",
    "refunded",
}
GRANT_STATUS_VALUES = {"all", "pending", "completed", "failed"}
ATTEMPT_STATUS_VALUES = {
    "all",
    "created",
    "pending",
    "confirmed",
    "manual_review",
    "expired",
    "canceled",
    "failed",
    "refunded",
}
WEBHOOK_STATUS_VALUES = {"all", "received", "processed", "ignored", "failed"}
PROVIDER_VALUES = {"all", "payos"}
PRODUCT_TYPE_VALUES = {"all", "note_type", "deck_marketplace_item"}
ORDER_SORT_VALUES = {"created_desc", "created_asc", "amount_desc", "amount_asc"}
ATTEMPT_SORT_VALUES = {"created_desc", "created_asc", "amount_desc", "amount_asc"}
DASHBOARD_RANGE_VALUES = {"7d", "30d", "90d", "all"}


@dataclass(frozen=True)
class OrderFilterInput:
    q: str = ""
    buyer: str = ""
    seller: str = ""
    order_status: str = "all"
    payment_status: str = "all"
    grant_status: str = "all"
    provider: str = "all"
    product_type: str = "all"
    date_from: str = ""
    date_to: str = ""
    min_amount_minor: int | None = None
    max_amount_minor: int | None = None
    sort: str = "created_desc"


@dataclass(frozen=True)
class TransactionFilterInput:
    q: str = ""
    buyer: str = ""
    order_code: str = ""
    status: str = "all"
    provider: str = "all"
    payment_method: str = "all"
    webhook_status: str = "all"
    date_from: str = ""
    date_to: str = ""
    min_amount_minor: int | None = None
    max_amount_minor: int | None = None
    sort: str = "created_desc"


@dataclass(frozen=True)
class DashboardFilterInput:
    period: str = "30d"


def parse_order_filters(args) -> OrderFilterInput:
    return OrderFilterInput(
        q=_sanitize_optional_text(args.get("q"), max_length=120),
        buyer=_sanitize_optional_text(args.get("buyer"), max_length=120),
        seller=_sanitize_optional_text(args.get("seller"), max_length=120),
        order_status=_normalize_choice(args.get("order_status"), ORDER_STATUS_VALUES, default="all"),
        payment_status=_normalize_choice(args.get("payment_status"), ATTEMPT_STATUS_VALUES, default="all"),
        grant_status=_normalize_choice(args.get("grant_status"), GRANT_STATUS_VALUES, default="all"),
        provider=_normalize_choice(args.get("provider"), PROVIDER_VALUES, default="all"),
        product_type=_normalize_choice(args.get("product_type"), PRODUCT_TYPE_VALUES, default="all"),
        date_from=_normalize_date_string(args.get("date_from")),
        date_to=_normalize_date_string(args.get("date_to")),
        min_amount_minor=_parse_amount_minor(args.get("min_amount")),
        max_amount_minor=_parse_amount_minor(args.get("max_amount")),
        sort=_normalize_choice(args.get("sort"), ORDER_SORT_VALUES, default="created_desc"),
    )


def parse_transaction_filters(args) -> TransactionFilterInput:
    payment_method = str(args.get("payment_method") or "all").strip().lower() or "all"
    if payment_method != "all":
        payment_method = _sanitize_optional_text(payment_method, max_length=64)
        if not payment_method:
            payment_method = "all"

    return TransactionFilterInput(
        q=_sanitize_optional_text(args.get("q"), max_length=120),
        buyer=_sanitize_optional_text(args.get("buyer"), max_length=120),
        order_code=_sanitize_optional_text(args.get("order_code"), max_length=64),
        status=_normalize_choice(args.get("status"), ATTEMPT_STATUS_VALUES, default="all"),
        provider=_normalize_choice(args.get("provider"), PROVIDER_VALUES, default="all"),
        payment_method=payment_method,
        webhook_status=_normalize_choice(args.get("webhook_status"), WEBHOOK_STATUS_VALUES, default="all"),
        date_from=_normalize_date_string(args.get("date_from")),
        date_to=_normalize_date_string(args.get("date_to")),
        min_amount_minor=_parse_amount_minor(args.get("min_amount")),
        max_amount_minor=_parse_amount_minor(args.get("max_amount")),
        sort=_normalize_choice(args.get("sort"), ATTEMPT_SORT_VALUES, default="created_desc"),
    )


def parse_dashboard_filters(args) -> DashboardFilterInput:
    return DashboardFilterInput(
        period=_normalize_choice(args.get("period"), DASHBOARD_RANGE_VALUES, default="30d"),
    )


def resolve_date_window(date_from: str, date_to: str) -> tuple[datetime | None, datetime | None]:
    start = _parse_date(date_from) if date_from else None
    end_inclusive = _parse_date(date_to) if date_to else None
    end_exclusive = (end_inclusive + timedelta(days=1)) if end_inclusive is not None else None
    return start, end_exclusive


def resolve_dashboard_since(period: str) -> datetime | None:
    now = datetime.utcnow()
    token = str(period or "30d").strip().lower()
    if token == "7d":
        return now - timedelta(days=7)
    if token == "30d":
        return now - timedelta(days=30)
    if token == "90d":
        return now - timedelta(days=90)
    return None


def _sanitize_optional_text(value: object, *, max_length: int) -> str:
    try:
        return sanitize_query_text(value, field_name="q", max_length=max_length)
    except RequestValidationError:
        return ""


def _normalize_choice(value: object, allowed: set[str], *, default: str) -> str:
    token = str(value or default).strip().lower() or default
    if token not in allowed:
        return default
    return token


def _normalize_date_string(value: object) -> str:
    token = str(value or "").strip()
    if not token:
        return ""
    try:
        _parse_date(token)
    except ValueError:
        return ""
    return token


def _parse_date(value: str) -> datetime:
    return datetime.strptime(str(value).strip(), "%Y-%m-%d")


def _parse_amount_minor(value: object) -> int | None:
    token = str(value or "").strip()
    if not token:
        return None
    try:
        amount = int(token)
    except (TypeError, ValueError):
        return None
    if amount < 0:
        return None
    return amount
