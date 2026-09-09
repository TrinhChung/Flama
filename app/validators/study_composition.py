"""Request-boundary validation for Phase 3 composition selection."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .flashcard_input import RequestValidationError


MAX_COMPOSITION_ID_LENGTH = 255


@dataclass(frozen=True)
class StudyCompositionSelectionInput:
    composition_id: str | None
    source: str


def _normalize_id(value: Any, *, field: str) -> str:
    if not isinstance(value, str):
        raise RequestValidationError(
            f"{field} must be a string.",
            field=field,
            code="INVALID_COMPOSITION_ID",
        )
    normalized = value.strip()
    if not normalized or len(normalized) > MAX_COMPOSITION_ID_LENGTH:
        raise RequestValidationError(
            f"{field} must be a non-empty supported identifier.",
            field=field,
            code="INVALID_COMPOSITION_ID",
        )
    return normalized


def validate_study_composition_selection_request(
    payload: dict[str, Any],
) -> StudyCompositionSelectionInput:
    has_canonical = "composition_id" in payload
    has_legacy = "composition_ids" in payload
    if has_canonical and has_legacy:
        raise RequestValidationError(
            "Use composition_id only; composition_ids cannot be combined with it.",
            field="composition_id",
            code="COMPOSITION_SELECTION_CONFLICT",
        )
    if has_canonical:
        return StudyCompositionSelectionInput(
            composition_id=_normalize_id(
                payload.get("composition_id"),
                field="composition_id",
            ),
            source="explicit",
        )
    if has_legacy:
        raw = payload.get("composition_ids")
        if not isinstance(raw, list) or len(raw) != 1:
            raise RequestValidationError(
                "composition_ids must contain exactly one identifier.",
                field="composition_ids",
                code="COMPOSITION_CARDINALITY_INVALID",
            )
        return StudyCompositionSelectionInput(
            composition_id=_normalize_id(raw[0], field="composition_ids[0]"),
            source="legacy_single",
        )
    return StudyCompositionSelectionInput(
        composition_id=None,
        source="omitted",
    )
