"""Tests for statistics overview calculations."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from app import create_app
from app.services.stats_overview import build_stats_overview
from models import db
from models.flashcard import ReviewEvent
from models.user import User
from models.deck import Deck
from models.card_progress import CardProgress


class StatsOverviewTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()
        self._card_seq = 0

        with self.app.app_context():
            db.create_all()
            user = User(username="stats-user", email="stats@example.com", timezone="UTC")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            deck = Deck(name="Stats Deck", owner_user_id=user.id)
            db.session.add(deck)
            db.session.commit()
            self.user_id = user.id
            self.deck_id = deck.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _add_event(self, *, when_utc: datetime, duration_ms: int | None = 1000):
        self._card_seq += 1
        db.session.add(
            ReviewEvent(
                user_id=self.user_id,
                card_id=f"card-{self._card_seq}",
                deck_id=None,
                note_type_id=None,
                reviewed_at=when_utc,
                duration_ms=duration_ms,
                rating="good",
                mode="review",
            )
        )

    def _login(self):
        self.client.post(
            "/login",
            data={"email": "stats@example.com", "password": "password"},
            follow_redirects=True,
        )

    def _add_progress(
        self,
        *,
        due_at: datetime | None,
        queue: str = "review",
        is_suspended: bool = False,
    ):
        db.session.add(
            CardProgress(
                user_id=self.user_id,
                queue=queue,
                due_at=due_at,
                interval_days=1,
                is_suspended=is_suspended,
            )
        )

    @staticmethod
    def _heatmap_day(payload: dict, day_iso: str) -> dict:
        for point in payload["heatmap"]:
            if point.get("day") == day_iso:
                return point
        raise AssertionError(f"Missing heatmap day: {day_iso}")

    def test_streak_calculation(self):
        with self.app.app_context():
            for day in (1, 2, 3, 7, 8, 9):
                self._add_event(when_utc=datetime(2026, 1, day, 10, 0, 0), duration_ms=1200)
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )
            self.assertEqual(payload["metrics"]["longest_streak_days"], 3)
            self.assertEqual(payload["metrics"]["current_streak_days"], 3)

    def test_percent_active_days(self):
        with self.app.app_context():
            for day in (1, 3, 5):
                self._add_event(when_utc=datetime(2026, 1, day, 9, 0, 0), duration_ms=900)
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )
            self.assertEqual(payload["metrics"]["days_learned_percent"], 30)

    def test_today_rounding(self):
        with self.app.app_context():
            self._add_event(when_utc=datetime(2026, 1, 10, 8, 0, 0), duration_ms=1000)
            self._add_event(when_utc=datetime(2026, 1, 10, 9, 0, 0), duration_ms=2345)
            self._add_event(when_utc=datetime(2026, 1, 10, 10, 0, 0), duration_ms=None)
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )
            self.assertEqual(payload["today"]["cards"], 3)
            self.assertAlmostEqual(payload["today"]["minutes"], 0.06, places=2)
            self.assertAlmostEqual(payload["today"]["sec_per_card"], 1.12, places=2)

    def test_stats_overview_api(self):
        with self.app.app_context():
            self._add_event(when_utc=datetime(2026, 1, 2, 9, 0, 0), duration_ms=1000)
            db.session.commit()

        self._login()
        response = self.client.get("/api/stats/overview?year=2026")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["year"], 2026)
        self.assertIn("today", payload)
        self.assertIn("heatmap", payload)
        self.assertIn("metrics", payload)
        self.assertIn("day", payload["heatmap"][0])
        self.assertIn("study_time", payload["heatmap"][0])
        self.assertIn("source", payload["heatmap"][0])

    def test_current_year_future_uses_due_without_double_count(self):
        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            for _ in range(10):
                self._add_event(when_utc=datetime(2026, 1, 5, 9, 0, 0), duration_ms=1000)

            for hour in range(10):
                self._add_progress(due_at=datetime(2026, 1, 12, 8 + hour, 0, 0))
            self._add_progress(due_at=datetime(2026, 1, 12, 23, 0, 0), is_suspended=True)

            # Future reviewed timestamps (clock skew) must not be used for future day cards.
            self._add_event(when_utc=datetime(2026, 1, 14, 9, 0, 0), duration_ms=1000)
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=now_utc,
            )

            past_day = self._heatmap_day(payload, "2026-01-05")
            self.assertEqual(past_day["cards"], 10)
            self.assertEqual(past_day["source"], "reviewed")
            self.assertFalse(past_day["is_future"])

            future_due_day = self._heatmap_day(payload, "2026-01-12")
            self.assertEqual(future_due_day["cards"], 10)
            self.assertEqual(future_due_day["study_time"], 0)
            self.assertEqual(future_due_day["source"], "due")
            self.assertTrue(future_due_day["is_future"])

            future_zero_due_day = self._heatmap_day(payload, "2026-01-13")
            self.assertEqual(future_zero_due_day["cards"], 0)
            self.assertEqual(future_zero_due_day["source"], "due")
            self.assertTrue(future_zero_due_day["is_future"])

            future_review_skew_day = self._heatmap_day(payload, "2026-01-14")
            self.assertEqual(future_review_skew_day["cards"], 0)
            self.assertEqual(future_review_skew_day["source"], "due")
            self.assertTrue(future_review_skew_day["is_future"])

    def test_future_due_local_day_boundary(self):
        with self.app.app_context():
            # UTC+7 local boundary: 17:30 UTC -> next local day.
            self._add_progress(due_at=datetime(2026, 1, 10, 17, 30, 0))
            # Still same local day, not counted as future due card for Jan 11.
            self._add_progress(due_at=datetime(2026, 1, 10, 16, 30, 0))
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="Asia/Ho_Chi_Minh",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )

            jan_11 = self._heatmap_day(payload, "2026-01-11")
            self.assertEqual(jan_11["cards"], 1)
            self.assertEqual(jan_11["source"], "due")
            self.assertTrue(jan_11["is_future"])

    def test_non_utc_mysql_falls_back_to_python_aggregation(self):
        with self.app.app_context():
            self._add_event(when_utc=datetime(2026, 1, 10, 15, 30, 0), duration_ms=2000)
            db.session.commit()

            with patch("app.repositories.stats_query_repository._session_dialect_name", return_value="mysql"):
                payload = build_stats_overview(
                    user_id=self.user_id,
                    year=2026,
                    timezone_name="Asia/Tokyo",
                    now_utc=datetime(2026, 1, 10, 16, 0, 0),
                )

            jan_11 = self._heatmap_day(payload, "2026-01-11")
            self.assertEqual(payload["today"]["cards"], 1)
            self.assertEqual(jan_11["cards"], 1)
            self.assertEqual(jan_11["source"], "reviewed")
            self.assertFalse(jan_11["is_future"])


if __name__ == "__main__":
    unittest.main()
