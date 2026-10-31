"""Tests for safe production release retention."""

from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "deploy" / "prune_releases.py"
SPEC = importlib.util.spec_from_file_location("prune_releases", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
prune_releases = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(prune_releases)


class PruneReleasesTests(unittest.TestCase):
    def _create_release(self, root: Path, character: str, *, succeeded_at: int | None = None) -> Path:
        release = root / (character * 40)
        release.mkdir()
        (release / "app.txt").write_text(character, encoding="utf-8")
        if succeeded_at is not None:
            marker = release / prune_releases.SUCCESS_MARKER
            marker.touch()
            os.utime(marker, (succeeded_at, succeeded_at))
        return release

    def test_keeps_current_and_previous_successful_release(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            release_root = Path(temporary_directory) / "releases"
            release_root.mkdir()
            oldest = self._create_release(release_root, "a")
            previous = self._create_release(release_root, "b", succeeded_at=200)
            failed_newer = self._create_release(release_root, "c")
            current = self._create_release(release_root, "d", succeeded_at=300)
            os.utime(failed_newer, (400, 400))
            ignored = release_root / "manual-backup"
            ignored.mkdir()

            removed_names, ignored_names = prune_releases.prune_releases(
                releases_directory=release_root,
                current_release=current,
                keep_count=2,
            )

            self.assertEqual(set(removed_names), {oldest.name, failed_newer.name})
            self.assertTrue(current.is_dir())
            self.assertTrue(previous.is_dir())
            self.assertTrue(ignored.is_dir())
            self.assertIn(ignored.name, ignored_names)

    def test_current_only_retention_preserves_linked_shared_assets(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_path = Path(temporary_directory)
            release_root = temp_path / "releases"
            release_root.mkdir()
            previous = self._create_release(release_root, "a", succeeded_at=200)
            current = self._create_release(release_root, "b", succeeded_at=300)
            shared_asset = temp_path / "shared-audio.mp3"
            shared_asset.write_bytes(b"shared media")
            try:
                (previous / "audio.mp3").symlink_to(shared_asset)
            except OSError as exc:
                self.skipTest(f"File symlinks unavailable on this host: {exc}")

            removed_names, _ = prune_releases.prune_releases(
                releases_directory=release_root,
                current_release=current,
                keep_count=1,
            )

            self.assertEqual(removed_names, [previous.name])
            self.assertTrue(current.is_dir())
            self.assertEqual(shared_asset.read_bytes(), b"shared media")

    def test_rejects_current_release_outside_release_root(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            temp_path = Path(temporary_directory)
            release_root = temp_path / "releases"
            release_root.mkdir()
            outside_release = self._create_release(temp_path, "e")

            with self.assertRaises(prune_releases.ReleasePruneError):
                prune_releases.prune_releases(
                    releases_directory=release_root,
                    current_release=outside_release,
                    keep_count=2,
                )

    def test_rejects_zero_retention(self):
        with tempfile.TemporaryDirectory() as temporary_directory:
            release_root = Path(temporary_directory) / "releases"
            release_root.mkdir()
            current = self._create_release(release_root, "f")

            with self.assertRaises(prune_releases.ReleasePruneError):
                prune_releases.prune_releases(
                    releases_directory=release_root,
                    current_release=current,
                    keep_count=0,
                )


if __name__ == "__main__":
    unittest.main()
