"""Converting a NoteType field to or from array: preview source, atomic apply, restore."""

import unittest

from app import create_app
from models import db
from models.audit_log import AuditLog
from models.field_def import FieldDef
from models.note import Note
from models.user import User
from tests.study_note_fixtures import create_note_user


class FieldArrayConversionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "WTF_CSRF_ENABLED": False,
            "STARTUP_RUN_MAINTENANCE": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False,
            "ENABLE_FIELD_ARRAY_CONVERSION_API": True,
        })

    def setUp(self):
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            owner = create_note_user(db.session, username="owner", email="owner@example.com")
            owner.set_password("password")
            other = create_note_user(db.session, username="other", email="other@example.com")
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
        # Every value changes storage from text to a list, so every Note is rewritten.
        self.assertEqual((body["note_count"], body["changed_note_count"]), (3, 3))
        self.assertEqual(self._field_type(), "array")
        self.assertEqual(self._meaning(self.note_ids[0]), ["ăn", "dùng bữa"])
        self.assertEqual(self._meaning(self.note_ids[1]), ["uống"])
        self.assertEqual(self._meaning(self.note_ids[2]), [])
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
        for bad in ("ăn\n\ndùng bữa", " ăn", "<script>alert(1)</script>", "ăn\r\nuống"):
            payload = self._payload(source, transform=lambda value, bad=bad: bad if value.startswith("ăn") else value)
            response = self.client.post(self._url(), json=payload)
            self.assertEqual(response.status_code, 400, (bad, response.get_json()))
            self.assertEqual(response.get_json()["error"], "INVALID_ARRAY_VALUE")
        # Safe rich-text HTML lines like <b> are allowed
        safe_payload = self._payload(source, transform=lambda value: "<b>ăn</b>" if value.startswith("ăn") else value)
        safe_response = self.client.post(self._url(), json=safe_payload)
        self.assertEqual(safe_response.status_code, 200, safe_response.get_json())
        self.assertEqual(self._meaning(self.note_ids[0]), ["<b>ăn</b>"])
        self.assertEqual(self._field_type(), "array")

    def test_array_note_edit_preserves_native_lists_and_rejects_text(self):
        source = self.client.get(self._url()).get_json()
        self.assertEqual(self.client.post(self._url(), json=self._payload(source)).status_code, 200)
        url = f"/api/notes/{self.note_ids[0]}"
        # Direct writes preserve native lists; import/conversion handles text.
        for sent, stored in ((['["a", "b"]'], ['["a", "b"]']), ([[["three"]]], [[["three"]]]), ([["a", "b"], ["c"]], [["a", "b"], ["c"]])):
            response = self.client.patch(url, json={"field_values": {"Word": "食べる", "Meaning": sent}})
            self.assertEqual(response.status_code, 200, response.get_json())
            self.assertEqual(self._meaning(self.note_ids[0]), stored)
        response = self.client.patch(url, json={"field_values": {"Word": "食べる2"}})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._meaning(self.note_ids[0]), [["a", "b"], ["c"]])
        for bad in ('["a", "b"]', 'a\nb', ["a", {"b": 1}], [[[["four levels"]]]], ["x" * 3000, "y" * 3000], [""] * 6000):
            response = self.client.patch(url, json={"field_values": {"Word": "食べる", "Meaning": bad}})
            self.assertEqual(response.status_code, 400, (bad, response.get_json()))
        self.assertEqual(self._meaning(self.note_ids[0]), [["a", "b"], ["c"]])

    def test_repeated_array_items_survive_conversion_and_note_edit(self):
        source = self.client.get(self._url()).get_json()
        repeated = "xử lý đồng thời\nkhác\nxử lý đồng thời"
        expected_array = ["xử lý đồng thời", "khác", "xử lý đồng thời"]
        payload = self._payload(source, transform=lambda value: repeated if value.startswith("ăn") else value)
        response = self.client.post(self._url(), json=payload)
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._meaning(self.note_ids[0]), expected_array)
        response = self.client.patch(f"/api/notes/{self.note_ids[0]}", json={"field_values": {"Word": "食べる", "Meaning": expected_array}})
        self.assertEqual(response.status_code, 200, response.get_json())
        self.assertEqual(self._meaning(self.note_ids[0]), expected_array)

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

    def test_schema_rename_keeps_values_and_does_not_require_a_rewrite_job(self):
        with self.app.app_context():
            before = {note.id: dict(note.field_values_by_id) for note in Note.query.all()}
            db.session.get(FieldDef, self.fields["Meaning"]).name = "Meaning2"
            db.session.commit()
            after = {note.id: dict(note.field_values_by_id) for note in Note.query.all()}
            self.assertEqual(before, after)
        source = self.client.get(self._url()).get_json()
        self.assertEqual(source["field"]["name"], "Meaning2")
        response = self.client.post(self._url(), json=self._payload(source))
        self.assertEqual(response.status_code, 200, response.get_json())

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

    def test_note_api_revisions_fence_stale_edits_and_renamed_raw_labels(self):
        url = f"/api/notes/{self.note_ids[0]}"
        original = self.client.get(url).get_json()
        self.assertIn("content_revision", original)
        self.assertIn("field_schema_revision", original)
        current = self.client.patch(url, json={"field_values": {"Meaning": "updated"},
            "expected_content_revision": original["content_revision"],
            "expected_field_schema_revision": original["field_schema_revision"]})
        self.assertEqual(current.status_code, 200, current.get_json())
        self.assertGreater(current.get_json()["content_revision"], original["content_revision"])
        stale = self.client.patch(url, json={"field_values": {"Meaning": "stale"},
            "expected_content_revision": original["content_revision"]})
        self.assertEqual(stale.status_code, 409, stale.get_json())
        with self.app.app_context():
            db.session.get(FieldDef, self.fields["Meaning"]).name = "Meaning2"
            db.session.commit()
        renamed = self.client.patch(url, json={"field_values": {"Meaning": "obsolete label"}})
        self.assertEqual(renamed.status_code, 409, renamed.get_json())
        latest = self.client.get(url).get_json()
        self.assertEqual(latest["field_values"]["Meaning2"], "updated")

    def test_conversion_disallowed_when_flag_disabled(self):
        try:
            self.app.config["ENABLE_FIELD_ARRAY_CONVERSION_API"] = False
            get_resp = self.client.get(self._url())
            self.assertEqual(get_resp.status_code, 403, get_resp.get_json())
            self.assertEqual(get_resp.get_json().get("error"), "CONVERSION_DISALLOWED")

            post_resp = self.client.post(self._url(), json={"notes": []})
            self.assertEqual(post_resp.status_code, 403, post_resp.get_json())
            self.assertEqual(post_resp.get_json().get("error"), "CONVERSION_DISALLOWED")
        finally:
            self.app.config["ENABLE_FIELD_ARRAY_CONVERSION_API"] = True


if __name__ == "__main__":
    unittest.main()

