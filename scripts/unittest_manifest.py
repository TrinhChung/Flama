"""Run unittest like ``python -m unittest`` and record every test outcome.

Used by ``scripts/run_tests.py --manifest``. Arguments, flags, output and exit
codes are those of ``python -m unittest``; the only addition is one manifest
line per recorded outcome, written to the path in ``FLAMA_TEST_MANIFEST_PATH``:

    <test id>\\t<outcome>\\t<skip reason>

Outcomes: ok, FAIL, ERROR, skipped, expected failure, unexpected success.
A failing subtest is recorded under its own id; import and class/module
fixture errors appear under the ids unittest gives them.
"""

from __future__ import annotations

import os
import sys
import unittest

MANIFEST_ENV = "FLAMA_TEST_MANIFEST_PATH"


def _clean(text: str) -> str:
    return " ".join(str(text).split())


class ManifestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.records: list[tuple[str, str, str]] = []

    def _record(self, test, outcome: str, reason: str = "") -> None:
        self.records.append((_clean(test.id()), outcome, _clean(reason)))

    def addSuccess(self, test):
        super().addSuccess(test)
        self._record(test, "ok")

    def addFailure(self, test, err):
        super().addFailure(test, err)
        self._record(test, "FAIL")

    def addError(self, test, err):
        super().addError(test, err)
        self._record(test, "ERROR")

    def addSkip(self, test, reason):
        super().addSkip(test, reason)
        self._record(test, "skipped", reason)

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        if err is not None:
            failed = issubclass(err[0], test.failureException)
            self._record(subtest, "FAIL" if failed else "ERROR")


class ManifestRunner(unittest.TextTestRunner):
    resultclass = ManifestResult

    def run(self, test):
        result = super().run(test)
        path = os.environ.get(MANIFEST_ENV)
        if path:
            with open(path, "w", encoding="utf-8", newline="\n") as handle:
                for record in result.records:
                    handle.write("\t".join(record) + "\n")
        return result


def main(argv: list[str] | None = None) -> None:
    program = "python -m unittest"
    arguments = sys.argv[1:] if argv is None else argv
    unittest.main(module=None, argv=[program, *arguments], testRunner=ManifestRunner)


if __name__ == "__main__":
    main()
