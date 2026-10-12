"""Unit tests for flashcards_share_repository batch methods."""

import unittest
from datetime import datetime
from sqlalchemy import event
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
from tests.study_note_fixtures import attach_template, create_note_user


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

        user = create_note_user(db.session, username="testuser", email="test@example.com")
        user.set_password("password")
        other_user = create_note_user(db.session, username="otheruser", email="other@example.com")
        other_user.set_password("password")
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
        self.tpl1 = attach_template(db.session, id="tpl_1", owner_user_id=self.user_id, note_type_id=self.nt1.id, name="Card 1")
        self.tpl2 = attach_template(db.session, id="tpl_2", owner_user_id=self.user_id, note_type_id=self.nt2.id, name="Card 2")
        StudyApplication.query.filter_by(note_type_id=self.nt2.id).one().status_code = "RETIRED"

        # Notes and derived presentations
        # Deck 1 has note1 and note1b (nt1), each with 1 card -> 2 cards total
        note1 = Note(id="note_1", user_id=self.user_id, deck_id=self.deck1.id, note_type_id=self.nt1.id)
        note1b = Note(id="note_1b", user_id=self.user_id, deck_id=self.deck1.id, note_type_id=self.nt1.id)

        # Deck 2 has note2 (nt2) with 1 card
        note2 = Note(id="note_2", user_id=self.user_id, deck_id=self.deck2.id, note_type_id=self.nt2.id)

        # Deck Other has note_oth with 1 card (should not be counted for user)
        note_other = Note(id="note_oth", user_id=self.other_user_id, deck_id=self.deck_other.id, note_type_id=self.nt1.id)

        db.session.add_all([note1, note1b, note2, note_other])
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
        self.assertEqual(counts.get(self.deck2.id, 0), 0)
        # deck_other belongs to other user, so count for this user must be 0 (or not present)
        self.assertNotIn(self.deck_other.id, counts)
        self.assertNotIn(99999, counts)

    def test_batch_get_cards_count_empty_deck_ids(self):
        counts = flashcards_share_repository.batch_get_cards_count_by_deck_ids(
            user_id=self.user_id,
            deck_ids=[],
        )
        self.assertEqual(counts, {})

    def test_combined_publish_facts_match_separate_queries_and_preserve_zero_card_note_types(self):
        extra_template = attach_template(db.session, owner_user_id=self.user_id, id="extra_tpl", note_type_id=self.nt1.id, name="Extra presentation")
        zero_card_deck = Deck(name="Zero card notes", owner_user_id=self.user_id)
        empty_deck = Deck(name="Empty", owner_user_id=self.user_id)
        deleted_deck = Deck(name="Deleted", owner_user_id=self.user_id, deleted_at=datetime.now())
        db.session.add_all([extra_template, zero_card_deck, empty_deck, deleted_deck])
        db.session.flush()
        db.session.add_all([
            Note(id="zero_mixed", user_id=self.user_id, deck_id=self.deck1.id, note_type_id=self.nt2.id),
            Note(id="zero_only", user_id=self.user_id, deck_id=zero_card_deck.id, note_type_id=self.nt_installed.id),
            Note(id="foreign_in_scope", user_id=self.other_user_id, deck_id=self.deck1.id, note_type_id=self.nt_installed.id),
            Note(id="outside_scope", user_id=self.user_id, deck_id=deleted_deck.id, note_type_id=self.nt_installed.id),
        ])
        db.session.commit()
        scope = [self.deck1.id, self.deck2.id, zero_card_deck.id, empty_deck.id, self.deck1.id, None]
        counts, note_types = flashcards_share_repository.batch_get_deck_publish_facts(
            user_id=self.user_id, deck_ids=scope,
        )
        self.assertEqual(counts, flashcards_share_repository.batch_get_cards_count_by_deck_ids(user_id=self.user_id, deck_ids=scope))
        self.assertEqual(note_types, flashcards_share_repository.batch_get_deck_note_types(user_id=self.user_id, deck_ids=scope))
        self.assertEqual(counts[self.deck1.id], 4)  # Two active Templates on two Notes.
        self.assertEqual(note_types[self.deck1.id], {self.nt1.id, self.nt2.id})
        self.assertEqual(note_types[zero_card_deck.id], {self.nt_installed.id})
        self.assertNotIn(zero_card_deck.id, counts)
        self.assertNotIn(empty_deck.id, note_types)
        self.assertNotIn(deleted_deck.id, note_types)
        self.assertNotIn(self.deck_other.id, counts)

    def test_combined_publish_facts_empty_scope(self):
        self.assertEqual(flashcards_share_repository.batch_get_deck_publish_facts(user_id=self.user_id, deck_ids=[]), ({}, {}))

    def test_publish_options_thousand_decks_keep_sql_bounded_and_roll_up_deep_chain(self):
        from app.services import flashcards_share_service
        from app.services.share import publish

        size = 1100
        first_id = 10000
        db.session.bulk_insert_mappings(Deck, [
            {
                "id": first_id + index, "owner_user_id": self.user_id,
                "name": f"Deep deck {index}",
                "parent_id": first_id + index - 1 if index else None,
            }
            for index in range(size)
        ])
        leaf_note = Note(
            id="deep_leaf", user_id=self.user_id, deck_id=first_id + size - 1,
            note_type_id=self.nt1.id,
        )
        db.session.add(leaf_note)
        db.session.flush()
        self.assertEqual(Card.query.filter_by(note_id=leaf_note.id).count(), 1)
        db.session.commit()
        db.session.remove()
        queries = []
        engine = db.engine

        def record_query(_connection, _cursor, statement, _parameters, _context, _executemany):
            queries.append(statement)

        event.listen(engine, "before_cursor_execute", record_query)
        try:
            result = flashcards_share_service.build_deck_publish_options(user_id=self.user_id)
        finally:
            event.remove(engine, "before_cursor_execute", record_query)
        self.assertLessEqual(len(queries), 7, queries)
        self.assertTrue(all(sql.lstrip().upper().startswith("SELECT") for sql in queries))
        self.assertEqual(sum("GROUP BY notes.deck_id, notes.note_type_id" in sql for sql in queries), 1)
        items = {item["id"]: item for item in result["items"]}
        self.assertEqual(len(items), size + 2)
        self.assertEqual(items[first_id]["card_count"], 1)
        self.assertEqual(items[first_id + size - 1]["card_count"], 1)
        self.assertEqual(result, publish.build_deck_publish_options(user_id=self.user_id))

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
