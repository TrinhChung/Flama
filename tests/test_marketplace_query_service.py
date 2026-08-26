import unittest

from sqlalchemy import event

from app import create_app
from app.services.marketplace_query_service import (
    batch_compute_deck_items_stats,
    build_shared_deck_lessons_structure,
    compute_deck_item_stats,
    parse_price_amount_minor,
    serialize_deck_marketplace_item,
    serialize_note_type_marketplace_card,
)
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


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
        self.assertEqual(deck_payload["lesson_count"], 0)
        self.assertEqual(deck_payload["note_count"], 0)

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


class MarketplaceDeckStatsTestCase(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        # Create user
        self.user = User(username="teacher", email="teacher@example.com")
        self.user.set_password("pass1234")
        db.session.add(self.user)
        db.session.flush()

        # Create note type & template
        self.nt = NoteType(name="Vocab Model", user_id=self.user.id)
        db.session.add(self.nt)
        db.session.flush()

        self.template = Template(
            note_type_id=self.nt.id,
            name="Card 1",
            front_html="{{Front}}",
            back_html="{{FrontSide}}<hr>{{Back}}",
            position=0,
        )
        db.session.add(self.template)
        db.session.flush()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_compute_deck_item_stats_single_deck(self):
        # Single deck with 3 notes
        root_deck = Deck(name="N5 Basics", owner_user_id=self.user.id)
        db.session.add(root_deck)
        db.session.flush()

        for i in range(3):
            note = Note(
                note_type_id=self.nt.id,
                user_id=self.user.id,
                deck_id=root_deck.id,
                field_values={"Front": f"Word {i}", "Back": f"Meaning {i}"},
            )
            db.session.add(note)
            db.session.flush()
            card = Card(note_id=note.id, template_id=self.template.id)
            db.session.add(card)

        deck_item = DeckMarketplaceItem(
            owner_user_id=self.user.id,
            source_deck_id=root_deck.id,
            title="N5 Basics Shared",
            description="desc",
        )
        db.session.add(deck_item)
        db.session.flush()

        stats = compute_deck_item_stats(deck_item)
        self.assertEqual(stats["lesson_count"], 1)
        self.assertEqual(stats["total_decks"], 1)
        self.assertEqual(stats["note_count"], 3)
        self.assertEqual(stats["card_count"], 3)
        self.assertFalse(stats["has_subdecks"])

        serialized = serialize_deck_marketplace_item(deck_item)
        self.assertEqual(serialized["lesson_count"], 1)
        self.assertEqual(serialized["note_count"], 3)
        self.assertEqual(serialized["card_count"], 3)

    def test_compute_deck_item_stats_and_lessons_structure_multi_subdecks(self):
        # Root deck with 2 subdecks (Lesson 1: 5 words, Lesson 2: 10 words)
        root = Deck(name="Minna no Nihongo", owner_user_id=self.user.id)
        db.session.add(root)
        db.session.flush()

        lesson1 = Deck(name="Bài 1", parent_id=root.id, owner_user_id=self.user.id, position=1)
        lesson2 = Deck(name="Bài 2", parent_id=root.id, owner_user_id=self.user.id, position=2)
        db.session.add_all([lesson1, lesson2])
        db.session.flush()

        for i in range(5):
            note = Note(
                note_type_id=self.nt.id,
                user_id=self.user.id,
                deck_id=lesson1.id,
                field_values={"Front": f"L1 Word {i}"},
            )
            db.session.add(note)
            db.session.flush()
            card = Card(note_id=note.id, template_id=self.template.id)
            db.session.add(card)

        for i in range(10):
            note = Note(
                note_type_id=self.nt.id,
                user_id=self.user.id,
                deck_id=lesson2.id,
                field_values={"Front": f"L2 Word {i}"},
            )
            db.session.add(note)
            db.session.flush()
            card = Card(note_id=note.id, template_id=self.template.id)
            db.session.add(card)

        deck_item = DeckMarketplaceItem(
            owner_user_id=self.user.id,
            source_deck_id=root.id,
            title="Minna Shared",
            description="desc",
        )
        db.session.add(deck_item)
        db.session.flush()

        stats = compute_deck_item_stats(deck_item)
        self.assertEqual(stats["lesson_count"], 2)
        self.assertEqual(stats["total_decks"], 3)
        self.assertEqual(stats["note_count"], 15)
        self.assertEqual(stats["card_count"], 15)
        self.assertTrue(stats["has_subdecks"])

        batch_stats = batch_compute_deck_items_stats([deck_item])
        self.assertEqual(batch_stats[deck_item.id]["lesson_count"], 2)
        self.assertEqual(batch_stats[deck_item.id]["note_count"], 15)

        lessons = build_shared_deck_lessons_structure(deck_item)
        self.assertEqual(len(lessons), 3)  # root + lesson1 + lesson2
        root_lesson = next(item for item in lessons if item["is_root"])
        self.assertEqual(root_lesson["name"], "Minna no Nihongo")
        self.assertEqual(root_lesson["total_note_count"], 15)

        l1 = next(item for item in lessons if item["name"] == "Bài 1")
        self.assertEqual(l1["note_count"], 5)
        self.assertEqual(l1["card_count"], 5)

        l2 = next(item for item in lessons if item["name"] == "Bài 2")
        self.assertEqual(l2["note_count"], 10)
        self.assertEqual(l2["card_count"], 10)

    def test_batch_stats_shares_tree_walk_across_overlapping_listings(self):
        root = Deck(name="Root", owner_user_id=self.user.id)
        db.session.add(root)
        db.session.flush()
        child = Deck(name="Child", parent_id=root.id, owner_user_id=self.user.id)
        db.session.add(child)
        db.session.flush()
        grandchild = Deck(
            name="Grandchild",
            parent_id=child.id,
            owner_user_id=self.user.id,
        )
        db.session.add(grandchild)
        db.session.flush()

        for deck in (root, child, grandchild):
            note = Note(
                note_type_id=self.nt.id,
                user_id=self.user.id,
                deck_id=deck.id,
                field_values={"Front": deck.name},
            )
            db.session.add(note)
            db.session.flush()
            db.session.add(Card(note_id=note.id, template_id=self.template.id))

        root_item = DeckMarketplaceItem(
            owner_user_id=self.user.id,
            source_deck_id=root.id,
            title="Root listing",
        )
        child_item = DeckMarketplaceItem(
            owner_user_id=self.user.id,
            source_deck_id=child.id,
            title="Child listing",
        )
        db.session.add_all([root_item, child_item])
        db.session.flush()

        select_statements: list[str] = []

        def _capture_selects(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", _capture_selects)
        try:
            stats = batch_compute_deck_items_stats(
                [root_item, child_item]
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", _capture_selects)

        self.assertEqual(stats[root_item.id]["note_count"], 3)
        self.assertEqual(stats[child_item.id]["note_count"], 2)
        # Three BFS depth queries plus one aggregate each for notes and cards.
        self.assertLessEqual(len(select_statements), 5)


if __name__ == "__main__":
    unittest.main()

