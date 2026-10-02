"""P9-05b: pristine NOTE materialization under CANONICAL_V1 writes no card_progress."""

from datetime import datetime
import re
import unittest
from unittest import mock

from sqlalchemy import event

from app.repositories.study_authority_repository import lock_study_authority_route
from app.services import study_progress_lifecycle_mirror_service as lifecycle
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject
from tests import test_study_direct_note_replay as fixtures

BOTH_PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1"})
NOW = datetime(2026, 10, 2, 1, 2, 3)
_TABLE = re.compile(r"\bcard_progress\b", re.IGNORECASE)


def _bytes(value):
    return bytes(value) if isinstance(value, (bytes, bytearray, memoryview)) else value


class StudyCanonicalMaterializationTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _answer = fixtures.StudyDirectNoteReplayTests._answer

    def _set_canonical(self):
        db.session.add(StudyAuthorityStorageProfile(
            id=1, profile_code="CANONICAL_V1", created_at=NOW, updated_at=NOW))
        db.session.commit()

    def _record(self):
        statements = []

        def record(_conn, _cursor, statement, *_args):
            if _TABLE.search(statement):
                statements.append(statement.split()[0].upper())

        engine = db.engine
        event.listen(engine, "before_cursor_execute", record)
        self.addCleanup(lambda: event.remove(engine, "before_cursor_execute", record))
        return statements

    def _add_note(self, word):
        template_card = db.session.get(Card, self.card_ids[0])
        note = Note(user_id=self.user_id, note_type_id=template_card.note.note_type_id,
                    deck_id=self.deck_id, field_values={"Word": word})
        db.session.add(note)
        db.session.flush()
        for card in Card.query.filter_by(note_id=template_card.note_id).all():
            db.session.add(Card(note_id=note.id, template_id=card.template_id))
        db.session.commit()
        return note

    def _materialized(self, note_ids):
        """Profile-independent view of the materialized rows of these Notes."""
        result = {}
        for note_id in note_ids:
            subject = StudyProgressSubject.query.filter_by(
                learner_user_id=self.user_id, logical_note_key=note_id.encode()).one()
            state = db.session.get(StudyProgressState, subject.id)
            token = db.session.get(StudyAuthoritySubjectToken, subject.id)
            availability = {}
            for contributor in StudyProgressContributor.query.filter_by(subject_id=subject.id):
                row = db.session.get(StudyProgressAvailability, contributor.id)
                availability[str(contributor.live_card_id)] = tuple(
                    _bytes(getattr(row, field)) for field in (
                        "normalized_queue", "due_at", "due_day", "is_suspended", "is_buried",
                        "card_created_at", "card_order_key", "semantic_state_hash")
                ) + (contributor.pointer_status, contributor.history_completeness_code,
                     contributor.current_provenance_code, _bytes(contributor.lineage_vector_hash))
            result[note_id] = {
                "subject": (subject.status_code, subject.contributor_count, subject.subject_generation,
                            subject.mirror_revision),
                "state": (dict(state.state_payload), _bytes(state.semantic_state_hash),
                          _bytes(state.algorithm_state_hash), state.algorithm_key),
                "token": (token.authority_revision, _bytes(token.semantic_state_hash)),
                "availability": availability,
            }
        return result

    def _materialize_all(self, notes):
        route = lock_study_authority_route(db.session, learner_user_id=self.user_id, allow_note_authority=True)
        first, *rest = notes
        lifecycle.materialize_pristine_note_authority(
            db.session, route=route, note=first, cards=Card.query.filter_by(note_id=first.id).all(),
            starting_ease=2.5, now_utc=NOW)
        lifecycle.materialize_pristine_notes_bulk(
            db.session, route=route, note_ids=[note.id for note in rest],
            starting_ease_by_note_id={note.id: 2.5 for note in rest}, now_utc=NOW)
        db.session.commit()

    def test_canonical_materialization_matches_the_projection_path_without_card_progress(self):
        with self.app.app_context():
            # Enrollment in setUp already materialized the fixture Note.
            baseline = CardProgress.query.count()
            projected_notes = [self._add_note(f"p{index}") for index in range(3)]
            self._materialize_all(projected_notes)
            projected = self._materialized([note.id for note in projected_notes])
            self.assertEqual(CardProgress.query.count(), baseline + 6)

            self._set_canonical()
            canonical_notes = [self._add_note(f"c{index}") for index in range(3)]
            statements = self._record()
            with mock.patch(
                "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES
            ):
                self._materialize_all(canonical_notes)
            self.assertEqual(statements, [])
            canonical = self._materialized([note.id for note in canonical_notes])
            self.assertEqual(CardProgress.query.count(), baseline + 6)
            kinds = {
                row.evidence_kind for row in StudyProgressContributor.query.join(
                    StudyProgressSubject, StudyProgressSubject.id == StudyProgressContributor.subject_id
                ).filter(StudyProgressSubject.logical_note_key.in_([n.id.encode() for n in canonical_notes]))
            }
            self.assertEqual(kinds, {"CANONICAL"})

        # Same rows except Card identity, which differs between the two Notes sets.
        for projected_note, canonical_note in zip(projected.values(), canonical.values()):
            self.assertEqual(canonical_note["subject"], projected_note["subject"])
            self.assertEqual(canonical_note["state"], projected_note["state"])
            self.assertEqual(canonical_note["token"], projected_note["token"])
            strip = lambda rows: sorted(row[:5] + row[7:] for row in rows.values())  # noqa: E731
            self.assertEqual(strip(canonical_note["availability"]), strip(projected_note["availability"]))

    def test_first_answer_of_a_pristine_note_under_canonical_touches_no_card_progress(self):
        with self.app.app_context():
            self._set_canonical()
            baseline = CardProgress.query.count()
            note = self._add_note("pristine")
            card_ids = [card.id for card in Card.query.filter_by(note_id=note.id).order_by(Card.id)]
            statements = self._record()
        with mock.patch(
            "app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", BOTH_PROFILES
        ):
            self._answer(card_id=card_ids[0])
            self._answer({**self.payload, "operation_key": "second-" + self.payload["operation_key"],
                          "rating": "good"}, card_id=card_ids[1])
        self.assertEqual(statements, [])
        with self.app.app_context():
            self.assertEqual(CardProgress.query.count(), baseline)
            subject = StudyProgressSubject.query.filter_by(logical_note_key=note.id.encode()).one()
            self.assertEqual(db.session.get(StudyAuthoritySubjectToken, subject.id).authority_revision, 2)
            self.assertEqual(
                {row.evidence_kind for row in StudyProgressContributor.query.filter_by(subject_id=subject.id)},
                {"CANONICAL"},
            )


if __name__ == "__main__":
    unittest.main()
