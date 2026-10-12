"""Tests for vocab-seed marketplace auto-sharing behavior."""

import os
import runpy
import shutil
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from app import create_app
from app.services.flashcard_legacy import (
    LEGACY_BACK_TEMPLATE,
    LEGACY_FRONT_TEMPLATE,
    LEGACY_SHARED_CSS,
)
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from models import db
from tests.study_note_fixtures import create_note_user, attach_template, assert_retired_progress_absent
from tests.note_progress_fixtures import stage_note_state, subject_for_card, decode_note_state
from models.study_progress_subject import StudyProgressSubject
from models.flashcard import Card, DeckMarketplaceItem, Note, NoteType, Template
from models.study_authority_enrollment import StudyAuthorityEnrollment
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
            user = create_note_user(db.session, username="seed-owner", email="seed-owner@example.com", is_admin=True)
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

    @staticmethod
    def _deck_subtree_ids(root_deck_id: int) -> set[int]:
        deck_ids = {root_deck_id}
        pending = [root_deck_id]
        while pending:
            parent_id = pending.pop()
            child_ids = [
                row[0]
                for row in db.session.query(Deck.id)
                .filter(Deck.parent_id == parent_id)
                .all()
            ]
            for child_id in child_ids:
                if child_id in deck_ids:
                    continue
                deck_ids.add(child_id)
                pending.append(child_id)
        return deck_ids

    def _count_notes_in_subtree(self, root_deck_id: int) -> int:
        return Note.query.filter(
            Note.deck_id.in_(self._deck_subtree_ids(root_deck_id))
        ).count()

    def _invoke_seed_data_ensure(
        self,
        *,
        admin_email: str = "seed-owner@example.com",
        admin_user: str = "seed-owner",
    ):
        with patch.dict(
            os.environ,
            {
                "ADMIN_EMAIL": admin_email,
                "ADMIN_USER": admin_user,
            },
            clear=False,
        ):
            return self.runner.invoke(
                args=["seed-data-ensure", "--path", str(self.seed_dir)]
            )

    def test_vocab_seed_rejects_legacy_authority_before_creating_content(self):
        with self.app.app_context():
            db.session.get(StudyAuthorityEnrollment, self.user_id).mode_code = "LEGACY"
            db.session.commit()

        result = self.runner.invoke(
            args=[
                "vocab-seed",
                "--path",
                str(self.seed_dir),
                "--owner-user-id",
                str(self.user_id),
            ]
        )
        self.assertNotEqual(result.exit_code, 0)
        self.assertIn("STUDY_AUTHORITY_MIGRATION_REQUIRED", result.output)
        with self.app.app_context():
            self.assertEqual(NoteType.query.count(), 0)
            self.assertEqual(Deck.query.count(), 0)
            self.assertEqual(Note.query.count(), 0)

    def test_seed_data_ensure_seeds_empty_database_then_fast_skips(self):
        first_result = self._invoke_seed_data_ensure()
        self.assertEqual(first_result.exit_code, 0, msg=first_result.output)
        self.assertIn("Seed data is incomplete", first_result.output)
        self.assertIn("Seed data ensure completed", first_result.output)

        with self.app.app_context():
            top_deck = Deck.query.filter_by(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Unit 1",
            ).one()
            self.assertGreater(Note.query.filter_by(user_id=self.user_id).count(), 0)
            self.assertIsNotNone(
                DeckMarketplaceItem.query.filter_by(
                    owner_user_id=self.user_id,
                    source_deck_id=top_deck.id,
                    publish_status="published",
                ).first()
            )
            card = (
                Card.query.join(Note, Card.note_id == Note.id)
                .filter(Note.user_id == self.user_id)
                .order_by(Card.id.asc())
                .first()
            )
            self.assertIsNotNone(card)
            db.session.add(
                stage_note_state(db.session,
                    user_id=self.user_id,
                    card_id=card.id,  # type: ignore[union-attr]
                    reps=7,
                )
            )
            db.session.commit()
            card_id = card.id  # type: ignore[union-attr]

        second_result = self._invoke_seed_data_ensure()
        self.assertEqual(second_result.exit_code, 0, msg=second_result.output)
        self.assertIn("Seed data already complete", second_result.output)
        self.assertNotIn("Seeding from:", second_result.output)

        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Card, card_id))
            progress = decode_note_state(subject_for_card(db.session, user_id=self.user_id, card_id=card_id))
            self.assertEqual(progress.reps, 7)

    def test_seed_data_ensure_adds_new_bundle_without_replacing_existing(self):
        first_result = self._invoke_seed_data_ensure()
        self.assertEqual(first_result.exit_code, 0, msg=first_result.output)

        with self.app.app_context():
            unit_one = Deck.query.filter_by(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Unit 1",
            ).one()
            unit_one_deck_ids = self._deck_subtree_ids(unit_one.id)
            unit_one_note_ids = {
                note.id
                for note in Note.query.filter(
                    Note.user_id == self.user_id,
                    Note.deck_id.in_(unit_one_deck_ids),
                ).all()
            }

            quiz_note_type = NoteType.query.filter_by(
                user_id=self.user_id,
                name="Trắc nghiệm",
            ).one()
            quiz_deck = Deck.query.filter_by(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Trac Nghiem Co Ban",
            ).one()
            quiz_card = (
                Card.query.join(Note, Card.note_id == Note.id)
                .filter(
                    Note.note_type_id == quiz_note_type.id,
                    Note.deck_id == quiz_deck.id,
                )
                .first()
            )
            self.assertIsNotNone(quiz_card)
            db.session.add(
                stage_note_state(db.session,
                    user_id=self.user_id,
                    card_id=quiz_card.id,  # type: ignore[union-attr]
                    reps=11,
                )
            )
            db.session.commit()
            quiz_card_id = quiz_card.id  # type: ignore[union-attr]

        unit_two = self.seed_dir / "Unit 2"
        unit_two.mkdir()
        (unit_two / "Lesson 1.csv").write_text(
            "deck,word,reading,translation_vi\n"
            "Unit 2,学校,がっこう,school\n",
            encoding="utf-8",
        )

        second_result = self._invoke_seed_data_ensure()
        self.assertEqual(second_result.exit_code, 0, msg=second_result.output)
        self.assertIn("seed bundle missing: Unit 2", second_result.output)
        self.assertIn("Skip quiz deck (already seeded)", second_result.output)

        with self.app.app_context():
            unit_two_deck = Deck.query.filter_by(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Unit 2",
            ).one()
            self.assertGreater(
                self._count_notes_in_subtree(unit_two_deck.id),
                0,
            )
            current_unit_one_note_ids = {
                note.id
                for note in Note.query.filter_by(user_id=self.user_id).all()
                if note.id in unit_one_note_ids
            }
            self.assertEqual(current_unit_one_note_ids, unit_one_note_ids)
            progress = decode_note_state(subject_for_card(db.session, user_id=self.user_id, card_id=quiz_card_id))
            self.assertEqual(progress.reps, 11)

    def test_seed_data_ensure_reuses_existing_owner_after_bootstrap_admin_changes(self):
        first_result = self._invoke_seed_data_ensure()
        self.assertEqual(first_result.exit_code, 0, msg=first_result.output)

        with self.app.app_context():
            new_admin = create_note_user(db.session,
                username="replacement-admin",
                email="replacement-admin@example.com",
                is_admin=True,
            )
            new_admin.set_password("password")
            db.session.add(new_admin)
            db.session.commit()
            new_admin_id = new_admin.id

        second_result = self._invoke_seed_data_ensure(
            admin_email="replacement-admin@example.com",
            admin_user="replacement-admin",
        )
        self.assertEqual(second_result.exit_code, 0, msg=second_result.output)
        self.assertIn("Using existing canonical seed owner", second_result.output)
        self.assertIn("Seed data already complete", second_result.output)

        with self.app.app_context():
            self.assertEqual(
                Deck.query.filter_by(
                    owner_user_id=self.user_id,
                    parent_id=None,
                    name="Unit 1",
                ).count(),
                1,
            )
            self.assertEqual(
                Deck.query.filter_by(
                    owner_user_id=new_admin_id,
                    parent_id=None,
                    name="Unit 1",
                ).count(),
                0,
            )

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

    def test_seed_owner_sees_owned_listing_in_installed_deck_workspace(self):
        result = self.runner.invoke(
            args=["vocab-seed", "--path", str(self.seed_dir), "--owner-user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            item = DeckMarketplaceItem.query.filter_by(
                owner_user_id=self.user_id,
                title="Unit 1",
            ).one()
            source_deck_id = item.source_deck_id
            item_id = item.id

        client = self.app.test_client()
        login_response = client.post(
            "/login",
            data={"email": "seed-owner@example.com", "password": "password"},
            follow_redirects=True,
        )
        self.assertEqual(login_response.status_code, 200)

        response = client.get("/flashcards/installed-decks")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', html)

        api_response = client.get("/api/marketplace/installed-decks")
        self.assertEqual(api_response.status_code, 200)
        items = (api_response.get_json() or {}).get("items", [])
        self.assertTrue(any(item.get("title") == "Unit 1" for item in items))

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
            other = create_note_user(db.session, username="other-seed-owner", email="other-seed-owner@example.com")
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

    def test_vocab_seed_archives_stale_duplicate_official_listing(self):
        with self.app.app_context():
            current_deck = Deck(
                owner_user_id=self.user_id,
                parent_id=None,
                name="Unit 1",
                position=1,
            )
            other = create_note_user(db.session, username="stale-owner", email="stale-owner@example.com")
            other.set_password("password")
            db.session.add_all([current_deck, other])
            db.session.flush()
            stale_deck = Deck(
                owner_user_id=other.id,
                parent_id=None,
                name="Unit 1",
                position=1,
            )
            db.session.add(stale_deck)
            db.session.flush()

            current_listing = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=current_deck.id,
                title="Unit 1",
                description="Current",
                primary_category="Japanese",
                tags=["seeded", "default"],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
                is_official=True,
            )
            stale_listing = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=stale_deck.id,
                title="Unit 1",
                description="Stale",
                primary_category="Japanese",
                tags=["seeded", "default"],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
                is_official=True,
            )
            db.session.add_all([current_listing, stale_listing])
            db.session.commit()
            current_listing_id = current_listing.id
            stale_listing_id = stale_listing.id

        result = self.runner.invoke(
            args=["vocab-seed", "--path", str(self.seed_dir), "--owner-user-id", str(self.user_id)],
        )
        self.assertEqual(result.exit_code, 0, msg=result.output)

        with self.app.app_context():
            current_listing = db.session.get(DeckMarketplaceItem, current_listing_id)
            stale_listing = db.session.get(DeckMarketplaceItem, stale_listing_id)
            self.assertEqual(current_listing.publish_status, "published")  # type: ignore[union-attr]
            self.assertTrue(current_listing.is_official)  # type: ignore[union-attr]
            self.assertEqual(stale_listing.publish_status, "archived")  # type: ignore[union-attr]
            self.assertFalse(stale_listing.is_official)  # type: ignore[union-attr]
            self.assertIsNotNone(stale_listing.archived_at)  # type: ignore[union-attr]

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

    def test_vocab_seed_uses_canonical_template_and_only_two_default_note_types(self):
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
            identity_fields = [
                field.name
                for field in note_type.field_defs  # type: ignore[union-attr]
                if field.identity_role == "primary"
            ]

            from models.study_application import StudyApplication
            template = Template.query.join(StudyApplication, StudyApplication.template_id == Template.id).filter(
                StudyApplication.note_type_id == note_type.id,
                StudyApplication.status_code == "ACTIVE", StudyApplication.is_default.is_(True),
            ).first()
            self.assertIsNotNone(template)
            note_type_names = {
                row[0]
                for row in db.session.query(NoteType.name)
                .filter(NoteType.user_id == self.user_id)
                .all()
            }
            template_names = {
                row[0]
                for row in db.session.query(Template.name)
                .join(StudyApplication, StudyApplication.template_id == Template.id)
                .join(NoteType, StudyApplication.note_type_id == NoteType.id)
                .filter(NoteType.user_id == self.user_id)
                .all()
            }

        self.assertEqual(template.front_html, LEGACY_FRONT_TEMPLATE.strip())  # type: ignore[union-attr]
        self.assertEqual(template.back_html, LEGACY_BACK_TEMPLATE.strip())  # type: ignore[union-attr]
        self.assertEqual(template.shared_css, LEGACY_SHARED_CSS.strip())  # type: ignore[union-attr]
        self.assertEqual(identity_fields, ["word"])
        self.assertEqual(
            note_type_names,
            {"Flama Standard Vocabulary", "Trắc nghiệm"},
        )
        self.assertEqual(
            template_names,
            {"Default Flama Flashcard", "Default Quiz Flashcard"},
        )

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

    def test_reseed_script_uses_canonical_flama_standard_vocabulary_template(self):
        seed_script = Path(__file__).resolve().parents[1] / "scripts" / "seed_flama_template.py"
        seed_globals = runpy.run_path(str(seed_script))
        seed_source = seed_script.read_text(encoding="utf-8")

        front_html = seed_globals["FRONT_HTML"]
        back_html = seed_globals["BACK_HTML"]
        shared_css = seed_globals["CSS"]

        self.assertIn("height:100vh", front_html)
        self.assertIn("{{word}}", front_html)
        self.assertIn("{{#word_audio}}", back_html)
        self.assertIn("{{#example_audio}}", back_html)
        self.assertIn(".kanji-stroke-images", shared_css)
        self.assertIn("@media (max-width: 480px)", shared_css)
        self.assertEqual(front_html.strip(), LEGACY_FRONT_TEMPLATE.strip())
        self.assertEqual(back_html.strip(), LEGACY_BACK_TEMPLATE.strip())
        self.assertEqual(shared_css.strip(), LEGACY_SHARED_CSS.strip())
        self.assertEqual(LEGACY_FRONT_TEMPLATE.strip().count("{{word}}"), 1)
        self.assertIn("ensure_legacy_note_type(db.session, user.id)", seed_source)
        self.assertNotIn("default-flama-vocab-000000000000", seed_source)
        self.assertNotIn("default-template-000000000000", seed_source)

    def test_reseed_quiz_helper_rejects_legacy_authority_before_content(self):
        seed_script = Path(__file__).resolve().parents[1] / "scripts" / "seed_flama_template.py"
        seed_globals = runpy.run_path(str(seed_script))
        with self.app.app_context():
            db.session.get(StudyAuthorityEnrollment, self.user_id).mode_code = "LEGACY"
            db.session.commit()
            with self.assertRaises(StudyAuthorityFenceError) as caught:
                seed_globals["_seed_quiz_dump_for_user"](
                    user_id=self.user_id,
                    note_type_id="unused",
                    template_id="unused",
                )
            self.assertEqual(caught.exception.code, "STUDY_AUTHORITY_MIGRATION_REQUIRED")
            db.session.rollback()
            self.assertEqual(Note.query.count(), 0)
            self.assertEqual(Deck.query.count(), 0)

    def test_reseed_wrapper_progress_counts_match_their_commands(self):
        scripts_dir = Path(__file__).resolve().parents[1] / "scripts"
        shell_source = (scripts_dir / "reseed_db.sh").read_text(encoding="utf-8")
        powershell_source = (scripts_dir / "reseed_db.ps1").read_text(encoding="utf-8")
        batch_source = (scripts_dir / "reseed_db.bat").read_text(encoding="utf-8")

        for step in range(1, 7):
            self.assertIn(f"[{step}/6]", shell_source)
        for source in (powershell_source, batch_source):
            for step in range(1, 6):
                self.assertIn(f"[{step}/5]", source)

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
