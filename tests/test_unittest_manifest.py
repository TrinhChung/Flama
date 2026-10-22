"""Pure unittest subprocess contracts for PR B evidence; no application/database."""

from collections import Counter
from copy import deepcopy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import textwrap
import unittest
from unittest import mock

from scripts import compare_test_manifests as compare
from scripts import unittest_manifest as manifest


class UnittestManifestTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.repo = Path(__file__).resolve().parents[1]
        self.counter = 0

    def run_source(self, source, *args, wrapped=True):
        self.counter += 1
        name = f"test_evidence_{self.counter}"
        (self.root / f"{name}.py").write_text(textwrap.dedent(source), encoding="utf-8")
        path = self.root / f"{name}.evidence"
        env = dict(os.environ, PYTHONPATH=str(self.repo), FLAMA_TEST_MANIFEST_PATH=str(path))
        proc = subprocess.run([sys.executable, "-m", "scripts.unittest_manifest" if wrapped else "unittest", *args, name], cwd=self.root, env=env, text=True, encoding="utf-8", errors="replace", capture_output=True, timeout=15)
        return proc, path

    def sample(self):
        proc, path = self.run_source("""
            import unittest
            class Cases(unittest.TestCase):
                def test_ok(self): pass
        """)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        return manifest.read_manifest(path)

    def events(self, document, kind):
        return [event for event in document["events"] if event["kind"] == kind]

    def test_success_records_loaded_started_finished_and_outcome(self):
        doc = self.sample()
        self.assertTrue(doc["complete"])
        self.assertTrue(doc["success"])
        self.assertEqual(doc["tests_run"], 1)
        self.assertEqual(Counter(event["kind"] for event in doc["events"]), Counter(loaded=1, started=1, finished=1, outcome=1))
        self.assertEqual(len({event["id"] for event in doc["events"]}), 1)

    def test_all_outcomes_and_successful_failing_error_skipped_subtests(self):
        proc, path = self.run_source("""
            import unittest
            class Cases(unittest.TestCase):
                def test_success(self): pass
                def test_failure(self): self.fail('failure')
                def test_error(self): raise RuntimeError('error')
                @unittest.skip('理由\\t exact\\n two  spaces')
                def test_skip(self): pass
                @unittest.expectedFailure
                def test_expected(self): self.fail('known')
                @unittest.expectedFailure
                def test_unexpected(self): pass
                def test_subtests(self):
                    with self.subTest(value='ok'): pass
                    with self.subTest(value='failure'): self.fail('no')
                    with self.subTest(value='error'): raise ValueError('bad')
                    with self.subTest(value='skip'): self.skipTest('subskip\\n exact')
        """)
        self.assertEqual(proc.returncode, 1)
        doc = manifest.read_manifest(path)
        self.assertFalse(doc["success"])
        self.assertEqual(doc["tests_run"], 7)
        self.assertEqual({event["outcome"] for event in self.events(doc, "outcome")}, manifest.OUTCOMES)
        self.assertEqual(Counter(event["outcome"] for event in self.events(doc, "subtest")), Counter(ok=1, FAIL=1, ERROR=1, skipped=1))
        self.assertEqual(next(event["reason"] for event in self.events(doc, "outcome") if event["outcome"] == "skipped"), "理由\t exact\n two  spaces")
        self.assertTrue(all(event["parent_id"].endswith("Cases.test_subtests") for event in self.events(doc, "subtest")))

    def test_load_tests_inherited_cases_and_duplicate_instances_preserved(self):
        proc, path = self.run_source("""
            import unittest
            class Base(unittest.TestCase):
                def test_inherited(self): pass
            class Child(Base): pass
            def load_tests(loader, tests, pattern):
                case = Child('test_inherited')
                return unittest.BaseTestSuite([case, case])
        """)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = manifest.read_manifest(path)
        self.assertEqual(doc["tests_run"], 2)
        for kind in ("loaded", "started", "finished", "outcome"):
            ids = [event["id"] for event in self.events(doc, kind)]
            self.assertEqual(len(ids), 2)
            self.assertEqual(len(set(ids)), 1)
            self.assertTrue(ids[0].endswith("Child.test_inherited"))

    def test_import_error_and_load_tests_error_are_completed_error_cases(self):
        for source in ("raise ImportError('import broke')", "def load_tests(loader, tests, pattern):\n    raise RuntimeError('loader broke')"):
            with self.subTest(source=source):
                proc, path = self.run_source(source)
                self.assertEqual(proc.returncode, 1)
                doc = manifest.read_manifest(path)
                self.assertEqual(doc["tests_run"], 1)
                self.assertEqual([event["outcome"] for event in self.events(doc, "outcome")], ["ERROR"])

    def test_module_fixture_errors_and_skip_keep_loaded_unexecuted_cases(self):
        for action, outcome in (("raise RuntimeError('setup')", "ERROR"), ("raise unittest.SkipTest('module reason')", "skipped")):
            with self.subTest(outcome=outcome):
                proc, path = self.run_source(f"""
                    import unittest
                    def setUpModule():
                        {action}
                    class Cases(unittest.TestCase):
                        def test_one(self): pass
                        def test_two(self): pass
                """)
                self.assertEqual(proc.returncode == 0, outcome == "skipped")
                doc = manifest.read_manifest(path)
                self.assertEqual(len(self.events(doc, "loaded")), 2)
                self.assertEqual(doc["tests_run"], 0)
                self.assertEqual([event["outcome"] for event in self.events(doc, "fixture")], [outcome])
                self.assertIn("setUpModule", self.events(doc, "fixture")[0]["id"])

    def test_class_setup_skip_error_and_class_cleanup_errors(self):
        sources = [
            ("@classmethod\n    def setUpClass(cls): raise RuntimeError('class setup')", "ERROR", 0),
            ("@classmethod\n    def setUpClass(cls): raise unittest.SkipTest('class skip')", "skipped", 0),
            ("@classmethod\n    def tearDownClass(cls): raise RuntimeError('class teardown')", "ERROR", 1),
            ("@classmethod\n    def setUpClass(cls): cls.addClassCleanup(lambda: 1/0)", "ERROR", 1),
        ]
        for body, outcome, ran in sources:
            with self.subTest(body=body):
                source = "import unittest\nclass Cases(unittest.TestCase):\n    " + body + "\n    def test_one(self): pass\n"
                proc, path = self.run_source(source)
                self.assertEqual(proc.returncode == 0, outcome == "skipped", proc.stderr)
                doc = manifest.read_manifest(path)
                self.assertEqual(doc["tests_run"], ran)
                self.assertEqual([event["outcome"] for event in self.events(doc, "fixture")], [outcome])

    def test_custom_test_ids_and_fixture_skip_use_actual_class_scope(self):
        for setup in ("@classmethod\n    def setUpClass(cls): raise unittest.SkipTest('scope skip')", ""):
            with self.subTest(setup=setup):
                source = "import unittest\nclass Cases(unittest.TestCase):\n    " + (setup + "\n    " if setup else "") + "def id(self): return 'arbitrary ID\\t\\nwith  spaces'\n    def test_one(self): pass\n"
                proc, path = self.run_source(source)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                doc = manifest.read_manifest(path)
                loaded = self.events(doc, "loaded")[0]
                self.assertEqual(loaded["id"], "arbitrary ID\t\nwith  spaces")
                self.assertTrue(loaded["scope"].endswith(".Cases.test_one"))
                self.assertEqual(loaded["parent_id"], "")

    def test_method_setup_teardown_and_cleanup_errors_keep_parent_lifecycle(self):
        for body in ("def setUp(self): raise ValueError('setup')", "def tearDown(self): raise ValueError('teardown')", "def setUp(self): self.addCleanup(lambda: 1/0)"):
            with self.subTest(body=body):
                proc, path = self.run_source("import unittest\nclass Cases(unittest.TestCase):\n    " + body + "\n    def test_one(self): pass\n")
                self.assertEqual(proc.returncode, 1)
                doc = manifest.read_manifest(path)
                self.assertEqual(doc["tests_run"], 1)
                self.assertEqual([event["outcome"] for event in self.events(doc, "outcome")], ["ERROR"])
                self.assertEqual(len(self.events(doc, "finished")), 1)

    def test_module_teardown_and_module_cleanup_errors_record_fixture_events(self):
        for body in ("def tearDownModule(): raise RuntimeError('teardown')", "unittest.addModuleCleanup(lambda: 1/0)"):
            with self.subTest(body=body):
                proc, path = self.run_source("import unittest\n" + body + "\nclass Cases(unittest.TestCase):\n    def test_one(self): pass\n")
                self.assertEqual(proc.returncode, 1)
                doc = manifest.read_manifest(path)
                self.assertEqual(doc["tests_run"], 1)
                self.assertEqual([event["outcome"] for event in self.events(doc, "fixture")], ["ERROR"])

    def test_failfast_keeps_all_loaded_ids_and_only_started_finished_cases(self):
        proc, path = self.run_source("""
            import unittest
            class Cases(unittest.TestCase):
                def test_a_failure(self): self.fail('stop')
                def test_b_not_run(self): pass
        """, "-f")
        self.assertEqual(proc.returncode, 1)
        doc = manifest.read_manifest(path)
        self.assertEqual(len(self.events(doc, "loaded")), 2)
        self.assertEqual(doc["tests_run"], 1)
        self.assertEqual(len(self.events(doc, "finished")), 1)

    def test_empty_suite_exit_code_matches_unittest_but_cannot_qualify_parity(self):
        wrapped, path = self.run_source("import unittest")
        plain, _ = self.run_source("import unittest", wrapped=False)
        self.assertEqual(wrapped.returncode, plain.returncode)
        with self.assertRaisesRegex(ValueError, "empty test inventory"):
            manifest.read_manifest(path)

    def test_exit_codes_match_for_success_failure_expected_unexpected_and_skip(self):
        bodies = ["def test_one(self): pass", "def test_one(self): self.fail('x')", "@unittest.expectedFailure\n    def test_one(self): self.fail('x')", "@unittest.expectedFailure\n    def test_one(self): pass", "@unittest.skip('why')\n    def test_one(self): pass"]
        for body in bodies:
            with self.subTest(body=body):
                source = "import unittest\nclass Cases(unittest.TestCase):\n    " + body
                wrapped, _ = self.run_source(source)
                plain, _ = self.run_source(source, wrapped=False)
                self.assertEqual(wrapped.returncode, plain.returncode)

    def test_strict_reader_rejects_corruption_incomplete_and_count_mismatches(self):
        good = self.sample()
        corruptions = []
        for key, value in (("complete", False), ("schema_version", 2), ("tests_run", 2), ("success", False)):
            doc = deepcopy(good)
            doc[key] = value
            corruptions.append(doc)
        doc = deepcopy(good)
        doc["events"].append(manifest._event("loaded", "t.Lost.test_unstarted"))
        corruptions.append(doc)
        for kind in ("loaded", "started", "finished", "outcome"):
            doc = deepcopy(good)
            doc["events"] = [event for event in doc["events"] if event["kind"] != kind]
            corruptions.append(doc)
        doc = deepcopy(good)
        doc["events"][0]["unknown"] = "x"
        corruptions.append(doc)
        path = self.root / "bad.json"
        for doc in corruptions:
            with self.subTest(doc=doc):
                path.write_text(json.dumps(doc), encoding="utf-8")
                with self.assertRaises(ValueError): manifest.read_manifest(path)
        for raw in ("", "not json", "t.A.test_one\tok\t\n", '{"schema_version":1,"schema_version":1}', '{"events":'):
            with self.subTest(raw=raw):
                path.write_text(raw, encoding="utf-8")
                with self.assertRaises(ValueError): manifest.read_manifest(path)

    def test_reader_and_writer_enforce_manifest_byte_limit(self):
        doc = self.sample()
        path = self.root / "large.json"
        path.write_text(json.dumps(doc), encoding="utf-8")
        with mock.patch.object(manifest, "MAX_MANIFEST_BYTES", 5):
            with self.assertRaises(ValueError): manifest.read_manifest(path)
            with self.assertRaises(ValueError): manifest._write_manifest(doc, path)

    def test_stale_completed_evidence_is_removed_before_loading_or_interruption(self):
        for source in ("raise RuntimeError('module import escaped loader')", "import unittest\nclass Cases(unittest.TestCase):\n    def test_interrupt(self): raise KeyboardInterrupt()"):
            with self.subTest(source=source):
                path = self.root / "stale.json"
                manifest._write_manifest(self.sample(), path)
                (self.root / "test_broken.py").write_text(source, encoding="utf-8")
                env = dict(os.environ, PYTHONPATH=str(self.repo), FLAMA_TEST_MANIFEST_PATH=str(path))
                proc = subprocess.run([sys.executable, "-m", "scripts.unittest_manifest", "test_broken"], cwd=self.root, env=env, capture_output=True, timeout=15)
                self.assertNotEqual(proc.returncode, 0)
                self.assertFalse(path.exists(), "an interrupted/load-aborted run must leave no completed evidence")

    def test_merge_and_fingerprints_are_order_independent_keep_duplicates(self):
        doc = self.sample()
        a, b, combined = [self.root / name for name in ("a.json", "b.json", "combined.json")]
        manifest._write_manifest(doc, a)
        manifest._write_manifest(dict(doc, events=list(reversed(doc["events"]))), b)
        first = manifest.merge_manifests([a, b], combined)
        original = combined.read_bytes()
        second = manifest.merge_manifests([b, a], combined)
        self.assertEqual(first, second)
        self.assertEqual(combined.read_bytes(), original)
        merged = manifest.read_manifest(combined)
        self.assertEqual((first[0], merged["tests_run"]), (8, 2))
        self.assertEqual(first[1], {"ok": 2})
        self.assertEqual(manifest.manifest_fingerprints(merged)["sha256"], first[2])
        for kind in ("loaded", "started", "finished", "outcome"):
            self.assertEqual(manifest.manifest_fingerprints(merged)["categories"][kind]["count"], 2)
        unchanged = combined.read_bytes()
        with self.assertRaises(ValueError): manifest.merge_manifests([], combined)
        with mock.patch.object(manifest.os, "replace", side_effect=OSError("no replace")):
            with self.assertRaises(OSError): manifest.merge_manifests([a], combined)
        self.assertEqual(combined.read_bytes(), unchanged)
        self.assertEqual(list(self.root.glob(".manifest-*")), [])

    def test_comparator_compares_loaded_and_subtest_events_and_rejects_invalid(self):
        doc = self.sample()
        before, after = self.root / "before.json", self.root / "after.json"
        manifest._write_manifest(doc, before)
        manifest._write_manifest(dict(doc, events=list(reversed(doc["events"]))), after)
        with mock.patch("builtins.print"):
            self.assertEqual(compare.main([str(before), str(after)]), 0)
        other = deepcopy(doc)
        other["events"].extend([manifest._event("loaded", "t.Hidden.test_not_executed", scope="t.Hidden.test_not_executed"), manifest._event("fixture", "setUpClass (t.Hidden)", "skipped", "explicit scope")])
        manifest._write_manifest(other, after)
        with mock.patch("builtins.print"):
            self.assertEqual(compare.main([str(before), str(after)]), 1)
        after.write_text("", encoding="utf-8")
        with mock.patch("builtins.print"):
            self.assertEqual(compare.main([str(before), str(after)]), 2)

    def test_skip_diagnostics_are_bounded_without_changing_evidence(self):
        proc, path = self.run_source("""
            import unittest
            @unittest.skip('long' * 200)
            class Cases(unittest.TestCase): pass
            for n in range(25):
                setattr(Cases, 'test_%02d' % n, lambda self: None)
        """)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = manifest.read_manifest(path)
        fingerprints = manifest.manifest_fingerprints(doc)
        self.assertEqual((len(fingerprints["skips"]), fingerprints["omitted_skips"]), (20, 5))
        self.assertTrue(all(len(event["reason"]) == 240 for event in fingerprints["skips"]))
        self.assertTrue(all(len(event["reason"]) == 800 for event in self.events(doc, "outcome")))

    def test_comparator_detects_lost_successful_subtest_and_changed_exact_reason(self):
        proc, path = self.run_source("""
            import unittest
            class Cases(unittest.TestCase):
                def test_sub(self):
                    with self.subTest(value=1): pass
                @unittest.skip('two  spaces')
                def test_skip(self): pass
        """)
        self.assertEqual(proc.returncode, 0, proc.stderr)
        doc = manifest.read_manifest(path)
        after = self.root / "after.json"
        without_subtest = deepcopy(doc)
        without_subtest["events"] = [event for event in doc["events"] if event["kind"] != "subtest"]
        manifest._write_manifest(without_subtest, after)
        with mock.patch("builtins.print"):
            self.assertEqual(compare.main([str(path), str(after)]), 1)
        changed_reason = deepcopy(doc)
        for event in changed_reason["events"]:
            if event["outcome"] == "skipped": event["reason"] = "two spaces"
        manifest._write_manifest(changed_reason, after)
        with mock.patch("builtins.print"):
            self.assertEqual(compare.main([str(path), str(after)]), 1)

    def test_comparator_rejects_failed_but_accepts_loaded_fixture_skipped_runs(self):
        samples = [("import unittest\nclass Cases(unittest.TestCase):\n    def test_one(self): self.fail('no')", 2), ("import unittest\ndef setUpModule(): raise unittest.SkipTest('scope')\nclass Cases(unittest.TestCase):\n    def test_one(self): pass", 0)]
        for source, expected in samples:
            with self.subTest(source=source):
                _, path = self.run_source(source)
                with mock.patch("builtins.print"):
                    self.assertEqual(compare.main([str(path), str(path)]), expected)
        fixture_only = dict(schema_version=1, complete=True, tests_run=0, success=True, events=[manifest._event("fixture", "setUpClass (t.Cases)", "skipped", "no inventory")])
        path = self.root / "fixture-only.json"
        manifest._write_manifest(fixture_only, path)
        with self.assertRaisesRegex(ValueError, "empty test inventory"):
            manifest.read_manifest(path)

    def test_dynamic_run_discovery_and_opaque_suites_cannot_qualify(self):
        samples = [
            """
                import unittest
                class Cases(unittest.TestCase):
                    def test_one(self): pass
                class Dynamic(unittest.TestSuite):
                    def run(self, result, debug=False):
                        self.addTest(Cases('test_one'))
                        return super().run(result, debug)
                def load_tests(loader, tests, pattern): return Dynamic()
            """,
            """
                import unittest
                class Cases(unittest.TestCase):
                    def test_one(self): pass
                class Opaque:
                    def countTestCases(self): return 1
                    def __call__(self, result): Cases('test_one')(result)
                def load_tests(loader, tests, pattern): return Opaque()
            """,
        ]
        for source in samples:
            with self.subTest(source=source):
                plain, _ = self.run_source(source, wrapped=False)
                wrapped, path = self.run_source(source)
                self.assertEqual(plain.returncode, 0, plain.stderr)
                self.assertNotEqual(wrapped.returncode, 0)
                self.assertFalse(path.exists())
                self.assertIn("pre-run inventory", wrapped.stderr)

    def test_colliding_custom_ids_keep_class_and_method_outcomes_distinct(self):
        for same_class in (False, True):
            with self.subTest(same_class=same_class):
                source = """
                    import os, unittest
                    flipped = os.environ.get('MANIFEST_FLIP') == '1'
                    class First(unittest.TestCase):
                        def id(self): return 'same-id'
                        def test_one(self):
                            if not flipped: self.skipTest('same reason')
                    class Second(unittest.TestCase):
                        def id(self): return 'same-id'
                        def test_one(self):
                            if flipped: self.skipTest('same reason')
                """
                if same_class:
                    source = """
                        import os, unittest
                        flipped = os.environ.get('MANIFEST_FLIP') == '1'
                        class First(unittest.TestCase):
                            def id(self): return 'same-id'
                            def test_one(self):
                                if not flipped: self.skipTest('same reason')
                            def test_two(self):
                                if flipped: self.skipTest('same reason')
                    """
                # Same module name/source on both sides: only which logical case
                # skips changes, so an original-ID-only manifest would match.
                name = "test_colliding_ids"
                (self.root / f"{name}.py").write_text(textwrap.dedent(source), encoding="utf-8")
                paths = []
                for flipped in ("0", "1"):
                    path = self.root / f"collision-{flipped}.json"
                    env = dict(os.environ, PYTHONPATH=str(self.repo), FLAMA_TEST_MANIFEST_PATH=str(path), MANIFEST_FLIP=flipped)
                    proc = subprocess.run([sys.executable, "-m", "scripts.unittest_manifest", name], cwd=self.root, env=env, capture_output=True, timeout=15)
                    self.assertEqual(proc.returncode, 0, proc.stderr)
                    paths.append(path)
                with mock.patch("builtins.print"):
                    self.assertEqual(compare.main(list(map(str, paths))), 1)


if __name__ == "__main__":
    unittest.main()
