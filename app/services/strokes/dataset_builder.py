"""Dataset builder and SVG normalizer for Kanji and Hanzi stroke diagrams."""

from __future__ import annotations

import json
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from app.services.strokes.cjk_extractor import CjkExtractor, is_cjk_ideograph

_FORBIDDEN_TAGS = {"script", "foreignobject", "iframe", "object", "embed", "applet"}
_FORBIDDEN_ATTR_PREFIXES = ("on", "javascript:", "data:")


def sanitize_stroke_svg(raw_svg: str) -> str:
    """Sanitize and standardize an SVG string for stroke order rendering.

    - Strips dangerous tags (<script>, <foreignObject>, etc.).
    - Strips event handlers (onload, onclick, etc.).
    - Ensures standard viewBox="0 0 109 109".
    - Adds standard class "flama-stroke-char".
    """
    if not raw_svg or not raw_svg.strip():
        return ""

    # Parse XML safely
    try:
        root = ET.fromstring(raw_svg)
    except ET.ParseError:
        # Fallback regex strip if XML parsing fails due to unclosed comments/entities
        cleaned = re.sub(r"(?is)<script\b[^>]*>.*?</script>", "", raw_svg)
        cleaned = re.sub(r"(?is)on\w+\s*=\s*['\"][^'\"]*['\"]", "", cleaned)
        return cleaned.strip()

    def _clean_node(elem: ET.Element) -> None:
        tag_name = elem.tag.split("}")[-1].lower()
        if tag_name in _FORBIDDEN_TAGS:
            elem.clear()
            return

        # Clean attributes
        attrib_keys = list(elem.attrib.keys())
        for key in attrib_keys:
            lowered_key = key.lower()
            if any(lowered_key.startswith(pref) for pref in _FORBIDDEN_ATTR_PREFIXES):
                del elem.attrib[key]
            val = str(elem.attrib.get(key, "")).strip().lower()
            if val.startswith("javascript:") or val.startswith("vbscript:"):
                del elem.attrib[key]

        # Recurse children
        for child in list(elem):
            _clean_node(child)
            # Remove empty pruned elements
            child_tag = child.tag.split("}")[-1].lower()
            if child_tag in _FORBIDDEN_TAGS:
                elem.remove(child)

    _clean_node(root)

    # Standardize root SVG attributes
    if not root.get("viewBox"):
        width = root.get("width", "109").replace("px", "")
        height = root.get("height", "109").replace("px", "")
        try:
            w_int, h_int = int(float(width)), int(float(height))
            root.set("viewBox", f"0 0 {w_int} {h_int}")
        except ValueError:
            root.set("viewBox", "0 0 109 109")

    # Set root namespace and styling classes
    root.set("xmlns", "http://www.w3.org/2000/svg")
    existing_class = root.get("class", "")
    if "flama-stroke-char" not in existing_class:
        root.set("class", f"flama-stroke-char {existing_class}".strip())

    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def generate_kanji_placeholder_svg(char: str) -> str:
    """Generate a clean vector SVG for a Kanji/Hanzi when high-detail stroke data is not yet downloaded."""
    hex_code = CjkExtractor.char_to_hex(char)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109" class="flama-stroke-char" data-char="{char}" data-hex="{hex_code}">'
        f'<rect width="107" height="107" x="1" y="1" fill="none" stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="3 3" rx="8" />'
        f'<line x1="54.5" y1="1" x2="54.5" y2="108" stroke="#f1f5f9" stroke-width="1" stroke-dasharray="2 2" />'
        f'<line x1="1" y1="54.5" x2="108" y2="54.5" stroke="#f1f5f9" stroke-width="1" stroke-dasharray="2 2" />'
        f'<text x="54.5" y="78" font-family="\'Noto Sans CJK JP\', \'Hiragino Sans\', \'PingFang SC\', sans-serif" '
        f'font-size="64" text-anchor="middle" fill="#1e293b" font-weight="500">{char}</text>'
        f'</svg>'
    )


def build_dataset_from_directory(
    source_dir: str | Path,
    target_dir: str | Path,
    locale: str = "ja",
) -> dict[str, int]:
    """Process an existing directory of KanjiVG or MakeMeAHanzi SVG files.

    Normalizes filenames to both {hex}.svg and {05hex}.svg, sanitizes content,
    and writes to target_dir.
    """
    src = Path(source_dir)
    dest = Path(target_dir)
    dest.mkdir(parents=True, exist_ok=True)

    processed = 0
    skipped = 0

    if not src.exists():
        return {"processed": 0, "skipped": 0, "error": 1}

    for svg_path in src.glob("**/*.svg"):
        stem = svg_path.stem.lower()
        # KanjiVG uses e.g. '052c9'
        hex_match = re.match(r"^0*([a-f0-9]{4,6})$", stem)
        if not hex_match:
            skipped += 1
            continue

        raw_hex = hex_match.group(1)
        try:
            content = svg_path.read_text(encoding="utf-8", errors="ignore")
            sanitized = sanitize_stroke_svg(content)
            # Write both unpadded and padded forms for maximum compatibility
            (dest / f"{raw_hex}.svg").write_text(sanitized, encoding="utf-8")
            if len(raw_hex) < 5:
                (dest / f"{raw_hex.zfill(5)}.svg").write_text(sanitized, encoding="utf-8")
            processed += 1
        except Exception:
            skipped += 1

    return {"processed": processed, "skipped": skipped}


def populate_starter_strokes(static_root: str | Path) -> dict[str, int]:
    """Populate starter Kanji & Hanzi stroke SVGs into static/strokes/ja and static/strokes/zh."""
    root = Path(static_root)
    ja_dir = root / "strokes" / "ja"
    zh_dir = root / "strokes" / "zh"
    ja_dir.mkdir(parents=True, exist_ok=True)
    zh_dir.mkdir(parents=True, exist_ok=True)

    # Core high frequency Kanji & Hanzi
    starter_chars = [
        "日", "本", "語", "勉", "強", "学", "校", "人", "大", "中", "小",
        "生", "先", "会", "社", "行", "来", "見", "聞", "食", "飲", "買",
        "書", "話", "読", "友", "達", "時", "分", "年", "月", "週", "今",
        "何", "漢", "字", "文", "習", "愛", "你", "我", "他", "她", "好",
        "们", "的", "是", "不", "了", "在", "有", "个", "这", "上", "一",
        "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千", "万",
    ]

    total_created = 0
    for char in starter_chars:
        if not is_cjk_ideograph(char):
            continue
        hex_unpadded = CjkExtractor.char_to_hex(char)
        hex_padded = CjkExtractor.char_to_hex(char, zero_pad=5)
        svg_content = generate_kanji_placeholder_svg(char)

        # JA
        ja_file = ja_dir / f"{hex_unpadded}.svg"
        if not ja_file.exists():
            ja_file.write_text(svg_content, encoding="utf-8")
            (ja_dir / f"{hex_padded}.svg").write_text(svg_content, encoding="utf-8")
            total_created += 1

        # ZH
        zh_file = zh_dir / f"{hex_unpadded}.svg"
        if not zh_file.exists():
            zh_file.write_text(svg_content, encoding="utf-8")
            (zh_dir / f"{hex_padded}.svg").write_text(svg_content, encoding="utf-8")

    return {"starter_kanji_count": len(starter_chars), "created": total_created}
