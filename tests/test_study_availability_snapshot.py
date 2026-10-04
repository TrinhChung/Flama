"""P5-11e: the set-wise availability snapshot equals the locking reader's availability."""

from datetime import datetime, timezone
import unittest
from unittest.mock import patch

from sqlalchemy import JSON, event

from app.repositories.study_authority_repository import StudyAuthorityFenceError, lock_study_authority_route
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import (
    load_study_authority_availability_snapshot,
    load_study_authority_card_reads,
    StudyAuthorityReadError,
    summarize_study_authority_queue,
)
from models import db
from models.card import Card
from models.note import Note
from models.study_progress_subject import StudyProgressSubject
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

    def test_classifier_keeps_locked_presence_reads_without_loading_state_document(self):
        from app.services.study_note_pristine_service import classify_note_authority_keys

        self._answer()
        with self.app.app_context():
            card = db.session.get(Card, self.card_ids[0])
            stateful_id = str(card.note_id)
            pristine = Note(user_id=self.user_id, note_type_id=card.note.note_type_id,
                            deck_id=self.deck_id, field_values={"Word": "pristine"})
            db.session.add(pristine)
            db.session.flush()
            pristine_id = str(pristine.id)
            db.session.commit()
            reads = []
            def capture(_conn, statement, *_args):
                if "FROM study_progress_subjects" in str(statement):
                    reads.append((tuple(statement.selected_columns.keys()),
                                  getattr(statement, "_for_update_arg", None) is not None))
            event.listen(db.engine, "before_execute", capture)
            try:
                stateful, untouched = classify_note_authority_keys(
                    db.session, learner_user_id=self.user_id,
                    note_ids=[stateful_id, pristine_id],
                )
            finally:
                event.remove(db.engine, "before_execute", capture)
            self.assertEqual(stateful, frozenset([stateful_id]))
            self.assertEqual(untouched, frozenset([pristine_id]))
            self.assertEqual(reads, [(("logical_note_key", "status_code", "live_note_id", "has_state"), True)])
            db.session.rollback()

    def test_classifier_preserves_json_null_as_missing_state(self):
        from app.services.study_note_pristine_service import classify_note_authority_keys

        self._answer()
        with self.app.app_context():
            subject = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
            note_id = str(subject.live_note_id)
            subject.state_payload = JSON.NULL
            db.session.commit()
            with self.assertRaises(StudyAuthorityFenceError) as raised:
                classify_note_authority_keys(db.session, learner_user_id=self.user_id, note_ids=[note_id])
            self.assertEqual(raised.exception.code, "INCOMPLETE_AUTHORITY_COVERAGE")
            db.session.rollback()

    def test_siblings_validate_once_but_keep_card_specific_order_metadata(self):
        from app.services import study_note_card_projection as projection

        self._answer()
        with self.app.app_context():
            _scope, cards = self._scope_and_cards()
            options = resolve_deck_options(user_id=self.user_id, deck_id=self.deck_id)
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            with patch.object(projection, "project_note_state", wraps=projection.project_note_state) as projected:
                reads = load_study_authority_card_reads(
                    db.session, learner_user_id=self.user_id, cards=tuple(cards),
                    now_utc=now, timezone_name="UTC",
                    deck_options_by_card_id={str(card.id): options for card in cards},
                )
            self.assertEqual(projected.call_count, 1)
            self.assertEqual(set(reads), set(self.card_ids))
            for card in cards:
                self.assertEqual(reads[str(card.id)].availability.card_order_key, str(card.id).encode())
                self.assertEqual(reads[str(card.id)].availability.card_created_at, card.created_at)
            db.session.rollback()

    def test_memoized_sibling_validation_still_rejects_availability_drift(self):
        self._answer()
        with self.app.app_context():
            subject = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
            subject.normalized_queue = "new"
            db.session.commit()
            _scope, cards = self._scope_and_cards()
            options = resolve_deck_options(user_id=self.user_id, deck_id=self.deck_id)
            with self.assertRaises(StudyAuthorityReadError) as raised:
                load_study_authority_card_reads(
                    db.session, learner_user_id=self.user_id, cards=tuple(cards),
                    now_utc=datetime.now(timezone.utc).replace(tzinfo=None), timezone_name="UTC",
                    deck_options_by_card_id={str(card.id): options for card in cards},
                )
            self.assertEqual(raised.exception.code, "AUTHORITY_READ_PARITY_DIVERGED")
            db.session.rollback()


if __name__ == "__main__":
    unittest.main()
