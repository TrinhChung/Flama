"""Adversarial stress-test suite for Flama MCP AI Search Integration.

Authored by Challenger 2 to aggressively probe:
1. Private user note / study log data leakage via public tools.
2. Unpublished / draft / unlisted deck retrieval attempts.
3. Mass-scraping & pagination bounds bypassing (limit=1000, limit=-1, offset=-10, sample capping <= 5).
4. Unauthenticated calls to personal tools (strictly returning -32001 AUTH_REQUIRED).
5. Stdio JSON-RPC server malformed payloads, protocol abuse, and edge cases.
"""

from __future__ import annotations

from datetime import datetime
import io
import json
import unittest

from app import create_app
from models import db
from models.card import Card
from models.review_event import ReviewEvent
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User
from scripts.flama_mcp_server import process_mcp_message, run_stdio_server


class TestMcpAdversarialChallenger(unittest.TestCase):
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

            # 1. Users
            public_author = User(
                username="public_sensei",
                email="sensei@flama.vn",
                timezone="Asia/Tokyo",
                is_admin=False,
            )
            public_author.set_password("pass1234")
            db.session.add(public_author)

            secret_learner = User(
                username="agent_007",
                email="secret@mi6.gov.uk",
                timezone="UTC",
                is_admin=False,
            )
            secret_learner.set_password("pass1234")
            db.session.add(secret_learner)
            db.session.flush()

            self.author_id = public_author.id
            self.learner_id = secret_learner.id

            # 2. Shared Note Type
            note_type = NoteType(user_id=public_author.id, name="Vocabulary Standard")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            db.session.add_all([
                FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0, required=True),
                FieldDef(note_type_id=note_type.id, name="Reading", field_type="text", position=1, required=True),
                FieldDef(note_type_id=note_type.id, name="Meaning", field_type="text", position=2, required=True),
                Template(
                    note_type_id=note_type.id,
                    name="Default",
                    front_html="<div>{{Word}}</div>",
                    back_html="<div>{{Reading}} - {{Meaning}}</div>",
                    position=0,
                ),
            ])

            # 3. Published Deck with 15 cards (to test sample preview truncation)
            pub_deck = Deck(name="Published Deck 101", owner_user_id=public_author.id)
            db.session.add(pub_deck)
            db.session.flush()
            self.pub_deck_id = pub_deck.id

            pub_words = [
                (f"単語_{i}", f"たんご_{i}", f"meaning_{i}")
                for i in range(1, 16)
            ]
            for w, r, m in pub_words:
                n = Note(
                    user_id=public_author.id,
                    deck_id=pub_deck.id,
                    note_type_id=note_type.id,
                    field_values={"Word": w, "Reading": r, "Meaning": m},
                    tags=["jlpt", "public_sample"],
                )
                db.session.add(n)
                db.session.flush()
                c = Card(note_id=n.id, template_id=note_type.templates[0].id)
                db.session.add(c)

            # Published Marketplace Item
            pub_item = DeckMarketplaceItem(
                id="pub-deck-adv-01",
                owner_user_id=public_author.id,
                source_deck_id=pub_deck.id,
                source_note_type_id=note_type.id,
                title="Japanese Core 1000 Verified",
                description="Publicly verified Japanese deck for all learners.",
                primary_category="JLPT",
                tags=["n3", "core", "jlpt"],
                taxonomy_metadata={"framework_level": "N3", "category": "JLPT"},
                publish_status="published",
                pricing_mode="free",
                sample_cards_count=len(pub_words),
                rating_avg=4.95,
                rating_count=120,
                install_count=800,
                # Even if preview_samples_json contains 10 items, code must truncate to <= 5
                preview_samples_json=[
                    {"word": f"単語_{i}", "reading": f"たんご_{i}", "meaning": f"meaning_{i}"}
                    for i in range(1, 11)
                ],
            )
            db.session.add(pub_item)

            # 4. Various Non-Published Marketplace Items
            statuses_to_test = ["private", "unlisted", "archived"]
            for idx, status in enumerate(statuses_to_test, 1):
                item = DeckMarketplaceItem(
                    id=f"nonpub-{status}-{idx}",
                    owner_user_id=public_author.id,
                    title=f"NonPublic Deck {status.upper()}",
                    description=f"Secret deck in {status} mode.",
                    primary_category="Classified",
                    tags=["secret", status],
                    taxonomy_metadata={"framework_level": "N2"},
                    publish_status=status,
                    pricing_mode="free",
                    sample_cards_count=5,
                    preview_samples_json=[
                        {"word": f"秘密_{status}", "reading": "ひみつ", "meaning": f"Secret in {status}"}
                    ],
                )
                db.session.add(item)

            # 5. Secret Learner's Personal Deck and Highly Sensitive Notes
            learner_secret_deck = Deck(name="Classified Mission Notes", owner_user_id=secret_learner.id)
            db.session.add(learner_secret_deck)
            db.session.flush()
            self.learner_secret_deck_id = learner_secret_deck.id

            secret_notes_data = [
                ("機密情報", "きみつじょうほう", "classified information intelligence"),
                ("極秘ミッション", "ごくひみっしょん", "top secret mission MI6"),
                ("核兵器コード", "かくへいきこーど", "nuclear launch passkey 007"),
                ("暗号通貨鍵", "あんごうつうかかぎ", "crypto private key bitcoin"),
            ]
            for w, r, m in secret_notes_data:
                sn = Note(
                    user_id=secret_learner.id,
                    deck_id=learner_secret_deck.id,
                    note_type_id=note_type.id,
                    field_values={"Word": w, "Reading": r, "Meaning": m},
                    tags=["classified", "mi6", "private_only"],
                )
                db.session.add(sn)
                db.session.flush()
                sc = Card(note_id=sn.id, template_id=note_type.templates[0].id)
                db.session.add(sc)
                db.session.flush()

                # Also add study logs to check if review data could leak
                review_log = ReviewEvent(
                    card_id=str(sc.id),
                    user_id=secret_learner.id,
                    reviewed_at=datetime.utcnow(),
                    rating="good",
                    mode="srs",
                    duration_ms=2500,
                )
                db.session.add(review_log)

            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _call_rpc(self, method: str, params: dict | None = None, req_id: int | str = 1, token: str | None = None):
        payload: dict = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }
        if params is not None:
            payload["params"] = params
        headers = {"MCP-Protocol-Version": "2025-11-25"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        return self.client.post("/api/mcp", json=payload, headers=headers)

    # =======================================================================
    # SECTION 1: PRIVACY LEAK PROBES (lookup_public_vocabulary & notes)
    # =======================================================================

    def test_probe_lookup_vocabulary_against_private_words(self):
        """Adversarial probe: Try to locate secret words stored in private decks."""
        secret_queries = [
            "機密情報",
            "極秘ミッション",
            "核兵器コード",
            "暗号通貨鍵",
            "きみつじょうほう",
            "ごくひみっしょん",
            "classified information",
            "nuclear launch",
            "bitcoin",
            "MI6",
        ]
        for query in secret_queries:
            resp = self._call_rpc(
                "tools/call",
                {"name": "lookup_public_vocabulary", "arguments": {"query": query}},
            )
            self.assertEqual(resp.status_code, 200, f"Query '{query}' failed with status {resp.status_code}")
            data = resp.get_json()
            matches = data["result"]["structuredContent"]["matches"]
            self.assertEqual(
                len(matches),
                0,
                f"PRIVACY VIOLATION: Private word leaked for query '{query}': {matches}",
            )

    def test_probe_lookup_vocabulary_sql_injection_and_wildcards(self):
        """Adversarial probe: Try SQL injection and wildcards to dump database notes."""
        adversarial_queries = [
            "%",
            "%%",
            "_",
            "%_%",
            "' OR '1'='1",
            "' OR 1=1 --",
            "admin' --",
            "'; DROP TABLE notes; --",
            "\" OR \"\"=\"",
            "*",
            "?*",
            "<script>alert(1)</script>",
        ]
        for query in adversarial_queries:
            resp = self._call_rpc(
                "tools/call",
                {"name": "lookup_public_vocabulary", "arguments": {"query": query}},
            )
            self.assertEqual(resp.status_code, 200)
            data = resp.get_json()
            # If matches are returned, none of them should ever be from the learner's private deck
            matches = data["result"]["structuredContent"]["matches"]
            for match in matches:
                self.assertNotEqual(
                    match.get("deck_id"),
                    str(self.learner_secret_deck_id),
                    f"PRIVACY LEAK: Private deck notes returned on wildcard query '{query}'",
                )
                self.assertNotIn("機密", match.get("term", ""))
                self.assertNotIn("核兵器", match.get("term", ""))

    def test_probe_lookup_vocabulary_does_not_leak_unpublished_deck_words(self):
        """Adversarial probe: Search for words in draft, unlisted, or private marketplace decks."""
        for status in ["private", "unlisted", "archived"]:
            resp = self._call_rpc(
                "tools/call",
                {"name": "lookup_public_vocabulary", "arguments": {"query": f"秘密_{status}"}},
            )
            self.assertEqual(resp.status_code, 200)
            matches = resp.get_json()["result"]["structuredContent"]["matches"]
            self.assertEqual(
                len(matches),
                0,
                f"PRIVACY LEAK: Word from '{status}' marketplace deck was leaked: {matches}",
            )

    # =======================================================================
    # SECTION 2: UNLISTED & PRIVATE DECK EXTRACTION PROBES
    # =======================================================================

    def test_probe_search_marketplace_decks_never_returns_non_published(self):
        """Adversarial probe: Search marketplace decks with wide filters to uncover hidden decks."""
        # 1. Broad query matching all
        resp = self._call_rpc(
            "tools/call",
            {"name": "search_marketplace_decks", "arguments": {"query": "", "limit": 20}},
        )
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["result"]["structuredContent"]["items"]
        returned_ids = {item["id"] for item in items}

        self.assertIn("pub-deck-adv-01", returned_ids)

        forbidden_statuses = ["private", "unlisted", "archived"]
        for status in forbidden_statuses:
            self.assertNotIn(
                f"nonpub-{status}",
                [item["id"].split("-")[0] + "-" + item["id"].split("-")[1] for item in items if "-" in item["id"]],
                f"SECURITY VIOLATION: Deck with status '{status}' was included in search results!",
            )

        # 2. Targeted search for secret keywords in titles
        for status in forbidden_statuses:
            resp_target = self._call_rpc(
                "tools/call",
                {"name": "search_marketplace_decks", "arguments": {"query": status}},
            )
            self.assertEqual(resp_target.status_code, 200)
            items_target = resp_target.get_json()["result"]["structuredContent"]["items"]
            self.assertEqual(
                len(items_target),
                0,
                f"SECURITY VIOLATION: Unpublished deck found searching for '{status}': {items_target}",
            )

    def test_probe_get_public_deck_preview_rejects_non_published_and_invalid(self):
        """Adversarial probe: Try direct retrieval of private, draft, and non-existent deck previews."""
        test_cases = [
            ("nonpub-private-1", "DECK_NOT_PUBLIC"),
            ("nonpub-unlisted-2", "DECK_NOT_PUBLIC"),
            ("nonpub-archived-3", "DECK_NOT_PUBLIC"),
            ("non-existent-uuid-9999", "DECK_NOT_PUBLIC"),
            (str(self.learner_secret_deck_id), "DECK_NOT_PUBLIC"),
            ("'; DROP TABLE decks; --", "DECK_NOT_PUBLIC"),
        ]

        for deck_id, expected_code in test_cases:
            resp = self._call_rpc(
                "tools/call",
                {"name": "get_public_deck_preview", "arguments": {"deck_item_id": deck_id}},
            )
            # Should be handled gracefully with JSON-RPC error
            data = resp.get_json()
            self.assertIn("error", data, f"Expected error for deck_id='{deck_id}' but got: {data}")
            err = data["error"]
            err_code = err.get("data", {}).get("code")
            self.assertEqual(
                err_code,
                expected_code,
                f"For deck_id='{deck_id}', expected code {expected_code}, got {err_code} (msg: {err.get('message')})",
            )

    def test_probe_get_public_deck_preview_missing_id_returns_invalid_params(self):
        """Adversarial probe: Call get_public_deck_preview with empty or missing ID."""
        for bad_id in ["", "   "]:
            resp = self._call_rpc(
                "tools/call",
                {"name": "get_public_deck_preview", "arguments": {"deck_item_id": bad_id}},
            )
            data = resp.get_json()
            self.assertIn("error", data)
            self.assertEqual(data["error"]["data"]["code"], "INVALID_PARAMS")

    # =======================================================================
    # SECTION 3: ANTI-SCRAPING & BOUNDS STRESS PROBES
    # =======================================================================

    def test_probe_anti_scraping_preview_cards_hard_capped_at_five(self):
        """Adversarial probe: Verify that get_public_deck_preview strictly caps sample cards to <= 5."""
        resp = self._call_rpc(
            "tools/call",
            {"name": "get_public_deck_preview", "arguments": {"deck_item_id": "pub-deck-adv-01"}},
        )
        self.assertEqual(resp.status_code, 200)
        structured = resp.get_json()["result"]["structuredContent"]

        samples = structured.get("sample_preview", [])
        self.assertIsInstance(samples, list)
        self.assertGreater(len(samples), 0)
        self.assertLessEqual(
            len(samples),
            5,
            f"ANTI-SCRAPING VIOLATION: get_public_deck_preview returned {len(samples)} cards, exceeding hard limit of 5!",
        )

        # Check total cards is reported as 15 without leaking all 15 in samples
        self.assertEqual(structured.get("total_cards"), 15)

    def test_probe_search_marketplace_decks_sample_preview_also_capped(self):
        """Adversarial probe: Verify search_marketplace_decks also caps each deck's sample_preview to <= 5."""
        resp = self._call_rpc(
            "tools/call",
            {"name": "search_marketplace_decks", "arguments": {"query": "Verified"}},
        )
        self.assertEqual(resp.status_code, 200)
        items = resp.get_json()["result"]["structuredContent"]["items"]
        self.assertGreater(len(items), 0)
        for item in items:
            samples = item.get("sample_preview", [])
            self.assertLessEqual(
                len(samples),
                5,
                f"ANTI-SCRAPING VIOLATION: search item {item['id']} sample preview has {len(samples)} cards, > 5!",
            )

    def test_probe_scraping_extreme_limits_and_negative_offsets(self):
        """Adversarial probe: Pass limit=1000, limit=-1, offset=-10 and verify bounds clamping."""
        # 1. Limit = 1000 on deck search
        resp_1000 = self._call_rpc(
            "tools/call",
            {"name": "search_marketplace_decks", "arguments": {"limit": 1000, "offset": -10}},
        )
        self.assertEqual(resp_1000.status_code, 200)
        data_1000 = resp_1000.get_json()["result"]["structuredContent"]
        self.assertEqual(data_1000["limit"], 20, "Requested limit=1000 must be clamped to max 20")
        self.assertEqual(data_1000["offset"], 0, "Requested offset=-10 must be clamped to 0")

        # 2. Limit = -1 on deck search
        resp_neg = self._call_rpc(
            "tools/call",
            {"name": "search_marketplace_decks", "arguments": {"limit": -1, "offset": -50}},
        )
        self.assertEqual(resp_neg.status_code, 200)
        data_neg = resp_neg.get_json()["result"]["structuredContent"]
        self.assertEqual(data_neg["limit"], 1, "Requested limit=-1 must be clamped to min 1")
        self.assertEqual(data_neg["offset"], 0, "Requested offset=-50 must be clamped to 0")

        # 3. Limit = 1000 on lookup_public_vocabulary
        resp_vocab_1000 = self._call_rpc(
            "tools/call",
            {"name": "lookup_public_vocabulary", "arguments": {"query": "単語", "limit": 1000, "offset": -100}},
        )
        self.assertEqual(resp_vocab_1000.status_code, 200)
        data_vocab_1000 = resp_vocab_1000.get_json()["result"]["structuredContent"]
        self.assertEqual(data_vocab_1000["limit"], 20, "Vocab query limit=1000 must be clamped to 20")
        self.assertEqual(data_vocab_1000["offset"], 0, "Vocab query offset=-100 must be clamped to 0")

        # 4. Limit = -10 on lookup_public_vocabulary
        resp_vocab_neg = self._call_rpc(
            "tools/call",
            {"name": "lookup_public_vocabulary", "arguments": {"query": "単語", "limit": -10}},
        )
        self.assertEqual(resp_vocab_neg.status_code, 200)
        data_vocab_neg = resp_vocab_neg.get_json()["result"]["structuredContent"]
        self.assertEqual(data_vocab_neg["limit"], 1, "Vocab query limit=-10 must be clamped to min 1")

    # =======================================================================
    # SECTION 4: AUTHENTICATION ENFORCEMENT PROBES (Personal Tools)
    # =======================================================================

    def test_probe_personal_tools_unauthenticated_strictly_return_32001(self):
        """Adversarial probe: Call all personal / mutating tools without token and verify code -32001."""
        personal_tools_catalog = [
            ("list_notes", {}),
            ("create_note", {"deck_id": 1, "fields": {"Word": "hacker"}}),
            ("get_study_queue", {"deck_id": 1}),
            ("list_my_decks", {}),
            ("get_deck_tree", {}),
            ("get_deck", {"deck_id": 1}),
            ("resolve_deck", {"path": "Japanese"}),
            ("create_deck", {"name": "Injected Deck"}),
            ("update_deck", {"deck_id": 1, "name": "Changed"}),
            ("delete_deck", {"deck_id": 1, "confirm": True}),
            ("get_note", {"note_id": "1"}),
            ("find_notes", {"query": "test"}),
            ("update_note", {"note_id": "1", "fields": {"Word": "changed"}}),
            ("delete_note", {"note_id": "1", "confirm": True}),
            ("move_note", {"note_id": "1", "deck_id": 2}),
            ("add_tags", {"note_ids": ["1"], "tags": ["injected"]}),
            ("remove_tags", {"note_ids": ["1"], "tags": ["injected"]}),
            ("batch_create_notes", {"notes": []}),
            ("batch_update_notes", {"notes": []}),
            ("batch_delete_notes", {"note_ids": ["1"], "confirm": True}),
            ("batch_move_notes", {"note_ids": ["1"], "deck_id": 2}),
            ("get_card", {"card_id": 1}),
            ("submit_review", {"card_id": 1, "rating": 3}),
            ("get_deck_stats", {"deck_id": 1}),
            ("get_study_stats", {}),
            ("list_note_types", {}),
            ("get_note_type_schema", {"note_type_id": "1"}),
        ]

        for tool_name, args in personal_tools_catalog:
            resp = self._call_rpc(
                "tools/call",
                {"name": tool_name, "arguments": args},
            )
            self.assertEqual(
                resp.status_code,
                401,
                f"Tool '{tool_name}' should return HTTP 401 when unauthenticated, got {resp.status_code}",
            )
            data = resp.get_json()
            self.assertIn("error", data, f"Tool '{tool_name}' missing error envelope")
            self.assertEqual(
                data["error"]["code"],
                -32001,
                f"Tool '{tool_name}' error code must be -32001 (AUTH_REQUIRED), got {data['error']['code']}",
            )
            self.assertIn(
                "WWW-Authenticate",
                resp.headers,
                f"Tool '{tool_name}' 401 response must include WWW-Authenticate header",
            )

    def test_probe_personal_tools_with_bogus_token_returns_32001(self):
        """Adversarial probe: Call personal tools with fake bearer token."""
        resp = self._call_rpc(
            "tools/call",
            {"name": "list_notes", "arguments": {}},
            token="bogus-bearer-token-xyz-123456",
        )
        self.assertEqual(resp.status_code, 401)
        data = resp.get_json()
        self.assertEqual(data["error"]["code"], -32001)

    # =======================================================================
    # SECTION 5: STDIO SERVER JSON-RPC PROTOCOL & EDGE CASES PROBES
    # =======================================================================

    def test_probe_stdio_server_malformed_json_syntax(self):
        """Adversarial probe: Feed invalid JSON syntax into process_mcp_message."""
        malformed_lines = [
            "{invalid-json",
            "{\"key\": ",
            "Hello, world!",
            "{'single_quotes': 1}",
            "True",
            "None",
            "undefined",
        ]
        for line in malformed_lines:
            resp_str = process_mcp_message(self.client, line)
            self.assertIsNotNone(resp_str, f"Expected error response for line '{line}'")
            parsed = json.loads(resp_str)
            self.assertEqual(parsed.get("jsonrpc"), "2.0")
            self.assertIsNone(parsed.get("id"))
            self.assertEqual(parsed.get("error", {}).get("code"), -32700, f"Line '{line}' should trigger -32700 Parse error")

    def test_probe_stdio_server_empty_and_whitespace_lines_ignored(self):
        """Adversarial probe: Empty lines and whitespace should return None (no output)."""
        empty_lines = ["", "   ", "\t", "\n", " \t \r\n "]
        for line in empty_lines:
            resp_str = process_mcp_message(self.client, line)
            self.assertIsNone(resp_str, f"Whitespace line '{repr(line)}' should return None")

    def test_probe_stdio_server_non_object_json_payloads(self):
        """Adversarial probe: JSON-RPC expects a JSON object, not a primitive or array."""
        non_object_payloads = [
            json.dumps(["array", "of", "values"]),
            json.dumps("just a string"),
            json.dumps(12345),
            json.dumps(True),
            json.dumps(None),
        ]
        for payload in non_object_payloads:
            resp_str = process_mcp_message(self.client, payload)
            self.assertIsNotNone(resp_str)
            parsed = json.loads(resp_str)
            self.assertEqual(parsed.get("error", {}).get("code"), -32600, f"Payload '{payload}' should trigger -32600")

    def test_probe_stdio_server_invalid_rpc_envelopes(self):
        """Adversarial probe: Valid JSON but missing jsonrpc or method."""
        invalid_envelopes = [
            {"id": 1, "method": "ping"},  # missing jsonrpc: "2.0"
            {"jsonrpc": "1.0", "id": 1, "method": "ping"},  # wrong jsonrpc version
            {"jsonrpc": "2.0", "id": 1},  # missing method
            {"jsonrpc": "2.0", "id": 1, "method": ""},  # empty method
            {"jsonrpc": "2.0", "id": 1, "method": 12345},  # integer method
            {"jsonrpc": "2.0", "id": 1, "method": "ping", "params": "not a dict"},  # invalid params type
        ]
        for env in invalid_envelopes:
            resp_str = process_mcp_message(self.client, json.dumps(env))
            self.assertIsNotNone(resp_str)
            parsed = json.loads(resp_str)
            self.assertIn("error", parsed, f"Envelope {env} should return error")
            err_code = parsed["error"]["code"]
            self.assertIn(err_code, (-32600, -32602), f"Envelope {env} error code should be -32600 or -32602")

    def test_probe_stdio_server_unknown_method_and_unknown_tool(self):
        """Adversarial probe: Unknown RPC method returns -32601; unknown tool returns -32602."""
        # 1. Unknown method
        resp_unknown_method = process_mcp_message(
            self.client,
            json.dumps({"jsonrpc": "2.0", "id": 99, "method": "quantum/teleport"}),
        )
        parsed_m = json.loads(resp_unknown_method)
        self.assertEqual(parsed_m["id"], 99)
        self.assertEqual(parsed_m["error"]["code"], -32601)

        # 2. Unknown tool
        resp_unknown_tool = process_mcp_message(
            self.client,
            json.dumps({
                "jsonrpc": "2.0",
                "id": 100,
                "method": "tools/call",
                "params": {"name": "hack_the_pentagon", "arguments": {}},
            }),
        )
        parsed_t = json.loads(resp_unknown_tool)
        self.assertEqual(parsed_t["id"], 100)
        self.assertEqual(parsed_t["error"]["code"], -32602)
        self.assertEqual(parsed_t["error"]["data"]["code"], "UNKNOWN_TOOL")

    def test_probe_stdio_server_stream_pipeline_stress(self):
        """Adversarial probe: Stream mixed sequence of valid, invalid, and notification requests."""
        stream_items = [
            # 1. Valid ping
            json.dumps({"jsonrpc": "2.0", "id": "req-1", "method": "ping"}),
            # 2. Malformed JSON
            "{corrupted-json",
            # 3. Notification (should NOT produce stdout line)
            json.dumps({"jsonrpc": "2.0", "method": "notifications/initialized"}),
            # 4. Another notification
            json.dumps({"jsonrpc": "2.0", "method": "notifications/arbitrary_event"}),
            # 5. Valid documentation lookup
            json.dumps({
                "jsonrpc": "2.0",
                "id": "req-2",
                "method": "tools/call",
                "params": {"name": "get_flama_documentation", "arguments": {"topic": "srs"}},
            }),
            # 6. Invalid non-dict
            json.dumps(["not", "an", "object"]),
            # 7. Valid marketplace search
            json.dumps({
                "jsonrpc": "2.0",
                "id": "req-3",
                "method": "tools/call",
                "params": {"name": "search_marketplace_decks", "arguments": {"limit": 5}},
            }),
            # 8. Unauthenticated call to personal tool
            json.dumps({
                "jsonrpc": "2.0",
                "id": "req-4",
                "method": "tools/call",
                "params": {"name": "create_note", "arguments": {"fields": {}}},
            }),
        ]

        input_buffer = io.StringIO("\n".join(stream_items) + "\n")
        output_buffer = io.StringIO()

        run_stdio_server(
            input_stream=input_buffer,
            output_stream=output_buffer,
            app_instance=self.app,
        )

        output_lines = [l.strip() for l in output_buffer.getvalue().strip().split("\n") if l.strip()]
        # Total responses expected: 8 items - 2 notifications = 6 responses
        self.assertEqual(len(output_lines), 6, f"Expected exactly 6 responses from 8 stream items, got {len(output_lines)}")

        # Verify req-1 (ping)
        r1 = json.loads(output_lines[0])
        self.assertEqual(r1["id"], "req-1")
        self.assertEqual(r1["result"], {})

        # Verify corrupted json error
        r2 = json.loads(output_lines[1])
        self.assertIsNone(r2["id"])
        self.assertEqual(r2["error"]["code"], -32700)

        # Verify req-2 (doc)
        r3 = json.loads(output_lines[2])
        self.assertEqual(r3["id"], "req-2")
        self.assertEqual(r3["result"]["structuredContent"]["topic"], "srs")

        # Verify array error
        r4 = json.loads(output_lines[3])
        self.assertIsNone(r4["id"])
        self.assertEqual(r4["error"]["code"], -32600)

        # Verify req-3 (search)
        r5 = json.loads(output_lines[4])
        self.assertEqual(r5["id"], "req-3")
        self.assertIn("items", r5["result"]["structuredContent"])

        # Verify req-4 (auth error on personal tool)
        r6 = json.loads(output_lines[5])
        self.assertEqual(r6["id"], "req-4")
        self.assertEqual(r6["error"]["code"], -32001)


if __name__ == "__main__":
    unittest.main()
