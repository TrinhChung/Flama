"""Repository helpers for deck change request queries.

The review UI can contain tens of thousands of atomic field changes.  Keep
header/count reads separate from item reads so an inbox or the first detail
page never hydrates the complete request graph.
"""

from __future__ import annotations

from sqlalchemy import and_, func, or_
from sqlalchemy.orm import joinedload, selectinload

from models import db
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


def get_request_header(request_id: str) -> DeckChangeRequest | None:
    """Load request metadata without hydrating its unbounded item graph."""

    if not request_id:
        return None
    return (
        DeckChangeRequest.query.options(
            joinedload(DeckChangeRequest.deck_item),
            joinedload(DeckChangeRequest.requester),
            joinedload(DeckChangeRequest.owner),
            joinedload(DeckChangeRequest.reviewed_by),
        )
        .filter(DeckChangeRequest.id == request_id)
        .first()
    )


def list_incoming_requests_for_owner(
    owner_user_id: int,
    *,
    statuses: set[str],
    deck_item_id: str | None = None,
    cursor_updated_at=None,
    cursor_id: str | None = None,
    limit: int = 30,
) -> tuple[list[tuple[DeckChangeRequest, int, int]], bool]:
    if not statuses:
        return [], False

    item_counts = (
        db.session.query(
            DeckChangeRequestItem.change_request_id.label("change_request_id"),
            func.count(DeckChangeRequestItem.id).label("item_count"),
        )
        .group_by(DeckChangeRequestItem.change_request_id)
        .subquery()
    )
    unresolved_counts = (
        db.session.query(
            DeckChangeRequestConflict.change_request_id.label("change_request_id"),
            func.count(DeckChangeRequestConflict.id).label("unresolved_conflict_count"),
        )
        .filter(DeckChangeRequestConflict.resolved_at.is_(None))
        .group_by(DeckChangeRequestConflict.change_request_id)
        .subquery()
    )
    query = (
        db.session.query(
            DeckChangeRequest,
            func.coalesce(item_counts.c.item_count, 0),
            func.coalesce(unresolved_counts.c.unresolved_conflict_count, 0),
        )
        .outerjoin(
            item_counts,
            item_counts.c.change_request_id == DeckChangeRequest.id,
        )
        .outerjoin(
            unresolved_counts,
            unresolved_counts.c.change_request_id == DeckChangeRequest.id,
        )
        .options(
            joinedload(DeckChangeRequest.deck_item),
            joinedload(DeckChangeRequest.requester),
        )
        .filter(
            DeckChangeRequest.owner_user_id == owner_user_id,
            DeckChangeRequest.status.in_(sorted(statuses)),
        )
    )
    if deck_item_id:
        query = query.filter(DeckChangeRequest.deck_item_id == deck_item_id)
    if cursor_updated_at is not None and cursor_id:
        query = query.filter(
            or_(
                DeckChangeRequest.updated_at < cursor_updated_at,
                and_(
                    DeckChangeRequest.updated_at == cursor_updated_at,
                    DeckChangeRequest.id < cursor_id,
                ),
            )
        )
    rows = (
        query.order_by(
            DeckChangeRequest.updated_at.desc(),
            DeckChangeRequest.id.desc(),
        )
        .limit(limit + 1)
        .all()
    )
    return [
        (request_obj, int(item_count or 0), int(unresolved_count or 0))
        for request_obj, item_count, unresolved_count in rows[:limit]
    ], len(rows) > limit


def get_request_counts(request_id: str) -> tuple[int, int, dict[str, int]]:
    """Return total item/conflict counters without loading JSON diff values."""

    item_count = (
        db.session.query(func.count(DeckChangeRequestItem.id))
        .filter(DeckChangeRequestItem.change_request_id == request_id)
        .scalar()
    )
    unresolved_count = (
        db.session.query(func.count(DeckChangeRequestConflict.id))
        .filter(
            DeckChangeRequestConflict.change_request_id == request_id,
            DeckChangeRequestConflict.resolved_at.is_(None),
        )
        .scalar()
    )
    change_counts = {
        str(change_type): int(row_count or 0)
        for change_type, row_count in (
            db.session.query(
                DeckChangeRequestItem.change_type,
                func.count(DeckChangeRequestItem.id),
            )
            .filter(DeckChangeRequestItem.change_request_id == request_id)
            .group_by(DeckChangeRequestItem.change_type)
            .all()
        )
    }
    return int(item_count or 0), int(unresolved_count or 0), change_counts


def list_request_items_page(
    request_id: str,
    *,
    after_sort_order: int | None,
    after_id: str | None,
    limit: int,
    change_types: set[str] | None = None,
    query_text: str | None = None,
    conflicts_only: bool = False,
) -> tuple[list[DeckChangeRequestItem], bool, int]:
    """Read a stable keyset page of atomic diff items."""

    query = DeckChangeRequestItem.query.filter(
        DeckChangeRequestItem.change_request_id == request_id
    )
    if change_types:
        query = query.filter(DeckChangeRequestItem.change_type.in_(sorted(change_types)))
    if query_text:
        pattern = f"%{query_text}%"
        query = query.filter(
            or_(
                DeckChangeRequestItem.path_label.ilike(pattern),
                DeckChangeRequestItem.path_key.ilike(pattern),
                DeckChangeRequestItem.source_ref_id.ilike(pattern),
            )
        )
    if conflicts_only:
        query = query.filter(DeckChangeRequestItem.is_conflict.is_(True))

    filtered_count = int(query.with_entities(func.count(DeckChangeRequestItem.id)).scalar() or 0)
    if after_sort_order is not None and after_id:
        query = query.filter(
            or_(
                DeckChangeRequestItem.sort_order > after_sort_order,
                and_(
                    DeckChangeRequestItem.sort_order == after_sort_order,
                    DeckChangeRequestItem.id > after_id,
                ),
            )
        )
    rows = (
        query.options(selectinload(DeckChangeRequestItem.conflicts))
        .order_by(
            DeckChangeRequestItem.sort_order.asc(),
            DeckChangeRequestItem.id.asc(),
        )
        .limit(limit + 1)
        .all()
    )
    return rows[:limit], len(rows) > limit, filtered_count


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
