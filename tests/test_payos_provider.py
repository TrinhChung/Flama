"""Unit tests for payOS provider helpers."""

from __future__ import annotations

import unittest
from datetime import datetime, timezone

from app.services.payment.provider import payos_provider


class PayOSProviderTests(unittest.TestCase):
    def test_to_unix_seconds_treats_naive_datetime_as_utc(self):
        naive_utc = datetime(2026, 3, 27, 13, 58, 28)

        actual = payos_provider._to_unix_seconds(naive_utc)

        expected = int(naive_utc.replace(tzinfo=timezone.utc).timestamp())
        self.assertEqual(actual, expected)


if __name__ == "__main__":
    unittest.main()
