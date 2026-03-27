"""Unit tests for template numeric formatters."""

import unittest

from app.template_formatters import format_number, format_price_display, format_vnd


class TemplateFormattersTestCase(unittest.TestCase):
    def test_format_number_adds_commas_for_integers(self):
        self.assertEqual(format_number(1234567), "1,234,567")

    def test_format_number_preserves_decimal_places_when_requested(self):
        self.assertEqual(format_number("1234567.5", digits=2), "1,234,567.50")

    def test_format_price_display_preserves_wrappers(self):
        self.assertEqual(format_price_display("$1234567.50"), "$1,234,567.50")
        self.assertEqual(format_price_display("1234567 VNĐ"), "1,234,567 VNĐ")

    def test_format_vnd_appends_suffix(self):
        self.assertEqual(format_vnd(50000), "50,000 VNĐ")


if __name__ == "__main__":
    unittest.main()
