"""Contract tests for the portable-only Flama Audio delivery workflow."""

from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW_PATH = ROOT / ".github" / "workflows" / "flama-audio-release.yml"


class TestFlamaAudioReleaseWorkflow(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = WORKFLOW_PATH.read_text(encoding="utf-8")

    def test_builds_only_portable_executable(self):
        self.assertIn("PublishSingleFile=true", self.workflow)
        self.assertIn("flama-audio/publish/release/FlamaAudio-Portable.exe", self.workflow)
        self.assertNotIn("Inno Setup", self.workflow)
        self.assertNotIn("FlamaAudio-Setup.exe", self.workflow)
        self.assertNotIn("action-gh-release", self.workflow)

    def test_checks_out_submodules_and_uses_deployment_environment(self):
        self.assertIn("submodules: recursive", self.workflow)
        self.assertIn("environment: Flama", self.workflow)

    def test_deploys_to_persistent_download_path(self):
        self.assertIn(
            "/var/lib/flama/downloads/FlamaAudio-Portable.exe",
            self.workflow,
        )
        self.assertIn("Missing required Flama environment secrets", self.workflow)


if __name__ == "__main__":
    unittest.main()
