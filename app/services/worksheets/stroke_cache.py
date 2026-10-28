"""Bounded per-worker SVG text cache, invalidated by the source file metadata."""

from functools import lru_cache
from pathlib import Path


_MAX_CACHED_BYTES = 64 * 1024


@lru_cache(maxsize=256)
def _read_svg(path: Path, mtime_ns: int, ctime_ns: int, size: int) -> str:
    return path.read_text(encoding="utf-8")


def read_stroke_svg(path: Path) -> str:
    """Reuse small SVGs without caching misses, stale files or another app root.

    Stat on every lookup so replacement and deletion take effect immediately.
    Large assets bypass the cache to bound retained text to about 16 MiB per
    worker for ASCII SVGs, plus Python object overhead.
    """
    path = path.absolute()
    stat = path.stat()
    if stat.st_size > _MAX_CACHED_BYTES:
        return path.read_text(encoding="utf-8")
    return _read_svg(path, stat.st_mtime_ns, stat.st_ctime_ns, stat.st_size)
