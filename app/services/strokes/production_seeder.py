"""Production Stroke Pre-generation and Seeding Pipeline."""

from __future__ import annotations

import concurrent.futures
import hashlib
import logging
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from models import db
from models.shared_image_asset import SharedImageAsset
from app.services.strokes.cjk_datasets import (
    get_production_kanji_list,
    get_production_hanzi_list,
)
from app.services.strokes.cjk_extractor import CjkExtractor, is_cjk_ideograph
from app.services.strokes.dataset_builder import (
    fetch_authentic_stroke_svg,
    generate_kanji_placeholder_svg,
    sanitize_stroke_svg,
)

logger = logging.getLogger(__name__)


def _process_single_character(
    char: str,
    locale: str,
    raw_folder: str,
    prefix: str,
    upload_dir: Path,
    static_dir: Path,
    force: bool = False,
) -> dict[str, Any]:
    """Download, sanitize and write stroke SVG files for a single character."""
    if not is_cjk_ideograph(char):
        return {"char": char, "status": "skipped", "reason": "not_cjk"}

    hex_code = CjkExtractor.char_to_hex(char)
    hex_padded = hex_code.zfill(5)
    image_key = f"{prefix}{hex_code}"

    upload_file = upload_dir / f"{hex_code}.svg"
    upload_file_padded = upload_dir / f"{hex_padded}.svg"
    static_file = static_dir / f"{hex_code}.svg"
    static_file_padded = static_dir / f"{hex_padded}.svg"

    # If already exists and not forced, read from disk
    if upload_file.exists() and not force:
        try:
            svg_content = upload_file.read_text(encoding="utf-8")
            svg_bytes = svg_content.encode("utf-8")
            return {
                "char": char,
                "hex": hex_code,
                "image_key": image_key,
                "locale": locale,
                "raw_folder": raw_folder,
                "status": "cached",
                "sha256": hashlib.sha256(svg_bytes).hexdigest(),
                "size_bytes": len(svg_bytes),
            }
        except Exception:
            pass

    # Fetch fresh SVG from upstream authentic dataset
    svg_content = fetch_authentic_stroke_svg(char, locale=locale)
    if not svg_content:
        svg_content = generate_kanji_placeholder_svg(char)

    # Write files to upload and static dirs
    upload_file.write_text(svg_content, encoding="utf-8")
    upload_file_padded.write_text(svg_content, encoding="utf-8")
    static_file.write_text(svg_content, encoding="utf-8")
    static_file_padded.write_text(svg_content, encoding="utf-8")

    svg_bytes = svg_content.encode("utf-8")
    return {
        "char": char,
        "hex": hex_code,
        "image_key": image_key,
        "locale": locale,
        "raw_folder": raw_folder,
        "status": "generated",
        "sha256": hashlib.sha256(svg_bytes).hexdigest(),
        "size_bytes": len(svg_bytes),
    }


def seed_production_strokes_dataset(
    *,
    locales: Sequence[str] = ("ja", "zh", "zh-hant"),
    limit_ja: int = 2500,
    limit_zh: int = 9000,
    limit_zh_hant: int = 9000,
    workers: int = 12,
    force: bool = False,
    progress_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Concurrent production seeder for 2,500+ Japanese Kanji & 9,000+ Chinese Hanzi."""
    upload_root = Path("app/static/uploads/flashcard_media/library/strokes")
    static_root = Path("static/strokes")

    targets = []
    if "ja" in locales or "all" in locales:
        targets.append(("ja", "ja", "stroke_ja_", get_production_kanji_list(limit=limit_ja)))
    if "zh" in locales or "zh-hans" in locales or "all" in locales:
        targets.append(("zh", "zh", "stroke_zh_", get_production_hanzi_list(locale="zh", limit=limit_zh)))
    if "zh-hant" in locales or "zh-tw" in locales or "all" in locales:
        targets.append(("zh-hant", "zh_hant", "stroke_zh_hant_", get_production_hanzi_list(locale="zh-hant", limit=limit_zh_hant)))

    overall_stats = {
        "total_targets": sum(len(chars) for _, _, _, chars in targets),
        "generated": 0,
        "cached": 0,
        "failed": 0,
        "db_updated": 0,
    }

    for locale_key, raw_folder, prefix, char_list in targets:
        upload_dir = upload_root / raw_folder
        static_dir = static_root / (locale_key if locale_key != "zh-hant" else "zh-hant")
        upload_dir.mkdir(parents=True, exist_ok=True)
        static_dir.mkdir(parents=True, exist_ok=True)

        total_locale = len(char_list)
        logger.info("Starting production stroke generation for [%s]: %d characters with %d workers", locale_key, total_locale, workers)

        completed_count = 0
        db_batch: list[dict[str, Any]] = []

        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(
                    _process_single_character,
                    char,
                    locale_key,
                    raw_folder,
                    prefix,
                    upload_dir,
                    static_dir,
                    force,
                ): char
                for char in char_list
            }

            for future in concurrent.futures.as_completed(futures):
                char = futures[future]
                completed_count += 1
                try:
                    res = future.result()
                    status = res.get("status")
                    if status == "generated":
                        overall_stats["generated"] += 1
                    elif status == "cached":
                        overall_stats["cached"] += 1
                    else:
                        overall_stats["failed"] += 1

                    if "image_key" in res:
                        db_batch.append(res)
                except Exception as exc:
                    logger.warning("Error processing %s (%s): %s", char, locale_key, exc)
                    overall_stats["failed"] += 1

                # Flush DB batch every 100 items
                if len(db_batch) >= 100:
                    _sync_db_batch(db_batch)
                    overall_stats["db_updated"] += len(db_batch)
                    db_batch.clear()

                if progress_callback:
                    progress_callback({
                        "locale": locale_key,
                        "completed": completed_count,
                        "total": total_locale,
                        "char": char,
                        "overall": overall_stats,
                    })

        # Flush remaining DB batch
        if db_batch:
            _sync_db_batch(db_batch)
            overall_stats["db_updated"] += len(db_batch)
            db_batch.clear()

    return overall_stats


def _sync_db_batch(batch: list[dict[str, Any]]) -> None:
    """Sync a batch of stroke asset metadata to SharedImageAsset table."""
    try:
        keys = [item["image_key"] for item in batch]
        existing_assets = {a.image_key: a for a in SharedImageAsset.query.filter(SharedImageAsset.image_key.in_(keys)).all()}

        for item in batch:
            image_key = item["image_key"]
            hex_code = item["hex"]
            char = item["char"]
            locale = item["locale"]
            storage_path = f"library/strokes/{item['raw_folder']}/{hex_code}.svg"
            sha256 = item["sha256"]
            size_bytes = item["size_bytes"]

            asset = existing_assets.get(image_key)
            if not asset:
                asset = SharedImageAsset(
                    image_key=image_key,
                    filename=f"{hex_code}.svg",
                    mime_type="image/svg+xml",
                    storage_path=storage_path,
                    sha256=sha256,
                    size_bytes=size_bytes,
                    description=f"Sơ đồ nét: {char} ({locale})",
                    tags=["stroke", locale, char, hex_code],
                    is_enabled=True,
                )
                db.session.add(asset)
            else:
                asset.storage_path = storage_path
                asset.mime_type = "image/svg+xml"
                asset.sha256 = sha256
                asset.size_bytes = size_bytes
                asset.is_enabled = True
                asset.description = f"Sơ đồ nét: {char} ({locale})"
                asset.tags = ["stroke", locale, char, hex_code]

        db.session.commit()
    except Exception as exc:
        db.session.rollback()
        logger.error("DB batch sync error: %s", exc)
