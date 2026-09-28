"""Bounded NOTE/v4 async envelopes; no database access or state mutation."""

from dataclasses import dataclass
import json
from typing import Any


# study_session_batches.payload_json is MySQL TEXT, not the 5 MiB HTTP limit.
MAX_NOTE_BATCH_BYTES = 60 * 1024


class NoteBatchPayloadError(ValueError):
    def __init__(self, code: str, message: str, *, status: int = 422):
        super().__init__(message)
        self.code, self.status = code, status


@dataclass(frozen=True)
class NoteBatchEnvelope:
    batch_id: str
    sequence: int
    reason: str
    is_final: bool
    events: list[dict[str, Any]]
    encoded: str


def validate_note_batch_envelope(payload: Any) -> NoteBatchEnvelope:
    if not isinstance(payload, dict):
        raise NoteBatchPayloadError("INVALID_BATCH", "Batch payload must be an object.", status=400)
    schema = payload.get("schema_version")
    if schema not in ("study-batch.v3", "study-commit.v3"):
        raise NoteBatchPayloadError("UNSUPPORTED_BATCH_SCHEMA", "NOTE batches require a v4-compatible envelope.")
    batch_id = payload.get("batch_id") or payload.get("commit_id")
    if not isinstance(batch_id, str) or not 1 <= len(batch_id) <= 64 or batch_id != batch_id.strip():
        raise NoteBatchPayloadError("INVALID_BATCH_ID", "A canonical batch_id or commit_id is required.")
    if any(payload.get(key) is not None and payload[key] != batch_id for key in ("batch_id", "commit_id")):
        raise NoteBatchPayloadError("INVALID_BATCH_ID", "Batch and commit identifiers must agree.")
    sequence = payload.get("batch_sequence", 1 if schema == "study-commit.v3" else None)
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence < 1:
        raise NoteBatchPayloadError("INVALID_BATCH_SEQUENCE", "batch_sequence must be a positive integer.")
    reason = str(payload.get("commit_reason") or ("manual_exit" if schema == "study-commit.v3" else "rollover")).strip().lower()
    if reason not in {"rollover", "auto_finish", "manual_exit", "page_exit"}:
        raise NoteBatchPayloadError("INVALID_COMMIT_REASON", "Unsupported batch commit reason.")
    if not isinstance(payload.get("is_final", False), bool):
        raise NoteBatchPayloadError("INVALID_BATCH_FINAL", "is_final must be a boolean.")
    events = payload.get("events")
    if not isinstance(events, list) or any(not isinstance(event, dict) for event in events):
        raise NoteBatchPayloadError("INVALID_EVENTS", "events must be an array of objects.")
    if payload.get("final_states") is not None and payload["final_states"] != []:
        raise NoteBatchPayloadError("INVALID_FINAL_STATES", "NOTE final state is derived only from its action log.")
    try:
        encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), sort_keys=True, allow_nan=False)
        size = len(encoded.encode("utf-8"))
    except (TypeError, ValueError, UnicodeError, RecursionError) as exc:
        raise NoteBatchPayloadError("INVALID_BATCH", "Batch must contain finite, UTF-8 JSON values.") from exc
    if size > MAX_NOTE_BATCH_BYTES:
        raise NoteBatchPayloadError("BATCH_TOO_LARGE", "NOTE batch exceeds its durable payload byte limit.", status=413)
    return NoteBatchEnvelope(
        batch_id=batch_id, sequence=sequence, reason=reason,
        is_final=payload.get("is_final", False) or reason != "rollover",
        events=events, encoded=encoded,
    )
