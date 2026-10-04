"""NOTE dashboard/overview reads: the consolidated row's availability, lock-free.

Evidence is created by the real NOTE writers (direct answers on an enrolled
learner with one Note and two sibling Cards). Reads trust the row's
availability; only the offline read audit re-derives it from state (ADR P10).
"""

from datetime import datetime, timezone
import unittest
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.sql.dml import Delete, Insert, Update

from tests import test_study_direct_note_replay as fixtures
from tests import test_study_note_overlay as overlay_fixtures
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.note import Note
from models.study_progress_subject import StudyProgressSubject


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NoteAnalyticsReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        fixtures.StudyDirectNoteReplayTests.setUpClass.__func__(cls)
        # These assertions exercise Card units (two Templates on one Note).
        # Keep a developer's .env Note-count rollout flag out of this fixture;
        # test_study_note_level_counts covers both units explicitly.
        cls.app.config["STUDY_NOTE_COUNT_ENABLED"] = False

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

    def _stable_dashboard(self):
        # Deck move tokens are signed with a per-second timestamp; drop them.
        def strip(row):
            return {**{key: value for key, value in row.items() if "move_" not in key},
                "children": [strip(child) for child in row["children"]]}
        body = self._dashboard()
        return {**body, "items": [strip(row) for row in body["items"]]}

    def _overview(self, expected=200):
        response = self.client.get("/api/statistics/overview", query_string={"year": _now().year})
        self.assertEqual(response.status_code, expected, response.get_json())
        return response.get_json()

    def _audit(self):
        return self.app.test_cli_runner().invoke(
            args=["study-authority-read-audit", "--user-id", str(self.user_id)])

    def test_counts_follow_the_row_and_only_the_audit_rederives_them(self):
        self._answer("again")
        before = self._dashboard()["summary"]
        self.assertEqual((before["new"], before["learning"], before["due"]), (0, 2, 0))
        self.assertEqual(self._audit().exit_code, 0)
        with self.app.app_context():
            # Availability drift without a state change: only the read audit sees it (K1).
            StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().normalized_queue = "new"
            db.session.commit()
        after = self._dashboard()["summary"]
        self.assertEqual((after["new"], after["learning"]), (2, 0))
        audit = self._audit()
        self.assertNotEqual(audit.exit_code, 0, audit.output)

    def test_frozen_card_progress_never_serves_note_analytics(self):
        self._answer("easy")
        before = (self._dashboard()["summary"], self._overview()["heatmap"])
        with self.app.app_context():
            # Rows kept from before NOTE, on a studied and on a pristine Note.
            note = Note.query.filter_by(user_id=self.user_id).one()
            other = Note(user_id=self.user_id, note_type_id=note.note_type_id, deck_id=self.deck_id,
                field_values={"Word": "other"})
            db.session.add(other)
            db.session.flush()
            card = Card(note_id=other.id, template_id=db.session.get(Card, self.card_ids[0]).template_id)
            db.session.add(card)
            db.session.flush()
            db.session.add_all([
                CardProgress(user_id=self.user_id, card_id=self.card_ids[0], queue="new",
                             due_at=datetime(_now().year, 12, 30, 12, 0, 0)),
                CardProgress(user_id=self.user_id, card_id=card.id, queue="review", due_day=1),
            ])
            db.session.commit()
        summary, heatmap = self._dashboard()["summary"], self._overview()["heatmap"]
        # The new pristine Note reads NEW; nothing else moves.
        self.assertEqual(summary["new"], before[0]["new"] + 1)
        self.assertEqual((summary["learning"], summary["due"]), (before[0]["learning"], before[0]["due"]))
        self.assertEqual(heatmap, before[1])

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

    def test_note_overview_shows_the_rows_future_due(self):
        self._answer("easy")
        heatmap = self._overview()["heatmap"]
        self.assertTrue(any(point.get("source") == "due" for point in heatmap))

    def test_overlay_install_dashboard_counts_the_source_note_row(self):
        self._install_overlay()
        self._answer("easy")
        response = self.client.post(f"/api/study/{self.source_card_ids[0]}/answer", json={
            "rating": "again", "operation_key": str(uuid4()), "duration_ms": 400,
            "scope": "deck", "scope_id": self.local_deck_id})
        self.assertEqual(response.status_code, 200, response.get_json())
        dashboard = self._stable_dashboard()
        installed = [row for row in dashboard["items"] if row["deck_id"] == self.local_deck_id]
        self.assertEqual([row["learn_count"] for row in installed], [2], dashboard["items"])
        self._overview()


if __name__ == "__main__":
    unittest.main()
