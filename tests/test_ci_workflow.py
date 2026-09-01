"""Static CI contracts for changed-file selection and component coverage."""

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

    def test_flama_audio_changes_have_pr_and_push_tests(self):
        self.assertIn("name: Flama Audio CI", self.audio_workflow)
        self.assertIn("push:", self.audio_workflow)
        self.assertIn("pull_request:", self.audio_workflow)
        self.assertIn('runs-on: windows-latest', self.audio_workflow)
        self.assertIn("submodules: recursive", self.audio_workflow)
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
