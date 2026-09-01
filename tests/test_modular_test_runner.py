"""Regression tests for full-suite discovery and process isolation."""

from __future__ import annotations

from pathlib import Path
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


if __name__ == "__main__":
    unittest.main()
