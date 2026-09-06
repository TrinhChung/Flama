#!/usr/bin/env python
"""Reseed Local Stroke SVG Datasets (Japanese, Simplified Chinese, Traditional Chinese).

1. Clears old SVG files in local folders:
   - static/strokes/ja, zh, zh-hant
   - app/static/uploads/flashcard_media/library/strokes/ja, zh, zh_hant
2. Resets SharedImageAsset records for stroke diagrams in local database.
3. Extracts all CJK characters from local notes in database + common starter lists.
4. Preserves authentic traditional vs simplified characters without forced conversion.
5. If an authentic stroke SVG is not available upstream, AUTOMATICALLY GENERATES a new vector SVG.
6. Writes files to disk and syncs metadata to local SharedImageAsset table.
"""

from __future__ import annotations

import concurrent.futures
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

# Add project root
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

from wsgi import app
from models import db
from models.note import Note
from models.deck import Deck
from models.shared_image_asset import SharedImageAsset
from app.services.strokes.cjk_extractor import CjkExtractor, is_cjk_ideograph
from app.services.strokes.dataset_builder import (
    fetch_authentic_stroke_svg,
    generate_kanji_placeholder_svg,
    JA_STARTER_KANJI,
    ZH_STARTER_HANZI,
    ZH_HANT_STARTER_HANZI,
)
from app.services.strokes.stroke_service import (
    _get_static_root,
    _get_upload_root,
    normalize_locale,
)


def clear_local_stroke_files(static_root: Path, upload_root: Path) -> dict[str, int]:
    """Remove old SVG files from local directories."""
    stats = {"static_removed": 0, "upload_removed": 0}

    # 1. Clean static directories
    for sub in ["ja", "zh", "zh-hant"]:
        d = static_root / "strokes" / sub
        if d.exists():
            for f in d.glob("*.svg"):
                try:
                    f.unlink()
                    stats["static_removed"] += 1
                except Exception:
                    pass

    # 2. Clean upload library directories
    for sub in ["ja", "zh", "zh_hant"]:
        d = upload_root / "library" / "strokes" / sub
        if d.exists():
            for f in d.glob("*.svg"):
                try:
                    f.unlink()
                    stats["upload_removed"] += 1
                except Exception:
                    pass

    return stats


def extract_characters_from_local_db() -> dict[str, set[str]]:
    """Scan local decks and notes to extract characters per language category."""
    chars_by_locale = {
        "ja": set(JA_STARTER_KANJI),
        "zh": set(ZH_STARTER_HANZI),
        "zh-hant": set(ZH_HANT_STARTER_HANZI),
    }

    # Add common production characters from seed data
    seed_dir = PROJECT_ROOT / "static" / "seed_data" / "strokes"
    if (seed_dir / "kanjivg_chars.json").exists():
        try:
            k_chars = json.loads((seed_dir / "kanjivg_chars.json").read_text(encoding="utf-8"))
            chars_by_locale["ja"].update(k_chars[:300])
        except Exception:
            pass

    if (seed_dir / "zh_production_hanzi.json").exists():
        try:
            zh_chars = json.loads((seed_dir / "zh_production_hanzi.json").read_text(encoding="utf-8"))
            chars_by_locale["zh"].update(zh_chars[:300])
        except Exception:
            pass

    if (seed_dir / "zh_hant_production_hanzi.json").exists():
        try:
            zh_hant_chars = json.loads((seed_dir / "zh_hant_production_hanzi.json").read_text(encoding="utf-8"))
            chars_by_locale["zh-hant"].update(zh_hant_chars[:300])
        except Exception:
            pass

    # Scan notes in local database
    notes = Note.query.all()
    for note in notes:
        field_vals = note.field_values or {}
        extracted: list[str] = []
        for val in field_vals.values():
            if isinstance(val, str):
                extracted.extend(CjkExtractor.extract_characters(val))

        if not extracted:
            continue

        # Check deck name / ancestor name
        deck = db.session.get(Deck, note.deck_id) if note.deck_id else None
        dname = (deck.name if deck else "").lower()
        is_chinese = any(kw in dname for kw in ["hsk", "trung", "chinese", "tiếng trung", "hoa"])

        if is_chinese:
            chars_by_locale["zh"].update(extracted)
            chars_by_locale["zh-hant"].update(extracted)
        else:
            chars_by_locale["ja"].update(extracted)

    return chars_by_locale


def process_character_for_region(
    char: str,
    locale: str,
    static_root: Path,
    upload_root: Path,
) -> dict[str, str]:
    """Fetch authentic SVG or auto-generate a new vector SVG for char in locale."""
    folder = normalize_locale(locale)
    raw_folder = folder.replace("-", "_")
    hex_code = CjkExtractor.char_to_hex(char)
    hex_padded = hex_code.zfill(5)
    image_key = f"stroke_{raw_folder}_{hex_code}"

    # 1. Try fetching authentic stroke SVG
    svg_content = None
    source = "authentic"
    try:
        svg_content = fetch_authentic_stroke_svg(char, locale=folder)
    except Exception:
        pass

    # 2. If missing upstream, GENERATE A NEW SVG!
    if not svg_content:
        svg_content = generate_kanji_placeholder_svg(char, locale=folder)
        source = "generated"

    # 3. Write files
    static_dir = static_root / "strokes" / folder
    upload_dir = upload_root / "library" / "strokes" / raw_folder

    static_dir.mkdir(parents=True, exist_ok=True)
    upload_dir.mkdir(parents=True, exist_ok=True)

    (static_dir / f"{hex_code}.svg").write_text(svg_content, encoding="utf-8")
    (static_dir / f"{hex_padded}.svg").write_text(svg_content, encoding="utf-8")

    (upload_dir / f"{hex_code}.svg").write_text(svg_content, encoding="utf-8")
    (upload_dir / f"{hex_padded}.svg").write_text(svg_content, encoding="utf-8")

    svg_bytes = svg_content.encode("utf-8")
    sha256 = hashlib.sha256(svg_bytes).hexdigest()

    return {
        "char": char,
        "hex": hex_code,
        "locale": folder,
        "raw_folder": raw_folder,
        "image_key": image_key,
        "source": source,
        "sha256": sha256,
        "size_bytes": len(svg_bytes),
    }


def main():
    print("=" * 65)
    print(" FLAMA LOCAL STROKE DATASET RESEEDING PIPELINE")
    print("=" * 65)

    start_time = time.time()
    with app.app_context():
        static_root = _get_static_root()
        upload_root = _get_upload_root()

        print(f" Static root : {static_root}")
        print(f" Upload root : {upload_root}")

        # Step 1: Clean old files
        print("\n[1/4] Xóa toàn bộ file SVG cũ trên local...")
        clean_stats = clear_local_stroke_files(static_root, upload_root)
        print(f"   -> Đã xóa {clean_stats['static_removed']} file SVG trong static/strokes/")
        print(f"   -> Đã xóa {clean_stats['upload_removed']} file SVG trong library/strokes/")

        # Step 2: Reset DB assets
        print("\n[2/4] Dọn dẹp records SharedImageAsset stroke cũ trên DB local...")
        try:
            deleted_count = SharedImageAsset.query.filter(SharedImageAsset.image_key.like("stroke_%")).delete(synchronize_session=False)
            db.session.commit()
            print(f"   -> Đã xóa {deleted_count} records SharedImageAsset cũ.")
        except Exception as e:
            db.session.rollback()
            print(f"   -> Cảnh báo khi dọn DB: {e}")

        # Step 3: Extract characters
        print("\n[3/4] Trích xuất chữ Hán từ database decks local & starter list...")
        chars_by_locale = extract_characters_from_local_db()
        for loc, chars in chars_by_locale.items():
            print(f"   -> Region [{loc.upper()}]: {len(chars)} chữ Hán cần seed")

        # Step 4: Seed & Generate
        print("\n[4/4] Bắt đầu tải và tự động sinh SVG mới cho từng region...")
        results_summary = {"authentic": 0, "generated": 0}
        all_db_records: list[dict] = []

        for loc, char_set in chars_by_locale.items():
            char_list = sorted(list(char_set))
            print(f"\n   Đang xử lý [{loc.upper()}] ({len(char_list)} ký tự)...")

            with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
                futures = {
                    executor.submit(process_character_for_region, ch, loc, static_root, upload_root): ch
                    for ch in char_list
                }
                for f in concurrent.futures.as_completed(futures):
                    try:
                        res = f.result()
                        results_summary[res["source"]] += 1
                        all_db_records.append(res)
                    except Exception as err:
                        ch = futures[f]
                        print(f"      Lỗi với {ch} ({loc}): {err}")

        # Sync all to DB
        print(f"\n   Đồng bộ {len(all_db_records)} records vào SharedImageAsset DB local...")
        try:
            for r in all_db_records:
                asset = SharedImageAsset(
                    image_key=r["image_key"],
                    filename=f"{r['hex']}.svg",
                    mime_type="image/svg+xml",
                    storage_path=f"library/strokes/{r['raw_folder']}/{r['hex']}.svg",
                    sha256=r["sha256"],
                    size_bytes=r["size_bytes"],
                    description=f"Sơ đồ nét: {r['char']} ({r['locale']})",
                    tags=["stroke", r["locale"], r["char"], r["hex"]],
                    is_enabled=True,
                )
                db.session.add(asset)
            db.session.commit()
            print("   -> Đồng bộ Database thành công!")
        except Exception as exc:
            db.session.rollback()
            print(f"   -> Lỗi commit DB: {exc}")

    elapsed = time.time() - start_time
    print("\n" + "=" * 65)
    print(" HOÀN TẤT SEED LOCAL STROKE DATASET!")
    print(f"   SVG Authentic tải từ upstream : {results_summary['authentic']}")
    print(f"   SVG Mới được tự động sinh     : {results_summary['generated']}")
    print(f"   Tổng số SVG đã ghi nhận       : {sum(results_summary.values())}")
    print(f"   Thời gian thực hiện           : {elapsed:.2f}s")
    print("=" * 65)


if __name__ == "__main__":
    main()
