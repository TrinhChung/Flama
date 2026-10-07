"""Durable count invalidation follows domain commits, including SAVEPOINT rollback."""

from datetime import datetime
import unittest
from unittest.mock import patch

from sqlalchemy import event, select, text, update

from app import create_app
from app.repositories.study_progress_subject_repository import ensure_and_lock_subject
from app.services.deck_aggregation_service import aggregate_deck_study_counts
from app.services.deck_count_snapshot_service import prewarm_owned_deck_counts
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_count_snapshot import DeckCountContentRevision, DeckCountLearnerRevision
from models.note import Note
from models.note_type import NoteType
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from tests import test_study_direct_note_replay as note_fixtures


class DeckCountProjectionTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "WTF_CSRF_ENABLED": False, "DECK_COUNT_WRITE_ENABLED": False,
            "DECK_COUNT_READ_MODE": "raw", "REVIEW_ANALYTICS_WRITE_ENABLED": False,
            "STUDY_NOTE_COUNT_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        users = [User(username=f"count-user-{number}",
                      email=f"count-user-{number}@example.invalid", timezone="UTC")
                 for number in range(2)]
        db.session.add_all(users)
        db.session.flush()
        self.user_id, self.other_user_id = [user.id for user in users]
        decks = [Deck(name=f"Count Deck {number}", owner_user_id=self.user_id)
                 for number in range(3)]
        note_type = NoteType(name="Counter fixture", user_id=self.user_id)
        db.session.add_all([*decks, note_type])
        db.session.flush()
        self.deck_ids = [deck.id for deck in decks]
        self.note_type_id = note_type.id
        template = Template(note_type_id=note_type.id, name="Front", front_html="Q", back_html="A")
        db.session.add(template)
        db.session.flush()
        self.template_id = template.id
        other_template = Template(note_type_id=note_type.id, name="Reverse", position=1,
                                  front_html="A", back_html="Q")
        db.session.add(other_template)
        db.session.flush()
        self.other_template_id = other_template.id
        notes = [Note(user_id=self.user_id, deck_id=deck.id, note_type_id=note_type.id,
                      field_values={"Front": "Q"}) for deck in decks]
        db.session.add_all(notes)
        db.session.flush()
        self.note_ids = [note.id for note in notes]
        cards = [Card(note_id=note.id, template_id=template.id) for note in notes]
        db.session.add_all(cards)
        db.session.flush()
        self.card_ids = [card.id for card in cards]
        db.session.commit()
        db.session.remove()
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = True

    def tearDown(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _revisions(self):
        content = dict(db.session.execute(select(
            DeckCountContentRevision.physical_deck_id, DeckCountContentRevision.revision)).all())
        learner = {(row.user_id, row.effective_deck_id): row.revision for row in
                   db.session.execute(select(DeckCountLearnerRevision)).scalars()}
        return content, learner

    def _add_note(self, deck_id, *, add_card=True):
        note = Note(user_id=self.user_id, deck_id=deck_id, note_type_id=self.note_type_id,
                    field_values={"Front": "new"})
        db.session.add(note)
        if add_card:
            db.session.add(Card(note=note, template_id=self.template_id))
        return note

    def test_new_related_note_and_card_bump_the_deck_once_at_outer_commit(self):
        note = self._add_note(self.deck_ids[0])
        db.session.flush()
        db.session.add(Card(note=note, template_id=self.other_template_id))
        db.session.flush()
        self.assertEqual(self._revisions(), ({}, {}), "Flush must not acquire revision locks")
        db.session.commit()
        self.assertEqual(self._revisions(), ({self.deck_ids[0]: 1}, {}))

    def test_unloaded_note_foreign_key_move_retains_old_and_new_deck(self):
        note = db.session.get(Note, self.note_ids[0])
        db.session.expire(note, ["deck_id"])
        note.deck_id = self.deck_ids[1]
        db.session.commit()
        self.assertEqual(self._revisions(), ({self.deck_ids[0]: 1, self.deck_ids[1]: 1}, {}))

    def test_card_foreign_key_move_and_delete_retain_old_and_new_deck(self):
        target = self._empty_target_note()
        card = db.session.get(Card, self.card_ids[0])
        card.note_id = target.id
        db.session.flush()
        db.session.delete(card)
        db.session.commit()
        self.assertEqual(self._revisions(), ({self.deck_ids[0]: 1, self.deck_ids[1]: 1}, {}))

    def test_card_relationship_move_invalidates_both_memberships(self):
        target = self._empty_target_note()
        card = db.session.get(Card, self.card_ids[0])
        card.note = target
        db.session.commit()
        self.assertEqual(db.session.get(Card, self.card_ids[0]).note_id, target.id)
        self.assertEqual(self._revisions(), ({self.deck_ids[0]: 1, self.deck_ids[1]: 1}, {}))

    def _empty_target_note(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        note = self._add_note(self.deck_ids[1], add_card=False)
        db.session.commit()
        _ = note.id
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = True
        return note

    def test_note_delete_invalidates_membership_before_cascade_removes_cards(self):
        db.session.delete(db.session.get(Note, self.note_ids[0]))
        db.session.commit()
        self.assertIsNone(db.session.get(Card, self.card_ids[0]))
        self.assertEqual(self._revisions(), ({self.deck_ids[0]: 1}, {}))

    def test_legacy_progress_deduplicates_multiple_flushes_without_global_epoch(self):
        progress = CardProgress(user_id=self.user_id, card_id=self.card_ids[0], queue="new")
        db.session.add(progress)
        db.session.flush()
        progress.queue = "review"
        progress.due_day = 1
        db.session.flush()
        progress.is_suspended = True
        db.session.commit()
        self.assertEqual(self._revisions(), ({}, {(self.user_id, self.deck_ids[0]): 1}))

    def test_legacy_progress_move_tracks_old_and_new_learner_and_card_scope(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        progress = CardProgress(user_id=self.user_id, card_id=self.card_ids[0], queue="new")
        db.session.add(progress)
        db.session.commit()
        # Load prior keys explicitly: unloaded replacements may safely use the global epoch.
        _ = progress.user_id, progress.card_id
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = True
        progress.user_id = self.other_user_id
        progress.card_id = self.card_ids[1]
        db.session.commit()
        self.assertEqual(self._revisions(), ({}, {
            (user_id, deck_id): 1 for user_id in (self.user_id, self.other_user_id)
            for deck_id in self.deck_ids[:2]
        }))

    def test_legacy_progress_relationship_move_invalidates_both_card_scopes(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        progress = CardProgress(user_id=self.user_id, card_id=self.card_ids[0], queue="new")
        db.session.add(progress)
        db.session.commit()
        _ = progress.card_id
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = True
        progress.card = db.session.get(Card, self.card_ids[1])
        db.session.commit()
        self.assertEqual(self._revisions(), ({}, {
            (self.user_id, self.deck_ids[0]): 1, (self.user_id, self.deck_ids[1]): 1,
        }))

    def test_subject_logical_key_is_tracked_even_with_wrong_live_pointer(self):
        subject = StudyProgressSubject(
            learner_user_id=self.user_id, logical_note_key=self.note_ids[0].encode(),
            live_note_id=self.note_ids[1], created_at=datetime.utcnow(), updated_at=datetime.utcnow())
        db.session.add(subject)
        db.session.commit()
        content, learner = self._revisions()
        self.assertEqual(content, {})
        self.assertEqual(learner[(self.user_id, self.deck_ids[0])], 1)
        self.assertEqual(learner[(self.user_id, self.deck_ids[1])], 1)
        _ = subject.logical_note_key
        subject.logical_note_key = self.note_ids[2].encode()
        db.session.commit()
        self.assertEqual(self._revisions(), ({}, {
            (self.user_id, self.deck_ids[0]): 2,
            (self.user_id, self.deck_ids[1]): 2,
            (self.user_id, self.deck_ids[2]): 1,
        }))

    def test_fields_tags_and_pristine_subject_envelope_do_not_invalidate(self):
        note = db.session.get(Note, self.note_ids[0])
        note.tags = ["leech"]
        note.field_values = {"Front": "edited"}
        db.session.commit()
        for _ in range(2):
            ensure_and_lock_subject(db.session(), learner_user_id=self.user_id,
                logical_note_key=self.note_ids[0], live_note_id=self.note_ids[0], now_utc=datetime.utcnow())
            db.session.commit()
        self.assertEqual(self._revisions(), ({}, {}))

    def test_released_descendant_rollback_preserves_only_root_scope(self):
        self._add_note(self.deck_ids[0])
        db.session.flush()
        outer = db.session.begin_nested()
        self._add_note(self.deck_ids[1])
        db.session.flush()
        child = db.session.begin_nested()
        self._add_note(self.deck_ids[2])
        db.session.flush()
        child.commit()
        self.assertEqual(self._revisions(), ({}, {}))
        outer.rollback()
        db.session.commit()
        self.assertEqual(self._revisions(), ({self.deck_ids[0]: 1}, {}))
        self.assertEqual(Note.query.filter_by(deck_id=self.deck_ids[1]).count(), 1)
        self.assertEqual(Note.query.filter_by(deck_id=self.deck_ids[2]).count(), 1)

    def test_released_savepoint_is_counted_once_and_root_rollback_clears_buffer(self):
        with db.session.begin_nested():
            self._add_note(self.deck_ids[1])
            db.session.flush()
        db.session.commit()
        self.assertEqual(self._revisions(), ({self.deck_ids[1]: 1}, {}))
        self._add_note(self.deck_ids[2])
        db.session.flush()
        db.session.rollback()
        note = db.session.get(Note, self.note_ids[0])
        note.tags = ["safe"]
        db.session.commit()
        self.assertEqual(self._revisions(), ({self.deck_ids[1]: 1}, {}))

    def test_structured_and_text_bulk_mutations_bump_global_once(self):
        db.session.execute(update(CardProgress).where(CardProgress.user_id == self.user_id)
                           .values(is_suspended=True))
        db.session.execute(text("UPDATE notes SET tags = :tags WHERE id = :note_id"),
                           {"tags": "[]", "note_id": self.note_ids[0]})
        db.session.commit()
        self.assertEqual(self._revisions(), ({0: 1}, {}))

    def test_revision_failure_rolls_back_domain_write_and_captured_scope(self):
        self._add_note(self.deck_ids[0])
        with patch("app.services.deck_count_projection_service.bump_content_revisions",
                   side_effect=RuntimeError("revision storage failed")):
            with self.assertRaisesRegex(RuntimeError, "revision storage failed"):
                db.session.commit()
        db.session.rollback()
        self.assertEqual(Note.query.filter_by(deck_id=self.deck_ids[0]).count(), 1)
        self.assertEqual(self._revisions(), ({}, {}))

    def test_disabled_writer_keeps_domain_commits_without_revision_queries(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        self._add_note(self.deck_ids[0])
        db.session.commit()
        self.assertEqual(self._revisions(), ({}, {}))

    def _dashboard(self):
        # Each HTTP request has its own app context, as in production. Reusing
        # the fixture's outer context would retain Flask-Login's cached user.
        with self.app.app_context(), self.app.test_client() as client:
            with client.session_transaction() as session:
                session["_user_id"] = str(self.user_id)
                session["_fresh"] = True
            response = client.get("/api/dashboard?compact=1")
            self.assertEqual(response.status_code, 200, response.get_json())
            return response.get_json()

    def test_dashboard_summary_hit_preserves_raw_metadata_and_has_no_dml(self):
        # Deck.note_type_id is NULL, so cached counters still need oldest-Note metadata.
        before = self._dashboard()
        db.session.remove()
        warmed = prewarm_owned_deck_counts(user_id=self.user_id)
        self.assertEqual(warmed["published"], 3)
        self.app.config["DECK_COUNT_READ_MODE"] = "summary"
        mutations = []

        def capture(connection, cursor, statement, parameters, context, many):
            if statement.lstrip().split(None, 1)[0].upper() in {"INSERT", "UPDATE", "DELETE", "REPLACE"}:
                mutations.append(statement)

        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            with patch("app.services.dashboard_service.aggregate_deck_study_counts",
                       wraps=aggregate_deck_study_counts) as aggregate:
                after = self._dashboard()
            self.assertEqual(aggregate.call_args.kwargs["visible_deck_ids"], [])
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(after, before)
        self.assertTrue(all(row["note_type_id"] == self.note_type_id for row in after["items"]))
        self.assertEqual(mutations, [])
        # A committed availability change must turn only that cache entry into raw fallback.
        db.session.add(CardProgress(user_id=self.user_id, card_id=self.card_ids[0], queue="learning"))
        db.session.commit()
        with patch("app.services.dashboard_service.aggregate_deck_study_counts",
                   wraps=aggregate_deck_study_counts) as aggregate:
            updated = self._dashboard()
        self.assertEqual(aggregate.call_args.kwargs["visible_deck_ids"], [self.deck_ids[0]])
        self.assertEqual(updated["summary"]["learning"], 1)
        self.app.config["DECK_COUNT_READ_MODE"] = "raw"
        self.assertEqual(updated, self._dashboard())


class DeckCountNotePipelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        note_fixtures.StudyDirectNoteReplayTests.setUpClass()
        cls.app = note_fixtures.StudyDirectNoteReplayTests.app

    def setUp(self):
        self.app.config.update(DECK_COUNT_WRITE_ENABLED=False, DECK_COUNT_READ_MODE="raw",
                               REVIEW_ANALYTICS_WRITE_ENABLED=False, STUDY_NOTE_COUNT_ENABLED=False)
        self.fixture = note_fixtures.StudyDirectNoteReplayTests(
            "test_retry_returns_original_result_without_executing_scheduler_or_side_effects")
        self.fixture.setUp()
        self.app.config.update(DECK_COUNT_WRITE_ENABLED=True, DECK_COUNT_READ_MODE="summary")

    def tearDown(self):
        self.app.config["DECK_COUNT_WRITE_ENABLED"] = False
        self.fixture.doCleanups()

    def _dashboard(self, dirty_ids):
        with patch("app.services.dashboard_service.aggregate_deck_study_counts",
                   wraps=aggregate_deck_study_counts) as aggregate:
            response = self.fixture.client.get("/api/dashboard?compact=1")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(aggregate.call_args.kwargs["visible_deck_ids"], dirty_ids)
        return response.get_json()

    def test_real_note_review_invalidates_cached_availability_and_replay_does_not(self):
        fixture = self.fixture
        with self.app.app_context():
            self.assertEqual(prewarm_owned_deck_counts(user_id=fixture.user_id)["published"], 1)
        pristine = self._dashboard([])
        self.assertEqual(pristine["summary"]["new"], 2)
        fixture.payload["rating"] = "again"
        fixture._answer()
        updated = self._dashboard([fixture.deck_id])
        self.assertEqual((updated["summary"]["new"], updated["summary"]["learning"]), (0, 2))
        with self.app.app_context():
            revisions = dict(db.session.execute(select(
                DeckCountLearnerRevision.effective_deck_id, DeckCountLearnerRevision.revision)
                .where(DeckCountLearnerRevision.user_id == fixture.user_id)).all())
            self.assertEqual(revisions, {fixture.deck_id: 1})
            self.assertEqual(DeckCountContentRevision.query.count(), 0,
                             "An ordinary NOTE review must not invalidate every deck")
            db.session.remove()
            self.assertEqual(prewarm_owned_deck_counts(user_id=fixture.user_id)["published"], 1)
        self.assertTrue(fixture._answer()["authority"]["replayed"])
        self.assertEqual(self._dashboard([]), updated)
        with self.app.app_context():
            revision = db.session.get(DeckCountLearnerRevision, (fixture.user_id, fixture.deck_id))
            self.assertEqual(revision.revision, 1)


if __name__ == "__main__":
    unittest.main()
