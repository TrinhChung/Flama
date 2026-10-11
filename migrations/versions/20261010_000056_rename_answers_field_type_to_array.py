"""Rename the one-item-per-line field type from "answers" to "array".

Revision ID: 20261010_000056
Revises: 20261007_000055
Create Date: 2026-10-10 00:00:56

The type shipped as "answers" (typed answers) and is now a general list type.
Only the type name changes: field values, template sources and version content
hashes (front, back and CSS only) are untouched. Both columns are non-native
enums (VARCHAR(8), no CHECK constraint), so no DDL is needed. Production had no
"answers" row when this was written; the migration is idempotent either way.
"""

from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa


revision = "20261010_000056"
down_revision = "20261007_000055"
branch_labels = None
depends_on = None

FIELD_TYPE_TABLES = ("field_defs", "deck_clone_added_field_defs")
INPUT_SCHEMA_TABLES = ("templates", "template_versions")


def _rename(old: str, new: str) -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    for table in FIELD_TYPE_TABLES:
        if inspector.has_table(table):
            bind.execute(sa.text(f"UPDATE {table} SET field_type = :new WHERE field_type = :old"), {"new": new, "old": old})
    for table in INPUT_SCHEMA_TABLES:
        if not inspector.has_table(table):
            continue
        rows = bind.execute(
            sa.text(f"SELECT id, input_schema FROM {table} WHERE CAST(input_schema AS CHAR) LIKE :pattern"),
            {"pattern": f'%"{old}"%'},
        ).fetchall()
        for row_id, raw in rows:
            schema = json.loads(raw) if isinstance(raw, (str, bytes)) else raw
            if not isinstance(schema, list):
                continue
            changed = False
            for item in schema:
                if isinstance(item, dict) and item.get("type") == old:
                    item["type"] = new
                    changed = True
            if changed:
                bind.execute(
                    sa.text(f"UPDATE {table} SET input_schema = :schema WHERE id = :id"),
                    {"schema": json.dumps(schema, ensure_ascii=False), "id": row_id},
                )


def upgrade() -> None:
    _rename("answers", "array")


def downgrade() -> None:
    _rename("array", "answers")
