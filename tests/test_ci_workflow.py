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
            "\n  redis-contract:\n", 1
        )[0]

        self.assertIn("needs: changes", backend_block)
        self.assertNotIn("needs: frontend", backend_block)
        self.assertNotIn("Download React build", backend_block)
        self.assertNotIn("image: redis", backend_block)

    def test_backend_parallelism_is_single_process_unless_dispatched(self):
        backend_block = self.workflow.split("\n  backend:\n", 1)[1].split(
            "\n  redis-contract:\n", 1
        )[0]
        dispatch = self.workflow.split("\n  workflow_dispatch:\n", 1)[1].split("\npermissions:", 1)[0]

        # The input reaches the shell through env, never interpolated into run.
        self.assertIn("BACKEND_JOBS: ${{ inputs.backend_jobs || '1' }}", backend_block)
        self.assertIn('--all --backend-only --jobs "$BACKEND_JOBS"', backend_block)
        self.assertIn('--changed --backend-only --jobs "$BACKEND_JOBS"', backend_block)
        self.assertNotIn("--jobs auto", self.workflow)
        self.assertIn("backend_jobs:", dispatch)
        self.assertIn("default: '1'", dispatch)
        # Dispatch inputs never appear inside the run script itself.
        run_script = backend_block.split("- name: Run backend tests\n", 1)[1].split("        run: |\n", 1)[1]
        self.assertNotIn("inputs.", run_script)

    def test_dispatch_benchmark_records_a_manifest_and_can_skip_other_jobs(self):
        backend_block = self.workflow.split("\n  backend:\n", 1)[1].split(
            "\n  redis-contract:\n", 1
        )[0]
        dispatch = self.workflow.split("\n  workflow_dispatch:\n", 1)[1].split("\npermissions:", 1)[0]

        # Only manual runs write a manifest; it stays on the runner as a hash.
        self.assertIn(
            "BACKEND_MANIFEST: ${{ github.event_name == 'workflow_dispatch' && 'output/backend-test-manifest.json' || '' }}",
            backend_block,
        )
        self.assertIn('extra+=(--manifest "$BACKEND_MANIFEST")', backend_block)
        self.assertIn("BACKEND_PARTITION_SEED: ${{ inputs.backend_partition_seed || '' }}", backend_block)
        self.assertIn("validation_scope:", dispatch)
        self.assertIn("default: 'all'", dispatch)
        for job, output in (
            ("frontend", "frontend"),
            ("redis-contract", "redis_contract"),
            ("mysql-contract", "mysql_contract"),
        ):
            block = self.workflow.split(f"\n  {job}:\n", 1)[1]
            self.assertIn(
                f"if: needs.changes.outputs.{output} == 'true' && inputs.validation_scope != 'backend'",
                block.split("\n    runs-on:", 1)[0],
            )
        self.assertIn("    if: needs.changes.outputs.backend == 'true'\n", backend_block)

    def test_backend_job_and_workers_have_time_limits(self):
        backend_block = self.workflow.split("\n  backend:\n", 1)[1].split(
            "\n  redis-contract:\n", 1
        )[0]

        self.assertIn("    timeout-minutes: 30\n", backend_block)
        self.assertIn("extra=(--bin-timeout 1200)", backend_block)

    def test_backend_installs_and_caches_yaml_test_dependencies(self):
        import yaml

        job = yaml.safe_load(self.workflow)["jobs"]["backend"]
        setup = next(step for step in job["steps"] if step.get("uses", "").startswith("actions/setup-python@"))
        self.assertEqual(
            setup["with"]["cache-dependency-path"].splitlines(),
            ["requirements.txt", "requirements-test.txt"],
        )
        install = next(step for step in job["steps"] if step.get("name") == "Install dependencies")
        self.assertIn("pip install -r requirements-test.txt", install["run"])
        requirements = (ROOT / "requirements-test.txt").read_text(encoding="utf-8").splitlines()
        self.assertIn("-r requirements.txt", requirements)
        self.assertIn("PyYAML>=6.0.2,<7.0", requirements)

    def test_expensive_environment_contracts_are_explicit(self):
        frontend = self.workflow.split("\n  frontend:\n", 1)[1].split("\n  backend:\n", 1)[0]
        self.assertIn("FLAMA_REQUIRE_REAL_SPA_ARTIFACT: '1'", frontend)
        self.assertIn("  redis-contract:\n", self.workflow)
        self.assertIn("image: redis:7-alpine", self.workflow)
        self.assertIn("  mysql-contract:\n", self.workflow)
        self.assertIn("image: mysql:8.0", self.workflow)
        self.assertIn("flask --app wsgi.py db upgrade", self.workflow)
        self.assertIn("scripts/probe_p1_02_mysql_concurrency.py", self.workflow)

    def _mysql_steps(self):
        import yaml

        job = yaml.safe_load(self.workflow)["jobs"]["mysql-contract"]
        return job, {step["name"]: step for step in job["steps"]}

    def test_mysql_service_runs_on_capped_tmpfs_with_a_job_time_limit(self):
        job, steps = self._mysql_steps()

        self.assertEqual(job["timeout-minutes"], 40)
        self.assertIn("--tmpfs /var/lib/mysql:rw,size=2g", job["services"]["mysql"]["options"])
        report = steps["Report MySQL tmpfs, binlog and runner memory use"]
        self.assertEqual(report["if"], "always()")
        self.assertEqual(report["env"]["MYSQL_CONTAINER"], "${{ job.services.mysql.id }}")
        self.assertNotIn("${{", report["run"])

    def test_browse_contracts_run_explicitly_on_local_mysql_without_skips(self):
        import shlex

        _, steps = self._mysql_steps()
        step = steps["Qualify Browse pagination, scope and release contracts on MySQL"]
        self.assertEqual(step["env"]["FLAMA_BROWSE_MYSQL_TESTS"], "1")
        self.assertEqual(step["env"]["DB_HOST"], "127.0.0.1")
        self.assertEqual(step["env"]["DB_NAME"], "ci")
        self.assertEqual(step["env"]["DB_USER"], "root")
        self.assertNotIn("continue-on-error", step)
        tokens = shlex.split(step["run"])
        self.assertEqual(tokens[:8], ["python", "scripts/run_tests.py", "--backend-only",
            "--jobs", "1", "--bin-timeout", "1200", "--file"])
        self.assertEqual(tokens[8:], [
            "tests/test_browse_notes_mysql.py",
            "tests/test_browse_scope_optimization_mysql.py",
            "tests/test_browse_deck_summary_mysql.py",
            "tests/test_browse_search_mysql.py",
            "tests/test_browse_mysql_contract.py",
        ])

    def test_only_schema_owning_probes_run_in_parallel_with_unchanged_commands(self):
        import shlex

        job, steps = self._mysql_steps()
        parallel = [step for step in job["steps"] if "run_mysql_probes.py" in step.get("run", "")]
        self.assertEqual(len(parallel), 1)
        tokens = shlex.split(parallel[0]["run"])
        self.assertEqual(tokens[:6], ["python", "scripts/run_mysql_probes.py", "--jobs", "2", "--timeout", "1500"])
        probes = [tokens[i + 1] for i, token in enumerate(tokens) if token == "--probe"]
        self.assertEqual(probes, [
            "scripts/probe_review_analytics_outbox_mysql.py --output output/review-outbox-mysql-ci.json",
            "scripts/probe_p5_direct_replay_mysql.py --overlay-only",
            "scripts/probe_forecast_snapshots_mysql.py --output output/forecast-snapshots-mysql-ci.json",
            "scripts/probe_field_value_consumers_mysql.py --output output/field-value-consumers-mysql-ci.json",
            "scripts/probe_p7_session_retention_mysql.py",
            "scripts/probe_p5_analytics_mysql.py",
            "scripts/probe_note_analytics_mysql.py",
            "scripts/probe_dashboard_due_counts_mysql.py",
        ])
        self.assertEqual(parallel[0]["env"]["DB_HOST"], "127.0.0.1")
        # Concurrency probes and probes that use the ci schema stay sequential.
        sequential = {
            "scripts/probe_p1_02_mysql_concurrency.py",
            "scripts/probe_p5_concurrency_mysql.py",
            "scripts/probe_review_analytics_mysql.py",
            "scripts/probe_deck_counts_mysql.py",
            "scripts/bootstrap_historical_schema.py",
        }
        for script in sequential:
            owners = [name for name, step in steps.items() if script in step.get("run", "")]
            self.assertEqual(len(owners), 1, script)
            self.assertNotIn("run_mysql_probes.py", steps[owners[0]]["run"], script)
        # Each probe still runs exactly once in the job.
        for probe in probes:
            script = probe.split()[0]
            self.assertEqual(sum(step.get("run", "").count(script) for step in job["steps"]), 1, script)

    def test_ci_uses_no_actions_artifact_storage(self):
        # An exhausted account artifact quota must never block validation, so
        # Flask checks the build on the frontend runner without transferring it.
        for workflow in (self.workflow, self.audio_workflow):
            self.assertNotIn("actions/upload-artifact", workflow)
            self.assertNotIn("actions/download-artifact", workflow)
        frontend = self.workflow.split("\n  frontend:\n", 1)[1].split("\n  backend:\n", 1)[0]
        self.assertEqual(self.workflow.count("npm ci"), 1)
        self.assertEqual(self.workflow.count("npm run build:ci"), 1)
        self.assertIn("node-version: '22.22.2'", frontend)
        self.assertLess(frontend.index("npm ci"), frontend.index("npm run build:ci"))
        self.assertLess(frontend.index("npm run build:ci"), frontend.index("tests.test_spa_artifact_contract"))
        self.assertIn("working-directory: .", frontend)
        self.assertIn("if: needs.changes.outputs.spa_contract == 'true'", frontend)

    def test_spa_contract_has_no_separate_runner(self):
        # The repository has no branch protection to require a check name, so
        # a pass-through job would only bill another runner minute.
        self.assertNotIn("\n  spa-contract:\n", self.workflow)
        self.assertNotIn("needs.spa-contract", self.workflow)

    def test_frontend_typecheck_is_not_repeated_during_ci_build(self):
        self.assertIn("npm run typecheck", self.workflow)
        self.assertIn("npm run build:ci", self.workflow)

    def test_production_deploy_is_called_only_after_master_validation(self):
        deploy_block = self.workflow.split("\n  deploy:\n", 1)[1]

        self.assertIn(
            "needs: [changes, frontend, backend, redis-contract, mysql-contract]",
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
