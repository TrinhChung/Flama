"""NOTE dashboard/overview reads: canonical availability, fail-closed, lock-free.

Evidence is created by the real NOTE writers (direct answers on an enrolled
learner with one Note and two sibling Cards), then corrupted one way at a time.
"""

from datetime import datetime, timezone
import unittest
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.sql.dml import Delete, Insert, Update

from tests import test_study_direct_note_replay as fixtures
from tests import test_study_note_overlay as overlay_fixtures
from app.services.study_authority_enrollment_service import stage_legacy_authority_enrollment
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.study_authority_subject_token import StudyAuthoritySubjectToken
from models.study_progress_availability import StudyProgressAvailability
from models.study_progress_contributor import StudyProgressContributor
from models.study_progress_state import StudyProgressState
from models.study_progress_subject import StudyProgressSubject


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NoteAnalyticsReadTests(unittest.TestCase):
    setUpClass = classmethod(fixtures.StudyDirectNoteReplayTests.setUpClass.__func__)
    setUp = fixtures.StudyDirectNoteReplayTests.setUp
    _cleanup = fixtures.StudyDirectNoteReplayTests._cleanup
    _install_overlay = overlay_fixtures.StudyNoteOverlayTests._install_overlay

    def _answer(self, rating):
        response = self.client.post(f"/api/study/{self.card_ids[0]}/answer", json={
            "rating": rating, "operation_key": str(uuid4()), "duration_ms": 400,
            "scope": "deck", "scope_id": self.deck_id})
        self.assertEqual(response.status_code, 200, response.get_json())

    def _dashboard(self, expected=200):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def _overview(self, expected=200):
        response = self.client.get("/api/statistics/overview", query_string={"year": _now().year})
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def _evidence(self):
        subject = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one()
        contributors = (
            StudyProgressContributor.query.filter_by(subject_id=subject.id, contributor_status="ACTIVE")
            .order_by(StudyProgressContributor.id).all()
        )
        return {
            "subject": subject,
            "state": db.session.get(StudyProgressState, subject.id),
            "token": db.session.get(StudyAuthoritySubjectToken, subject.id),
            "contributor": next(row for row in contributors if row.live_card_id == self.card_ids[0]),
            "availability": db.session.get(StudyProgressAvailability, next(
                row.id for row in contributors if row.live_card_id == self.card_ids[0])),
            "progress": CardProgress.query.filter_by(user_id=self.user_id, card_id=self.card_ids[0]).one(),
        }

    def _corrupt_and_expect(self, corrupt, code):
        self._answer("again")
        with self.app.app_context():
            corrupt(self._evidence())
            db.session.commit()
        for body in (self._dashboard(409), self._overview(409)):
            self.assertEqual(body["error"], code)

    def test_counts_come_from_canonical_availability_not_the_projection(self):
        self._answer("again")
        before = self._dashboard()["summary"]
        self.assertEqual((before["new"], before["learning"], before["due"]), (0, 2, 0))
        with self.app.app_context():
            # Content drift without a revision bump: only the read audit sees it (K1).
            CardProgress.query.filter_by(user_id=self.user_id).update({"queue": "new"})
            db.session.commit()
        self.assertEqual(self._dashboard()["summary"], before)
        audit = self.app.test_cli_runner().invoke(args=["study-authority-read-audit", "--user-id", str(self.user_id)])
        self.assertNotEqual(audit.exit_code, 0, audit.output)

    def test_missing_token_is_tolerated_like_the_locking_reader(self):
        self._answer("again")
        with self.app.app_context():
            db.session.delete(self._evidence()["token"])
            db.session.commit()
        self.assertEqual(self._dashboard()["summary"]["learning"], 2)
        self._overview()

    def test_missing_contributor_fails_closed(self):
        def corrupt(evidence):
            db.session.delete(evidence["availability"])
            db.session.delete(evidence["contributor"])
        self._corrupt_and_expect(corrupt, "INCOMPLETE_AUTHORITY_COMPATIBILITY")

    def test_missing_availability_fails_closed(self):
        self._corrupt_and_expect(lambda e: db.session.delete(e["availability"]), "INCOMPLETE_AUTHORITY_COMPATIBILITY")

    def test_missing_projection_row_fails_closed(self):
        self._corrupt_and_expect(lambda e: db.session.delete(e["progress"]), "INCOMPLETE_AUTHORITY_COMPATIBILITY")

    def test_contributor_count_mismatch_fails_closed(self):
        def corrupt(evidence):
            evidence["subject"].contributor_count = 3
        self._corrupt_and_expect(corrupt, "INCOMPLETE_AUTHORITY_COMPATIBILITY")

    def test_state_generation_drift_fails_closed(self):
        def corrupt(evidence):
            evidence["state"].subject_generation = int(evidence["subject"].subject_generation) + 1
        self._corrupt_and_expect(corrupt, "AUTHORITY_GENERATION_DIVERGED")

    def test_mirror_revision_drift_fails_closed(self):
        def corrupt(evidence):
            evidence["state"].mirror_revision = int(evidence["subject"].mirror_revision) + 1
        self._corrupt_and_expect(corrupt, "AUTHORITY_STATE_DIVERGED")

    def test_token_hash_drift_fails_closed(self):
        def corrupt(evidence):
            evidence["token"].semantic_state_hash = b"\x01" * 32
        self._corrupt_and_expect(corrupt, "AUTHORITY_STATE_DIVERGED")

    def test_availability_hash_drift_fails_closed(self):
        def corrupt(evidence):
            evidence["availability"].semantic_state_hash = b"\x02" * 32
        self._corrupt_and_expect(corrupt, "AUTHORITY_READ_PARITY_DIVERGED")

    def test_projection_revision_drift_fails_closed(self):
        def corrupt(evidence):
            evidence["progress"].revision = int(evidence["progress"].revision) + 1
        self._corrupt_and_expect(corrupt, "AUTHORITY_READ_PARITY_DIVERGED")

    def test_detached_subject_fails_closed(self):
        def corrupt(evidence):
            evidence["subject"].live_note_id = None
        self._corrupt_and_expect(corrupt, "DETACHED_AUTHORITY_SUBJECT")

    def test_projection_without_note_state_fails_closed(self):
        self._answer("again")
        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.user_id).one()
            other = Note(user_id=self.user_id, note_type_id=note.note_type_id, deck_id=self.deck_id,
                field_values={"Word": "other"})
            db.session.add(other)
            db.session.flush()
            card = Card(note_id=other.id, template_id=Card.query.get(self.card_ids[0]).template_id)
            db.session.add(card)
            db.session.flush()
            db.session.add(CardProgress(user_id=self.user_id, card_id=card.id, queue="review", due_day=1))
            db.session.commit()
        for body in (self._dashboard(409), self._overview(409)):
            self.assertEqual(body["error"], "INCOMPLETE_AUTHORITY_COVERAGE")

    def test_analytics_routes_take_no_locks_and_write_nothing(self):
        self._answer("again")
        seen = []

        def capture(conn, clause, multiparams, params, execution_options):
            if getattr(clause, "_for_update_arg", None) is not None or isinstance(clause, (Insert, Update, Delete)):
                seen.append(str(clause))

        with self.app.app_context():
            engine = db.engine
        event.listen(engine, "before_execute", capture)
        try:
            self._dashboard()
            self._overview()
        finally:
            event.remove(engine, "before_execute", capture)
        self.assertEqual(seen, [])

    def test_overview_follows_availability_without_projection_fallback(self):
        self._answer("easy")
        before = self._overview()["heatmap"]
        with self.app.app_context():
            CardProgress.query.filter_by(user_id=self.user_id).update(
                {"due_day": None, "due_at": datetime(_now().year, 12, 30, 12, 0, 0)})
            db.session.commit()
        self.assertEqual(self._overview()["heatmap"], before)

    def test_note_dashboard_and_overview_equal_legacy_on_same_data(self):
        self._answer("easy")
        note_view = (self._dashboard()["summary"], self._overview()["heatmap"])
        self.assertTrue(any(point.get("source") == "due" for point in note_view[1]))
        with self.app.app_context():
            stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=_now())
            db.session.commit()
        self.assertEqual((self._dashboard()["summary"], self._overview()["heatmap"]), note_view)

    def test_overlay_install_dashboard_and_overview_equal_legacy(self):
        self._install_overlay()
        self._answer("easy")
        response = self.client.post(f"/api/study/{self.source_card_ids[0]}/answer", json={
            "rating": "again", "operation_key": str(uuid4()), "duration_ms": 400,
            "scope": "deck", "scope_id": self.local_deck_id})
        self.assertEqual(response.status_code, 200, response.get_json())
        note_view = (self._dashboard(), self._overview())
        installed = [row for row in note_view[0]["items"] if row["deck_id"] == self.local_deck_id]
        self.assertEqual([row["learn_count"] for row in installed], [2], note_view[0]["items"])
        with self.app.app_context():
            stage_legacy_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=_now())
            db.session.commit()
        self.assertEqual((self._dashboard(), self._overview()), note_view)


if __name__ == "__main__":
    unittest.main()
