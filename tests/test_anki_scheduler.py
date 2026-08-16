from datetime import datetime, timedelta
import unittest

from app.services.anki_scheduler import (
    CardState,
    FsrsAnswerState,
    FsrsNextStates,
    applyAnswer,
    computeAnswerPreview,
    default_deck_options,
    format_interval_days,
)


class AnkiSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.options = default_deck_options()
        self.now = datetime(2026, 2, 22, 9, 0, 0)

    def test_format_interval_days_scales_to_months_and_years(self):
        self.assertEqual(format_interval_days(1), "1d")
        self.assertEqual(format_interval_days(15), "15d")
        self.assertEqual(format_interval_days(29), "29d")
        self.assertEqual(format_interval_days(30), "1m")
        self.assertEqual(format_interval_days(45), "1.5m")
        self.assertEqual(format_interval_days(50), "1.7m")
        self.assertEqual(format_interval_days(60), "2m")
        self.assertEqual(format_interval_days(90), "3m")
        self.assertEqual(format_interval_days(180), "6m")
        self.assertEqual(format_interval_days(360), "12m")
        self.assertEqual(format_interval_days(365), "1y")
        self.assertEqual(format_interval_days(500), "1.4y")
        self.assertEqual(format_interval_days(600), "1.6y")
        self.assertEqual(format_interval_days(730), "2y")
        self.assertEqual(format_interval_days(36500), "100y")

    def test_case1_learning_hard_preview_is_6m(self):
        card = CardState(
            type="learning",
            stepIndex=0,
            due=self.now,
            ease=self.options.startingEase,
        )
        preview = computeAnswerPreview(card, self.options, self.now)
        self.assertEqual(preview["hard"]["label"], "<6m")

    def test_case2_review_intervals_sm2(self):
        due_day = self.now.date().toordinal()
        card = CardState(
            type="review",
            intervalDays=10.0,
            ease=2.5,
            dueDay=due_day,
            due=self.now,
        )

        hard = applyAnswer(card, self.options, self.now, "hard")
        good = applyAnswer(card, self.options, self.now, "good")
        easy = applyAnswer(card, self.options, self.now, "easy")

        self.assertAlmostEqual(hard.intervalDays, 12.0, delta=0.01)
        self.assertAlmostEqual(hard.ease, 2.35, delta=0.0001)
        self.assertAlmostEqual(good.intervalDays, 25.0, delta=0.01)
        self.assertAlmostEqual(easy.intervalDays, 32.5, delta=0.01)
        self.assertAlmostEqual(easy.ease, 2.65, delta=0.0001)

    def test_case3_days_late_affects_good_easy_not_hard(self):
        # ivl=5d, daysLate=20d
        due = self.now - timedelta(days=20)
        card = CardState(
            type="review",
            intervalDays=5.0,
            ease=2.5,
            due=due,
            dueDay=due.date().toordinal(),
        )

        hard = applyAnswer(card, self.options, self.now, "hard")
        good = applyAnswer(card, self.options, self.now, "good")
        easy = applyAnswer(card, self.options, self.now, "easy")

        # Hard base uses ivl only: 5 * 1.2 = 6
        self.assertAlmostEqual(hard.intervalDays, 6.0, delta=0.01)
        # Good base uses (5 + 20/2)=15 => *2.5 = 37.5
        self.assertAlmostEqual(good.intervalDays, 37.5, delta=0.01)
        # Easy base uses (5 + 20)=25 => *2.5*1.3 = 81.25
        self.assertAlmostEqual(easy.intervalDays, 81.25, delta=0.01)

    def test_learning_cross_day_boundary_uses_user_timezone(self):
        now_utc = datetime(2026, 2, 22, 18, 55, 0)  # 03:55 Asia/Tokyo local time
        card = CardState(
            type="new",
            stepIndex=0,
            due=now_utc,
            ease=self.options.startingEase,
        )
        preview = computeAnswerPreview(
            card,
            self.options,
            now_utc,
            timezone_name="Asia/Tokyo",
        )

        updated = applyAnswer(
            card,
            self.options,
            now_utc,
            "good",
            timezone_name="Asia/Tokyo",
        )

        self.assertEqual(updated.type, "learning")
        self.assertEqual(preview["good"]["label"], "1d")
        self.assertEqual(updated.intervalDays, 1.0)
        self.assertEqual(updated.due, datetime(2026, 2, 22, 19, 0, 0))
        self.assertEqual(updated.dueDay, datetime(2026, 2, 23, 0, 0, 0).date().toordinal())

    def test_early_review_uses_filtered_kind_and_early_formula(self):
        future_due_day = self.now.date().toordinal() + 3
        card = CardState(
            type="review",
            intervalDays=10.0,
            ease=2.5,
            dueDay=future_due_day,
            due=self.now + timedelta(days=3),
        )

        hard = applyAnswer(card, self.options, self.now, "hard")
        good = applyAnswer(card, self.options, self.now, "good")
        easy = applyAnswer(card, self.options, self.now, "easy")

        self.assertEqual(hard.reviewKind, "filtered")
        self.assertEqual(good.reviewKind, "filtered")
        self.assertEqual(easy.reviewKind, "filtered")
        self.assertAlmostEqual(hard.intervalDays, 8.0, delta=0.01)
        self.assertAlmostEqual(good.intervalDays, 18.0, delta=0.01)
        self.assertAlmostEqual(easy.intervalDays, 20.0, delta=0.01)

    def test_leech_threshold_suspends_on_threshold(self):
        options = default_deck_options()
        options.leechThreshold = 2
        card = CardState(
            type="review",
            intervalDays=5.0,
            ease=2.5,
            dueDay=self.now.date().toordinal(),
            due=self.now,
            lapses=1,
        )

        again = applyAnswer(card, options, self.now, "again")

        self.assertTrue(again.leeched)
        self.assertTrue(again.suspended)
        self.assertEqual(again.lapses, 2)

    def test_fsrs_mode_ignores_interval_modifier_for_passing_answers(self):
        options = default_deck_options()
        options.schedulerMode = "fsrs"
        options.intervalModifier = 0.5
        options.fsrsNextStates = FsrsNextStates(
            again=FsrsAnswerState(intervalDays=1.0),
            hard=FsrsAnswerState(intervalDays=6.0),
            good=FsrsAnswerState(intervalDays=20.0),
            easy=FsrsAnswerState(intervalDays=30.0),
        )
        card = CardState(
            type="review",
            intervalDays=5.0,
            ease=2.5,
            dueDay=self.now.date().toordinal(),
            due=self.now,
        )

        updated = applyAnswer(card, options, self.now, "good")

        self.assertAlmostEqual(updated.intervalDays, 20.0, delta=0.01)


if __name__ == "__main__":
    unittest.main()
