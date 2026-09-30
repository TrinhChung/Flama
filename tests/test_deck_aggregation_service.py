"""Tests for the single-query deck aggregation seam used by the dashboard.

LEGACY rows come from ``card_progress``; NOTE rows (canonical availability and
fail-closed evidence checks) are covered with real writers in
``test_note_analytics_read.py``. Buckets must match
``study_repository.counter_bucket_for_progress_values``.
"""

from __future__ import annotations

from datetime import date, datetime, timezone, timedelta
import random
import unittest
from uuid import uuid4

from app import create_app
from app.repositories.study_repository import _today_day_index, counter_bucket_for_progress_values
from app.services.anki_scheduler import _day_index_to_datetime
from app.services.deck_aggregation_service import aggregate_deck_study_counts
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import DeckCloneDeckMap, DeckInstall, Note
from models.study_progress_subject import StudyProgressSubject
from models.user import User

UTC = timezone.utc


def _next_day_start(today_day: int) -> datetime:
    """Start of the next study day for a UTC learner with a midnight boundary."""
    return datetime.combine(date.fromordinal(today_day + 1), datetime.min.time())


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
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
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
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
                is_note_mode=False,
            )

            local_counts = counts[self.local_deck_id]
            self.assertEqual(local_counts["new"], 1)
            self.assertEqual(local_counts["due"], 1)
            self.assertEqual(local_counts["learn"], 0)
            self.assertEqual(local_counts["total"], 2)
            self.assertEqual(note_types.get(self.local_deck_id), "shared-nt-123")

    def test_empty_visible_decks_returns_empty(self):
        """Test that empty visible_deck_ids returns immediately without error."""
        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            counts, note_types = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[],
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
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
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
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
                    today_day_index=today_day,
                    day_cutoff_utc=_next_day_start(today_day),
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
            # Due yesterday: the dashboard counts from the learner's study day
            # (day boundary 04:00), so "today in UTC" is not yet due before 04:00.
            self._add_progress(user_id=self.learner_id, card_id=cards_rev[0].id, queue="review", due_day=today_day - 1)
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

    def test_multi_author_nested_subdecks_marketplace_overlay(self):
        """Test Open Issue 3: Complex nested subdecks from multiple marketplace authors with overlapping template IDs."""
        from app.services.dashboard_service import build_dashboard_data

        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            # Author 2
            author2 = User(username="author2", email="author2@example.com")
            author2.set_password("pass")
            db.session.add(author2)
            db.session.flush()

            # Author 1 Deck Hierarchy: Parent A -> Child A1 -> Grandchild A2
            src_a = Deck(name="Source A (N5)", owner_user_id=self.author_id)
            db.session.add(src_a)
            db.session.flush()
            src_a1 = Deck(name="Source A1 (Kanji)", owner_user_id=self.author_id, parent_id=src_a.id)
            db.session.add(src_a1)
            db.session.flush()
            src_a2 = Deck(name="Source A2 (Vocab)", owner_user_id=self.author_id, parent_id=src_a1.id)
            db.session.add(src_a2)
            db.session.flush()

            # Author 2 Deck Hierarchy: Parent B -> Child B1
            src_b = Deck(name="Source B (N4)", owner_user_id=author2.id)
            db.session.add(src_b)
            db.session.flush()
            src_b1 = Deck(name="Source B1 (Grammar)", owner_user_id=author2.id, parent_id=src_b.id)
            db.session.add(src_b1)
            db.session.flush()

            # Learner Local Decks: L_A -> L_A1 -> L_A2
            local_a = Deck(name="Local A", owner_user_id=self.learner_id)
            db.session.add(local_a)
            db.session.flush()
            local_a1 = Deck(name="Local A1", owner_user_id=self.learner_id, parent_id=local_a.id)
            db.session.add(local_a1)
            db.session.flush()
            local_a2 = Deck(name="Local A2", owner_user_id=self.learner_id, parent_id=local_a1.id)
            db.session.add(local_a2)
            db.session.flush()

            # Learner Local Decks: L_B -> L_B1
            local_b = Deck(name="Local B", owner_user_id=self.learner_id)
            db.session.add(local_b)
            db.session.flush()
            local_b1 = Deck(name="Local B1", owner_user_id=self.learner_id, parent_id=local_b.id)
            db.session.add(local_b1)
            db.session.flush()

            # Install 1 (Author 1 Deck A)
            inst_a = DeckInstall(
                id=str(uuid4()),
                deck_item_id="item-a",
                user_id=self.learner_id,
                local_deck_id=local_a.id,
                source_deck_id=src_a.id,
                source_owner_user_id=self.author_id,
                clone_mode="logical_overlay",
                source_note_type_id="nt-author1",
                installed_at=now_utc,
            )
            db.session.add(inst_a)
            db.session.flush()
            db.session.add_all([
                DeckCloneDeckMap(deck_install_id=inst_a.id, source_deck_id=src_a.id, local_deck_id=local_a.id),
                DeckCloneDeckMap(deck_install_id=inst_a.id, source_deck_id=src_a1.id, local_deck_id=local_a1.id),
                DeckCloneDeckMap(deck_install_id=inst_a.id, source_deck_id=src_a2.id, local_deck_id=local_a2.id),
            ])

            # Install 2 (Author 2 Deck B)
            inst_b = DeckInstall(
                id=str(uuid4()),
                deck_item_id="item-b",
                user_id=self.learner_id,
                local_deck_id=local_b.id,
                source_deck_id=src_b.id,
                source_owner_user_id=author2.id,
                clone_mode="logical_overlay",
                source_note_type_id="nt-author2",
                installed_at=now_utc,
            )
            db.session.add(inst_b)
            db.session.flush()
            db.session.add_all([
                DeckCloneDeckMap(deck_install_id=inst_b.id, source_deck_id=src_b.id, local_deck_id=local_b.id),
                DeckCloneDeckMap(deck_install_id=inst_b.id, source_deck_id=src_b1.id, local_deck_id=local_b1.id),
            ])

            # Notes in Author 1 decks (overlapping template IDs: tmpl-1)
            _, cards_a = self._create_note_and_cards(user_id=self.author_id, deck_id=src_a.id, created_at=now_utc - timedelta(days=1))
            _, cards_a1 = self._create_note_and_cards(user_id=self.author_id, deck_id=src_a1.id, created_at=now_utc - timedelta(days=1))
            _, cards_a2 = self._create_note_and_cards(user_id=self.author_id, deck_id=src_a2.id, created_at=now_utc - timedelta(days=1))

            # Notes in Author 2 decks (SAME overlapping template ID: tmpl-1)
            _, cards_b = self._create_note_and_cards(user_id=author2.id, deck_id=src_b.id, created_at=now_utc - timedelta(days=1))
            _, cards_b1 = self._create_note_and_cards(user_id=author2.id, deck_id=src_b1.id, created_at=now_utc - timedelta(days=1))

            # Progress for learner:
            # - cards_a2: due today
            self._add_progress(user_id=self.learner_id, card_id=cards_a2[0].id, queue="review", due_day=today_day)
            # - cards_b1: learn
            self._add_progress(user_id=self.learner_id, card_id=cards_b1[0].id, queue="learning")
            # Other cards: unstudied (NEW)
            db.session.commit()

            learner_user = db.session.get(User, self.learner_id)
            with self.app.test_request_context():
                nodes, total_new, total_learn, total_due, _ = build_dashboard_data(learner_user)

            node_a = next(n for n in nodes if n.deck_id == local_a.id)
            node_b = next(n for n in nodes if n.deck_id == local_b.id)

            # Subtree counts roll up cleanly:
            # Local A subtree (A, A1, A2): total=3, new=2 (A, A1), due=1 (A2), learn=0
            self.assertEqual(node_a.new_count, 2)
            self.assertEqual(node_a.due_count, 1)
            self.assertEqual(node_a.learn_count, 0)
            self.assertEqual(node_a.note_type_id, "nt-author1")

            # Local B subtree (B, B1): total=2, new=1 (B), learn=1 (B1), due=0
            self.assertEqual(node_b.new_count, 1)
            self.assertEqual(node_b.learn_count, 1)
            self.assertEqual(node_b.due_count, 0)
            self.assertEqual(node_b.note_type_id, "nt-author2")

    def test_analytics_read_transaction_isolation_and_write_safety(self):
        """Test R5 & Open Issue 2: Verify analytics_read_transaction contract, dirty write rejection, and MySQL snapshot."""
        from unittest.mock import MagicMock, patch
        from app.services.study_analytics_read_service import analytics_read_transaction

        now_utc = datetime(2026, 9, 29, 12, 0, 0)
        today_day = now_utc.date().toordinal()

        with self.app.app_context():
            # 1. Clean execution under read transaction
            with analytics_read_transaction():
                counts, _ = aggregate_deck_study_counts(
                    db.session,
                    learner_user_id=self.learner_id,
                    visible_deck_ids=[self.owned_deck_id],
                    today_day_index=today_day,
                    day_cutoff_utc=_next_day_start(today_day),
                    is_note_mode=False,
                )
                self.assertIn(self.owned_deck_id, counts)

            # 2. Reject pending writes
            pending_note = Note(user_id=self.learner_id, deck_id=self.owned_deck_id, field_values={})
            db.session.add(pending_note)
            with self.assertRaises(RuntimeError) as ctx:
                with analytics_read_transaction():
                    pass
            self.assertIn("Analytics must start after pending writes are resolved", str(ctx.exception))
            db.session.rollback()

            # 3. Test MySQL dialect path executes START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY
            mock_conn = MagicMock()
            mock_session = MagicMock()
            mock_session.new = set()
            mock_session.dirty = set()
            mock_session.deleted = set()
            mock_session.get_bind.return_value.dialect.name = "mysql"
            mock_session.connection.return_value = mock_conn

            with patch("app.services.study_analytics_read_service.db.session", return_value=mock_session):
                with analytics_read_transaction():
                    pass

            mock_session.connection.assert_called_once_with(
                execution_options={"isolation_level": "REPEATABLE READ"}
            )
            mock_conn.exec_driver_sql.assert_called_once_with(
                "START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY"
            )
            mock_session.rollback.assert_called()

    def test_empty_decks_and_unattached_notes(self):
        """Test edge cases: empty decks, unattached notes (deck_id=None), and invisible decks."""
        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            # Empty deck
            empty_deck = Deck(name="Empty Deck", owner_user_id=self.learner_id)
            db.session.add(empty_deck)
            db.session.flush()

            # Note with deck_id=None (e.g. unattached/orphaned)
            self._create_note_and_cards(user_id=self.learner_id, deck_id=None, card_count=2)

            db.session.commit()

            # Query empty deck
            counts, note_types = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[empty_deck.id],
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
                is_note_mode=False,
            )
            self.assertEqual(counts[empty_deck.id], {"total": 0, "new": 0, "learn": 0, "due": 0})
            self.assertNotIn(empty_deck.id, note_types)

            # Query with empty visible_deck_ids list
            empty_res, empty_nt = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[],
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
                is_note_mode=False,
            )
            self.assertEqual(empty_res, {})
            self.assertEqual(empty_nt, {})

    def test_custom_day_boundary_hour_and_day_cutoff_parity(self):
        """Test R4: Parity around day boundary hour local and review card with due_day=None."""
        from unittest.mock import patch
        from app.services.dashboard_service import build_dashboard_data
        from models.user_scheduler_settings import UserSchedulerSettings

        with self.app.app_context():
            user = db.session.get(User, self.learner_id)
            user.timezone = "Asia/Tokyo"
            # Set custom boundary hour to 6 AM (default is 4 AM)
            setting = UserSchedulerSettings(
                user_id=self.learner_id,
                day_boundary_hour_local=6,
                learn_ahead_seconds=1200,
            )
            db.session.add(setting)

            # Test time: 2026-09-30 19:30:00 UTC = 2026-10-01 04:30:00 Tokyo time
            # If boundary_hour were default (4), this would be Day D+1 (04:30 >= 04:00).
            # But with custom boundary_hour (6), it is still Day D (04:30 < 06:00)!
            now_utc = datetime(2026, 9, 30, 19, 30, 0)

            # Create a review card with due_day=None and due_at = 2026-09-30 20:00:00 UTC (05:00 Tokyo time)
            # This is before 06:00 Tokyo time, so it belongs to Day D!
            _, cards = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(
                user_id=self.learner_id,
                card_id=cards[0].id,
                queue="review",
                due_day=None,
                due_at=datetime(2026, 9, 30, 20, 0, 0),
            )
            db.session.commit()

            with self.app.test_request_context():
                with patch("app.services.dashboard_service._utcnow", return_value=now_utc):
                    rows, total_new, total_learn, total_due, _ = build_dashboard_data(user)
                    # Should be due on today's study day because due_at is before tomorrow's 6 AM boundary!
                    self.assertEqual(total_due, 1)

    def test_corrupted_and_null_due_dates(self):
        """Test robust handling of NULL/corrupted due dates across queues."""
        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            # 1. Review with both due_day=None and due_at=None -> treated as due today
            _, c1 = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=c1[0].id, queue="review", due_day=None, due_at=None)

            # 2. queue=None -> treated as "new"
            _, c2 = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=c2[0].id, queue=None)

            # 3. Negative due_day=-5 -> overdue, treated as due review
            _, c3 = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=c3[0].id, queue="review", due_day=-5)

            # 4. Learning with due_at=None -> treated as learn
            _, c4 = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            self._add_progress(user_id=self.learner_id, card_id=c4[0].id, queue="learning", due_at=None)

            db.session.commit()

            counts, _ = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[self.owned_deck_id],
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
                is_note_mode=False,
            )
            d = counts[self.owned_deck_id]
            self.assertEqual(d["total"], 4)
            self.assertEqual(d["due"], 2)     # c1 (null dates) & c3 (negative due_day)
            self.assertEqual(d["new"], 1)     # c2 (queue=None)
            self.assertEqual(d["learn"], 1)   # c4 (learning with due_at=None)

    def test_large_dataset_40k_cards_uses_constant_statements(self):
        """R4: 40,000 Cards aggregate correctly without per-Card statements."""
        from sqlalchemy import event

        with self.app.app_context():
            now_utc = datetime(2026, 9, 29, 12, 0, 0)
            today_day = now_utc.date().toordinal()

            # Fast bulk-insert 40,000 notes and cards via raw Core table insert
            note_table = Note.__table__
            card_table = Card.__table__
            progress_table = CardProgress.__table__

            notes_data = []
            cards_data = []
            progress_data = []

            # 40,000 cards:
            # 10,000 new (no progress)
            # 10,000 new (with progress queue='new')
            # 5,000 learning
            # 10,000 review due today
            # 5,000 review future (due today + 7)
            total_cards = 40000
            for i in range(total_cards):
                nid = f"bench-note-{i}"
                cid = f"bench-card-{i}"
                notes_data.append({
                    "id": nid,
                    "user_id": self.learner_id,
                    "deck_id": self.owned_deck_id,
                    "note_type_id": "general-nt",
                    "field_values": {},
                    "tags": [],
                    "created_at": now_utc,
                    "updated_at": now_utc,
                })
                cards_data.append({
                    "id": cid,
                    "note_id": nid,
                    "template_id": "tmpl-1",
                    "created_at": now_utc,
                    "updated_at": now_utc,
                })
                if i < 10000:
                    pass  # no progress row
                elif i < 20000:
                    progress_data.append({
                        "user_id": self.learner_id,
                        "card_id": cid,
                        "queue": "new",
                        "due_day": None,
                        "due_at": None,
                        "is_suspended": False,
                        "is_buried": False,
                    })
                elif i < 25000:
                    progress_data.append({
                        "user_id": self.learner_id,
                        "card_id": cid,
                        "queue": "learning",
                        "due_day": None,
                        "due_at": now_utc,
                        "is_suspended": False,
                        "is_buried": False,
                    })
                elif i < 35000:
                    progress_data.append({
                        "user_id": self.learner_id,
                        "card_id": cid,
                        "queue": "review",
                        "due_day": today_day,
                        "due_at": now_utc,
                        "is_suspended": False,
                        "is_buried": False,
                    })
                else:
                    progress_data.append({
                        "user_id": self.learner_id,
                        "card_id": cid,
                        "queue": "review",
                        "due_day": today_day + 7,
                        "due_at": now_utc,
                        "is_suspended": False,
                        "is_buried": False,
                    })

            db.session.execute(note_table.insert(), notes_data)
            db.session.execute(card_table.insert(), cards_data)
            if progress_data:
                db.session.execute(progress_table.insert(), progress_data)
            db.session.commit()

            statements = []

            def count_statement(conn, cursor, statement, parameters, context, executemany):
                statements.append(statement)

            event.listen(db.engine, "before_cursor_execute", count_statement)
            try:
                counts, _ = aggregate_deck_study_counts(
                    db.session,
                    learner_user_id=self.learner_id,
                    visible_deck_ids=[self.owned_deck_id],
                    today_day_index=today_day,
                    day_cutoff_utc=_next_day_start(today_day),
                    is_note_mode=False,
                )
            finally:
                event.remove(db.engine, "before_cursor_execute", count_statement)

            d = counts[self.owned_deck_id]
            self.assertEqual(d["total"], 40000)
            self.assertEqual(d["new"], 20000)
            self.assertEqual(d["learn"], 5000)
            self.assertEqual(d["due"], 10000)
            # Installs, aggregate and note types: the statement count never grows with Cards.
            self.assertLessEqual(len(statements), 3, statements)

    def test_counts_match_counter_bucket_helper_around_boundaries(self):
        """R3: SQL buckets equal the Study helper for every queue/due/bury combination."""
        queues = ["new", "learning", "relearning", "learn", "review", " Review ", "", "weird"]
        contexts = [
            ("UTC", 0, datetime(2026, 9, 29, 12, 0, 0)),
            ("Asia/Tokyo", 4, datetime(2026, 9, 29, 18, 59, 59)),
            ("America/Los_Angeles", 23, datetime(2026, 11, 1, 9, 30, 0)),
            ("Asia/Ho_Chi_Minh", 4, datetime(2026, 9, 29, 21, 0, 0)),
        ]
        rng = random.Random(20260930)
        with self.app.app_context():
            for timezone_name, boundary, now_utc in contexts:
                with self.subTest(timezone=timezone_name, boundary=boundary):
                    CardProgress.query.delete()
                    Card.query.delete()
                    Note.query.delete()
                    today = _today_day_index(
                        now=now_utc, timezone_name=timezone_name, day_boundary_hour_local=boundary
                    )
                    cutoff = _day_index_to_datetime(today + 1, boundary, timezone_name=timezone_name)
                    due_ats = [None, cutoff - timedelta(seconds=1), cutoff, cutoff + timedelta(seconds=1),
                        now_utc - timedelta(hours=30), now_utc + timedelta(minutes=5)]
                    expected = {"new": 0, "learn": 0, "due": 0}
                    for index in range(120):
                        _, cards = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
                        if index % 12 == 0:
                            bucket = counter_bucket_for_progress_values(queue=None, due_at=None, due_day=None,
                                now=now_utc, timezone_name=timezone_name, day_boundary_hour_local=boundary)
                        else:
                            values = dict(
                                queue=rng.choice(queues),
                                due_day=rng.choice([None, None, today - 1, today, today + 1]),
                                due_at=rng.choice(due_ats),
                                is_suspended=rng.random() < 0.1,
                                is_buried=rng.random() < 0.2,
                                buried_until_day=rng.choice([None, today - 1, today, today + 1]),
                            )
                            self._add_progress(user_id=self.learner_id, card_id=cards[0].id, **values)
                            bucket = counter_bucket_for_progress_values(now=now_utc, timezone_name=timezone_name,
                                day_boundary_hour_local=boundary, **values)
                        if bucket == "learning":
                            expected["learn"] += 1
                        elif bucket == "review":
                            expected["due"] += 1
                        elif bucket == "new":
                            expected["new"] += 1
                    db.session.commit()
                    counts, _ = aggregate_deck_study_counts(
                        db.session,
                        learner_user_id=self.learner_id,
                        visible_deck_ids=[self.owned_deck_id],
                        today_day_index=today,
                        day_cutoff_utc=cutoff,
                        is_note_mode=False,
                    )
                    got = counts[self.owned_deck_id]
                    self.assertEqual({key: got[key] for key in expected}, expected)
                    self.assertEqual(got["total"], 120)

    def _install_overlay_with_source_card(self, *, note_type_id="shared-nt"):
        now_utc = datetime(2026, 9, 29, 12, 0, 0)
        install = DeckInstall(id=str(uuid4()), deck_item_id=f"item-{uuid4()}", user_id=self.learner_id,
            local_deck_id=self.local_deck_id, source_deck_id=self.source_deck_id,
            source_owner_user_id=self.author_id, clone_mode="logical_overlay",
            source_note_type_id=note_type_id, installed_at=now_utc)
        db.session.add(install)
        db.session.flush()
        db.session.add(DeckCloneDeckMap(id=str(uuid4()), deck_install_id=install.id,
            local_deck_id=self.local_deck_id, source_deck_id=self.source_deck_id))
        self._create_note_and_cards(user_id=self.author_id, deck_id=self.source_deck_id,
            created_at=now_utc - timedelta(hours=1))
        db.session.commit()
        return now_utc.date().toordinal()

    def test_admin_never_counts_overlay_sources_in_either_mode(self):
        """R5: admin dashboards skip logical-overlay sources, LEGACY and NOTE alike."""
        with self.app.app_context():
            today_day = self._install_overlay_with_source_card()
            for is_note_mode in (False, True):
                counts, note_types = aggregate_deck_study_counts(
                    db.session,
                    learner_user_id=self.learner_id,
                    visible_deck_ids=[self.local_deck_id],
                    today_day_index=today_day,
                    day_cutoff_utc=_next_day_start(today_day),
                    is_note_mode=is_note_mode,
                    admin_mode=True,
                )
                self.assertEqual(counts[self.local_deck_id]["total"], 0)
                self.assertNotIn(self.local_deck_id, note_types)
                learner_counts, _ = aggregate_deck_study_counts(
                    db.session,
                    learner_user_id=self.learner_id,
                    visible_deck_ids=[self.local_deck_id],
                    today_day_index=today_day,
                    day_cutoff_utc=_next_day_start(today_day),
                    is_note_mode=is_note_mode,
                )
                self.assertEqual(learner_counts[self.local_deck_id]["total"], 1)

    def test_owned_note_type_wins_over_install_and_oldest_note_type_is_stable(self):
        """R6: owned Notes decide the deck Note type first, oldest Note type first."""
        with self.app.app_context():
            today_day = self._install_overlay_with_source_card(note_type_id="install-nt")
            self._create_note_and_cards(user_id=self.learner_id, deck_id=self.local_deck_id,
                note_type_id="z-older-nt", created_at=datetime(2026, 1, 1))
            self._create_note_and_cards(user_id=self.learner_id, deck_id=self.local_deck_id,
                note_type_id="a-newer-nt", created_at=datetime(2026, 5, 1))
            db.session.commit()
            for _ in range(3):
                _, note_types = aggregate_deck_study_counts(
                    db.session,
                    learner_user_id=self.learner_id,
                    visible_deck_ids=[self.local_deck_id],
                    today_day_index=today_day,
                    day_cutoff_utc=_next_day_start(today_day),
                    is_note_mode=False,
                )
                self.assertEqual(note_types[self.local_deck_id], "z-older-nt")

    def test_note_mode_ignores_pristine_subject_without_token(self):
        """A never-studied subject needs no token (the locking reader never read it either)."""
        with self.app.app_context():
            note, _cards = self._create_note_and_cards(user_id=self.learner_id, deck_id=self.owned_deck_id)
            db.session.add(StudyProgressSubject(learner_user_id=self.learner_id,
                logical_note_key=str(note.id).encode("utf-8"), live_note_id=str(note.id),
                created_at=datetime.utcnow(), updated_at=datetime.utcnow()))
            db.session.commit()
            today_day = datetime(2026, 9, 29).toordinal()
            counts, _ = aggregate_deck_study_counts(
                db.session,
                learner_user_id=self.learner_id,
                visible_deck_ids=[self.owned_deck_id],
                today_day_index=today_day,
                day_cutoff_utc=_next_day_start(today_day),
                is_note_mode=True,
            )
            self.assertEqual(counts[self.owned_deck_id], {"total": 1, "new": 1, "learn": 0, "due": 0})


if __name__ == "__main__":
    unittest.main()
