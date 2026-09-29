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
            "frontend_deploy",
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

    def test_ci_uses_no_actions_artifact_storage(self):
        # An exhausted account artifact quota must never block validation, so
        # the SPA contract builds its own dist instead of passing an artifact.
        for workflow in (self.workflow, self.audio_workflow):
            self.assertNotIn("actions/upload-artifact", workflow)
            self.assertNotIn("actions/download-artifact", workflow)
        spa_block = self.workflow.split("\n  spa-contract:\n", 1)[1].split(
            "\n  redis-contract:\n", 1
        )[0]
        build = spa_block.index("npm run build:ci")
        self.assertIn("node-version: '22.22.2'", spa_block)
        self.assertIn("working-directory: frontend", spa_block)
        self.assertLess(spa_block.index("npm ci"), build)
        self.assertLess(build, spa_block.index("tests.test_spa_artifact_contract"))

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

    def test_frontend_is_published_only_after_the_backend_release(self):
        backend_deploy_block = self.workflow.split("\n  deploy:\n", 1)[1].split(
            "\n  deploy-frontend:\n", 1
        )[0]
        frontend_block = self.workflow.split("\n  deploy-frontend:\n", 1)[1]

        self.assertNotIn("deploy-frontend.yml", backend_deploy_block)
        self.assertIn(
            "needs: [changes, frontend, backend, spa-contract, redis-contract, mysql-contract, deploy]",
            frontend_block,
        )
        # A skipped backend deploy (frontend-only push) may continue; a
        # failed or cancelled one must block the SPA.
        self.assertIn("!cancelled()", frontend_block)
        self.assertNotIn("always()", frontend_block)
        self.assertIn("!contains(needs.*.result, 'failure')", frontend_block)
        self.assertIn("!contains(needs.*.result, 'cancelled')", frontend_block)
        self.assertIn(
            "(needs.deploy.result == 'success' || needs.changes.outputs.deploy != 'true')",
            frontend_block,
        )
        self.assertIn("needs.frontend.result == 'success'", frontend_block)
        self.assertIn("github.event_name == 'push'", frontend_block)
        self.assertIn("github.ref == 'refs/heads/master'", frontend_block)
        self.assertIn("needs.changes.outputs.frontend_deploy == 'true'", frontend_block)
        self.assertIn("uses: ./.github/workflows/deploy-frontend.yml", frontend_block)

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
