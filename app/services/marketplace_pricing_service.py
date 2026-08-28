"""Marketplace pricing and student discount calculation engine."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.services.student_verification_service import (
    StudentStatus,
    get_user_student_status,
    is_user_verified_student,
)
from models.deck_marketplace_item import DeckMarketplaceItem
from models.user import User


@dataclass(frozen=True)
class PricingBreakdown:
    base_price_minor: int
    effective_price_minor: int
    discount_amount_minor: int
    student_discount_applied: bool
    student_offer_mode: str
    student_discount_percent: int | None
    is_payment_required: bool
    user_student_status: str


def format_vnd(amount_minor: int) -> str:
    """Format minor VND amount to display string."""
    if amount_minor <= 0:
        return "Miễn phí"
    return f"{amount_minor:,.0f} ₫".replace(",", ".")


def validate_student_offer(
    *,
    pricing_mode: str,
    student_offer_mode: str | None,
    student_discount_percent: int | None,
) -> tuple[str, int | None, str | None]:
    """Validate student offer settings for marketplace items.
    
    Returns (normalized_mode, normalized_percent, error_message).
    """
    mode = str(pricing_mode or "free").strip().lower()
    if mode != "paid":
        # Globally free deck cannot have student discount settings
        return "none", None, None

    offer_mode = str(student_offer_mode or "none").strip().lower()
    if offer_mode not in {"none", "free", "percent_discount"}:
        return "none", None, "Chế độ ưu đãi sinh viên không hợp lệ (chọn none, free, hoặc percent_discount)."

    if offer_mode == "none":
        return "none", None, None

    if offer_mode == "free":
        return "free", None, None

    if offer_mode == "percent_discount":
        if student_discount_percent is None:
            return "percent_discount", None, "Vui lòng nhập mức giảm giá phần trăm cho sinh viên."
        try:
            percent = int(student_discount_percent)
        except (ValueError, TypeError):
            return "percent_discount", None, "Mức giảm giá phần trăm phải là số nguyên."
        if percent < 1 or percent > 99:
            return "percent_discount", None, "Mức giảm giá cho sinh viên phải nằm trong khoảng từ 1% đến 99%."
        return "percent_discount", percent, None

    return "none", None, None


def calculate_pricing_breakdown(
    deck_item: DeckMarketplaceItem,
    user: User | None,
) -> PricingBreakdown:
    """Authoritative server-side calculation of deck price and student discount."""
    base_price = int(deck_item.price_amount_minor or 0)
    pricing_mode = str(deck_item.pricing_mode or "free").strip().lower()

    if pricing_mode != "paid" or base_price <= 0:
        return PricingBreakdown(
            base_price_minor=0,
            effective_price_minor=0,
            discount_amount_minor=0,
            student_discount_applied=False,
            student_offer_mode="none",
            student_discount_percent=None,
            is_payment_required=False,
            user_student_status=get_user_student_status(user).value,
        )

    student_offer_mode = str(deck_item.student_offer_mode or "none").strip().lower()
    student_discount_percent = (
        int(deck_item.student_discount_percent)
        if deck_item.student_discount_percent is not None
        else None
    )

    user_status = get_user_student_status(user)
    is_student = user_status == StudentStatus.VERIFIED_STUDENT

    # If user is not a verified student or no student offer is enabled
    if not is_student or student_offer_mode == "none":
        return PricingBreakdown(
            base_price_minor=base_price,
            effective_price_minor=base_price,
            discount_amount_minor=0,
            student_discount_applied=False,
            student_offer_mode=student_offer_mode,
            student_discount_percent=student_discount_percent,
            is_payment_required=True,
            user_student_status=user_status.value,
        )

    # Student Offer: Free
    if student_offer_mode == "free":
        return PricingBreakdown(
            base_price_minor=base_price,
            effective_price_minor=0,
            discount_amount_minor=base_price,
            student_discount_applied=True,
            student_offer_mode="free",
            student_discount_percent=100,
            is_payment_required=False,
            user_student_status=user_status.value,
        )

    # Student Offer: Percentage discount
    if student_offer_mode == "percent_discount" and student_discount_percent:
        percent = min(max(student_discount_percent, 1), 99)
        discount_amount = int(round(base_price * (percent / 100.0)))
        effective_price = max(0, base_price - discount_amount)
        return PricingBreakdown(
            base_price_minor=base_price,
            effective_price_minor=effective_price,
            discount_amount_minor=discount_amount,
            student_discount_applied=True,
            student_offer_mode="percent_discount",
            student_discount_percent=percent,
            is_payment_required=effective_price > 0,
            user_student_status=user_status.value,
        )

    # Default fallback
    return PricingBreakdown(
        base_price_minor=base_price,
        effective_price_minor=base_price,
        discount_amount_minor=0,
        student_discount_applied=False,
        student_offer_mode=student_offer_mode,
        student_discount_percent=student_discount_percent,
        is_payment_required=True,
        user_student_status=user_status.value,
    )


def serialize_item_student_offer(
    deck_item: DeckMarketplaceItem,
    user: User | None = None,
) -> dict[str, Any]:
    """Serialize student offer information for marketplace listings and detail views."""
    breakdown = calculate_pricing_breakdown(deck_item, user)
    base_price = int(deck_item.price_amount_minor or 0)
    has_student_offer = (
        deck_item.pricing_mode == "paid"
        and str(deck_item.student_offer_mode or "none") in {"free", "percent_discount"}
    )

    # Student preview price (what any verified student would pay)
    student_preview_price_minor = base_price
    student_preview_display = None
    if has_student_offer:
        if deck_item.student_offer_mode == "free":
            student_preview_price_minor = 0
            student_preview_display = "Miễn phí cho sinh viên"
        elif deck_item.student_offer_mode == "percent_discount" and deck_item.student_discount_percent:
            percent = int(deck_item.student_discount_percent)
            discount = int(round(base_price * (percent / 100.0)))
            student_preview_price_minor = max(0, base_price - discount)
            student_preview_display = format_vnd(student_preview_price_minor)

    return {
        "student_offer_mode": str(deck_item.student_offer_mode or "none"),
        "student_discount_percent": (
            int(deck_item.student_discount_percent)
            if deck_item.student_discount_percent is not None
            else None
        ),
        "has_student_offer": has_student_offer,
        "student_preview_price_minor": student_preview_price_minor,
        "student_preview_display": student_preview_display,
        "effective_price_amount_minor": breakdown.effective_price_minor,
        "effective_price_display": format_vnd(breakdown.effective_price_minor),
        "discount_amount_minor": breakdown.discount_amount_minor,
        "student_discount_applied": breakdown.student_discount_applied,
        "is_payment_required": breakdown.is_payment_required,
        "user_student_status": breakdown.user_student_status,
    }
