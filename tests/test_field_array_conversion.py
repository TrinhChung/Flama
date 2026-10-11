"""Converting a NoteType field to or from array: preview source, atomic apply, restore."""

import unittest

from app import create_app
from models import db
from models.audit_log import AuditLog
from models.field_def import FieldDef
from models.field_rename_job import FieldRenameJob
from models.note import Note
from models.user import User


class FieldArrayConversionTests(unittest.TestCase):
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
            owner = User(username="owner", email="owner@example.com")
            owner.set_password("password")
            other = User(username="other", email="other@example.com")
            other.set_password("password")
            db.session.add_all([owner, other])
            db.session.commit()
            self.owner_id, self.other_id = owner.id, other.id
        self._login("owner@example.com")
        response = self.client.post("/api/note-types", json={
            "name": "Vocab",
            "field_defs": [
                {"name": "Word", "field_type": "text", "identity_role": "primary"},
                {"name": "Meaning", "field_type": "text"},
                {"name": "Usage", "field_type": "richtext"},
                {"name": "Picture", "field_type": "image"},
            ],
        })
        self.assertEqual(response.status_code, 201, response.get_json())
        self.note_type = response.get_json()
        self.fields = {field["name"]: field["id"] for field in self.note_type["field_defs"]}
        self.note_ids = []
        for word, meaning in (("食べる", "ăn, dùng bữa"), ("飲む", "uống"), ("行く", "")):
            created = self.client.post("/api/notes", json={
                "note_type_id": self.note_type["id"],
                "field_values": {"Word": word, "Meaning": meaning},
            })
            self.assertEqual(created.status_code, 201, created.get_json())
            self.note_ids.append(created.get_json()["id"])
        with self.app.app_context():
            # A Note another user added to an installed copy shares the NoteType.
            foreign = Note(user_id=self.other_id, note_type_id=self.note_type["id"], field_values={"Word": "見る", "Meaning": "nhìn, xem"})
            db.session.add(foreign)
            db.session.commit()
            self.foreign_note_id = foreign.id

    def tearDown(self):
        with self.app.app_context():
            db.session.rollback()
            db.session.remove()
            db.drop_all()

    def _login(self, email):
        self.client.post("/logout")
        self.client.post("/login", data={"email": email, "password": "password"})

    def _url(self, field="Meaning"):
        return f"/api/note-types/{self.note_type['id']}/fields/{self.fields[field]}/array-conversion"

    def _split(self, value):
        return "\n".join(part.strip() for part in value.split(",") if part.strip())

    def _payload(self, source, transform=None, target_type="array"):
        transform = transform or self._split
        return {
            "target_type": target_type,
            "expected_field_type": source["field"]["field_type"],
            "notes": [{"note_id": note["note_id"], "expected": note["value"], "value": transform(note["value"])} for note in source["notes"]],
        }

    def _meaning(self, note_id):
        with self.app.app_context():
            return db.session.get(Note, note_id).field_values.get("Meaning")

    def _field_type(self, field="Meaning"):
        with self.app.app_context():
            return db.session.get(FieldDef, self.fields[field]).field_type

    def test_source_lists_only_the_owner_notes(self):
        source = self.client.get(self._url()).get_json()
        self.assertTrue(source["convertible"])
        # Notes come in (created_at, id) order; Notes created in the same instant
        # tie on created_at, so compare by id rather than position.
        values = {note["note_id"]: note["value"] for note in source["notes"]}
        self.assertEqual(sorted(values), sorted(self.note_ids))
        self.assertNotIn(self.foreign_note_id, values)
        self.assertEqual(values[self.note_ids[0]], "ăn, dùng bữa")

    def test_conversion_applies_type_and_values_atomically(self):
        source = self.client.get(self._url()).get_json()
        response = self.client.post(self._url(), json=self._payload(source))
        self.assertEqual(response.status_code, 200, response.get_json())
        body = response.get_json()
        self.assertEqual(body["field"]["field_type"], "array")
        self.assertEqual((body["note_count"], body["changed_note_count"]), (3, 1))
        self.assertEqual(self._field_type(), "array")
        self.assertEqual(self._meaning(self.note_ids[0]), "ăn\ndùng bữa")
        self.assertEqual(self._meaning(self.note_ids[1]), "uống")
        self.assertEqual(self._meaning(self.foreign_note_id), "nhìn, xem")
        with self.app.app_context():
            self.assertEqual(AuditLog.query.filter_by(action="field.convert_array").count(), 1)

    def test_any_change_since_the_preview_writes_nothing(self):
        source = self.client.get(self._url()).get_json()
        missing = self._payload(source)
        missing["notes"] = missing["notes"][1:]
        stale = self._payload(source)
        stale["notes"][1]["expected"] = "khác"
        foreign = self._payload(source)
        foreign["notes"].append({"note_id": self.foreign_note_id, "expected": "nhìn, xem", "value": "nhìn"})
        for payload in (missing, stale, foreign):
            response = self.client.post(self._url(), json=payload)
            self.assertEqual(response.status_code, 409, response.get_json())
            self.assertEqual(response.get_json()["error"], "NOTES_CHANGED")
        self.assertEqual(response.get_json()["details"]["extra_count"], 1)
        self.assertEqual(self._field_type(), "text")
        self.assertEqual(self._meaning(self.note_ids[0]), "ăn, dùng bữa")

    def test_array_values_must_be_clean_lines(self):
        source = self.client.get(self._url()).get_json()
        for bad in ("ăn\n\ndùng bữa", " ăn", "<b>ăn</b>", "ăn\r\nuống"):
            payload = self._payload(source, transform=lambda value, bad=bad: bad if value.startswith("ăn") else value)
            response = self.client.post(self._url(), json=payload)
            self.assertEqual(response.status_code, 400, (bad, response.get_json()))
            self.assertEqual(response.get_json()["error"], "INVALID_ARRAY_VALUE")
        self.assertEqual(self._field_type(), "text")

    def test_repeated_array_items_survive_conversion_and_note_edit(self):
        source = self.client.get(self._url()).get_json()
        repeated = "xử lý đồng thời\nkhác\nxử lý đồng thời"
        payload = self._payload(source, transform=lambda value: repeated if value.startswith("ăn") else value)
        response = self.client.post(self._url(), json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._meaning(self.note_ids[0]), repeated)
        response = self.client.patch(f"/api/notes/{self.note_ids[0]}", json={"field_values": {"Word": "食べる", "Meaning": repeated}})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._meaning(self.note_ids[0]), repeated)

    def test_primary_media_and_changed_fields_are_refused(self):
        word = self.client.get(self._url("Word")).get_json()
        self.assertEqual((word["convertible"], word["blocked_reason"]), (False, "PRIMARY_FIELD"))
        self.assertEqual(self.client.post(self._url("Word"), json=self._payload(word)).status_code, 409)
        picture = self.client.get(self._url("Picture")).get_json()
        self.assertEqual(picture["blocked_reason"], "UNSUPPORTED_FIELD_TYPE")
        source = self.client.get(self._url()).get_json()
        payload = self._payload(source)
        payload["expected_field_type"] = "markdown"
        response = self.client.post(self._url(), json=payload)
        self.assertEqual((response.status_code, response.get_json()["error"]), (409, "FIELD_CHANGED"))

    def test_invalid_direction_and_body_are_rejected(self):
        source = self.client.get(self._url()).get_json()
        same = self._payload(source, target_type="text")
        self.assertEqual(self.client.post(self._url(), json=same).status_code, 400)
        self.assertEqual(self.client.post(self._url(), json={"target_type": "array"}).status_code, 400)
        duplicated = self._payload(source)
        duplicated["notes"].append(duplicated["notes"][0])
        self.assertEqual(self.client.post(self._url(), json=duplicated).status_code, 400)

    def test_rename_in_progress_blocks_the_conversion(self):
        with self.app.app_context():
            db.session.add(FieldRenameJob(note_type_id=self.note_type["id"], user_id=self.owner_id, field_def_id=self.fields["Meaning"], old_name="Meaning", new_name="Meaning2", status="pending"))
            db.session.commit()
        source = self.client.get(self._url()).get_json()
        response = self.client.post(self._url(), json=self._payload(source))
        self.assertEqual((response.status_code, response.get_json()["error"]), (409, "FIELD_RENAME_IN_PROGRESS"))

    def test_restore_from_backup_returns_the_original_type_and_values(self):
        before = self.client.get(self._url()).get_json()
        self.assertEqual(self.client.post(self._url(), json=self._payload(before)).status_code, 200)
        backup = {note["note_id"]: note["value"] for note in before["notes"]}
        converted = self.client.get(self._url()).get_json()
        response = self.client.post(self._url(), json=self._payload(
            converted, transform=None, target_type="text",
        ) | {"notes": [
            {"note_id": note["note_id"], "expected": note["value"], "value": backup[note["note_id"]]}
            for note in converted["notes"]
        ]})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._field_type(), "text")
        self.assertEqual(self._meaning(self.note_ids[0]), "ăn, dùng bữa")

    def test_restore_to_richtext_goes_through_the_richtext_sanitizer(self):
        source = self.client.get(self._url("Usage")).get_json()
        self.assertEqual(self.client.post(self._url("Usage"), json=self._payload(source, transform=lambda value: value)).status_code, 200)
        converted = self.client.get(self._url("Usage")).get_json()
        payload = self._payload(converted, target_type="richtext")
        payload["notes"][0]["value"] = '<b onclick="x()">ăn</b><script>alert(1)</script>'
        response = self.client.post(self._url("Usage"), json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        with self.app.app_context():
            stored = db.session.get(Note, self.note_ids[0]).field_values.get("Usage", "")
        self.assertNotIn("script", stored)
        self.assertNotIn("onclick", stored)

    def test_other_users_cannot_read_or_convert(self):
        self._login("other@example.com")
        self.assertEqual(self.client.get(self._url()).status_code, 404)
        self.assertEqual(self.client.post(self._url(), json={"target_type": "array", "expected_field_type": "text", "notes": []}).status_code, 404)


if __name__ == "__main__":
    unittest.main()
