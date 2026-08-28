"""CJK Character Extractor for Kanji and Hanzi stroke diagrams."""

from __future__ import annotations

import html
import re


_HTML_TAG_RE = re.compile(r"<[^>]+>")

# Unicode code point ranges for CJK Ideographs (Kanji / Hanzi)
_CJK_IDEOGRAPH_RANGES: tuple[tuple[int, int], ...] = (
    (0x4E00, 0x9FFF),    # CJK Unified Ideographs (Main Block)
    (0x3400, 0x4DBF),    # CJK Unified Ideographs Extension A
    (0x20000, 0x2A6DF),  # CJK Unified Ideographs Extension B
    (0x2A700, 0x2B73F),  # CJK Unified Ideographs Extension C
    (0x2B740, 0x2B81F),  # CJK Unified Ideographs Extension D
    (0x2B820, 0x2CEAF),  # CJK Unified Ideographs Extension E
    (0x2CEB0, 0x2EBEF),  # CJK Unified Ideographs Extension F
    (0x30000, 0x3134F),  # CJK Unified Ideographs Extension G
    (0xF900, 0xFAFF),    # CJK Compatibility Ideographs
    (0x2F800, 0x2FA1F),  # CJK Compatibility Supplement
)


def is_cjk_ideograph(char: str) -> bool:
    """Check if a single character is a CJK ideograph (Kanji/Hanzi)."""
    if not char or len(char) != 1:
        return False
    cp = ord(char)
    for start, end in _CJK_IDEOGRAPH_RANGES:
        if start <= cp <= end:
            return True
    return False


class CjkExtractor:
    """Extracts CJK characters (Kanji/Hanzi) from arbitrary text or HTML."""

    @staticmethod
    def strip_html(text: str) -> str:
        """Strip HTML tags and unescape HTML entities."""
        if not text:
            return ""
        # Remove tags
        cleaned = _HTML_TAG_RE.sub(" ", str(text))
        # Unescape entities (e.g. &amp;, &#12345;)
        return html.unescape(cleaned)

    @classmethod
    def extract_characters(
        cls,
        text: str | None,
        *,
        deduplicate: bool = True,
        max_limit: int = 15,
    ) -> list[str]:
        """Extract a list of CJK characters (Kanji / Hanzi) from text or HTML.

        Args:
            text: Input string (can contain HTML, Kana, Latin, punctuation, etc.).
            deduplicate: If True, duplicate characters are removed while preserving order.
            max_limit: Maximum number of characters returned.

        Returns:
            List of CJK character strings.
        """
        if not text:
            return []

        plain_text = cls.strip_html(text)
        extracted: list[str] = []
        seen: set[str] = set()

        for char in plain_text:
            if is_cjk_ideograph(char):
                if deduplicate:
                    if char in seen:
                        continue
                    seen.add(char)
                extracted.append(char)
                if max_limit > 0 and len(extracted) >= max_limit:
                    break

        return extracted

    @staticmethod
    def char_to_hex(char: str, zero_pad: int = 0) -> str:
        """Convert a character to lowercase hex string (e.g. '勉' -> '52c9' or '052c9')."""
        if not char:
            return ""
        hex_str = format(ord(char), "x").lower()
        if zero_pad > 0 and len(hex_str) < zero_pad:
            hex_str = hex_str.zfill(zero_pad)
        return hex_str
