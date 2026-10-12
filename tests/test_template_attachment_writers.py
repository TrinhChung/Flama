"""Writer paths follow ACTIVE NoteType occurrences, not a Template's legacy origin.

A reusable definition attached to several NoteTypes, or a received copy with
no origin NoteType, must get Cards from every note-creating path. Removing it
from one NoteType retires only that occurrence: other NoteTypes keep their
Cards, and the definition keeps its history.
"""

import io
import tempfile
import unittest
from datetime import datetime, timezone

from app import create_app
from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
from app.repositories import template_library_repository
from app.connect import create_connect_app
from app.services import mcp_tool_service, user_api_token_service
from models import db
from models.card import Card
from models.study_progress_subject import StudyProgressSubject
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template
from models.template_version import TemplateVersion
from models.user import User

_SCHEMA = [{"key": "term", "type": "text", "label": "Term", "required": True}]


class NoteTypeTemplateMembershipTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False})

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            user = User(username="owner", email="owner@example.com")
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            enroll_new_learner_note_authority(db.session, user=user)
            deck = Deck(owner_user_id=user.id, name="Sync")
            db.session.add(deck)
            db.session.commit()
            self.user_id = user.id
            self.deck_id = deck.id
        self.client.post("/login", data={"email": "owner@example.com", "password": "password"})
        self.types = []
        for name in ("One", "Two"):
            response = self.client.post("/api/note-types", json={"name": name, "field_defs": [{"name": "Word", "field_type": "text"}]})
            self.assertEqual(response.status_code, 201, response.get_json())
            self.types.append(response.get_json())
        response = self.client.post("/api/card-templates", json={"name": "Reusable", "front_html": "{{term}}", "back_html": "{{FrontSide}}", "input_schema": _SCHEMA})
        self.assertEqual(response.status_code, 201, response.get_json())
        self.template_id = response.get_json()["id"]

    def tearDown(self):
        with self.app.app_context():
            db.session.rollback()
            db.session.remove()
            db.drop_all()

    def _nt(self, index):
        return self.types[index]["id"]

    def _default_template(self, index):
        with self.app.app_context():
            return next(row.template_id for row in template_library_repository.applications(db.session, self._nt(index)) if row.is_default)

    def _attach(self, index, template_id=None, bindings=True):
        data = {"template_id": template_id or self.template_id}
        if bindings:
            data["input_bindings"] = {"term": self.types[index]["field_defs"][0]["id"]}
        response = self.client.post(f"/api/note-types/{self._nt(index)}/template-applications", json=data)
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["id"]

    def _application(self, index, template_id):
        with self.app.app_context():
            return StudyApplication.query.filter_by(note_type_id=self._nt(index), template_id=template_id).one()

    def _note(self, index, word="犬"):
        response = self.client.post("/api/notes", json={"note_type_id": self._nt(index), "field_values": {"Word": word}})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["id"]

    def _second_template(self):
        response = self.client.post(f"/api/note-types/{self._nt(0)}/templates", json={"name": "Card 2", "front_html": "{{Word}}", "back_html": "{{Word}}"})
        self.assertEqual(response.status_code, 201, response.get_json())
        return response.get_json()["id"]

    def _assert_independent_attachment(self, index):
        # Every definition is independent; only an application attaches it.
        with self.app.app_context():
            self.assertNotIn("note_type_id", Template.__table__.c)
            self.assertTrue(template_library_repository.applications(db.session, self._nt(index)))

    def _card_templates(self, note_ids):
        with self.app.app_context():
            return {note_id: sorted(card.template_id for card in Card.query.filter_by(note_id=note_id)) for note_id in note_ids}

    def _csv_import(self, index, rows):
        parsed = self.client.post("/api/flashcards/import/parse", data={
            "note_type_id": self._nt(index), "delimiter_mode": "csv", "has_header": "1",
            "file": (io.BytesIO(("Word\n" + "\n".join(rows) + "\n").encode("utf-8")), "words.csv"),
        }, content_type="multipart/form-data")
        self.assertEqual(parsed.status_code, 200, parsed.get_json())
        payload = parsed.get_json()
        executed = self.client.post("/api/flashcards/import/execute", json={
            "token": payload["token"], "note_type_id": self._nt(index), "target_deck_id": self.deck_id,
            "import_mode": "insert_only", "uniqueness_fields": ["Word"], "mapping": payload.get("suggested_mapping", {}),
            "dont_overwrite_empty": True, "confirm_column_mismatch": False,
        })
        self.assertEqual(executed.status_code, 200, executed.get_json())
        self.assertEqual(executed.get_json()["summary"]["inserted"], len(rows))
        with self.app.app_context():
            return [note.id for note in Note.query.filter_by(note_type_id=self._nt(index)).order_by(Note.id)]

    def test_note_type_routes_edit_and_preview_attached_definition(self):
        self._attach(1)
        self._note(1, "犬")
        listed = self.client.get(f"/api/note-types/{self._nt(1)}").get_json()["templates"]
        self.assertIn(self.template_id, [item["id"] for item in listed])

        preview = self.client.post(f"/api/note-types/{self._nt(1)}/templates/{self.template_id}/preview", json={})
        self.assertEqual(preview.status_code, 200, preview.get_json())
        self.assertIn("犬", preview.get_json()["front_html"])

        with self.app.app_context():
            versions = TemplateVersion.query.filter_by(template_id=self.template_id).count()
        response = self.client.patch(f"/api/note-types/{self._nt(1)}/templates/{self.template_id}", json={"front_html": "<b>{{term}}</b>"})
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            self.assertEqual(db.session.get(Template, self.template_id).front_html, "<b>{{term}}</b>")
            self.assertEqual(TemplateVersion.query.filter_by(template_id=self.template_id).count(), versions + 1)

        # Not attached to One: the NoteType route still does not reach it.
        response = self.client.patch(f"/api/note-types/{self._nt(0)}/templates/{self.template_id}", json={"name": "Nope"})
        self.assertEqual(response.status_code, 404)

    def test_delete_from_note_type_detaches_shared_definition(self):
        shared = self._second_template()
        notes = [self._note(0, "猫"), self._note(1, "犬")]
        self._attach(1, shared, bindings=False)
        before = self._card_templates(notes)
        self.assertIn(shared, before[notes[0]])
        self.assertIn(shared, before[notes[1]])

        response = self.client.delete(f"/api/note-types/{self._nt(0)}/templates/{shared}")
        self.assertEqual(response.status_code, 200, response.get_json())
        # One stops presenting the shared definition; Two keeps it (ADR P11).
        self.assertEqual(self._card_templates(notes), {
            notes[0]: [item for item in before[notes[0]] if item != shared],
            notes[1]: before[notes[1]],
        })
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Template, shared))
        self.assertEqual(self._application(0, shared).status_code, "RETIRED")
        self.assertEqual(self._application(1, shared).status_code, "ACTIVE")
        listed = self.client.get(f"/api/note-types/{self._nt(0)}").get_json()["templates"]
        self.assertNotIn(shared, [item["id"] for item in listed])

    def test_delete_attached_definition_retires_only_this_occurrence(self):
        note = self._note(1)
        self._attach(1)
        response = self.client.delete(f"/api/note-types/{self._nt(1)}/templates/{self.template_id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        application = self._application(1, self.template_id)
        self.assertEqual(application.status_code, "RETIRED")
        # The retired occurrence presents nothing; its Card stays addressable (ADR P11).
        self.assertNotIn(self.template_id, self._card_templates([note])[note])
        with self.app.app_context():
            from models.card import card_key, get_card

            self.assertIsNotNone(get_card(db.session, card_key(note, application.id)))
            self.assertIsNone(db.session.get(Template, self.template_id).archived_at)

    def test_delete_requires_an_active_template_to_remain(self):
        second = self._second_template()
        first = self._application(0, self._default_template(0))
        response = self.client.delete(f"/api/note-types/{self._nt(0)}/template-applications/{first.id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        response = self.client.delete(f"/api/note-types/{self._nt(0)}/templates/{second}")
        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.get_json()["message"], "A note type requires at least one template.")
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Template, second))

    def test_unshared_attachment_delete_preserves_definition_and_history(self):
        second = self._second_template()
        note = self._note(0)
        with self.app.app_context():
            history_count = TemplateVersion.query.filter_by(template_id=second).count()
        response = self.client.delete(f"/api/note-types/{self._nt(0)}/templates/{second}")
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Template, second))
            self.assertEqual(TemplateVersion.query.filter_by(template_id=second).count(), history_count)
            self.assertEqual(StudyApplication.query.filter_by(note_type_id=self._nt(0), template_id=second).one().status_code,
                             "RETIRED")
        self.assertEqual(self._card_templates([note])[note], [self._default_template(0)])

    def test_csv_import_creates_cards_for_active_occurrences_only(self):
        retired = self._second_template()
        response = self.client.delete(f"/api/note-types/{self._nt(0)}/template-applications/{self._application(0, retired).id}")
        self.assertEqual(response.status_code, 200, response.get_json())
        self._attach(0)
        notes = self._csv_import(0, ["犬", "猫"])
        expected = sorted([self._default_template(0), self.template_id])
        self.assertEqual(self._card_templates(notes), {note: expected for note in notes})
        with self.app.app_context():
            statuses = {card.application.status_code for card in Card.query.filter(Card.note_id.in_(notes))}
        self.assertEqual(statuses, {"ACTIVE"})

    def test_csv_import_into_note_type_without_legacy_templates(self):
        legacy = self._default_template(1)
        self._assert_independent_attachment(1)
        notes = self._csv_import(1, ["犬"])
        self.assertEqual(self._card_templates(notes), {notes[0]: [legacy]})

    def test_sync_notes_materializes_attached_occurrences(self):
        legacy = self._default_template(1)
        self._assert_independent_attachment(1)
        self._attach(1)
        with self.app.app_context():
            result = mcp_tool_service.sync_notes(
                user_id=self.user_id, source_key="sheet:words", deck_path="Sync", note_type_id=self._nt(1),
                notes=[{"external_id": "row-1", "fields": {"Word": "犬"}}],
            )
            self.assertTrue(result["success"], result)
            self.assertEqual(result["summary"]["created"], 1)
            note_id = result["created_note_ids"][0]
        self.assertEqual(self._card_templates([note_id])[note_id], sorted([legacy, self.template_id]))


class _ConnectHarness(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.upload_root = tempfile.TemporaryDirectory()
        cls.app = create_connect_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:", "CONNECT_CORS_ALLOWED_ORIGINS": (),
            "CONNECT_LEGACY_WEB_ACTIONS_ENABLED": True, "CONNECT_IP_RATE_LIMIT": 1000, "CONNECT_TOKEN_RATE_LIMIT": 1000, "CONNECT_USER_RATE_LIMIT": 1000,
            "CONNECT_ADD_NOTE_RATE_LIMIT": 1000, "FLASHCARD_MEDIA_UPLOAD_ROOT": cls.upload_root.name,
        })

    @classmethod
    def tearDownClass(cls):
        cls.upload_root.cleanup()

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            owner = User(username="connect-owner", email="connect@example.com")
            owner.set_password("password")
            db.session.add(owner)
            db.session.flush()
            self.user_id = owner.id
            from app.services.study_authority_enrollment_service import enroll_new_learner_note_authority
            enroll_new_learner_note_authority(db.session, user=owner)
            self.note_type_id, self.word_field_id, self.legacy_id = self._note_type("Yomitan Vocabulary")
            definition = Template(owner_user_id=owner.id, name="Reusable", front_html="{{term}}", back_html="{{FrontSide}}", input_schema=_SCHEMA)
            db.session.add_all([definition, Deck(owner_user_id=owner.id, name="Inbox")])
            db.session.flush()
            self.template_id = definition.id
            db.session.add(StudyApplication(note_type_id=self.note_type_id, template_id=definition.id, occurrence_key="compat", status_code="ACTIVE", input_bindings={"term": self.word_field_id}, position=1))
            self.token = user_api_token_service.issue_token(user_id=owner.id, name="Yomitan PC").plaintext
            db.session.commit()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def _note_type(self, name, *, extra_template=False):
        note_type = NoteType(user_id=self.user_id, name=name)
        db.session.add(note_type)
        db.session.flush()
        word = FieldDef(note_type_id=note_type.id, name="Word", field_type="text", position=0, required=True, identity_role="primary")
        meaning = FieldDef(note_type_id=note_type.id, name="Meaning", field_type="text", position=1)
        db.session.add_all([word, meaning])
        db.session.flush()
        templates = [template_library_repository.create_attached_template(db.session, note_type=note_type,
                     name="Card 1", front_html="{{Word}}", back_html="{{Meaning}}", position=0, is_default=True)]
        if extra_template:
            templates.append(template_library_repository.create_attached_template(db.session, note_type=note_type, name="Card 2", front_html="{{Meaning}}", back_html="{{Word}}", position=1))
        db.session.add_all([word, meaning, *templates])
        db.session.flush()
        return note_type.id, word.id, templates[0].id

    def _cards(self, note_type_id=None):
        with self.app.app_context():
            query = Card.query.join(Note, Note.id == Card.note_id).filter(Note.note_type_id == (note_type_id or self.note_type_id))
            return {card.template_id: card.id for card in query}

    def _enroll_note_authority(self):
        from app.services.study_authority_enrollment_service import stage_note_authority_enrollment
        with self.app.app_context():
            stage_note_authority_enrollment(db.session, learner_user_id=self.user_id, now_utc=datetime.now(timezone.utc).replace(tzinfo=None))
            db.session.commit()


class ConnectAttachmentImportTests(_ConnectHarness):
    def _call(self, action, params):
        return self.client.post("/v1/flama-connect", json={"action": action, "params": params, "version": 2, "key": self.token})

    def _session(self):
        plan = {
            "sourceModelId": "1001", "sourceModelName": "Yomitan Vocabulary", "targetNoteTypeId": self.note_type_id,
            "fields": [{"name": "Word", "fieldType": "text"}, {"name": "Meaning", "fieldType": "text"}],
            "templates": [{"name": "Card 1", "frontHtml": "{{Word}}", "backHtml": "{{Meaning}}", "sharedCss": ""}],
            "fieldMapping": {"Word": "Word", "Meaning": "Meaning"},
        }
        session = self._call("createImportSession", {
            "source": "anki", "sourceKey": "test-profile", "sourceRootPath": "Inbox", "targetRootPath": "Inbox",
            "selectedDecks": ["Inbox"], "totalNotes": 1, "totalMedia": 0, "mode": "strict", "noteTypes": [plan], "planHash": "a" * 64,
        }).get_json()
        self.assertEqual(session["status"], "note_types_ready", session)
        return session["importSessionId"]

    def _import(self, session_id, meaning, content_hash):
        note = {"deckName": "Inbox", "modelName": self.note_type_id, "fields": {"Word": "猫", "Meaning": meaning}, "tags": []}
        response = self._call("importCards", {"importSessionId": session_id, "cards": [{
            "ankiNoteId": 101, "sourceModelId": "1001", "sourceDeckId": "1", "sourceDeckPath": "Inbox",
            "contentHash": content_hash, "note": note,
        }]})
        result = response.get_json()["results"][0]
        self.assertTrue(result["imported"], result)

    def _assert_reimport_keeps_attached_card(self):
        session_id = self._session()
        self._import(session_id, "cat", "1" * 64)
        cards = self._cards()
        self.assertEqual(set(cards), {self.legacy_id, self.template_id})
        with self.app.app_context():
            note_id = Card.query.filter_by(id=cards[self.template_id]).one().note_id
            subject = StudyProgressSubject.query.filter_by(learner_user_id=self.user_id, live_note_id=note_id).first()
            if subject is None:
                now = datetime.now(timezone.utc).replace(tzinfo=None)
                subject = StudyProgressSubject(learner_user_id=self.user_id, live_note_id=note_id,
                    logical_note_key=note_id.encode("utf-8"), subject_generation=1, mirror_revision=0,
                    status_code="NO_CURRENT_PROGRESS", contributor_count=0, created_at=now, updated_at=now)
                db.session.add(subject)
            db.session.commit()
            subject_id, generation, revision = subject.id, subject.subject_generation, subject.authority_revision
        self._import(session_id, "kitten", "2" * 64)
        self.assertEqual(self._cards(), cards)
        with self.app.app_context():
            preserved = db.session.get(StudyProgressSubject, subject_id)
            self.assertEqual((preserved.live_note_id, preserved.subject_generation, preserved.authority_revision),
                             (note_id, generation, revision))

    def test_import_creates_and_reimport_preserves_attached_definition_cards(self):
        self._assert_reimport_keeps_attached_card()

    def test_note_authority_import_preserves_attached_definition_cards(self):
        self._enroll_note_authority()
        session_id = self._session()
        self._import(session_id, "cat", "1" * 64)
        cards = self._cards()
        self.assertEqual(set(cards), {self.legacy_id, self.template_id})
        self._import(session_id, "kitten", "2" * 64)
        self.assertEqual(self._cards(), cards)

    def test_import_targets_note_type_without_legacy_templates(self):
        with self.app.app_context():
            # A received NoteType reaches its copy only through an occurrence.
            self.assertNotIn("note_type_id", Template.__table__.c)
            StudyApplication.query.filter_by(template_id=self.template_id).one().status_code = "RETIRED"
            db.session.commit()
        self._import(self._session(), "cat", "1" * 64)
        self.assertEqual(set(self._cards()), {self.legacy_id})


class McpTemplateRemovalTests(_ConnectHarness):
    def setUp(self):
        super().setUp()
        with self.app.app_context():
            self.source_id, _word, _legacy = self._note_type("Source", extra_template=True)
            self.shared_id = next(row.id for row in template_library_repository.attached_templates(db.session, self.source_id) if row.name == "Card 2")
            db.session.add(StudyApplication(note_type_id=self.note_type_id, template_id=self.shared_id, occurrence_key="compat", status_code="ACTIVE", input_bindings={}, position=2))
            for note_type_id in (self.source_id, self.note_type_id):
                # Each Note presents its NoteType's occurrences (ADR P11).
                db.session.add(Note(user_id=self.user_id, note_type_id=note_type_id, field_values={"Word": "猫", "Meaning": "cat"}))
            db.session.commit()

    def _remove_shared(self):
        changes = {"removed": ["Card 2"]}
        with self.app.app_context():
            preview = mcp_tool_service.preview_note_type_update(user_id=self.user_id, note_type_id=self.source_id, templates=changes)
            mcp_tool_service.update_note_type(user_id=self.user_id, note_type_id=self.source_id, templates=changes, preview_id=preview["preview_id"], confirm=True)

    def _assert_detached(self, before):
        with self.app.app_context():
            self.assertIsNotNone(db.session.get(Template, self.shared_id))
            statuses = {row.note_type_id: row.status_code for row in StudyApplication.query.filter_by(template_id=self.shared_id)}
        self.assertEqual(statuses, {self.source_id: "RETIRED", self.note_type_id: "ACTIVE"})
        self.assertEqual(self._cards(), before)

    def test_template_removal_detaches_definition_shared_with_another_note_type(self):
        before = self._cards()
        self.assertIn(self.shared_id, before)
        self._remove_shared()
        self._assert_detached(before)

    def test_note_authority_removal_detaches_shared_definition(self):
        self._enroll_note_authority()
        before = self._cards()
        self._remove_shared()
        self._assert_detached(before)

    def test_schema_of_published_note_type_hides_unpublished_author_drafts(self):
        from app.services.template_release_service import stage_note_type_publications
        with self.app.app_context():
            reader = User(username="reader", email="reader@example.com")
            reader.set_password("password")
            db.session.add(reader)
            note_type = db.session.get(NoteType, self.source_id)
            note_type.publish_status = "published"
            stage_note_type_publications(db.session, note_type_id=self.source_id, actor_user_id=self.user_id)
            db.session.commit()
            db.session.get(Template, self.shared_id).front_html = "<i>unpublished draft</i>"
            db.session.commit()
            reader_id = reader.id
            published = mcp_tool_service.get_note_type_schema(user_id=reader_id, note_type_id=self.source_id)
            owned = mcp_tool_service.get_note_type_schema(user_id=self.user_id, note_type_id=self.source_id)
        published_sources = {row["id"]: row["front_html"] for row in published["templates"]}
        self.assertEqual(published_sources[self.shared_id], "{{Meaning}}")
        self.assertNotIn("unpublished draft", str(published["templates"]))
        self.assertEqual({row["id"]: row["front_html"] for row in owned["templates"]}[self.shared_id], "<i>unpublished draft</i>")


if __name__ == "__main__":
    unittest.main()
