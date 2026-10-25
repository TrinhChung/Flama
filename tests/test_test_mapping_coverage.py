"""Guard the changed-file catalog against silently stale source mappings."""

from __future__ import annotations

import fnmatch
from pathlib import Path
import subprocess
import unittest

from scripts import run_tests


class TestMappingCoverageTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Local experiments must neither hide missing CI files nor require
        # domain mappings. The index is also valid before a new commit exists.
        cls.tracked_paths = set(subprocess.check_output(
            ["git", "ls-files", "-z"], cwd=run_tests.ROOT_DIR,
        ).decode("utf-8").split("\0")) - {""}

    def test_every_backend_source_is_mapped_or_explicitly_full_suite(self):
        missing: list[str] = []
        source_paths = [
            *(run_tests.ROOT_DIR / "app").rglob("*.py"),
            *(run_tests.ROOT_DIR / "models").rglob("*.py"),
            *(run_tests.ROOT_DIR / "scripts").glob("*"),
            *run_tests.ROOT_DIR.glob("*.py"),
        ]
        for path in source_paths:
            if not path.is_file() or path.suffix.lower() not in {
                ".py",
                ".ps1",
                ".sh",
                ".bat",
            }:
                continue
            relative = path.relative_to(run_tests.ROOT_DIR).as_posix()
            if relative not in self.tracked_paths:
                continue
            mapped = any(
                fnmatch.fnmatch(relative, pattern)
                for module in run_tests.MODULES.values()
                for pattern in module["source_patterns"]
            )
            full_suite = any(
                fnmatch.fnmatch(relative, pattern)
                for pattern in run_tests.FULL_BACKEND_SOURCE_PATTERNS
            )
            if not mapped and not full_suite:
                missing.append(relative)

        self.assertEqual(
            sorted(missing),
            [],
            "New backend source files need a domain mapping in scripts/run_tests.py",
        )

    def test_every_catalog_test_path_exists(self):
        missing: list[str] = []
        for module_name, module in run_tests.MODULES.items():
            for relative in module["backend_tests"]:
                if relative not in self.tracked_paths or not (run_tests.ROOT_DIR / relative).is_file():
                    missing.append(f"{module_name}:backend:{relative}")
            for relative in module["frontend_tests"]:
                if f"frontend/{relative}" not in self.tracked_paths or not (run_tests.ROOT_DIR / "frontend" / relative).is_file():
                    missing.append(f"{module_name}:frontend:{relative}")

        self.assertEqual(
            sorted(missing),
            [],
            "Catalog tests must exist in Git; untracked local files do not exist in CI",
        )


if __name__ == "__main__":
    unittest.main()
