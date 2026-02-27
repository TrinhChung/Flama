"""Integration tests for deck settings actions on dashboard dropdown."""

import unittest

from app import create_app
from app.utils.deck_move_token import create_deck_move_token
from models import db
from models.flashcard import Card, DeckInstall, DeckMarketplaceItem, Note, NoteType, Template
from models.user import User
from models.user_role import UserRole
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_progress import VocabularyProgress


class DeckSettingsRoutesTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            admin_role = UserRole.query.filter_by(code="admin").first()
            regular_role = UserRole.query.filter_by(code="regular").first()
            assert admin_role is not None
            assert regular_role is not None

            admin = User(
                username="admin",
                email="admin@example.com",
                is_admin=True,
                role_id=admin_role.id,
            )
            admin.set_password("password")
            other = User(
                username="other",
                email="other@example.com",
                is_admin=False,
                role_id=regular_role.id,
            )
            other.set_password("password")
            db.session.add_all([admin, other])
            db.session.commit()
            self.admin_id = admin.id
            self.other_user_id = other.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_admin(self):
        return self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )

    def _login_other(self):
        return self.client.post(
            "/login",
            data={"email": "other@example.com", "password": "password"},
            follow_redirects=True,
        )

    def test_rename_deck_rejects_duplicate_sibling_name(self):
        with self.app.app_context():
            deck_a = VocabularyDeck(name="Deck A", parent_id=None, position=1)
            deck_b = VocabularyDeck(name="Deck B", parent_id=None, position=2)
            db.session.add_all([deck_a, deck_b])
            db.session.commit()
            deck_a_id = deck_a.id

        self._login_admin()
        response = self.client.post(
            f"/vocabulary/decks/{deck_a_id}/rename",
            data={"name": "Deck B", "next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            deck_a = VocabularyDeck.query.get(deck_a_id)
            self.assertIsNotNone(deck_a)
            self.assertEqual(deck_a.name, "Deck A")

    def test_move_deck_rejects_duplicate_name_under_target_parent(self):
        with self.app.app_context():
            parent_a = VocabularyDeck(name="Parent A", parent_id=None, position=1)
            parent_b = VocabularyDeck(name="Parent B", parent_id=None, position=2)
            db.session.add_all([parent_a, parent_b])
            db.session.flush()

            moving = VocabularyDeck(name="Shared Name", parent_id=parent_a.id, position=1)
            existing = VocabularyDeck(name="Shared Name", parent_id=parent_b.id, position=1)
            db.session.add_all([moving, existing])
            db.session.commit()
            moving_id = moving.id
            original_parent_id = parent_a.id
            target_parent_id = parent_b.id

        self._login_admin()
        response = self.client.post(
            f"/vocabulary/decks/{moving_id}/move",
            data={"parent_id": str(target_parent_id), "next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            moved = VocabularyDeck.query.get(moving_id)
            self.assertIsNotNone(moved)
            self.assertEqual(moved.parent_id, original_parent_id)

    def test_move_deck_rejects_parent_into_child(self):
        with self.app.app_context():
            parent = VocabularyDeck(name="Parent", parent_id=None, position=1)
            db.session.add(parent)
            db.session.flush()
            child = VocabularyDeck(name="Child", parent_id=parent.id, position=1)
            db.session.add(child)
            db.session.commit()
            parent_id = parent.id
            child_id = child.id

        self._login_admin()
        response = self.client.post(
            f"/vocabulary/decks/{parent_id}/move",
            data={"parent_id": str(child_id), "next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            moved_parent = VocabularyDeck.query.get(parent_id)
            self.assertIsNotNone(moved_parent)
            self.assertIsNone(moved_parent.parent_id)

    def test_move_deck_accepts_temporary_tokens(self):
        with self.app.app_context():
            parent_a = VocabularyDeck(name="Parent A", parent_id=None, position=1)
            parent_b = VocabularyDeck(name="Parent B", parent_id=None, position=2)
            db.session.add_all([parent_a, parent_b])
            db.session.flush()
            moving = VocabularyDeck(name="Deck Move", parent_id=parent_a.id, position=1)
            db.session.add(moving)
            db.session.commit()

            moving_id = moving.id
            target_parent_id = parent_b.id
            moving_token = create_deck_move_token(moving_id, self.admin_id)
            target_parent_token = create_deck_move_token(target_parent_id, self.admin_id)

        self._login_admin()
        response = self.client.post(
            "/vocabulary/decks/move",
            data={
                "deck_token": moving_token,
                "parent_token": target_parent_token,
                "next": "/dashboard",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            moved = VocabularyDeck.query.get(moving_id)
            self.assertIsNotNone(moved)
            self.assertEqual(moved.parent_id, target_parent_id)

    def test_reset_deck_only_clears_current_user_progress(self):
        with self.app.app_context():
            deck = VocabularyDeck(name="Deck Reset", parent_id=None, position=1)
            db.session.add(deck)
            db.session.flush()

            note_type = NoteType(user_id=self.admin_id, name="Deck Reset Note Type")
            template = Template(
                note_type=note_type,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Word}}",
                shared_css="",
                position=0,
                is_default=True,
            )
            note = Note(
                note_type=note_type,
                user_id=self.admin_id,
                deck_id=deck.id,
                field_values={"Word": "test"},
            )
            card = Card(note=note, template=template, queue="new")
            db.session.add_all([note_type, template, note, card])
            db.session.flush()

            admin_progress = VocabularyProgress(
                user_id=self.admin_id,
                new_card_id=card.id,
                queue="learning",
                step_index=1,
            )
            other_progress = VocabularyProgress(
                user_id=self.other_user_id,
                new_card_id=card.id,
                queue="learning",
                step_index=1,
            )
            db.session.add_all([admin_progress, other_progress])
            db.session.commit()
            deck_id = deck.id
            card_id = card.id

        self._login_admin()
        response = self.client.post(
            f"/vocabulary/decks/{deck_id}/reset",
            data={"next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            admin_progress_count = VocabularyProgress.query.filter_by(
                user_id=self.admin_id,
                new_card_id=card_id,
            ).count()
            other_progress_count = VocabularyProgress.query.filter_by(
                user_id=self.other_user_id,
                new_card_id=card_id,
            ).count()
            self.assertEqual(admin_progress_count, 0)
            self.assertEqual(other_progress_count, 1)

    def test_clone_owner_can_delete_cloned_deck_and_install_row(self):
        with self.app.app_context():
            cloned_root = VocabularyDeck(
                name="Installed Root",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(cloned_root)
            db.session.flush()

            cloned_child = VocabularyDeck(
                name="Installed Child",
                parent_id=cloned_root.id,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(cloned_child)
            db.session.flush()

            shared_item = DeckMarketplaceItem(
                owner_user_id=self.admin_id,
                title="Shared Deck",
                description="Shared deck description",
                primary_category="General",
                tags=[],
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(shared_item)
            db.session.flush()

            install_row = DeckInstall(
                deck_item_id=shared_item.id,
                user_id=self.other_user_id,
                local_deck_id=cloned_root.id,
            )
            db.session.add(install_row)
            db.session.commit()
            cloned_root_id = cloned_root.id
            cloned_child_id = cloned_child.id
            install_row_id = install_row.id

        self._login_other()
        response = self.client.post(
            f"/vocabulary/decks/{cloned_root_id}/delete",
            data={"next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNone(VocabularyDeck.query.get(cloned_root_id))
            self.assertIsNone(VocabularyDeck.query.get(cloned_child_id))
            self.assertIsNone(DeckInstall.query.get(install_row_id))

    def test_non_admin_cannot_delete_owned_deck_without_clone_install(self):
        with self.app.app_context():
            owned_deck = VocabularyDeck(
                name="Owned Deck",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(owned_deck)
            db.session.commit()
            owned_deck_id = owned_deck.id

        self._login_other()
        response = self.client.post(
            f"/vocabulary/decks/{owned_deck_id}/delete",
            data={"next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNotNone(VocabularyDeck.query.get(owned_deck_id))

    def test_clone_owner_can_delete_subdeck_with_install_on_ancestor(self):
        with self.app.app_context():
            cloned_root = VocabularyDeck(
                name="Installed Root",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(cloned_root)
            db.session.flush()

            cloned_child = VocabularyDeck(
                name="Installed Child",
                parent_id=cloned_root.id,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(cloned_child)
            db.session.flush()

            shared_item = DeckMarketplaceItem(
                owner_user_id=self.admin_id,
                title="Shared Deck Child Delete",
                description="Shared deck description",
                primary_category="General",
                tags=[],
                pricing_mode="free",
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(shared_item)
            db.session.flush()

            install_row = DeckInstall(
                deck_item_id=shared_item.id,
                user_id=self.other_user_id,
                local_deck_id=cloned_root.id,
            )
            db.session.add(install_row)
            db.session.commit()
            cloned_root_id = cloned_root.id
            cloned_child_id = cloned_child.id
            install_row_id = install_row.id

        self._login_other()
        response = self.client.post(
            f"/vocabulary/decks/{cloned_child_id}/delete",
            data={"next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNotNone(VocabularyDeck.query.get(cloned_root_id))
            self.assertIsNone(VocabularyDeck.query.get(cloned_child_id))
            self.assertIsNotNone(DeckInstall.query.get(install_row_id))


if __name__ == "__main__":
    unittest.main()
