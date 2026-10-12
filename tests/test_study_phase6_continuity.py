"""Phase 6 exit-gate continuity: removing a Template keeps the learner's Note.

The fixture Note has two Templates, the learner is on NOTE authority and has
reviewed the Card of the Template that is then deleted while a v4 session on
that Template is open.
"""

import unittest
from unittest.mock import patch
from uuid import uuid4

from tests import test_study_direct_note_replay as fixtures
from app.services import flashcard_content_service as content
from app.services.study_composition_service import make_compatibility_composition_id
from models import db
from models.card import Card
from models.connect_source_card_ref import ConnectSourceCardRef
from models.review_event import ReviewEvent
from models.study_application import StudyApplication
from tests.study_note_fixtures import assert_retired_progress_absent
from models.note_type import NoteType
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.template import Template


class StudyPhase6ContinuityTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def test_template_delete_keeps_note_state_history_and_external_ref(self):
        removed_card_id = self.card_ids[1]
        self._answer(card_id=removed_card_id)
        with self.app.app_context():
            card = db.session.get(Card, removed_card_id)
            note_id, template_id = card.note_id, card.template_id
            note_type_id = card.note.note_type_id
            db.session.add(ConnectSourceCardRef(
                user_id=self.user_id, source_key="anki", external_card_id="ext-1",
                external_note_id="ext-n", source_ord=1, card_id=removed_card_id,
                snapshot_hash="h" * 64, applied_local_revision=1, review_cursor=7,
            ))
            db.session.commit()
            row_before = StudyProgressSubject.query.one()
            before = (row_before.authority_revision, bytes(row_before.semantic_state_hash),
                      dict(row_before.state_payload))
            self.assertEqual(ReviewEvent.query.one().note_id, note_id)

        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            opened = self.client.post("/api/study/sessions", json={
                "scope": "deck", "scope_id": self.deck_id,
                "composition_id": make_compatibility_composition_id(note_type_id, template_id),
                "accepted_session_schema_versions": ["study-session.v4"],
                "accepted_note_storage_profiles": ["note-mysql-float-text.v1"],
            })
            self.assertEqual(opened.status_code, 201, opened.get_json())
            snapshot = opened.get_json()

        with self.app.app_context():
            content.delete_template(user_id=self.user_id, note_type_id=note_type_id, template_id=template_id)
            self.assertIsNone(db.session.get(Card, removed_card_id))
            self.assertEqual(StudyApplication.query.filter_by(template_id=template_id, status_code="ACTIVE").count(), 0)
            self.assertIsNotNone(db.session.get(Template, template_id))
            self.assertEqual(db.session.get(StudySession, snapshot["session_id"]).status, "open")
            row = StudyProgressSubject.query.one()
            self.assertEqual(
                (row.authority_revision, bytes(row.semantic_state_hash), dict(row.state_payload)),
                before,
            )
            event = ReviewEvent.query.one()
            self.assertEqual((event.card_id, event.note_id), (removed_card_id, note_id))
            ref = ConnectSourceCardRef.query.one()
            self.assertEqual((ref.note_id, ref.source_ord, ref.review_cursor), (note_id, 1, 7))
            if db.engine.dialect.name == "mysql":  # SQLite tests do not enforce foreign keys
                self.assertIsNone(ref.card_id)

        with patch.dict(self.app.config, STUDY_WIRE_V4_ENABLED=True):
            committed = self.client.post(f"/api/study/sessions/{snapshot['session_id']}/commit", json={
                "schema_version": "study-commit.v3", "commit_id": str(uuid4()),
                "session_token": snapshot["session_token"], "snapshot_hash": snapshot["snapshot_hash"],
                "commit_reason": "manual_exit", "events": [], "final_states": [],
            })
        self.assertEqual(committed.status_code, 200, committed.get_json())

        # The surviving sibling still studies from the same Note state.
        self._answer(dict(self.payload, operation_key=str(uuid4())), card_id=self.card_ids[0])
        with self.app.app_context():
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, before[0] + 1)


class StudyRepeatedApplicationTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def test_a_template_applied_twice_shares_one_note_state(self):
        from app.repositories.study_authority_repository import lock_study_authority_route
        from app.services.study_application_service import stage_repeated_application

        self._answer()  # state exists before the second occurrence is added
        with self.app.app_context():
            template = db.session.get(Card, self.card_ids[0]).template
            note_id = db.session.get(Card, self.card_ids[0]).note_id
            routes = (lock_study_authority_route(
                db.session, learner_user_id=self.user_id, allow_note_authority=True),)
            occurrence = stage_repeated_application(
                db.session, routes=routes, template=template, note_type=db.session.get(NoteType, db.session.get(Card, self.card_ids[0]).note.note_type_id), occurrence_key="repeat-1")
            db.session.commit()
            repeated = Card.query.filter_by(application_id=occurrence.id).one()
            self.assertEqual((repeated.note_id, repeated.template_id), (note_id, template.id))
            self.assertEqual(Card.query.filter_by(note_id=note_id, template_id=template.id).count(), 2)
            # The occurrence's Card shares the Note's one row; nothing is copied (ADR P10).
            self.assertEqual(StudyProgressSubject.query.count(), 1)
            assert_retired_progress_absent(self, db.session)
            revision = StudyProgressSubject.query.one().authority_revision
            repeated_id = repeated.id

        # Answering through the repeated occurrence schedules the one Note.
        self._answer(dict(self.payload, operation_key=str(uuid4())), card_id=repeated_id)
        with self.app.app_context():
            self.assertEqual(StudyProgressSubject.query.one().authority_revision, revision + 1)
            self.assertEqual(StudyProgressSubject.query.count(), 1)


if __name__ == "__main__":
    unittest.main()
