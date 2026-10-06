"""Pure Python Mustache token parsing and content hashing for card templates."""

import hashlib as _hashlib
import json as _json
import re as _re

__all__ = [
    "TemplateTokenError",
    "base_variable_name",
    "extract_variable_names",
    "rewrite_variable_names",
    "template_content_hash",
]


class TemplateTokenError(ValueError):
    """Raised when an unsupported template token or construct is encountered."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_TAG_RE = _re.compile(r"\{\{\{(?P<triple>.*?)\}\}\}|\{\{(?P<body>.*?)\}\}", _re.DOTALL)


def _scan_tags(source: str):
    """Yield (name, start, end) for variable tokens in source.

    Raises TemplateTokenError on unsupported constructs (e.g. delimiter change).
    """
    for m in _TAG_RE.finditer(source):
        triple = m.group("triple")
        if triple is not None:
            name = triple.strip()
            if not name or name == ".":
                continue
            leading = len(triple) - len(triple.lstrip())
            start = m.start("triple") + leading
            end = start + len(name)
            yield name, start, end
            continue

        body = m.group("body")
        if body is not None:
            body_l = body.lstrip()
            if not body_l:
                continue
            sigil = body_l[0]
            if sigil in ("!", ">"):
                continue
            if sigil == "=":
                raise TemplateTokenError(
                    "DELIMITER_CHANGE_UNSUPPORTED",
                    "Delimiter change tags are not supported.",
                )
            if sigil in ("#", "^", "/", "&"):
                after_sigil = body_l[1:]
                name = after_sigil.strip()
                if not name or name == ".":
                    continue
                leading_in_after = len(after_sigil) - len(after_sigil.lstrip())
                leading_body = len(body) - len(body_l)
                start = m.start("body") + leading_body + 1 + leading_in_after
                end = start + len(name)
                yield name, start, end
            else:
                name = body.strip()
                if not name or name == ".":
                    continue
                leading_body = len(body) - len(body_l)
                start = m.start("body") + leading_body
                end = start + len(name)
                yield name, start, end


def extract_variable_names(source: str | None) -> list[str]:
    """Extract unique variable names in order of first appearance.

    Returns empty list if source is None or empty.
    Raises TemplateTokenError if delimiter change tags are present.
    """
    if not source:
        return []

    names: list[str] = []
    seen: set[str] = set()
    for name, _, _ in _scan_tags(source):
        if name not in seen:
            seen.add(name)
            names.append(name)
    return names


def rewrite_variable_names(source: str | None, mapping: dict[str, str]) -> str:
    """Rewrite variable names based on token spans using mapping.

    Mapping values must be non-empty trimmed strings not containing '{' or '}'.
    Supports '_url' and '_urls' media suffixes if base field is mapped.
    Returns empty string if source is None.
    Raises ValueError on invalid mapping.
    Raises TemplateTokenError on unsupported delimiter change tag.
    """
    for val in mapping.values():
        if not isinstance(val, str) or not val.strip() or val.strip() != val or "{" in val or "}" in val:
            raise ValueError(f"Invalid variable mapping value: {val!r}")

    if source is None:
        return ""

    replacements: list[tuple[int, int, str]] = []
    for name, start, end in _scan_tags(source):
        if name in mapping:
            replacement = mapping[name]
        elif name.endswith("_urls") and name[:-5] in mapping:
            replacement = mapping[name[:-5]] + "_urls"
        elif name.endswith("_url") and name[:-4] in mapping:
            replacement = mapping[name[:-4]] + "_url"
        else:
            replacement = name

        replacements.append((start, end, replacement))

    pieces: list[str] = []
    last_pos = 0
    for start, end, replacement in replacements:
        pieces.append(source[last_pos:start])
        pieces.append(replacement)
        last_pos = end
    pieces.append(source[last_pos:])
    return "".join(pieces)


def base_variable_name(name: str, known_names: set[str]) -> str:
    """Strip '_url' or '_urls' from name if the base name is in known_names."""
    if name in known_names:
        return name
    if name.endswith("_urls") and name[:-5] in known_names:
        return name[:-5]
    if name.endswith("_url") and name[:-4] in known_names:
        return name[:-4]
    return name


def template_content_hash(
    front_html: str | None,
    back_html: str | None,
    shared_css: str | None,
) -> str:
    """Deterministic SHA-256 digest of normalized template content JSON."""
    payload = {
        "front_html": front_html or "",
        "back_html": back_html or "",
        "shared_css": shared_css or "",
    }
    encoded = _json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return _hashlib.sha256(encoded).hexdigest()
