"""Author draft isolation on disposable local MySQL; no application writes."""
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import event, select, update

from app.services.field_value_identity_service import FieldIdentityConflict, FieldIdentityError
from app.services.note_base_context import base_maintenance, note_author_view, published_base_write
from app.services.note_draft_service import effective_note_metadata, stage_note_delete
from models import db
from models.deck import Deck
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_draft import NoteDraft
from models.note_type import NoteType
from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user


class NoteDraftMySQLTests(NoteBaseMySQLTestCase):
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": True}

    def setUp(self):
        super().setUp()
        self.owner = create_note_user(db.session, username="draft-owner", email="draft-owner@example.invalid")
        self.note_type = NoteType(user_id=self.owner.id, name="Draft schema")
        db.session.add(self.note_type)
        db.session.flush()
        self.word = FieldDef(note_type_id=self.note_type.id, name="Word", field_type="text", position=0)
        self.array = FieldDef(note_type_id=self.note_type.id, name="Array", field_type="array", position=1)
        self.deck = Deck(owner_user_id=self.owner.id, note_type_id=self.note_type.id, name="Draft deck")
        db.session.add_all([self.word, self.array, self.deck])
        db.session.flush()
        self.note = Note(user_id=self.owner.id, note_type_id=self.note_type.id, deck_id=self.deck.id,
                         field_values={"Word": "base", "Array": ["a", ["b"]], "Extra": "base extra"}, tags=["base"])
        db.session.add(self.note)
        db.session.flush()
        with published_base_write():
            self.note.published_at = datetime.utcnow()
            db.session.flush()
        db.session.commit()
        self.base_revision = self.note.content_revision

    def _stored(self):
        return db.session.connection().execute(select(Note.__table__).where(Note.__table__.c.id == self.note.id)).mappings().one()

    def test_published_edits_remain_sparse_and_base_is_unchanged(self):
        self.note.field_values = {**self.note.field_values, "Word": "draft"}
        db.session.commit()
        self.assertEqual(self._stored()["field_values_by_id"][self.word.id], "base")
        self.assertEqual(self.note.field_values["Word"], "draft")
        self.assertEqual(self.note.content_revision, self.base_revision)
        draft = db.session.get(NoteDraft, self.note.id)
        self.assertEqual(draft.field_values_by_id, {self.word.id: {"op": "set", "value": "draft"}})

    def test_last_save_wins_and_revert_removes_draft_row(self):
        for value in ("first", "second", "base"):
            self.note.field_values = {**self.note.field_values, "Word": value}
            db.session.commit()
            self.assertEqual(self.note.field_values["Word"], value)
        self.assertIsNone(db.session.get(NoteDraft, self.note.id))

    def test_current_draft_metadata_survives_an_old_reader_snapshot(self):
        self.note.field_values = {**self.note.field_values, "Word": "old draft"}
        db.session.commit()
        draft = db.session.get(NoteDraft, self.note.id)
        self.assertEqual(draft.tags, None)  # establish an older RR snapshot
        with db.engine.begin() as connection:
            connection.execute(NoteDraft.__table__.update().where(NoteDraft.note_id == self.note.id)
                .values(tags=["concurrent metadata"]))
        self.note.field_values = {**self.note.field_values, "Word": "my field edit"}
        db.session.commit()
        self.assertEqual(effective_note_metadata(self.note)['tags'], ["concurrent metadata"])
        self.assertEqual(self.note.field_values['Word'], "my field edit")

    def test_metadata_save_does_not_revert_a_base_published_after_read_snapshot(self):
        other = Deck(owner_user_id=self.owner.id, note_type_id=self.note_type.id, name='Published destination')
        db.session.add(other); db.session.commit()
        self.note.field_values = {**self.note.field_values, 'Word': 'old private draft'}
        db.session.commit()
        self.assertEqual(self.note.field_values['Word'], 'old private draft')
        destination, note_id = other.id, self.note.id
        current = {**self.note.field_values_by_id, self.word.id: 'new published word'}
        with db.engine.begin() as connection:
            connection.execute(Note.__table__.update().where(Note.id == note_id).values(
                field_values_by_id=current, deck_id=destination, tags=['new published tags'],
                content_revision=Note.content_revision+1))
            connection.execute(NoteDraft.__table__.delete().where(NoteDraft.note_id == note_id))
        self.note.tags = ['my tag edit']
        db.session.commit()
        self.assertEqual(self.note.field_values['Word'], 'new published word')
        self.assertEqual(effective_note_metadata(self.note)['deck_id'], destination)
        draft = db.session.get(NoteDraft, note_id)
        self.assertEqual(draft.field_values_by_id, {})
        self.assertIsNone(draft.deck_id)
        self.assertEqual(draft.tags, ['my tag edit'])

    def test_direct_author_timestamp_cannot_mutate_published_base(self):
        from datetime import timedelta
        timestamp = self.note.updated_at
        self.note.updated_at = timestamp + timedelta(days=1)
        db.session.commit()
        self.assertEqual(self.note.updated_at, timestamp)
        self.assertIsNone(db.session.get(NoteDraft, self.note.id))

    def test_direct_draft_edit_retains_current_untouched_columns(self):
        self.note.field_values = {**self.note.field_values, "Word": "old draft"}
        db.session.commit()
        draft = db.session.get(NoteDraft, self.note.id)
        replacement = {self.word.id: {"op": "set", "value": "concurrent field"}}
        with db.engine.begin() as connection:
            connection.execute(NoteDraft.__table__.update().where(NoteDraft.note_id == self.note.id)
                .values(field_values_by_id=replacement))
        draft.tags = ["my metadata"]
        db.session.commit()
        self.assertEqual(self.note.field_values['Word'], "concurrent field")
        self.assertEqual(effective_note_metadata(self.note)['tags'], ["my metadata"])

    def test_direct_metadata_edit_after_publication_does_not_restore_consumed_fields(self):
        self.note.field_values = {**self.note.field_values, 'Word': 'old draft'}
        db.session.commit()
        draft = db.session.get(NoteDraft, self.note.id)
        current = {**self.note.field_values_by_id, self.word.id: 'new publication'}
        with db.engine.begin() as connection:
            connection.execute(Note.__table__.update().where(Note.id == self.note.id).values(
                field_values_by_id=current, content_revision=Note.content_revision+1))
            connection.execute(NoteDraft.__table__.delete().where(NoteDraft.note_id == self.note.id))
        draft.tags = ['my metadata']
        db.session.flush()
        self.assertEqual(self.note.field_values['Word'], 'new publication')
        db.session.commit()
        self.assertEqual(self.note.field_values['Word'], 'new publication')
        self.assertEqual(db.session.get(NoteDraft, self.note.id).field_values_by_id, {})

    def test_direct_draft_assignment_preserves_boolean_number_type_change(self):
        self.note.field_values = {**self.note.field_values, 'Word': True}
        db.session.commit()
        draft = db.session.get(NoteDraft, self.note.id)
        draft.field_values_by_id = {self.word.id: {'op': 'set', 'value': 1}}
        db.session.commit()
        self.assertIs(type(db.session.get(NoteDraft, self.note.id).field_values_by_id[self.word.id]['value']), int)

    def test_draft_created_after_an_old_empty_snapshot_is_reconciled(self):
        from app.services.note_draft_service import get_note_draft
        self.assertIsNone(get_note_draft(self.note))
        with db.engine.begin() as connection:
            connection.execute(NoteDraft.__table__.insert().values(note_id=self.note.id,
                field_values_by_id={}, tags=["concurrent metadata"]))
        self.note.field_values = {**self.note.field_values, "Word": "my edit"}
        db.session.commit()
        self.assertEqual(effective_note_metadata(self.note)['tags'], ["concurrent metadata"])
        self.assertEqual(self.note.field_values['Word'], "my edit")

    def test_existing_draft_keeps_boolean_and_number_distinct(self):
        for value in (True, 1, False, 0):
            self.note.field_values = {**self.note.field_values, "Extra": value}
            db.session.commit()
            self.assertIs(type(self.note.field_values['Extra']), type(value))
            self.assertEqual(self.note.field_values['Extra'], value)

    def test_draft_relationship_and_explicit_detach_keep_lookup_consistent(self):
        row = NoteDraft(note=self.note, field_values_by_id={self.word.id: {'op': 'set', 'value': 'related'}})
        db.session.add(row)
        db.session.flush()
        self.assertEqual(self.note.field_values['Word'], 'related')
        db.session.expunge(row)
        self.assertEqual(self.note.field_values['Word'], 'related')
        self.note.field_values = {**self.note.field_values, 'Word': 'after detach'}
        db.session.commit()
        self.assertEqual(self.note.field_values['Word'], 'after detach')

    def test_locked_schema_cache_is_refreshed_after_savepoint_rollback(self):
        self.note.field_values = {**self.note.field_values, 'Word': 'first edit'}
        db.session.flush()
        savepoint = db.session.begin_nested()
        self.word.name = 'Temporary label'
        db.session.flush()
        savepoint.rollback()
        self.note.field_values = {**self.note.field_values, 'Word': 'second edit'}
        db.session.commit()
        self.assertEqual(self.note.field_values['Word'], 'second edit')
        self.assertNotIn('Temporary label', self.note.field_values)

    def test_metadata_can_be_reverted_to_base_after_prior_draft(self):
        self.note.tags = ["changed"]
        db.session.commit()
        self.assertEqual(effective_note_metadata(self.note)["tags"], ["changed"])
        self.note.tags = ["base"]
        db.session.commit()
        self.assertEqual(effective_note_metadata(self.note)["tags"], ["base"])
        self.assertIsNone(db.session.get(NoteDraft, self.note.id))

    def test_remove_null_native_arrays_and_extras_have_distinct_semantics(self):
        self.note.field_values = {"Word": None, "Array": ["x", ["y", "<b>z</b>"]], "Extra": None}
        db.session.commit()
        self.assertEqual(self.note.field_values, {"Word": None, "Array": ["x", ["y", "<b>z</b>"]], "Extra": None})
        self.note.field_values = {"Array": []}
        db.session.commit()
        self.assertEqual(self.note.field_values, {"Array": []})
        draft = db.session.get(NoteDraft, self.note.id)
        self.assertEqual(draft.field_values_by_id[self.word.id], {"op": "remove"})
        self.assertEqual(self._stored()["field_values_extras"], {"Extra": "base extra"})

    def test_tags_and_move_do_not_mutate_base_or_erase_field_draft(self):
        child = Deck(owner_user_id=self.owner.id, note_type_id=self.note_type.id, name="Child", parent_id=self.deck.id)
        db.session.add(child)
        db.session.flush()
        self.note.field_values = {**self.note.field_values, "Word": "draft"}
        db.session.commit()
        self.note.tags, self.note.deck_id = ["draft"], child.id
        db.session.commit()
        self.assertEqual(self._stored()["tags"], ["base"])
        self.assertEqual(self._stored()["deck_id"], self.deck.id)
        self.assertEqual(effective_note_metadata(self.note), {"tags": ["draft"], "deck_id": child.id, "op": "edit"})
        self.assertEqual(self.note.field_values["Word"], "draft")

    def test_unpublished_note_writes_directly_without_a_draft(self):
        note = Note(user_id=self.owner.id, note_type_id=self.note_type.id, deck_id=self.deck.id, field_values={"Word": "new"})
        db.session.add(note)
        db.session.commit()
        note.field_values = {"Word": "edited"}
        db.session.commit()
        self.assertEqual(note.field_values_by_id[self.word.id], "edited")
        self.assertIsNone(db.session.get(NoteDraft, note.id))

    def test_delete_stages_draft_and_only_author_hides_it_before_publish(self):
        stage_note_delete(self.note)
        db.session.commit()
        with note_author_view(self.owner.id):
            self.assertIsNone(db.session.execute(select(Note).where(Note.id == self.note.id)).scalar_one_or_none())
        with note_author_view(self.owner.id + 100):
            self.assertIsNotNone(db.session.execute(select(Note).where(Note.id == self.note.id)).scalar_one_or_none())
        self.assertIsNone(self._stored()["deleted_at"])

    def test_direct_orm_delete_retains_published_note_as_draft(self):
        db.session.delete(self.note)
        db.session.commit()
        self.assertEqual(db.session.get(NoteDraft, self.note.id).op, "delete")
        self.assertEqual(self._stored()["field_values_by_id"][self.word.id], "base")

    def test_note_and_field_tombstones_are_hidden_with_explicit_audit_escape(self):
        with published_base_write():
            self.note.deleted_at = datetime.utcnow()
            db.session.flush()
        db.session.delete(self.word)
        db.session.commit()
        self.assertIsNone(db.session.execute(select(Note).where(Note.id == self.note.id)).scalar_one_or_none())
        self.assertIsNotNone(db.session.execute(select(Note).where(Note.id == self.note.id)
            .execution_options(include_deleted_notes=True)).scalar_one_or_none())
        self.assertIsNone(db.session.execute(select(FieldDef).where(FieldDef.id == self.word.id)).scalar_one_or_none())
        field = db.session.execute(select(FieldDef).where(FieldDef.id == self.word.id)
            .execution_options(include_deleted_fields=True)).scalar_one()
        self.assertIsNotNone(field.deleted_at)

    def test_base_write_and_maintenance_are_explicit_and_revisioned(self):
        with base_maintenance("test technical normalization"):
            self.note.field_values = {**self.note.field_values, "Word": "normalized"}
            db.session.flush()
        db.session.commit()
        self.assertEqual(self._stored()["field_values_by_id"][self.word.id], "normalized")
        self.assertGreater(self.note.content_revision, self.base_revision)
        self.assertIsNone(db.session.get(NoteDraft, self.note.id))
        with self.assertRaises(FieldIdentityError):
            db.session.execute(update(Note).where(Note.id == self.note.id).values(tags=[]))
        db.session.rollback()

    def test_drafts_are_loaded_once_for_a_page(self):
        notes = [self.note]
        for index in range(4):
            note = Note(user_id=self.owner.id, note_type_id=self.note_type.id, deck_id=self.deck.id,
                        field_values={"Word": str(index)})
            db.session.add(note)
            notes.append(note)
        db.session.flush()
        with published_base_write():
            for note in notes:
                note.published_at = datetime.utcnow()
            db.session.flush()
        db.session.commit()
        for note in notes:
            note.field_values = {**note.field_values, "Word": "draft"}
        db.session.commit()
        db.session.expire_all()
        page = db.session.execute(select(Note).order_by(Note.id)).scalars().all()
        statements = []
        def capture(_connection, _cursor, statement, _params, _context, _many):
            if "FROM note_drafts" in statement:
                statements.append(statement)
        event.listen(db.engine, "before_cursor_execute", capture)
        try:
            self.assertTrue(all(note.field_values["Word"] == "draft" for note in page))
        finally:
            event.remove(db.engine, "before_cursor_execute", capture)
        self.assertEqual(len(statements), 1)

    def test_author_edits_bump_listing_without_dirty_journal(self):
        item = DeckMarketplaceItem(owner_user_id=self.owner.id, source_deck_id=self.deck.id,
            source_note_type_id=self.note_type.id, title="Draft listing", publish_status="private")
        db.session.add(item)
        db.session.commit()
        previous = item.working_revision
        self.note.field_values = {**self.note.field_values, "Word": "draft"}
        db.session.commit()
        self.assertEqual(item.working_revision, previous + 1)

    def test_flag_off_preserves_direct_write_behavior(self):
        with patch.dict(self.app.config, NOTE_PUBLISHED_BASE_ENABLED=False):
            self.note.field_values = {**self.note.field_values, "Word": "legacy"}
            db.session.commit()
            self.assertEqual(self.note.field_values_by_id[self.word.id], "legacy")
            self.assertIsNone(db.session.get(NoteDraft, self.note.id))

    def test_large_session_loads_drafts_in_bounded_batches_and_reuses_after_flush(self):
        notes = [self.note] + [Note(user_id=self.owner.id, note_type_id=self.note_type.id,
            deck_id=self.deck.id, field_values={"Word": str(index)}) for index in range(1999)]
        db.session.add_all(notes[1:])
        db.session.flush()
        with published_base_write():
            for note in notes:
                note.published_at = datetime.utcnow()
            db.session.flush()
        db.session.commit()
        page = db.session.execute(select(Note).order_by(Note.id)).scalars().all()
        draft_selects = []
        def capture(_conn, _cursor, statement, params, *_args):
            if statement.lstrip().lower().startswith('select') and 'from note_drafts' in statement.lower():
                draft_selects.append((statement, len(params)))
        event.listen(db.engine, 'before_cursor_execute', capture)
        try:
            first = [note.field_values for note in page]
            self.assertEqual(len(draft_selects), 4)
            self.assertTrue(all(count <= 500 for _, count in draft_selects))
            # A changed Note creates its own Draft; an unrelated cached miss
            # remains known across that flush and must not reload the page.
            page[0].field_values = {**first[0], 'Word': 'changed'}
            db.session.flush()
            before = len(draft_selects)
            self.assertEqual(page[0].field_values['Word'], 'changed')
            self.assertEqual([note.field_values for note in page[1:]], first[1:])
            self.assertEqual(len(draft_selects), before)
        finally:
            event.remove(db.engine, 'before_cursor_execute', capture)

    def test_draft_cache_tracks_pending_removal_and_rollback(self):
        self.assertEqual(self.note.field_values['Word'], 'base')
        draft = NoteDraft(note_id=self.note.id, field_values_by_id={self.word.id:{'op':'set','value':'pending'}})
        db.session.add(draft)
        self.assertEqual(self.note.field_values['Word'], 'pending')
        db.session.flush()
        db.session.delete(draft)
        self.assertEqual(self.note.field_values['Word'], 'base')
        db.session.flush()
        self.assertEqual(self.note.field_values['Word'], 'base')
        db.session.rollback()
        self.assertEqual(self.note.field_values['Word'], 'base')

    def test_property_only_exposes_drafts_to_owner_or_trusted_job(self):
        from flask import g, request
        learner = create_note_user(db.session, username='draft-learner', email='draft-learner@example.invalid')
        self.note.field_values = {**self.note.field_values, 'Word':'private draft'}
        db.session.commit()
        owner_id, learner_id = self.owner.id, learner.id
        for user, expected in ((self.owner,'private draft'),(learner,'base'),(None,'base')):
            with self.app.test_request_context('/published-note'):
                g.pop('_login_user',None)
                if user is not None:
                    g._login_user = user
                self.assertEqual(self.note.field_values['Word'],expected)
        with note_author_view(owner_id):
            self.assertEqual(self.note.field_values['Word'],'private draft')
        with note_author_view(learner_id):
            self.assertEqual(self.note.field_values['Word'],'base')
        with self.app.test_request_context('/connect-token'):
            g.pop('_login_user',None)
            request.environ['flama.note_author_user_id'] = owner_id
            self.assertEqual(self.note.field_values['Word'],'private draft')
        with self.app.test_request_context('/anonymous'):
            g.pop('_login_user',None)
            self.assertEqual(self.note.field_values['Word'],'base')

    def test_foreign_property_or_direct_draft_write_cannot_replace_author_draft(self):
        learner = create_note_user(db.session, username='foreign-writer', email='foreign-writer@example.invalid')
        self.note.field_values = {**self.note.field_values, 'Word':'private draft'}
        db.session.commit()
        learner_id, note_id = learner.id, self.note.id
        with note_author_view(learner_id), self.assertRaises(FieldIdentityConflict):
            self.note.field_values = {'Word':'intruder'}
        db.session.rollback()
        with note_author_view(learner_id), self.assertRaises(FieldIdentityConflict):
            draft = db.session.get(NoteDraft,note_id)
            draft.field_values_by_id = {self.word.id:{'op':'set','value':'intruder'}}
            db.session.flush()
        db.session.rollback()
        from sqlalchemy import delete, insert
        for statement in (update(NoteDraft).where(NoteDraft.note_id == note_id).values(op='delete'),
                delete(NoteDraft).where(NoteDraft.note_id == note_id),
                insert(NoteDraft).values(note_id=note_id,field_values_by_id={})):
            with note_author_view(learner_id), self.assertRaises(FieldIdentityConflict):
                db.session.execute(statement)
            db.session.rollback()
        self.assertEqual(self.note.field_values['Word'],'private draft')
