"""Tests for CJK character extractor."""

import unittest
from app.services.strokes.cjk_extractor import CjkExtractor, is_cjk_ideograph


class TestCjkExtractor(unittest.TestCase):
    def test_is_cjk_ideograph(self):
        # Kanji / Hanzi
        self.assertTrue(is_cjk_ideograph("日"))
        self.assertTrue(is_cjk_ideograph("本"))
        self.assertTrue(is_cjk_ideograph("勉"))
        self.assertTrue(is_cjk_ideograph("学"))
        self.assertTrue(is_cjk_ideograph("學"))
        self.assertTrue(is_cjk_ideograph("漢"))

        # Kana (Hiragana & Katakana)
        self.assertFalse(is_cjk_ideograph("あ"))
        self.assertFalse(is_cjk_ideograph("ん"))
        self.assertFalse(is_cjk_ideograph("ア"))
        self.assertFalse(is_cjk_ideograph("ン"))

        # Latin / digits / punctuation
        self.assertFalse(is_cjk_ideograph("A"))
        self.assertFalse(is_cjk_ideograph("1"))
        self.assertFalse(is_cjk_ideograph("。"))
        self.assertFalse(is_cjk_ideograph("、"))
        self.assertFalse(is_cjk_ideograph(" "))
        self.assertFalse(is_cjk_ideograph(""))

    def test_strip_html(self):
        html_input = "<p>日本語を<strong>勉強</strong>する</p>"
        self.assertIn("日本語を", CjkExtractor.strip_html(html_input))
        self.assertNotIn("<p>", CjkExtractor.strip_html(html_input))

        # Ruby markup
        ruby_input = "<ruby>勉<rp>(</rp><rt>べん</rt><rp>)</rp>強<rp>(</rp><rt>きょう</rt><rp>)</rp></ruby>"
        stripped = CjkExtractor.strip_html(ruby_input)
        self.assertNotIn("<ruby>", stripped)
        self.assertNotIn("<rt>", stripped)

    def test_extract_characters_japanese(self):
        text = "日本語を勉強する (にほんごをべんきょうする) - JLPT N5"
        chars = CjkExtractor.extract_characters(text)
        self.assertEqual(chars, ["日", "本", "語", "勉", "強"])

    def test_extract_characters_chinese(self):
        text = "我喜欢学习中文！"
        chars = CjkExtractor.extract_characters(text)
        self.assertEqual(chars, ["我", "喜", "欢", "学", "习", "中", "文"])

    def test_extract_characters_deduplication(self):
        text = "日曜日と月曜日 (Sunday and Monday)"
        chars_dedup = CjkExtractor.extract_characters(text, deduplicate=True)
        self.assertEqual(chars_dedup, ["日", "曜", "月"])

        chars_no_dedup = CjkExtractor.extract_characters(text, deduplicate=False)
        self.assertEqual(chars_no_dedup, ["日", "曜", "日", "月", "曜", "日"])

    def test_extract_characters_max_limit(self):
        text = "一二三四五六七八九十百千万"
        chars = CjkExtractor.extract_characters(text, max_limit=5)
        self.assertEqual(chars, ["一", "二", "三", "四", "五"])

    def test_char_to_hex(self):
        self.assertEqual(CjkExtractor.char_to_hex("勉"), "52c9")
        self.assertEqual(CjkExtractor.char_to_hex("勉", zero_pad=5), "052c9")
        self.assertEqual(CjkExtractor.char_to_hex("日"), "65e5")
        self.assertEqual(CjkExtractor.char_to_hex("日", zero_pad=5), "065e5")


if __name__ == "__main__":
    unittest.main()
