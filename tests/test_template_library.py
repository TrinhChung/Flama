"""Reusable ownership, safe attachments, ID bindings and personal presets."""

import unittest
from datetime import datetime, timezone
from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
from app import create_app
from models import db
from models.user import User
from models.card import Card
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.template_version import TemplateVersion
from models.study_application import StudyApplication
from app.services.study_artifact_service import build_effective_study_card


class TemplateLibraryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="owner", email="owner@example.com")
            user.set_password("password")
            other = User(username="other", email="other@example.com")
            other.set_password("password")
            db.session.add_all([user, other])
            db.session.flush()
            for learner in (user, other):
                enroll_new_learner_note_authority(db.session, user=learner)
            db.session.commit()
            self.user_id = user.id
        self.client.post("/login", data={"email": "owner@example.com", "password": "password"})
        self.types = []
        for name in ("One", "Two"):
            response = self.client.post("/api/note-types", json={"name": name, "field_defs": [{"name": "Word", "field_type": "text"}]})
            self.assertEqual(response.status_code, 201, response.get_json())
            self.types.append(response.get_json())
        response = self.client.post("/api/card-templates", json={"name": "Reusable", "front_html": "{{term}}", "back_html": "{{FrontSide}}", "input_schema": [{"key": "term", "type": "text", "label": "Term", "required": True}]})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.definition = response.get_json()
        self.template_id = self.definition["id"]

    def tearDown(self):
        with self.app.app_context():
            db.session.rollback()
            db.session.remove()
            db.drop_all()

    def _attach(self, index=0, occurrence="compat", bindings=True):
        data = {"template_id": self.template_id, "occurrence_key": occurrence}
        if bindings:
            data["input_bindings"] = {"term": self.types[index]["field_defs"][0]["id"]}
        response = self.client.post(f"/api/note-types/{self.types[index]['id']}/template-applications", json=data)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()

    def _note(self, index=0):
        response = self.client.post("/api/notes", json={"note_type_id": self.types[index]["id"], "field_values": {"Word": "犬"}})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["id"]

    def test_independent_versioned_template_is_in_owner_library(self):
        self.assertTrue(self.definition["current_version_id"])
        with self.app.app_context():
            row = db.session.get(Template, self.template_id)
            self.assertNotIn("note_type_id", Template.__table__.c)
            self.assertEqual(row.owner_user_id, self.user_id)
            self.assertEqual(StudyApplication.query.filter_by(template_id=row.id).count(), 0)
            self.assertEqual(TemplateVersion.query.filter_by(template_id=row.id).count(), 1)
        response = self.client.get("/api/card-templates?q=Reusable")
        self.assertEqual([item["id"] for item in response.get_json()["items"]], [self.template_id])
        response = self.client.get(f"/api/card-templates/{self.template_id}/versions")
        self.assertEqual(response.status_code, 200)

    def test_cross_note_type_attachments_create_cards_and_reject_duplicate_on_same_note_type(self):
        self._note(0)
        self._note(1)
        applications = [self._attach(0), self._attach(1)]
        duplicate = self.client.post(
            f"/api/note-types/{self.types[0]['id']}/template-applications",
            json={"template_id": self.template_id, "occurrence_key": "reverse"},
        )
        self.assertEqual(duplicate.status_code, 409, duplicate.get_json())
        self.assertEqual(duplicate.get_json()["error"], "APPLICATION_EXISTS")
        with self.app.app_context():
            cards = Card.query.filter_by(template_id=self.template_id).all()
            self.assertEqual(len(cards), 2)
            self.assertEqual({item.application_id for item in cards}, {item["id"] for item in applications})
        self._note(0)
        with self.app.app_context():
            self.assertEqual(Card.query.filter_by(template_id=self.template_id).count(), 3)

    def test_retire_hides_cards_and_reactivation_restores_the_same_keys(self):
        from models.card import get_card

        application = self._attach()
        self._note()
        base = f"/api/note-types/{self.types[0]['id']}/template-applications/{application['id']}"
        with self.app.app_context():
            old_ids = {item.id for item in Card.query.filter_by(template_id=self.template_id)}
            self.assertEqual(len(old_ids), 1)
        self.assertEqual(self.client.delete(base).status_code, 200)
        self._note()
        with self.app.app_context():
            # A retired occurrence presents nothing; a dealt Card stays addressable.
            self.assertEqual(Card.query.filter_by(template_id=self.template_id).count(), 0)
            self.assertIsNotNone(get_card(db.session, next(iter(old_ids))))
        revived = self._attach()
        self.assertEqual(revived["id"], application["id"])
        with self.app.app_context():
            ids = {item.id for item in Card.query.filter_by(template_id=self.template_id)}
            self.assertEqual(len(ids), 2)
            self.assertTrue(old_ids <= ids)

    def test_attach_writes_one_occurrence_and_no_row_per_note(self):
        # Template is presentation: attaching it is O(1) whatever the Note count (ADR P11).
        from sqlalchemy import event

        for _ in range(5):
            self._note()
        statements = []

        def capture(_conn, _cursor, statement, _params, _context, _executemany):
            statements.append(statement.lower())

        with self.app.app_context():
            engine = db.engine
            event.listen(engine, "before_cursor_execute", capture)
            try:
                self._attach()
            finally:
                event.remove(engine, "before_cursor_execute", capture)
            self.assertEqual(Card.query.filter_by(template_id=self.template_id).count(), 5)
        self.assertEqual([sql for sql in statements if sql.startswith("insert into cards")], [])
        self.assertEqual(len([sql for sql in statements if sql.startswith("insert into study_applications")]), 1)

    def test_bound_input_survives_field_rename_without_source_rewrite(self):
        application = self._attach()
        note_id = self._note()
        field = self.types[0]["field_defs"][0]
        response = self.client.patch(f"/api/note-types/{self.types[0]['id']}/fields/{field['id']}", json={"name": "Expression"})
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id, template_id=self.template_id).one()
            context = build_effective_study_card(card=card, clone_scope=None)
            self.assertEqual(context.field_values["term"], "犬")
            self.assertEqual(card.template.front_html, "{{term}}")
            self.assertEqual(card.application.input_bindings, application["input_bindings"])

    def test_required_unbound_input_warns_and_renders_empty(self):
        application = self._attach(bindings=False)
        self.assertEqual(application["warnings"][0]["code"], "INPUT_UNBOUND")
        note_id = self._note()
        with self.app.app_context():
            card = Card.query.filter_by(note_id=note_id, template_id=self.template_id).one()
            context = build_effective_study_card(card=card, clone_scope=None)
            self.assertEqual(context.field_values["term"], "")

    def test_invalid_schema_bindings_compile_and_body_are_atomic(self):
        before = self.client.get(f"/api/card-templates/{self.template_id}/versions").get_json()
        for payload in (["bad"], {"input_schema": [{"key": "x"}, {"key": "x"}]}, {"input_schema": [{"key": "FrontSide"}]}, {"front_html": "{{#unclosed}}"}, {"name": ""}):
            response = self.client.patch(f"/api/card-templates/{self.template_id}", json=payload)
            self.assertEqual(response.status_code, 400, response.get_json())
        self.assertEqual(before, self.client.get(f"/api/card-templates/{self.template_id}/versions").get_json())
        response = self.client.post(f"/api/note-types/{self.types[0]['id']}/template-applications", json={"template_id": self.template_id, "input_bindings": {"term": self.types[1]["field_defs"][0]["id"]}})
        self.assertEqual(response.status_code, 400)
        with self.app.app_context():
            self.assertEqual(StudyApplication.query.filter_by(template_id=self.template_id).count(), 0)

    def test_update_shared_definition_warns_all_attachments_and_checks_stale_head(self):
        a, b = self._attach(0), self._attach(1)
        response = self.client.patch(f"/api/card-templates/{self.template_id}", json={"front_html": "<b>{{term}}</b>", "expected_current_version_id": self.definition["current_version_id"]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(set(response.get_json()["affected_applications"]), {a["id"], b["id"]})
        response = self.client.patch(f"/api/card-templates/{self.template_id}", json={"front_html": "lost", "expected_current_version_id": self.definition["current_version_id"]})
        self.assertEqual(response.status_code, 409)

    def test_archive_hides_library_and_blocks_attach_but_preserves_existing(self):
        application = self._attach()
        self._note()
        response = self.client.patch(f"/api/card-templates/{self.template_id}/archive", json={"archived": True})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(any(item["id"] == self.template_id for item in self.client.get("/api/card-templates").get_json()["items"]))
        self.assertTrue(any(item["id"] == self.template_id for item in self.client.get("/api/card-templates?include_archived=true").get_json()["items"]))
        response = self.client.post(f"/api/note-types/{self.types[1]['id']}/template-applications", json={"template_id": self.template_id})
        self.assertEqual(response.status_code, 409)
        with self.app.app_context():
            self.assertEqual(db.session.get(StudyApplication, application["id"]).status_code, "ACTIVE")
            self.assertEqual(Card.query.filter_by(template_id=self.template_id).count(), 1)

    def test_attach_reads_no_learner_progress_or_session(self):
        # Adding a sibling writes no progress (ADR P10 §2.3): no learner fence or recheck.
        from sqlalchemy import event

        self._note()
        self._note()
        statements = []

        def capture(_conn, _cursor, statement, _params, _context, _executemany):
            statements.append(statement.lower())

        with self.app.app_context():
            engine = db.engine
            event.listen(engine, "before_cursor_execute", capture)
            try:
                self._attach()
            finally:
                event.remove(engine, "before_cursor_execute", capture)
        learner_tables = ("study_progress_subjects", "card_progress", "study_session_cards",
                          "study_sessions", "study_authority_enrollments", "study_authority_storage_profile")
        self.assertEqual([sql for sql in statements if any(table in sql for table in learner_tables)], [])

    def test_duplicate_has_new_independent_history(self):
        response = self.client.post(f"/api/card-templates/{self.template_id}/duplicate", json={"name": "Second"})
        self.assertEqual(response.status_code, 201, response.get_json())
        data = response.get_json()
        self.assertNotEqual(data["id"], self.template_id)
        self.assertNotEqual(data["current_version_id"], self.definition["current_version_id"])
        self.assertEqual(data["front_html"], self.definition["front_html"])

    def test_cross_user_ownership_hidden_and_no_binding_write(self):
        self.client.post("/logout")
        self.client.post("/login", data={"email": "other@example.com", "password": "password"})
        self.assertEqual(self.client.get(f"/api/card-templates/{self.template_id}").status_code, 404)
        self.assertEqual(self.client.patch(f"/api/card-templates/{self.template_id}", json={"name": "stolen"}).status_code, 404)
        self.assertEqual(self.client.post(f"/api/note-types/{self.types[0]['id']}/template-applications", json={"template_id": self.template_id}).status_code, 404)

    def test_delete_template_success_and_in_use_error(self):
        # 1. Cannot delete when in use by active application
        self._attach(0)
        res_in_use = self.client.delete(f"/api/card-templates/{self.template_id}")
        self.assertEqual(res_in_use.status_code, 409)
        self.assertEqual(res_in_use.get_json()["error"], "TEMPLATE_IN_USE")

        # 2. Can delete a standalone template
        created = self.client.post("/api/card-templates", json={"name": "Standalone", "front_html": "q", "back_html": "a"}).get_json()
        standalone_id = created["id"]
        res_delete = self.client.delete(f"/api/card-templates/{standalone_id}")
        self.assertEqual(res_delete.status_code, 200)
        self.assertTrue(res_delete.get_json()["success"])
        # Verify it's gone
        res_get = self.client.get(f"/api/card-templates/{standalone_id}")
        self.assertEqual(res_get.status_code, 404)
