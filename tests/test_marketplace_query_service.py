"""Unit tests for marketplace price parsing and display serialization."""

import unittest

from app.services.marketplace_query_service import (
    parse_price_amount_minor,
    serialize_deck_marketplace_item,
    serialize_note_type_marketplace_card,
)
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType


class MarketplaceQueryServiceTestCase(unittest.TestCase):
    def test_parse_price_cents_treats_float_numbers_as_whole_vnd(self):
        self.assertEqual(parse_price_amount_minor(50000.0), 50000)
        self.assertIsNone(parse_price_amount_minor(50000.5))

    def test_parse_price_cents_accepts_vnd_suffix_and_grouping(self):
        self.assertEqual(parse_price_amount_minor("50,000 VNĐ"), 50000)
        self.assertEqual(parse_price_amount_minor("75.000"), 75000)
        self.assertEqual(parse_price_amount_minor("90000 VND"), 90000)

    def test_serialize_note_type_marketplace_card_uses_vnd_display(self):
        note_type = NoteType(
            user_id=1,
            name="Kanji N3",
            pricing_mode="paid",
            price_amount_minor=50000,
        )

        payload = serialize_note_type_marketplace_card(note_type)

        self.assertEqual(payload["price_display"], "50,000 VNĐ")

    def test_serialize_marketplace_items_show_free_in_vietnamese(self):
        note_type = NoteType(
            user_id=1,
            name="Grammar Basics",
            pricing_mode="free",
            price_amount_minor=0,
        )
        deck_item = DeckMarketplaceItem(
            owner_user_id=1,
            title="Deck miễn phí",
            description="desc",
            primary_category="Japanese",
            pricing_mode="free",
            price_amount_minor=0,
        )

        note_type_payload = serialize_note_type_marketplace_card(note_type)
        deck_payload = serialize_deck_marketplace_item(deck_item)

        self.assertEqual(note_type_payload["price_display"], "Miễn phí")
        self.assertEqual(deck_payload["price_display"], "Miễn phí")

    def test_serialize_deck_marketplace_item_uses_vnd_display(self):
        deck_item = DeckMarketplaceItem(
            owner_user_id=1,
            title="Deck trả phí",
            description="desc",
            primary_category="Japanese",
            pricing_mode="paid",
            price_amount_minor=125000,
        )

        payload = serialize_deck_marketplace_item(deck_item)

        self.assertEqual(payload["price_display"], "125,000 VNĐ")


if __name__ == "__main__":
    unittest.main()
