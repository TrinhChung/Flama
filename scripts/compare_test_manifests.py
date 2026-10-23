"""Qualify successful unittest runs by typed event multisets and loaded inventory.

Identical nonempty inventories wholly skipped by class/module fixtures are valid;
failed, incomplete or empty-inventory runs cannot qualify.
"""

from __future__ import annotations

import argparse
import sys

try:
    from scripts.unittest_manifest import event_multiset, read_manifest
except ModuleNotFoundError:  # Also support ``python scripts/compare_test_manifests.py``.
    from unittest_manifest import event_multiset, read_manifest


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("before")
    parser.add_argument("after")
    parser.add_argument("--limit", type=int, default=20, help="Maximum differing events printed per side")
    args = parser.parse_args(argv)
    if args.limit < 0 or args.limit > 100:
        parser.error("--limit must be between 0 and 100")
    try:
        before, after = read_manifest(args.before), read_manifest(args.after)
        if not before["success"] or not after["success"]:
            raise ValueError("Both runs must be successful to qualify parity")
    except (OSError, ValueError) as exc:
        print(f"Invalid evidence: {exc}", file=sys.stderr)
        return 2
    before_events, after_events = event_multiset(before), event_multiset(after)
    for label, diff in (("only before", before_events - after_events), ("only after", after_events - before_events)):
        print(f"{label}: {sum(diff.values())}")
        for event, count in sorted(diff.items())[:args.limit]:
            # repr escapes tabs/newlines in IDs and reasons without changing evidence.
            print(f"  {count}x {event!r}"[:1600])
    same = before_events == after_events and before["tests_run"] == after["tests_run"] and before["success"] == after["success"]
    print("RESULT: identical" if same else "RESULT: different")
    return 0 if same else 1


if __name__ == "__main__":
    sys.exit(main())
