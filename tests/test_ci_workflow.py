"""Static CI contracts for selective, gated component coverage."""

from __future__ import annotations

from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]
CI_WORKFLOW = ROOT / ".github" / "workflows" / "ci.yml"
AUDIO_CI_WORKFLOW = ROOT / ".github" / "workflows" / "flama-audio-ci.yml"


class CiWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = CI_WORKFLOW.read_text(encoding="utf-8")
        cls.audio_workflow = AUDIO_CI_WORKFLOW.read_text(encoding="utf-8")

    def test_ci_passes_complete_event_diff_to_modular_runner(self):
        self.assertIn("TEST_DIFF_BASE:", self.workflow)
        self.assertIn("github.event.pull_request.base.sha", self.workflow)
        self.assertIn("github.event.before", self.workflow)
        self.assertIn("TEST_DIFF_HEAD: ${{ github.sha }}", self.workflow)

    def test_both_layers_use_same_changed_file_selector(self):
        self.assertIn(
            "python ../scripts/run_tests.py --changed --frontend-only",
            self.workflow,
        )
        self.assertIn(
            "python scripts/run_tests.py --changed --backend-only",
            self.workflow,
        )
        self.assertNotIn("npm run test:changed", self.workflow)
        self.assertNotIn("|| npm test", self.workflow)

    def test_pr_runs_are_deduplicated_and_superseded_revisions_cancel(self):
        self.assertIn("push:\n    branches:\n      - master", self.workflow)
        self.assertIn("pull_request:\n    branches:\n      - master", self.workflow)
        self.assertIn("      - develop", self.workflow)
        self.assertIn(
            "group: ci-${{ github.event.pull_request.number || github.ref }}",
            self.workflow,
        )
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            self.workflow,
        )

    def test_change_plan_controls_layer_and_contract_jobs(self):
        self.assertIn("  changes:\n", self.workflow)
        self.assertIn(
            'python scripts/run_tests.py --ci-plan --github-output "$GITHUB_OUTPUT"',
            self.workflow,
        )
        for output_name in (
            "backend",
            "frontend",
            "spa_contract",
            "redis_contract",
            "mysql_contract",
            "deploy",
        ):
            self.assertIn(f"steps.plan.outputs.{output_name}", self.workflow)

    def test_backend_is_independent_from_frontend_and_redis(self):
        backend_block = self.workflow.split("\n  backend:\n", 1)[1].split(
            "\n  spa-contract:\n", 1
        )[0]

        self.assertIn("needs: changes", backend_block)
        self.assertNotIn("needs: frontend", backend_block)
        self.assertNotIn("Download React build", backend_block)
        self.assertNotIn("image: redis", backend_block)

    def test_expensive_environment_contracts_are_explicit(self):
        self.assertIn("  spa-contract:\n", self.workflow)
        self.assertIn("FLAMA_REQUIRE_REAL_SPA_ARTIFACT: '1'", self.workflow)
        self.assertIn("  redis-contract:\n", self.workflow)
        self.assertIn("image: redis:7-alpine", self.workflow)
        self.assertIn("  mysql-contract:\n", self.workflow)
        self.assertIn("image: mysql:8.0", self.workflow)
        self.assertIn("flask --app wsgi.py db upgrade", self.workflow)
        self.assertIn("scripts/probe_p1_02_mysql_concurrency.py", self.workflow)

    def test_spa_build_artifact_is_minimal_and_deleted_after_use(self):
        frontend_block = self.workflow.split("\n  frontend:\n", 1)[1].split(
            "\n  backend:\n", 1
        )[0]
        spa_block = self.workflow.split("\n  spa-contract:\n", 1)[1].split(
            "\n  redis-contract:\n", 1
        )[0]
        upload_block = frontend_block.split("name: Upload React build", 1)[1]

        # Uploaded only for the one job that consumes it, without source maps.
        self.assertIn("if: needs.changes.outputs.spa_contract == 'true'", upload_block)
        self.assertIn("frontend/dist\n            !frontend/dist/**/*.map", upload_block)
        self.assertIn("retention-days: 1", upload_block)
        self.assertIn("if-no-files-found: error", upload_block)
        self.assertIn(
            "dist_artifact_id: ${{ steps.upload_dist.outputs.artifact-id }}",
            frontend_block,
        )
        # The consumer frees the storage immediately; cleanup never fails CI.
        self.assertIn("actions: write", spa_block)
        cleanup_block = spa_block.split("name: Delete consumed React build artifact", 1)[1]
        self.assertIn("if: always() && needs.frontend.outputs.dist_artifact_id != ''", cleanup_block)
        self.assertIn("continue-on-error: true", cleanup_block)
        self.assertIn('gh api --method DELETE "repos/${{ github.repository }}/actions/artifacts/$ARTIFACT_ID"', cleanup_block)
        self.assertEqual(self.workflow.count("actions/upload-artifact"), 1)

    def test_frontend_typecheck_is_not_repeated_during_ci_build(self):
        self.assertIn("npm run typecheck", self.workflow)
        self.assertIn("npm run build:ci", self.workflow)

    def test_production_deploy_is_called_only_after_master_validation(self):
        deploy_block = self.workflow.split("\n  deploy:\n", 1)[1]

        self.assertIn(
            "needs: [changes, frontend, backend, spa-contract, redis-contract, mysql-contract]",
            deploy_block,
        )
        self.assertIn("github.event_name == 'push'", deploy_block)
        self.assertIn("github.ref == 'refs/heads/master'", deploy_block)
        self.assertIn("needs.changes.outputs.deploy == 'true'", deploy_block)
        self.assertIn("uses: ./.github/workflows/deploy.yml", deploy_block)

    def test_flama_audio_changes_have_pr_and_push_tests(self):
        self.assertIn("name: Flama Audio CI", self.audio_workflow)
        self.assertIn("push:", self.audio_workflow)
        self.assertIn("pull_request:", self.audio_workflow)
        self.assertIn('runs-on: windows-latest', self.audio_workflow)
        self.assertIn("submodules: recursive", self.audio_workflow)
        self.assertIn(
            "group: flama-audio-ci-${{ github.event.pull_request.number || github.ref }}",
            self.audio_workflow,
        )
        self.assertIn(
            "cancel-in-progress: ${{ github.event_name == 'pull_request' }}",
            self.audio_workflow,
        )
        self.assertIn(
            "dotnet test flama-audio/Flama.Audio.sln -c Release --no-restore",
            self.audio_workflow,
        )
        self.assertIn(
            "dotnet test flama-audio/src/Flama.Audio.Engine.Kokoro/G2P/Flama.G2P.sln -c Release --no-restore",
            self.audio_workflow,
        )


if __name__ == "__main__":
    unittest.main()
