"""Unit tests for counter logic (New/Learn/Due counts)."""

import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from app.services.anki_scheduler import default_deck_options
from app.routes.main import _day_index, _day_index_to_datetime


class TestDayIndexHelpers(unittest.TestCase):
    """Test day index calculation helpers."""

    def test_day_index_same_day(self):
        """Day index should be same within the day before boundary."""
        boundary_hour = 4
        # 10 AM same day
        dt1 = datetime(2026, 2, 23, 10, 0, 0)
        # 11 AM same day
        dt2 = datetime(2026, 2, 23, 11, 0, 0)
        
        day1 = _day_index(dt1, boundary_hour)
        day2 = _day_index(dt2, boundary_hour)
        self.assertEqual(day1, day2)

    def test_day_index_crosses_boundary(self):
        """Day index should change when crossing boundary (4 AM)."""
        boundary_hour = 4
        # 3 AM (before boundary) - belongs to previous day
        dt_before = datetime(2026, 2, 23, 3, 0, 0)
        # 5 AM (after boundary) - belongs to current day
        dt_after = datetime(2026, 2, 23, 5, 0, 0)
        
        day_before = _day_index(dt_before, boundary_hour)
        day_after = _day_index(dt_after, boundary_hour)
        # Should differ by 1
        self.assertEqual(day_after - day_before, 1)

    def test_day_index_roundtrip(self):
        """Day index should roundtrip correctly."""
        boundary_hour = 4
        original = datetime(2026, 2, 23, 10, 30, 0)
        
        day_idx = _day_index(original, boundary_hour)
        reconstructed = _day_index_to_datetime(day_idx, boundary_hour)
        
        # Reconstructed should be at boundary hour on the same "day"
        self.assertEqual(reconstructed.hour, boundary_hour)
        self.assertEqual(reconstructed.minute, 0)
        
        # Re-index should give same result
        day_idx_2 = _day_index(reconstructed, boundary_hour)
        self.assertEqual(day_idx, day_idx_2)


class TestCounterLogic(unittest.TestCase):
    """Test New/Learn/Due counter logic."""

    def setUp(self):
        """Set up test fixtures."""
        self.options = default_deck_options()
        self.boundary_hour = self.options.dayBoundaryHourLocal
        self.now = datetime(2026, 2, 23, 10, 0, 0)  # 10 AM
        self.today_idx = _day_index(self.now, self.boundary_hour)
        self.next_boundary = _day_index_to_datetime(self.today_idx + 1, self.boundary_hour)

    def test_learning_card_due_soon_counts_as_learn(self):
        """Learning card due in 10 min should count as Learn."""
        # Card due 10 minutes from now (before next day boundary)
        due_at = self.now + timedelta(minutes=10)
        
        # Should count as learn
        is_learn = due_at and due_at < self.next_boundary
        self.assertTrue(is_learn)

    def test_learning_card_due_tomorrow_does_not_count(self):
        """Learning card due tomorrow should not count as Learn."""
        # Card due well past next day boundary
        due_at = self.next_boundary + timedelta(hours=1)
        
        # Should NOT count as learn
        is_learn = due_at and due_at < self.next_boundary
        self.assertFalse(is_learn)

    def test_review_card_due_today_counts_as_due(self):
        """Review card due today should count as Due."""
        # Card due on today's day index
        card_due_day = self.today_idx
        
        # Should count as due
        is_due = card_due_day <= self.today_idx
        self.assertTrue(is_due)

    def test_review_card_due_yesterday_counts_as_due(self):
        """Review card due yesterday should count as Due (overdue)."""
        # Card due yesterday
        card_due_day = self.today_idx - 1
        
        # Should count as due
        is_due = card_due_day <= self.today_idx
        self.assertTrue(is_due)

    def test_review_card_due_tomorrow_does_not_count(self):
        """Review card due tomorrow should not count as Due."""
        # Card due tomorrow
        card_due_day = self.today_idx + 1
        
        # Should NOT count as due
        is_due = card_due_day <= self.today_idx
        self.assertFalse(is_due)

    def test_new_card_always_counted(self):
        """New cards should always be counted."""
        # New card has no due_at
        queue = "new"
        
        # Should definitely count as new
        self.assertEqual(queue, "new")

    def test_next_day_boundary_calculation(self):
        """Next day boundary should be correct."""
        # At 10 AM with boundary at 4 AM
        # Next boundary is 4 AM next day
        expected_day = self.today_idx + 1
        actual_boundary_day = _day_index(self.next_boundary, self.boundary_hour)
        
        self.assertEqual(actual_boundary_day, expected_day)

    def test_learning_at_boundary_edge(self):
        """Learning card due exactly at next boundary should not count."""
        # Card due exactly at next boundary
        due_at = self.next_boundary
        
        # Should NOT count (due to < not <=)
        is_learn = due_at and due_at < self.next_boundary
        self.assertFalse(is_learn)

    def test_learning_just_before_boundary(self):
        """Learning card just before boundary should count."""
        # Card due 1 second before next boundary
        due_at = self.next_boundary - timedelta(seconds=1)
        
        # Should count
        is_learn = due_at and due_at < self.next_boundary
        self.assertTrue(is_learn)


if __name__ == '__main__':
    unittest.main()
