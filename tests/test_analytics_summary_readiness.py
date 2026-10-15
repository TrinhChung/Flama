"""Opt-in pending responses prevent unbounded raw scans on projection misses."""

import unittest
from unittest.mock import Mock, patch

from app.repositories.review_analytics_read_repository import read_or_raw
from app.services.analytics_summary_readiness import AnalyticsSummaryNotReady
from app.services.forecast_snapshot_service import resolve_forecast_summary
from app.routes import register_blueprints
from models import db
from tests import test_note_stats_retirement as fixture


class AnalyticsSummaryReadinessTests(unittest.TestCase):
    def setUp(self):
        self.fixture = fixture.NoteStatsRetirementTests()
        self.fixture.setUp()
        self.app = self.fixture.app
        self.app.config.update(ANALYTICS_REQUIRE_READY_USER_IDS=[1],
            DECK_COUNT_WRITE_ENABLED=True, DECK_COUNT_READ_MODE="summary",
            FORECAST_SUMMARY_READ_MODE="summary", FORECAST_SUMMARY_READ_USER_IDS=[1],
            REVIEW_ANALYTICS_WRITE_ENABLED=True, REVIEW_ANALYTICS_READ_MODE="summary",
            REVIEW_ANALYTICS_READ_USER_IDS=[1])

    def tearDown(self):
        self.fixture.tearDown()

    def test_forecast_miss_is_pending_without_loading_progress(self):
        self.fixture.trace.clear()
        with self.assertRaises(AnalyticsSummaryNotReady):
            resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
                timezone_name="UTC", day_boundary_hour=4, now_utc=fixture.NOW,
                backlog=False, end_offset=29)
        sql = " ".join(self.fixture.trace).lower()
        self.assertNotIn("study_progress_subjects", sql)
        self.assertNotIn("review_events", sql)
        self.assertNotIn("from notes", sql)

    def test_raw_recovery_and_other_learners_keep_previous_contract(self):
        self.app.config["FORECAST_SUMMARY_READ_MODE"] = "raw"
        self.assertIsNone(resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=fixture.NOW,
            backlog=False, end_offset=29))
        self.app.config["FORECAST_SUMMARY_READ_MODE"] = "summary"
        self.app.config["ANALYTICS_REQUIRE_READY_USER_IDS"] = [2]
        self.assertIsNone(resolve_forecast_summary(db.session, user_id=1, deck_ids=None,
            timezone_name="UTC", day_boundary_hour=4, now_utc=fixture.NOW,
            backlog=False, end_offset=29))

    def test_history_generation_miss_never_invokes_raw_for_canary(self):
        raw, summary = Mock(return_value="raw"), Mock(return_value="summary")
        with self.assertRaises(AnalyticsSummaryNotReady):
            read_or_raw(metric="history", user_id=1, timezone_name="UTC",
                day_boundary_hour_local=4, raw=raw, summary=summary)
        raw.assert_not_called()
        summary.assert_not_called()
        self.app.config["REVIEW_ANALYTICS_READ_MODE"] = "shadow"
        self.assertEqual(read_or_raw(metric="history", user_id=1, timezone_name="UTC",
            day_boundary_hour_local=4, raw=raw, summary=summary), "raw")

    def test_http_miss_has_readiness_code_and_retry_after_without_zero_counts(self):
        register_blueprints(self.app)
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True
        self.fixture.trace.clear()
        with patch("app.services.dashboard_service._utcnow", return_value=fixture.NOW):
            response = client.get("/api/dashboard?compact=1")
        self.assertEqual(response.status_code, 409, response.get_json())
        self.assertEqual(response.get_json()["error"], "ANALYTICS_SUMMARY_NOT_READY")
        self.assertEqual(response.headers["Retry-After"], "60")
        self.assertEqual(response.get_json()["details"][0]["metric"], "dashboard")
        self.assertNotIn("total_due", response.get_json())
        sql = " ".join(self.fixture.trace).lower()
        self.assertNotIn("study_progress_subjects", sql)
        self.assertNotIn("from notes", sql)

    def test_all_analytics_routes_map_pending_and_keep_authority_errors(self):
        from app.services.study_authority_read_service import StudyAuthorityReadError
        register_blueprints(self.app)
        client = self.app.test_client()
        with client.session_transaction() as session:
            session["_user_id"] = "1"
            session["_fresh"] = True
        prefix = "app.api.v1.analytics.routes."
        for path, builder in (("/api/dashboard", "build_dashboard_payload"),
                ("/api/statistics/overview", "build_stats_overview"),
                ("/api/statistics/today-future", "build_today_future_stats"),
                ("/api/statistics/study-time", "build_user_study_time_stats")):
            with self.subTest(path=path), patch(prefix + builder,
                    side_effect=AnalyticsSummaryNotReady("test")):
                response = client.get(path)
                self.assertEqual(response.status_code, 409)
                self.assertEqual(response.get_json()["error"], "ANALYTICS_SUMMARY_NOT_READY")
        with patch(prefix + "build_today_future_stats",
                   side_effect=StudyAuthorityReadError("AUTHORITY_READ_PARITY_DIVERGED", "fixture")):
            response = client.get("/api/statistics/today-future")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "AUTHORITY_READ_PARITY_DIVERGED")


if __name__ == "__main__":
    unittest.main()
