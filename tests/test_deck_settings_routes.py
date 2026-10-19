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
from tests.study_note_fixtures import create_note_user, attach_template, assert_retired_progress_absent
from tests.note_progress_fixtures import stage_note_state, subject_for_card, decode_note_state
from models.study_progress_subject import StudyProgressSubject
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_subject import StudyProgressSubject


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

            admin = create_note_user(db.session,
                username="admin",
                email="admin@example.com",
                is_admin=True,
                role_id=admin_role.id,
            )
            admin.set_password("password")
            other = create_note_user(db.session,
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
        response = self.client.patch(
            f"/api/decks/{deck_a_id}",
            json={"name": "Deck B"},
        )
        self.assertEqual(response.status_code, 409)

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
        response = self.client.patch(
            f"/api/decks/{moving_id}",
            json={"parent_id": target_parent_id},
        )
        self.assertEqual(response.status_code, 409)

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
        response = self.client.patch(
            f"/api/decks/{parent_id}",
            json={"parent_id": child_id},
        )
        self.assertEqual(response.status_code, 400)

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
        response = self.client.patch(
            f"/api/decks/{moving_id}",
            json={"parent_token": target_parent_token},
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            moved = Deck.query.get(moving_id)
            self.assertIsNotNone(moved)
            self.assertEqual(moved.parent_id, target_parent_id)

    def test_reset_deck_only_clears_current_user_progress(self):
        self.app.config["STUDY_PROGRESS_SHADOW_WRITE_ENABLED"] = True
        with self.app.app_context():
            deck = Deck(name="Deck Reset", parent_id=None, position=1)
            db.session.add(deck)
            db.session.flush()

            note_type = NoteType(user_id=self.admin_id, name="Deck Reset Note Type")
            db.session.add(note_type)
            db.session.flush()
            template = attach_template(db.session, owner_user_id=note_type.user_id,
                note_type_id=note_type.id,
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
            db.session.add_all([note_type, template, note])
            db.session.flush()
            card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()

            from tests.study_note_fixtures import archive_wire_alias
            from uuid import uuid4
            wire_id = str(uuid4())
            archive_wire_alias(db.session, card, wire_id)

            admin_progress = stage_note_state(db.session,
                user_id=self.admin_id,
                card_id=card.id,
                queue="learning",
                step_index=1,
            )
            other_progress = stage_note_state(db.session,
                user_id=self.other_user_id,
                card_id=card.id,
                queue="learning",
                step_index=1,
            )
            admin_session = StudySession(
                user_id=self.admin_id,
                scope_type="deck",
                scope_id=str(deck.id),
                local_deck_id=deck.id,
                snapshot_hash="admin-reset-snapshot",
                token_hash="a" * 64,
                config_snapshot_json="{}",
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            other_session = StudySession(
                user_id=self.other_user_id,
                scope_type="deck",
                scope_id=str(deck.id),
                local_deck_id=deck.id,
                snapshot_hash="other-reset-snapshot",
                token_hash="b" * 64,
                config_snapshot_json="{}",
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            db.session.add_all(
                [admin_progress, other_progress, admin_session, other_session]
            )
            db.session.flush()
            db.session.add_all(
                [
                    StudySessionCard(
                        session_id=admin_session.id,
                        card_id=wire_id,
                        local_deck_id=deck.id,
                        base_progress_revision=0,
                        base_state_hash="admin-state",
                        scheduler_config_hash="admin-config",
                        initial_state_json="{}",
                        ordinal=0,
                    ),
                    StudySessionCard(
                        session_id=other_session.id,
                        card_id=wire_id,
                        local_deck_id=deck.id,
                        base_progress_revision=0,
                        base_state_hash="other-state",
                        scheduler_config_hash="other-config",
                        initial_state_json="{}",
                        ordinal=0,
                    ),
                ]
            )
            db.session.commit()
            deck_id = deck.id
            card_id = card.id
            admin_session_id = admin_session.id
            other_session_id = other_session.id

        self._login_admin()
        response = self.client.post(
            f"/api/decks/{deck_id}/progress-reset",
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            admin_progress_count = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id, live_note_id=db.session.get(Card, card_id).note_id).filter(StudyProgressSubject.state_payload.isnot(None)).count()
            other_progress_count = StudyProgressSubject.query.filter_by(learner_user_id=self.other_user_id, live_note_id=db.session.get(Card, card_id).note_id).filter(StudyProgressSubject.state_payload.isnot(None)).count()
            self.assertEqual(admin_progress_count, 1)
            self.assertEqual(decode_note_state(subject_for_card(db.session, user_id=self.admin_id,
                                                              card_id=card_id)).type, "new")
            self.assertEqual(other_progress_count, 1)
            self.assertEqual(
                db.session.get(StudySession, admin_session_id).status,
                "cancelled",
            )
            self.assertEqual(
                db.session.get(StudySession, other_session_id).status,
                "open",
            )
            self.assertEqual(StudyProgressSubject.query.count(), 2)
            self.assertGreater(StudyProgressLifecycleEvent.query.count(), 0)

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
            db.session.add(note_type)
            db.session.flush()
            template = attach_template(db.session, owner_user_id=note_type.user_id,
                note_type_id=note_type.id,
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
            db.session.add_all([note_type, template, note])
            db.session.flush()
            card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()

            owner_progress = stage_note_state(db.session,
                user_id=self.other_user_id,
                card_id=card.id,
                queue="review",
                reps=3,
            )
            admin_progress = stage_note_state(db.session,
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
            f"/api/decks/{owned_deck_id}/progress-reset",
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            owner_progress_count = StudyProgressSubject.query.filter_by(learner_user_id=self.other_user_id, live_note_id=db.session.get(Card, card_id).note_id).filter(StudyProgressSubject.state_payload.isnot(None)).count()
            admin_progress_count = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id, live_note_id=db.session.get(Card, card_id).note_id).filter(StudyProgressSubject.state_payload.isnot(None)).count()
            self.assertEqual(owner_progress_count, 1)
            self.assertEqual(decode_note_state(subject_for_card(db.session, user_id=self.other_user_id,
                                                              card_id=card_id)).type, "new")
            self.assertEqual(admin_progress_count, 1)

    def test_clone_owner_can_reset_progress_for_overlay_source_cards(self):
        with self.app.app_context():
            source_root = Deck(name="Source Root", parent_id=None, owner_user_id=self.admin_id, position=1)
            cloned_root = Deck(name="Installed Root", parent_id=None, owner_user_id=self.other_user_id, position=2)
            db.session.add_all([source_root, cloned_root])
            db.session.flush()

            note_type = NoteType(user_id=self.admin_id, name="Clone Reset Note Type")
            db.session.add(note_type)
            db.session.flush()
            template = attach_template(db.session, owner_user_id=note_type.user_id,
                note_type_id=note_type.id,
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
            db.session.add_all([note_type, template, source_note])
            db.session.flush()
            source_card = Card.query.filter_by(note_id=source_note.id, template_id=template.id).one()

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

            owner_progress = stage_note_state(db.session,
                user_id=self.other_user_id,
                card_id=source_card.id,
                queue="review",
                reps=5,
            )
            admin_progress = stage_note_state(db.session,
                user_id=self.admin_id,
                card_id=source_card.id,
                queue="review",
                reps=7,
            )
            overlay_session = StudySession(
                user_id=self.other_user_id,
                scope_type="deck",
                scope_id=str(cloned_root.id),
                local_deck_id=cloned_root.id,
                clone_install_id=install_row.id,
                snapshot_hash="overlay-reset-snapshot",
                token_hash="c" * 64,
                config_snapshot_json="{}",
                expires_at=datetime.utcnow() + timedelta(hours=1),
            )
            db.session.add_all([owner_progress, admin_progress, overlay_session])
            db.session.flush()
            db.session.add(
                StudySessionCard(
                    session_id=overlay_session.id,
                    card_id=source_card.id,
                    source_deck_id=source_root.id,
                    local_deck_id=cloned_root.id,
                    note_type_id=note_type.id,
                    base_progress_revision=0,
                    base_state_hash="overlay-state",
                    scheduler_config_hash="overlay-config",
                    initial_state_json="{}",
                    ordinal=0,
                )
            )
            db.session.commit()
            cloned_root_id = cloned_root.id
            source_card_id = source_card.id
            overlay_session_id = overlay_session.id

        self._login_other()
        response = self.client.post(
            f"/api/decks/{cloned_root_id}/progress-reset",
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            owner_progress_count = StudyProgressSubject.query.filter_by(learner_user_id=self.other_user_id, live_note_id=db.session.get(Card, source_card_id).note_id).filter(StudyProgressSubject.state_payload.isnot(None)).count()
            admin_progress_count = StudyProgressSubject.query.filter_by(learner_user_id=self.admin_id, live_note_id=db.session.get(Card, source_card_id).note_id).filter(StudyProgressSubject.state_payload.isnot(None)).count()
            self.assertEqual(owner_progress_count, 1)
            self.assertEqual(decode_note_state(subject_for_card(db.session, user_id=self.other_user_id,
                                                              card_id=source_card_id)).type, "new")
            self.assertEqual(admin_progress_count, 1)
            self.assertEqual(
                db.session.get(StudySession, overlay_session_id).status,
                "cancelled",
            )

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
            "/api/decks",
            json={"name": "My Regular Deck"},
        )
        self.assertEqual(response.status_code, 201)

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
            "/api/decks",
            json={
                "parent_id": local_root_id,
                "name": "Installed Child",
            },
        )
        self.assertEqual(response.status_code, 201)

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
        response = self.client.delete(
            f"/api/decks/{cloned_root_id}",
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNone(Deck.query.get(cloned_root_id))
            self.assertIsNone(Deck.query.get(cloned_child_id))
            self.assertIsNone(DeckInstall.query.get(install_row_id))

    def test_deleting_shared_source_archives_it_without_breaking_installed_clone(self):
        with self.app.app_context():
            note_type = NoteType(user_id=self.admin_id, name="Protected Source Type")
            db.session.add(note_type)
            db.session.flush()
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
            template = attach_template(db.session, owner_user_id=db.session.get(NoteType, note_type.id).user_id,
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
            source_card = Card.query.filter_by(note_id=source_note.id, template_id=template.id).one()
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
        response = self.client.delete(
            f"/api/decks/{source_root_id}",
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
            f"/api/browse/cards?deck_id={local_root_id}&include_subdecks=1"
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
        response = self.client.delete(
            f"/api/decks/{owned_deck_id}",
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
        response = self.client.delete(
            f"/api/decks/{cloned_child_id}",
        )
        self.assertEqual(response.status_code, 200)

        with self.app.app_context():
            self.assertIsNotNone(Deck.query.get(cloned_root_id))
            self.assertIsNone(Deck.query.get(cloned_child_id))
            self.assertIsNotNone(DeckInstall.query.get(install_row_id))


if __name__ == "__main__":
    unittest.main()
