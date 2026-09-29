"""Deployment workflow safety checks."""

from pathlib import Path
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import textwrap
import unittest


WORKFLOW_PATH = (
    Path(__file__).resolve().parents[1]
    / ".github"
    / "workflows"
    / "deploy.yml"
)
BOOTSTRAP_PATH = (
    Path(__file__).resolve().parents[1]
    / "deploy"
    / "bootstrap_hostinger.sh"
)
FRONTEND_WORKFLOW_PATH = WORKFLOW_PATH.with_name("deploy-frontend.yml")


class DeployWorkflowTests(unittest.TestCase):
    def test_host_bootstrap_requires_headers_more_for_media_cache_headers(self):
        bootstrap = BOOTSTRAP_PATH.read_text(encoding="utf-8")

        self.assertIn("nginx openssl", bootstrap)
        self.assertIn(
            "/etc/nginx/modules-enabled/50-mod-http-headers-more-filter.conf",
            bootstrap,
        )
        self.assertIn("libnginx-mod-http-headers-more-filter", bootstrap)

    def test_deploy_is_reusable_and_has_manual_recovery_only(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertIn("  workflow_call:\n", workflow)
        self.assertIn("  workflow_dispatch:\n", workflow)
        self.assertNotIn("  push:\n", workflow)

    def test_vps_release_does_not_build_or_package_frontend(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        self.assertNotIn("actions/setup-node", workflow)
        self.assertNotIn("npm run build", workflow)
        self.assertNotIn(
            "tar --append --file=\"$release_tar\" frontend/dist",
            workflow,
        )
        self.assertIn("-- . ':(exclude)frontend'", workflow)

    def test_database_migration_runs_before_data_bootstrap_and_activation(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

        migration_position = workflow.index(
            '"$PROJECT_DIR/venv/bin/flask" --app wsgi.py db upgrade'
        )
        admin_bootstrap_position = workflow.index(
            '"$PROJECT_DIR/venv/bin/flask" --app wsgi.py bootstrap-admin-sync'
        )
        activation_position = workflow.index(
            'ln -sfn "$release_dir" "$PROJECT_DIR/current"'
        )

        self.assertLess(migration_position, admin_bootstrap_position)
        self.assertLess(admin_bootstrap_position, activation_position)
        self.assertNotIn("seed-data-ensure", workflow)

    def test_database_migration_uses_release_directory_and_managed_environment(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        migration_unit_start = workflow.index(
            '--unit="flama-db-migrate-$RELEASE_ID"'
        )
        migration_command_end = workflow.index(
            '"$PROJECT_DIR/venv/bin/flask" --app wsgi.py db upgrade'
        )
        migration_block = workflow[migration_unit_start:migration_command_end]

        self.assertIn(
            '--property="WorkingDirectory=$release_dir"',
            migration_block,
        )
        self.assertIn(
            '--property="EnvironmentFile=$desired_environment_file"',
            migration_block,
        )

    def test_consumer_is_installed_after_migrations_and_part_of_release_health(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        activate = workflow[workflow.index('test -f "$environment_file"'):]
        self.assertLess(activate.index("db upgrade"), activate.index('install -m 0644 "$release_dir/deploy/flama-study-worker.service"'))
        self.assertLess(activate.index("systemctl stop flama-study-worker.service"), activate.index('mv -f "$desired_environment_file" "$environment_file"'))
        self.assertLess(activate.index("systemctl restart flama-study-worker.service"), activate.index("study_worker.py --check-ready"))
        self.assertLess(activate.index("study_worker.py --check-ready"), activate.index('touch "$release_dir/.deployment_succeeded"'))
        self.assertIn("systemctl is-active --quiet flama-study-worker.service", activate)
        self.assertIn('STUDY_ASYNC_BATCH_ENABLED: ${{ vars.STUDY_ASYNC_BATCH_ENABLED || \'0\' }}', workflow)
        self.assertIn('STUDY_QUEUE_NAMESPACE: ${{ vars.STUDY_QUEUE_NAMESPACE || \'flama-production\' }}', workflow)

    def test_code_rollback_quiesces_writers_then_checks_data_before_restoring_environment(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        rollback = workflow[workflow.index("rollback_activation() {"):workflow.index("cleanup() {")]
        stop_writers = rollback.index("systemctl stop flama.service flama-connect.service")
        check_data = rollback.index("study_worker.py --check-code-rollback --writers-quiesced")
        stop_consumer = rollback.index("systemctl stop flama-study-worker.service")
        restore_environment = rollback.index('cp -p "$environment_backup_file" "$environment_file"')
        restore_code = rollback.index('ln -sfn "$previous_release" "$PROJECT_DIR/current"')
        self.assertLess(stop_writers, check_data)
        self.assertLess(check_data, stop_consumer)
        self.assertLess(stop_consumer, restore_environment)
        self.assertLess(restore_environment, restore_code)
        self.assertIn("Automatic rollback blocked", rollback[check_data:stop_consumer])
        self.assertIn("return", rollback[check_data:stop_consumer])
        self.assertIn("systemctl disable flama-study-worker.service", rollback)

    def test_release_is_stamped_for_health_before_activation(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        activate = workflow[workflow.index('test -f "$environment_file"'):]

        stamp = activate.index("printf '%s\\n' \"$RELEASE_ID\" > \"$release_dir/REVISION\"")
        self.assertLess(activate.index('tar -xzf "$archive_path" -C "$release_dir"'), stamp)
        self.assertLess(stamp, activate.index('ln -sfn "$release_dir" "$PROJECT_DIR/current"'))

    def test_consumer_unit_uses_same_environment_and_graceful_stop(self):
        unit = (WORKFLOW_PATH.parents[2] / "deploy" / "flama-study-worker.service").read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=/etc/flama/flama.env", unit)
        self.assertIn("WorkingDirectory=/opt/flama/current", unit)
        self.assertIn("ExecStart=/opt/flama/venv/bin/python study_worker.py", unit)
        self.assertIn("KillSignal=SIGTERM", unit)
        self.assertNotIn("db upgrade", unit)


class FrontendDeployWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = FRONTEND_WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_frontend_publish_is_reusable_and_never_runs_on_push(self):
        self.assertIn("  workflow_call:\n", self.workflow)
        self.assertIn("  workflow_dispatch:\n", self.workflow)
        self.assertNotIn("  push:\n", self.workflow)
        self.assertIn("if: github.ref == 'refs/heads/master'", self.workflow)
        self.assertIn("group: flama-cloudflare-pages-production", self.workflow)
        self.assertIn("cancel-in-progress: false", self.workflow)

    def test_live_backend_gate_runs_after_build_and_right_before_publish(self):
        build = self.workflow.index("npm run build:ci")
        gate = self.workflow.index("python scripts/check_backend_release.py")
        publish = self.workflow.index("wrangler@4 pages deploy dist")

        self.assertLess(build, gate)
        self.assertLess(gate, publish)
        self.assertIn("fetch-depth: 0", self.workflow)
        self.assertIn('--health-url "${VITE_API_BASE_URL%/}/health"', self.workflow)
        self.assertIn('--target-sha "$RELEASE_ID"', self.workflow)

    def test_pages_deployment_is_pinned_to_the_validated_commit(self):
        self.assertIn("RELEASE_ID: ${{ github.sha }}", self.workflow)
        self.assertIn('--commit-hash="$RELEASE_ID"', self.workflow)
        self.assertIn('--branch="$GITHUB_REF_NAME"', self.workflow)
        self.assertIn('--project-name="$CLOUDFLARE_PAGES_PROJECT"', self.workflow)
        self.assertIn("secrets.CLOUDFLARE_API_TOKEN", self.workflow)


class DeployRollbackShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = shutil.which("bash")
        if not cls.bash and Path("C:/Program Files/Git/bin/bash.exe").is_file():
            cls.bash = "C:/Program Files/Git/bin/bash.exe"
        if not cls.bash:
            raise unittest.SkipTest("Bash is required for the stubbed deploy-shell rehearsal.")

    def _rollback(self, *, check_exit=0, quiesce_exit=0, consumer_stop_exit=0, previous_worker=True):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        function = workflow[workflow.index("          rollback_activation() {"):workflow.index("          cleanup() {")]
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            previous = fixture / "previous"
            (previous / "deploy").mkdir(parents=True)
            units = ["flama.service", "flama-connect.service"]
            if previous_worker:
                units.append("flama-study-worker.service")
            for unit in units:
                (previous / "deploy" / unit).write_text("test fixture only", encoding="utf-8")
            backup = fixture / "rollback.env"
            backup.write_text("test fixture only", encoding="utf-8")
            # Every effectful command in the extracted function is a shell
            # stub. Only -f/-d inspect these generated fixtures; no real service,
            # env file or release symlink is touched, even on a Linux CI host.
            script = "\n".join((
                "set -Eeuo pipefail",
                "activation_started=1", "deployment_succeeded=0", "RELEASE_ID=test",
                "PROJECT_DIR=/test-project", "release_dir=/test-new-release",
                "environment_file=/test-environment",
                "environment_backup_file=" + shlex.quote(backup.as_posix()),
                "previous_release=" + shlex.quote(previous.as_posix()),
                f"CHECK_EXIT={check_exit}", f"QUIESCE_EXIT={quiesce_exit}", f"CONSUMER_STOP_EXIT={consumer_stop_exit}",
                '''systemctl() {
                  printf '%s\\n' "systemctl $*"
                  if [ "$*" = 'stop flama.service flama-connect.service' ]; then return "$QUIESCE_EXIT"; fi
                  if [ "$*" = 'stop flama-study-worker.service' ]; then return "$CONSUMER_STOP_EXIT"; fi
                  return 0
                }
                systemd-run() { printf '%s\\n' "systemd-run $*"; return "$CHECK_EXIT"; }
                cp() { printf '%s\\n' "cp $*"; }
                install() { printf '%s\\n' "install $*"; }
                ln() { printf '%s\\n' "ln $*"; }
                curl() { return 0; }
                sleep() { return 0; }
                ''',
                textwrap.dedent(function), "rollback_activation",
            ))
            env = {key: value for key, value in os.environ.items() if key not in {"BASH_ENV", "ENV"}}
            result = subprocess.run([self.bash, "--noprofile", "--norc", "-s"], input=script, text=True, capture_output=True, timeout=10, env=env, cwd=fixture)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout, result.stderr

    def test_blocked_gate_preserves_consumer_environment_and_selected_code(self):
        output, errors = self._rollback(check_exit=1)
        self.assertIn("stop flama.service flama-connect.service", output)
        self.assertIn("--check-code-rollback --writers-quiesced", output)
        self.assertNotIn("stop flama-study-worker.service", output)
        self.assertNotIn("cp ", output)
        self.assertNotIn("ln ", output)
        self.assertIn("Automatic rollback blocked", errors)

    def test_cannot_stop_request_writers_never_inspects_or_changes_release(self):
        output, errors = self._rollback(quiesce_exit=1)
        self.assertNotIn("systemd-run", output)
        self.assertNotIn("cp ", output)
        self.assertIn("writers did not stop", errors)

    def test_cannot_stop_consumer_never_replaces_environment_or_code(self):
        output, errors = self._rollback(consumer_stop_exit=1)
        self.assertIn("stop flama-study-worker.service", output)
        self.assertNotIn("cp ", output)
        self.assertNotIn("ln ", output)
        self.assertIn("consumer did not stop", errors)

    def test_safe_rollback_restores_consumer_with_previous_release(self):
        output, errors = self._rollback()
        self.assertLess(output.index("--check-code-rollback"), output.index("stop flama-study-worker.service"))
        self.assertLess(output.index("stop flama-study-worker.service"), output.index("cp "))
        self.assertLess(output.index("ln "), output.index("restart flama-study-worker.service"))
        self.assertIn("Previous release restored", errors)

    def test_pre_consumer_release_disables_obsolete_unit_after_safe_gate(self):
        output, errors = self._rollback(previous_worker=False)
        self.assertIn("disable flama-study-worker.service", output)
        self.assertNotIn("restart flama-study-worker.service", output)
        self.assertIn("Previous release restored", errors)

    def test_entire_remote_activation_block_has_valid_bash_syntax(self):
        workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
        match = re.search(r"<<'REMOTE_SCRIPT'\n(.*?)^\s*REMOTE_SCRIPT", workflow, re.MULTILINE | re.DOTALL)
        self.assertIsNotNone(match)
        result = subprocess.run([self.bash, "--noprofile", "--norc", "-n"], input=textwrap.dedent(match.group(1)), text=True, capture_output=True, timeout=10)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == "__main__":
    unittest.main()
