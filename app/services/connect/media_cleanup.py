"""Reclaim expired uploads and crash leftovers in Connect-owned directories."""

from pathlib import Path
import re
import time

from app.services import flama_connect_media_service as media
from models.connect_pending_media import ConnectPendingMedia
from models.media_asset import MediaAsset

_STORAGE_NAME = re.compile(r"^[a-f0-9]{32}_[a-f0-9]{12}\.(?:mp3|png|jpg|jpeg)$")


def cleanup():
    expired = 0
    for _ in range(100):
        count = media._purge_expired()
        expired += count
        if not count:
            break
    known = {path for (path,) in ConnectPendingMedia.query.with_entities(ConnectPendingMedia.storage_path).all()}
    known.update(path for (path,) in MediaAsset.query.with_entities(MediaAsset.storage_path)
                 .filter(MediaAsset.storage_path.like("connect_mined/%")).all())
    root = media._upload_root()
    cutoff = time.time() - 2 * media._config_int("CONNECT_PENDING_MEDIA_TTL_SECONDS", 1800)
    orphans = 0
    for directory in ("connect_pending", "connect_mined"):
        for path in (root / directory).rglob("*"):
            if not path.is_file() or not _STORAGE_NAME.fullmatch(path.name):
                continue
            relative = path.relative_to(root).as_posix()
            if relative in known or path.stat().st_mtime > cutoff:
                continue
            # Resolve again before deleting, including symlinks within the tree.
            safe = media._safe_path(Path(relative))
            media._unlink_quietly(safe)
            orphans += 1
    return {"expired_uploads": expired, "orphan_files": orphans}
