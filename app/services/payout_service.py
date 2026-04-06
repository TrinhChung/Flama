from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

try:
    from payos import APIError
    from payos.types import Payout, PayoutBatchItem as PayOSPayoutBatchItem, PayoutBatchRequest

    _PAYOS_SDK_AVAILABLE = True
except ModuleNotFoundError:
    class APIError(Exception):
        def __init__(
            self,
            message: str = "",
            *,
            status_code: int = 502,
            error_code: str | None = None,
            error_desc: str | None = None,
            response: Any | None = None,
        ) -> None:
            super().__init__(message)
            self.status_code = status_code
            self.error_code = error_code
            self.error_desc = error_desc
            self.response = response

    Payout = Any  # type: ignore[misc,assignment]
    PayOSPayoutBatchItem = Any  # type: ignore[misc,assignment]
    PayoutBatchRequest = Any  # type: ignore[misc,assignment]
    _PAYOS_SDK_AVAILABLE = False
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from app.repositories import payout_repository
from app.services import payos_client
from app.validators.payout_input import ValidatedCreatePayoutBatchInput, validate_create_payout_batch_request
from models import db
from models.audit_log import AuditLog
from models.payout_batch import PayoutBatch
from models.payout_batch_item import PayoutBatchItem

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class CreatePayoutBatchResult:
    batch: PayoutBatch
    created: bool
    duplicate_reused: bool


class PayoutServiceError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        status: int,
        batch_id: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status = int(status)
        self.batch_id = batch_id


def create_payout_batch(*, actor_user_id: int, raw_payload: dict[str, Any] | None) -> CreatePayoutBatchResult:
    validated = validate_create_payout_batch_request(raw_payload)
    request_fingerprint = _build_request_fingerprint(validated)
    reference_id = _build_batch_reference_id(
        actor_user_id=actor_user_id,
        reference_seed=validated.reference_id,
        allow_duplicate=validated.allow_duplicate,
    )
    payout_request, request_payload, item_rows = _build_provider_request_payload(
        batch_reference_id=reference_id,
        validated=validated,
    )

    existing_batch = payout_repository.get_batch_by_reference_id(reference_id)
    if existing_batch is not None and not validated.allow_duplicate:
        if existing_batch.request_fingerprint != request_fingerprint:
            raise PayoutServiceError(
                "reference_id has already been used for a different payout batch.",
                code="PAYOUT_REFERENCE_CONFLICT",
                status=409,
                batch_id=existing_batch.id,
            )
        logger.info(
            "payos_payout_reuse internal_id=%s reference_id=%s item_count=%s",
            existing_batch.id,
            existing_batch.reference_id,
            existing_batch.item_count,
        )
        return CreatePayoutBatchResult(batch=existing_batch, created=False, duplicate_reused=True)

    try:
        batch = payout_repository.create_batch(
            reference_id=reference_id,
            client_reference_key=validated.reference_id,
            request_fingerprint=request_fingerprint,
            validate_destination=validated.validate_destination,
            category_json=_json_dumps(validated.category),
            request_payload_json=_json_dumps(request_payload),
            created_by_admin_id=actor_user_id,
            items=item_rows,
        )
        _append_audit(
            actor_user_id=actor_user_id,
            action="payos.payout_batch.create_pending",
            payload={
                "batch_id": batch.id,
                "reference_id": batch.reference_id,
                "item_count": batch.item_count,
            },
        )
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        existing_batch = payout_repository.get_batch_by_reference_id(reference_id)
        if existing_batch is not None and not validated.allow_duplicate:
            if existing_batch.request_fingerprint != request_fingerprint:
                raise PayoutServiceError(
                    "reference_id has already been used for a different payout batch.",
                    code="PAYOUT_REFERENCE_CONFLICT",
                    status=409,
                    batch_id=existing_batch.id,
                ) from None
            return CreatePayoutBatchResult(batch=existing_batch, created=False, duplicate_reused=True)
        raise PayoutServiceError(
            "Unable to persist payout batch.",
            code="DB_ERROR",
            status=500,
        ) from None
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise PayoutServiceError(
            "Unable to persist payout batch.",
            code="DB_ERROR",
            status=500,
        ) from exc

    logger.info(
        "payos_payout_submit_start internal_id=%s reference_id=%s item_count=%s",
        batch.id,
        batch.reference_id,
        batch.item_count,
    )

    try:
        provider_response = payos_client.create_payout_batch(
            batch_data=payout_request,
            idempotency_key=batch.reference_id,
        )
    except payos_client.PayOSConfigurationError as exc:
        _mark_batch_failed(
            batch_id=batch.id,
            actor_user_id=actor_user_id,
            error_payload={
                "type": "configuration_error",
                "message": str(exc),
            },
        )
        raise PayoutServiceError(
            "payOS payout is not configured correctly.",
            code="PAYOUT_UNAVAILABLE",
            status=503,
            batch_id=batch.id,
        ) from exc
    except APIError as exc:
        _mark_batch_failed(
            batch_id=batch.id,
            actor_user_id=actor_user_id,
            error_payload=_build_api_error_payload(exc),
        )
        raise PayoutServiceError(
            _build_provider_message(exc),
            code="PAYOUT_PROVIDER_ERROR",
            status=_map_provider_status(exc.status_code),
            batch_id=batch.id,
        ) from exc
    except Exception as exc:
        _mark_batch_failed(
            batch_id=batch.id,
            actor_user_id=actor_user_id,
            error_payload={
                "type": type(exc).__name__,
                "message": str(exc),
            },
        )
        raise PayoutServiceError(
            "Unable to submit payout batch to payOS.",
            code="PAYOUT_SUBMISSION_FAILED",
            status=502,
            batch_id=batch.id,
        ) from exc

    updated_batch = _mark_batch_submitted(
        batch_id=batch.id,
        actor_user_id=actor_user_id,
        provider_response=provider_response,
    )
    logger.info(
        "payos_payout_submit_success internal_id=%s reference_id=%s provider_payout_id=%s item_count=%s approval_state=%s",
        updated_batch.id,
        updated_batch.reference_id,
        updated_batch.provider_payout_id,
        updated_batch.item_count,
        updated_batch.provider_approval_state,
    )
    return CreatePayoutBatchResult(batch=updated_batch, created=True, duplicate_reused=False)


def get_payout_batch(*, batch_id: int, refresh: bool = False) -> PayoutBatch | None:
    batch = payout_repository.get_batch_by_id(batch_id)
    if batch is None:
        return None
    if not refresh or not batch.provider_payout_id:
        return batch

    try:
        provider_response = payos_client.get_payout(batch.provider_payout_id)
    except payos_client.PayOSConfigurationError as exc:
        raise PayoutServiceError(
            "payOS payout is not configured correctly.",
            code="PAYOUT_UNAVAILABLE",
            status=503,
            batch_id=batch.id,
        ) from exc
    except APIError as exc:
        raise PayoutServiceError(
            _build_provider_message(exc),
            code="PAYOUT_PROVIDER_ERROR",
            status=_map_provider_status(exc.status_code),
            batch_id=batch.id,
        ) from exc
    except Exception as exc:
        raise PayoutServiceError(
            "Unable to refresh payout batch from payOS.",
            code="PAYOUT_REFRESH_FAILED",
            status=502,
            batch_id=batch.id,
        ) from exc

    return _mark_batch_submitted(
        batch_id=batch.id,
        actor_user_id=batch.created_by_admin_id,
        provider_response=provider_response,
    )


def serialize_payout_batch(batch: PayoutBatch) -> dict[str, Any]:
    request_payload = _mask_account_numbers(_json_loads(batch.request_payload_json))
    response_payload = _mask_account_numbers(_json_loads(batch.response_payload_json))
    error_payload = _mask_account_numbers(_json_loads(batch.error_payload_json))

    return {
        "id": batch.id,
        "reference_id": batch.reference_id,
        "client_reference_id": batch.client_reference_key,
        "status": batch.internal_status,
        "provider_payout_id": batch.provider_payout_id,
        "provider_approval_state": batch.provider_approval_state,
        "validate_destination": bool(batch.validate_destination),
        "item_count": int(batch.item_count or 0),
        "category": _json_loads(batch.category_json) or [],
        "submitted_at": _isoformat(batch.submitted_at),
        "last_synced_at": _isoformat(batch.last_synced_at),
        "created_at": _isoformat(batch.created_at),
        "updated_at": _isoformat(batch.updated_at),
        "request_payload": request_payload,
        "response_payload": response_payload,
        "error_payload": error_payload,
        "items": [serialize_payout_batch_item(item) for item in batch.items],
    }


def serialize_payout_batch_item(item: PayoutBatchItem) -> dict[str, Any]:
    response_payload = _mask_account_numbers(_json_loads(item.response_payload_json))
    return {
        "id": item.id,
        "reference_id": item.reference_id,
        "client_reference_id": item.client_reference_key,
        "amount": item.amount,
        "description": item.description,
        "to_bin": item.to_bin,
        "to_account_number_masked": _mask_account_number(item.to_account_number),
        "status": item.internal_status,
        "provider_transaction_id": item.provider_transaction_id,
        "provider_reference": item.provider_reference,
        "provider_state": item.provider_state,
        "error_code": item.error_code,
        "error_message": item.error_message,
        "response_payload": response_payload,
        "created_at": _isoformat(item.created_at),
        "updated_at": _isoformat(item.updated_at),
    }


def _mark_batch_submitted(*, batch_id: int, actor_user_id: int | None, provider_response: Payout) -> PayoutBatch:
    payload = provider_response.model_dump_camel_case()

    for attempt in range(2):
        try:
            batch = payout_repository.get_batch_by_id(batch_id)
            if batch is None:
                raise PayoutServiceError(
                    "Unable to reload payout batch after submission.",
                    code="DB_ERROR",
                    status=500,
                    batch_id=batch_id,
                )

            now = datetime.utcnow()
            batch.provider_payout_id = str(provider_response.id)
            batch.provider_approval_state = str(provider_response.approval_state)
            batch.internal_status = "submitted"
            batch.response_payload_json = _json_dumps(payload)
            batch.error_payload_json = None
            batch.submitted_at = batch.submitted_at or now
            batch.last_synced_at = now

            item_by_reference_id = {item.reference_id: item for item in batch.items}
            for item in batch.items:
                item.internal_status = "submitted"
                item.error_code = None
                item.error_message = None

            for transaction in provider_response.transactions:
                item = item_by_reference_id.get(str(transaction.reference_id))
                if item is None:
                    continue
                item.provider_transaction_id = str(transaction.id)
                item.provider_reference = str(transaction.reference) if transaction.reference is not None else None
                item.provider_state = str(transaction.state)
                item.response_payload_json = _json_dumps(transaction.model_dump_camel_case())
                item.error_code = transaction.error_code
                item.error_message = transaction.error_message

            _append_audit(
                actor_user_id=actor_user_id,
                action="payos.payout_batch.submitted",
                payload={
                    "batch_id": batch.id,
                    "reference_id": batch.reference_id,
                    "provider_payout_id": batch.provider_payout_id,
                    "item_count": batch.item_count,
                    "provider_approval_state": batch.provider_approval_state,
                },
            )
            db.session.commit()
            return payout_repository.get_batch_by_id(batch.id) or batch
        except SQLAlchemyError as exc:
            db.session.rollback()
            if attempt == 0:
                continue
            logger.exception(
                "payos_payout_submit_persist_failed internal_id=%s provider_payout_id=%s",
                batch_id,
                getattr(provider_response, "id", None),
            )
            raise PayoutServiceError(
                "Payout batch was submitted but the local confirmation record could not be updated.",
                code="DB_ERROR",
                status=500,
                batch_id=batch_id,
            ) from exc

    raise PayoutServiceError(
        "Payout batch was submitted but the local confirmation record could not be updated.",
        code="DB_ERROR",
        status=500,
        batch_id=batch_id,
    )


def _mark_batch_failed(*, batch_id: int, actor_user_id: int | None, error_payload: dict[str, Any]) -> None:
    try:
        batch = payout_repository.get_batch_by_id(batch_id)
        if batch is None:
            return
        batch.internal_status = "submission_failed"
        batch.error_payload_json = _json_dumps(error_payload)
        batch.last_synced_at = datetime.utcnow()
        for item in batch.items:
            item.internal_status = "submission_failed"
        _append_audit(
            actor_user_id=actor_user_id,
            action="payos.payout_batch.failed",
            payload={
                "batch_id": batch.id,
                "reference_id": batch.reference_id,
                "item_count": batch.item_count,
                "error_type": str(error_payload.get("type") or ""),
                "error_code": str(error_payload.get("error_code") or error_payload.get("code") or ""),
            },
        )
        db.session.commit()
        logger.warning(
            "payos_payout_submit_failed internal_id=%s reference_id=%s item_count=%s error_type=%s",
            batch.id,
            batch.reference_id,
            batch.item_count,
            error_payload.get("type"),
        )
    except SQLAlchemyError:
        db.session.rollback()
        logger.exception("payos_payout_failure_persist_failed internal_id=%s", batch_id)


def _append_audit(*, actor_user_id: int | None, action: str, payload: dict[str, Any]) -> None:
    db.session.add(
        AuditLog(
            user_id=actor_user_id,
            action=action,
            payload=payload,
        )
    )


def _build_request_fingerprint(validated: ValidatedCreatePayoutBatchInput) -> str:
    normalized = {
        "reference_id": validated.reference_id,
        "validate_destination": bool(validated.validate_destination),
        "category": list(validated.category),
        "payouts": [
            {
                "reference_id": item.reference_id,
                "amount": item.amount,
                "description": item.description,
                "to_bin": item.to_bin,
                "to_account_number": item.to_account_number,
            }
            for item in sorted(validated.payouts, key=lambda row: row.reference_id)
        ],
    }
    encoded = json.dumps(normalized, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _build_batch_reference_id(*, actor_user_id: int, reference_seed: str, allow_duplicate: bool) -> str:
    seed_hash = hashlib.sha256(f"{actor_user_id}:{reference_seed}".encode("utf-8")).hexdigest()[:12]
    base_reference = f"po_{actor_user_id}_{reference_seed[:48]}_{seed_hash}"
    if not allow_duplicate:
        return base_reference[:96]
    duplicate_hash = hashlib.sha256(
        f"{base_reference}:{datetime.utcnow().isoformat()}".encode("utf-8")
    ).hexdigest()[:8]
    return f"{base_reference[:84]}_dup_{duplicate_hash}"


def _build_item_reference_id(*, batch_reference_id: str, item_reference_seed: str) -> str:
    item_hash = hashlib.sha256(f"{batch_reference_id}:{item_reference_seed}".encode("utf-8")).hexdigest()[:10]
    return f"{batch_reference_id[:96]}_{item_reference_seed[:18]}_{item_hash}"[:128]


def _build_provider_request_payload(
    *,
    batch_reference_id: str,
    validated: ValidatedCreatePayoutBatchInput,
) -> tuple[PayoutBatchRequest, dict[str, Any], list[dict[str, object]]]:
    provider_items: list[dict[str, Any]] = []
    request_items: list[dict[str, Any]] = []
    item_rows: list[dict[str, object]] = []
    for item in validated.payouts:
        provider_reference_id = _build_item_reference_id(
            batch_reference_id=batch_reference_id,
            item_reference_seed=item.reference_id,
        )
        provider_item = {
            "reference_id": provider_reference_id,
            "amount": item.amount,
            "description": item.description,
            "to_bin": item.to_bin,
            "to_account_number": item.to_account_number,
        }
        provider_items.append(provider_item)
        request_items.append(
            {
                "referenceId": provider_reference_id,
                "amount": item.amount,
                "description": item.description,
                "toBin": item.to_bin,
                "toAccountNumber": item.to_account_number,
            }
        )
        item_rows.append(
            {
                "reference_id": provider_reference_id,
                "client_reference_key": item.reference_id,
                "amount": item.amount,
                "description": item.description,
                "to_bin": item.to_bin,
                "to_account_number": item.to_account_number,
            }
        )

    request_payload = {
        "referenceId": batch_reference_id,
        "category": list(validated.category) or None,
        "validateDestination": validated.validate_destination,
        "payouts": request_items,
    }
    if not _PAYOS_SDK_AVAILABLE:
        return request_payload, request_payload, item_rows

    request_model = PayoutBatchRequest(
        reference_id=batch_reference_id,
        category=list(validated.category) or None,
        validate_destination=validated.validate_destination,
        payouts=[PayOSPayoutBatchItem(**item) for item in provider_items],
    )
    return request_model, request_payload, item_rows


def _build_api_error_payload(exc: APIError) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "type": type(exc).__name__,
        "status_code": exc.status_code,
        "error_code": exc.error_code,
        "error_desc": exc.error_desc,
        "message": str(exc),
    }
    response = getattr(exc, "response", None)
    if response is not None:
        payload["response_text"] = (response.text or "")[:2000]
        try:
            payload["response_json"] = response.json()
        except Exception:
            payload["response_json"] = None
    return payload


def _build_provider_message(exc: APIError) -> str:
    if exc.status_code == 400:
        return "payOS rejected the payout batch."
    if exc.status_code == 429:
        return "payOS rate-limited the payout batch request."
    return "payOS could not process the payout batch request."


def _map_provider_status(status_code: int | None) -> int:
    if status_code == 400:
        return 400
    if status_code == 429:
        return 503
    return 502


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _json_loads(value: str | None) -> Any:
    if not value:
        return None
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return None


def _mask_account_numbers(payload: Any) -> Any:
    if isinstance(payload, dict):
        masked: dict[str, Any] = {}
        for key, value in payload.items():
            if key in {"toAccountNumber", "to_account_number"}:
                masked[key] = _mask_account_number(value)
            else:
                masked[key] = _mask_account_numbers(value)
        return masked
    if isinstance(payload, list):
        return [_mask_account_numbers(item) for item in payload]
    return payload


def _mask_account_number(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    if len(text) <= 4:
        return "*" * len(text)
    return f"{'*' * max(len(text) - 4, 0)}{text[-4:]}"


def _isoformat(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()
