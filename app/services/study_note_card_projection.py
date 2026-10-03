"""Project NOTE Algorithm State onto one Card without a CardProgress row.

Pure code: no SQL, no transaction. It is the adapter of ADR P9-03 §2.2/§2.8.
While the legacy projection is still written, ``map_card_progress`` stays the
oracle and ``tests/test_study_note_card_projection.py`` pins both paths to the
same availability and semantic hash.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Mapping

from app.services.anki_scheduler import DeckOptions, _round_review_interval
from app.services.study_progress_contract import (
    NORMALIZED_QUEUES,
    PROJECTION_VERSION,
    STATE_SCHEMA_VERSION,
)
from app.services.study_progress_shadow_codec import (
    StudyProgressCodecError,
    algorithm_state_hash,
    canonical_document,
    decode_datetime,
    decode_integer,
    encode_integer,
    state_document,
)
from app.services.study_progress_shadow_mapper import (
    AvailabilityProjection,
    encode_identity,
)


@dataclass(frozen=True)
class NoteCardBurial:
    """Burial is bound by the semantic hash but is not Algorithm State."""

    is_buried: bool = False
    buried_until_day: int | None = None


@dataclass(frozen=True)
class NoteCardProjection:
    algorithm_state_hash: bytes
    semantic_state_hash: bytes
    availability: AvailabilityProjection


def _burial_anchors(burial: NoteCardBurial) -> tuple[bool, int | None]:
    if not isinstance(burial, NoteCardBurial) or not isinstance(burial.is_buried, bool):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "Burial flag must be a boolean."
        )
    until = burial.buried_until_day
    if until is not None and (isinstance(until, bool) or not isinstance(until, int) or until < 0):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "buried_until_day must be null or non-negative."
        )
    return burial.is_buried, until


@dataclass(frozen=True)
class NoteStateProjection:
    """The Note-level part of a projection: every sibling Card shares it."""

    algorithm_state_hash: bytes
    semantic_state_hash: bytes
    projection_version: str
    normalized_queue: str
    due_at: datetime | None
    due_day: int | None
    is_suspended: bool
    is_buried: bool
    buried_until_day: int | None
    state_schema_version: str


def project_note_state(
    state_payload: Mapping[str, Any],
    *,
    burial: NoteCardBurial,
) -> NoteStateProjection:
    """Availability anchors and semantic hash of one Note state (ADR P10 §2.2).

    Nothing here depends on a Card: siblings differ only in their order key.
    """

    if not isinstance(state_payload, Mapping):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "Algorithm State payload must be an object."
        )
    state = state_document(state_payload)
    payload = state.payload
    queue = payload.get("type")
    if queue not in NORMALIZED_QUEUES:
        raise StudyProgressCodecError(
            "UNSUPPORTED_QUEUE", f"Unsupported state queue {queue!r}."
        )
    suspended = payload.get("suspended")
    if not isinstance(suspended, bool):
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "Suspension flag must be a boolean."
        )
    due_at_token = payload.get("due_at")
    due_day_token = payload.get("due_day")
    due_at = (
        decode_datetime(due_at_token, field_name="due_at")
        if due_at_token is not None
        else None
    )
    due_day = (
        decode_integer(due_day_token, field_name="due_day")
        if due_day_token is not None
        else None
    )
    if due_day is not None and due_day < 0:
        raise StudyProgressCodecError(
            "INVALID_STATE_VALUE", "due_day must be null or non-negative."
        )
    is_buried, buried_until_day = _burial_anchors(burial)
    algorithm_hash = algorithm_state_hash(payload)
    semantic_anchors = {
        "algorithm_state_hash": algorithm_hash.hex(),
        "buried_until_day": (
            encode_integer(buried_until_day, field_name="buried_until_day")
            if buried_until_day is not None
            else None
        ),
        "due_at": due_at_token,
        "due_day": due_day_token,
        "is_buried": is_buried,
        "is_suspended": suspended,
        "normalized_queue": queue,
    }
    semantic_hash = canonical_document(
        semantic_anchors, too_large_code="STATE_PAYLOAD_TOO_LARGE"
    ).digest
    return NoteStateProjection(
        algorithm_state_hash=algorithm_hash,
        semantic_state_hash=semantic_hash,
        projection_version=PROJECTION_VERSION,
        normalized_queue=queue,
        due_at=due_at,
        due_day=due_day,
        is_suspended=suspended,
        is_buried=is_buried,
        buried_until_day=buried_until_day,
        state_schema_version=STATE_SCHEMA_VERSION,
    )


def project_note_card(
    state_payload: Mapping[str, Any],
    *,
    burial: NoteCardBurial,
    card_id: str,
    card_created_at: datetime,
) -> NoteCardProjection:
    """Return what ``map_card_progress`` derives for this Card, from state alone."""

    note = project_note_state(state_payload, burial=burial)
    encoded_card_key = encode_identity(card_id, max_bytes=144, field_name="card_order_key")
    if not isinstance(card_created_at, datetime):
        raise StudyProgressCodecError(
            "MISSING_CARD_CREATED_AT", "A projected Card requires Card.created_at."
        )
    return NoteCardProjection(
        algorithm_state_hash=note.algorithm_state_hash,
        semantic_state_hash=note.semantic_state_hash,
        availability=AvailabilityProjection(
            projection_version=note.projection_version,
            normalized_queue=note.normalized_queue,
            due_at=note.due_at,
            due_day=note.due_day,
            is_suspended=note.is_suspended,
            is_buried=note.is_buried,
            buried_until_day=note.buried_until_day,
            card_created_at=card_created_at,
            card_order_key=encoded_card_key,
            state_schema_version=note.state_schema_version,
            semantic_state_hash=note.semantic_state_hash,
        ),
    )


def rounded_interval_days(
    *,
    queue: str,
    interval_days: float,
    deck_options: DeckOptions | None = None,
) -> int:
    """The whole-day interval the legacy projection stores beside the raw one.

    Writers pass the Deck Options of the answer. Readers pass none: the
    scheduler clamps a review interval to those options before storing it,
    so rounding half up gives the same day count (ADR P9-03 §2.8).
    """

    if queue == "review":
        if deck_options is not None:
            return _round_review_interval(float(interval_days), deck_options)
        return int(float(interval_days) + 0.5)
    return int(round(float(interval_days)))
