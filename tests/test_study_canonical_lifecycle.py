"""P9-05c: NOTE lifecycle under CANONICAL_V1 matches the projection path, without card_progress."""

from datetime import datetime
import re
import traceback
import unittest
from unittest import mock
from uuid import uuid4

from sqlalchemy import event

from app.services import flashcard_content_service as content
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.review_event import ReviewEvent
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_history_fact import StudyProgressHistoryFact
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from tests import test_study_direct_note_replay as fixtures
from tests import test_study_note_templates as template_tests

BOTH_PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1"})
NOW = datetime(2026, 10, 2)
_TABLE = re.compile(r"\bcard_progress\b", re.IGNORECASE)
_STABLE_STATE_KEYS = ("type", "reps", "lapses", "step_index", "ease", "suspended", "leeched")


class StudyCanonicalLifecycleTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer
    _review = template_tests.StudyNoteTemplateTests._review
    _update = template_tests.StudyNoteTemplateTests._update

    def _snapshot(self):
        """Time-independent view of every NOTE row the story touched."""
        subject = StudyProgressSubject.query.one()
        state = db.session.get(StudyProgressState, subject.id)
        token = db.session.get(StudyAuthoritySubjectToken, subject.id)
        contributors = sorted(
            (
                row.contributor_status,
                row.current_provenance_code,
                row.history_completeness_code,
                row.pointer_status,
                int(row.subject_generation),
                row.live_card_id is not None,
                db.session.get(StudyProgressAvailability, row.id) is not None,
            )
            for row in StudyProgressContributor.query.all()
        )
        availability = sorted(
            (row.normalized_queue, bool(row.is_suspended), bool(row.is_buried), int(row.subject_generation))
            for row in StudyProgressAvailability.query.all()
        )
        events = [
            (row.transition_code, int(row.old_generation), int(row.new_generation),
             row.evidence_payload["old_contributor_count"], row.evidence_payload["new_contributor_count"],
             row.evidence_payload["removed_card_count"], row.new_topology_hash is None)
            for row in StudyProgressLifecycleEvent.query.order_by(StudyProgressLifecycleEvent.id)
        ]
        return {
            "subject": (subject.status_code, int(subject.contributor_count), int(subject.subject_generation),
                        int(subject.mirror_revision), subject.live_note_id is None),
            "state": None if state is None else {key: state.state_payload.get(key) for key in _STABLE_STATE_KEYS},
            "token": (int(token.subject_generation), int(token.authority_revision),
                      token.semantic_state_hash is None),
            "contributors": contributors,
            "availability": availability,
            "lifecycle": events,
            "counts": (Card.query.count(), ReviewEvent.query.count(), StudyProgressHistoryFact.query.count()),
        }

    def _story(self, before_reset=None):
        snapshots = {}
        self._review()
        with self.app.app_context():
            self._update({"added": [{"name": "Reverse"}]})
            db.session.commit()
            snapshots["template_added"] = self._snapshot()
            self._update({"removed": ["Card 1"]}, confirmed=True)
            db.session.commit()
            snapshots["template_removed"] = self._snapshot()
            if before_reset is not None:
                before_reset()
        reset = self.client.post(f"/api/decks/{self.deck_id}/progress-reset")
        self.assertEqual(reset.status_code, 200, reset.get_json())
        with self.app.app_context():
            snapshots["reset"] = self._snapshot()
        self._answer({**self.payload, "operation_key": str(uuid4()), "rating": "good"})
        with self.app.app_context():
            snapshots["answered_after_reset"] = self._snapshot()
            note_id = Note.query.one().id
            self.assertEqual(content.delete_note(user_id=self.user_id, note_id=note_id), {"success": True})
            snapshots["note_deleted"] = self._snapshot()
        return snapshots

    def _keep_progress_ids_fresh(self):
        # SQLite reuses the highest deleted rowid; MySQL never reuses ids. A
        # filler row above every id keeps the projection reset's new rows on
        # fresh ids, as in production, so they never match old contributors.
        top = db.session.execute(db.select(db.func.max(CardProgress.id))).scalar() or 0
        db.session.execute(CardProgress.__table__.insert().values(
            id=top + 1000, user_id=self.user_id, card_id="filler-card", queue="new", step_index=0,
            interval_days=0, is_suspended=False, is_buried=False, review_kind="review",
            scheduler_mode="legacy", ease_factor=2.5, last_leech_lapses=0, reps=0, lapses=0,
            revision=0, created_at=NOW, updated_at=NOW))
        db.session.commit()

    def test_lifecycle_story_matches_the_projection_path_without_card_progress(self):
        projected = self._story(before_reset=self._keep_progress_ids_fresh)

        self._cleanup()
        self.setUp()
        with self.app.app_context():
            db.session.add(StudyAuthorityStorageProfile(
                id=1, profile_code="CANONICAL_V1", created_at=NOW, updated_at=NOW))
            db.session.execute(CardProgress.__table__.delete())
            db.session.commit()
            engine = db.engine
        statements = []

        def record(_conn, _cursor, statement, *_args):
            if not _TABLE.search(statement) or statement.lstrip().upper().startswith("DELETE"):
                return
            # Deleting a Card cascades to its (already emptied) progress rows
            # at flush time: cleanup of the frozen projection, not a read.
            if any(
                frame.name == "cascade_iterator"
                or frame.filename.replace("\\", "/").endswith(("orm/dependency.py", "orm/unitofwork.py"))
                for frame in traceback.extract_stack()
            ):
                return
            statements.append(statement.split()[0].upper())

        event.listen(engine, "before_cursor_execute", record)
        try:
            with mock.patch(
                "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES
            ):
                canonical = self._story()
        finally:
            event.remove(engine, "before_cursor_execute", record)

        # Content deletion still clears frozen card_progress rows (cleanup, ADR §2.5);
        # nothing reads, inserts or updates them.
        self.assertEqual(statements, [])
        with self.app.app_context():
            self.assertEqual(CardProgress.query.count(), 0)
        for step in projected:
            with self.subTest(step=step):
                self.assertEqual(canonical[step], projected[step])


if __name__ == "__main__":
    unittest.main()
