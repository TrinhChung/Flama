"""Unit tests for flashcards_share_repository batch methods."""

import unittest
from app import create_app
from models import db
from models.user import User
from models.deck import Deck
from models.flashcard import (
    Card,
    FieldDef,
    Note,
    NoteType,
    NoteTypeInstall,
    Template,
)
from models.study_application import StudyApplication
from app.repositories import flashcards_share_repository


class FlashcardsShareRepositoryBatchTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )
        self.app_context = self.app.app_context()
        self.app_context.push()
        db.create_all()

        user = User(username="testuser", email="test@example.com")
        user.set_password("password")
        other_user = User(username="otheruser", email="other@example.com")
        other_user.set_password("password")
        db.session.add_all([user, other_user])
        db.session.flush()

        self.user_id = user.id
        self.other_user_id = other_user.id

        self.deck1 = Deck(name="Deck 1", owner_user_id=self.user_id)
        self.deck2 = Deck(name="Deck 2", owner_user_id=self.user_id)
        self.deck_other = Deck(name="Deck Other", owner_user_id=self.other_user_id)
        db.session.add_all([self.deck1, self.deck2, self.deck_other])
        db.session.flush()

        # Note types
        self.nt1 = NoteType(id="nt_test_1", user_id=self.user_id, name="Test NT 1")
        self.nt2 = NoteType(id="nt_test_2", user_id=self.user_id, name="Test NT 2")
        self.nt_installed = NoteType(id="nt_inst_1", user_id=self.user_id, name="Installed NT")
        db.session.add_all([self.nt1, self.nt2, self.nt_installed])
        db.session.flush()

        # Note type install
        nt_install = NoteTypeInstall(
            user_id=self.user_id,
            source_note_type_id="source_nt_remote",
            installed_note_type_id=self.nt_installed.id,
        )
        db.session.add(nt_install)

        # Templates
        self.tpl1 = Template(id="tpl_1", note_type_id=self.nt1.id, name="Card 1")
        self.tpl2 = Template(id="tpl_2", note_type_id=self.nt2.id, name="Card 2")
        db.session.add_all([self.tpl1, self.tpl2])
        db.session.flush()

        # Study application: tpl1 is ACTIVE, tpl2 is RETIRED
        app1 = StudyApplication(
            note_type_id=self.nt1.id,
            template_id=self.tpl1.id,
            occurrence_key="default_1",
            status_code="ACTIVE",
        )
        app2 = StudyApplication(
            note_type_id=self.nt2.id,
            template_id=self.tpl2.id,
            occurrence_key="default_2",
            status_code="RETIRED",
        )
        db.session.add_all([app1, app2])
        db.session.flush()

        # Ensure all applications for nt2 are RETIRED
        StudyApplication.query.filter_by(note_type_id=self.nt2.id).update({"status_code": "RETIRED"})
        db.session.flush()

        # Notes and cards
        # Deck 1 has note1 and note1b (nt1), each with 1 card -> 2 cards total
        note1 = Note(id="note_1", user_id=self.user_id, deck_id=self.deck1.id, note_type_id=self.nt1.id)
        card1a = Card(id="card_1a", note_id="note_1", template_id=self.tpl1.id)
        note1b = Note(id="note_1b", user_id=self.user_id, deck_id=self.deck1.id, note_type_id=self.nt1.id)
        card1b = Card(id="card_1b", note_id="note_1b", template_id=self.tpl1.id)

        # Deck 2 has note2 (nt2) with 1 card
        note2 = Note(id="note_2", user_id=self.user_id, deck_id=self.deck2.id, note_type_id=self.nt2.id)
        card2a = Card(id="card_2a", note_id="note_2", template_id=self.tpl2.id)

        # Deck Other has note_oth with 1 card (should not be counted for user)
        note_other = Note(id="note_oth", user_id=self.other_user_id, deck_id=self.deck_other.id, note_type_id=self.nt1.id)
        card_oth = Card(id="card_oth", note_id="note_oth", template_id=self.tpl1.id)

        db.session.add_all([note1, card1a, note1b, card1b, note2, card2a, note_other, card_oth])
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.app_context.pop()

    def test_batch_get_cards_count_by_deck_ids(self):
        counts = flashcards_share_repository.batch_get_cards_count_by_deck_ids(
            user_id=self.user_id,
            deck_ids=[self.deck1.id, self.deck2.id, self.deck_other.id, 99999],
        )
        self.assertEqual(counts.get(self.deck1.id), 2)
        self.assertEqual(counts.get(self.deck2.id), 1)
        # deck_other belongs to other user, so count for this user must be 0 (or not present)
        self.assertNotIn(self.deck_other.id, counts)
        self.assertNotIn(99999, counts)

    def test_batch_get_cards_count_empty_deck_ids(self):
        counts = flashcards_share_repository.batch_get_cards_count_by_deck_ids(
            user_id=self.user_id,
            deck_ids=[],
        )
        self.assertEqual(counts, {})

    def test_batch_get_deck_note_types(self):
        deck_nt_map = flashcards_share_repository.batch_get_deck_note_types(
            user_id=self.user_id,
            deck_ids=[self.deck1.id, self.deck2.id],
        )
        self.assertEqual(deck_nt_map.get(self.deck1.id), {self.nt1.id})
        self.assertEqual(deck_nt_map.get(self.deck2.id), {self.nt2.id})

    def test_batch_get_deck_note_types_empty(self):
        deck_nt_map = flashcards_share_repository.batch_get_deck_note_types(
            user_id=self.user_id,
            deck_ids=[],
        )
        self.assertEqual(deck_nt_map, {})

    def test_batch_get_installed_note_type_ids(self):
        installed = flashcards_share_repository.batch_get_installed_note_type_ids(
            [self.nt1.id, self.nt_installed.id, "non_existent"]
        )
        self.assertEqual(installed, {self.nt_installed.id})

    def test_batch_get_installed_note_type_ids_empty(self):
        installed = flashcards_share_repository.batch_get_installed_note_type_ids([])
        self.assertEqual(installed, set())

    def test_batch_get_active_template_note_type_ids(self):
        # nt1 has ACTIVE template, nt2 has DRAFT template
        active = flashcards_share_repository.batch_get_active_template_note_type_ids(
            [self.nt1.id, self.nt2.id, "non_existent"]
        )
        self.assertEqual(active, {self.nt1.id})

    def test_batch_get_active_template_note_type_ids_empty(self):
        active = flashcards_share_repository.batch_get_active_template_note_type_ids([])
        self.assertEqual(active, set())


if __name__ == "__main__":
    unittest.main()
