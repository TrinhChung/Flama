"""NOTE write precision while legacy MySQL FLOAT projections are mandatory.

This is a persistence profile, not a change to the versioned scheduler. Apply it
to a newly evaluated transition BEFORE hashing/event construction. Never use it
to rewrite an existing authority document or a historical raw baseline.

PyMySQL uses MySQL's text protocol: FLOAT is stored as binary32, then returned
with FLT_DIG (6) significant decimal digits. Checking binary32 equality alone
both rejects ordinary values such as 2.35 and accepts values the reader rounds.
"""

from __future__ import annotations

from dataclasses import replace
import math
import struct

from app.services.anki_scheduler import CardState


NOTE_STORAGE_PROFILE = "note-mysql-float-text.v1"


class StudyStoragePrecisionError(ValueError):
    code = "UNPROJECTABLE_LEGACY_FLOAT"


def legacy_float_round_trip(value: float) -> float:
    """Model a finite MySQL FLOAT write/read through the supported text driver."""

    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise StudyStoragePrecisionError("Legacy FLOAT requires a finite number.")
    try:
        number = float(value)
        stored = struct.unpack(">f", struct.pack(">f", number))[0]
    except (OverflowError, struct.error) as exc:
        raise StudyStoragePrecisionError("Value exceeds legacy MySQL FLOAT range.") from exc
    if not math.isfinite(number) or not math.isfinite(stored):
        raise StudyStoragePrecisionError("Legacy FLOAT requires a finite number.")
    # Python's general format uses round-to-nearest, ties-to-even, like dtoa.
    # Keep signed zero here; canonical semantic state already normalizes zero.
    return float(format(stored, ".6g"))


def normalize_note_transition_state(state: CardState) -> CardState:
    """Return a fresh, storage-representable state; do not mutate its input."""

    memory = state.memoryState
    return replace(
        state,
        intervalDays=legacy_float_round_trip(state.intervalDays),
        ease=legacy_float_round_trip(state.ease),
        memoryState=None if memory is None else replace(
            memory,
            stability=legacy_float_round_trip(memory.stability),
            difficulty=legacy_float_round_trip(memory.difficulty),
        ),
    )
