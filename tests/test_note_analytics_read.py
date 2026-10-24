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

from app import create_app
from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template, dashboard_totals


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


class NoteAnalyticsReadTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'WTF_CSRF_ENABLED': False, 'STARTUP_RUN_MAINTENANCE': False,
            'STARTUP_CHECK_DB_CONNECTIVITY': False, 'REDIS_URL': ''})
        # These assertions exercise Card units (two Templates on one Note).
        # Keep a developer's .env Note-count rollout flag out of this fixture;
        # test_study_note_level_counts covers both units explicitly.
        cls.app.config["STUDY_NOTE_COUNT_ENABLED"] = False

    def setUp(self):
        self.addCleanup(self._cleanup)
        with self.app.app_context():
            db.create_all()
            user = User(username='note-analytics', email='note-analytics@example.test')
            db.session.add(user)
            db.session.flush()
            stage_note_authority_enrollment(db.session, learner_user_id=user.id, now_utc=_now())
            deck = Deck(name='Analytics', owner_user_id=user.id)
            note_type = NoteType(name='Analytics', user_id=user.id)
            db.session.add_all([deck, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name='Word', field_type='text', position=0))
            note = Note(user_id=user.id, note_type_id=note_type.id, deck_id=deck.id, field_values={'Word': 'test'})
            templates = [attach_template(db.session, note_type_id=note_type.id, owner_user_id=user.id,
                name=f'Front {index}', front_html='{{Word}}', back_html='{{Word}}') for index in range(2)]
            db.session.add(note)
            db.session.flush()
            self.user_id, self.deck_id = user.id, deck.id
            self.card_ids = [card.id for card in Card.query.filter_by(note_id=note.id).all()]
            db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as login:
            login['_user_id'], login['_fresh'] = str(self.user_id), True

    def _cleanup(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _install_overlay(self):
        from datetime import timedelta
        with self.app.app_context():
            publisher = User(username='publisher', email='publisher@example.test')
            db.session.add(publisher)
            db.session.flush()
            source = Deck(name='Shared source', owner_user_id=publisher.id)
            local = Deck(name='Installed', owner_user_id=self.user_id)
            note_type = NoteType(name='Shared type', user_id=publisher.id)
            db.session.add_all([source, local, note_type])
            db.session.flush()
            db.session.add(FieldDef(note_type_id=note_type.id, name='Word', field_type='text', position=0))
            for index in range(2):
                attach_template(db.session, note_type_id=note_type.id, owner_user_id=publisher.id,
                                name=f'Source {index}', front_html='{{Word}}', back_html='{{Word}}')
            note = Note(user_id=publisher.id, note_type_id=note_type.id, deck_id=source.id,
                        field_values={'Word': 'shared'}, created_at=_now() - timedelta(days=1))
            db.session.add(note)
            db.session.flush()
            item = DeckMarketplaceItem(owner_user_id=publisher.id, source_deck_id=source.id,
                source_note_type_id=note_type.id, title='Shared', publish_status='published', pricing_mode='free')
            db.session.add(item)
            db.session.flush()
            install = DeckInstall(deck_item_id=item.id, user_id=self.user_id, local_deck_id=local.id,
                clone_mode='logical_overlay', source_deck_id=source.id, source_note_type_id=note_type.id,
                source_owner_user_id=publisher.id, base_snapshot_at=_now() + timedelta(seconds=1))
            db.session.add(install)
            db.session.flush()
            db.session.add(DeckCloneDeckMap(deck_install_id=install.id, local_deck_id=local.id, source_deck_id=source.id))
            self.local_deck_id, self.source_note_id, self.install_id = local.id, note.id, install.id
            self.source_card_ids = [card.id for card in Card.query.filter_by(note_id=note.id).all()]
            db.session.commit()

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

    def _audit(self):
        return self.app.test_cli_runner().invoke(
            args=["study-authority-read-audit", "--user-id", str(self.user_id)])

    def test_counts_follow_the_row_and_only_the_audit_rederives_them(self):
        self._answer("again")
        before = dashboard_totals(self._dashboard())
        self.assertEqual((before["new"], before["learning"], before["due"]), (0, 2, 0))
        self.assertEqual(self._audit().exit_code, 0)
        with self.app.app_context():
            # Availability drift without a state change: only the read audit sees it (K1).
            StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().normalized_queue = "new"
            db.session.commit()
        after = dashboard_totals(self._dashboard())
        self.assertEqual((after["new"], after["learning"]), (2, 0))
        audit = self._audit()
        self.assertNotEqual(audit.exit_code, 0, audit.output)

    def test_pristine_note_presentations_never_require_a_progress_fallback(self):
        self._answer("easy")
        before = (dashboard_totals(self._dashboard()), self._overview()["heatmap"])
        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.user_id).one()
            other = Note(user_id=self.user_id, note_type_id=note.note_type_id, deck_id=self.deck_id,
                field_values={"Word": "other"})
            db.session.add(other)
            db.session.flush()
            self.assertEqual(Card.query.filter_by(note_id=other.id).count(), 2)
            self.assertNotIn('card_progress', db.metadata.tables)
            db.session.commit()
        summary, heatmap = dashboard_totals(self._dashboard()), self._overview()["heatmap"]
        # The new pristine Note reads NEW; nothing else moves.
        self.assertEqual(summary["new"], before[0]["new"] + 2)
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

    def test_overview_reads_note_availability_and_full_hash_audit_detects_drift(self):
        self._answer("easy")
        before = self._overview()["heatmap"]
        with self.app.app_context():
            StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).one().semantic_state_hash = b'x' * 32
            db.session.commit()
        self.assertEqual(self._overview()["heatmap"], before)
        self.assertNotEqual(self._audit().exit_code, 0)

    def test_note_overview_shows_the_rows_future_due(self):
        self._answer("easy")
        heatmap = self._overview()["heatmap"]
        self.assertTrue(any(point["is_future"] and point["cards"] for point in heatmap))

    def test_overlay_install_dashboard_counts_the_source_note_row(self):
        self._install_overlay()
        self._answer("easy")
        response = self.client.post(f"/api/study/{self.source_card_ids[0]}/answer", json={
            "rating": "again", "operation_key": str(uuid4()), "duration_ms": 400,
            "scope": "deck", "scope_id": self.local_deck_id})
        self.assertEqual(response.status_code, 200, response.get_json())
        dashboard = self._dashboard()
        installed = [row for row in dashboard["items"] if row["deck_id"] == self.local_deck_id]
        self.assertEqual([row["learn_count"] for row in installed], [2], dashboard["items"])
        self._overview()


if __name__ == "__main__":
    unittest.main()
