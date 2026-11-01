#!/usr/bin/env python3
"""Configures Git hooks path to use the repository's tracked .githooks directory.

Usage:
    python scripts/install_git_hooks.py
"""

from __future__ import annotations

import os
from pathlib import Path
import stat
import subprocess
import sys


def install_hooks() -> int:
    repo_root = Path(__file__).resolve().parent.parent
    hooks_dir = repo_root / ".githooks"

    if not hooks_dir.is_dir():
        print(f"[install_git_hooks] ERROR: Hooks directory not found at {hooks_dir}", file=sys.stderr)
        return 1

    try:
        # Configure Git to use tracked .githooks directory
        subprocess.run(
            ["git", "config", "core.hooksPath", ".githooks"],
            cwd=repo_root,
            check=True,
            capture_output=True,
            text=True,
        )
        print("[install_git_hooks] Successfully configured git: core.hooksPath = .githooks")
    except subprocess.CalledProcessError as e:
        print(f"[install_git_hooks] ERROR: Failed to run git config: {e.stderr}", file=sys.stderr)
        return 1

    # On POSIX environments, ensure executable permission on hook scripts
    pre_commit_hook = hooks_dir / "pre-commit"
    if pre_commit_hook.exists() and os.name != "nt":
        try:
            current_stat = pre_commit_hook.stat()
            pre_commit_hook.chmod(current_stat.st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
            print(f"[install_git_hooks] Marked {pre_commit_hook.name} as executable.")
        except OSError as e:
            print(f"[install_git_hooks] WARNING: Could not chmod {pre_commit_hook}: {e}", file=sys.stderr)

    print("[install_git_hooks] Git pre-commit security hooks are active and ready.")
    return 0


if __name__ == "__main__":
    sys.exit(install_hooks())
