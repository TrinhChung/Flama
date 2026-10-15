"""Queue metadata preserves ordering/counts while avoiding unselected Note content."""

from collections import Counter
from datetime import datetime, timedelta, timezone
import unittest

from sqlalchemy import event

from app.repositories.study_queue_repository import StudyQueueCardRef, query_study_queue_card_refs
from app.services.mcp import study_tools
from app.services.study_authority_read_service import load_study_authority_availability_snapshot, summarize_study_authority_queue
from models import db
from models.card import Card
from models.note import Note
from models.user_scheduler_settings import UserSchedulerSettings
from tests import test_study_direct_note_replay as fixtures
from tests import test_study_note_overlay as overlay_fixtures


class StudyQueueMetadataTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer
    _install_overlay = overlay_fixtures.StudyNoteOverlayTests._install_overlay

    def _record_loads(self):
        loaded = Counter()
        def card_load(_card, _context): loaded["Card"] += 1
        def note_load(_note, _context): loaded["Note"] += 1
        event.listen(Card, "load", card_load)
        event.listen(Note, "load", note_load)
        self.addCleanup(event.remove, Card, "load", card_load)
        self.addCleanup(event.remove, Note, "load", note_load)
        return loaded

    def test_minimal_refs_match_full_card_queue_for_both_count_units(self):
        self._answer()
        with self.app.app_context():
            query = Card.query.join(Note, Note.id == Card.note_id).filter(Note.user_id == self.user_id)
            scope = study_tools._card_scope(query)
            cards = query.order_by(Card.id.asc()).all()
            refs = query_study_queue_card_refs(query)
            self.assertTrue(all(isinstance(ref, StudyQueueCardRef) for ref in refs))
            self.assertEqual([(ref.id, ref.note_id, ref.created_at) for ref in refs],
                             [(str(card.id), str(card.note_id), card.created_at) for card in cards])
            now = datetime.now(timezone.utc).replace(tzinfo=None) + timedelta(days=10)
            full = load_study_authority_availability_snapshot(
                db.session, learner_user_id=self.user_id, cards=cards, scope=scope, now_utc=now)
            minimal = load_study_authority_availability_snapshot(
                db.session, learner_user_id=self.user_id, cards=refs, scope=scope, now_utc=now)
            self.assertEqual(full, minimal)
            for by_note in (False, True):
                args = dict(learner_user_id=self.user_id, now_utc=now, timezone_name="UTC", count_by_note=by_note)
                expected = summarize_study_authority_queue(cards=cards, reads_by_card_id=full, **args)
                actual = summarize_study_authority_queue(cards=refs, reads_by_card_id=minimal, **args)
                self.assertEqual(expected, actual)
                self.assertEqual(actual.due_count, 1 if by_note else 2)
            db.session.rollback()

    def test_complete_study_next_loads_no_card_or_note_entities(self):
        self._answer()  # easy -> review in the future for both siblings
        loaded = self._record_loads()
        response = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["session_state"], "complete")
        self.assertIsNone(response.get_json()["card_id"])
        self.assertEqual(loaded["Card"], 0)
        self.assertEqual(loaded["Note"], 0)

    def test_pending_learning_study_next_preserves_waiting_without_content_loads(self):
        self._answer({**self.payload, "rating": "again"})
        with self.app.app_context():
            settings = db.session.get(UserSchedulerSettings, self.user_id)
            if settings is None:
                settings = UserSchedulerSettings(user_id=self.user_id)
                db.session.add(settings)
            settings.learn_ahead_seconds = 0
            db.session.commit()
        loaded = self._record_loads()
        response = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["session_state"], "waiting")
        self.assertIsNone(body["card_id"])
        self.assertTrue(body["next_due_at"])
        self.assertEqual(loaded["Card"], 0)
        self.assertEqual(loaded["Note"], 0)

    def test_selected_study_next_still_renders_the_full_card(self):
        loaded = self._record_loads()
        response = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertIn(body["card_id"], self.card_ids)
        self.assertIn("test", body["rendered_front_html"])
        self.assertEqual(body["field_values"]["Word"], "test")
        self.assertEqual(body["authority_mode"], "NOTE")
        self.assertEqual(loaded["Note"], 1)

    def test_clone_study_next_keeps_source_card_visibility_and_rendering(self):
        self._install_overlay()
        response = self.client.get(f"/api/study/next?scope=deck&scope_id={self.local_deck_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertIn(body["card_id"], self.source_card_ids)
        self.assertEqual(body["note_id"], self.source_note_id)
        self.assertIn("共有", body["rendered_front_html"])
        self.assertFalse(body["can_edit_card"])

    def test_mcp_counts_and_stats_load_no_card_or_note_content(self):
        self._answer()
        loaded = self._record_loads()
        with self.app.app_context():
            counts = study_tools.get_due_card_counts(user_id=self.user_id, deck_id=self.deck_id)
            stats = study_tools.get_deck_stats(user_id=self.user_id, deck_id=self.deck_id)
            self.assertEqual(counts["total_due"], 0)
            self.assertEqual((stats["note_count"], stats["card_count"]), (1, 2))
            self.assertEqual((stats["new_cards"], stats["learning_cards"], stats["review_due_cards"]), (0, 0, 0))
            self.assertEqual(stats["young_cards"] + stats["mature_cards"], 2)
            self.assertEqual(loaded["Card"], 0)
            self.assertEqual(loaded["Note"], 0)
            db.session.rollback()

    def test_mcp_completed_queue_loads_no_content(self):
        self._answer()
        loaded = self._record_loads()
        with self.app.app_context():
            body = study_tools.get_study_queue(user_id=self.user_id, deck_id=self.deck_id, limit=1)
            self.assertEqual(body["cards"], [])
            self.assertEqual(body["queue_counts"]["total_due"], 0)
            self.assertEqual(loaded["Card"], 0)
            self.assertEqual(loaded["Note"], 0)
            db.session.rollback()

    def test_mcp_queue_skips_missing_note_type_before_limiting(self):
        with self.app.app_context():
            card = db.session.get(Card, self.card_ids[0])
            # SQLite fixture permits an orphaned type; the previous MCP path
            # skipped it before slicing the queue. Keep that contract.
            # Write this deliberately invalid historical row outside ORM
            # writers, which correctly require a resolvable current schema.
            from uuid import uuid4
            orphan_id = str(uuid4())
            older = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=10)
            db.session.connection().execute(Note.__table__.insert().values(
                id=orphan_id, user_id=self.user_id, deck_id=self.deck_id,
                note_type_id="missing-note-type", field_values_by_id={},
                field_values_extras={"Word": "orphan"}, field_values_codec="field-id.v1",
                created_at=older))
            orphan = db.session.get(Note, orphan_id)
            from models.study_application import StudyApplication
            db.session.add(StudyApplication(note_type_id=orphan.note_type_id,
                template_id=card.template_id, occurrence_key="orphan-fixture", status_code="ACTIVE",
                created_at=older, updated_at=older))
            db.session.commit()
        loaded = self._record_loads()
        with self.app.app_context():
            body = study_tools.get_study_queue(user_id=self.user_id, deck_id=self.deck_id, limit=1)
            self.assertEqual(len(body["cards"]), 1)
            self.assertIn(body["cards"][0]["card_id"], self.card_ids)
            self.assertEqual(body["cards"][0]["fields"]["Word"], "test")
            self.assertEqual(loaded["Note"], 1)
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
