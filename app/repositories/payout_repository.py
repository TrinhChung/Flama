from __future__ import annotations

from sqlalchemy.orm import selectinload

from models import db
from models.payout_batch import PayoutBatch
from models.payout_batch_item import PayoutBatchItem


def get_batch_by_id(batch_id: int) -> PayoutBatch | None:
    if not batch_id:
        return None
    return (
        PayoutBatch.query.options(selectinload(PayoutBatch.items))
        .filter(PayoutBatch.id == batch_id)
        .first()
    )


def get_batch_by_reference_id(reference_id: str) -> PayoutBatch | None:
    return (
        PayoutBatch.query.options(selectinload(PayoutBatch.items))
        .filter(PayoutBatch.reference_id == reference_id)
        .first()
    )


def create_batch(
    *,
    reference_id: str,
    client_reference_key: str,
    request_fingerprint: str,
    validate_destination: bool,
    category_json: str,
    request_payload_json: str,
    created_by_admin_id: int,
    items: list[dict[str, object]],
) -> PayoutBatch:
    batch = PayoutBatch(
        reference_id=reference_id,
        client_reference_key=client_reference_key,
        request_fingerprint=request_fingerprint,
        validate_destination=validate_destination,
        item_count=len(items),
        category_json=category_json,
        request_payload_json=request_payload_json,
        created_by_admin_id=created_by_admin_id,
    )
    db.session.add(batch)
    db.session.flush()

    for row in items:
        db.session.add(
            PayoutBatchItem(
                batch_id=batch.id,
                reference_id=str(row["reference_id"]),
                client_reference_key=str(row["client_reference_key"]),
                amount=int(row["amount"]),
                description=str(row["description"]),
                to_bin=str(row["to_bin"]),
                to_account_number=str(row["to_account_number"]),
            )
        )

    db.session.flush()
    return batch
