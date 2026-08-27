"""MCP protocol response helpers extracted from ``mcp_tool_service.py``.

These helpers wrap structured content / errors into the canonical
MCP ``CallToolResult`` envelope used by all MCP tool implementations.
"""

from __future__ import annotations

import json
from typing import Any


def compact_description(raw_value: str | None, *, max_length: int = 200) -> str | None:
    """Collapse whitespace and truncate a description string.

    Returns ``None`` when the input is empty/None.
    """
    normalized = " ".join(str(raw_value or "").split())
    if not normalized:
        return None
    if len(normalized) <= max_length:
        return normalized
    return normalized[: max_length - 3].rstrip() + "..."


def wrap_tool_result(structured_content: dict[str, Any], *, is_error: bool = False) -> dict[str, Any]:
    """Wrap structured content in standard MCP ``content`` + ``structuredContent`` envelope."""
    if is_error:
        error_info = structured_content.get("error") if isinstance(structured_content, dict) else None
        error_msg = error_info.get("message") if isinstance(error_info, dict) else str(structured_content)
        text_content = error_msg or json.dumps(structured_content, ensure_ascii=False, indent=2)
    else:
        text_content = json.dumps(structured_content, ensure_ascii=False, indent=2)

    result: dict[str, Any] = {
        "content": [
            {
                "type": "text",
                "text": text_content,
            }
        ],
        "structuredContent": structured_content,
    }
    if is_error:
        result["isError"] = True
    return result


def wrap_tool_error(
    exc: Exception | str,
    *,
    code: str | None = None,
    field: str | None = None,
) -> dict[str, Any]:
    """Wrap a tool execution error in a standard MCP ``CallToolResult`` with ``isError=True``.

    Supports ``RequestValidationError`` (which carries its own ``code`` / ``field``)
    as well as generic exceptions and plain strings.
    """
    # Detect RequestValidationError by attribute check to avoid hard import coupling.
    exc_code = getattr(exc, "code", None)
    exc_field = getattr(exc, "field", None)

    error_payload = {
        "error": {
            "code": exc_code or code or "TOOL_ERROR",
            "message": str(exc),
            "field": exc_field or field,
        }
    }
    return {
        "content": [
            {
                "type": "text",
                "text": error_payload["error"]["message"],
            }
        ],
        "isError": True,
        "structuredContent": error_payload,
    }
