"""Tests for Stroke Service (character resolution and batch note operations)."""

import unittest
from app import create_app
from app.services.strokes.stroke_service import (
    StrokeServiceError,
    batch_generate_strokes,
    normalize_locale,
    resolve_stroke_items,
)
from models import db
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.user import User


class TestStrokeService(unittest.TestCase):
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

        user = User(username="stroke_user", email="stroke_user@example.com")
        user.set_password("password")
        db.session.add(user)
        db.session.flush()

        note_type = NoteType(user_id=user.id, name="Vocabulary Standard")
        deck = Deck(name="JLPT N5 Core", owner_user_id=user.id)
        db.session.add_all([note_type, deck])
        db.session.flush()

        note1 = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "日本語を勉強する", "Meaning": "To study Japanese"},
        )
        note2 = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "学校に行く", "Meaning": "Go to school", "StrokeDiagram": "existing_svg"},
        )
        note3 = Note(
            user_id=user.id,
            note_type_id=note_type.id,
            deck_id=deck.id,
            field_values={"Expression": "hiragana only", "Meaning": "No kanji here"},
        )
        db.session.add_all([note1, note2, note3])
        db.session.commit()

        self.user = user
        self.deck = deck
        self.note1 = note1
        self.note2 = note2
        self.note3 = note3

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_normalize_locale(self):
        self.assertEqual(normalize_locale("ja"), "ja")
        self.assertEqual(normalize_locale("ja-JP"), "ja")
        self.assertEqual(normalize_locale("japanese"), "ja")
        self.assertEqual(normalize_locale("zh-CN"), "zh")
        self.assertEqual(normalize_locale("zh"), "zh")
        self.assertEqual(normalize_locale("zh-TW"), "zh-hant")
        self.assertEqual(normalize_locale("zh-hant"), "zh-hant")

    def test_resolve_stroke_items_html(self):
        res = resolve_stroke_items("勉強", locale="ja", output_format="html")
        self.assertEqual(res["characters"], ["勉", "強"])
        self.assertEqual(len(res["items"]), 2)
        self.assertIn('class="flama-stroke-diagram"', res["output"])
        self.assertIn('/media/library/stroke_ja_52c9', res["output"])
        self.assertIn('/media/library/stroke_ja_5f37', res["output"])

    def test_resolve_stroke_items_urls(self):
        res = resolve_stroke_items("勉強", locale="ja", output_format="urls")
        self.assertEqual(res["characters"], ["勉", "強"])
        self.assertIn('/media/library/stroke_ja_52c9', res["output"])

    def test_resolve_stroke_items_raw(self):
        res = resolve_stroke_items("勉強", locale="ja", output_format="raw")
        self.assertEqual(res["characters"], ["勉", "強"])
        self.assertEqual(res["output"], "/media/library/stroke_ja_52c9.svg\n/media/library/stroke_ja_5f37.svg")

    def test_batch_generate_strokes_deck(self):
        res = batch_generate_strokes(
            user_id=self.user.id,
            admin_mode=False,
            deck_id=self.deck.id,
            source_field="Expression",
            target_field="StrokeDiagram",
            locale="ja",
            overwrite=False,
        )
        self.assertEqual(res["total_processed"], 3)
        self.assertEqual(res["updated"], 1)  # note1 updated
        self.assertEqual(res["skipped"], 2)  # note2 already has existing_svg, note3 has no kanji

        # Verify note1 has StrokeDiagram
        db.session.refresh(self.note1)
        self.assertIn("/media/library/stroke_ja_52c9", self.note1.field_values.get("StrokeDiagram", ""))

        # Verify note2 was not overwritten
        db.session.refresh(self.note2)
        self.assertEqual(self.note2.field_values.get("StrokeDiagram"), "existing_svg")

    def test_batch_generate_strokes_overwrite(self):
        res = batch_generate_strokes(
            user_id=self.user.id,
            admin_mode=False,
            deck_id=self.deck.id,
            source_field="Expression",
            target_field="StrokeDiagram",
            locale="ja",
            overwrite=True,
        )
        self.assertEqual(res["updated"], 2)  # note1 and note2 updated

        db.session.refresh(self.note2)
        self.assertIn("/media/library/stroke_ja_5b66", self.note2.field_values.get("StrokeDiagram", ""))


if __name__ == "__main__":
    unittest.main()
