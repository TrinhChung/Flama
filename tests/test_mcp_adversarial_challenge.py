"""Empirical Adversarial Challenge Test Suite for Flama MCP AI Search Integration.

Exhaustively probes:
1. Vector 1: Private user notes and study logs leakage via lookup_public_vocabulary.
2. Vector 2: Unpublished, private, and unlisted deck extraction via search_marketplace_decks & get_public_deck_preview.
3. Vector 3: Scraping bypass attempts: limit=1000, limit=-1, offset=-10, sample preview clamping (max 5 cards).
4. Vector 4: Unauthenticated privilege escalation on personal tools (AUTH_REQUIRED / code -32001).
5. Vector 5: stdio JSON-RPC server robustness against malformed payloads, non-object JSON, unknown methods, and protocol attacks.
"""

from __future__ import annotations

import io
import json
import unittest

from app import create_app
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from scripts.flama_mcp_server import process_mcp_message, run_stdio_server


class TestMcpAdversarialChallenge(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )

    def setUp(self):
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()

            # Create test users
            author = User(
                username="adversarial_author",
                email="author@flama.vn",
                timezone="UTC",
                is_admin=False,
            )
            author.set_password("pass123")
            db.session.add(author)

            victim = User(
                username="victim_learner",
                email="victim@flama.vn",
                timezone="Asia/Tokyo",
                is_admin=False,
            )
            victim.set_password("secretpass123")
            db.session.add(victim)
            db.session.flush()

            self.author_id = author.id
            self.victim_id = victim.id

            # Note type
            note_type = NoteType(user_id=author.id, name="Japanese Vocab")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            db.session.add_all([
                FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0, required=True),
                FieldDef(note_type_id=note_type.id, name="Reading", field_type="text", position=1, required=True),
                FieldDef(note_type_id=note_type.id, name="Meaning", field_type="text", position=2, required=True),
                Template(
                    note_type_id=note_type.id,
                    name="Recognition",
                    front_html="<div>{{Word}}</div>",
                    back_html="<div>{{Reading}} - {{Meaning}}</div>",
                    position=0,
                ),
            ])

            # Author's Public Deck with 25 cards (to stress test anti-scraping card limits)
            pub_deck = Deck(name="Mega Public JLPT Deck", owner_user_id=author.id)
            db.session.add(pub_deck)
            db.session.flush()
            self.pub_deck_id = pub_deck.id

            for i in range(25):
                n = Note(
                    user_id=author.id,
                    deck_id=pub_deck.id,
                    note_type_id=note_type.id,
                    field_values={
                        "Word": f"単語_{i}",
                        "Reading": f"たんご_{i}",
                        "Meaning": f"Public meaning definition number {i}",
                    },
                    tags=["public", "n3"],
                )
                db.session.add(n)
                db.session.flush()
                c = Card(note_id=n.id, template_id=note_type.templates[0].id)
                db.session.add(c)

            # Published Marketplace Item for Mega Public Deck
            # Has 25 real cards in DB, but preview_samples_json has 3
            pub_market_item = DeckMarketplaceItem(
                id="pub-mega-deck-001",
                owner_user_id=author.id,
                source_deck_id=pub_deck.id,
                source_note_type_id=note_type.id,
                title="Mega Public Japanese Deck",
                description="Comprehensive Japanese deck with 25 vocabulary cards.",
                primary_category="JLPT",
                tags=["n3", "intermediate"],
                taxonomy_metadata={"framework_level": "N3"},
                publish_status="published",
                pricing_mode="free",
                sample_cards_count=25,
                rating_avg=4.95,
                rating_count=88,
                preview_samples_json=[
                    {"word": "単語_0", "reading": "たんご_0", "meaning": "Public meaning definition number 0"},
                    {"word": "単語_1", "reading": "たんご_1", "meaning": "Public meaning definition number 1"},
                    {"word": "単語_2", "reading": "たんご_2", "meaning": "Public meaning definition number 2"},
                ],
            )
            db.session.add(pub_market_item)

            # Another published deck with NO precomputed preview_samples_json (fallback to live notes)
            pub_deck_fallback = Deck(name="Fallback Public Deck", owner_user_id=author.id)
            db.session.add(pub_deck_fallback)
            db.session.flush()
            for i in range(15):
                n = Note(
                    user_id=author.id,
                    deck_id=pub_deck_fallback.id,
                    note_type_id=note_type.id,
                    field_values={
                        "Word": f"動詞_{i}",
                        "Reading": f"どうし_{i}",
                        "Meaning": f"Fallback verb number {i}",
                    },
                    tags=["verb"],
                )
                db.session.add(n)
                db.session.flush()
                c = Card(note_id=n.id, template_id=note_type.templates[0].id)
                db.session.add(c)

            pub_market_item_fallback = DeckMarketplaceItem(
                id="pub-fallback-deck-002",
                owner_user_id=author.id,
                source_deck_id=pub_deck_fallback.id,
                source_note_type_id=note_type.id,
                title="Fallback Live Notes Deck",
                description="Deck without precomputed samples, extracts from live notes.",
                primary_category="Grammar",
                tags=["verb", "live"],
                taxonomy_metadata={"framework_level": "N4"},
                publish_status="published",
                pricing_mode="free",
                sample_cards_count=15,
                preview_samples_json=None,  # Forces fallback to Note query!
            )
            db.session.add(pub_market_item_fallback)

            # Unpublished Private Deck (status = private)
            priv_market_item = DeckMarketplaceItem(
                id="priv-secret-deck-003",
                owner_user_id=author.id,
                title="Confidential Corporate Internal Deck",
                description="Trade secrets and internal terminology.",
                primary_category="Business",
                publish_status="private",
                pricing_mode="free",
            )
            db.session.add(priv_market_item)

            # Unlisted Deck (status = unlisted)
            unlisted_market_item = DeckMarketplaceItem(
                id="unlisted-deck-004",
                owner_user_id=author.id,
                title="Unlisted VIP Deck",
                description="Only accessible via direct secret URL.",
                primary_category="VIP",
                publish_status="unlisted",
                pricing_mode="paid",
            )
            db.session.add(unlisted_market_item)

            # Archived Deck (status = archived)
            archived_market_item = DeckMarketplaceItem(
                id="archived-deck-005",
                owner_user_id=author.id,
                title="Archived Deprecated Deck",
                description="Archived deck not available for public study.",
                primary_category="Archived",
                publish_status="archived",
                pricing_mode="free",
            )
            db.session.add(archived_market_item)

            # VICTIM'S PRIVATE PERSONAL DATA
            # Personal private deck
            victim_deck = Deck(name="Victim Top Secret Diary Deck", owner_user_id=victim.id)
            db.session.add(victim_deck)
            db.session.flush()

            victim_private_notes = [
                ("機密情報", "きみつじょうほう", "classified confidential top secret leaked credentials"),
                ("パスワード", "ぱすわーど", "password123456789_bank_pin"),
                ("個人メモ", "こじんめも", "medical diagnosis and private diary entry"),
            ]
            for w, r, m in victim_private_notes:
                n = Note(
                    user_id=victim.id,
                    deck_id=victim_deck.id,
                    note_type_id=note_type.id,
                    field_values={"Word": w, "Reading": r, "Meaning": m},
                    tags=["strictly_private", "diary"],
                )
                db.session.add(n)
                db.session.flush()
                c = Card(note_id=n.id, template_id=note_type.templates[0].id)
                db.session.add(c)

            # Author's OWN personal private deck (author has a public deck, but also private notes)
            author_private_deck = Deck(name="Author Secret Private Deck", owner_user_id=author.id)
            db.session.add(author_private_deck)
            db.session.flush()

            author_priv_note = Note(
                user_id=author.id,
                deck_id=author_private_deck.id,
                note_type_id=note_type.id,
                field_values={
                    "Word": "作者の秘密",
                    "Reading": "さくしゃのひみつ",
                    "Meaning": "author unshared private proprietary card",
                },
                tags=["author_private"],
            )
            db.session.add(author_priv_note)

            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _post_mcp(self, payload: dict, token: str | None = None, path: str = "/api/mcp"):
        headers = {"MCP-Protocol-Version": "2025-11-25"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.post(path, json=payload, headers=headers)

    # =======================================================================
    # VECTOR 1: Private Notes & Study Logs Leakage Probing
    # =======================================================================

    def test_vector1_probe_victim_private_notes_exact_word(self):
        """Attacker queries victim's private word '機密情報'."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "機密情報"},
            },
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        matches = data["result"]["structuredContent"]["matches"]
        self.assertEqual(len(matches), 0, "Victim's private note MUST NOT be returned!")

    def test_vector1_probe_victim_private_notes_reading(self):
        """Attacker queries victim's private reading 'きみつじょうほう'."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 102,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "きみつじょうほう"},
            },
        })
        self.assertEqual(response.status_code, 200)
        matches = response.get_json()["result"]["structuredContent"]["matches"]
        self.assertEqual(len(matches), 0)

    def test_vector1_probe_victim_private_notes_meaning_substring(self):
        """Attacker queries confidential keyword in meaning 'password123456789'."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 103,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "password123456789"},
            },
        })
        self.assertEqual(response.status_code, 200)
        matches = response.get_json()["result"]["structuredContent"]["matches"]
        self.assertEqual(len(matches), 0)

    def test_vector1_probe_author_own_private_deck_isolation(self):
        """Author published Deck A, but has private Deck B. Attacker queries word from author's private Deck B."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 104,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "作者の秘密"},
            },
        })
        self.assertEqual(response.status_code, 200)
        matches = response.get_json()["result"]["structuredContent"]["matches"]
        self.assertEqual(len(matches), 0, "Author's private unshared notes MUST NOT leak via author's public decks!")

    def test_vector1_sql_injection_and_wildcard_probing_in_query(self):
        """Attacker injects SQL or wildcard payloads into lookup_public_vocabulary."""
        injection_queries = [
            "' OR '1'='1",
            "' UNION SELECT * FROM notes --",
            "%",
            "_",
            "'; DROP TABLE notes; --",
            "<script>alert(1)</script>",
            "\x00",
        ]
        for idx, injection in enumerate(injection_queries):
            response = self._post_mcp({
                "jsonrpc": "2.0",
                "id": 110 + idx,
                "method": "tools/call",
                "params": {
                    "name": "lookup_public_vocabulary",
                    "arguments": {"query": injection},
                },
            })
            self.assertEqual(response.status_code, 200)
            data = response.get_json()
            self.assertIn("result", data, f"Query '{injection}' failed unexpectedly")
            matches = data["result"]["structuredContent"]["matches"]
            for m in matches:
                self.assertNotIn("機密情報", m.get("term", ""))
                self.assertNotIn("作者の秘密", m.get("term", ""))

    # =======================================================================
    # VECTOR 2: Unpublished, Private, Draft & Unlisted Deck Extraction Probing
    # =======================================================================

    def test_vector2_search_marketplace_rejects_non_published(self):
        """search_marketplace_decks must NEVER return private, unlisted, or draft decks."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 201,
            "method": "tools/call",
            "params": {
                "name": "search_marketplace_decks",
                "arguments": {"query": ""},
            },
        })
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["result"]["structuredContent"]["items"]
        deck_ids = {it["id"] for it in items}

        self.assertIn("pub-mega-deck-001", deck_ids)
        self.assertIn("pub-fallback-deck-002", deck_ids)

        # Probed target decks
        self.assertNotIn("priv-secret-deck-003", deck_ids, "Private deck must not appear in search results")
        self.assertNotIn("unlisted-deck-004", deck_ids, "Unlisted deck must not appear in search results")
        self.assertNotIn("archived-deck-005", deck_ids, "Archived deck must not appear in search results")

    def test_vector2_get_public_deck_preview_direct_access_to_private(self):
        """Attacker guesses UUID and calls get_public_deck_preview on private deck."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 202,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {"deck_item_id": "priv-secret-deck-003"},
            },
        })
        data = response.get_json()
        self.assertIn("error", data, "Private deck preview must return an error")
        self.assertEqual(data["error"]["data"]["code"], "DECK_NOT_PUBLIC")

    def test_vector2_get_public_deck_preview_direct_access_to_unlisted(self):
        """Attacker guesses UUID and calls get_public_deck_preview on unlisted deck."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 203,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {"deck_item_id": "unlisted-deck-004"},
            },
        })
        data = response.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["data"]["code"], "DECK_NOT_PUBLIC")

    def test_vector2_get_public_deck_preview_direct_access_to_archived(self):
        """Attacker calls get_public_deck_preview on archived deck."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 204,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {"deck_item_id": "archived-deck-005"},
            },
        })
        data = response.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["data"]["code"], "DECK_NOT_PUBLIC")

    def test_vector2_get_public_deck_preview_nonexistent_and_malformed_id(self):
        """Attacker passes non-existent, empty, and injection deck IDs."""
        bad_ids = [
            "non-existent-uuid-99999",
            "",
            "   ",
            "' OR '1'='1",
            "../../etc/passwd",
        ]
        for idx, bad_id in enumerate(bad_ids):
            response = self._post_mcp({
                "jsonrpc": "2.0",
                "id": 210 + idx,
                "method": "tools/call",
                "params": {
                    "name": "get_public_deck_preview",
                    "arguments": {"deck_item_id": bad_id},
                },
            })
            data = response.get_json()
            self.assertIn("error", data, f"Expected error for deck_item_id='{bad_id}'")
            err_code = data["error"]["data"]["code"]
            self.assertIn(err_code, ("DECK_NOT_PUBLIC", "INVALID_PARAMS"))

    # =======================================================================
    # VECTOR 3: Anti-Scraping Hard Bounds & Clamping Probing
    # =======================================================================

    def test_vector3_preview_samples_hard_clamped_to_max_5_precomputed(self):
        """Published deck with precomputed samples returns <= 5 samples."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 301,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {"deck_item_id": "pub-mega-deck-001"},
            },
        })
        self.assertEqual(response.status_code, 200)
        structured = response.get_json()["result"]["structuredContent"]
        samples = structured["sample_preview"]
        self.assertLessEqual(len(samples), 5, "Sample preview must never exceed 5 cards!")

    def test_vector3_preview_samples_hard_clamped_to_max_5_live_fallback(self):
        """Published deck with 15 live notes (no precomputed cache) MUST clamp to <= 5 cards."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 302,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {"deck_item_id": "pub-fallback-deck-002"},
            },
        })
        self.assertEqual(response.status_code, 200)
        structured = response.get_json()["result"]["structuredContent"]
        samples = structured["sample_preview"]
        self.assertEqual(len(samples), 5, "Live note extraction must be strictly capped at 5!")
        self.assertEqual(structured["total_cards"], 15)

    def test_vector3_scraping_attempt_massive_and_negative_limit(self):
        """Attacker passes limit=1000, limit=999999, limit=-1, offset=-10."""
        # 1. limit=1000, offset=-10
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 303,
            "method": "tools/call",
            "params": {
                "name": "search_marketplace_decks",
                "arguments": {"limit": 1000, "offset": -10},
            },
        })
        self.assertEqual(response.status_code, 200)
        structured = response.get_json()["result"]["structuredContent"]
        self.assertEqual(structured["limit"], 20, "Limit 1000 must be clamped to MAX_PAGE_LIMIT (20)")
        self.assertEqual(structured["offset"], 0, "Negative offset must be clamped to 0")

        # 2. limit=-1
        response_neg = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 304,
            "method": "tools/call",
            "params": {
                "name": "search_marketplace_decks",
                "arguments": {"limit": -1},
            },
        })
        self.assertEqual(response_neg.status_code, 200)
        structured_neg = response_neg.get_json()["result"]["structuredContent"]
        self.assertEqual(structured_neg["limit"], 1, "Negative limit must clamp to MIN_PAGE_LIMIT (1)")

        # 3. Vocabulary search limit=99999, offset=-50
        response_vocab = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 305,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "単語", "limit": 99999, "offset": -50},
            },
        })
        self.assertEqual(response_vocab.status_code, 200)
        struct_vocab = response_vocab.get_json()["result"]["structuredContent"]
        self.assertEqual(struct_vocab["limit"], 20)
        self.assertEqual(struct_vocab["offset"], 0)

    def test_vector3_offset_exceeding_total(self):
        """Attacker queries offset beyond total results."""
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 306,
            "method": "tools/call",
            "params": {
                "name": "search_marketplace_decks",
                "arguments": {"offset": 50000},
            },
        })
        self.assertEqual(response.status_code, 200)
        struct = response.get_json()["result"]["structuredContent"]
        self.assertEqual(len(struct["items"]), 0)
        self.assertFalse(struct["has_more"])

    # =======================================================================
    # VECTOR 4: Unauthenticated Privilege Escalation on Personal Tools
    # =======================================================================

    def test_vector4_unauthenticated_personal_tools_strictly_rejected(self):
        """Verify code -32001 (AUTH_REQUIRED) is strictly returned for all personal tools."""
        personal_tools = [
            ("list_notes", {}),
            ("create_note", {"fields": {"Word": "hacked"}}),
            ("get_study_queue", {"deck_id": 1}),
            ("get_note", {"note_id": "any-uuid"}),
            ("find_notes", {"query": "secret"}),
            ("update_note", {"note_id": "any-uuid", "fields": {"Word": "mod"}}),
            ("delete_note", {"note_id": "any-uuid"}),
            ("batch_create_notes", {"notes": []}),
            ("batch_update_notes", {"notes": []}),
            ("batch_delete_notes", {"note_ids": []}),
            ("submit_review", {"card_id": 1, "rating": 3}),
            ("get_deck_stats", {"deck_id": 1}),
            ("get_study_stats", {}),
            ("list_my_decks", {}),
            ("create_deck", {"name": "Hacked Deck"}),
            ("delete_deck", {"deck_id": 1}),
        ]

        for idx, (tname, targs) in enumerate(personal_tools):
            response = self._post_mcp({
                "jsonrpc": "2.0",
                "id": 400 + idx,
                "method": "tools/call",
                "params": {"name": tname, "arguments": targs},
            })
            data = response.get_json()
            self.assertIn("error", data, f"Tool '{tname}' did not return error when unauthenticated!")
            self.assertEqual(
                data["error"]["code"],
                -32001,
                f"Tool '{tname}' error code was {data['error']['code']}, expected -32001 (AUTH_REQUIRED)",
            )

    def test_vector4_namespaced_tool_aliases_still_require_auth(self):
        """Attacker tries to bypass auth by prefixing or formatting tool name."""
        aliased_personal_calls = [
            "Flama.list_notes",
            "flama.list_notes",
            "Flama:list_notes",
            "flama:list_notes",
            "Flama/list_notes",
            "flama/list_notes",
            "flama_list_notes",
            "Flama__list_notes",
        ]
        for idx, tool_alias in enumerate(aliased_personal_calls):
            response = self._post_mcp({
                "jsonrpc": "2.0",
                "id": 450 + idx,
                "method": "tools/call",
                "params": {"name": tool_alias, "arguments": {}},
            })
            data = response.get_json()
            self.assertIn("error", data)
            self.assertEqual(data["error"]["code"], -32001, f"Tool alias '{tool_alias}' must require auth")

    def test_vector4_invalid_bearer_token_rejection(self):
        """Attacker sends garbage bearer token."""
        response = self._post_mcp(
            {
                "jsonrpc": "2.0",
                "id": 460,
                "method": "tools/call",
                "params": {"name": "list_notes", "arguments": {}},
            },
            token="invalid_token_123456",
        )
        data = response.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["code"], -32001)

    # =======================================================================
    # VECTOR 5: stdio JSON-RPC Server Edge Cases & Malformed Payloads
    # =======================================================================

    def test_vector5_stdio_malformed_json_syntax(self):
        """Test process_mcp_message with invalid JSON string."""
        client = self.app.test_client()
        bad_payloads = [
            "{invalid json",
            "Hello World",
            "{\"jsonrpc\": \"2.0\", id: 1",
            "}{",
            "   ",
        ]
        for bad in bad_payloads:
            resp_str = process_mcp_message(client, bad)
            if not bad.strip():
                self.assertIsNone(resp_str, "Whitespace line should return None")
            else:
                self.assertIsNotNone(resp_str)
                resp = json.loads(resp_str)
                self.assertIn("error", resp)
                self.assertEqual(resp["error"]["code"], -32700, "Parse error must be -32700")

    def test_vector5_stdio_non_object_json(self):
        """Test process_mcp_message with JSON arrays, numbers, strings."""
        client = self.app.test_client()
        non_objects = [
            "[]",
            "\"just a string\"",
            "12345",
            "true",
            "null",
        ]
        for non_obj in non_objects:
            resp_str = process_mcp_message(client, non_obj)
            self.assertIsNotNone(resp_str)
            resp = json.loads(resp_str)
            self.assertIn("error", resp)
            self.assertEqual(resp["error"]["code"], -32600, "Invalid Request must be -32600")

    def test_vector5_unknown_mcp_method(self):
        """Test unknown methods return -32601 METHOD_NOT_FOUND."""
        client = self.app.test_client()
        unknown_methods = [
            "unknown_method",
            "system.reboot",
            "eval",
            "flama/admin",
        ]
        for m in unknown_methods:
            req = json.dumps({"jsonrpc": "2.0", "id": 501, "method": m})
            resp_str = process_mcp_message(client, req)
            self.assertIsNotNone(resp_str)
            resp = json.loads(resp_str)
            self.assertIn("error", resp)
            self.assertEqual(resp["error"]["code"], -32601, f"Method '{m}' must return -32601")

    def test_vector5_id_types_support(self):
        """Test JSON-RPC 2.0 supports string, int, negative int, null IDs."""
        client = self.app.test_client()
        ids_to_test = ["str-id-123", 42, 0, -99, None]
        for test_id in ids_to_test:
            req = json.dumps({
                "jsonrpc": "2.0",
                "id": test_id,
                "method": "ping",
            })
            resp_str = process_mcp_message(client, req)
            self.assertIsNotNone(resp_str)
            resp = json.loads(resp_str)
            self.assertEqual(resp["id"], test_id, f"Response ID must match request ID {test_id}")
            self.assertIn("result", resp)

    def test_vector5_stdio_stream_handling_with_mixed_traffic(self):
        """Test run_stdio_server with a mix of valid, invalid, notification, and tool call lines."""
        lines = [
            "   ",  # blank line
            "{broken json",  # parse error
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),  # notification (no response)
            json.dumps({"jsonrpc": "2.0", "id": "req-1", "method": "ping"}),  # ping
            json.dumps({"jsonrpc": "2.0", "id": "req-2", "method": "tools/call", "params": {"name": "get_flama_documentation", "arguments": {"topic": "faq"}}}),
            "[1, 2, 3]",  # non-object error
        ]

        input_buffer = io.StringIO("\n".join(lines) + "\n")
        output_buffer = io.StringIO()

        run_stdio_server(
            input_stream=input_buffer,
            output_stream=output_buffer,
            app_instance=self.app,
        )

        output_lines = [l.strip() for l in output_buffer.getvalue().strip().split("\n") if l.strip()]
        # Expected outputs: broken json (error), ping (result), doc (result), [1,2,3] (error) -> 4 responses
        self.assertEqual(len(output_lines), 4)

        r0 = json.loads(output_lines[0])
        self.assertEqual(r0["error"]["code"], -32700)

        r1 = json.loads(output_lines[1])
        self.assertEqual(r1["id"], "req-1")
        self.assertEqual(r1["result"], {})

        r2 = json.loads(output_lines[2])
        self.assertEqual(r2["id"], "req-2")
        self.assertIn("Frequently Asked Questions", r2["result"]["structuredContent"]["content"])

        r3 = json.loads(output_lines[3])
        self.assertEqual(r3["error"]["code"], -32600)

    # =======================================================================
    # ADVANCED PROTOCOL FUZZING & ERROR CODE VERIFICATION
    # =======================================================================

    def test_advanced_http_jsonrpc_envelope_fuzzing(self):
        """Test HTTP endpoint /api/mcp with malformed outer envelopes."""
        # 1. Missing jsonrpc field
        resp = self.client.post("/api/mcp", json={"id": 1, "method": "ping"}, headers={"MCP-Protocol-Version": "2025-11-25"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], -32600)

        # 2. Invalid jsonrpc version "1.0"
        resp = self.client.post("/api/mcp", json={"jsonrpc": "1.0", "id": 1, "method": "ping"}, headers={"MCP-Protocol-Version": "2025-11-25"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], -32600)

        # 3. Method is integer
        resp = self.client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": 12345}, headers={"MCP-Protocol-Version": "2025-11-25"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], -32600)

        # 4. Params is list instead of dict
        resp = self.client.post("/api/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping", "params": [1, 2, 3]}, headers={"MCP-Protocol-Version": "2025-11-25"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], -32602)

        # 5. Empty request body
        resp = self.client.post("/api/mcp", data="", content_type="application/json", headers={"MCP-Protocol-Version": "2025-11-25"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["code"], -32700)

    def test_advanced_public_tool_missing_required_arguments(self):
        """Test public tools when mandatory arguments are missing or malformed."""
        # 1. lookup_public_vocabulary without query
        resp = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 601,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {},
            },
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32602)
        self.assertEqual(data["error"]["data"]["code"], "INVALID_PARAMS")

        # 2. get_public_deck_preview without deck_item_id
        resp = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 602,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {},
            },
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32602)
        self.assertEqual(data["error"]["data"]["code"], "INVALID_PARAMS")

        # 3. Unknown tool call
        resp = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 603,
            "method": "tools/call",
            "params": {
                "name": "non_existent_tool_xyz",
                "arguments": {},
            },
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32602)
        self.assertEqual(data["error"]["data"]["code"], "UNKNOWN_TOOL")

    def test_advanced_resources_and_prompts_edge_cases(self):
        """Test resource path traversal and prompt error codes."""
        # 1. Path traversal attempt on resources/read
        resp = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 701,
            "method": "resources/read",
            "params": {"uri": "flama://docs/../../etc/passwd"},
        })
        self.assertEqual(resp.status_code, 400)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32602)
        self.assertEqual(data["error"]["data"]["code"], "RESOURCE_NOT_FOUND")

        # 2. Non-existent resource
        resp = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 702,
            "method": "resources/read",
            "params": {"uri": "flama://docs/definitely_not_a_topic"},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["data"]["code"], "RESOURCE_NOT_FOUND")

        # 3. prompts/get should return -32602 PROMPT_NOT_FOUND
        resp = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 703,
            "method": "prompts/get",
            "params": {"name": "test_prompt"},
        })
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(resp.get_json()["error"]["data"]["code"], "PROMPT_NOT_FOUND")

    def test_concurrent_stdio_requests(self):
        """Stress-test concurrent request handling across multiple threads."""
        import concurrent.futures

        client = self.app.test_client()

        def send_probe(probe_id: int):
            req = json.dumps({
                "jsonrpc": "2.0",
                "id": probe_id,
                "method": "tools/call",
                "params": {
                    "name": "lookup_public_vocabulary",
                    "arguments": {"query": f"単語_{probe_id % 5}"},
                },
            })
            resp_str = process_mcp_message(client, req)
            return json.loads(resp_str)

        with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
            futures = [executor.submit(send_probe, i) for i in range(40)]
            results = [f.result() for f in concurrent.futures.as_completed(futures)]

        self.assertEqual(len(results), 40)
        for r in results:
            self.assertIn("result", r)
            self.assertIn("structuredContent", r["result"])


if __name__ == "__main__":
    unittest.main()

