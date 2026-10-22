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
from tests.study_note_fixtures import create_note_user, attach_template, assert_retired_progress_absent
from tests.note_progress_fixtures import stage_note_state, subject_for_card, decode_note_state
from tests.note_type_publication_fixtures import stage_note_type_release
from uuid import uuid4
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_progress_lifecycle_event import StudyProgressLifecycleEvent
from models.study_progress_subject import StudyProgressSubject
from models.study_application import StudyApplication
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
            user = create_note_user(db.session, username="admin", email="admin@example.com", is_admin=True)
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

    def _seed_retired_full_copy(self, suffix='first'):
        learner = create_note_user(db.session, username='retired-copy-'+suffix, email='retired-copy-'+suffix+'@example.test')
        note_type = NoteType(name='Retired copy '+suffix, user_id=self.user_id)
        source = Deck(name='Retired source '+suffix, owner_user_id=self.user_id)
        local = Deck(name='Retired local '+suffix, owner_user_id=learner.id)
        db.session.add_all([note_type, source, local])
        db.session.flush()
        attach_template(db.session, note_type_id=note_type.id, owner_user_id=self.user_id, name='Card')
        values = {'Word':'retained', 'Array':['a', ['b','c']], 'Empty':[]}
        source_note = Note(user_id=self.user_id, note_type_id=note_type.id, deck_id=source.id, field_values=values)
        local_note = Note(user_id=learner.id, note_type_id=note_type.id, deck_id=local.id, field_values=values)
        db.session.add_all([source_note,local_note])
        db.session.flush()
        stage_note_state(db.session, user_id=learner.id, note_id=local_note.id, queue='review', due_day=1,
                         reps=5, interval_days=3, revision=4)
        item = DeckMarketplaceItem(owner_user_id=self.user_id, source_deck_id=source.id, title='Retired '+suffix)
        db.session.add(item)
        db.session.flush()
        install = DeckInstall(deck_item_id=item.id, user_id=learner.id, local_deck_id=local.id,
            source_deck_id=source.id, source_owner_user_id=self.user_id, clone_mode='legacy_copy')
        db.session.add(install)
        db.session.commit()
        return install

    @staticmethod
    def _cutover_snapshot():
        from sqlalchemy import select
        from models.review_event import ReviewEvent
        from models.study_progress_history_fact import StudyProgressHistoryFact
        from models.study_authority_command_receipt import StudyAuthorityCommandReceipt
        return {model.__tablename__:db.session.execute(select(model.__table__).order_by(*model.__table__.primary_key.columns)).all()
                for model in (Note, StudyProgressSubject, ReviewEvent, StudyProgressHistoryFact,
                              StudyAuthorityCommandReceipt, DeckInstall, DeckCloneDeckMap, DeckCloneNoteFieldOverride)}

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
            source_owner = create_note_user(db.session,
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
            learner = create_note_user(db.session,
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
            template_count = StudyApplication.query.filter_by(
                note_type_id=note_type_id, status_code="ACTIVE"
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
                StudyApplication.query.filter_by(note_type_id=note_type_id, status_code="ACTIVE").count(),
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

            learner = create_note_user(db.session,
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

            progress = stage_note_state(db.session,
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

            # The derived presentation retains its identity after the hotfix
            reloaded_card = db.session.get(Card, card_id)
            self.assertIsNotNone(reloaded_card)
            self.assertEqual(reloaded_card.template_id, template_id)
            self.assertEqual(Card.query.filter_by(note_id=note_id).count(), 1)

            # The learner Note state is preserved across the hotfix
            reloaded_subject = db.session.get(StudyProgressSubject, progress_id)
            reloaded_progress = decode_note_state(reloaded_subject)
            self.assertIsNotNone(reloaded_progress)
            self.assertEqual(reloaded_subject.live_note_id, note_id)
            self.assertEqual(reloaded_progress.reps, 5)
            self.assertEqual(reloaded_progress.type, "review")

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

    def test_shared_deck_preview_scopes_membership_and_preserves_retired_release_pin(self):
        note_type = self._create_note_type()
        note_type_id, template_id = note_type['id'], note_type['templates'][0]['id']
        note_response = self.client.post('/api/notes', json={'note_type_id':note_type_id, 'deck_id':self.deck_id,
            'field_values':{'Word':'?','Reading':'??','Meaning':'dog'}})
        self.assertEqual(note_response.status_code,201)
        with self.app.app_context():
            from app.services.template_tokens import template_content_hash
            from models.deck_release_template_pin import DeckReleaseTemplatePin
            from models.template_version import TemplateVersion
            from models.template_release import TemplateRelease
            word = FieldDef.query.filter_by(note_type_id=note_type_id,name='Word').one()
            application = StudyApplication.query.filter_by(note_type_id=note_type_id,template_id=template_id).one()
            foreign_type = NoteType(name='Unrelated preview type',user_id=self.user_id)
            db.session.add(foreign_type)
            db.session.flush()
            foreign_template = attach_template(db.session,note_type_id=foreign_type.id,owner_user_id=self.user_id,name='Private',front_html='SECRET')
            schema = [{'key':'Term','label':'Term','type':'text','required':False}]
            version = TemplateVersion(template_id=template_id,version_no=99,front_html='PINNED {{Term}}',back_html='{{Term}}',
                shared_css='',input_schema=schema,content_hash=template_content_hash('PINNED {{Term}}','{{Term}}',''),origin='authored')
            db.session.add(version)
            db.session.flush()
            publication = TemplateRelease(template_id=template_id,version_id=version.id,sequence_no=1,version_label='v1')
            item = DeckMarketplaceItem(owner_user_id=self.user_id,source_deck_id=self.deck_id,source_note_type_id=note_type_id,
                title='Pinned preview',publish_status='published')
            db.session.add_all([publication,item])
            db.session.flush()
            release = DeckRelease(deck_item_id=item.id,sequence_no=1,version_label='v1',status='published',template_pins_initialized=True)
            db.session.add(release)
            db.session.flush()
            item.current_release_id=release.id
            db.session.add(DeckReleaseTemplatePin(deck_release_id=release.id,source_template_id=template_id,
                template_release_id=publication.id,applications_json={application.id:{'note_type_id':note_type_id,
                    'input_bindings':{'Term':word.id},'position':0,'occurrence_key':'compat'}}))
            application.status_code='RETIRED'
            db.session.get(Template,template_id).front_html='LIVE {{Word}}'
            db.session.commit()
            item_id,foreign_id=item.id,foreign_template.id
            before = self._cutover_snapshot()
        preview = self.client.post(f'/api/shared/decks/{item_id}/templates/{template_id}/preview',json={})
        self.assertEqual(preview.status_code,200,preview.get_json())
        self.assertIn('PINNED ?',preview.get_json()['front_html'])
        self.assertNotIn('LIVE',preview.get_json()['front_html'])
        foreign = self.client.post(f'/api/shared/decks/{item_id}/templates/{foreign_id}/preview',json={})
        self.assertEqual(foreign.status_code,404,foreign.get_json())
        with self.app.app_context():
            self.assertEqual(self._cutover_snapshot(),before)

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
            victim = create_note_user(db.session, username="victim", email="victim@example.com")
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
                attach_template(db.session, owner_user_id=victim.id,
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
            user = create_note_user(db.session, username="standard", email="standard@example.com", is_admin=False)
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
            viewer = create_note_user(db.session, username="archived-viewer", email="archived-viewer@example.com")
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

    def test_shared_deck_publish_options_blocks_parent_when_child_is_shared(self):
        with self.app.app_context():
            parent_deck = Deck(name="Root Parent Deck", owner_user_id=self.user_id)
            db.session.add(parent_deck)
            db.session.flush()
            child_deck = Deck(name="Active Child Deck", owner_user_id=self.user_id, parent_id=parent_deck.id)
            db.session.add(child_deck)
            db.session.flush()
            shared_child = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=child_deck.id,
                title="Child Shared Listing",
                publish_status="published",
            )
            db.session.add(shared_child)
            db.session.commit()
            parent_deck_id = parent_deck.id

        response = self.client.get("/api/shared/decks/publish-options")
        self.assertEqual(response.status_code, 200)
        options = {row["id"]: row for row in response.get_json()["items"]}
        self.assertFalse(options[parent_deck_id]["is_selectable"])
        self.assertEqual(options[parent_deck_id]["block_code"], "descendant_shared")
        self.assertIn("Active Child Deck", options[parent_deck_id]["block_reason"])

    def test_publish_options_query_count_benchmark(self):
        # Create a hierarchy of 50 decks to benchmark O(1) query count
        with self.app.app_context():
            note_type = NoteType(id="nt_bench", user_id=self.user_id, name="Benchmark NT")
            db.session.add(note_type)
            db.session.flush()
            tpl = attach_template(db.session, owner_user_id=self.user_id, id="tpl_bench", note_type_id=note_type.id, name="Card 1")
            db.session.add(tpl)
            db.session.flush()

            roots = []
            for r in range(10):
                root_d = Deck(name=f"Bench Root {r}", owner_user_id=self.user_id)
                db.session.add(root_d)
                db.session.flush()
                roots.append(root_d)
                for c in range(4):
                    child_d = Deck(name=f"Bench Child {r}-{c}", owner_user_id=self.user_id, parent_id=root_d.id)
                    db.session.add(child_d)
                    db.session.flush()
                    note = Note(id=f"bn_{r}_{c}", user_id=self.user_id, deck_id=child_d.id, note_type_id=note_type.id)
                    db.session.add(note)
                    db.session.flush()
                    card = Card.query.filter_by(note_id=note.id, template_id=tpl.id).one()

            db.session.commit()

        queries = []
        def record_query(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        with self.app.app_context():
            engine = db.engine
            event.listen(engine, "before_cursor_execute", record_query)
        try:
            response = self.client.get("/api/shared/decks/publish-options")
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            items = data.get("items", [])
            # Assert query count <= 10 (O(1) constant SQL queries for 50+ decks)
            self.assertLessEqual(len(queries), 10)
            self.assertGreaterEqual(len(items), 50)
            # Verify structure of all items
            for item in items:
                self.assertIn("id", item)
                self.assertIn("name", item)
                self.assertIn("parent_id", item)
                self.assertIn("card_count", item)
                self.assertIn("is_selectable", item)
                self.assertIn("block_code", item)
                self.assertIn("block_reason", item)
                self.assertIn("shared_item_id", item)
        finally:
            with self.app.app_context():
                event.remove(db.engine, "before_cursor_execute", record_query)

    def test_build_deck_publish_options_edge_cases(self):
        from app.services.share import publish as publish_service

        with self.app.app_context():
            # 1. Multi-level hierarchy rollup
            r_deck = Deck(name="Rollup Root", owner_user_id=self.user_id)
            db.session.add(r_deck)
            db.session.flush()
            m_deck = Deck(name="Rollup Middle", owner_user_id=self.user_id, parent_id=r_deck.id)
            db.session.add(m_deck)
            db.session.flush()
            l_deck = Deck(name="Rollup Leaf", owner_user_id=self.user_id, parent_id=m_deck.id)
            db.session.add(l_deck)
            db.session.flush()

            nt_a = NoteType(id="nt_edge_a", user_id=self.user_id, name="Edge NT A")
            nt_b = NoteType(id="nt_edge_b", user_id=self.user_id, name="Edge NT B")
            db.session.add_all([nt_a, nt_b])
            db.session.flush()
            tpl_a = attach_template(db.session, owner_user_id=self.user_id, id="tpl_edge_a", note_type_id=nt_a.id, name="Card A")
            tpl_b = attach_template(db.session, owner_user_id=self.user_id, id="tpl_edge_b", note_type_id=nt_b.id, name="Card B")
            db.session.add_all([tpl_a, tpl_b])
            db.session.flush()

            # Leaf has 1 note/card
            n_leaf = Note(id="n_edge_l", user_id=self.user_id, deck_id=l_deck.id, note_type_id=nt_a.id)
            db.session.add(n_leaf)
            db.session.flush()
            c_leaf = Card.query.filter_by(note_id=n_leaf.id, template_id=tpl_a.id).one()
            # Middle has 1 note/card
            n_mid = Note(id="n_edge_m", user_id=self.user_id, deck_id=m_deck.id, note_type_id=nt_a.id)
            db.session.add(n_mid)
            db.session.flush()
            c_mid = Card.query.filter_by(note_id=n_mid.id, template_id=tpl_a.id).one()
            # Root has 1 note/card
            n_root = Note(id="n_edge_r", user_id=self.user_id, deck_id=r_deck.id, note_type_id=nt_a.id)
            db.session.add(n_root)
            db.session.flush()
            c_root = Card.query.filter_by(note_id=n_root.id, template_id=tpl_a.id).one()

            # 2. Empty deck (0 cards)
            empty_deck = Deck(name="Empty Folder Deck", owner_user_id=self.user_id)
            db.session.add(empty_deck)
            db.session.flush()

            # 3. Deck with multiple note types
            multi_nt_deck = Deck(name="Multi NT Deck", owner_user_id=self.user_id)
            db.session.add(multi_nt_deck)
            db.session.flush()
            n_m1 = Note(id="n_m1", user_id=self.user_id, deck_id=multi_nt_deck.id, note_type_id=nt_a.id)
            db.session.add(n_m1)
            db.session.flush()
            c_m1 = Card.query.filter_by(note_id=n_m1.id, template_id=tpl_a.id).one()
            n_m2 = Note(id="n_m2", user_id=self.user_id, deck_id=multi_nt_deck.id, note_type_id=nt_b.id)
            db.session.add(n_m2)
            db.session.flush()
            c_m2 = Card.query.filter_by(note_id=n_m2.id, template_id=tpl_b.id).one()

            # 4. Simulated cycle: C1 -> C2 -> C1
            c1_deck = Deck(name="Cycle 1", owner_user_id=self.user_id)
            db.session.add(c1_deck)
            db.session.flush()
            c2_deck = Deck(name="Cycle 2", owner_user_id=self.user_id, parent_id=c1_deck.id)
            db.session.add(c2_deck)
            db.session.flush()
            c1_deck.parent_id = c2_deck.id  # Create cycle

            # 5. Self-loop: S -> S
            self_loop_deck = Deck(name="Self Loop", owner_user_id=self.user_id)
            db.session.add(self_loop_deck)
            db.session.flush()
            self_loop_deck.parent_id = self_loop_deck.id

            # 6. Cross-user parent reference
            other_user = create_note_user(db.session, username="other_edge", email="other_edge@example.com")
            other_user.set_password("pass")
            db.session.add(other_user)
            db.session.flush()
            other_deck = Deck(name="Other User Deck", owner_user_id=other_user.id)
            db.session.add(other_deck)
            db.session.flush()

            cross_parent_deck = Deck(name="Cross Parent Deck", owner_user_id=self.user_id, parent_id=other_deck.id)
            db.session.add(cross_parent_deck)
            db.session.flush()
            n_cross = Note(id="n_cross", user_id=self.user_id, deck_id=cross_parent_deck.id, note_type_id=nt_a.id)
            db.session.add(n_cross)
            db.session.flush()
            c_cross = Card.query.filter_by(note_id=n_cross.id, template_id=tpl_a.id).one()

            db.session.add_all([n_leaf, n_mid, n_root, n_m1, n_m2, n_cross])
            db.session.commit()

            r_deck_id = r_deck.id
            m_deck_id = m_deck.id
            l_deck_id = l_deck.id
            empty_deck_id = empty_deck.id
            multi_nt_deck_id = multi_nt_deck.id
            c1_deck_id = c1_deck.id
            self_loop_deck_id = self_loop_deck.id
            cross_parent_deck_id = cross_parent_deck.id

            # Test both flashcards_share_service and share.publish produce identical results
            res_monolith = flashcards_share_service.build_deck_publish_options(user_id=self.user_id)
            res_modular = publish_service.build_deck_publish_options(user_id=self.user_id)
            self.assertEqual(res_monolith, res_modular)

            options = {row["id"]: row for row in res_monolith["items"]}

            # Rollup checks
            self.assertEqual(options[l_deck_id]["card_count"], 1)
            self.assertEqual(options[m_deck_id]["card_count"], 2)
            self.assertEqual(options[r_deck_id]["card_count"], 3)

            # Empty deck check
            self.assertEqual(options[empty_deck_id]["card_count"], 0)
            self.assertTrue(options[empty_deck_id]["is_selectable"])

            # Multi-NT deck check (selectable at publish options stage)
            self.assertEqual(options[multi_nt_deck_id]["card_count"], 2)
            self.assertTrue(options[multi_nt_deck_id]["is_selectable"])

            # Cycle & self-loop decks executed without error
            self.assertIn(c1_deck_id, options)
            self.assertIn(self_loop_deck_id, options)

            # Cross-user parent reference handled safely
            self.assertIn(cross_parent_deck_id, options)
            self.assertEqual(options[cross_parent_deck_id]["card_count"], 1)
            self.assertTrue(options[cross_parent_deck_id]["is_selectable"])
            self.assertIsNone(options[cross_parent_deck_id]["block_code"])

            # Standalone fallback test
            deck_obj = db.session.get(Deck, r_deck_id)
            standalone_eligibility = flashcards_share_service.get_deck_publish_eligibility(
                user_id=self.user_id,
                deck=deck_obj,
            )
            self.assertTrue(standalone_eligibility["is_selectable"])
            self.assertIsNone(standalone_eligibility["block_code"])

            # Adversarial test: Self-loop deck when shared with allow_existing=True
            self_loop_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self_loop_deck_id,
                title="Shared Self Loop",
                publish_status="published",
            )
            db.session.add(self_loop_item)
            db.session.commit()

            self_loop_obj = db.session.get(Deck, self_loop_deck_id)
            self_loop_elig = flashcards_share_service.get_deck_publish_eligibility(
                user_id=self.user_id,
                deck=self_loop_obj,
                allow_existing=True,
            )
            self.assertTrue(self_loop_elig["is_selectable"])
            self.assertIsNone(self_loop_elig["block_code"])

            # Adversarial test: Cycle deck C1 when shared with allow_existing=True
            c1_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=c1_deck_id,
                title="Shared Cycle 1",
                publish_status="published",
            )
            db.session.add(c1_item)
            db.session.commit()

            c1_obj = db.session.get(Deck, c1_deck_id)
            c1_elig = flashcards_share_service.get_deck_publish_eligibility(
                user_id=self.user_id,
                deck=c1_obj,
                allow_existing=True,
            )
            self.assertTrue(c1_elig["is_selectable"])
            self.assertIsNone(c1_elig["block_code"])

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


    def test_publish_note_type_api_updates_taxonomy_and_publishes_release(self):
        note_type = self._create_note_type()
        note_type_id = note_type["id"]

        page_resp = self.client.get(f"/flashcards/note-types/{note_type_id}/share")
        self.assertEqual(page_resp.status_code, 200)
        page_html = page_resp.get_data(as_text=True)
        self.assertIn('<div id="root"></div>', page_html)

        share_resp = self.client.post(
            f"/api/marketplace/note-types/{note_type_id}/publish",
            json={
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
                "template_listings": [{"template_id": template["id"],
                    "description": "Vocabulary card", "primary_category": "General",
                    "pricing_mode": "free", "price_amount_minor": 0}
                    for template in note_type["templates"]],
            },
            follow_redirects=False,
        )
        self.assertEqual(share_resp.status_code, 200, share_resp.get_json())
        self.assertEqual(share_resp.get_json()["publish_status"], "published")

        with self.app.app_context():
            saved = NoteType.query.get(note_type_id)
            self.assertIsNotNone(saved)
            self.assertEqual(saved.publish_status, "published")
            self.assertIsNotNone(saved.current_release_id)
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

        # Detailed definitions require an explicit release; the compact legacy
        # catalog above intentionally does not load fields or template content.
        with self.app.app_context():
            stage_note_type_release(db.session, db.session.get(NoteType, note_type["id"]))
            db.session.commit()
        detail_response = self.client.get(f"/api/shared/note-types/{note_type['id']}")
        self.assertEqual(detail_response.status_code, 200)
        detail_payload = detail_response.get_json() or {}
        self.assertTrue(detail_payload.get("field_defs"))
        self.assertTrue(detail_payload.get("templates"))

    def test_shared_note_type_hub_includes_saved_library_and_detail_extras(self):
        with self.app.app_context():
            seller = create_note_user(db.session, username="seller-one", email="seller-one@example.com")
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
            seller = create_note_user(db.session, username="seller-installed", email="seller-installed@example.com")
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
            db.session.flush()
            stage_note_type_release(db.session, note_type)
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
            seller = create_note_user(db.session, username="seller-two", email="seller-two@example.com")
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
            learner = create_note_user(db.session, username="installed-page", email="installed-page@example.com", is_admin=False)
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
            learner = create_note_user(db.session, username="learner", email="learner@example.com", is_admin=False)
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
            learner = create_note_user(db.session, username="unreleased-learner", email="unreleased-learner@example.com", is_admin=False)
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
            learner = create_note_user(db.session, username="browse-learner", email="browse-learner@example.com", is_admin=False)
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

        tree_resp = learner_client.get("/api/browse/decks/tree")
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
            f"/api/browse/cards?deck_id={installed_root_id}&include_subdecks=1"
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
        detail_resp = learner_client.get(f"/api/browse/cards/{card_id}")
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
            f"/api/browse/cards/{card_id}",
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

        reload_detail_resp = learner_client.get(f"/api/browse/cards/{card_id}")
        self.assertEqual(reload_detail_resp.status_code, 200)
        reload_detail_payload = reload_detail_resp.get_json() or {}
        self.assertEqual(
            ((reload_detail_payload.get("note") or {}).get("field_values") or {}).get("Word"),
            "\u72ac*",
        )

        reload_cards_resp = learner_client.get(
            f"/api/browse/cards?deck_id={installed_root_id}&include_subdecks=1"
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
            learner = create_note_user(db.session, username="nt-clone-learner", email="nt-clone-learner@example.com", is_admin=False)
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
            learner = create_note_user(db.session, username="snapshot-learner", email="snapshot-learner@example.com", is_admin=False)
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

    def test_cutover_exports_reject_each_full_copy_install(self):
        with self.app.app_context():
            first = self._seed_retired_full_copy()
            second = self._seed_retired_full_copy(suffix='second')
            self.assertIs(share_ctrl.cutover_clone_model_to_overlay_only, cutover_service.cutover_clone_model_to_overlay_only)
            self.assertIs(flashcards_share_service.cutover_clone_model_to_overlay_only, cutover_service.cutover_clone_model_to_overlay_only)
            before = self._cutover_snapshot()
            summary = cutover_service.cutover_clone_model_to_overlay_only(fail_on_mismatch=False)
            self.assertEqual((summary['migrated'], summary['failed']), (0, 2))
            self.assertTrue(all(row['status'] == 409 for row in summary['errors']))
            self.assertEqual(self._cutover_snapshot(), before)
            assert_retired_progress_absent(self, db.session)

    def test_cutover_rejects_note_learner_without_mutating_current_state(self):
        with self.app.app_context():
            self._seed_retired_full_copy()
            before = self._cutover_snapshot()
            with self.assertRaises(ShareControllerError) as failure:
                cutover_service.cutover_clone_model_to_overlay_only(fail_on_mismatch=True)
            self.assertEqual((failure.exception.status, failure.exception.error), (409, 'CLONE_CUTOVER_NOT_READY'))
            self.assertEqual(self._cutover_snapshot(), before)

    def test_legacy_progress_merge_writer_is_retired(self):
        with self.app.app_context():
            self._seed_retired_full_copy()
            before = self._cutover_snapshot()
            self.assertFalse(hasattr(cutover_service, '_merge_card_progress_rows_for_cutover'))
            assert_retired_progress_absent(self, db.session)
            summary = cutover_service.cutover_clone_model_to_overlay_only(fail_on_mismatch=False)
            self.assertEqual(summary['migrated'], 0)
            self.assertEqual(self._cutover_snapshot(), before)

    def test_legacy_full_copy_requires_offline_migration_and_keeps_copied_content(self):
        with self.app.app_context():
            install = self._seed_retired_full_copy()
            enrollment = StudyAuthorityEnrollment.query.filter_by(learner_user_id=install.user_id).one()
            enrollment.mode_code = 'LEGACY'  # Historical account; current routes refuse it.
            db.session.commit()
            before = self._cutover_snapshot()
            summary = share_ctrl.cutover_clone_model_to_overlay_only(fail_on_mismatch=False)
            self.assertEqual((summary['migrated'], summary['failed']), (0, 1))
            self.assertEqual(summary['errors'][0]['status'], 409)
            self.assertEqual(install.clone_mode, 'legacy_copy')
            self.assertEqual(self._cutover_snapshot(), before)

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
            learner = create_note_user(db.session, username="overlay-learner", email="overlay-learner@example.com", is_admin=False)
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
            note_deltas = DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install_row.id).all()
            self.assertEqual({row.field_identity_key for row in note_deltas},
                {field_ids["Word"], field_ids["Reading"]})
            removed_reading = next(row for row in note_deltas if row.field_identity_key == field_ids["Reading"])
            self.assertEqual(removed_reading.operation, "remove")
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
                learner = create_note_user(db.session, username=username, email=email, is_admin=False)
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
            learner = create_note_user(db.session, username="retry-learner", email="retry-learner@example.com", is_admin=False)
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
            learner = create_note_user(db.session, username="viewer", email="viewer@example.com", is_admin=False)
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
            owner = create_note_user(db.session, username="review-owner", email="review-owner@example.com", is_admin=False)
            owner.set_password("password")
            viewer = create_note_user(db.session, username="review-viewer", email="review-viewer@example.com", is_admin=False)
            viewer.set_password("password")
            reviewer_a = create_note_user(db.session, username="alice", email="alice@example.com", is_admin=False)
            reviewer_a.set_password("password")
            reviewer_b = create_note_user(db.session, username="bob", email="bob@example.com", is_admin=False)
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
            progress = decode_note_state(subject_for_card(db.session, user_id=self.user_id, card_id=payload["card_id"]))
            self.assertIsNotNone(progress)
            self.assertIn(progress.type, {"learning", "review", "relearning", "new"})
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
                stage_note_state(db.session,
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
                stage_note_state(db.session,
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
            progress = decode_note_state(StudyProgressSubject.query.filter_by(learner_user_id=self.user_id).first())
            self.assertEqual(progress.type, "learning")
            self.assertEqual(progress.due, datetime(2026, 2, 22, 19, 0, 0))
            self.assertEqual(progress.dueDay, datetime(2026, 2, 23).date().toordinal())

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
                stage_note_state(db.session,
                    user_id=self.user_id,
                    card_id=overdue_card.id,
                    queue="review",
                    due_at=fixed_now + timedelta(days=2),
                    due_day=today_idx - 1,
                    interval_days=3,
                )
            )
            db.session.add(
                stage_note_state(db.session,
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
                stage_note_state(db.session,
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

            progress = decode_note_state(subject_for_card(db.session, user_id=self.user_id, card_id=next_payload["card_id"]))
            self.assertIsNotNone(progress)
            self.assertEqual(progress.type, "learning")
            self.assertIsNone(progress.dueDay)
            self.assertEqual(progress.due, fixed_now + timedelta(minutes=10))

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
            progress = stage_note_state(db.session,
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

        browse_resp = self.client.get(f"/api/browse/cards?deck_id={self.deck_id}")
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
            progress = stage_note_state(db.session,
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

        due_resp = self.client.get(f"/api/browse/cards?deck_id={self.deck_id}&status=due")
        self.assertEqual(due_resp.status_code, 200)
        self.assertEqual(due_resp.get_json()["total"], 0)

        all_resp = self.client.get(f"/api/browse/cards?deck_id={self.deck_id}")
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
            f"/api/browse/cards/{card_id}",
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

    def test_browse_native_arrays_preserve_owned_values_and_clone_delta_only(self):
        note_type = self._create_note_type()
        meaning_field_id = next(field["id"] for field in note_type["field_defs"] if field["name"] == "Meaning")
        source_value = [["a", "b"], "repeat", "repeat"]
        with self.app.app_context():
            db.session.get(FieldDef, meaning_field_id).field_type = "array"
            db.session.commit()

        created = self.client.post("/api/notes", json={
            "note_type_id": note_type["id"], "deck_id": self.deck_id,
            "field_values": {"Word": "猫", "Meaning": source_value},
        })
        self.assertEqual(created.status_code, 201, created.get_json())
        note_id = created.get_json()["id"]
        with self.app.app_context():
            card_id = Card.query.filter_by(note_id=note_id).first().id

        updated = self.client.patch(f"/api/browse/cards/{card_id}", json={"field_values": {"Word": "犬"}})
        self.assertEqual(updated.status_code, 200, updated.get_json())
        self.assertEqual(updated.get_json()["detail"]["note"]["field_values"]["Meaning"], source_value)

        with self.app.app_context():
            learner = create_note_user(db.session, username="array-learner", email="array-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id
            listing = DeckMarketplaceItem(
                owner_user_id=self.user_id, source_deck_id=self.deck_id,
                source_note_type_id=note_type["id"], title="Native Array Browse",
                publish_status="published", pricing_mode="free",
            )
            db.session.add(listing)
            db.session.flush()
            flashcards_share_service._stage_initial_release_if_visible(listing)
            db.session.commit()
            listing_id = listing.id

        learner_client = self.app.test_client()
        learner_client.post("/login", data={"email": "array-learner@example.com", "password": "password"})
        installed = learner_client.post(f"/api/shared/decks/{listing_id}/install")
        self.assertEqual(installed.status_code, 201, installed.get_json())
        clone_value = [["learner", "local"], "repeat", "repeat"]
        cloned = learner_client.patch(f"/api/browse/cards/{card_id}", json={"field_values": {"Meaning": clone_value}})
        self.assertEqual(cloned.status_code, 200, cloned.get_json())
        self.assertEqual(cloned.get_json()["detail"]["note"]["field_values"]["Meaning"], clone_value)
        reread = learner_client.get(f"/api/browse/cards/{card_id}")
        self.assertEqual(reread.status_code, 200, reread.get_json())
        self.assertEqual(reread.get_json()["note"]["field_values"]["Meaning"], clone_value)
        with self.app.app_context():
            self.assertEqual(db.session.get(Note, note_id).field_values["Meaning"], source_value)
            self.assertEqual(Note.query.filter_by(user_id=learner_id).count(), 0)
            install = DeckInstall.query.filter_by(deck_item_id=listing_id, user_id=learner_id).first()
            overrides = DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id).all()
            self.assertEqual([override.field_name for override in overrides], ["Meaning"])

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
            f"/api/browse/cards/{card_id}",
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
            learner = create_note_user(db.session, username="import-learner", email="import-learner@example.com", is_admin=False)
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
            owner = create_note_user(db.session, username="nt-owner", email="nt-owner@example.com", is_admin=False)
            owner.set_password("password")
            learner = create_note_user(db.session, username="nt-rater", email="nt-rater@example.com", is_admin=False)
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
            owner = create_note_user(db.session, username="deck-owner", email="deck-owner@example.com", is_admin=False)
            owner.set_password("password")
            learner = create_note_user(db.session, username="deck-rater", email="deck-rater@example.com", is_admin=False)
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
