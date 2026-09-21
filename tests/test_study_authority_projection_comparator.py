"""P5-03 exact Note-to-sibling-Card comparison without product routing."""

from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
import unittest

from app.services.study_authority_projection_comparator import (
    ProjectionCandidate,
    ProjectionComparisonError,
    compare_note_legacy_projection,
)
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress


CREATED_AT = datetime(2026, 1, 1, 1, 2, 3, 123456)
DUE_AT = datetime(2026, 1, 8, 2, 3, 4, 567890)


def _progress(card_id: str, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 101 if card_id == "card-a" else 102,
        "user_id": 7,
        "card_id": card_id,
        "queue": "learning",
        "step_index": 1,
        "due_at": DUE_AT,
        "due_day": None,
        "interval_days": 0,
        "interval_days_raw": -0.0,
        "is_suspended": False,
        "is_buried": False,
        "buried_until_day": None,
        "review_kind": "review",
        "scheduler_mode": "legacy",
        "ease_factor": 2.5,
        "memory_stability": None,
        "memory_difficulty": None,
        "suspension_reason": None,
        "last_leech_at": None,
        "last_leech_lapses": 0,
        "last_review_event_id": 17,
        "reps": 3,
        "lapses": 0,
        "last_reviewed_at": datetime(2026, 1, 7, 3, 4, 5, 123456),
        "revision": 4,
        "created_at": CREATED_AT,
        "updated_at": DUE_AT,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _mapped(progress: SimpleNamespace) -> MappedCardProgress:
    result = map_card_progress(progress, card_created_at=CREATED_AT)
    assert isinstance(result, MappedCardProgress)
    return result


def _compare(
    expected: MappedCardProgress,
    raw_by_card: dict[str, bytes],
    *progress_rows: SimpleNamespace,
    **overrides: object,
):
    arguments: dict[str, object] = {
        "expected_learner_user_id": 7,
        "algorithm_key": ALGORITHM_KEY,
        "algorithm_version": ALGORITHM_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "storage_codec": STORAGE_CODEC,
        "state_payload": expected.state.payload,
        "expected_state_payload_size": expected.state.size,
        "expected_algorithm_state_hash": expected.algorithm_state_hash,
        "expected_semantic_state_hash": expected.semantic_state_hash,
        "expected_raw_digest_by_card": raw_by_card,
        "candidates": tuple(
            ProjectionCandidate(progress=row, card_created_at=CREATED_AT)
            for row in progress_rows
        ),
    }
    arguments.update(overrides)
    return compare_note_legacy_projection(**arguments)


class StudyAuthorityProjectionComparatorTests(unittest.TestCase):
    def test_two_siblings_preserve_note_state_and_independent_raw_metadata(self):
        first = _progress("card-a")
        second = _progress("card-b", last_review_event_id=18, revision=5)
        mapped_first = _mapped(first)
        mapped_second = _mapped(second)
        self.assertEqual(mapped_first.state.digest, mapped_second.state.digest)
        self.assertEqual(mapped_first.semantic_state_hash, mapped_second.semantic_state_hash)
        self.assertNotEqual(mapped_first.raw.digest, mapped_second.raw.digest)

        checked = _compare(
            mapped_first,
            {"card-a": mapped_first.raw.digest, "card-b": mapped_second.raw.digest},
            second,
            first,
        )
        self.assertEqual(checked.card_ids, ("card-a", "card-b"))
        self.assertEqual(checked.semantic_state_hash, mapped_first.semantic_state_hash)

    def test_missing_and_duplicate_siblings_fail_closed(self):
        first = _progress("card-a")
        mapped = _mapped(first)
        raw = {"card-a": mapped.raw.digest, "card-b": b"b" * 32}
        with self.assertRaises(ProjectionComparisonError) as missing:
            _compare(mapped, raw, first)
        self.assertEqual(missing.exception.code, "MISSING_SIBLING")

        with self.assertRaises(ProjectionComparisonError) as duplicate:
            _compare(mapped, {"card-a": mapped.raw.digest}, first, first)
        self.assertEqual(duplicate.exception.code, "DUPLICATE_SIBLING")

    def test_state_semantic_and_raw_mismatches_are_distinct(self):
        original = _progress("card-a")
        expected = _mapped(original)
        raw = {"card-a": expected.raw.digest}
        cases = (
            (_progress("card-a", reps=4), "STATE_MISMATCH"),
            (_progress("card-a", is_buried=True), "SEMANTIC_MISMATCH"),
            (_progress("card-a", last_review_event_id=19), "RAW_MISMATCH"),
            (_progress("card-a", queue="learn"), "RAW_MISMATCH"),
            (_progress("card-a", interval_days_raw=0.0), "RAW_MISMATCH"),
        )
        for candidate, code in cases:
            with self.subTest(code=code, candidate=candidate):
                with self.assertRaises(ProjectionComparisonError) as failure:
                    _compare(expected, raw, candidate)
                self.assertEqual(failure.exception.code, code)

    def test_unknown_algorithm_and_unmappable_candidate_fail_closed(self):
        original = _progress("card-a")
        expected = _mapped(original)
        raw = {"card-a": expected.raw.digest}
        with self.assertRaises(ProjectionComparisonError) as unknown:
            _compare(expected, raw, original, algorithm_version="unregistered")
        self.assertEqual(unknown.exception.code, "STATE_DECODER_UNAVAILABLE")

        with self.assertRaises(ProjectionComparisonError) as unmappable:
            _compare(expected, raw, _progress("card-a", ease_factor=float("nan")))
        self.assertEqual(unmappable.exception.code, "UNMAPPABLE_SIBLING")

    def test_wrong_learner_or_stored_state_hash_fails_closed(self):
        original = _progress("card-a")
        expected = _mapped(original)
        raw = {"card-a": expected.raw.digest}
        with self.assertRaises(ProjectionComparisonError) as wrong_user:
            _compare(expected, raw, _progress("card-a", user_id=8))
        self.assertEqual(wrong_user.exception.code, "WRONG_LEARNER")

        with self.assertRaises(ProjectionComparisonError) as wrong_hash:
            _compare(
                expected,
                raw,
                original,
                expected_algorithm_state_hash=b"x" * 32,
            )
        self.assertEqual(wrong_hash.exception.code, "STATE_HASH_MISMATCH")

        with self.assertRaises(ProjectionComparisonError) as wrong_size:
            _compare(expected, raw, original, expected_state_payload_size=1)
        self.assertEqual(wrong_size.exception.code, "STATE_HASH_MISMATCH")

    def test_empty_or_invalid_expectation_is_not_a_vacuous_pass(self):
        expected = _mapped(_progress("card-a"))
        with self.assertRaises(ProjectionComparisonError) as empty:
            _compare(expected, {})
        self.assertEqual(empty.exception.code, "INVALID_EXPECTATION")

        with self.assertRaises(ProjectionComparisonError) as bad_hash:
            _compare(expected, {"card-a": b"short"}, _progress("card-a"))
        self.assertEqual(bad_hash.exception.code, "INVALID_EXPECTATION")


if __name__ == "__main__":
    unittest.main()
