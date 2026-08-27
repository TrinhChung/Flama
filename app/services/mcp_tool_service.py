"""MCP tool execution service (backward-compatibility facade).

All implementations have been refactored into domain-focused submodules in `app.services.mcp`.
"""

from app.services.mcp import *
from app.services.mcp import (
    _compact_description,
    _wrap_tool_result,
    _wrap_tool_error,
    _resolve_deck_for_user,
    _build_deck_full_path,
    _resolve_note_type_for_user,
    _owned_note_type_for_mutation,
    _auto_crawl_note_fields,
    _ensure_note_tags_version_safe,
    _detect_destructive_note_type_changes,
)
