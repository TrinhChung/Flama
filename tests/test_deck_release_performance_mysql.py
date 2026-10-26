"""Opt-in local MySQL release regressions, using rollback-only outer transactions.

FLAMA_MYSQL_TESTS=1 runs against the existing loopback .env schema. No DDL is
performed. Service commits release SAVEPOINTs; cleanup rolls back the outer
connection transaction, including all synthetic users, notes and releases.
"""
from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from uuid import uuid4

from sqlalchemy import event
from sqlalchemy.orm import scoped_session, sessionmaker

from app import create_app
from app.repositories import deck_release_repository as repository
from app.services import deck_release_service as service, deck_working_tree_service
from app.services import marketplace_query_service
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.deck_working_dirty_entity import DeckWorkingDirtyEntity
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from tests.study_note_fixtures import create_note_user


@unittest.skipUnless(os.getenv("FLAMA_MYSQL_TESTS") == "1", "requires opt-in local MySQL")
class DeckReleasePerformanceMySQLTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = create_app(audit_mode=True)
        with cls.app.app_context():
            if db.engine.dialect.name != "mysql" or db.engine.url.host not in {
                "localhost", "127.0.0.1", "::1",
            }:
                raise RuntimeError("Release regressions require loopback MySQL")

    def setUp(self):
        context = self.app.app_context()
        context.push()
        self.addCleanup(context.pop)
        connection = db.engine.connect()
        self.addCleanup(connection.close)
        outer = connection.begin()
        self.addCleanup(outer.rollback)

        def forbid_physical_commit(_connection):
            raise AssertionError("MySQL regression tests must never commit the outer transaction")

        event.listen(connection, "commit", forbid_physical_commit)
        sessions = scoped_session(sessionmaker(bind=connection, join_transaction_mode="create_savepoint"))
        session_patch = patch.object(db, "session", sessions)
        session_patch.start()
        self.addCleanup(session_patch.stop)
        self.addCleanup(sessions.remove)
        token = uuid4().hex
        self.owner = create_note_user(db.session, username=f"release-probe-{token}", email=f"{token}@example.invalid")
        self.learner = create_note_user(db.session, username=f"release-peer-{token}", email=f"peer-{token}@example.invalid")
        self.note_type = NoteType(user_id=self.owner.id, name="Release probe")
        db.session.add(self.note_type)
        db.session.flush()
        self.word = FieldDef(note_type_id=self.note_type.id, name="Word", field_type="text", position=0)
        self.values = FieldDef(note_type_id=self.note_type.id, name="Values", field_type="array", position=1)
        self.deck = Deck(name="Release probe", owner_user_id=self.owner.id, note_type_id=self.note_type.id)
        db.session.add_all([self.word, self.values, self.deck])
        db.session.flush()
        self.notes = [self._new_note("first"), self._new_note("second")]
        db.session.flush()
        self.item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=self.deck.id,
            source_note_type_id=self.note_type.id, title="Release probe", publish_status="private")
        db.session.add(self.item)
        db.session.commit()

    def _new_note(self, word):
        note = Note(user_id=self.owner.id, note_type_id=self.note_type.id, deck_id=self.deck.id,
            field_values={"Word": word, "Values": ["one", ["two", "<b>three</b>"]]})
        db.session.add(note)
        return note

    def _legacy_install(self):
        db.session.add(DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            clone_mode="logical_overlay", source_deck_id=self.deck.id,
            source_note_type_id=self.note_type.id, source_owner_user_id=self.owner.id,
            version_mode="legacy_snapshot"))
        db.session.commit()

    def _publish(self, label):
        return service.publish_release_and_commit(deck_item_id=self.item.id, user_id=self.owner.id,
            version_label=label, changelog=None, expected_current_release_id=self.item.current_release_id,
            expected_working_revision=self.item.working_revision, idempotency_key=f"probe:{label}").release

    def _edit(self, note, name, value):
        note.field_values = {**note.field_values, name: value}
        db.session.flush()
        deck_working_tree_service.mark_note_fields_changed(note=note, field_names=[name])
        db.session.commit()

    def test_checkpoint_filter_preserves_legacy_baseline_and_notes_without_checkpoint(self):
        self._legacy_install()
        first = self._publish("1")
        first_id = first.id
        self._edit(self.notes[0], "Word", "updated")
        added = self._new_note("added later")
        db.session.flush()
        deck_working_tree_service.mark_note_fields_changed(note=added, field_names=["Word", "Values"])
        db.session.commit()
        second = self._publish("2")
        # A newer checkpoint covers only one note; other notes retain their
        # earlier checkpoint or no checkpoint at all.
        db.session.add(DeckReleaseNoteCheckpoint(release_id=second.id, release_sequence_no=2,
            source_note_id=self.notes[0].id, source_deck_id=self.deck.id, note_type_id=self.note_type.id,
            field_values=self.notes[0].field_values, tags=[], content_hash="a" * 64))
        db.session.commit()
        all_ids = [note.id for note in self.notes] + [added.id]
        names = service.get_note_values_for_ids_at_release(second.id, all_ids)
        self.assertEqual(names[self.notes[0].id]["Word"], "updated")
        self.assertEqual(names[added.id]["Values"], ["one", ["two", "<b>three</b>"]])
        self.assertEqual(service.get_note_values_at_release(first_id, self.notes[0].id)["Word"], "first")
        full = service.reconstruct_release_state(second.id)
        self.assertEqual(set(full.notes), set(all_ids))
        self.assertEqual(full.notes[added.id].field_values_by_id[self.word.id], "added later")
        pruned = repository.list_release_history_changes(deck_item_id=self.item.id, through_sequence=2,
            entity_kinds=["note_field"], content_only=True, after_checkpoints=True)
        self.assertEqual(len(pruned), 2)  # Only the added note has no checkpoint.
        atoms = service.get_atomic_changes_between_releases(from_release_or_id=None, to_release_or_id=first_id)
        self.assertEqual(sum(row["entity_kind"] == "note_field" for row in atoms), 4)
        # Old receipts can still diff from null to the complete initial baseline.
        self.assertEqual(DeckReleaseChange.query.filter_by(release_id=first_id, entity_kind="note_field").count(), 4)

    def test_stale_schema_journal_is_rejected_before_loading_note_history(self):
        first = self._publish("1")
        self.word.field_type = "richtext"
        db.session.flush()
        deck_working_tree_service.mark_field_def_changed(field_def=self.word, owner_user_id=self.owner.id,
            property_keys=["field_type"])
        row = DeckWorkingDirtyEntity.query.filter_by(deck_item_id=self.item.id, entity_kind="field_def").one()
        row.current_hash = "bad" * 21
        db.session.commit()
        with patch.object(repository, "list_note_field_history_for_ids", side_effect=AssertionError("read note history")), \
             patch.object(repository, "list_notes_by_ids", side_effect=AssertionError("read live notes")):
            self.assertIsNone(service._try_build_sparse_diff(item=self.item, base_release=first))
        preview = service.preview_release(deck_item_id=self.item.id, user_id=self.owner.id)
        self.assertEqual(preview["summary"]["change_count"], 1)

    def test_batch_failure_rolls_back_and_same_request_can_retry(self):
        self._legacy_install()
        for number in range(603):
            self._new_note(f"bulk {number}")
        db.session.commit()
        calls = []

        def fail_second_batch(conn, cursor, statement, parameters, context, many):
            if statement.startswith("INSERT INTO deck_release_changes "):
                calls.append((many, len(parameters)))
                if len(calls) == 2:
                    raise RuntimeError("injected batch failure")

        event.listen(db.engine, "before_cursor_execute", fail_second_batch)
        try:
            with self.assertRaisesRegex(RuntimeError, "injected batch failure"):
                self._publish("1")
        finally:
            event.remove(db.engine, "before_cursor_execute", fail_second_batch)
        self.assertIsNone(self.item.current_release_id)
        self.assertEqual(DeckRelease.query.filter_by(deck_item_id=self.item.id).count(), 0)
        self.assertTrue(all(many for many, _ in calls))
        self.assertEqual([size for _, size in calls], [500, 500])
        release = self._publish("1")
        # 605 notes x 2 fields plus 10 schema atoms, all in one transaction.
        self.assertEqual(release.change_count, 1220)
        self.assertEqual(DeckReleaseChange.query.filter_by(release_id=release.id).count(), 1220)
        values = service.get_note_values_at_release(release, self.notes[0].id)
        self.assertEqual(values["Values"], ["one", ["two", "<b>three</b>"]])
        replay = service.publish_release_and_commit(deck_item_id=self.item.id, user_id=self.owner.id,
            version_label="1", changelog=None, expected_current_release_id=None,
            expected_working_revision=0, idempotency_key="probe:1")
        self.assertTrue(replay.replayed)
        self.assertEqual(replay.release.id, release.id)

    def test_sample_query_is_bounded_and_respects_membership_intervals(self):
        release = self._publish("1")
        original = repository.list_memberships_for_entities

        def forbid_unbounded_notes(**kwargs):
            if kwargs["entity_kind"] == "note":
                self.assertIsNotNone(kwargs.get("entity_ids"))
            return original(**kwargs)

        with patch.object(repository, "list_memberships_for_entities", side_effect=forbid_unbounded_notes):
            samples = marketplace_query_service.build_release_sample_cache_from_release(self.item, release, limit=1)
        self.assertEqual(len(samples), 1)
        ids = sorted(note.id for note in self.notes)
        row = DeckReleaseEntityMembership.query.filter_by(deck_item_id=self.item.id,
            entity_kind="note", entity_id=ids[0]).one()
        row.removed_sequence = 2
        db.session.add(DeckReleaseEntityMembership(deck_item_id=self.item.id, entity_kind="note", entity_id=ids[0],
            source_deck_id=self.deck.id, introduced_sequence=3, metadata_json={"note_type_id":self.note_type.id}))
        db.session.flush()
        self.assertEqual(repository.list_note_ids_at_release(deck_item_id=self.item.id, sequence_no=1, limit=1), ids[:1])
        self.assertEqual(repository.list_note_ids_at_release(deck_item_id=self.item.id, sequence_no=2, limit=1), ids[1:])
        self.assertEqual(repository.list_note_ids_at_release(deck_item_id=self.item.id, sequence_no=3, limit=1), ids[:1])


if __name__ == "__main__":
    unittest.main()
