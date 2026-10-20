#!/usr/bin/env python3
"""
Mirror repo-local agent skills into Claude Code and Codex discovery folders.

skills/ stays the source of truth; .claude/skills/ and .agents/skills/ are
generated discovery mirrors. Only files git does not ignore are
mirrored, so external skills kept locally in skills/ never reach the repo.

Usage:
  python scripts/sync_claude_skills.py            # rewrite both repo mirrors
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
TARGET_DIRS = (TARGET_DIR, ".agents/skills")


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
    target_dir: str = TARGET_DIR,
) -> list[str]:
    """Describe every difference between skills/<name> and its mirror."""
    if skills is None:
        skills = list_project_skill_files(root)

    drift: list[str] = []
    for name, files in sorted(skills.items()):
        source = root / SOURCE_DIR / name
        target = root / target_dir / name
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
                drift.append(f"missing {target_dir}/{name}/{relative}")
            elif (source / relative).read_bytes() != (target / relative).read_bytes():
                drift.append(f"changed {target_dir}/{name}/{relative}")
        for relative in sorted(mirrored - set(files)):
            drift.append(f"extra {target_dir}/{name}/{relative}")
    return drift


def sync(
    root: Path = ROOT_DIR,
    skills: dict[str, list[str]] | None = None,
    target_dir: str = TARGET_DIR,
) -> list[str]:
    """Replace managed skill folders in one repository mirror."""
    if target_dir not in TARGET_DIRS:
        raise ValueError(f"Unsupported repository mirror: {target_dir}")
    if skills is None:
        skills = list_project_skill_files(root)

    for name, files in sorted(skills.items()):
        target = root / target_dir / name
        mirror_root = (root / target_dir).absolute()
        if not mirror_root.resolve().is_relative_to(root.resolve()):
            raise ValueError(f"Mirror resolves outside the repository: {mirror_root}")
        if not target.resolve().is_relative_to(mirror_root.resolve()) or target.is_symlink():
            raise ValueError(f"Unsafe mirror target: {target}")
        if target.exists():
            shutil.rmtree(target)
        for relative in files:
            destination = target / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(root / SOURCE_DIR / name / relative, destination)
    return sorted(skills)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Mirror skills/ into repository Claude Code and Codex skill folders."
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
        skills = list_project_skill_files()
        drift = [item for target in TARGET_DIRS for item in find_drift(skills=skills, target_dir=target)]
        for line in drift:
            print(line)
        if drift:
            print("Out of sync. Run: python scripts/sync_claude_skills.py")
            return 1
        print(f"Both repository mirrors match {SOURCE_DIR}/.")
        return 0

    skills = list_project_skill_files()
    names = sorted(skills)
    for target in TARGET_DIRS:
        sync(skills=skills, target_dir=target)
    if args.stage and names:
        subprocess.run(
            ["git", "add", "-A", "--", *(f"{target}/{name}" for target in TARGET_DIRS for name in names)],
            cwd=ROOT_DIR,
            check=True,
        )
    print(f"Mirrored {len(names)} skill(s) into both repository mirrors: {', '.join(names)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
