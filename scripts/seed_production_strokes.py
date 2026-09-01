#!/usr/bin/env python
"""Production Pre-generation script for 2,500+ Japanese Kanji & 9,000+ Chinese Hanzi."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from wsgi import app
from app.services.strokes.production_seeder import seed_production_strokes_dataset


def main():
    parser = argparse.ArgumentParser(description="Pre-generate Production Stroke Diagrams for Japanese & Chinese.")
    parser.add_argument("--locale", default="all", choices=["all", "ja", "zh", "zh-hant"], help="Language target")
    parser.add_argument("--limit-ja", type=int, default=2500, help="Japanese Kanji count (default: 2500)")
    parser.add_argument("--limit-zh", type=int, default=9000, help="Simplified Chinese Hanzi count (default: 9000)")
    parser.add_argument("--limit-zh-hant", type=int, default=9000, help="Traditional Chinese Hanzi count (default: 9000)")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent worker threads (default: 4)")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay in seconds between requests (default: 0.0)")
    parser.add_argument("--force", action="store_true", help="Force overwrite existing SVGs")

    args = parser.parse_args()

    print("=" * 60)
    print(" FLAMA PRODUCTION STROKE PRE-GENERATION PIPELINE")
    print("=" * 60)
    print(f"  Locale target : {args.locale}")
    print(f"  JA limit      : {args.limit_ja}")
    print(f"  ZH limit      : {args.limit_zh}")
    print(f"  ZH-HANT limit : {args.limit_zh_hant}")
    print(f"  Concurrency   : {args.workers} worker threads (delay: {args.delay}s)")
    print(f"  Force rewrite : {args.force}")
    print("-" * 60)

    start_time = time.time()

    def on_progress(p: dict):
        completed = p["completed"]
        total = p["total"]
        loc = p["locale"]
        if completed % 100 == 0 or completed == total:
            pct = (completed / total) * 100 if total else 100
            print(f"[{loc.upper()}] Progress: {completed}/{total} ({pct:.1f}%) - U+{ord(p['char']):04X}")

    with app.app_context():
        stats = seed_production_strokes_dataset(
            locales=(args.locale,) if args.locale != "all" else ("ja", "zh", "zh-hant"),
            limit_ja=args.limit_ja,
            limit_zh=args.limit_zh,
            limit_zh_hant=args.limit_zh_hant,
            workers=args.workers,
            delay=args.delay,
            force=args.force,
            progress_callback=on_progress,
        )

    elapsed = time.time() - start_time
    print("-" * 60)
    print(" PRODUCTION STROKE PRE-GENERATION COMPLETED!")
    print(f"  Total Characters Processed : {stats['total_targets']}")
    print(f"  Newly Generated SVGs       : {stats['generated']}")
    print(f"  Cached / Skipped           : {stats['cached']}")
    print(f"  Failed / Fallbacks         : {stats['failed']}")
    print(f"  Database Records Synced    : {stats['db_updated']}")
    print(f"  Total Duration             : {elapsed:.2f}s")
    print("=" * 60)


if __name__ == "__main__":
    main()
