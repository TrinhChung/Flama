"""Integration tests for the minimal MCP list_my_decks tool."""

from __future__ import annotations

import unittest
from datetime import datetime

from app import create_app
from models import db
from models.deck import Deck
from models.user import User


class McpListMyDecksTests(unittest.TestCase):
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
            owner = User(username="mcp-owner", email="mcp-owner@example.com", timezone="UTC")
            owner.set_password("password")
            other = User(username="mcp-other", email="mcp-other@example.com", timezone="UTC")
            other.set_password("password")
            db.session.add_all([owner, other])
            db.session.flush()

            self.owner_id = owner.id
            self.other_user_id = other.id

            db.session.add_all(
                [
                    Deck(
                        name="Owned Root",
                        owner_user_id=self.owner_id,
                        description="Root deck for MCP test",
                        position=1,
                        created_at=datetime(2026, 1, 2, 3, 4, 5),
                    ),
                    Deck(
                        name="Owned Child",
                        owner_user_id=self.owner_id,
                        description="Child deck for MCP test",
                        position=2,
                        created_at=datetime(2026, 1, 3, 3, 4, 5),
                    ),
                    Deck(
                        name="Other User Deck",
                        owner_user_id=self.other_user_id,
                        position=3,
                        created_at=datetime(2026, 1, 4, 3, 4, 5),
                    ),
                    Deck(
                        name="Legacy Null Owner",
                        owner_user_id=None,
                        position=4,
                        created_at=datetime(2026, 1, 5, 3, 4, 5),
                    ),
                ]
            )
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _login_owner(self):
        return self.client.post(
            "/login",
            data={"email": "mcp-owner@example.com", "password": "password"},
            follow_redirects=True,
        )

    def _mcp_post(self, payload: dict):
        return self.client.post(
            "/api/mcp",
            json=payload,
            headers={"MCP-Protocol-Version": "2025-11-25"},
        )

    def test_mcp_requires_authenticated_user(self):
        response = self._mcp_post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {},
            }
        )

        self.assertEqual(response.status_code, 401)
        payload = response.get_json()
        self.assertEqual(payload["error"]["message"], "Authentication required.")

    def test_initialize_returns_tools_capability(self):
        self._login_owner()

        response = self._mcp_post(
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {
                    "protocolVersion": "2025-11-25",
                    "capabilities": {},
                    "clientInfo": {"name": "test-client", "version": "0.1.0"},
                },
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        self.assertEqual(payload["result"]["protocolVersion"], "2025-11-25")
        self.assertIn("tools", payload["result"]["capabilities"])

    def test_tools_list_exposes_only_list_my_decks(self):
        self._login_owner()

        response = self._mcp_post(
            {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/list",
                "params": {},
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        tools = payload["result"]["tools"]
        self.assertEqual(len(tools), 1)
        self.assertEqual(tools[0]["name"], "list_my_decks")
        self.assertEqual(tools[0]["inputSchema"]["properties"], {})

    def test_list_my_decks_returns_only_owned_decks(self):
        self._login_owner()

        response = self._mcp_post(
            {
                "jsonrpc": "2.0",
                "id": 3,
                "method": "tools/call",
                "params": {
                    "name": "list_my_decks",
                    "arguments": {},
                },
            }
        )

        self.assertEqual(response.status_code, 200)
        payload = response.get_json()
        decks = payload["result"]["structuredContent"]["decks"]
        deck_names = {item["name"] for item in decks}

        self.assertEqual(deck_names, {"Owned Root", "Owned Child"})
        self.assertNotIn("Other User Deck", deck_names)
        self.assertNotIn("Legacy Null Owner", deck_names)
        self.assertTrue(all("deck_id" in item for item in decks))
        self.assertTrue(any(item.get("description") == "Root deck for MCP test" for item in decks))
        self.assertTrue(any(item.get("created_at") == "2026-01-02T03:04:05" for item in decks))

    def test_list_my_decks_rejects_user_id_argument(self):
        self._login_owner()

        response = self._mcp_post(
            {
                "jsonrpc": "2.0",
                "id": 4,
                "method": "tools/call",
                "params": {
                    "name": "list_my_decks",
                    "arguments": {"user_id": self.other_user_id},
                },
            }
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertEqual(payload["error"]["data"]["field"], "arguments")

    def test_list_my_decks_rejects_top_level_user_id_param(self):
        self._login_owner()

        response = self._mcp_post(
            {
                "jsonrpc": "2.0",
                "id": 5,
                "method": "tools/call",
                "params": {
                    "name": "list_my_decks",
                    "arguments": {},
                    "user_id": self.other_user_id,
                },
            }
        )

        self.assertEqual(response.status_code, 400)
        payload = response.get_json()
        self.assertEqual(payload["error"]["code"], -32602)
        self.assertEqual(payload["error"]["data"]["field"], "params")
