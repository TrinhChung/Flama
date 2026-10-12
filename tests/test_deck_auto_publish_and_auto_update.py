"""Tests for Shared Deck Auto-Publish, Subscriber Auto-Update, and Conflict Resolution."""

import unittest
from datetime import datetime, timezone

from app import create_app
from app.services import (
    deck_auto_publish_service,
    deck_install_rebase_service,
    deck_release_service,
    deck_working_tree_service,
)
from models import db
from models.card import Card
from tests.study_note_fixtures import create_note_user, attach_template, assert_retired_progress_absent
from tests.note_progress_fixtures import stage_note_state, subject_for_card, decode_note_state
from models.study_progress_subject import StudyProgressSubject
from models.deck import Deck
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


class DeckAutoPublishAndAutoUpdateTests(unittest.TestCase):
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
        self.client = self.app.test_client()
        db.create_all()
        self.ids = self._seed_fixture()

    def tearDown(self):
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _login(self, email: str = "creator@example.com"):
        self.client.delete("/api/session")
        res = self.client.post(
            "/api/auth/login",
            json={"email": email, "password": "password"},
        )
        self.assertEqual(res.status_code, 200)

    def _seed_fixture(self):
        creator = create_note_user(db.session, username="creator", email="creator@example.com")
        creator.set_password("password")
        subscriber1 = create_note_user(db.session, username="sub1", email="sub1@example.com")
        subscriber1.set_password("password")
        subscriber2 = create_note_user(db.session, username="sub2", email="sub2@example.com")
        subscriber2.set_password("password")
        db.session.add_all([creator, subscriber1, subscriber2])
        db.session.flush()

        note_type = NoteType(user_id=creator.id, name="Vocabulary")
        db.session.add(note_type)
        db.session.flush()
        db.session.add(note_type)
        db.session.flush()

        front_field = FieldDef(
            note_type_id=note_type.id,
            name="Front",
            field_type="text",
            position=0,
            required=True,
        )
        back_field = FieldDef(
            note_type_id=note_type.id,
            name="Back",
            field_type="text",
            position=1,
            required=True,
        )
        db.session.add_all([front_field, back_field])
        db.session.flush()

        template = attach_template(db.session, owner_user_id=db.session.get(NoteType, note_type.id).user_id,
            note_type_id=note_type.id,
            name="Card 1",
            front_html="{{Front}}",
            back_html="{{FrontSide}}<hr>{{Back}}",
            position=0,
        )
        db.session.add(template)
        db.session.flush()

        source_deck = Deck(
            owner_user_id=creator.id,
            note_type_id=note_type.id,
            name="Source JLPT N5",
        )
        db.session.add(source_deck)
        db.session.flush()

        note = Note(
            user_id=creator.id,
            deck_id=source_deck.id,
            note_type_id=note_type.id,
            field_values={"Front": "猫", "Back": "Cat / Mèo"},
            tags=[],
        )
        db.session.add(note)
        db.session.flush()

        card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()

        item = DeckMarketplaceItem(
            owner_user_id=creator.id,
            source_deck_id=source_deck.id,
            source_note_type_id=note_type.id,
            title="JLPT N5 Core",
            description="Official N5 deck",
            version="1.0.0",
            publish_status="published",
            working_revision=1,
            auto_publish_enabled=False,
        )
        db.session.add(item)
        db.session.flush()

        # Publish initial release 1.0.0
        rel1 = deck_release_service.publish_release(
            deck_item_id=item.id,
            user_id=creator.id,
            version_label="1.0.0",
            changelog="Initial release",
            expected_current_release_id=None,
            expected_working_revision=1,
            idempotency_key="seed-rel-1",
        ).release

        # Install for subscriber1 (auto_update_enabled=True)
        sub1_deck = Deck(
            owner_user_id=subscriber1.id,
            note_type_id=note_type.id,
            name="Sub1 JLPT N5",
        )
        db.session.add(sub1_deck)
        db.session.flush()

        install1 = DeckInstall(
            deck_item_id=item.id,
            user_id=subscriber1.id,
            local_deck_id=sub1_deck.id,
            source_deck_id=source_deck.id,
            source_note_type_id=note_type.id,
            source_owner_user_id=creator.id,
            clone_mode="logical_overlay",
            applied_release_id=rel1.id,
            seen_release_id=rel1.id,
            version_mode="release",
            auto_update_enabled=True,
            sync_mode="automatic",
            overlay_revision=0,
        )
        db.session.add(install1)
        db.session.flush()

        sub1_progress = stage_note_state(db.session,
            user_id=subscriber1.id,
            card_id=card.id,
            queue="review",
            interval_days=14,
            ease_factor=2.5,
        )
        db.session.add(sub1_progress)
        db.session.flush()

        # Install for subscriber2 (auto_update_enabled=False, manual mode)
        sub2_deck = Deck(
            owner_user_id=subscriber2.id,
            note_type_id=note_type.id,
            name="Sub2 JLPT N5",
        )
        db.session.add(sub2_deck)
        db.session.flush()

        install2 = DeckInstall(
            deck_item_id=item.id,
            user_id=subscriber2.id,
            local_deck_id=sub2_deck.id,
            source_deck_id=source_deck.id,
            source_note_type_id=note_type.id,
            source_owner_user_id=creator.id,
            clone_mode="logical_overlay",
            applied_release_id=rel1.id,
            seen_release_id=rel1.id,
            version_mode="release",
            auto_update_enabled=False,
            sync_mode="manual",
            overlay_revision=0,
        )
        db.session.add(install2)
        db.session.commit()

        return {
            "creator_id": creator.id,
            "subscriber1_id": subscriber1.id,
            "subscriber2_id": subscriber2.id,
            "item_id": item.id,
            "source_deck_id": source_deck.id,
            "note_id": note.id,
            "card_id": card.id,
            "back_field_id": back_field.id,
            "install1_id": install1.id,
            "install2_id": install2.id,
            "rel1_id": rel1.id,
        }

    def test_auto_version_helper(self):
        self.assertEqual(deck_auto_publish_service.next_auto_version("1.0.0"), "1.0.1")
        self.assertEqual(deck_auto_publish_service.next_auto_version("1.2.9"), "1.2.10")
        self.assertEqual(deck_auto_publish_service.next_auto_version("v1"), "v2")
        self.assertEqual(deck_auto_publish_service.next_auto_version(""), "1.0.0")

    def test_creator_auto_publish_setting_toggle(self):
        status = deck_auto_publish_service.get_auto_publish_status(
            deck_item_id=self.ids["item_id"],
            user_id=self.ids["creator_id"],
        )
        self.assertFalse(status["auto_publish_enabled"])

        updated = deck_auto_publish_service.update_auto_publish_setting(
            deck_item_id=self.ids["item_id"],
            user_id=self.ids["creator_id"],
            auto_publish_enabled=True,
        )
        self.assertTrue(updated["auto_publish_enabled"])

        item = DeckMarketplaceItem.query.get(self.ids["item_id"])
        self.assertTrue(item.auto_publish_enabled)

    def test_creator_auto_publish_and_subscriber_auto_update_clean_merge(self):
        # 1. Enable auto-publish on deck item
        deck_auto_publish_service.update_auto_publish_setting(
            deck_item_id=self.ids["item_id"],
            user_id=self.ids["creator_id"],
            auto_publish_enabled=True,
        )

        # 2. Modify note in source deck
        note = Note.query.get(self.ids["note_id"])
        note.field_values = {"Front": "猫", "Back": "Cat / Con mèo (Updated)"}
        db.session.flush()

        # 3. Mark change in working tree
        deck_working_tree_service.mark_note_fields_changed(
            note=note,
            field_names=["Back"],
            operation="set",
        )
        db.session.commit()

        # 4. Verify new release was auto-published with version 1.0.1
        item = DeckMarketplaceItem.query.get(self.ids["item_id"])
        rel2 = item.current_release
        self.assertIsNotNone(rel2)
        self.assertEqual(rel2.version_label, "1.0.1")
        self.assertEqual(rel2.publish_mode, "automatic")
        self.assertIsNotNone(item.last_auto_published_at)

        # 5. Verify Subscriber 1 (auto_update_enabled=True) was automatically updated!
        install1 = DeckInstall.query.get(self.ids["install1_id"])
        self.assertEqual(install1.applied_release_id, rel2.id)
        self.assertEqual(install1.last_sync_status, "synced")
        self.assertEqual(install1.pending_conflict_count, 0)
        self.assertIsNotNone(install1.last_auto_updated_at)

        # 6. Verify Subscriber 1 Card learning progress is 100% PRESERVED
        progress1 = decode_note_state(subject_for_card(db.session, user_id=self.ids["subscriber1_id"], card_id=self.ids["card_id"]))
        self.assertIsNotNone(progress1)
        self.assertEqual(progress1.intervalDays, 14)
        self.assertEqual(progress1.ease, 2.5)
        self.assertEqual(progress1.type, "review")

        # 7. Verify Subscriber 2 (auto_update_enabled=False) remained on release 1.0.0
        install2 = DeckInstall.query.get(self.ids["install2_id"])
        self.assertEqual(install2.applied_release_id, self.ids["rel1_id"])

    def test_subscriber_auto_update_safe_conflict_detection(self):
        # 1. Subscriber 1 creates local override on "Back" field
        override = DeckCloneNoteFieldOverride(
            deck_install_id=self.ids["install1_id"],
            source_note_id=self.ids["note_id"],
            source_field_def_id=self.ids["back_field_id"],
            field_name="Back",
            operation="set",
            value="Con mèo của riêng tôi",
        )
        db.session.add(override)
        install1 = DeckInstall.query.get(self.ids["install1_id"])
        install1.overlay_revision = 1
        db.session.commit()

        # 2. Creator enables auto-publish and modifies "Back" field
        deck_auto_publish_service.update_auto_publish_setting(
            deck_item_id=self.ids["item_id"],
            user_id=self.ids["creator_id"],
            auto_publish_enabled=True,
        )

        note = Note.query.get(self.ids["note_id"])
        note.field_values = {"Front": "猫", "Back": "Cat / Mèo upstream edit"}
        db.session.flush()

        deck_working_tree_service.mark_note_fields_changed(
            note=note,
            field_names=["Back"],
            operation="set",
        )
        db.session.commit()

        # 3. Verify that because of conflict on "Back", Subscriber 1 is NOT silently overwritten!
        install1 = DeckInstall.query.get(self.ids["install1_id"])
        self.assertEqual(install1.last_sync_status, "conflict")
        self.assertEqual(install1.pending_conflict_count, 1)
        # Still on previous release until user resolves
        self.assertEqual(install1.applied_release_id, self.ids["rel1_id"])

        # Local override still intact
        override_db = DeckCloneNoteFieldOverride.query.filter_by(
            deck_install_id=self.ids["install1_id"],
            source_note_id=self.ids["note_id"],
            field_name="Back",
        ).first()
        self.assertEqual(override_db.value, "Con mèo của riêng tôi")

    def test_batch_conflict_resolution_and_apply(self):
        # Setup conflicting rebase preparation
        override = DeckCloneNoteFieldOverride(
            deck_install_id=self.ids["install1_id"],
            source_note_id=self.ids["note_id"],
            source_field_def_id=self.ids["back_field_id"],
            field_name="Back",
            operation="set",
            value="Local edit",
        )
        db.session.add(override)
        install1 = DeckInstall.query.get(self.ids["install1_id"])
        install1.overlay_revision = 1
        db.session.flush()

        # Creator publishes 1.0.1
        note = Note.query.get(self.ids["note_id"])
        note.field_values = {"Front": "猫", "Back": "Upstream edit"}
        db.session.flush()
        deck_working_tree_service.mark_note_fields_changed(
            note=note,
            field_names=["Back"],
            operation="set",
        )
        item = DeckMarketplaceItem.query.get(self.ids["item_id"])
        rel2 = deck_release_service.publish_release(
            deck_item_id=item.id,
            user_id=self.ids["creator_id"],
            version_label="1.0.1",
            changelog="Update",
            expected_current_release_id=self.ids["rel1_id"],
            expected_working_revision=item.working_revision,
            idempotency_key="batch-test-rel2",
        ).release
        db.session.commit()

        # Prepare update
        rebase = deck_install_rebase_service.prepare_update(
            install_id=self.ids["install1_id"],
            release_id=rel2.id,
            user_id=self.ids["subscriber1_id"],
        )
        self.assertEqual(rebase.status, "has_conflict")
        self.assertEqual(rebase.conflict_count, 1)

        # Batch resolve using "keep_upstream"
        resolved_rebase = deck_install_rebase_service.resolve_all_conflicts(
            rebase_id=rebase.id,
            user_id=self.ids["subscriber1_id"],
            resolution_mode="keep_upstream",
        )
        self.assertEqual(resolved_rebase.status, "ready")
        self.assertEqual(resolved_rebase.resolved_conflict_count, 1)

        # Apply update
        applied_rebase = deck_install_rebase_service.apply_prepared_update(
            rebase_id=rebase.id,
            user_id=self.ids["subscriber1_id"],
        )
        self.assertEqual(applied_rebase.status, "applied")

        install1 = DeckInstall.query.get(self.ids["install1_id"])
        self.assertEqual(install1.applied_release_id, rel2.id)

    def test_detach_installed_deck(self):
        res = deck_install_rebase_service.detach_installed_deck(
            install_id=self.ids["install1_id"],
            user_id=self.ids["subscriber1_id"],
        )
        self.assertEqual(res["version_mode"], "detached")

        install1 = DeckInstall.query.get(self.ids["install1_id"])
        self.assertEqual(install1.version_mode, "detached")
        self.assertFalse(install1.auto_update_enabled)
        self.assertEqual(install1.sync_mode, "detached")

    def test_rest_api_auto_publish_and_subscriber_settings(self):
        # 1. Creator GET and POST auto-publish
        self._login("creator@example.com")
        get_res = self.client.get(f"/api/marketplace/decks/{self.ids['item_id']}/auto-publish")
        self.assertEqual(get_res.status_code, 200)
        self.assertFalse(get_res.get_json()["auto_publish_enabled"])

        post_res = self.client.post(
            f"/api/marketplace/decks/{self.ids['item_id']}/auto-publish",
            json={"auto_publish_enabled": True},
        )
        self.assertEqual(post_res.status_code, 200)
        self.assertTrue(post_res.get_json()["auto_publish_enabled"])

        # 2. Subscriber GET and POST settings
        self._login("sub1@example.com")
        settings_get = self.client.get(f"/api/marketplace/installations/{self.ids['install1_id']}/settings")
        self.assertEqual(settings_get.status_code, 200)
        self.assertTrue(settings_get.get_json()["auto_update_enabled"])

        settings_post = self.client.post(
            f"/api/marketplace/installations/{self.ids['install1_id']}/settings",
            json={"auto_update_enabled": False},
        )
        self.assertEqual(settings_post.status_code, 200)
        self.assertFalse(settings_post.get_json()["auto_update_enabled"])

        # 3. Subscriber Detach
        detach_res = self.client.post(f"/api/marketplace/installations/{self.ids['install1_id']}/detach")
        self.assertEqual(detach_res.status_code, 200)
        self.assertEqual(detach_res.get_json()["version_mode"], "detached")
