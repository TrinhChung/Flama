"""Parity and read-only contracts for the verified history read facade."""

from __future__ import annotations

import unittest
from collections import defaultdict
from datetime import date, datetime, timedelta
from unittest.mock import patch

from sqlalchemy import event, update

from app import create_app
from app.repositories import stats_query_repository as stats
from app.services.anki_scheduler import _day_index_to_datetime
from app.services.review_analytics_policy import ReviewAnalyticsPolicy
from app.services.stats_overview import build_stats_overview
from app.services.stats_today_future import build_today_future_stats, build_user_study_time_stats
from app.services.study_analytics_read_service import analytics_read_transaction
from models import db
from models.deck import Deck
from models.flashcard import ReviewEvent
from models.review_analytics import DailyReviewCount, ReviewAnalyticsGeneration, ReviewAnalyticsHead
from models.user import User


class ReviewAnalyticsReadTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "REVIEW_ANALYTICS_READ_MODE": "raw",
            "REVIEW_ANALYTICS_WRITE_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        user = User(username="projection-reader", email="projection-reader@example.com", timezone="UTC")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()
        self.user_id = user.id
        root = Deck(name="Root", owner_user_id=user.id)
        db.session.add(root)
        db.session.flush()
        middle = Deck(name="Middle", parent_id=root.id, owner_user_id=user.id)
        db.session.add(middle)
        db.session.flush()
        child = Deck(name="Child", parent_id=middle.id, owner_user_id=user.id)
        other = Deck(name="Other", owner_user_id=user.id)
        db.session.add_all([child, other])
        db.session.flush()
        self.root_id, self.middle_id, self.child_id, self.other_id = root.id, middle.id, child.id, other.id
        self.events = []
        for index, (moment, duration, rating, deck_id) in enumerate([
            (datetime(2025, 12, 30, 12), 1000, "good", root.id),
            (datetime(2025, 12, 31, 12), 3100, "3", middle.id),
            (datetime(2026, 1, 1, 3, 59), -20, "again", child.id),
            (datetime(2026, 1, 1, 4), 3100, "4", root.id),
            (datetime(2026, 1, 1, 7), None, "easy", middle.id),
            (datetime(2026, 1, 1, 8), 0, "hard", child.id),
            (datetime(2026, 1, 1, 9), 90000, "good", None),
            (datetime(2026, 1, 1, 10), 5000, "3", other.id),
            (datetime(2026, 1, 2, 4), 3000, "easy", root.id),
            (datetime(2026, 3, 8, 6, 59), 12500, "3", middle.id),
            (datetime(2026, 3, 8, 7), 8500, "4", child.id),
            (datetime(2026, 11, 1, 5, 59), 3500, "easy", root.id),
            (datetime(2026, 11, 1, 6), 6100, "hard", None),
            (datetime(2026, 12, 31, 23), 100, "again", root.id),
        ]):
            row = ReviewEvent(
                user_id=user.id, card_id=f"read-card-{index}", deck_id=deck_id,
                reviewed_at=moment, duration_ms=duration, rating=rating, mode="review",
            )
            db.session.add(row)
            self.events.append((moment, duration, rating, deck_id))
        db.session.commit()
        self._install_generation("UTC", 4)
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = True

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _install_generation(self, timezone_name, boundary):
        self.policy = ReviewAnalyticsPolicy(timezone_name, boundary)
        db.session.query(DailyReviewCount).delete()
        db.session.query(ReviewAnalyticsGeneration).delete()
        db.session.query(ReviewAnalyticsHead).delete()
        db.session.add(ReviewAnalyticsHead(
            user_id=self.user_id, active_generation=1, source_revision=7,
        ))
        db.session.flush()
        db.session.add(ReviewAnalyticsGeneration(
            user_id=self.user_id, generation=1, policy_hash=self.policy.policy_hash,
            timezone_name=self.policy.timezone_name, day_boundary_hour=boundary,
            grouping_version=self.policy.grouping_version,
            timezone_rules_version=self.policy.timezone_rules_version,
            status=1, baseline_high_water_id=len(self.events), backfill_cursor_id=len(self.events),
            applied_source_revision=7, verified_source_revision=7,
            verification_contract_version=1, verified_at=datetime(2026, 1, 1),
        ))
        db.session.flush()
        buckets = defaultdict(lambda: [0, 0, 0])
        for moment, duration, rating, deck_id in self.events:
            day = stats._utc_to_business_day(
                moment, timezone_name=timezone_name, day_boundary_hour_local=boundary,
            )
            scopes = [(0, 0)] + ([(1, deck_id)] if deck_id is not None else [])
            for scope_kind, scope_id in scopes:
                values = buckets[(scope_kind, scope_id, day)]
                values[0] += 1
                values[1] += max(0, int(duration or 0))
                values[2] += int(str(rating).strip().lower() in {"good", "easy", "3", "4"})
        for (kind, scope, day), values in buckets.items():
            db.session.add(DailyReviewCount(
                user_id=self.user_id, generation=1, scope_kind=kind, scope_id=scope,
                study_day=day, review_event_count=values[0],
                positive_duration_ms=values[1], passed_review_count=values[2],
            ))
        db.session.commit()

    def _bounds(self, start=date(2025, 12, 30), end=date(2026, 1, 3)):
        return {
            "user_id": self.user_id, "timezone_name": self.policy.timezone_name,
            "day_boundary_hour_local": self.policy.day_boundary_hour,
            "start_utc": _day_index_to_datetime(
                start.toordinal(), self.policy.day_boundary_hour,
                timezone_name=self.policy.timezone_name,
            ),
            "end_utc": _day_index_to_datetime(
                end.toordinal(), self.policy.day_boundary_hour,
                timezone_name=self.policy.timezone_name,
            ),
        }

    def _result(self, mode, callback):
        self.app.config["REVIEW_ANALYTICS_READ_MODE"] = mode
        with analytics_read_transaction():
            return callback()

    def test_all_four_readers_preserve_exact_shapes_and_subtree_attribution(self):
        bounds = self._bounds()
        callbacks = [
            lambda: stats.query_daily_review_aggregates(timezone_obj=None, **bounds),
            lambda: stats.query_active_review_days(
                timezone_obj=None, **{key: val for key, val in bounds.items() if key != "start_utc"},
            ),
            lambda: stats.query_today_review_summary(
                user_id=self.user_id, scope_deck_ids=[self.root_id, self.middle_id, self.child_id],
                today_start_utc=datetime(2026, 1, 1, 4),
                tomorrow_start_utc=datetime(2026, 1, 2, 4),
                timezone_name="UTC", day_boundary_hour_local=4,
            ),
        ]
        for scope in [None, [], [self.root_id], [self.root_id, self.middle_id, self.child_id]]:
            callbacks.append(lambda scope=scope: stats.query_user_daily_study_time(
                scope_deck_ids=scope, **bounds,
            ))
        for callback in callbacks:
            self.assertEqual(self._result("raw", callback), self._result("summary", callback))
        self.assertEqual(self._result("summary", callbacks[2]), (3, 3100))

    def test_summary_reads_do_not_scan_raw_history_or_write_or_lock(self):
        statements = []

        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.upper())

        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            result = self._result("summary", lambda: stats.query_daily_review_aggregates(
                timezone_obj=None, **self._bounds(),
            ))
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertTrue(result)
        self.assertFalse(any("REVIEW_EVENTS" in sql for sql in statements))
        self.assertFalse(any(sql.lstrip().startswith(("INSERT", "UPDATE", "DELETE"))
                             or "FOR UPDATE" in sql or "FOR SHARE" in sql for sql in statements))
        self.assertEqual(len(statements), 2)

    def test_missing_dirty_stale_policy_and_incomplete_generations_fall_back(self):
        callback = lambda: stats.query_daily_review_aggregates(timezone_obj=None, **self._bounds())
        expected = self._result("raw", callback)
        mutations = [
            {"status": 0}, {"status": 2}, {"status": 3}, {"status": 4},
            {"applied_source_revision": 6}, {"policy_hash": b"x" * 32},
            {"backfill_cursor_id": 9},
            {"verified_at": None}, {"verification_contract_version": None},
            {"verification_contract_version": 2}, {"verified_source_revision": None},
            {"verified_source_revision": 8},
        ]
        for mutation in mutations:
            with self.subTest(mutation=mutation):
                self._install_generation("UTC", 4)
                db.session.execute(update(ReviewAnalyticsGeneration).values(**mutation))
                db.session.commit()
                self.assertEqual(self._result("summary", callback), expected)
        db.session.query(ReviewAnalyticsHead).update({"active_generation": None})
        db.session.commit()
        self.assertEqual(self._result("summary", callback), expected)

    def test_allowlist_and_raw_default_skip_projection_reads(self):
        from app.repositories import review_analytics_read_repository as projection

        callback = lambda: stats.query_daily_review_aggregates(timezone_obj=None, **self._bounds())
        expected = self._result("raw", callback)
        for mode, allowlist in [("raw", None), ("summary", "9999"), ("summary", "malformed")]:
            self.app.config["REVIEW_ANALYTICS_READ_USER_IDS"] = allowlist
            with patch.object(projection, "_ready_generation", side_effect=AssertionError("projection accessed")):
                self.assertEqual(self._result(mode, callback), expected)
        self.app.config["REVIEW_ANALYTICS_READ_USER_IDS"] = f" {self.user_id},9999 "
        self.assertEqual(self._result("summary", callback), expected)

    def test_writes_disabled_keeps_raw_even_with_ready_metadata_and_enabled_reads(self):
        from app.repositories import review_analytics_read_repository as projection

        callback = lambda: stats.query_daily_review_aggregates(timezone_obj=None, **self._bounds())
        expected = self._result("raw", callback)
        self.app.config["REVIEW_ANALYTICS_WRITE_ENABLED"] = False
        self.app.config["REVIEW_ANALYTICS_SHADOW_SAMPLE_RATE"] = 1
        for mode in ["summary", "shadow"]:
            with patch.object(projection, "_ready_generation", side_effect=AssertionError("projection accessed")):
                self.assertEqual(self._result(mode, callback), expected)

    def test_partial_day_intervals_keep_raw_precision(self):
        bounds = self._bounds()
        bounds["start_utc"] += timedelta(hours=8)
        bounds["end_utc"] -= timedelta(hours=10)
        callback = lambda: stats.query_user_daily_study_time(scope_deck_ids=None, **bounds)
        self.assertEqual(self._result("raw", callback), self._result("summary", callback))
        with patch.object(self.app.logger, "info") as logged:
            self._result("summary", callback)
            self.assertEqual(logged.call_args.args[-1], "fallback_partial_day")

    def test_shadow_returns_raw_and_logs_exact_parity_or_drift(self):
        self.app.config["REVIEW_ANALYTICS_SHADOW_SAMPLE_RATE"] = 1
        callback = lambda: stats.query_user_daily_study_time(scope_deck_ids=None, **self._bounds())
        expected = self._result("raw", callback)
        with patch.object(self.app.logger, "info") as logged:
            self.assertEqual(self._result("shadow", callback), expected)
            self.assertEqual(logged.call_args.args[-1], "shadow_match")
        db.session.execute(update(DailyReviewCount).where(
            DailyReviewCount.scope_kind == 0, DailyReviewCount.study_day == date(2026, 1, 1),
        ).values(positive_duration_ms=1))
        db.session.commit()
        with patch.object(self.app.logger, "info") as logged:
            self.assertEqual(self._result("shadow", callback), expected)
            self.assertEqual(logged.call_args.args[-1], "shadow_drift")

    def test_shadow_samples_once_per_request_and_skips_unsampled_projection_reads(self):
        from app.repositories import review_analytics_read_repository as projection

        self.app.config["REVIEW_ANALYTICS_READ_MODE"] = "shadow"
        self.app.config["REVIEW_ANALYTICS_SHADOW_SAMPLE_RATE"] = 0.5
        with self.app.test_request_context(), patch.object(projection.random, "random", return_value=0.25) as draw:
            with analytics_read_transaction(), patch.object(self.app.logger, "info") as logged:
                stats.query_daily_review_aggregates(timezone_obj=None, **self._bounds())
                stats.query_user_daily_study_time(scope_deck_ids=None, **self._bounds())
                self.assertEqual(draw.call_count, 1)
                self.assertEqual([call.args[-1] for call in logged.call_args_list], ["shadow_match", "shadow_match"])
        self.app.config["REVIEW_ANALYTICS_SHADOW_SAMPLE_RATE"] = 0
        with self.app.test_request_context(), patch.object(
            projection, "_ready_generation", side_effect=AssertionError("unsampled projection accessed"),
        ):
            with analytics_read_transaction():
                self.assertTrue(stats.query_daily_review_aggregates(timezone_obj=None, **self._bounds()))

    def test_full_service_payloads_keep_year_today_streak_all_and_rounding_contracts(self):
        now = datetime(2026, 1, 1, 12)
        callbacks = [
            lambda year=year: build_stats_overview(
                user_id=self.user_id, timezone_name="UTC", year=year, now_utc=now,
            ) for year in [2025, 2026]
        ]
        for scope, deck in [("collection", None), ("deck", self.root_id), ("deck", None)]:
            for preset in ["7d", "30d", "all", "custom"]:
                callbacks.append(lambda scope=scope, deck=deck, preset=preset: build_user_study_time_stats(
                    user_id=self.user_id, timezone_name="UTC", scope=scope, deck_id=deck,
                    range_preset=preset, now_utc=now,
                    start_date_str="2025-12-30", end_date_str="2026-01-01",
                ))
            callbacks.append(lambda scope=scope, deck=deck: build_today_future_stats(
                user_id=self.user_id, timezone_name="UTC", scope=scope, deck_id=deck,
                now_utc=now, history_range="all", future_range="30", backlog=True,
            ))
        for callback in callbacks:
            self.assertEqual(self._result("raw", callback), self._result("summary", callback))

    def test_dst_zones_and_different_boundary_policy_preserve_raw(self):
        for timezone_name, boundary in [("Asia/Tokyo", 0), ("America/New_York", 4)]:
            with self.subTest(timezone=timezone_name, boundary=boundary):
                self._install_generation(timezone_name, boundary)
                callback = lambda: stats.query_user_daily_study_time(
                    scope_deck_ids=None,
                    **self._bounds(start=date(2026, 3, 6), end=date(2026, 11, 3)),
                )
                self.assertEqual(self._result("raw", callback), self._result("summary", callback))
                mismatched = self._bounds()
                mismatched["day_boundary_hour_local"] = (boundary + 1) % 24
                mismatch_callback = lambda: stats.query_daily_review_aggregates(timezone_obj=None, **mismatched)
                self.assertEqual(self._result("raw", mismatch_callback), self._result("summary", mismatch_callback))


if __name__ == "__main__":
    unittest.main()
