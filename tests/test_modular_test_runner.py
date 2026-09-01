"""Regression tests for full-suite discovery and process isolation."""

from __future__ import annotations

from pathlib import Path
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
        modules, _, frontend_tests = run_tests.map_files_to_modules(
            ["frontend/src/features/browse/components/MediaFieldPreview.tsx"]
        )

        self.assertIn("browse", modules)
        self.assertIn(
            "src/features/browse/components/MediaFieldPreview.test.tsx",
            frontend_tests,
        )
        self.assertIn(
            "src/features/browse/services/ttsSettingsStorage.test.ts",
            frontend_tests,
        )

    def test_changed_browse_route_selects_route_behavior_tests(self):
        modules, backend_tests, _ = run_tests.map_files_to_modules(
            ["app/api/v1/learning/browse.py"]
        )

        self.assertIn("browse", modules)
        self.assertIn("tests/test_flashcard_api_integration.py", backend_tests)
        self.assertIn("tests/test_rest_api_v1.py", backend_tests)

    def test_changed_media_normalizer_selects_its_regression_tests(self):
        _, backend_tests, _ = run_tests.map_files_to_modules(
            ["app/services/flashcard_media_normalizer.py"]
        )

        self.assertIn("tests/test_flashcard_media_normalizer.py", backend_tests)
        self.assertIn("tests/test_flashcard_media_migration.py", backend_tests)

    def test_changed_worksheet_service_selects_backend_and_frontend_tests(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/services/worksheets/worksheet_service.py"]
        )

        self.assertIn("worksheets", modules)
        self.assertIn("tests/test_worksheet_service.py", backend_tests)
        self.assertIn("src/features/worksheets/api.test.ts", frontend_tests)


if __name__ == "__main__":
    unittest.main()
