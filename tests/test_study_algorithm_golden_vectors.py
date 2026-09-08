from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
import unittest

from app.services.anki_scheduler import (
    CardState,
    FsrsAnswerState,
    FsrsMemoryState,
    FsrsNextStates,
    default_deck_options,
)
from app.services.study_action_runtime import (
    REVIEW_RATINGS,
    compute_review_previews,
    execute_review_action,
)
from app.services.study_algorithm_registry import DEFAULT_ALGORITHM_IDENTITY


FIXTURE_PATH = (
    Path(__file__).parent
    / "fixtures"
    / "study"
    / "legacy-anki-1.0.0-golden-vectors.json"
)


def _parse_utc(value: str | None) -> datetime | None:
    if value is None:
        return None
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    return parsed.astimezone(timezone.utc).replace(tzinfo=None)


def _format_utc(value: datetime | None) -> str | None:
    if value is None:
        return None
    if value.tzinfo is not None:
        value = value.astimezone(timezone.utc).replace(tzinfo=None)
    return value.isoformat(timespec="milliseconds") + "Z"


def _card_from_wire(raw: dict) -> CardState:
    memory_state = raw.get("memory_state")
    return CardState(
        type=raw["type"],
        stepIndex=raw["step_index"],
        due=_parse_utc(raw.get("due_at")),
        dueDay=raw.get("due_day"),
        intervalDays=raw["interval_days"],
        ease=raw["ease"],
        reps=raw["reps"],
        lapses=raw["lapses"],
        lastReviewAt=_parse_utc(raw.get("last_review_at")),
        reviewKind=raw["review_kind"],
        schedulerMode=raw["scheduler_mode"],
        suspended=raw["suspended"],
        suspensionReason=raw.get("suspension_reason"),
        leeched=raw["leeched"],
        memoryState=FsrsMemoryState(**memory_state) if memory_state else None,
    )


def _card_to_wire(card: CardState) -> dict:
    return {
        "type": card.type,
        "step_index": card.stepIndex,
        "due_at": _format_utc(card.due),
        "due_day": card.dueDay,
        "interval_days": card.intervalDays,
        "ease": card.ease,
        "reps": card.reps,
        "lapses": card.lapses,
        "last_review_at": _format_utc(card.lastReviewAt),
        "review_kind": card.reviewKind,
        "scheduler_mode": card.schedulerMode,
        "suspended": card.suspended,
        "suspension_reason": card.suspensionReason,
        "leeched": card.leeched,
        "memory_state": asdict(card.memoryState) if card.memoryState else None,
    }


def _options_from_wire(base: dict, patch: dict | None):
    raw = {**base, **(patch or {})}
    options = default_deck_options()
    options.learningSteps = [
        timedelta(milliseconds=value) for value in raw["learning_steps_ms"]
    ]
    options.graduatingIntervalDays = raw["graduating_interval_days"]
    options.easyIntervalDays = raw["easy_interval_days"]
    options.relearningSteps = [
        timedelta(milliseconds=value) for value in raw["relearning_steps_ms"]
    ]
    options.minimumIntervalDays = raw["minimum_interval_days"]
    options.startingEase = raw["starting_ease"]
    options.easyBonus = raw["easy_bonus"]
    options.intervalModifier = raw["interval_modifier"]
    options.hardFactor = raw["hard_factor"]
    options.newIntervalFactor = raw["new_interval_factor"]
    options.minEase = raw["min_ease"]
    options.maxIntervalDays = raw["max_interval_days"]
    options.dayBoundaryHourLocal = raw["day_boundary_hour_local"]
    options.learnAheadSeconds = raw["learn_ahead_seconds"]
    options.leechThreshold = raw["leech_threshold"]
    options.leechSuspend = raw["leech_suspend"]
    options.schedulerMode = raw["scheduler_mode"]
    options.reviewFuzzFactor = raw["review_fuzz_factor"]

    fsrs_states = raw.get("fsrs_next_states")
    if fsrs_states is None:
        options.fsrsNextStates = None
    else:
        options.fsrsNextStates = FsrsNextStates(
            **{
                rating: FsrsAnswerState(
                    intervalDays=value["interval_days"],
                    memory=(
                        FsrsMemoryState(**value["memory"])
                        if value.get("memory")
                        else None
                    ),
                )
                for rating, value in fsrs_states.items()
            }
        )
    return options


class StudyAlgorithmGoldenVectorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))

    def test_fixture_is_pinned_to_the_registered_compatibility_contract(self):
        self.assertEqual(
            self.fixture["vector_schema_version"],
            "study-algorithm-golden-vectors.v1",
        )
        self.assertEqual(
            self.fixture["algorithm"],
            {
                "key": DEFAULT_ALGORITHM_IDENTITY.key,
                "version": DEFAULT_ALGORITHM_IDENTITY.version,
                "state_schema_version": DEFAULT_ALGORITHM_IDENTITY.state_schema_version,
            },
        )
        self.assertEqual(len(self.fixture["cases"]), 10)
        self.assertEqual(
            sum(len(vector["expected"]) for vector in self.fixture["cases"]),
            40,
        )

    def test_python_runtime_matches_all_frozen_cross_language_vectors(self):
        contract = self.fixture["action_contract"]
        self.assertEqual(set(contract["ratings"]), set(REVIEW_RATINGS))

        for vector in self.fixture["cases"]:
            options = _options_from_wire(
                self.fixture["base_options"],
                vector.get("options_patch"),
            )
            source = _card_from_wire(vector["state"])
            now = _parse_utc(vector["now"])
            self.assertIsNotNone(now)
            previews = compute_review_previews(
                state=source,
                options=options,
                now=now,
                timezone_name=vector["timezone"],
            )

            for rating in REVIEW_RATINGS:
                with self.subTest(vector=vector["id"], rating=rating):
                    expected = vector["expected"][rating]
                    transition = execute_review_action(
                        state=source,
                        options=options,
                        now=now,
                        action=rating,
                        timezone_name=vector["timezone"],
                        algorithm_key=self.fixture["algorithm"]["key"],
                        algorithm_version=self.fixture["algorithm"]["version"],
                    )
                    expected_state = {
                        **vector["state"],
                        **expected["state_patch"],
                    }
                    self.assertEqual(_card_to_wire(transition.state), expected_state)
                    self.assertEqual(previews[rating], expected["preview"])
                    self.assertEqual(
                        transition.metadata(),
                        {
                            **contract["ratings"][rating],
                            "action_contract_version": contract["version"],
                            "trigger_contract_version": contract["version"],
                            "algorithm_key": self.fixture["algorithm"]["key"],
                            "algorithm_version": self.fixture["algorithm"]["version"],
                            "state_schema_version": self.fixture["algorithm"]
                            ["state_schema_version"],
                        },
                    )


if __name__ == "__main__":
    unittest.main()
