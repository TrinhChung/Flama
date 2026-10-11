"""Field types a NoteType field can have — the single list models and services share.

Order is the display order. The column stays a non-native Enum (VARCHAR sized to
the longest value, no CHECK constraint), so adding a value of at most eight
characters needs no migration.

``array`` stores a JSON list of plain-text items (nested lists allowed) in
``notes.field_values``; values written before 2026-10-11 may still be one item
per line until they are migrated. Renderers hand a list to Mustache unchanged:
the template iterates it with ``{{#field}}...{{/field}}`` or its own
``<script>``. Flama only imports from Anki and never exports to it. Named
``answers`` until 2026-10-10 (migration 20261010_000056 renames stored values).
"""

from typing import Any

ARRAY_FIELD_TYPE = "array"
FIELD_TYPES = ("text", "richtext", "markdown", "image", "audio", "diagram", ARRAY_FIELD_TYPE)


def field_value_text(value: Any) -> str:
    """Plain text of a stored field value; array items go one per line."""
    if value is None:
        return ""
    if isinstance(value, list):
        return "\n".join(field_value_text(item) for item in value)
    return str(value)


def stored_field_value(value: Any) -> Any:
    """A stored field value as text, except an ``array`` list, which stays a list."""
    if isinstance(value, list):
        return value
    return "" if value is None else str(value)
