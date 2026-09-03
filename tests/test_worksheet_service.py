"""Unit tests for Worksheet Service."""

import unittest

from app import create_app
from app.services.worksheets.template_catalog import (
    KANJI_COMPACT_TEMPLATE,
    KANJI_STROKE_TEMPLATE,
    VOCAB_RECALL_TEMPLATE,
    VOCAB_WRITING_TEMPLATE,
    get_template,
    list_templates,
)
from app.services.worksheets.worksheet_service import (
    WorksheetServiceError,
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
        self.assertIn("kanji_stroke", ids)
        self.assertIn("kanji_compact", ids)
        self.assertIn("vocab_writing", ids)
        self.assertIn("vocab_recall", ids)
        self.assertIn("deck_table", ids)

    def test_get_template(self):
        tpl = get_template("kanji_stroke")
        self.assertIsNotNone(tpl)
        self.assertEqual(tpl.id, "kanji_stroke")
        self.assertEqual(tpl.category, "kanji")

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

    def test_generate_worksheet_preview_kanji_stroke(self):
        payload = {
            "template_id": "kanji_stroke",
            "deck_id": self.deck.id,
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
        self.assertEqual(res["template"]["id"], "kanji_stroke")
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
            "template_id": "kanji_stroke",
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
        # Optimal rows for kanji_stroke (36px box) with 1 extra blank row in Portrait = 9 items/page
        self.assertEqual(res["options"]["rows_per_page"], 9)
        self.assertEqual(len(res["pages"]), 1)
        # Page 1 has 5 real items + 4 filled blank rows = 9 items
        self.assertEqual(len(res["pages"][0]["items"]), 9)
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

    def test_kanji_reference_char_color_and_stroke_mode(self):
        # Test custom reference_char_color and monochrome stroke mode
        payload = {
            "template_id": "kanji_stroke",
            "deck_id": self.deck.id,
            "field_mapping": {"kanji": "Expression"},
            "options": {
                "reference_char_color": "#2563eb",
                "stroke_color_mode": "monochrome",
                "show_stroke_diagram": True,
            },
        }
        res = generate_worksheet_preview(user_id=self.user.id, payload=payload)
        self.assertEqual(res["template"]["id"], "kanji_stroke")
        self.assertEqual(res["options"]["reference_char_color"], "#2563eb")
        self.assertEqual(res["options"]["stroke_color_mode"], "monochrome")

        html_out = render_printable_html(res)
        # Verify custom fill color in reference char
        self.assertIn('fill="#2563eb"', html_out)
        # Verify monochrome stroke class and styles
        self.assertIn("flama-stroke-monochrome", html_out)


if __name__ == "__main__":
    unittest.main()
