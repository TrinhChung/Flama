from datetime import datetime
import unittest

from app.services.anki_scheduler import CardState, default_deck_options
from app.services.study_action_runtime import (
    REVIEW_RATINGS,
    StudyActionValidationError,
    StudyTriggerValidationError,
    compute_review_previews,
    execute_review_action,
    resolve_review_action,
)
from app.services.study_algorithm_registry import (
    DEFAULT_ALGORITHM_IDENTITY,
    StudyAlgorithmNotFoundError,
    resolve_study_algorithm,
)


class StudyActionRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.now = datetime(2026, 8, 27, 9, 0, 0)
        self.options = default_deck_options()

    def test_default_algorithm_is_resolved_by_exact_key_and_version(self):
        adapter = resolve_study_algorithm(
            DEFAULT_ALGORITHM_IDENTITY.key,
            DEFAULT_ALGORITHM_IDENTITY.version,
        )

        self.assertEqual(adapter.identity, DEFAULT_ALGORITHM_IDENTITY)

    def test_unknown_pinned_algorithm_is_rejected(self):
        with self.assertRaises(StudyAlgorithmNotFoundError):
            resolve_study_algorithm("legacy-anki", "missing")

    def test_review_action_has_stable_action_and_trigger_identity(self):
        action = resolve_review_action("review.good")

        self.assertEqual(action.rating, "good")
        self.assertEqual(action.action_key, "review.good")
        self.assertEqual(action.trigger_key, "scheduler.review.good")
        self.assertEqual(action.trigger_contract_version, "1")

    def test_invalid_review_action_is_rejected_without_casting(self):
        with self.assertRaises(StudyActionValidationError):
            resolve_review_action("correct")

    def test_preview_adapter_matches_all_four_actions(self):
        state = CardState(
            type="review",
            intervalDays=5.0,
            ease=2.5,
            dueDay=self.now.date().toordinal(),
            due=self.now,
        )

        previews = compute_review_previews(
            state=state,
            options=self.options,
            now=self.now,
            timezone_name="UTC",
        )

        self.assertEqual(set(previews), set(REVIEW_RATINGS))

    def test_execute_review_action_with_valid_trigger_identity(self):
        state = CardState(type="new")
        result = execute_review_action(
            state=state,
            options=self.options,
            now=self.now,
            action="good",
            timezone_name="UTC",
            trigger_key="scheduler.review.good",
            trigger_contract_version="1",
        )
        self.assertEqual(result.action.rating, "good")
        self.assertEqual(result.metadata()["trigger_key"], "scheduler.review.good")

    def test_execute_review_action_with_mismatched_trigger_is_rejected(self):
        state = CardState(type="new")
        with self.assertRaises(StudyTriggerValidationError):
            execute_review_action(
                state=state,
                options=self.options,
                now=self.now,
                action="good",
                timezone_name="UTC",
                trigger_key="scheduler.review.again",
            )

    def test_execute_review_action_with_invalid_trigger_version_is_rejected(self):
        state = CardState(type="new")
        with self.assertRaises(StudyTriggerValidationError):
            execute_review_action(
                state=state,
                options=self.options,
                now=self.now,
                action="good",
                timezone_name="UTC",
                trigger_contract_version="999",
            )


if __name__ == "__main__":
    unittest.main()
