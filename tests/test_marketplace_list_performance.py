"""List contract parity and bounded catalog hydration/payload regressions."""

import json
import unittest
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy import event
from werkzeug.datastructures import MultiDict

from app import create_app
from app.services.marketplace_list_service import list_shared_decks
from app.services.marketplace_note_type_service import list_shared_note_types
from models import db
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.template import Template
from models.user import User


class MarketplaceListPerformanceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.learner = User(username="list-learner", email="list-learner@example.com")
        self.authors = [User(username=f"list-author-{i}", email=f"list-author-{i}@example.com") for i in range(20)]
        db.session.add_all([self.learner, *self.authors])
        db.session.flush()
        self.learner_id = self.learner.id
        self.author_ids = [author.id for author in self.authors]

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _seed_note_types(self, public=40, private=120):
        rows = []
        for i in range(public + private):
            row = NoteType(
                user_id=self.author_ids[i % len(self.author_ids)],
                name=f"Japanese Vocab {i}", primary_category="JLPT N5",
                publish_status="published" if i < public else "private",
                pricing_mode="paid" if i % 2 else "free",
                price_amount_minor=50000 if i % 2 else 0,
                install_count=i % 5, active_usage_count=i % 7,
                rating_avg=float(i % 5), rating_count=i % 3,
                created_at=datetime(2026, 1, 1) + timedelta(days=i % 5),
                updated_at=datetime(2026, 2, 1) + timedelta(days=i % 3),
            )
            db.session.add(row)
            db.session.flush()
            db.session.add(FieldDef(note_type_id=row.id, name="Word", field_type="text", position=0))
            db.session.add(Template(note_type_id=row.id, name="Card", front_html="{{Word}}" + "x" * 8192, back_html="{{Word}}", position=0))
            rows.append(row)
        for name, status, owner in (("Own private", "private", self.learner_id), ("Own archive", "archived", self.learner_id), ("Unlisted", "unlisted", self.author_ids[0])):
            row = NoteType(user_id=owner, name=name, publish_status=status)
            db.session.add(row)
            rows.append(row)
        db.session.flush()
        installed = NoteType(user_id=self.learner_id, name="Installed copy", publish_status="private")
        db.session.add(installed)
        db.session.flush()
        db.session.add(NoteTypeInstall(user_id=self.learner_id, source_note_type_id=rows[0].id, installed_note_type_id=installed.id))
        db.session.commit()
        db.session.expunge_all()

    def _measure_note_list(self, args):
        counts = Counter()
        def loaded(_session, instance):
            counts[type(instance).__name__] += 1
        def query(_conn, _cursor, statement, _parameters, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                counts["selects"] += 1
        session = db.session()
        event.listen(session, "loaded_as_persistent", loaded)
        event.listen(db.engine, "before_cursor_execute", query)
        try:
            payload = list_shared_note_types(user_id=self.learner_id, args=MultiDict(args))
        finally:
            event.remove(session, "loaded_as_persistent", loaded)
            event.remove(db.engine, "before_cursor_execute", query)
        db.session.expunge_all()
        return payload, counts

    def test_compact_pages_do_not_hydrate_private_rows_or_template_source(self):
        self._seed_note_types(public=100, private=500)
        small, small_counts = self._measure_note_list({"compact": "1", "page_size": "8"})
        large, large_counts = self._measure_note_list({"compact": "1", "page_size": "80"})
        self.assertEqual(small["pagination"]["total"], 104)
        self.assertEqual(small_counts["NoteType"], 8)
        self.assertEqual(large_counts["NoteType"], 80)
        self.assertEqual(small_counts["Template"] + large_counts["Template"], 0)
        self.assertEqual(small_counts["FieldDef"] + large_counts["FieldDef"], 0)
        # Author count grows, SQL count does not grow per card.
        self.assertLessEqual(large_counts["selects"], small_counts["selects"] + 2)
        self.assertLessEqual(large_counts["selects"], 12)
        self.assertNotIn("templates", large["items"][0])
        self.assertNotIn("field_defs", large["items"][0])
        self.assertLess(len(json.dumps(large)), 300000)

    def test_compact_search_filters_and_paging_match_legacy_list(self):
        self._seed_note_types(public=18, private=8)
        for sort in ("popular", "top_rated", "newest", "recently_updated"):
            for filters in ({}, {"q": "Japanese N5"}, {"category": "JLPT N5"}, {"subject": "japanese", "pricing_mode": "paid", "min_price": "50,000 VNĐ"}):
                args = {"sort": sort, **filters}
                legacy = list_shared_note_types(user_id=self.learner_id, args=MultiDict(args))
                collected = []
                page = 1
                while True:
                    compact = list_shared_note_types(user_id=self.learner_id, args=MultiDict({**args, "compact": "1", "page": str(page), "page_size": "5"}))
                    collected.extend(compact["items"])
                    self.assertEqual(compact["pagination"]["total"], len(legacy["items"]))
                    if not compact["pagination"]["has_more"]:
                        break
                    page += 1
                self.assertEqual([item["id"] for item in collected], [item["id"] for item in legacy["items"]])
                for compact_row, full_row in zip(collected, legacy["items"]):
                    for key in ("author", "is_owner", "is_installed", "installed_note_type_id", "taxonomy_metadata", "price_display"):
                        self.assertEqual(compact_row[key], full_row[key])
                if not filters:
                    self.assertTrue(any(row["is_owner"] and row["publish_status"] == "archived" for row in collected))
                    self.assertTrue(any(row["publish_status"] == "unlisted" for row in collected))
                    self.assertTrue(any(row["is_installed"] for row in collected))
                    self.assertIn("templates", legacy["items"][0])

    def test_curated_pages_keep_full_category_counts_and_all_other_items(self):
        for category in range(10):
            for i in range(7):
                db.session.add(DeckMarketplaceItem(owner_user_id=self.author_ids[i], title=f"Category {category} deck {i}", primary_category=f"Category {category}", publish_status="published", active_usage_count=i))
        for i in range(29):
            db.session.add(DeckMarketplaceItem(owner_user_id=self.author_ids[0], title=f"Other {i}", primary_category=f"Other category {i}", publish_status="published"))
        for i in range(100):
            db.session.add(DeckMarketplaceItem(owner_user_id=self.author_ids[0], title=f"Private {i}", publish_status="private"))
        db.session.commit()
        db.session.expunge_all()
        sections = []
        others = []
        page = 1
        loaded_decks = []
        session = db.session()
        def loaded(_session, instance):
            if isinstance(instance, DeckMarketplaceItem):
                loaded_decks.append(instance.id)
        event.listen(session, "loaded_as_persistent", loaded)
        while True:
            before = len(loaded_decks)
            payload = list_shared_decks(user_id=self.learner_id, args=MultiDict({"compact": "1", "curated": "1", "page": str(page), "page_size": "24"}))
            self.assertEqual(payload["pagination"]["total"], 99)
            self.assertLessEqual(len(payload["items"]), 48)
            self.assertLessEqual(len(loaded_decks) - before, 48)
            curated = payload["curated_sections"]
            self.assertEqual(curated["other_total"], 29)
            sections.extend(curated["major_sections"])
            others.extend(curated["other_item_ids"])
            if not payload["pagination"]["has_more"]:
                break
            page += 1
            db.session.expunge_all()
        event.remove(session, "loaded_as_persistent", loaded)
        self.assertEqual(len(sections), 10)
        self.assertEqual(len({section["category"] for section in sections}), 10)
        self.assertTrue(all(section["total"] == 7 and len(section["item_ids"]) == 4 for section in sections))
        self.assertEqual(len(set(others)), 29)

    def test_deck_pricing_and_python_taxonomy_pages_match_legacy_contract(self):
        for i in range(20):
            db.session.add(DeckMarketplaceItem(owner_user_id=self.author_ids[0], title=f"JLPT N5 {i}", primary_category="Japanese", publish_status="unlisted" if i == 0 else "published", pricing_mode="paid" if i % 2 else "free", price_amount_minor=50000 if i % 2 else 0, active_usage_count=i % 3))
        db.session.add(DeckMarketplaceItem(owner_user_id=self.learner_id, title="Own archive", publish_status="archived"))
        db.session.add(DeckMarketplaceItem(owner_user_id=self.author_ids[0], title="Private", publish_status="private"))
        db.session.commit()
        for filters in ({}, {"pricing_mode": "paid"}, {"subject": "japanese", "framework_level": "n5"}, {"q": "N5", "category": "Japanese"}):
            legacy = list_shared_decks(user_id=self.learner_id, args=MultiDict(filters))
            first = list_shared_decks(user_id=self.learner_id, args=MultiDict({**filters, "compact": "1", "page_size": "10"}))
            self.assertEqual(first["pagination"]["total"], len(legacy["items"]))
            self.assertEqual(first["items"], legacy["items"][:10])

    def test_page_bounds_cannot_expand_the_response_or_overflow_sql_offsets(self):
        self._seed_note_types(public=105, private=2)
        for page_size in ("50000", "0", "broken"):
            payload = list_shared_note_types(user_id=self.learner_id, args=MultiDict({"compact": "1", "page": "0", "page_size": page_size}))
            self.assertEqual(payload["pagination"]["page"], 1)
            self.assertLessEqual(len(payload["items"]), 100)
        args = MultiDict({"compact": "1", "page": str(10**30)})
        self.assertEqual(list_shared_note_types(user_id=self.learner_id, args=args)["items"], [])
        self.assertEqual(list_shared_decks(user_id=self.learner_id, args=args)["items"], [])


if __name__ == "__main__":
    unittest.main()
