"""Canonical license checks before granting a paid template a second time."""

from app.repositories import note_type_bundle_repository, payment_repository
from app.services.payment.base import PaymentServiceError, _iso
from models import db


DUPLICATE_TEMPLATE_PAYMENT = "PAYMENT_TEMPLATE_ALREADY_LICENSED"


def duplicate_template_charge_ids(order):
    """Current reads remain correct after an earlier REPEATABLE READ snapshot."""
    if order.user_id is None:
        return []
    payment_repository.lock_buyer_for_payment(order.user_id)
    already_granted = {row.payment_order_item_id for row in order.entitlements if row.status == "active"}
    charged = {item.product_ref_id for item in order.items
        if item.product_type == "template" and int(item.line_total_amount_minor or 0) > 0
        and item.id not in already_granted}
    return sorted(note_type_bundle_repository.licensed_template_ids(db.session,
        user_id=order.user_id, template_ids=list(charged), current_read=True))


def require_unlicensed_template_charges(order):
    duplicates = duplicate_template_charge_ids(order)
    if duplicates:
        raise PaymentServiceError(DUPLICATE_TEMPLATE_PAYMENT,
            "A paid template in this quote is already licensed. The payment needs review; no duplicate rights or creator revenue were granted.",
            status=409, extra={"template_ids": duplicates, "order_id": order.id})


def mark_duplicate_payment_for_review(order, attempt, error, *, now, source):
    """Keep the verified payment evidence for support/refund reconciliation."""
    metadata = dict(attempt.provider_metadata_json or {})
    metadata["duplicate_license_review"] = {
        "template_ids": list(error.extra.get("template_ids") or []),
        "detected_at": _iso(now), "source": source,
        "amount_minor": int(attempt.amount_minor or 0),
    }
    attempt.provider_metadata_json = metadata
    attempt.status = "manual_review"
    attempt.manual_review_reason = error.message
    attempt.confirmed_at = attempt.confirmed_at or now
    order.status = "under_review"
    order.paid_at = order.paid_at or now
    order.closed_at = None
