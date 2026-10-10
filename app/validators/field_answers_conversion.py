"""Request validation for converting a NoteType field to or from ``answers``.

The frontend splits values and sends the final text of every Note; the server
only checks the request shape and that ``answers`` values are one clean answer
per line. It never splits or rewrites answers itself.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from models.field_types import ANSWERS_FIELD_TYPE

RESTORABLE_FIELD_TYPES = ("text", "richtext", "markdown")
MAX_CONVERSION_NOTES = 20_000
MAX_ANSWERS_VALUE_LENGTH = 5_000
_HTML_TAG_RE = re.compile(r"<\s*/?\s*[a-zA-Z!][^>]*>")


class AnswersConversionError(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 400, details: dict[str, Any] | None = None) -> None:
        super().__init__(message)
        self.code = code
        self.status = status
        self.details = details or {}


@dataclass(frozen=True)
class ConversionNote:
    note_id: str
    expected: str
    value: str


@dataclass(frozen=True)
class ConversionRequest:
    target_type: str
    expected_field_type: str
    notes: tuple[ConversionNote, ...]

    @property
    def to_answers(self) -> bool:
        return self.target_type == ANSWERS_FIELD_TYPE


def parse_conversion_request(payload: Any) -> ConversionRequest:
    if not isinstance(payload, dict) or set(payload) - {"target_type", "expected_field_type", "notes"}:
        raise AnswersConversionError("VALIDATION_ERROR", "Request body contains unsupported properties.")
    allowed = (*RESTORABLE_FIELD_TYPES, ANSWERS_FIELD_TYPE)
    target_type = payload.get("target_type")
    expected_type = payload.get("expected_field_type")
    if target_type not in allowed or expected_type not in allowed:
        raise AnswersConversionError("VALIDATION_ERROR", "target_type and expected_field_type must be text-like or answers.")
    if (target_type == ANSWERS_FIELD_TYPE) == (expected_type == ANSWERS_FIELD_TYPE):
        raise AnswersConversionError(
            "VALIDATION_ERROR",
            "A conversion goes from a text-like type to answers, or from answers back to a text-like type.",
        )
    raw_notes = payload.get("notes")
    if not isinstance(raw_notes, list) or len(raw_notes) > MAX_CONVERSION_NOTES:
        raise AnswersConversionError("VALIDATION_ERROR", f"notes must be an array of at most {MAX_CONVERSION_NOTES} items.")
    notes: list[ConversionNote] = []
    seen: set[str] = set()
    for item in raw_notes:
        if (
            not isinstance(item, dict)
            or set(item) != {"note_id", "expected", "value"}
            or not isinstance(item["note_id"], str)
            or not item["note_id"]
            or not isinstance(item["expected"], str)
            or not isinstance(item["value"], str)
        ):
            raise AnswersConversionError("VALIDATION_ERROR", "Each note needs a note_id, its expected current value and the new value.")
        if item["note_id"] in seen:
            raise AnswersConversionError("VALIDATION_ERROR", "A note appears more than once.")
        seen.add(item["note_id"])
        notes.append(ConversionNote(note_id=item["note_id"], expected=item["expected"], value=item["value"]))
    return ConversionRequest(target_type=target_type, expected_field_type=expected_type, notes=tuple(notes))


def answers_value_problem(value: str) -> str | None:
    """Why ``value`` is not one clean answer per line, or None when it is."""
    if value == "":
        return None
    if len(value) > MAX_ANSWERS_VALUE_LENGTH:
        return "too_long"
    if "\r" in value or _HTML_TAG_RE.search(value):
        return "not_plain_lines"
    seen: set[str] = set()
    for line in value.split("\n"):
        if not line or line != line.strip():
            return "not_plain_lines"
        key = line.lower()  # same rule as the frontend normalizer (toLowerCase)
        if key in seen:
            return "duplicate_answer"
        seen.add(key)
    return None
