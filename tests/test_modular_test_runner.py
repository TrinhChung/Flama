"""Regression tests for full-suite discovery and process isolation."""

from __future__ import annotations

import os
from pathlib import Path
import sys
import tempfile
import time
from unittest import mock
import unittest

from scripts import run_tests


class ModularTestRunnerTests(unittest.TestCase):
    def test_full_backend_discovery_matches_test_files_on_disk(self):
        expected = sorted(
            path.relative_to(run_tests.ROOT_DIR).as_posix()
            for path in (run_tests.ROOT_DIR / "tests").rglob("test_*.py")
            if "__pycache__" not in path.parts
        )

        self.assertEqual(run_tests.discover_all_backend_tests(), expected)
        self.assertIn("tests/test_modular_test_runner.py", expected)

    def test_full_frontend_discovery_includes_unmapped_tests(self):
        discovered = run_tests.discover_all_frontend_tests()

        self.assertIn("src/features/audio/audioGenerator.test.ts", discovered)
        self.assertIn(
            "src/features/browse/components/MediaFieldPreview.test.tsx",
            discovered,
        )
        self.assertGreater(len(discovered), 37)

    def test_backend_environment_isolates_media_and_disables_default_quota(self):
        media_root = str(Path("isolated-test-media").resolve())

        env = run_tests.build_backend_test_environment(media_root)

        self.assertEqual(env["FLASHCARD_MEDIA_UPLOAD_ROOT"], media_root)
        self.assertEqual(env["FLAMA_TEST_MEDIA_UPLOAD_ROOT"], media_root)
        self.assertEqual(env["RATE_LIMIT_DAILY_ENABLED"], "0")
        self.assertEqual(env["EMAIL_ENABLED"], "0")
        self.assertEqual(env["EMAIL_PROVIDER"], "memory")
        self.assertEqual(env["EMAIL_ENVIRONMENT"], "test")

    def test_changed_frontend_source_selects_colocated_feature_tests(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["frontend/src/features/browse/components/MediaFieldPreview.tsx"]
        )

        self.assertIn("browse", modules)
        self.assertEqual(backend_tests, set())
        self.assertIn(
            "src/features/browse/components/MediaFieldPreview.test.tsx",
            frontend_tests,
        )
        self.assertIn(
            "src/features/browse/services/ttsSettingsStorage.test.ts",
            frontend_tests,
        )

    def test_changed_browse_route_selects_route_behavior_tests(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/api/v1/learning/browse.py"]
        )

        self.assertIn("browse", modules)
        self.assertNotIn("study", modules)
        self.assertIn("tests/test_flashcard_api_integration.py", backend_tests)
        self.assertIn("tests/test_rest_api_v1.py", backend_tests)
        self.assertIn("tests/test_api_v1_route_map.py", backend_tests)
        self.assertEqual(frontend_tests, set())

    def test_changed_media_normalizer_selects_its_regression_tests(self):
        _, backend_tests, _ = run_tests.map_files_to_modules(
            ["app/services/flashcard_media_normalizer.py"]
        )

        self.assertIn("tests/test_flashcard_media_normalizer.py", backend_tests)
        self.assertIn("tests/test_flashcard_media_migration.py", backend_tests)

    def test_changed_worksheet_service_selects_backend_only(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/services/worksheets/worksheet_service.py"]
        )

        self.assertIn("worksheets", modules)
        self.assertIn("tests/test_worksheet_service.py", backend_tests)
        self.assertEqual(frontend_tests, set())

    def test_direct_test_change_does_not_expand_its_domain(self):
        _, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["tests/test_flashcard_renderer.py"]
        )

        self.assertEqual(backend_tests, {"tests/test_flashcard_renderer.py"})
        self.assertEqual(frontend_tests, set())

    def test_new_unmapped_api_runs_route_contract_and_full_backend_layer(self):
        _, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/api/v1/new_domain/routes.py"]
        )

        self.assertIn("tests/test_api_v1_route_map.py", backend_tests)
        self.assertEqual(backend_tests, set(run_tests.discover_all_backend_tests()))
        self.assertEqual(frontend_tests, set())

    def test_queue_metadata_repository_runs_study_regressions(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/repositories/study_queue_repository.py"]
        )
        self.assertEqual(modules, {"study"})
        self.assertIn("tests/test_study_queue_metadata.py", backend_tests)
        self.assertIn("tests/test_study_session_scaling.py", backend_tests)
        self.assertNotEqual(backend_tests, set(run_tests.discover_all_backend_tests()))
        self.assertEqual(frontend_tests, set())

    def test_template_service_selects_focused_template_contracts(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/services/template_release_service.py"]
        )
        self.assertEqual(modules, {"templates"})
        self.assertIn("tests/test_template_release_service.py", backend_tests)
        self.assertIn("tests/test_template_deck_release.py", backend_tests)
        self.assertNotEqual(backend_tests, set(run_tests.discover_all_backend_tests()))
        self.assertEqual(frontend_tests, set())

    def test_shared_release_core_selects_deck_and_template_parity(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/services/release_core/__init__.py"]
        )
        self.assertEqual(modules, {"decks", "templates"})
        self.assertIn("tests/test_deck_auto_publish_and_auto_update.py", backend_tests)
        self.assertIn("tests/test_template_release_service.py", backend_tests)
        self.assertEqual(frontend_tests, set())

    def test_template_entity_change_selects_its_frontend_tests_only(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["frontend/src/entities/card-template/model/types.ts"]
        )
        self.assertEqual(modules, {"templates"})
        self.assertEqual(backend_tests, set())
        self.assertIn("src/entities/card-template/api/cardTemplateApi.test.ts", frontend_tests)
        self.assertNotEqual(frontend_tests, set(run_tests.discover_all_frontend_tests()))

    def test_seed_and_migration_changes_have_explicit_modules(self):
        seed_modules, seed_tests, _ = run_tests.map_files_to_modules(
            ["scripts/seed_flama_template.py"]
        )
        database_modules, database_tests, _ = run_tests.map_files_to_modules(
            ["migrations/versions/example.py"]
        )

        self.assertEqual(seed_modules, {"seed"})
        self.assertIn("tests/test_vocab_seed_sharing.py", seed_tests)
        self.assertEqual(database_modules, {"database"})
        self.assertIn("tests/test_flashcard_media_migration.py", database_tests)

    def test_dependency_change_runs_entire_affected_layer(self):
        _, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["requirements.txt"]
        )

        self.assertEqual(backend_tests, set(run_tests.discover_all_backend_tests()))
        self.assertEqual(frontend_tests, set())

    def test_ci_plan_skips_unrelated_layer_and_external_contracts(self):
        plan = run_tests.build_ci_change_plan(
            ["app/services/worksheets/worksheet_service.py"]
        )

        self.assertTrue(plan["backend"])
        self.assertFalse(plan["frontend"])
        self.assertFalse(plan["spa_contract"])
        self.assertFalse(plan["redis_contract"])
        self.assertFalse(plan["mysql_contract"])
        self.assertTrue(plan["deploy"])

    def test_ci_plan_marks_spa_change_as_cross_stack_contract(self):
        plan = run_tests.build_ci_change_plan(["app/spa.py"])

        self.assertTrue(plan["backend"])
        self.assertTrue(plan["frontend"])
        self.assertTrue(plan["spa_contract"])

    def test_frontend_build_contract_does_not_start_full_backend(self):
        plan = run_tests.build_ci_change_plan(["frontend/package.json"])

        self.assertFalse(plan["backend"])
        self.assertTrue(plan["frontend"])
        self.assertTrue(plan["spa_contract"])

    def test_ci_plan_keeps_test_only_master_validation_out_of_deploy(self):
        plan = run_tests.build_ci_change_plan(
            ["tests/test_ci_workflow.py"],
            force_all_validation=True,
        )

        self.assertTrue(plan["backend"])
        self.assertTrue(plan["frontend"])
        self.assertTrue(plan["redis_contract"])
        self.assertTrue(plan["mysql_contract"])
        self.assertFalse(plan["deploy"])

    def test_ci_plan_deploys_runtime_code_still_missing_from_production(self):
        # #171 changed app/ but its master CI failed; #172 only changed a test.
        stuck = run_tests.build_ci_change_plan(
            ["tests/test_note_analytics_read.py"],
            force_all_validation=True,
            files_since_deploy=["app/services/dashboard_service.py", "tests/test_note_analytics_read.py"],
        )
        current = run_tests.build_ci_change_plan(
            ["tests/test_note_analytics_read.py"],
            force_all_validation=True,
            files_since_deploy=["tests/test_note_analytics_read.py", "docs/x.md"],
        )
        unknown = run_tests.build_ci_change_plan(
            ["tests/test_note_analytics_read.py"],
            force_all_validation=True,
            files_since_deploy=None,
        )

        self.assertTrue(stuck["deploy"])
        self.assertFalse(current["deploy"])
        self.assertFalse(unknown["deploy"])

    def test_files_changed_since_rejects_non_sha_input(self):
        self.assertIsNone(run_tests.files_changed_since(""))
        self.assertIsNone(run_tests.files_changed_since("HEAD; rm -rf /"))

    def test_ci_plan_selects_external_contracts_by_source(self):
        redis_plan = run_tests.build_ci_change_plan(
            ["app/services/redis_state_service.py"]
        )
        mysql_plan = run_tests.build_ci_change_plan(["models/card.py"])

        self.assertTrue(redis_plan["redis_contract"])
        self.assertTrue(mysql_plan["mysql_contract"])

    def test_cli_monolith_uses_broad_contract_set_without_full_backend(self):
        _, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/cli.py"]
        )

        self.assertIn("tests/test_anki_import_api.py", backend_tests)
        self.assertIn("tests/test_vocab_seed_sharing.py", backend_tests)
        self.assertIn("tests/test_api_strokes.py", backend_tests)
        self.assertLess(len(backend_tests), len(run_tests.discover_all_backend_tests()))
        self.assertEqual(frontend_tests, set())

    @mock.patch.dict(
        run_tests.os.environ,
        {"TEST_DIFF_BASE": "base-sha", "TEST_DIFF_HEAD": "head-sha"},
        clear=True,
    )
    @mock.patch("scripts.run_tests.subprocess.run")
    def test_ci_diff_uses_complete_explicit_event_range(self, run_mock):
        run_mock.side_effect = [
            mock.Mock(stdout="", returncode=0),
            mock.Mock(stdout="", returncode=0),
            mock.Mock(stdout="app/api/v1/health.py\n", returncode=0),
        ]

        changed = run_tests.get_git_modified_files()

        self.assertEqual(changed, ["app/api/v1/health.py"])
        self.assertEqual(
            run_mock.call_args_list[2].args[0],
            ["git", "diff", "--name-only", "base-sha", "head-sha"],
        )

    @mock.patch.dict(
        run_tests.os.environ,
        {"TEST_DIFF_BASE": "0" * 40, "TEST_DIFF_HEAD": "head-sha"},
        clear=True,
    )
    @mock.patch("scripts.run_tests.subprocess.run")
    def test_new_branch_push_compares_integration_branch_before_head_parent(self, run_mock):
        run_mock.side_effect = [
            mock.Mock(stdout="", returncode=0),
            mock.Mock(stdout="", returncode=0),
            mock.Mock(stdout="app/services/anki_scheduler.py\n", returncode=0),
        ]

        changed = run_tests.get_git_modified_files()

        self.assertEqual(changed, ["app/services/anki_scheduler.py"])
        self.assertEqual(
            run_mock.call_args_list[2].args[0],
            ["git", "diff", "--name-only", "origin/develop...HEAD"],
        )


class ParallelBackendRunnerTests(unittest.TestCase):
    """Process lifecycle of ``--jobs``; workers here are tiny Python commands."""

    FILES = [f"tests/test_fake_{name}.py" for name in "abcdefg"]
    WEIGHTS = {path: float(index + 1) for index, path in enumerate(FILES)}

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def test_partition_places_every_file_in_exactly_one_bin(self):
        bins = run_tests.partition_backend_tests(self.FILES, 3, self.WEIGHTS)

        flattened = [path for group in bins for path in group]
        self.assertEqual(sorted(flattened), sorted(self.FILES))
        self.assertEqual(len(flattened), len(set(flattened)))
        self.assertEqual(len(bins), 3)

    def test_partition_is_deterministic_and_starts_with_the_heaviest_bin(self):
        first = run_tests.partition_backend_tests(self.FILES, 3, self.WEIGHTS)
        second = run_tests.partition_backend_tests(list(reversed(self.FILES)), 3, self.WEIGHTS)

        loads = [sum(self.WEIGHTS[path] for path in group) for group in first]
        self.assertEqual(first, second)
        self.assertEqual(loads, sorted(loads, reverse=True))
        self.assertLessEqual(max(loads) - min(loads), max(self.WEIGHTS.values()))

    def test_partition_never_creates_more_bins_than_files(self):
        bins = run_tests.partition_backend_tests(self.FILES[:2], 10, self.WEIGHTS)

        self.assertEqual(sorted(path for group in bins for path in group), self.FILES[:2])
        self.assertEqual(len(bins), 2)

    @mock.patch("scripts.run_tests.available_memory_bytes", return_value=64 * 1024**3)
    @mock.patch("scripts.run_tests.effective_cpu_count", return_value=16)
    def test_jobs_resolution_caps_auto_and_numbers_by_file_count(self, _cpus, _memory):
        self.assertEqual(run_tests.resolve_backend_jobs("auto", 300), 16)
        self.assertEqual(run_tests.resolve_backend_jobs("auto", 5), 5)
        self.assertEqual(run_tests.resolve_backend_jobs("4", 300), 4)
        self.assertEqual(run_tests.resolve_backend_jobs("1", 300), 1)
        for invalid in ("0", "-2", "abc"):
            with self.assertRaises(ValueError):
                run_tests.resolve_backend_jobs(invalid, 300)

    @mock.patch("scripts.run_tests.effective_cpu_count", return_value=16)
    def test_auto_jobs_leave_memory_for_each_worker(self, _cpus):
        per_worker = run_tests.BACKEND_WORKER_MEMORY_BYTES
        with mock.patch("scripts.run_tests.available_memory_bytes", return_value=per_worker * 3):
            self.assertEqual(run_tests.resolve_backend_jobs("auto", 300), 3)
            # An explicit number is the caller's decision, not capped by memory.
            self.assertEqual(run_tests.resolve_backend_jobs("8", 300), 8)
        with mock.patch("scripts.run_tests.available_memory_bytes", return_value=per_worker // 2):
            self.assertEqual(run_tests.resolve_backend_jobs("auto", 300), 1)
        with mock.patch("scripts.run_tests.available_memory_bytes", return_value=None):
            self.assertEqual(
                run_tests.resolve_backend_jobs("auto", 300),
                run_tests.BACKEND_AUTO_JOBS_WITHOUT_MEMORY_INFO,
            )

    def test_unittest_summary_parsing_covers_pass_skip_and_failure(self):
        ok = run_tests.parse_unittest_summary("..\n----\nRan 2 tests in 0.1s\n\nOK\n")
        skipped = run_tests.parse_unittest_summary("Ran 5 tests in 1.0s\n\nOK (skipped=2)\n")
        failed = run_tests.parse_unittest_summary(
            "Ran 9 tests in 3.0s\n\nFAILED (failures=1, errors=2, skipped=3)\n"
        )

        self.assertEqual((ok.ran, ok.ok, ok.counts), (2, True, {}))
        self.assertEqual((skipped.ran, skipped.ok, skipped.counts), (5, True, {"skipped": 2}))
        self.assertEqual(
            (failed.ran, failed.ok, failed.counts),
            (9, False, {"failures": 1, "errors": 2, "skipped": 3}),
        )
        self.assertIsNone(run_tests.parse_unittest_summary("Traceback: interpreter crashed"))

    def _bin_result(self, files, returncode, output):
        path = os.path.join(self.temp.name, f"bin-{len(os.listdir(self.temp.name))}.log")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(output)
        return run_tests.BackendBinResult(
            files, returncode, path, 0.1, run_tests.parse_unittest_summary(output)
        )

    def test_bin_passes_only_with_exit_zero_and_an_ok_summary_of_run_tests(self):
        cases = {
            "ok": (0, "Ran 3 tests in 0.1s\n\nOK\n", True),
            "exit zero without summary": (0, "worker exited early\n", False),
            "exit zero but FAILED summary": (0, "Ran 3 tests in 0.1s\n\nFAILED (errors=1)\n", False),
            "no tests ran": (0, "Ran 0 tests in 0.0s\n\nOK\n", False),
            "non-zero exit with OK summary": (1, "Ran 3 tests in 0.1s\n\nOK\n", False),
        }
        for name, (returncode, output, expected) in cases.items():
            with self.subTest(name):
                self.assertIs(self._bin_result(["a"], returncode, output).passed, expected)

    @mock.patch("scripts.run_tests.subprocess.run")
    def test_single_job_keeps_one_unittest_process_for_all_files(self, run_mock):
        run_mock.return_value = mock.Mock(returncode=0)
        files = ["tests/test_ci_workflow.py", "tests/test_modular_test_runner.py"]

        with mock.patch("builtins.print"):
            passed = run_tests.run_backend_tests(["python"], files, failfast=True, jobs=1)

        self.assertTrue(passed)
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.args[0], ["python", "-m", "unittest", "-f", *files])

    def _fake_bin(self, outcome):
        def fake(_python_cmd, files, _failfast, _verbose, _registry=None, **kwargs):
            returncode, output = outcome(files)
            with open(kwargs["log_path"], "w", encoding="utf-8") as handle:
                handle.write(output)
            return run_tests.BackendBinResult(
                files, returncode, kwargs["log_path"], 0.1, run_tests.parse_unittest_summary(output)
            )
        return fake

    def test_parallel_run_fails_when_any_bin_fails(self):
        def outcome(files):
            if self.FILES[0] in files:
                return 1, f"Ran {len(files)} tests in 0.1s\n\nFAILED (failures=1)\n"
            return 0, f"Ran {len(files)} tests in 0.1s\n\nOK\n"

        with mock.patch("scripts.run_tests._run_backend_bin", side_effect=self._fake_bin(outcome)) as bin_mock, \
                mock.patch("builtins.print"), mock.patch("sys.stdout"):
            passed = run_tests.run_backend_tests_parallel(
                ["python"], self.FILES, jobs=2, weights=self.WEIGHTS
            )

        self.assertFalse(passed)
        executed = [path for call in bin_mock.call_args_list for path in call.args[1]]
        self.assertEqual(sorted(executed), sorted(self.FILES))

    def test_parallel_run_passes_when_every_bin_passes(self):
        def outcome(files):
            return 0, f"Ran {len(files)} tests in 0.1s\n\nOK\n"

        with mock.patch("scripts.run_tests._run_backend_bin", side_effect=self._fake_bin(outcome)), \
                mock.patch("builtins.print") as print_mock:
            passed = run_tests.run_backend_tests_parallel(
                ["python"], self.FILES, jobs=3, weights=self.WEIGHTS
            )

        self.assertTrue(passed)
        summary = print_mock.call_args_list[-1].args[0]
        self.assertIn(f"{len(self.FILES)} tests", summary)

    def test_parallel_failfast_does_not_start_bins_after_a_failure(self):
        def outcome(files):
            return 1, "Ran 1 tests in 0.1s\n\nFAILED (failures=1)\n"

        with mock.patch("scripts.run_tests._run_backend_bin", side_effect=self._fake_bin(outcome)) as bin_mock, \
                mock.patch("builtins.print"), mock.patch("sys.stdout"):
            passed = run_tests.run_backend_tests_parallel(
                ["python"], self.FILES, jobs=1, failfast=True, weights=self.WEIGHTS
            )

        self.assertFalse(passed)
        bin_mock.assert_called_once()

    def test_failfast_stops_running_workers_and_their_process_tree(self):
        registry = run_tests._WorkerRegistry()
        running = mock.Mock()
        registry.add(running)

        with mock.patch("scripts.run_tests._terminate_process_tree") as terminate:
            registry.stop_all()
            late = mock.Mock()
            registry.add(late)

        self.assertTrue(registry.stopped.is_set())
        self.assertEqual([call.args[0] for call in terminate.call_args_list], [running, late])

    def test_worker_that_cannot_start_fails_the_run(self):
        with mock.patch("scripts.run_tests._run_backend_bin", side_effect=OSError("spawn failed")), \
                mock.patch("builtins.print"), mock.patch("sys.stdout"):
            passed = run_tests.run_backend_tests_parallel(
                ["python"], self.FILES, jobs=2, weights=self.WEIGHTS
            )

        self.assertFalse(passed)

    def _command_for(self, scripts):
        """Patch the unittest command so each fake file runs a small script."""
        def command(_python_cmd, files, _failfast, _verbose):
            return [sys.executable, "-c", scripts[files[0]]]
        return mock.patch("scripts.run_tests._unittest_command", side_effect=command)

    def test_parallel_worker_spools_output_and_isolates_media(self):
        code = (
            "import os, sys; print('media=' + os.environ['FLASHCARD_MEDIA_UPLOAD_ROOT']); "
            "print('x' * 200000); sys.stderr.write('Ran 1 test in 0.0s\\n\\nOK\\n')"
        )
        base_env = dict(os.environ, UPDATE_SNAPSHOT="1")
        with self._command_for({"a": code, "b": code}):
            first = run_tests._run_backend_bin(
                [sys.executable], ["a"], False, False,
                log_path=os.path.join(self.temp.name, "a.log"), base_env=base_env,
            )
            second = run_tests._run_backend_bin(
                [sys.executable], ["b"], False, False,
                log_path=os.path.join(self.temp.name, "b.log"), base_env=base_env,
            )

        self.assertTrue(first.passed)
        self.assertEqual(first.summary.ran, 1)
        output = first.read_output()
        self.assertIn("x" * 200000, output)
        media = [
            line
            for result in (first, second)
            for line in result.read_output().splitlines()
            if line.startswith("media=")
        ]
        self.assertEqual(len(set(media)), 2)

    def test_worker_environment_comes_from_one_snapshot_without_snapshot_updates(self):
        base = {"PATH": "x", "UPDATE_SNAPSHOT": "1", "UPDATE_ROUTE_SNAPSHOT": "true", "MARKER": "parent"}

        with mock.patch.dict(run_tests.os.environ, {"MARKER": "changed-later"}):
            env = run_tests.build_parallel_worker_environment("media-dir", base)

        self.assertEqual(env["MARKER"], "parent")
        self.assertEqual(env["UPDATE_SNAPSHOT"], "0")
        self.assertEqual(env["UPDATE_ROUTE_SNAPSHOT"], "0")
        self.assertEqual(env["FLASHCARD_MEDIA_UPLOAD_ROOT"], "media-dir")
        self.assertEqual(env["PYTHONUNBUFFERED"], "1")

    def test_timeout_stops_a_hung_worker_and_fails_it(self):
        started = time.time()
        with self._command_for({"a": "import time; time.sleep(60)"}):
            result = run_tests._run_backend_bin(
                [sys.executable], ["a"], False, False,
                log_path=os.path.join(self.temp.name, "hung.log"),
                base_env=dict(os.environ), timeout=2,
            )

        self.assertFalse(result.passed)
        self.assertIn("[TIMEOUT]", result.read_output())
        self.assertLess(time.time() - started, 30)

    def test_failfast_kills_a_running_sibling_worker(self):
        files = ["tests/test_fake_fail.py", "tests/test_fake_slow.py"]
        scripts = {
            files[0]: "import sys, time; time.sleep(1); sys.exit(1)",
            files[1]: "import time; time.sleep(60)",
        }
        started = time.time()
        with self._command_for(scripts), mock.patch("builtins.print"), mock.patch("sys.stdout"):
            passed = run_tests.run_backend_tests_parallel(
                [sys.executable], files, jobs=2, failfast=True, weights={files[0]: 1, files[1]: 2}
            )

        self.assertFalse(passed)
        self.assertLess(time.time() - started, 30)


if __name__ == "__main__":
    unittest.main()
