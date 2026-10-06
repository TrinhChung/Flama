"""Temporal and measure policy parity with the existing raw analytics reader."""

from datetime import date, datetime, timedelta, timezone
from types import SimpleNamespace
import unittest
from unittest.mock import patch
from zoneinfo import ZoneInfoNotFoundError

from flask import Flask

from app.services.review_analytics_policy import (
    ReviewAnalyticsPolicy, passed_count_for_policy, policy_from_generation,
)


class ReviewAnalyticsPolicyTests(unittest.TestCase):
    def test_fixed_offset_boundaries_and_aware_utc_normalization(self):
        policy = ReviewAnalyticsPolicy("Asia/Tokyo", 4)
        self.assertEqual(policy.study_day(datetime(2026, 10, 4, 18, 59, 59)), date(2026, 10, 4))
        self.assertEqual(policy.study_day(datetime(2026, 10, 4, 19)), date(2026, 10, 5))
        self.assertEqual(policy.study_day(datetime(2026, 10, 5, 4, tzinfo=timezone(timedelta(hours=9)))),
                         date(2026, 10, 5))

    def test_explicit_offset_fallback_and_leap_day(self):
        policy = ReviewAnalyticsPolicy("UTC+07:00", 4)
        self.assertEqual(policy.study_day(datetime(2024, 2, 28, 21)), date(2024, 2, 29))
        self.assertEqual(policy.study_day(datetime(2024, 2, 28, 20, 59)), date(2024, 2, 28))

    def test_known_fixed_zone_when_zoneinfo_data_is_unavailable(self):
        with patch("app.services.stats_overview.ZoneInfo", side_effect=ZoneInfoNotFoundError):
            policy = ReviewAnalyticsPolicy("Asia/Tokyo", 4)
            self.assertEqual(policy.study_day(datetime(2026, 10, 4, 19)), date(2026, 10, 5))

    def test_dst_spring_business_day_uses_wall_clock_boundary(self):
        policy = ReviewAnalyticsPolicy("America/New_York", 4)
        self.assertEqual(policy.study_day(datetime(2026, 3, 8, 7, 59)), date(2026, 3, 7))
        self.assertEqual(policy.study_day(datetime(2026, 3, 8, 8)), date(2026, 3, 8))

    def test_dst_fall_repeated_hour_and_business_day_boundary(self):
        policy = ReviewAnalyticsPolicy("America/New_York", 4)
        for utc_hour in (5, 6):
            self.assertEqual(policy.study_day(datetime(2026, 11, 1, utc_hour, 30)), date(2026, 10, 31))
        self.assertEqual(policy.study_day(datetime(2026, 11, 1, 8, 59)), date(2026, 10, 31))
        self.assertEqual(policy.study_day(datetime(2026, 11, 1, 9)), date(2026, 11, 1))

    def test_canonical_policy_hash_and_each_effective_input(self):
        first = ReviewAnalyticsPolicy("GMT", 4, timezone_rules_version="test-rules-1")
        same = ReviewAnalyticsPolicy("UTC", 4, timezone_rules_version="test-rules-1")
        self.assertEqual(first.policy_hash, same.policy_hash)
        self.assertEqual(len(first.policy_hash), 32)
        for policy in (
            ReviewAnalyticsPolicy("Asia/Tokyo", 4, timezone_rules_version="test-rules-1"),
            ReviewAnalyticsPolicy("UTC", 5, timezone_rules_version="test-rules-1"),
            ReviewAnalyticsPolicy("UTC", 4, grouping_version=2, timezone_rules_version="test-rules-1"),
            ReviewAnalyticsPolicy("UTC", 4, timezone_rules_version="test-rules-2"),
        ):
            self.assertNotEqual(first.policy_hash, policy.policy_hash)

    def test_stored_policy_restores_immutable_rules_and_rejects_corrupt_hash(self):
        policy = ReviewAnalyticsPolicy("UTC", 4, timezone_rules_version="old-rules")
        generation = SimpleNamespace(**policy.__dict__, policy_hash=policy.policy_hash)
        self.assertEqual(policy_from_generation(generation), policy)
        generation.policy_hash = b"x" * 32
        with self.assertRaises(ValueError):
            policy_from_generation(generation)

    def test_config_rules_override_environment_and_default_fingerprint(self):
        app = Flask(__name__)
        app.config["REVIEW_ANALYTICS_TIMEZONE_RULES_VERSION"] = "config-rules"
        with patch.dict("os.environ", {"REVIEW_ANALYTICS_TIMEZONE_RULES_VERSION": "env-rules"}):
            with app.app_context():
                self.assertEqual(ReviewAnalyticsPolicy("UTC", 4).timezone_rules_version, "config-rules")
            self.assertEqual(ReviewAnalyticsPolicy("UTC", 4).timezone_rules_version, "env-rules")
        self.assertTrue(ReviewAnalyticsPolicy("UTC", 4).timezone_rules_version)

    def test_passed_count_follows_sql_or_python_reader_for_each_policy(self):
        fixed = ReviewAnalyticsPolicy("Asia/Tokyo", 4)
        dst = ReviewAnalyticsPolicy("America/New_York", 4)
        self.assertEqual(passed_count_for_policy(fixed, "góód", 1, "mysql"), 1)
        self.assertEqual(passed_count_for_policy(dst, "góód", 1, "mysql"), 0)
        self.assertEqual(passed_count_for_policy(fixed, "\tgood\n", 0, "mysql"), 0)
        self.assertEqual(passed_count_for_policy(dst, "\tgood\n", 0, "mysql"), 1)
        self.assertEqual(passed_count_for_policy(fixed, "\u00a0 EASY\t", 0, "sqlite"), 1)

    def test_invalid_boundaries_and_rules_are_rejected(self):
        for value in (-1, 24, True, "4"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                ReviewAnalyticsPolicy("UTC", value)
        with self.assertRaises(ValueError):
            ReviewAnalyticsPolicy("UTC", 4, timezone_rules_version="x" * 65)


if __name__ == "__main__":
    unittest.main()
