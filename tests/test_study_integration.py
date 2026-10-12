"""Real NOTE review persistence, counters and scheduling boundaries."""

import unittest
from datetime import datetime, timedelta
from uuid import uuid4

from app import create_app
from app.repositories.study_repository import study_bucket_for_progress_values
from app.services.anki_scheduler import _day_index
from app.services.study_service import execute_native_review_command
from models import db
from models.card import Card
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.study_progress_subject import StudyProgressSubject
from models.user import User
from tests.note_progress_fixtures import stage_note_state, decode_note_state, subject_for_card
from tests.study_note_fixtures import attach_template, enroll_note_user, assert_retired_progress_absent


class StudyCounterIntegrationTest(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "WTF_CSRF_ENABLED": False, "REDIS_URL": "", "STUDY_NOTE_COUNT_ENABLED": True})
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        db.create_all()
        self.addCleanup(db.drop_all)
        self.addCleanup(db.session.remove)
        user = User(username="integration-note", email="integration-note@example.test")
        db.session.add(user)
        db.session.flush()
        enroll_note_user(db.session, user)
        deck = Deck(name="NOTE integration", owner_user_id=user.id)
        note_type = NoteType(name="NOTE integration", user_id=user.id)
        db.session.add_all([deck, note_type])
        db.session.flush()
        for position in range(2):
            attach_template(db.session, owner_user_id=user.id, note_type_id=note_type.id,
                name=f"Presentation {position}", position=position, front_html="{{Word}}", back_html="{{Word}}")
        self.note_ids = []
        self.card_ids = []
        for index in range(5):
            note = Note(user_id=user.id, deck_id=deck.id, note_type_id=note_type.id, field_values={"Word": str(index)})
            db.session.add(note)
            db.session.flush()
            self.note_ids.append(note.id)
            self.card_ids.append(Card.query.filter_by(note_id=note.id).order_by(Card.id).first().id)
        self.user_id, self.deck_id = user.id, deck.id
        db.session.commit()
        self.client = self.app.test_client()
        with self.client.session_transaction() as login:
            login["_user_id"], login["_fresh"] = str(user.id), True

    def _review(self, index, now, *, rating="good", timezone_name="UTC", **initial):
        stage_note_state(db.session, user_id=self.user_id, card_id=self.card_ids[index], now=now, **initial)
        db.session.commit()
        execute_native_review_command(user=db.session.get(User, self.user_id),
            card=db.session.get(Card, self.card_ids[index]), action=rating,
            payload={"operation_key": str(uuid4()), "duration_ms": 500}, clone_scope=None,
            requested_scope_id=self.deck_id, timezone_name=timezone_name, now=now)
        subject = subject_for_card(db.session, user_id=self.user_id, card_id=self.card_ids[index])
        self.assertEqual(subject.authority_revision, 1)
        self.assertEqual(StudyProgressSubject.query.filter_by(live_note_id=self.note_ids[index]).count(), 1)
        assert_retired_progress_absent(self, db.session)
        return decode_note_state(subject)

    def test_new_cards_show_in_counter(self):
        self.assertEqual(StudyProgressSubject.query.count(), 0)
        self.assertEqual(Card.query.count(), 10)
        response = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(response.get_json()["new_count"], 5)
        self.assertEqual(StudyProgressSubject.query.count(), 0)

    def test_learning_card_after_good_answer(self):
        now = datetime(2026, 2, 22, 9)
        state = self._review(0, now, queue="new")
        self.assertEqual(state.type, "learning")
        self.assertGreater(state.due, now)

    def test_review_card_scheduling(self):
        now = datetime(2026, 2, 22, 9)
        state = self._review(1, now, queue="learning", step_index=1, due_at=now + timedelta(minutes=10))
        self.assertEqual(state.type, "review")
        self.assertIsNotNone(state.dueDay)
        self.assertGreater(state.intervalDays, 0)

    def test_review_interval_persistence_matches_due_day_rounding(self):
        now = datetime(2026, 2, 22, 9)
        state = self._review(2, now, rating="easy", queue="review", due_at=now,
                             interval_days=10, ease_factor=2.5)
        self.assertEqual(state.type, "review")
        # NOTE keeps the exact algorithm interval; its availability uses the
        # scheduler's rounded day anchor, without lossy legacy integer storage.
        self.assertEqual(int(state.intervalDays + 0.5), state.dueDay - _day_index(now, 4))

    def test_interday_learning_persists_boundary_due_time(self):
        now = datetime(2026, 2, 22, 18, 55)
        state = self._review(3, now, queue="new", timezone_name="Asia/Tokyo")
        self.assertEqual(state.type, "learning")
        self.assertEqual(state.intervalDays, 1)
        self.assertEqual(state.due, datetime(2026, 2, 22, 19))
        self.assertEqual(state.dueDay, datetime(2026, 2, 23).date().toordinal())

    def test_buried_progress_is_hidden_until_its_day_expires(self):
        now = datetime(2026, 8, 13, 12)
        today = _day_index(now, 4, timezone_name="Asia/Tokyo")
        common = dict(queue="new", due_at=None, due_day=None, is_suspended=False, is_buried=True,
                      now=now, timezone_name="Asia/Tokyo", day_boundary_hour_local=4)
        self.assertIsNone(study_bucket_for_progress_values(**common, buried_until_day=today + 1))
        self.assertEqual(study_bucket_for_progress_values(**common, buried_until_day=today - 1), "new")


if __name__ == "__main__":
    unittest.main()
