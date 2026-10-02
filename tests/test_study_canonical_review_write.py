"""P9-05a: an existing-state NOTE review under CANONICAL_V1 writes no card_progress."""

from datetime import datetime, timezone
import re
import unittest
from unittest import mock
from uuid import uuid4

from sqlalchemy import event

from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import load_study_authority_card_reads
from app.services.study_note_card_projection import NoteCardBurial, project_note_card
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.review_event import ReviewEvent
from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_state import StudyProgressState
from tests import test_study_direct_note_replay as fixtures

BOTH_PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1"})
NOW = datetime(2026, 10, 1)


def _without_replayed(value):
    if isinstance(value, dict):
        return {key: _without_replayed(item) for key, item in value.items() if key != "replayed"}
    return value


class StudyCanonicalReviewWriteTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def _switch_to_canonical_without_projection(self):
        with self.app.app_context():
            db.session.add(StudyAuthorityStorageProfile(
                id=1, profile_code="CANONICAL_V1", created_at=NOW, updated_at=NOW))
            db.session.execute(CardProgress.__table__.delete())
            db.session.commit()

    def _card_progress_statements(self):
        statements = []

        def record(_conn, _cursor, statement, *_args):
            # The table, not contributor columns such as live_card_progress_id.
            if re.search(r"card_progress", statement, re.IGNORECASE):
                statements.append(statement.split()[0].upper())

        return statements, record

    def test_review_under_canonical_writes_state_availability_history_and_no_projection(self):
        self._answer()  # first state under PROJECTION_V1 (pristine materialization)
        self._switch_to_canonical_without_projection()
        statements, record = self._card_progress_statements()
        second = {**self.payload, "operation_key": str(uuid4()), "rating": "good"}

        with mock.patch(
            "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES
        ):
            with self.app.app_context():
                event.listen(db.engine, "before_cursor_execute", record)
            try:
                response = self._answer(second, card_id=self.card_ids[1])
                replay = self._answer(second, card_id=self.card_ids[1])
            finally:
                with self.app.app_context():
                    event.remove(db.engine, "before_cursor_execute", record)
            self.assertEqual(_without_replayed(replay), _without_replayed(response))
            self.assertEqual(statements, [])

            with self.app.app_context():
                self.assertEqual(CardProgress.query.count(), 0)
                self.assertEqual(ReviewEvent.query.count(), 2)
                self.assertEqual(StudyAuthorityCommandReceipt.query.count(), 2)
                self.assertEqual(
                    StudyProgressHistoryFact.query.filter(
                        StudyProgressHistoryFact.review_event_id.isnot(None)).count(),
                    2,
                )
                token = StudyAuthoritySubjectToken.query.one()
                state = StudyProgressState.query.one()
                self.assertEqual(token.authority_revision, 2)
                self.assertEqual(bytes(token.semantic_state_hash), bytes(state.semantic_state_hash))
                receipt = StudyAuthorityCommandReceipt.query.order_by(
                    StudyAuthorityCommandReceipt.created_at.desc(),
                    StudyAuthorityCommandReceipt.id.desc(),
                ).first()

                contributors = {
                    str(row.live_card_id): row
                    for row in StudyProgressContributor.query.filter_by(contributor_status="ACTIVE")
                }
                self.assertEqual(set(contributors), {str(card_id) for card_id in self.card_ids})
                reviewed = contributors[str(self.card_ids[1])]
                self.assertEqual(reviewed.pointer_status, "VALID")
                self.assertEqual(reviewed.current_provenance_code, "NATIVE_DIRECT")
                for card_id, contributor in contributors.items():
                    availability = db.session.get(StudyProgressAvailability, contributor.id)
                    card = db.session.get(Card, card_id)
                    expected = project_note_card(
                        state.state_payload,
                        burial=NoteCardBurial(),
                        card_id=card_id,
                        card_created_at=card.created_at,
                    ).availability
                    for field in ("normalized_queue", "due_at", "due_day", "semantic_state_hash"):
                        stored = getattr(availability, field)
                        stored = bytes(stored) if isinstance(stored, (bytes, memoryview)) else stored
                        self.assertEqual(stored, getattr(expected, field), (card_id, field))

                cards = Card.query.filter(Card.id.in_(self.card_ids)).all()
                reads = load_study_authority_card_reads(
                    db.session,
                    learner_user_id=self.user_id,
                    cards=tuple(cards),
                    now_utc=datetime.now(timezone.utc).replace(tzinfo=None),
                    timezone_name="UTC",
                    deck_options_by_card_id={
                        str(card.id): resolve_deck_options(user_id=self.user_id, deck_id=self.deck_id)
                        for card in cards
                    },
                )
                self.assertEqual({read.authority_revision for read in reads.values()}, {2})
                db.session.rollback()
        self.assertIsNotNone(receipt)


if __name__ == "__main__":
    unittest.main()
