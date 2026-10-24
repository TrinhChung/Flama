"""Browse contract qualification in generated, disposable local MySQL schemas.

Enable with FLAMA_BROWSE_MYSQL_TESTS=1 and use scripts/run_tests.py --file.
The configured development schema is read only for its default collation.
"""

import os
from copy import deepcopy
from types import SimpleNamespace
import re
import secrets
import unittest
from unittest.mock import patch

import pymysql
from sqlalchemy import inspect

from app import create_audit_app
from app.settings import load_environment
from models import db
from models.deck import Deck
from models.note import Note
from app.services import browse_card_service
from scripts.mysql_probe_db import (
    _connection_settings,
    _database_uri,
    _source_database_collation,
)
from tests import test_browse_query_bounds as fixtures


_PROBE_NAME = re.compile(r"^flama_browse_contract_[0-9]+_[a-f0-9]{12}$")


@unittest.skipUnless(os.getenv("FLAMA_BROWSE_MYSQL_TESTS") == "1", "Opt-in local MySQL qualification")
class BrowseMySQLContractTests(fixtures.BrowseQueryBoundsTests):
    """Run existing query-bounds fixtures on MySQL plus effective-name regressions."""

    def setUp(self):
        load_environment()
        settings = _connection_settings()
        if settings["host"] not in {"localhost", "127.0.0.1", "::1"}:
            raise RuntimeError("Browse qualification requires loopback MySQL.")
        schema = f"flama_browse_contract_{os.getpid()}_{secrets.token_hex(6)}"
        if not _PROBE_NAME.fullmatch(schema) or schema == os.getenv("DB_NAME"):
            raise RuntimeError("Refusing a non-generated fixture schema.")
        admin = pymysql.connect(**settings)
        self.addCleanup(admin.close)
        collation = _source_database_collation(admin)
        with admin.cursor() as cursor:
            cursor.execute(
                "SELECT SCHEMA_NAME FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s", (schema,)
            )
            if cursor.fetchone():
                raise RuntimeError("Generated schema already exists; refusing reuse.")
            cursor.execute(f"CREATE DATABASE `{schema}` CHARACTER SET utf8mb4 COLLATE {collation}")

        def drop_generated_schema():
            if not _PROBE_NAME.fullmatch(schema) or schema == os.getenv("DB_NAME"):
                raise RuntimeError("Refusing non-fixture cleanup.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{schema}`")

        self.addCleanup(drop_generated_schema)
        self.app = create_audit_app({
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": _database_uri(settings, schema),
            "REDIS_URL": "",
            "DECK_COUNT_WRITE_ENABLED": False,
            "REVIEW_ANALYTICS_WRITE_ENABLED": False,
            "STUDY_NOTE_COUNT_ENABLED": False,
        })
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.engine.dispose)
        self.addCleanup(db.session.remove)
        if db.engine.url.database != schema or set(db.engines) != {None}:
            raise RuntimeError("Fixture ORM target escaped the generated schema.")
        if inspect(db.engine).get_table_names():
            raise RuntimeError("Fixture schema is not empty.")
        db.create_all()
        self.learner_id = fixtures.seed_learner()

    def _assert_display_name_order(self, *, release):
        fixtures.seed_owned_deck(self.learner_id, count=4)
        ids = fixtures.seed_clone_install(self.learner_id, count=6, release=release)
        db.session.get(Deck, ids["source_root_id"]).name = "A source root"
        db.session.get(Deck, ids["source_child_id"]).name = "Z source child"
        db.session.get(Deck, ids["local_root_id"]).name = "Z local root"
        db.session.get(Deck, ids["local_child_id"]).name = "A local child"
        db.session.commit()
        source_values = {row.id: row.field_values_by_id for row in Note.query.filter(Note.id.in_(ids["note_ids"]))}
        for direction, first_name in (("asc", "A local child"), ("desc", "Z local root")):
            with self.subTest(direction=direction, release=release):
                whole, _ = self._list(sort_by="deck", sort_dir=direction, per_page=100)
                self.assertEqual(whole["total"], 10)
                names = [row["deck_name"] for row in whole["items"]]
                self.assertEqual(names, sorted(names, reverse=direction == "desc"))
                first, _ = self._list(sort_by="deck", sort_dir=direction, per_page=1)
                self.assertEqual(first["items"][0]["deck_name"], first_name)
                paged = []
                for page in range(1, 5):
                    chunk, _ = self._list(sort_by="deck", sort_dir=direction, per_page=3, page=page)
                    paged.extend(row["card_id"] for row in chunk["items"])
                self.assertEqual(paged, [row["card_id"] for row in whole["items"]])
        self.assertEqual(
            {row.id: row.field_values_by_id for row in Note.query.filter(Note.id.in_(ids["note_ids"]))},
            source_values,
        )

    def test_release_clone_sorts_by_local_names_before_pagination(self):
        self._assert_display_name_order(release=True)

    def test_snapshot_clone_sorts_by_local_names_before_pagination(self):
        self._assert_display_name_order(release=False)

    def test_owned_decks_keep_name_order_without_clone_mapping(self):
        fixtures.seed_owned_deck(self.learner_id, count=6)
        for direction in ("asc", "desc"):
            page, _ = self._list(sort_by="deck", sort_dir=direction)
            names = [row["deck_name"] for row in page["items"]]
            self.assertEqual(names, sorted(names, reverse=direction == "desc"))

    def test_release_schema_deltas_and_native_arrays_preserve_source_values(self):
        from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
        from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
        from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
        from models.deck_install import DeckInstall
        from models.field_def import FieldDef

        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=True, override_every=0)
        install = db.session.get(DeckInstall, ids["install_id"])
        fields = {field.name: field.id for field in FieldDef.query.filter_by(note_type_id=install.source_note_type_id)}
        original_values = {row.id: deepcopy(row.field_values_by_id) for row in Note.query.filter(Note.id.in_(ids["note_ids"]))}
        db.session.add_all([
            DeckCloneFieldDefOverride(deck_install_id=install.id, source_field_def_id=fields["Word"], properties={"name": "LocalWord"}),
            DeckCloneFieldDefOverride(deck_install_id=install.id, source_field_def_id=fields["Reading"], is_disabled=True),
            DeckCloneFieldDefOverride(deck_install_id=install.id, source_field_def_id=fields["Meaning"], properties={"name": "Answers", "field_type": "array"}),
        ])
        added = DeckCloneAddedFieldDef(deck_install_id=install.id, name="Extra", field_type="array", position=3)
        db.session.add(added)
        db.session.flush()
        nested = [["first", "second"], "third"]
        for identity, label, value, source_id in (
            (fields["Word"], "LocalWord", "local-word", fields["Word"]),
            (fields["Meaning"], "Answers", nested, fields["Meaning"]),
            (f"added:{install.id}:{added.id}", "Extra", ["local-added"], None),
        ):
            db.session.add(DeckCloneNoteFieldOverride(
                deck_install_id=install.id, source_note_id=ids["note_ids"][0], source_field_def_id=source_id,
                base_release_id=install.applied_release_id, field_identity_key=identity,
                field_name=label, operation="set", value=value,
            ))
        db.session.add(DeckCloneNoteFieldOverride(
            deck_install_id=install.id, source_note_id=ids["note_ids"][1], source_field_def_id=fields["Word"],
            base_release_id=install.applied_release_id, field_identity_key=fields["Word"],
            field_name="LocalWord", operation="remove", value=None,
        ))
        db.session.commit()
        page, _ = self._list(deck_id=ids["local_root_id"])
        selected = next(row for row in page["items"] if row["note_id"] == ids["note_ids"][0])
        detail = browse_card_service.get_browse_card_detail(
            user_id=self.learner_id, admin_mode=False, timezone_name="UTC", card_id=selected["card_id"],
        )
        self.assertEqual(detail["note"]["field_values"]["LocalWord"], "local-word")
        self.assertEqual(detail["note"]["field_values"]["Answers"], nested)
        self.assertEqual(detail["note"]["field_values"]["Extra"], ["local-added"])
        self.assertNotIn("Reading", detail["note"]["field_values"])
        removed_row = next(row for row in page["items"] if row["note_id"] == ids["note_ids"][1])
        removed_detail = browse_card_service.get_browse_card_detail(
            user_id=self.learner_id, admin_mode=False, timezone_name="UTC", card_id=removed_row["card_id"],
        )
        self.assertNotIn("LocalWord", removed_detail["note"]["field_values"])
        for keyword, total in (("local-word", 1), ("local-added", 1), ("pinned-reading", 0)):
            searched, _ = self._list(deck_id=ids["local_root_id"], q=keyword)
            self.assertEqual(searched["total"], total)
        self.assertEqual(
            {row.id: row.field_values_by_id for row in Note.query.filter(Note.id.in_(ids["note_ids"]))}, original_values,
        )

    def test_note_preview_and_active_occurrence_contract(self):
        from models.note_type import NoteType
        from models.study_application import StudyApplication
        from tests.study_note_fixtures import attach_template

        root_id = fixtures.seed_owned_deck(self.learner_id, count=6)
        note_type_id = NoteType.query.filter_by(user_id=self.learner_id).one().id
        template = attach_template(db.session, note_type_id=note_type_id, owner_user_id=self.learner_id,
                                   name="Alternate", front_html="{{Word}}", back_html="{{Meaning}}", is_default=True)
        db.session.commit()
        application_id = StudyApplication.query.filter_by(template_id=template.id).one().id
        page, _ = self._list(deck_id=root_id)
        self.assertEqual(page["total"], 6)
        self.assertTrue(all(row["card_id"].endswith("." + application_id) for row in page["items"]))
        expanded, _ = self._list(deck_id=root_id, all_templates=1)
        self.assertEqual(expanded["total"], 12)
        db.session.get(StudyApplication, application_id).status_code = "RETIRED"
        db.session.commit()
        active, _ = self._list(deck_id=root_id, all_templates=1)
        self.assertEqual(active["total"], 6)
        self.assertFalse(any(row["card_id"].endswith("." + application_id) for row in active["items"]))

    def test_baseline_context_isolation_and_write_guard(self):
        from scripts.benchmark_browse_mysql import sample

        root_id = fixtures.seed_owned_deck(self.learner_id, count=6)
        options = SimpleNamespace(max_statement_ms=5000, lock_wait_seconds=2, as_of=fixtures.NOW, explain=False)
        case = {"name": "fixture", "user_id": self.learner_id, "query": {"deck_id": root_id}}
        first = sample(self.app, case, options)
        second = sample(self.app, case, options)
        self.assertNotIn("error_type", first)
        self.assertNotIn("error_type", second)
        self.assertEqual(first["payload_sha256"], second["payload_sha256"])
        self.assertEqual(first["returned"], 6)
        self.assertIn("count", first["phases"])
        self.assertIn("page_and_hydrate", first["phases"])
        self.assertIn("authority", first["phases"])
        with patch.object(browse_card_service, "list_browse_cards", side_effect=lambda **_kwargs:
                          db.session.connection().exec_driver_sql("UPDATE notes SET tags = JSON_ARRAY('forbidden')")):
            refused = sample(self.app, case, options)
        self.assertEqual(refused["error_type"], "RuntimeError")
        self.assertTrue(all(row.tags == [] for row in Note.query.filter_by(user_id=self.learner_id)))

    def test_owned_source_note_is_not_sorted_by_its_installed_copy_name(self):
        from models.deck_install import DeckInstall
        from models.user import User

        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=True, override_every=0)
        install = db.session.get(DeckInstall, ids["install_id"])
        publisher_id = install.source_owner_user_id
        install.source_owner_user_id = self.learner_id
        for note in Note.query.filter(Note.id.in_(ids["note_ids"])):
            note.user_id = self.learner_id
        db.session.get(Deck, ids["source_root_id"]).name = "A own source"
        db.session.get(Deck, ids["source_child_id"]).name = "Z own source"
        db.session.get(Deck, ids["local_root_id"]).name = "Z installed copy"
        db.session.get(Deck, ids["local_child_id"]).name = "A installed copy"
        self.assertIsNotNone(db.session.get(User, publisher_id))
        db.session.commit()
        for direction in ("asc", "desc"):
            page, _ = self._list(sort_by="deck", sort_dir=direction)
            names = [row["deck_name"] for row in page["items"]]
            self.assertEqual(set(names), {"A own source", "Z own source"})
            self.assertEqual(names, sorted(names, reverse=direction == "desc"))

    def test_historical_preview_keeps_missing_occurrence_absent(self):
        from sqlalchemy import insert
        from models.card import Card, cutover_applications, cutover_notes
        from models.note_type import NoteType
        from models.study_application import StudyApplication
        from tests.study_note_fixtures import archive_wire_alias, attach_template

        root_id = fixtures.seed_owned_deck(self.learner_id, count=6)
        note_type_id = NoteType.query.filter_by(user_id=self.learner_id).one().id
        original_application = StudyApplication.query.filter_by(note_type_id=note_type_id).one()
        original_application_id = original_application.id
        template = attach_template(db.session, note_type_id=note_type_id, owner_user_id=self.learner_id,
                                   name="Default", front_html="{{Word}}", back_html="{{Meaning}}", is_default=True)
        db.session.flush()
        default_id = StudyApplication.query.filter_by(template_id=template.id).one().id
        note_id = Note.query.filter_by(user_id=self.learner_id).order_by(Note.id).first().id
        original_card = Card.query.filter_by(note_id=note_id, application_id=original_application_id).one()
        archive_wire_alias(db.session, original_card, "aaaaaaaa-0000-0000-0000-000000000001")
        db.session.execute(insert(cutover_notes).values(note_id=note_id))
        db.session.execute(insert(cutover_applications), [
            {"application_id": original_application_id}, {"application_id": default_id},
        ])
        db.session.commit()
        page, _ = self._list(deck_id=root_id)
        historical = next(row for row in page["items"] if row["note_id"] == note_id)
        self.assertEqual(page["total"], 6)
        self.assertTrue(historical["card_id"].endswith("." + original_application_id))
        expanded, _ = self._list(deck_id=root_id, all_templates=1)
        self.assertEqual(expanded["total"], 11)
        db.session.get(StudyApplication, original_application_id).status_code = "RETIRED"
        db.session.commit()
        retired, _ = self._list(deck_id=root_id)
        self.assertEqual(retired["total"], 5)
        self.assertNotIn(note_id, {row["note_id"] for row in retired["items"]})


if __name__ == "__main__":
    unittest.main()
