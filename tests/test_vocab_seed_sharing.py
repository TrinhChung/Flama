"""Tests for vocab-seed marketplace auto-sharing behavior."""

import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

from app import create_app
from app.services.flashcard_legacy import LEGACY_FRONT_TEMPLATE, LEGACY_SHARED_CSS
from models import db
from models.flashcard import DeckMarketplaceItem, Note, NoteType, Template
from models.user import User
from models.deck import Deck


class VocabSeedSharingTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            }
        )
        self.runner = self.app.test_cli_runner()
        with self.app.app_context():
            db.create_all()
            user = User(username="seed-owner", email="seed-owner@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.commit()
            self.user_id = user.id

        self.seed_dir = Path(tempfile.mkdtemp(prefix="flama-seed-"))
        unit_dir = self.seed_dir / "Unit 1"
        unit_dir.mkdir(parents=True, exist_ok=True)
        (unit_dir / "Lesson 1.csv").write_text(
            "deck,word,reading,translation_vi\n"
            "Unit 1,犬,いぬ,dog\n"
            "Unit 1,猫,ねこ,cat\n",
            encoding="utf-8",
        )
        (unit_dir / "Lesson 2.csv").write_text(
            "deck,word,reading,translation_vi\n"
            "Unit 1,鳥,とり,bird\n",
            encoding="utf-8",
        )
        chapter_dir = unit_dir / "Chapter A"
        chapter_dir.mkdir(parents=True, exist_ok=True)
        (chapter_dir / "Lesson 3.csv").write_text(
            "deck,word,reading,translation_vi\n"
            "Unit 1,魚,さかな,fish\n",
            encoding="utf-8",
        )

    def tearDown(self):
        shutil.rmtree(self.seed_dir, ignore_errors=True)
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_vocab_seed_auto_shares_only_top_level_deck_by_default(self):
        result = self.runner.invoke(
            args=["vocab-seed", "--path", str(self.seed_dir), "--owner-user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            shared_items = DeckMarketplaceItem.query.all()
            self.assertEqual(len(shared_items), 1)
            item = shared_items[0]
            top_deck = Deck.query.filter_by(name="Unit 1", parent_id=None).first()
            self.assertIsNotNone(top_deck)
            self.assertEqual(item.owner_user_id, self.user_id)
            self.assertEqual(item.publish_status, "published")
            self.assertTrue(item.is_official)
            self.assertEqual(item.pricing_mode, "free")
            self.assertEqual(item.source_deck_id, top_deck.id)

    def test_vocab_seed_can_disable_auto_share(self):
        result = self.runner.invoke(
            args=[
                "vocab-seed",
                "--path",
                str(self.seed_dir),
                "--owner-user-id",
                str(self.user_id),
                "--no-share-seeded-decks",
            ],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            self.assertEqual(DeckMarketplaceItem.query.count(), 0)

    def test_vocab_seed_uses_non_scrolling_front_template_for_default_vocab(self):
        result = self.runner.invoke(
            args=["vocab-seed", "--path", str(self.seed_dir), "--owner-user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            note_type = NoteType.query.filter_by(
                user_id=self.user_id,
                name="Flama Standard Vocabulary",
            ).first()
            self.assertIsNotNone(note_type)

            template = Template.query.filter_by(
                note_type_id=note_type.id,  # type: ignore[union-attr]
                is_default=True,
            ).first()
            self.assertIsNotNone(template)
        self.assertIn('class="legacy-front"', template.front_html)  # type: ignore[union-attr]
        self.assertIn('class="front-word"', template.front_html)  # type: ignore[union-attr]
        self.assertIn("{{word}}", template.front_html)  # type: ignore[union-attr]
        self.assertNotIn("100vh", template.front_html)  # type: ignore[union-attr]
        self.assertIn("html, body, .card", template.shared_css)  # type: ignore[union-attr]
        self.assertIn("height: 100%;", template.shared_css)  # type: ignore[union-attr]
        self.assertNotIn("100vh", template.shared_css)  # type: ignore[union-attr]

    def test_vocab_seed_seeds_quiz_dump_deck_for_owner(self):
        result = self.runner.invoke(
            args=["vocab-seed", "--path", str(self.seed_dir), "--owner-user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            quiz_note_type = NoteType.query.filter_by(
                user_id=self.user_id,
                name="Trắc nghiệm",
            ).first()
            self.assertIsNotNone(quiz_note_type)

            quiz_deck = Deck.query.filter_by(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Trac Nghiem Co Ban",
            ).first()
            self.assertIsNotNone(quiz_deck)
            self.assertEqual(quiz_deck.note_type_id, quiz_note_type.id)

            quiz_note_count = Note.query.filter_by(
                user_id=self.user_id,
                note_type_id=quiz_note_type.id,
                deck_id=quiz_deck.id,
            ).count()
            self.assertGreater(quiz_note_count, 0)

    def test_vocab_seed_supports_legacy_txt_dump_for_standard_vocab(self):
        legacy_root = Path(tempfile.mkdtemp(prefix="flama-legacy-seed-"))
        try:
            legacy_dir = legacy_root / "ChungBech"
            legacy_dir.mkdir(parents=True, exist_ok=True)
            legacy_file = legacy_dir / "ChungBechN1__言葉__Bài 01.txt"
            legacy_file.write_text(
                (
                    "#separator:tab\n"
                    "#html:true\n"
                    "#tags column:16\n"
                    "N1語彙Riki::Bài 1\t配布\tはいふ\tPhân phát\t不特定多数の人に配ること。\tPhân phát cho nhiều người.\t"
                    "チラシを配布する\tPhát tờ rơi\t駅前で配布した。\tPhát ở trước ga.\t\t\t\tvoice-1.mp3\texample-1.mp3\tseeded\n"
                    "N1語彙Riki::Bài 1\t完結\tかんけつ\tKết thúc\t物事が終わること。\tHoàn thành trọn vẹn.\t\t\t"
                    "ドラマが完結する。\tBộ phim kết thúc.\t\t\"<li>Dòng 1\nDòng 2</li>\"\t\tvoice-2.mp3\texample-2.mp3\tseeded\n"
                ),
                encoding="utf-8",
            )

            result = self.runner.invoke(
                args=[
                    "vocab-seed",
                    "--path",
                    str(legacy_root),
                    "--owner-user-id",
                    str(self.user_id),
                    "--no-share-seeded-decks",
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)

            with self.app.app_context():
                note_type = NoteType.query.filter_by(
                    user_id=self.user_id,
                    name="Flama Standard Vocabulary",
                ).first()
                self.assertIsNotNone(note_type)

                leaf_deck = Deck.query.filter_by(
                    owner_user_id=self.user_id,
                    name="ChungBechN1__言葉__Bài 01",
                ).first()
                self.assertIsNotNone(leaf_deck)

                notes = Note.query.filter_by(
                    user_id=self.user_id,
                    note_type_id=note_type.id,  # type: ignore[union-attr]
                    deck_id=leaf_deck.id,  # type: ignore[union-attr]
                ).all()
                self.assertEqual(len(notes), 2)

                note_by_word = {
                    str((note.field_values or {}).get("word")): (note.field_values or {})
                    for note in notes
                }
                self.assertIn("配布", note_by_word)
                self.assertIn("完結", note_by_word)

                first = note_by_word["配布"]
                self.assertIsNone(first.get("hanviet"))
                self.assertIsNone(first.get("diagram"))
                self.assertEqual(first.get("word_audio"), "voice-1.mp3")
                self.assertEqual(first.get("example_audio"), "example-1.mp3")

                second = note_by_word["完結"]
                self.assertEqual(second.get("reading"), "かんけつ")
                self.assertEqual(second.get("additional_note_vi"), "<li>Dòng 1\nDòng 2</li>")
                self.assertIsNone(second.get("image"))
        finally:
            shutil.rmtree(legacy_root, ignore_errors=True)

    def test_reseed_script_front_template_avoids_viewport_height_wrapper(self):
        seed_globals = runpy.run_path(
            str(Path(__file__).resolve().parents[1] / "scripts" / "seed_flama_template.py")
        )

        front_html = seed_globals["FRONT_HTML"]
        back_html = seed_globals["BACK_HTML"]
        shared_css = seed_globals["CSS"]

        self.assertIn('class="front-word"', front_html)
        self.assertIn("{{word}}", front_html)
        self.assertNotIn("100vh", front_html)
        self.assertIn("{{#word_audio}}", back_html)
        self.assertIn("{{#example_audio}}", back_html)
        self.assertIn(".front-word", shared_css)
        self.assertIn("html,", shared_css)
        self.assertIn("height: 100%;", shared_css)
        self.assertNotIn("100vh", shared_css)
        self.assertEqual(LEGACY_FRONT_TEMPLATE.strip().count("{{word}}"), 1)
        self.assertIn("height: 100%;", LEGACY_SHARED_CSS)

    def test_vocab_seed_supports_path_pointing_directly_to_seed_subfolder(self):
        direct_root = Path(tempfile.mkdtemp(prefix="flama-direct-seed-"))
        try:
            target_dir = direct_root / "ChungBech"
            target_dir.mkdir(parents=True, exist_ok=True)
            (target_dir / "Lesson 1.txt").write_text(
                (
                    "#separator:tab\n"
                    "#html:true\n"
                    "#tags column:16\n"
                    "Deck A\t犬\tいぬ\tdog\t\t\t\t\t\t\t\t\t\tword-audio.mp3\texample-audio.mp3\tseeded\n"
                ),
                encoding="utf-8",
            )

            result = self.runner.invoke(
                args=[
                    "vocab-seed",
                    "--path",
                    str(target_dir),
                    "--owner-user-id",
                    str(self.user_id),
                    "--no-share-seeded-decks",
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)

            with self.app.app_context():
                top_deck = Deck.query.filter_by(
                    owner_user_id=self.user_id,
                    parent_id=None,
                    name="ChungBech",
                ).first()
                self.assertIsNotNone(top_deck)

                leaf_deck = Deck.query.filter_by(
                    owner_user_id=self.user_id,
                    parent_id=top_deck.id,  # type: ignore[union-attr]
                    name="Lesson 1",
                ).first()
                self.assertIsNotNone(leaf_deck)

                note = Note.query.filter_by(
                    user_id=self.user_id,
                    deck_id=leaf_deck.id,  # type: ignore[union-attr]
                ).first()
                self.assertIsNotNone(note)
                self.assertEqual((note.field_values or {}).get("word"), "犬")  # type: ignore[union-attr]
        finally:
            shutil.rmtree(direct_root, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
