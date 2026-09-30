"""Integration tests for flashcard API CRUD, preview, and study."""

import io
import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch
from pathlib import Path

from app import create_app
from app.services import flashcards_share as share_ctrl
from app.services import flashcards_share_service
from app.services.share import cutover as cutover_service
from app.services.share.helpers import ShareControllerError
from app.services.anki_scheduler import _day_index, _day_index_to_datetime, default_deck_options
from app.services.study_progress_backfill_service import run_current_progress_backfill
from app.services.study_progress_reconciliation_service import (
    build_study_progress_reconciliation,
)
from models import db
from models.flashcard import (
    Card,
    DeckCloneAddedFieldDef,
    DeckCloneDeckMap,
    DeckCloneFieldDefOverride,
    DeckCloneFieldOrderOverride,
    DeckCloneNoteFieldOverride,
    DeckInstall,
    DeckMarketplaceItem,
    DeckReview,
    Note,
    NoteType,
    NoteTypeInstall,
    NoteTypeReview,
)
from models.user import User
from models.deck import Deck
from models.deck_release import DeckRelease
from models.field_def import FieldDef
from models.template import Template
from models.card_progress import CardProgress
from models.study_progress_contributor import StudyProgressContributor
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_subject import StudyProgressSubject
from sqlalchemy import event
from sqlalchemy.exc import OperationalError

_MIN_WAV_BYTES = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


class FlashcardApiIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    def setUp(self):
        self.app.config["STUDY_PROGRESS_SHADOW_WRITE_ENABLED"] = False
        self.app.config["STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED"] = False
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Deck A", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _create_note_type(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Japanese Vocabulary",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Reading", "field_type": "text", "position": 1, "required": False},
                    {"name": "Meaning", "field_type": "richtext", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}} - {{Reading}} {{{Meaning}}}</div>",
                    "shared_css": ".card{color:red;}",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()

    def _collect_subtree_ids(self, root_deck_id: int) -> list[int]:
        seen: set[int] = set()
        frontier: set[int] = {int(root_deck_id)}
        while frontier:
            current = {deck_id for deck_id in frontier if deck_id not in seen}
            if not current:
                break
            seen.update(current)
            child_rows = (
                db.session.query(Deck.id)
                .filter(Deck.parent_id.in_(current))
                .all()
            )
            frontier = {int(row[0]) for row in child_rows if row and row[0] is not None}
        return sorted(seen)

    def _create_installed_clone_decks(self) -> tuple[int, int]:
        with self.app.app_context():
            source_owner = User(
                username="market-source-owner",
                email="market-source-owner@example.com",
            )
            source_owner.set_password("password")
            db.session.add(source_owner)
            db.session.flush()

            source_root = Deck(
                name="Marketplace Source",
                owner_user_id=source_owner.id,
            )
            db.session.add(source_root)
            db.session.flush()
            source_child = Deck(
                name="Marketplace Source Child",
                owner_user_id=source_owner.id,
                parent_id=source_root.id,
            )
            local_root = Deck(
                name="Installed Marketplace Deck",
                owner_user_id=self.user_id,
            )
            db.session.add_all([source_child, local_root])
            db.session.flush()
            local_child = Deck(
                name="Installed Marketplace Child",
                owner_user_id=self.user_id,
                parent_id=local_root.id,
            )
            deck_item = DeckMarketplaceItem(
                owner_user_id=source_owner.id,
                source_deck_id=source_root.id,
                title="Marketplace Source Listing",
                publish_status="published",
            )
            db.session.add_all([local_child, deck_item])
            db.session.flush()
            install = DeckInstall(
                deck_item_id=deck_item.id,
                user_id=self.user_id,
                local_deck_id=local_root.id,
                clone_mode="logical_overlay",
                source_deck_id=source_root.id,
                source_owner_user_id=source_owner.id,
                base_snapshot_at=datetime.utcnow(),
            )
            db.session.add(install)
            db.session.flush()
            db.session.add_all(
                [
                    DeckCloneDeckMap(
                        deck_install_id=install.id,
                        local_deck_id=local_root.id,
                        source_deck_id=source_root.id,
                    ),
                    DeckCloneDeckMap(
                        deck_install_id=install.id,
                        local_deck_id=local_child.id,
                        source_deck_id=source_child.id,
                    ),
                ]
            )
            db.session.commit()
            return local_root.id, local_child.id

    def test_crud_preview_flow(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "<b>dog</b>",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        preview_resp = self.client.post(
            f"/api/note-types/{note_type_id}/templates/{template_id}/preview",
            json={"note_id": note_id},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.get_json()
        self.assertIn("\u72ac", preview["front_html"])
        self.assertIn("\u3044\u306c", preview["back_html"])
        self.assertIn("<b>dog</b>", preview["back_html"])
        self.assertEqual(preview["front_renderer_payload"]["html"], preview["front_html"])
        self.assertEqual(preview["back_renderer_payload"]["html"], preview["back_html"])

    def test_released_shared_note_type_rejects_all_template_mutations(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]
        note_response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "dog",
                    "Reading": "inu",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(note_response.status_code, 201, note_response.get_json())

        with self.app.app_context():
            learner = User(
                username="template-guard-learner",
                email="template-guard-learner@example.com",
            )
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            local_deck = Deck(
                name="Template guard install",
                owner_user_id=learner.id,
                note_type_id=note_type_id,
            )
            db.session.add(local_deck)
            db.session.flush()
            item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Template guard source",
                publish_status="published",
            )
            db.session.add(item)
            db.session.flush()
            release = DeckRelease(
                deck_item_id=item.id,
                sequence_no=1,
                version_label="1.0.0",
                status="published",
                created_by_user_id=self.user_id,
            )
            db.session.add(release)
            db.session.flush()
            item.current_release_id = release.id
            db.session.add(
                DeckInstall(
                    deck_item_id=item.id,
                    user_id=learner.id,
                    local_deck_id=local_deck.id,
                    source_deck_id=self.deck_id,
                    source_note_type_id=note_type_id,
                    source_owner_user_id=self.user_id,
                    applied_release_id=release.id,
                    seen_release_id=release.id,
                    version_mode="release",
                    clone_mode="logical_overlay",
                )
            )
            db.session.commit()
            template = db.session.get(Template, template_id)
            template_snapshot = (
                template.name,
                template.front_html,
                template.back_html,
                template.shared_css,
                bool(template.is_default),
            )
            card_snapshot = [
                (str(card.id), str(card.template_id))
                for card in Card.query.order_by(Card.id.asc()).all()
            ]
            template_count = Template.query.filter_by(
                note_type_id=note_type_id
            ).count()

        blocked_requests = [
            self.client.post(
                f"/api/note-types/{note_type_id}/templates",
                json={
                    "name": "Blocked template",
                    "front_html": "{{Word}}",
                    "back_html": "{{Meaning}}",
                },
            ),
            self.client.patch(
                f"/api/note-types/{note_type_id}/templates/{template_id}",
                json={"position": 2},
            ),
            self.client.post(
                f"/api/note-types/{note_type_id}/templates/{template_id}/reset"
            ),
            self.client.delete(
                f"/api/note-types/{note_type_id}/templates/{template_id}"
            ),
        ]
        for response in blocked_requests:
            with self.subTest(payload=response.get_json()):
                self.assertEqual(response.status_code, 409, response.get_json())
                self.assertEqual(
                    response.get_json()["error"],
                    "SHARED_SCHEMA_VERSIONING_REQUIRED",
                )
                self.assertEqual(response.get_json()["field"], "template")

        with self.app.app_context():
            db.session.expire_all()
            template = db.session.get(Template, template_id)
            self.assertIsNotNone(template)
            self.assertEqual(
                (
                    template.name,
                    template.front_html,
                    template.back_html,
                    template.shared_css,
                    bool(template.is_default),
                ),
                template_snapshot,
            )
            self.assertEqual(
                Template.query.filter_by(note_type_id=note_type_id).count(),
                template_count,
            )
            self.assertEqual(
                [
                    (str(card.id), str(card.template_id))
                    for card in Card.query.order_by(Card.id.asc()).all()
                ],
                card_snapshot,
            )

    def test_released_shared_note_type_allows_source_author_content_hotfix(self):
        # 1. Create a note type with fields and a template
        create_response = self.client.post(
            "/api/note-types",
            json={
                "name": "Hotfix Shared Note Type",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Meaning", "field_type": "richtext", "position": 1, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Meaning}}</div>",
                    "shared_css": ".card { font-size: 14px; }",
                },
            },
        )
        self.assertEqual(create_response.status_code, 201, create_response.get_json())
        note_type_id = create_response.get_json()["id"]
        template_id = create_response.get_json()["templates"][0]["id"]

        # 2. Add a note to create physical Card row
        note_response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "りんご", "Meaning": "apple"},
            },
        )
        self.assertEqual(note_response.status_code, 201, note_response.get_json())
        note_id = note_response.get_json()["id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id, template_id=template_id).first()
            self.assertIsNotNone(card)
            card_id = str(card.id)

            learner = User(
                username="hotfix-learner",
                email="hotfix-learner@example.com",
            )
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()

            local_deck = Deck(
                name="Learner Deck",
                owner_user_id=learner.id,
                note_type_id=note_type_id,
            )
            db.session.add(local_deck)
            db.session.flush()

            item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck for Hotfix",
                publish_status="published",
            )
            db.session.add(item)
            db.session.flush()

            release = DeckRelease(
                deck_item_id=item.id,
                sequence_no=1,
                version_label="1.0.0",
                status="published",
                created_by_user_id=self.user_id,
            )
            db.session.add(release)
            db.session.flush()
            item.current_release_id = release.id

            install = DeckInstall(
                deck_item_id=item.id,
                user_id=learner.id,
                local_deck_id=local_deck.id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                source_owner_user_id=self.user_id,
                applied_release_id=release.id,
                seen_release_id=release.id,
                version_mode="release",
                clone_mode="logical_overlay",
            )
            db.session.add(install)
            db.session.flush()

            progress = CardProgress(
                user_id=learner.id,
                card_id=card_id,
                queue="review",
                step_index=2,
                reps=5,
                lapses=1,
            )
            db.session.add(progress)
            db.session.commit()
            progress_id = progress.id

        # 3. Non-owner / learner cannot hotfix or mutate source template
        self.client.post("/logout", follow_redirects=True)
        self.client.post(
            "/login",
            data={"email": "hotfix-learner@example.com", "password": "password"},
            follow_redirects=True,
        )
        unauthorized_patch = self.client.patch(
            f"/api/note-types/{note_type_id}/templates/{template_id}",
            json={
                "front_html": "<div>Hacked {{Word}}</div>",
            },
        )
        self.assertEqual(unauthorized_patch.status_code, 404)

        # 4. Author logs back in and executes content hotfix
        self.client.post("/logout", follow_redirects=True)
        self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )
        hotfix_response = self.client.patch(
            f"/api/note-types/{note_type_id}/templates/{template_id}",
            json={
                "name": "Card 1 (Hotfixed)",
                "front_html": "<div class=\"hotfix-front\">{{Word}}</div>",
                "back_html": "<div class=\"hotfix-back\">{{Meaning}}</div>",
                "shared_css": ".hotfix-front { color: #ff0000; font-weight: bold; }",
            },
        )
        self.assertEqual(hotfix_response.status_code, 200, hotfix_response.get_json())
        updated_data = hotfix_response.get_json()
        self.assertEqual(updated_data["id"], template_id)
        self.assertEqual(updated_data["name"], "Card 1 (Hotfixed)")
        self.assertEqual(updated_data["front_html"], '<div class="hotfix-front">{{Word}}</div>')
        self.assertEqual(updated_data["back_html"], '<div class="hotfix-back">{{Meaning}}</div>')
        self.assertEqual(updated_data["shared_css"], '.hotfix-front { color: #ff0000; font-weight: bold; }')

        # 5. Verify database invariants
        with self.app.app_context():
            db.session.expire_all()
            reloaded_template = db.session.get(Template, template_id)
            self.assertIsNotNone(reloaded_template)
            self.assertEqual(reloaded_template.id, template_id)
            self.assertEqual(reloaded_template.name, "Card 1 (Hotfixed)")
            self.assertEqual(reloaded_template.front_html, '<div class="hotfix-front">{{Word}}</div>')
            self.assertEqual(reloaded_template.back_html, '<div class="hotfix-back">{{Meaning}}</div>')
            self.assertEqual(reloaded_template.shared_css, '.hotfix-front { color: #ff0000; font-weight: bold; }')

            # Physical Card row is preserved with identical ID
            reloaded_card = db.session.get(Card, card_id)
            self.assertIsNotNone(reloaded_card)
            self.assertEqual(reloaded_card.template_id, template_id)
            self.assertEqual(Card.query.filter_by(note_id=note_id).count(), 1)

            # CardProgress is preserved and attached to same Card row
            reloaded_progress = db.session.get(CardProgress, progress_id)
            self.assertIsNotNone(reloaded_progress)
            self.assertEqual(reloaded_progress.card_id, card_id)
            self.assertEqual(reloaded_progress.reps, 5)
            self.assertEqual(reloaded_progress.queue, "review")

            # Verify study artifact / render resolves updated live template
            from app.services import study_artifact_service
            effective_card = study_artifact_service.build_effective_study_card(
                card=reloaded_card,
                clone_scope=None,
            )
            template_artifact = study_artifact_service.build_template_artifact(effective_card)
            self.assertIn('<div class="hotfix-front">', template_artifact["front_source"])
            self.assertIn('<div class="hotfix-back">', template_artifact["back_source"])
            self.assertIn('.hotfix-front { color: #ff0000', template_artifact["shared_css"])

        # 6. Verify unreleased / private note type retains normal CRUD behavior
        private_nt_res = self.client.post(
            "/api/note-types",
            json={
                "name": "Private Note Type",
                "field_defs": [
                    {"name": "Front", "field_type": "text", "position": 0, "required": True},
                ],
                "template": {
                    "name": "Private Card",
                    "front_html": "{{Front}}",
                    "back_html": "{{Front}}",
                },
            },
        )
        self.assertEqual(private_nt_res.status_code, 201)
        private_nt_id = private_nt_res.get_json()["id"]
        # Can create template on private note type
        new_tmpl_res = self.client.post(
            f"/api/note-types/{private_nt_id}/templates",
            json={
                "name": "Private Card 2",
                "front_html": "<b>{{Front}}</b>",
                "back_html": "<i>{{Front}}</i>",
            },
        )
        self.assertEqual(new_tmpl_res.status_code, 201)
        # Can delete template on private note type
        del_tmpl_res = self.client.delete(
            f"/api/note-types/{private_nt_id}/templates/{new_tmpl_res.get_json()['id']}"
        )
        self.assertEqual(del_tmpl_res.status_code, 200)

    def test_canonical_api_content_crud_and_media_contract(self):
        create_response = self.client.post(
            "/api/note-types",
            json={
                "name": "API Content",
                "field_defs": [
                    {
                        "name": "Word",
                        "field_type": "text",
                        "position": 0,
                        "required": True,
                    },
                    {
                        "name": "Audio",
                        "field_type": "audio",
                        "position": 1,
                        "required": False,
                    },
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "{{Word}}",
                    "back_html": "{{Word}} {{{Audio}}}",
                },
            },
        )
        self.assertEqual(create_response.status_code, 201)
        note_type_id = create_response.get_json()["id"]

        list_response = self.client.get("/api/note-types")
        self.assertEqual(list_response.status_code, 200)
        self.assertEqual(len(list_response.get_json()["items"]), 1)

        note_response = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {"Word": "犬", "Audio": ""},
            },
        )
        self.assertEqual(note_response.status_code, 201)
        note_id = note_response.get_json()["id"]

        upload_response = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Audio",
                "file": (io.BytesIO(_MIN_WAV_BYTES), "voice.wav"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_response.status_code, 201)
        asset_id = upload_response.get_json()["asset_id"]

        detail_response = self.client.get(f"/api/notes/{note_id}")
        self.assertEqual(detail_response.status_code, 200)
        self.assertEqual(
            detail_response.get_json()["field_values"]["Audio"],
            f"/media/proxy/{asset_id}",
        )
        self.assertEqual(
            self.client.get("/api/flashcards/import/options").status_code,
            200,
        )

    def test_preview_sample_mode_uses_field_name_dump_and_image_placeholder(self):
        response = self.client.post(
            "/api/note-types",
            json={
                "name": "Preview Sample",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Illustration", "field_type": "image", "position": 1, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>{{{Illustration}}}",
                    "back_html": "<div>{{Word}}</div>",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(response.status_code, 201)
        note_type = response.get_json()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]

        preview_resp = self.client.post(
            f"/api/note-types/{note_type_id}/templates/{template_id}/preview",
            json={"use_sample_data": True},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.get_json()
        self.assertIn("Word", preview["front_html"])
        self.assertIn("fc-preview-media-box", preview["front_html"])
        self.assertIn("[Image: Illustration]", preview["front_html"])
        self.assertEqual(preview["front_renderer_payload"]["html"], preview["front_html"])

    def test_preview_raw_template_endpoint(self):
        with self.client.session_transaction() as sess:
            sess["_user_id"] = str(self.user_id)
        res = self.client.post(
            "/api/note-types/preview",
            json={
                "front_html": "{{Front}}",
                "back_html": "{{Front}}<hr>{{Back}}",
                "shared_css": "card { color: red; }",
                "fields": ["Front", "Back"],
            },
        )
        self.assertEqual(res.status_code, 200)
        data = res.get_json()
        self.assertIn("front_html", data)
        self.assertIn("back_html", data)

    def test_shared_deck_preview_uses_first_note_from_source_deck(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        template_id = note_type["templates"][0]["id"]

        first_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(first_note_resp.status_code, 201)

        second_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(second_note_resp.status_code, 201)

        with self.app.app_context():
            # "First" is the earliest created_at, ties broken by random UUID;
            # two notes created in the same second would make this test flaky.
            first_note = db.session.get(Note, first_note_resp.get_json()["id"])
            second_note = db.session.get(Note, second_note_resp.get_json()["id"])
            second_note.created_at = first_note.created_at + timedelta(seconds=1)
            db.session.commit()
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck A",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.get_json()
        self.assertEqual(detail_payload["source_note_type_id"], note_type_id)
        self.assertIsNotNone(detail_payload.get("source_note_type"))
        self.assertTrue((detail_payload["source_note_type"].get("templates") or []))
        test_samples = detail_payload.get("test_samples") or []
        self.assertEqual(len(test_samples), 2)
        self.assertEqual(detail_payload.get("test_sample_limit"), 5)
        sampled_words = {sample.get("word") for sample in test_samples}
        self.assertIn("\u72ac", sampled_words)
        self.assertIn("\u732b", sampled_words)

        preview_resp = self.client.post(
            f"/api/shared/decks/{deck_item_id}/templates/{template_id}/preview",
            json={},
        )
        self.assertEqual(preview_resp.status_code, 200)
        preview = preview_resp.get_json()
        self.assertIn("\u72ac", preview["front_html"])
        self.assertIn("\u3044\u306c", preview["back_html"])
        self.assertNotIn("\u306d\u3053", preview["back_html"])

        selected_cat = next((row for row in test_samples if row.get("word") == "\u732b"), None)
        self.assertIsNotNone(selected_cat)
        self.assertIsNotNone(selected_cat.get("note_id"))
        selected_preview_resp = self.client.post(
            f"/api/shared/decks/{deck_item_id}/templates/{template_id}/preview",
            json={"note_id": selected_cat.get("note_id")},
        )
        self.assertEqual(selected_preview_resp.status_code, 200)
        selected_preview = selected_preview_resp.get_json()
        self.assertIn("\u732b", selected_preview["front_html"])
        self.assertIn("\u306d\u3053", selected_preview["back_html"])

    def test_share_deck_page_publishes_parent_deck_using_child_deck_note_type(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            child_deck = Deck(name="Deck Child", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)

        share_resp = self.client.post(
            f"/flashcards/decks/{self.deck_id}/share",
            data={
                "title": "Shared Parent Deck",
                "description": "Deck description",
                "preview_text": "Preview",
                "tags": "jlpt,n1",
                "pricing_mode": "free",
                "taxonomy_domain": "language_learning",
                "taxonomy_subject": "japanese",
                "taxonomy_difficulty_band": "advanced",
                "taxonomy_framework": "jlpt",
                "taxonomy_framework_level": "n1",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["reading_recall"],
                "format_features": ["preview_available"],
            },
            follow_redirects=False,
        )
        self.assertEqual(share_resp.status_code, 302)
        self.assertIn("/flashcards/shared-decks", share_resp.headers.get("Location", ""))

        with self.app.app_context():
            deck_item = DeckMarketplaceItem.query.filter_by(source_deck_id=self.deck_id).first()
            self.assertIsNotNone(deck_item)
            self.assertEqual(deck_item.source_note_type_id, note_type_id)
            self.assertEqual(deck_item.title, "Shared Parent Deck")
            self.assertEqual(deck_item.publish_status, "published")
            self.assertEqual((deck_item.taxonomy_metadata or {}).get("subject"), "japanese")
            self.assertEqual((deck_item.taxonomy_metadata or {}).get("framework_level"), "n1")

    def test_shared_decks_page_includes_share_edit_url_template(self):
        response = self.client.get("/flashcards/shared-decks")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)

    def test_shared_deck_detail_page_exposes_share_edit_action(self):
        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=None,
                title="Shared Deck Detail Edit",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        response = self.client.get(f"/flashcards/shared-decks/{deck_item_id}")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', response.data)

    def test_shared_deck_api_create_persists_item_and_infers_source_note_type(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)

        create_resp = self.client.post(
            "/api/shared/decks",
            json={
                "title": "Shared Deck API Create",
                "source_deck_id": self.deck_id,
                "source_note_type_id": note_type_id,
                "subcategory": "JLPT vocabulary",
                "target_audience": "Self-study beginners",
                "description": "Deck description",
                "preview_text": "Preview",
                "tags": ["jlpt", "n5"],
                "pricing_mode": "free",
                "taxonomy_domain": "language_learning",
                "taxonomy_subject": "japanese",
                "taxonomy_difficulty_band": "beginner",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["reading_recall"],
                "publish_status": "published",
            },
        )
        self.assertEqual(create_resp.status_code, 201)
        payload = create_resp.get_json() or {}
        self.assertEqual(payload.get("title"), "Shared Deck API Create")
        self.assertEqual(payload.get("taxonomy_metadata", {}).get("subcategory"), "JLPT vocabulary")
        self.assertEqual(payload.get("taxonomy_metadata", {}).get("target_audience"), "Self-study beginners")
        self.assertEqual(payload.get("source_deck_id"), self.deck_id)
        self.assertEqual(payload.get("source_note_type_id"), note_type_id)
        self.assertTrue(payload.get("release_versioned"))
        self.assertIsNotNone(payload.get("current_release_id"))

        with self.app.app_context():
            deck_item = DeckMarketplaceItem.query.filter_by(title="Shared Deck API Create").first()
            self.assertIsNotNone(deck_item)
            self.assertEqual(deck_item.source_deck_id, self.deck_id)
            self.assertEqual(deck_item.source_note_type_id, note_type_id)
            self.assertIsNotNone(deck_item.current_release_id)
            self.assertEqual(len(deck_item.releases), 1)
            self.assertEqual(deck_item.releases[0].version_label, "1.0.0")

    def test_shared_deck_api_rejects_duplicate_and_child_of_shared_parent(self):
        with self.app.app_context():
            child_deck = Deck(
                name="Child of Shared Parent",
                owner_user_id=self.user_id,
                parent_id=self.deck_id,
            )
            existing_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                title="Existing Shared Parent",
                publish_status="published",
            )
            db.session.add_all([child_deck, existing_item])
            db.session.commit()
            child_deck_id = child_deck.id

        duplicate_response = self.client.post(
            "/api/shared/decks",
            json={"title": "Duplicate listing", "source_deck_id": self.deck_id},
        )
        self.assertEqual(duplicate_response.status_code, 409)
        self.assertEqual(duplicate_response.get_json().get("error"), "CONFLICT")
        self.assertEqual(duplicate_response.get_json().get("field"), "source_deck_id")

        child_response = self.client.post(
            "/api/shared/decks",
            json={"title": "Child listing", "source_deck_id": child_deck_id},
        )
        self.assertEqual(child_response.status_code, 409)
        child_payload = child_response.get_json() or {}
        self.assertEqual(child_payload.get("error"), "CONFLICT")
        self.assertIn("bộ cha", child_payload.get("message", "").lower())

    def test_shared_deck_api_rejects_marketplace_clone_subtree(self):
        _local_root_id, local_child_id = self._create_installed_clone_decks()

        response = self.client.post(
            "/api/shared/decks",
            json={
                "title": "Re-shared Marketplace clone",
                "source_deck_id": local_child_id,
            },
        )

        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("error"), "CONFLICT")
        self.assertEqual(payload.get("field"), "source_deck_id")
        self.assertIn("Marketplace", payload.get("message", ""))

        legacy_response = self.client.get(
            f"/flashcards/decks/{local_child_id}/share",
            follow_redirects=False,
        )
        self.assertEqual(legacy_response.status_code, 200)
        self.assertIn(b'<div id="root"></div>', legacy_response.data)

    def test_shared_deck_api_rejects_foreign_note_type_and_source_mutation(self):
        with self.app.app_context():
            victim = User(username="victim", email="victim@example.com")
            victim.set_password("password")
            db.session.add(victim)
            db.session.flush()
            victim_note_type = NoteType(
                user_id=victim.id,
                name="Private Victim Template",
                publish_status="private",
            )
            db.session.add(victim_note_type)
            db.session.flush()
            db.session.add(
                Template(
                    note_type_id=victim_note_type.id,
                    name="Private Card",
                    front_html="TOP SECRET",
                    back_html="PRIVATE BACK",
                    position=0,
                )
            )
            other_deck = Deck(name="Other owned deck", owner_user_id=self.user_id)
            db.session.add(other_deck)
            db.session.commit()
            victim_note_type_id = victim_note_type.id
            other_deck_id = other_deck.id

        create_response = self.client.post(
            "/api/shared/decks",
            json={
                "title": "Foreign template leak",
                "source_deck_id": self.deck_id,
                "source_note_type_id": victim_note_type_id,
                "description": "Must not publish",
                "preview_text": "Private preview",
                "taxonomy_domain": "language_learning",
                "taxonomy_subject": "japanese",
                "taxonomy_difficulty_band": "beginner",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["meaning_recall"],
                "publish_status": "published",
            },
        )
        self.assertEqual(create_response.status_code, 404)
        self.assertEqual((create_response.get_json() or {}).get("field"), "source_note_type_id")

        note_type = self._create_note_type()
        with self.app.app_context():
            item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type["id"],
                title="Immutable source listing",
                publish_status="private",
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id

        patch_response = self.client.patch(
            f"/api/shared/decks/{item_id}",
            json={"source_deck_id": other_deck_id},
        )
        self.assertEqual(patch_response.status_code, 409)
        self.assertEqual((patch_response.get_json() or {}).get("error"), "CONFLICT")

    def test_shared_deck_api_allows_updating_existing_shared_deck(self):
        note_type = self._create_note_type()
        with self.app.app_context():
            deck = Deck(name="Update Deck", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=deck.id,
                source_note_type_id=note_type["id"],
                title="Original Title",
                description="Original Description",
                publish_status="published",
            )
            db.session.add(item)
            db.session.commit()
            item_id = item.id
            deck_id = deck.id

        patch_response = self.client.patch(
            f"/api/shared/decks/{item_id}",
            json={
                "source_deck_id": deck_id,
                "title": "Updated Title",
                "description": "Updated Description",
                "preview_text": "Updated Preview Text",
                "taxonomy_domain": "language_learning",
                "taxonomy_subject": "japanese",
                "taxonomy_difficulty_band": "beginner",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["reading_recall"],
            },
        )
        self.assertEqual(patch_response.status_code, 200)
        payload = patch_response.get_json() or {}
        self.assertEqual(payload.get("title"), "Updated Title")
        self.assertEqual(payload.get("description"), "Updated Description")
        self.assertEqual(payload.get("preview_text"), "Updated Preview Text")

        version_response = self.client.patch(
            f"/api/shared/decks/{item_id}",
            json={"version": "2.0.0"},
        )
        self.assertEqual(version_response.status_code, 409)
        self.assertEqual((version_response.get_json() or {}).get("field"), "version")

    def test_shared_deck_api_rejects_parent_when_descendant_is_shared(self):
        with self.app.app_context():
            child = Deck(
                name="Already shared descendant",
                owner_user_id=self.user_id,
                parent_id=self.deck_id,
            )
            db.session.add(child)
            db.session.flush()
            db.session.add(
                DeckMarketplaceItem(
                    owner_user_id=self.user_id,
                    source_deck_id=child.id,
                    title="Shared descendant",
                    publish_status="published",
                )
            )
            db.session.commit()

        response = self.client.post(
            "/api/shared/decks",
            json={"title": "Overlapping parent", "source_deck_id": self.deck_id},
        )
        self.assertEqual(response.status_code, 409)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("field"), "source_deck_id")
        self.assertIn("bộ con", payload.get("message", "").lower())

    def test_shared_deck_api_defaults_title_to_source_deck_name(self):
        note_type_id = self._create_note_type()["id"]
        with self.app.app_context():
            deck = Deck(
                name="Auto Titled Deck",
                owner_user_id=self.user_id,
            )
            db.session.add(deck)
            db.session.commit()
            deck_id = deck.id

        response = self.client.post(
            "/api/shared/decks",
            json={
                "source_deck_id": deck_id,
                "source_note_type_id": note_type_id,
                "primary_category": "General",
            },
        )
        self.assertEqual(response.status_code, 201)
        payload = response.get_json() or {}
        self.assertEqual(payload.get("title"), "Auto Titled Deck")

    def test_standard_user_can_load_deck_publish_options(self):
        with self.app.app_context():
            user = User(username="standard", email="standard@example.com", is_admin=False)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            db.session.add(Deck(name="Standard user deck", owner_user_id=user.id))
            db.session.commit()

        client = self.app.test_client()
        client.post(
            "/login",
            data={"email": "standard@example.com", "password": "password"},
            follow_redirects=True,
        )
        response = client.get("/api/shared/decks/publish-options")
        self.assertEqual(response.status_code, 200)
        self.assertTrue((response.get_json() or {}).get("items"))

    def test_archived_deck_listing_remains_visible_to_owner_only(self):
        with self.app.app_context():
            viewer = User(username="archived-viewer", email="archived-viewer@example.com")
            viewer.set_password("password")
            archived_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                title="Archived owner listing",
                publish_status="archived",
                archived_at=datetime.utcnow(),
            )
            db.session.add_all([viewer, archived_item])
            db.session.commit()
            archived_item_id = archived_item.id

        owner_list = self.client.get("/api/shared/decks")
        self.assertEqual(owner_list.status_code, 200)
        self.assertTrue(
            any(
                row.get("id") == archived_item_id
                for row in (owner_list.get_json() or {}).get("items", [])
            )
        )
        self.assertEqual(
            self.client.get(f"/api/shared/decks/{archived_item_id}").status_code,
            200,
        )

        viewer_client = self.app.test_client()
        viewer_client.post(
            "/login",
            data={"email": "archived-viewer@example.com", "password": "password"},
            follow_redirects=True,
        )
        viewer_list = viewer_client.get("/api/shared/decks")
        self.assertFalse(
            any(
                row.get("id") == archived_item_id
                for row in (viewer_list.get_json() or {}).get("items", [])
            )
        )
        self.assertEqual(
            viewer_client.get(f"/api/shared/decks/{archived_item_id}").status_code,
            404,
        )

    def test_shared_deck_publish_options_mark_tree_eligibility(self):
        local_root_id, local_child_id = self._create_installed_clone_decks()
        with self.app.app_context():
            shared_child = Deck(
                name="Blocked Shared Child",
                owner_user_id=self.user_id,
                parent_id=self.deck_id,
            )
            anki_deck = Deck(
                name="Anki Synced Deck",
                owner_user_id=self.user_id,
            )
            nested_anki_deck = Deck(
                name="Anki Deck Under Installed Folder",
                owner_user_id=self.user_id,
                parent_id=local_root_id,
            )
            existing_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                title="Published Root",
                publish_status="published",
            )
            db.session.add_all([shared_child, anki_deck, nested_anki_deck, existing_item])
            db.session.commit()
            shared_child_id = shared_child.id
            anki_deck_id = anki_deck.id
            nested_anki_deck_id = nested_anki_deck.id

        response = self.client.get("/api/shared/decks/publish-options")
        self.assertEqual(response.status_code, 200)
        rows = {
            int(row["id"]): row
            for row in (response.get_json() or {}).get("items", [])
        }

        self.assertEqual(rows[self.deck_id]["block_code"], "already_shared")
        self.assertFalse(rows[self.deck_id]["is_selectable"])
        self.assertEqual(rows[shared_child_id]["parent_id"], self.deck_id)
        self.assertEqual(rows[shared_child_id]["block_code"], "ancestor_shared")
        self.assertEqual(rows[local_child_id]["block_code"], "marketplace_clone")
        self.assertTrue(rows[anki_deck_id]["is_selectable"])
        self.assertIsNone(rows[anki_deck_id]["block_code"])
        self.assertTrue(rows[nested_anki_deck_id]["is_selectable"])
        self.assertIsNone(rows[nested_anki_deck_id]["block_code"])

    def test_shared_deck_api_patch_updates_item_for_owner(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)

        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Before Patch",
                description="Deck description",
                primary_category="General",
                tags=["old"],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="private",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        patch_resp = self.client.patch(
            f"/api/shared/decks/{deck_item_id}",
            json={
                "title": "Shared Deck After Patch",
                "source_note_type_id": note_type_id,
                "description": "Updated description",
                "tags": ["updated", "deck"],
                "taxonomy_domain": "language_learning",
                "taxonomy_subject": "japanese",
                "taxonomy_difficulty_band": "beginner",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["reading_recall"],
                "publish_status": "published",
            },
        )
        self.assertEqual(patch_resp.status_code, 200)
        payload = patch_resp.get_json() or {}
        self.assertEqual(payload.get("title"), "Shared Deck After Patch")
        self.assertEqual(payload.get("publish_status"), "published")
        self.assertEqual(payload.get("tags"), ["updated", "deck"])

        with self.app.app_context():
            deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
            self.assertIsNotNone(deck_item)
            self.assertEqual(deck_item.title, "Shared Deck After Patch")  # type: ignore[union-attr]
            self.assertEqual(deck_item.description, "Updated description")  # type: ignore[union-attr]
            self.assertEqual(deck_item.publish_status, "published")  # type: ignore[union-attr]
            self.assertEqual(deck_item.tags, ["updated", "deck"])  # type: ignore[union-attr]

    def test_authenticated_navbar_places_installed_decks_under_content_management(self):
        response = self.client.get("/api/session")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("authenticated"))
        self.assertEqual(data.get("user", {}).get("email"), "admin@example.com")


    def test_share_note_type_page_updates_taxonomy_and_redirects_to_detail(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        page_resp = self.client.get(f"/flashcards/note-types/{note_type_id}/share")
        self.assertEqual(page_resp.status_code, 200)
        page_html = page_resp.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', page_html)

        share_resp = self.client.post(
            f"/flashcards/note-types/{note_type_id}/share",
            data={
                "title": "Shared Note Type",
                "description": "Template description",
                "preview_text": "Template preview",
                "pricing_mode": "free",
                "taxonomy_domain": "language_learning",
                "taxonomy_subject": "japanese",
                "taxonomy_difficulty_band": "beginner",
                "taxonomy_framework": "jlpt",
                "taxonomy_framework_level": "n5",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["meaning_recall"],
                "format_features": ["preview_available"],
                "taxonomy_best_used_for": "vocabulary",
            },
            follow_redirects=False,
        )
        self.assertEqual(share_resp.status_code, 302)
        self.assertIn(f"/flashcards/shared-note-types/{note_type_id}", share_resp.headers.get("Location", ""))

        with self.app.app_context():
            saved = NoteType.query.get(note_type_id)
            self.assertIsNotNone(saved)
            self.assertEqual(saved.publish_status, "published")
            self.assertEqual((saved.taxonomy_metadata or {}).get("subject"), "japanese")
            self.assertEqual((saved.taxonomy_metadata or {}).get("best_used_for"), "vocabulary")

    def test_shared_note_type_marketplace_uses_react_shell(self):
        note_type_response = self.client.get("/flashcards/shared-note-types")
        self.assertEqual(note_type_response.status_code, 200)
        note_type_html = note_type_response.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', note_type_html)
        self.assertIn('type="module"', note_type_html)
        self.assertNotIn("market-hub-page--compact-catalog", note_type_html)

        deck_response = self.client.get("/flashcards/shared-decks")
        self.assertEqual(deck_response.status_code, 200)
        deck_html = deck_response.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', deck_html)

    def test_shared_note_type_compact_hub_omits_unused_extended_payload(self):
        note_type = self._create_note_type()
        with self.app.app_context():
            db.session.add_all(
                [
                    NoteType(
                        user_id=self.user_id,
                        name=f"Private compact {index}",
                        publish_status="private",
                    )
                    for index in range(15)
                ]
            )
            from app.services import marketplace_taxonomy_service
            marketplace_taxonomy_service.ensure_default_taxonomy_data(db.session)
            marketplace_taxonomy_service.build_taxonomy_schema(content_type="note_type")
            db.session.commit()
            engine = db.engine

        query_count = 0

        def count_query(*_args, **_kwargs):
            nonlocal query_count
            query_count += 1

        event.listen(engine, "before_cursor_execute", count_query)
        try:
            hub_response = self.client.get("/api/shared/note-types/hub?compact=1")
        finally:
            event.remove(engine, "before_cursor_execute", count_query)
        self.assertEqual(hub_response.status_code, 200)
        self.assertLessEqual(query_count, 10)
        hub_payload = hub_response.get_json() or {}
        marketplace_rows = (hub_payload.get("marketplace") or {}).get("items") or []
        row = next(item for item in marketplace_rows if item.get("id") == note_type["id"])

        self.assertNotIn("field_defs", row)
        self.assertNotIn("templates", row)
        self.assertEqual((hub_payload.get("discovery") or {}).get("recommended"), [])
        self.assertEqual((hub_payload.get("seller") or {}).get("drafts"), [])

        detail_response = self.client.get(f"/api/shared/note-types/{note_type['id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.get_json() or {}
        self.assertTrue(detail_payload.get("field_defs"))
        self.assertTrue(detail_payload.get("templates"))

    def test_shared_note_type_hub_includes_saved_library_and_detail_extras(self):
        with self.app.app_context():
            seller = User(username="seller-one", email="seller-one@example.com")
            seller.set_password("password")
            db.session.add(seller)
            db.session.flush()

            note_type = NoteType(
                user_id=seller.id,
                name="Kanji Library",
                description="Core kanji deck",
                primary_category="Kanji",
                tags=["jlpt", "n3"],
                pricing_mode="free",
                price_amount_minor=0,
                publish_status="published",
            )
            sibling = NoteType(
                user_id=seller.id,
                name="Kanji Library 2",
                description="Sibling template",
                primary_category="Kanji",
                tags=["jlpt", "n3"],
                pricing_mode="free",
                price_amount_minor=0,
                publish_status="published",
            )
            related = NoteType(
                user_id=self.user_id,
                name="Grammar N3",
                description="Related item",
                primary_category="Kanji",
                tags=["n3"],
                pricing_mode="free",
                price_amount_minor=0,
                publish_status="published",
            )
            db.session.add_all([note_type, sibling, related])
            db.session.commit()
            note_type_id = note_type.id

        save_resp = self.client.post(f"/api/shared/note-types/{note_type_id}/save")
        self.assertEqual(save_resp.status_code, 200)
        self.assertTrue((save_resp.get_json() or {}).get("saved"))

        hub_resp = self.client.get("/api/shared/note-types/hub")
        self.assertEqual(hub_resp.status_code, 200)
        hub_payload = hub_resp.get_json() or {}
        self.assertIn("discovery", hub_payload)
        self.assertIn("library", hub_payload)
        self.assertIn("seller", hub_payload)

        saved_rows = (hub_payload.get("library") or {}).get("saved") or []
        self.assertTrue(any(row.get("id") == note_type_id for row in saved_rows))

        detail_resp = self.client.get(f"/api/shared/note-types/{note_type_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.get_json() or {}
        self.assertTrue(detail_payload.get("is_saved"))
        self.assertIn("author_profile", detail_payload)
        self.assertIn("author_other_items", detail_payload)
        self.assertIn("related_items", detail_payload)
        self.assertIn("recent_reviews", detail_payload)

    def test_shared_note_type_hub_handles_installed_note_type_library(self):
        with self.app.app_context():
            seller = User(username="seller-installed", email="seller-installed@example.com")
            seller.set_password("password")
            db.session.add(seller)
            db.session.flush()

            note_type = NoteType(
                user_id=seller.id,
                name="Installed Library",
                description="Installed template",
                primary_category="Kanji",
                tags=["jlpt"],
                pricing_mode="free",
                price_amount_minor=0,
                publish_status="published",
            )
            db.session.add(note_type)
            db.session.commit()
            note_type_id = note_type.id

        install_resp = self.client.post(f"/api/shared/note-types/{note_type_id}/install")
        self.assertEqual(install_resp.status_code, 201)

        hub_resp = self.client.get("/api/shared/note-types/hub")
        self.assertEqual(hub_resp.status_code, 200)
        hub_payload = hub_resp.get_json() or {}

        library_rows = [
            *(hub_payload.get("library", {}).get("using_now") or []),
            *(hub_payload.get("library", {}).get("installed") or []),
        ]
        self.assertTrue(any(row.get("id") == note_type_id for row in library_rows))

    def test_shared_deck_hub_and_detail_include_saved_state(self):
        with self.app.app_context():
            seller = User(username="seller-two", email="seller-two@example.com")
            seller.set_password("password")
            db.session.add(seller)
            db.session.flush()

            source_note_type = NoteType(
                user_id=seller.id,
                name="Shared Source",
                description="Source note type",
                primary_category="General",
                tags=["deck"],
                pricing_mode="free",
                price_amount_minor=0,
                publish_status="published",
            )
            db.session.add(source_note_type)
            db.session.flush()

            source_deck = Deck(name="Shared Deck Hub Source", owner_user_id=seller.id)
            sibling_source_deck = Deck(name="Shared Deck Hub Sibling Source", owner_user_id=seller.id)
            db.session.add_all([source_deck, sibling_source_deck])
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=seller.id,
                source_deck_id=source_deck.id,
                source_note_type_id=source_note_type.id,
                title="Shared Deck Hub",
                description="Deck description",
                primary_category="General",
                tags=["deck", "n4"],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            sibling = DeckMarketplaceItem(
                owner_user_id=seller.id,
                source_deck_id=sibling_source_deck.id,
                source_note_type_id=source_note_type.id,
                title="Shared Deck Hub 2",
                description="Sibling deck",
                primary_category="General",
                tags=["deck"],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add_all([deck_item, sibling])
            db.session.commit()
            deck_item_id = deck_item.id

        save_resp = self.client.post(f"/api/shared/decks/{deck_item_id}/save")
        self.assertEqual(save_resp.status_code, 200)
        self.assertTrue((save_resp.get_json() or {}).get("saved"))

        hub_resp = self.client.get("/api/shared/decks/hub")
        self.assertEqual(hub_resp.status_code, 200)
        hub_payload = hub_resp.get_json() or {}
        self.assertIn("discovery", hub_payload)
        self.assertIn("library", hub_payload)
        self.assertIn("seller", hub_payload)
        saved_rows = (hub_payload.get("library") or {}).get("saved") or []
        self.assertTrue(any(row.get("id") == deck_item_id for row in saved_rows))

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.get_json() or {}
        self.assertTrue(detail_payload.get("is_saved"))
        self.assertIn("author_profile", detail_payload)
        self.assertIn("author_other_items", detail_payload)
        self.assertIn("related_items", detail_payload)

    def test_installed_decks_page_lists_installed_deck_actions(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "inu",
                    "Reading": "いぬ",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="installed-page", email="installed-page@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Installed Deck Workspace",
                description="Deck description",
                primary_category="General",
                tags=["n4"],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "installed-page@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)
        installed_root_id = int((install_resp.get_json() or {}).get("installed_deck_id"))

        response = learner_client.get("/flashcards/installed-decks")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', html)
        installed_api = learner_client.get("/api/marketplace/installed-decks")
        self.assertEqual(installed_api.status_code, 200)
        self.assertTrue(
            any(
                int(item.get("installed_deck_id") or 0) == installed_root_id
                for item in (installed_api.get_json() or {}).get("items", [])
            )
        )

    def test_shared_deck_preview_requires_source_note_type_when_notes_missing(self):
        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=None,
                title="Shared Deck Entries Only",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.get_json()
        self.assertIsNone(detail_payload.get("source_note_type"))
        self.assertEqual(detail_payload.get("test_samples"), [])

        preview_resp = self.client.post(
            f"/api/shared/decks/{deck_item_id}/templates/unknown-template/preview",
            json={},
        )
        self.assertEqual(preview_resp.status_code, 409)
        self.assertIn(
            "source note type",
            (preview_resp.get_json() or {}).get("message", "").lower(),
        )

    def test_shared_deck_install_creates_pointer_clone_without_note_copy(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            child_deck = Deck(name="Installed Child", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="learner", email="learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Install Clone",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "learner@example.com", "password": "password"},
            follow_redirects=True,
        )

        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)
        install_payload = install_resp.get_json()
        installed_root_id = install_payload.get("installed_deck_id")
        self.assertIsNotNone(installed_root_id)

        with self.app.app_context():
            install_row = DeckInstall.query.filter_by(deck_item_id=deck_item_id, user_id=learner_id).first()
            self.assertIsNotNone(install_row)
            self.assertEqual(install_row.clone_mode, "logical_overlay")
            self.assertIsNotNone(install_row.base_snapshot_at)
            self.assertEqual(install_row.version_mode, "release")
            self.assertIsNotNone(install_row.applied_release_id)
            deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
            self.assertEqual(install_row.applied_release_id, deck_item.current_release_id)
            subtree_ids = self._collect_subtree_ids(int(installed_root_id))
            cloned_notes_count = Note.query.filter(
                Note.user_id == learner_id,
                Note.deck_id.in_(subtree_ids),
            ).count()
            self.assertEqual(cloned_notes_count, 0)

            cloned_map_rows = DeckCloneDeckMap.query.filter_by(deck_install_id=install_row.id).all()
            self.assertTrue(cloned_map_rows)
            self.assertEqual({int(row.local_deck_id) for row in cloned_map_rows}, set(subtree_ids))
            self.assertEqual(
                {int(row.source_deck_id) for row in cloned_map_rows},
                {self.deck_id, child_deck_id},
            )

        next_resp = learner_client.get(f"/api/study/next?scope=deck&scope_id={installed_root_id}")
        self.assertEqual(next_resp.status_code, 200)
        next_payload = next_resp.get_json()
        self.assertIsNotNone(next_payload.get("card_id"))
        self.assertIn("\u72ac", next_payload.get("rendered_front_html", ""))

    def test_shared_deck_install_fails_fast_when_release_not_ready(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            learner = User(username="unreleased-learner", email="unreleased-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()

            # Create unversioned visible listing (current_release_id is None)
            unversioned_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Unreleased Deck Listing",
                description="Unreleased deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(unversioned_item)
            db.session.commit()
            unversioned_item_id = unversioned_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "unreleased-learner@example.com", "password": "password"},
            follow_redirects=True,
        )

        install_resp = learner_client.post(f"/api/shared/decks/{unversioned_item_id}/install")
        self.assertEqual(install_resp.status_code, 503)
        error_payload = install_resp.get_json() or {}
        self.assertEqual(error_payload.get("error"), "DECK_RELEASE_NOT_READY")

        with self.app.app_context():
            # Invariant: zero install rows and zero releases created
            self.assertEqual(
                DeckInstall.query.filter_by(deck_item_id=unversioned_item_id).count(),
                0,
            )
            self.assertEqual(
                DeckRelease.query.filter_by(deck_item_id=unversioned_item_id).count(),
                0,
            )

    def test_shared_deck_install_clone_cards_visible_in_browse_api(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            child_deck = Deck(name="Browse Child", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="browse-learner", email="browse-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Browse Visibility",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "browse-learner@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)
        installed_root_id = int(install_resp.get_json().get("installed_deck_id"))
        with self.app.app_context():
            install_row = DeckInstall.query.filter_by(deck_item_id=deck_item_id, user_id=learner_id).first()
            self.assertIsNotNone(install_row)
            install_id = install_row.id
            cloned_child_map = DeckCloneDeckMap.query.filter_by(
                deck_install_id=install_row.id,
                source_deck_id=child_deck_id,
            ).first()
            self.assertIsNotNone(cloned_child_map)
            cloned_child_local_id = int(cloned_child_map.local_deck_id)

        tree_resp = learner_client.get("/vocabulary/api/browse/decks/tree")
        self.assertEqual(tree_resp.status_code, 200)
        tree_payload = tree_resp.get_json() or {}
        tree_nodes = tree_payload.get("tree") or []
        self.assertTrue(tree_nodes)

        visible_deck_ids: set[int] = set()

        def _collect_ids(nodes):
            for node in nodes:
                node_id = node.get("id")
                if node_id is not None:
                    visible_deck_ids.add(int(node_id))
                _collect_ids(node.get("children") or [])

        _collect_ids(tree_nodes)
        self.assertIn(installed_root_id, visible_deck_ids)

        cards_resp = learner_client.get(
            f"/vocabulary/api/browse/cards?deck_id={installed_root_id}&include_subdecks=1"
        )
        self.assertEqual(cards_resp.status_code, 200)
        cards_payload = cards_resp.get_json() or {}
        items = cards_payload.get("items") or []
        self.assertEqual(int(cards_payload.get("total") or 0), 1)
        self.assertEqual(len(items), 1)
        row = items[0]
        self.assertIn("\u72ac", row.get("word", ""))
        self.assertTrue((row.get("deck_name") or "").strip())

        card_id = row.get("card_id")
        self.assertIsNotNone(card_id)
        detail_resp = learner_client.get(f"/vocabulary/api/browse/cards/{card_id}")
        self.assertEqual(detail_resp.status_code, 200)
        detail_payload = detail_resp.get_json() or {}
        self.assertIn("\u72ac", ((detail_payload.get("card") or {}).get("word") or ""))
        self.assertEqual(
            int(((detail_payload.get("note") or {}).get("deck_id") or 0)),
            cloned_child_local_id,
        )
        self.assertEqual(
            int(((detail_payload.get("card") or {}).get("deck_id") or 0)),
            cloned_child_local_id,
        )

        save_resp = learner_client.patch(
            f"/vocabulary/api/browse/cards/{card_id}",
            json={
                "deck_id": cloned_child_local_id,
                "tags": row.get("tags") or [],
                "field_values": {
                    "Word": "\u72ac*",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(save_resp.status_code, 200)
        save_payload = save_resp.get_json() or {}
        self.assertIn("\u72ac*", ((save_payload.get("row") or {}).get("word") or ""))
        self.assertEqual(
            ((save_payload.get("detail") or {}).get("note") or {}).get("field_values", {}).get("Word"),
            "\u72ac*",
        )

        reload_detail_resp = learner_client.get(f"/vocabulary/api/browse/cards/{card_id}")
        self.assertEqual(reload_detail_resp.status_code, 200)
        reload_detail_payload = reload_detail_resp.get_json() or {}
        self.assertEqual(
            ((reload_detail_payload.get("note") or {}).get("field_values") or {}).get("Word"),
            "\u72ac*",
        )

        reload_cards_resp = learner_client.get(
            f"/vocabulary/api/browse/cards?deck_id={installed_root_id}&include_subdecks=1"
        )
        self.assertEqual(reload_cards_resp.status_code, 200)
        reload_items = (reload_cards_resp.get_json() or {}).get("items") or []
        self.assertEqual(len(reload_items), 1)
        self.assertIn("\u72ac*", reload_items[0].get("word", ""))

        with self.app.app_context():
            source_note = db.session.get(Note, row.get("note_id"))
            self.assertIsNotNone(source_note)
            self.assertEqual((source_note.field_values or {}).get("Word"), "\u72ac")
            override_row = DeckCloneNoteFieldOverride.query.filter_by(
                deck_install_id=install_id,
                source_note_id=row.get("note_id"),
                field_name="Word",
            ).first()
            self.assertIsNotNone(override_row)
            self.assertEqual(override_row.operation, "set")
            self.assertEqual(override_row.value, "\u72ac*")

    def test_shared_deck_install_clones_source_note_type_for_installer(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="nt-clone-learner", email="nt-clone-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Clones Note Type",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "nt-clone-learner@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)
        installed_root_id = int((install_resp.get_json() or {}).get("installed_deck_id"))

        with self.app.app_context():
            install_row = DeckInstall.query.filter_by(deck_item_id=deck_item_id, user_id=learner_id).first()
            self.assertIsNotNone(install_row)
            root_deck = Deck.query.get(installed_root_id)
            self.assertIsNotNone(root_deck)

            note_type_install = NoteTypeInstall.query.filter_by(
                source_note_type_id=note_type_id,
                user_id=learner_id,
            ).first()
            self.assertIsNotNone(note_type_install)
            self.assertIsNotNone(note_type_install.installed_note_type_id)
            self.assertNotEqual(note_type_install.installed_note_type_id, note_type_id)

            installed_note_type = NoteType.query.get(note_type_install.installed_note_type_id)
            self.assertIsNotNone(installed_note_type)
            self.assertEqual(installed_note_type.user_id, learner_id)
            self.assertEqual(root_deck.note_type_id, installed_note_type.id)

    def test_shared_deck_clone_pins_snapshot_against_new_source_notes(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            child_deck = Deck(name="Snapshot Child", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="snapshot-learner", email="snapshot-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Snapshot Pin Deck",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        # The re-shown learning step must not cross the study-day boundary.
        self._keep_day_boundary_away(learner_id)
        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "snapshot-learner@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)
        installed_root_id = int(install_resp.get_json().get("installed_deck_id"))

        # Add a new upstream note after clone install; pinned clone should not see it.
        new_source_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(new_source_note_resp.status_code, 201)

        first_next_resp = learner_client.get(f"/api/study/next?scope=deck&scope_id={installed_root_id}")
        self.assertEqual(first_next_resp.status_code, 200)
        first_next_payload = first_next_resp.get_json()
        self.assertIsNotNone(first_next_payload.get("card_id"))
        self.assertIn("\u72ac", first_next_payload.get("rendered_front_html", ""))
        self.assertNotIn("\u732b", first_next_payload.get("rendered_front_html", ""))

        answer_resp = learner_client.post(
            f"/api/study/{first_next_payload['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": installed_root_id},
        )
        self.assertEqual(answer_resp.status_code, 200)

        second_next_resp = learner_client.get(f"/api/study/next?scope=deck&scope_id={installed_root_id}")
        self.assertEqual(second_next_resp.status_code, 200)
        second_next_payload = second_next_resp.get_json()
        self.assertEqual(second_next_payload.get("card_id"), first_next_payload.get("card_id"))
        self.assertIn("\u72ac", second_next_payload.get("rendered_front_html", ""))
        self.assertNotIn("\u732b", second_next_payload.get("rendered_front_html", ""))

    def test_cutover_uses_per_install_savepoints_and_canonical_exports(self):
        with self.app.app_context():
            source_decks = [
                Deck(name=f"Cutover Source {index}", owner_user_id=self.user_id)
                for index in range(2)
            ]
            local_decks = [
                Deck(name=f"Cutover Local {index}", owner_user_id=self.user_id)
                for index in range(2)
            ]
            db.session.add_all([*source_decks, *local_decks])
            db.session.flush()
            items = [
                DeckMarketplaceItem(
                    owner_user_id=self.user_id,
                    source_deck_id=source_decks[index].id,
                    title=f"Cutover Item {index}",
                    description="Cutover savepoint contract",
                    primary_category="General",
                    tags=[],
                    pricing_mode="free",
                    price_amount_minor=0,
                    version="1.0.0",
                    publish_status="private",
                )
                for index in range(2)
            ]
            db.session.add_all(items)
            db.session.flush()
            installs = [
                DeckInstall(
                    deck_item_id=items[index].id,
                    user_id=self.user_id,
                    local_deck_id=local_decks[index].id,
                    source_deck_id=source_decks[index].id,
                    source_owner_user_id=self.user_id,
                    clone_mode="legacy_copy",
                    installed_at=datetime.utcnow() + timedelta(seconds=index),
                )
                for index in range(2)
            ]
            db.session.add_all(installs)
            db.session.commit()

            self.assertIs(
                share_ctrl.cutover_clone_model_to_overlay_only,
                cutover_service.cutover_clone_model_to_overlay_only,
            )
            self.assertIs(
                flashcards_share_service.cutover_clone_model_to_overlay_only,
                cutover_service.cutover_clone_model_to_overlay_only,
            )

            calls = 0

            def fake_migrate(_install):
                nonlocal calls
                calls += 1
                if calls == 1:
                    raise ShareControllerError("expected mismatch", status=409)
                return {
                    "deck_map_rows": 1,
                    "note_pairs": 2,
                    "note_overrides": 3,
                    "progress_rows": 4,
                }

            with patch.object(
                cutover_service,
                "migrate_legacy_clone_install_to_overlay",
                side_effect=fake_migrate,
            ):
                summary = cutover_service.cutover_clone_model_to_overlay_only(
                    fail_on_mismatch=False
                )
            self.assertEqual(calls, 2)
            self.assertEqual((summary["migrated"], summary["failed"]), (1, 1))
            self.assertEqual(summary["progress_rows"], 4)
            self.assertEqual(summary["errors"][0]["status"], 409)

            with patch.object(
                cutover_service,
                "migrate_legacy_clone_install_to_overlay",
                side_effect=ShareControllerError("strict mismatch", status=409),
            ):
                with self.assertRaises(ShareControllerError):
                    cutover_service.cutover_clone_model_to_overlay_only(
                        fail_on_mismatch=True
                    )

    def test_cutover_rejects_note_learner_before_clone_map_or_progress_mutation(self):
        with self.app.app_context():
            learner = User(
                username="note-cutover-learner",
                email="note-cutover-learner@example.com",
                is_admin=False,
            )
            learner.set_password("password")
            source = Deck(name="NOTE cutover source", owner_user_id=self.user_id)
            db.session.add_all([learner, source])
            db.session.flush()
            local = Deck(name="NOTE cutover local", owner_user_id=learner.id)
            item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=source.id,
                title="NOTE cutover item",
                description="Cutover authority fence",
                primary_category="General",
                tags=[],
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="private",
            )
            db.session.add_all([local, item])
            db.session.flush()
            note_type = NoteType(user_id=learner.id, name="NOTE cutover type")
            template = Template(
                note_type=note_type,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Word}}",
                position=0,
                is_default=True,
            )
            note = Note(
                note_type=note_type,
                user_id=learner.id,
                deck_id=local.id,
                field_values={"Word": "retained"},
            )
            card = Card(note=note, template=template)
            db.session.add_all([note_type, template, note, card])
            db.session.flush()
            db.session.add(
                CardProgress(
                    user_id=learner.id,
                    card_id=card.id,
                    queue="review",
                    due_at=datetime.utcnow(),
                    interval_days=3,
                    revision=4,
                )
            )
            install = DeckInstall(
                deck_item_id=item.id,
                user_id=learner.id,
                local_deck_id=local.id,
                source_deck_id=source.id,
                source_owner_user_id=self.user_id,
                clone_mode="legacy_copy",
                installed_at=datetime.utcnow(),
            )
            db.session.add_all(
                [
                    install,
                    StudyAuthorityEnrollment(
                        learner_user_id=learner.id,
                        mode_code="NOTE",
                        epoch=1,
                        created_at=datetime.utcnow(),
                        updated_at=datetime.utcnow(),
                    ),
                ]
            )
            db.session.commit()

            summary = cutover_service.cutover_clone_model_to_overlay_only(
                fail_on_mismatch=False
            )
            self.assertEqual((summary["migrated"], summary["failed"]), (0, 1))
            self.assertEqual(summary["errors"][0]["status"], 409)
            self.assertIn("NOTE_AUTHORITY_UNAVAILABLE", summary["errors"][0]["message"])
            self.assertEqual(DeckInstall.query.get(install.id).clone_mode, "legacy_copy")
            self.assertEqual(
                DeckCloneDeckMap.query.filter_by(deck_install_id=install.id).count(), 0
            )
            self.assertIsNotNone(db.session.get(Note, note.id))
            self.assertEqual(
                CardProgress.query.filter_by(user_id=learner.id, card_id=card.id)
                .one()
                .revision,
                4,
            )

            with self.assertRaises(ShareControllerError) as failure:
                cutover_service.cutover_clone_model_to_overlay_only(
                    fail_on_mismatch=True
                )
            self.assertEqual(failure.exception.error, "CLONE_CUTOVER_NOT_READY")
            self.assertEqual(DeckInstall.query.get(install.id).clone_mode, "legacy_copy")
            self.assertEqual(
                DeckCloneDeckMap.query.filter_by(deck_install_id=install.id).count(), 0
            )

    def test_cutover_progress_rekey_and_merge_revision_contract(self):
        with self.app.app_context():
            note_type = NoteType(user_id=self.user_id, name="Cutover Progress Contract")
            template = Template(
                note_type=note_type,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Word}}",
                position=0,
                is_default=True,
            )
            notes = [
                Note(
                    note_type=note_type,
                    user_id=self.user_id,
                    deck_id=self.deck_id,
                    field_values={"Word": f"card-{index}"},
                )
                for index in range(7)
            ]
            cards = [Card(note=note, template=template) for note in notes]
            db.session.add_all([note_type, template, *notes, *cards])
            db.session.flush()

            now = datetime.utcnow()
            local_only = CardProgress(
                user_id=self.user_id,
                card_id=cards[0].id,
                queue="learning",
                interval_days=5,
                reps=3,
                revision=5,
                updated_at=now,
            )
            local_newer = CardProgress(
                user_id=self.user_id,
                card_id=cards[2].id,
                queue="review",
                interval_days=20,
                reps=5,
                lapses=2,
                revision=7,
                updated_at=now,
            )
            source_older = CardProgress(
                user_id=self.user_id,
                card_id=cards[3].id,
                queue="learning",
                interval_days=2,
                reps=9,
                lapses=1,
                revision=10,
                updated_at=now - timedelta(days=1),
            )
            local_older = CardProgress(
                user_id=self.user_id,
                card_id=cards[4].id,
                queue="learning",
                interval_days=4,
                reps=12,
                lapses=1,
                revision=4,
                updated_at=now - timedelta(days=2),
            )
            source_newer = CardProgress(
                user_id=self.user_id,
                card_id=cards[5].id,
                queue="review",
                interval_days=30,
                reps=8,
                lapses=3,
                revision=6,
                updated_at=now,
            )
            db.session.add_all(
                [local_only, local_newer, source_older, local_older, source_newer]
            )
            db.session.commit()

            self.assertEqual(
                cutover_service._merge_card_progress_rows_for_cutover(
                    user_id=self.user_id,
                    local_card_id=cards[0].id,
                    source_card_id=cards[1].id,
                ),
                1,
            )
            self.assertEqual(
                cutover_service._merge_card_progress_rows_for_cutover(
                    user_id=self.user_id,
                    local_card_id=cards[6].id,
                    source_card_id=cards[1].id,
                ),
                0,
            )
            self.assertEqual(
                cutover_service._merge_card_progress_rows_for_cutover(
                    user_id=self.user_id,
                    local_card_id=cards[2].id,
                    source_card_id=cards[3].id,
                ),
                1,
            )
            self.assertEqual(
                cutover_service._merge_card_progress_rows_for_cutover(
                    user_id=self.user_id,
                    local_card_id=cards[4].id,
                    source_card_id=cards[5].id,
                ),
                1,
            )
            db.session.flush()

            rekeyed = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=cards[1].id,
            ).one()
            self.assertEqual((rekeyed.queue, rekeyed.interval_days, rekeyed.revision), ("learning", 5, 6))

            local_won = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=cards[3].id,
            ).one()
            self.assertEqual(local_won.queue, "review")
            self.assertEqual(local_won.interval_days, 20)
            self.assertEqual((local_won.reps, local_won.lapses), (9, 2))
            self.assertEqual(int(local_won.revision or 0), 11)

            source_won = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=cards[5].id,
            ).one()
            self.assertEqual(source_won.queue, "review")
            self.assertEqual(source_won.interval_days, 30)
            self.assertEqual((source_won.reps, source_won.lapses), (12, 3))
            self.assertEqual(int(source_won.revision or 0), 7)

            for local_card in (cards[0], cards[2], cards[4]):
                self.assertIsNone(
                    CardProgress.query.filter_by(
                        user_id=self.user_id,
                        card_id=local_card.id,
                    ).first()
                )
            self.assertEqual(
                [note.field_values["Word"] for note in notes],
                [f"card-{index}" for index in range(7)],
            )

    def test_cutover_migrates_legacy_full_copy_install_to_overlay(self):
        self.app.config["STUDY_PROGRESS_SHADOW_WRITE_ENABLED"] = True
        self.app.config["STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED"] = True
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = True
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            source_child = Deck(name="Cutover Source Child", parent_id=self.deck_id)
            db.session.add(source_child)
            db.session.flush()
            source_child_id = source_child.id
            db.session.commit()

        source_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": source_child_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(source_note_resp.status_code, 201)
        source_note_id = source_note_resp.get_json()["id"]

        with self.app.app_context():
            source_note = Note.query.get(source_note_id)
            self.assertIsNotNone(source_note)
            source_card = Card.query.filter_by(note_id=source_note.id).first()
            self.assertIsNotNone(source_card)

            learner = User(username="legacy-cutover", email="legacy-cutover@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Legacy Cutover Deck",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()

            local_root = Deck(
                name="Legacy Local Root",
                parent_id=None,
                owner_user_id=learner_id,
            )
            db.session.add(local_root)
            db.session.flush()
            local_child = Deck(
                name="Legacy Local Child",
                parent_id=local_root.id,
                owner_user_id=learner_id,
            )
            db.session.add(local_child)
            db.session.flush()

            install = DeckInstall(
                deck_item_id=deck_item.id,
                user_id=learner_id,
                local_deck_id=local_root.id,
                clone_mode="legacy_copy",
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                source_owner_user_id=self.user_id,
                base_snapshot_at=datetime.utcnow(),
                installed_at=datetime.utcnow(),
            )
            db.session.add(install)
            db.session.flush()

            db.session.add(
                DeckCloneDeckMap(
                    deck_install_id=install.id,
                    local_deck_id=local_root.id,
                    source_deck_id=self.deck_id,
                )
            )
            db.session.add(
                DeckCloneDeckMap(
                    deck_install_id=install.id,
                    local_deck_id=local_child.id,
                    source_deck_id=source_child_id,
                )
            )

            legacy_note = Note(
                note_type_id=note_type_id,
                user_id=learner_id,
                deck_id=local_child.id,
                field_values={
                    "Word": "\u72ac*",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
                tags=[],
            )
            db.session.add(legacy_note)
            db.session.flush()
            legacy_note_id = legacy_note.id
            legacy_card = Card(
                note_id=legacy_note.id,
                template_id=source_card.template_id,
            )
            db.session.add(legacy_card)
            db.session.flush()
            legacy_card_id = legacy_card.id
            db.session.add(
                CardProgress(
                    user_id=learner_id,
                    card_id=legacy_card.id,
                    queue="review",
                    step_index=0,
                    due_at=datetime.utcnow(),
                    due_day=_day_index(datetime.utcnow(), 4),
                    interval_days=8,
                    ease_factor=2.5,
                    reps=5,
                    lapses=1,
                    revision=7,
                )
            )
            db.session.commit()

            self.assertIs(
                share_ctrl.cutover_clone_model_to_overlay_only,
                cutover_service.cutover_clone_model_to_overlay_only,
            )
            self.assertIs(
                flashcards_share_service.cutover_clone_model_to_overlay_only,
                cutover_service.cutover_clone_model_to_overlay_only,
            )
            summary = share_ctrl.cutover_clone_model_to_overlay_only(fail_on_mismatch=True)
            db.session.commit()
            self.assertEqual(int(summary.get("migrated") or 0), 1)
            self.assertEqual(int(summary.get("failed") or 0), 0)

            migrated_install = DeckInstall.query.get(install.id)
            self.assertIsNotNone(migrated_install)
            self.assertEqual((migrated_install.clone_mode or "").strip().lower(), "logical_overlay")

            self.assertIsNone(Note.query.get(legacy_note_id))
            override_row = DeckCloneNoteFieldOverride.query.filter_by(
                deck_install_id=install.id,
                source_note_id=source_note.id,
                field_name="Word",
            ).first()
            self.assertIsNotNone(override_row)
            self.assertEqual(override_row.operation, "set")
            self.assertEqual(override_row.value, "\u72ac*")

            source_progress = CardProgress.query.filter_by(
                user_id=learner_id,
                card_id=source_card.id,
            ).first()
            self.assertIsNotNone(source_progress)
            self.assertEqual(int(source_progress.reps or 0), 5)
            self.assertEqual(int(source_progress.revision or 0), 8)

            surviving_source_note = db.session.get(Note, source_note.id)
            surviving_source_card = db.session.get(Card, source_card.id)
            self.assertIsNotNone(surviving_source_note)
            self.assertIsNotNone(surviving_source_card)
            self.assertEqual(surviving_source_note.field_values["Word"], "\u72ac")

            legacy_progress = CardProgress.query.filter_by(
                user_id=learner_id,
                card_id=legacy_card_id,
            ).first()
            self.assertIsNone(legacy_progress)
            old_subject = StudyProgressSubject.query.filter_by(
                learner_user_id=learner_id,
                logical_note_key=str(legacy_note_id).encode("utf-8"),
            ).one()
            new_subject = StudyProgressSubject.query.filter_by(
                learner_user_id=learner_id,
                logical_note_key=str(source_note.id).encode("utf-8"),
            ).one()
            self.assertEqual(old_subject.status_code, "REKEYED_CLONE_CUTOVER")
            self.assertIsNone(old_subject.live_note_id)
            self.assertEqual(new_subject.status_code, "MIRRORED_SINGLE")
            self.assertEqual(
                (old_subject.subject_generation, new_subject.subject_generation),
                (2, 2),
            )
            active = StudyProgressContributor.query.filter_by(
                subject_id=new_subject.id,
                contributor_status="ACTIVE",
            ).one()
            self.assertEqual(active.current_provenance_code, "CLONE_CUTOVER")
            self.assertEqual(active.history_completeness_code, "HISTORY_MIXED_PARTIAL")
            self.assertEqual(StudyProgressLifecycleEvent.query.count(), 2)
            self.assertTrue(run_current_progress_backfill(db.session, apply=True).complete)
            reconciled = build_study_progress_reconciliation(
                db.session, observed_at=datetime.utcnow()
            )
            self.assertEqual(reconciled["unexplained"]["by_code"], {})
            self.assertEqual(reconciled["gate"]["status"], "PASS")
            self.assertEqual(
                reconciled["writer_coverage"]["current_contributor_provenance"],
                {"CLONE_CUTOVER": 1},
            )
            self.assertEqual(
                reconciled["writer_coverage"]["matrix"]["CLONE_CUTOVER"]["status"],
                "PASS",
            )

    def test_shared_deck_clone_overlay_saves_delta_only_and_updates_render(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        field_ids = {row["name"]: row["id"] for row in note_type.get("field_defs", [])}

        with self.app.app_context():
            child_deck = Deck(name="Overlay Child", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)
        source_note_id = owner_note_resp.get_json()["id"]

        with self.app.app_context():
            learner = User(username="overlay-learner", email="overlay-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Overlay Deck",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "overlay-learner@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)
        installed_root_id = int(install_resp.get_json().get("installed_deck_id"))

        overlay_resp = learner_client.post(
            f"/api/shared/decks/{deck_item_id}/clone/overlay",
            json={
                "updated_defs": [
                    {
                        "source_field_def_id": field_ids["Meaning"],
                        "properties": {"required": True},
                    }
                ],
                "disabled_def_ids": [field_ids["Reading"]],
                "added_defs": [
                    {
                        "name": "Example",
                        "field_type": "text",
                        "position": 99,
                        "required": False,
                    }
                ],
                "ordered_def_ids": [field_ids["Word"], field_ids["Meaning"]],
                "note_field_overrides": [
                    {
                        "source_note_id": source_note_id,
                        "field_name": "Word",
                        "operation": "set",
                        "value": "\u72ac*",
                    },
                    {
                        "source_note_id": source_note_id,
                        "field_name": "Reading",
                        "operation": "remove",
                    },
                ],
            },
        )
        self.assertEqual(overlay_resp.status_code, 200)
        overlay_payload = overlay_resp.get_json() or {}
        changes = overlay_payload.get("changes") or {}
        self.assertGreaterEqual(int(changes.get("updated_defs") or 0), 1)
        self.assertGreaterEqual(int(changes.get("disabled_defs") or 0), 1)
        self.assertGreaterEqual(int(changes.get("added_defs") or 0), 1)
        self.assertGreaterEqual(int(changes.get("updated_note_fields") or 0), 1)

        with self.app.app_context():
            install_row = DeckInstall.query.filter_by(deck_item_id=deck_item_id, user_id=learner_id).first()
            self.assertIsNotNone(install_row)
            self.assertEqual(
                DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install_row.id).count(),
                2,
            )
            self.assertEqual(
                DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install_row.id).count(),
                1,
            )
            self.assertEqual(
                DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install_row.id).count(),
                1,
            )
            self.assertEqual(
                DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install_row.id).count(),
                2,
            )
            learner_notes_count = Note.query.filter_by(user_id=learner_id).count()
            self.assertEqual(learner_notes_count, 0)

        next_resp = learner_client.get(f"/api/study/next?scope=deck&scope_id={installed_root_id}")
        self.assertEqual(next_resp.status_code, 200)
        next_payload = next_resp.get_json()
        self.assertIsNotNone(next_payload.get("card_id"))
        self.assertIn("\u72ac*", next_payload.get("rendered_front_html", ""))
        self.assertNotIn("\u3044\u306c", next_payload.get("rendered_back_html", ""))

    def test_shared_deck_install_stress_grows_pointer_rows_not_note_rows(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        for index in range(30):
            owner_note_resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": f"word-{index}",
                        "Reading": f"reading-{index}",
                        "Meaning": f"meaning-{index}",
                    },
                },
            )
            self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Stress Pointer Deck",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            deck_item_id = deck_item.id

            learner_specs: list[tuple[str, str]] = []
            for index in range(12):
                username = f"stress{index}"
                email = f"stress{index}@example.com"
                learner = User(username=username, email=email, is_admin=False)
                learner.set_password("password")
                db.session.add(learner)
                learner_specs.append((username, email))
            db.session.commit()
            learner_ids = [int(row[0]) for row in db.session.query(User.id).filter(User.email.like("stress%@example.com")).all()]

        for _, email in learner_specs:
            learner_client = self.app.test_client()
            learner_client.post(
                "/login",
                data={"email": email, "password": "password"},
                follow_redirects=True,
            )
            install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")
            self.assertEqual(install_resp.status_code, 201)

        with self.app.app_context():
            install_count = DeckInstall.query.filter_by(deck_item_id=deck_item_id).count()
            self.assertEqual(install_count, len(learner_ids))
            deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
            self.assertEqual(deck_item.install_count, install_count)
            source_note_type = db.session.get(NoteType, note_type_id)
            self.assertEqual(source_note_type.install_count, install_count)

            source_note_count = Note.query.filter_by(user_id=self.user_id, deck_id=self.deck_id).count()
            self.assertEqual(source_note_count, 30)

            learner_note_count = Note.query.filter(Note.user_id.in_(learner_ids)).count()
            self.assertEqual(learner_note_count, 0)

            source_deck_count = len(self._collect_subtree_ids(self.deck_id))
            pointer_map_count = (
                DeckCloneDeckMap.query.join(DeckInstall, DeckCloneDeckMap.deck_install_id == DeckInstall.id)
                .filter(DeckInstall.deck_item_id == deck_item_id)
                .count()
            )
            self.assertEqual(pointer_map_count, install_count * source_deck_count)

    def test_shared_deck_install_retries_when_deadlock_occurs(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            learner = User(username="retry-learner", email="retry-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Deadlock Retry",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "retry-learner@example.com", "password": "password"},
            follow_redirects=True,
        )

        class _DeadlockError(Exception):
            def __init__(self):
                super().__init__(1213, "Deadlock found when trying to get lock; try restarting transaction")

        deadlock_exc = OperationalError(
            "INSERT INTO notes (...) VALUES (...)",
            {},
            _DeadlockError(),
        )
        expected_response = {
            "deck_item_id": deck_item_id,
            "installed_deck_id": 999,
            "already_installed": True,
        }

        with (
            patch(
                "app.services.flashcards_share_service.install_shared_deck_item_for_user",
                side_effect=[
                    deadlock_exc,
                    {"created": False, "response": expected_response},
                ],
            ) as install_mock,
            patch("app.services.flashcards_share_service.time.sleep") as sleep_mock,
        ):
            install_resp = learner_client.post(f"/api/shared/decks/{deck_item_id}/install")

        self.assertEqual(install_resp.status_code, 200)
        self.assertEqual(install_resp.get_json(), expected_response)
        self.assertEqual(install_mock.call_count, 2)
        sleep_mock.assert_called_once()

    def test_dashboard_for_installed_deck_includes_child_deck_rows(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            child_deck = Deck(name="Visible Child Deck", parent_id=self.deck_id)
            db.session.add(child_deck)
            db.session.flush()
            child_deck_id = child_deck.id
            db.session.commit()

        owner_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": child_deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(owner_note_resp.status_code, 201)

        with self.app.app_context():
            learner = User(username="viewer", email="viewer@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Dashboard Child Visibility",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        viewer_client = self.app.test_client()
        viewer_client.post(
            "/login",
            data={"email": "viewer@example.com", "password": "password"},
            follow_redirects=True,
        )
        install_resp = viewer_client.post(f"/api/shared/decks/{deck_item_id}/install")
        self.assertEqual(install_resp.status_code, 201)

        dashboard_resp = viewer_client.get("/api/dashboard")
        self.assertEqual(dashboard_resp.status_code, 200)
        dashboard_items = dashboard_resp.get_json().get("items", [])

        def _labels(rows):
            return [
                label
                for row in rows
                for label in [row.get("label"), *_labels(row.get("children", []))]
            ]

        labels = _labels(dashboard_items)
        self.assertIn("Deck A", labels)
        self.assertIn("Visible Child Deck", labels)

    def test_dashboard_counts_include_imported_note_cards(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        create_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(create_note_resp.status_code, 201)

        dashboard_resp = self.client.get("/api/dashboard")
        self.assertEqual(dashboard_resp.status_code, 200)
        dashboard_items = dashboard_resp.get_json().get("items", [])

        def _find(rows):
            for row in rows:
                if row.get("label") == "Deck A":
                    return row
                nested = _find(row.get("children", []))
                if nested is not None:
                    return nested
            return None

        match = _find(dashboard_items)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.get("new_count") or 0), 1)

    def test_vocabulary_study_deck_renders_note_card_source(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        create_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(create_note_resp.status_code, 201)

        study_resp = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")
        self.assertEqual(study_resp.status_code, 200)
        html = study_resp.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', html)

    def test_vocabulary_study_topic_route_is_removed(self):
        study_resp = self.client.get("/vocabulary/study/topic/1")
        self.assertEqual(study_resp.status_code, 410)

    def test_vocabulary_study_lesson_route_is_removed(self):
        study_resp = self.client.get("/vocabulary/study/lesson/1")
        self.assertEqual(study_resp.status_code, 410)

    def test_shared_deck_detail_returns_up_to_five_random_test_words(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        source_rows = [
            ("\u6d77", "\u3046\u307f", "bi\u1ec3n"),
            ("\u5c71", "\u3084\u307e", "n\u00fai"),
            ("\u7a7a", "\u305d\u3089", "tr\u1eddi"),
            ("\u5ddd", "\u304b\u308f", "s\u00f4ng"),
            ("\u68ee", "\u3082\u308a", "r\u1eebng"),
            ("\u96e8", "\u3042\u3081", "m\u01b0a"),
            ("\u98a8", "\u304b\u305c", "gi\u00f3"),
        ]

        for word, reading, translation_vi in source_rows:
            note_resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": reading,
                        "Meaning": translation_vi,
                    },
                },
            )
            self.assertEqual(note_resp.status_code, 201)

        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Random Samples",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        payload = detail_resp.get_json()
        self.assertEqual(payload.get("test_sample_limit"), 5)

        samples = payload.get("test_samples") or []
        self.assertEqual(len(samples), 5)

        source_words = {row[0] for row in source_rows}
        for sample in samples:
            self.assertIn(sample.get("word"), source_words)
            self.assertIsNotNone(sample.get("note_id"))

    def test_shared_deck_detail_returns_all_test_words_when_less_than_five(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        source_rows = [
            ("\u706b", "\u3072", "l\u1eeda"),
            ("\u6c34", "\u307f\u305a", "n\u01b0\u1edbc"),
            ("\u571f", "\u3064\u3061", "\u0111\u1ea5t"),
        ]

        for word, reading, translation_vi in source_rows:
            note_resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": reading,
                        "Meaning": translation_vi,
                    },
                },
            )
            self.assertEqual(note_resp.status_code, 201)

        with self.app.app_context():
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=note_type_id,
                title="Shared Deck Small Samples",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        detail_resp = self.client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        payload = detail_resp.get_json()

        samples = payload.get("test_samples") or []
        self.assertEqual(len(samples), 3)
        self.assertEqual(payload.get("test_sample_limit"), 5)

        source_words = {row[0] for row in source_rows}
        for sample in samples:
            self.assertIn(sample.get("word"), source_words)
            self.assertIsNotNone(sample.get("note_id"))

    def test_shared_deck_detail_includes_other_users_recent_reviews(self):
        with self.app.app_context():
            owner = User(username="review-owner", email="review-owner@example.com", is_admin=False)
            owner.set_password("password")
            viewer = User(username="review-viewer", email="review-viewer@example.com", is_admin=False)
            viewer.set_password("password")
            reviewer_a = User(username="alice", email="alice@example.com", is_admin=False)
            reviewer_a.set_password("password")
            reviewer_b = User(username="bob", email="bob@example.com", is_admin=False)
            reviewer_b.set_password("password")
            db.session.add_all([owner, viewer, reviewer_a, reviewer_b])
            db.session.flush()

            deck_item = DeckMarketplaceItem(
                owner_user_id=owner.id,
                title="Deck With Public Reviews",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()

            db.session.add(
                DeckReview(
                    deck_item_id=deck_item.id,
                    user_id=reviewer_a.id,
                    rating=5,
                    comment="Great deck!",
                )
            )
            db.session.add(
                DeckReview(
                    deck_item_id=deck_item.id,
                    user_id=reviewer_b.id,
                    rating=4,
                    comment="Useful content.",
                )
            )
            # Viewer's own review should stay in my_review, not in recent_reviews list.
            db.session.add(
                DeckReview(
                    deck_item_id=deck_item.id,
                    user_id=viewer.id,
                    rating=3,
                    comment="My own review",
                )
            )
            db.session.commit()
            deck_item_id = deck_item.id

        viewer_client = self.app.test_client()
        viewer_client.post(
            "/login",
            data={"email": "review-viewer@example.com", "password": "password"},
            follow_redirects=True,
        )

        detail_resp = viewer_client.get(f"/api/shared/decks/{deck_item_id}")
        self.assertEqual(detail_resp.status_code, 200)
        payload = detail_resp.get_json() or {}

        recent_reviews = payload.get("recent_reviews") or []
        self.assertEqual(int(payload.get("recent_reviews_count") or 0), 2)
        self.assertEqual(len(recent_reviews), 2)
        usernames = {str(item.get("username") or "") for item in recent_reviews}
        self.assertEqual(usernames, {"alice", "bob"})
        comments = {str(item.get("comment") or "") for item in recent_reviews}
        self.assertIn("Great deck!", comments)
        self.assertIn("Useful content.", comments)

    def test_note_create_rejects_mixed_note_types_in_same_deck(self):
        note_type_a = self._create_note_type()
        note_type_a_id = note_type_a["id"]

        note_type_b_resp = self.client.post(
            "/api/note-types",
            json={
                "name": "Japanese Vocabulary Alt",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Reading", "field_type": "text", "position": 1, "required": False},
                    {"name": "Meaning", "field_type": "richtext", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}} - {{Reading}} {{{Meaning}}}</div>",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(note_type_b_resp.status_code, 201)
        note_type_b_id = note_type_b_resp.get_json()["id"]

        first_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_a_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(first_note_resp.status_code, 201)

        second_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_b_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(second_note_resp.status_code, 400)
        self.assertIn("same template", second_note_resp.get_json().get("message", ""))

    def test_add_field_without_schema_change(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        field_resp = self.client.post(
            f"/api/note-types/{note_type_id}/fields",
            json={"name": "PitchAccent", "field_type": "text", "required": False},
        )
        self.assertEqual(field_resp.status_code, 201)

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u6a4b",
                    "Reading": "\u306f\u3057",
                    "Meaning": "bridge",
                    "PitchAccent": "L-H",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        detail_resp = self.client.get(f"/api/notes/{note_id}")
        self.assertEqual(detail_resp.status_code, 200)
        self.assertEqual(detail_resp.get_json()["field_values"]["PitchAccent"], "L-H")

    def test_study_next_and_answer(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        payload = next_resp.get_json()
        self.assertIsNotNone(payload["card_id"])
        self.assertIn("\u732b", payload["rendered_front_html"])

        answer_resp = self.client.post(
            f"/api/study/{payload['card_id']}/answer",
            json={"rating": "good"},
        )
        self.assertEqual(answer_resp.status_code, 200)
        self.assertTrue(answer_resp.get_json()["success"])

        with self.app.app_context():
            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=payload["card_id"],
            ).first()
            self.assertIsNotNone(progress)
            self.assertIn(progress.queue, {"learning", "review", "relearning", "new"})
            self.assertIsNotNone(progress.reps)

    def test_react_study_uses_versioned_artifacts_and_client_render(self):
        note_type = self._create_note_type()
        create_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type["id"],
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "猫",
                    "Reading": "ねこ",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 201)

        from unittest.mock import patch

        with patch(
            "app.routes.flashcards.study.render_template_pair",
            side_effect=AssertionError("React study must not server-render templates"),
        ):
            next_resp = self.client.get(
                f"/api/study/next?scope=deck&scope_id={self.deck_id}"
                "&render_contract=client_v1"
            )
            self.assertEqual(next_resp.status_code, 200)
            manifest = next_resp.get_json()
            self.assertEqual(manifest["schema_version"], "study-manifest.v1")
            self.assertNotIn("rendered_front_html", manifest)
            self.assertEqual(next_resp.headers.get("Cache-Control"), "private, no-store")

            template_resp = self.client.get(manifest["template_ref"]["url"])
            content_resp = self.client.get(manifest["content_ref"]["url"])
            intervals_resp = self.client.get(manifest["intervals_ref"]["url"])
            self.assertEqual(template_resp.status_code, 200)
            self.assertEqual(content_resp.status_code, 200)
            self.assertEqual(intervals_resp.status_code, 200)
            self.assertIn("{{Word}}", template_resp.get_json()["front_source"])
            self.assertEqual(content_resp.get_json()["render_context"]["Word"], "猫")
            self.assertEqual(
                content_resp.headers.get("Cache-Control"),
                "private, no-cache, must-revalidate",
            )
            self.assertEqual(
                intervals_resp.headers.get("Cache-Control"),
                "private, no-store",
            )

            edit_resp = self.client.patch(
                f"/api/study/cards/{manifest['card_id']}/edit",
                json={
                    "field_values": {"Word": "犬"},
                    "render_contract": "client_v1",
                },
            )
            self.assertEqual(edit_resp.status_code, 200)
            edit_payload = edit_resp.get_json()
            self.assertNotIn("rendered_front_html", edit_payload)
            self.assertNotEqual(
                edit_payload["content_ref"]["version"],
                manifest["content_ref"]["version"],
            )
            self.assertEqual(
                self.client.get(manifest["content_ref"]["url"]).status_code,
                410,
            )
            self.assertEqual(
                self.client.get(edit_payload["content_ref"]["url"]).status_code,
                200,
            )

            answer_resp = self.client.post(
                f"/api/study/{manifest['card_id']}/answer",
                json={
                    "rating": "good",
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "selection_id": manifest["selection_id"],
                    "review_state_version": manifest["review_state_version"],
                    "render_contract": "client_v1",
                },
            )
            self.assertEqual(answer_resp.status_code, 200)
            answer_payload = answer_resp.get_json()
            self.assertIn("next_manifest", answer_payload)
            self.assertNotIn("next_card_payload", answer_payload)

    def test_public_study_artifact_is_immutable_and_anonymous_cacheable(self):
        note_type = self._create_note_type()
        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type["id"],
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "空",
                    "Reading": "そら",
                    "Meaning": "sky",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        share_resp = self.client.post(
            "/api/shared/decks",
            json={
                "title": "Public artifact deck",
                "source_deck_id": self.deck_id,
                "source_note_type_id": note_type["id"],
                "description": "Public cache test",
                "preview_text": "Preview",
                "tags": ["test"],
                "pricing_mode": "free",
                "taxonomy_domain": "language_learning",
                "taxonomy_subject": "japanese",
                "taxonomy_difficulty_band": "beginner",
                "learning_goals": ["vocabulary"],
                "primary_topics": ["reading_recall"],
                "publish_status": "published",
            },
        )
        self.assertEqual(share_resp.status_code, 201)

        next_resp = self.client.get(
            f"/api/study/next?scope=deck&scope_id={self.deck_id}"
            "&render_contract=client_v1"
        )
        manifest = next_resp.get_json()
        self.assertEqual(manifest["template_ref"]["visibility"], "public")
        self.assertEqual(manifest["content_ref"]["visibility"], "public")

        anonymous_client = self.app.test_client()
        artifact_resp = anonymous_client.get(manifest["content_ref"]["url"])
        self.assertEqual(artifact_resp.status_code, 200)
        self.assertEqual(
            artifact_resp.headers.get("Cache-Control"),
            "public, max-age=31536000, s-maxage=31536000, immutable",
        )
        self.assertIsNone(artifact_resp.headers.get("Set-Cookie"))
        etag = artifact_resp.headers.get("ETag")
        self.assertTrue(etag)
        not_modified = anonymous_client.get(
            manifest["content_ref"]["url"],
            headers={"If-None-Match": etag},
        )
        self.assertEqual(not_modified.status_code, 304)

    def test_study_answer_returns_prefetched_next_card_payload(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        for word in ("猫", "犬"):
            create_resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": word,
                        "Meaning": word,
                    },
                },
            )
            self.assertEqual(create_resp.status_code, 201)

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        next_payload = next_resp.get_json()
        self.assertIsNotNone(next_payload.get("card_id"))

        answer_resp = self.client.post(
            f"/api/study/{next_payload['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(answer_resp.status_code, 200)
        answer_payload = answer_resp.get_json()

        prefetched_payload = answer_payload.get("next_card_payload") or {}
        self.assertIsNotNone(prefetched_payload.get("card_id"))
        self.assertNotEqual(prefetched_payload.get("card_id"), next_payload.get("card_id"))
        self.assertIn(prefetched_payload.get("card_id"), prefetched_payload.get("save_card_url", ""))
        self.assertEqual(int(prefetched_payload.get("new_count") or 0), 1)
        self.assertEqual(int(prefetched_payload.get("learn_count") or 0), 1)

    def _keep_day_boundary_away(self, user_id):
        """A 10-minute learning step near 04:00 UTC would cross the study day."""
        from models.user_scheduler_settings import UserSchedulerSettings

        with self.app.app_context():
            db.session.add(UserSchedulerSettings(
                user_id=user_id,
                day_boundary_hour_local=(datetime.utcnow().hour + 12) % 24,
            ))
            db.session.commit()

    def test_study_next_uses_learn_ahead_when_only_intraday_learning_remains(self):
        self._keep_day_boundary_away(self.user_id)
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog",
                },
            },
        )

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        payload = next_resp.get_json()
        self.assertIsNotNone(payload.get("card_id"))

        answer_resp = self.client.post(
            f"/api/study/{payload['card_id']}/answer",
            json={"rating": "good", "scope": "deck", "scope_id": self.deck_id},
        )
        self.assertEqual(answer_resp.status_code, 200)
        answer_payload = answer_resp.get_json()
        self.assertEqual(
            (answer_payload.get("next_card_payload") or {}).get("card_id"),
            payload.get("card_id"),
        )

        waiting_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(waiting_resp.status_code, 200)
        waiting_payload = waiting_resp.get_json()

        self.assertEqual(waiting_payload.get("card_id"), payload.get("card_id"))
        self.assertIsNone(waiting_payload.get("session_state"))
        self.assertEqual(int(waiting_payload.get("new_count") or 0), 0)
        self.assertEqual(int(waiting_payload.get("learn_count") or 0), 1)
        self.assertEqual(int(waiting_payload.get("due_count") or 0), 0)
        self.assertNotIn("pending_learning_count", waiting_payload)
        self.assertNotIn("next_due_at", waiting_payload)

    def test_study_next_aggregates_due_now_and_due_later_cards_into_learn_count(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        for word in ("犬", "猫"):
            create_resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": word,
                        "Meaning": word,
                    },
                },
            )
            self.assertEqual(create_resp.status_code, 201)

        with self.app.app_context():
            cards = (
                Card.query.join(Note, Card.note_id == Note.id)
                .filter(Note.deck_id == self.deck_id)
                .order_by(Card.id.asc())
                .all()
            )
            self.assertEqual(len(cards), 2)
            due_now_card = cards[0]
            due_later_card = cards[1]
            now = datetime.utcnow()
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=due_now_card.id,
                    queue="learning",
                    due_at=now - timedelta(minutes=1),
                    interval_days=0,
                    ease_factor=default_deck_options().startingEase,
                    reps=1,
                    lapses=0,
                )
            )
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=due_later_card.id,
                    queue="learning",
                    due_at=now + timedelta(minutes=15),
                    interval_days=0,
                    ease_factor=default_deck_options().startingEase,
                    reps=1,
                    lapses=0,
                )
            )
            db.session.commit()
            due_now_card_id = due_now_card.id

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        next_payload = next_resp.get_json()

        self.assertEqual(next_payload.get("card_id"), due_now_card_id)
        self.assertEqual(int(next_payload.get("new_count") or 0), 0)
        self.assertEqual(int(next_payload.get("learn_count") or 0), 2)
        self.assertEqual(int(next_payload.get("due_count") or 0), 0)
        self.assertNotIn("pending_learning_count", next_payload)

    def test_learning_crossing_boundary_stays_waiting_until_actual_due_time(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        create_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 201)

        with self.app.app_context():
            user = User.query.get(self.user_id)
            user.timezone = "Asia/Tokyo"
            db.session.commit()

        fixed_now = datetime(2026, 2, 22, 18, 55, 0)
        with patch("app.routes.flashcards.study.datetime") as study_datetime:
            study_datetime.utcnow.return_value = fixed_now

            next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
            self.assertEqual(next_resp.status_code, 200)
            next_payload = next_resp.get_json()
            self.assertEqual(next_payload["intervals_preview"]["good"]["label"], "1d")

            answer_resp = self.client.post(
                f"/api/study/{next_payload['card_id']}/answer",
                json={"rating": "good", "scope": "deck", "scope_id": self.deck_id},
            )
            self.assertEqual(answer_resp.status_code, 200)
            answer_payload = answer_resp.get_json()

            waiting_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
            self.assertEqual(waiting_resp.status_code, 200)
            waiting_payload = waiting_resp.get_json()

        self.assertEqual(
            (answer_payload.get("next_card_payload") or {}).get("session_state"),
            "waiting",
        )
        self.assertEqual(
            (answer_payload.get("next_card_payload") or {}).get("next_due_at"),
            "2026-02-22T19:00:00Z",
        )
        self.assertIsNone(waiting_payload.get("card_id"))
        self.assertEqual(waiting_payload.get("session_state"), "waiting")
        self.assertEqual(int(waiting_payload.get("learn_count") or 0), 1)
        self.assertEqual(waiting_payload.get("next_due_at"), "2026-02-22T19:00:00Z")

        with patch("app.routes.vocabulary.datetime") as vocab_datetime:
            vocab_datetime.utcnow.return_value = fixed_now
            study_resp = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")

        self.assertEqual(study_resp.status_code, 200)
        self.assertIn('<div id="root"></div>', study_resp.get_data(as_text=True))

        with self.app.app_context():
            progress = CardProgress.query.filter_by(user_id=self.user_id).first()
            self.assertEqual(progress.queue, "learning")
            self.assertEqual(progress.due_at, datetime(2026, 2, 22, 19, 0, 0))
            self.assertEqual(progress.due_day, datetime(2026, 2, 23).date().toordinal())

    def test_vocabulary_study_first_render_matches_next_card_review_priority(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        for word in ("犬", "猫"):
            resp = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": word,
                        "Meaning": word,
                    },
                },
            )
            self.assertEqual(resp.status_code, 201)

        fixed_now = datetime(2026, 2, 23, 10, 0, 0)
        options = default_deck_options()
        today_idx = _day_index(fixed_now, options.dayBoundaryHourLocal)

        with self.app.app_context():
            cards = (
                Card.query.join(Note, Card.note_id == Note.id)
                .filter(Note.deck_id == self.deck_id)
                .order_by(Card.id.asc())
                .all()
            )
            overdue_card = cards[0]
            today_card = cards[1]
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=overdue_card.id,
                    queue="review",
                    due_at=fixed_now + timedelta(days=2),
                    due_day=today_idx - 1,
                    interval_days=3,
                )
            )
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=today_card.id,
                    queue="review",
                    due_at=fixed_now - timedelta(days=2),
                    due_day=today_idx,
                    interval_days=3,
                )
            )
            db.session.commit()
            expected_card_id = overdue_card.id

        with patch("app.routes.flashcards.study.datetime") as study_datetime, patch("app.routes.vocabulary.datetime") as vocab_datetime:
            study_datetime.utcnow.return_value = fixed_now
            vocab_datetime.utcnow.return_value = fixed_now

            next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
            self.assertEqual(next_resp.status_code, 200)
            self.assertEqual(next_resp.get_json().get("card_id"), expected_card_id)

            study_resp = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")

        self.assertEqual(study_resp.status_code, 200)
        self.assertIn('<div id="root"></div>', study_resp.get_data(as_text=True))

    def test_vocabulary_study_deck_shows_waiting_state_for_pending_learning(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        create_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 201)

        fixed_now = datetime(2026, 2, 22, 18, 55, 0)
        with self.app.app_context():
            user = User.query.get(self.user_id)
            user.timezone = "Asia/Tokyo"
            card = (
                Card.query.join(Note, Card.note_id == Note.id)
                .filter(Note.deck_id == self.deck_id)
                .first()
            )
            self.assertIsNotNone(card)
            db.session.add(
                CardProgress(
                    user_id=self.user_id,
                    card_id=card.id,
                    queue="learning",
                    due_at=datetime(2026, 2, 22, 19, 0, 0),
                    due_day=datetime(2026, 2, 23).date().toordinal(),
                    interval_days=1,
                    ease_factor=default_deck_options().startingEase,
                    reps=1,
                    lapses=0,
                )
            )
            db.session.commit()

        with patch("app.routes.vocabulary.datetime") as vocab_datetime:
            vocab_datetime.utcnow.return_value = fixed_now
            study_resp = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")
        self.assertEqual(study_resp.status_code, 200)
        html = study_resp.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', html)

    def test_study_answer_uses_persisted_timezone_and_returns_applied_preview(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        create_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "æ°´",
                    "Reading": "ã¿ãš",
                    "Meaning": "water",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 201)

        fixed_now = datetime(2026, 2, 22, 18, 55, 0)
        with patch("app.routes.flashcards.study.datetime") as mock_datetime:
            mock_datetime.utcnow.return_value = fixed_now

            next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
            self.assertEqual(next_resp.status_code, 200)
            next_payload = next_resp.get_json()

            answer_resp = self.client.post(
                f"/api/study/{next_payload['card_id']}/answer",
                json={
                    "rating": "good",
                    "scope": "deck",
                    "scope_id": self.deck_id,
                    "timezone": "Asia/Tokyo",
                },
            )

        self.assertEqual(answer_resp.status_code, 200)
        answer_payload = answer_resp.get_json()
        self.assertEqual(
            answer_payload["applied_interval"]["label"],
            next_payload["intervals_preview"]["good"]["label"],
        )
        self.assertEqual(
            answer_payload["intervals_preview"]["good"]["label"],
            next_payload["intervals_preview"]["good"]["label"],
        )

        with self.app.app_context():
            user = User.query.get(self.user_id)
            self.assertEqual(user.timezone, "UTC")

            progress = CardProgress.query.filter_by(
                user_id=self.user_id,
                card_id=next_payload["card_id"],
            ).first()
            self.assertIsNotNone(progress)
            self.assertEqual(progress.queue, "learning")
            self.assertIsNone(progress.due_day)
            self.assertEqual(progress.due_at, fixed_now + timedelta(minutes=10))

    def test_study_and_browse_exclude_suspended_cards(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "ç©º",
                    "Reading": "ãã‚‰",
                    "Meaning": "sky",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)

        with self.app.app_context():
            card = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck_id).first()
            progress = CardProgress(
                user_id=self.user_id,
                card_id=card.id,
                queue="review",
                due_at=datetime.utcnow() - timedelta(days=1),
                due_day=_day_index(datetime.utcnow(), default_deck_options().dayBoundaryHourLocal),
                is_suspended=True,
                interval_days=3,
            )
            db.session.add(progress)
            db.session.commit()

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        next_payload = next_resp.get_json()
        self.assertIsNone(next_payload.get("card_id"))
        self.assertEqual(next_payload.get("session_state"), "complete")

        browse_resp = self.client.get(f"/vocabulary/api/browse/cards?deck_id={self.deck_id}")
        self.assertEqual(browse_resp.status_code, 200)
        browse_payload = browse_resp.get_json()
        self.assertEqual(browse_payload["total"], 0)

        study_resp = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")
        self.assertEqual(study_resp.status_code, 200)
        self.assertIn('<div id="root"></div>', study_resp.get_data(as_text=True))

    def test_review_due_day_wins_over_stale_due_at_in_study_and_browse(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "ç«",
                    "Reading": "ã²",
                    "Meaning": "fire",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)

        now_utc = datetime.utcnow()
        options = default_deck_options()
        tomorrow_due_day = _day_index(now_utc, options.dayBoundaryHourLocal) + 1
        expected_due_at = _day_index_to_datetime(
            tomorrow_due_day,
            options.dayBoundaryHourLocal,
            timezone_name="UTC",
        )

        with self.app.app_context():
            card = Card.query.join(Note, Card.note_id == Note.id).filter(Note.deck_id == self.deck_id).first()
            progress = CardProgress(
                user_id=self.user_id,
                card_id=card.id,
                queue="review",
                due_at=now_utc - timedelta(days=1),
                due_day=tomorrow_due_day,
                interval_days=5,
            )
            db.session.add(progress)
            db.session.commit()

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        self.assertIsNone(next_resp.get_json().get("card_id"))

        due_resp = self.client.get(f"/vocabulary/api/browse/cards?deck_id={self.deck_id}&status=due")
        self.assertEqual(due_resp.status_code, 200)
        self.assertEqual(due_resp.get_json()["total"], 0)

        all_resp = self.client.get(f"/vocabulary/api/browse/cards?deck_id={self.deck_id}")
        self.assertEqual(all_resp.status_code, 200)
        all_payload = all_resp.get_json()
        self.assertEqual(all_payload["total"], 1)
        self.assertEqual(all_payload["items"][0]["due_at"], expected_due_at.isoformat())

    def test_study_next_returns_sandbox_renderer_payload_for_inline_template_script(self):
        note_type_resp = self.client.post(
            "/api/note-types",
            json={
                "name": "Study Script Guard",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": (
                        "<div>{{Word}}</div>"
                        "<script>window.__study_inline_script_test__=true;"
                        "window.__study_inline_script_side='back';</script>"
                    ),
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(note_type_resp.status_code, 201)
        note_type_id = note_type_resp.get_json()["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72d0",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        payload = next_resp.get_json()
        self.assertIsNotNone(payload.get("card_id"))
        rendered_back = payload.get("rendered_back_html", "")
        self.assertIn("\u72d0", rendered_back)
        self.assertIn("__study_inline_script_test__", rendered_back)
        self.assertIn("<script", rendered_back)
        rendered_back_payload = payload.get("rendered_back_payload") or {}
        self.assertEqual(rendered_back_payload.get("html"), rendered_back)
        self.assertTrue(rendered_back_payload.get("template_key"))
        self.assertEqual(rendered_back_payload.get("shell_key"), rendered_back_payload.get("template_key"))
        self.assertFalse(rendered_back_payload.get("supports_live_patch"))
        self.assertTrue(rendered_back_payload.get("has_inline_script"))

    def test_study_next_payload_allowlists_legacy_audio_button_media(self):
        note_type_resp = self.client.post(
            "/api/note-types",
            json={
                "name": "Study Legacy Audio",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Word_Audio", "field_type": "audio", "position": 1, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": (
                        "<div>{{Word}}</div>"
                        "{{#Word_Audio}}"
                        "<audio id=\"custom-audio\" src=\"{{Word_Audio}}\"></audio>"
                        "<button onclick=\"document.getElementById('custom-audio').play()\">Nghe</button>"
                        "{{/Word_Audio}}"
                    ),
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(note_type_resp.status_code, 201)
        note_type_id = note_type_resp.get_json()["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72d0",
                    "Word_Audio": "",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Word_Audio",
                "file": (io.BytesIO(_MIN_WAV_BYTES), "voice.wav", "audio/wav"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        asset_id = (upload_resp.get_json() or {})["asset_id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id  # type: ignore[union-attr]

        edit_resp = self.client.patch(
            f"/api/study/cards/{card_id}/edit",
            json={"field_values": {"Word_Audio": "voice.wav"}},
        )
        self.assertEqual(edit_resp.status_code, 200)

        next_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
        self.assertEqual(next_resp.status_code, 200)
        payload = next_resp.get_json()
        rendered_back_payload = payload.get("rendered_back_payload") or {}
        allowed_audio_urls = rendered_back_payload.get("allowed_audio_urls") or []
        allowed_audio_asset_ids = rendered_back_payload.get("allowed_audio_asset_ids") or []
        self.assertEqual(len(allowed_audio_urls), 1)
        self.assertEqual(len(allowed_audio_asset_ids), 1)
        self.assertTrue(str(allowed_audio_urls[0]).startswith("/media/proxy/"))
        self.assertIn("custom-audio", rendered_back_payload.get("html") or "")
        self.assertIn(".play()", rendered_back_payload.get("html") or "")

    def test_study_edit_card_updates_note_and_returns_rendered_html(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id  # type: ignore[union-attr]

        edit_resp = self.client.patch(
            f"/api/study/cards/{card_id}/edit",
            json={
                "field_values": {
                    "Word": "\u72ac-edit",
                    "Reading": "\u3044\u306c-edit",
                    "Meaning": "<b>dog edited</b>",
                }
            },
        )
        self.assertEqual(edit_resp.status_code, 200)
        payload = edit_resp.get_json()
        self.assertTrue(payload.get("success"))
        self.assertIn("\u72ac-edit", payload.get("rendered_front_html", ""))
        self.assertIn("\u3044\u306c-edit", payload.get("rendered_back_html", ""))
        self.assertIn("<b>dog edited</b>", payload.get("rendered_back_html", ""))
        self.assertEqual(
            (payload.get("rendered_front_payload") or {}).get("html"),
            payload.get("rendered_front_html", ""),
        )
        self.assertEqual(
            (payload.get("rendered_back_payload") or {}).get("html"),
            payload.get("rendered_back_html", ""),
        )
        self.assertTrue((payload.get("rendered_front_payload") or {}).get("template_key"))
        self.assertTrue((payload.get("rendered_front_payload") or {}).get("supports_live_patch"))
        self.assertTrue((payload.get("rendered_back_payload") or {}).get("template_key"))
        self.assertTrue((payload.get("rendered_back_payload") or {}).get("supports_live_patch"))

        with self.app.app_context():
            note = db.session.get(Note, note_id)
            self.assertIsNotNone(note)
            self.assertEqual(note.field_values.get("Word"), "\u72ac-edit")  # type: ignore[union-attr]
            self.assertEqual(note.field_values.get("Reading"), "\u3044\u306c-edit")  # type: ignore[union-attr]

    def test_study_edit_card_rejects_empty_required_field(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id  # type: ignore[union-attr]

        edit_resp = self.client.patch(
            f"/api/study/cards/{card_id}/edit",
            json={"field_values": {"Word": ""}},
        )
        self.assertEqual(edit_resp.status_code, 400)
        payload = edit_resp.get_json()
        self.assertEqual(payload.get("error"), "VALIDATION_ERROR")
        self.assertEqual(payload.get("field"), "Word")

    def test_study_edit_card_updates_only_changed_fields(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id  # type: ignore[union-attr]

        edit_resp = self.client.patch(
            f"/api/study/cards/{card_id}/edit",
            json={
                "field_values": {
                    "Word": "\u72ac-only-word-updated",
                }
            },
        )
        self.assertEqual(edit_resp.status_code, 200)
        payload = edit_resp.get_json() or {}
        self.assertTrue(payload.get("success"))
        field_values = payload.get("field_values") or {}
        self.assertEqual(field_values.get("Word"), "\u72ac-only-word-updated")
        self.assertEqual(field_values.get("Reading"), "\u3044\u306c")
        self.assertEqual(field_values.get("Meaning"), "dog")

        with self.app.app_context():
            note = db.session.get(Note, note_id)
            self.assertIsNotNone(note)
            values = note.field_values or {}  # type: ignore[union-attr]
            self.assertEqual(values.get("Word"), "\u72ac-only-word-updated")
            self.assertEqual(values.get("Reading"), "\u3044\u306c")
            self.assertEqual(values.get("Meaning"), "dog")

    def test_study_edit_card_accepts_audio_filename_reference(self):
        note_type_resp = self.client.post(
            "/api/note-types",
            json={
                "name": "Study Audio Edit",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Word_Audio", "field_type": "audio", "position": 1, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "<div>{{Word}}</div>",
                    "back_html": "<div>{{Word}}</div>{{{Word_Audio}}}",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(note_type_resp.status_code, 201)
        note_type_id = note_type_resp.get_json()["id"]

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Word_Audio": "",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        upload_resp = self.client.post(
            f"/api/notes/{note_id}/media",
            data={
                "field_name": "Word_Audio",
                "file": (io.BytesIO(_MIN_WAV_BYTES), "voice.wav", "audio/wav"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(upload_resp.status_code, 201)
        asset_id = (upload_resp.get_json() or {})["asset_id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id  # type: ignore[union-attr]

        edit_resp = self.client.patch(
            f"/api/study/cards/{card_id}/edit",
            json={
                "field_values": {
                    "Word_Audio": "voice.wav",
                }
            },
        )
        self.assertEqual(edit_resp.status_code, 200)
        payload = edit_resp.get_json() or {}
        self.assertTrue(payload.get("success"))
        self.assertEqual(
            (payload.get("field_values") or {}).get("Word_Audio"),
            f"/media/proxy/{asset_id}",
        )

    def test_study_edit_card_updates_deck_and_tags(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            target_deck = Deck(name="Target Study Deck")
            db.session.add(target_deck)
            db.session.commit()
            target_deck_id = target_deck.id

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
                "tags": ["JLPT-N5"],
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id

        edit_resp = self.client.patch(
            f"/api/study/cards/{card_id}/edit",
            json={
                "deck_id": target_deck_id,
                "tags": ["JLPT-N4", "Animals"],
            },
        )
        self.assertEqual(edit_resp.status_code, 200)
        payload = edit_resp.get_json() or {}
        self.assertTrue(payload.get("success"))
        self.assertEqual(payload.get("deck_id"), target_deck_id)
        self.assertEqual(payload.get("tags"), ["JLPT-N4", "Animals"])

        with self.app.app_context():
            note = db.session.get(Note, note_id)
            self.assertIsNotNone(note)
            self.assertEqual(note.deck_id, target_deck_id)
            self.assertEqual(note.tags, ["JLPT-N4", "Animals"])

    def test_browse_card_update_accepts_partial_field_values_payload(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]
        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u72ac",
                    "Reading": "\u3044\u306c",
                    "Meaning": "dog",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id  # type: ignore[union-attr]

        patch_resp = self.client.patch(
            f"/vocabulary/api/browse/cards/{card_id}",
            json={
                "field_values": {
                    "Word": "\u72ac-browse-updated",
                }
            },
        )
        self.assertEqual(patch_resp.status_code, 200)
        payload = patch_resp.get_json() or {}
        detail_values = ((payload.get("detail") or {}).get("note") or {}).get("field_values") or {}
        self.assertEqual(detail_values.get("Word"), "\u72ac-browse-updated")
        self.assertEqual(detail_values.get("Reading"), "\u3044\u306c")
        self.assertEqual(detail_values.get("Meaning"), "dog")

        with self.app.app_context():
            note = db.session.get(Note, note_id)
            self.assertIsNotNone(note)
            values = note.field_values or {}  # type: ignore[union-attr]
            self.assertEqual(values.get("Word"), "\u72ac-browse-updated")
            self.assertEqual(values.get("Reading"), "\u3044\u306c")
            self.assertEqual(values.get("Meaning"), "dog")

    def test_browse_batch_delete_removes_owned_cards_and_orphaned_notes(self):
        note_type_id = self._create_note_type()["id"]
        note_ids = []
        card_ids = []

        for word in ("\u72ac", "\u732b"):
            note_response = self.client.post(
                "/api/notes",
                json={
                    "note_type_id": note_type_id,
                    "deck_id": self.deck_id,
                    "field_values": {
                        "Word": word,
                        "Reading": "reading",
                        "Meaning": "meaning",
                    },
                },
            )
            self.assertEqual(note_response.status_code, 201)
            note_id = note_response.get_json()["id"]
            note_ids.append(note_id)
            with self.app.app_context():
                card = Card.query.filter_by(note_id=note_id).one()
                card_ids.append(card.id)

        invalid_response = self.client.post(
            "/api/browse/cards/batch-delete",
            json={"card_ids": card_ids[0]},
        )
        self.assertEqual(invalid_response.status_code, 400)
        self.assertEqual(invalid_response.get_json()["field"], "card_ids")

        invalid_payload_response = self.client.post(
            "/api/browse/cards/batch-delete",
            json=[],
        )
        self.assertEqual(invalid_payload_response.status_code, 400)
        self.assertEqual(
            invalid_payload_response.get_json()["code"],
            "VALIDATION_ERROR",
        )

        response = self.client.post(
            "/api/browse/cards/batch-delete",
            json={"card_ids": card_ids},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.get_json(),
            {"success": True, "deleted_count": 2},
        )
        with self.app.app_context():
            self.assertEqual(Card.query.filter(Card.id.in_(card_ids)).count(), 0)
            self.assertEqual(Note.query.filter(Note.id.in_(note_ids)).count(), 0)

    def test_browse_card_update_can_move_owned_card_to_another_deck(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            target_deck = Deck(name="Deck B")
            db.session.add(target_deck)
            db.session.commit()
            target_deck_id = target_deck.id

        note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "\u732b",
                    "Reading": "\u306d\u3053",
                    "Meaning": "cat",
                },
            },
        )
        self.assertEqual(note_resp.status_code, 201)
        note_id = note_resp.get_json()["id"]

        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id).first()
            self.assertIsNotNone(card)
            card_id = card.id  # type: ignore[union-attr]

        patch_resp = self.client.patch(
            f"/vocabulary/api/browse/cards/{card_id}",
            json={"deck_id": target_deck_id},
        )
        self.assertEqual(patch_resp.status_code, 200)
        payload = patch_resp.get_json() or {}
        self.assertEqual(((payload.get("row") or {}).get("deck_id")), target_deck_id)
        self.assertEqual(((payload.get("row") or {}).get("deck_name")), "Deck B")
        self.assertEqual(((payload.get("detail") or {}).get("note") or {}).get("deck_id"), target_deck_id)

        with self.app.app_context():
            note = db.session.get(Note, note_id)
            self.assertIsNotNone(note)
            self.assertEqual(note.deck_id, target_deck_id)  # type: ignore[union-attr]

    def test_flashcard_import_parse_and_execute_upsert(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        parse_resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "custom",
                "custom_delimiter": "|",
                "has_header": "1",
                "file": (
                    io.BytesIO(
                        "Word|Reading|Meaning\n犬|いぬ|dog\n猫|ねこ|cat\n".encode("utf-8")
                    ),
                    "bulk-import.txt",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json()
        self.assertTrue(parse_payload.get("token"))
        self.assertEqual(parse_payload.get("total_rows"), 2)

        execute_resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": "upsert",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        result = execute_resp.get_json()
        summary = result.get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 2)
        self.assertEqual(int(summary.get("updated") or 0), 0)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            note_count = Note.query.filter_by(user_id=self.user_id, note_type_id=note_type_id).count()
            card_count = (
                db.session.query(Card)
                .join(Note, Card.note_id == Note.id)
                .filter(Note.user_id == self.user_id, Note.note_type_id == note_type_id)
                .count()
            )
            self.assertEqual(note_count, 2)
            self.assertGreaterEqual(card_count, 2)

    def test_flashcard_import_update_only_respects_dont_overwrite_empty(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        create_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog-old",
                },
            },
        )
        self.assertEqual(create_resp.status_code, 201)

        parse_resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "has_header": "1",
                "file": (
                    io.BytesIO(
                        "Word,Reading,Meaning\n犬,,dog-new\n".encode("utf-8")
                    ),
                    "update.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json()

        execute_resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": "update_only",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        result = execute_resp.get_json()
        summary = result.get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 0)
        self.assertEqual(int(summary.get("updated") or 0), 1)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            note = Note.query.filter_by(user_id=self.user_id, note_type_id=note_type_id).first()
            self.assertIsNotNone(note)
            values = note.field_values or {}
            self.assertEqual(values.get("Word"), "犬")
            self.assertEqual(values.get("Reading"), "いぬ")
            self.assertEqual(values.get("Meaning"), "dog-new")

    def test_flashcard_import_txt_preamble_uses_separator_directive(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        parse_resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "has_header": "0",
                "file": (
                    io.BytesIO(
                        (
                            "#separator:tab\n"
                            "#html:true\n"
                            "#tags column:16\n"
                            "\\u72ac\\t\\u3044\\u306c\\t<b>dog</b>\n"
                            "\\u732b\\t\\u306d\\u3053\\tcat\n"
                        ).encode("utf-8").decode("unicode_escape").encode("utf-8")
                    ),
                    "anki-export.txt",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json() or {}
        self.assertEqual(parse_payload.get("delimiter"), "\t")
        self.assertEqual(parse_payload.get("column_count"), 3)
        self.assertEqual(parse_payload.get("total_rows"), 2)
        preview_rows = parse_payload.get("preview_rows") or []
        self.assertEqual(preview_rows[0][0], "犬")
        self.assertEqual(preview_rows[0][2], "<b>dog</b>")

        execute_resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": self.deck_id,
                "import_mode": "upsert",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        result = execute_resp.get_json() or {}
        summary = result.get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 2)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            imported = (
                Note.query.filter_by(
                    user_id=self.user_id,
                    note_type_id=note_type_id,
                    deck_id=self.deck_id,
                )
                .order_by(Note.id.asc())
                .all()
            )
            self.assertEqual(len(imported), 2)
            values_by_word = {
                str((note.field_values or {}).get("Word")): (note.field_values or {})
                for note in imported
            }
            self.assertEqual(values_by_word["犬"].get("Meaning"), "<b>dog</b>")
            self.assertEqual(values_by_word["猫"].get("Meaning"), "cat")

    def test_flashcard_import_insert_only_scoped_to_target_deck(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        with self.app.app_context():
            deck_b = Deck(name="Deck B")
            db.session.add(deck_b)
            db.session.commit()
            deck_b_id = deck_b.id

        existing_note_resp = self.client.post(
            "/api/notes",
            json={
                "note_type_id": note_type_id,
                "deck_id": self.deck_id,
                "field_values": {
                    "Word": "犬",
                    "Reading": "いぬ",
                    "Meaning": "dog-existing",
                },
            },
        )
        self.assertEqual(existing_note_resp.status_code, 201)

        parse_resp = self.client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "has_header": "1",
                "file": (
                    io.BytesIO("Word,Reading,Meaning\n犬,いぬ,dog-import\n".encode("utf-8")),
                    "insert-only.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json()

        execute_resp = self.client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": deck_b_id,
                "import_mode": "insert_only",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        result = execute_resp.get_json()
        summary = result.get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 1)
        self.assertEqual(int(summary.get("skipped") or 0), 0)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            deck_a_count = Note.query.filter_by(
                user_id=self.user_id,
                note_type_id=note_type_id,
                deck_id=self.deck_id,
            ).count()
            deck_b_count = Note.query.filter_by(
                user_id=self.user_id,
                note_type_id=note_type_id,
                deck_id=deck_b_id,
            ).count()
            self.assertEqual(deck_a_count, 1)
            self.assertEqual(deck_b_count, 1)

    def test_flashcard_import_allows_non_admin_with_own_note_type(self):
        with self.app.app_context():
            learner = User(username="import-learner", email="import-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()

            nt = NoteType(user_id=learner.id, name="Learner Vocab")
            db.session.add(nt)
            db.session.flush()
            db.session.add(FieldDef(note_type_id=nt.id, name="Word", position=0))
            db.session.add(FieldDef(note_type_id=nt.id, name="Meaning", position=1))
            db.session.commit()
            note_type_id = nt.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "import-learner@example.com", "password": "password"},
            follow_redirects=True,
        )

        parse_resp = learner_client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "file": (io.BytesIO(b"Word,Meaning\n"), "test.csv"),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)

    def test_flashcard_import_page_renders(self):
        response = self.client.get("/flashcards/import")
        self.assertEqual(response.status_code, 200)

    def test_flashcard_import_options_returns_options_json(self):
        response = self.client.get("/api/flashcards/import/options")
        self.assertEqual(response.status_code, 200)
        data = response.get_json() or {}
        self.assertIn("deck_options", data)
        self.assertIn("note_type_options", data)
        self.assertIn("uniqueness_defaults", data)

    def test_flashcard_import_options_preselects_specified_deck_id(self):
        with self.app.app_context():
            deck = Deck(name="Target Import Deck", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.commit()
            deck_id = deck.id

        response = self.client.get(f"/api/flashcards/import/options?deck_id={deck_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json() or {}
        self.assertEqual(data.get("initial_deck_id"), deck_id)

    def test_shared_note_type_rate_is_limited_to_two_submissions_per_user(self):
        with self.app.app_context():
            owner = User(username="nt-owner", email="nt-owner@example.com", is_admin=False)
            owner.set_password("password")
            learner = User(username="nt-rater", email="nt-rater@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add_all([owner, learner])
            db.session.flush()
            learner_id = learner.id

            note_type = NoteType(
                user_id=owner.id,
                name="Rate Limit NoteType",
                description="desc",
                primary_category="General",
                preview_text="preview",
                pricing_mode="free",
                price_amount_minor=0,
                publish_status="published",
                version="1.0.0",
            )
            db.session.add(note_type)
            db.session.commit()
            note_type_id = note_type.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "nt-rater@example.com", "password": "password"},
            follow_redirects=True,
        )

        with patch(
            "app.services.marketplace_note_type_service."
            "flashcards_share_service.can_user_rate_note_type",
            return_value=True,
        ):
            first_resp = learner_client.post(
                f"/api/shared/note-types/{note_type_id}/rate",
                json={"rating": 5, "comment": "first"},
            )
            self.assertEqual(first_resp.status_code, 200)

            second_resp = learner_client.post(
                f"/api/shared/note-types/{note_type_id}/rate",
                json={"rating": 4, "comment": "second"},
            )
            self.assertEqual(second_resp.status_code, 200)

            third_resp = learner_client.post(
                f"/api/shared/note-types/{note_type_id}/rate",
                json={"rating": 3, "comment": "third"},
            )
            self.assertEqual(third_resp.status_code, 403)

            detail_resp = learner_client.get(f"/api/shared/note-types/{note_type_id}")
            self.assertEqual(detail_resp.status_code, 200)
            detail_payload = detail_resp.get_json() or {}
            self.assertEqual(int(detail_payload.get("review_submission_count") or 0), 2)
            self.assertEqual(int(detail_payload.get("review_submissions_remaining") or 0), 0)
            self.assertFalse(bool(detail_payload.get("can_rate")))

        with self.app.app_context():
            review = NoteTypeReview.query.filter_by(note_type_id=note_type_id, user_id=learner_id).first()
            self.assertIsNotNone(review)
            self.assertEqual(review.rating, 4)
            self.assertEqual(review.comment, "second")

    def test_shared_deck_rate_is_limited_to_two_submissions_per_user(self):
        with self.app.app_context():
            owner = User(username="deck-owner", email="deck-owner@example.com", is_admin=False)
            owner.set_password("password")
            learner = User(username="deck-rater", email="deck-rater@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add_all([owner, learner])
            db.session.flush()
            learner_id = learner.id

            deck_item = DeckMarketplaceItem(
                owner_user_id=owner.id,
                title="Rate Limit Deck",
                description="desc",
                primary_category="General",
                tags=[],
                preview_text="preview",
                pricing_mode="free",
                price_amount_minor=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "deck-rater@example.com", "password": "password"},
            follow_redirects=True,
        )

        with patch("app.routes.flashcards.share._can_user_rate_deck", return_value=True):
            first_resp = learner_client.post(
                f"/api/shared/decks/{deck_item_id}/rate",
                json={"rating": 5, "comment": "first"},
            )
            self.assertEqual(first_resp.status_code, 200)

            second_resp = learner_client.post(
                f"/api/shared/decks/{deck_item_id}/rate",
                json={"rating": 4, "comment": "second"},
            )
            self.assertEqual(second_resp.status_code, 200)

            third_resp = learner_client.post(
                f"/api/shared/decks/{deck_item_id}/rate",
                json={"rating": 3, "comment": "third"},
            )
            self.assertEqual(third_resp.status_code, 403)

            detail_resp = learner_client.get(f"/api/shared/decks/{deck_item_id}")
            self.assertEqual(detail_resp.status_code, 200)
            detail_payload = detail_resp.get_json() or {}
            self.assertEqual(int(detail_payload.get("review_submission_count") or 0), 2)
            self.assertEqual(int(detail_payload.get("review_submissions_remaining") or 0), 0)
            self.assertFalse(bool(detail_payload.get("can_rate")))

        with self.app.app_context():
            review = DeckReview.query.filter_by(deck_item_id=deck_item_id, user_id=learner_id).first()
            self.assertIsNotNone(review)
            self.assertEqual(review.rating, 4)
            self.assertEqual(review.comment, "second")


if __name__ == "__main__":
    unittest.main()
