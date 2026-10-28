"""SVG cache invalidation and worksheet lookup behavior, without a database."""

import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from flask import Flask

from app.services.strokes.stroke_service import check_stroke_svg_exists
from app.services.worksheets import stroke_cache, worksheet_service


class WorksheetStrokeCacheTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        stroke_cache._read_svg.cache_clear()
        self.addCleanup(stroke_cache._read_svg.cache_clear)
        self.app = Flask(__name__, static_folder=str(self.root / "static"))
        self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = str(self.root / "uploads")
        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)

    def _write(self, relative, content):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def test_repeated_lookup_reads_file_once(self):
        path = self._write("static/strokes/ja/65e5.svg", "<svg>日</svg>")
        original = Path.read_text
        with patch.object(Path, "read_text", autospec=True, side_effect=original) as reader:
            self.assertEqual(stroke_cache.read_stroke_svg(path), "<svg>日</svg>")
            self.assertEqual(stroke_cache.read_stroke_svg(path), "<svg>日</svg>")
        self.assertEqual(reader.call_count, 1)

    def test_same_size_replacement_invalidates_cache(self):
        path = self._write("character.svg", "<svg>A</svg>")
        self.assertEqual(stroke_cache.read_stroke_svg(path), "<svg>A</svg>")
        before = path.stat()
        path.write_text("<svg>B</svg>", encoding="utf-8")
        os.utime(path, ns=(before.st_atime_ns, before.st_mtime_ns + 1_000_000_000))
        self.assertEqual(stroke_cache.read_stroke_svg(path), "<svg>B</svg>")

    def test_deleted_file_is_not_served_from_cache(self):
        path = self._write("character.svg", "<svg>A</svg>")
        stroke_cache.read_stroke_svg(path)
        path.unlink()
        with self.assertRaises(FileNotFoundError):
            stroke_cache.read_stroke_svg(path)

    def test_missing_file_is_not_negatively_cached(self):
        path = self.root / "later.svg"
        with self.assertRaises(FileNotFoundError):
            stroke_cache.read_stroke_svg(path)
        path.write_text("<svg>new</svg>", encoding="utf-8")
        self.assertEqual(stroke_cache.read_stroke_svg(path), "<svg>new</svg>")

    def test_large_files_bypass_cache(self):
        path = self._write("large.svg", "x" * (stroke_cache._MAX_CACHED_BYTES + 1))
        stroke_cache.read_stroke_svg(path)
        stroke_cache.read_stroke_svg(path)
        self.assertEqual(stroke_cache._read_svg.cache_info().currsize, 0)

    def test_cache_does_not_mix_roots_or_locales(self):
        for relative, content in (("a/ja/65e5.svg", "<svg>one</svg>"),
                ("b/ja/65e5.svg", "<svg>two</svg>"), ("a/zh/65e5.svg", "<svg>three</svg>")):
            path = self._write(relative, content)
            self.assertEqual(stroke_cache.read_stroke_svg(path), content)

    def test_static_lookup_preserves_precedence_and_skips_upload_resolution(self):
        self._write("static/strokes/ja/65e5.svg", "<svg>static</svg>")
        self._write("uploads/library/strokes/ja/65e5.svg", "<svg>library</svg>")
        with patch.object(worksheet_service, "_get_upload_root", side_effect=AssertionError("unneeded")):
            self.assertEqual(worksheet_service._get_stroke_svg_content("ja", "65e5"), "<svg>static</svg>")
        with patch("app.services.strokes.stroke_service._get_upload_root", side_effect=AssertionError("unneeded")):
            self.assertTrue(check_stroke_svg_exists("ja", "65e5"))

    def test_padded_and_chinese_fallbacks_preserve_content(self):
        self._write("static/strokes/ja/065e5.svg", "<svg>padded</svg>")
        self._write("static/strokes/zh/65e5.svg", "<svg>Chinese</svg>")
        self.assertEqual(worksheet_service._get_stroke_svg_content("ja", "65e5"), "<svg>padded</svg>")
        self.assertEqual(worksheet_service._get_stroke_svg_content("zh-hant", "65e5"), "<svg>Chinese</svg>")
        self.assertTrue(check_stroke_svg_exists("ja", "65e5"))

    def test_library_fallback_and_deletion_are_visible(self):
        path = self._write("uploads/library/strokes/ja/65e5.svg", "<svg>library</svg>")
        self.assertTrue(check_stroke_svg_exists("ja", "65e5"))
        self.assertEqual(worksheet_service._get_stroke_svg_content("ja", "65e5"), "<svg>library</svg>")
        path.unlink()
        self.assertFalse(check_stroke_svg_exists("ja", "65e5"))
        self.assertIsNone(worksheet_service._get_stroke_svg_content("ja", "65e5"))


if __name__ == "__main__":
    unittest.main()
