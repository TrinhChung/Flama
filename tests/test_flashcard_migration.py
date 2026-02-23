"""Migration command tests for legacy -> flashcard v2 backfill."""

import unittest

from app import create_app
from models import db
from models.flashcard import LegacyMigrationMap, Note, NoteType
from models.user import User
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_entry import VocabularyEntry
from models.vocabulary_progress import VocabularyProgress


class FlashcardMigrationCommandTests(unittest.TestCase):
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
            user = User(username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = VocabularyDeck(name="Legacy Deck")
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id

            entry1 = VocabularyEntry(
                deck_id=deck.id,
                deck="Legacy Deck",
                word="犬",
                reading="いぬ",
                translation_vi="dog",
                meaning_jp="<b>犬</b>",
            )
            entry2 = VocabularyEntry(
                deck_id=deck.id,
                deck="Legacy Deck",
                word="猫",
                reading="ねこ",
                translation_vi="cat",
                meaning_jp="<b>猫</b>",
            )
            db.session.add_all([entry1, entry2])
            db.session.flush()
            self.entry_ids = [entry1.id, entry2.id]

            progress1 = VocabularyProgress(user_id=user.id, entry_id=entry1.id, queue="new")
            progress2 = VocabularyProgress(user_id=user.id, entry_id=entry2.id, queue="review")
            db.session.add_all([progress1, progress2])
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_legacy_backfill_command_maps_notes_cards_and_progress(self):
        result = self.runner.invoke(
            args=["flashcard-migrate-legacy", "--user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            legacy_nt = NoteType.query.filter_by(user_id=self.user_id, name="Legacy Japanese").first()
            self.assertIsNotNone(legacy_nt)
            note_count = Note.query.filter_by(note_type_id=legacy_nt.id, user_id=self.user_id).count()
            self.assertEqual(note_count, 2)

            map_count = LegacyMigrationMap.query.count()
            self.assertEqual(map_count, 2)

            mapped_progress = VocabularyProgress.query.filter(
                VocabularyProgress.entry_id.isnot(None),
                VocabularyProgress.new_card_id.isnot(None),
            ).count()
            self.assertEqual(mapped_progress, 2)

            sample_note = Note.query.filter_by(note_type_id=legacy_nt.id).first()
            self.assertEqual(sample_note.field_values.get("Word"), "犬")
            self.assertEqual(sample_note.field_values.get("Reading"), "いぬ")

    def test_dry_run_rolls_back(self):
        result = self.runner.invoke(
            args=["flashcard-migrate-legacy", "--user-id", str(self.user_id), "--dry-run"],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)
        with self.app.app_context():
            self.assertEqual(LegacyMigrationMap.query.count(), 0)
            self.assertEqual(Note.query.count(), 0)
            mapped_progress = VocabularyProgress.query.filter(
                VocabularyProgress.new_card_id.isnot(None)
            ).count()
            self.assertEqual(mapped_progress, 0)


if __name__ == "__main__":
    unittest.main()
