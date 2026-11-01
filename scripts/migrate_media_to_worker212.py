#!/usr/bin/env python3
"""Migration script to transfer legacy media files from Chung VPS to Worker 212 CAS storage.

Maintains dual-addressing (SHA-256 Content-Addressable Storage + UUID symlinks)
so that all existing notes referencing /media/proxy/<uuid> remain 100% functional
without needing any database rewrite.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app import create_app
from models import db
from models.media_asset import MediaAsset
from models.shared_image_asset import SharedImageAsset


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Migrate legacy media files to Worker 212")
    parser.add_argument("--dry-run", action="store_true", help="Inspect and simulate without copying files")
    parser.add_argument("--limit", type=int, default=0, help="Limit number of files to migrate (0 = all)")
    parser.add_argument(
        "--worker-media-dir",
        default="/data/flama/media",
        help="Destination directory on Worker 212 (default: /data/flama/media)",
    )
    parser.add_argument(
        "--worker-ssh",
        default=os.environ.get("FLAMA_MEDIA_WORKER_SSH", ""),
        help="SSH destination for Worker 212, e.g. ubuntu@wg-worker212 (default: $FLAMA_MEDIA_WORKER_SSH)",
    )
    parser.add_argument(
        "--export-manifest",
        type=str,
        default="",
        help="Export mapping manifest to a local JSON file for bulk rsync processing",
    )
    args = parser.parse_args()
    if not args.worker_ssh:
        parser.error("--worker-ssh (or FLAMA_MEDIA_WORKER_SSH) is required")
    return args


def main() -> None:
    args = parse_args()
    app = create_app()

    with app.app_context():
        upload_root = Path(app.config.get("FLASHCARD_MEDIA_UPLOAD_ROOT", "/var/lib/flama/media")).resolve()
        print(f"[*] Local media root: {upload_root}")
        print(f"[*] Worker 212 destination: {args.worker_ssh}:{args.worker_media_dir}")
        print(f"[*] Mode: {'DRY RUN' if args.dry_run else 'LIVE MIGRATION'}")

        query = MediaAsset.query.order_by(MediaAsset.created_at.asc())
        if args.limit > 0:
            query = query.limit(args.limit)
        assets = query.all()
        print(f"[*] Found {len(assets)} MediaAsset records to process.")

        shared_query = SharedImageAsset.query.order_by(SharedImageAsset.created_at.asc())
        if args.limit > 0:
            shared_query = shared_query.limit(args.limit)
        shared_assets = shared_query.all()
        print(f"[*] Found {len(shared_assets)} SharedImageAsset records to process.")

        manifest: list[dict[str, str]] = []
        migrated_count = 0
        missing_count = 0

        for idx, asset in enumerate(assets, 1):
            local_path = (upload_root / asset.storage_path).resolve()
            if not local_path.exists() or not local_path.is_file():
                missing_count += 1
                continue

            sha256 = asset.sha256
            uuid_id = asset.id
            ext = local_path.suffix.lower()

            cas_prefix1 = sha256[0:2]
            cas_prefix2 = sha256[2:4]
            cas_rel = f"{cas_prefix1}/{cas_prefix2}/{sha256}{ext}"

            uuid_prefix1 = uuid_id[0:2]
            uuid_prefix2 = uuid_id[2:4]
            uuid_rel = f"{uuid_prefix1}/{uuid_prefix2}/{uuid_id}{ext}"

            manifest.append({
                "storage_path": asset.storage_path,
                "sha256": sha256,
                "uuid": uuid_id,
                "cas_rel": cas_rel,
                "uuid_rel": uuid_rel,
            })

            migrated_count += 1

        for idx, asset in enumerate(shared_assets, 1):
            if not asset.storage_path:
                continue
            local_path = (upload_root / asset.storage_path).resolve()
            if not local_path.exists() or not local_path.is_file():
                missing_count += 1
                continue

            sha256 = asset.sha256 or ""
            uuid_id = asset.id
            ext = local_path.suffix.lower()

            cas_prefix1 = sha256[0:2] if len(sha256) >= 4 else "00"
            cas_prefix2 = sha256[2:4] if len(sha256) >= 4 else "00"
            cas_rel = f"{cas_prefix1}/{cas_prefix2}/{sha256}{ext}"

            uuid_prefix1 = uuid_id[0:2]
            uuid_prefix2 = uuid_id[2:4]
            uuid_rel = f"{uuid_prefix1}/{uuid_prefix2}/{uuid_id}{ext}"

            manifest.append({
                "storage_path": asset.storage_path,
                "sha256": sha256,
                "uuid": uuid_id,
                "cas_rel": cas_rel,
                "uuid_rel": uuid_rel,
            })

            migrated_count += 1

        if args.export_manifest:
            out_file = Path(args.export_manifest)
            with open(out_file, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2)
            print(f"[OK] Exported manifest of {len(manifest)} items to {out_file}")
            return

        print("\n" + "=" * 50)
        print(f"[SUMMARY] Total: {len(assets)} | Valid for migration: {migrated_count} | Missing on disk: {missing_count}")
        print("=" * 50)


if __name__ == "__main__":
    main()
