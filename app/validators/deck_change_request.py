"""Validation helpers for deck change request payloads."""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

from .flashcard_input import RequestValidationError, sanitize_plain_text


MAX_CHANGE_REQUEST_TITLE_LENGTH = 255
MAX_CHANGE_REQUEST_DESCRIPTION_LENGTH = 5_000
RESOLUTION_MODES = {"keep_mine", "keep_upstream", "manual"}


@dataclass(frozen=True)
class ChangeRequestDraftInput:
    title: str
    description: str


@dataclass(frozen=True)
class ChangeRequestSendInput:
    title: str
    description: str
    expected_overlay_fingerprint: str


@dataclass(frozen=True)
class ChangeRequestConflictResolutionInput:
    resolution_mode: str
    resolved_value: Any


@dataclass(frozen=True)
class ChangeRequestReviewInput:
    review_comment: str


def _payload_dict(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {}
    if not isinstance(payload, dict):
        raise RequestValidationError("Payload must be an object.", field="body")
    return payload


def _normalize_optional_text(raw_value: Any, *, field_name: str, max_length: int) -> str:
    text = "" if raw_value is None else str(raw_value)
    normalized = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not normalized:
        return ""
    return sanitize_plain_text(normalized, field_name=field_name, max_length=max_length)


def validate_change_request_draft_request(payload: dict[str, Any] | None) -> ChangeRequestDraftInput:
    body = _payload_dict(payload)
    unknown_keys = sorted(key for key in body if key not in {"title", "description"})
    if unknown_keys:
        raise RequestValidationError(
            f"Unknown fields: {', '.join(unknown_keys)}",
            field=unknown_keys[0],
        )
    return ChangeRequestDraftInput(
        title=_normalize_optional_text(
            body.get("title"),
            field_name="title",
            max_length=MAX_CHANGE_REQUEST_TITLE_LENGTH,
        ),
        description=_normalize_optional_text(
            body.get("description"),
            field_name="description",
            max_length=MAX_CHANGE_REQUEST_DESCRIPTION_LENGTH,
        ),
    )


def validate_change_request_send_request(payload: dict[str, Any] | None) -> ChangeRequestSendInput:
    body = dict(_payload_dict(payload))
    fingerprint = body.pop("expected_overlay_fingerprint", None)
    if not isinstance(fingerprint, str) or not re.fullmatch(r"[a-f0-9]{64}", fingerprint):
        raise RequestValidationError(
            "Reload the contribution preview before sending.",
            field="expected_overlay_fingerprint",
        )
    draft = validate_change_request_draft_request(body)
    return ChangeRequestSendInput(draft.title, draft.description, fingerprint)


def validate_change_request_conflict_resolution_request(
    payload: dict[str, Any] | None,
) -> ChangeRequestConflictResolutionInput:
    body = _payload_dict(payload)
    unknown_keys = sorted(key for key in body if key not in {"resolution_mode", "resolved_value"})
    if unknown_keys:
        raise RequestValidationError(
            f"Unknown fields: {', '.join(unknown_keys)}",
            field=unknown_keys[0],
        )
    resolution_mode = str(body.get("resolution_mode") or "").strip().lower()
    if resolution_mode not in RESOLUTION_MODES:
        raise RequestValidationError(
            "resolution_mode must be keep_mine, keep_upstream, or manual.",
            field="resolution_mode",
        )
    resolved_value = body.get("resolved_value")
    if resolution_mode == "manual" and "resolved_value" not in body:
        raise RequestValidationError(
            "resolved_value is required when resolution_mode is manual.",
            field="resolved_value",
        )
    return ChangeRequestConflictResolutionInput(
        resolution_mode=resolution_mode,
        resolved_value=resolved_value,
    )


def validate_change_request_review_request(
    payload: dict[str, Any] | None,
    *,
    require_reason: bool,
) -> ChangeRequestReviewInput:
    body = _payload_dict(payload)
    unknown_keys = sorted(key for key in body if key not in {"review_comment", "reason"})
    if unknown_keys:
        raise RequestValidationError(
            f"Unknown fields: {', '.join(unknown_keys)}",
            field=unknown_keys[0],
        )
    raw_comment = body.get("review_comment")
    if raw_comment in (None, ""):
        raw_comment = body.get("reason")
    review_comment = _normalize_optional_text(
        raw_comment,
        field_name="review_comment",
        max_length=MAX_CHANGE_REQUEST_DESCRIPTION_LENGTH,
    )
    if require_reason and not review_comment:
        raise RequestValidationError(
            "review_comment is required.",
            field="review_comment",
        )
    return ChangeRequestReviewInput(review_comment=review_comment)
