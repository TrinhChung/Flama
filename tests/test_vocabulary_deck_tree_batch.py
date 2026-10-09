import unittest
from datetime import datetime, timezone

from sqlalchemy import event

from app import create_app
from app.repositories import vocabulary_repository
from app.repositories.deck_tree_query import query_accessible_stats_decks
from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.flashcard import Card, Note, NoteType, Template
from models.user import User


class VocabularyDeckTreeBatchTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        owner = User(username="owner", email="owner@example.com")
        owner.set_password("password")
        learner = User(username="learner", email="learner@example.com")
        learner.set_password("password")
        db.session.add_all([owner, learner])
        db.session.flush()
        self.owner_id = owner.id
        self.learner_id = learner.id

        # Create note type & template
        nt = NoteType(name="Standard", user_id=owner.id)
        db.session.add(nt)
        db.session.flush()
        tmpl = Template(name="Card 1", note_type_id=nt.id)
        db.session.add(tmpl)
        db.session.flush()

        self.note_type_id = nt.id
        self.template_id = tmpl.id

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_empty_stats_scope_does_not_hydrate_foreign_decks(self):
        db.session.add_all([
            Deck(name=f"Foreign {index}", owner_user_id=self.owner_id)
            for index in range(100)
        ])
        db.session.commit()
        db.session.expunge_all()
        loaded = []

        def capture(deck, _context):
            loaded.append(deck.id)

        event.listen(Deck, "load", capture)
        try:
            result = query_accessible_stats_decks(user_id=self.learner_id, admin_mode=False)
        finally:
            event.remove(Deck, "load", capture)
        self.assertEqual(result, [])
        self.assertEqual(loaded, [])

    def test_stats_fallback_preserves_progress_scope_order_and_deleted_filter(self):
        parent = Deck(name="Legacy parent", owner_user_id=None, position=10)
        other = Deck(name="Progress deck", owner_user_id=self.owner_id, position=1)
        deleted = Deck(name="Deleted", deleted_at=datetime(2026, 1, 1))
        unrelated = Deck(name="Unrelated", owner_user_id=self.owner_id)
        db.session.add_all([parent, other, deleted, unrelated])
        db.session.flush()
        child = Deck(name="Legacy child", parent_id=parent.id, owner_user_id=None, position=0)
        db.session.add(child)
        db.session.flush()
        for deck in (parent, other, child, deleted):
            note = Note(user_id=self.owner_id, deck_id=deck.id, note_type_id=self.note_type_id)
            db.session.add(note)
            db.session.flush()
            card = Card(note_id=note.id, template_id=self.template_id)
            db.session.add(card)
            db.session.flush()
            db.session.add(CardProgress(user_id=self.learner_id, card_id=card.id))
        expected = [other.id, parent.id, child.id]
        db.session.commit()
        db.session.expunge_all()
        loaded = []

        def capture(deck, _context):
            loaded.append(deck.id)

        event.listen(Deck, "load", capture)
        try:
            result = query_accessible_stats_decks(user_id=self.learner_id, admin_mode=False)
        finally:
            event.remove(Deck, "load", capture)
        self.assertEqual([deck.id for deck in result], expected)
        self.assertCountEqual(loaded, expected)

    def test_batch_deck_tree_queries_and_counts_with_multiple_installs(self):
        # Create 5 source decks with notes and cards
        # And 5 installed local decks for learner
        num_installs = 5
        installs: list[DeckInstall] = []

        for i in range(num_installs):
            src_deck = Deck(name=f"Source Deck {i}", owner_user_id=self.owner_id, position=i)
            local_deck = Deck(name=f"Local Deck {i}", owner_user_id=self.learner_id, position=i)
            db.session.add_all([src_deck, local_deck])
            db.session.flush()

            m_item = DeckMarketplaceItem(
                title=f"Shared {i}",
                owner_user_id=self.owner_id,
                source_deck_id=src_deck.id,
                source_note_type_id=str(self.note_type_id),
            )
            db.session.add(m_item)
            db.session.flush()

            install = DeckInstall(
                deck_item_id=m_item.id,
                user_id=self.learner_id,
                local_deck_id=local_deck.id,
                clone_mode="logical_overlay",
                source_deck_id=src_deck.id,
                source_note_type_id=str(self.note_type_id),
                source_owner_user_id=self.owner_id,
                base_snapshot_at=datetime(2099, 1, 1),
            )
            db.session.add(install)
            db.session.flush()
            installs.append(install)

            # Map source to local
            clone_map = DeckCloneDeckMap(
                deck_install_id=str(install.id),
                local_deck_id=local_deck.id,
                source_deck_id=src_deck.id,
            )
            db.session.add(clone_map)

            # Add notes and cards to source deck (3 cards per deck = 15 total)
            for n_idx in range(3):
                note = Note(
                    deck_id=src_deck.id,
                    note_type_id=self.note_type_id,
                    user_id=self.owner_id,
                )
                db.session.add(note)
                db.session.flush()
                card = Card(
                    note_id=note.id,
                    template_id=self.template_id,
                )
                db.session.add(card)
                db.session.flush()

                # For the first card in each deck, simulate a learning progress
                if n_idx == 0:
                    prog = CardProgress(
                        user_id=self.learner_id,
                        card_id=card.id,
                        queue="learn",
                        due_at=datetime.now(timezone.utc).replace(tzinfo=None),
                    )
                    db.session.add(prog)

        db.session.commit()

        # Capture queries
        db.session.expire_all()
        select_statements: list[str] = []

        def _capture_selects(_conn, _cursor, statement, _params, _context, _many):
            if statement.lstrip().upper().startswith("SELECT"):
                select_statements.append(statement)

        event.listen(db.engine, "before_cursor_execute", _capture_selects)
        try:
            tree_payload = vocabulary_repository.build_browse_deck_tree_payload(
                user_id=self.learner_id,
                admin_mode=False,
            )
        finally:
            event.remove(db.engine, "before_cursor_execute", _capture_selects)

        # Verify tree payload returned
        self.assertIsNotNone(tree_payload)
        self.assertEqual(len(tree_payload), num_installs)

        # Verify card counts per deck:
        # Total: 3, New: 2, Learn: 1, Due: 0
        for node in tree_payload:
            self.assertEqual(node["counts"]["total"], 3)
            self.assertEqual(node["counts"]["new"], 2)
            self.assertEqual(node["counts"]["learn"], 1)
            self.assertEqual(node["counts"]["due"], 0)

        # Check total SELECT statements executed:
        # With 5 installs, exactly 1 batch query for maps and 1 batch query for counts
        # (Total 11 queries across the entire tree building operation regardless of M installs)
        self.assertEqual(len(select_statements), 11)

    def test_overlap_guard_fallback_on_cross_install_overlap(self):
        # Simulate edge-case where two installs map the same source_deck_id
        src_deck = Deck(name="Shared Source", owner_user_id=self.owner_id, position=0)
        local_deck_1 = Deck(name="Local 1", owner_user_id=self.learner_id, position=1)
        local_deck_2 = Deck(name="Local 2", owner_user_id=self.learner_id, position=2)
        db.session.add_all([src_deck, local_deck_1, local_deck_2])
        db.session.flush()

        m_item_1 = DeckMarketplaceItem(title="M1", owner_user_id=self.owner_id)
        m_item_2 = DeckMarketplaceItem(title="M2", owner_user_id=self.owner_id)
        db.session.add_all([m_item_1, m_item_2])
        db.session.flush()

        inst1 = DeckInstall(
            deck_item_id=m_item_1.id,
            user_id=self.learner_id,
            local_deck_id=local_deck_1.id,
            clone_mode="logical_overlay",
            source_deck_id=src_deck.id,
            base_snapshot_at=datetime(2099, 1, 1),
        )
        inst2 = DeckInstall(
            deck_item_id=m_item_2.id,
            user_id=self.learner_id,
            local_deck_id=local_deck_2.id,
            clone_mode="logical_overlay",
            source_deck_id=src_deck.id,
            base_snapshot_at=datetime(2099, 1, 1),
        )
        db.session.add_all([inst1, inst2])
        db.session.flush()

        # Both map to src_deck.id
        db.session.add(DeckCloneDeckMap(deck_install_id=str(inst1.id), local_deck_id=local_deck_1.id, source_deck_id=src_deck.id))
        db.session.add(DeckCloneDeckMap(deck_install_id=str(inst2.id), local_deck_id=local_deck_2.id, source_deck_id=src_deck.id))

        note = Note(deck_id=src_deck.id, note_type_id=self.note_type_id, user_id=self.owner_id)
        db.session.add(note)
        db.session.flush()
        db.session.add(Card(note_id=note.id, template_id=self.template_id))
        db.session.commit()

        tree_payload = vocabulary_repository.build_browse_deck_tree_payload(
            user_id=self.learner_id,
            admin_mode=False,
        )
        self.assertIsNotNone(tree_payload)
        self.assertEqual(len(tree_payload), 2)


if __name__ == "__main__":
    unittest.main()
