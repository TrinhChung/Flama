"""Unit tests for payOS provider helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone
from unittest.mock import patch

from payos.types import PaymentLink

from app.services.payment.provider import payos_provider


class PayOSProviderTests(unittest.TestCase):
    def test_to_unix_seconds_treats_naive_datetime_as_utc(self):
        naive_utc = datetime(2026, 3, 27, 13, 58, 28)

        actual = payos_provider._to_unix_seconds(naive_utc)

        expected = int(naive_utc.replace(tzinfo=timezone.utc).timestamp())
        self.assertEqual(actual, expected)

    def test_get_payment_link_state_handles_payment_link_without_optional_fields(self):
        provider_link = PaymentLink(
            id="plink-1",
            order_code=1774664619309320,
            amount=120000,
            amount_paid=0,
            amount_remaining=120000,
            status="CANCELLED",
            created_at="2026-03-28T11:24:05Z",
            transactions=[],
            cancellation_reason="User cancelled payment",
            canceled_at="2026-03-28T11:24:05Z",
        )

        with patch(
            "app.services.payment.provider.payos_provider.assert_payos_provider_available",
            return_value=None,
        ), patch(
            "app.services.payment.provider.payos_provider.payos_client.get_payment_link",
            return_value=provider_link,
        ):
            payload = payos_provider.get_payment_link_state(provider_order_code="1774664619309320")

        self.assertEqual(payload["provider_payment_id"], "plink-1")
        self.assertEqual(payload["provider_order_code"], "1774664619309320")
        self.assertEqual(payload["status"], "CANCELLED")
        self.assertEqual(payload["currency_code"], "VND")
        self.assertIsNone(payload["payment_reference"])
        self.assertIsNone(payload["checkout_url"])
        self.assertEqual(payload["cancellation_reason"], "User cancelled payment")


if __name__ == "__main__":
    unittest.main()
