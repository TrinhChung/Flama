"""Dataset builder and SVG normalizer for Kanji and Hanzi stroke diagrams."""

from __future__ import annotations

import hashlib
import json
import os
import re
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any

from app.services.strokes.cjk_extractor import CjkExtractor, is_cjk_ideograph, to_simplified_chinese

_FORBIDDEN_TAGS = {"script", "foreignobject", "iframe", "object", "embed", "applet"}
_FORBIDDEN_ATTR_PREFIXES = ("on", "javascript:", "data:")


STROKE_COLORS = [
    "#e11d48",  # 1: Rose / Red
    "#2563eb",  # 2: Blue
    "#16a34a",  # 3: Green
    "#d97706",  # 4: Amber
    "#9333ea",  # 5: Purple
    "#0891b2",  # 6: Cyan
    "#ea580c",  # 7: Orange
    "#4f46e5",  # 8: Indigo
    "#059669",  # 9: Teal
    "#c026d3",  # 10: Fuchsia
]


def sanitize_stroke_svg(raw_svg: str, char_hex: str = "") -> str:
    """Sanitize, standardize, and animate an SVG string for stroke order rendering.

    - Strips dangerous tags (<script>, <foreignObject>, etc.).
    - Strips event handlers (onload, onclick, etc.).
    - Adds sequential stroke drawing animation (@keyframes) for Japanese KanjiVG and static SVGs.
    - Applies vibrant multi-color stroke palette for easy stroke component distinction.
    - Preserves stroke paths (<path>) and stroke numbers (<text>).
    - Ensures standard viewBox="0 0 109 109".
    - Adds standard class "flama-stroke-char".
    """
    if not raw_svg or not raw_svg.strip():
        return ""

    # Register XML namespaces so ElementTree does not rename tags or strip stroke paths
    try:
        ET.register_namespace("", "http://www.w3.org/2000/svg")
        ET.register_namespace("kvg", "https://kanjivg.tagaini.net/")
    except Exception:
        pass

    # Pre-clean any duplicate xmlns declaration from raw SVG
    cleaned_input = re.sub(r'\s+xmlns="[^"]*"', '', raw_svg)
    cleaned_input = re.sub(r'(<svg\b[^>]*?)(\s*>)', r'\1 xmlns="http://www.w3.org/2000/svg"\2', cleaned_input, count=1)

    # Parse XML safely
    try:
        root = ET.fromstring(cleaned_input)
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

    # Check if SVG already has MakeMeAHanzi animations
    is_makemeahanzi = False
    for style_node in root.iter():
        if style_node.tag.split("}")[-1].lower() == "style" and ("make-me-a-hanzi" in (style_node.text or "") or "keyframes0" in (style_node.text or "")):
            is_makemeahanzi = True
            break

    # If it's MakeMeAHanzi (Chinese), add crisp practice box grid, stroke order numbers,
    # and scope all clipPath and animation IDs with character's hex code to prevent ID collisions
    if is_makemeahanzi:
        # Determine unique prefix per character (e.g. mmah-4e0d) to prevent
        # cross-contamination of clip-paths when multiple SVGs exist on the same HTML page
        clean_hex = (char_hex or "").strip().lower()
        if not clean_hex:
            m_hex = re.search(r'data-hex="([a-f0-9]+)"', raw_svg, re.IGNORECASE)
            clean_hex = m_hex.group(1).lower() if m_hex else hashlib.md5(raw_svg.encode("utf-8")).hexdigest()[:6]
        prefix = f"mmah-{clean_hex}"

        # Scope IDs and clip-path URLs throughout the DOM
        for elem in root.iter():
            elem_id = elem.get("id", "")
            if elem_id.startswith("make-me-a-hanzi-"):
                elem.set("id", elem_id.replace("make-me-a-hanzi-", f"{prefix}-"))
            clip_attr = elem.get("clip-path", "")
            if "make-me-a-hanzi-" in clip_attr:
                elem.set("clip-path", clip_attr.replace("make-me-a-hanzi-", f"{prefix}-"))

        # Scope <style> keyframes and selectors inside SVG
        for style_node in root.iter():
            if style_node.tag.split("}")[-1].lower() == "style" and style_node.text:
                txt = style_node.text
                txt = txt.replace("make-me-a-hanzi-", f"{prefix}-")
                txt = re.sub(r"\bkeyframes(\d+)\b", rf"{prefix}-kf-\1", txt)
                style_node.text = txt

        # Remove old faint grid elements and previous number groups if present
        for child in list(root):
            if child.get("stroke") == "lightgray" or child.get("class") in {"flama-grid-box", "flama-mmah-numbers"}:
                root.remove(child)

        grid_group = ET.Element("{http://www.w3.org/2000/svg}g", {"class": "flama-grid-box", "fill": "none"})
        border_rect = ET.Element("{http://www.w3.org/2000/svg}rect", {
            "x": "8", "y": "8", "width": "1008", "height": "1008",
            "stroke": "#cbd5e1", "stroke-width": "3", "stroke-opacity": "0.7", "rx": "24",
        })
        grid_lines = ET.Element("{http://www.w3.org/2000/svg}path", {
            "d": "M 0 512 L 1024 512 M 512 0 L 512 1024 M 0 0 L 1024 1024 M 1024 0 L 0 1024",
            "stroke": "#e2e8f0", "stroke-width": "2.5", "stroke-dasharray": "10,10", "stroke-opacity": "0.8",
        })
        grid_group.append(border_rect)
        grid_group.append(grid_lines)
        root.insert(0, grid_group)

        # Extract centerline starting points and append stroke numbers (1, 2, 3...)
        stroke_points: list[tuple[int, float, float]] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag == "path":
                elem_id = elem.get("id", "")
                d_attr = elem.get("d", "")
                m_id = re.search(rf"{prefix}-animation-(\d+)", elem_id) or re.search(r"make-me-a-hanzi-animation-(\d+)", elem_id)
                if m_id and d_attr.strip().startswith("M"):
                    coords = re.findall(r"^M\s*([0-9.-]+)\s+([0-9.-]+)", d_attr.strip())
                    if coords:
                        stroke_idx = int(m_id.group(1))
                        x0, y0 = float(coords[0][0]), float(coords[0][1])
                        stroke_points.append((stroke_idx, x0, y0))

        if stroke_points:
            stroke_points.sort(key=lambda item: item[0])
            numbers_group = ET.Element("{http://www.w3.org/2000/svg}g", {
                "class": "flama-mmah-numbers",
                "style": "font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-weight: 900; font-size: 56px; paint-order: stroke fill; stroke: #ffffff; stroke-width: 10px; stroke-linejoin: round;",
            })
            for stroke_idx, x0, y0 in stroke_points:
                num_x = max(24, min(980, x0 - 18))
                num_y = max(48, min(980, 900 - y0 - 12))
                color = STROKE_COLORS[stroke_idx % len(STROKE_COLORS)]
                txt_elem = ET.Element("{http://www.w3.org/2000/svg}text", {
                    "x": f"{num_x:.0f}",
                    "y": f"{num_y:.0f}",
                    "fill": color,
                    "fill-opacity": "0.95",
                    "class": f"flama-stroke-num flama-sn-{stroke_idx+1}",
                })
                txt_elem.text = str(stroke_idx + 1)
                numbers_group.append(txt_elem)
            root.append(numbers_group)

    # If it's a KanjiVG or static SVG, apply smooth 1-shot sequential drawing & multi-color palette & practice grid
    if not is_makemeahanzi:
        # Remove existing generated style & bg layers
        for child in list(root):
            tag_name = child.tag.split("}")[-1].lower()
            if tag_name == "style" or child.get("class") == "flama-kvg-bg-layer":
                root.remove(child)

        paths: list[ET.Element] = []
        texts: list[ET.Element] = []
        for elem in root.iter():
            tag = elem.tag.split("}")[-1].lower()
            if tag == "path" and "d" in elem.attrib and elem.get("class") != "flama-kvg-bg":
                paths.append(elem)
            elif tag == "text":
                texts.append(elem)

        num_strokes = len(paths)
        if num_strokes > 0:
            stroke_dur = 0.45

            css_rules = [
                "/* Flama Sequential Stroke Order Animation (Single Run) & Multi-color Styling */",
                ":root {",
                "  --flama-stroke-width: 3.2px;",
                "  --flama-grid-color: #f1f5f9;",
                "  --flama-ghost-color: #e2e8f0;",
            ]
            for i, c in enumerate(STROKE_COLORS, 1):
                css_rules.append(f"  --flama-stroke-c{i}: {c};")
            css_rules.extend([
                "}",
                "@keyframes flama-kanjivg-dash {",
                "  0% { stroke-dashoffset: 100; opacity: 0.15; }",
                "  20% { opacity: 1; }",
                "  100% { stroke-dashoffset: 0; opacity: 1; }",
                "}",
                ".flama-kvg-bg { stroke: var(--flama-ghost-color, #e2e8f0); stroke-width: var(--flama-stroke-width, 3.2px); fill: none; stroke-linecap: round; stroke-linejoin: round; }",
                ".flama-kvg-stroke { fill: none; stroke-linecap: round; stroke-linejoin: round; }",
                ".flama-kvg-num { font-family: ui-monospace, SFMono-Regular, Menlo, monospace; font-size: 11px; font-weight: 800; paint-order: stroke fill; stroke: #ffffff; stroke-width: 2px; stroke-linejoin: round; }",
            ])

            # Create background guide layer with rounded border, grid & ghost paths
            bg_group = ET.Element("{http://www.w3.org/2000/svg}g", {"class": "flama-kvg-bg-layer", "fill": "none"})
            border_rect = ET.Element("{http://www.w3.org/2000/svg}rect", {
                "x": "2", "y": "2", "width": "105", "height": "105",
                "stroke": "#cbd5e1", "stroke-width": "0.8", "stroke-opacity": "0.7", "rx": "4",
            })
            grid_path = ET.Element("{http://www.w3.org/2000/svg}path", {
                "d": "M 0 54.5 L 109 54.5 M 54.5 0 L 54.5 109 M 0 0 L 109 109 M 109 0 L 0 109",
                "stroke": "#e2e8f0",
                "stroke-width": "0.6",
                "stroke-dasharray": "2,2",
                "stroke-opacity": "0.8",
                "fill": "none",
            })
            bg_group.append(border_rect)
            bg_group.append(grid_path)

            for p in paths:
                ghost = ET.Element("{http://www.w3.org/2000/svg}path", {
                    "d": p.get("d", ""),
                    "class": "flama-kvg-bg",
                })
                bg_group.append(ghost)

            # Style each stroke path with 1-shot sequential drawing animation and distinct color
            for idx, p in enumerate(paths):
                color_var = f"var(--flama-stroke-c{(idx % len(STROKE_COLORS)) + 1}, {STROKE_COLORS[idx % len(STROKE_COLORS)]})"
                delay = idx * stroke_dur
                p.set("class", f"flama-kvg-stroke flama-kvg-s{idx+1}")
                p.set("pathLength", "100")
                p.set("stroke-dasharray", "100")
                p.set("stroke-dashoffset", "100")
                p.set("style", f"stroke: {color_var}; stroke-width: var(--flama-stroke-width, 3.2px); animation: flama-kanjivg-dash {stroke_dur:.2f}s cubic-bezier(0.4, 0, 0.2, 1) {delay:.2f}s 1 forwards;")

            # Style stroke numbers with static fixed visibility and matching stroke colors
            for idx, txt in enumerate(texts):
                color_var = f"var(--flama-stroke-c{(idx % len(STROKE_COLORS)) + 1}, {STROKE_COLORS[idx % len(STROKE_COLORS)]})"
                txt.set("class", f"flama-kvg-num flama-kvg-n{idx+1}")
                txt.set("style", f"fill: {color_var}; fill-opacity: 0.95; paint-order: stroke fill; stroke: #ffffff; stroke-width: 2px;")

            style_elem = ET.Element("{http://www.w3.org/2000/svg}style", {"type": "text/css"})
            style_elem.text = "\n" + "\n".join(css_rules) + "\n"

            # Remove previous styles and insert new elements
            for child in list(root):
                if child.tag.split("}")[-1].lower() == "style":
                    root.remove(child)

            root.insert(0, style_elem)
            root.insert(1, bg_group)

    # Standardize root SVG attributes
    if not root.get("viewBox"):
        width = root.get("width", "109").replace("px", "")
        height = root.get("height", "109").replace("px", "")
        try:
            w_int, h_int = int(float(width)), int(float(height))
            root.set("viewBox", f"0 0 {w_int} {h_int}")
        except ValueError:
            root.set("viewBox", "0 0 109 109")

    # Ensure SVG has explicit 100% width and height so it scales to its parent container and never expands to 300px
    root.set("width", "100%")
    root.set("height", "100%")
    root.set("preserveAspectRatio", "xMidYMid meet")

    # Pop any manual xmlns attribute from root to prevent duplicate xmlns in XML output
    root.attrib.pop("xmlns", None)
    for key in list(root.attrib.keys()):
        if key.endswith("}xmlns") or key == "xmlns":
            del root.attrib[key]

    # Standardize root styling classes
    existing_class = root.get("class", "")
    if "flama-stroke-char" not in existing_class:
        root.set("class", f"flama-stroke-char {existing_class}".strip())

    return ET.tostring(root, encoding="utf-8").decode("utf-8")


def fetch_authentic_stroke_svg(char: str, locale: str = "ja") -> str | None:
    """Fetch authentic stroke diagram SVG (KanjiVG or MakeMeAHanzi) with stroke paths & stroke numbers.
    
    Preserves traditional vs simplified characters based on the character itself, as MakeMeAHanzi
    contains dedicated authentic stroke diagrams for both traditional (e.g. 國, 學) and simplified (e.g. 国, 学).
    """
    if not is_cjk_ideograph(char):
        return None

    norm_locale = str(locale or "ja").strip().lower()
    hex_code = CjkExtractor.char_to_hex(char)
    padded_hex = hex_code.zfill(5)
    cp = ord(char)

    # Primary URLs based on target locale
    urls: list[str] = []
    if "zh" in norm_locale:
        urls.extend([
            f"https://raw.githubusercontent.com/skishore/makemeahanzi/master/svgs/{cp}.svg",
            f"https://cdn.jsdelivr.net/gh/skishore/makemeahanzi@master/svgs/{cp}.svg",
            f"https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{padded_hex}.svg",
        ])
    else:
        urls.extend([
            f"https://raw.githubusercontent.com/KanjiVG/kanjivg/master/kanji/{padded_hex}.svg",
            f"https://cdn.jsdelivr.net/gh/KanjiVG/kanjivg@master/kanji/{padded_hex}.svg",
            f"https://raw.githubusercontent.com/skishore/makemeahanzi/master/svgs/{cp}.svg",
        ])

    for u in urls:
        try:
            req = urllib.request.Request(u, headers={"User-Agent": "Flama/1.0"})
            with urllib.request.urlopen(req, timeout=4.0) as resp:
                if resp.status == 200:
                    raw_data = resp.read().decode("utf-8", errors="ignore")
                    if "<path" in raw_data:
                        return sanitize_stroke_svg(raw_data, char_hex=hex_code)
        except Exception:
            continue

    return None


def generate_kanji_placeholder_svg(char: str, locale: str = "ja") -> str:
    """Generate a clean vector SVG for a Kanji/Hanzi when high-detail stroke data is not yet downloaded."""
    hex_code = CjkExtractor.char_to_hex(char)
    norm_locale = str(locale or "ja").strip().lower()
    if "zh-hant" in norm_locale or "tw" in norm_locale:
        font_stack = "'PingFang TC', 'Microsoft JhengHei', 'Noto Sans TC', sans-serif"
    elif "zh" in norm_locale:
        font_stack = "'PingFang SC', 'Microsoft YaHei', 'SimHei', 'Noto Sans SC', sans-serif"
    else:
        font_stack = "'Noto Sans CJK JP', 'Hiragino Sans', 'Yu Gothic', 'Meiryo', sans-serif"

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109" width="100%" height="100%" preserveAspectRatio="xMidYMid meet" class="flama-stroke-char" data-char="{char}" data-hex="{hex_code}">'
        f'<rect width="107" height="107" x="1" y="1" fill="none" stroke="#e2e8f0" stroke-width="1.5" stroke-dasharray="3 3" rx="8" />'
        f'<line x1="54.5" y1="1" x2="54.5" y2="108" stroke="#f1f5f9" stroke-width="1" stroke-dasharray="2 2" />'
        f'<line x1="1" y1="54.5" x2="108" y2="54.5" stroke="#f1f5f9" stroke-width="1" stroke-dasharray="2 2" />'
        f'<text x="54.5" y="78" font-family="{font_stack}" '
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
            sanitized = sanitize_stroke_svg(content, char_hex=raw_hex)
            # Write both unpadded and padded forms for maximum compatibility
            (dest / f"{raw_hex}.svg").write_text(sanitized, encoding="utf-8")
            if len(raw_hex) < 5:
                (dest / f"{raw_hex.zfill(5)}.svg").write_text(sanitized, encoding="utf-8")
            processed += 1
        except Exception:
            skipped += 1

    return {"processed": processed, "skipped": skipped}


JA_STARTER_KANJI = [
    "日", "本", "語", "勉", "強", "学", "校", "人", "大", "中", "小",
    "生", "先", "会", "社", "行", "来", "見", "聞", "食", "飲", "買",
    "書", "話", "読", "友", "達", "時", "分", "年", "月", "週", "今",
    "何", "漢", "字", "文", "習", "愛", "好", "上", "下", "左", "右",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千", "万",
    "国", "家", "山", "川", "木", "天", "気", "雨", "電", "車",
    "道", "手", "目", "口", "耳", "足", "心", "力", "名", "前", "後", "高", "新", "古",
    "白", "黒", "赤", "青", "花", "父", "母", "兄", "弟", "姉", "妹", "男", "女", "子",
    "出", "入", "休", "立", "買", "売", "春", "夏", "秋", "冬", "東", "西", "南", "北",
]

ZH_STARTER_HANZI = [
    "汉", "语", "话", "书", "买", "卖", "时", "间", "样", "谁", "现", "会", "听", "说", "读", "写",
    "认", "识", "见", "边", "远", "近", "进", "出", "门", "关", "开", "问", "题", "帮", "助",
    "给", "让", "岁", "钱", "块", "俩", "哪", "儿", "还", "过", "鸡", "蛋", "苹", "果", "鱼",
    "羊", "肉", "面", "条", "穿", "衣", "服", "视", "影", "脑", "钟", "点", "笔", "课", "练",
    "难", "易", "简", "单", "结", "束", "发", "经", "济", "动", "物", "园", "绿", "红", "蓝",
    "颜", "色", "欢", "迎", "宾", "馆", "银", "辆", "跑", "步", "跳", "飞", "机", "站", "坐",
    "船", "票", "房", "医", "院", "药", "病", "感", "冒", "身", "体", "运", "游", "泳", "球",
    "你", "我", "他", "她", "它", "好", "们", "的", "是", "不", "了", "在", "有", "个", "这",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千", "万",
    "大", "小", "多", "少", "冷", "热", "高", "新", "老", "朋", "友", "人", "男", "女", "子",
    "爱", "学", "习", "电", "车", "国", "家", "山", "水", "天", "气", "雨", "东", "西", "南", "北",
]

ZH_HANT_STARTER_HANZI = [
    "漢", "語", "話", "書", "買", "賣", "時", "間", "樣", "誰", "現", "會", "聽", "說", "讀", "寫",
    "認", "識", "見", "邊", "遠", "近", "進", "出", "門", "關", "開", "問", "題", "幫", "助",
    "給", "讓", "歲", "錢", "塊", "倆", "哪", "兒", "還", "過", "雞", "蛋", "蘋", "果", "魚",
    "羊", "肉", "麵", "條", "穿", "衣", "服", "視", "影", "腦", "鐘", "點", "筆", "課", "練",
    "難", "易", "簡", "單", "結", "束", "發", "經", "濟", "動", "物", "園", "綠", "紅", "藍",
    "顏", "色", "歡", "迎", "賓", "館", "銀", "輛", "跑", "步", "跳", "飛", "機", "站", "坐",
    "船", "票", "房", "醫", "院", "藥", "病", "感", "冒", "身", "體", "運", "遊", "泳", "球",
    "你", "我", "他", "她", "好", "們", "的", "是", "不", "了", "在", "有", "個", "這",
    "一", "二", "三", "四", "五", "六", "七", "八", "九", "十", "百", "千", "萬",
    "國", "家", "山", "川", "木", "天", "氣", "雨", "電", "車",
    "道", "手", "目", "口", "耳", "足", "心", "力", "名", "前", "後", "高", "新", "古",
    "白", "黑", "赤", "青", "花", "父", "母", "兄", "弟", "姊", "妹", "男", "女", "子",
    "東", "西", "南", "北", "春", "夏", "秋", "冬",
]

# Combined starter list
STARTER_CHARS = list(dict.fromkeys(JA_STARTER_KANJI + ZH_STARTER_HANZI + ZH_HANT_STARTER_HANZI))


def populate_starter_strokes(static_root: str | Path) -> dict[str, int]:
    """Populate starter Kanji & Hanzi stroke SVGs into static/strokes/ja, zh, and zh-hant."""
    root = Path(static_root)
    ja_dir = root / "strokes" / "ja"
    zh_dir = root / "strokes" / "zh"
    zh_hant_dir = root / "strokes" / "zh-hant"
    ja_dir.mkdir(parents=True, exist_ok=True)
    zh_dir.mkdir(parents=True, exist_ok=True)
    zh_hant_dir.mkdir(parents=True, exist_ok=True)

    total_created = 0

    # 1. JA
    for char in JA_STARTER_KANJI:
        if not is_cjk_ideograph(char):
            continue
        hex_unpadded = CjkExtractor.char_to_hex(char)
        hex_padded = CjkExtractor.char_to_hex(char, zero_pad=5)
        ja_file = ja_dir / f"{hex_unpadded}.svg"
        ja_content = fetch_authentic_stroke_svg(char, locale="ja") or generate_kanji_placeholder_svg(char, locale="ja")
        ja_file.write_text(ja_content, encoding="utf-8")
        (ja_dir / f"{hex_padded}.svg").write_text(ja_content, encoding="utf-8")
        total_created += 1

    # 2. ZH (Simplified)
    for char in ZH_STARTER_HANZI:
        if not is_cjk_ideograph(char):
            continue
        hex_unpadded = CjkExtractor.char_to_hex(char)
        hex_padded = CjkExtractor.char_to_hex(char, zero_pad=5)
        zh_file = zh_dir / f"{hex_unpadded}.svg"
        zh_content = fetch_authentic_stroke_svg(char, locale="zh") or generate_kanji_placeholder_svg(char, locale="zh")
        zh_file.write_text(zh_content, encoding="utf-8")
        (zh_dir / f"{hex_padded}.svg").write_text(zh_content, encoding="utf-8")
        total_created += 1

    # 3. ZH-HANT (Traditional)
    for char in ZH_HANT_STARTER_HANZI:
        if not is_cjk_ideograph(char):
            continue
        hex_unpadded = CjkExtractor.char_to_hex(char)
        hex_padded = CjkExtractor.char_to_hex(char, zero_pad=5)
        zh_hant_file = zh_hant_dir / f"{hex_unpadded}.svg"
        zh_hant_content = fetch_authentic_stroke_svg(char, locale="zh-hant") or generate_kanji_placeholder_svg(char, locale="zh-hant")
        zh_hant_file.write_text(zh_hant_content, encoding="utf-8")
        (zh_hant_dir / f"{hex_padded}.svg").write_text(zh_hant_content, encoding="utf-8")
        total_created += 1

    return {"processed": total_created, "ja": len(JA_STARTER_KANJI), "zh": len(ZH_STARTER_HANZI), "zh_hant": len(ZH_HANT_STARTER_HANZI)}
