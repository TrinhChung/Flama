"""Integration tests for flashcard API CRUD, preview, and study."""

import io
import re
import unittest
from datetime import datetime, timedelta
from unittest.mock import patch

from app import create_app
from app.services import flashcards_share as share_ctrl
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
from models.card_progress import CardProgress
from sqlalchemy.exc import OperationalError

_MIN_WAV_BYTES = (
    b"RIFF$\x00\x00\x00WAVEfmt \x10\x00\x00\x00\x01\x00\x01\x00"
    b"D\xac\x00\x00\x88X\x01\x00\x02\x00\x10\x00data\x00\x00\x00\x00"
)


class FlashcardApiIntegrationTests(unittest.TestCase):
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
            db.create_all()
            user = User(username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Deck A")
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
            deck_item = DeckMarketplaceItem(
                owner_user_id=self.user_id,
                source_deck_id=self.deck_id,
                source_note_type_id=None,
                title="Shared Deck A",
                description="Deck description",
                primary_category="General",
                tags=[],
                preview_text="Preview",
                pricing_mode="free",
                price_cents=0,
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
                price_cents=0,
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
        self.assertIn("no notes", (preview_resp.get_json() or {}).get("message", "").lower())

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
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
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
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
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
            source_note = Note.query.get(row.get("note_id"))
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
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
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
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.commit()
            deck_item_id = deck_item.id

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

    def test_cutover_migrates_legacy_full_copy_install_to_overlay(self):
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
                price_cents=0,
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
                    due_day=0,
                    interval_days=8,
                    ease_factor=2.5,
                    reps=5,
                    lapses=1,
                )
            )
            db.session.commit()

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

            legacy_progress = CardProgress.query.filter_by(
                user_id=learner_id,
                card_id=legacy_card_id,
            ).first()
            self.assertIsNone(legacy_progress)

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
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
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
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
            db.session.flush()
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
                price_cents=0,
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
                "app.routes.flashcards.share.share_ctrl.install_shared_deck_item_for_user",
                side_effect=[
                    deadlock_exc,
                    {"created": False, "response": expected_response},
                ],
            ) as install_mock,
            patch("app.routes.flashcards.time.sleep") as sleep_mock,
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
                price_cents=0,
                version="1.0.0",
                publish_status="published",
            )
            db.session.add(deck_item)
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

        dashboard_resp = viewer_client.get("/dashboard")
        self.assertEqual(dashboard_resp.status_code, 200)
        dashboard_html = dashboard_resp.get_data(as_text=True)
        self.assertIn("Deck A", dashboard_html)
        self.assertIn("Visible Child Deck", dashboard_html)

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

        dashboard_resp = self.client.get("/dashboard")
        self.assertEqual(dashboard_resp.status_code, 200)
        dashboard_html = dashboard_resp.get_data(as_text=True)

        pattern = re.compile(
            r'data-node-name="Deck A".*?<span class="stat-num stat-new">(\d+)</span>\s*<span class="stat-num stat-learn">(\d+)</span>\s*<span class="stat-num stat-due">(\d+)</span>',
            re.S,
        )
        match = pattern.search(dashboard_html)
        self.assertIsNotNone(match)
        self.assertGreaterEqual(int(match.group(1)), 1)

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
        self.assertIn('data-card-id="', html)
        self.assertIn('data-answer-url="', html)
        self.assertNotIn('data-entry-id="', html)

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
                price_cents=0,
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
                price_cents=0,
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
                price_cents=0,
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

    def test_study_next_uses_learn_ahead_when_only_intraday_learning_remains(self):
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

            waiting_resp = self.client.get(f"/api/study/next?scope=deck&scope_id={self.deck_id}")
            self.assertEqual(waiting_resp.status_code, 200)
            waiting_payload = waiting_resp.get_json()

        self.assertIsNone(waiting_payload.get("card_id"))
        self.assertEqual(waiting_payload.get("session_state"), "waiting")
        self.assertEqual(int(waiting_payload.get("learn_count") or 0), 1)
        self.assertEqual(waiting_payload.get("next_due_at"), "2026-02-22T19:00:00Z")

        with patch("app.routes.vocabulary.datetime") as vocab_datetime:
            vocab_datetime.utcnow.return_value = fixed_now
            study_resp = self.client.get(f"/vocabulary/study/deck/{self.deck_id}")

        self.assertEqual(study_resp.status_code, 200)
        self.assertIn('data-next-due-at="2026-02-22T19:00:00Z"', study_resp.get_data(as_text=True))

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
        self.assertIn(f'data-card-id="{expected_card_id}"', study_resp.get_data(as_text=True))

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

        self.assertIn("Learning in progress.", html)
        self.assertRegex(html, r"Learn\s*<strong[^>]*>1</strong>")
        self.assertIn('id="study-waiting-next-due"', html)
        self.assertNotIn("Later", html)
        self.assertNotIn("No cards due right now.", html)
        self.assertNotIn("You have finished this deck for now.", html)

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
        self.assertIn("No due cards in this deck.", study_resp.get_data(as_text=True))

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

    def test_study_next_defers_inline_template_script(self):
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
        self.assertIn('data-flama-inline-script="1"', rendered_back)
        self.assertIn('type="application/x-flama-note-script"', rendered_back)

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

        with self.app.app_context():
            note = Note.query.get(note_id)
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
            note = Note.query.get(note_id)
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
        self.assertEqual((payload.get("field_values") or {}).get("Word_Audio"), "voice.wav")

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
            note = Note.query.get(note_id)
            self.assertIsNotNone(note)
            values = note.field_values or {}  # type: ignore[union-attr]
            self.assertEqual(values.get("Word"), "\u72ac-browse-updated")
            self.assertEqual(values.get("Reading"), "\u3044\u306c")
            self.assertEqual(values.get("Meaning"), "dog")

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

    def test_flashcard_import_execute_allows_non_admin_owned_deck_without_install(self):
        with self.app.app_context():
            learner = User(username="import-learner", email="import-learner@example.com", is_admin=False)
            learner.set_password("password")
            db.session.add(learner)
            db.session.flush()
            learner_id = learner.id

            owned_deck = Deck(name="Owned Import Deck", owner_user_id=learner_id)
            db.session.add(owned_deck)
            db.session.commit()
            owned_deck_id = owned_deck.id

        learner_client = self.app.test_client()
        learner_client.post(
            "/login",
            data={"email": "import-learner@example.com", "password": "password"},
            follow_redirects=True,
        )

        note_type_resp = learner_client.post(
            "/api/note-types",
            json={
                "name": "Owned Import Type",
                "field_defs": [
                    {"name": "Word", "field_type": "text", "position": 0, "required": True},
                    {"name": "Reading", "field_type": "text", "position": 1, "required": False},
                    {"name": "Meaning", "field_type": "text", "position": 2, "required": False},
                ],
                "template": {
                    "name": "Card 1",
                    "front_html": "{{Word}}",
                    "back_html": "{{Word}} - {{Meaning}}",
                    "shared_css": "",
                },
            },
        )
        self.assertEqual(note_type_resp.status_code, 201)
        note_type_id = (note_type_resp.get_json() or {}).get("id")
        self.assertTrue(note_type_id)

        parse_resp = learner_client.post(
            "/api/flashcards/import/parse",
            data={
                "note_type_id": note_type_id,
                "delimiter_mode": "csv",
                "has_header": "1",
                "file": (
                    io.BytesIO("Word,Reading,Meaning\n犬,いぬ,dog\n".encode("utf-8")),
                    "owned-import.csv",
                ),
            },
            content_type="multipart/form-data",
        )
        self.assertEqual(parse_resp.status_code, 200)
        parse_payload = parse_resp.get_json() or {}
        self.assertTrue(parse_payload.get("token"))

        execute_resp = learner_client.post(
            "/api/flashcards/import/execute",
            json={
                "token": parse_payload["token"],
                "note_type_id": note_type_id,
                "target_deck_id": owned_deck_id,
                "import_mode": "upsert",
                "uniqueness_fields": ["Word"],
                "mapping": parse_payload.get("suggested_mapping", {}),
                "dont_overwrite_empty": True,
                "confirm_column_mismatch": False,
            },
        )
        self.assertEqual(execute_resp.status_code, 200)
        summary = (execute_resp.get_json() or {}).get("summary") or {}
        self.assertEqual(int(summary.get("inserted") or 0), 1)
        self.assertEqual(int(summary.get("errors") or 0), 0)

        with self.app.app_context():
            imported_note = Note.query.filter_by(
                user_id=learner_id,
                note_type_id=note_type_id,
                deck_id=owned_deck_id,
            ).first()
            self.assertIsNotNone(imported_note)
            self.assertEqual((imported_note.field_values or {}).get("Word"), "犬")

    def test_flashcard_import_page_renders(self):
        response = self.client.get("/flashcards/import")
        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("Step A - Upload & Parse", html)
        self.assertIn("Step D - Review & Execute", html)
        self.assertIn("previewSelectAllInput", html)

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
                price_cents=0,
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

        with patch("app.routes.flashcards.share._can_user_rate_note_type", return_value=True):
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
                price_cents=0,
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
