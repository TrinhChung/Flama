"""Deck naming analysis, natural sorting, and next lesson name generation services."""

from __future__ import annotations

import os
import re
from typing import Any, Sequence

# Regex patterns for matching common lesson/chapter/deck structures
_PATTERNS = [
    # Vietnamese patterns: Bài 01, Chương 2, Tuần 3, Ngày 04, Phần 1...
    re.compile(
        r"^(?P<prefix>(?:Bài|Bai|Chương|Chuong|Phần|Phan|Tuần|Tuan|Ngày|Ngay|Mục|Muc)\s+)(?P<num_str>0*\d+)(?P<suffix>.*)$",
        re.IGNORECASE,
    ),
    # English patterns: Lesson 01, Unit 2, Chapter 3, Day 4, Part 5, Section 6, Deck 7...
    re.compile(
        r"^(?P<prefix>(?:Lesson|Unit|Chapter|Day|Week|Part|Section|Deck)\s+)(?P<num_str>0*\d+)(?P<suffix>.*)$",
        re.IGNORECASE,
    ),
    # Japanese patterns: 第1課, 第02章, 第3回, レッスン 1...
    re.compile(
        r"^(?P<prefix>第\s*)(?P<num_str>0*\d+)(?P<suffix>\s*(?:課|章|回|節|部).*)$"
    ),
    re.compile(
        r"^(?P<prefix>(?:レッスン|セクション)\s*)(?P<num_str>0*\d+)(?P<suffix>.*)$",
        re.IGNORECASE,
    ),
    # Pure numeric with optional prefix/suffix: 01, 02, #1, 1 - Vocab...
    re.compile(
        r"^(?P<prefix>[#№]?\s*)(?P<num_str>0*\d+)(?P<suffix>(?:\s*[-:–—\.\)].*)?)$"
    ),
]

_FILENAME_EXTRACT_RE = re.compile(
    r"(?:(?:b[aàáảãạăắằẳẵặâấầẩẫậ]i|lesson|unit|chap(?:ter)?|day|week|part|section|d[eé]ck|t[aà]p|ph[aà]n|第)\s*[-_]?\s*|[-_#])0*(?P<num>\d+)",
    re.IGNORECASE,
)


def natural_sort_key(text: str) -> list[Any]:
    """Generates a key for natural/alphanumeric sorting (e.g. 'file2' before 'file10')."""
    return [
        int(c) if c.isdigit() else c.lower()
        for c in re.split(r"(\d+)", str(text or ""))
    ]


def sanitize_filename_to_deck_name(filename: str) -> str:
    """Cleans up a raw filename (removes extension, cleans symbols and underscores)."""
    base_name, _ = os.path.splitext(os.path.basename(str(filename or "")))
    cleaned = re.sub(r"[_\-]+", " ", base_name)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    return cleaned or "Bài mới"


def parse_deck_name_pattern(name: str) -> dict[str, Any] | None:
    """Parses a deck name into prefix, number, zero_pad_length, and suffix if matched."""
    trimmed = str(name or "").strip()
    if not trimmed:
        return None

    for pattern in _PATTERNS:
        match = pattern.match(trimmed)
        if match:
            prefix = match.group("prefix")
            num_str = match.group("num_str")
            suffix = match.group("suffix") or ""
            number = int(num_str)
            zero_pad = len(num_str) if num_str.startswith("0") and len(num_str) > 1 else 1
            return {
                "prefix": prefix,
                "num_str": num_str,
                "number": number,
                "zero_pad": zero_pad,
                "suffix": suffix,
                "raw": trimmed,
            }

    return None


def extract_number_from_filename(filename: str) -> int | None:
    """Extracts explicit lesson or sequence number from a filename."""
    base_name, _ = os.path.splitext(os.path.basename(str(filename or "")))
    match = _FILENAME_EXTRACT_RE.search(base_name)
    if match:
        try:
            return int(match.group("num"))
        except (ValueError, TypeError):
            pass

    digits = re.findall(r"\d+", base_name)
    if digits:
        try:
            return int(digits[-1])
        except (ValueError, TypeError):
            pass

    return None


def analyze_existing_child_decks(child_decks: Sequence[Any]) -> dict[str, Any]:
    """Analyzes existing child decks of a parent to find dominant naming conventions."""
    parsed_items: list[dict[str, Any]] = []
    existing_names: set[str] = set()
    existing_decks_map: dict[str, Any] = {}

    for deck in child_decks:
        name = getattr(deck, "name", "") or ""
        trimmed = name.strip()
        if not trimmed:
            continue

        normalized_key = trimmed.lower()
        existing_names.add(normalized_key)
        existing_decks_map[normalized_key] = deck

        parsed = parse_deck_name_pattern(trimmed)
        if parsed:
            parsed["deck_id"] = getattr(deck, "id", None)
            parsed_items.append(parsed)

    if not parsed_items:
        return {
            "has_pattern": False,
            "dominant_prefix": "",
            "dominant_suffix": "",
            "max_number": 0,
            "zero_pad": 1,
            "existing_names": existing_names,
            "existing_decks_map": existing_decks_map,
            "total_children": len(child_decks),
        }

    # Find the most frequent prefix
    prefix_counts: dict[str, int] = {}
    for item in parsed_items:
        p = item["prefix"]
        prefix_counts[p] = prefix_counts.get(p, 0) + 1

    dominant_prefix = max(prefix_counts.keys(), key=lambda k: prefix_counts[k])
    matching_items = [item for item in parsed_items if item["prefix"] == dominant_prefix]

    max_number = max(item["number"] for item in matching_items)
    max_zero_pad = max(item["zero_pad"] for item in matching_items)

    # Check suffix
    suffix_counts: dict[str, int] = {}
    for item in matching_items:
        s = item["suffix"]
        suffix_counts[s] = suffix_counts.get(s, 0) + 1

    dominant_suffix = ""
    if suffix_counts:
        top_suffix = max(suffix_counts.keys(), key=lambda k: suffix_counts[k])
        # Only use dominant suffix if it appears in at least half of matching items
        if suffix_counts[top_suffix] >= max(1, len(matching_items) // 2):
            dominant_suffix = top_suffix

    return {
        "has_pattern": True,
        "dominant_prefix": dominant_prefix,
        "dominant_suffix": dominant_suffix,
        "max_number": max_number,
        "zero_pad": max_zero_pad,
        "existing_names": existing_names,
        "existing_decks_map": existing_decks_map,
        "total_children": len(child_decks),
    }


def format_deck_number(number: int, zero_pad: int) -> str:
    """Formats a number with zero padding (e.g. format_deck_number(5, 2) -> '05')."""
    return f"{number:0{max(1, zero_pad)}d}"


def generate_suggested_deck_names(
    *,
    child_decks: Sequence[Any],
    filenames: list[str],
    custom_pattern: str | None = None,
    naming_mode: str = "auto",
) -> list[dict[str, Any]]:
    """Generates suggested deck names for uploaded files based on existing children and filenames.

    naming_mode options:
    - 'auto': Automatically uses dominant pattern from child decks or filename numbering
    - 'filename': Uses sanitized filename as deck name
    - 'custom': Uses custom_pattern (e.g. 'Bài {n}' or 'Lesson {n}')
    """
    analysis = analyze_existing_child_decks(child_decks)
    sorted_filenames = sorted(filenames, key=natural_sort_key)

    results: list[dict[str, Any]] = []
    used_names: set[str] = set()

    current_next_num = analysis["max_number"] + 1
    zero_pad = max(1, analysis["zero_pad"])

    for index, filename in enumerate(sorted_filenames, start=1):
        sanitized = sanitize_filename_to_deck_name(filename)
        file_num = extract_number_from_filename(filename)

        suggested_name = ""

        if naming_mode == "filename":
            suggested_name = sanitized
        elif naming_mode == "custom" and custom_pattern:
            # Custom template e.g. "Bài {n}" or "Unit {n}: {filename}"
            pattern = custom_pattern
            num_val = format_deck_number(current_next_num, zero_pad)
            suggested_name = (
                pattern.replace("{n}", num_val)
                .replace("{number}", str(current_next_num))
                .replace("{filename}", sanitized)
            )
            current_next_num += 1
        elif analysis["has_pattern"]:
            # Pattern from child decks exists
            prefix = analysis["dominant_prefix"]
            suffix = analysis["dominant_suffix"]

            # If filename has its own number and it is greater than 0
            if file_num is not None and file_num > 0:
                num_str = format_deck_number(file_num, zero_pad)
                candidate = f"{prefix}{num_str}{suffix}".strip()
                suggested_name = candidate
            else:
                num_str = format_deck_number(current_next_num, zero_pad)
                suggested_name = f"{prefix}{num_str}{suffix}".strip()
                current_next_num += 1
        else:
            # No existing children pattern: Check if uploaded filenames share a pattern
            if file_num is not None:
                # If filename has "bai 1" or "lesson 01"
                parsed_file = parse_deck_name_pattern(sanitized)
                if parsed_file:
                    suggested_name = sanitized
                else:
                    suggested_name = f"Bài {format_deck_number(file_num, 2)}"
            else:
                suggested_name = sanitized

        suggested_name = suggested_name.strip() or f"Bài {index}"

        # Check collision with existing child decks in database
        is_existing_collision = suggested_name.lower() in analysis["existing_names"]
        # Check collision within the batch
        is_batch_collision = suggested_name.lower() in used_names

        used_names.add(suggested_name.lower())

        results.append(
            {
                "filename": filename,
                "sanitized_name": sanitized,
                "suggested_deck_name": suggested_name,
                "extracted_number": file_num,
                "is_existing_collision": is_existing_collision,
                "is_batch_collision": is_batch_collision,
                "existing_deck": (
                    analysis["existing_decks_map"].get(suggested_name.lower())
                    if is_existing_collision
                    else None
                ),
            }
        )

    return results
