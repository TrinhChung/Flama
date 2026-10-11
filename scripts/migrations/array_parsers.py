"""Reviewed legacy separators, used only by the one-off data migration."""

import re
import unicodedata
from typing import List, Optional, Set

OPENING_BRACKETS = '([（［【「『{｛'
CLOSING_BRACKETS = ')]）］】」』}｝'

BRACKET_PAIRS = {
    '(': ')',
    '（': '）',
    '[': ']',
    '［': '］',
    '【': '】',
    '「': '」',
    '『': '』',
    '{': '}',
    '｛': '｝',
}

HTML_TAG_RE = re.compile(r'<\s*/?\s*[a-zA-Z!][^>]*>')
SOUND_TAG_RE = re.compile(r'\[sound:[^\]]*\]', re.IGNORECASE)
LONG_ITEM_THRESHOLD = 80


# ============================================================================
# Normalization & Delimiter Parsing Rules
# ============================================================================

def clean_html_and_newlines(raw: str) -> str:
    """Normalize newlines, convert <br> tags to newlines, and drop sound tags."""
    if not raw:
        return ""
    text = raw.replace('\r\n', '\n').replace('\r', '\n')
    text = re.sub(r'<br\s*/?>', '\n', text, flags=re.IGNORECASE)
    text = re.sub(r'</?(div|p|li)\b[^>]*>', '\n', text, flags=re.IGNORECASE)
    text = SOUND_TAG_RE.sub('', text)
    return text


def split_outside_brackets(
    text: str,
    separator_pattern: str,
    opening_chars: str = OPENING_BRACKETS,
    closing_chars: str = CLOSING_BRACKETS,
) -> List[str]:
    """Split text on separator_pattern only when outside bracket pairs.
    
    Shields nested CJK and ASCII brackets so delimiters inside brackets
    (e.g., '(giấy, ảnh, vé)') are never split.
    """
    if not text:
        return []

    sep_regex = re.compile(separator_pattern)
    parts: List[str] = []
    depth = 0
    start = 0
    i = 0
    n = len(text)

    while i < n:
        char = text[i]
        if char in opening_chars:
            depth += 1
        elif char in closing_chars:
            depth = max(0, depth - 1)
        elif depth == 0:
            m = sep_regex.match(text, i)
            if m and len(m.group(0)) > 0:
                parts.append(text[start:i])
                i += len(m.group(0))
                start = i
                continue
        i += 1

    parts.append(text[start:])
    return parts


def check_unmatched_brackets(text: str) -> bool:
    """Check if text contains unmatched opening or closing brackets."""
    stack: List[Tuple[str, str]] = []
    for char in text:
        if char in BRACKET_PAIRS:
            stack.append((char, BRACKET_PAIRS[char]))
        elif char in BRACKET_PAIRS.values():
            if stack and stack[-1][1] == char:
                stack.pop()
            else:
                return True
    return len(stack) > 0


def normalize_item(item: str) -> str:
    """Normalize a single array item: NFC normalization, whitespace collapse, trim."""
    nfc = unicodedata.normalize('NFC', item)
    collapsed = re.sub(r'[ \t]+', ' ', nfc)
    return collapsed.strip()


def split_reading(raw: Optional[str]) -> List[str]:
    """Split reading or Phiên âm.
    
    Delimiters: /, ,, 、, \\n
    Whitespace trimmed, preserves kana/kanji/romaji/pinyin.
    """
    if not raw:
        return []
    cleaned = clean_html_and_newlines(raw)
    raw_parts = re.split(r'[/，,、\n]+', cleaned)
    items: List[str] = []
    for part in raw_parts:
        norm = normalize_item(part)
        if norm:
            items.append(norm)
    return items


def split_translation_vi(raw: Optional[str]) -> List[str]:
    """Split translation_vi in Flama Standard Vocabulary.
    
    Delimiters: $, \\n
    Protects parenthetical content (...) and （...） from splitting.
    Commas are intentionally NOT split as they are explanatory punctuation.
    """
    if not raw:
        return []
    cleaned = clean_html_and_newlines(raw)
    raw_parts = split_outside_brackets(cleaned, r'[\$\n]+')
    items: List[str] = []
    for part in raw_parts:
        norm = normalize_item(part)
        if norm:
            items.append(norm)
    return items


def split_meaning_en4everyone(raw: Optional[str]) -> List[str]:
    """Split Meaning in En4Everyone.
    
    Delimiters: [;；], \\n
    Protects parenthetical content.
    """
    if not raw:
        return []
    cleaned = clean_html_and_newlines(raw)
    raw_parts = split_outside_brackets(cleaned, r'[;；\n]+')
    items: List[str] = []
    for part in raw_parts:
        norm = normalize_item(part)
        if norm:
            items.append(norm)
    return items


def split_nghia_kanji_n3(raw: Optional[str]) -> List[str]:
    """Split Nghĩa in Kanji_N3.
    
    Delimiters: ,, ，, \\n
    Protects parenthetical content.
    """
    if not raw:
        return []
    cleaned = clean_html_and_newlines(raw)
    raw_parts = split_outside_brackets(cleaned, r'[,，\n]+')
    items: List[str] = []
    for part in raw_parts:
        norm = normalize_item(part)
        if norm:
            items.append(norm)
    return items


def split_paired_list(raw: Optional[str], preserve_duplicates: bool = True) -> List[str]:
    """Split paired list in En4Everyone (Collocation, Synonym, Antonym & VI pairs).
    
    Delimiters: [;；], \\n
    CRUCIAL: preserve_duplicates=True MUST be enforced to guarantee 1-to-1 index alignment
    between English and Vietnamese pair items.
    """
    if not raw:
        return []
    cleaned = clean_html_and_newlines(raw)
    raw_parts = split_outside_brackets(cleaned, r'[;；\n]+')
    items: List[str] = []
    seen: Set[str] = set()
    for part in raw_parts:
        norm = normalize_item(part)
        if not norm:
            continue
        if not preserve_duplicates:
            key = norm.lower()
            if key in seen:
                continue
            seen.add(key)
        items.append(norm)
    return items


def to_flama_array_value(items: List[str]) -> str:
    """Format array items into Flama native newline-delimited storage format."""
    return "\n".join(items) if items else ""


def detect_anomalies(raw: Optional[str], items: List[str]) -> List[str]:
    """Detect anomalies and flags for auditing."""
    flags: List[str] = []
    raw_str = raw or ""
    trimmed = raw_str.strip()

    if trimmed and not items:
        flags.append('empty_after_split')
    elif not trimmed:
        flags.append('empty_input')

    if HTML_TAG_RE.search(raw_str):
        flags.append('html')

    if SOUND_TAG_RE.search(raw_str):
        flags.append('sound')

    if check_unmatched_brackets(raw_str):
        flags.append('unmatched_brackets')

    if any(len(it) > LONG_ITEM_THRESHOLD for it in items):
        flags.append('excessive_length')

    seen: Set[str] = set()
    for it in items:
        k = it.lower()
        if k in seen:
            flags.append('duplicates')
            break
        seen.add(k)

    return flags
