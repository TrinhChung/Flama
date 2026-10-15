"""Canonical Field ID value, revision and transaction contracts."""
import unittest

from sqlalchemy import event, inspect, select, text, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app import create_app
from app.repositories.field_value_identity_repository import insert_field_definition
from app.services.field_value_identity_service import (
    FIELD_VALUE_CODEC, FieldIdentityError, FieldIdentityConflict,
    capture_field_schema, encode_named_values, project_named_values, typed_value_equal,
)
from models import db
from models.field_def import FieldDef
from models.field_value_identity_definition import FieldValueIdentityDefinition
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from tests.study_note_fixtures import create_note_user


class FieldIdentityCodecTests(unittest.TestCase):
    def schema(self, fields=None):
        return capture_field_schema("type", 7, fields or [
            dict(id="id-a", name="A.b", note_type_id="type"),
            dict(id="id-b", name="00000000-0000-0000-0000-000000000000", note_type_id="type"),
            dict(id="id-c", name="Missing", note_type_id="type"),
        ])

    def test_typed_roundtrip_presence_extras_nested_arrays_and_uuid_labels(self):
        values = {"A.b": ["", "duplicate", "duplicate", [None, False, 1, 1.0, ["猫"]]],
            "00000000-0000-0000-0000-000000000000": None, "extra": [], "orphan": {"nested": None}}
        encoded = encode_named_values(self.schema(), values)
        self.assertNotIn("id-c", encoded.by_id)
        self.assertIsNone(encoded.by_id["id-b"])
        self.assertEqual(encoded.extras, {"extra": [], "orphan": {"nested": None}})
        projected = project_named_values(self.schema(), encoded.by_id, encoded.extras, encoded.codec)
        self.assertTrue(typed_value_equal(values, projected))
        encoded.by_id["id-a"].append("mutation")
        self.assertNotIn("mutation", values["A.b"])

    def test_fail_closed_duplicate_scope_unknown_codec_id_and_extra_collision(self):
        for fields in ([dict(id="a", name="Name", note_type_id="type"), dict(id="b", name="Name", note_type_id="type")],
                       [dict(id="a", name="A", note_type_id="other")],
                       [dict(id="a", name="A", note_type_id="type"), dict(id="a", name="B", note_type_id="type")]):
            with self.assertRaises(FieldIdentityError):
                self.schema(fields)
        for by_id, extras, codec in (({}, {}, "unknown"), ({"foreign": "value"}, {}, FIELD_VALUE_CODEC),
            ({"id-a": "x"}, {"A.b": "x"}, FIELD_VALUE_CODEC)):
            with self.assertRaises(FieldIdentityError):
                project_named_values(self.schema(), by_id, extras, codec)
        for value in (("tuple",), float("nan"), {1: "key"}):
            with self.assertRaises(FieldIdentityError):
                encode_named_values(self.schema(), {"A.b": value})
        self.assertFalse(typed_value_equal({"x": True}, {"x": 1}))
        self.assertFalse(typed_value_equal({}, {"x": None}))


class FieldIdentityPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False}, audit_mode=True)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = create_note_user(db.session, username="identity", email="identity@example.com")
        self.note_type = NoteType(user_id=self.user.id, name="Identity")
        db.session.add(self.note_type)
        db.session.flush()
        self.field = FieldDef(note_type_id=self.note_type.id, name="Word", field_type="array")
        db.session.add(self.field)
        db.session.flush()
        self.note = Note(user_id=self.user.id, note_type_id=self.note_type.id,
            field_values={"Word": ["duplicate", ["猫", None], "duplicate"], "extra": {"nested": []}})
        db.session.add(self.note)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def test_one_live_store_without_flag_or_rename_job_table(self):
        self.assertNotIn("field_values", Note.__table__.c)
        self.assertNotIn("field_rename_jobs", db.metadata.tables)
        self.assertNotIn("FIELD_VALUE_IDENTITY_WRITE_ENABLED", self.app.config)
        self.assertEqual(self.note.field_values_codec, FIELD_VALUE_CODEC)
        self.note.field_values = {"Word": [], "extra": None}
        db.session.commit()
        self.assertEqual(self.note.field_values_by_id, {self.field.id: []})
        self.assertEqual(self.note.field_values_extras, {"extra": None})

    def test_owned_batch_reads_share_schema_and_do_not_lookup_clone_per_note(self):
        type_id, user_id = self.note_type.id, self.user.id
        db.session.add_all([Note(user_id=user_id, note_type_id=type_id,
            field_values={"Word": [str(number)]}) for number in range(40)])
        db.session.commit()
        db.session.remove()
        statements = []
        def capture(_connection, _cursor, statement, _params, _context, _many):
            statements.append(statement.lower())
        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            notes = db.session.execute(select(Note).where(Note.note_type_id == type_id)).scalars().all()
            self.assertEqual(len(notes), 41)
            self.assertTrue(all("Word" in note.field_values for note in notes))
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertLessEqual(sum("from note_types" in query for query in statements), 1)
        self.assertLessEqual(sum("from field_defs" in query for query in statements), 1)
        self.assertLessEqual(sum("from note_type_installs" in query for query in statements), 1)
        self.assertFalse(any("from deck_clone_added_notes" in query for query in statements))

    def test_schema_rename_is_metadata_only_and_raw_types_survive(self):
        raw = self.note.field_values_by_id
        version = self.note.content_revision
        statements = []
        def capture(_connection, _cursor, statement, _params, _context, _many):
            statements.append(statement.lower())
        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            self.field.name = "New.Word"
            db.session.commit()
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(self.note.field_values_by_id, raw)
        self.assertEqual(self.note.content_revision, version)
        self.assertEqual(self.note.field_values["New.Word"], ["duplicate", ["猫", None], "duplicate"])
        self.assertNotIn("Word", self.note.field_values)
        self.assertFalse(any("from notes" in sql or "update notes" in sql for sql in statements))

    def test_retired_id_is_preserved_and_same_name_replacement_does_not_inherit_value(self):
        retired_id = self.field.id
        db.session.delete(self.field)
        db.session.commit()
        replacement = FieldDef(note_type_id=self.note_type.id, name="Word", field_type="array")
        db.session.add(replacement)
        db.session.commit()
        self.assertNotIn("Word", self.note.field_values)
        self.note.field_values = {"Word": ["stale replacement"]}
        with self.assertRaises(FieldIdentityConflict):
            db.session.flush()
        db.session.rollback()
        from app.services.note_value_precondition_service import check_note_write_preconditions
        check_note_write_preconditions(self.note, {"expected_field_schema_revision": self.note_type.field_schema_revision})
        self.note.field_values = {"Word": ["replacement"], "extra": {"nested": []}}
        db.session.commit()
        self.assertEqual(self.note.field_values_by_id[retired_id], ["duplicate", ["猫", None], "duplicate"])
        self.assertEqual(self.note.field_values_by_id[replacement.id], ["replacement"])
        self.assertTrue(db.session.get(FieldValueIdentityDefinition, retired_id).is_retired)

    def test_stale_named_label_cannot_become_an_orphan_after_rename(self):
        self.field.name = "New.Word"
        db.session.commit()
        self.note.field_values = {"Word": ["stale"]}
        with self.assertRaises(FieldIdentityConflict):
            db.session.flush()
        db.session.rollback()
        self.assertIn("New.Word", self.note.field_values)
        self.assertNotIn("Word", self.note.field_values_extras)

    def test_undeclared_collision_retains_both_values_and_requires_explicit_disposition(self):
        self.note.field_values = {"Word": ["kept"], "Future": "undeclared"}
        db.session.commit()
        future = FieldDef(note_type_id=self.note_type.id, name="Future", field_type="text")
        db.session.add(future)
        db.session.commit()
        with self.assertRaises(FieldIdentityError):
            _ = self.note.field_values
        self.note.field_values_by_id = dict(self.note.field_values_by_id, **{future.id: "declared"})
        db.session.commit()
        with self.assertRaises(FieldIdentityError):
            _ = self.note.field_values
        self.assertEqual(self.note.field_values_extras["Future"], "undeclared")
        self.assertEqual(self.note.field_values_by_id[future.id], "declared")

    def test_new_schema_note_and_media_in_one_flush(self):
        parent = NoteType(user_id=self.user.id, name="Single flush")
        field = FieldDef(note_type=parent, name="Text", field_type="text")
        note = Note(note_type=parent, user_id=self.user.id, field_values={"Text": None})
        asset = MediaAsset(note=note, field_name="Text", filename="a", mime_type="text/plain",
            storage_path="a", sha256="a" * 64, size_bytes=1)
        db.session.add_all([parent, field, note, asset])
        db.session.commit()
        self.assertEqual(note.field_values_by_id, {field.id: None})
        self.assertEqual(asset.field_identity_key, field.id)

    def test_foreign_ids_and_media_refs_are_rejected(self):
        self.note.field_values_by_id = dict(self.note.field_values_by_id, foreign="lost")
        with self.assertRaises(FieldIdentityError):
            db.session.flush()
        db.session.rollback()
        asset = MediaAsset(note_id=self.note.id, field_name="Word", field_identity_key="foreign",
            filename="a", mime_type="text/plain", storage_path="a", sha256="a" * 64)
        db.session.add(asset)
        with self.assertRaises(FieldIdentityError):
            db.session.flush()

    def test_note_cas_rejects_lost_content_update(self):
        sessions = [Session(db.engine, expire_on_commit=False) for _ in range(2)]
        try:
            first, second = [session.get(Note, self.note.id) for session in sessions]
            first.field_values = {"Word": ["first"]}
            second.field_values = {"Word": ["second"]}
            sessions[0].commit()
            with self.assertRaises(StaleDataError):
                sessions[1].commit()
            sessions[1].rollback()
        finally:
            for session in sessions:
                session.close()
        db.session.expire_all()
        self.assertEqual(self.note.field_values["Word"], ["first"])

    def test_schema_fence_rejects_edit_captured_before_concurrent_rename(self):
        with Session(db.engine, expire_on_commit=False) as editor:
            note = editor.get(Note, self.note.id)
            note.field_values = {"Word": ["stale"]}
            self.field.name = "Renamed"
            db.session.commit()
            with self.assertRaises(FieldIdentityConflict):
                editor.flush()
            editor.rollback()
        self.assertEqual(self.note.field_values["Renamed"], ["duplicate", ["猫", None], "duplicate"])

    def test_savepoint_rollback_discards_pending_names_and_id_writes(self):
        before = self.note.field_values
        with self.assertRaisesRegex(RuntimeError, "abort"):
            with db.session.begin_nested():
                self.note.field_values = {"Word": ["nested"]}
                db.session.flush()
                raise RuntimeError("abort")
        self.assertEqual(self.note.field_values, before)
        self.note.field_values = {"Word": ["outer"]}
        db.session.commit()
        self.assertEqual(self.note.field_values["Word"], ["outer"])

    def test_core_schema_adapter_uses_canonical_ledger_and_transaction(self):
        revision = self.note_type.field_schema_revision
        insert_field_definition(db.session, id="scoped-core", note_type_id=self.note_type.id,
            name="Core", field_type="text", position=1, required=False)
        db.session.flush()
        self.assertIsNotNone(db.session.get(FieldValueIdentityDefinition, "scoped-core"))
        db.session.rollback()
        self.assertIsNone(db.session.get(FieldDef, "scoped-core"))
        self.assertEqual(self.note_type.field_schema_revision, revision)

    def test_schema_and_ledger_history_roll_back_together(self):
        revision = self.note_type.field_schema_revision
        self.field.name = "Temporary"
        db.session.flush()
        self.assertEqual(self.note_type.field_schema_revision, revision + 1)
        db.session.rollback()
        self.assertEqual(self.field.name, "Word")
        self.assertEqual(self.note_type.field_schema_revision, revision)
        self.assertNotIn("Temporary", db.session.get(FieldValueIdentityDefinition, self.field.id).label_history)

    def test_bulk_id_writes_require_scoped_adapter(self):
        with self.assertRaises(FieldIdentityError):
            db.session.execute(update(Note).where(Note.id == self.note.id).values(field_values_by_id={}))

    def test_parameter_bulk_and_raw_session_writes_cannot_bypass_codec_and_cas(self):
        with self.assertRaises(FieldIdentityError):
            db.session.execute(update(Note), [{"id": self.note.id,
                "content_revision": self.note.content_revision, "field_values_by_id": {"foreign": "bad"}}])
        with self.assertRaises(FieldIdentityError):
            db.session.execute(text("UPDATE notes SET field_values_by_id='{}' WHERE id=:id"), {"id": self.note.id})
        self.assertIn(self.field.id, self.note.field_values_by_id)


if __name__ == "__main__":
    unittest.main()
