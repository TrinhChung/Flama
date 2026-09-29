"""The frontend deploy gate must block a SPA the live backend cannot serve."""

from __future__ import annotations

import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock
from urllib.error import URLError

from scripts import check_backend_release as gate


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc_info):
        self.close()


def _health_opener(*payloads):
    """Return an urlopen stand-in that replays payloads (or raises errors)."""
    remaining = list(payloads)

    def opener(request, timeout):
        payload = remaining.pop(0)
        if isinstance(payload, Exception):
            raise payload
        return _Response(json.dumps(payload).encode("utf-8"))

    return opener


class FetchLiveReleaseTests(unittest.TestCase):
    def test_returns_the_release_reported_by_health(self):
        release = gate.fetch_live_release(
            "https://backend.test/api/health",
            attempts=1,
            delay_seconds=0,
            opener=_health_opener({"status": "ok", "release": "abc123"}),
        )

        self.assertEqual(release, "abc123")

    def test_retries_a_restarting_backend_before_reading_the_release(self):
        with mock.patch.object(gate.time, "sleep") as sleep:
            release = gate.fetch_live_release(
                "https://backend.test/api/health",
                attempts=3,
                delay_seconds=5,
                opener=_health_opener(
                    URLError("connection refused"),
                    {"status": "unavailable", "dependency": "redis"},
                    {"status": "ok", "release": "abc123"},
                ),
            )

        self.assertEqual(release, "abc123")
        self.assertEqual(sleep.call_count, 2)

    def test_backend_without_a_release_stamp_blocks_the_frontend(self):
        with self.assertRaisesRegex(gate.GateError, "has no release"):
            gate.fetch_live_release(
                "https://backend.test/api/health",
                attempts=2,
                delay_seconds=0,
                opener=_health_opener(
                    {"status": "ok"},
                    {"status": "ok", "release": None},
                ),
            )


class EvaluateReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if not shutil.which("git"):
            raise unittest.SkipTest("git is required for the release gate rehearsal.")

    def setUp(self):
        self._directory = tempfile.TemporaryDirectory()
        self.repo = Path(self._directory.name)
        self._git("init", "--quiet")
        self.base = self._commit({"app/api/v1/health.py": "v1", "frontend/src/a.ts": "v1"})

    def tearDown(self):
        self._directory.cleanup()

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            [
                "git",
                "-c", "user.name=Gate Test",
                "-c", "user.email=gate@example.invalid",
                "-c", "commit.gpgsign=false",
                *args,
            ],
            cwd=self.repo,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()

    def _commit(self, files: dict[str, str]) -> str:
        for relative, content in files.items():
            path = self.repo / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        self._git("add", "--all")
        self._git("commit", "--quiet", "-m", "change")
        return self._git("rev-parse", "HEAD")

    def test_backend_already_on_the_frontend_commit_passes(self):
        summary = gate.evaluate(self.repo, self.base, self.base)

        self.assertIn("already runs", summary)

    def test_frontend_only_changes_since_the_live_backend_pass(self):
        target = self._commit({"frontend/src/a.ts": "v2"})

        summary = gate.evaluate(self.repo, self.base, target)

        self.assertIn("no backend runtime changes pending", summary)

    def test_undeployed_backend_change_blocks_the_frontend(self):
        self._commit({"app/api/v1/health.py": "v2"})
        target = self._commit({"frontend/src/a.ts": "v2"})

        with self.assertRaises(gate.GateError) as caught:
            gate.evaluate(self.repo, self.base, target)

        self.assertIn("missing 1 backend runtime change", str(caught.exception))
        self.assertEqual(caught.exception.details, ["app/api/v1/health.py"])

    def test_newer_live_backend_passes(self):
        target = self._commit({"frontend/src/a.ts": "v2"})
        live = self._commit({"app/api/v1/health.py": "v2"})

        summary = gate.evaluate(self.repo, live, target)

        self.assertIn("newer than frontend", summary)

    def test_backend_from_a_diverged_history_blocks_the_frontend(self):
        target = self._commit({"frontend/src/a.ts": "v2"})
        self._git("checkout", "--quiet", "-b", "side", self.base)
        live = self._commit({"app/api/v1/health.py": "side"})

        with self.assertRaisesRegex(gate.GateError, "not on the history"):
            gate.evaluate(self.repo, live, target)

    def test_unknown_live_commit_blocks_the_frontend(self):
        with self.assertRaisesRegex(gate.GateError, "not in this checkout"):
            gate.evaluate(self.repo, "f" * 40, self.base)


if __name__ == "__main__":
    unittest.main()
