"""Trace forbidden retired-table SQL in selected current NOTE test flows.

Historical migration/audit fixture statements are reported separately from
application callsites. --guard-note-writes rejects runtime statements touching
retired tables without creating any legacy model, table or trigger.

    python scripts/trace_card_progress_callsites.py --tests tests/test_study_session_api.py --guard-note-writes --json output/retired-sql.json
"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import os
from pathlib import Path
import re
import sys
import traceback
import unittest

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from sqlalchemy import event  # noqa: E402
from sqlalchemy.engine import Engine  # noqa: E402

_TABLE = re.compile(r"\bcard_progress\b", re.IGNORECASE)
# The tables CONSOLIDATED_V1 must not touch (ADR P10 §2.1).
_CONSOLIDATED_TABLES = re.compile(
    r"\b(cards|card_progress|study_progress_backfill_runs|study_progress_backfill_checkpoints|"
    r"study_progress_backfill_dispositions|vocabulary_column_preferences|study_progress_states|study_authority_subject_tokens|"
    r"study_progress_contributors|study_progress_availability|study_progress_lineage_refs)\b",
    re.IGNORECASE,
)
_OP =re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE)", re.IGNORECASE)
_APP = str(ROOT_DIR / "app") + os.sep
_MODELS = str(ROOT_DIR / "models") + os.sep

records: dict[tuple, dict] = defaultdict(lambda: {"count": 0, "tests": set()})
current_test = {"id": ""}


def _frames():
    inner = outer = None
    for frame in traceback.extract_stack():
        if frame.filename.startswith(_APP) or frame.filename.startswith(_MODELS):
            where = f"{Path(frame.filename).relative_to(ROOT_DIR).as_posix()}:{frame.name}"
            if outer is None:
                outer = where
            inner = where
    return inner, outer


@event.listens_for(Engine, "before_cursor_execute")
def _trace(conn, cursor, statement, parameters, context, executemany):
    table = _TABLE.search(statement)
    if table is None:
        return
    match = _OP.match(statement)
    operation = match.group(1).upper() if match else "OTHER"
    for_update = operation == "SELECT" and "FOR UPDATE" in statement.upper()
    if operation == "SELECT" and for_update:
        operation = "SELECT FOR UPDATE"
    inner, outer = _frames()
    if _TABLE is _CONSOLIDATED_TABLES:
        operation = f"{operation} {table.group(1).lower()}"
    key = (operation, inner or "<no app frame>", outer or "<no app frame>")
    records[key]["count"] += 1
    records[key]["tests"].add(current_test["id"])


note_write_hits: dict[str, set[str]] = defaultdict(set)


def _guard_note_writes() -> None:
    @event.listens_for(Engine, "before_cursor_execute")
    def _reject_runtime_retired_sql(_connection, _cursor, statement, *_args):
        if _TABLE.search(statement) is None:
            return
        inner, _outer = _frames()
        if inner is not None:
            note_write_hits[inner].add(current_test["id"])
            raise RuntimeError("RETIRED_RUNTIME_TABLE_SQL")


class _Result(unittest.TextTestResult):
    def startTest(self, test):
        current_test["id"] = test.id()
        super().startTest(test)


def _tests_for_module(module: str) -> list[str]:
    from scripts.run_tests import MODULES

    return list(MODULES[module]["backend_tests"])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--tests", nargs="*", default=[])
    parser.add_argument("--module", action="append", default=[])
    parser.add_argument("--json", dest="json_path")
    parser.add_argument("--profile", choices=("CONSOLIDATED_V1",), default="CONSOLIDATED_V1")
    parser.add_argument("--guard-note-writes", action="store_true")
    args = parser.parse_args()
    global _TABLE
    if args.profile == "CONSOLIDATED_V1":
        _TABLE = _CONSOLIDATED_TABLES
    if args.guard_note_writes:
        _guard_note_writes()
    files = list(args.tests)
    for module in args.module:
        files.extend(_tests_for_module(module))
    names = sorted({Path(path).with_suffix("").as_posix().replace("/", ".") for path in files})
    suite = unittest.defaultTestLoader.loadTestsFromNames(names)
    result = unittest.TextTestRunner(resultclass=_Result, verbosity=0, stream=open(os.devnull, "w")).run(suite)
    rows = [
        {"operation": op, "issuer": inner, "entrypoint": outer, "count": data["count"],
         "tests": len(data["tests"]), "sample_test": sorted(data["tests"])[0]}
        for (op, inner, outer), data in records.items()
    ]
    rows.sort(key=lambda row: (row["issuer"], row["operation"], row["entrypoint"]))
    report = {"tests_run": result.testsRun, "failures": len(result.failures), "errors": len(result.errors),
              "files": len(names), "profile": args.profile, "callsites": rows,
              "failed_tests": sorted(test.id() for test, _ in result.failures + result.errors)}
    if args.guard_note_writes:
        report["note_projection_writes"] = {issuer: sorted(tests) for issuer, tests in note_write_hits.items()}
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=1), encoding="utf-8")
    by_issuer = defaultdict(set)
    for row in rows:
        by_issuer[row["issuer"]].add(row["operation"])
    for issuer, operations in sorted(by_issuer.items()):
        print(f"{issuer:90} {','.join(sorted(operations))}")
    for issuer, tests in sorted(report.get("note_projection_writes", {}).items()):
        print(f"NOTE projection write from {issuer}: {len(tests)} test(s), e.g. {tests[0]}")
    print(json.dumps({key: report[key] for key in ("tests_run", "failures", "errors", "files", "profile")}))
    return 0 if result.wasSuccessful() and not note_write_hits else 1


if __name__ == "__main__":
    raise SystemExit(main())
