#!/usr/bin/env python3
"""Verify the quoted evidence and the coverage of an inventory report.

Every Markdown table row that has a location cell ``path:line`` must also
have one quote cell written as a code span. The quote must be a verbatim
substring (at least 12 characters) of that line. Rows without a location
cell are ignored, so headings and summary tables can stay in the report.

A row may cover more lines of the same file with a cell that lists line
numbers only, for example ``12, 15, 18``.

With ``--candidates FILE`` (output of ``git grep -n``: ``path:line:text``)
every candidate line must be covered by some row.

Usage:
  python scripts/tools/verify_inventory_quotes.py REPORT.md [--root DIR] [--candidates FILE]
Exit code 0 when every row matches and every candidate is covered, 1 otherwise.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

LOCATION_RE = re.compile(
    r"^`?(?P<path>[A-Za-z0-9_./\-]+\.(?:py|ts|tsx|json|md|ya?ml)):(?P<line>\d+)`?$"
)
QUOTE_RE = re.compile(r"^`(?P<quote>[^`]+)`$")
LINE_LIST_RE = re.compile(r"^\d+(?:\s*,\s*\d+)*$")
CANDIDATE_RE = re.compile(r"^(?P<path>[^:]+):(?P<line>\d+):")
MIN_QUOTE_LENGTH = 12


def split_row(raw: str) -> list[str]:
    cells = re.split(r"(?<!\\)\|", raw.strip())
    return [cell.strip().replace("\\|", "|") for cell in cells[1:-1]]


def verify(report: Path, root: Path, candidates: Path | None) -> int:
    rows = 0
    failures: list[str] = []
    covered: set[tuple[str, int]] = set()
    cache: dict[Path, list[str]] = {}
    for number, raw in enumerate(report.read_text(encoding="utf-8").splitlines(), start=1):
        if not raw.lstrip().startswith("|"):
            continue
        cells = split_row(raw)
        location = next((m for m in (LOCATION_RE.match(c) for c in cells) if m), None)
        if location is None:
            continue
        rows += 1
        rel_path = location.group("path")
        line_number = int(location.group("line"))
        covered.add((rel_path, line_number))
        for cell in cells:
            if LINE_LIST_RE.match(cell):
                covered.update((rel_path, int(item)) for item in re.findall(r"\d+", cell))
        quote_match = next(
            (
                m
                for m in (QUOTE_RE.match(c) for c in cells if not LOCATION_RE.match(c))
                if m
            ),
            None,
        )
        if quote_match is None:
            failures.append(f"report:{number}: no quote cell")
            continue
        quote = quote_match.group("quote")
        if len(quote) < MIN_QUOTE_LENGTH:
            failures.append(f"report:{number}: quote shorter than {MIN_QUOTE_LENGTH} chars")
            continue
        path = root / rel_path
        if not path.is_file():
            failures.append(f"report:{number}: missing file {rel_path}")
            continue
        lines = cache.setdefault(path, path.read_text(encoding="utf-8").splitlines())
        if not 1 <= line_number <= len(lines):
            failures.append(f"report:{number}: {rel_path} has no line {line_number}")
            continue
        if quote not in lines[line_number - 1]:
            failures.append(f"report:{number}: {rel_path}:{line_number} does not contain the quote")

    missing: list[str] = []
    if candidates is not None:
        for raw in candidates.read_text(encoding="utf-8").splitlines():
            match = CANDIDATE_RE.match(raw)
            if match is None:
                continue
            key = (match.group("path").replace("\\", "/"), int(match.group("line")))
            if key not in covered:
                missing.append(f"{key[0]}:{key[1]}")

    print(f"rows={rows} failures={len(failures)} uncovered_candidates={len(missing)}")
    for failure in failures:
        print(f"FAIL {failure}")
    for item in missing[:200]:
        print(f"UNCOVERED {item}")
    return 1 if failures or missing else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify the quoted evidence and the coverage of an inventory report."
    )
    parser.add_argument("report", type=Path, help="Path to markdown report")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path("."),
        help="Repository root directory (default: current directory)",
    )
    parser.add_argument(
        "--candidates",
        type=Path,
        default=None,
        help="Optional path to candidates file",
    )
    args = parser.parse_args()
    return verify(args.report, args.root, args.candidates)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(2)
    sys.exit(main())
