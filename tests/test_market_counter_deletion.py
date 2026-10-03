import unittest
from datetime import datetime, timedelta

from app import create_app
from app.services import (
    deck_management_service,
    flashcard_content_service,
    flashcards_share_service,
)
from app.services.share.helpers import ShareControllerError
from app.services.share.install import (
    install_shared_deck_item as modular_install_shared_deck_item,
    install_shared_deck_item_for_user as modular_install_shared_deck,
)
from models import db
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.review_event import ReviewEvent
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.template import Template
from models.user import User


class MarketCounterDeletionTests(unittest.TestCase):
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

        self.owner = User(username="owner", email="owner@example.com")
        self.owner.set_password("password")
        self.learner = User(username="learner", email="learner@example.com")
        self.learner.set_password("password")
        db.session.add_all([self.owner, self.learner])
        db.session.flush()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _note_type_install(self) -> tuple[NoteType, NoteType, NoteTypeInstall]:
        source = NoteType(
            user_id=self.owner.id,
            name="Source",
            install_count=1,
            active_usage_count=1,
        )
        installed = NoteType(
            user_id=self.learner.id,
            name="Installed",
            publish_status="private",
        )
        db.session.add_all([source, installed])
        db.session.flush()
        install = NoteTypeInstall(
            source_note_type_id=source.id,
            installed_note_type_id=installed.id,
            user_id=self.learner.id,
            market_active=True,
            market_active_policy_version=1,
        )
        db.session.add(install)
        db.session.commit()
        return source, installed, install

    def _enroll_note_authority(self, learner_id: int) -> None:
        now = datetime(2026, 9, 23)
        db.session.add(
            StudyAuthorityEnrollment(
                learner_user_id=learner_id,
                mode_code="NOTE",
                epoch=1,
                created_at=now,
                updated_at=now,
            )
        )
        db.session.commit()

    def test_deleting_installed_note_type_deactivates_usage_counter(self):
        source, installed, install = self._note_type_install()

        result = flashcard_content_service.delete_note_type(
            user_id=self.learner.id,
            note_type_id=installed.id,
        )

        self.assertTrue(result["success"])
        db.session.refresh(source)
        db.session.refresh(install)
        self.assertEqual(source.install_count, 1)
        self.assertEqual(source.active_usage_count, 0)
        self.assertFalse(install.market_active)

    def test_purging_installed_note_type_removes_install_counters(self):
        source, installed, install = self._note_type_install()
        install_id = install.id

        result = flashcard_content_service.delete_note_type(
            user_id=self.owner.id,
            note_type_id=installed.id,
            purge=True,
            is_admin=True,
        )

        self.assertTrue(result["purged"])
        db.session.refresh(source)
        self.assertEqual(source.install_count, 0)
        self.assertEqual(source.active_usage_count, 0)
        self.assertIsNone(db.session.get(NoteTypeInstall, install_id))

    def test_note_authority_owner_can_purge_empty_note_type(self):
        note_type = NoteType(user_id=self.owner.id, name="NOTE owner")
        db.session.add(note_type)
        db.session.commit()
        note_type_id = note_type.id
        self._enroll_note_authority(self.owner.id)

        result = flashcard_content_service.delete_note_type(
            user_id=self.learner.id, note_type_id=note_type_id, purge=True, is_admin=True)
        self.assertTrue(result["purged"])
        self.assertIsNone(db.session.get(NoteType, note_type_id))

    def test_note_authority_learners_frozen_progress_goes_with_the_purged_content(self):
        source, installed, install = self._note_type_install()
        template = Template(note_type_id=source.id, name="Front")
        note = Note(note_type_id=source.id, user_id=self.owner.id)
        db.session.add_all([template, note])
        db.session.flush()
        card = Card(note_id=note.id, template_id=template.id)
        db.session.add(card)
        db.session.flush()
        progress = CardProgress(user_id=self.learner.id, card_id=card.id)
        review = ReviewEvent(
            user_id=self.owner.id,
            card_id=card.id,
            note_type_id=source.id,
            rating="good",
            mode="review",
            reviewed_at=datetime(2026, 9, 23),
        )
        db.session.add_all([progress, review])
        db.session.commit()
        source_id, note_id, card_id = source.id, note.id, card.id
        install_id, progress_id, review_id = install.id, progress.id, review.id
        self._enroll_note_authority(self.learner.id)

        # A NOTE learner's card_progress is frozen, never authority (ADR P10):
        # it goes with its Card instead of blocking the purge.
        result = flashcard_content_service.delete_note_type(
            user_id=self.owner.id,
            note_type_id=source_id,
            purge=True,
            is_admin=True,
        )

        self.assertTrue(result["purged"])
        self.assertIsNone(db.session.get(NoteType, source_id))
        self.assertIsNone(db.session.get(Note, note_id))
        self.assertIsNone(db.session.get(Card, card_id))
        self.assertIsNone(db.session.get(CardProgress, progress_id))
        self.assertIsNotNone(db.session.get(ReviewEvent, review_id))
        self.assertIsNone(db.session.get(NoteTypeInstall, install_id))
        self.assertIsNone(db.session.get(ReviewEvent, review_id).note_type_id)

    def test_purging_local_clone_removes_deck_install_counters(self):
        source_deck = Deck(name="Source", owner_user_id=self.owner.id)
        local_deck = Deck(name="Installed", owner_user_id=self.learner.id)
        db.session.add_all([source_deck, local_deck])
        db.session.flush()
        item = DeckMarketplaceItem(
            owner_user_id=self.owner.id,
            source_deck_id=source_deck.id,
            title="Shared deck",
            install_count=1,
            active_usage_count=1,
        )
        db.session.add(item)
        db.session.flush()
        install = DeckInstall(
            deck_item_id=item.id,
            user_id=self.learner.id,
            local_deck_id=local_deck.id,
            source_deck_id=source_deck.id,
            source_owner_user_id=self.owner.id,
            market_active=True,
            market_active_policy_version=1,
        )
        db.session.add(install)
        db.session.commit()
        install_id = install.id

        result = deck_management_service.delete_deck_subtree(
            deck_obj=local_deck,
            user_id=self.owner.id,
            is_admin=True,
            purge=True,
        )

        self.assertEqual(result, "purged")
        db.session.refresh(item)
        self.assertEqual(item.install_count, 0)
        self.assertEqual(item.active_usage_count, 0)
        self.assertIsNone(db.session.get(DeckInstall, install_id))

    def test_note_authority_installs_overlay_like_legacy_from_both_entrypoints(self):
        source_deck = Deck(name="Source", owner_user_id=self.owner.id)
        source_type = NoteType(user_id=self.owner.id, name="Source type")
        db.session.add_all([source_deck, source_type])
        db.session.flush()
        item = DeckMarketplaceItem(
            owner_user_id=self.owner.id,
            source_deck_id=source_deck.id,
            source_note_type_id=source_type.id,
            title="NOTE install",
            publish_status="published",
        )
        legacy = User(username="legacy-installer", email="legacy-installer@example.com")
        db.session.add_all([item, legacy])
        db.session.commit()
        self._enroll_note_authority(self.learner.id)

        def outcome(install, user_id):
            try:
                install(item, user_id=user_id)
                db.session.commit()
            except Exception as exc:  # Two ShareControllerError classes exist.
                db.session.rollback()
                if not hasattr(exc, "error"):
                    raise
                return ("error", exc.error)
            return ("installed", DeckInstall.query.filter_by(user_id=user_id).count())

        for install in (
            modular_install_shared_deck,
            flashcards_share_service.install_shared_deck_item_for_user,
        ):
            DeckInstall.query.delete()
            db.session.commit()
            legacy_outcome = outcome(install, legacy.id)
            note_outcome = outcome(install, self.learner.id)
            # Overlay install no longer depends on the learner's authority mode.
            self.assertNotEqual(note_outcome, ("error", "OVERLAY_AUTHORITY_NOT_READY"))
            self.assertEqual(note_outcome, legacy_outcome)

    def test_note_authority_deletes_installed_clone_child_then_root(self):
        source_deck = Deck(name="Source", owner_user_id=self.owner.id)
        local_root = Deck(name="Installed", owner_user_id=self.learner.id)
        db.session.add_all([source_deck, local_root])
        db.session.flush()
        local_child = Deck(
            name="Installed child",
            owner_user_id=self.learner.id,
            parent_id=local_root.id,
        )
        item = DeckMarketplaceItem(
            owner_user_id=self.owner.id,
            source_deck_id=source_deck.id,
            title="Installed clone",
            install_count=1,
        )
        db.session.add_all([local_child, item])
        db.session.flush()
        install = DeckInstall(
            deck_item_id=item.id,
            user_id=self.learner.id,
            local_deck_id=local_root.id,
            source_deck_id=source_deck.id,
            source_owner_user_id=self.owner.id,
            clone_mode="logical_overlay",
        )
        db.session.add(install)
        db.session.flush()
        db.session.add(
            DeckCloneDeckMap(
                deck_install_id=install.id,
                local_deck_id=local_child.id,
                source_deck_id=source_deck.id,
            )
        )
        db.session.commit()
        self._enroll_note_authority(self.learner.id)

        install_id, child_id, root_id = install.id, local_child.id, local_root.id
        for target_id in (child_id, root_id):
            self.assertEqual(
                deck_management_service.delete_deck_subtree(
                    deck_obj=db.session.get(Deck, target_id),
                    user_id=self.learner.id,
                    is_admin=False,
                ),
                "deleted",
            )
            self.assertIsNone(db.session.get(Deck, target_id))
        self.assertIsNone(db.session.get(DeckInstall, install_id))
        db.session.refresh(item)
        self.assertEqual(item.install_count, 0)

    def test_deck_purge_takes_a_note_learners_frozen_progress_with_the_content(self):
        source_type = NoteType(user_id=self.owner.id, name="Deck source type")
        source_deck = Deck(
            name="Deck source", owner_user_id=self.owner.id, note_type=source_type
        )
        db.session.add_all([source_type, source_deck])
        db.session.flush()
        template = Template(note_type_id=source_type.id, name="Front")
        note = Note(
            note_type_id=source_type.id,
            user_id=self.owner.id,
            deck_id=source_deck.id,
        )
        db.session.add_all([template, note])
        db.session.flush()
        card = Card(note_id=note.id, template_id=template.id)
        db.session.add(card)
        db.session.flush()
        progress = CardProgress(user_id=self.learner.id, card_id=card.id)
        item = DeckMarketplaceItem(
            owner_user_id=self.owner.id,
            source_deck_id=source_deck.id,
            title="Deck source",
            install_count=1,
            active_usage_count=1,
        )
        db.session.add_all([progress, item])
        db.session.flush()
        local_deck = Deck(name="Installed", owner_user_id=self.learner.id)
        db.session.add(local_deck)
        db.session.flush()
        install = DeckInstall(
            deck_item_id=item.id,
            user_id=self.learner.id,
            local_deck_id=local_deck.id,
            source_deck_id=source_deck.id,
            source_owner_user_id=self.owner.id,
            market_active=True,
            market_active_policy_version=1,
        )
        review = ReviewEvent(
            user_id=self.owner.id,
            card_id=card.id,
            deck_id=source_deck.id,
            rating="good",
            mode="review",
            reviewed_at=datetime(2026, 9, 23),
        )
        db.session.add_all([install, review])
        db.session.commit()
        deck_id, note_id, card_id = source_deck.id, note.id, card.id
        progress_id, install_id, review_id = progress.id, install.id, review.id
        self._enroll_note_authority(self.learner.id)

        self.assertEqual(deck_management_service.delete_deck_subtree(
            deck_obj=source_deck,
            user_id=self.owner.id,
            is_admin=True,
            purge=True,
        ), "purged")

        self.assertFalse(db.session().in_transaction())
        self.assertIsNone(db.session.get(Deck, deck_id))
        self.assertIsNone(db.session.get(Note, note_id))
        self.assertIsNone(db.session.get(Card, card_id))
        self.assertIsNone(db.session.get(CardProgress, progress_id))
        self.assertIsNotNone(db.session.get(ReviewEvent, review_id))
        self.assertIsNone(db.session.get(DeckInstall, install_id))
        self.assertIsNone(db.session.get(ReviewEvent, review_id).deck_id)

    def _note_authority_clone_session_without_progress(self) -> tuple[str, int, int]:
        source_type = NoteType(user_id=self.owner.id, name="Session source type")
        source_deck = Deck(
            name="Session source", owner_user_id=self.owner.id, note_type=source_type
        )
        clone_deck = Deck(name="Session clone", owner_user_id=self.learner.id)
        db.session.add_all([source_type, source_deck, clone_deck])
        db.session.flush()
        template = Template(note_type_id=source_type.id, name="Front")
        note = Note(
            note_type_id=source_type.id,
            user_id=self.owner.id,
            deck_id=source_deck.id,
        )
        db.session.add_all([template, note])
        db.session.flush()
        card = Card(note_id=note.id, template_id=template.id)
        db.session.add(card)
        db.session.flush()
        session = StudySession(
            user_id=self.learner.id,
            scope_type="deck",
            scope_id=str(clone_deck.id),
            local_deck_id=clone_deck.id,
            snapshot_hash="session-only-snapshot",
            token_hash="a" * 64,
            config_snapshot_json="{}",
            expires_at=datetime(2026, 9, 23) + timedelta(hours=1),
        )
        db.session.add(session)
        db.session.flush()
        db.session.add(
            StudySessionCard(
                session_id=session.id,
                card_id=card.id,
                source_deck_id=source_deck.id,
                local_deck_id=clone_deck.id,
                note_type_id=source_type.id,
                base_progress_revision=0,
                base_state_hash="session-only-state",
                scheduler_config_hash="session-only-config",
                initial_state_json="{}",
                ordinal=0,
            )
        )
        db.session.commit()
        source_type_id, source_deck_id, session_id = (
            source_type.id,
            source_deck.id,
            session.id,
        )
        self._enroll_note_authority(self.learner.id)
        return source_type_id, source_deck_id, session_id

    def test_admin_deck_purge_cancels_note_authority_clone_session_without_progress(self):
        _, source_deck_id, session_id = self._note_authority_clone_session_without_progress()

        result = deck_management_service.delete_deck_subtree(
            deck_obj=db.session.get(Deck, source_deck_id),
            user_id=self.owner.id,
            is_admin=True,
            purge=True,
        )
        self.assertEqual(result, "purged")
        self.assertIsNone(db.session.get(Deck, source_deck_id))
        self.assertEqual(Card.query.count(), 0)
        self.assertEqual(db.session.get(StudySession, session_id).status, "cancelled")

    def test_admin_note_type_purge_cancels_note_authority_clone_session_without_progress(self):
        source_type_id, source_deck_id, session_id = (
            self._note_authority_clone_session_without_progress()
        )

        result = flashcard_content_service.delete_note_type(
            user_id=self.owner.id, note_type_id=source_type_id, purge=True, is_admin=True)
        self.assertTrue(result["purged"])
        self.assertIsNotNone(db.session.get(Deck, source_deck_id))
        self.assertIsNone(db.session.get(NoteType, source_type_id))
        self.assertEqual(db.session.get(StudySession, session_id).status, "cancelled")


if __name__ == "__main__":
    unittest.main()
