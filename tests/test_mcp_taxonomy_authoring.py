"""Unit and integration tests for MCP taxonomy authoring tools (admin permissions, domain, subject, framework, level, options, and ensure_taxonomy_category)."""

from __future__ import annotations

import json
import unittest

from app.connect import create_connect_app
from app.services import user_api_token_service
from models import db
from models.taxonomy import (
    TaxonomyDomain,
    TaxonomyFramework,
    TaxonomyFrameworkLevel,
    TaxonomyOption,
    TaxonomySubject,
)
from models.user import User
from tests.study_note_fixtures import create_note_user


class McpTaxonomyAuthoringTests(unittest.TestCase):
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

            # Normal user (non-admin)
            normal_user = create_note_user(
                db.session,
                username="normal_user",
                email="normal_user@example.com",
                timezone="UTC",
                is_admin=False,
            )
            normal_user.set_password("password123")
            self.normal_user_id = normal_user.id
            normal_token_obj = user_api_token_service.issue_token(
                user_id=normal_user.id,
                name="Normal Token",
                scopes=["deck-share:write", "deck-share:read", "deck:write", "deck:read"],
            )
            self.normal_token = normal_token_obj.plaintext

            # Admin user
            admin_user = create_note_user(
                db.session,
                username="admin_user",
                email="admin_user@example.com",
                timezone="UTC",
                is_admin=True,
            )
            admin_user.set_password("adminpass123")
            self.admin_user_id = admin_user.id
            admin_token_obj = user_api_token_service.issue_token(
                user_id=admin_user.id,
                name="Admin Token",
                scopes=["deck-share:write", "deck-share:read", "deck:write", "deck:read"],
            )
            self.admin_token = admin_token_obj.plaintext
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _rpc_call(self, method: str, params: dict, token: str | None = None) -> dict:
        auth_token = token or self.admin_token
        headers = {
            "MCP-Protocol-Version": "2025-11-25",
            "Content-Type": "application/json",
        }
        if auth_token:
            headers["Authorization"] = f"Bearer {auth_token}"

        payload = {
            "jsonrpc": "2.0",
            "id": 1,
            "method": method,
            "params": params,
        }
        res = self.client.post("/v1/mcp", data=json.dumps(payload), headers=headers)
        return res.get_json(silent=True) or {}

    def test_list_tools_includes_new_taxonomy_authoring_tools(self):
        """Verify all new taxonomy authoring tools are registered and advertised in tools/list."""
        resp = self._rpc_call("tools/list", {})
        self.assertNotIn("error", resp)
        tools = resp.get("result", {}).get("tools", [])
        tool_names = {t["name"] for t in tools}

        expected_tools = {
            "create_taxonomy_domain",
            "create_taxonomy_subject",
            "create_taxonomy_framework",
            "create_taxonomy_framework_level",
            "create_taxonomy_option",
            "ensure_taxonomy_category",
        }
        for expected in expected_tools:
            self.assertIn(expected, tool_names, f"Missing tool {expected} in tools/list")

    def test_non_admin_cannot_create_taxonomy_domain(self):
        """Verify that non-admin user is rejected with 403 Forbidden."""
        resp = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_domain",
                "arguments": {
                    "id": "music_theory",
                    "label": "Lý thuyết Âm nhạc",
                },
            },
            token=self.normal_token,
        )
        self.assertIn("error", resp)
        error = resp["error"]
        self.assertEqual(error.get("data", {}).get("code"), "FORBIDDEN")
        self.assertIn("quản trị viên", error.get("message", "").lower())

    def test_admin_can_create_taxonomy_domain(self):
        """Verify that admin user can successfully create a new taxonomy domain."""
        resp = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_domain",
                "arguments": {
                    "id": "data_science",
                    "label": "Khoa học Dữ liệu",
                    "sort_order": 15,
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", resp, f"Unexpected error: {resp.get('error')}")
        result = resp["result"]["structuredContent"]
        self.assertTrue(result.get("success"))
        self.assertEqual(result["domain"]["id"], "data_science")
        self.assertEqual(result["domain"]["label"], "Khoa học Dữ liệu")
        self.assertEqual(result["domain"]["sort_order"], 15)

        with self.app.app_context():
            dom = db.session.get(TaxonomyDomain, "data_science")
            self.assertIsNotNone(dom)
            self.assertEqual(dom.label, "Khoa học Dữ liệu")

    def test_duplicate_domain_returns_409_conflict(self):
        """Verify that creating an existing domain ID returns 409 DUPLICATE_ID."""
        # First creation
        resp1 = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_domain",
                "arguments": {
                    "id": "culinary_arts",
                    "label": "Nghệ thuật Ẩm thực",
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", resp1)

        # Duplicate creation
        resp2 = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_domain",
                "arguments": {
                    "id": "culinary_arts",
                    "label": "Ẩm thực",
                },
            },
            token=self.admin_token,
        )
        self.assertIn("error", resp2)
        self.assertEqual(resp2["error"].get("data", {}).get("code"), "DUPLICATE_ID")

    def test_create_subject_under_domain(self):
        """Verify creating a subject under an existing domain, and error for missing domain."""
        # 1. Non-admin fails
        resp_forbidden = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_subject",
                "arguments": {
                    "id": "deep_learning",
                    "domain_id": "data_science",
                    "label": "Deep Learning",
                },
            },
            token=self.normal_token,
        )
        self.assertIn("error", resp_forbidden)
        self.assertEqual(resp_forbidden["error"].get("data", {}).get("code"), "FORBIDDEN")

        # 2. Admin fails if domain does not exist
        resp_missing_dom = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_subject",
                "arguments": {
                    "id": "deep_learning",
                    "domain_id": "non_existent_domain",
                    "label": "Deep Learning",
                },
            },
            token=self.admin_token,
        )
        self.assertIn("error", resp_missing_dom)
        self.assertEqual(resp_missing_dom["error"].get("data", {}).get("code"), "DOMAIN_NOT_FOUND")

        # 3. Create parent domain first
        self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_domain",
                "arguments": {"id": "data_science", "label": "Khoa học Dữ liệu"},
            },
            token=self.admin_token,
        )

        # 4. Admin succeeds creating subject
        resp_ok = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_subject",
                "arguments": {
                    "id": "deep_learning",
                    "domain_id": "data_science",
                    "label": "Deep Learning & Mạng nơ-ron",
                    "sort_order": 5,
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", resp_ok)
        result = resp_ok["result"]["structuredContent"]
        self.assertEqual(result["subject"]["id"], "deep_learning")
        self.assertEqual(result["subject"]["domain_id"], "data_science")

        with self.app.app_context():
            sub = db.session.get(TaxonomySubject, "deep_learning")
            self.assertIsNotNone(sub)
            self.assertEqual(sub.domain_id, "data_science")

    def test_create_framework_and_level(self):
        """Verify creating framework under subject, and level under framework."""
        # Create domain and subject
        self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_domain",
                "arguments": {"id": "languages", "label": "Ngôn ngữ"},
            },
            token=self.admin_token,
        )
        self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_subject",
                "arguments": {"id": "german", "domain_id": "languages", "label": "Tiếng Đức"},
            },
            token=self.admin_token,
        )

        # Create Framework: Goethe Zertifikat
        fw_resp = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_framework",
                "arguments": {
                    "id": "goethe",
                    "subject_id": "german",
                    "label": "Goethe-Zertifikat",
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", fw_resp)
        self.assertEqual(fw_resp["result"]["structuredContent"]["framework"]["id"], "goethe")

        # Create Framework Level: Goethe B1
        lvl_resp = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_framework_level",
                "arguments": {
                    "id": "goethe_b1",
                    "framework_id": "goethe",
                    "subject_id": "german",
                    "label": "Goethe B1 (Mittelstufe)",
                    "difficulty_band": "intermediate",
                    "suggested_tags": ["deutsch", "b1", "goethe"],
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", lvl_resp)
        lvl_data = lvl_resp["result"]["structuredContent"]["framework_level"]
        self.assertEqual(lvl_data["id"], "goethe_b1")
        self.assertEqual(lvl_data["difficulty_band"], "intermediate")

        with self.app.app_context():
            lvl = db.session.get(TaxonomyFrameworkLevel, "goethe_b1")
            self.assertIsNotNone(lvl)
            self.assertEqual(lvl.label, "Goethe B1 (Mittelstufe)")

    def test_create_taxonomy_option(self):
        """Verify creating taxonomy option (topic, learning goal, etc.)."""
        # Non-admin fails
        resp_forbidden = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_option",
                "arguments": {
                    "id": "prompt_engineering",
                    "option_type": "topic",
                    "label": "Prompt Engineering",
                },
            },
            token=self.normal_token,
        )
        self.assertIn("error", resp_forbidden)
        self.assertEqual(resp_forbidden["error"].get("data", {}).get("code"), "FORBIDDEN")

        # Admin creates option with normalized type "topic" -> "primary_topic"
        resp_ok = self._rpc_call(
            "tools/call",
            {
                "name": "create_taxonomy_option",
                "arguments": {
                    "id": "prompt_engineering",
                    "option_type": "topic",
                    "label": "Kỹ nghệ Prompt",
                    "sub_label": "Kỹ thuật tối ưu câu lệnh cho LLM",
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", resp_ok)
        opt_data = resp_ok["result"]["structuredContent"]["option"]
        self.assertEqual(opt_data["id"], "prompt_engineering")
        self.assertEqual(opt_data["option_type"], "primary_topic")

        with self.app.app_context():
            opt = db.session.get(TaxonomyOption, ("prompt_engineering", "primary_topic"))
            self.assertIsNotNone(opt)
            self.assertEqual(opt.label, "Kỹ nghệ Prompt")

    def test_ensure_taxonomy_category_auto_creates_hierarchy(self):
        """Verify that ensure_taxonomy_category creates domain, subject, framework, level in a single call."""
        # Non-admin fails
        resp_forbidden = self._rpc_call(
            "tools/call",
            {
                "name": "ensure_taxonomy_category",
                "arguments": {
                    "domain_id": "cloud_computing",
                    "subject_id": "kubernetes",
                },
            },
            token=self.normal_token,
        )
        self.assertIn("error", resp_forbidden)
        self.assertEqual(resp_forbidden["error"].get("data", {}).get("code"), "FORBIDDEN")

        # Admin calls ensure_taxonomy_category with full hierarchy
        resp = self._rpc_call(
            "tools/call",
            {
                "name": "ensure_taxonomy_category",
                "arguments": {
                    "domain_id": "cloud_infrastructure",
                    "domain_label": "Hạ tầng Điện toán Đám mây",
                    "subject_id": "kubernetes",
                    "subject_label": "Kubernetes & Containers",
                    "framework_id": "cncf_certs",
                    "framework_label": "CNCF Certifications",
                    "level_id": "cka",
                    "level_label": "Certified Kubernetes Administrator (CKA)",
                    "difficulty_band": "advanced",
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", resp, f"Unexpected error: {resp.get('error')}")
        res_data = resp["result"]["structuredContent"]
        self.assertTrue(res_data.get("success"))
        self.assertIn("domain:cloud_infrastructure", res_data.get("created_entities", []))
        self.assertIn("subject:kubernetes", res_data.get("created_entities", []))
        self.assertIn("framework:cncf_certs", res_data.get("created_entities", []))
        self.assertIn("level:cka", res_data.get("created_entities", []))

        # Check suggested_taxonomy_metadata
        meta = res_data.get("suggested_taxonomy_metadata", {})
        self.assertEqual(meta.get("domain"), "cloud_infrastructure")
        self.assertEqual(meta.get("subject"), "kubernetes")
        self.assertEqual(meta.get("framework"), "cncf_certs")
        self.assertEqual(meta.get("framework_level"), "cka")
        self.assertEqual(meta.get("difficulty_band"), "advanced")

        # Second call to ensure is idempotent: no new entities created
        resp2 = self._rpc_call(
            "tools/call",
            {
                "name": "ensure_taxonomy_category",
                "arguments": {
                    "domain_id": "cloud_infrastructure",
                    "subject_id": "kubernetes",
                    "framework_id": "cncf_certs",
                    "level_id": "cka",
                },
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", resp2)
        res_data2 = resp2["result"]["structuredContent"]
        self.assertEqual(res_data2.get("created_entities"), [])

        # Verify get_taxonomy_schema now returns the newly ensured domain & subject
        schema_resp = self._rpc_call(
            "tools/call",
            {
                "name": "get_taxonomy_schema",
                "arguments": {"content_type": "deck_marketplace_item"},
            },
            token=self.admin_token,
        )
        self.assertNotIn("error", schema_resp)
        schema_data = schema_resp["result"]["structuredContent"]
        domains = [d["id"] for d in schema_data.get("domains", [])]
        subjects = [s["id"] for s in schema_data.get("subjects", [])]
        self.assertIn("cloud_infrastructure", domains)
        self.assertIn("kubernetes", subjects)
