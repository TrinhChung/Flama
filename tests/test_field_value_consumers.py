"""Consumer behavior after live field-name storage and rename jobs retire."""
import json
import unittest
from types import SimpleNamespace

from sqlalchemy import event, select
from sqlalchemy.dialects import mysql

from app import create_app
from app.repositories import connect_identity_repository
from app.repositories.browse_card_repository import owned_note_word_expression
from app.repositories.field_value_query_repository import note_values_search_condition
from app.repositories.media_field_identity_repository import find_note_field_media
from app.services.note_value_precondition_service import check_note_write_preconditions
from app.validators import RequestValidationError, escape_like_pattern
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from tests.study_note_fixtures import create_note_user


class FieldValueConsumerTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_CHECK_DB_CONNECTIVITY": False}, audit_mode=True)
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        self.user = create_note_user(db.session, username="consumer", email="consumer@example.com")
        self.type = NoteType(user_id=self.user.id, name="Value consumers")
        db.session.add(self.type)
        db.session.flush()
        self.field = FieldDef(note_type_id=self.type.id, name="Word.a", field_type="array", position=0)
        self.identity = FieldDef(note_type_id=self.type.id, name="Identity", field_type="text", position=1)
        self.deck = Deck(owner_user_id=self.user.id, note_type_id=self.type.id, name="Consumer deck")
        db.session.add_all([self.field, self.identity, self.deck])
        db.session.flush()
        self.note = Note(user_id=self.user.id, note_type_id=self.type.id, deck_id=self.deck.id,
            field_values={"Word.a": ["Café", ["猫", "100%"]], "Identity": "猫", "extra-label": "extra-value"})
        db.session.add(self.note)
        db.session.commit()

    def tearDown(self):
        db.session.rollback()
        db.session.remove()
        db.drop_all()
        self.context.pop()

    def _matches(self, value):
        return Note.query.filter(note_values_search_condition(
            keyword_like="%" + escape_like_pattern(value.lower()) + "%")).count()

    def _media(self):
        asset = MediaAsset(note_id=self.note.id, field_name=self.field.name,
            filename="image.webp", storage_path="image.webp", mime_type="image/webp",
            sha256="a" * 64, size_bytes=10)
        db.session.add(asset)
        db.session.commit()
        return asset

    def test_search_matches_nested_unicode_and_literal_wildcards_but_not_keys(self):
        for value in ("café", "猫", "100%", "extra-value"):
            self.assertEqual(self._matches(value), 1, value)
        for value in (self.field.id, self.identity.id, "Word.a", "extra-label", "100_"):
            self.assertEqual(self._matches(value), 0, value)

    def test_search_retains_nested_legacy_numeric_boolean_values_without_matching_object_keys(self):
        values = dict(self.note.field_values)
        values["retained-object"] = {"42-only-key": [7, [False, 3.25]], "uuid-key": "ordinary"}
        self.note.field_values = values
        db.session.commit()
        for value in ("7", "false", "3.25"):
            self.assertEqual(self._matches(value), 1, value)
        for value in ("42-only-key", "uuid-key"):
            self.assertEqual(self._matches(value), 0, value)

    def test_rename_changes_labels_without_note_reads_or_note_updates(self):
        raw = json.dumps(self.note.field_values_by_id, sort_keys=True)
        statements = []
        def capture(_connection, _cursor, statement, _parameters, _context, _many):
            statements.append(statement.lower())
        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            self.field.name = "Renamed.a"
            db.session.commit()
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(raw, json.dumps(self.note.field_values_by_id, sort_keys=True))
        self.assertEqual(self.note.field_values["Renamed.a"], ["Café", ["猫", "100%"]])
        self.assertNotIn("Word.a", self.note.field_values)
        self.assertFalse(any("update notes " in sql or "from notes " in sql for sql in statements), statements)
        self.assertEqual(self._matches("猫"), 1)
        self.assertIn("Caf", db.session.execute(select(owned_note_word_expression()).select_from(Note)).scalar_one())

    def test_deleted_field_stays_retained_but_hidden_from_current_search_and_same_name_replacement(self):
        retired_id = self.field.id
        db.session.delete(self.field)
        db.session.commit()
        replacement = FieldDef(note_type_id=self.type.id, name="Word.a", field_type="array")
        db.session.add(replacement)
        db.session.commit()
        self.assertIn(retired_id, self.note.field_values_by_id)
        self.assertNotIn("Word.a", self.note.field_values)
        self.assertEqual(self._matches("café"), 0)

    def test_connect_identity_query_projects_current_label_and_raw_json_type(self):
        rows = connect_identity_repository.local_identity_rows(user_id=self.user.id,
            deck_id=self.deck.id, field_name="Word.a")
        self.assertEqual(rows[0].identity_value, ["Café", ["猫", "100%"]])
        self.field.name = "Renamed.a"
        db.session.commit()
        rows = connect_identity_repository.local_identity_rows(user_id=self.user.id,
            deck_id=self.deck.id, field_name="Renamed.a")
        self.assertEqual(rows[0].identity_value, ["Café", ["猫", "100%"]])

    def test_media_deduplicates_after_rename_without_reusing_retired_identity(self):
        asset = self._media()
        self.field.name = "Renamed.a"
        db.session.commit()
        self.assertEqual(asset.field_name, "Renamed.a")
        self.assertEqual(find_note_field_media(note_id=self.note.id, field_name="Renamed.a",
            sha256=asset.sha256).id, asset.id)
        db.session.delete(self.field)
        db.session.commit()
        replacement = FieldDef(note_type_id=self.type.id, name="Renamed.a", field_type="image")
        db.session.add(replacement)
        db.session.commit()
        self.assertIsNone(find_note_field_media(note_id=self.note.id, field_name="Renamed.a", sha256=asset.sha256))

    def test_public_preconditions_reject_stale_note_and_schema_versions(self):
        version = self.note.content_revision
        schema = self.type.field_schema_revision
        check_note_write_preconditions(self.note, {"expected_content_revision": version,
            "expected_field_schema_revision": schema})
        for payload in ({"expected_content_revision": version + 1},
                        {"expected_field_schema_revision": schema + 1}):
            with self.assertRaises(RequestValidationError) as failure:
                check_note_write_preconditions(self.note, payload)
            self.assertEqual(failure.exception.status, 409)
        for bad in (-1, "0", False):
            with self.assertRaises(RequestValidationError):
                check_note_write_preconditions(self.note, {"expected_content_revision": bad})

    def test_captured_media_label_render_and_content_fingerprint_survive_live_source_rename(self):
        from app.services.flashcard_renderer import render_template_pair
        from app.services.media_field_codec import build_media_reference_lookup, media_field_label_for_schema
        from app.services.study_artifact_service import EffectiveStudyCard, build_content_artifact, content_version
        asset = self._media()
        captured_fields = [SimpleNamespace(id=self.field.id, name="Word.a", field_type="image",
            required=False, position=0)]
        captured_values = {"Word.a": f"/media/proxy/{asset.id}"}
        template = SimpleNamespace(id="captured-template", front_html="{{{Word.a}}}", back_html="",
            shared_css="", input_bindings={}, input_schema=[])
        context = EffectiveStudyCard(card=SimpleNamespace(id="captured-card"), note=self.note,
            template=template, field_defs=captured_fields, field_values=captured_values)
        before = content_version(context)
        before_render = render_template_pair(template=template, field_defs=captured_fields,
            field_values=captured_values, media_assets=[asset])["front_html"]
        self.field.name = "Renamed.a"
        db.session.commit()
        self.assertEqual(asset.field_name, "Renamed.a")
        self.assertEqual(media_field_label_for_schema(asset, captured_fields), "Word.a")
        self.assertEqual(content_version(context), before)
        artifact = build_content_artifact(context)
        self.assertEqual(artifact["media"][0]["field_name"], "Word.a")
        self.assertEqual(artifact["media"][0]["proxy_url"], f"/store/{asset.id}")
        after_render = render_template_pair(template=template, field_defs=captured_fields,
            field_values=captured_values, media_assets=[asset])["front_html"]
        self.assertEqual(before_render, after_render)
        self.assertEqual(build_media_reference_lookup([asset])[asset.id].url, f"/store/{asset.id}")

    def test_mysql_search_compilation_reads_values_without_named_live_column(self):
        sql = str(select(Note.id).where(note_values_search_condition(keyword_like="%cat%")).compile(
            dialect=mysql.dialect()))
        self.assertIn("JSON_SEARCH", sql)
        self.assertIn("field_values_by_id", sql)
        self.assertNotIn("notes.field_values,", sql)
        self.assertNotIn("notes.field_values ", sql)
