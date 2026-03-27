from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

from .flashcard_input import RequestValidationError, sanitize_plain_text

MAX_PAYOUT_BATCH_REFERENCE_LENGTH = 96
MAX_PAYOUT_ITEM_REFERENCE_LENGTH = 96
MAX_PAYOUT_DESCRIPTION_LENGTH = 255
MAX_PAYOUT_CATEGORY_LENGTH = 64
MAX_PAYOUT_CATEGORY_COUNT = 10
MAX_PAYOUT_ITEMS = 100

_REFERENCE_SANITIZE_RE = re.compile(r"[^a-z0-9._:-]+")
_WHITESPACE_RE = re.compile(r"\s+")
_BIN_RE = re.compile(r"^\d{6}$")
_ACCOUNT_NUMBER_RE = re.compile(r"^\d{6,30}$")


@dataclass(frozen=True)
class ValidatedPayoutBatchItemInput:
    reference_id: str
    amount: int
    description: str
    to_bin: str
    to_account_number: str


@dataclass(frozen=True)
class ValidatedCreatePayoutBatchInput:
    reference_id: str
    validate_destination: bool
    category: list[str]
    payouts: list[ValidatedPayoutBatchItemInput]
    allow_duplicate: bool


def validate_create_payout_batch_request(payload: dict[str, Any] | None) -> ValidatedCreatePayoutBatchInput:
    body = _require_dict(payload, field_name="body")
    _reject_unknown_keys(
        body,
        allowed_keys={"reference_id", "category", "validate_destination", "payouts", "allow_duplicate"},
    )

    reference_id = _sanitize_reference_id(
        body.get("reference_id"),
        field_name="reference_id",
        max_length=MAX_PAYOUT_BATCH_REFERENCE_LENGTH,
    )
    validate_destination = _parse_bool(body.get("validate_destination"), field_name="validate_destination", default=False)
    allow_duplicate = _parse_bool(body.get("allow_duplicate"), field_name="allow_duplicate", default=False)
    category = _validate_category_list(body.get("category"))
    payouts = _validate_payout_items(body.get("payouts"))

    return ValidatedCreatePayoutBatchInput(
        reference_id=reference_id,
        validate_destination=validate_destination,
        category=category,
        payouts=payouts,
        allow_duplicate=allow_duplicate,
    )


def _require_dict(value: Any, *, field_name: str) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise RequestValidationError("Payload must be a JSON object.", field=field_name)
    return value


def _reject_unknown_keys(payload: dict[str, Any], *, allowed_keys: set[str]) -> None:
    unknown_keys = sorted(key for key in payload if key not in allowed_keys)
    if unknown_keys:
        raise RequestValidationError(
            f"Unknown fields: {', '.join(unknown_keys)}",
            field=unknown_keys[0],
        )


def _sanitize_reference_id(raw_value: Any, *, field_name: str, max_length: int) -> str:
    value = sanitize_plain_text(raw_value, field_name=field_name, max_length=max_length)
    value = _WHITESPACE_RE.sub("-", value.strip().lower())
    value = _REFERENCE_SANITIZE_RE.sub("-", value).strip("._:-")
    value = re.sub(r"-{2,}", "-", value)
    if not value:
        raise RequestValidationError(f"{field_name} is required.", field=field_name)
    if len(value) > max_length:
        value = value[:max_length].rstrip("._:-")
    if not value:
        raise RequestValidationError(f"{field_name} is invalid.", field=field_name)
    return value


def _parse_bool(raw_value: Any, *, field_name: str, default: bool) -> bool:
    if raw_value is None:
        return default
    if isinstance(raw_value, bool):
        return raw_value
    token = str(raw_value).strip().lower()
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    raise RequestValidationError(f"{field_name} must be a boolean-like value.", field=field_name)


def _validate_category_list(raw_value: Any) -> list[str]:
    if raw_value in (None, ""):
        return []
    if not isinstance(raw_value, list):
        raise RequestValidationError("category must be an array of strings.", field="category")
    if len(raw_value) > MAX_PAYOUT_CATEGORY_COUNT:
        raise RequestValidationError(
            f"category must not contain more than {MAX_PAYOUT_CATEGORY_COUNT} values.",
            field="category",
        )

    normalized: list[str] = []
    seen: set[str] = set()
    for index, item in enumerate(raw_value):
        field_name = f"category[{index}]"
        value = sanitize_plain_text(item, field_name=field_name, max_length=MAX_PAYOUT_CATEGORY_LENGTH).strip().lower()
        if not value:
            raise RequestValidationError("category values must be non-empty strings.", field=field_name)
        if value in seen:
            continue
        normalized.append(value)
        seen.add(value)
    return normalized


def _validate_payout_items(raw_value: Any) -> list[ValidatedPayoutBatchItemInput]:
    if not isinstance(raw_value, list):
        raise RequestValidationError("payouts must be an array.", field="payouts")
    if not raw_value:
        raise RequestValidationError("payouts must not be empty.", field="payouts")
    if len(raw_value) > MAX_PAYOUT_ITEMS:
        raise RequestValidationError(
            f"payouts must not contain more than {MAX_PAYOUT_ITEMS} items.",
            field="payouts",
        )

    validated: list[ValidatedPayoutBatchItemInput] = []
    seen_reference_ids: set[str] = set()
    for index, item in enumerate(raw_value):
        field_prefix = f"payouts[{index}]"
        row = _require_dict(item, field_name=field_prefix)
        _reject_unknown_keys(
            row,
            allowed_keys={"reference_id", "amount", "description", "to_bin", "to_account_number"},
        )

        reference_id = _sanitize_reference_id(
            row.get("reference_id"),
            field_name=f"{field_prefix}.reference_id",
            max_length=MAX_PAYOUT_ITEM_REFERENCE_LENGTH,
        )
        if reference_id in seen_reference_ids:
            raise RequestValidationError(
                "payout item reference_id values must be unique within the batch.",
                field=f"{field_prefix}.reference_id",
            )
        seen_reference_ids.add(reference_id)

        amount = _validate_amount(row.get("amount"), field_name=f"{field_prefix}.amount")
        description = sanitize_plain_text(
            row.get("description"),
            field_name=f"{field_prefix}.description",
            max_length=MAX_PAYOUT_DESCRIPTION_LENGTH,
        ).strip()
        if not description:
            raise RequestValidationError("description is required.", field=f"{field_prefix}.description")

        to_bin = re.sub(r"\s+", "", str(row.get("to_bin") or "").strip())
        if not _BIN_RE.fullmatch(to_bin):
            raise RequestValidationError(
                "to_bin must be a 6-digit bank BIN.",
                field=f"{field_prefix}.to_bin",
            )

        to_account_number = re.sub(r"[\s-]+", "", str(row.get("to_account_number") or "").strip())
        if not _ACCOUNT_NUMBER_RE.fullmatch(to_account_number):
            raise RequestValidationError(
                "to_account_number must contain 6 to 30 digits.",
                field=f"{field_prefix}.to_account_number",
            )

        validated.append(
            ValidatedPayoutBatchItemInput(
                reference_id=reference_id,
                amount=amount,
                description=description,
                to_bin=to_bin,
                to_account_number=to_account_number,
            )
        )

    return validated


def _validate_amount(raw_value: Any, *, field_name: str) -> int:
    try:
        amount = int(raw_value)
    except (TypeError, ValueError):
        raise RequestValidationError("amount must be a positive integer.", field=field_name) from None
    if amount <= 0:
        raise RequestValidationError("amount must be a positive integer.", field=field_name)
    return amount
