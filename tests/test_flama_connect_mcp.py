"""Integration tests for MCP JSON-RPC endpoints on Flama Connect."""

from __future__ import annotations

import json
import io
import base64
from unittest.mock import patch
from PIL import Image
from app.services.remote_image_fetcher import RemoteImagePayload
import unittest
from datetime import datetime

from app.connect import create_connect_app
from app.services import mcp_access_token_service, user_api_token_service
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from models.shared_image_asset import SharedImageAsset




def _make_test_png_b64(color=(245, 105, 24, 255)) -> str:
    output = io.BytesIO()
    Image.new("RGBA", (24, 18), color).save(output, format="PNG")
    return base64.b64encode(output.getvalue()).decode("utf-8")


def _make_test_png_b64_bytes(color=(200, 100, 50, 255)) -> bytes:
    output = io.BytesIO()
    Image.new("RGBA", (24, 18), color).save(output, format="PNG")
    return output.getvalue()

class FlamaConnectMcpTests(unittest.TestCase):
    def setUp(self):
        self.app = create_connect_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "CONNECT_CORS_ALLOWED_ORIGINS": (),
            }
        )
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = User(
                username="mcp_user",
                email="mcp_user@example.com",
                timezone="UTC",
                is_admin=False,
            )
            user.set_password("password")
            db.session.add(user)

            other_user = User(
                username="other_user",
                email="other@example.com",
                timezone="UTC",
                is_admin=False,
            )
            other_user.set_password("password")
            db.session.add(other_user)
            db.session.flush()

            self.user_id = user.id
            self.other_user_id = other_user.id

            # Create UserApiToken
            issued_api_token = user_api_token_service.issue_token(
                user_id=user.id,
                name="Cursor MCP Token",
            )
            self.api_token_str = issued_api_token.plaintext

            # Create McpAccessToken
            issued_mcp_token = mcp_access_token_service.issue_short_lived_token(
                user_id=user.id,
            )
            self.mcp_token_str = issued_mcp_token.token

            # NoteType with fields and templates
            note_type = NoteType(user_id=user.id, name="Japanese Vocabulary")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            db.session.add_all(
                [
                    FieldDef(
                        note_type_id=note_type.id,
                        name="Word",
                        field_type="text",
                        position=0,
                        required=True,
                        identity_role="primary",
                    ),
                    FieldDef(
                        note_type_id=note_type.id,
                        name="Reading",
                        field_type="text",
                        position=1,
                        required=False,
                    ),
                    FieldDef(
                        note_type_id=note_type.id,
                        name="Meaning",
                        field_type="text",
                        position=2,
                        required=True,
                    ),
                    Template(
                        note_type_id=note_type.id,
                        name="Recognition",
                        front_html="<div>{{Word}}</div>",
                        back_html="<div>{{Reading}} - {{Meaning}}</div>",
                        position=0,
                    ),
                ]
            )

            # Create Decks
            deck = Deck(
                name="JLPT N5",
                owner_user_id=user.id,
                description="Core JLPT N5 deck",
                position=1,
            )
            db.session.add(deck)

            other_deck = Deck(
                name="Secret Other Deck",
                owner_user_id=other_user.id,
                description="Other user deck",
                position=1,
            )
            db.session.add(other_deck)
            db.session.flush()

            self.deck_id = deck.id
            self.other_deck_id = other_deck.id

            # Initial Note
            note = Note(
                user_id=user.id,
                deck_id=deck.id,
                note_type_id=note_type.id,
                field_values={"Word": "食べる", "Reading": "たべる", "Meaning": "to eat"},
                tags=["verb", "n5"],
            )
            db.session.add(note)

            other_note = Note(
                user_id=other_user.id,
                deck_id=other_deck.id,
                note_type_id=note_type.id,
                field_values={"Word": "他人の言葉", "Reading": "たにん", "Meaning": "other's note"},
                tags=["secret"],
            )
            db.session.add(other_note)
            db.session.flush()

            self.note_id = note.id
            self.other_note_id = other_note.id

            card = Card(note_id=note.id, template_id=note_type.templates[0].id)
            db.session.add(card)
            db.session.add(Card(note_id=other_note.id, template_id=note_type.templates[0].id))
            db.session.flush()
            self.card_id = card.id

            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _post_mcp(self, payload: dict, token: str | None = None, url_token: str | None = None):
        headers = {"MCP-Protocol-Version": "2025-11-25"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        path = f"/v1/mcp/{url_token}" if url_token else "/v1/mcp"
        return self.client.post(path, json=payload, headers=headers)

    def test_initialize(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25"},
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("tools", data["result"]["capabilities"])
        self.assertEqual(data["result"]["serverInfo"]["name"], "flama-mcp-connect")

    def test_notifications_initialized(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "method": "notifications/initialized",
                "params": {},
            }
        )
        self.assertEqual(response.status_code, 204)

    def test_tools_list(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        tools = data["result"]["tools"]
        tool_names = {t["name"] for t in tools}
        expected_tools = {
            # Decks
            "list_my_decks",
            "get_deck_tree",
            "get_deck",
            "resolve_deck",
            "batch_ensure_decks",
            "create_deck",
            "update_deck",
            "delete_deck",
            # Notes
            "list_notes",
            "get_note",
            "find_notes",
            "create_note",
            "update_note",
            "delete_note",
            "move_note",
            "add_tags",
            "remove_tags",
            # Batch & Sync
            "batch_create_notes",
            "batch_update_notes",
            "batch_delete_notes",
            "batch_move_notes",
            "preview_note_sync",
            "sync_notes",
            # Study
            "get_due_card_counts",
            "get_study_queue",
            "get_card",
            "submit_review",
            # Stats
            "get_deck_stats",
            "get_study_stats",
            # Note Types
            "list_note_types",
            "get_note_type_schema",
            "create_note_type",
            "preview_note_type_update",
            "update_note_type",
            "delete_note_type",
            # Image Library
            "import_image",
            "search_images",
            "get_image",
        }
        self.assertEqual(tool_names, expected_tools)
        self.assertEqual(len(tools), 38)

    # -----------------------------------------------------------------------
    # Deck Tests
    # -----------------------------------------------------------------------

    def test_call_list_my_decks_bearer_auth(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {"name": "list_my_decks", "arguments": {}},
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        decks = data["result"]["structuredContent"]["decks"]
        self.assertEqual(len(decks), 1)
        self.assertEqual(decks[0]["name"], "JLPT N5")

    def test_call_get_deck(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "get_deck", "arguments": {"deck_id": self.deck_id}},
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        res = data["result"]["structuredContent"]
        self.assertEqual(res["deck_id"], self.deck_id)
        self.assertEqual(res["name"], "JLPT N5")
        self.assertEqual(res["note_count"], 1)
        self.assertEqual(res["card_count"], 1)

    def test_call_create_update_delete_deck(self):
        # 1. create_deck (simple)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "create_deck",
                    "arguments": {
                        "name": "JLPT N1",
                        "description": "Advanced Japanese deck",
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        created = response.get_json()["result"]["structuredContent"]
        new_deck_id = created["deck_id"]
        self.assertEqual(created["name"], "JLPT N1")

        # 2. create_deck (hierarchical path)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {
                    "name": "create_deck",
                    "arguments": {
                        "name": "Japanese::Grammar::N1",
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)

        # 3. update_deck (rename & reparent)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {
                    "name": "update_deck",
                    "arguments": {
                        "deck_id": new_deck_id,
                        "name": "JLPT N1 Super",
                        "description": "Updated desc",
                        "parent_id": self.deck_id,
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()["result"]["structuredContent"]
        self.assertEqual(updated["name"], "JLPT N1 Super")
        self.assertEqual(updated["parent_id"], self.deck_id)

        # 4. delete_deck without confirm (dry-run impact preview)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "delete_deck",
                    "arguments": {"deck_id": new_deck_id},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        preview = response.get_json()["result"]["structuredContent"]
        self.assertTrue(preview["requires_confirmation"])
        self.assertEqual(preview["deck_id"], new_deck_id)
        self.assertIn("impact", preview)
        self.assertIn("warning", preview)

        # 5. delete_deck with confirm=True (actual deletion)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 81,
                "method": "tools/call",
                "params": {
                    "name": "delete_deck",
                    "arguments": {"deck_id": new_deck_id, "confirm": True},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        deleted = response.get_json()["result"]["structuredContent"]
        self.assertTrue(deleted["success"])

    # -----------------------------------------------------------------------
    # Note Listing & Reading Tests
    # -----------------------------------------------------------------------

    def test_call_list_notes_and_get_note(self):
        # 1. list_notes without query
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "list_notes",
                    "arguments": {
                        "deck_id": self.deck_id,
                        "limit": 10,
                        "offset": 0,
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        list_res = data["result"]["structuredContent"]
        self.assertEqual(list_res["total"], 1)
        self.assertEqual(len(list_res["notes"]), 1)
        self.assertEqual(list_res["notes"][0]["fields"]["Word"], "食べる")

        # 2. get_note
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "get_note",
                    "arguments": {"note_id": str(self.note_id)},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        note_data = response.get_json()["result"]["structuredContent"]
        self.assertEqual(note_data["note_id"], str(self.note_id))
        self.assertEqual(note_data["fields"]["Word"], "食べる")
        self.assertEqual(len(note_data["cards"]), 1)
        self.assertEqual(note_data["cards"][0]["queue"], "new")

    def test_call_find_notes(self):
        # find_notes by keyword
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "find_notes",
                    "arguments": {
                        "query": "食べる",
                        "deck_id": self.deck_id,
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        res = response.get_json()["result"]["structuredContent"]
        self.assertEqual(res["total_matches"], 1)
        self.assertEqual(res["notes"][0]["fields"]["Word"], "食べる")

        # find_notes by tag
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {
                    "name": "find_notes",
                    "arguments": {"tag": "verb"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        res = response.get_json()["result"]["structuredContent"]
        self.assertEqual(res["total_matches"], 1)

    # -----------------------------------------------------------------------
    # Note Mutation & Organization Tests
    # -----------------------------------------------------------------------

    def test_call_update_note_partial_fields(self):
        # update_note with only Meaning field (Word & Reading must be preserved!)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 13,
                "method": "tools/call",
                "params": {
                    "name": "update_note",
                    "arguments": {
                        "note_id": str(self.note_id),
                        "fields": {"Meaning": "to eat, consume"},
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        updated = response.get_json()["result"]["structuredContent"]
        self.assertTrue(updated["success"])
        self.assertEqual(updated["fields"]["Word"], "食べる")
        self.assertEqual(updated["fields"]["Reading"], "たべる")
        self.assertEqual(updated["fields"]["Meaning"], "to eat, consume")

    def test_call_add_and_remove_tags(self):
        # add_tags
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 14,
                "method": "tools/call",
                "params": {
                    "name": "add_tags",
                    "arguments": {
                        "note_ids": [str(self.note_id)],
                        "tags": ["difficult", "JLPT_N5"],
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        res = response.get_json()["result"]["structuredContent"]
        self.assertEqual(res["updated_count"], 1)

        # verify tags on note
        note_res = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 15,
                "method": "tools/call",
                "params": {"name": "get_note", "arguments": {"note_id": str(self.note_id)}},
            },
            token=self.api_token_str,
        ).get_json()["result"]["structuredContent"]
        self.assertIn("difficult", note_res["tags"])
        self.assertIn("verb", note_res["tags"])

        # remove_tags
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 16,
                "method": "tools/call",
                "params": {
                    "name": "remove_tags",
                    "arguments": {
                        "note_ids": [str(self.note_id)],
                        "tags": ["difficult"],
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)

        # verify tag removed
        note_res = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 17,
                "method": "tools/call",
                "params": {"name": "get_note", "arguments": {"note_id": str(self.note_id)}},
            },
            token=self.api_token_str,
        ).get_json()["result"]["structuredContent"]
        self.assertNotIn("difficult", note_res["tags"])
        self.assertIn("verb", note_res["tags"])

    def test_call_move_note_and_delete_note(self):
        # 1. create secondary deck
        new_deck_res = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 18,
                "method": "tools/call",
                "params": {"name": "create_deck", "arguments": {"name": "Deck 2"}},
            },
            token=self.api_token_str,
        ).get_json()["result"]["structuredContent"]
        target_deck_id = new_deck_res["deck_id"]

        # 2. move_note
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 19,
                "method": "tools/call",
                "params": {
                    "name": "move_note",
                    "arguments": {
                        "note_id": str(self.note_id),
                        "deck_id": target_deck_id,
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)

        # verify deck moved
        note_res = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 20,
                "method": "tools/call",
                "params": {"name": "get_note", "arguments": {"note_id": str(self.note_id)}},
            },
            token=self.api_token_str,
        ).get_json()["result"]["structuredContent"]
        self.assertEqual(note_res["deck_id"], target_deck_id)

        # 3. delete_note without confirm (preview only)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 21,
                "method": "tools/call",
                "params": {
                    "name": "delete_note",
                    "arguments": {"note_id": str(self.note_id)},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        note_del_preview = response.get_json()["result"]["structuredContent"]
        self.assertTrue(note_del_preview["requires_confirmation"])
        self.assertEqual(note_del_preview["note_id"], str(self.note_id))

        # 4. delete_note with confirm=True
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 211,
                "method": "tools/call",
                "params": {
                    "name": "delete_note",
                    "arguments": {"note_id": str(self.note_id), "confirm": True},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.get_json()["result"]["structuredContent"]["success"])

    # -----------------------------------------------------------------------
    # Batch Operations Tests
    # -----------------------------------------------------------------------

    def test_call_batch_operations(self):
        # 1. batch_create_notes
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 22,
                "method": "tools/call",
                "params": {
                    "name": "batch_create_notes",
                    "arguments": {
                        "notes": [
                            {
                                "deck_id": self.deck_id,
                                "note_type_id": self.note_type_id,
                                "fields": {"Word": "本", "Reading": "ほん", "Meaning": "book"},
                                "tags": ["noun"],
                            },
                            {
                                "deck_id": self.deck_id,
                                "note_type_id": self.note_type_id,
                                "fields": {"Word": "車", "Reading": "くるま", "Meaning": "car"},
                                "tags": ["noun"],
                            },
                        ]
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        batch_create_res = response.get_json()["result"]["structuredContent"]
        self.assertEqual(batch_create_res["created_count"], 2)
        note_ids = batch_create_res["note_ids"]

        # 2. batch_update_notes
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 23,
                "method": "tools/call",
                "params": {
                    "name": "batch_update_notes",
                    "arguments": {
                        "notes": [
                            {
                                "note_id": note_ids[0],
                                "fields": {"Meaning": "book, main"},
                            },
                            {
                                "note_id": note_ids[1],
                                "tags": ["noun", "vehicle"],
                            },
                        ]
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        batch_up_res = response.get_json()["result"]["structuredContent"]
        self.assertEqual(batch_up_res["updated_count"], 2)

        # 3. batch_delete_notes without confirm (preview only)
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 24,
                "method": "tools/call",
                "params": {
                    "name": "batch_delete_notes",
                    "arguments": {"note_ids": note_ids},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        batch_preview = response.get_json()["result"]["structuredContent"]
        self.assertTrue(batch_preview["requires_confirmation"])
        self.assertEqual(batch_preview["impact"]["found_notes_to_delete"], 2)

        # 4. batch_delete_notes with confirm=True
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 241,
                "method": "tools/call",
                "params": {
                    "name": "batch_delete_notes",
                    "arguments": {"note_ids": note_ids, "confirm": True},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        batch_del_res = response.get_json()["result"]["structuredContent"]
        self.assertEqual(batch_del_res["deleted_count"], 2)

    # -----------------------------------------------------------------------
    # Study & Card Review Tests
    # -----------------------------------------------------------------------

    def test_call_study_flow_and_review(self):
        # 1. get_study_queue
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 25,
                "method": "tools/call",
                "params": {
                    "name": "get_study_queue",
                    "arguments": {"deck_id": self.deck_id, "limit": 5},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        queue_res = response.get_json()["result"]["structuredContent"]
        self.assertIn("cards", queue_res)
        self.assertGreaterEqual(len(queue_res["cards"]), 1)
        card_item = queue_res["cards"][0]
        self.assertIn("front_html", card_item)
        self.assertIn("intervals_preview", card_item)
        target_card_id = card_item["card_id"]

        # 2. get_card
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 26,
                "method": "tools/call",
                "params": {
                    "name": "get_card",
                    "arguments": {"card_id": target_card_id},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        card_res = response.get_json()["result"]["structuredContent"]
        self.assertEqual(card_res["card_id"], target_card_id)
        self.assertIn("intervals_preview", card_res)

        # 3. submit_review ("good")
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 27,
                "method": "tools/call",
                "params": {
                    "name": "submit_review",
                    "arguments": {
                        "card_id": target_card_id,
                        "rating": "good",
                        "duration_ms": 3500,
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        review_res = response.get_json()["result"]["structuredContent"]
        self.assertTrue(review_res["success"])
        self.assertEqual(review_res["card_id"], target_card_id)
        self.assertEqual(review_res["rating"], "good")
        self.assertEqual(review_res["reps"], 1)

    # -----------------------------------------------------------------------
    # Statistics Tests
    # -----------------------------------------------------------------------

    def test_call_get_deck_stats_and_study_stats(self):
        # 1. get_deck_stats
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 28,
                "method": "tools/call",
                "params": {
                    "name": "get_deck_stats",
                    "arguments": {"deck_id": self.deck_id},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        deck_stats = response.get_json()["result"]["structuredContent"]
        self.assertEqual(deck_stats["deck_id"], self.deck_id)
        self.assertEqual(deck_stats["note_count"], 1)
        self.assertEqual(deck_stats["card_count"], 1)

        # 2. get_study_stats
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 29,
                "method": "tools/call",
                "params": {
                    "name": "get_study_stats",
                    "arguments": {},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        study_stats = response.get_json()["result"]["structuredContent"]
        self.assertIn("current_streak_days", study_stats)
        self.assertIn("total_decks", study_stats)
        self.assertIn("total_notes", study_stats)

    # -----------------------------------------------------------------------
    # Security & Error Handling Tests
    # -----------------------------------------------------------------------

    def test_unauthorized_access_to_other_user_resources_rejected(self):
        # Attempt to get other user's deck
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 30,
                "method": "tools/call",
                "params": {
                    "name": "get_deck",
                    "arguments": {"deck_id": self.other_deck_id},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], -32602)
        self.assertEqual(data["error"]["data"]["code"], "DECK_NOT_FOUND")

        # Attempt to get other user's note
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 31,
                "method": "tools/call",
                "params": {
                    "name": "get_note",
                    "arguments": {"note_id": str(self.other_note_id)},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], -32602)
        self.assertEqual(data["error"]["data"]["code"], "NOTE_NOT_FOUND")

    def test_invalid_rating_rejected(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 32,
                "method": "tools/call",
                "params": {
                    "name": "submit_review",
                    "arguments": {
                        "card_id": str(self.card_id),
                        "rating": "super_easy",
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 400)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], -32602)

    def test_unauthenticated_tools_call_rejected(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 33,
                "method": "tools/call",
                "params": {"name": "list_my_decks", "arguments": {}},
            }
        )
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], -32001)

    def test_invalid_token_rejected(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 34,
                "method": "tools/call",
                "params": {"name": "list_my_decks", "arguments": {}},
            },
            token="invalid_token_123",
        )
        self.assertEqual(response.status_code, 401)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], -32001)

    def test_unknown_method_rejected(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 35,
                "method": "unknown/method",
                "params": {},
            }
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], -32601)



    # -----------------------------------------------------------------------
    # Image Library MCP Tests
    # -----------------------------------------------------------------------

    def test_import_image_base64_and_search_and_get(self):
        b64_data = _make_test_png_b64()
        # 1. Import image with base64 data and tags
        resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 101,
                "method": "tools/call",
                "params": {
                    "name": "import_image",
                    "arguments": {
                        "file_data": b64_data,
                        "filename": "apple.png",
                        "image_key": "red_apple",
                        "tags": ["apple", "Red Apple", "fruit", "food"],
                        "description": "A crisp red apple",
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["result"]["structuredContent"]
        self.assertIn("image", data)
        image = data["image"]
        self.assertEqual(image["image_key"], "red_apple")
        self.assertIn("apple", image["tags"])
        self.assertIn("red apple", image["tags"])
        self.assertIn("fruit", image["tags"])
        self.assertIn("food", image["tags"])
        self.assertFalse(data["is_deduplicated"])

        # 2. Search images by tag
        search_resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 102,
                "method": "tools/call",
                "params": {
                    "name": "search_images",
                    "arguments": {"tag": "apple"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(search_resp.status_code, 200)
        search_data = search_resp.get_json()["result"]["structuredContent"]
        self.assertEqual(search_data["total"], 1)
        self.assertEqual(search_data["items"][0]["image_key"], "red_apple")

        # 3. Get image by key
        get_resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 103,
                "method": "tools/call",
                "params": {
                    "name": "get_image",
                    "arguments": {"image_key": "red_apple"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(get_resp.status_code, 200)
        get_data = get_resp.get_json()["result"]["structuredContent"]
        self.assertEqual(get_data["image"]["image_key"], "red_apple")

    def test_import_image_deduplication_merges_tags(self):
        b64_data = _make_test_png_b64(color=(10, 200, 50, 255))

        # First import
        resp1 = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 104,
                "method": "tools/call",
                "params": {
                    "name": "import_image",
                    "arguments": {
                        "file_data": b64_data,
                        "tags": ["tree", "green"],
                        "description": "Green tree",
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp1.status_code, 200)
        data1 = resp1.get_json()["result"]["structuredContent"]
        self.assertFalse(data1["is_deduplicated"])
        asset_id = data1["image"]["id"]

        # Second import with identical content hash but new tags
        resp2 = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 105,
                "method": "tools/call",
                "params": {
                    "name": "import_image",
                    "arguments": {
                        "file_data": b64_data,
                        "tags": ["nature", "forest", "tree"],
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp2.status_code, 200)
        data2 = resp2.get_json()["result"]["structuredContent"]
        self.assertTrue(data2["is_deduplicated"])
        self.assertEqual(data2["image"]["id"], asset_id)
        # Verify merged tags
        tags = data2["image"]["tags"]
        self.assertIn("tree", tags)
        self.assertIn("green", tags)
        self.assertIn("nature", tags)
        self.assertIn("forest", tags)

    @patch("app.services.image_library_service.fetch_remote_image")
    def test_import_image_url_mocked(self, mock_fetch):
        png_bytes = _make_test_png_b64_bytes()
        mock_fetch.return_value = RemoteImagePayload(
            content=png_bytes,
            mime_type="image/png",
            filename="banana.png",
            source_url="https://example.com/banana.png",
        )
        resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 106,
                "method": "tools/call",
                "params": {
                    "name": "import_image",
                    "arguments": {
                        "url": "https://example.com/banana.png",
                        "tags": ["banana", "yellow", "fruit"],
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["result"]["structuredContent"]
        self.assertEqual(data["image"]["source_url"], "https://example.com/banana.png")
        self.assertIn("banana", data["image"]["tags"])

    def test_search_images_empty_library(self):
        resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 107,
                "method": "tools/call",
                "params": {
                    "name": "search_images",
                    "arguments": {"limit": 5},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["result"]["structuredContent"]
        self.assertEqual(data["total"], 0)
        self.assertEqual(data["items"], [])
        self.assertEqual(data["limit"], 5)
        self.assertEqual(data["offset"], 0)
        self.assertFalse(data["has_more"])

    def test_search_images_default_status_filter_and_queries(self):
        with self.app.app_context():
            img_enabled = SharedImageAsset(
                image_key="cherry_red",
                description="Red cherry fruit",
                is_enabled=True,
                tags=["cherry", "fruit", "red"],
            )
            img_disabled = SharedImageAsset(
                image_key="cherry_black",
                description="Black cherry fruit",
                is_enabled=False,
                tags=["cherry", "fruit", "black"],
            )
            db.session.add_all([img_enabled, img_disabled])
            db.session.commit()

        # 1. Default status should be "enabled"
        resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 108,
                "method": "tools/call",
                "params": {
                    "name": "search_images",
                    "arguments": {"query": "cherry"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()["result"]["structuredContent"]
        self.assertEqual(data["total"], 1)
        self.assertEqual(data["items"][0]["image_key"], "cherry_red")

        # 2. status="all" should return both
        resp_all = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 109,
                "method": "tools/call",
                "params": {
                    "name": "search_images",
                    "arguments": {"query": "cherry", "status": "all"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp_all.status_code, 200)
        data_all = resp_all.get_json()["result"]["structuredContent"]
        self.assertEqual(data_all["total"], 2)

    def test_get_image_not_found_returns_404_not_502(self):
        # 1. Non-existent image_key
        resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 110,
                "method": "tools/call",
                "params": {
                    "name": "get_image",
                    "arguments": {"image_key": "non_existent_key_999"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp.status_code, 404)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32602)
        self.assertEqual(data["error"]["data"]["code"], "IMAGE_NOT_FOUND")

        # 2. Non-existent asset_id
        resp_id = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 111,
                "method": "tools/call",
                "params": {
                    "name": "get_image",
                    "arguments": {"asset_id": "00000000-0000-0000-0000-000000000000"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp_id.status_code, 404)
        data_id = resp_id.get_json()
        self.assertEqual(data_id["error"]["code"], -32602)
        self.assertEqual(data_id["error"]["data"]["code"], "IMAGE_NOT_FOUND")

        # 3. Non-existent alias name / id
        resp_alias = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 112,
                "method": "tools/call",
                "params": {
                    "name": "get_image",
                    "arguments": {"name": "ghost_image_slug"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp_alias.status_code, 404)
        self.assertEqual(resp_alias.get_json()["error"]["data"]["code"], "IMAGE_NOT_FOUND")

        # 4. Empty / whitespace arguments rejected with 400 INVALID_PARAMS
        resp_empty = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 113,
                "method": "tools/call",
                "params": {
                    "name": "get_image",
                    "arguments": {"image_key": "   "},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp_empty.status_code, 400)
        self.assertEqual(resp_empty.get_json()["error"]["data"]["code"], "INVALID_PARAMS")

        # 5. Wrong image_key with valid fallback asset_id succeeds
        with self.app.app_context():
            from models.shared_image_asset import SharedImageAsset
            existing_asset = SharedImageAsset(
                image_key="fallback_test_image",
                description="Fallback image",
                mime_type="image/webp",
                sha256="fallbacktest000000000000000000000000000000000000000000000000000000",
                size_bytes=1024,
                storage_path="image_library/fallback_test.webp",
                is_enabled=True,
                tags=["fallback"],
            )
            db.session.add(existing_asset)
            db.session.commit()
            valid_id = existing_asset.id

        resp_fallback = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 114,
                "method": "tools/call",
                "params": {
                    "name": "get_image",
                    "arguments": {
                        "image_key": "wrong_key_that_does_not_exist",
                        "asset_id": valid_id,
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(resp_fallback.status_code, 200)
        fallback_data = resp_fallback.get_json()["result"]["structuredContent"]["image"]
        self.assertEqual(fallback_data["asset_id"], valid_id)

    def test_search_images_missing_scope_returns_403(self):
        with self.app.app_context():
            issued_token = mcp_access_token_service.issue_token_and_commit(
                user_id=self.user_id,
                name="Deck Only Token",
                scopes=["deck:read"],
            )
            deck_token_str = issued_token.token

        resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 111,
                "method": "tools/call",
                "params": {
                    "name": "search_images",
                    "arguments": {"limit": 5},
                },
            },
            token=deck_token_str,
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32003)
        self.assertEqual(data["error"]["data"]["code"], "MCP_SCOPE_FORBIDDEN")

    def test_import_image_missing_scope_returns_403(self):
        with self.app.app_context():
            issued_token = mcp_access_token_service.issue_token_and_commit(
                user_id=self.user_id,
                name="Media Read Only Token",
                scopes=["media:read"],
            )
            read_only_token_str = issued_token.token

        resp = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 112,
                "method": "tools/call",
                "params": {
                    "name": "import_image",
                    "arguments": {
                        "file_data": _make_test_png_b64(),
                        "image_key": "peach",
                    },
                },
            },
            token=read_only_token_str,
        )
        self.assertEqual(resp.status_code, 403)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32003)
        self.assertEqual(data["error"]["data"]["code"], "MCP_SCOPE_FORBIDDEN")

    def test_serialize_mcp_image_asset_robustness(self):
        from app.services.mcp_tool_service import serialize_mcp_image_asset

        with self.app.app_context():
            asset_null_tags = SharedImageAsset(
                image_key="null_tags",
                description="null tags asset",
                tags=None,
            )
            asset_str_tags = SharedImageAsset(
                image_key="str_tags",
                description="str tags asset",
                tags='["orange", "citrus"]',
            )
            asset_invalid_str = SharedImageAsset(
                image_key="inv_tags",
                description="invalid str tags asset",
                tags="invalid_json_string",
            )
            res_null = serialize_mcp_image_asset(asset_null_tags)
            self.assertEqual(res_null["tags"], [])
            self.assertEqual(res_null["image_key"], "null_tags")

            res_str = serialize_mcp_image_asset(asset_str_tags)
            self.assertEqual(res_str["tags"], ["orange", "citrus"])

            res_inv = serialize_mcp_image_asset(asset_invalid_str)
            self.assertEqual(res_inv["tags"], [])


if __name__ == "__main__":
    unittest.main()
