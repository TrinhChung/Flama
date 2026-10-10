"""Field types a NoteType field can have — the single list models and services share.

Order is the display order. The column stays a non-native Enum (VARCHAR sized to
the longest value, no CHECK constraint), so adding a value of at most eight
characters needs no migration.

``answers`` stores one accepted answer per line for the typing Study mode. It
is plain text everywhere else (rendering, search, import); only the explicit
conversion endpoint may turn an existing field into it.
"""

ANSWERS_FIELD_TYPE = "answers"
FIELD_TYPES = ("text", "richtext", "markdown", "image", "audio", "diagram", ANSWERS_FIELD_TYPE)
