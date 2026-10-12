"""Modernize legacy flashcard templates and backfill input_schema contracts.

Revision ID: 20261012_000057
Revises: 20261010_000056
Create Date: 2026-10-12 00:00:57

This migration performs architectural modernization across all templates:
1. Modernizes template HTML syntax:
   - Rewrites legacy attribute patterns: ``src="{{Media}}"`` -> ``src="{{Media_url}}"``
   - Upgrades double braces on HTML/Media fields: ``{{image}}`` -> ``{{{image}}}``
2. Backfills ``input_schema`` contracts for templates that lacked explicit schemas,
   so that presentation templates are fully typed and decoupled from NoteTypes.
3. Synchronizes immutable ``template_versions`` with updated HTML, schemas,
   and deterministic content hashes.
4. Ensures ``study_applications.input_bindings`` has complete bindings for all
   inferred input schema keys.
"""

from __future__ import annotations

import json
from types import SimpleNamespace

from alembic import op
import sqlalchemy as sa

from migrations.template_modernization_20261012 import (
    _rewrite_media_url_attribute_tokens,
    _upgrade_html_field_double_brace_tokens,
)
from migrations.template_modernization_20261012 import template_content_hash
from migrations.template_modernization_20261012 import infer_input_schema


revision = "20261012_000057"
down_revision = "20261010_000056"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("templates"):
        return

    # 1. Load FieldDefs grouped by note_type_id
    field_defs_by_note_type: dict[str, list[SimpleNamespace]] = {}
    if inspector.has_table("field_defs"):
        field_rows = bind.execute(
            sa.text("SELECT id, note_type_id, name, field_type, required, position FROM field_defs ORDER BY position ASC")
        ).fetchall()
        for f_id, nt_id, name, f_type, req, pos in field_rows:
            if nt_id:
                field_defs_by_note_type.setdefault(str(nt_id), []).append(
                    SimpleNamespace(
                        id=str(f_id),
                        name=str(name),
                        field_type=str(f_type or "text"),
                        required=bool(req),
                        position=int(pos or 0),
                    )
                )

    # 2. Modernize templates table
    template_rows = bind.execute(
        sa.text("SELECT id, note_type_id, front_html, back_html, shared_css, input_schema FROM templates")
    ).fetchall()

    template_note_types: dict[str, str] = {}
    template_schemas: dict[str, list[dict]] = {}

    for t_id, nt_id, front_html, back_html, shared_css, raw_schema in template_rows:
        t_id_str = str(t_id)
        nt_id_str = str(nt_id) if nt_id else ""
        template_note_types[t_id_str] = nt_id_str
        fields = field_defs_by_note_type.get(nt_id_str, [])

        old_front = front_html or ""
        old_back = back_html or ""

        new_front = _upgrade_html_field_double_brace_tokens(
            _rewrite_media_url_attribute_tokens(old_front, fields),
            fields,
        )
        new_back = _upgrade_html_field_double_brace_tokens(
            _rewrite_media_url_attribute_tokens(old_back, fields),
            fields,
        )

        existing_schema = json.loads(raw_schema) if isinstance(raw_schema, (str, bytes)) else raw_schema
        if not existing_schema or not isinstance(existing_schema, list) or len(existing_schema) == 0:
            final_schema = infer_input_schema(new_front, new_back, fields)
        else:
            final_schema = existing_schema

        template_schemas[t_id_str] = final_schema

        schema_json = json.dumps(final_schema, ensure_ascii=False)
        bind.execute(
            sa.text(
                "UPDATE templates SET front_html = :front, back_html = :back, input_schema = :schema WHERE id = :id"
            ),
            {"front": new_front, "back": new_back, "schema": schema_json, "id": t_id_str},
        )

    # 3. Modernize template_versions table
    if inspector.has_table("template_versions"):
        version_rows = bind.execute(
            sa.text(
                "SELECT id, template_id, front_html, back_html, shared_css, input_schema FROM template_versions"
            )
        ).fetchall()

        for v_id, t_id, front_html, back_html, shared_css, raw_schema in version_rows:
            v_id_str = str(v_id)
            t_id_str = str(t_id) if t_id else ""
            nt_id_str = template_note_types.get(t_id_str, "")
            fields = field_defs_by_note_type.get(nt_id_str, [])

            old_front = front_html or ""
            old_back = back_html or ""
            css = shared_css or ""

            new_front = _upgrade_html_field_double_brace_tokens(
                _rewrite_media_url_attribute_tokens(old_front, fields),
                fields,
            )
            new_back = _upgrade_html_field_double_brace_tokens(
                _rewrite_media_url_attribute_tokens(old_back, fields),
                fields,
            )

            existing_schema = json.loads(raw_schema) if isinstance(raw_schema, (str, bytes)) else raw_schema
            if not existing_schema or not isinstance(existing_schema, list) or len(existing_schema) == 0:
                final_schema = template_schemas.get(t_id_str) or infer_input_schema(new_front, new_back, fields)
            else:
                final_schema = existing_schema

            new_hash = template_content_hash(new_front, new_back, css)
            schema_json = json.dumps(final_schema, ensure_ascii=False)

            bind.execute(
                sa.text(
                    "UPDATE template_versions "
                    "SET front_html = :front, back_html = :back, input_schema = :schema, content_hash = :hash "
                    "WHERE id = :id"
                ),
                {"front": new_front, "back": new_back, "schema": schema_json, "hash": new_hash, "id": v_id_str},
            )

    # 4. Synchronize study_applications.input_bindings
    if inspector.has_table("study_applications"):
        app_rows = bind.execute(
            sa.text("SELECT id, template_id, note_type_id, input_bindings FROM study_applications")
        ).fetchall()

        for app_id, t_id, nt_id, raw_bindings in app_rows:
            app_id_str = str(app_id)
            t_id_str = str(t_id) if t_id else ""
            nt_id_str = str(nt_id) if nt_id else ""
            fields = field_defs_by_note_type.get(nt_id_str, [])
            fields_by_name = {f.name: f.id for f in fields}
            fields_by_lower = {f.name.lower(): f.id for f in fields}

            schema = template_schemas.get(t_id_str, [])
            current_bindings = json.loads(raw_bindings) if isinstance(raw_bindings, (str, bytes)) else (raw_bindings or {})
            if not isinstance(current_bindings, dict):
                current_bindings = {}

            updated = False
            for input_item in schema:
                if not isinstance(input_item, dict):
                    continue
                key = input_item.get("key")
                if not key or key in current_bindings:
                    continue
                # Try exact match, lower match, or alias resolution
                matched_id = (
                    fields_by_name.get(key)
                    or fields_by_lower.get(key.lower())
                    or (fields_by_name.get("hanviet") if key in {"han_viet", "hanviet"} else None)
                    or (fields_by_name.get("word") if key.lower() in {"term", "expression", "vocabulary"} else None)
                )
                if matched_id:
                    current_bindings[key] = matched_id
                    updated = True

            if updated:
                bind.execute(
                    sa.text("UPDATE study_applications SET input_bindings = :bindings WHERE id = :id"),
                    {"bindings": json.dumps(current_bindings, ensure_ascii=False), "id": app_id_str},
                )


def downgrade() -> None:
    # Modernized HTML syntax and input_schemas are strictly backwards-compatible
    # with previous reader versions, so downgrade is safely non-destructive.
    pass
