#!/usr/bin/env python3
"""
Mirror the repo-local agent skills from skills/ into .claude/skills/.

skills/ stays the source of truth for Codex and the other agents; Claude Code
only discovers skills under .claude/skills/. Only files git does not ignore are
mirrored, so external skills kept locally in skills/ never reach the repo.

Usage:
  python scripts/sync_claude_skills.py            # rewrite .claude/skills/<name>
  python scripts/sync_claude_skills.py --stage    # ...and git add the mirror
  python scripts/sync_claude_skills.py --check    # exit 1 when out of sync
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
SOURCE_DIR = "skills"
TARGET_DIR = ".claude/skills"


def list_project_skill_files(root: Path = ROOT_DIR) -> dict[str, list[str]]:
    """Map each non-ignored skill in skills/ to its files, relative to the skill."""
    listing = subprocess.run(
        [
            "git",
            "ls-files",
            "-z",
            "--cached",
            "--others",
            "--exclude-standard",
            "--",
            SOURCE_DIR,
        ],
        cwd=root,
        check=True,
        capture_output=True,
    ).stdout.decode("utf-8")

    skills: dict[str, list[str]] = {}
    for relative in sorted(filter(None, listing.split("\0"))):
        parts = Path(relative).parts
        if len(parts) < 3 or not (root / relative).is_file():
            continue
        skills.setdefault(parts[1], []).append(Path(*parts[2:]).as_posix())
    return {name: files for name, files in skills.items() if "SKILL.md" in files}


def find_drift(
    root: Path = ROOT_DIR,
    skills: dict[str, list[str]] | None = None,
) -> list[str]:
    """Describe every difference between skills/<name> and its mirror."""
    if skills is None:
        skills = list_project_skill_files(root)

    drift: list[str] = []
    for name, files in sorted(skills.items()):
        source = root / SOURCE_DIR / name
        target = root / TARGET_DIR / name
        mirrored = (
            {
                path.relative_to(target).as_posix()
                for path in target.rglob("*")
                if path.is_file()
            }
            if target.is_dir()
            else set()
        )
        for relative in files:
            if relative not in mirrored:
                drift.append(f"missing {TARGET_DIR}/{name}/{relative}")
            elif (source / relative).read_bytes() != (target / relative).read_bytes():
                drift.append(f"changed {TARGET_DIR}/{name}/{relative}")
        for relative in sorted(mirrored - set(files)):
            drift.append(f"extra {TARGET_DIR}/{name}/{relative}")
    return drift


def sync(
    root: Path = ROOT_DIR,
    skills: dict[str, list[str]] | None = None,
) -> list[str]:
    """Replace .claude/skills/<name> with a copy of skills/<name>."""
    if skills is None:
        skills = list_project_skill_files(root)

    for name, files in sorted(skills.items()):
        target = root / TARGET_DIR / name
        if target.exists():
            shutil.rmtree(target)
        for relative in files:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / SOURCE_DIR / name / relative, destination)
    return sorted(skills)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirror skills/ into .claude/skills/ for Claude Code."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="Report drift and exit 1 instead of writing files.",
    )
    mode.add_argument(
        "--stage",
        action="store_true",
        help="Stage the mirrored skill directories after syncing.",
    )
    args = parser.parse_args(argv)

    if args.check:
        drift = find_drift()
        for line in drift:
            print(line)
        if drift:
            print("Out of sync. Run: python scripts/sync_claude_skills.py")
            return 1
        print(f"{TARGET_DIR}/ matches {SOURCE_DIR}/.")
        return 0

    names = sync()
    if args.stage and names:
        subprocess.run(
            ["git", "add", "-A", "--", *(f"{TARGET_DIR}/{name}" for name in names)],
            cwd=ROOT_DIR,
            check=True,
        )
    print(f"Mirrored {len(names)} skill(s) into {TARGET_DIR}/: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
