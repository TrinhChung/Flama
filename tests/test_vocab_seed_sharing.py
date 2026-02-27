"""Tests for vocab-seed marketplace auto-sharing behavior."""

import shutil
import tempfile
import unittest
from pathlib import Path

from app import create_app
from models import db
from models.flashcard import DeckMarketplaceItem
from models.user import User
from models.vocabulary_deck import VocabularyDeck


class VocabSeedSharingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        self.runner = self.app.test_cli_runner()
        with self.app.app_context():
            db.create_all()
            user = User(username="seed-owner", email="seed-owner@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

        self.seed_dir = Path(tempfile.mkdtemp(prefix="flama-seed-"))
        unit_dir = self.seed_dir / "Unit 1"
        unit_dir.mkdir(parents=True, exist_ok=True)
        (unit_dir / "Lesson 1.csv").write_text(
            "deck,word,reading,translation_vi\n"
            "Unit 1,犬,いぬ,dog\n"
            "Unit 1,猫,ねこ,cat\n",
            encoding="utf-8",
        )
        (unit_dir / "Lesson 2.csv").write_text(
            "deck,word,reading,translation_vi\n"
            "Unit 1,鳥,とり,bird\n",
            encoding="utf-8",
        )
        chapter_dir = unit_dir / "Chapter A"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        (chapter_dir / "Lesson 3.csv").write_text(
            "deck,word,reading,translation_vi\n"
            "Unit 1,魚,さかな,fish\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.seed_dir, ignore_errors=True)
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_vocab_seed_auto_shares_only_top_level_deck_by_default(self):
        result = self.runner.invoke(
            args=["vocab-seed", "--path", str(self.seed_dir), "--owner-user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            shared_items = DeckMarketplaceItem.query.all()
            self.assertEqual(len(shared_items), 1)
            item = shared_items[0]
            top_deck = VocabularyDeck.query.filter_by(name="Unit 1", parent_id=None).first()
            self.assertIsNotNone(top_deck)
            self.assertEqual(item.owner_user_id, self.user_id)
            self.assertEqual(item.publish_status, "published")
            self.assertTrue(item.is_official)
            self.assertEqual(item.pricing_mode, "free")
            self.assertEqual(item.source_deck_id, top_deck.id)

    def test_vocab_seed_can_disable_auto_share(self):
        result = self.runner.invoke(
            args=[
                "vocab-seed",
                "--path",
                str(self.seed_dir),
                "--owner-user-id",
                str(self.user_id),
                "--no-share-seeded-decks",
            ],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            self.assertEqual(DeckMarketplaceItem.query.count(), 0)


if __name__ == "__main__":
    unittest.main()
