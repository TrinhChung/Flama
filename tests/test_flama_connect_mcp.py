"""Integration tests for MCP JSON-RPC endpoints on Flama Connect."""

from __future__ import annotations

import json
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
            db.session.flush()
            self.user_id = user.id

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
            db.session.flush()
            self.deck_id = deck.id

            # Initial Note
            note = Note(
                user_id=user.id,
                deck_id=deck.id,
                note_type_id=note_type.id,
                field_values={"Word": "食べる", "Reading": "たべる", "Meaning": "to eat"},
                tags=["verb", "n5"],
            )
            db.session.add(note)
            db.session.flush()
            self.note_id = note.id

            db.session.add(Card(note_id=note.id, template_id=note_type.templates[0].id))
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
            "list_my_decks",
            "get_deck_tree",
            "list_note_types",
            "get_note_type_schema",
            "find_notes",
            "create_note",
            "batch_create_notes",
            "get_due_card_counts",
        }
        self.assertTrue(expected_tools.issubset(tool_names))

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

    def test_call_list_my_decks_url_token_auth(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {"name": "list_my_decks", "arguments": {}},
            },
            url_token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        decks = data["result"]["structuredContent"]["decks"]
        self.assertEqual(len(decks), 1)

    def test_call_list_my_decks_mcp_access_token(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {"name": "list_my_decks", "arguments": {}},
            },
            token=self.mcp_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        decks = data["result"]["structuredContent"]["decks"]
        self.assertEqual(len(decks), 1)

    def test_call_get_deck_tree(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 6,
                "method": "tools/call",
                "params": {"name": "get_deck_tree", "arguments": {}},
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        tree = data["result"]["structuredContent"]["tree"]
        self.assertIsInstance(tree, list)
        self.assertGreaterEqual(len(tree), 1)

    def test_call_list_note_types_and_schema(self):
        # 1. list_note_types
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 7,
                "method": "tools/call",
                "params": {"name": "list_note_types", "arguments": {}},
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        note_types = data["result"]["structuredContent"]["note_types"]
        self.assertGreaterEqual(len(note_types), 1)

        # 2. get_note_type_schema
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 8,
                "method": "tools/call",
                "params": {
                    "name": "get_note_type_schema",
                    "arguments": {"note_type_id": self.note_type_id},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        schema = data["result"]["structuredContent"]
        self.assertEqual(schema["name"], "Japanese Vocabulary")
        self.assertEqual(len(schema["fields"]), 3)
        self.assertEqual(len(schema["templates"]), 1)

    def test_call_create_note_and_find_notes(self):
        # 1. create_note
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {
                    "name": "create_note",
                    "arguments": {
                        "deck_id": self.deck_id,
                        "note_type_id": self.note_type_id,
                        "fields": {
                            "Word": "飲む",
                            "Reading": "のむ",
                            "Meaning": "to drink",
                        },
                        "tags": ["verb", "n5"],
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        created = data["result"]["structuredContent"]
        self.assertIn("note_id", created)
        self.assertEqual(len(created["cards"]), 1)

        # 2. find_notes
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 10,
                "method": "tools/call",
                "params": {
                    "name": "find_notes",
                    "arguments": {"query": "飲む"},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        notes = data["result"]["structuredContent"]["notes"]
        self.assertEqual(len(notes), 1)
        self.assertEqual(notes[0]["fields"]["Word"], "飲む")

    def test_call_batch_create_notes(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 11,
                "method": "tools/call",
                "params": {
                    "name": "batch_create_notes",
                    "arguments": {
                        "notes": [
                            {
                                "deck_id": self.deck_id,
                                "note_type_id": self.note_type_id,
                                "fields": {"Word": "本", "Reading": "ほん", "Meaning": "book"},
                            },
                            {
                                "deck_id": self.deck_id,
                                "note_type_id": self.note_type_id,
                                "fields": {"Word": "車", "Reading": "くるま", "Meaning": "car"},
                            },
                        ]
                    },
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        batch_res = data["result"]["structuredContent"]
        self.assertEqual(batch_res["created_count"], 2)
        self.assertEqual(len(batch_res["note_ids"]), 2)

    def test_call_get_due_card_counts(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 12,
                "method": "tools/call",
                "params": {
                    "name": "get_due_card_counts",
                    "arguments": {},
                },
            },
            token=self.api_token_str,
        )
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        counts = data["result"]["structuredContent"]
        self.assertIn("total_due", counts)
        self.assertIn("new_cards", counts)

    def test_unauthenticated_tools_call_rejected(self):
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 13,
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
                "id": 14,
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
                "id": 15,
                "method": "unknown/method",
                "params": {},
            }
        )
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data["error"]["code"], -32601)


if __name__ == "__main__":
    unittest.main()
