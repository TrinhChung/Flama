"""P9-03a: the state-only Card adapter matches the CardProgress mapper."""

from __future__ import annotations

from datetime import datetime
from itertools import product
from types import SimpleNamespace
import unittest

from app.services.anki_scheduler import _round_review_interval, default_deck_options
from app.services.study_note_card_projection import (
    NoteCardBurial,
    project_note_card,
    rounded_interval_days,
)
from app.services.study_progress_shadow_codec import StudyProgressCodecError
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress


CREATED_AT = datetime(2026, 2, 1, 1, 2, 3, 456789)
CARD_CREATED_AT = datetime(2026, 1, 31, 0, 1, 2, 345678)
PROJECTED_AT = datetime(2026, 2, 3, 3, 4, 5)


def _progress(card_id: str = "card-a", **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 201,
        "user_id": 7,
        "card_id": card_id,
        "queue": "review",
        "step_index": 0,
        "due_at": datetime(2026, 2, 8, 4, 5, 6, 789012),
        "due_day": 20492,
        "interval_days": 13,
        "interval_days_raw": 12.75,
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
        "last_review_event_id": 31,
        "reps": 5,
        "lapses": 1,
        "last_reviewed_at": datetime(2026, 2, 2, 1, 0, 0),
        "revision": 8,
        "created_at": CREATED_AT,
        "updated_at": CREATED_AT,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _mapped(progress: SimpleNamespace, *, card_created_at=CARD_CREATED_AT) -> MappedCardProgress:
    mapped = map_card_progress(
        progress, card_created_at=card_created_at, card_order_key=progress.card_id
    )
    assert isinstance(mapped, MappedCardProgress), mapped
    return mapped


def _burial(progress: SimpleNamespace) -> NoteCardBurial:
    return NoteCardBurial(
        is_buried=progress.is_buried, buried_until_day=progress.buried_until_day
    )


class NoteCardProjectionContractTests(unittest.TestCase):
    def assert_same_as_mapper(self, progress: SimpleNamespace) -> None:
        mapped = _mapped(progress)
        projected = project_note_card(
            mapped.state.payload,
            burial=_burial(progress),
            card_id=progress.card_id,
            card_created_at=CARD_CREATED_AT,
        )
        self.assertEqual(projected.availability, mapped.availability)
        self.assertEqual(projected.semantic_state_hash, mapped.semantic_state_hash)
        self.assertEqual(projected.algorithm_state_hash, mapped.algorithm_state_hash)

    def test_matches_mapper_across_queue_due_suspend_bury_memory_and_leech(self):
        queues = (
            ("new", 0, 0.0, 0),
            ("learn", 1, 0.0, 0),
            ("learning", 2, 0.0, 0),
            ("relearning", 0, 1.0, 1),
            ("review", 0, 12.75, 13),
            ("review", 0, 20.5, 21),
            ("review", 0, 801.0, 801),
        )
        dues = (
            (None, None),
            (datetime(2026, 2, 4, 1, 0, 0), None),
            (datetime(2026, 2, 8, 4, 5, 6, 789012), 20492),
        )
        burials = ((False, None), (True, None), (True, 20500), (False, 20500))
        memories = ((None, None), (10.5, 4.25))
        leeches = ((0, None), (3, PROJECTED_AT))
        for (
            (queue, step, interval_raw, interval),
            (due_at, due_day),
            suspended,
            (is_buried, buried_until_day),
            (stability, difficulty),
            (leech_lapses, leech_at),
        ) in product(queues, dues, (False, True), burials, memories, leeches):
            progress = _progress(
                queue=queue,
                step_index=step,
                interval_days=interval,
                interval_days_raw=interval_raw,
                due_at=due_at,
                due_day=due_day,
                is_suspended=suspended,
                suspension_reason="leech" if suspended else None,
                is_buried=is_buried,
                buried_until_day=buried_until_day,
                memory_stability=stability,
                memory_difficulty=difficulty,
                scheduler_mode="fsrs" if stability is not None else "legacy",
                last_leech_lapses=leech_lapses,
                last_leech_at=leech_at,
                lapses=3,
            )
            with self.subTest(
                queue=queue, due=due_day, suspended=suspended, buried=(is_buried, buried_until_day),
                memory=stability, leech=leech_lapses,
            ):
                self.assert_same_as_mapper(progress)

    def test_siblings_share_semantic_hash_and_differ_only_by_card(self):
        state = _mapped(_progress()).state.payload
        first = project_note_card(
            state, burial=NoteCardBurial(), card_id="card-a", card_created_at=CARD_CREATED_AT
        )
        second = project_note_card(
            state, burial=NoteCardBurial(), card_id="card-b", card_created_at=CREATED_AT
        )
        self.assertEqual(first.semantic_state_hash, second.semantic_state_hash)
        self.assertEqual(first.availability.card_order_key, b"card-a")
        self.assertEqual(second.availability.card_order_key, b"card-b")
        self.assertEqual(second.availability.card_created_at, CREATED_AT)

    def test_rejects_what_the_mapper_rejects(self):
        state = dict(_mapped(_progress()).state.payload)
        cases = (
            ({**state, "type": "learn"}, NoteCardBurial(), "card-a", CARD_CREATED_AT, "UNSUPPORTED_QUEUE"),
            ({**state, "suspended": 0}, NoteCardBurial(), "card-a", CARD_CREATED_AT, "INVALID_STATE_VALUE"),
            ({**state, "due_at": "2026-02-08T04:05:06Z"}, NoteCardBurial(), "card-a", CARD_CREATED_AT, "INVALID_STATE_VALUE"),
            ({**state, "due_day": "-1"}, NoteCardBurial(), "card-a", CARD_CREATED_AT, "INVALID_STATE_VALUE"),
            (state, NoteCardBurial(is_buried=1), "card-a", CARD_CREATED_AT, "INVALID_STATE_VALUE"),
            (state, NoteCardBurial(buried_until_day=-2), "card-a", CARD_CREATED_AT, "INVALID_STATE_VALUE"),
            (state, NoteCardBurial(), "", CARD_CREATED_AT, "INVALID_STATE_VALUE"),
            (state, NoteCardBurial(), "card-a", None, "MISSING_CARD_CREATED_AT"),
        )
        for payload, burial, card_id, created_at, code in cases:
            with self.subTest(code=code, card_id=card_id, burial=burial):
                with self.assertRaises(StudyProgressCodecError) as raised:
                    project_note_card(
                        payload, burial=burial, card_id=card_id, card_created_at=created_at
                    )
                self.assertEqual(raised.exception.code, code)


class RoundedIntervalTests(unittest.TestCase):
    def test_review_uses_deck_rounding_and_readers_round_half_up(self):
        options = default_deck_options()
        for raw in (1.0, 1.49, 1.5, 12.75, 20.5, 20.49, 801.0, 36500.0):
            with self.subTest(raw=raw):
                expected = _round_review_interval(raw, options)
                self.assertEqual(
                    rounded_interval_days(queue="review", interval_days=raw, deck_options=options),
                    expected,
                )
                self.assertEqual(rounded_interval_days(queue="review", interval_days=raw), expected)

    def test_other_queues_keep_the_projection_rounding(self):
        for queue in ("new", "learning", "relearning"):
            for raw, expected in ((0.0, 0), (0.4, 0), (1.0, 1), (1.6, 2), (2.5, 2)):
                with self.subTest(queue=queue, raw=raw):
                    self.assertEqual(
                        rounded_interval_days(
                            queue=queue, interval_days=raw, deck_options=default_deck_options()
                        ),
                        expected,
                    )
                    self.assertEqual(
                        rounded_interval_days(queue=queue, interval_days=raw), expected
                    )


if __name__ == "__main__":
    unittest.main()
