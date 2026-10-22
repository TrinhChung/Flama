#!/usr/bin/env python3
"""Compare two test runs case by case: test-ID multisets, outcomes, skip reasons.

Inputs are manifests written by ``scripts/run_tests.py --manifest`` or, with
--verbose-logs, two ``python -m unittest -v`` logs. Exit 0 only when every
record matches; equal ``Ran N`` totals are not enough.

Usage:
  python scripts/compare_test_manifests.py before.tsv after.tsv
  python scripts/compare_test_manifests.py --verbose-logs serial.log parallel.log \
      --ignore-prefix tests.test_modular_test_runner.NewTests
"""

from __future__ import annotations

import argparse
from collections import Counter
import re
import sys

# Named groups: these patterns are combined, so numbered back-references would
# point at the wrong group. A docstring may put the result on the next line.
_ID = r"(?P<name>test\w*) \((?P<prefix>(?:\w+\.)+)(?P=name)\)"
# Same line, or (docstring) the very next line when the id line ends at the id
# and that next line is not another test.
_RESULT_SEP = r"(?:[^\n]*?|\n(?!test\w* \()[^\n]*?)\.\.\. "
VERBOSE_START = re.compile(_ID)
VERBOSE_SKIP = re.compile(_ID + _RESULT_SEP + r"skipped '(?P<reason>[^']*)'")
VERBOSE_SAME_LINE = re.compile(
    _ID + _RESULT_SEP + r"(?P<outcome>expected failure|unexpected success)$", re.MULTILINE
)
VERBOSE_FAILED = re.compile(r"^(?P<outcome>FAIL|ERROR): " + _ID, re.MULTILINE)


def _test_id(match: re.Match) -> str:
    return match.group("prefix") + match.group("name")

Record = tuple[str, str, str]


def read_manifest(path: str) -> Counter[Record]:
    records: Counter[Record] = Counter()
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            line = line.rstrip("\n")
            if not line:
                continue
            test_id, outcome, reason = (line.split("\t") + ["", ""])[:3]
            records[(test_id, outcome, reason)] += 1
    return records


def read_verbose_log(path: str) -> Counter[Record]:
    """Records inferred from a ``-v`` log; prefer manifests when available.

    Test output can sit between a test's name and its result, so results are
    not read from that line. Each started test id counts once; FAIL/ERROR come
    from unittest's failure headers (which repeat the id), skips and expected
    or unexpected outcomes from their result lines, and the rest are ``ok``.
    """
    text = open(path, encoding="utf-8", errors="replace").read()
    started = Counter(_test_id(m) for m in VERBOSE_START.finditer(text))
    special: Counter[Record] = Counter()
    for match in VERBOSE_FAILED.finditer(text):
        test_id = _test_id(match)
        started[test_id] -= 1  # the header repeats the id
        special[(test_id, match.group("outcome"), "")] += 1
    for match in VERBOSE_SKIP.finditer(text):
        special[(_test_id(match), "skipped", match.group("reason"))] += 1
    for match in VERBOSE_SAME_LINE.finditer(text):
        special[(_test_id(match), match.group("outcome"), "")] += 1
    records = Counter(special)
    special_ids = Counter(record[0] for record in special.elements())
    for test_id, count in (+started - special_ids).items():
        records[(test_id, "ok", "")] += count
    return records


def _keep(records: Counter[Record], prefixes: tuple[str, ...]) -> Counter[Record]:
    if not prefixes:
        return records
    return Counter({record: n for record, n in records.items() if not record[0].startswith(prefixes)})


def summarize(records: Counter[Record]) -> str:
    outcomes = Counter()
    for (_, outcome, _), count in records.items():
        outcomes[outcome] += count
    detail = ", ".join(f"{name}={count}" for name, count in sorted(outcomes.items()))
    return f"{sum(records.values())} records ({detail})"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--verbose-logs", action="store_true", help="Inputs are unittest -v logs.")
    parser.add_argument(
        "--ignore-prefix",
        action="append",
        default=[],
        help="Exclude test ids with this prefix from both sides (for tests added on purpose).",
    )
    parser.add_argument("--limit", type=int, default=50, help="Differences printed per side.")
    args = parser.parse_args(argv)

    read = read_verbose_log if args.verbose_logs else read_manifest
    prefixes = tuple(args.ignore_prefix)
    before = _keep(read(args.before), prefixes)
    after = _keep(read(args.after), prefixes)
    print(f"before: {summarize(before)}")
    print(f"after:  {summarize(after)}")

    only_before, only_after = before - after, after - before
    for label, diff in (("only before", only_before), ("only after", only_after)):
        print(f"{label}: {sum(diff.values())}")
        for (test_id, outcome, reason), count in sorted(diff.items())[: args.limit]:
            suffix = f" ({reason})" if reason else ""
            print(f"  {count}x {test_id} {outcome}{suffix}")
    same = not only_before and not only_after
    print("RESULT: identical" if same else "RESULT: different")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
