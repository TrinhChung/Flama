"""Tests for Today + Future Due statistics."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from app import create_app
from app.services.stats_today_future import build_today_future_stats
from models import db
from models.flashcard import ReviewEvent
from models.user import User
from models.deck import Deck
from tests.study_note_fixtures import attach_template, enroll_note_user
from tests.note_progress_fixtures import stage_note_state
from models.note_type import NoteType
from models.note import Note


class StatsTodayFutureTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username="stats2-user", email="stats2@example.com", timezone="UTC")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            enroll_note_user(db.session, user)
            self.user_id = user.id

            deck = Deck(name="Deck A", owner_user_id=user.id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            note_type = NoteType(name="Forecast fixture", user_id=user.id)
            db.session.add(note_type)
            db.session.flush()
            attach_template(db.session, note_type_id=note_type.id, owner_user_id=user.id, name="Card")
            self.note_type_id = note_type.id
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self):
        self.client.post(
            "/login",
            data={"email": "stats2@example.com", "password": "password"},
            follow_redirects=True,
        )

    def _add_progress(
        self,
        *,
        due_at: datetime | None,
        interval_days: int,
        queue: str = "review",
        due_day: int | None = None,
        is_suspended: bool = False,
    ):
        note = Note(user_id=self.user_id, deck_id=self.deck_id, note_type_id=self.note_type_id)
        db.session.add(note)
        db.session.flush()
        return stage_note_state(db.session, user_id=self.user_id, note_id=note.id,
            queue=queue, due_at=due_at, due_day=due_day, interval_days=interval_days, is_suspended=is_suspended)

    def test_backlog_on_off(self):
        with self.app.app_context():
            now_utc = datetime(2026, 2, 23, 12, 0, 0)
            self._add_progress(due_at=datetime(2026, 2, 22, 12, 0, 0), interval_days=3)
            self._add_progress(due_at=datetime(2026, 2, 24, 9, 0, 0), interval_days=3)
            db.session.commit()

            payload_off = build_today_future_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                deck_id=None,
                history_range="12m",
                future_range="30",
                backlog=False,
                now_utc=now_utc,
            )
            offsets_off = [point["day_offset"] for point in payload_off["future_due"]["series"]]
            self.assertTrue(all(offset >= 0 for offset in offsets_off))

            payload_on = build_today_future_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                deck_id=None,
                history_range="12m",
                future_range="30",
                backlog=True,
                now_utc=now_utc,
            )
            offsets_on = [point["day_offset"] for point in payload_on["future_due"]["series"]]
            self.assertIn(-1, offsets_on)
            self.assertGreater(len(offsets_on), len(offsets_off))

    def test_due_tomorrow(self):
        with self.app.app_context():
            now_utc = datetime(2026, 2, 23, 12, 0, 0)
            self._add_progress(due_at=datetime(2026, 2, 24, 1, 0, 0), interval_days=4)
            self._add_progress(due_at=datetime(2026, 2, 24, 18, 0, 0), interval_days=5)
            self._add_progress(due_at=datetime(2026, 2, 25, 10, 0, 0), interval_days=6)
            db.session.commit()

            payload = build_today_future_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                deck_id=None,
                history_range="12m",
                future_range="30",
                backlog=False,
                now_utc=now_utc,
            )
            self.assertEqual(payload["totals"]["due_tomorrow"], 1)

    def test_daily_load_formula(self):
        with self.app.app_context():
            now_utc = datetime(2026, 2, 23, 12, 0, 0)
            self._add_progress(due_at=datetime(2026, 2, 24, 12, 0, 0), interval_days=10)
            self._add_progress(due_at=datetime(2026, 2, 24, 12, 0, 0), interval_days=2)
            self._add_progress(due_at=datetime(2026, 2, 24, 12, 0, 0), interval_days=0, queue="new")
            self._add_progress(
                due_at=datetime(2026, 2, 24, 12, 0, 0),
                interval_days=1,
                is_suspended=True,
            )
            db.session.commit()

            payload = build_today_future_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                deck_id=None,
                history_range="12m",
                future_range="30",
                backlog=False,
                now_utc=now_utc,
            )
            self.assertAlmostEqual(payload["totals"]["daily_load"], 0.6, places=6)

    def test_future_due_uses_review_due_day_over_stale_due_at(self):
        with self.app.app_context():
            now_utc = datetime(2026, 2, 23, 12, 0, 0)
            self._add_progress(
                due_at=datetime(2026, 2, 22, 8, 0, 0),
                due_day=datetime(2026, 2, 24).date().toordinal(),
                interval_days=4,
                queue="review",
            )
            db.session.commit()

            payload = build_today_future_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                deck_id=None,
                history_range="12m",
                future_range="30",
                backlog=False,
                now_utc=now_utc,
            )

            self.assertEqual(payload["totals"]["due_tomorrow"], 1)

    def test_timezone_boundary_today(self):
        with self.app.app_context():
            db.session.add(
                ReviewEvent(
                    user_id=self.user_id,
                    card_id="c1",
                    deck_id=self.deck_id,
                    note_type_id=None,
                    reviewed_at=datetime(2026, 2, 22, 23, 30, 0),  # previous day 23:30 UTC
                    duration_ms=2000,
                    rating="good",
                    mode="review",
                )
            )
            db.session.add(
                ReviewEvent(
                    user_id=self.user_id,
                    card_id="c2",
                    deck_id=self.deck_id,
                    note_type_id=None,
                    reviewed_at=datetime(2026, 2, 23, 0, 10, 0),  # current day 00:10 UTC
                    duration_ms=3000,
                    rating="good",
                    mode="review",
                )
            )
            db.session.commit()

            payload = build_today_future_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                deck_id=None,
                history_range="12m",
                future_range="30",
                backlog=False,
                now_utc=datetime(2026, 2, 23, 0, 30, 0),
            )
            self.assertEqual(payload["today"]["cards"], 2)
            self.assertEqual(payload["today"]["minutes"], 0.08)
            self.assertEqual(payload["today"]["sec_per_card"], 2.5)

    def test_stats_today_future_api(self):
        with self.app.app_context():
            self._add_progress(due_at=datetime(2026, 2, 24, 9, 0, 0), interval_days=3)
            db.session.commit()

        self._login()
        response = self.client.get(
            f"/api/statistics/today-future?scope=deck&deck_id={self.deck_id}&history_range=12m&future_range=30&backlog=false"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("today", payload)
        self.assertIn("future_due", payload)
        self.assertIn("totals", payload)

    def test_python_local_day_future_due(self):
        with self.app.app_context():
            db.session.add(
                ReviewEvent(
                    user_id=self.user_id,
                    card_id="tokyo-card",
                    deck_id=self.deck_id,
                    note_type_id=None,
                    reviewed_at=datetime(2026, 2, 22, 15, 30, 0),
                    duration_ms=2000,
                    rating="good",
                    mode="review",
                )
            )
            self._add_progress(due_at=datetime(2026, 2, 23, 15, 30, 0), interval_days=3)
            db.session.commit()

            from app.services.stats_today_future import _aggregate_future_due_python
            with patch("app.services.stats_today_future._aggregate_future_due_python", wraps=_aggregate_future_due_python) as future:
                payload = build_today_future_stats(
                    user_id=self.user_id,
                    timezone_name="Asia/Tokyo",
                    scope="collection",
                    deck_id=None,
                    history_range="12m",
                    future_range="30",
                    backlog=False,
                    now_utc=datetime(2026, 2, 22, 16, 0, 0),
                )

            future.assert_called_once()
            self.assertEqual(payload["today"]["cards"], 1)
            self.assertEqual(payload["totals"]["due_tomorrow"], 1)


if __name__ == "__main__":
    unittest.main()
