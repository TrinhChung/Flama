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


ACTIVATION_PATH = WORKFLOW_PATH.parents[2] / "deploy" / "activate_release.sh"
LAUNCHER_PATH = WORKFLOW_PATH.parents[2] / "deploy" / "run_remote_deploy.sh"


def deployment_source():
    return WORKFLOW_PATH.read_text(encoding="utf-8") + "\n" + ACTIVATION_PATH.read_text(encoding="utf-8")


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
        workflow = deployment_source()

        self.assertIn("  workflow_call:\n", workflow)
        self.assertIn("  workflow_dispatch:\n", workflow)
        self.assertNotIn("  push:\n", workflow)

    def test_release_packages_only_mcp_ui_and_never_builds_spa_on_vps(self):
        workflow = deployment_source()
        activation = ACTIVATION_PATH.read_text(encoding="utf-8")
        self.assertNotIn("npm", activation)
        self.assertIn("npm run build:mcp", workflow)
        self.assertNotIn("npm run build:ci", workflow)
        self.assertNotIn(
            "tar --append --file=\"$release_tar\" frontend/dist\n",
            workflow,
        )
        self.assertIn('tar --append --file="$release_tar" frontend/dist-mcp/index.html', workflow)
        self.assertIn("-- . ':(exclude)frontend'", workflow)

    def test_database_migration_runs_before_data_bootstrap_and_activation(self):
        workflow = deployment_source()

        migration_position = workflow.index(
            '"$PROJECT_DIR/venv/bin/python" "$release_dir/deploy/migrate_database.py" --writers-quiesced'
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
        workflow = deployment_source()
        migration_unit_start = workflow.index(
            '--unit="flama-db-migrate-$RELEASE_ID"'
        )
        migration_command_end = workflow.index(
            '"$PROJECT_DIR/venv/bin/python" "$release_dir/deploy/migrate_database.py" --writers-quiesced'
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
        workflow = deployment_source()
        activate = workflow[workflow.index('test -f "$environment_file"'):]
        self.assertLess(activate.index("deploy/migrate_database.py"), activate.index('install -m 0644 "$release_dir/deploy/flama-study-worker.service"'))
        self.assertLess(activate.index("systemctl stop flama-study-worker.service"), activate.index('mv -f "$desired_environment_file" "$environment_file"'))
        self.assertLess(activate.index("systemctl restart flama-study-worker.service"), activate.index("study_worker.py --check-ready"))
        self.assertLess(activate.index("study_worker.py --check-ready"), activate.index('touch "$release_dir/.deployment_succeeded"'))
        self.assertIn("systemctl is-active --quiet flama-study-worker.service", activate)
        self.assertIn('STUDY_ASYNC_BATCH_ENABLED: ${{ vars.STUDY_ASYNC_BATCH_ENABLED || \'0\' }}', workflow)
        self.assertIn('STUDY_QUEUE_NAMESPACE: ${{ vars.STUDY_QUEUE_NAMESPACE || \'flama-production\' }}', workflow)

    def test_code_rollback_quiesces_writers_then_checks_data_before_restoring_environment(self):
        workflow = deployment_source()
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

    def test_consumer_unit_uses_same_environment_and_graceful_stop(self):
        unit = (WORKFLOW_PATH.parents[2] / "deploy" / "flama-study-worker.service").read_text(encoding="utf-8")
        self.assertIn("EnvironmentFile=/etc/flama/flama.env", unit)
        self.assertIn("WorkingDirectory=/opt/flama/current", unit)
        self.assertIn("ExecStart=/opt/flama/venv/bin/python study_worker.py", unit)
        self.assertIn("KillSignal=SIGTERM", unit)
        self.assertNotIn("db upgrade", unit)

    def test_ci_container_and_vps_run_the_interpreter_named_in_python_version(self):
        root = WORKFLOW_PATH.parents[2]
        version = (root / ".python-version").read_text(encoding="utf-8").strip()
        ci = (root / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8")
        activation = ACTIVATION_PATH.read_text(encoding="utf-8")
        self.assertRegex(version, r"^3\.\d+$")
        self.assertNotIn("python-version:", ci)
        self.assertEqual(ci.count("uses: actions/setup-python@"), ci.count("python-version-file: '.python-version'"))
        self.assertIn(f"FROM python:{version}-slim", (root / "Dockerfile").read_text(encoding="utf-8"))
        self.assertIn('"$release_dir/.python-version"', activation)
        self.assertNotRegex(activation, r"(?m)^\s*python3\s")

    def test_new_interpreter_venv_is_built_before_quiesce_and_linked_while_writers_stopped(self):
        activation = ACTIVATION_PATH.read_text(encoding="utf-8")
        body = activation[activation.index('test -f "$environment_file"'):]
        build = body.index('"$runtime_venv/bin/pip" install')
        quiesce = body.index("phase=quiescing")
        stop_writers = body.index('systemctl stop "$unit"')
        switch = body.index("\nswitch_runtime_venv\n")
        migrate = body.index("deploy/migrate_database.py")
        self.assertLess(build, quiesce)
        self.assertLess(stop_writers, switch)
        self.assertLess(switch, migrate)

    def test_existing_study_retention_is_quiesced_and_only_resumed_if_previously_enabled(self):
        activation = ACTIVATION_PATH.read_text(encoding="utf-8")
        quiesce = activation[activation.index("phase=quiescing"):activation.index("phase=migrating")]
        self.assertIn("flama-study-retention.timer flama-study-retention.service", quiesce)
        health = activation[activation.index("phase=health"):]
        self.assertIn('if [ "$previous_study_retention_timer_enabled" -eq 1 ]; then\n      systemctl enable --now flama-study-retention.timer', health)


class DeployRollbackShellTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.bash = shutil.which("bash")
        if not cls.bash and Path("C:/Program Files/Git/bin/bash.exe").is_file():
            cls.bash = "C:/Program Files/Git/bin/bash.exe"
        if not cls.bash:
            raise unittest.SkipTest("Bash is required for the stubbed deploy-shell rehearsal.")

    def _rollback(self, *, check_exit=0, quiesce_exit=0, consumer_stop_exit=0,
                  history_exit=0, field_exit=0, previous_worker=True, venv_switched=0,
                  study_retention_stop_exit=0):
        workflow = deployment_source()
        function = workflow[workflow.index("rollback_activation() {"):workflow.index("cleanup() {")]
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            previous = fixture / "previous"
            (previous / "deploy").mkdir(parents=True)
            current = fixture / "current"
            (current / "deploy").mkdir(parents=True)
            (current / "deploy" / "flama-review-analytics-worker.service").write_text("test fixture only", encoding="utf-8")
            (current / "deploy" / "check_field_code_rollback.py").write_text("test fixture only", encoding="utf-8")
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
                "PROJECT_DIR=/test-project", "release_dir=" + shlex.quote(current.as_posix()),
                "environment_file=/test-environment",
                "environment_backup_file=" + shlex.quote(backup.as_posix()),
                "previous_release=" + shlex.quote(previous.as_posix()),
                f"venv_switched={venv_switched}", "previous_venv=/test-project/venv-legacy",
                f"CHECK_EXIT={check_exit}", f"QUIESCE_EXIT={quiesce_exit}", f"CONSUMER_STOP_EXIT={consumer_stop_exit}",
                f"HISTORY_EXIT={history_exit}",
                f"FIELD_EXIT={field_exit}",
                f"STUDY_RETENTION_STOP_EXIT={study_retention_stop_exit}",
                '''systemctl() {
                  printf '%s\\n' "systemctl $*"
                  if [ "$*" = 'stop flama.service flama-connect.service' ]; then return "$QUIESCE_EXIT"; fi
                  if [ "$*" = 'stop flama-study-worker.service' ]; then return "$CONSUMER_STOP_EXIT"; fi
                  if [ "$*" = 'stop flama-study-retention.timer flama-study-retention.service' ]; then return "$STUDY_RETENTION_STOP_EXIT"; fi
                  return 0
                }
                systemd-run() {
                  printf '%s\\n' "systemd-run $*"
                  case "$*" in *review-analytics-rollback-check*) return "$HISTORY_EXIT" ;; esac
                  case "$*" in *check_field_code_rollback.py*) return "$FIELD_EXIT" ;; esac
                  return "$CHECK_EXIT"
                }
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
        output, errors = self._rollback(check_exit=1, venv_switched=1)
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

    def test_cannot_stop_study_retention_blocks_rollback_before_inspection(self):
        output, errors = self._rollback(study_retention_stop_exit=1)
        self.assertNotIn("systemd-run", output)
        self.assertNotIn("cp ", output)
        self.assertNotIn("ln ", output)
        self.assertIn("Study retention writer did not stop", errors)

    def test_safe_rollback_restores_consumer_with_previous_release(self):
        output, errors = self._rollback()
        self.assertLess(output.index("--check-code-rollback"), output.index("stop flama-study-worker.service"))
        self.assertLess(output.index("stop flama-study-worker.service"), output.index("cp "))
        self.assertLess(output.index("ln "), output.index("restart flama-study-worker.service"))
        self.assertIn("Previous release restored", errors)
        self.assertNotIn("/test-project/venv-legacy", output)

    def test_safe_rollback_points_venv_back_before_restarting_previous_release(self):
        output, errors = self._rollback(venv_switched=1)
        relink = output.index("ln -sfn /test-project/venv-legacy /test-project/venv")
        self.assertLess(output.index("stop flama-study-worker.service"), relink)
        self.assertLess(relink, output.index("restart flama.service"))
        self.assertIn("Previous release restored", errors)

    def _switch_venv(self, project):
        coordinator = ACTIVATION_PATH.read_text(encoding="utf-8")
        function = coordinator[coordinator.index("switch_runtime_venv() {"):coordinator.index("cleanup() {")]
        # Only ln is stubbed; -d/-L/mv act on the generated fixture directory.
        script = "\n".join((
            "set -Eeuo pipefail",
            "PROJECT_DIR=" + shlex.quote(project.as_posix()),
            'runtime_venv="$PROJECT_DIR/venv-3.12"', 'previous_venv=""', "venv_switched=0",
            "ln() { printf '%s\\n' \"ln $*\"; }",
            function, "switch_runtime_venv",
            'echo "switched=$venv_switched previous=$previous_venv"',
        ))
        env = {key: value for key, value in os.environ.items() if key not in {"BASH_ENV", "ENV"}}
        result = subprocess.run([self.bash, "--noprofile", "--norc", "-s"], input=script, text=True, capture_output=True, timeout=10, env=env)
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout

    def test_legacy_venv_directory_is_kept_for_rollback_and_link_points_to_runtime(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            (project / "venv" / "bin").mkdir(parents=True)
            output = self._switch_venv(project)
            self.assertTrue((project / "venv-legacy" / "bin").is_dir())
        root = project.as_posix()
        self.assertIn(f"ln -sfn {root}/venv-3.12 {root}/venv", output)
        self.assertIn(f"switched=1 previous={root}/venv-legacy", output)

    def test_first_host_links_runtime_venv_without_a_rollback_target(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory)
            output = self._switch_venv(project)
        self.assertIn(f"ln -sfn {project.as_posix()}/venv-3.12 {project.as_posix()}/venv", output)
        self.assertIn("switched=0 previous=\n", output)

    @unittest.skipUnless(os.name == "posix", "Needs POSIX symlinks with matching path spelling.")
    def test_venv_already_on_runtime_interpreter_is_left_alone(self):
        with tempfile.TemporaryDirectory() as directory:
            project = Path(directory).resolve()
            (project / "venv-3.12").mkdir()
            (project / "venv").symlink_to(project / "venv-3.12", target_is_directory=True)
            output = self._switch_venv(project)
        self.assertNotIn("ln ", output)
        self.assertIn("switched=0", output)

    def test_pending_history_gate_preserves_environment_and_selected_release(self):
        output, errors = self._rollback(history_exit=1)
        self.assertIn("stop flama-study-worker.service", output)
        self.assertIn("review-analytics-rollback-check --writers-quiesced", output)
        self.assertNotIn("cp ", output)
        self.assertNotIn("ln ", output)
        self.assertIn("drain committed history revisions", errors)

    def test_field_contraction_blocks_restoring_an_incompatible_binary(self):
        output, errors = self._rollback(field_exit=1)
        self.assertIn("check_field_code_rollback.py", output)
        self.assertNotIn("cp ", output)
        self.assertNotIn("ln ", output)
        self.assertIn("contracted Field ID storage", errors)

    def test_pre_consumer_release_disables_obsolete_unit_after_safe_gate(self):
        output, errors = self._rollback(previous_worker=False)
        self.assertIn("disable flama-study-worker.service", output)
        self.assertNotIn("restart flama-study-worker.service", output)
        self.assertIn("Previous release restored", errors)

    def test_coordinator_and_transport_have_valid_bash_syntax(self):
        for path in (ACTIVATION_PATH, LAUNCHER_PATH):
            with self.subTest(path=path.name):
                result = subprocess.run([self.bash, "--noprofile", "--norc", "-n", str(path)], text=True, capture_output=True, timeout=10)
                self.assertEqual(result.returncode, 0, result.stderr)

    def test_deployment_lifetime_and_stdio_are_owned_by_systemd(self):
        launcher = LAUNCHER_PATH.read_text(encoding="utf-8")
        coordinator = ACTIVATION_PATH.read_text(encoding="utf-8")
        self.assertIn("--property=StandardInput=null", launcher)
        self.assertIn("--property=StandardOutput=journal", launcher)
        self.assertIn("--property=StandardError=journal", launcher)
        self.assertIn("--property=RemainAfterExit=yes", launcher)
        self.assertNotIn("--pipe", coordinator)
        self.assertIn('flock -n 9', coordinator)
        self.assertIn('record_state failed', coordinator)
        self.assertIn('record_state succeeded', coordinator)
        self.assertIn('phase=migrating', coordinator)
        self.assertIn('phase=activating', coordinator)
        self.assertIn('phase=health', coordinator)

    def test_failed_cleanup_preserves_recovery_files_and_original_error(self):
        coordinator = ACTIVATION_PATH.read_text(encoding="utf-8")
        cleanup = coordinator[coordinator.index("cleanup() {"):coordinator.index("trap cleanup EXIT")]
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            artifacts = [fixture / name for name in ("archive", "payload", "desired", "backup")]
            for artifact in artifacts:
                artifact.write_text("recovery evidence", encoding="utf-8")
            assignments = "\n".join(name + "=" + shlex.quote(path.as_posix()) for name, path in zip(
                ("archive_path", "managed_env_payload_path", "desired_environment_file", "environment_backup_file"), artifacts))
            script = "\n".join(("set -Eeuo pipefail", assignments,
                "rollback_activation() { false; echo UNSAFE_CONTINUATION; }", "record_state() { echo STATE=$1; }",
                cleanup, "trap cleanup EXIT", "exit 42"))
            result = subprocess.run([self.bash, "--noprofile", "--norc", "-s"], input=script, text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 42, result.stderr)
            self.assertIn("STATE=failed", result.stdout)
            self.assertNotIn("UNSAFE_CONTINUATION", result.stdout)
            self.assertTrue(all(path.exists() for path in artifacts))

    def test_ssh_loss_after_start_and_during_observation_reconnects_without_restarting(self):
        with tempfile.TemporaryDirectory() as directory:
            fixture = Path(directory)
            script = "\n".join((
                "set -Eeuo pipefail",
                "fixture_path=" + shlex.quote(fixture.as_posix()),
                "SSH_HOST=fixture SSH_USER=fixture SSH_PORT=22 PROJECT_DIR=/opt/flama",
                "RELEASE_ID=" + "a" * 40,
                "DEPLOYMENT_ID=" + "a" * 40 + "-123-1",
                '''ssh() {
                  case "${!#}" in
                    *"cat >"*) cat >/dev/null ;;
                    *"systemd-run"*)
                      if [ ! -f "$fixture_path/started" ]; then
                        echo once > "$fixture_path/started"
                        echo 'running migrating' > "$fixture_path/state"
                        # Emulate systemd ownership: the producer has its own
                        # stdin/stdout/stderr, independent of the failed SSH.
                        nohup bash -c 'sleep .2; echo "succeeded health" > "$1/state"' _ "$fixture_path" </dev/null >/dev/null 2>&1 &
                        return 255
                      fi
                      ;;
                    *"cat '"*)
                      if [ ! -f "$fixture_path/observation_lost" ]; then
                        touch "$fixture_path/observation_lost"
                        return 255
                      fi
                      cat "$fixture_path/state"
                      ;;
                    *"systemctl show"*) echo active ;;
                    *) return 2 ;;
                  esac
                }
                sleep() { command sleep .03; }
                ''',
                "source " + shlex.quote(LAUNCHER_PATH.as_posix()),
            ))
            result = subprocess.run([self.bash, "--noprofile", "--norc", "-s"], input=script,
                cwd=WORKFLOW_PATH.parents[2], text=True, capture_output=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
            self.assertIn("SSH start response unavailable", result.stdout)
            self.assertIn("SSH observation interrupted", result.stdout)
            self.assertIn("succeeded health", result.stdout)
            self.assertEqual((fixture / "started").read_text().strip(), "once")


if __name__ == "__main__":
    unittest.main()
