"""Tests for User Study Time Analytics."""

from __future__ import annotations

import unittest
from datetime import datetime
from unittest.mock import patch

from app import create_app
from app.services.stats_today_future import build_user_study_time_stats
from models import db
from models.flashcard import ReviewEvent
from models.user import User
from models.deck import Deck


class StatsUserStudyTimeTests(unittest.TestCase):
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
            user = User(username="study-user", email="study@example.com", timezone="UTC")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck_a = Deck(name="Deck A", owner_user_id=user.id)
            deck_b = Deck(name="Deck B", owner_user_id=user.id)
            db.session.add_all([deck_a, deck_b])
            db.session.flush()
            self.deck_a_id = deck_a.id
            self.deck_b_id = deck_b.id
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login(self):
        self.client.post(
            "/login",
            data={"email": "study@example.com", "password": "password"},
            follow_redirects=False,
        )

    def _add_review(
        self,
        *,
        reviewed_at: datetime,
        duration_ms: int = 30000,
        rating: str = "good",
        deck_id: int | None = None,
    ):
        with self.app.app_context():
            event = ReviewEvent(
                user_id=self.user_id,
                card_id=f"card_{datetime.utcnow().timestamp()}",
                deck_id=deck_id or self.deck_a_id,
                reviewed_at=reviewed_at,
                duration_ms=duration_ms,
                rating=rating,
                mode="review",
            )
            db.session.add(event)
            db.session.commit()

    def test_empty_study_time(self):
        with self.app.app_context():
            fixed_now = datetime(2026, 8, 27, 10, 0, 0)
            res = build_user_study_time_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                range_preset="7d",
                now_utc=fixed_now,
            )
            self.assertEqual(res["range_preset"], "7d")
            self.assertEqual(res["summary"]["total_study_minutes"], 0.0)
            self.assertEqual(res["summary"]["total_study_hours"], 0.0)
            self.assertEqual(res["summary"]["total_reviews"], 0)
            self.assertEqual(res["summary"]["avg_daily_minutes"], 0.0)
            self.assertEqual(len(res["daily_time_series"]), 7)

    def test_study_time_aggregation_and_pass_rate(self):
        with self.app.app_context():
            fixed_now = datetime(2026, 8, 27, 10, 0, 0)
            # Day 1: 2026-08-26 (2 reviews, 60s total, 1 good, 1 again)
            self._add_review(
                reviewed_at=datetime(2026, 8, 26, 8, 0, 0),
                duration_ms=30000,
                rating="good",
                deck_id=self.deck_a_id,
            )
            self._add_review(
                reviewed_at=datetime(2026, 8, 26, 8, 5, 0),
                duration_ms=30000,
                rating="again",
                deck_id=self.deck_a_id,
            )
            # Day 2: 2026-08-27 (1 review, 120s total, 1 easy in deck_b)
            self._add_review(
                reviewed_at=datetime(2026, 8, 27, 9, 0, 0),
                duration_ms=120000,
                rating="easy",
                deck_id=self.deck_b_id,
            )

            # Collection scope (both decks)
            res_all = build_user_study_time_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="collection",
                range_preset="7d",
                now_utc=fixed_now,
            )
            self.assertEqual(res_all["summary"]["total_reviews"], 3)
            # 30s + 30s + 120s = 180s = 3.0 minutes
            self.assertEqual(res_all["summary"]["total_study_minutes"], 3.0)
            self.assertEqual(res_all["summary"]["total_study_hours"], 0.05)
            # 2 passed (good, easy) out of 3 = 66.7%
            self.assertEqual(res_all["summary"]["retention_pass_rate"], 66.7)
            self.assertEqual(res_all["summary"]["active_days_count"], 2)

            # Deck A scope only
            res_deck_a = build_user_study_time_stats(
                user_id=self.user_id,
                timezone_name="UTC",
                scope="deck",
                deck_id=self.deck_a_id,
                range_preset="7d",
                now_utc=fixed_now,
            )
            self.assertEqual(res_deck_a["summary"]["total_reviews"], 2)
            self.assertEqual(res_deck_a["summary"]["total_study_minutes"], 1.0)
            # 1 passed out of 2 = 50.0%
            self.assertEqual(res_deck_a["summary"]["retention_pass_rate"], 50.0)

    def test_study_time_api_endpoint(self):
        self._login()
        with self.app.app_context():
            self._add_review(
                reviewed_at=datetime.utcnow(),
                duration_ms=60000,
                rating="good",
                deck_id=self.deck_a_id,
            )

        resp = self.client.get("/api/statistics/study-time?scope=collection&range=30d")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["range_preset"], "30d")
        self.assertIn("summary", data)
        self.assertIn("daily_time_series", data)
        self.assertEqual(len(data["daily_time_series"]), 30)
        self.assertGreaterEqual(data["summary"]["total_reviews"], 1)


if __name__ == "__main__":
    unittest.main()
