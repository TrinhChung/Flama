"""Regression tests for full-suite discovery and process isolation."""

from __future__ import annotations

import os
import json
from pathlib import Path
import sys
import tempfile
import time
from unittest import mock
import unittest

from scripts import run_tests


def _case_manifest(cases):
    events = []
    for test_id, outcome, reason in cases:
        for kind in ("loaded", "started", "finished", "outcome"):
            events.append(dict(kind=kind, scope="", id=test_id, outcome=outcome if kind == "outcome" else "", reason=reason if kind == "outcome" else "", parent_id=""))
    return dict(schema_version=1, complete=True, tests_run=len(cases), success=all(outcome not in {"FAIL", "ERROR", "unexpected success"} for _, outcome, _ in cases), events=events)


class ModularTestRunnerTests(unittest.TestCase):
    def test_worker_media_selects_its_contracts_and_mysql_job(self):
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["app/services/worker_media_service.py"]
        )
        self.assertIn("flashcards", modules)
        self.assertIn("tests/test_worker_media_mysql.py", backend_tests)
        self.assertIn("tests/test_stroke_worker_client.py", backend_tests)
        self.assertEqual(frontend_tests, set())
        self.assertTrue(run_tests.build_ci_change_plan(
            ["app/services/worker_media_service.py"]
        )["mysql_contract"])

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

    def test_test_dependencies_run_full_backend_without_external_contracts(self):
        _, backend_tests, frontend_tests = run_tests.map_files_to_modules(
            ["requirements-test.txt"]
        )
        self.assertEqual(backend_tests, set(run_tests.discover_all_backend_tests()))
        self.assertEqual(frontend_tests, set())

        plan = run_tests.build_ci_change_plan(["requirements-test.txt"])
        self.assertTrue(plan["backend"])
        for job in ("frontend", "spa_contract", "redis_contract", "mysql_contract", "deploy"):
            self.assertFalse(plan[job], job)

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

    def test_probe_runner_change_keeps_mysql_contract_gate(self):
        plan = run_tests.build_ci_change_plan(["scripts/run_mysql_probes.py"])
        self.assertTrue(plan["backend"])
        self.assertTrue(plan["mysql_contract"])
        self.assertFalse(plan["deploy"])

    def test_browse_sql_and_mysql_regressions_select_mysql_contract(self):
        for path in (
            "app/api/v1/learning/browse.py",
            "app/services/browse_card_service.py",
            "app/services/browse_note_service.py",
            "app/services/browse_deck_service.py",
            "app/repositories/browse_card_repository.py",
            "app/repositories/browse_note_repository.py",
            "app/repositories/browse_deck_repository.py",
            "app/repositories/browse_search_repository.py",
            "app/validators/browse_decks.py",
            "tests/test_browse_notes_mysql.py",
            "tests/test_browse_scope_optimization_mysql.py",
            "tests/test_browse_deck_summary_mysql.py",
            "tests/test_browse_search_mysql.py",
            "tests/test_browse_mysql_contract.py",
            "tests/test_browse_query_bounds.py",
        ):
            with self.subTest(path=path):
                plan = run_tests.build_ci_change_plan([path])
                self.assertTrue(plan["backend"])
                self.assertTrue(plan["mysql_contract"])

    def test_browse_frontend_only_change_does_not_start_mysql(self):
        plan = run_tests.build_ci_change_plan([
            "frontend/src/features/browse/components/BrowseToolbar.tsx",
        ])
        self.assertTrue(plan["frontend"])
        self.assertFalse(plan["mysql_contract"])

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

    @mock.patch("sys.stderr")
    @mock.patch("sys.argv", ["run_tests.py", "--file", "tests/test_nonexistent.py"])
    def test_missing_explicit_file_exits_with_code_1(self, mock_stderr):
        exit_code = run_tests.main()
        self.assertEqual(exit_code, 1)

    @mock.patch("sys.stderr")
    @mock.patch("sys.argv", ["run_tests.py", "--file", "tests/test_modular_test_runner.py", "tests/test_nonexistent.py"])
    def test_mixed_existing_and_nonexisting_files_in_file_arg_triggers_error_exit(self, mock_stderr):
        exit_code = run_tests.main()
        self.assertEqual(exit_code, 1)

    @mock.patch("sys.stderr")
    @mock.patch("sys.argv", ["run_tests.py", "--file", "README.md"])
    def test_file_arg_with_no_resolved_test_suites_exits_with_code_1(self, mock_stderr):
        exit_code = run_tests.main()
        self.assertEqual(exit_code, 1)

    def test_direct_selection_of_nested_test_files(self):
        archive_path = "tests/example_nested/test_nested_contract.py"
        modules, backend_tests, frontend_tests = run_tests.map_files_to_modules([archive_path])
        self.assertIn(archive_path, backend_tests)
        self.assertEqual(frontend_tests, set())

    def test_ci_change_plan_marks_backend_for_nested_test_files(self):
        archive_path = "tests/example_nested/test_nested_contract.py"
        plan = run_tests.build_ci_change_plan([archive_path])
        self.assertTrue(plan["backend"])
        self.assertFalse(plan["frontend"])
        self.assertFalse(plan["deploy"])

    @mock.patch("sys.stderr")
    def test_run_backend_tests_returns_false_if_test_file_missing(self, mock_stderr):
        result = run_tests.run_backend_tests([run_tests.sys.executable], ["tests/test_nonexistent.py"])
        self.assertFalse(result)

    def test_map_files_to_modules_resolves_renamed_test_against_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            target = root / "tests/nested/test_relocated.py"
            target.parent.mkdir(parents=True)
            target.write_text("", encoding="utf-8")
            modules = {"fixture": {"source_patterns": [], "backend_tests": ["tests/nested/test_relocated.py"], "frontend_tests": []}}
            with mock.patch.object(run_tests, "ROOT_DIR", root), mock.patch.object(run_tests, "MODULES", modules):
                _, backend_tests, _ = run_tests.map_files_to_modules(["tests/test_relocated.py"])
            self.assertEqual(backend_tests, {"tests/nested/test_relocated.py"})



class ChangedTestSelectionTests(unittest.TestCase):
    """Git deletions broaden coverage; explicit and catalog mistakes still fail."""

    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        for name, value in (("ROOT_DIR", self.root), ("MODULES", {})):
            patcher = mock.patch.object(run_tests, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def files(self, *paths):
        for path in paths:
            target = self.root / path
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text("", encoding="utf-8")

    def test_moved_uncataloged_frontend_test_runs_current_entire_frontend(self):
        old = "frontend/src/features/marketplace/pages/SharedNoteTypeDetailPage.test.tsx"
        new = "frontend/src/pages/marketplace-note-type-detail/ui/SharedNoteTypeDetailPage.test.tsx"
        other = "frontend/src/entities/flashcard/ui/NoteFieldEditor.test.tsx"
        self.files(new, other, "tests/test_other.py")
        _, backend, frontend = run_tests.map_files_to_modules([old], from_git_diff=True)
        self.assertEqual(frontend, {new.removeprefix("frontend/"), other.removeprefix("frontend/")})
        self.assertEqual(backend, set())
        self.assertNotIn(old.removeprefix("frontend/"), frontend)

    def test_removed_test_covers_differently_named_replacement_and_other_current_tests(self):
        self.files("frontend/src/entities/flashcard/ui/NoteFieldEditor.test.tsx", "frontend/src/features/browse/Browse.test.tsx")
        _, backend, frontend = run_tests.map_files_to_modules(
            ["frontend\\src\\shared\\ui\\CardFieldsForm.test.tsx"], from_git_diff=True,
        )
        self.assertEqual(frontend, set(run_tests.discover_all_frontend_tests()))
        self.assertEqual(len(frontend), 2)
        self.assertEqual(backend, set())

    def test_removed_backend_without_replacement_runs_current_backend_only(self):
        self.files("tests/nested/test_current.py", "tests/test_other.py", "frontend/src/Other.test.tsx")
        _, backend, frontend = run_tests.map_files_to_modules(["tests/test_removed.py"], from_git_diff=True)
        self.assertEqual(backend, {"tests/nested/test_current.py", "tests/test_other.py"})
        self.assertEqual(frontend, set())

    def test_colliding_basenames_do_not_guess_a_replacement_from_catalog_order(self):
        targets = ["src/pages/one/Same.test.tsx", "src/pages/two/Same.test.tsx", "src/entities/Other.test.tsx"]
        self.files(*(f"frontend/{path}" for path in targets))
        for order in (targets, list(reversed(targets))):
            with self.subTest(order=order):
                run_tests.MODULES = {"example": {"source_patterns": [], "backend_tests": [], "frontend_tests": order[:1]}}
                _, backend, frontend = run_tests.map_files_to_modules(["frontend/src/deleted/Same.test.tsx"], from_git_diff=True)
                self.assertEqual(frontend, set(targets))
                self.assertEqual(backend, set())

    def test_existing_changed_test_stays_direct_only(self):
        self.files("frontend/src/Current.test.tsx", "frontend/src/Other.test.tsx", "tests/test_current.py", "tests/test_other.py")
        _, backend, frontend = run_tests.map_files_to_modules(["frontend/src/Current.test.tsx", "tests/test_current.py"], from_git_diff=True)
        self.assertEqual(frontend, {"src/Current.test.tsx"})
        self.assertEqual(backend, {"tests/test_current.py"})

    def test_explicit_missing_and_mixed_frontend_files_fail_before_mapping(self):
        current = "frontend/src/current/Current.test.tsx"
        self.files(current)
        for paths in (["frontend/src/deleted/Current.test.tsx"], [current, "frontend/src/Missing.test.tsx"]):
            with self.subTest(paths=paths), mock.patch.object(sys, "argv", ["run_tests.py", "--frontend-only", "--file", *paths]), mock.patch.object(run_tests, "resolve_python_command", return_value=[sys.executable]), mock.patch.object(run_tests, "map_files_to_modules") as mapper, mock.patch("sys.stderr"):
                self.assertEqual(run_tests.main(), 1)
                mapper.assert_not_called()

    def test_stale_frontend_catalog_entry_remains_a_failure(self):
        source = "frontend/src/features/example/Current.tsx"
        self.files(source, "frontend/src/features/example/Other.test.tsx")
        run_tests.MODULES = {"example": {"source_patterns": [source], "backend_tests": [], "frontend_tests": ["src/features/example/Missing.test.tsx"]}}
        _, _, selected = run_tests.map_files_to_modules([source], from_git_diff=True)
        self.assertIn("src/features/example/Missing.test.tsx", selected)
        with mock.patch.object(run_tests.subprocess, "run") as child, mock.patch("sys.stderr"):
            self.assertFalse(run_tests.run_frontend_tests(sorted(selected)))
            child.assert_not_called()

    def test_stale_backend_catalog_entry_remains_a_failure(self):
        source = "app/services/current.py"
        self.files(source, "tests/test_other.py")
        run_tests.MODULES = {"example": {"source_patterns": [source], "backend_tests": ["tests/test_missing.py"], "frontend_tests": []}}
        _, selected, _ = run_tests.map_files_to_modules([source], from_git_diff=True)
        self.assertIn("tests/test_missing.py", selected)
        with mock.patch.object(run_tests, "run_backend_tests_parallel") as child, mock.patch("builtins.print"):
            self.assertFalse(run_tests.run_backend_tests([sys.executable], sorted(selected)))
            child.assert_not_called()

    def test_deleted_only_ci_plan_activates_only_affected_layer(self):
        self.files("tests/test_current.py", "frontend/src/Current.test.tsx")
        for old, layer, other in (("tests/test_removed.py", "backend", "frontend"), ("frontend/src/Removed.test.tsx", "frontend", "backend")):
            with self.subTest(layer=layer):
                plan = run_tests.build_ci_change_plan([old])
                self.assertTrue(plan[layer])
                self.assertFalse(plan[other])
                self.assertFalse(plan["deploy"])

    def test_current_inventory_is_discovered_once_per_layer_in_large_diff(self):
        with mock.patch.object(run_tests, "discover_all_frontend_tests", return_value=["src/Current.test.tsx"]) as frontend, mock.patch.object(run_tests, "discover_all_backend_tests", return_value=["tests/test_current.py"]) as backend:
            _, selected_backend, selected_frontend = run_tests.map_files_to_modules(
                ["frontend/src/Removed.test.tsx", "frontend/src/OtherRemoved.test.tsx", "tests/test_removed.py", "tests/test_other_removed.py"], from_git_diff=True,
            )
        self.assertEqual(selected_frontend, {"src/Current.test.tsx"})
        self.assertEqual(selected_backend, {"tests/test_current.py"})
        frontend.assert_called_once_with()
        backend.assert_called_once_with()

    def test_empty_fallback_inventory_rejects_selection_for_both_layers(self):
        for old in ("tests/test_removed.py", "frontend/src/Removed.spec.ts"):
            with self.subTest(old=old), self.assertRaisesRegex(ValueError, "coverage cannot be verified"):
                run_tests.map_files_to_modules([old], from_git_diff=True)

    def test_cli_changed_and_ci_plan_fail_when_inventory_is_empty(self):
        for mode in ("--changed", "--ci-plan"):
            output = self.root / "github-output"
            with self.subTest(mode=mode), mock.patch.object(sys, "argv", ["run_tests.py", mode, "--frontend-only", "--github-output", str(output)]), mock.patch.object(run_tests, "get_git_modified_files", return_value=["frontend/src/Removed.test.tsx"]), mock.patch.object(run_tests, "resolve_python_command", return_value=[sys.executable]), mock.patch("sys.stderr"):
                self.assertEqual(run_tests.main(), 1)
                self.assertFalse(output.exists())

    def test_cli_changed_runs_current_frontend_after_deletion(self):
        current = "frontend/src/entities/flashcard/ui/NoteFieldEditor.test.tsx"
        self.files(current)
        with mock.patch.object(sys, "argv", ["run_tests.py", "--changed", "--frontend-only"]), mock.patch.object(run_tests, "get_git_modified_files", return_value=["frontend/src/shared/ui/CardFieldsForm.test.tsx"]), mock.patch.object(run_tests, "resolve_python_command", return_value=[sys.executable]), mock.patch.object(run_tests, "run_frontend_tests", return_value=True) as child, mock.patch("builtins.print"):
            self.assertEqual(run_tests.main(), 0)
            self.assertEqual(child.call_args.kwargs["test_files"], [current.removeprefix("frontend/")])

    def test_missing_frontend_directory_for_selected_tests_fails(self):
        with mock.patch.object(run_tests.subprocess, "run") as child, mock.patch("sys.stderr"):
            self.assertFalse(run_tests.run_frontend_tests(["src/Current.test.tsx"]))
            child.assert_not_called()


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

    def test_explicit_jobs_above_memory_estimate_warn_but_are_kept(self):
        per_worker = run_tests.BACKEND_WORKER_MEMORY_BYTES
        argv = ["run_tests.py", "--module", "tooling", "--backend-only", "--jobs", "4"]
        with mock.patch.object(sys, "argv", argv), \
                mock.patch("scripts.run_tests.available_memory_bytes", return_value=per_worker * 2), \
                mock.patch("scripts.run_tests.run_backend_tests", return_value=True) as run_mock, \
                mock.patch("builtins.print") as print_mock:
            self.assertEqual(run_tests.main(), 0)

        printed = " ".join(str(call.args[0]) for call in print_mock.call_args_list if call.args)
        self.assertIn("[WARN] --jobs 4 exceeds the 2 worker(s)", printed)
        self.assertEqual(run_mock.call_args.kwargs["jobs"], 4)

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
        Path(path).write_text(output, encoding="utf-8")
        summary = run_tests.parse_unittest_summary(output)
        data = _case_manifest([(f"t.C.test_{i}", "ok" if summary.ok else "ERROR", "") for i in range(summary.ran)]) if summary and summary.ran else None
        return run_tests.BackendBinResult(files, returncode, path, 0.1, summary, manifest_data=data)

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

    @mock.patch("scripts.run_tests.run_backend_tests_parallel", return_value=True)
    def test_single_job_keeps_one_unittest_process_for_all_files(self, run_mock):
        files = ["tests/test_ci_workflow.py", "tests/test_modular_test_runner.py"]
        with mock.patch("builtins.print"):
            passed = run_tests.run_backend_tests(["python"], files, failfast=True, jobs=1)
        self.assertTrue(passed)
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.args[:2], (["python"], files))
        self.assertEqual(run_mock.call_args.kwargs["jobs"], 1)
        self.assertTrue(run_mock.call_args.kwargs["failfast"])

    def _fake_bin(self, outcome):
        def fake(_python_cmd, files, _failfast, _verbose, _registry=None, **kwargs):
            from scripts.unittest_manifest import _write_manifest
            returncode, output = outcome(files)
            Path(kwargs["log_path"]).write_text(output, encoding="utf-8")
            summary = run_tests.parse_unittest_summary(output)
            data = _case_manifest([(f, "ok" if returncode == 0 else "FAIL", "") for f in files])
            _write_manifest(data, kwargs["manifest_path"])
            return run_tests.BackendBinResult(files, returncode, kwargs["log_path"], 0.1, summary, manifest_path=kwargs["manifest_path"], manifest_data=data)
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
        return mock.patch("scripts.run_tests._manifest_command", side_effect=command)

    def test_parallel_worker_spools_output_and_isolates_media(self):
        from scripts.unittest_manifest import _write_manifest
        data = _case_manifest([("t.C.test_output", "ok", "")])
        code = (
            "import os,sys,json; print('media='+os.environ['FLASHCARD_MEDIA_UPLOAD_ROOT']); "
            "print('x'*200000); open(os.environ['FLAMA_TEST_MANIFEST_PATH'],'w',encoding='utf-8').write(" + repr(json.dumps(data)) + "); "
            "print('worker complete')"
        )
        base_env = dict(os.environ, UPDATE_SNAPSHOT="1")
        with self._command_for({"a": code, "b": code}):
            first = run_tests._run_backend_bin([sys.executable], ["a"], False, False, log_path=os.path.join(self.temp.name, "a.log"), base_env=base_env)
            second = run_tests._run_backend_bin([sys.executable], ["b"], False, False, log_path=os.path.join(self.temp.name, "b.log"), base_env=base_env)
        self.assertTrue(first.passed, first.read_output())
        self.assertEqual(first.summary.ran, 1)
        self.assertIn("x"*200000, first.read_output())
        media = [line for r in (first,second) for line in r.read_output().splitlines() if line.startswith("media=")]
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


class MysqlProbeRunnerTests(unittest.TestCase):
    """The probe runner only orchestrates processes; these use no database."""

    SCRIPT = run_tests.ROOT_DIR / "scripts" / "run_mysql_probes.py"

    def _run(self, *probes):
        import subprocess

        args = [sys.executable, str(self.SCRIPT), "--jobs", "2"]
        for probe in probes:
            args += ["--probe", probe]
        return subprocess.run(args, capture_output=True, text=True, encoding="utf-8", errors="replace")

    def test_windows_style_probe_path_is_accepted(self):
        result = self._run("scripts\\run_mysql_probes.py --help")

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("ok    scripts/run_mysql_probes.py --help", result.stdout)

    def test_any_failing_probe_fails_the_run_after_all_finish(self):
        # The runner invoking itself: --help exits 0, --jobs 0 exits 2.
        result = self._run(
            "scripts/run_mysql_probes.py --help",
            "scripts/run_mysql_probes.py --jobs 0 --probe scripts/run_mysql_probes.py",
        )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("ok    scripts/run_mysql_probes.py --help", result.stdout)
        self.assertIn("FAIL  scripts/run_mysql_probes.py --jobs 0", result.stdout)

    def test_probe_running_past_its_timeout_is_killed_and_fails(self):
        from scripts import run_mysql_probes

        started = time.time()
        returncode, elapsed, output = run_mysql_probes.run_probe(
            ["-c", "import time; time.sleep(60)"], timeout=2
        )

        self.assertNotEqual(returncode, 0)
        self.assertIn("[TIMEOUT]", output)
        self.assertLess(time.time() - started, 30)
        self.assertLess(elapsed, 30)

    def test_missing_probe_script_is_rejected_before_running(self):
        result = self._run("scripts/run_mysql_probes.py --help", "scripts/no_such_probe.py")

        self.assertEqual(result.returncode, 2)
        self.assertIn("probe script not found", result.stderr)
        self.assertNotIn("Probe timings", result.stdout)


class TestManifestTests(unittest.TestCase):
    """Case-level evidence for comparing runs; subprocesses run tiny temp modules."""

    SAMPLE = (
        "import unittest\n"
        "class Sample(unittest.TestCase):\n"
        "    def test_ok(self):\n"
        "        pass\n"
        "    def test_fail(self):\n"
        "        self.fail('no')\n"
        "    def test_error(self):\n"
        "        raise RuntimeError('boom')\n"
        "    @unittest.skip('not here')\n"
        "    def test_skip(self):\n"
        "        pass\n"
        "    @unittest.expectedFailure\n"
        "    def test_expected(self):\n"
        "        self.fail('known')\n"
        "    @unittest.expectedFailure\n"
        "    def test_unexpected(self):\n"
        "        pass\n"
        "    def test_subtests(self):\n"
        "        for value in (1, 2):\n"
        "            with self.subTest(value=value):\n"
        "                self.assertEqual(value, 1)\n"
    )

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)

    def _run(self, module_source, *args, manifest=True):
        import subprocess
        name = "test_manifest_sample.py"
        with open(os.path.join(self.temp.name, name), "w", encoding="utf-8") as handle:
            handle.write(module_source)
        env = dict(os.environ, PYTHONPATH=str(run_tests.ROOT_DIR))
        manifest_path = os.path.join(self.temp.name, "out.json")
        env.pop("FLAMA_TEST_MANIFEST_PATH", None)
        if manifest:
            env["FLAMA_TEST_MANIFEST_PATH"] = manifest_path
        module = "scripts.unittest_manifest" if manifest else "unittest"
        result = subprocess.run([sys.executable, "-m", module, *args, name], cwd=self.temp.name, env=env, capture_output=True, text=True)
        records = []
        if manifest and os.path.exists(manifest_path):
            with open(manifest_path, encoding="utf-8") as handle:
                document = json.load(handle)
            records = [(e["id"], e["outcome"], e["reason"]) for e in document["events"] if e["kind"] in {"outcome", "fixture", "subtest"}]
        return result, records

    def test_wrapper_records_every_outcome_and_keeps_unittest_exit_codes(self):
        wrapped, records = self._run(self.SAMPLE)
        plain, _ = self._run(self.SAMPLE, manifest=False)

        self.assertEqual(wrapped.returncode, plain.returncode)
        self.assertEqual(wrapped.returncode, 1)
        outcomes = {(test_id.rsplit(".", 1)[-1], outcome, reason) for test_id, outcome, reason in records}
        self.assertIn(("test_ok", "ok", ""), outcomes)
        self.assertIn(("test_fail", "FAIL", ""), outcomes)
        self.assertIn(("test_error", "ERROR", ""), outcomes)
        self.assertIn(("test_skip", "skipped", "not here"), outcomes)
        self.assertIn(("test_expected", "expected failure", ""), outcomes)
        self.assertIn(("test_unexpected", "unexpected success", ""), outcomes)
        self.assertTrue(any("test_subtests" in test_id and "value=2" in test_id and outcome == "FAIL"
                            for test_id, outcome, _ in records))

    def test_wrapper_exit_codes_match_for_passing_and_empty_modules(self):
        passing = "import unittest\nclass P(unittest.TestCase):\n    def test_ok(self):\n        pass\n"
        empty = "import unittest\n"
        for source, expected in ((passing, 0), (empty, 5)):
            with self.subTest(expected=expected):
                wrapped, _ = self._run(source)
                plain, _ = self._run(source, manifest=False)
                self.assertEqual((wrapped.returncode, plain.returncode), (expected, expected))

    def test_merged_manifest_is_sorted_keeps_duplicates_and_changes_hash(self):
        from scripts.unittest_manifest import _write_manifest, read_manifest
        first, second, out = [os.path.join(self.temp.name, name) for name in ("a.json", "b.json", "merged.json")]
        _write_manifest(_case_manifest([("t.B.test_b", "ok", ""), ("t.A.test_a", "skipped", "why")]), first)
        _write_manifest(_case_manifest([("t.C.test_c", "ok", "")]), second)
        count, outcomes, digest = run_tests.write_test_manifest([first, second], out)
        duplicate_count, _, duplicate_digest = run_tests.write_test_manifest([first, second, second], out)
        events = read_manifest(out)["events"]
        self.assertEqual((count, outcomes), (12, {"ok": 2, "skipped": 1}))
        self.assertEqual(duplicate_count, 16)
        self.assertNotEqual(digest, duplicate_digest)
        self.assertEqual(events, sorted(events, key=lambda e: (e["kind"], e["scope"], e["id"], e["outcome"], e["reason"], e["parent_id"])))

    def test_partition_seed_changes_grouping_but_never_loses_a_file(self):
        files = [f"tests/test_seed_{index:02d}.py" for index in range(20)]
        weights = {path: 100.0 + index for index, path in enumerate(files)}

        plain = run_tests.partition_backend_tests(files, 4, weights)
        seeded = run_tests.partition_backend_tests(files, 4, weights, seed=1)
        again = run_tests.partition_backend_tests(files, 4, weights, seed=1)

        for bins in (plain, seeded):
            self.assertEqual(sorted(path for group in bins for path in group), sorted(files))
        self.assertEqual(seeded, again)
        self.assertNotEqual(sorted(map(tuple, plain)), sorted(map(tuple, seeded)))

    def test_parallel_run_fails_when_a_bin_writes_no_manifest(self):
        from scripts.unittest_manifest import _write_manifest
        files = ["tests/test_fake_a.py", "tests/test_fake_b.py"]
        def fake(_python_cmd, bin_files, _failfast, _verbose, _registry=None, **kwargs):
            output = f"Ran {len(bin_files)} tests in 0.1s\n\nOK\n"
            Path(kwargs["log_path"]).write_text(output, encoding="utf-8")
            data = _case_manifest([(f, "ok", "") for f in bin_files])
            if files[0] in bin_files:
                _write_manifest(data, kwargs["manifest_path"])
            return run_tests.BackendBinResult(bin_files, 0, kwargs["log_path"], 0.1, run_tests.parse_unittest_summary(output), manifest_path=kwargs["manifest_path"], manifest_data=data)
        out = os.path.join(self.temp.name, "run.json")
        with mock.patch("scripts.run_tests._run_backend_bin", side_effect=fake), mock.patch("builtins.print"), mock.patch("sys.stdout"):
            passed = run_tests.run_backend_tests_parallel(["python"], files, jobs=2, weights={files[0]: 1, files[1]: 2}, manifest=out)
        self.assertFalse(passed)
        self.assertFalse(Path(out).exists(), "Incomplete evidence must never be exported as a completed manifest")

    def _compare(self, *args):
        from scripts import compare_test_manifests

        with mock.patch("builtins.print"):
            return compare_test_manifests.main(list(args))

    def test_compare_reports_identical_and_different_manifests(self):
        from scripts.unittest_manifest import _write_manifest
        base, same, changed = [os.path.join(self.temp.name, name) for name in ("base.json", "same.json", "changed.json")]
        events = [("t.A.test_a", "ok", ""), ("t.A.test_b", "skipped", "why")]
        _write_manifest(_case_manifest(events), base)
        _write_manifest(_case_manifest(list(reversed(events))), same)
        _write_manifest(_case_manifest([(events[0]), ("t.A.test_b", "skipped", "other reason")]), changed)
        self.assertEqual(self._compare(base, same), 0)
        self.assertEqual(self._compare(base, changed), 1)
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as rejected:
            self._compare(base, changed, "--ignore-prefix", "t.A.test_b")
        self.assertEqual(rejected.exception.code, 2)

    def test_compare_reads_verbose_logs_with_interleaved_output(self):
        before = os.path.join(self.temp.name, "truncated.log")
        Path(before).write_text("test_a (t.A.test_a) ... noisy\n", encoding="utf-8")
        # A truncated text log cannot qualify exact execution parity.
        self.assertEqual(self._compare(before, before), 2)
        with mock.patch("sys.stderr"), self.assertRaises(SystemExit) as rejected:
            self._compare("--verbose-logs", before, before)
        self.assertEqual(rejected.exception.code, 2)


if __name__ == "__main__":
    unittest.main()
