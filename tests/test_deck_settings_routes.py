"""Integration tests for deck settings actions on dashboard dropdown."""

from datetime import datetime, timedelta
import unittest

from app import create_app
from app.utils.deck_move_token import create_deck_move_token
from models import db
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, DeckMarketplaceItem, Note, NoteType, Template
from models.user import User
from models.user_role import UserRole
from models.deck import Deck
from models.card_progress import CardProgress


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
            deck_a = Deck(name="Deck A", parent_id=None, position=1)
            deck_b = Deck(name="Deck B", parent_id=None, position=2)
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
            deck_a = Deck.query.get(deck_a_id)
            self.assertIsNotNone(deck_a)
            self.assertEqual(deck_a.name, "Deck A")

    def test_move_deck_rejects_duplicate_name_under_target_parent(self):
        with self.app.app_context():
            parent_a = Deck(name="Parent A", parent_id=None, position=1)
            parent_b = Deck(name="Parent B", parent_id=None, position=2)
            db.session.add_all([parent_a, parent_b])
            db.session.flush()

            moving = Deck(name="Shared Name", parent_id=parent_a.id, position=1)
            existing = Deck(name="Shared Name", parent_id=parent_b.id, position=1)
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
            moved = Deck.query.get(moving_id)
            self.assertIsNotNone(moved)
            self.assertEqual(moved.parent_id, original_parent_id)

    def test_move_deck_rejects_parent_into_child(self):
        with self.app.app_context():
            parent = Deck(name="Parent", parent_id=None, position=1)
            db.session.add(parent)
            db.session.flush()
            child = Deck(name="Child", parent_id=parent.id, position=1)
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
            moved_parent = Deck.query.get(parent_id)
            self.assertIsNotNone(moved_parent)
            self.assertIsNone(moved_parent.parent_id)

    def test_move_deck_accepts_temporary_tokens(self):
        with self.app.app_context():
            parent_a = Deck(name="Parent A", parent_id=None, position=1)
            parent_b = Deck(name="Parent B", parent_id=None, position=2)
            db.session.add_all([parent_a, parent_b])
            db.session.flush()
            moving = Deck(name="Deck Move", parent_id=parent_a.id, position=1)
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
            moved = Deck.query.get(moving_id)
            self.assertIsNotNone(moved)
            self.assertEqual(moved.parent_id, target_parent_id)

    def test_reset_deck_only_clears_current_user_progress(self):
        with self.app.app_context():
            deck = Deck(name="Deck Reset", parent_id=None, position=1)
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
            card = Card(note=note, template=template)
            db.session.add_all([note_type, template, note, card])
            db.session.flush()

            admin_progress = CardProgress(
                user_id=self.admin_id,
                card_id=card.id,
                queue="learning",
                step_index=1,
            )
            other_progress = CardProgress(
                user_id=self.other_user_id,
                card_id=card.id,
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
            admin_progress_count = CardProgress.query.filter_by(
                user_id=self.admin_id,
                card_id=card_id,
            ).count()
            other_progress_count = CardProgress.query.filter_by(
                user_id=self.other_user_id,
                card_id=card_id,
            ).count()
            self.assertEqual(admin_progress_count, 0)
            self.assertEqual(other_progress_count, 1)

    def test_non_admin_owner_can_reset_owned_deck_without_clone_install(self):
        with self.app.app_context():
            owned_deck = Deck(
                name="Owned Reset Deck",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(owned_deck)
            db.session.flush()

            note_type = NoteType(user_id=self.other_user_id, name="Owned Reset Note Type")
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
                user_id=self.other_user_id,
                deck_id=owned_deck.id,
                field_values={"Word": "mine"},
            )
            card = Card(note=note, template=template)
            db.session.add_all([note_type, template, note, card])
            db.session.flush()

            owner_progress = CardProgress(
                user_id=self.other_user_id,
                card_id=card.id,
                queue="review",
                reps=3,
            )
            admin_progress = CardProgress(
                user_id=self.admin_id,
                card_id=card.id,
                queue="review",
                reps=4,
            )
            db.session.add_all([owner_progress, admin_progress])
            db.session.commit()
            owned_deck_id = owned_deck.id
            card_id = card.id

        self._login_other()
        response = self.client.post(
            f"/vocabulary/decks/{owned_deck_id}/reset",
            data={"next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            owner_progress_count = CardProgress.query.filter_by(
                user_id=self.other_user_id,
                card_id=card_id,
            ).count()
            admin_progress_count = CardProgress.query.filter_by(
                user_id=self.admin_id,
                card_id=card_id,
            ).count()
            self.assertEqual(owner_progress_count, 0)
            self.assertEqual(admin_progress_count, 1)

    def test_clone_owner_can_reset_progress_for_overlay_source_cards(self):
        with self.app.app_context():
            source_root = Deck(name="Source Root", parent_id=None, owner_user_id=self.admin_id, position=1)
            cloned_root = Deck(name="Installed Root", parent_id=None, owner_user_id=self.other_user_id, position=2)
            db.session.add_all([source_root, cloned_root])
            db.session.flush()

            note_type = NoteType(user_id=self.admin_id, name="Clone Reset Note Type")
            template = Template(
                note_type=note_type,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Word}}",
                shared_css="",
                position=0,
                is_default=True,
            )
            source_note = Note(
                note_type=note_type,
                user_id=self.admin_id,
                deck_id=source_root.id,
                field_values={"Word": "overlay"},
            )
            source_card = Card(note=source_note, template=template)
            db.session.add_all([note_type, template, source_note, source_card])
            db.session.flush()

            shared_item = DeckMarketplaceItem(
                owner_user_id=self.admin_id,
                source_deck_id=source_root.id,
                source_note_type_id=note_type.id,
                title="Shared Deck",
                description="Shared deck description",
                primary_category="General",
                tags=[],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(shared_item)
            db.session.flush()

            install_row = DeckInstall(
                deck_item_id=shared_item.id,
                user_id=self.other_user_id,
                local_deck_id=cloned_root.id,
                clone_mode="logical_overlay",
                source_deck_id=source_root.id,
                source_owner_user_id=self.admin_id,
                base_snapshot_at=datetime.utcnow() + timedelta(minutes=1),
            )
            db.session.add(install_row)
            db.session.flush()
            db.session.add(
                DeckCloneDeckMap(
                    deck_install_id=install_row.id,
                    local_deck_id=cloned_root.id,
                    source_deck_id=source_root.id,
                )
            )

            owner_progress = CardProgress(
                user_id=self.other_user_id,
                card_id=source_card.id,
                queue="review",
                reps=5,
            )
            admin_progress = CardProgress(
                user_id=self.admin_id,
                card_id=source_card.id,
                queue="review",
                reps=7,
            )
            db.session.add_all([owner_progress, admin_progress])
            db.session.commit()
            cloned_root_id = cloned_root.id
            source_card_id = source_card.id

        self._login_other()
        response = self.client.post(
            f"/vocabulary/decks/{cloned_root_id}/reset",
            data={"next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            owner_progress_count = CardProgress.query.filter_by(
                user_id=self.other_user_id,
                card_id=source_card_id,
            ).count()
            admin_progress_count = CardProgress.query.filter_by(
                user_id=self.admin_id,
                card_id=source_card_id,
            ).count()
            self.assertEqual(owner_progress_count, 0)
            self.assertEqual(admin_progress_count, 1)

    def test_non_admin_dashboard_serves_react_shell(self):
        self._login_other()
        response = self.client.get("/dashboard")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)

    def test_non_admin_can_open_note_type_manager_page(self):
        self._login_other()
        response = self.client.get("/flashcards/note-types")
        self.assertEqual(response.status_code, 200)

    def test_non_admin_can_create_deck(self):
        self._login_other()
        response = self.client.post(
            "/vocabulary/decks/create",
            data={"name": "My Regular Deck", "next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)

        with self.app.app_context():
            deck = Deck.query.filter_by(name="My Regular Deck").first()
            self.assertIsNotNone(deck)
            self.assertEqual(deck.owner_user_id, self.other_user_id)

    def test_non_admin_create_deck_under_installed_root_uses_selected_parent(self):
        with self.app.app_context():
            source_root = Deck(
                name="Shared Root",
                parent_id=None,
                owner_user_id=self.admin_id,
                position=1,
            )
            local_root = Deck(
                name="Shared Root",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=2,
            )
            db.session.add_all([source_root, local_root])
            db.session.flush()

            shared_item = DeckMarketplaceItem(
                owner_user_id=self.admin_id,
                title="Shared Root Deck",
                description="Shared root deck description",
                primary_category="General",
                tags=[],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(shared_item)
            db.session.flush()

            install_row = DeckInstall(
                deck_item_id=shared_item.id,
                user_id=self.other_user_id,
                local_deck_id=local_root.id,
            )
            db.session.add(install_row)
            db.session.commit()
            source_root_id = source_root.id
            local_root_id = local_root.id

        self._login_other()
        response = self.client.post(
            "/vocabulary/decks/create",
            data={
                "parent_id": str(local_root_id),
                "name": "Installed Child",
                "deck_path": "Shared Root::Installed Child",
                "next": "/dashboard",
            },
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)

        with self.app.app_context():
            created = (
                Deck.query.filter_by(name="Installed Child", owner_user_id=self.other_user_id)
                .order_by(Deck.id.desc())
                .first()
            )
            self.assertIsNotNone(created)
            self.assertEqual(created.parent_id, local_root_id)
            self.assertNotEqual(created.parent_id, source_root_id)

    def test_clone_owner_can_delete_cloned_deck_and_install_row(self):
        with self.app.app_context():
            cloned_root = Deck(
                name="Installed Root",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(cloned_root)
            db.session.flush()

            cloned_child = Deck(
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
                price_amount_minor=0,
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
            self.assertIsNone(Deck.query.get(cloned_root_id))
            self.assertIsNone(Deck.query.get(cloned_child_id))
            self.assertIsNone(DeckInstall.query.get(install_row_id))

    def test_deleting_shared_source_archives_it_without_breaking_installed_clone(self):
        with self.app.app_context():
            note_type = NoteType(user_id=self.admin_id, name="Protected Source Type")
            source_root = Deck(
                name="Protected Source",
                parent_id=None,
                owner_user_id=self.admin_id,
                position=1,
            )
            local_root = Deck(
                name="Installed Protected Source",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add_all([note_type, source_root, local_root])
            db.session.flush()
            template = Template(
                note_type_id=note_type.id,
                name="Protected Source Template",
                front_html="{{word}}",
                back_html="{{word}}",
                shared_css="",
                position=0,
                is_default=True,
            )
            db.session.add(template)
            db.session.flush()
            source_note = Note(
                note_type_id=note_type.id,
                user_id=self.admin_id,
                deck_id=source_root.id,
                field_values={"word": "維持"},
                tags=[],
            )
            shared_item = DeckMarketplaceItem(
                owner_user_id=self.admin_id,
                source_deck_id=source_root.id,
                source_note_type_id=note_type.id,
                title="Protected Source",
                description="Shared source deck",
                primary_category="Japanese",
                tags=["seeded"],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add_all([source_note, shared_item])
            db.session.flush()
            source_card = Card(note_id=source_note.id, template_id=template.id)
            db.session.add(source_card)
            db.session.flush()
            install = DeckInstall(
                deck_item_id=shared_item.id,
                user_id=self.other_user_id,
                local_deck_id=local_root.id,
                clone_mode="logical_overlay",
                source_deck_id=source_root.id,
                source_note_type_id=note_type.id,
                source_owner_user_id=self.admin_id,
            )
            db.session.add(install)
            db.session.flush()
            clone_map = DeckCloneDeckMap(
                deck_install_id=install.id,
                local_deck_id=local_root.id,
                source_deck_id=source_root.id,
            )
            db.session.add(clone_map)
            db.session.commit()
            source_root_id = source_root.id
            local_root_id = local_root.id
            source_note_id = source_note.id
            source_card_id = source_card.id
            shared_item_id = shared_item.id
            install_id = install.id
            clone_map_id = clone_map.id

        self._login_admin()
        response = self.client.post(
            f"/vocabulary/decks/{source_root_id}/delete",
            data={"next": "/dashboard"},
            follow_redirects=True,
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            source_root = db.session.get(Deck, source_root_id)
            shared_item = db.session.get(DeckMarketplaceItem, shared_item_id)
            self.assertIsNotNone(source_root)
            self.assertIsNotNone(source_root.deleted_at)  # type: ignore[union-attr]
            self.assertIsNotNone(db.session.get(Note, source_note_id))
            self.assertIsNotNone(db.session.get(Card, source_card_id))
            self.assertEqual(shared_item.publish_status, "archived")  # type: ignore[union-attr]
            self.assertIsNotNone(shared_item.archived_at)  # type: ignore[union-attr]
            self.assertIsNotNone(db.session.get(Deck, local_root_id))
            self.assertIsNotNone(db.session.get(DeckInstall, install_id))
            self.assertIsNotNone(db.session.get(DeckCloneDeckMap, clone_map_id))

        dashboard_response = self.client.get("/dashboard")
        self.assertNotIn('data-node-name="Protected Source"', dashboard_response.get_data(as_text=True))
        author_detail = self.client.get(f"/api/shared/decks/{shared_item_id}")
        self.assertEqual(author_detail.status_code, 200)
        self.assertEqual(author_detail.get_json().get("publish_status"), "archived")
        market_response = self.client.get("/api/shared/decks")
        market_item_ids = {
            item.get("id") for item in (market_response.get_json() or {}).get("items", [])
        }
        self.assertIn(shared_item_id, market_item_ids)

        self.client.post("/logout")
        self._login_other()
        installed_detail = self.client.get(f"/api/shared/decks/{shared_item_id}")
        self.assertEqual(installed_detail.status_code, 200)
        installed_cards = self.client.get(
            f"/vocabulary/api/browse/cards?deck_id={local_root_id}&include_subdecks=1"
        )
        installed_cards_payload = installed_cards.get_json() or {}
        self.assertEqual(installed_cards.status_code, 200)
        self.assertEqual(installed_cards_payload.get("total"), 1)
        self.assertIn("維持", (installed_cards_payload.get("items") or [{}])[0].get("word", ""))

    def test_non_admin_can_delete_owned_deck_without_clone_install(self):
        with self.app.app_context():
            owned_deck = Deck(
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
            self.assertIsNone(Deck.query.get(owned_deck_id))

    def test_clone_owner_can_delete_subdeck_with_install_on_ancestor(self):
        with self.app.app_context():
            cloned_root = Deck(
                name="Installed Root",
                parent_id=None,
                owner_user_id=self.other_user_id,
                position=1,
            )
            db.session.add(cloned_root)
            db.session.flush()

            cloned_child = Deck(
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
                price_amount_minor=0,
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
            self.assertIsNotNone(Deck.query.get(cloned_root_id))
            self.assertIsNone(Deck.query.get(cloned_child_id))
            self.assertIsNotNone(DeckInstall.query.get(install_row_id))


if __name__ == "__main__":
    unittest.main()
