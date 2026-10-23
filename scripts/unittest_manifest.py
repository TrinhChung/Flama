"""Record unittest evidence for suites with a fixed pre-run test inventory.

``FLAMA_TEST_MANIFEST_PATH`` selects the output path. Its extension is immaterial:
the document is versioned JSON, written atomically only after the runner returns.
Normal unittest CLI/output/exit semantics are retained. Suites discovering new
cases inside run(), or opaque callable suites without iterable inventory, cannot
qualify and fail explicitly. No timestamps, process IDs or bin assignments enter
the canonical fingerprint.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile
import unittest

MANIFEST_ENV = "FLAMA_TEST_MANIFEST_PATH"
SCHEMA_VERSION = 1
MAX_MANIFEST_BYTES = 32 * 1024 * 1024
KINDS = {"loaded", "started", "finished", "outcome", "subtest", "fixture"}
OUTCOMES = {"ok", "FAIL", "ERROR", "skipped", "expected failure", "unexpected success"}
EVENT_KEYS = {"kind", "scope", "id", "outcome", "reason", "parent_id"}
DOCUMENT_KEYS = {"schema_version", "complete", "tests_run", "success", "events"}


def _event(kind, test_id, outcome="", reason="", parent_id="", scope=""):
    return dict(kind=kind, scope=scope, id=test_id, outcome=outcome, reason=reason, parent_id=parent_id)


def _scope(test):
    """Stable logical definition, independent of custom id(), bin or occurrence."""
    cls = type(test)
    scope = cls.__module__ + "." + cls.__qualname__
    method = getattr(test, "_testMethodName", None)
    if method:
        scope += "." + method
    if isinstance(test, unittest.FunctionTestCase):
        function = test._testFunc
        scope += ":" + getattr(function, "__module__", "") + "." + getattr(function, "__qualname__", type(function).__qualname__)
        code = getattr(function, "__code__", None)
        if code is not None:
            scope += ":" + str(code.co_firstlineno)
    return scope


def _event_key(event):
    return tuple(event[key] for key in ("kind", "scope", "id", "outcome", "reason", "parent_id"))


def event_multiset(document):
    """Typed events with multiplicities; sorting never removes duplicate cases."""
    return Counter(_event_key(event) for event in document["events"])


def validate_manifest(document):
    """Reject incomplete/corrupt evidence, including mismatched lifecycle counts."""
    def invalid(message):
        raise ValueError(f"Invalid unittest manifest: {message}")

    if not isinstance(document, dict) or set(document) != DOCUMENT_KEYS:
        invalid("document keys")
    if type(document["schema_version"]) is not int or document["schema_version"] != SCHEMA_VERSION:
        invalid("unsupported schema version")
    if document["complete"] is not True:
        invalid("run is incomplete")
    if type(document["tests_run"]) is not int or document["tests_run"] < 0:
        invalid("tests_run")
    if type(document["success"]) is not bool or not isinstance(document["events"], list):
        invalid("success/events types")
    counts = {kind: Counter() for kind in KINDS}
    parent_outcomes = Counter()
    failures = False
    for event in document["events"]:
        if not isinstance(event, dict) or set(event) != EVENT_KEYS:
            invalid("event keys")
        if any(not isinstance(value, str) for value in event.values()):
            invalid("event values must be strings")
        kind = event["kind"]
        if kind not in KINDS or not event["id"]:
            invalid("event kind/id")
        if kind in {"loaded", "started", "finished"}:
            if event["outcome"] or event["reason"] or event["parent_id"]:
                invalid("lifecycle event contains outcome data")
        else:
            if event["outcome"] not in OUTCOMES:
                invalid("unknown outcome")
            if event["reason"] and event["outcome"] != "skipped":
                invalid("only skips carry reasons")
            if (kind == "subtest") != bool(event["parent_id"]):
                invalid("subtest parent_id")
            if kind == "fixture" and event["outcome"] not in {"ERROR", "skipped"}:
                invalid("fixture outcome")
            failures |= event["outcome"] in {"FAIL", "ERROR", "unexpected success"}
            if kind == "subtest":
                parent_outcomes[(event["scope"], event["parent_id"])] += 1
        counts[kind][(event["scope"], event["id"])] += 1
    if counts["started"] != counts["finished"]:
        invalid("started/finished multisets differ")
    if sum(counts["started"].values()) != document["tests_run"]:
        invalid("tests_run disagrees with started events")
    if counts["started"] - counts["loaded"]:
        invalid("started cases were not loaded; dynamic run-time discovery cannot qualify a fixed pre-run inventory")
    if counts["outcome"].keys() - counts["started"].keys():
        invalid("outcome without started case")
    if parent_outcomes.keys() - counts["started"].keys():
        invalid("subtest without started parent")
    if counts["started"] - (counts["outcome"] + parent_outcomes):
        invalid("started case has no outcome or subtest result")
    if document["success"] == failures:
        invalid("success disagrees with recorded failures")
    # Successful suites may leave loaded cases unstarted only when a class or
    # module fixture explicitly skipped them. Failfast after an error/failure
    # legitimately leaves the rest of the inventory unexecuted.
    if document["success"] and counts["loaded"] - counts["started"]:
        skipped_scopes = []
        for event in document["events"]:
            if event["kind"] == "fixture" and event["outcome"] == "skipped":
                fixture_id = event["id"]
                if fixture_id.startswith(("setUpClass (", "setUpModule (")) and fixture_id.endswith(")"):
                    skipped_scopes.append(fixture_id.split(" (", 1)[1][:-1] + ".")
        for (scope, test_id), remaining in (counts["loaded"] - counts["started"]).items():
            explained = sum(
                1 for event in document["events"]
                if event["kind"] == "loaded" and (event["scope"], event["id"]) == (scope, test_id)
                and any((scope + "." if scope else test_id).startswith(skipped_scope) for skipped_scope in skipped_scopes)
            )
            if remaining > explained:
                invalid("successful run left loaded cases unexecuted without a fixture skip")
    if not document["events"] and document["tests_run"]:
        invalid("missing events")
    return document


def _canonical_bytes(document):
    document = dict(document, events=sorted(document["events"], key=_event_key))
    return (json.dumps(document, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")


def _write_manifest(document, destination):
    validate_manifest(document)
    data = _canonical_bytes(document)
    if len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Unittest manifest exceeds the 32 MiB limit")
    target = Path(destination)
    target.parent.mkdir(parents=True, exist_ok=True)
    name = None
    try:
        with tempfile.NamedTemporaryFile(mode="wb", prefix=".manifest-", dir=target.parent, delete=False) as handle:
            name = handle.name
            handle.write(data)
        os.replace(name, target)
    finally:
        if name is not None and os.path.exists(name):
            os.unlink(name)
    return hashlib.sha256(data).hexdigest()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate manifest JSON key: {key}")
        result[key] = value
    return result


def read_manifest(path):
    """Read a completed versioned document; legacy TSV/logs are never evidence."""
    with open(path, "rb") as handle:
        data = handle.read(MAX_MANIFEST_BYTES + 1)
    if not data or len(data) > MAX_MANIFEST_BYTES:
        raise ValueError("Unittest manifest is empty or exceeds 32 MiB")
    try:
        document = json.loads(data.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"Invalid unittest manifest JSON: {exc}") from exc
    validate_manifest(document)
    if not any(event["kind"] == "loaded" for event in document["events"]):
        raise ValueError("Unittest manifest has an empty test inventory")
    return document


def merge_manifests(paths, destination):
    """Atomically merge complete documents without introducing bin-dependent data."""
    if not paths:
        raise ValueError("No unittest manifests to merge")
    documents = [read_manifest(path) for path in paths]
    combined = dict(
        schema_version=SCHEMA_VERSION, complete=True,
        tests_run=sum(doc["tests_run"] for doc in documents),
        success=all(doc["success"] for doc in documents),
        events=[event for doc in documents for event in doc["events"]],
    )
    digest = _write_manifest(combined, destination)
    outcomes = Counter(event["outcome"] for event in combined["events"] if event["kind"] in {"outcome", "fixture", "subtest"})
    return len(combined["events"]), dict(outcomes), digest


def manifest_fingerprints(document):
    """Compact hashes and bounded skip diagnostics suitable for ordinary CI logs."""
    validate_manifest(document)
    categories = {}
    for kind in sorted(KINDS):
        events = sorted((_event_key(event) for event in document["events"] if event["kind"] == kind))
        encoded = json.dumps(events, ensure_ascii=True, separators=(",", ":")).encode("utf-8")
        categories[kind] = dict(count=len(events), sha256=hashlib.sha256(encoded).hexdigest())
    skips = sorted((event for event in document["events"] if event["outcome"] == "skipped"), key=_event_key)
    # Each item is clipped only in diagnostics. The source manifest retains exact strings.
    diagnostic = [dict(id=event["id"][:240], reason=event["reason"][:240], kind=event["kind"]) for event in skips[:20]]
    return dict(sha256=hashlib.sha256(_canonical_bytes(document)).hexdigest(), tests_run=document["tests_run"], success=document["success"], categories=categories, skips=diagnostic, omitted_skips=max(0, len(skips) - len(diagnostic)))


def _loaded_events(suite):
    if isinstance(suite, unittest.BaseTestSuite):
        for child in suite:
            yield from _loaded_events(child)
    else:
        if not callable(getattr(suite, "id", None)):
            raise ValueError("Unsupported qualification: suite must expose a fixed pre-run inventory of test IDs")
        yield _event("loaded", suite.id(), scope=_scope(suite))


class ManifestResult(unittest.TextTestResult):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.events = []
        self._active = Counter()

    def startTest(self, test):
        super().startTest(test)
        self._active[id(test)] += 1
        self.events.append(_event("started", test.id(), scope=_scope(test)))

    def stopTest(self, test):
        self.events.append(_event("finished", test.id(), scope=_scope(test)))
        self._active[id(test)] -= 1
        super().stopTest(test)

    def _record(self, test, outcome, reason=""):
        # Ordinary TestCases may themselves own an attribute called test_case.
        # Only unittest's synthetic, unstarted subtest holders have a parent.
        parent = getattr(test, "test_case", None) if not self._active[id(test)] else None
        kind = "subtest" if parent is not None else "outcome" if self._active[id(test)] else "fixture"
        self.events.append(_event(kind, test.id(), outcome, reason, parent.id() if parent is not None else "", scope=_scope(parent if parent is not None else test) if kind != "fixture" else ""))

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
        self._record(test, "skipped", str(reason))

    def addExpectedFailure(self, test, err):
        super().addExpectedFailure(test, err)
        self._record(test, "expected failure")

    def addUnexpectedSuccess(self, test):
        super().addUnexpectedSuccess(test)
        self._record(test, "unexpected success")

    def addSubTest(self, test, subtest, err):
        super().addSubTest(test, subtest, err)
        outcome = "ok" if err is None else "FAIL" if issubclass(err[0], test.failureException) else "ERROR"
        self.events.append(_event("subtest", subtest.id(), outcome, parent_id=test.id(), scope=_scope(test)))


class ManifestRunner(unittest.TextTestRunner):
    resultclass = ManifestResult

    def run(self, test):
        path = os.environ.get(MANIFEST_ENV)
        if not path:
            return super().run(test)
        loaded = list(_loaded_events(test))
        result = super().run(test)
        _write_manifest(dict(schema_version=SCHEMA_VERSION, complete=True, tests_run=result.testsRun, success=result.wasSuccessful(), events=loaded + result.events), path)
        return result


def main(argv=None):
    # Remove stale evidence before loading: an import/load_tests failure must not
    # accidentally leave a previous completed document at the requested path.
    path = os.environ.get(MANIFEST_ENV)
    if path:
        Path(path).unlink(missing_ok=True)
    arguments = sys.argv[1:] if argv is None else argv
    unittest.main(module=None, argv=["python -m unittest", *arguments], testRunner=ManifestRunner)


if __name__ == "__main__":
    main()
