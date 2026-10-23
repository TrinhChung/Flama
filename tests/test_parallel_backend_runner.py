"""Process-only runner regressions: no Flask app, database, or external service."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import redirect_stdout
import ctypes
import io
import os
from pathlib import Path
import signal
import shutil
import subprocess
import sys
import tempfile
import textwrap
import time
import unittest
from unittest import mock

from scripts import run_tests


class ManagedBackendRunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="flama-runner-regression-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.counter = 0
        self.pids = []
        self.addCleanup(self._cleanup_processes)

    def _cleanup_processes(self):
        for pid in self.pids:
            if self._alive(pid):
                if sys.platform == "win32":
                    subprocess.run(
                        ["taskkill", "/T", "/F", "/PID", str(pid)],
                        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5,
                    )
                else:
                    try:
                        os.kill(pid, signal.SIGKILL)
                    except ProcessLookupError:
                        pass

    @staticmethod
    def _alive(pid):
        if sys.platform == "win32":
            from ctypes import wintypes
            api = ctypes.WinDLL("kernel32", use_last_error=True)
            api.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
            api.OpenProcess.restype = wintypes.HANDLE
            api.GetExitCodeProcess.argtypes = [wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD)]
            api.CloseHandle.argtypes = [wintypes.HANDLE]
            handle = api.OpenProcess(0x1000, False, pid)
            if not handle:
                return False
            try:
                code = wintypes.DWORD()
                return bool(api.GetExitCodeProcess(handle, ctypes.byref(code))) and code.value == 259
            finally:
                api.CloseHandle(handle)
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return False
        # A killed orphan awaiting init's reap cannot execute or hold a pipe.
        try:
            return Path(f"/proc/{pid}/stat").read_text().split(") ", 1)[1][0] != "Z"
        except (OSError, IndexError):
            return True

    def _module(self, source):
        self.counter += 1
        path = self.root / f"test_worker_fixture_{self.counter}.py"
        path.write_text(textwrap.dedent(source), encoding="utf-8")
        return str(path)

    def _command(self, _python, files, failfast, verbose):
        arguments = ["-f"] if failfast else []
        if verbose:
            arguments.append("-v")
        arguments.extend(Path(path).stem for path in files)
        code = (
            f"import sys,runpy; sys.path.insert(0,{str(self.root)!r}); "
            f"sys.argv=['unittest',*{arguments!r}]; "
            "runpy.run_module('scripts.unittest_manifest',run_name='__main__')"
        )
        return [sys.executable, "-c", code]

    def _bin(self, files, **kwargs):
        self.counter += 1
        with mock.patch.object(run_tests, "_manifest_command", side_effect=self._command):
            return run_tests._run_backend_bin(
                [sys.executable], files, False, False,
                log_path=str(self.root / f"bin-{self.counter}.log"), base_env=dict(os.environ), **kwargs,
            )

    def _child_source(self, pid_path, *, hang=True):
        return f"""
            import os, subprocess, sys, time, unittest
            from pathlib import Path
            class Child(unittest.TestCase):
                def test_child(self):
                    child = subprocess.Popen(
                        [sys.executable, '-c', 'import time; time.sleep(60)'],
                        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    )
                    Path({str(pid_path)!r}).write_text(str(child.pid))
                    {'time.sleep(60)' if hang else 'self.assertGreater(child.pid, 0)'}
        """

    def _read_pid(self, path):
        pid = int(path.read_text())
        self.pids.append(pid)
        return pid

    def _wait_for(self, path):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            try:
                if path.read_text().strip():
                    return
            except OSError:
                pass
            time.sleep(0.01)
        self.fail(f"worker did not finish writing {path.name}")

    def test_default_one_job_is_one_managed_unittest_process(self):
        first = self._module("""
            import os, unittest
            from pathlib import Path
            class T(unittest.TestCase):
                def test_pid(self):
                    with Path(PID_PATH).open('a') as handle:
                        handle.write(str(os.getpid()) + '\\n')
        """.replace("PID_PATH", repr(str(self.root / "pids"))))
        second = self._module(Path(first).read_text())
        with mock.patch.object(run_tests, "_manifest_command", side_effect=self._command), redirect_stdout(io.StringIO()):
            self.assertTrue(run_tests.run_backend_tests([sys.executable], [first, second]))
        ids = (self.root / "pids").read_text().splitlines()
        self.assertEqual(len(ids), 2)
        self.assertEqual(len(set(ids)), 1)

    def test_actual_script_cli_works_without_pythonpath_or_script_import_path(self):
        # A tiny disposable checkout exercises the real file entry point,
        # including imports in the coordinator and the child interpreter.
        repo = self.root / "cli-repo"
        (repo / "scripts").mkdir(parents=True)
        (repo / "tests").mkdir()
        for name in ("run_tests.py", "unittest_manifest.py"):
            shutil.copyfile(run_tests.ROOT_DIR / "scripts" / name, repo / "scripts" / name)
        (repo / "scripts" / "__init__.py").write_text("")
        (repo / "tests" / "__init__.py").write_text("")
        (repo / "tests" / "test_cli_fixture.py").write_text(
            "import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): self.assertEqual(2+2,4)\n"
        )
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)
        result = subprocess.run(
            [sys.executable, "-I", str(repo / "scripts" / "run_tests.py"),
             "--file", "tests/test_cli_fixture.py", "--backend-only", "--bin-timeout", "10"],
            cwd=repo, env=env, capture_output=True, text=True, timeout=20,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("1 tests", result.stdout)

    def test_timeout_applies_when_requested_jobs_collapse_to_one_file(self):
        pid_path = self.root / "child.pid"
        path = self._module(self._child_source(pid_path))
        started = time.monotonic()
        with mock.patch.object(run_tests, "_manifest_command", side_effect=self._command), redirect_stdout(io.StringIO()):
            self.assertFalse(run_tests.run_backend_tests([sys.executable], [path], jobs=2, bin_timeout=0.8))
        self.assertLess(time.monotonic() - started, 10)
        self.assertFalse(self._alive(self._read_pid(pid_path)))

    def test_timeout_kills_descendant_and_removes_worker_media(self):
        pid_path = self.root / "child.pid"
        media_path = self.root / "media.txt"
        source = self._child_source(pid_path).replace(
            "time.sleep(60)\n", f"Path({str(media_path)!r}).write_text(os.environ['TEMP']); time.sleep(60)\n"
        )
        result = self._bin([self._module(source)], timeout=0.8)
        self.assertFalse(result.passed)
        self.assertIn("[TIMEOUT]", result.read_output())
        self.assertFalse(self._alive(self._read_pid(pid_path)))
        self.assertFalse(Path(media_path.read_text()).exists())

    def test_exited_successful_root_cannot_leave_descendant_alive(self):
        pid_path = self.root / "child.pid"
        result = self._bin([self._module(self._child_source(pid_path, hang=False))])
        self.assertTrue(result.passed, result.read_output())
        self.assertFalse(self._alive(self._read_pid(pid_path)))

    def test_concurrent_successful_roots_wait_for_descendants_before_returning(self):
        paths = [self.root / f"concurrent-child-{index}.pid" for index in range(4)]
        files = [self._module(self._child_source(path, hang=False)) for path in paths]
        with mock.patch.object(run_tests, "_manifest_command", side_effect=self._command), redirect_stdout(io.StringIO()):
            self.assertTrue(run_tests.run_backend_tests_parallel(
                [sys.executable], files, jobs=2, weights=dict.fromkeys(files, 1),
            ))
        for index, path in enumerate(paths):
            with self.subTest(worker=index):
                self.assertFalse(self._alive(self._read_pid(path)))

    def test_failfast_stops_running_tree_and_pending_bins(self):
        pid_path = self.root / "slow-child.pid"
        slow = self._module(self._child_source(pid_path))
        fail = self._module(f"""
            import time, unittest
            from pathlib import Path
            class T(unittest.TestCase):
                def test_fail(self):
                    deadline = time.monotonic() + 5
                    while not Path({str(pid_path)!r}).exists() and time.monotonic() < deadline:
                        time.sleep(0.01)
                    self.assertTrue(Path({str(pid_path)!r}).exists())
                    self.fail('stop siblings')
        """)
        marker = self.root / "pending.txt"
        pending = [self._module(f"""
            import unittest
            from pathlib import Path
            class T(unittest.TestCase):
                def test_pending(self):
                    Path({str(marker)!r}).write_text('should not start')
        """) for _ in range(2)]
        files = [slow, fail, *pending]
        weights = {path: 4 - index for index, path in enumerate(files)}
        started = time.monotonic()
        with mock.patch.object(run_tests, "_manifest_command", side_effect=self._command), redirect_stdout(io.StringIO()):
            self.assertFalse(run_tests.run_backend_tests_parallel(
                [sys.executable], files, jobs=2, failfast=True, weights=weights,
            ))
        self.assertLess(time.monotonic() - started, 10)
        self.assertFalse(marker.exists())
        self.assertFalse(self._alive(self._read_pid(pid_path)))

    def test_noisy_worker_is_drained_with_bounded_disk_and_emission(self):
        path = self._module("""
            import sys, unittest
            class T(unittest.TestCase):
                def test_noise(self):
                    sys.stdout.write('HEAD' + 'x' * (3 * 1024 * 1024) + 'TAIL')
        """)
        result = self._bin([path], timeout=8)
        self.assertTrue(result.passed, result.note)
        self.assertLessEqual(Path(result.log_path).stat().st_size, run_tests.BACKEND_LOG_LIMIT_BYTES)
        output = result.read_output()
        self.assertIn("HEAD", output)
        self.assertIn("TAIL", output)
        self.assertIn("[OUTPUT TRUNCATED", output)
        emitted = io.StringIO()
        result.write_output(emitted)
        self.assertLessEqual(len(emitted.getvalue()), run_tests.BACKEND_LOG_LIMIT_BYTES + 1)

    def test_forged_printed_summary_and_exit_zero_do_not_pass(self):
        source = "import os,sys; print('Ran 100 tests in 0.1s\\n\\nOK',flush=True); os._exit(0)"
        with mock.patch.object(run_tests, "_manifest_command", return_value=[sys.executable, "-c", source]):
            result = run_tests._run_backend_bin(
                [sys.executable], ["fake"], False, False,
                log_path=str(self.root / "fake.log"), base_env=dict(os.environ),
            )
        self.assertFalse(result.passed)
        self.assertIn("[MANIFEST ERROR]", result.note)

    def test_partial_failure_removes_stale_requested_manifest(self):
        export = self.root / "old-success.json"
        export.write_text("previous successful result")
        with mock.patch.object(run_tests, "_run_backend_bin", side_effect=OSError("cannot spawn")), \
                redirect_stdout(io.StringIO()):
            self.assertFalse(run_tests.run_backend_tests_parallel(
                [sys.executable], ["fake"], jobs=1, weights={"fake": 1}, manifest=str(export),
            ))
        self.assertFalse(export.exists())

    def test_unexpected_empty_suite_fails(self):
        result = self._bin([self._module("import unittest\n")])
        self.assertFalse(result.passed)

    def test_import_error_fails_with_diagnostics(self):
        result = self._bin([self._module("import definitely_missing_flama_runner_fixture\n")])
        self.assertFalse(result.passed)
        self.assertIn("definitely_missing_flama_runner_fixture", result.read_output())

    def test_fixture_skip_with_zero_started_tests_remains_valid(self):
        result = self._bin([self._module("""
            import unittest
            class T(unittest.TestCase):
                @classmethod
                def setUpClass(cls):
                    raise unittest.SkipTest('platform unavailable')
                def test_unused(self):
                    self.fail('must not execute')
        """)])
        self.assertTrue(result.passed, result.read_output())
        self.assertEqual(result.summary.ran, 0)
        self.assertEqual(result.summary.counts, {"skipped": 1})

    def test_common_environment_pins_snapshots_and_preserves_intentional_flags(self):
        parent = {"UPDATE_SNAPSHOT": "1", "UPDATE_ROUTE_SNAPSHOT": "yes", "STUDY_WIRE_V4_ENABLED": "1"}
        before = dict(parent)
        for environment in (
            run_tests.build_backend_test_environment("media", parent),
            run_tests.build_parallel_worker_environment("media", parent),
        ):
            self.assertEqual(environment["UPDATE_SNAPSHOT"], "0")
            self.assertEqual(environment["UPDATE_ROUTE_SNAPSHOT"], "0")
            self.assertEqual(environment["STUDY_WIRE_V4_ENABLED"], "1")
        self.assertEqual(parent, before)

    def test_nonfinite_and_negative_timeouts_are_rejected_before_spawn(self):
        for value in (float("nan"), float("inf"), -1):
            with self.subTest(value=value), mock.patch.object(run_tests.subprocess, "Popen") as spawn:
                with self.assertRaises(ValueError):
                    run_tests.run_backend_tests([sys.executable], ["missing"], bin_timeout=value)
                spawn.assert_not_called()

    def test_late_launch_does_not_release_test_code_after_stop(self):
        registry = run_tests._WorkerRegistry()
        marker = self.root / "late.txt"
        env = run_tests.build_parallel_worker_environment(str(self.root), dict(os.environ))
        env["FLAMA_TEST_GATE_PID_PATH"] = str(self.root / "late.pid")
        command = [sys.executable, "-c", f"from pathlib import Path; Path({str(marker)!r}).write_text('late')"]
        original = subprocess.Popen

        def stop_during_spawn(*args, **kwargs):
            proc = original(*args, **kwargs)
            registry.stopped.set()
            return proc

        with mock.patch.object(run_tests.subprocess, "Popen", side_effect=stop_during_spawn):
            proc = registry.launch(command, env, env["FLAMA_TEST_GATE_PID_PATH"])
        self.addCleanup(proc.stdout.close)
        self.addCleanup(proc.stdin.close)
        registry.discard(proc)
        self.assertIsNotNone(proc.returncode)
        self.assertFalse(marker.exists())

    def test_interrupt_during_submit_and_consume_stops_tree_before_shutdown(self):
        for phase in ("submit", "consume"):
            for signum in (signal.SIGINT, signal.SIGTERM):
                with self.subTest(phase=phase, signum=signum):
                    self._interrupt_case(phase, signum)

    def _interrupt_case(self, phase, signum):
        pid_path = self.root / f"interrupt-{phase}-{signum}.pid"
        slow = self._module(self._child_source(pid_path))
        another = self._module("import unittest\nclass T(unittest.TestCase):\n    def test_ok(self): pass\n")
        owner = self
        shutdown_checks = []

        def interrupt():
            owner._wait_for(pid_path)
            owner._read_pid(pid_path)
            signal.raise_signal(signum)

        class Executor(ThreadPoolExecutor):
            count = 0
            def submit(self, *args, **kwargs):
                self.count += 1
                if phase == "submit" and self.count == 2:
                    interrupt()
                return super().submit(*args, **kwargs)

            def shutdown(self, *args, **kwargs):
                shutdown_checks.append(not owner._alive(int(pid_path.read_text())))
                return super().shutdown(*args, **kwargs)

        def consume(_futures):
            interrupt()
            yield  # generator protocol; unreachable after the signal

        patches = [mock.patch.object(run_tests, "ThreadPoolExecutor", Executor)]
        if phase == "consume":
            patches.append(mock.patch.object(run_tests, "as_completed", consume))
        with mock.patch.object(run_tests, "_manifest_command", side_effect=self._command), redirect_stdout(io.StringIO()):
            with patches[0]:
                if len(patches) == 2:
                    patches[1].start()
                try:
                    with self.assertRaises(KeyboardInterrupt):
                        run_tests.run_backend_tests_parallel(
                            [sys.executable], [slow, another], jobs=2,
                            weights={slow: 100, another: 1},
                        )
                finally:
                    if len(patches) == 2:
                        patches[1].stop()
        self.assertEqual(shutdown_checks, [True])

    @unittest.skipUnless(sys.platform == "win32", "Windows kill-on-close Job Object contract")
    def test_abrupt_windows_coordinator_exit_kills_its_worker_tree(self):
        pid_path = self.root / "abrupt-child.pid"
        worker_path = self.root / "abrupt-worker.pid"
        module = self._module(self._child_source(pid_path).replace(
            "child = subprocess.Popen(",
            f"Path({str(worker_path)!r}).write_text(str(os.getpid())); child = subprocess.Popen(",
        ))
        command = self._command(None, [module], False, False)
        code = (
            "from scripts import run_tests; "
            f"run_tests._manifest_command=lambda *args: {command!r}; "
            f"run_tests.run_backend_tests_parallel([{sys.executable!r}],[{module!r}],jobs=1)"
        )
        coordinator = subprocess.Popen(
            [sys.executable, "-c", code], cwd=str(run_tests.ROOT_DIR),
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        self.addCleanup(lambda: coordinator.poll() is None and coordinator.kill())
        self._wait_for(pid_path)
        child_pid = self._read_pid(pid_path)
        worker_pid = self._read_pid(worker_path)
        coordinator.terminate()
        coordinator.wait(timeout=5)
        deadline = time.monotonic() + 5
        while (self._alive(worker_pid) or self._alive(child_pid)) and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertFalse(self._alive(worker_pid))
        self.assertFalse(self._alive(child_pid))

    @unittest.skipUnless(sys.platform == "win32", "Windows Job Object launch failure contract")
    def test_failed_job_assignment_reaps_gated_worker_without_loading_tests(self):
        marker = self.root / "unowned-test.txt"
        path = self._module(f"""
            from pathlib import Path
            Path({str(marker)!r}).write_text('must not execute')
        """)
        original = subprocess.Popen
        processes = []

        def spawn(*args, **kwargs):
            proc = original(*args, **kwargs)
            processes.append(proc)
            return proc

        with mock.patch.object(run_tests._WindowsJob, "assign_handle", side_effect=OSError("assignment failed")), \
                mock.patch.object(run_tests.subprocess, "Popen", side_effect=spawn):
            with self.assertRaisesRegex(OSError, "assignment failed"):
                self._bin([path])
        self.assertTrue(processes)
        self.assertTrue(all(proc.poll() is not None for proc in processes))
        self.assertFalse(marker.exists())

    def test_cpu_quota_caps_affinity_count_on_linux(self):
        directory = Path("/fake/cgroup")
        with mock.patch.object(run_tests.sys, "platform", "linux"), \
                mock.patch.object(run_tests.os, "cpu_count", return_value=16), \
                mock.patch.object(run_tests.os, "process_cpu_count", return_value=16, create=True), \
                mock.patch.object(run_tests, "_cgroup_directories", return_value=[(directory, True)]), \
                mock.patch.object(run_tests, "_resource_text", return_value="150000 100000"):
            self.assertEqual(run_tests.effective_cpu_count(), 1)

    def test_memory_limit_uses_cgroup_remaining_instead_of_host_ram(self):
        directory = Path("/fake/cgroup")
        values = {directory / "memory.max": str(2 * 1024**3), directory / "memory.current": str(1536 * 1024**2)}
        with mock.patch.object(run_tests.sys, "platform", "linux"), \
                mock.patch("builtins.open", mock.mock_open(read_data="MemAvailable: 4194304 kB\n")), \
                mock.patch.object(run_tests, "_cgroup_directories", return_value=[(directory, True)]), \
                mock.patch.object(run_tests, "_resource_text", side_effect=values.get):
            self.assertEqual(run_tests.available_memory_bytes(), 512 * 1024**2)

    def test_hidden_cgroup_memory_limit_conservatively_allows_one_worker(self):
        with mock.patch.object(run_tests.sys, "platform", "linux"), \
                mock.patch("builtins.open", mock.mock_open(read_data="MemAvailable: 4194304 kB\n")), \
                mock.patch.object(run_tests, "_cgroup_directories", return_value=[(Path("/hidden"), True)]), \
                mock.patch.object(run_tests, "_resource_text", return_value=None):
            self.assertEqual(run_tests.memory_worker_limit(), 1)

    @unittest.skipIf(sys.platform == "win32", "POSIX real SIGINT/SIGTERM forwarding contract")
    def test_posix_signals_stop_coordinator_and_descendant_tree(self):
        for signum in (signal.SIGINT, signal.SIGTERM):
            with self.subTest(signum=signum):
                pid_path = self.root / f"posix-child-{signum}.pid"
                module = self._module(self._child_source(pid_path))
                command = self._command(None, [module], False, False)
                code = (
                    "from scripts import run_tests; "
                    f"run_tests._manifest_command=lambda *args: {command!r}; "
                    f"run_tests.run_backend_tests_parallel([{sys.executable!r}],[{module!r}],jobs=1)"
                )
                coordinator = subprocess.Popen(
                    [sys.executable, "-c", code], cwd=str(run_tests.ROOT_DIR),
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                try:
                    self._wait_for(pid_path)
                    pid = self._read_pid(pid_path)
                    coordinator.send_signal(signum)
                    self.assertNotEqual(coordinator.wait(timeout=8), 0)
                    self.assertFalse(self._alive(pid))
                finally:
                    if coordinator.poll() is None:
                        coordinator.kill()
                    coordinator.wait(timeout=5)


class PosixCleanupContracts(unittest.TestCase):
    """Deterministic Linux cleanup races, also executable on Windows hosts."""

    def test_cleanup_reaps_root_and_waits_until_group_has_no_live_members(self):
        proc = mock.Mock(pid=123, _flama_job=None, _flama_session=True)
        proc.poll.return_value = 0  # The root exited before its child.
        order = mock.Mock()
        with mock.patch.object(run_tests.sys, "platform", "linux"), \
                mock.patch.object(run_tests.signal, "SIGKILL", 9, create=True), \
                mock.patch.object(run_tests.os, "killpg", create=True) as kill, \
                mock.patch.object(run_tests, "_posix_process_group_alive", side_effect=[True, True, False]) as alive, \
                mock.patch.object(run_tests.time, "sleep") as sleep:
            order.attach_mock(kill, "kill")
            order.attach_mock(proc.wait, "reap")
            order.attach_mock(alive, "alive")
            run_tests._terminate_process_tree(proc)
        self.assertEqual(order.mock_calls, [
            mock.call.kill(123, 9),
            mock.call.reap(timeout=run_tests.BACKEND_CLEANUP_TIMEOUT),
            mock.call.alive(123), mock.call.alive(123), mock.call.alive(123),
        ])
        self.assertEqual(sleep.call_count, 2)

    def test_live_group_past_deadline_fails_cleanup(self):
        proc = mock.Mock(pid=123, _flama_job=None, _flama_session=True)
        proc.poll.return_value = 0
        with mock.patch.object(run_tests.sys, "platform", "linux"), \
                mock.patch.object(run_tests.signal, "SIGKILL", 9, create=True), \
                mock.patch.object(run_tests.os, "killpg", create=True), \
                mock.patch.object(run_tests, "_posix_process_group_alive", return_value=True), \
                mock.patch.object(run_tests.time, "monotonic", side_effect=[0, run_tests.BACKEND_CLEANUP_TIMEOUT + 1]):
            with self.assertRaisesRegex(RuntimeError, "POSIX worker group 123 did not terminate"):
                run_tests._terminate_process_tree(proc)
        proc.wait.assert_called_once()

    def test_linux_group_scan_ignores_zombies_other_groups_and_vanished_processes(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for pid, state, group in ((11, "Z", 123), (12, "X", 123), (13, "S", 456)):
                entry = root / str(pid)
                entry.mkdir()
                (entry / "stat").write_text(f"{pid} (worker ) with spaces) {state} 1 {group} 0")
            (root / "14").mkdir()  # Exited between iterdir() and stat read.
            (root / "self").mkdir()
            with mock.patch.object(run_tests.sys, "platform", "linux"), \
                    mock.patch.object(run_tests.os, "killpg", create=True) as kill, \
                    mock.patch.object(run_tests, "Path", return_value=root):
                self.assertFalse(run_tests._posix_process_group_alive(123))
                (root / "13" / "stat").write_text("13 (live worker) R 1 123 0")
                self.assertTrue(run_tests._posix_process_group_alive(123))
            self.assertEqual(kill.call_args_list, [mock.call(123, 0), mock.call(123, 0)])

    def test_vanished_group_needs_no_proc_scan(self):
        with mock.patch.object(run_tests.os, "killpg", side_effect=ProcessLookupError, create=True), \
                mock.patch.object(run_tests, "Path") as path:
            self.assertFalse(run_tests._posix_process_group_alive(123))
        path.assert_not_called()


if __name__ == "__main__":
    unittest.main()
