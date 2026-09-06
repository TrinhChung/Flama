"""Unit tests for Worksheet Service."""

import unittest
from unittest.mock import patch

from app import create_app
from app.services.worksheets.template_catalog import (
    KANJI_COMPACT_TEMPLATE,
    KANJI_COMPOUND_TEMPLATE,
    KANJI_STEP_BY_STEP_TEMPLATE,
    KANJI_STROKE_TEMPLATE,
    VOCAB_RECALL_TEMPLATE,
    VOCAB_WRITING_TEMPLATE,
    calculate_optimal_rows_per_page,
    get_template,
    list_templates,
)
from app.services.worksheets.worksheet_service import (
    WorksheetServiceError,
    detect_deck_language,
    extract_cumulative_step_svgs,
    generate_worksheet_preview,
    get_deck_worksheet_meta,
    render_printable_html,
)
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.user import User


class TestWorksheetService(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()

        user = User(username="worksheet_user", email="worksheet_user@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()

        other_user = User(username="other_user", email="other@example.com")
        other_user.set_password("password")
        db.session.add(other_user)
        db.session.flush()

        note_type = NoteType(user_id=user.id, name="Vocabulary Standard")
        db.session.add(note_type)
        db.session.flush()

        f1 = FieldDef(note_type_id=note_type.id, name="Expression", position=0)
        f2 = FieldDef(note_type_id=note_type.id, name="Reading", position=1)
        f3 = FieldDef(note_type_id=note_type.id, name="Meaning", position=2)
        db.session.add_all([f1, f2, f3])
        db.session.flush()

        deck = Deck(name="JLPT N5 Core Vocabulary", owner_user_id=user.id)
        db.session.add(deck)
        db.session.flush()

        note1 = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "日本語を勉強する", "Reading": "にほんごをべんきょうする", "Meaning": "Học tiếng Nhật"},
        )
        note2 = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "学校に行く", "Reading": "がっこうにいく", "Meaning": "Đi đến trường"},
        )
        note3 = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "ひらがなだけ", "Reading": "ひらがなだけ", "Meaning": "Chỉ có hiragana"},
        )
        db.session.add_all([note1, note2, note3])
        db.session.commit()

        self.user = user
        self.other_user = other_user
        self.deck = deck
        self.note_type = note_type
        self.note1 = note1
        self.note2 = note2
        self.note3 = note3

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_list_templates(self):
        templates = list_templates()
        self.assertGreaterEqual(len(templates), 5)
        ids = [t["id"] for t in templates]
        self.assertNotIn("kanji_stroke", ids)
        self.assertIn("kanji_compact", ids)
        self.assertIn("vocab_writing", ids)
        self.assertIn("vocab_recall", ids)
        self.assertIn("deck_table", ids)

    def test_get_template(self):
        tpl = get_template("kanji_compact")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.id, "kanji_compact")
        self.assertEqual(tpl.name_vi, "Luyện viết Kanji chuẩn")
        self.assertEqual(tpl.category, "kanji")

        # kanji_stroke seamlessly aliases to kanji_compact
        tpl_stroke = get_template("kanji_stroke")
        self.assertIsNotNone(tpl_stroke)
        self.assertEqual(tpl_stroke.id, "kanji_compact")

    def test_get_deck_worksheet_meta(self):
        meta = get_deck_worksheet_meta(user_id=self.user.id, deck_id=self.deck.id)
        self.assertEqual(meta["deck_id"], self.deck.id)
        self.assertEqual(meta["deck_name"], "JLPT N5 Core Vocabulary")
        self.assertEqual(meta["total_notes"], 3)
        self.assertEqual(len(meta["note_types"]), 1)
        self.assertEqual(meta["note_types"][0]["fields"], ["Expression", "Reading", "Meaning"])
        self.assertEqual(meta["suggested_mappings"]["kanji"], "Expression")
        self.assertEqual(meta["suggested_mappings"]["reading"], "Reading")
        self.assertEqual(meta["suggested_mappings"]["meaning"], "Meaning")

    def test_get_deck_worksheet_meta_unauthorized(self):
        with self.assertRaises(WorksheetServiceError) as ctx:
            get_deck_worksheet_meta(user_id=self.other_user.id, deck_id=self.deck.id)
        self.assertEqual(ctx.exception.status, 403)

    @patch("app.services.worksheets.worksheet_service.check_stroke_svg_exists", return_value=True)
    @patch("app.services.worksheets.worksheet_service._get_stroke_svg_content", return_value="<svg><path d='M0,0'/></svg>")
    def test_generate_worksheet_preview_kanji_stroke(self, mock_svg_content, mock_stroke_exists):
        payload = {
            "template_id": "kanji_compact",
            "deck_id": self.deck.id,
            "note_type_id": self.note_type.id,
            "field_mapping": {
                "kanji": "Expression",
                "reading": "Reading",
                "meaning": "Meaning",
            },
            "options": {
                "rows_per_page": 4,
                "grid_style": "cross",
                "trace_count": 2,
                "practice_count": 5,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["template"]["id"], "kanji_compact")
        self.assertEqual(res["total_pages"], 2)  # 7 Kanji chars / 4 per page = 2 pages
        # "日本語を勉強する" -> 日, 本, 語, 勉, 強 (5)
        # "学校に行く" -> 学, 校, 行 (3)
        # Total = 8 chars
        self.assertGreaterEqual(res["total_items"], 7)
        self.assertEqual(len(res["pages"]), 2)

        # Check first item
        first_item = res["pages"][0]["items"][0]
        self.assertEqual(first_item["type"], "kanji")
        self.assertEqual(first_item["char"], "日")
        self.assertTrue(first_item["has_stroke"])

    def test_generate_worksheet_preview_vocab_writing(self):
        payload = {
            "template_id": "vocab_writing",
            "deck_id": self.deck.id,
            "field_mapping": {
                "word": "Expression",
                "reading": "Reading",
                "meaning": "Meaning",
            },
            "options": {
                "rows_per_page": 2,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["template"]["id"], "vocab_writing")
        self.assertEqual(res["total_items"], 3)
        self.assertEqual(res["total_pages"], 2)

    def test_generate_worksheet_preview_vocab_recall(self):
        payload = {
            "template_id": "vocab_recall",
            "deck_id": self.deck.id,
            "field_mapping": {
                "word": "Expression",
                "prompt_reading": "Reading",
                "prompt_meaning": "Meaning",
            },
            "options": {
                "rows_per_page": 10,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["template"]["id"], "vocab_recall")
        self.assertEqual(res["total_items"], 3)
        self.assertEqual(res["total_pages"], 1)

    def test_render_printable_html(self):
        payload = {
            "template_id": "kanji_stroke",
            "deck_id": self.deck.id,
            "field_mapping": {
                "kanji": "Expression",
                "reading": "Reading",
                "meaning": "Meaning",
            },
            "options": {
                "rows_per_page": 5,
                "grid_style": "cross",
                "header_title": "JLPT N5 Kanji Practice",
            },
        }
        preview_data = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        html_out = render_printable_html(preview_data)

        self.assertIn("<!DOCTYPE html>", html_out)
        self.assertIn("@page", html_out)
        self.assertIn("JLPT N5 Kanji Practice", html_out)
        self.assertIn("worksheet-grid-box", html_out)
        self.assertIn("<svg", html_out)

    def test_auto_fit_page_and_extra_blank_rows(self):
        # 1. Test optimal row calculation with auto_fit_page
        payload = {
            "template_id": "kanji_compact",
            "deck_id": self.deck.id,
            "note_ids": [self.note1.id],  # 5 Kanji chars
            "field_mapping": {"kanji": "Expression"},
            "options": {
                "auto_fit_page": True,
                "extra_blank_rows": 1,
                "fill_blank_rows": True,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertTrue(res["options"]["auto_fit_page"])
        self.assertEqual(res["options"]["extra_blank_rows"], 1)
        # Optimal rows for kanji_compact with 1 extra blank row in Portrait (max_density) = 12 items/page
        self.assertEqual(res["options"]["rows_per_page"], 12)
        self.assertEqual(len(res["pages"]), 1)
        # Page 1 has 5 real items + 7 filled blank rows = 12 items
        self.assertEqual(len(res["pages"][0]["items"]), 12)
        self.assertTrue(res["pages"][0]["items"][-1].get("is_blank_filler"))

        # Render printable HTML and verify extra blank strips
        html_out = render_printable_html(res)
        self.assertIn("kanji-extra-blank-strip", html_out)

    def test_sentence_writing_and_grammar_practice(self):
        # 1. Test Sentence Writing
        payload_sentence = {
            "template_id": "sentence_writing",
            "deck_id": self.deck.id,
            "field_mapping": {
                "sentence": "Expression",
                "reading": "Reading",
                "meaning": "Meaning",
            },
            "options": {
                "writing_lines_count": 4,
                "writing_line_style": "dashed",
                "watermark_enabled": True,
                "watermark_text": "FLAMA.APP",
            },
        }
        res_s = generate_worksheet_preview(user_id=self.user.id, payload=payload_sentence)
        self.assertEqual(res_s["template"]["id"], "sentence_writing")
        self.assertEqual(res_s["total_items"], 3)
        html_s = render_printable_html(res_s)
        self.assertIn("sentence-card", html_s)
        self.assertIn("sentence-write-line", html_s)
        self.assertIn("watermark-overlay", html_s)
        self.assertIn("FLAMA.APP", html_s)

        # 2. Test Grammar Practice
        payload_grammar = {
            "template_id": "grammar_practice",
            "deck_id": self.deck.id,
            "field_mapping": {
                "grammar_point": "Expression",
                "meaning_usage": "Meaning",
                "example": "Reading",
            },
            "options": {
                "exercise_prompt": "Hãy đặt 2 câu hoàn chỉnh với ngữ pháp trên:",
                "writing_lines_count": 3,
            },
        }
        res_g = generate_worksheet_preview(user_id=self.user.id, payload=payload_grammar)
        self.assertEqual(res_g["template"]["id"], "grammar_practice")
        html_g = render_printable_html(res_g)
        self.assertIn("grammar-card", html_g)
        self.assertIn("Hãy đặt 2 câu hoàn chỉnh", html_g)

    @patch("app.services.worksheets.worksheet_service.check_stroke_svg_exists", return_value=True)
    @patch("app.services.worksheets.worksheet_service._get_stroke_svg_content", return_value="<svg><path d='M0,0'/></svg>")
    def test_kanji_reference_char_color_and_stroke_mode(self, mock_svg_content, mock_stroke_exists):
        # Test custom reference_char_color and monochrome stroke mode
        payload = {
            "template_id": "kanji_compact",
            "deck_id": self.deck.id,
            "field_mapping": {"kanji": "Expression"},
            "options": {
                "reference_char_color": "#2563eb",
                "stroke_color_mode": "monochrome",
                "show_stroke_diagram": True,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["template"]["id"], "kanji_compact")
        self.assertEqual(res["options"]["reference_char_color"], "#2563eb")
        self.assertEqual(res["options"]["stroke_color_mode"], "monochrome")

        html_out = render_printable_html(res)
        # Verify custom fill color in reference char
        self.assertIn('fill="#2563eb"', html_out)
        # Verify monochrome stroke class and styles
        self.assertIn("flama-stroke-monochrome", html_out)

    def test_genkouyoushi_blank_and_text_modes(self):
        # 1. Blank worksheet generation without any deck_id
        blank_payload = {
            "template_id": "genkouyoushi",
            "options": {
                "content_mode": "blank",
                "grid_columns": 20,
                "grid_rows": 20,
                "header_student_style": "chinese",
                "title_placement": "first_row",
                "header_title": "如何离开手机",
                "essay_page_count": 1,
            },
        }
        res_blank = generate_worksheet_preview(user_id=self.user.id, payload=blank_payload)
        self.assertEqual(res_blank["template"]["id"], "genkouyoushi")
        self.assertEqual(res_blank["deck_id"], 0)
        self.assertEqual(res_blank["total_pages"], 1)
        self.assertEqual(len(res_blank["pages"][0]["items"]), 20)  # 20 rows
        self.assertEqual(len(res_blank["pages"][0]["items"][0]["cells"]), 20)  # 20 cells per row

        # Row 0 cells should be completely blank in blank mode
        self.assertTrue(all(c["is_blank"] for c in res_blank["pages"][0]["items"][0]["cells"]))

        html_blank = render_printable_html(res_blank)
        self.assertIn("genkou-sheet-body", html_blank)
        self.assertIn("班级", html_blank)
        self.assertIn("姓名", html_blank)
        self.assertIn("学号", html_blank)
        self.assertIn("分数", html_blank)
        self.assertIn("genkou-spacer-band", html_blank)
        self.assertIn("400格", html_blank)

        # 2. Text-filled worksheet generation
        text_payload = {
            "template_id": "genkouyoushi",
            "deck_id": self.deck.id,
            "options": {
                "content_mode": "text",
                "custom_text": "随着现代社会的发展，由于科技越来越发达，手机、电脑也走进了人们的生活。",
                "grid_columns": 20,
                "grid_rows": 20,
                "header_student_style": "vietnamese",
                "title_placement": "header",
                "header_title": "Tập làm văn tiếng Trung",
                "essay_page_count": 1,
            },
        }
        res_text = generate_worksheet_preview(user_id=self.user.id, payload=text_payload)
        self.assertEqual(res_text["template"]["id"], "genkouyoushi")
        self.assertEqual(res_text["total_pages"], 1)
        # Check that characters are placed in row 0
        first_row_chars = "".join([c["char"] for c in res_text["pages"][0]["items"][0]["cells"]])
        self.assertIn("随着现代社会的发展", first_row_chars)

        html_text = render_printable_html(res_text)
        self.assertIn("Lớp: ________________", html_text)
        self.assertIn("Họ tên: ________________", html_text)
        self.assertIn("Tập làm văn tiếng Trung", html_text)

    def test_detect_deck_language_and_meta_locale(self):
        """Test automatic language detection for Japanese vs Chinese decks."""
        # 1. Japanese deck (existing in setUp)
        self.assertEqual(detect_deck_language(self.deck, [self.note1, self.note2]), "ja")
        meta_ja = get_deck_worksheet_meta(user_id=self.user.id, deck_id=self.deck.id)
        self.assertEqual(meta_ja.get("detected_locale"), "ja")

        # 2. Chinese deck
        nt_zh = NoteType(user_id=self.user.id, name="Chinese HSK Note")
        db.session.add(nt_zh)
        db.session.flush()

        f_word = FieldDef(note_type_id=nt_zh.id, name="Word", position=0)
        f_pinyin = FieldDef(note_type_id=nt_zh.id, name="Pinyin", position=1)
        f_mean_vi = FieldDef(note_type_id=nt_zh.id, name="meaning_vi", position=2)
        db.session.add_all([f_word, f_pinyin, f_mean_vi])
        db.session.flush()

        deck_zh = Deck(name="HSK 1 - Từ vựng tiếng Trung cơ bản", owner_user_id=self.user.id)
        db.session.add(deck_zh)
        db.session.flush()

        note_zh1 = Note(
            user_id=self.user.id,
            note_type_id=nt_zh.id,
            deck_id=deck_zh.id,
            field_values={"Word": "汉语", "Pinyin": "Hànyǔ", "meaning_vi": "Tiếng Hán / Tiếng Trung"},
        )
        note_zh2 = Note(
            user_id=self.user.id,
            note_type_id=nt_zh.id,
            deck_id=deck_zh.id,
            field_values={"Word": "中国", "Pinyin": "Zhōngguó", "meaning_vi": "Trung Quốc"},
        )
        db.session.add_all([note_zh1, note_zh2])
        db.session.commit()

        self.assertEqual(detect_deck_language(deck_zh, [note_zh1, note_zh2]), "zh")
        meta_zh = get_deck_worksheet_meta(user_id=self.user.id, deck_id=deck_zh.id)
        self.assertEqual(meta_zh.get("detected_locale"), "zh")
        # Ensure meaning_vi is suggested over empty or Japanese meaning
        self.assertEqual(meta_zh.get("suggested_mappings", {}).get("meaning"), "meaning_vi")

    def test_chinese_simplified_stroke_svg_selection_and_numbers(self):
        """Test that Chinese decks use simplified Chinese SVGs with stroke numbers."""
        nt_zh = NoteType(user_id=self.user.id, name="HSK Test")
        db.session.add(nt_zh)
        db.session.flush()
        f1 = FieldDef(note_type_id=nt_zh.id, name="Word", position=0)
        f2 = FieldDef(note_type_id=nt_zh.id, name="Meaning", position=1)
        db.session.add_all([f1, f2])
        db.session.flush()

        deck_zh = Deck(name="HSK 1 Luyện viết chữ Hán", owner_user_id=self.user.id)
        db.session.add(deck_zh)
        db.session.flush()

        # '汉' is simplified Chinese
        note_zh = Note(
            user_id=self.user.id,
            note_type_id=nt_zh.id,
            deck_id=deck_zh.id,
            field_values={"Word": "汉", "Meaning": "Hán"},
        )
        db.session.add(note_zh)
        db.session.commit()

        # Generate preview without explicitly passing locale -> should auto-detect 'zh'
        payload = {
            "template_id": "kanji_stroke",
            "deck_id": deck_zh.id,
            "field_mapping": {"kanji": "Word", "meaning": "Meaning"},
            "options": {
                "show_stroke_diagram": True,
                "show_stroke_numbers": True,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["options"].get("locale"), "zh")
        self.assertGreater(res["total_items"], 0)
        item = res["pages"][0]["items"][0]
        self.assertEqual(item["char"], "汉")
        self.assertTrue(item["has_stroke"])
        self.assertIn("/strokes/zh/", item["stroke_url"])
        self.assertIn("flama-mmah-numbers", item["stroke_svg"])
        self.assertIn("flama-stroke-num", item["stroke_svg"])

        # Render HTML and verify stroke numbers and classes
        html_out = render_printable_html(res)
        self.assertIn("flama-mmah-numbers", html_out)
        self.assertIn("flama-stroke-num", html_out)

        # Test show_stroke_numbers: False adds flama-hide-stroke-numbers class
        payload["options"]["show_stroke_numbers"] = False
        res_no_num = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        html_no_num = render_printable_html(res_no_num)
        self.assertIn("flama-hide-stroke-numbers", html_no_num)

    def test_extract_cumulative_step_svgs(self):
        """Test generating cumulative stroke step SVGs for KanjiVG and MakeMeAHanzi formats."""
        # 1. KanjiVG sample
        kanjivg_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109">
            <path id="s1" class="flama-kvg-stroke" d="M10,10 L50,50" />
            <path id="s2" class="flama-kvg-stroke" d="M50,10 L10,50" />
        </svg>"""
        kvg_steps = extract_cumulative_step_svgs(kanjivg_svg, highlight_color="#e11d48", show_step_numbers=True)
        self.assertEqual(len(kvg_steps), 2)
        self.assertIn("flama-stroke-step", kvg_steps[0])
        self.assertIn("M10,10 L50,50", kvg_steps[0])
        self.assertNotIn("M50,10 L10,50", kvg_steps[0])  # Step 1 does not have stroke 2
        self.assertIn("M50,10 L10,50", kvg_steps[1])      # Step 2 has both strokes
        # Verify step 1 has stroke 1 faint highlighted for tracing (width 2.2, opacity 0.38)
        self.assertIn('stroke-width="2.2"', kvg_steps[0])
        self.assertIn('stroke="#e11d48"', kvg_steps[0])
        self.assertIn('stroke-opacity="0.38"', kvg_steps[0])
        # Verify step 2 has stroke 1 faint guide (#cbd5e1) and stroke 2 faint highlighted (#e11d48)
        self.assertIn('stroke="#cbd5e1"', kvg_steps[1])
        self.assertIn('stroke="#e11d48"', kvg_steps[1])
        self.assertIn('stroke-width="2.2"', kvg_steps[1])
        self.assertIn('stroke-opacity="0.38"', kvg_steps[1])

        # 2. MakeMeAHanzi sample
        mmah_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1024 1024">
            <path d="M 100 100 L 500 500" fill="lightgray" />
            <path d="M 500 100 L 100 500" fill="lightgray" />
            <path d="M 100 300 L 500 300" fill="lightgray" />
        </svg>"""
        mmah_steps = extract_cumulative_step_svgs(mmah_svg, highlight_color="#e11d48", show_step_numbers=True)
        self.assertEqual(len(mmah_steps), 3)
        self.assertIn("1024", mmah_steps[0])
        self.assertIn("scale(1, -1)", mmah_steps[0])
        # Step 1: stroke 1 is faint highlighted for tracing (opacity 0.38, no heavy outline)
        self.assertIn('fill="#e11d48"', mmah_steps[0])
        self.assertIn('fill-opacity="0.38"', mmah_steps[0])
        # Step 2: stroke 1 is faint guide (#cbd5e1), stroke 2 is faint highlighted (#e11d48)
        self.assertIn('fill="#cbd5e1"', mmah_steps[1])
        self.assertIn('fill-opacity="0.38"', mmah_steps[1])
        self.assertIn('fill="#e11d48"', mmah_steps[1])

    @patch("app.services.worksheets.worksheet_service.check_stroke_svg_exists", return_value=True)
    def test_generate_worksheet_preview_kanji_compound(self, mock_stroke_exists):
        """Test kanji_compound keeps words together as vocabulary compound units and uses normal text without SVGs."""
        payload = {
            "template_id": "kanji_compound",
            "deck_id": self.deck.id,
            "note_type_id": self.note_type.id,
            "field_mapping": {
                "kanji": "Expression",
                "reading": "Reading",
                "meaning": "Meaning",
            },
            "options": {
                "rows_per_page": 2,
                "grid_style": "cross",
                "trace_count": 2,
                "practice_count": 4,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["template"]["id"], "kanji_compound")
        self.assertEqual(res["total_items"], 2)  # 2 notes = 2 compound words (not split!)

        # First item should be the compound word "日本語を勉強する"
        first_item = res["pages"][0]["items"][0]
        self.assertEqual(first_item["type"], "kanji_compound")
        self.assertEqual(first_item["word"], "日本語を勉強する")
        # Characters should contain the extracted CJK characters in order without requiring stroke SVGs
        chars = [c["char"] for c in first_item["characters"]]
        self.assertIn("日", chars)
        self.assertIn("本", chars)
        self.assertIn("語", chars)
        self.assertIn("勉", chars)
        self.assertIn("強", chars)
        self.assertIsNone(first_item["characters"][0]["stroke_svg"])

        # Render HTML test
        html_out = render_printable_html(res)
        self.assertIn("compound-unit-block", html_out)
        self.assertNotIn('<div class="stroke-box-wrap"', html_out)
        self.assertNotIn('<div class="stroke-diagram-wrapper', html_out)

    @patch("app.services.worksheets.worksheet_service.check_stroke_svg_exists", return_value=True)
    @patch("app.services.worksheets.worksheet_service._get_stroke_svg_content")
    def test_generate_worksheet_preview_kanji_step_by_step(self, mock_svg_content, mock_stroke_exists):
        """Test kanji_step_by_step decomposes character into cumulative stroke steps."""
        mock_svg = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 109 109">
            <path id="s1" class="flama-kvg-stroke" d="M10,10 L50,50" />
            <path id="s2" class="flama-kvg-stroke" d="M50,10 L10,50" />
            <path id="s3" class="flama-kvg-stroke" d="M10,30 L50,30" />
        </svg>"""
        mock_svg_content.return_value = mock_svg

        payload = {
            "template_id": "kanji_step_by_step",
            "deck_id": self.deck.id,
            "note_type_id": self.note_type.id,
            "field_mapping": {
                "kanji": "Expression",
                "reading": "Reading",
                "meaning": "Meaning",
            },
            "options": {
                "rows_per_page": 4,
                "step_highlight_color": "#e11d48",
                "show_step_numbers": True,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["template"]["id"], "kanji_step_by_step")
        self.assertGreater(res["total_items"], 0)

        first_item = res["pages"][0]["items"][0]
        self.assertEqual(first_item["type"], "kanji_step_by_step")
        self.assertEqual(first_item["total_strokes"], 3)
        self.assertEqual(len(first_item["step_svgs"]), 3)
        self.assertIsNotNone(first_item.get("static_svg"))
        self.assertIsNotNone(first_item.get("trace_svg"))
        self.assertIn("flama-static-kanji-box", first_item["static_svg"])
        self.assertIn("flama-static-kanji-box", first_item["trace_svg"])

        # Render HTML test
        html_out = render_printable_html(res)
        self.assertIn("stroke-step-box", html_out)
        self.assertIn("stroke-static-box", html_out)
        self.assertIn("stroke-trace-box", html_out)
        self.assertIn("flama-stroke-step", html_out)
        self.assertNotIn("3 nét", html_out)
        self.assertIn("lbl-reading", html_out)

    def test_calculate_optimal_rows_per_page_comprehensive(self):
        # 1. Kanji templates Portrait
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compact", orientation="portrait", extra_blank_rows=0), 20)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compact", orientation="portrait", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 10)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compact", orientation="portrait", extra_blank_rows=1), 11)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_stroke", orientation="portrait", extra_blank_rows=0), 20)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_stroke", orientation="portrait", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 10)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_step_by_step", orientation="portrait", extra_blank_rows=0), 19)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_step_by_step", orientation="portrait", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 7)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_step_by_step", orientation="portrait", box_size=38, extra_blank_rows=0), 18)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_step_by_step", orientation="portrait", box_size=30, extra_blank_rows=0), 22)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_step_by_step", orientation="portrait", box_size=38, extra_blank_rows=1), 10)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compound", orientation="portrait", extra_blank_rows=0), 20)
        # Test page_fill_mode: max_density vs balanced_stretch in Portrait
        self.assertGreaterEqual(calculate_optimal_rows_per_page("kanji_compound", orientation="portrait", extra_blank_rows=0, page_fill_mode="max_density"), 18)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compound", orientation="portrait", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 10)

        # 2. Kanji templates Landscape
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compact", orientation="landscape", extra_blank_rows=0), 13)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compact", orientation="landscape", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 6)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compact", orientation="landscape", extra_blank_rows=1), 7)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_stroke", orientation="landscape", extra_blank_rows=0), 13)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_stroke", orientation="landscape", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 6)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_step_by_step", orientation="landscape", extra_blank_rows=0), 13)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_step_by_step", orientation="landscape", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 5)
        # Test page_fill_mode: max_density vs balanced_stretch in Landscape
        self.assertGreaterEqual(calculate_optimal_rows_per_page("kanji_compound", orientation="landscape", extra_blank_rows=0, page_fill_mode="max_density"), 11)
        self.assertEqual(calculate_optimal_rows_per_page("kanji_compound", orientation="landscape", extra_blank_rows=0, page_fill_mode="balanced_stretch"), 6)

        # 3. Vocabulary & Table templates
        self.assertEqual(calculate_optimal_rows_per_page("vocab_writing", orientation="portrait"), 28)
        self.assertEqual(calculate_optimal_rows_per_page("vocab_writing", orientation="portrait", page_fill_mode="balanced_stretch"), 18)
        self.assertEqual(calculate_optimal_rows_per_page("vocab_writing", orientation="landscape"), 18)
        self.assertEqual(calculate_optimal_rows_per_page("vocab_writing", orientation="landscape", page_fill_mode="balanced_stretch"), 12)
        self.assertEqual(calculate_optimal_rows_per_page("vocab_recall", orientation="portrait"), 24)
        self.assertEqual(calculate_optimal_rows_per_page("vocab_recall", orientation="portrait", page_fill_mode="balanced_stretch"), 20)
        self.assertEqual(calculate_optimal_rows_per_page("vocab_recall", orientation="landscape"), 16)
        self.assertEqual(calculate_optimal_rows_per_page("vocab_recall", orientation="landscape", page_fill_mode="balanced_stretch"), 13)
        self.assertEqual(calculate_optimal_rows_per_page("deck_table", orientation="portrait"), 29)
        self.assertEqual(calculate_optimal_rows_per_page("deck_table", orientation="portrait", page_fill_mode="balanced_stretch"), 24)
        self.assertEqual(calculate_optimal_rows_per_page("deck_table", orientation="landscape"), 19)
        self.assertEqual(calculate_optimal_rows_per_page("deck_table", orientation="landscape", page_fill_mode="balanced_stretch"), 15)

        # 4. Sentence & Grammar & Genkouyoushi
        self.assertEqual(calculate_optimal_rows_per_page("sentence_writing", orientation="portrait", extra_blank_rows=3), 7)
        self.assertEqual(calculate_optimal_rows_per_page("grammar_practice", orientation="portrait", extra_blank_rows=3), 7)
        self.assertEqual(calculate_optimal_rows_per_page("grammar_practice", orientation="portrait", extra_blank_rows=3, page_fill_mode="balanced_stretch"), 5)
        self.assertEqual(calculate_optimal_rows_per_page("genkouyoushi", orientation="portrait"), 20)
        self.assertEqual(calculate_optimal_rows_per_page("genkouyoushi", orientation="landscape"), 14)

        # 5. Margin awareness: wide margin reduces capacity if cramped
        rows_compact = calculate_optimal_rows_per_page("deck_table", orientation="portrait", margin="compact")
        rows_wide = calculate_optimal_rows_per_page("deck_table", orientation="portrait", margin="wide")
        self.assertGreaterEqual(rows_compact, rows_wide)

    def test_smart_deck_size_aware_pagination(self):
        # When a deck has e.g. 16 items for kanji_compact in balanced_stretch (aesthetic cap 10),
        # it expands to 16 to fit on 1 page instead of splitting into 2 pages with orphan items!
        rows_expanded = calculate_optimal_rows_per_page("kanji_compact", orientation="portrait", extra_blank_rows=0, total_items=16, page_fill_mode="balanced_stretch")
        self.assertEqual(rows_expanded, 16)

        # When fill_blank_rows is False and items < optimal, fits exact total_items
        rows_exact = calculate_optimal_rows_per_page("kanji_compact", orientation="portrait", extra_blank_rows=0, total_items=14, fill_blank_rows=False)
        self.assertEqual(rows_exact, 14)

        # Test preview with auto_fit_page (defaults to max_density: 23 rows/page for default box_size 30):
        # self.note1 has 5 kanji characters
        payload = {
            "template_id": "kanji_compact",
            "deck_id": self.deck.id,
            "note_ids": [self.note1.id],  # 5 characters
            "field_mapping": {"kanji": "Expression"},
            "options": {
                "auto_fit_page": True,
                "extra_blank_rows": 0,
                "fill_blank_rows": True,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["total_pages"], 1)
        self.assertEqual(res["options"]["rows_per_page"], 23)
        self.assertEqual(len(res["pages"][0]["items"]), 23)

    def test_adaptive_row_boxes_layout(self):
        """Test that kanji_compound and kanji_step_by_step dynamically calculate and fill row practice boxes."""
        # 1. Test kanji_compound with words of different character counts
        compound_preview = {
            "template": {"id": "kanji_compound", "name": "Từ vựng ghép chữ Hán"},
            "options": {
                "orientation": "portrait",
                "margin": "compact",
                "box_size": 36,
                "trace_count": 2,
                "practice_count": 4,
                "show_reading": True,
                "show_meaning": True,
            },
            "pages": [
                {
                    "page_number": 1,
                    "total_pages": 1,
                    "header": {"title": "Compound Practice"},
                    "items": [
                        {
                            "word": "春",
                            "reading": "はる",
                            "meaning": "spring",
                            "characters": [{"char": "春"}],
                        },
                        {
                            "word": "勉強",
                            "reading": "べんきょう",
                            "meaning": "study",
                            "characters": [{"char": "勉"}, {"char": "強"}],
                        },
                        {
                            "word": "日本語",
                            "reading": "にほんご",
                            "meaning": "Japanese",
                            "characters": [{"char": "日"}, {"char": "本"}, {"char": "語"}],
                        },
                    ],
                }
            ],
        }
        html_output = render_printable_html(compound_preview)
        self.assertIn("compound-unit-block", html_output)
        self.assertIn("compound-fill-boxes", html_output)
        self.assertIn("flex:1;overflow:hidden", html_output)
        # All 3 items should be rendered
        self.assertIn("はる", html_output)
        self.assertIn("べんきょう", html_output)
        self.assertIn("にほんご", html_output)

        # 2. Test kanji_step_by_step with low and high stroke counts
        mock_step_svg = '<svg viewBox="0 0 109 109"><path d="M10,10 L50,50" /></svg>'
        step_preview = {
            "template": {"id": "kanji_step_by_step", "name": "Luyện từng nét Kanji"},
            "options": {
                "orientation": "portrait",
                "margin": "compact",
                "box_size": 34,
                "trace_count": 2,
                "practice_count": 3,
                "show_reading": True,
                "show_meaning": True,
            },
            "pages": [
                {
                    "page_number": 1,
                    "total_pages": 1,
                    "header": {"title": "Step Practice"},
                    "items": [
                        {
                            "char": "木",
                            "reading": "き",
                            "meaning": "tree",
                            "total_strokes": 4,
                            "step_svgs": [mock_step_svg] * 4,
                        },
                        {
                            "char": "鬱",
                            "reading": "うつ",
                            "meaning": "depression",
                            "total_strokes": 18,
                            "step_svgs": [mock_step_svg] * 18,
                        },
                    ],
                }
            ],
        }
        step_html = render_printable_html(step_preview)
        self.assertIn("stroke-step-box", step_html)
        self.assertIn("kanji-step-strip", step_html)
        self.assertIn("flex:1;flex-wrap:wrap", step_html)
        self.assertIn("tree", step_html)
        self.assertIn("depression", step_html)

    def test_kanji_templates_default_hide_reading_meaning_and_example(self):
        """Kanji templates should default show_reading, show_meaning, and show_source_word to False."""
        for t_id in ("kanji_compact", "kanji_stroke", "kanji_compound", "kanji_step_by_step"):
            tpl = get_template(t_id)
            self.assertFalse(tpl.default_options.get("show_reading", True), f"{t_id} show_reading should default to False")
            self.assertFalse(tpl.default_options.get("show_meaning", True), f"{t_id} show_meaning should default to False")
            if t_id != "kanji_compound":
                self.assertFalse(tpl.default_options.get("show_source_word", True), f"{t_id} show_source_word should default to False")

        # Verify rendered HTML omits reading, meaning, and source word when using defaults
        preview = {
            "template": {"id": "kanji_compact", "name": "Luyện viết Kanji chuẩn"},
            "options": {},
            "pages": [
                {
                    "page_number": 1,
                    "total_pages": 1,
                    "header": {"title": "Test Kanji"},
                    "items": [
                        {
                            "char": "日",
                            "reading": "にち",
                            "meaning": "mặt trời",
                            "source_word": "日曜日",
                        }
                    ],
                }
            ],
        }
        html_out = render_printable_html(preview)
        self.assertNotIn('class="lbl-reading"', html_out)
        self.assertNotIn('class="lbl-meaning"', html_out)
        self.assertNotIn('class="lbl-word"', html_out)
        self.assertNotIn("にち", html_out)
        self.assertNotIn("mặt trời", html_out)
        self.assertNotIn("日曜日", html_out)


if __name__ == "__main__":
    unittest.main()


