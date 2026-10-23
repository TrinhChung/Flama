"""Pure pending-quote checks; no database or live provider calls."""

from datetime import datetime
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from app.services.payment import checkout


class PaymentQuoteReplacementTests(unittest.TestCase):
    def setUp(self):
        self.bundle = {"product_type": "note_type", "product_ref_id": "nt", "amount_minor": 10000,
            "product_snapshot": {"note_type_release_id": "ntr", "owner_user_id": 1}}
        self.foreign = {"product_type": "template", "product_ref_id": "foreign", "amount_minor": 15000,
            "product_snapshot": {"release_id": "tr", "owner_user_id": 2}}
        self.order = SimpleNamespace(total_amount_minor=25000, status="pending_payment", closed_at=None,
            items=[SimpleNamespace(product_type=line["product_type"], product_ref_id=line["product_ref_id"],
                line_total_amount_minor=line["amount_minor"], product_snapshot_json=line["product_snapshot"])
                for line in (self.bundle, self.foreign)])
        self.context = {**self.bundle, "amount_minor": 25000, "order_items": [self.bundle, self.foreign]}
        self.attempt = SimpleNamespace(provider_payment_id="link", provider_order_code="123", status="pending")

    def test_newly_acquired_template_right_requires_a_repriced_quote(self):
        self.assertTrue(checkout._same_quote(self.order, self.context))
        self.context.update(amount_minor=10000, order_items=[self.bundle])
        self.assertFalse(checkout._same_quote(self.order, self.context))

    def test_changed_published_release_cannot_reuse_old_selected_quote(self):
        replacement = {**self.foreign, "product_snapshot": {"release_id": "new-release", "owner_user_id": 2}}
        self.context["order_items"] = [self.bundle, replacement]
        self.assertFalse(checkout._same_quote(self.order, self.context))

    def test_remote_link_is_canceled_before_replacing_pending_order(self):
        now = datetime.utcnow()
        with patch.object(checkout.payos_provider, "cancel_checkout_session", return_value={"status": "CANCELLED"}) as cancel:
            self.assertEqual(checkout._cancel_replaced_quote(self.order, self.attempt, now=now), "recreate")
        cancel.assert_called_once_with(provider_payment_id="link", provider_order_code="123")
        self.assertEqual((self.order.status, self.attempt.status, self.attempt.failure_code), ("canceled", "canceled", "quote_replaced"))

    def test_payment_winning_cancellation_race_is_reconciled_before_new_order(self):
        error = checkout.payos_provider.PayOSProviderError("Already paid", code="PAYMENT_PROVIDER_CANCEL_FAILED", status=502)
        with patch.object(checkout.payos_provider, "cancel_checkout_session", side_effect=error), patch.object(checkout,
                "_sync_attempt_with_payos", return_value="completed"):
            self.assertEqual(checkout._cancel_replaced_quote(self.order, self.attempt, now=datetime.utcnow()), "completed")


if __name__ == "__main__":
    unittest.main()
