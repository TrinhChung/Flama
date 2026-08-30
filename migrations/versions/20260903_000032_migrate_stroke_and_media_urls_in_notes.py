"""migrate stroke and media urls in notes

Revision ID: 20260903_000032
Revises: 20260902_000031
Create Date: 2026-09-03 00:00:32
"""

from __future__ import annotations

import json
import re
from alembic import op
import sqlalchemy as sa


revision = "20260903_000032"
down_revision = "20260902_000031"
branch_labels = None
depends_on = None


_STROKE_KEY_RE = re.compile(r"^stroke_[a-z0-9_]+_[a-f0-9]{4,6}$", re.IGNORECASE)
_STROKE_URL_NO_EXT_RE = re.compile(r"^/media/library/(stroke_[a-z0-9_]+_[a-f0-9]{4,6})$", re.IGNORECASE)
_STROKE_HTML_NO_EXT_RE = re.compile(r"/media/library/(stroke_[a-z0-9_]+_[a-f0-9]{4,6})(?!\.svg)", re.IGNORECASE)
_UUID_RE = re.compile(r"^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$", re.IGNORECASE)


def _normalize_field_value(val: str, asset_lookup: dict[str, str]) -> tuple[str, bool]:
    if not isinstance(val, str) or not val.strip():
        return val, False
    
    trimmed = val.strip()
    
    # 1. Raw stroke key (e.g. stroke_ja_65e5)
    if _STROKE_KEY_RE.match(trimmed):
        return f"/media/library/{trimmed}.svg", True
    
    # 2. Stroke URL without extension (e.g. /media/library/stroke_ja_65e5)
    m = _STROKE_URL_NO_EXT_RE.match(trimmed)
    if m:
        return f"/media/library/{m.group(1)}.svg", True
    
    # 3. HTML / SVG embed snippet containing /media/library/stroke_... without .svg
    if "/media/library/stroke_" in trimmed and ".svg" not in trimmed:
        new_val = _STROKE_HTML_NO_EXT_RE.sub(r"/media/library/\1.svg", trimmed)
        if new_val != trimmed:
            return new_val, True
    
    # 4. Raw MediaAsset UUID in media fields (e.g. e33ad045-29e0-4db9-938f-224f45a24cbf)
    if _UUID_RE.match(trimmed) and trimmed in asset_lookup:
        return asset_lookup[trimmed], True
            
    return val, False


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if not inspector.has_table("notes"):
        return
    
    columns = {col["name"] for col in inspector.get_columns("notes")}
    if "field_values" not in columns:
        return

    # Build asset lookup if media_assets exists
    asset_lookup: dict[str, str] = {}
    if inspector.has_table("media_assets"):
        asset_rows = bind.execute(
            sa.text("SELECT id, filename FROM media_assets WHERE filename IS NOT NULL AND filename != ''")
        ).fetchall()
        for a_id, a_fn in asset_rows:
            if a_id and a_fn:
                asset_lookup[str(a_id)] = str(a_fn)

    # Select notes with non-null field_values
    rows = bind.execute(
        sa.text("SELECT id, field_values FROM notes WHERE field_values IS NOT NULL")
    ).fetchall()

    for row in rows:
        note_id = row[0]
        raw_fv = row[1]
        if not raw_fv:
            continue
        
        fv_dict: dict | None = None
        if isinstance(raw_fv, dict):
            fv_dict = dict(raw_fv)
        elif isinstance(raw_fv, str):
            try:
                fv_dict = json.loads(raw_fv)
            except Exception:
                continue
        
        if not isinstance(fv_dict, dict):
            continue

        changed = False
        for k, v in list(fv_dict.items()):
            if isinstance(v, str):
                new_v, was_modified = _normalize_field_value(v, asset_lookup)
                if was_modified:
                    fv_dict[k] = new_v
                    changed = True

        if changed:
            serialized = json.dumps(fv_dict, ensure_ascii=False)
            bind.execute(
                sa.text("UPDATE notes SET field_values = :fv WHERE id = :id"),
                {"fv": serialized, "id": note_id},
            )


def downgrade() -> None:
    pass
