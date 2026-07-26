#!/usr/bin/env python3
"""Remove old Git-SHA release directories while retaining rollback coverage."""

from __future__ import annotations

import argparse
import re
import shutil
from pathlib import Path


RELEASE_NAME_RE = re.compile(r"^[0-9a-f]{40,64}$")
SUCCESS_MARKER = ".deployment_succeeded"


class ReleasePruneError(RuntimeError):
    """Raised when release pruning cannot be performed safely."""


def _resolve_directory(path: Path, *, label: str) -> Path:
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise ReleasePruneError(f"{label} does not exist: {path}") from exc
    if not resolved.is_dir():
        raise ReleasePruneError(f"{label} is not a directory: {resolved}")
    return resolved


def _release_sort_key(path: Path) -> tuple[int, int, str]:
    success_marker = path / SUCCESS_MARKER
    if success_marker.is_file():
        return (1, success_marker.stat().st_mtime_ns, path.name)
    return (0, path.stat().st_mtime_ns, path.name)


def prune_releases(
    *,
    releases_directory: Path,
    current_release: Path,
    keep_count: int,
) -> tuple[list[str], list[str]]:
    if keep_count < 1:
        raise ReleasePruneError("At least one release must be retained.")

    release_root = _resolve_directory(releases_directory, label="Release directory")
    current_path = _resolve_directory(current_release, label="Current release")
    if current_path.parent != release_root or not RELEASE_NAME_RE.fullmatch(current_path.name):
        raise ReleasePruneError("Current release is not a Git-SHA directory directly under the release root.")

    candidates: list[Path] = []
    ignored_names: list[str] = []
    for child in release_root.iterdir():
        if child.is_symlink() or not child.is_dir() or not RELEASE_NAME_RE.fullmatch(child.name):
            ignored_names.append(child.name)
            continue
        resolved_child = child.resolve(strict=True)
        if resolved_child.parent != release_root:
            raise ReleasePruneError(f"Release candidate escapes the release root: {child}")
        candidates.append(resolved_child)

    if current_path not in candidates:
        raise ReleasePruneError("Current release is not present in the validated release set.")

    previous_releases = sorted(
        (path for path in candidates if path != current_path),
        key=_release_sort_key,
        reverse=True,
    )
    retained = {current_path, *previous_releases[: max(keep_count - 1, 0)]}
    removal_candidates = [path for path in candidates if path not in retained]

    removed_names: list[str] = []
    for release_path in removal_candidates:
        resolved_path = release_path.resolve(strict=True)
        if (
            resolved_path == current_path
            or resolved_path.parent != release_root
            or not RELEASE_NAME_RE.fullmatch(resolved_path.name)
        ):
            raise ReleasePruneError(f"Refusing to remove unsafe release path: {release_path}")
        shutil.rmtree(resolved_path)
        removed_names.append(resolved_path.name)

    if removed_names:
        print("Removed old releases: " + ", ".join(sorted(removed_names)))
    else:
        print("No old releases need removal.")
    if ignored_names:
        print("Ignored non-release entries: " + ", ".join(sorted(ignored_names)))
    return removed_names, ignored_names


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--releases-dir", type=Path, required=True)
    parser.add_argument("--current-release", type=Path, required=True)
    parser.add_argument("--keep", type=int, default=2)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        prune_releases(
            releases_directory=args.releases_dir,
            current_release=args.current_release,
            keep_count=args.keep,
        )
    except ReleasePruneError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
