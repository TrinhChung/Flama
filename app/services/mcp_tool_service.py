"""Minimal MCP tool execution service for authenticated deck access."""

from __future__ import annotations

import json

from app.repositories import vocabulary_repository

MCP_PROTOCOL_VERSION = "2025-11-25"
LIST_MY_DECKS_TOOL_NAME = "list_my_decks"


def _compact_description(raw_value: str | None, *, max_length: int = 200) -> str | None:
    normalized = " ".join(str(raw_value or "").split())
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def list_my_decks(*, user_id: int) -> list[dict[str, Any]]:
    """Return a compact list of decks owned by the current authenticated user."""
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
        }

        description = _compact_description(deck_obj.description)
        if description:
            item["description"] = description
        if deck_obj.created_at is not None:
            item["created_at"] = deck_obj.created_at.isoformat()

        payload_items.append(item)

    return payload_items


def build_list_my_decks_tool_result(*, user_id: int) -> dict[str, Any]:
    """Build an MCP-compatible tool result for list_my_decks."""
    structured_content = {
        "decks": list_my_decks(user_id=user_id),
    }
    return {
        "content": [
            {
                "type": "text",
                "text": json.dumps(structured_content, ensure_ascii=False),
            }
        ],
        "structuredContent": structured_content,
    }
