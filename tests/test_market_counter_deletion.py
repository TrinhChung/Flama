import unittest

from app import create_app
from app.services import deck_management_service, flashcard_content_service
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
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


if __name__ == "__main__":
    unittest.main()
