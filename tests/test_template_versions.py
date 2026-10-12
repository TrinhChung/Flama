"""Transactional source history and owner API tests (CT-03, contract A2)."""

from datetime import datetime, timezone
from unittest import TestCase
from unittest.mock import patch

from sqlalchemy import insert

from app import create_app
from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
from app.repositories import template_library_repository
from app.services import template_version_service
from app.services.template_tokens import template_content_hash
from models import db
from models.card import Card
from models.deck import Deck
from models.model_uuid import uuid_str
from models.note_type import NoteType
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User


class TemplateVersionsTests(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
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
            for learner in (user, other):
                enroll_new_learner_note_authority(db.session, user=learner)
            self.user_id, self.other_id = user.id, other.id
            deck = Deck(name="History deck", owner_user_id=user.id)
            db.session.add(deck)
            db.session.commit()
            self.deck_id = deck.id
        self.client.post("/login", data={"email": "owner@example.com", "password": "password"})
        response = self.client.post("/api/note-types", json={
            "name": "History type",
            "field_defs": [{"name": "Kanji", "field_type": "text", "position": 0},
                           {"name": "Meaning", "field_type": "text", "position": 1}],
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

    def _history(self):
        response = self.client.get(self.base)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def _patch(self, payload):
        response = self.client.patch(self.template_url, json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        return response.get_json()

    def test_create_update_noop_metadata_and_content_hash(self):
        initial = self._history()
        self.assertEqual(initial["schema_version"], "template-versions.v2")
        self.assertEqual(len(initial["items"]), 1)
        self.assertEqual(initial["items"][0]["origin"], "create")
        self.assertEqual(initial["items"][0]["created_by"]["id"], self.user_id)
        self._patch({"front_html": "<b>{{Kanji}}</b>", "change_note": "sửa màu"})
        self._patch({"back_html": "{{Meaning}}", "shared_css": ".card{color:red}"})
        self._patch({"name": "Renamed"})
        self._patch({"back_html": "{{Meaning}}", "shared_css": ".card{color:red}"})
        history = self._history()
        self.assertEqual([item["version_no"] for item in history["items"]], [3, 2, 1])
        self.assertEqual([item["is_current"] for item in history["items"]], [True, False, False])
        self.assertEqual(history["items"][1]["change_note"], "sửa màu")
        detail = self.client.get(f"{self.base}/{history['items'][0]['id']}").get_json()
        self.assertEqual(detail["content_hash"], template_content_hash(
            detail["front_html"], detail["back_html"], detail["shared_css"],
        ))
        self.assertEqual([(item["key"], item["type"]) for item in detail["input_schema"]],
                         [("Kanji", "text"), ("Meaning", "text")])
        self.assertTrue(detail["created_at"].endswith("+00:00"))

    def test_legacy_alias_and_ownership_hide_other_templates(self):
        alias = self.client.get(f"{self.template_url}/versions")
        self.assertEqual(alias.status_code, 200)
        self.assertEqual(alias.get_json(), self._history())
        first = alias.get_json()["items"][0]["id"]
        self.assertEqual(self.client.get(f"{self.template_url}/versions/{first}").status_code, 200)
        self.assertEqual(self.client.get(
            f"/api/note-types/not-the-type/templates/{self.template_id}/versions",
        ).status_code, 404)
        self.client.post("/logout")
        self.client.post("/login", data={"email": "other@example.com", "password": "password"})
        for method, url in [("get", self.base), ("get", f"{self.base}/{first}"),
                            ("post", f"{self.base}/{first}/restore")]:
            response = getattr(self.client, method)(url)
            self.assertEqual(response.status_code, 404)
            self.assertEqual(response.get_json()["error"], "TEMPLATE_NOT_FOUND")

    def test_restore_appends_and_preserves_card_ids(self):
        response = self.client.post("/api/notes", json={
            "note_type_id": self.nt_id, "deck_id": self.deck_id,
            "field_values": {"Kanji": "日本", "Meaning": "Japan"},
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        with self.app.app_context():
            card_ids = [row.id for row in Card.query.filter_by(template_id=self.template_id).all()]
        first = self._history()["items"][0]["id"]
        self._patch({"front_html": "CHANGED"})
        with patch("app.services.deck_working_tree_service.note_type_has_shared_release_dependents", return_value=True):
            restored = self.client.post(f"{self.base}/{first}/restore", json={"change_note": "restore old"})
        self.assertEqual(restored.status_code, 200, restored.get_json())
        self.assertEqual(restored.get_json()["front_html"], "{{Kanji}}")
        history = self._history()
        self.assertEqual(len(history["items"]), 3)
        self.assertEqual(history["items"][0]["origin"], "restore")
        self.assertEqual(history["items"][0]["change_note"], "restore old")
        self.assertEqual(history["current_version_id"], restored.get_json()["current_version_id"])
        self.assertIn(first, [item["id"] for item in history["items"]])
        with self.app.app_context():
            self.assertEqual(card_ids, [row.id for row in Card.query.filter_by(template_id=self.template_id).all()])

    def test_restore_same_content_is_explicit_history_event(self):
        first = self._history()["items"][0]["id"]
        response = self.client.post(f"{self.base}/{first}/restore", json={})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(len(self._history()["items"]), 2)

    def test_wrong_version_and_invalid_body_do_not_append(self):
        response = self.client.post(f"{self.base}/wrong-id/restore", json={})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["error"], "TEMPLATE_VERSION_NOT_FOUND")
        first = self._history()["items"][0]["id"]
        for payload in (["bad"], {"front_html": "override"}, {"change_note": "x" * 1001}, {"change_note": 12}):
            response = self.client.post(f"{self.base}/{first}/restore", json=payload)
            self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(len(self._history()["items"]), 1)

    def test_invalid_compile_rolls_back_restore(self):
        with self.app.app_context():
            template = db.session.get(Template, self.template_id)
            template.front_html = "{{#unclosed}}"
            db.session.commit()
            bad_version = template.current_version_id
            template.front_html = "{{Kanji}}"
            db.session.commit()
        before = self._history()
        response = self.client.post(f"{self.base}/{bad_version}/restore", json={})
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["error"], "TEMPLATE_COMPILE_ERROR")
        self.assertEqual(self._history(), before)
        with self.app.app_context():
            self.assertEqual(db.session.get(Template, self.template_id).front_html, "{{Kanji}}")

    def test_structural_restore_stays_closed_for_released_note_type(self):
        first = self._history()["items"][0]["id"]
        with self.app.app_context():
            template = db.session.get(Template, self.template_id)
            template.input_schema = [{"key": "input", "label": "Input", "type": "text", "required": False}]
            db.session.commit()
        with patch("app.services.deck_working_tree_service.note_type_has_shared_release_dependents", return_value=True):
            response = self.client.post(f"{self.base}/{first}/restore", json={})
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["error"], "SHARED_SCHEMA_VERSIONING_REQUIRED")
        self.assertEqual(len(self._history()["items"]), 2)

    def test_multiple_flushes_coalesce_at_outer_commit_and_rollback_is_clean(self):
        with self.app.app_context():
            template = template_library_repository.create_attached_template(db.session, note_type=db.session.get(NoteType, self.nt_id), name="Imported", front_html="intermediate", back_html="")
            db.session.add(template)
            db.session.flush()
            template_id = template.id
            template.front_html = "final"
            db.session.flush()
            self.assertEqual(TemplateVersion.query.filter_by(template_id=template_id).count(), 0)
            db.session.commit()
            versions = TemplateVersion.query.filter_by(template_id=template_id).all()
            self.assertEqual(len(versions), 1)
            self.assertEqual(versions[0].front_html, "final")
            template.front_html = "rolled-back"
            db.session.flush()
            db.session.rollback()
            template = db.session.get(Template, template_id)
            self.assertEqual(template.front_html, "final")
            template.front_html = "next"
            db.session.commit()
            self.assertEqual(TemplateVersion.query.filter_by(template_id=template_id).count(), 2)

    def test_savepoint_rollback_preserves_outer_changes(self):
        with self.app.app_context():
            template = db.session.get(Template, self.template_id)
            template.front_html = "outer"
            with db.session.begin_nested() as savepoint:
                template.back_html = "inner"
                template_version_service.mark_template_version(template, origin="reset")
                db.session.flush()
                savepoint.rollback()
            db.session.commit()
            versions = TemplateVersion.query.filter_by(template_id=self.template_id).order_by(TemplateVersion.version_no).all()
            self.assertEqual(len(versions), 2)
            self.assertEqual(versions[-1].front_html, "outer")
            self.assertEqual(versions[-1].back_html, "{{Kanji}}<hr>{{Meaning}}")
            self.assertEqual(versions[-1].origin, "edit")

    def test_versions_are_immutable_and_delete_cascades(self):
        with self.app.app_context():
            version = TemplateVersion.query.filter_by(template_id=self.template_id).first()
            version.front_html = "tamper"
            with self.assertRaises(template_version_service.TemplateVersionError):
                db.session.commit()
            db.session.rollback()
            self.assertEqual(TemplateVersion.query.filter_by(template_id=self.template_id).first().front_html, "{{Kanji}}")
            db.session.delete(db.session.get(Template, self.template_id))
            db.session.commit()
            self.assertEqual(TemplateVersion.query.filter_by(template_id=self.template_id).count(), 0)

    def test_backfill_is_idempotent_and_dirty_unversioned_row_keeps_baseline(self):
        with self.app.app_context():
            template_id = uuid_str()
            now = datetime.utcnow()
            db.session.execute(insert(Template.__table__).values(
                id=template_id, owner_user_id=self.user_id, name="Unversioned", front_html="original\r\n漢字",
                back_html="", shared_css="", position=2, is_default=False, created_at=now, updated_at=now,
            ))
            db.session.commit()
            template = db.session.get(Template, template_id)
            template.front_html = "new content"
            db.session.commit()
            rows = TemplateVersion.query.filter_by(template_id=template_id).order_by(TemplateVersion.version_no).all()
            self.assertEqual([(row.origin, row.front_html) for row in rows],
                             [("backfill", "original\r\n漢字"), ("edit", "new content")])
            self.assertEqual(template_version_service.backfill_versions(), 0)
            db.session.commit()
            self.assertEqual(TemplateVersion.query.filter_by(template_id=template_id).count(), 2)

    def test_automatic_defaults_reject_reserved_names_without_rows(self):
        with self.app.app_context():
            before_types = NoteType.query.count()
            before_versions = TemplateVersion.query.count()
        for index, name in enumerate(["#Kanji", "!Word", ".", "A}}B"]):
            response = self.client.post("/api/note-types", json={
                "name": f"Bad {index}", "field_defs": [{"name": name, "field_type": "text", "position": 0}],
            })
            self.assertEqual(response.status_code, 400, response.get_json())
            self.assertEqual(response.get_json()["error"], "VALIDATION_ERROR")
        with self.app.app_context():
            self.assertEqual(NoteType.query.count(), before_types)
            self.assertEqual(TemplateVersion.query.count(), before_versions)
        response = self.client.post("/api/note-types", json={
            "name": "Explicit reserved field", "field_defs": [{"name": "#Kanji", "field_type": "text", "position": 0}],
            "template": {"front_html": "explicit", "back_html": "explicit"},
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        created_id = response.get_json()["id"]
        response = self.client.post(f"/api/note-types/{created_id}/templates", json={"name": "Automatic"})
        self.assertEqual(response.status_code, 400, response.get_json())
