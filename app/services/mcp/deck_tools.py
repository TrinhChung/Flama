"""MCP deck operations: list, inspect, resolve, create, update, delete."""

from __future__ import annotations

from typing import Any

from app.repositories import vocabulary_repository
from app.repositories.deck_tree_query import collect_subtree_ids as _collect_deck_subtree_ids
from app.services import flashcards_share_service
from app.services import browse_card_service
from app.services.deck_management_service import delete_deck_subtree
from app.services.stats_overview import get_effective_timezone_name
from app.services.mcp.base import (
    _build_deck_full_path,
    _compact_description,
    _resolve_deck_for_user,
    _resolve_note_type_for_user,
)
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.user import User

# 1. Deck Operations
# ---------------------------------------------------------------------------


def list_my_decks(*, user_id: int) -> list[dict[str, Any]]:
    """Return a compact list of decks owned or accessible by the user."""
    decks = vocabulary_repository.collect_accessible_browse_decks(
        user_id=user_id,
        admin_mode=False,
    )

    payload_items: list[dict[str, Any]] = []
    seen_ids: set[int] = set()
    for deck_obj in decks:
        if deck_obj.id is None or int(deck_obj.id) in seen_ids:
            continue
        if int(deck_obj.owner_user_id or 0) != int(user_id):
            continue

        seen_ids.add(int(deck_obj.id))
        item: dict[str, Any] = {
            "deck_id": int(deck_obj.id),
            "name": deck_obj.name,
            "parent_id": int(deck_obj.parent_id) if deck_obj.parent_id is not None else None,
            "position": int(deck_obj.position or 0),
        }

        description = _compact_description(deck_obj.description)
        if description:
            item["description"] = description
        if deck_obj.created_at is not None:
            item["created_at"] = deck_obj.created_at.isoformat()

        payload_items.append(item)

    return payload_items


def get_deck_tree(*, user_id: int) -> list[dict[str, Any]]:
    """Return the hierarchical deck tree structure for the user."""
    user = db.session.get(User, user_id)
    try:
        return browse_card_service.build_browse_deck_tree(
            user_id=user_id,
            admin_mode=False,
            timezone_name=get_effective_timezone_name(
                getattr(user, "timezone", "UTC")
            ),
        )["tree"]
    except browse_card_service.BrowseApiError as exc:
        raise RequestValidationError(
            str(exc),
            field="user_id",
            status=exc.status,
            code=exc.code or "BROWSE_AUTHORITY_READ_FAILED",
        ) from exc


def get_deck(*, user_id: int, deck_id: int) -> dict[str, Any]:
    """Get metadata and counts for a single deck owned by user, including default note type and note types in use."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    full_path = _build_deck_full_path(deck, user_id)
    note_count = Note.query.filter_by(deck_id=deck_id, user_id=user_id).count()
    card_count = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id == deck_id, Note.user_id == user_id)
        .count()
    )
    subdeck_count = Deck.query.filter_by(parent_id=deck_id, owner_user_id=user_id, deleted_at=None).count()

    default_nt = None
    if deck.note_type:
        default_nt = {
            "id": str(deck.note_type.id),
            "name": deck.note_type.name,
        }

    note_types_rows = (
        db.session.query(Note.note_type_id, db.func.count(Note.id))
        .filter(Note.deck_id == deck_id, Note.user_id == user_id)
        .group_by(Note.note_type_id)
        .all()
    )
    note_type_ids = [r[0] for r in note_types_rows if r[0]]
    note_type_map: dict[str, str] = {}
    if note_type_ids:
        nts = NoteType.query.filter(NoteType.id.in_(note_type_ids)).all()
        note_type_map = {nt.id: nt.name for nt in nts}

    note_types_in_use = [
        {
            "id": str(nt_id),
            "name": note_type_map.get(nt_id, "Unknown"),
            "notes_count": int(count),
        }
        for nt_id, count in note_types_rows
    ]

    return {
        "deck_id": int(deck.id),
        "name": deck.name,
        "full_path": full_path,
        "description": deck.description,
        "parent_id": int(deck.parent_id) if deck.parent_id is not None else None,
        "position": int(deck.position or 0),
        "default_note_type": default_nt,
        "note_types_in_use": note_types_in_use,
        "note_count": note_count,
        "card_count": card_count,
        "subdeck_count": subdeck_count,
        "created_at": deck.created_at.isoformat() if deck.created_at else None,
    }


def resolve_deck(*, user_id: int, path: str) -> dict[str, Any]:
    """Find a deck by hierarchical path without creating it if missing."""
    cleaned = str(path or "").strip()
    if not cleaned:
        return {
            "found": False,
            "deck_id": None,
            "name": None,
            "full_path": None,
            "parent_id": None,
        }

    tokens = [t.strip() for t in cleaned.replace("/", "::").split("::") if t.strip()]
    if not tokens:
        return {
            "found": False,
            "deck_id": None,
            "name": None,
            "full_path": None,
            "parent_id": None,
        }

    current_parent_id: int | None = None
    leaf_deck: Deck | None = None

    for token in tokens:
        candidates = Deck.query.filter_by(
            parent_id=current_parent_id,
            owner_user_id=user_id,
            deleted_at=None,
        ).all()

        # 1. Exact match
        matched = next((d for d in candidates if d.name == token), None)
        # 2. Case-insensitive fallback
        if matched is None:
            token_lower = token.lower()
            matched = next((d for d in candidates if d.name.lower() == token_lower), None)

        if matched is None:
            return {
                "found": False,
                "deck_id": None,
                "name": None,
                "full_path": None,
                "parent_id": None,
            }

        leaf_deck = matched
        current_parent_id = matched.id

    if leaf_deck is None:
        return {
            "found": False,
            "deck_id": None,
            "name": None,
            "full_path": None,
            "parent_id": None,
        }

    return {
        "found": True,
        "deck_id": int(leaf_deck.id),
        "name": leaf_deck.name,
        "full_path": _build_deck_full_path(leaf_deck, user_id),
        "parent_id": int(leaf_deck.parent_id) if leaf_deck.parent_id is not None else None,
        "description": leaf_deck.description,
    }


def batch_ensure_decks(*, user_id: int, paths: list[str]) -> dict[str, Any]:
    """Ensure multiple hierarchical deck paths exist, creating missing nodes idempotently."""
    results: dict[str, Any] = {}
    created_count = 0
    existing_count = 0

    for raw_path in paths:
        cleaned = str(raw_path or "").strip()
        if not cleaned:
            continue
        tokens = [t.strip() for t in cleaned.replace("/", "::").split("::") if t.strip()]
        if not tokens:
            continue

        upsert_res = vocabulary_repository.upsert_deck_path(
            parent_id=None,
            path_tokens=tokens,
            owner_user_id=user_id,
            admin_mode=False,
        )
        if upsert_res.final_deck is not None:
            final_deck = upsert_res.final_deck
            is_created = upsert_res.created_count > 0
            if is_created:
                created_count += 1
            else:
                existing_count += 1

            results[cleaned] = {
                "deck_id": int(final_deck.id),
                "name": final_deck.name,
                "full_path": _build_deck_full_path(final_deck, user_id),
                "parent_id": int(final_deck.parent_id) if final_deck.parent_id is not None else None,
                "created": is_created,
            }

    db.session.commit()

    return {
        "results": results,
        "total_requested": len(paths),
        "created_count": created_count,
        "existing_count": existing_count,
    }


def create_deck(
    *,
    user_id: int,
    name: str,
    parent_id: int | None = None,
    description: str | None = None,
    default_note_type_id: str | None = None,
) -> dict[str, Any]:
    """Create a new flashcard deck or subdeck."""
    if parent_id is not None:
        parent_deck = Deck.query.filter_by(id=parent_id, owner_user_id=user_id, deleted_at=None).first()
        if parent_deck is None:
            raise RequestValidationError(
                f"Không tìm thấy parent deck ID {parent_id} của bạn.",
                field="parent_id",
                status=404,
                code="PARENT_DECK_NOT_FOUND",
            )

    resolved_note_type = None
    if default_note_type_id:
        resolved_note_type = _resolve_note_type_for_user(user_id=user_id, note_type_id=default_note_type_id)
        guard_error = flashcards_share_service.validate_marketplace_note_type_for_deck(
            deck_id=parent_id,
            note_type_id=resolved_note_type.id,
            user_id=user_id,
        )
        if guard_error:
            raise RequestValidationError(
                guard_error,
                field="default_note_type_id",
                status=409,
                code="DECK_SOURCE_NOTETYPE_MISMATCH",
            )

    cleaned_name = str(name).strip()
    if "::" in cleaned_name or "/" in cleaned_name:
        tokens = [t.strip() for t in cleaned_name.replace("/", "::").split("::") if t.strip()]
        upsert_res = vocabulary_repository.upsert_deck_path(
            parent_id=parent_id,
            path_tokens=tokens,
            owner_user_id=user_id,
            admin_mode=False,
        )
        if upsert_res.final_deck is None:
            raise RequestValidationError(
                f"Không thể tạo deck '{name}'.",
                field="name",
                status=400,
                code="DECK_CREATION_FAILED",
            )
        if description:
            upsert_res.final_deck.description = description
        if resolved_note_type:
            upsert_res.final_deck.note_type_id = resolved_note_type.id
        db.session.commit()
        return {
            "deck_id": int(upsert_res.final_deck.id),
            "name": upsert_res.final_deck.name,
            "parent_id": int(upsert_res.final_deck.parent_id) if upsert_res.final_deck.parent_id else None,
            "default_note_type": {"id": str(resolved_note_type.id), "name": resolved_note_type.name} if resolved_note_type else None,
            "created_count": upsert_res.created_count,
            "created_at": upsert_res.final_deck.created_at.isoformat() if upsert_res.final_deck.created_at else None,
        }

    existing = Deck.query.filter_by(
        parent_id=parent_id,
        name=cleaned_name,
        owner_user_id=user_id,
        deleted_at=None,
    ).first()
    if existing is not None:
        if resolved_note_type and existing.note_type_id != resolved_note_type.id:
            existing.note_type_id = resolved_note_type.id
            db.session.commit()
        return {
            "deck_id": int(existing.id),
            "name": existing.name,
            "parent_id": int(existing.parent_id) if existing.parent_id is not None else None,
            "description": existing.description,
            "default_note_type": {"id": str(existing.note_type.id), "name": existing.note_type.name} if existing.note_type else None,
            "created_at": existing.created_at.isoformat() if existing.created_at else None,
            "existing": True,
        }

    position = vocabulary_repository.next_deck_position(parent_id)
    new_deck = Deck(
        owner_user_id=user_id,
        parent_id=parent_id,
        name=cleaned_name,
        description=description,
        position=position,
        note_type_id=resolved_note_type.id if resolved_note_type else None,
    )
    db.session.add(new_deck)
    db.session.commit()

    return {
        "deck_id": int(new_deck.id),
        "name": new_deck.name,
        "parent_id": int(new_deck.parent_id) if new_deck.parent_id is not None else None,
        "description": new_deck.description,
        "default_note_type": {"id": str(resolved_note_type.id), "name": resolved_note_type.name} if resolved_note_type else None,
        "created_at": new_deck.created_at.isoformat() if new_deck.created_at else None,
        "existing": False,
    }


def update_deck(
    *,
    user_id: int,
    deck_id: int,
    name: str | None = None,
    description: str | None = None,
    parent_id: int | None = None,
    update_parent: bool = False,
    default_note_type_id: str | None = None,
    update_default_note_type: bool = False,
) -> dict[str, Any]:
    """Update a deck's name, description, parent, or default note type."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    if name is not None:
        deck.name = name
    if description is not None:
        deck.description = description
    if update_parent:
        if parent_id == deck.id:
            raise RequestValidationError(
                "Một deck không thể làm parent của chính nó.",
                field="parent_id",
                status=400,
                code="CYCLIC_PARENT_ERROR",
            )
        if parent_id is not None:
            parent_deck = Deck.query.filter_by(id=parent_id, owner_user_id=user_id, deleted_at=None).first()
            if parent_deck is None:
                raise RequestValidationError(
                    f"Không tìm thấy parent deck ID {parent_id} của bạn.",
                    field="parent_id",
                    status=404,
                    code="PARENT_DECK_NOT_FOUND",
                )
            subtree_ids = _collect_deck_subtree_ids(deck.id)
            if parent_id in subtree_ids:
                raise RequestValidationError(
                    "Không thể chuyển deck vào một subdeck của chính nó.",
                    field="parent_id",
                    status=400,
                    code="CYCLIC_PARENT_ERROR",
                )
        guard_error = flashcards_share_service.validate_deck_subtree_move_to_parent(
            deck_id=deck.id,
            new_parent_id=parent_id,
            user_id=user_id,
        )
        if guard_error:
            raise RequestValidationError(
                guard_error,
                field="parent_id",
                status=409,
                code="DECK_SOURCE_NOTETYPE_MISMATCH",
            )
        deck.parent_id = parent_id
        deck.position = vocabulary_repository.next_deck_position(parent_id)

    if update_default_note_type:
        if default_note_type_id is not None:
            resolved_nt = _resolve_note_type_for_user(user_id=user_id, note_type_id=default_note_type_id)
            guard_error = flashcards_share_service.validate_marketplace_note_type_for_deck(
                deck_id=deck.id,
                note_type_id=resolved_nt.id,
                user_id=user_id,
            )
            if guard_error:
                raise RequestValidationError(
                    guard_error,
                    field="default_note_type_id",
                    status=409,
                    code="DECK_SOURCE_NOTETYPE_MISMATCH",
                )
            deck.note_type_id = resolved_nt.id
        else:
            deck.note_type_id = None

    db.session.commit()
    return {
        "deck_id": int(deck.id),
        "name": deck.name,
        "description": deck.description,
        "parent_id": int(deck.parent_id) if deck.parent_id is not None else None,
        "position": int(deck.position or 0),
        "default_note_type": {"id": str(deck.note_type.id), "name": deck.note_type.name} if deck.note_type else None,
        "updated": True,
    }


def delete_deck(*, user_id: int, deck_id: int, confirm: bool = False) -> dict[str, Any]:
    """Delete a deck subtree owned by the user with safety confirmation guardrail."""
    deck = Deck.query.filter_by(id=deck_id, owner_user_id=user_id, deleted_at=None).first()
    if deck is None:
        raise RequestValidationError(
            f"Không tìm thấy deck ID {deck_id} của bạn.",
            field="deck_id",
            status=404,
            code="DECK_NOT_FOUND",
        )

    subtree_ids = _collect_deck_subtree_ids(deck.id)
    subdeck_count = max(0, len(subtree_ids) - 1)
    notes_count = Note.query.filter(Note.deck_id.in_(subtree_ids), Note.user_id == user_id).count()
    cards_count = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(subtree_ids), Note.user_id == user_id)
        .count()
    )

    if not confirm:
        return {
            "requires_confirmation": True,
            "action": "delete_deck",
            "deck_id": int(deck.id),
            "deck_name": deck.name,
            "impact": {
                "subdecks_to_delete": subdeck_count,
                "notes_to_delete": notes_count,
                "cards_to_delete": cards_count,
            },
            "warning": (
                f"⚠️ CẢNH BÁO XÓA DECK: Thao tác này sẽ xóa vĩnh viễn deck '{deck.name}' "
                f"cùng {subdeck_count} subdeck(s), {notes_count} note(s), {cards_count} card(s) và toàn bộ tiến độ học tập. "
                "AI PHẢI giải thích rõ các mất mát này cho người dùng và yêu cầu người dùng phê duyệt trước. "
                "Chỉ gọi lại tool với 'confirm=true' khi người dùng đã xác nhận đồng ý."
            ),
        }

    action = delete_deck_subtree(deck_obj=deck, user_id=user_id, is_admin=False, purge=False)
    return {
        "success": True,
        "deck_id": deck_id,
        "action": action,
        "deleted_subdecks_count": subdeck_count,
        "deleted_notes_count": notes_count,
        "deleted_cards_count": cards_count,
        "message": f"Deck '{deck.name}' (ID: {deck_id}) đã được xóa thành công ({action}).",
    }


