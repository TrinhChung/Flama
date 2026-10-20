"""Guard Claude Code's mirror of the repo-local agent skills."""

from __future__ import annotations

from pathlib import Path
import subprocess
import tempfile
import unittest

from scripts import sync_claude_skills


class ClaudeSkillsSyncTests(unittest.TestCase):
    def test_claude_mirror_matches_repo_skills(self):
        skills = sync_claude_skills.list_project_skill_files()

        self.assertIn("flama-database-architecture", skills)
        for target in sync_claude_skills.TARGET_DIRS:
            with self.subTest(target=target):
                self.assertEqual(
                    sync_claude_skills.find_drift(skills=skills, target_dir=target),
                    [],
                    "Out of sync. Run: python scripts/sync_claude_skills.py",
                )

    def test_codex_sync_preserves_other_agent_artifacts_and_external_skills(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills/demo").mkdir(parents=True)
            (root / "skills/demo/SKILL.md").write_text("shared", encoding="utf-8")
            (root / ".agents/reviews").mkdir(parents=True)
            (root / ".agents/reviews/keep.txt").write_text("review", encoding="utf-8")
            (root / ".agents/skills/external").mkdir(parents=True)
            (root / ".agents/skills/external/SKILL.md").write_text("private", encoding="utf-8")
            skills = {"demo": ["SKILL.md"]}

            sync_claude_skills.sync(root, skills, target_dir=".agents/skills")

            self.assertEqual(sync_claude_skills.find_drift(root, skills, target_dir=".agents/skills"), [])
            self.assertEqual((root / ".agents/reviews/keep.txt").read_text(), "review")
            self.assertEqual((root / ".agents/skills/external/SKILL.md").read_text(), "private")

    def test_sync_rejects_targets_outside_managed_mirrors(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                sync_claude_skills.sync(Path(tmp), {}, target_dir="../global-skills")

    def test_sync_replaces_stale_mirror(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "skills/demo/references").mkdir(parents=True)
            (root / "skills/demo/SKILL.md").write_text("new", encoding="utf-8")
            (root / "skills/demo/references/a.md").write_text("a", encoding="utf-8")
            (root / ".claude/skills/demo").mkdir(parents=True)
            (root / ".claude/skills/demo/SKILL.md").write_text("old", encoding="utf-8")
            (root / ".claude/skills/demo/stale.md").write_text("x", encoding="utf-8")
            skills = {"demo": ["SKILL.md", "references/a.md"]}

            self.assertEqual(
                sync_claude_skills.find_drift(root, skills),
                [
                    "changed .claude/skills/demo/SKILL.md",
                    "missing .claude/skills/demo/references/a.md",
                    "extra .claude/skills/demo/stale.md",
                ],
            )

            sync_claude_skills.sync(root, skills)

            self.assertEqual(sync_claude_skills.find_drift(root, skills), [])
            self.assertEqual(
                (root / ".claude/skills/demo/SKILL.md").read_text(encoding="utf-8"),
                "new",
            )

    def test_ignored_and_incomplete_skills_are_not_mirrored(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            subprocess.run(["git", "init", "-q"], cwd=root, check=True)
            (root / ".gitignore").write_text(
                "skills/*\n!skills/kept/\n!skills/draft/\n", encoding="utf-8"
            )
            for relative in (
                "skills/kept/SKILL.md",
                "skills/kept/references/notes.md",
                "skills/draft/notes.md",
                "skills/external/SKILL.md",
            ):
                (root / relative).parent.mkdir(parents=True, exist_ok=True)
                (root / relative).write_text("x", encoding="utf-8")

            self.assertEqual(
                sync_claude_skills.list_project_skill_files(root),
                {"kept": ["SKILL.md", "references/notes.md"]},
            )


if __name__ == "__main__":
    unittest.main()
