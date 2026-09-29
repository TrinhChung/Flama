"""Pure, fail-closed comparison for a prospective Note-to-Card projection.

This is an inert P5-03 diagnostic. It neither builds a legacy projection nor
selects study authority. The caller must supply independent expected raw
digests for every sibling Card, including presentation-specific metadata.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping, Sequence

from app.services.study_progress_shadow_codec import (
    STATE_DECODERS,
    StudyProgressCodecError,
    algorithm_state_hash,
    state_document,
)
from app.services.study_progress_shadow_mapper import (
    MappedCardProgress,
    map_card_progress,
)


class ProjectionComparisonError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class ProjectionCandidate:
    progress: Any
    card_created_at: datetime


@dataclass(frozen=True)
class ProjectionComparison:
    card_ids: tuple[str, ...]
    algorithm_state_hash: bytes
    semantic_state_hash: bytes
    raw_digest_by_card: tuple[tuple[str, bytes], ...]


def compare_note_legacy_projection(
    *,
    expected_learner_user_id: int,
    algorithm_key: str,
    algorithm_version: str,
    state_schema_version: str,
    storage_codec: str,
    state_payload: Mapping[str, Any],
    expected_state_payload_size: int,
    expected_algorithm_state_hash: bytes,
    expected_semantic_state_hash: bytes,
    expected_raw_digest_by_card: Mapping[str, bytes],
    candidates: Sequence[ProjectionCandidate],
) -> ProjectionComparison:
    """Check exact state, semantic anchors and raw bytes for all active siblings.

    A state-only match is insufficient: the Phase 4 Algorithm State normalizes
    legacy queue aliases and signed zero, and omits Card identity, event pointer
    and timestamps. Raw digests must come from an independent, lossless encoder.
    """

    if (
        isinstance(expected_learner_user_id, bool)
        or not isinstance(expected_learner_user_id, int)
        or expected_learner_user_id <= 0
    ):
        raise ProjectionComparisonError(
            "INVALID_EXPECTATION", "Expected learner ID must be positive."
        )
    if (
        isinstance(expected_state_payload_size, bool)
        or not isinstance(expected_state_payload_size, int)
        or expected_state_payload_size < 0
    ):
        raise ProjectionComparisonError(
            "INVALID_EXPECTATION", "Expected state payload size is invalid."
        )
    if not isinstance(expected_algorithm_state_hash, bytes) or len(
        expected_algorithm_state_hash
    ) != 32:
        raise ProjectionComparisonError(
            "INVALID_EXPECTATION", "Expected Algorithm hash must contain 32 bytes."
        )
    if not isinstance(expected_semantic_state_hash, bytes) or len(
        expected_semantic_state_hash
    ) != 32:
        raise ProjectionComparisonError(
            "INVALID_EXPECTATION", "Expected semantic hash must contain 32 bytes."
        )
    expected_ids = set(expected_raw_digest_by_card)
    if not expected_ids or any(
        not isinstance(card_id, str) or not card_id for card_id in expected_ids
    ):
        raise ProjectionComparisonError(
            "INVALID_EXPECTATION", "At least one non-empty Card ID is required."
        )
    if any(
        not isinstance(digest, bytes) or len(digest) != 32
        for digest in expected_raw_digest_by_card.values()
    ):
        raise ProjectionComparisonError(
            "INVALID_EXPECTATION", "Every expected raw digest must contain 32 bytes."
        )

    try:
        expected_state = state_document(state_payload)
        if expected_state.size != expected_state_payload_size:
            raise StudyProgressCodecError(
                "STATE_HASH_MISMATCH", "Stored Algorithm State size does not match."
            )
        identity = (algorithm_key, algorithm_version, state_schema_version, storage_codec)
        # An unknown identity is reported as such before its hash is checked.
        if not STATE_DECODERS.has_decoder(identity):
            raise StudyProgressCodecError(
                "STATE_DECODER_UNAVAILABLE", f"No decoder is registered for {identity!r}."
            )
        expected_algorithm_hash = algorithm_state_hash(
            expected_state.payload,
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
            state_schema_version=state_schema_version,
            storage_codec=storage_codec,
        )
        if expected_algorithm_hash != expected_algorithm_state_hash:
            raise StudyProgressCodecError(
                "STATE_HASH_MISMATCH", "Stored Algorithm State hash does not match."
            )
        STATE_DECODERS.decode(
            algorithm_key=algorithm_key,
            algorithm_version=algorithm_version,
            state_schema_version=state_schema_version,
            storage_codec=storage_codec,
            payload=expected_state.payload,
            expected_size=expected_state_payload_size,
            expected_hash=expected_algorithm_state_hash,
        )
    except StudyProgressCodecError as exc:
        raise ProjectionComparisonError(exc.code, str(exc)) from exc

    seen: dict[str, MappedCardProgress] = {}
    for candidate in candidates:
        card_id = getattr(candidate.progress, "card_id", None)
        if not isinstance(card_id, str) or not card_id:
            raise ProjectionComparisonError(
                "INVALID_CARD_IDENTITY", "Candidate has no Card ID."
            )
        if card_id in seen:
            raise ProjectionComparisonError(
                "DUPLICATE_SIBLING", f"Duplicate Card candidate: {card_id}."
            )
        if card_id not in expected_ids:
            raise ProjectionComparisonError(
                "UNEXPECTED_SIBLING", f"Unexpected Card candidate: {card_id}."
            )
        if getattr(candidate.progress, "user_id", None) != expected_learner_user_id:
            raise ProjectionComparisonError(
                "WRONG_LEARNER", f"Card {card_id} belongs to another learner."
            )
        mapped = map_card_progress(
            candidate.progress,
            card_created_at=candidate.card_created_at,
            card_order_key=card_id,
        )
        if not isinstance(mapped, MappedCardProgress):
            raise ProjectionComparisonError(
                "UNMAPPABLE_SIBLING", f"Card {card_id} cannot map: {mapped.code}."
            )
        if mapped.state.digest != expected_state.digest:
            raise ProjectionComparisonError(
                "STATE_MISMATCH", f"Card {card_id} differs from Note Algorithm State."
            )
        if mapped.semantic_state_hash != expected_semantic_state_hash:
            raise ProjectionComparisonError(
                "SEMANTIC_MISMATCH", f"Card {card_id} differs in semantic anchors."
            )
        if mapped.raw.digest != expected_raw_digest_by_card[card_id]:
            raise ProjectionComparisonError(
                "RAW_MISMATCH", f"Card {card_id} lost exact legacy raw values."
            )
        seen[card_id] = mapped

    missing = expected_ids - set(seen)
    if missing:
        raise ProjectionComparisonError(
            "MISSING_SIBLING", f"Missing {len(missing)} expected Card projection(s)."
        )
    ordered_ids = tuple(sorted(seen))
    return ProjectionComparison(
        card_ids=ordered_ids,
        algorithm_state_hash=expected_algorithm_hash,
        semantic_state_hash=expected_semantic_state_hash,
        raw_digest_by_card=tuple(
            (card_id, seen[card_id].raw.digest) for card_id in ordered_ids
        ),
    )
