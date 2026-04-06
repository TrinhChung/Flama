"""Repository helpers for deck change request queries."""

from __future__ import annotations

from sqlalchemy.orm import joinedload, selectinload

from models.deck_change_request import DeckChangeRequest
from models.deck_change_request_conflict import DeckChangeRequestConflict
from models.deck_change_request_item import DeckChangeRequestItem


def get_active_request_for_install(
    deck_install_id: str,
    *,
    statuses: set[str],
) -> DeckChangeRequest | None:
    if not deck_install_id or not statuses:
        return None
    return (
        DeckChangeRequest.query.filter(
            DeckChangeRequest.deck_install_id == deck_install_id,
            DeckChangeRequest.status.in_(sorted(statuses)),
        )
        .order_by(DeckChangeRequest.updated_at.desc(), DeckChangeRequest.created_at.desc(), DeckChangeRequest.id.desc())
        .first()
    )


def get_request_with_detail(request_id: str) -> DeckChangeRequest | None:
    if not request_id:
        return None
    return (
        DeckChangeRequest.query.options(
            joinedload(DeckChangeRequest.deck_item),
            joinedload(DeckChangeRequest.requester),
            joinedload(DeckChangeRequest.owner),
            joinedload(DeckChangeRequest.reviewed_by),
            selectinload(DeckChangeRequest.items).selectinload(DeckChangeRequestItem.conflicts),
            selectinload(DeckChangeRequest.conflicts),
        )
        .filter(DeckChangeRequest.id == request_id)
        .first()
    )


def list_incoming_requests_for_owner(
    owner_user_id: int,
    *,
    statuses: set[str],
    deck_item_id: str | None = None,
) -> list[DeckChangeRequest]:
    if not statuses:
        return []
    query = DeckChangeRequest.query.options(
        joinedload(DeckChangeRequest.deck_item),
        joinedload(DeckChangeRequest.requester),
    ).filter(
        DeckChangeRequest.owner_user_id == owner_user_id,
        DeckChangeRequest.status.in_(sorted(statuses)),
    )
    if deck_item_id:
        query = query.filter(DeckChangeRequest.deck_item_id == deck_item_id)
    return (
        query.order_by(
            DeckChangeRequest.updated_at.desc(),
            DeckChangeRequest.created_at.desc(),
            DeckChangeRequest.id.desc(),
        ).all()
    )


def get_request_conflict(change_request_id: str, conflict_id: str) -> DeckChangeRequestConflict | None:
    if not change_request_id or not conflict_id:
        return None
    return (
        DeckChangeRequestConflict.query.filter_by(
            change_request_id=change_request_id,
            id=conflict_id,
        )
        .order_by(DeckChangeRequestConflict.created_at.asc(), DeckChangeRequestConflict.id.asc())
        .first()
    )
