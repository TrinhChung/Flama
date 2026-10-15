"""Input contracts for explicit Note deletion in Browse."""

from app.validators.flashcard_input import RequestValidationError


def validate_note_delete_payload(payload) -> list[str]:
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be a JSON object.")
    ids = payload.get("note_ids")
    if not isinstance(ids, list) or any(
        not isinstance(value, str) or not value.strip() or len(value.strip()) > 36
        for value in ids
    ):
        raise RequestValidationError("note_ids must be a list of Note IDs.", field="note_ids")
    return sorted({value.strip() for value in ids})
