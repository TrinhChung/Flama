"""P9-00: trace every SQL statement that touches ``card_progress``.

Runs chosen test modules in-process with a SQLAlchemy cursor listener and
records, for each statement on ``card_progress`` (or the projection-linked
contributor columns), the operation, the innermost ``app/`` frame (the code
that issued it) and the outermost ``app/`` frame (the entrypoint). The
result is the runtime callsite list the Phase 9 plan asks for instead of a
grep. Nothing is written to any configured database: the tests use their
own in-memory SQLite.

    python scripts/trace_card_progress_callsites.py --tests tests/test_study_session_api.py ...
    python scripts/trace_card_progress_callsites.py --module study --json out.json
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
_OP = re.compile(r"^\s*(SELECT|INSERT|UPDATE|DELETE)", re.IGNORECASE)
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
    if not _TABLE.search(statement):
        return
    match = _OP.match(statement)
    operation = match.group(1).upper() if match else "OTHER"
    for_update = operation == "SELECT" and "FOR UPDATE" in statement.upper()
    if operation == "SELECT" and for_update:
        operation = "SELECT FOR UPDATE"
    inner, outer = _frames()
    key = (operation, inner or "<no app frame>", outer or "<no app frame>")
    records[key]["count"] += 1
    records[key]["tests"].add(current_test["id"])


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
    args = parser.parse_args()
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
              "files": len(names), "callsites": rows}
    if args.json_path:
        Path(args.json_path).write_text(json.dumps(report, indent=1), encoding="utf-8")
    by_issuer = defaultdict(set)
    for row in rows:
        by_issuer[row["issuer"]].add(row["operation"])
    for issuer, operations in sorted(by_issuer.items()):
        print(f"{issuer:90} {','.join(sorted(operations))}")
    print(json.dumps({key: report[key] for key in ("tests_run", "failures", "errors", "files")}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
