"""Frozen MySQL text-profile vectors shared with the browser implementation."""

from datetime import datetime
import json
from pathlib import Path
import struct
import unittest

from app.services.anki_scheduler import CardState, FsrsMemoryState, default_deck_options
from app.services.study_note_storage_precision import (
    NOTE_STORAGE_PROFILE, StudyStoragePrecisionError, legacy_float_round_trip,
    normalize_note_transition_state,
)
from app.services.study_service import NativeReviewTransitionInput, execute_native_review_transition


class StudyNoteStoragePrecisionTests(unittest.TestCase):
    def test_shared_scalar_vectors_are_exact_and_idempotent(self):
        fixture = json.loads((Path(__file__).parent / "fixtures/study/note-storage-precision-v1.json").read_text())
        self.assertEqual(fixture["profile"], NOTE_STORAGE_PROFILE)
        for vector in fixture["cases"]:
            with self.subTest(vector=vector):
                actual = legacy_float_round_trip(vector["input"])
                self.assertEqual(struct.pack(">d", actual), struct.pack(">d", vector["expected"]))
                self.assertEqual(struct.pack(">d", legacy_float_round_trip(actual)), struct.pack(">d", actual))

    def test_invalid_or_overflowing_values_fail_closed(self):
        for value in (True, "2.35", None, float("nan"), float("inf"), float("-inf"), 1e100):
            with self.subTest(value=value), self.assertRaises(StudyStoragePrecisionError):
                legacy_float_round_trip(value)

    def test_state_normalization_copies_only_numeric_outputs(self):
        before = CardState(type="review", intervalDays=1 / 3, ease=2.0500000000000003,
                           memoryState=FsrsMemoryState(stability=1.015625, difficulty=1.046875),
                           due=datetime(2026, 9, 27), reps=5)
        after = normalize_note_transition_state(before)
        self.assertIsNot(after, before)
        self.assertEqual(after.intervalDays, 0.333333)
        self.assertEqual(after.ease, 2.05)
        self.assertEqual(after.memoryState, FsrsMemoryState(stability=1.01562, difficulty=1.04688))
        self.assertEqual(before.memoryState.stability, 1.015625)
        self.assertEqual(after.due, before.due)
        self.assertEqual(after.reps, before.reps)

    def test_native_note_profile_does_not_change_legacy_evaluator(self):
        command = dict(state=CardState(type="review", ease=2.2, intervalDays=5),
                       deck_options=default_deck_options(), reviewed_at=datetime(2026, 9, 27),
                       action="hard", timezone_name="UTC")
        legacy = execute_native_review_transition(NativeReviewTransitionInput(**command))
        note = execute_native_review_transition(NativeReviewTransitionInput(**command, storage_profile=NOTE_STORAGE_PROFILE))
        self.assertEqual(legacy.state.ease, 2.2 - 0.15)
        self.assertNotEqual(legacy.state.ease, note.state.ease)
        self.assertEqual(note.state.ease, 2.05)
        self.assertNotIn("storage_profile", legacy.metadata())
        self.assertEqual(note.metadata()["storage_profile"], NOTE_STORAGE_PROFILE)


if __name__ == "__main__":
    unittest.main()
