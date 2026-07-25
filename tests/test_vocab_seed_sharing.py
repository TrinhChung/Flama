"""Tests for vocab-seed marketplace auto-sharing behavior."""

import runpy
import shutil
import tempfile
import unittest
from datetime import datetime
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

    def test_vocab_seed_keeps_same_named_decks_scoped_to_owner_and_reattaches_listing(self):
        with self.app.app_context():
            other = User(username="other-seed-owner", email="other-seed-owner@example.com")
            other.set_password("password")
            db.session.add(other)
            db.session.flush()
            other_deck = Deck(
                owner_user_id=other.id,
                parent_id=None,
                name="Unit 1",
                position=1,
            )
            db.session.add(other_deck)
            db.session.flush()
            listing = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=other_deck.id,
                title="Unit 1",
                description="Seeded deck: Unit 1",
                primary_category="Japanese",
                tags=["seeded", "default"],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="archived",
                is_official=True,
            )
            db.session.add(listing)
            db.session.commit()
            other_deck_id = other_deck.id
            listing_id = listing.id

        result = self.runner.invoke(
            args=[
                "vocab-seed",
                "--path",
                str(self.seed_dir),
                "--owner-user-id",
                str(self.user_id),
                "--replace-lessons",
            ],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            owner_deck = Deck.query.filter_by(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Unit 1",
            ).one()
            self.assertNotEqual(owner_deck.id, other_deck_id)
            self.assertEqual(Note.query.filter_by(deck_id=other_deck_id).count(), 0)

            listing = db.session.get(DeckMarketplaceItem, listing_id)
            self.assertIsNotNone(listing)
            self.assertEqual(listing.source_deck_id, owner_deck.id)  # type: ignore[union-attr]
            self.assertEqual(listing.publish_status, "published")  # type: ignore[union-attr]
            self.assertIsNone(listing.archived_at)  # type: ignore[union-attr]
            self.assertEqual(
                DeckMarketplaceItem.query.filter_by(
                    owner_user_id=self.user_id,
                    title="Unit 1",
                ).count(),
                1,
            )

    def test_vocab_seed_restores_soft_deleted_owned_deck_and_listing(self):
        archived_at = datetime(2026, 1, 1)
        with self.app.app_context():
            archived_deck = Deck(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Unit 1",
                position=1,
                deleted_at=archived_at,
            )
            db.session.add(archived_deck)
            db.session.flush()
            listing = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=archived_deck.id,
                title="Unit 1",
                description="Seeded deck: Unit 1",
                primary_category="Japanese",
                tags=["seeded", "default"],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="archived",
                archived_at=archived_at,
                is_official=True,
            )
            db.session.add(listing)
            db.session.commit()
            archived_deck_id = archived_deck.id
            listing_id = listing.id

        result = self.runner.invoke(
            args=["vocab-seed", "--path", str(self.seed_dir), "--owner-user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            restored_deck = db.session.get(Deck, archived_deck_id)
            restored_listing = db.session.get(DeckMarketplaceItem, listing_id)
            self.assertIsNotNone(restored_deck)
            self.assertIsNone(restored_deck.deleted_at)  # type: ignore[union-attr]
            self.assertGreater(Note.query.filter_by(user_id=self.user_id).count(), 0)
            self.assertEqual(restored_listing.source_deck_id, archived_deck_id)  # type: ignore[union-attr]
            self.assertEqual(restored_listing.publish_status, "published")  # type: ignore[union-attr]
            self.assertIsNone(restored_listing.archived_at)  # type: ignore[union-attr]

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

    def test_vocab_seed_splits_anki_export_by_deck_column(self):
        export_root = Path(tempfile.mkdtemp(prefix="flama-anki-seed-"))
        try:
            tettei_dir = export_root / "Tettei N1"
            tettei_dir.mkdir(parents=True, exist_ok=True)
            export_file = tettei_dir / "Tettei N1 export.txt"
            rows = [
                [
                    "ChungBechN1::語彙徹底N1::Bài 001",
                    "N1::徹底N1",
                    "維持",
                    "DUY TRÌ",
                    "いじ",
                    "duy trì",
                    "状態を保つこと",
                    "giữ nguyên trạng thái",
                    "状態を維持する",
                    "duy trì trạng thái",
                    "制度を維持する。",
                    "Duy trì chế độ.",
                    "保持との違い",
                    "Khác với 保持",
                    "image-1.jpg",
                    "diagram-1.svg",
                    "word-1.mp3",
                    "example-1.mp3",
                    "seeded",
                ],
                [
                    "ChungBechN1::語彙徹底N1::Bài 002",
                    "N1::徹底N2",
                    "意図",
                    "Ý ĐỒ",
                    "いと",
                    "ý đồ",
                    "目的やねらい",
                    "mục đích",
                    "意図を持つ",
                    "có ý đồ",
                    "別の意図がある。",
                    "Có ý đồ khác.",
                    "目的より主観的",
                    "Chủ quan hơn 目的",
                    "",
                    "",
                    "word-2.mp3",
                    "example-2.mp3",
                    "seeded",
                ],
            ]
            export_file.write_text(
                "\n".join(
                    [
                        "#separator:tab",
                        "#html:false",
                        "#deck column:1",
                        "#tags column:19",
                        *("\t".join(row) for row in rows),
                    ]
                )
                + "\n",
                encoding="utf-8",
            )

            result = self.runner.invoke(
                args=[
                    "vocab-seed",
                    "--path",
                    str(export_root),
                    "--owner-user-id",
                    str(self.user_id),
                    "--no-share-seeded-decks",
                ],
            )
            self.assertEqual(result.exit_code, 0, msg=result.output)
            self.assertIn("Split Anki export: Tettei N1 export.txt -> 2 deck(s)", result.output)

            with self.app.app_context():
                top_deck = Deck.query.filter_by(
                    owner_user_id=self.user_id,
                    parent_id=None,
                    name="Tettei N1",
                ).first()
                self.assertIsNotNone(top_deck)

                lesson_1 = Deck.query.filter_by(
                    owner_user_id=self.user_id,
                    parent_id=top_deck.id,  # type: ignore[union-attr]
                    name="Bài 001",
                ).first()
                lesson_2 = Deck.query.filter_by(
                    owner_user_id=self.user_id,
                    parent_id=top_deck.id,  # type: ignore[union-attr]
                    name="Bài 002",
                ).first()
                self.assertIsNotNone(lesson_1)
                self.assertIsNotNone(lesson_2)
                self.assertIsNone(Deck.query.filter_by(name="Tettei N1 export").first())
                self.assertIsNone(Deck.query.filter_by(name="ChungBechN1").first())

                first_note = Note.query.filter_by(deck_id=lesson_1.id).one()  # type: ignore[union-attr]
                first_values = first_note.field_values or {}
                self.assertEqual(first_values.get("word"), "維持")
                self.assertEqual(first_values.get("hanviet"), "DUY TRÌ")
                self.assertEqual(first_values.get("reading"), "いじ")
                self.assertEqual(first_values.get("diagram"), "diagram-1.svg")
                self.assertEqual(first_values.get("word_audio"), "word-1.mp3")
                self.assertEqual(first_values.get("example_audio"), "example-1.mp3")
                self.assertEqual(Note.query.filter_by(deck_id=lesson_2.id).count(), 1)  # type: ignore[union-attr]

            replace_result = self.runner.invoke(
                args=[
                    "vocab-seed",
                    "--path",
                    str(export_root),
                    "--owner-user-id",
                    str(self.user_id),
                    "--replace-lessons",
                    "--no-share-seeded-decks",
                ],
            )
            self.assertEqual(replace_result.exit_code, 0, msg=replace_result.output)
            self.assertIn("Replace seeded deck: Tettei N1 export.txt::Bài 001", replace_result.output)
            self.assertIn("Replace seeded deck: Tettei N1 export.txt::Bài 002", replace_result.output)
            with self.app.app_context():
                lesson_ids = [
                    row[0]
                    for row in db.session.query(Deck.id)
                    .filter(Deck.name.in_(["Bài 001", "Bài 002"]))
                    .all()
                ]
                self.assertEqual(Note.query.filter(Note.deck_id.in_(lesson_ids)).count(), 2)
        finally:
            shutil.rmtree(export_root, ignore_errors=True)

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
