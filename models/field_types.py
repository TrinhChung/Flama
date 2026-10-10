"""Field types a NoteType field can have — the single list models and services share.

Order is the display order. The column stays a non-native Enum (VARCHAR sized to
the longest value, no CHECK constraint), so adding a value of at most eight
characters needs no migration.
"""

FIELD_TYPES = ("text", "richtext", "markdown", "image", "audio", "diagram")
