"""Integration tests for template note count in note-type template listing (GT-02)."""

import unittest
from uuid import uuid4

from app import create_app
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User

from tests.study_note_fixtures import attach_template, create_note_user

class TemplateNoteCountTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "STARTUP_RUN_MAINTENANCE": False,
                "STARTUP_CHECK_DB_CONNECTIVITY": False,
            }
        )

    def setUp(self):
        self.app.config["STUDY_PROGRESS_SHADOW_COMPARE_ENABLED"] = False
        self.client = self.app.test_client()

        with self.app.app_context():
            db.create_all()
            user = create_note_user(db.session, username="admin", email="admin@example.com", is_admin=True)
            user.set_password("password")
            db.session.add(user)
            db.session.flush()
            self.user_id = user.id

            deck = Deck(name="Deck A", owner_user_id=self.user_id)
            db.session.add(deck)
            db.session.flush()
            self.deck_id = deck.id
            db.session.commit()

        self.client.post(
            "/login",
            data={"email": "admin@example.com", "password": "password"},
            follow_redirects=True,
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_counts_distinct_notes_per_template(self):
        with self.app.app_context():
            nt = NoteType(name="NT 1", user_id=self.user_id)
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            fd = FieldDef(note_type_id=nt_id, name="Front", field_type="text", position=0)
            db.session.add(fd)

            t1 = attach_template(db.session, owner_user_id=self.user_id,
                note_type_id=nt_id,
                name="T1",
                front_html="{{Front}}",
                back_html="{{Front}}",
                position=0,
                is_default=True,
            )
            t2 = attach_template(db.session, owner_user_id=self.user_id,
                note_type_id=nt_id,
                name="T2",
                front_html="{{Front}}",
                back_html="{{Front}}",
                position=1,
                is_default=False,
            )
            db.session.add_all([t1, t2])
            db.session.flush()
            t1_id = t1.id
            t2_id = t2.id

            n1 = Note(user_id=self.user_id, deck_id=self.deck_id, note_type_id=nt_id, field_values={"Front": "1"})
            n2 = Note(user_id=self.user_id, deck_id=self.deck_id, note_type_id=nt_id, field_values={"Front": "2"})
            n3 = Note(user_id=self.user_id, deck_id=self.deck_id, note_type_id=nt_id, field_values={"Front": "3"})
            db.session.add_all([n1, n2, n3])
            db.session.flush()

            # Explicit pre-cutover evidence preserves historical missing pairs:
            # all three Notes had T1, while only n1 had T2.
            from models.card import cutover_notes, cutover_applications
            from tests.study_note_fixtures import archive_wire_alias
            pairs = [(n1, t1), (n2, t1), (n3, t1), (n1, t2)]
            applications = {row.template_id: row.application_id
                            for row in Card.query.filter_by(note_id=n1.id)}
            for note, template in pairs:
                card = Card.query.filter_by(note_id=note.id, template_id=template.id).one()
                archive_wire_alias(db.session, card, str(uuid4()))
            db.session.connection().execute(cutover_notes.insert(),
                [{"note_id": note.id} for note in (n1, n2, n3)])
            db.session.connection().execute(cutover_applications.insert(),
                [{"application_id": value} for value in applications.values()])
            db.session.commit()

        response = self.client.get(f"/api/note-types/{nt_id}/templates")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual(items[0]["id"], t1_id)
        self.assertEqual(items[0]["note_count"], 3)
        self.assertEqual(items[1]["id"], t2_id)
        self.assertEqual(items[1]["note_count"], 1)

    def test_template_without_cards_is_zero(self):
        with self.app.app_context():
            nt = NoteType(name="NT Zero", user_id=self.user_id)
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            t3 = attach_template(db.session, owner_user_id=self.user_id,
                note_type_id=nt_id,
                name="T3",
                front_html="{{Front}}",
                back_html="{{Front}}",
                position=0,
                is_default=True,
            )
            db.session.add(t3)
            db.session.commit()
            t3_id = t3.id

        response = self.client.get(f"/api/note-types/{nt_id}/templates")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertEqual(len(items), 1)
        self.assertEqual(items[0]["id"], t3_id)
        self.assertEqual(items[0]["note_count"], 0)

    def test_scoped_template_keys_preserve_values_and_expose_application_identity(self):
        with self.app.app_context():
            nt = NoteType(name="NT Keys", user_id=self.user_id)
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            t1 = attach_template(db.session, owner_user_id=self.user_id,
                note_type_id=nt_id,
                name="T1",
                front_html="<div>Front</div>",
                back_html="<div>Back</div>",
                shared_css=".card { font-size: 16px; }",
                position=0,
                is_default=True,
            )
            db.session.add(t1)
            db.session.commit()
            t1_id = t1.id

        response = self.client.get(f"/api/note-types/{nt_id}/templates")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        self.assertEqual(len(items), 1)
        item = items[0]

        expected_keys = {
            "id",
            "note_type_id",
            "name",
            "front_html",
            "back_html",
            "shared_css",
            "position",
            "is_default",
            "updated_at",
            "note_count",
            "current_version_id",
            "application_id",
        }
        self.assertEqual(set(item.keys()), expected_keys)
        self.assertEqual(item["id"], t1_id)
        self.assertEqual(item["note_type_id"], nt_id)
        self.assertEqual(item["name"], "T1")
        self.assertEqual(item["front_html"], "<div>Front</div>")
        self.assertEqual(item["back_html"], "<div>Back</div>")
        self.assertEqual(item["shared_css"], ".card { font-size: 16px; }")
        self.assertEqual(item["position"], 0)
        self.assertTrue(item["is_default"])
        self.assertIsInstance(item["current_version_id"], str)
        with self.app.app_context():
            from models.study_application import StudyApplication
            application = db.session.get(StudyApplication, item["application_id"])
            self.assertEqual((application.note_type_id, application.template_id), (nt_id, t1_id))

    def test_other_users_note_type_is_404(self):
        with self.app.app_context():
            other_user = create_note_user(db.session,
                username=f"other_{uuid4().hex[:8]}",
                email=f"other_{uuid4().hex[:8]}@example.com",
            )
            other_user.set_password("pass")
            db.session.add(other_user)
            db.session.flush()

            nt_other = NoteType(name="Other NT", user_id=other_user.id)
            db.session.add(nt_other)
            db.session.commit()
            other_nt_id = nt_other.id

        response = self.client.get(f"/api/note-types/{other_nt_id}/templates")
        self.assertEqual(response.status_code, 404)
        data = response.get_json()
        self.assertEqual(data.get("error"), "FIELD_NOT_FOUND")

    def test_detail_endpoint_has_no_note_count(self):
        with self.app.app_context():
            nt = NoteType(name="NT Detail", user_id=self.user_id)
            db.session.add(nt)
            db.session.flush()
            nt_id = nt.id

            t1 = attach_template(db.session, owner_user_id=self.user_id,
                note_type_id=nt_id,
                name="T1",
                front_html="{{Front}}",
                back_html="{{Front}}",
                position=0,
                is_default=True,
            )
            db.session.add(t1)
            db.session.commit()

        response = self.client.get(f"/api/note-types/{nt_id}")
        self.assertEqual(response.status_code, 200)
        data = response.get_json()
        self.assertTrue(data.get("templates"))
        for tpl in data["templates"]:
            self.assertNotIn("note_count", tpl)


if __name__ == "__main__":
    unittest.main()
