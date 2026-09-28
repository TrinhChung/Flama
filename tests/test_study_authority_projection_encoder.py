"""P5-03 lossless Note-authority to legacy Card projection vectors."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from types import SimpleNamespace
import unittest

from app.services.study_authority_projection_encoder import (
    PRESERVE_MATCHING_STATE,
    LegacyProjectionEncodingError,
    LegacyProjectionMetadata,
    LegacySiblingBaseline,
    encode_note_state_to_legacy_cards,
)
from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import serialize_raw_card_progress
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress


CREATED_AT = datetime(2026, 2, 1, 1, 2, 3, 456789)
CARD_CREATED_AT = datetime(2026, 1, 31, 0, 1, 2, 345678)
BASE_UPDATED_AT = datetime(2026, 2, 2, 2, 3, 4, 567890)
PROJECTED_AT = datetime(2026, 2, 3, 3, 4, 5)
DUE_AT = datetime(2026, 2, 8, 4, 5, 6)
LAST_REVIEWED_AT = datetime(2026, 2, 3, 2, 3, 4)


def _progress(card_id: str, **overrides: object) -> SimpleNamespace:
    values: dict[str, object] = {
        "id": 201 if card_id == "card-a" else 202,
        "user_id": 7,
        "card_id": card_id,
        "queue": "learn",
        "step_index": 0,
        "due_at": datetime(2026, 2, 4, 1, 0, 0),
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
        "last_review_event_id": 31,
        "reps": 1,
        "lapses": 0,
        "last_reviewed_at": datetime(2026, 2, 2, 1, 0, 0),
        "revision": 8 if card_id == "card-a" else 11,
        "created_at": CREATED_AT,
        "updated_at": BASE_UPDATED_AT,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def _target(**overrides: object) -> MappedCardProgress:
    progress = _progress(
        "target-only",
        id=999,
        queue="review",
        step_index=2,
        due_at=DUE_AT,
        due_day=20492,
        interval_days=13,
        interval_days_raw=12.75,
        is_suspended=True,
        is_buried=True,
        buried_until_day=20493,
        review_kind="manual",
        scheduler_mode="fsrs",
        ease_factor=2.5,
        memory_stability=10.5,
        memory_difficulty=4.25,
        suspension_reason="leech",
        last_leech_at=PROJECTED_AT,
        last_leech_lapses=3,
        last_review_event_id=99,
        reps=14,
        lapses=3,
        last_reviewed_at=LAST_REVIEWED_AT,
    )
    for field_name, value in overrides.items():
        setattr(progress, field_name, value)
    mapped = map_card_progress(progress, card_created_at=CREATED_AT)
    assert isinstance(mapped, MappedCardProgress)
    return mapped


def _baseline(
    progress: SimpleNamespace,
    *,
    event_id: int | None,
    disposition_code: str = "APPLY_NOTE_STATE",
) -> LegacySiblingBaseline:
    raw = serialize_raw_card_progress(progress)
    return LegacySiblingBaseline(
        card_id=progress.card_id,
        expected_base_revision=progress.revision,
        card_created_at=CARD_CREATED_AT,
        raw_payload=raw.payload,
        raw_payload_size=raw.size,
        raw_payload_hash=raw.digest,
        projected_last_review_event_id=event_id,
        disposition_code=disposition_code,
    )


def _metadata(**overrides: object) -> LegacyProjectionMetadata:
    values: dict[str, object] = {
        "interval_days_rounded": 13,
        "is_buried": True,
        "buried_until_day": 20493,
        "last_leech_at": PROJECTED_AT,
        "last_leech_lapses": 3,
        "projected_at": PROJECTED_AT,
    }
    values.update(overrides)
    return LegacyProjectionMetadata(**values)  # type: ignore[arg-type]


def _encode(
    *siblings: LegacySiblingBaseline,
    metadata: LegacyProjectionMetadata | None = None,
    target_overrides: dict[str, object] | None = None,
    **overrides: object,
):
    target = _target(**(target_overrides or {}))
    arguments: dict[str, object] = {
        "expected_learner_user_id": 7,
        "algorithm_key": ALGORITHM_KEY,
        "algorithm_version": ALGORITHM_VERSION,
        "state_schema_version": STATE_SCHEMA_VERSION,
        "storage_codec": STORAGE_CODEC,
        "state_payload": target.state.payload,
        "expected_state_payload_size": target.state.size,
        "expected_algorithm_state_hash": target.algorithm_state_hash,
        "metadata": metadata or _metadata(),
        "siblings": siblings,
    }
    arguments.update(overrides)
    return encode_note_state_to_legacy_cards(**arguments)  # type: ignore[arg-type]


class StudyAuthorityProjectionEncoderTests(unittest.TestCase):
    def test_two_siblings_are_exactly_encoded_and_self_verified(self):
        first = _progress("card-a")
        second = _progress("card-b", last_review_event_id=44)
        first_raw_before = deepcopy(serialize_raw_card_progress(first).payload)
        encoded = _encode(
            _baseline(first, event_id=101),
            _baseline(second, event_id=102),
        )

        self.assertEqual(encoded.comparison.card_ids, ("card-a", "card-b"))
        self.assertEqual(set(encoded.raw_digest_by_card), {"card-a", "card-b"})
        projected_first, projected_second = encoded.siblings
        self.assertEqual(projected_first.progress.queue, "review")
        self.assertEqual(projected_first.progress.interval_days, 13)
        self.assertEqual(projected_first.progress.interval_days_raw, 12.75)
        self.assertEqual(projected_first.progress.revision, 9)
        self.assertEqual(projected_second.progress.revision, 12)
        self.assertEqual(projected_first.progress.last_review_event_id, 101)
        self.assertEqual(projected_second.progress.last_review_event_id, 102)
        self.assertEqual(projected_first.progress.created_at, CREATED_AT)
        self.assertEqual(projected_first.progress.updated_at, PROJECTED_AT)
        self.assertEqual(projected_first.card_created_at, CARD_CREATED_AT)
        self.assertEqual(serialize_raw_card_progress(first).payload, first_raw_before)

    def test_new_sibling_can_apply_while_matching_existing_sibling_is_preserved(self):
        first_projection = _encode(_baseline(_progress("card-a"), event_id=101))
        existing = first_projection.siblings[0]
        existing_row = SimpleNamespace(**existing.progress.as_dict())
        existing_raw = existing.raw.encoded
        new_row = _progress("card-c", id=203, revision=0, last_review_event_id=None)

        encoded = _encode(
            _baseline(
                existing_row,
                event_id=101,
                disposition_code=PRESERVE_MATCHING_STATE,
            ),
            _baseline(new_row, event_id=None),
        )

        preserved, materialized = encoded.siblings
        self.assertEqual(preserved.raw.encoded, existing_raw)
        self.assertEqual(preserved.progress.revision, 9)
        self.assertEqual(materialized.progress.revision, 1)
        self.assertEqual(encoded.comparison.card_ids, ("card-a", "card-c"))

    def test_single_card_raw_document_matches_independent_golden_vector(self):
        encoded = _encode(_baseline(_progress("card-a"), event_id=101))
        sibling = encoded.siblings[0]
        self.assertEqual(sibling.raw.encoded.decode("utf-8"), GOLDEN_CARD_A_JSON)
        self.assertEqual(sibling.raw.digest.hex(), GOLDEN_CARD_A_SHA256)

    def test_hash_revision_identity_and_learner_guards_fail_closed(self):
        source = _progress("card-a")
        baseline = _baseline(source, event_id=101)
        cases = (
            (
                LegacySiblingBaseline(
                    **{**baseline.__dict__, "raw_payload_hash": b"x" * 32}
                ),
                "BASELINE_HASH_MISMATCH",
            ),
            (
                LegacySiblingBaseline(
                    **{**baseline.__dict__, "expected_base_revision": 7}
                ),
                "STALE_BASELINE",
            ),
            (
                LegacySiblingBaseline(**{**baseline.__dict__, "card_id": "wrong"}),
                "INVALID_CARD_IDENTITY",
            ),
        )
        for candidate, code in cases:
            with self.subTest(code=code):
                with self.assertRaises(LegacyProjectionEncodingError) as failure:
                    _encode(candidate)
                self.assertEqual(failure.exception.code, code)

        with self.assertRaises(LegacyProjectionEncodingError) as wrong_learner:
            _encode(baseline, expected_learner_user_id=8)
        self.assertEqual(wrong_learner.exception.code, "WRONG_LEARNER")

    def test_duplicate_empty_and_unknown_state_fail_closed(self):
        baseline = _baseline(_progress("card-a"), event_id=101)
        with self.assertRaises(LegacyProjectionEncodingError) as empty:
            _encode()
        self.assertEqual(empty.exception.code, "MISSING_SIBLING")

        with self.assertRaises(LegacyProjectionEncodingError) as duplicate:
            _encode(baseline, baseline)
        self.assertEqual(duplicate.exception.code, "DUPLICATE_SIBLING")

        with self.assertRaises(LegacyProjectionEncodingError) as unknown:
            _encode(baseline, algorithm_version="not-registered")
        self.assertEqual(unknown.exception.code, "STATE_DECODER_UNAVAILABLE")

        invalid_disposition = LegacySiblingBaseline(
            **{**baseline.__dict__, "disposition_code": "UNKNOWN"}
        )
        with self.assertRaises(LegacyProjectionEncodingError) as disposition:
            _encode(invalid_disposition)
        self.assertEqual(disposition.exception.code, "INVALID_SIBLING_DISPOSITION")

    def test_unprojectable_leech_metadata_is_rejected(self):
        baseline = _baseline(_progress("card-a"), event_id=101)
        with self.assertRaises(LegacyProjectionEncodingError) as failure:
            _encode(baseline, metadata=_metadata(last_leech_lapses=0))
        self.assertEqual(failure.exception.code, "UNPROJECTABLE_STATE")

    def test_projection_metadata_requires_unambiguous_utc_storage_values(self):
        baseline = _baseline(_progress("card-a"), event_id=101)
        invalid = (
            (_metadata(interval_days_rounded=-1), "INVALID_PROJECTION_METADATA"),
            (
                _metadata(interval_days_rounded=1 << 31),
                "INVALID_PROJECTION_METADATA",
            ),
            (
                _metadata(projected_at=PROJECTED_AT.replace(tzinfo=timezone.utc)),
                "INVALID_PROJECTION_METADATA",
            ),
            (
                _metadata(projected_at=PROJECTED_AT.replace(microsecond=1)),
                "UNPROJECTABLE_LEGACY_TIMESTAMP",
            ),
            (_metadata(is_buried=1), "INVALID_PROJECTION_METADATA"),
        )
        for metadata, code in invalid:
            with self.subTest(metadata=metadata, code=code):
                with self.assertRaises(LegacyProjectionEncodingError) as failure:
                    _encode(baseline, metadata=metadata)
                self.assertEqual(failure.exception.code, code)

    def test_state_must_round_trip_through_legacy_mysql_float_and_datetime(self):
        baseline = _baseline(_progress("card-a"), event_id=101)
        _encode(baseline, target_overrides={"ease_factor": 2.35})
        with self.assertRaises(LegacyProjectionEncodingError) as float_failure:
            _encode(baseline, target_overrides={"ease_factor": 2.3500001})
        self.assertEqual(
            float_failure.exception.code, "UNPROJECTABLE_LEGACY_FLOAT"
        )
        # Binary32-exact is insufficient: MySQL text rounds this to 1.01562.
        with self.assertRaises(LegacyProjectionEncodingError) as binary32_failure:
            _encode(baseline, target_overrides={"ease_factor": 1.015625})
        self.assertEqual(binary32_failure.exception.code, "UNPROJECTABLE_LEGACY_FLOAT")

        with self.assertRaises(LegacyProjectionEncodingError) as time_failure:
            _encode(
                baseline,
                target_overrides={"due_at": DUE_AT.replace(microsecond=1)},
            )
        self.assertEqual(
            time_failure.exception.code, "UNPROJECTABLE_LEGACY_TIMESTAMP"
        )


GOLDEN_CARD_A_JSON = (
    '{"buried_until_day":"20493","card_id":"card-a",'
    '"created_at":"2026-02-01T01:02:03.456789Z",'
    '"due_at":"2026-02-08T04:05:06.000000Z","due_day":"20492",'
    '"ease_factor":"f64:4004000000000000","id":"201",'
    '"interval_days":"13","interval_days_raw":"f64:4029800000000000",'
    '"is_buried":true,"is_suspended":true,"lapses":"3",'
    '"last_leech_at":"2026-02-03T03:04:05.000000Z",'
    '"last_leech_lapses":"3","last_review_event_id":"101",'
    '"last_reviewed_at":"2026-02-03T02:03:04.000000Z",'
    '"memory_difficulty":"f64:4011000000000000",'
    '"memory_stability":"f64:4025000000000000","queue":"review",'
    '"reps":"14","review_kind":"manual","revision":"9",'
    '"scheduler_mode":"fsrs","step_index":"2",'
    '"suspension_reason":"leech",'
    '"updated_at":"2026-02-03T03:04:05.000000Z","user_id":"7"}'
)
GOLDEN_CARD_A_SHA256 = (
    "87bc91938bc06e0c213a7227f659c5f4d4e76b3ac67fe686005fdde98d35b33b"
)


if __name__ == "__main__":
    unittest.main()
