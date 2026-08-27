"""Tests for Marketplace Taxonomy & Smart Category/Topic Filtering."""

import unittest
from app import create_app
from models import db
from models.user import User
from models.flashcard import DeckMarketplaceItem, NoteType, Deck, DeckRelease
from app.services import marketplace_taxonomy_service


class MarketplaceTaxonomyFilterTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": True,
                "STARTUP_RUN_DB_CREATE_ALL": True,
                "STARTUP_RUN_DEFAULT_TAXONOMY_SEED": True,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            # Create user
            self.user = User(email="author@example.com", username="author1", password_hash="hashed_test_pw", is_admin=False)
            db.session.add(self.user)
            db.session.commit()

            # Create DeckMarketplaceItems with rich taxonomy
            deck1 = Deck(name="Minna No Nihongo N5", owner_user_id=self.user.id)
            db.session.add(deck1)
            db.session.commit()

            self.item_n5 = DeckMarketplaceItem(
                id="deck-item-n5",
                owner_user_id=self.user.id,
                source_deck_id=deck1.id,
                title="Minna No Nihongo Bài 1-25 N5",
                description="Bộ thẻ học từ vựng và Kanji trình độ N5 cơ bản",
                primary_category="Tiếng Nhật",
                tags=["n5", "minna", "vocabulary"],
                pricing_mode="free",
                publish_status="published",
                taxonomy_metadata={
                    "domain": "language_learning",
                    "subject": "japanese",
                    "framework": "jlpt",
                    "framework_level": "n5",
                    "difficulty_band": "beginner",
                    "primary_topics": ["vocabulary", "kanji"],
                    "learning_goals": ["daily_communication", "exam_pass"],
                },
            )

            deck2 = Deck(name="IELTS Academic Vocabulary", owner_user_id=self.user.id)
            db.session.add(deck2)
            db.session.commit()

            self.item_ielts = DeckMarketplaceItem(
                id="deck-item-ielts",
                owner_user_id=self.user.id,
                source_deck_id=deck2.id,
                title="IELTS 3000 Essential Words",
                description="Từ vựng IELTS học thuật 7.0+",
                primary_category="Tiếng Anh",
                tags=["ielts", "academic", "vocabulary"],
                pricing_mode="paid",
                price_amount_minor=50000,
                publish_status="published",
                taxonomy_metadata={
                    "domain": "language_learning",
                    "subject": "english",
                    "framework": "ielts",
                    "framework_level": "ielts_7_0",
                    "difficulty_band": "advanced",
                    "primary_topics": ["vocabulary"],
                    "learning_goals": ["academic_study", "exam_pass"],
                },
            )

            deck3 = Deck(name="AWS Solutions Architect", owner_user_id=self.user.id)
            db.session.add(deck3)
            db.session.commit()

            self.item_aws = DeckMarketplaceItem(
                id="deck-item-aws",
                owner_user_id=self.user.id,
                source_deck_id=deck3.id,
                title="AWS SAA-C03 Flashcards",
                description="Bộ thẻ ôn thi chứng chỉ AWS Cloud Architect",
                primary_category="Công nghệ thông tin",
                tags=["aws", "cloud", "exam"],
                pricing_mode="free",
                publish_status="published",
                taxonomy_metadata={
                    "domain": "certification",
                    "subject": "aws",
                    "framework": "aws_cert",
                    "framework_level": "aws_saa",
                    "difficulty_band": "intermediate",
                    "primary_topics": ["compute"],
                    "learning_goals": ["exam_prep"],
                },
            )

            db.session.add_all([self.item_n5, self.item_ielts, self.item_aws])
            db.session.commit()

            self.user_id = self.user.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user_id)
            sess["_fresh"] = True

    def test_filter_by_smart_category_pill(self):
        self._login()

        # 1. Filter by "JLPT N5" -> should match item_n5 via framework & level
        resp = self.client.get("/api/shared/decks?category=JLPT+N5")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "deck-item-n5")

        # 2. Filter by "Tiếng Anh" -> should match item_ielts via primary_category / subject
        resp = self.client.get("/api/shared/decks?category=Ti%E1%BA%BFng+Anh")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "deck-item-ielts")

        # 3. Filter by "Kanji" -> should match item_n5 via primary_topics
        resp = self.client.get("/api/shared/decks?category=Kanji")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "deck-item-n5")

        # 4. Filter by "AWS" -> should match item_aws via tag/framework
        resp = self.client.get("/api/shared/decks?category=AWS")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "deck-item-aws")

    def test_filter_by_explicit_taxonomy_params(self):
        self._login()

        # Filter by domain="certification"
        resp = self.client.get("/api/shared/decks?domain=certification")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "deck-item-aws")

        # Filter by subject="japanese" and difficulty_band="beginner"
        resp = self.client.get("/api/shared/decks?subject=japanese&difficulty_band=beginner")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "deck-item-n5")

        # Filter by pricing_mode="paid"
        resp = self.client.get("/api/shared/decks?pricing_mode=paid")
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], "deck-item-ielts")


if __name__ == "__main__":
    unittest.main()
