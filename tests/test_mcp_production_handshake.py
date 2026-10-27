"""Tests for MCP production handshake, ping, namespaced tools, RFC 9728 discovery, and full execution sequence."""

from __future__ import annotations

import json
import unittest

from app import create_app
from app.connect import create_connect_app
from app.services import mcp_access_token_service
from models import db
from models.deck import Deck
from models.flashcard import FieldDef, NoteType, Template
from models.user import User
from tests.study_note_fixtures import attach_template, create_note_user


class McpProductionHandshakeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "SERVER_NAME": "api.flama.vn",
            }
        )
        self.connect_app = create_connect_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "SERVER_NAME": "connect.flama.vn",
            }
        )
        self.client = self.app.test_client()
        self.connect_client = self.connect_app.test_client()
        mcp_access_token_service.reset_rate_limit_state()

        with self.app.app_context():
            self.user = create_note_user(
                db.session,
                username="testuser",
                email="testuser@example.com",
                timezone="UTC",
            )
            self.user.set_password("password123")
            self.user_id = self.user.id

            deck = Deck(
                name="IELTS 7.0",
                owner_user_id=self.user_id,
            )
            db.session.add(deck)
            db.session.flush()
            subdeck = Deck(
                name="Bài 3",
                parent_id=deck.id,
                owner_user_id=self.user_id,
            )
            db.session.add(subdeck)

            note_type = NoteType(user_id=self.user_id, name="Vocabulary")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            db.session.add(FieldDef(note_type_id=note_type.id, name="Front", field_type="text", position=0))
            db.session.add(FieldDef(note_type_id=note_type.id, name="Back", field_type="text", position=1))
            attach_template(
                db.session,
                note_type_id=note_type.id,
                owner_user_id=self.user_id,
                name="Card 1",
                front_html="{{Front}}",
                back_html="{{FrontSide}}<hr id='answer'>{{Back}}",
                position=0,
            )

            # Issue an MCP access token with full scopes
            self.token_obj = mcp_access_token_service.issue_token(
                user_id=self.user_id,
                name="Production Test Token",
                scopes=mcp_access_token_service.ALLOWED_SCOPES,
            )
            self.raw_token = self.token_obj.token
            db.session.commit()

    def _post_mcp(self, payload: dict, token: str | None = None, client=None):
        target_client = client or self.client
        headers = {"Content-Type": "application/json", "User-Agent": "openai-mcp/1.0.0"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return target_client.post("/api/mcp", data=json.dumps(payload), headers=headers)

    def test_ping_returns_success_http_200(self):
        """MCP clients send 'ping' to check connection liveness. Must return JSON-RPC 2.0 result {} with HTTP 200."""
        resp = self._post_mcp({"jsonrpc": "2.0", "id": 1, "method": "ping"})
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["jsonrpc"], "2.0")
        self.assertEqual(data["id"], 1)
        self.assertEqual(data["result"], {})

    def test_resources_templates_list_and_logging_set_level(self):
        """Standard MCP methods resources/templates/list and logging/setLevel should return 200."""
        resp = self._post_mcp({"jsonrpc": "2.0", "id": 2, "method": "resources/templates/list"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.get_json()["result"], {"resourceTemplates": []})

        resp2 = self._post_mcp({"jsonrpc": "2.0", "id": 3, "method": "logging/setLevel", "params": {"level": "info"}})
        self.assertEqual(resp2.status_code, 200)
        self.assertEqual(resp2.get_json()["result"], {})

    def test_notifications_initialized_and_other_notifications(self):
        """Accepted notifications return HTTP 202 without a JSON-RPC body."""
        resp = self._post_mcp({"jsonrpc": "2.0", "method": "notifications/initialized"})
        self.assertEqual(resp.status_code, 202)
        self.assertEqual(resp.data, b"")

        resp2 = self._post_mcp({"jsonrpc": "2.0", "method": "notifications/cancelled", "params": {"requestId": 1}})
        self.assertEqual(resp2.status_code, 202)
        self.assertEqual(resp2.data, b"")

    def test_unsupported_mcp_method_returns_http_400_not_404(self):
        """Unknown MCP methods must return HTTP 400 with -32601 METHOD_NOT_FOUND (never HTTP 404)."""
        resp = self._post_mcp({"jsonrpc": "2.0", "id": 4, "method": "nonexistent/method"})
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32601)
        self.assertEqual(data["error"]["data"]["code"], "METHOD_NOT_FOUND")

    def test_namespaced_tool_resolution(self):
        """AI clients call tools with namespace prefixes like 'Flama.search_images' or 'Flama:resolve_deck'."""
        with self.app.app_context():
            # 1. Dot namespace: Flama.resolve_deck
            resp = self._post_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": 10,
                    "method": "tools/call",
                    "params": {
                        "name": "Flama.resolve_deck",
                        "arguments": {"path": "IELTS 7.0::Bài 3"},
                    },
                },
                token=self.raw_token,
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            self.assertIn("result", data)
            content = json.loads(data["result"]["content"][0]["text"])
            self.assertTrue(content["found"])
            self.assertEqual(content["name"], "Bài 3")

            # 2. Dot namespace: Flama.search_images
            resp2 = self._post_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": 11,
                    "method": "tools/call",
                    "params": {
                        "name": "Flama.search_images",
                        "arguments": {"limit": 5},
                    },
                },
                token=self.raw_token,
            )
            self.assertEqual(resp2.status_code, 200)
            data2 = resp2.get_json()
            content2 = json.loads(data2["result"]["content"][0]["text"])
            self.assertEqual(content2["limit"], 5)

            # 3. Colon namespace: Flama:list_my_decks
            resp3 = self._post_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": 12,
                    "method": "tools/call",
                    "params": {
                        "name": "Flama:list_my_decks",
                        "arguments": {},
                    },
                },
                token=self.raw_token,
            )
            self.assertEqual(resp3.status_code, 200)

            # 4. Double underscore namespace: Flama__get_deck_tree
            resp4 = self._post_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": 13,
                    "method": "tools/call",
                    "params": {
                        "name": "Flama__get_deck_tree",
                        "arguments": {},
                    },
                },
                token=self.raw_token,
            )
            self.assertEqual(resp4.status_code, 200)

            # 5. Fallback prefix: flama_search_images
            resp5 = self._post_mcp(
                {
                    "jsonrpc": "2.0",
                    "id": 14,
                    "method": "tools/call",
                    "params": {
                        "name": "flama_search_images",
                        "arguments": {"limit": 5},
                    },
                },
                token=self.raw_token,
            )
            self.assertEqual(resp5.status_code, 200)

    def test_acceptance_criteria_full_sequence_repeatable(self):
        """Verify the full acceptance criteria sequence:
        1. tools/list -> tools visible
        2. list_my_decks() -> success
        3. resolve_deck("IELTS 7.0::Bài 3") -> normal response
        4. search_images(limit=5) -> normal response
        5. get_image(nonexistent) -> structured IMAGE_NOT_FOUND (HTTP 400, JSON-RPC -32602)
        6. search_images(limit=5) -> still succeeds, session remains healthy
        Repeat sequence across multiple iterations.
        """
        with self.app.app_context():
            for iteration in range(3):
                # 1. tools/list
                resp1 = self._post_mcp(
                    {"jsonrpc": "2.0", "id": f"iter_{iteration}_1", "method": "tools/list"},
                    token=self.raw_token,
                )
                self.assertEqual(resp1.status_code, 200)
                tools = resp1.get_json()["result"]["tools"]
                tool_names = [t["name"] for t in tools]
                self.assertIn("list_my_decks", tool_names)
                self.assertIn("resolve_deck", tool_names)
                self.assertIn("search_images", tool_names)
                self.assertIn("get_image", tool_names)
                self.assertIn("import_image", tool_names)

                # 2. list_my_decks()
                resp2 = self._post_mcp(
                    {
                        "jsonrpc": "2.0",
                        "id": f"iter_{iteration}_2",
                        "method": "tools/call",
                        "params": {"name": "list_my_decks", "arguments": {}},
                    },
                    token=self.raw_token,
                )
                self.assertEqual(resp2.status_code, 200)

                # 3. resolve_deck("IELTS 7.0::Bài 3")
                resp3 = self._post_mcp(
                    {
                        "jsonrpc": "2.0",
                        "id": f"iter_{iteration}_3",
                        "method": "tools/call",
                        "params": {
                            "name": "resolve_deck",
                            "arguments": {"path": "IELTS 7.0::Bài 3"},
                        },
                    },
                    token=self.raw_token,
                )
                self.assertEqual(resp3.status_code, 200)
                data3 = json.loads(resp3.get_json()["result"]["content"][0]["text"])
                self.assertTrue(data3["found"])
                self.assertEqual(data3["name"], "Bài 3")

                # 4. search_images(limit=5)
                resp4 = self._post_mcp(
                    {
                        "jsonrpc": "2.0",
                        "id": f"iter_{iteration}_4",
                        "method": "tools/call",
                        "params": {
                            "name": "search_images",
                            "arguments": {"limit": 5},
                        },
                    },
                    token=self.raw_token,
                )
                self.assertEqual(resp4.status_code, 200)
                data4 = json.loads(resp4.get_json()["result"]["content"][0]["text"])
                self.assertEqual(data4["limit"], 5)
                self.assertEqual(data4["items"], [])

                # 5. get_image(image_key="mcp-healthcheck-nonexistent") -> IMAGE_NOT_FOUND structured error
                resp5 = self._post_mcp(
                    {
                        "jsonrpc": "2.0",
                        "id": f"iter_{iteration}_5",
                        "method": "tools/call",
                        "params": {
                            "name": "get_image",
                            "arguments": {"image_key": "mcp-healthcheck-nonexistent"},
                        },
                    },
                    token=self.raw_token,
                )
                self.assertEqual(resp5.status_code, 400)
                data5 = resp5.get_json()
                self.assertEqual(data5["error"]["code"], -32602)
                self.assertEqual(data5["error"]["data"]["code"], "IMAGE_NOT_FOUND")

                # 6. search_images(limit=5) -> still succeeds immediately afterwards
                resp6 = self._post_mcp(
                    {
                        "jsonrpc": "2.0",
                        "id": f"iter_{iteration}_6",
                        "method": "tools/call",
                        "params": {
                            "name": "search_images",
                            "arguments": {"limit": 5},
                        },
                    },
                    token=self.raw_token,
                )
                self.assertEqual(resp6.status_code, 200)
                data6 = json.loads(resp6.get_json()["result"]["content"][0]["text"])
                self.assertEqual(data6["limit"], 5)

    def test_rfc_9728_discovery_routes(self):
        """Test that RFC 9728 discovery routes return 200 on all subpaths and prefix formats."""
        # 1. Main app: root
        resp1 = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(resp1.status_code, 200)
        self.assertIn("resource", resp1.get_json())

        # 2. Main app: subpath /api/mcp
        resp2 = self.client.get("/.well-known/oauth-protected-resource/api/mcp")
        self.assertEqual(resp2.status_code, 200)
        self.assertIn("resource", resp2.get_json())

        # 3. Main app: resource-prefixed /.well-known/oauth-protected-resource
        resp3 = self.client.get("/api/mcp/.well-known/oauth-protected-resource")
        self.assertEqual(resp3.status_code, 200)
        self.assertIn("resource", resp3.get_json())

        # 4. Connect app: subpath /v1/mcp
        resp4 = self.connect_client.get("/.well-known/oauth-protected-resource/v1/mcp")
        self.assertEqual(resp4.status_code, 200)
        self.assertIn("resource", resp4.get_json())

        # 5. Connect app: resource-prefixed
        resp5 = self.connect_client.get("/v1/mcp/.well-known/oauth-protected-resource")
        self.assertEqual(resp5.status_code, 200)
        self.assertIn("resource", resp5.get_json())

        # 6. Auth server metadata with subpath
        resp6 = self.client.get("/.well-known/oauth-authorization-server/api/mcp")
        self.assertEqual(resp6.status_code, 200)
        resp7 = self.client.get("/.well-known/openid-configuration/api/mcp")
        self.assertEqual(resp7.status_code, 200)


if __name__ == "__main__":
    unittest.main()
