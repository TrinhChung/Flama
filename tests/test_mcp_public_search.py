"""Comprehensive test suite for Flama Model Context Protocol (MCP) Public Search Integration.

Verifies:
1. Unauthenticated discovery of public search tools.
2. Strict privacy barrier: queries only published marketplace decks, never private notes or study logs.
3. Anti-scraping guardrail: sample preview capped at strictly 3 to 5 cards max.
4. Pagination bounds: limit clamped to [1, 20], offset >= 0.
5. Personal / creator tools still require authentication (AUTH_REQUIRED).
6. Authoritative documentation retrieval and resources/list & resources/read.
7. Standalone stdio JSON-RPC server loop.
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
from tests.study_note_fixtures import attach_template, create_note_user
from scripts.flama_mcp_server import process_mcp_message, run_stdio_server


class TestMcpPublicSearch(unittest.TestCase):
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

            # 1. Create author and learner users
            author = create_note_user(
                db.session,
                username="deck_creator",
                email="creator@flama.vn",
                timezone="UTC",
                is_admin=False,
            )
            author.set_password("password123")

            learner = create_note_user(
                db.session,
                username="private_learner",
                email="learner@flama.vn",
                timezone="UTC",
                is_admin=False,
            )
            learner.set_password("password123")
            db.session.flush()

            self.author_id = author.id
            self.learner_id = learner.id

            # 2. Note type for Japanese vocabulary
            note_type = NoteType(user_id=author.id, name="Japanese Vocab")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            db.session.add_all([
                FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0, required=True),
                FieldDef(note_type_id=note_type.id, name="Reading", field_type="text", position=1, required=True),
                FieldDef(note_type_id=note_type.id, name="Meaning", field_type="text", position=2, required=True),
            ])
            template = attach_template(
                db.session,
                note_type_id=note_type.id,
                owner_user_id=author.id,
                name="Recognition",
                front_html="<div>{{Word}}</div>",
                back_html="<div>{{Reading}} - {{Meaning}}</div>",
                position=0,
            )

            # 3. Public Source Deck for Author
            pub_deck = Deck(name="JLPT N5 Core Vocabulary", owner_user_id=author.id)
            db.session.add(pub_deck)
            db.session.flush()
            self.pub_deck_id = pub_deck.id

            # Add published notes to author's deck
            pub_notes_data = [
                ("食べる", "たべる", "to eat (verb)"),
                ("飲む", "のむ", "to drink (verb)"),
                ("本", "ほん", "book (noun)"),
                ("行く", "いく", "to go (verb)"),
                ("見る", "みる", "to see / watch"),
                ("買う", "かう", "to buy"),
                ("話す", "はなす", "to speak / talk"),
            ]
            for w, r, m in pub_notes_data:
                n = Note(
                    user_id=author.id,
                    deck_id=pub_deck.id,
                    note_type_id=note_type.id,
                    field_values={"Word": w, "Reading": r, "Meaning": m},
                    tags=["n5", "vocab"],
                )
                db.session.add(n)
                db.session.flush()
                c = Card.query.filter_by(note_id=n.id, template_id=template.id).one()

            # 4. Published Marketplace Deck
            pub_market_item = DeckMarketplaceItem(
                id="pub-deck-uuid-1",
                owner_user_id=author.id,
                source_deck_id=pub_deck.id,
                source_note_type_id=note_type.id,
                title="JLPT N5 Core Vocabulary Deck",
                description="The ultimate JLPT N5 deck with high-frequency vocabulary and audio.",
                primary_category="JLPT",
                tags=["n5", "beginner", "jlpt"],
                taxonomy_metadata={"framework_level": "N5", "category": "JLPT"},
                publish_status="published",
                pricing_mode="free",
                sample_cards_count=len(pub_notes_data),
                rating_avg=4.85,
                rating_count=42,
                install_count=150,
                preview_samples_json=[
                    {"word": "食べる", "reading": "たべる", "meaning": "to eat (verb)"},
                    {"word": "飲む", "reading": "のむ", "meaning": "to drink (verb)"},
                    {"word": "本", "reading": "ほん", "meaning": "book (noun)"},
                ],
            )
            db.session.add(pub_market_item)

            # 5. Published Marketplace Deck for JLPT N1 (for level filtering test)
            n1_deck = Deck(name="JLPT N1 Advanced Vocabulary", owner_user_id=author.id)
            db.session.add(n1_deck)
            db.session.flush()
            n1_market_item = DeckMarketplaceItem(
                id="pub-deck-uuid-n1",
                owner_user_id=author.id,
                source_deck_id=n1_deck.id,
                source_note_type_id=note_type.id,
                title="JLPT N1 Advanced Vocabulary Deck",
                description="Advanced vocabulary for JLPT N1 mastery.",
                primary_category="JLPT",
                tags=["n1", "advanced"],
                taxonomy_metadata={"framework_level": "N1"},
                publish_status="published",
                pricing_mode="free",
                sample_cards_count=10,
                rating_avg=4.9,
                rating_count=20,
                preview_samples_json=[
                    {"word": "矛盾", "reading": "むじゅん", "meaning": "contradiction"},
                ],
            )
            db.session.add(n1_market_item)

            # 6. Unpublished Private Marketplace Item
            priv_market_item = DeckMarketplaceItem(
                id="priv-deck-uuid-2",
                owner_user_id=author.id,
                title="Secret Draft Deck",
                description="Unpublished work in progress.",
                primary_category="Personal",
                publish_status="private",
                pricing_mode="free",
            )
            db.session.add(priv_market_item)

            # 7. Unlisted Marketplace Item
            unlisted_market_item = DeckMarketplaceItem(
                id="unlisted-deck-uuid-3",
                owner_user_id=author.id,
                title="Unlisted Private Sharing Deck",
                description="Shared only with private link.",
                primary_category="Personal",
                publish_status="unlisted",
                pricing_mode="free",
            )
            db.session.add(unlisted_market_item)

            # 8. Learner's Private Notes in a completely private deck
            private_deck = Deck(name="Secret Private Notes", owner_user_id=learner.id)
            db.session.add(private_deck)
            db.session.flush()

            private_note = Note(
                user_id=learner.id,
                deck_id=private_deck.id,
                note_type_id=note_type.id,
                field_values={
                    "Word": "秘密の単語",
                    "Reading": "ひみつのたんご",
                    "Meaning": "classified secret confidential notes",
                },
                tags=["private", "confidential"],
            )
            db.session.add(private_note)

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

    # -----------------------------------------------------------------------
    # 1. Unauthenticated discovery includes public search tools
    # -----------------------------------------------------------------------
    def test_unauthenticated_tools_list_includes_public_search_tools(self):
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/list",
            "params": {},
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertIn("tools", data["result"])
        tool_names = {t["name"] for t in data["result"]["tools"]}

        required_public_tools = {
            "search_marketplace_decks",
            "lookup_public_vocabulary",
            "get_public_deck_preview",
            "get_flama_documentation",
        }
        for expected_tool in required_public_tools:
            self.assertIn(expected_tool, tool_names, f"Expected {expected_tool} in tools/list")

    # -----------------------------------------------------------------------
    # 2. Public deck search returns strictly published decks
    # -----------------------------------------------------------------------
    def test_unauthenticated_search_marketplace_decks_returns_only_published(self):
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 2,
            "method": "tools/call",
            "params": {
                "name": "search_marketplace_decks",
                "arguments": {"query": ""},
            },
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        structured = data["result"]["structuredContent"]
        items = structured["items"]
        deck_ids = {item["id"] for item in items}

        # Published deck MUST be present
        self.assertIn("pub-deck-uuid-1", deck_ids)
        self.assertIn("pub-deck-uuid-n1", deck_ids)

        # Private and unlisted decks MUST NOT be present
        self.assertNotIn("priv-deck-uuid-2", deck_ids)
        self.assertNotIn("unlisted-deck-uuid-3", deck_ids)

        # Verify required metadata fields on published deck item
        target_item = next(it for it in items if it["id"] == "pub-deck-uuid-1")
        self.assertEqual(target_item["title"], "JLPT N5 Core Vocabulary Deck")
        self.assertEqual(target_item["primary_category"], "JLPT")
        self.assertEqual(target_item["jlpt_level"], "N5")
        self.assertEqual(target_item["pricing_mode"], "free")
        self.assertEqual(target_item["author_username"], "deck_creator")
        self.assertEqual(target_item["canonical_url"], "https://flama.vn/marketplace/decks/pub-deck-uuid-1")
        self.assertIsInstance(target_item["sample_preview"], list)
        self.assertLessEqual(len(target_item["sample_preview"]), 5)

    # -----------------------------------------------------------------------
    # 3. Privacy barrier: Private notes are NEVER leaked
    # -----------------------------------------------------------------------
    def test_private_notes_never_leaked_in_public_vocabulary_lookup(self):
        # 1. Search for secret word present only in learner's private deck
        response_private = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 3,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "秘密"},
            },
        })
        self.assertEqual(response_private.status_code, 200)
        data_private = response_private.get_json()
        matches_private = data_private["result"]["structuredContent"]["matches"]
        # MUST BE EMPTY: Zero leakage of private notes
        self.assertEqual(len(matches_private), 0, "Private notes must NEVER leak via public search")

        # 2. Search for secret meaning keyword
        response_secret_meaning = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 4,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "classified"},
            },
        })
        matches_meaning = response_secret_meaning.get_json()["result"]["structuredContent"]["matches"]
        self.assertEqual(len(matches_meaning), 0)

        # 3. Search for published word '食べる'
        response_public = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 5,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "食べる"},
            },
        })
        self.assertEqual(response_public.status_code, 200)
        data_public = response_public.get_json()
        matches_public = data_public["result"]["structuredContent"]["matches"]
        self.assertGreater(len(matches_public), 0)
        first_match = matches_public[0]
        self.assertEqual(first_match["term"], "食べる")
        self.assertEqual(first_match["reading"], "たべる")
        self.assertEqual(first_match["deck_id"], "pub-deck-uuid-1")
        self.assertEqual(first_match["canonical_url"], "https://flama.vn/marketplace/decks/pub-deck-uuid-1")

    # -----------------------------------------------------------------------
    # 4. Anti-scraping preview limit enforced (strictly 3 to 5 sample cards max)
    # -----------------------------------------------------------------------
    def test_lookup_cannot_extract_words_outside_the_fixed_preview(self):
        response = self._post_mcp({
            "jsonrpc": "2.0", "id": 101, "method": "tools/call",
            "params": {"name": "lookup_public_vocabulary", "arguments": {"query": "話す", "limit": 20}},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"]["structuredContent"]["matches"], [])

    def test_lookup_never_reads_working_values_after_publication(self):
        from app.services import flashcards_share_service

        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, "pub-deck-uuid-1")
            flashcards_share_service._stage_initial_release_if_visible(item)
            db.session.commit()
            note = Note.query.filter_by(deck_id=self.pub_deck_id).first()
            note.field_values = {"Word": "未公開の草稿", "Reading": "draft", "Meaning": "unpublished working secret"}
            db.session.commit()
        response = self._post_mcp({
            "jsonrpc": "2.0", "id": 102, "method": "tools/call",
            "params": {"name": "lookup_public_vocabulary", "arguments": {"query": "unpublished working secret"}},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"]["structuredContent"]["matches"], [])

    def test_preview_reconstructs_current_release_when_sample_cache_is_stale(self):
        from app.services import flashcards_share_service

        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, "pub-deck-uuid-1")
            flashcards_share_service._stage_initial_release_if_visible(item)
            db.session.commit()
            item.preview_samples_release_id = "another-release"
            item.preview_samples_json = [{"word": "STALE_PRIVATE_CONTENT", "meaning": "not in current release"}]
            db.session.commit()
        response = self._post_mcp({
            "jsonrpc": "2.0", "id": 103, "method": "tools/call",
            "params": {"name": "get_public_deck_preview", "arguments": {"deck_item_id": "pub-deck-uuid-1"}},
        })
        self.assertEqual(response.status_code, 200)
        samples = response.get_json()["result"]["structuredContent"]["sample_preview"]
        self.assertGreater(len(samples), 0)
        self.assertNotIn("STALE_PRIVATE_CONTENT", json.dumps(samples))

    def test_preview_does_not_read_live_notes_for_a_missing_published_release(self):
        with self.app.app_context():
            item = db.session.get(DeckMarketplaceItem, "pub-deck-uuid-1")
            item.current_release_id = "missing-release"
            item.preview_samples_json = None
            db.session.commit()
        response = self._post_mcp({
            "jsonrpc": "2.0", "id": 104, "method": "tools/call",
            "params": {"name": "get_public_deck_preview", "arguments": {"deck_item_id": "pub-deck-uuid-1"}},
        })
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["result"]["structuredContent"]["sample_preview"], [])

    def test_anti_scraping_preview_limit_enforced(self):
        # Even though the published deck has 7 cards and can have 1000s,
        # get_public_deck_preview must strictly return <= 5 sample cards.
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 6,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {"deck_item_id": "pub-deck-uuid-1"},
            },
        })
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        structured = data["result"]["structuredContent"]

        samples = structured["sample_preview"]
        self.assertIsInstance(samples, list)
        self.assertGreater(len(samples), 0)
        self.assertLessEqual(len(samples), 5, "Sample cards must strictly not exceed 5 cards (anti-scraping limit)")

        guardrail = structured["anti_scraping_guardrail"]
        self.assertTrue(guardrail["is_sample_preview_only"])
        self.assertEqual(guardrail["max_allowed_samples"], 5)

    # -----------------------------------------------------------------------
    # 5. Rate limit and paging bounds enforced
    # -----------------------------------------------------------------------
    def test_rate_limit_and_paging_bounds_enforced(self):
        # Limit > 20 must be clamped to 20
        response_deck = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 7,
            "method": "tools/call",
            "params": {
                "name": "search_marketplace_decks",
                "arguments": {"limit": 100, "offset": -5},
            },
        })
        self.assertEqual(response_deck.status_code, 200)
        structured_deck = response_deck.get_json()["result"]["structuredContent"]
        self.assertEqual(structured_deck["limit"], 20, "Requested limit 100 must clamp to 20")
        self.assertEqual(structured_deck["offset"], 0, "Negative offset must clamp to 0")

        # Vocabulary lookup limit > 20 clamped to 20
        response_vocab = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 8,
            "method": "tools/call",
            "params": {
                "name": "lookup_public_vocabulary",
                "arguments": {"query": "食べる", "limit": 50},
            },
        })
        self.assertEqual(response_vocab.status_code, 200)
        structured_vocab = response_vocab.get_json()["result"]["structuredContent"]
        self.assertEqual(structured_vocab["limit"], 20, "Vocabulary lookup limit 50 must clamp to 20")

    # -----------------------------------------------------------------------
    # 6. Personal tools still require authentication
    # -----------------------------------------------------------------------
    def test_personal_tools_still_require_auth(self):
        personal_tools_to_test = [
            ("list_notes", {}),
            ("create_note", {"deck_id": 1, "fields": {"Word": "test"}}),
            ("get_study_queue", {"deck_id": 1}),
            ("list_my_decks", {}),
        ]

        for tool_name, args in personal_tools_to_test:
            response = self._post_mcp({
                "jsonrpc": "2.0",
                "id": 9,
                "method": "tools/call",
                "params": {"name": tool_name, "arguments": args},
            })
            # Must return HTTP 401 or JSON-RPC auth error
            data = response.get_json()
            self.assertIn("error", data, f"Personal tool {tool_name} should return error when unauthenticated")
            err_code = data["error"]["code"]
            self.assertEqual(err_code, -32001, f"Personal tool {tool_name} error code should be -32001 (AUTH_REQUIRED)")

    # -----------------------------------------------------------------------
    # 7. Documentation topic retrieval & resources
    # -----------------------------------------------------------------------
    def test_documentation_topic_retrieval(self):
        # 1. Tool call for 'srs'
        response_srs = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 10,
            "method": "tools/call",
            "params": {
                "name": "get_flama_documentation",
                "arguments": {"topic": "srs"},
            },
        })
        self.assertEqual(response_srs.status_code, 200)
        srs_content = response_srs.get_json()["result"]["structuredContent"]
        self.assertEqual(srs_content["topic"], "srs")
        self.assertIn("FSRS", srs_content["content"])
        self.assertIn("SM-2", srs_content["content"])

        # 2. Tool call for 'yomitan'
        response_yomitan = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 11,
            "method": "tools/call",
            "params": {
                "name": "get_flama_documentation",
                "arguments": {"topic": "yomitan"},
            },
        })
        yomitan_content = response_yomitan.get_json()["result"]["structuredContent"]
        self.assertEqual(yomitan_content["topic"], "yomitan")
        self.assertIn("4790", yomitan_content["content"])

        # 3. Resources list
        response_res_list = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 12,
            "method": "resources/list",
            "params": {},
        })
        self.assertEqual(response_res_list.status_code, 200)
        resources = response_res_list.get_json()["result"]["resources"]
        uris = {r["uri"] for r in resources}
        self.assertIn("flama://docs/overview", uris)
        self.assertIn("flama://docs/srs", uris)
        self.assertIn("flama://docs/marketplace", uris)

        # 4. Resources read
        response_res_read = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 13,
            "method": "resources/read",
            "params": {"uri": "flama://docs/overview"},
        })
        self.assertEqual(response_res_read.status_code, 200)
        res_data = response_res_read.get_json()["result"]["contents"][0]
        self.assertEqual(res_data["uri"], "flama://docs/overview")
        self.assertEqual(res_data["mimeType"], "text/markdown")
        self.assertIn("Flama Platform Overview", res_data["text"])

    # -----------------------------------------------------------------------
    # 8. Standalone stdio JSON-RPC server loop
    # -----------------------------------------------------------------------
    def test_stdio_server_initialize_and_tool_call(self):
        init_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 100,
            "method": "initialize",
            "params": {"protocolVersion": "2025-11-25"},
        })
        notify_req = json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
            "params": {},
        })
        tool_req = json.dumps({
            "jsonrpc": "2.0",
            "id": 101,
            "method": "tools/call",
            "params": {
                "name": "get_flama_documentation",
                "arguments": {"topic": "overview"},
            },
        })

        input_buffer = io.StringIO(f"{init_req}\n{notify_req}\n{tool_req}\n")
        output_buffer = io.StringIO()

        run_stdio_server(
            input_stream=input_buffer,
            output_stream=output_buffer,
            app_instance=self.app,
        )

        lines = [line.strip() for line in output_buffer.getvalue().strip().split("\n") if line.strip()]
        self.assertEqual(len(lines), 2, "Notifications produce no output, expect exactly 2 responses")

        # Response 1: initialize
        init_resp = json.loads(lines[0])
        self.assertEqual(init_resp["id"], 100)
        self.assertEqual(init_resp["result"]["protocolVersion"], "2025-11-25")
        self.assertEqual(init_resp["result"]["serverInfo"]["name"], "flama-mcp-connect")

        # Response 2: tools/call get_flama_documentation
        tool_resp = json.loads(lines[1])
        self.assertEqual(tool_resp["id"], 101)
        self.assertEqual(tool_resp["result"]["structuredContent"]["topic"], "overview")

    # -----------------------------------------------------------------------
    # Supplementary: Unpublished deck preview rejected
    # -----------------------------------------------------------------------
    def test_unpublished_deck_preview_rejected(self):
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 14,
            "method": "tools/call",
            "params": {
                "name": "get_public_deck_preview",
                "arguments": {"deck_item_id": "priv-deck-uuid-2"},
            },
        })
        data = response.get_json()
        self.assertIn("error", data)
        self.assertEqual(data["error"]["data"]["code"], "DECK_NOT_PUBLIC")

    # -----------------------------------------------------------------------
    # Supplementary: JLPT level filtering
    # -----------------------------------------------------------------------
    def test_search_marketplace_decks_jlpt_filtering(self):
        response = self._post_mcp({
            "jsonrpc": "2.0",
            "id": 15,
            "method": "tools/call",
            "params": {
                "name": "search_marketplace_decks",
                "arguments": {"jlpt_level": "N5"},
            },
        })
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["result"]["structuredContent"]["items"]
        deck_ids = {it["id"] for it in items}
        self.assertIn("pub-deck-uuid-1", deck_ids)
        self.assertNotIn("pub-deck-uuid-n1", deck_ids, "N1 deck should not appear when filtering for N5")


if __name__ == "__main__":
    unittest.main()
