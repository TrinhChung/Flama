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
from models.card_progress import CardProgress


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
            self.user_id = user.id

            deck = Deck(name="Deck A", owner_user_id=user.id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
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
        is_suspended: bool = False,
    ):
        db.session.add(
            CardProgress(
                user_id=self.user_id,
                queue=queue,
                due_at=due_at,
                interval_days=interval_days,
                is_suspended=is_suspended,
            )
        )

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
            self.assertEqual(payload["totals"]["due_tomorrow"], 2)

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
            # 1/10 + 1/2 + 1/max(1,0) = 1.6
            self.assertAlmostEqual(payload["totals"]["daily_load"], 1.6, places=6)

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
            self.assertEqual(payload["today"]["cards"], 1)
            self.assertEqual(payload["today"]["minutes"], 0.05)
            self.assertEqual(payload["today"]["sec_per_card"], 3.0)

    def test_stats_today_future_api(self):
        with self.app.app_context():
            self._add_progress(due_at=datetime(2026, 2, 24, 9, 0, 0), interval_days=3)
            db.session.commit()

        self._login()
        response = self.client.get(
            f"/api/stats/today-future?scope=deck&deck_id={self.deck_id}&history_range=12m&future_range=30&backlog=false"
        )
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertIn("today", payload)
        self.assertIn("future_due", payload)
        self.assertIn("totals", payload)

    def test_non_utc_mysql_falls_back_to_python_future_due(self):
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

            with patch("app.repositories.stats_query_repository._session_dialect_name", return_value="mysql"):
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

            self.assertEqual(payload["today"]["cards"], 1)
            self.assertEqual(payload["totals"]["due_tomorrow"], 1)


if __name__ == "__main__":
    unittest.main()
