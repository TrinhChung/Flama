"""Local coordination watcher contracts; no app, database, network or AI calls."""

from datetime import datetime, timedelta, timezone
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

from scripts import watch_test_coordination as watcher


NOW = datetime(2026, 10, 23, 3, 0, tzinfo=timezone.utc)


def sample_snapshot(value="one", name="scripts/run_tests.py"):
    return {"head": "abc", "dirty_paths": [name], "files": {name: value}, "fingerprint": value}


def completed_review(codex, repo, report, prompt):
    report.write_text("No new issue; no messages delivered.\n", encoding="utf-8")
    return {"success": True, "error": None, "returncode": 0}


class CoordinationStateTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="coordination with spaces ")
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.repo = self.root / "repo with spaces"
        self.state_dir = self.root / "external state"
        self.repo.mkdir()
        self.state_dir.mkdir()
        self.current = sample_snapshot()
        self.patch = mock.patch.object(watcher, "snapshot", side_effect=lambda *unused: self.current)
        self.patch.start()
        self.addCleanup(self.patch.stop)

    def check(self, **kwargs):
        return watcher.check_once(self.repo, self.state_dir, now=kwargs.pop("now", NOW), **kwargs)

    def state(self):
        return json.loads((self.state_dir / "state.json").read_text(encoding="utf-8"))

    def test_static_poll_records_pending_without_spawning_ai(self):
        with mock.patch.object(watcher, "run_review") as review:
            code, result = self.check()
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "pending_review")
        self.assertTrue(result["pending"])
        self.assertEqual(result["attempts_today"], 0)
        review.assert_not_called()

    def test_unchanged_reviewed_content_skips_ai_even_if_head_or_dirty_status_changes(self):
        with mock.patch.object(watcher, "run_review", side_effect=completed_review) as review:
            self.check(review=True, codex="Codex App/codex.exe")
            self.current = {**self.current, "head": "new head", "dirty_paths": []}
            code, result = self.check(review=True, codex="Codex App/codex.exe")
        self.assertEqual(code, 0)
        self.assertEqual(result["status"], "unchanged")
        self.assertEqual(review.call_count, 1)
        self.assertFalse(result["pending"])

    def test_changed_content_requests_read_only_review_and_static_pending_is_retained(self):
        self.check()
        self.current = sample_snapshot("two", "tests/test_modular_test_runner.py")
        self.check()
        with mock.patch.object(watcher, "run_review", side_effect=completed_review) as review:
            _, result = self.check(review=True, codex="Codex App/codex.exe")
        prompt = review.call_args.args[3]
        self.assertIn("scripts/run_tests.py", prompt)
        self.assertIn("tests/test_modular_test_runner.py", prompt)
        self.assertIn("READ-ONLY", prompt)
        self.assertIn("Do not send messages", prompt)
        self.assertIn("0.5 GB", prompt)
        self.assertEqual(result["status"], "reviewed")
        self.assertEqual(result["attempts_today"], 1)
        self.assertTrue((self.state_dir / result["latest_report"]).exists())

    def test_daily_cap_resets_at_tokyo_midnight_and_retains_pending(self):
        before_midnight = datetime(2026, 10, 23, 14, 59, tzinfo=timezone.utc)
        with mock.patch.object(watcher, "run_review", side_effect=completed_review) as review:
            for number in range(4):
                self.current = sample_snapshot(str(number))
                self.check(review=True, codex="codex", now=before_midnight)
            self.current = sample_snapshot("fifth")
            _, result = self.check(review=True, codex="codex", now=before_midnight)
            self.assertEqual(result["status"], "daily_limit")
            self.assertTrue(result["pending"])
            self.assertEqual(review.call_count, 4)
            _, result = self.check(review=True, codex="codex", now=before_midnight + timedelta(minutes=1))
        self.assertEqual(result["status"], "reviewed")
        self.assertEqual(result["attempt_day"], "2026-10-24")
        self.assertEqual(result["attempts_today"], 1)

    def test_failure_cooldown_and_retry_each_count_as_attempts(self):
        failure = {"success": False, "error": "timeout", "returncode": -9}
        with mock.patch.object(watcher, "run_review", return_value=failure) as review:
            code, result = self.check(review=True, codex="codex")
            self.assertEqual(code, 1)
            self.assertEqual(result["status"], "review_failed")
            _, result = self.check(review=True, codex="codex", now=NOW + timedelta(minutes=29))
            self.assertEqual(result["status"], "failure_cooldown")
            self.assertEqual(review.call_count, 1)
            self.check(review=True, codex="codex", now=NOW + timedelta(minutes=30))
            self.assertEqual(review.call_count, 2)
        self.assertEqual(self.state()["attempts_today"], 2)
        self.assertTrue(self.state()["pending"])

    def test_attempt_is_persisted_before_process_spawn(self):
        def inspect_and_finish(*args):
            state = self.state()
            self.assertEqual(state["status"], "review_running")
            self.assertEqual(state["attempts_today"], 1)
            return completed_review(*args)
        with mock.patch.object(watcher, "run_review", side_effect=inspect_and_finish):
            self.check(review=True, codex="codex")

    def test_bounded_batches_preserve_overflow_and_do_not_mark_it_reviewed(self):
        files = {f"tests/test_batch_{number:03d}.py": str(number) for number in range(29)}
        self.current = {"head": "abc", "dirty_paths": list(files), "files": files, "fingerprint": "29-files"}
        reviewed = []

        def review_batch(codex, repo, report, prompt):
            paths = json.loads(prompt.split("Changed path data (JSON):\n", 1)[1])
            self.assertLessEqual(len(paths), watcher.MAX_REVIEW_FILES)
            self.assertFalse(set(paths) & set(reviewed))
            reviewed.extend(paths)
            return completed_review(codex, repo, report, prompt)

        with mock.patch.object(watcher, "run_review", side_effect=review_batch):
            _, result = self.check(review=True, codex="codex")
            self.assertEqual(result["status"], "reviewed_partial")
            self.assertTrue(result["pending"])
            self.assertEqual(len(result["pending_paths"]), 17)
            self.assertNotIn("reviewed_fingerprint", self.state())
            # A static poll cannot discard the 17 remaining files.
            self.check()
            _, result = self.check(review=True, codex="codex")
            self.assertEqual(len(result["pending_paths"]), 5)
            _, result = self.check(review=True, codex="codex")
        self.assertEqual(set(reviewed), set(files))
        self.assertEqual(result["status"], "reviewed")
        self.assertFalse(result["pending"])
        self.assertEqual(self.state()["reviewed_fingerprint"], "29-files")

    def test_first_check_baselines_clean_tests_without_claiming_a_review(self):
        self.current = {**sample_snapshot(), "dirty_paths": []}
        with mock.patch.object(watcher, "run_review") as review:
            _, result = self.check(review=True, codex="codex")
        self.assertEqual(result["status"], "baseline")
        self.assertFalse(result["pending"])
        self.assertNotIn("reviewed_fingerprint", self.state())
        review.assert_not_called()

    def test_content_changed_during_review_is_pending_on_next_poll(self):
        def change_during_review(*args):
            self.current = sample_snapshot("changed during review")
            return completed_review(*args)
        with mock.patch.object(watcher, "run_review", side_effect=change_during_review):
            self.check(review=True, codex="codex")
        _, result = self.check()
        self.assertTrue(result["pending"])
        self.assertEqual(result["pending_paths"], ["scripts/run_tests.py"])

    def test_spawn_failure_does_not_claim_review_completed(self):
        with mock.patch.object(watcher, "run_review", side_effect=OSError("secret diagnostic")):
            code, result = self.check(review=True, codex="missing.exe")
        self.assertEqual(code, 1)
        self.assertEqual(result["status"], "review_failed")
        self.assertTrue(result["pending"])
        self.assertNotIn("secret diagnostic", json.dumps(self.state()))

    def test_unavailable_cli_uses_cooldown_without_spawning(self):
        with mock.patch.object(watcher.shutil, "which", return_value=None), mock.patch.object(watcher, "run_review") as review:
            code, result = self.check(review=True)
            self.assertEqual(code, 2)
            self.assertEqual(result["status"], "codex_unavailable")
            _, result = self.check(review=True, now=NOW + timedelta(minutes=1))
            self.assertEqual(result["status"], "failure_cooldown")
        review.assert_not_called()

    def test_corrupt_state_fails_closed_and_cannot_reset_quota(self):
        (self.state_dir / "state.json").write_text("{broken", encoding="utf-8")
        with mock.patch.object(watcher, "run_review") as review, self.assertRaises(watcher.WatcherError):
            self.check(review=True, codex="codex")
        review.assert_not_called()

    def test_atomic_write_failure_preserves_previous_state_and_removes_temp(self):
        path = self.state_dir / "state.json"
        path.write_text('{"previous": true}', encoding="utf-8")
        with mock.patch.object(watcher.os, "replace", side_effect=OSError("interrupted")):
            with self.assertRaises(OSError):
                watcher.atomic_state(path, {"new": True})
        self.assertEqual(json.loads(path.read_text()), {"previous": True})
        self.assertEqual(list(self.state_dir.glob("*.tmp")), [])

    def test_reports_and_state_are_bounded_and_unrelated_files_are_retained(self):
        for number in range(14):
            (self.state_dir / f"report-{number:02d}.md").write_bytes(b"x" * (watcher.MAX_OUTPUT_BYTES + 1))
        untouched = self.state_dir / "personal.txt"
        untouched.write_text("keep")
        watcher.prune_reports(self.state_dir)
        reports = list(self.state_dir.glob("report-*.md"))
        self.assertEqual(len(reports), watcher.REPORTS_TO_KEEP)
        self.assertTrue(all(p.stat().st_size == watcher.MAX_OUTPUT_BYTES for p in reports))
        self.assertEqual(untouched.read_text(), "keep")
        with self.assertRaises(watcher.WatcherError):
            watcher.atomic_state(self.state_dir / "state.json", {"huge": "x" * watcher.MAX_STATE_BYTES})

    def test_cli_rejects_state_inside_repo_and_unsafe_inbox(self):
        for extra in (["--state-dir", str(self.repo / "state")],
                      ["--inbox", "../private.md"], ["--inbox", "C:/private.md"],
                      ["--inbox", ".env/private.md"]):
            with self.subTest(extra=extra), mock.patch("sys.stderr", new_callable=io.StringIO):
                with self.assertRaises(SystemExit) as raised:
                    watcher.main(["--repo", str(self.repo), *extra])
                self.assertEqual(raised.exception.code, 2)


class CoordinationSnapshotTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="git watcher with spaces ")
        self.addCleanup(self.temporary.cleanup)
        self.repo = Path(self.temporary.name)
        self.git("init", "--quiet")
        self.write("AGENTS.md", "repo guidance")
        self.write(".gitignore", "tests/ignored.py\nignored-inbox.md\n.env\n")
        self.write("tests/test_sample.py", "assert True\n")
        self.git("add", ".")
        self.git("-c", "user.name=Watcher Test", "-c", "user.email=watcher@example.invalid",
                 "commit", "--quiet", "-m", "fixture")

    def write(self, name, content):
        path = self.repo / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def git(self, *arguments):
        subprocess.run(["git", "-C", str(self.repo), *arguments], check=True, capture_output=True, timeout=15)

    def test_secret_ignored_and_unrelated_files_do_not_enter_snapshot_or_trigger_review(self):
        before = watcher.snapshot(self.repo, ("ignored-inbox.md",))
        for name in (".env", "tests/.env.local.py", "tests/secrets/test_secret.py", "tests/ignored.py",
                     "ignored-inbox.md", "private.md"):
            self.write(name, "PRIVATE SENTINEL")
        after = watcher.snapshot(self.repo, ("ignored-inbox.md",))
        self.assertEqual(before["fingerprint"], after["fingerprint"])
        self.assertNotIn("PRIVATE SENTINEL", json.dumps(after))
        self.assertEqual(set(after["files"]), {"AGENTS.md", "tests/test_sample.py"})

    def test_tracked_but_ignored_file_is_also_excluded(self):
        self.write("tests/ignored.py", "private")
        self.git("add", "--force", "tests/ignored.py")
        self.assertNotIn("tests/ignored.py", watcher.snapshot(self.repo)["files"])

    def test_content_hash_detects_untracked_modified_and_deleted_relevant_files(self):
        before = watcher.snapshot(self.repo)
        self.write("tests/test_sample.py", "assert False\n")
        self.write("docs/plans/TEST_NEW_TASK.md", "new work")
        changed = watcher.snapshot(self.repo)
        self.assertNotEqual(before["fingerprint"], changed["fingerprint"])
        self.assertEqual(set(watcher.changed_paths(before, changed)),
                         {"tests/test_sample.py", "docs/plans/TEST_NEW_TASK.md"})
        self.assertIn("docs/plans/TEST_NEW_TASK.md", changed["dirty_paths"])
        (self.repo / "tests/test_sample.py").unlink()
        deleted = watcher.snapshot(self.repo)
        self.assertIn("tests/test_sample.py", watcher.changed_paths(changed, deleted))

    def test_explicit_coordination_inbox_is_hashed_but_symlink_escape_is_not(self):
        self.write("coordination/inbox.md", "Claude: pending review")
        self.assertIn("coordination/inbox.md", watcher.snapshot(self.repo, ("coordination/inbox.md",))["files"])
        self.assertNotIn("coordination/inbox.md", watcher.snapshot(self.repo)["files"])
        with tempfile.TemporaryDirectory() as external:
            target = Path(external) / "private.py"
            target.write_text("private")
            link = self.repo / "tests/test_escape.py"
            try:
                link.symlink_to(target)
            except OSError:
                self.skipTest("Creating symlinks is unavailable on this host")
            self.assertNotIn("tests/test_escape.py", watcher.snapshot(self.repo)["files"])


class CoordinationLockTests(unittest.TestCase):
    def test_overlap_is_rejected_and_stale_metadata_does_not_block(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "watcher.lock"
            path.write_text('{"pid": 99999999, "started_at": "old"}')
            with watcher.ProcessLock(path):
                with self.assertRaises(watcher.AlreadyRunning):
                    with watcher.ProcessLock(path):
                        self.fail("overlapping lock acquired")
            with watcher.ProcessLock(path):
                pass
            self.assertEqual(json.loads(path.read_text())["pid"], os.getpid())

    def test_lock_recovers_after_owner_process_dies_without_cleanup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "watcher.lock"
            code = ("import os; from pathlib import Path; "
                    "from scripts.watch_test_coordination import ProcessLock; "
                    "lock=ProcessLock(Path(__import__('sys').argv[1])); lock.__enter__(); os._exit(0)")
            subprocess.run([sys.executable, "-c", code, str(path)], check=True,
                           cwd=Path(__file__).resolve().parents[1], capture_output=True, timeout=15)
            with watcher.ProcessLock(path):
                pass
            self.assertEqual(json.loads(path.read_text())["pid"], os.getpid())


class FakeProcess:
    def __init__(self, *, finished=True, output=b"diagnostic"):
        self.stdin = io.BytesIO()
        self.stdout = io.BytesIO(output)
        self.stderr = io.BytesIO(output)
        self.pid = 1234
        self.returncode = 0 if finished else None

    def poll(self):
        return self.returncode

    def wait(self, timeout=None):
        return self.returncode

    def kill(self):
        self.returncode = -9


class CoordinationProcessTests(unittest.TestCase):
    def test_paths_with_spaces_use_exact_argv_and_configured_model_is_retained(self):
        with tempfile.TemporaryDirectory(prefix="review paths with spaces ") as temporary:
            root = Path(temporary)
            report = root / "report.md"
            report.write_text("reviewed")
            process = FakeProcess(output=b"x" * (watcher.MAX_OUTPUT_BYTES + 20000))
            with mock.patch.object(watcher.subprocess, "Popen", return_value=process) as spawn:
                result = watcher.run_review("C:/Codex App/codex.exe", root, report, "exact prompt")
            argv = spawn.call_args.args[0]
            self.assertEqual(argv, ["C:/Codex App/codex.exe", "exec", "--sandbox", "read-only", "--ephemeral",
                                    "--color", "never", "-C", str(root), "-o", str(report), "-"])
            self.assertFalse(spawn.call_args.kwargs["shell"])
            self.assertNotIn("--model", argv)
            self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", argv)
            self.assertTrue(result["success"])
            self.assertEqual(result["stdout_bytes"], watcher.MAX_OUTPUT_BYTES)
            self.assertEqual(result["stderr_bytes"], watcher.MAX_OUTPUT_BYTES)

    def test_timeout_terminates_process_tree_and_does_not_claim_success(self):
        with tempfile.TemporaryDirectory() as temporary:
            process = FakeProcess(finished=False)

            def terminate(target):
                self.assertIs(target, process)
                target.returncode = -9

            with mock.patch.object(watcher.subprocess, "Popen", return_value=process), mock.patch.object(
                watcher, "terminate_tree", side_effect=terminate
            ) as terminate_mock:
                result = watcher.run_review("codex", Path(temporary), Path(temporary) / "report.md", "prompt", timeout=0)
            terminate_mock.assert_called_once_with(process)
            self.assertFalse(result["success"])
            self.assertEqual(result["error"], "timeout")

    def test_report_growth_terminates_tree_and_truncates_report(self):
        with tempfile.TemporaryDirectory() as temporary:
            report = Path(temporary) / "report.md"
            report.write_bytes(b"x" * (watcher.MAX_OUTPUT_BYTES + 1))
            process = FakeProcess(finished=False)
            with mock.patch.object(watcher.subprocess, "Popen", return_value=process), mock.patch.object(
                watcher, "terminate_tree", side_effect=lambda target: setattr(target, "returncode", -9)
            ) as terminate:
                result = watcher.run_review("codex", Path(temporary), report, "prompt")
            terminate.assert_called_once_with(process)
            self.assertEqual(result["error"], "report_limit")
            self.assertEqual(report.stat().st_size, watcher.MAX_OUTPUT_BYTES)

    def test_termination_uses_windows_tree_kill_or_posix_process_group(self):
        process = FakeProcess(finished=False)
        with mock.patch.object(watcher.subprocess, "run") as run, mock.patch.object(watcher.os, "killpg", create=True) as killpg:
            watcher.terminate_tree(process)
        if os.name == "nt":
            self.assertEqual(run.call_args.args[0], ["taskkill", "/PID", "1234", "/T", "/F"])
            self.assertFalse(run.call_args.kwargs["shell"])
        else:
            killpg.assert_called_once_with(1234, watcher.signal.SIGKILL)

    @unittest.skipUnless(os.name == "nt", "Windows taskkill fallback")
    def test_tree_kill_failure_still_kills_and_reaps_immediate_process(self):
        for error in (OSError("taskkill unavailable"), subprocess.TimeoutExpired("taskkill", 15)):
            process = FakeProcess(finished=False)
            with self.subTest(error=type(error).__name__), mock.patch.object(
                watcher.subprocess, "run", side_effect=error
            ), mock.patch.object(process, "kill", wraps=process.kill) as kill, mock.patch.object(
                process, "wait", wraps=process.wait
            ) as wait:
                watcher.terminate_tree(process)
                kill.assert_called_once_with()
                wait.assert_called_once_with(timeout=10)
                self.assertEqual(process.returncode, -9)


if __name__ == "__main__":
    unittest.main()
