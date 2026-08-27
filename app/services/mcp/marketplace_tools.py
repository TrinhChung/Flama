"""MCP shared decks, releases, and marketplace integration tools."""

from __future__ import annotations

from typing import Any
from sqlalchemy import or_

from app.repositories import flashcards_share_repository
from app.repositories.deck_tree_query import collect_subtree_ids as _collect_deck_subtree_ids
from app.services.mcp.deck_tools import resolve_deck
from app.services import (
    deck_release_service,
    flashcards_share_service,
    marketplace_hub_service,
)
from app.services.mcp.base import (
    _compact_description,
    _resolve_deck_for_user,
)
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.deck import Deck
from models.note_type import NoteType
from models.user import User
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.note import Note

# 8. Shared Decks, Shared Notes & Deck Releases
# ---------------------------------------------------------------------------


def list_shared_decks(
    *,
    user_id: int,
    query: str | None = None,
    category: str | None = None,
    tags: list[str] | None = None,
    pricing_mode: str | None = None,
    sort_by: str = "popular",
    only_mine: bool = False,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """List or search shared decks on the marketplace."""
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.deck_install import DeckInstall
    from app.services import marketplace_query_service

    items_query = DeckMarketplaceItem.query
    if only_mine:
        items_query = items_query.filter_by(owner_user_id=user_id)
    else:
        items_query = items_query.filter(
            or_(
                DeckMarketplaceItem.publish_status.in_(["published", "unlisted"]),
                DeckMarketplaceItem.owner_user_id == user_id,
            )
        )

    all_items = items_query.order_by(DeckMarketplaceItem.updated_at.desc()).all()

    normalized_tags = {t.lower() for t in (tags or [])}
    filtered = marketplace_query_service.filter_deck_items(
        all_items,
        query_text=query or "",
        category=category or "",
        tags=normalized_tags,
        pricing_mode=pricing_mode or "",
        min_price_amount_minor=None,
        max_price_amount_minor=None,
    )
    sorted_items = marketplace_query_service.sort_deck_items(filtered, sort_by)

    total = len(sorted_items)
    paged_items = sorted_items[offset : offset + limit]

    installs = DeckInstall.query.filter_by(user_id=user_id).all()
    install_map = {row.deck_item_id: row for row in installs}
    stats_map = marketplace_query_service.batch_compute_deck_items_stats(paged_items)

    result_items: list[dict[str, Any]] = []
    for item in paged_items:
        row = marketplace_query_service.serialize_deck_marketplace_item(item, stats=stats_map.get(item.id))
        install = install_map.get(item.id)
        row["is_installed"] = install is not None
        row["installed_deck_id"] = install.local_deck_id if install else None
        row["is_owner"] = item.owner_user_id == user_id
        result_items.append(row)

    return {
        "items": result_items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(result_items) < total),
    }


def get_shared_deck(*, user_id: int, deck_item_id: str) -> dict[str, Any]:
    """Get full details of a single shared deck item."""
    from app.services import marketplace_hub_service, marketplace_query_service

    deck_item = flashcards_share_service.get_shared_deck_item_for_view(deck_item_id, user_id)
    if deck_item is None:
        raise RequestValidationError(
            f"Không tìm thấy shared deck ID '{deck_item_id}'.",
            field="deck_item_id",
            status=404,
            code="DECK_ITEM_NOT_FOUND",
        )

    payload = flashcards_share_service.build_shared_deck_item_payload(
        deck_item,
        user_id=user_id,
        sample_limit=5,
        deck_active_review_threshold=3,
        review_preview_limit=10,
    )
    payload.update(
        marketplace_hub_service.build_deck_detail_extras(
            deck_item=deck_item,
            user_id=user_id,
        )
    )
    payload["lessons"] = marketplace_query_service.build_shared_deck_lessons_structure(deck_item)
    return payload


def list_shared_deck_notes(
    *,
    user_id: int,
    deck_item_id: str,
    query: str | None = None,
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    """Inspect notes and cards of a shared deck to review contents and descriptions."""
    deck_item = flashcards_share_service.get_shared_deck_item_for_view(deck_item_id, user_id)
    if deck_item is None:
        raise RequestValidationError(
            f"Không tìm thấy shared deck ID '{deck_item_id}'.",
            field="deck_item_id",
            status=404,
            code="DECK_ITEM_NOT_FOUND",
        )

    subtree_ids = _collect_deck_subtree_ids(deck_item.source_deck_id)
    notes_query = Note.query.filter(
        Note.deck_id.in_(subtree_ids),
        Note.user_id == deck_item.owner_user_id,
    )

    if query:
        search_term = f"%{query}%"
        notes_query = notes_query.filter(
            or_(
                Note.field_values.cast(db.String).ilike(search_term),
                Note.tags.cast(db.String).ilike(search_term),
            )
        )

    total = notes_query.count()
    notes = notes_query.order_by(Note.id.asc()).offset(offset).limit(limit).all()

    decks_map = {d.id: d.name for d in Deck.query.filter(Deck.id.in_(subtree_ids)).all()}
    note_types_map = {nt.id: nt.name for nt in NoteType.query.all()}

    note_items: list[dict[str, Any]] = []
    for note in notes:
        note_items.append(
            {
                "note_id": str(note.id),
                "deck_id": int(note.deck_id) if note.deck_id else None,
                "deck_name": decks_map.get(note.deck_id),
                "note_type_id": str(note.note_type_id),
                "note_type_name": note_types_map.get(note.note_type_id),
                "fields": dict(note.field_values or {}),
                "tags": list(note.tags or []),
                "card_count": len(note.cards),
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            }
        )

    return {
        "deck_item_id": str(deck_item.id),
        "deck_item_title": deck_item.title,
        "source_deck_id": int(deck_item.source_deck_id),
        "current_release_id": str(deck_item.current_release_id) if deck_item.current_release_id else None,
        "notes": note_items,
        "total": total,
        "limit": limit,
        "offset": offset,
        "has_more": (offset + len(note_items) < total),
    }


def get_deck_publish_options(*, user_id: int, deck_id: int | None = None) -> dict[str, Any]:
    """Check deck publish eligibility and list available categories and note types."""
    from app.services import marketplace_taxonomy_service

    options = flashcards_share_service.build_deck_publish_options(user_id=user_id)
    options["categories"] = [opt["id"] for opt in marketplace_taxonomy_service.SUBJECT_OPTIONS]
    if deck_id is not None:
        user_deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
        if user_deck is None:
            raise RequestValidationError(
                f"Không tìm thấy deck ID {deck_id} của bạn.",
                field="deck_id",
                status=404,
                code="DECK_NOT_FOUND",
            )
        eligibility = flashcards_share_service.get_deck_publish_eligibility(
            deck=user_deck,
            user_id=user_id,
        )
        options["selected_deck"] = {
            "deck_id": int(user_deck.id),
            "name": user_deck.name,
            "eligible": eligibility.get("is_selectable", False),
            "block_code": eligibility.get("block_code"),
            "reason": eligibility.get("block_reason"),
            "shared_item_id": eligibility.get("shared_item_id"),
        }
    return options


def get_taxonomy_schema(
    *,
    user_id: int,
    content_type: str = "deck_marketplace_item",
) -> dict[str, Any]:
    """Retrieve full hierarchical taxonomy schema (domains, subjects, frameworks, levels, topics, goals)."""
    from app.services import marketplace_taxonomy_service

    del user_id
    return marketplace_taxonomy_service.build_taxonomy_schema(content_type=content_type)


def share_deck(
    *,
    user_id: int,
    deck_id: int | None = None,
    deck_path: str | None = None,
    title: str | None = None,
    description: str | None = None,
    primary_category: str | None = None,
    tags: list[str] | None = None,
    pricing_mode: str = "free",
    price_amount_minor: int | None = None,
    is_unlisted: bool = False,
    preview_text: str | None = None,
    sample_cards_count: int | None = None,
    taxonomy_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Publish/share a personal deck to the marketplace."""
    resolved_deck_id = deck_id
    if resolved_deck_id is None and deck_path:
        res = resolve_deck(user_id=user_id, path=deck_path)
        if not res.get("found"):
            raise RequestValidationError(
                f"Không tìm thấy deck với đường dẫn '{deck_path}'.",
                field="deck_path",
                status=404,
                code="DECK_NOT_FOUND",
            )
        resolved_deck_id = res["deck_id"]

    user_deck = Deck.query.filter_by(id=resolved_deck_id, owner_user_id=user_id, deleted_at=None).first()
    if user_deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {resolved_deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    payload = {
        "source_deck_id": resolved_deck_id,
        "title": title or user_deck.name,
        "description": description or user_deck.description or "",
        "primary_category": primary_category or "japanese",
        "tags": tags or [],
        "pricing_mode": pricing_mode,
        "price_amount_minor": price_amount_minor or 0,
        "is_unlisted": is_unlisted,
    }
    if preview_text is not None:
        payload["preview_text"] = preview_text
    if sample_cards_count is not None:
        payload["sample_cards_count"] = sample_cards_count
    if taxonomy_metadata is not None:
        payload.update(taxonomy_metadata)

    user = db.session.get(User, user_id)
    is_admin = bool(user and user.is_admin)

    deck_item, val_err, err_field = flashcards_share_service.create_shared_deck_item(
        user_id=user_id,
        payload=payload,
        is_admin=is_admin,
        require_source_note_type=True,
    )
    if val_err:
        raise RequestValidationError(val_err, field=err_field or "deck_id", status=400, code="SHARE_DECK_ERROR")

    flashcards_share_service._stage_initial_release_if_visible(deck_item)
    db.session.commit()
    from app.services import marketplace_query_service

    return marketplace_query_service.serialize_deck_marketplace_item(deck_item)


def update_shared_deck(
    *,
    user_id: int,
    deck_item_id: str,
    title: str | None = None,
    description: str | None = None,
    primary_category: str | None = None,
    tags: list[str] | None = None,
    pricing_mode: str | None = None,
    price_amount_minor: int | None = None,
    publish_status: str | None = None,
    preview_text: str | None = None,
    sample_cards_count: int | None = None,
    taxonomy_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Update metadata, description, tags, and status of an already shared deck."""
    from models.deck_marketplace_item import DeckMarketplaceItem
    from app.services import marketplace_query_service

    deck_item = DeckMarketplaceItem.query.filter_by(id=deck_item_id).first()
    if deck_item is None:
        raise RequestValidationError(
            f"Không tìm thấy shared deck ID '{deck_item_id}'.",
            field="deck_item_id",
            status=404,
            code="DECK_ITEM_NOT_FOUND",
        )

    user = db.session.get(User, user_id)
    is_admin = bool(user and user.is_admin)

    if deck_item.owner_user_id != user_id and not is_admin:
        raise RequestValidationError(
            "Bạn chỉ có thể chỉnh sửa bộ thẻ do chính mình chia sẻ.",
            field="deck_item_id",
            status=403,
            code="PERMISSION_DENIED",
        )

    payload: dict[str, Any] = {}
    if title is not None:
        payload["title"] = title
    if description is not None:
        payload["description"] = description
    if primary_category is not None:
        payload["primary_category"] = primary_category
    if tags is not None:
        payload["tags"] = tags
    if pricing_mode is not None:
        payload["pricing_mode"] = pricing_mode
    if price_amount_minor is not None:
        payload["price_amount_minor"] = price_amount_minor
    if publish_status is not None:
        payload["publish_status"] = publish_status
    if preview_text is not None:
        payload["preview_text"] = preview_text
    if sample_cards_count is not None:
        payload["sample_cards_count"] = sample_cards_count
    if taxonomy_metadata is not None:
        payload.update(taxonomy_metadata)

    _, val_err, err_field = flashcards_share_service.update_shared_deck_item(
        deck_item=deck_item,
        user_id=user_id,
        payload=payload,
        is_admin=is_admin,
        require_source_note_type=True,
    )
    if val_err:
        raise RequestValidationError(val_err, field=err_field, status=400, code="UPDATE_SHARED_DECK_ERROR")

    db.session.commit()
    return marketplace_query_service.serialize_deck_marketplace_item(deck_item)



def preview_deck_release(
    *,
    user_id: int,
    deck_item_id: str,
    limit: int = 50,
    cursor: str | None = None,
) -> dict[str, Any]:
    """Preview changes/diff between working notes and current release of a shared deck."""
    from app.services import deck_release_service

    try:
        payload = deck_release_service.preview_release(
            deck_item_id=deck_item_id,
            user_id=user_id,
            limit=limit,
            cursor=cursor,
        )
        return payload
    except deck_release_service.DeckReleaseError as exc:
        raise RequestValidationError(
            exc.message,
            field=exc.field or "deck_item_id",
            status=exc.status,
            code=exc.error,
        )


def publish_deck_release(
    *,
    user_id: int,
    deck_item_id: str,
    version_label: str,
    changelog: str | None = None,
    expected_current_release_id: str | None = None,
    expected_working_revision: int | None = None,
) -> dict[str, Any]:
    """Publish a new immutable version/release for a shared deck after notes/cards are updated."""
    from app.services import deck_release_service
    from models.deck_marketplace_item import DeckMarketplaceItem

    deck_item = DeckMarketplaceItem.query.filter_by(id=deck_item_id).first()
    if deck_item is None:
        raise RequestValidationError(
            f"Không tìm thấy shared deck ID '{deck_item_id}'.",
            field="deck_item_id",
            status=404,
            code="DECK_ITEM_NOT_FOUND",
        )

    user = db.session.get(User, user_id)
    is_admin = bool(user and user.is_admin)
    if deck_item.owner_user_id != user_id and not is_admin:
        raise RequestValidationError(
            "Chỉ tác giả sở hữu bộ thẻ mới có thể phát hành bản release mới.",
            field="deck_item_id",
            status=403,
            code="PERMISSION_DENIED",
        )

    current_rel_id = expected_current_release_id if expected_current_release_id is not None else deck_item.current_release_id
    current_rev = expected_working_revision if expected_working_revision is not None else int(deck_item.working_revision or 0)
    idempotency_key = f"mcp_{deck_item_id}_{version_label}_{current_rev}"

    try:
        result = deck_release_service.publish_release(
            deck_item_id=deck_item_id,
            user_id=user_id,
            version_label=version_label,
            changelog=changelog,
            expected_current_release_id=current_rel_id,
            expected_working_revision=current_rev,
            idempotency_key=idempotency_key,
        )
        db.session.commit()
        return {
            "release": deck_release_service.serialize_release(result.release),
            "replayed": result.replayed,
        }
    except deck_release_service.DeckReleaseError as exc:
        db.session.rollback()
        raise RequestValidationError(
            exc.message,
            field=exc.field or "deck_item_id",
            status=exc.status,
            code=exc.error,
        )


def list_deck_releases(
    *,
    user_id: int,
    deck_item_id: str,
    limit: int = 20,
    cursor: str | None = None,
) -> dict[str, Any]:
    """List release history for a shared deck."""
    from app.services import deck_release_service

    try:
        return deck_release_service.list_deck_releases(
            deck_item_id=deck_item_id,
            user_id=user_id,
            limit=limit,
            cursor=cursor,
        )
    except deck_release_service.DeckReleaseError as exc:
        raise RequestValidationError(
            exc.message,
            field=exc.field or "deck_item_id",
            status=exc.status,
            code=exc.error,
        )


def list_installed_decks(*, user_id: int) -> dict[str, Any]:
    """List shared marketplace decks installed in the user's library."""
    from models.deck_install import DeckInstall

    installs = DeckInstall.query.filter_by(user_id=user_id).order_by(DeckInstall.installed_at.desc()).all()
    items: list[dict[str, Any]] = []

    for inst in installs:
        deck_item = inst.deck_item
        local_deck = inst.local_deck
        if not deck_item or not local_deck:
            continue

        has_update = bool(
            deck_item.current_release_id
            and inst.base_release_id
            and str(deck_item.current_release_id) != str(inst.base_release_id)
        )

        items.append(
            {
                "install_id": str(inst.id),
                "deck_item_id": str(deck_item.id),
                "deck_item_title": deck_item.title,
                "local_deck_id": int(local_deck.id),
                "local_deck_name": local_deck.name,
                "installed_at": inst.installed_at.isoformat() if inst.installed_at else None,
                "current_upstream_version": deck_item.version,
                "installed_base_release_id": str(inst.base_release_id) if inst.base_release_id else None,
                "update_available": has_update,
                "note_override_count": len(inst.note_field_overrides),
            }
        )

    return {
        "installed_decks": items,
        "total": len(items),
    }

