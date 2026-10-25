"""Bounded inputs for progressive Browse deck metadata reads."""

from app.validators.flashcard_input import RequestValidationError


MAX_SUMMARY_DECKS = 50


def validate_structure_only(value) -> bool:
    normalized = str(value or "0").strip().lower()
    if normalized in {"0", "false", "no"}:
        return False
    if normalized in {"1", "true", "yes"}:
        return True
    raise RequestValidationError("Invalid structure_only.", field="structure_only")


def validate_deck_summary_ids(value) -> tuple[int, ...]:
    raw = str(value or "").strip()
    parts = raw.split(",")
    if not raw or len(raw) > 1100 or len(parts) > MAX_SUMMARY_DECKS:
        raise RequestValidationError("Provide between 1 and 50 deck IDs.", field="deck_ids")
    result = []
    for part in parts:
        part = part.strip()
        if not part.isascii() or not part.isdecimal() or not 0 < int(part) <= 2147483647:
            raise RequestValidationError("deck_ids must contain positive deck IDs.", field="deck_ids")
        deck_id = int(part)
        if deck_id not in result:
            result.append(deck_id)
    return tuple(result)
