"""Field types a NoteType field can have — the single list models and services share.

Order is the display order. The column stays a non-native Enum (VARCHAR sized to
the longest value, no CHECK constraint), so adding a value of at most eight
characters needs no migration.

``array`` stores a list of plain-text items, one per line (accepted answers,
choices, …; a template decides what the items mean). It is plain text
everywhere else (rendering, search, import); only the explicit conversion
endpoint may turn an existing field into it. Named ``answers`` until 2026-10-10
(migration 20261010_000056 renames stored values).
"""

ARRAY_FIELD_TYPE = "array"
FIELD_TYPES = ("text", "richtext", "markdown", "image", "audio", "diagram", ARRAY_FIELD_TYPE)
