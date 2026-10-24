"""Tests for statistics overview calculations."""

from __future__ import annotations

import unittest
from datetime import date, datetime
from unittest.mock import patch

from app import create_app
from app.services.stats_overview import build_stats_overview
from models import db
from models.flashcard import Card, Note, NoteType, ReviewEvent, Template
from models.user import User
from models.deck import Deck
from tests.study_note_fixtures import attach_template, enroll_note_user, assert_retired_progress_absent
from tests.note_progress_fixtures import stage_note_state
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_subject import StudyProgressSubject


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
            enroll_note_user(db.session, user)
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
        due_day: int | None = None,
        is_suspended: bool = False,
    ):
        return self._add_canonical_due(due_at=due_at, due_day=due_day, queue=queue, suspended=is_suspended)

    def _add_canonical_due(
        self, *, due_at=None, due_day=None, queue="review", siblings=1,
        suspended=False, buried=False, learner_id=None, owner_id=None,
        detached=False, logical_key=None,
    ):
        now = datetime(2026, 1, 1)
        self._card_seq += 1
        note_type = NoteType(name=f"Canonical Stats {self._card_seq}", user_id=owner_id or self.user_id)
        db.session.add(note_type)
        db.session.flush()
        templates = [attach_template(db.session, owner_user_id=owner_id or self.user_id, name=f"Stats Card {index}", note_type_id=note_type.id, position=index) for index in range(siblings)]
        db.session.add_all(templates)
        db.session.flush()
        note = Note(note_type_id=note_type.id, user_id=owner_id or self.user_id, deck_id=self.deck_id)
        db.session.add(note)
        db.session.flush()
        cards = Card.query.filter_by(note_id=note.id).all()
        db.session.flush()
        subject = stage_note_state(db.session, user_id=learner_id or self.user_id,
            note_id=note.id, now=now, queue=queue, due_at=due_at, due_day=due_day,
            is_suspended=suspended, is_buried=buried,
            buried_until_day=date(2026, 1, 20).toordinal() if buried else None)
        if logical_key is not None:
            subject.logical_note_key = logical_key  # Deliberate identity drift fixture.
        if detached:
            subject.live_note_id = None
        db.session.flush()
        return subject

    def _canonical_day_counts(self, *, timezone_name="Asia/Tokyo", boundary=4,
                              start=date(2026, 1, 10), end=date(2026, 1, 13)):
        from app.services.anki_scheduler import _day_index_to_datetime
        from app.services.stats_overview import _canonical_future_due_day_counts

        return _canonical_future_due_day_counts(
            user_id=self.user_id, timezone_name=timezone_name, timezone_obj=None,
            start_utc=_day_index_to_datetime(start.toordinal(), boundary, timezone_name=timezone_name),
            end_utc=_day_index_to_datetime(end.toordinal(), boundary, timezone_name=timezone_name),
            day_boundary_hour_local=boundary,
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

    def _streak_and_history_reads(self, *, year, now_utc):
        from app.services import stats_overview as overview

        with patch.object(overview, "query_active_review_days", wraps=overview.query_active_review_days) as history:
            payload = build_stats_overview(user_id=self.user_id, year=year, timezone_name="UTC", now_utc=now_utc)
        return payload["metrics"]["current_streak_days"], history.call_count

    def test_current_streak_inside_the_year_needs_no_history_read(self):
        with self.app.app_context():
            for day in (1, 2, 3, 7, 8, 9):
                self._add_event(when_utc=datetime(2026, 1, day, 10, 0, 0), duration_ms=1200)
            db.session.commit()
            # Ends yesterday (Jan 9) and starts after Jan 1: the year's days suffice.
            self.assertEqual(self._streak_and_history_reads(year=2026, now_utc=datetime(2026, 1, 10, 12)), (3, 0))

    def test_current_streak_reaching_the_year_start_reads_history(self):
        with self.app.app_context():
            for when in (datetime(2025, 12, 30, 10), datetime(2025, 12, 31, 10),
                         datetime(2026, 1, 1, 10), datetime(2026, 1, 2, 10)):
                self._add_event(when_utc=when, duration_ms=1200)
            db.session.commit()
            # Jan 2 back to Dec 30: the streak crosses into last year.
            self.assertEqual(self._streak_and_history_reads(year=2026, now_utc=datetime(2026, 1, 2, 12)), (4, 1))
            # On Jan 5 the streak broke on Jan 3/4, inside the year: no history read.
            self.assertEqual(self._streak_and_history_reads(year=2026, now_utc=datetime(2026, 1, 5, 12)), (0, 0))

    def test_current_streak_for_another_year_reads_history(self):
        with self.app.app_context():
            for day in (8, 9, 10):
                self._add_event(when_utc=datetime(2026, 1, day, 10, 0, 0), duration_ms=1200)
            db.session.commit()
            self.assertEqual(self._streak_and_history_reads(year=2025, now_utc=datetime(2026, 1, 10, 12)), (3, 1))

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
        response = self.client.get("/api/statistics/overview?year=2026")
        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["year"], 2026)
        self.assertIn("today", payload)
        self.assertIn("metrics", payload)
        self.assertEqual(set(payload["heatmap"][0]), {"date", "cards", "minutes", "is_future"})

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

            # Year totals must only aggregate up to today_local, excluding future clock skew
            self.assertEqual(payload["metrics"]["total_cards"], 10)
            self.assertEqual(payload["total_cards"], 10)
            self.assertEqual(payload["metrics"]["total_minutes"], 0.17)
            self.assertEqual(payload["total_minutes"], 0.17)

    def test_future_due_local_day_boundary(self):
        with self.app.app_context():
            # UTC+7 study-day boundary is 04:00 local, so 00:30 local still belongs to Jan 10.
            self._add_progress(due_at=datetime(2026, 1, 10, 17, 30, 0))
            # Still same study day, also not counted as future due card for Jan 11.
            self._add_progress(due_at=datetime(2026, 1, 10, 16, 30, 0))
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="Asia/Ho_Chi_Minh",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )

            jan_11 = self._heatmap_day(payload, "2026-01-11")
            self.assertEqual(jan_11["cards"], 0)
            self.assertEqual(jan_11["source"], "due")
            self.assertTrue(jan_11["is_future"])

    def test_future_due_uses_review_due_day_over_stale_due_at(self):
        with self.app.app_context():
            self._add_progress(
                due_at=datetime(2026, 1, 10, 8, 0, 0),
                due_day=datetime(2026, 1, 12).date().toordinal(),
                queue="review",
            )
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )

            jan_12 = self._heatmap_day(payload, "2026-01-12")
            self.assertEqual(jan_12["cards"], 1)
            self.assertEqual(jan_12["source"], "due")
            self.assertTrue(jan_12["is_future"])

    def test_python_local_day_aggregation(self):
        with self.app.app_context():
            self._add_event(when_utc=datetime(2026, 1, 10, 15, 30, 0), duration_ms=2000)
            db.session.commit()

            with patch("app.services.stats_overview.can_use_mysql_local_day_sql", return_value=False):
                payload = build_stats_overview(
                    user_id=self.user_id,
                    year=2026,
                    timezone_name="Asia/Tokyo",
                    now_utc=datetime(2026, 1, 10, 16, 0, 0),
                )

            jan_10 = self._heatmap_day(payload, "2026-01-10")
            self.assertEqual(payload["today"]["cards"], 1)
            self.assertEqual(payload["today"]["date"], "2026-01-10")
            self.assertEqual(jan_10["cards"], 1)
            self.assertEqual(jan_10["source"], "reviewed")
            self.assertFalse(jan_10["is_future"])

    def test_today_reviewed_cards_take_precedence_over_due_cards(self):
        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            # Add 5 reviewed cards today
            for _ in range(5):
                self._add_event(when_utc=datetime(2026, 1, 10, 9, 0, 0), duration_ms=1000)
            # Add 44 due cards today
            for _ in range(44):
                self._add_progress(due_at=datetime(2026, 1, 10, 8, 0, 0))
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=now_utc,
            )

            today_point = self._heatmap_day(payload, "2026-01-10")
            self.assertEqual(payload["today"]["cards"], 5)
            self.assertEqual(payload["today"]["date"], "2026-01-10")
            # Today must show reviewed cards (5), not due cards (44)
            self.assertEqual(today_point["cards"], 5)
            self.assertEqual(today_point["source"], "reviewed")
            self.assertFalse(today_point["is_future"])

    def test_today_unstudied_shows_due_cards(self):
        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            # 0 reviews today, but 44 due cards
            for _ in range(44):
                self._add_progress(due_at=datetime(2026, 1, 10, 8, 0, 0))
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=now_utc,
            )

            today_point = self._heatmap_day(payload, "2026-01-10")
            self.assertEqual(payload["today"]["cards"], 0)
            self.assertEqual(payload["today"]["date"], "2026-01-10")
            # Since unstudied today, show 44 due cards with is_future=True and source="due"
            self.assertEqual(today_point["cards"], 44)
            self.assertEqual(today_point["source"], "due")
            self.assertTrue(today_point["is_future"])

    def test_today_unstudied_and_no_due_shows_zero(self):
        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=now_utc,
            )

            today_point = self._heatmap_day(payload, "2026-01-10")
            self.assertEqual(payload["today"]["cards"], 0)
            self.assertEqual(today_point["cards"], 0)
            self.assertEqual(today_point["source"], "reviewed")
            self.assertFalse(today_point["is_future"])

    def test_suspended_note_state_is_excluded_and_old_storage_is_absent(self):
        """Forecast reads valid canonical state and never recreates old progress storage."""
        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            for hour in range(5):
                self._add_progress(due_at=datetime(2026, 1, 12, 8 + hour, 0, 0), is_suspended=True)
            assert_retired_progress_absent(self, db.session)
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=now_utc,
            )
            self.assertEqual(self._heatmap_day(payload, "2026-01-12")["cards"], 0)

    def test_note_authority_mode_pristine_subject_without_token_is_not_an_error(self):
        """K2: a never-studied subject needs no token; the locking reader created them lazily."""
        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            db.session.add_all([
                StudyProgressSubject(
                    learner_user_id=self.user_id, logical_note_key=b"note-missing-token-key",
                    created_at=now_utc, updated_at=now_utc),
            ])
            db.session.commit()

            payload = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=now_utc,
            )
            self.assertEqual(payload["year"], 2026)

    def test_note_authority_mode_non_locking(self):
        """Test R5: Verify no 'FOR UPDATE' queries run during NOTE overview."""
        from sqlalchemy import event

        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            subject = StudyProgressSubject(
                learner_user_id=self.user_id,
                logical_note_key=b"note-non-locking-key",
                created_at=now_utc,
                updated_at=now_utc,
            )
            db.session.add(subject)
            db.session.commit()

            executed_clauses = []

            def before_execute(conn, clause, multiparams, params, options):
                if getattr(clause, "_for_update_arg", None) is not None:
                    executed_clauses.append(clause)

            event.listen(db.engine, "before_execute", before_execute)
            try:
                build_stats_overview(
                    user_id=self.user_id,
                    year=2026,
                    timezone_name="UTC",
                    now_utc=now_utc,
                )
            finally:
                event.remove(db.engine, "before_execute", before_execute)

            self.assertEqual(executed_clauses, [], "Found unexpected locking queries in overview!")

    def test_canonical_future_due_mysql_routing(self):
        """Verify _canonical_future_due_day_counts routes to MySQL query when supported."""
        from app.services.stats_overview import _canonical_future_due_day_counts

        with self.app.app_context():
            now_utc = datetime(2026, 1, 10, 12, 0, 0)
            with patch("app.services.stats_overview.can_use_mysql_local_day_sql", return_value=True) as mock_can, \
                 patch("app.services.stats_overview.query_canonical_future_due_day_counts_mysql", return_value={date(2026, 1, 10): 5}) as mock_query:
                result = _canonical_future_due_day_counts(
                    user_id=self.user_id,
                    timezone_name="Asia/Tokyo",
                    timezone_obj=None,
                    start_utc=now_utc,
                    end_utc=datetime(2026, 1, 11, 12),
                    day_boundary_hour_local=4,
                )
                self.assertEqual(result, {date(2026, 1, 10): 5})
                mock_can.assert_called_once_with(timezone_name="Asia/Tokyo")
                mock_query.assert_called_once_with(
                    user_id=self.user_id, timezone_name="Asia/Tokyo",
                    day_boundary_hour_local=4, start_local_day=date(2026, 1, 10),
                    end_local_day=date(2026, 1, 11),
                )

    def test_canonical_due_counts_keep_precedence_day_boundary_and_card_units(self):
        with self.app.app_context():
            self._add_canonical_due(due_at=datetime(2026, 1, 9), due_day=date(2026, 1, 12).toordinal(), siblings=2)
            self._add_canonical_due(due_day=date(2026, 1, 8).toordinal(), buried=True)
            # Tokyo 04:00 is UTC 19:00 on the preceding calendar date.
            self._add_canonical_due(due_at=datetime(2026, 1, 10, 18, 59), due_day=date(2026, 1, 12).toordinal(), queue="learning")
            self._add_canonical_due(due_at=datetime(2026, 1, 10, 19), queue="relearning")
            self._add_canonical_due(due_day=date(2026, 1, 13).toordinal())
            self._add_canonical_due(due_day=0, due_at=datetime(2026, 1, 11))
            self._add_canonical_due(due_day=date(2026, 1, 11).toordinal(), suspended=True)
            self._add_canonical_due()
            db.session.commit()
            self.assertEqual(self._canonical_day_counts(), {
                date(2026, 1, 10): 2, date(2026, 1, 11): 1, date(2026, 1, 12): 2,
            })

    def test_canonical_due_scope_preserves_learner_source_notes_detach_and_identity_drift(self):
        with self.app.app_context():
            publisher = User(username="publisher", email="publisher@example.test")
            db.session.add(publisher)
            db.session.flush()
            due = date(2026, 1, 11).toordinal()
            # An uninstalled publisher Note is outside the learner presentation scope.
            self._add_canonical_due(due_day=due, siblings=2, owner_id=publisher.id)
            self._add_canonical_due(due_day=due, learner_id=publisher.id)
            self._add_canonical_due(due_day=due, detached=True)
            # The scope's live association does not substitute for logical-key availability.
            self._add_canonical_due(due_day=due, logical_key=b"mismatched-logical-key")
            db.session.commit()
            # The publisher's Notes are not installed and a mismatched key has no
            # availability; a detached subject still names its Note by logical
            # key, so it reads as stored, like every other count.
            self.assertEqual(self._canonical_day_counts(), {date(2026, 1, 11): 1})

    def test_canonical_due_dst_timezone_uses_python_business_day_mapping(self):
        with self.app.app_context():
            # After US spring-forward: local 03:59 and 04:00 straddle the study day.
            self._add_canonical_due(due_at=datetime(2026, 3, 9, 7, 59), queue="learning")
            self._add_canonical_due(due_at=datetime(2026, 3, 9, 8), queue="learning")
            db.session.commit()
            with patch("app.services.stats_overview.query_canonical_future_due_day_counts_mysql", side_effect=AssertionError("DST must use Python")):
                self.assertEqual(self._canonical_day_counts(
                    timezone_name="America/New_York", start=date(2026, 3, 8), end=date(2026, 3, 10),
                ), {date(2026, 3, 8): 1, date(2026, 3, 9): 1})

    def test_overview_year_metrics_and_aliases(self):
        with self.app.app_context():
            # 5 reviews in 2025 (30s each = 150s = 2.5 min)
            for day in range(1, 6):
                self._add_event(when_utc=datetime(2025, 6, day, 10, 0, 0), duration_ms=30000)
            # 3 reviews in 2026 (60s each = 180s = 3.0 min)
            for day in range(1, 4):
                self._add_event(when_utc=datetime(2026, 1, day, 10, 0, 0), duration_ms=60000)
            db.session.commit()

            # Query year 2025 (past year)
            p2025 = build_stats_overview(
                user_id=self.user_id,
                year=2025,
                timezone_name="UTC",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )
            self.assertEqual(p2025["metrics"]["total_cards"], 5)
            self.assertEqual(p2025["total_cards"], 5)
            self.assertEqual(p2025["metrics"]["total_minutes"], 2.5)
            self.assertEqual(p2025["total_minutes"], 2.5)

            # Query year 2026 (current year)
            p2026 = build_stats_overview(
                user_id=self.user_id,
                year=2026,
                timezone_name="UTC",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )
            self.assertEqual(p2026["metrics"]["total_cards"], 3)
            self.assertEqual(p2026["total_cards"], 3)
            self.assertEqual(p2026["metrics"]["total_minutes"], 3.0)
            self.assertEqual(p2026["total_minutes"], 3.0)

            # Query future year 2030 (no reviews)
            p2030 = build_stats_overview(
                user_id=self.user_id,
                year=2030,
                timezone_name="UTC",
                now_utc=datetime(2026, 1, 10, 12, 0, 0),
            )
            self.assertEqual(p2030["metrics"]["total_cards"], 0)
            self.assertEqual(p2030["total_cards"], 0)
            self.assertEqual(p2030["metrics"]["total_minutes"], 0.0)
            self.assertEqual(p2030["total_minutes"], 0.0)


if __name__ == "__main__":
    unittest.main()
