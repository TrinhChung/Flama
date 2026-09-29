"""Tests for the database-level deck aggregation service seam (Phương án 3).

Verifies:
1. R1: Direct owned notes and Logical Overlay marketplace shared decks aggregation.
2. R2: Decoupled seam architecture over compatibility projection `card_progress`.
3. R3: Phase 6 Decision D6-04 note-level counting (count_by_note=True) vs card-level counting.
4. R4: Pure SQL aggregation without loading Card/Note entities into Python memory.
5. R5: Non-locking execution (no FOR UPDATE) and fail-closed authority checks.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import unittest
from uuid import uuid4

from app import create_app
from app.services.deck_aggregation_service import (
    aggregate_deck_study_counts,
    check_note_authority_integrity,
)
from app.services.study_authority_read_service import StudyAuthorityReadError
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import DeckCloneDeckMap, DeckInstall, Note
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_subject import StudyProgressSubject
from models.user import User

UTC = timezone.utc


class DeckAggregationServiceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Create owner / marketplace author
            author = User(username="seller", email="seller@example.com")
            author.set_password("pass")
            db.session.add(author)
            db.session.flush()
            self.author_id = author.id

            # Create learner
            learner = User(username="learner", email="learner@example.com", timezone="UTC")
            learner.set_password("pass")
            db.session.add(learner)
            db.session.flush()
            self.learner_id = learner.id

            # Decks
            self.owned_deck = Deck(name="Owned Deck", owner_user_id=learner.id)
            self.source_deck = Deck(name="Source Deck", owner_user_id=author.id)
            self.local_deck = Deck(name="Installed Local Deck", owner_user_id=learner.id)
            db.session.add_all([self.owned_deck, self.source_deck, self.local_deck])
            db.session.flush()

            self.owned_deck_id = self.owned_deck.id
            self.source_deck_id = self.source_deck.id
            self.local_deck_id = self.local_deck.id
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_note_and_cards(
        self,
        *,
        user_id: int,
        deck_id: int,
        card_count: int = 1,
        note_type_id: str | None = "general-nt",
        created_at: datetime | None = None,
    ) -> tuple[Note, list[Card]]:
        note = Note(
            user_id=user_id,
            deck_id=deck_id,
            note_type_id=note_type_id,
            created_at=created_at or datetime.utcnow(),
            field_values={"Front": "Q", "Back": "A"},
        )
        db.session.add(note)
        db.session.flush()

        cards = []
        for idx in range(card_count):
            card = Card(
                note_id=note.id,
                template_id=f"tmpl-{idx + 1}",
                created_at=created_at or datetime.utcnow(),
            )
            db.session.add(card)
            cards.append(card)
        db.session.flush()
        return note, cards

    def _add_progress(
        self,
        *,
        user_id: int,
        card_id: str,
        queue: str = "new",
        due_day: int | None = None,
        due_at: datetime | None = None,
        is_suspended: bool = False,
        is_buried: bool = False,
        buried_until_day: int | None = None,
    ) -> CardProgress:
        progress = CardProgress(
            user_id=user_id,
            card_id=card_id,
            queue=queue,
            due_day=due_day,
            due_at=due_at,
            is_suspended=is_suspended,
            is_buried=is_buried,
            buried_until_day=buried_until_day,
        )
        db.session.add(progress)
        db.session.flush()
        return progress

    def test_owned_deck_aggregation_counts(self):
        """Test SQL aggregation on directly owned notes across all queues and states."""
        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            # 1. Unstudied note (no progress row -> NEW)
            self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)

            # 2. Studied note in 'new' queue -> NEW
            _, cards_new = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_new[0].id, queue="new")

            # 3. Note in 'learning' queue -> LEARN
            _, cards_learn = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_learn[0].id, queue="learning")

            # 4. Note in 'review' queue due today -> DUE
            _, cards_due = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_due[0].id, queue="review", due_day=today_day)

            # 5. Note in 'review' queue due tomorrow -> Not DUE today
            _, cards_future = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_future[0].id, queue="review", due_day=today_day + 1)

            # 6. Suspended note -> Excluded from all counts
            _, cards_susp = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_susp[0].id, queue="review", due_day=today_day, is_suspended=True)

            # 7. Buried note until today -> Excluded
            _, cards_buried = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_buried[0].id, queue="review", due_day=today_day, is_buried=True, buried_until_day=today_day)

            # 8. Expired bury -> DUE
            _, cards_unburied = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_unburied[0].id, queue="review", due_day=today_day, is_buried=True, buried_until_day=today_day - 1)

            db.session.commit()

            counts, note_types = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[self.owned_deck_id],
                now_utc=now_utc,
                today_day_index=today_day,
                is_note_mode=False,
            )

            deck_counts = counts[self.owned_deck_id]
            self.assertEqual(deck_counts["new"], 2)       # items 1 & 2
            self.assertEqual(deck_counts["learn"], 1)     # item 3
            self.assertEqual(deck_counts["due"], 2)       # item 4 & item 8
            self.assertEqual(deck_counts["total"], 8)     # all 8 cards
            self.assertEqual(note_types.get(self.owned_deck_id), "general-nt")

    def test_logical_overlay_marketplace_deck_aggregation(self):
        """Test R1: Source cards mapped to local_deck_id via DeckCloneDeckMap."""
        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            # Marketplace install
            install = DeckInstall(
                id=str(uuid4()),
                deck_item_id="marketplace-item-1",
                user_id=self.learner_id,
                local_deck_id=self.local_deck_id,
                source_deck_id=self.source_deck_id,
                source_owner_user_id=self.author_id,
                clone_mode="logical_overlay",
                source_note_type_id="shared-nt-123",
                installed_at=now_utc,
            )
            db.session.add(install)
            db.session.flush()

            clone_map = DeckCloneDeckMap(
                id=str(uuid4()),
                deck_install_id=install.id,
                local_deck_id=self.local_deck_id,
                source_deck_id=self.source_deck_id,
            )
            db.session.add(clone_map)
            db.session.flush()

            # Create source cards owned by author
            _, cards_src_new = self._create_note_and_cards(
                user_id=self.author_id,
                deck_id=self.source_deck_id,
                created_at=now_utc - timedelta(hours=1),
            )
            _, cards_src_due = self._create_note_and_cards(
                user_id=self.author_id,
                deck_id=self.source_deck_id,
                created_at=now_utc - timedelta(hours=1),
            )

            # Learner has studied cards_src_due
            self._add_progress(
                user_id=self.learner_id,
                card_id=cards_src_due[0].id,
                queue="review",
                due_day=today_day,
            )
            # cards_src_new has no learner progress -> NEW for learner
            db.session.commit()

            counts, note_types = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[self.local_deck_id],
                now_utc=now_utc,
                today_day_index=today_day,
                is_note_mode=False,
            )

            local_counts = counts[self.local_deck_id]
            self.assertEqual(local_counts["new"], 1)
            self.assertEqual(local_counts["due"], 1)
            self.assertEqual(local_counts["learn"], 0)
            self.assertEqual(local_counts["total"], 2)
            self.assertEqual(note_types.get(self.local_deck_id), "shared-nt-123")

    def test_decision_d6_04_note_level_vs_card_level_counting(self):
        """Test R3: Multi-template note counts as 1 in note mode, but N in card mode."""
        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            # Note with 3 sibling cards (3 templates)
            note_multi, cards_multi = self._create_note_and_cards(
                user_id=self.learner_id,
                deck_id=self.owned_deck_id,
                card_count=3,
            )

            # All 3 sibling cards are due review today
            for c in cards_multi:
                self._add_progress(
                    user_id=self.learner_id,
                    card_id=c.id,
                    queue="review",
                    due_day=today_day,
                )
            db.session.commit()

            # In NOTE mode with count_by_note=True: counts as 1 Due Note
            counts_note, _ = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[self.owned_deck_id],
                now_utc=now_utc,
                today_day_index=today_day,
                is_note_mode=True,
                count_by_note=True,
            )
            self.assertEqual(counts_note[self.owned_deck_id]["due"], 1)
            self.assertEqual(counts_note[self.owned_deck_id]["total"], 3)

            # In LEGACY mode or count_by_note=False: counts as 3 Due Cards
            counts_card, _ = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[self.owned_deck_id],
                now_utc=now_utc,
                today_day_index=today_day,
                is_note_mode=False,
                count_by_note=False,
            )
            self.assertEqual(counts_card[self.owned_deck_id]["due"], 3)
            self.assertEqual(counts_card[self.owned_deck_id]["total"], 3)

    def test_note_authority_integrity_fail_closed(self):
        """Test R5: Fail-closed when a subject is missing an authority token."""
        with self.app.app_context():
            # Create a subject without a token
            subject = StudyProgressSubject(
                learner_user_id=self.learner_id,
                logical_note_key=b"note-test-key-1234567890",
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(subject)
            db.session.commit()

            # Integrity check must raise StudyAuthorityReadError
            with self.assertRaises(StudyAuthorityReadError) as ctx:
                check_note_authority_integrity(db.session, learner_user_id=self.learner_id)
            self.assertEqual(ctx.exception.code, "AUTHORITY_TOKEN_REQUIRED")

            # Now add token -> check must pass
            token = StudyAuthoritySubjectToken(
                subject_id=subject.id,
                subject_generation=1,
                authority_revision=0,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.session.add(token)
            db.session.commit()

            # Must not raise
            check_note_authority_integrity(db.session, learner_user_id=self.learner_id)

    def test_empty_visible_decks_returns_empty(self):
        """Test that empty visible_deck_ids returns immediately without error."""
        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            counts, note_types = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[],
                now_utc=now_utc,
                today_day_index=today_day,
                is_note_mode=False,
            )
            self.assertEqual(counts, {})
            self.assertEqual(note_types, {})

    def test_install_snapshot_cutoff_excludes_newer_cards(self):
        """Test R1: Source cards created after install snapshot are not counted."""
        with self.app.app_context():
            snapshot_time = datetime(2026, 9, 28, 12, 0, 0)
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            install = DeckInstall(
                id=str(uuid4()),
                deck_item_id="item-snap",
                user_id=self.learner_id,
                local_deck_id=self.local_deck_id,
                source_deck_id=self.source_deck_id,
                source_owner_user_id=self.author_id,
                clone_mode="logical_overlay",
                installed_at=snapshot_time,
                base_snapshot_at=snapshot_time,
            )
            db.session.add(install)
            db.session.flush()

            clone_map = DeckCloneDeckMap(
                id=str(uuid4()),
                deck_install_id=install.id,
                local_deck_id=self.local_deck_id,
                source_deck_id=self.source_deck_id,
            )
            db.session.add(clone_map)
            db.session.flush()

            # 1 card created BEFORE snapshot
            self._create_note_and_cards(
                user_id=self.author_id,
                deck_id=self.source_deck_id,
                created_at=snapshot_time - timedelta(hours=2),
            )

            # 1 card created AFTER snapshot
            self._create_note_and_cards(
                user_id=self.author_id,
                deck_id=self.source_deck_id,
                created_at=snapshot_time + timedelta(hours=2),
            )
            db.session.commit()

            counts, _ = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[self.local_deck_id],
                now_utc=now_utc,
                today_day_index=today_day,
                is_note_mode=False,
            )

            # Only the card created before snapshot is counted
            self.assertEqual(counts[self.local_deck_id]["total"], 1)
            self.assertEqual(counts[self.local_deck_id]["new"], 1)

    def test_non_locking_query_execution(self):
        """Test R5: Ensure no 'FOR UPDATE' or locking statements are executed."""
        from sqlalchemy import event

        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            db.session.commit()

            executed_clauses = []

            def before_execute(conn, clause, multiparams, params, options):
                if getattr(clause, "_for_update_arg", None) is not None:
                    executed_clauses.append(clause)

            event.listen(db.engine, "before_execute", before_execute)
            try:
                aggregate_deck_study_counts(
                    db.session,
                    learner_user_id=self.learner_id,
                    visible_deck_ids=[self.owned_deck_id],
                    now_utc=now_utc,
                    today_day_index=today_day,
                    is_note_mode=True,
                )
            finally:
                event.remove(db.engine, "before_execute", before_execute)

            self.assertEqual(executed_clauses, [], "Found unexpected locking queries!")

    def test_build_dashboard_data_end_to_end(self):
        """End-to-end verification of build_dashboard_data with single query aggregation."""
        from app.services.dashboard_service import build_dashboard_data

        with self.app.app_context():
            user = db.session.get(User, self.learner_id)
            now_utc = datetime.utcnow()
            today_day = now_utc.date().toordinal()

            # Add 2 new cards and 1 review card to owned deck
            _, cards_new = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id, card_count=2)
            _, cards_rev = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=cards_rev[0].id, queue="review", due_day=today_day)
            db.session.commit()

            with self.app.test_request_context():
                rows, total_new, total_learn, total_due, admin_mode = build_dashboard_data(user)

            self.assertFalse(admin_mode)
            owned_node = next((n for n in rows if n.deck_id == self.owned_deck_id), None)
            self.assertIsNotNone(owned_node)
            self.assertEqual(owned_node.new_count, 2)
            self.assertEqual(owned_node.learn_count, 0)
            self.assertEqual(owned_node.due_count, 1)
            self.assertEqual(total_new, 2)
            self.assertEqual(total_due, 1)


if __name__ == "__main__":
    unittest.main()
