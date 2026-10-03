"""P5-11e: the set-wise availability snapshot equals the locking reader's availability."""

from datetime import datetime, timezone
import unittest

from app.repositories.study_authority_repository import lock_study_authority_route
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import (
    load_study_authority_availability_snapshot,
    load_study_authority_card_reads,
    summarize_study_authority_queue,
)
from models import db
from models.card import Card
from models.note import Note
from tests import test_study_direct_note_replay as fixtures


class StudyAvailabilitySnapshotTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def _scope_and_cards(self):
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == self.user_id, Note.deck_id == self.deck_id)
        scope = query.with_entities(
            Note.deck_id.label("deck_id"), Card.id.label("card_id"), Card.note_id.label("note_id"),
        ).order_by(None).subquery("scope")
        return scope, query.order_by(Card.id.asc()).all()

    def test_snapshot_matches_the_locking_reader_for_studied_and_pristine_notes(self):
        self._answer()  # the fixture Note (two Cards) gets NOTE state
        with self.app.app_context():
            note = Note(user_id=self.user_id, note_type_id=db.session.get(Card, self.card_ids[0]).note.note_type_id,
                        deck_id=self.deck_id, field_values={"Word": "pristine"})
            db.session.add(note)
            db.session.flush()
            db.session.add(Card(note_id=note.id, template_id=db.session.get(Card, self.card_ids[0]).template_id))
            db.session.commit()
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            scope, cards = self._scope_and_cards()
            self.assertEqual(len(cards), 3)
            snapshot = load_study_authority_availability_snapshot(
                db.session, learner_user_id=self.user_id, cards=cards, scope=scope, now_utc=now)
            lock_study_authority_route(db.session, learner_user_id=self.user_id, allow_note_authority=True)
            reads = load_study_authority_card_reads(
                db.session, learner_user_id=self.user_id, cards=tuple(cards), now_utc=now, timezone_name="UTC",
                deck_options_by_card_id={str(card.id): resolve_deck_options(user_id=self.user_id,
                                                                              deck_id=self.deck_id)
                                         for card in cards})
            self.assertEqual({key: value.availability for key, value in snapshot.items()},
                             {key: value.availability for key, value in reads.items()})
            self.assertEqual(
                summarize_study_authority_queue(cards=tuple(cards), reads_by_card_id=snapshot,
                                                learner_user_id=self.user_id, now_utc=now, timezone_name="UTC"),
                summarize_study_authority_queue(cards=tuple(cards), reads_by_card_id=reads,
                                                learner_user_id=self.user_id, now_utc=now, timezone_name="UTC"),
            )
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
