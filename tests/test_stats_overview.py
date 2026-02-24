"""Tests for statistics overview calculations."""

from __future__ import annotations

import unittest
from datetime import datetime

from app import create_app
from app.services.stats_overview import build_stats_overview
from models import db
from models.flashcard import ReviewEvent
from models.user import User


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
            db.session.commit()
            self.user_id = user.id

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
                entry_id=None,
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


if __name__ == "__main__":
    unittest.main()
