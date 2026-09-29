"""Golden and negative vectors for the Phase 4 shadow-progress codecs."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime
import math
from types import SimpleNamespace
import unittest

from app.services.study_progress_contract import (
    ALGORITHM_KEY,
    ALGORITHM_VERSION,
    STATE_SCHEMA_VERSION,
    STORAGE_CODEC,
)
from app.services.study_progress_shadow_codec import (
    RAW_CARD_PROGRESS_FIELDS,
    STATE_DECODERS,
    StateDecoderRegistry,
    StudyProgressCodecError,
    algorithm_state_hash,
    canonical_typed_document,
    decode_raw_card_progress,
    serialize_raw_card_progress,
    state_document,
)
from app.services.anki_scheduler import CardState
from app.services.study_progress_shadow_mapper import (
    AvailabilityContext,
    MappedCardProgress,
    MappingFailure,
    build_contributor_evidence,
    encode_identity,
    evaluate_availability,
    map_card_progress,
)
from models.card_progress import CardProgress


RAW_GOLDEN = (
    '{"buried_until_day":null,"card_id":"Card-A",'
    '"created_at":"2025-12-01T00:00:00.000000Z",'
    '"due_at":"2026-01-02T03:04:05.678901Z","due_day":null,'
    '"ease_factor":"f64:4004000000000000","id":"9007199254740993",'
    '"interval_days":"3","interval_days_raw":"f64:8000000000000000",'
    '"is_buried":false,"is_suspended":true,"lapses":"8",'
    '"last_leech_at":null,"last_leech_lapses":"8",'
    '"last_review_event_id":"99",'
    '"last_reviewed_at":"2026-01-01T01:02:03.000004Z",'
    '"memory_difficulty":"f64:4023800000000000",'
    '"memory_stability":"f64:3fb999999999999a","queue":"learn",'
    '"reps":"9","review_kind":"review","revision":"9007199254740995",'
    '"scheduler_mode":"fsrs","step_index":"1","suspension_reason":null,'
    '"updated_at":"2026-01-02T03:04:05.678901Z","user_id":"7"}'
)
RAW_GOLDEN_SHA256 = "d3cf1627a8c6514c87fa606ca0b0e3e7dd24734b6eed6383523648f658941d15"
STATE_GOLDEN = (
    '{"due_at":"2026-01-02T03:04:05.678901Z","due_day":null,'
    '"ease":"f64:4004000000000000",'
    '"interval_days":"f64:0000000000000000","lapses":"8",'
    '"last_review_at":"2026-01-01T01:02:03.000004Z","leeched":true,'
    '"memory_state":{"difficulty":"f64:4023800000000000",'
    '"stability":"f64:3fb999999999999a"},"reps":"9",'
    '"review_kind":"review","scheduler_mode":"fsrs","step_index":"1",'
    '"suspended":true,"suspension_reason":null,"type":"learning"}'
)
ALGORITHM_GOLDEN_SHA256 = "30c7e1e5372bef50643e73b8d2113d45b83da9b4ceb014d9c454da0d8603048c"
SEMANTIC_GOLDEN_SHA256 = "de8eb920e671770736cd0b76511d0c50b74a603edf795d0d05178491c5647ec5"


def golden_progress(**overrides):
    values = {
        "id": 9_007_199_254_740_993,
        "user_id": 7,
        "card_id": "Card-A",
        "queue": "learn",
        "step_index": 1,
        "due_at": datetime(2026, 1, 2, 3, 4, 5, 678901),
        "due_day": None,
        "interval_days": 3,
        "interval_days_raw": -0.0,
        "is_suspended": True,
        "is_buried": False,
        "buried_until_day": None,
        "review_kind": "review",
        "scheduler_mode": "fsrs",
        "ease_factor": 2.5,
        "memory_stability": 0.1,
        "memory_difficulty": 9.75,
        "suspension_reason": None,
        "last_leech_at": None,
        "last_leech_lapses": 8,
        "last_review_event_id": 99,
        "reps": 9,
        "lapses": 8,
        "last_reviewed_at": datetime(2026, 1, 1, 1, 2, 3, 4),
        "revision": 9_007_199_254_740_995,
        "created_at": datetime(2025, 12, 1),
        "updated_at": datetime(2026, 1, 2, 3, 4, 5, 678901),
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class StudyProgressShadowCodecTests(unittest.TestCase):
    def test_raw_inventory_matches_every_card_progress_column(self):
        self.assertEqual(
            RAW_CARD_PROGRESS_FIELDS,
            tuple(column.name for column in CardProgress.__table__.columns),
        )

    def test_raw_golden_bytes_hash_and_round_trip_are_lossless(self):
        source = golden_progress()
        document = serialize_raw_card_progress(source)

        self.assertEqual(document.encoded.decode("utf-8"), RAW_GOLDEN)
        self.assertEqual(document.digest.hex(), RAW_GOLDEN_SHA256)
        decoded = decode_raw_card_progress(
            document.payload,
            expected_size=document.size,
            expected_hash=document.digest,
        )
        for field_name in RAW_CARD_PROGRESS_FIELDS:
            expected = getattr(source, field_name)
            actual = decoded[field_name]
            if field_name == "interval_days_raw":
                self.assertEqual(math.copysign(1.0, actual), -1.0)
            else:
                self.assertEqual(actual, expected)

    def test_mapper_golden_normalizes_alias_and_semantic_zero_only(self):
        mapped = map_card_progress(
            golden_progress(), card_created_at=datetime(2025, 12, 1)
        )
        self.assertIsInstance(mapped, MappedCardProgress)
        assert isinstance(mapped, MappedCardProgress)
        self.assertEqual(mapped.state.encoded.decode("utf-8"), STATE_GOLDEN)
        self.assertEqual(mapped.algorithm_state_hash.hex(), ALGORITHM_GOLDEN_SHA256)
        self.assertEqual(mapped.semantic_state_hash.hex(), SEMANTIC_GOLDEN_SHA256)
        self.assertEqual(mapped.availability.normalized_queue, "learning")

        canonical = map_card_progress(
            golden_progress(queue="learning", interval_days_raw=0.0),
            card_created_at=datetime(2025, 12, 1),
        )
        assert isinstance(canonical, MappedCardProgress)
        self.assertNotEqual(mapped.raw.digest, canonical.raw.digest)
        self.assertEqual(mapped.state.digest, canonical.state.digest)
        self.assertEqual(mapped.semantic_state_hash, canonical.semantic_state_hash)

    def test_exact_decoder_verifies_identity_size_and_algorithm_hash(self):
        mapped = map_card_progress(
            golden_progress(), card_created_at=datetime(2025, 12, 1)
        )
        assert isinstance(mapped, MappedCardProgress)
        decoded = STATE_DECODERS.decode(
            algorithm_key=ALGORITHM_KEY,
            algorithm_version=ALGORITHM_VERSION,
            state_schema_version=STATE_SCHEMA_VERSION,
            storage_codec=STORAGE_CODEC,
            payload=mapped.state.payload,
            expected_size=mapped.state.size,
            expected_hash=mapped.algorithm_state_hash,
        )
        self.assertEqual(decoded.type, "learning")
        self.assertEqual(decoded.intervalDays, 0.0)
        self.assertTrue(decoded.leeched)

        with self.assertRaisesRegex(StudyProgressCodecError, "digest") as raised:
            STATE_DECODERS.decode(
                algorithm_key=ALGORITHM_KEY,
                algorithm_version=ALGORITHM_VERSION,
                state_schema_version=STATE_SCHEMA_VERSION,
                storage_codec=STORAGE_CODEC,
                payload=mapped.state.payload,
                expected_hash=b"x" * 32,
            )
        self.assertEqual(raised.exception.code, "STATE_HASH_MISMATCH")

    def test_exact_decoder_hash_binds_nonlegacy_algorithm_identity(self):
        identity = ("future-test", "2.0.0", "future-state.v1", "future-json.v1")
        payload = {"test": "state"}
        document = state_document(payload)
        expected_hash = algorithm_state_hash(
            payload,
            algorithm_key=identity[0],
            algorithm_version=identity[1],
            state_schema_version=identity[2],
            storage_codec=identity[3],
        )
        self.assertNotEqual(expected_hash, algorithm_state_hash(payload))
        decoders = StateDecoderRegistry()
        decoders.register(identity, lambda _payload: CardState(type="new"))
        decoded = decoders.decode(
            algorithm_key=identity[0],
            algorithm_version=identity[1],
            state_schema_version=identity[2],
            storage_codec=identity[3],
            payload=payload,
            expected_size=document.size,
            expected_hash=expected_hash,
        )
        self.assertEqual(decoded.type, "new")
        with self.assertRaises(StudyProgressCodecError) as caught:
            decoders.decode(
                algorithm_key=identity[0],
                algorithm_version=identity[1],
                state_schema_version=identity[2],
                storage_codec=identity[3],
                payload=payload,
                expected_hash=algorithm_state_hash(payload),
            )
        self.assertEqual(caught.exception.code, "STATE_HASH_MISMATCH")

    def test_contributor_identity_pointer_and_provenance_are_validated(self):
        source = golden_progress()
        mapped = map_card_progress(source, card_created_at=datetime(2025, 12, 1))
        assert isinstance(mapped, MappedCardProgress)
        evidence = build_contributor_evidence(
            mapped,
            source,
            subject_generation=3,
            pointer_status="VALID",
            history_completeness_code="HISTORY_NATIVE_COMPLETE",
            current_provenance_code="NATIVE_SESSION",
            lineage_vector_hash=b"l" * 32,
        )
        self.assertEqual(evidence.source_progress_id, source.id)
        self.assertEqual(evidence.logical_card_key, b"Card-A")
        self.assertEqual(evidence.card_progress_revision, source.revision)
        with self.assertRaises(StudyProgressCodecError):
            build_contributor_evidence(
                mapped,
                source,
                subject_generation=3,
                pointer_status="GUESSED",
                history_completeness_code="HISTORY_NATIVE_COMPLETE",
                current_provenance_code="NATIVE_SESSION",
                lineage_vector_hash=b"l" * 32,
            )

    def test_unassigned_zero_ease_is_lossless_but_negative_quarantines(self):
        # Anki imports keep factor 0 on ungraduated cards; the scheduler falls
        # back to startingEase, so the codec must carry it without quarantine.
        mapped = map_card_progress(
            golden_progress(queue="learning", ease_factor=0.0),
            card_created_at=datetime(2025, 12, 1),
        )
        self.assertIsInstance(mapped, MappedCardProgress)
        assert isinstance(mapped, MappedCardProgress)
        decoded = STATE_DECODERS.decode(
            algorithm_key=ALGORITHM_KEY,
            algorithm_version=ALGORITHM_VERSION,
            state_schema_version=STATE_SCHEMA_VERSION,
            storage_codec=STORAGE_CODEC,
            payload=mapped.state.payload,
            expected_size=mapped.state.size,
            expected_hash=mapped.algorithm_state_hash,
        )
        self.assertEqual(decoded.ease, 0.0)

        negative = map_card_progress(
            golden_progress(ease_factor=-0.5), card_created_at=datetime(2025, 12, 1)
        )
        self.assertIsInstance(negative, MappingFailure)
        assert isinstance(negative, MappingFailure)
        self.assertEqual(negative.code, "INVALID_STATE_VALUE")

    def test_unknown_queue_partial_memory_and_nonfinite_values_quarantine(self):
        cases = (
            (golden_progress(queue="NEW"), "UNSUPPORTED_QUEUE"),
            (
                golden_progress(memory_stability=1.0, memory_difficulty=None),
                "INCOMPLETE_MEMORY_STATE",
            ),
            (golden_progress(ease_factor=float("nan")), "NON_FINITE_STATE_NUMBER"),
        )
        for source, expected_code in cases:
            with self.subTest(expected_code=expected_code):
                result = map_card_progress(
                    source, card_created_at=datetime(2025, 12, 1)
                )
                self.assertIsInstance(result, MappingFailure)
                assert isinstance(result, MappingFailure)
                self.assertEqual(result.code, expected_code)

        oversized = map_card_progress(
            golden_progress(queue="x" * 17_000),
            card_created_at=datetime(2025, 12, 1),
        )
        assert isinstance(oversized, MappingFailure)
        self.assertEqual(oversized.code, "RAW_PROGRESS_PAYLOAD_TOO_LARGE")

    def test_generic_evidence_codec_uses_the_same_typed_scalar_contract(self):
        document = canonical_typed_document(
            {
                "count": 9_007_199_254_740_993,
                "ratio": -0.0,
                "seen_at": datetime(2026, 9, 13, 1, 2, 3, 4),
                "values": [True, None],
            },
            too_large_code="STATE_PAYLOAD_TOO_LARGE",
        )
        self.assertEqual(
            document.encoded.decode("utf-8"),
            '{"count":"9007199254740993","ratio":"f64:8000000000000000",'
            '"seen_at":"2026-09-13T01:02:03.000004Z","values":[true,null]}',
        )

    def test_identity_capacity_is_measured_in_utf8_bytes(self):
        self.assertEqual(len(encode_identity("界" * 48, max_bytes=144, field_name="key")), 144)
        with self.assertRaises(StudyProgressCodecError):
            encode_identity("界" * 49, max_bytes=144, field_name="key")

    def test_availability_requires_explicit_context_and_preserves_anchors(self):
        mapped = map_card_progress(
            golden_progress(
                queue="review",
                is_suspended=False,
                due_day=10,
                due_at=datetime(2026, 1, 2, 3),
            ),
            card_created_at=datetime(2025, 12, 1),
        )
        assert isinstance(mapped, MappedCardProgress)
        context = AvailabilityContext(
            now_utc=datetime(2026, 1, 2, 12),
            timezone_name="UTC",
            day_boundary_hour_local=4,
            learn_ahead_seconds=1200,
            effective_card_keys=(mapped.availability.card_order_key,),
            comparison_policy_version="phase4-current-v1",
        )
        decision = evaluate_availability(mapped.availability, context)
        self.assertTrue(decision.is_visible)
        self.assertTrue(decision.is_due)

        hidden = replace(mapped.availability, is_buried=True, buried_until_day=None)
        self.assertFalse(evaluate_availability(hidden, context).is_visible)
        with self.assertRaises(StudyProgressCodecError) as raised:
            evaluate_availability(
                mapped.availability,
                replace(context, timezone_name="No/Such_Timezone"),
            )
        self.assertEqual(raised.exception.code, "INVALID_AVAILABILITY_CONTEXT")


if __name__ == "__main__":
    unittest.main()
