from datetime import datetime, timedelta
import unittest

from app.services.anki_scheduler import (
    CardState,
    applyAnswer,
    computeAnswerPreview,
    default_deck_options,
)


class AnkiSchedulerTests(unittest.TestCase):
    def setUp(self):
        self.options = default_deck_options()
        self.now = datetime(2026, 2, 22, 9, 0, 0)

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


if __name__ == "__main__":
    unittest.main()
