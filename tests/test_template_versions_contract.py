"""Contract tests for template source history (GT-15A, Contract A2).

Covers test cases A7, A12-A17 according to GT-15_CONTRACT_TESTS.md specification.
"""

from datetime import datetime
from unittest import TestCase

from sqlalchemy import insert

from app import create_app
from app.services.flashcard_legacy import (
    LEGACY_BACK_TEMPLATE,
    LEGACY_FRONT_TEMPLATE,
    LEGACY_SHARED_CSS,
)
from models import db
from models.card import Card
from models.deck import Deck
from models.model_uuid import uuid_str
from models.note_type import NoteType
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User


class TemplateVersionsContractTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
        })

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="owner", email="owner@example.com", is_admin=True)
            user.set_password("password")
            other = User(username="other", email="other@example.com")
            other.set_password("password")
            db.session.add_all([user, other])
            db.session.flush()
            self.user_id, self.other_id = user.id, other.id
            deck = Deck(name="History deck", owner_user_id=user.id)
            db.session.add(deck)
            db.session.commit()
            self.deck_id = deck.id
        self.client.post("/login", data={"email": "owner@example.com", "password": "password"})
        response = self.client.post("/api/note-types", json={
            "name": "History type",
            "field_defs": [
                {"name": "Kanji", "field_type": "text", "position": 0},
                {"name": "Meaning", "field_type": "text", "position": 1},
            ],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        result = response.get_json()
        self.nt_id = result["id"]
        self.template_id = result["templates"][0]["id"]
        self.base = f"/api/card-templates/{self.template_id}/versions"
        self.template_url = f"/api/note-types/{self.nt_id}/templates/{self.template_id}"

    def tearDown(self):
        with self.app.app_context():
            db.session.rollback()
            db.session.remove()
            db.drop_all()

    def _history(self, template_id=None):
        url = f"/api/card-templates/{template_id}/versions" if template_id else self.base
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _patch(self, payload, template_url=None):
        url = template_url or self.template_url
        response = self.client.patch(url, json=payload)
        return response

    def test_a7_cross_template_version_access_rejected_preserves_state(self):
        """A7: Accessing another template's version returns 404 TEMPLATE_VERSION_NOT_FOUND."""
        # Create a second template on the same NoteType (same owner).
        create_resp = self.client.post(
            f"/api/note-types/{self.nt_id}/templates",
            json={
                "name": "Template B",
                "front_html": "<b>{{Meaning}}</b>",
                "back_html": "{{Kanji}}",
            },
        )
        self.assertEqual(create_resp.status_code, 201, create_resp.get_json())
        template_b_id = create_resp.get_json()["id"]

        history_a_before = self._history()
        count_a_before = len(history_a_before["items"])
        head_a_before = history_a_before["current_version_id"]
        v_a_id = history_a_before["items"][0]["id"]

        history_b_before = self._history(template_b_id)
        count_b_before = len(history_b_before["items"])
        head_b_before = history_b_before["current_version_id"]
        v_b_id = history_b_before["items"][0]["id"]

        with self.app.app_context():
            t_a = db.session.get(Template, self.template_id)
            state_a_before = (t_a.front_html, t_a.back_html, t_a.shared_css, t_a.current_version_id)
            t_b = db.session.get(Template, template_b_id)
            state_b_before = (t_b.front_html, t_b.back_html, t_b.shared_css, t_b.current_version_id)

        # 1. Canonical GET: access version of B via template A URL.
        resp_canonical_get = self.client.get(f"{self.base}/{v_b_id}")
        self.assertEqual(resp_canonical_get.status_code, 404, resp_canonical_get.get_json())
        self.assertEqual(resp_canonical_get.get_json()["error"], "TEMPLATE_VERSION_NOT_FOUND")

        # 2. Canonical POST restore: restore version of B via template A URL.
        resp_canonical_restore = self.client.post(f"{self.base}/{v_b_id}/restore", json={})
        self.assertEqual(resp_canonical_restore.status_code, 404, resp_canonical_restore.get_json())
        self.assertEqual(resp_canonical_restore.get_json()["error"], "TEMPLATE_VERSION_NOT_FOUND")

        # 3. Alias GET: access version of B via template A note-type URL.
        alias_url = f"{self.template_url}/versions"
        resp_alias_get = self.client.get(f"{alias_url}/{v_b_id}")
        self.assertEqual(resp_alias_get.status_code, 404, resp_alias_get.get_json())
        self.assertEqual(resp_alias_get.get_json()["error"], "TEMPLATE_VERSION_NOT_FOUND")

        # 4. Alias POST restore: restore version of B via template A note-type URL.
        resp_alias_restore = self.client.post(f"{alias_url}/{v_b_id}/restore", json={})
        self.assertEqual(resp_alias_restore.status_code, 404, resp_alias_restore.get_json())
        self.assertEqual(resp_alias_restore.get_json()["error"], "TEMPLATE_VERSION_NOT_FOUND")

        # 5. Reverse: access version of A via template B URL.
        resp_rev_get = self.client.get(f"/api/card-templates/{template_b_id}/versions/{v_a_id}")
        self.assertEqual(resp_rev_get.status_code, 404, resp_rev_get.get_json())
        self.assertEqual(resp_rev_get.get_json()["error"], "TEMPLATE_VERSION_NOT_FOUND")

        resp_rev_restore = self.client.post(f"/api/card-templates/{template_b_id}/versions/{v_a_id}/restore", json={})
        self.assertEqual(resp_rev_restore.status_code, 404, resp_rev_restore.get_json())
        self.assertEqual(resp_rev_restore.get_json()["error"], "TEMPLATE_VERSION_NOT_FOUND")

        # Verify state preservation for both templates.
        history_a_after = self._history()
        self.assertEqual(len(history_a_after["items"]), count_a_before)
        self.assertEqual(history_a_after["current_version_id"], head_a_before)

        history_b_after = self._history(template_b_id)
        self.assertEqual(len(history_b_after["items"]), count_b_before)
        self.assertEqual(history_b_after["current_version_id"], head_b_before)

        with self.app.app_context():
            t_a_after = db.session.get(Template, self.template_id)
            state_a_after = (t_a_after.front_html, t_a_after.back_html, t_a_after.shared_css, t_a_after.current_version_id)
            self.assertEqual(state_a_after, state_a_before)

            t_b_after = db.session.get(Template, template_b_id)
            state_b_after = (t_b_after.front_html, t_b_after.back_html, t_b_after.shared_css, t_b_after.current_version_id)
            self.assertEqual(state_b_after, state_b_before)

    def test_a12_unauthenticated_canonical_endpoints_require_auth(self):
        """A12: Unauthenticated calls to 3 canonical endpoints return 401 AUTHENTICATION_REQUIRED."""
        history = self._history()
        v_id = history["items"][0]["id"]

        with self.app.app_context():
            versions_count_before = TemplateVersion.query.count()

        # Log out current session.
        self.client.post("/logout")

        endpoints = [
            ("get", self.base),
            ("get", f"{self.base}/{v_id}"),
            ("post", f"{self.base}/{v_id}/restore"),
        ]

        for method, url in endpoints:
            kwargs = {"json": {}} if method == "post" else {}
            response = getattr(self.client, method)(url, **kwargs)
            self.assertEqual(response.status_code, 401, f"Expected 401 for {method.upper()} {url}")
            body = response.get_json()
            self.assertEqual(body["error"], "AUTHENTICATION_REQUIRED")
            self.assertEqual(body["message"], "Authentication is required.")

        # Alias endpoints also reject unauthenticated access.
        alias_base = f"{self.template_url}/versions"
        alias_endpoints = [
            ("get", alias_base),
            ("get", f"{alias_base}/{v_id}"),
            ("post", f"{alias_base}/{v_id}/restore"),
        ]
        for method, url in alias_endpoints:
            kwargs = {"json": {}} if method == "post" else {}
            response = getattr(self.client, method)(url, **kwargs)
            self.assertEqual(response.status_code, 401, f"Expected 401 for {method.upper()} {url}")
            self.assertEqual(response.get_json()["error"], "AUTHENTICATION_REQUIRED")

        # Verify no version added.
        with self.app.app_context():
            self.assertEqual(TemplateVersion.query.count(), versions_count_before)

    def test_a13_patch_change_note_boundary_and_validation(self):
        """A13: Change note boundary (1000 ok, 1001 / object 400 VALIDATION_ERROR on change_note)."""
        valid_note = "a" * 1000
        patch_ok = self._patch({"shared_css": ".card{color:blue;}", "change_note": valid_note})
        self.assertEqual(patch_ok.status_code, 200, patch_ok.get_json())

        history = self._history()
        self.assertEqual(len(history["items"]), 2)
        self.assertEqual(history["items"][0]["change_note"], valid_note)
        head_id = history["current_version_id"]

        with self.app.app_context():
            template = db.session.get(Template, self.template_id)
            source_css = template.shared_css
            count_baseline = TemplateVersion.query.filter_by(template_id=self.template_id).count()

        # 1001 characters note -> 400 VALIDATION_ERROR on field change_note.
        invalid_note = "b" * 1001
        patch_long = self._patch({"shared_css": ".card{color:green;}", "change_note": invalid_note})
        self.assertEqual(patch_long.status_code, 400, patch_long.get_json())
        body_long = patch_long.get_json()
        self.assertEqual(body_long["error"], "VALIDATION_ERROR")
        self.assertEqual(body_long["field"], "change_note")

        # Non-string object note -> 400 VALIDATION_ERROR on field change_note.
        patch_obj = self._patch({"shared_css": ".card{color:purple;}", "change_note": {"note": "nested"}})
        self.assertEqual(patch_obj.status_code, 400, patch_obj.get_json())
        body_obj = patch_obj.get_json()
        self.assertEqual(body_obj["error"], "VALIDATION_ERROR")
        self.assertEqual(body_obj["field"], "change_note")

        # Non-string integer note -> 400 VALIDATION_ERROR on field change_note.
        patch_int = self._patch({"shared_css": ".card{color:orange;}", "change_note": 12345})
        self.assertEqual(patch_int.status_code, 400, patch_int.get_json())
        body_int = patch_int.get_json()
        self.assertEqual(body_int["error"], "VALIDATION_ERROR")
        self.assertEqual(body_int["field"], "change_note")

        # State preserved: source, head, and count remain unchanged.
        with self.app.app_context():
            template_after = db.session.get(Template, self.template_id)
            self.assertEqual(template_after.shared_css, source_css)
            self.assertEqual(template_after.current_version_id, head_id)
            self.assertEqual(
                TemplateVersion.query.filter_by(template_id=self.template_id).count(),
                count_baseline,
            )

    def test_a14_patch_then_reset_custom_template(self):
        """A14: PATCH CSS then POST reset custom template returns 200 with origin 'reset'."""
        # Create a Note and Card using REST, verifying Card rows exist.
        note_resp = self.client.post("/api/notes", json={
            "note_type_id": self.nt_id,
            "deck_id": self.deck_id,
            "field_values": {"Kanji": "日本語", "Meaning": "Japanese language"},
        })
        self.assertEqual(note_resp.status_code, 201, note_resp.get_json())

        with self.app.app_context():
            card_ids_before = [row.id for row in Card.query.filter_by(template_id=self.template_id).all()]
            self.assertGreater(len(card_ids_before), 0)

        # PATCH changing CSS.
        patch_resp = self._patch({"shared_css": ".card{background:darkblue;}"})
        self.assertEqual(patch_resp.status_code, 200, patch_resp.get_json())

        # POST reset custom template.
        reset_resp = self.client.post(f"/api/note-types/{self.nt_id}/templates/{self.template_id}/reset")
        self.assertEqual(reset_resp.status_code, 200, reset_resp.get_json())

        history = self._history()
        self.assertEqual(len(history["items"]), 3)
        last_version = history["items"][0]
        self.assertTrue(last_version["is_current"])
        self.assertEqual(last_version["origin"], "reset")
        self.assertEqual(last_version["created_by"]["id"], self.user_id)

        # Verify sources match stripped LEGACY_* constants.
        version_detail = self.client.get(f"{self.base}/{last_version['id']}").get_json()
        self.assertEqual(version_detail["front_html"], LEGACY_FRONT_TEMPLATE.strip())
        self.assertEqual(version_detail["back_html"], LEGACY_BACK_TEMPLATE.strip())
        self.assertEqual(version_detail["shared_css"], LEGACY_SHARED_CSS.strip())

        with self.app.app_context():
            template = db.session.get(Template, self.template_id)
            self.assertEqual(template.front_html, LEGACY_FRONT_TEMPLATE.strip())
            self.assertEqual(template.back_html, LEGACY_BACK_TEMPLATE.strip())
            self.assertEqual(template.shared_css, LEGACY_SHARED_CSS.strip())

            # Card ID and count preserved.
            card_ids_after = [row.id for row in Card.query.filter_by(template_id=self.template_id).all()]
            self.assertEqual(card_ids_after, card_ids_before)

    def test_a15_restore_body_validation_and_empty_body(self):
        """A15: Restore invalid body / array / null returns 400 VALIDATION_ERROR; empty body {} restores."""
        # Create second version via PATCH.
        patch_resp = self._patch({"front_html": "CHANGED_FRONT"})
        self.assertEqual(patch_resp.status_code, 200, patch_resp.get_json())

        history = self._history()
        self.assertEqual(len(history["items"]), 2)
        first_version_id = history["items"][1]["id"]
        head_id = history["current_version_id"]
        count_baseline = len(history["items"])

        # 1. Invalid JSON string body -> 400 VALIDATION_ERROR.
        resp_malformed = self.client.post(
            f"{self.base}/{first_version_id}/restore",
            data="not-valid-json{{{",
            content_type="application/json",
        )
        self.assertEqual(resp_malformed.status_code, 400, resp_malformed.get_json())
        self.assertEqual(resp_malformed.get_json()["error"], "VALIDATION_ERROR")

        # 2. JSON Array body -> 400 VALIDATION_ERROR.
        resp_array = self.client.post(f"{self.base}/{first_version_id}/restore", json=[1, 2, 3])
        self.assertEqual(resp_array.status_code, 400, resp_array.get_json())
        self.assertEqual(resp_array.get_json()["error"], "VALIDATION_ERROR")

        # 3. JSON Null body -> 400 VALIDATION_ERROR.
        resp_null = self.client.post(
            f"{self.base}/{first_version_id}/restore",
            data="null",
            content_type="application/json",
        )
        self.assertEqual(resp_null.status_code, 400, resp_null.get_json())
        self.assertEqual(resp_null.get_json()["error"], "VALIDATION_ERROR")

        # Verify DB state unchanged after invalid calls.
        with self.app.app_context():
            template = db.session.get(Template, self.template_id)
            self.assertEqual(template.front_html, "CHANGED_FRONT")
            self.assertEqual(template.current_version_id, head_id)
            self.assertEqual(
                TemplateVersion.query.filter_by(template_id=self.template_id).count(),
                count_baseline,
            )

        # 4. Valid empty JSON object body {} -> 200 and restores successfully.
        resp_empty_json = self.client.post(f"{self.base}/{first_version_id}/restore", json={})
        self.assertEqual(resp_empty_json.status_code, 200, resp_empty_json.get_json())
        self.assertEqual(resp_empty_json.get_json()["front_html"], "{{Kanji}}")

        history_restored = self._history()
        self.assertEqual(len(history_restored["items"]), count_baseline + 1)
        self.assertEqual(history_restored["items"][0]["origin"], "restore")
        self.assertEqual(history_restored["items"][0]["change_note"], "")

        # 5. Empty request body (data="") -> 200 and restores successfully.
        self._patch({"front_html": "CHANGED_AGAIN"})
        resp_empty_data = self.client.post(f"{self.base}/{first_version_id}/restore", data="")
        self.assertEqual(resp_empty_data.status_code, 200, resp_empty_data.get_json())
        self.assertEqual(resp_empty_data.get_json()["front_html"], "{{Kanji}}")

    def test_a16_cli_backfill_dry_run_and_apply_idempotent(self):
        """A16: CLI dry run creates no version; CLI --apply creates 1 backfill; second call is idempotent."""
        template_id = uuid_str()
        now = datetime(2026, 10, 7, 12, 0, 0)
        with self.app.app_context():
            db.session.execute(insert(Template.__table__).values(
                id=template_id,
                note_type_id=self.nt_id,
                name="Raw SQL Template",
                front_html="<raw>{{Kanji}}</raw>",
                back_html="<raw>{{Meaning}}</raw>",
                shared_css=".raw{margin:0;}",
                position=3,
                is_default=False,
                created_at=now,
                updated_at=now,
            ))
            db.session.commit()

        # Initial state: pointer is null, version count is 0.
        with self.app.app_context():
            raw_t = db.session.get(Template, template_id)
            self.assertIsNone(raw_t.current_version_id)
            self.assertEqual(TemplateVersion.query.filter_by(template_id=template_id).count(), 0)

        runner = self.app.test_cli_runner()

        # 1. CLI dry run without --apply.
        res_dry = runner.invoke(args=["template-versions-backfill"])
        self.assertEqual(res_dry.exit_code, 0, res_dry.output)
        self.assertIn("applied=false", res_dry.output)
        self.assertIn("templates=1", res_dry.output)

        with self.app.app_context():
            raw_t_dry = db.session.get(Template, template_id)
            self.assertIsNone(raw_t_dry.current_version_id)
            self.assertEqual(TemplateVersion.query.filter_by(template_id=template_id).count(), 0)

        # 2. CLI with --apply.
        res_apply = runner.invoke(args=["template-versions-backfill", "--apply"])
        self.assertEqual(res_apply.exit_code, 0, res_apply.output)
        self.assertIn("applied=true", res_apply.output)
        self.assertIn("templates=1", res_apply.output)

        with self.app.app_context():
            raw_t_applied = db.session.get(Template, template_id)
            self.assertIsNotNone(raw_t_applied.current_version_id)
            self.assertEqual(raw_t_applied.front_html, "<raw>{{Kanji}}</raw>")
            self.assertEqual(raw_t_applied.back_html, "<raw>{{Meaning}}</raw>")
            self.assertEqual(raw_t_applied.shared_css, ".raw{margin:0;}")
            self.assertEqual(raw_t_applied.updated_at, now)

            versions = TemplateVersion.query.filter_by(template_id=template_id).all()
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0].id, raw_t_applied.current_version_id)
            self.assertEqual(versions[0].origin, "backfill")
            self.assertEqual(versions[0].version_no, 1)

        # 3. CLI with --apply second time (idempotent).
        res_second = runner.invoke(args=["template-versions-backfill", "--apply"])
        self.assertEqual(res_second.exit_code, 0, res_second.output)
        self.assertIn("applied=true", res_second.output)
        self.assertIn("templates=0", res_second.output)

        with self.app.app_context():
            self.assertEqual(TemplateVersion.query.filter_by(template_id=template_id).count(), 1)

    def test_a17_canonical_and_alias_schema_headers_and_wrong_note_type(self):
        """A17: GET canonical and alias return identical schema v2 & Cache-Control; wrong NoteType returns 404."""
        # 1. Canonical and alias list comparison.
        resp_canonical_list = self.client.get(self.base)
        self.assertEqual(resp_canonical_list.status_code, 200, resp_canonical_list.get_json())

        resp_alias_list = self.client.get(f"{self.template_url}/versions")
        self.assertEqual(resp_alias_list.status_code, 200, resp_alias_list.get_json())

        self.assertEqual(resp_canonical_list.headers.get("Cache-Control"), "private, no-store")
        self.assertEqual(resp_alias_list.headers.get("Cache-Control"), "private, no-store")

        canonical_data = resp_canonical_list.get_json()
        alias_data = resp_alias_list.get_json()
        self.assertEqual(canonical_data, alias_data)
        self.assertEqual(canonical_data["schema_version"], "template-versions.v2")
        self.assertEqual(canonical_data["template_id"], self.template_id)
        self.assertEqual(canonical_data["current_version_id"], alias_data["current_version_id"])

        # 2. Canonical and alias detail comparison.
        v_id = canonical_data["items"][0]["id"]
        resp_canonical_detail = self.client.get(f"{self.base}/{v_id}")
        self.assertEqual(resp_canonical_detail.status_code, 200, resp_canonical_detail.get_json())

        resp_alias_detail = self.client.get(f"{self.template_url}/versions/{v_id}")
        self.assertEqual(resp_alias_detail.status_code, 200, resp_alias_detail.get_json())

        self.assertEqual(resp_canonical_detail.headers.get("Cache-Control"), "private, no-store")
        self.assertEqual(resp_alias_detail.headers.get("Cache-Control"), "private, no-store")
        self.assertEqual(resp_canonical_detail.get_json(), resp_alias_detail.get_json())

        # 3. Alias with non-existent NoteType ID -> 404 TEMPLATE_NOT_FOUND.
        resp_wrong_nt = self.client.get(f"/api/note-types/non-existent-nt/templates/{self.template_id}/versions")
        self.assertEqual(resp_wrong_nt.status_code, 404, resp_wrong_nt.get_json())
        self.assertEqual(resp_wrong_nt.get_json()["error"], "TEMPLATE_NOT_FOUND")

        resp_wrong_nt_detail = self.client.get(
            f"/api/note-types/non-existent-nt/templates/{self.template_id}/versions/{v_id}"
        )
        self.assertEqual(resp_wrong_nt_detail.status_code, 404, resp_wrong_nt_detail.get_json())
        self.assertEqual(resp_wrong_nt_detail.get_json()["error"], "TEMPLATE_NOT_FOUND")

        resp_wrong_nt_restore = self.client.post(
            f"/api/note-types/non-existent-nt/templates/{self.template_id}/versions/{v_id}/restore",
            json={},
        )
        self.assertEqual(resp_wrong_nt_restore.status_code, 404, resp_wrong_nt_restore.get_json())
        self.assertEqual(resp_wrong_nt_restore.get_json()["error"], "TEMPLATE_NOT_FOUND")

        # 4. Alias with another valid NoteType ID of same owner -> 404 TEMPLATE_NOT_FOUND.
        nt2_resp = self.client.post("/api/note-types", json={
            "name": "Second Note Type",
            "field_defs": [{"name": "Field1", "field_type": "text", "position": 0}],
        })
        self.assertEqual(nt2_resp.status_code, 201, nt2_resp.get_json())
        other_nt_id = nt2_resp.get_json()["id"]

        resp_mismatched = self.client.get(f"/api/note-types/{other_nt_id}/templates/{self.template_id}/versions")
        self.assertEqual(resp_mismatched.status_code, 404, resp_mismatched.get_json())
        self.assertEqual(resp_mismatched.get_json()["error"], "TEMPLATE_NOT_FOUND")
