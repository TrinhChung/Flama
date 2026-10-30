"""Published Base and effective SQL semantics on disposable local MySQL."""
from datetime import datetime
from unittest.mock import patch

from sqlalchemy import event, select

from tests.note_base_mysql_fixture import NoteBaseMySQLTestCase
from tests.study_note_fixtures import create_note_user
from models import db
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from app.services.note_base_context import published_base_write, note_author_view
from app.services.note_draft_service import stage_note_delete
from app.services.effective_note_reader import (
    expanded_source_deck_mapping, published_note_values_for_ids,
)
from app.services.share.overlay import (
    apply_clone_note_field_overrides, build_clone_schema_view, resolve_clone_scope_for_local_deck,
)
from app.repositories.field_value_query_repository import (
    author_note_visible, note_field_text_expression, note_values_search_condition,
)
from app.repositories.browse_card_repository import clone_effective_field_text_expression
from app.repositories.browse_search_repository import clone_note_search_ids
from app.repositories.flashcards_share_repository import source_deck_map_condition


class NoteBaseReaderTests(NoteBaseMySQLTestCase):
    APP_CONFIG = {"NOTE_PUBLISHED_BASE_ENABLED": True}

    def test_card_scope_lookup_does_not_scan_unrelated_installs(self):
        from types import SimpleNamespace
        from tests.study_note_fixtures import attach_template
        from models.card import Card
        from app.services.share.overlay import resolve_clone_scope_for_card
        attach_template(db.session, note_type_id=self.nt.id, owner_user_id=self.author.id,
            name='Scope card', front_html='{{Word}}', back_html='{{Word}}', shared_css='')
        db.session.commit()
        card = Card.query.filter(Card.note_id == self.note.id).first()
        note_id, app_id, learner_id, expected = self.note.id, card.application_id, self.learner.id, self.install.id
        def measure():
            db.session.expire_all()
            ref = SimpleNamespace(note=db.session.get(Note,note_id), note_id=note_id, application_id=app_id)
            statements = []
            def capture(_conn,_cursor,sql,*_args):statements.append(sql)
            event.listen(db.engine,'before_cursor_execute',capture)
            try:
                scope = resolve_clone_scope_for_card(user_id=learner_id,card_obj=ref)
                self.assertEqual(scope.install.id,expected)
            finally:event.remove(db.engine,'before_cursor_execute',capture)
            return len(statements)
        before = measure()
        for index in range(4):
            source = Deck(owner_user_id=self.author.id,note_type_id=self.nt.id,name=f'Unrelated source {index}')
            local = Deck(owner_user_id=learner_id,note_type_id=self.nt.id,name=f'Unrelated local {index}')
            db.session.add_all([source,local]);db.session.flush()
            item = DeckMarketplaceItem(owner_user_id=self.author.id,source_deck_id=source.id,
                source_note_type_id=self.nt.id,title=f'Unrelated {index}')
            db.session.add(item);db.session.flush()
            install = DeckInstall(deck_item_id=item.id,user_id=learner_id,local_deck_id=local.id,
                clone_mode='logical_overlay',source_deck_id=source.id,
                source_owner_user_id=self.author.id,source_note_type_id=self.nt.id)
            db.session.add(install);db.session.flush()
            db.session.add(DeckCloneDeckMap(deck_install_id=install.id,source_deck_id=source.id,local_deck_id=local.id))
        db.session.commit()
        self.assertLessEqual(measure(),before+1)

    def test_author_sort_and_detail_use_draft_edit_time_without_changing_base_time(self):
        from datetime import timedelta
        from app.services.note_base_context import base_maintenance
        from app.services.browse_note_service import list_notes,get_note_detail
        from models.note_draft import NoteDraft
        older = datetime.utcnow()-timedelta(days=3)
        other = Note(user_id=self.author.id,note_type_id=self.nt.id,deck_id=self.source.id,
            field_values={'Word':'base','Array':[]})
        db.session.add(other);db.session.flush()
        with base_maintenance('Author timestamp regression fixture'):
            self.note.updated_at = older
            other.updated_at = older+timedelta(days=1)
            other.published_at = older
            db.session.flush()
        db.session.commit()
        args={'deck_id':str(self.source.id),'sort_by':'word','sort_dir':'asc','per_page':'20'}
        base_time = self.note.updated_at
        def rows():return list_notes(user_id=self.author.id,admin_mode=False,timezone_name='UTC',query_args=args)['items']
        self.assertEqual(rows()[0]['note_id'],other.id)
        self.note.field_values={**self.note.field_values,'Array':['private recent edit']}
        db.session.commit()
        self.assertEqual(self.note.updated_at,base_time)
        self.assertEqual(rows()[0]['note_id'],self.note.id)
        draft = db.session.get(NoteDraft,self.note.id)
        owner = get_note_detail(user_id=self.author.id,admin_mode=False,timezone_name='UTC',note_id=self.note.id,compact=True)
        learner = get_note_detail(user_id=self.learner.id,admin_mode=False,timezone_name='UTC',note_id=self.note.id,compact=True)
        self.assertEqual(owner['note']['updated_at'],draft.updated_at.isoformat())
        self.assertEqual(learner['note']['updated_at'],self.note.updated_at.isoformat())

    def test_browse_joined_draft_search_preserves_value_and_removal_semantics(self):
        from app.services.browse_note_service import list_notes
        with published_base_write('Joined search fixture'):
            self.note.field_values = {'Word': 'base word', 'Array': ['base array'],
                'RemovedExtra': 'old extra needle'}
            db.session.flush()
        db.session.commit()
        self.note.field_values = {'Word': 'draft word', 'Array': ['nested', ['deep needle', 12345]],
            'AddedExtra': 'new extra needle', 'BooleanExtra': True, 'NullExtra': None}
        db.session.commit()
        def search(keyword):
            return list_notes(user_id=self.author.id, admin_mode=False, timezone_name='UTC', query_args={
                'deck_id': str(self.source.id), 'q': keyword, 'sort_by': 'word', 'per_page': '20'})
        for keyword in ('draft word', 'deep needle', '12345', 'new extra needle', 'true'):
            with self.subTest(keyword=keyword):
                self.assertEqual([row['note_id'] for row in search(keyword)['items']], [self.note.id])
        for keyword in ('base word', 'old extra needle', 'RemovedExtra', 'AddedExtra', 'NullExtra', self.word.id):
            with self.subTest(keyword=keyword):
                self.assertEqual(search(keyword)['items'], [])

    def test_scalar_leaf_search_ignores_escaped_member_keys_and_nulls(self):
        from sqlalchemy import literal
        from app.repositories.field_value_query_repository import _JsonLeafLike
        cases = [
            ({'12345': None, 'true': None, 'escaped\\"false': None}, '12345', False),
            ({'12345': None, 'true': None, 'escaped\\"false': None}, 'true', False),
            ({'12345': None, 'true': None, 'escaped\\"false': None}, 'false', False),
            ([None, [None]], 'l', False),
            ([None, [None]], 'u', False),
            ([12345, [True, False, -12.5]], '234', True),
            ([12345, [True, False, -12.5]], 'true', True),
            ([12345, [True, False, -12.5]], '-12.5', True),
            ({'label': 'escaped\\"12345'}, '12345', True),
        ]
        for document, keyword, expected in cases:
            with self.subTest(document=document, keyword=keyword):
                result = db.session.execute(select(_JsonLeafLike(literal(document, type_=db.JSON),
                    literal(f'%{keyword}%')))).scalar_one()
                self.assertEqual(bool(result), expected)

    def test_bounded_schema_word_sort_matches_scoped_fallback(self):
        from app.repositories.browse_card_repository import owned_note_word_expression, owned_text_field_ids
        from app.repositories.field_value_query_repository import join_author_draft
        from models.note_draft import NoteDraft
        from sqlalchemy.orm import aliased
        for value, array in [('  z', []), ('b', []), ('', ['fallback']), ('  ', ['nested', ['list']])]:
            db.session.add(Note(user_id=self.author.id, note_type_id=self.nt.id,
                deck_id=self.source.id, field_values={'Word': value, 'Array': array}))
        db.session.commit()
        self.note.field_values = {'Word': '  a', 'Array': ['draft']}
        db.session.commit()
        draft = aliased(NoteDraft)
        fields = owned_text_field_ids(self.author.id)
        query = join_author_draft(select(Note.id), draft, self.author.id).where(Note.user_id == self.author.id)
        original = owned_note_word_expression(draft_model=draft)
        bounded = owned_note_word_expression(draft_model=draft, field_ids_by_type=fields)
        old = db.session.execute(query.order_by(original, Note.id)).scalars().all()
        new = db.session.execute(query.order_by(bounded, Note.id)).scalars().all()
        self.assertEqual(new, old)

    def setUp(self):
        super().setUp()
        self.author = create_note_user(db.session, username="reader-author", email="reader-author@example.invalid")
        self.learner = create_note_user(db.session, username="reader-learner", email="reader-learner@example.invalid")
        self.nt = NoteType(user_id=self.author.id, name="Reader schema")
        db.session.add(self.nt)
        db.session.flush()
        self.word = FieldDef(note_type_id=self.nt.id, name="Word", field_type="text", position=0)
        self.array = FieldDef(note_type_id=self.nt.id, name="Array", field_type="array", position=1)
        self.source = Deck(owner_user_id=self.author.id, note_type_id=self.nt.id, name="Source")
        self.local = Deck(owner_user_id=self.learner.id, note_type_id=self.nt.id, name="Local")
        db.session.add_all([self.word, self.array, self.source, self.local])
        db.session.flush()
        self.note = Note(user_id=self.author.id, note_type_id=self.nt.id, deck_id=self.source.id,
            field_values={"Word": "base", "Array": ["array", ["nested"]]}, tags=["base"])
        self.item = DeckMarketplaceItem(owner_user_id=self.author.id, source_deck_id=self.source.id,
            source_note_type_id=self.nt.id, title="Reader", publish_status="published",
            published_schema_json={self.word.id: {"name": "Word", "field_type": "text", "position": 0},
                self.array.id: {"name": "Array", "field_type": "array", "position": 1}})
        db.session.add_all([self.note, self.item])
        db.session.flush()
        self.install = DeckInstall(deck_item_id=self.item.id, user_id=self.learner.id,
            local_deck_id=self.local.id, source_deck_id=self.source.id, source_note_type_id=self.nt.id,
            source_owner_user_id=self.author.id, clone_mode="logical_overlay")
        db.session.add(self.install)
        db.session.flush()
        db.session.add(DeckCloneDeckMap(deck_install_id=self.install.id,
            source_deck_id=self.source.id, local_deck_id=self.local.id))
        with published_base_write():
            self.note.published_at = datetime.utcnow()
            db.session.flush()
        db.session.commit()

    def override(self, *, operation="set", value="personal"):
        row = DeckCloneNoteFieldOverride(deck_install_id=self.install.id, source_note_id=self.note.id,
            source_field_def_id=self.word.id, field_identity_key=self.word.id,
            field_name="Word", operation=operation, value=value)
        db.session.add(row)
        db.session.commit()
        return row

    def test_learner_reads_published_labels_and_values_without_draft_property(self):
        self.note.field_values = {"Word": "secret", "Array": ["secret"]}
        db.session.commit()
        self.word.name = "Unpublished rename"
        db.session.commit()
        with patch("app.services.field_value_runtime_service.read_note_named_values",
                   side_effect=AssertionError("Learner cannot read author property")):
            values = published_note_values_for_ids(self.install, [self.note.id])
            self.assertEqual(values[self.note.id], {"Word": "base", "Array": ["array", ["nested"]]})
            view = build_clone_schema_view(install=self.install, source_note_type_id=self.nt.id)
            self.assertEqual([field.name for field in view.field_defs], ["Word", "Array"])
            self.assertEqual(apply_clone_note_field_overrides(install=self.install,
                source_note=self.note, schema_view=view), values[self.note.id])

    def test_new_and_deleted_source_notes_are_invisible_but_local_notes_remain(self):
        unpublished = Note(user_id=self.author.id, note_type_id=self.nt.id,
            deck_id=self.source.id, field_values={"Word": "unpublished"})
        local = Note(user_id=self.learner.id, note_type_id=self.nt.id,
            deck_id=self.local.id, field_values={"Word": "local"})
        db.session.add_all([unpublished, local])
        db.session.flush()
        db.session.add(DeckCloneAddedNote(deck_install_id=self.install.id, note_id=local.id))
        db.session.commit()
        self.assertEqual(set(published_note_values_for_ids(self.install,
            [self.note.id, unpublished.id, local.id])), {self.note.id})
        with published_base_write():
            self.note.deleted_at = datetime.utcnow()
            db.session.flush()
        db.session.commit()
        self.assertEqual(published_note_values_for_ids(self.install, [self.note.id]), {})
        self.assertIsNotNone(db.session.get(Note, local.id))

    def test_personal_override_and_remove_have_effective_sql_semantics(self):
        self.note.field_values = {"Word": "secret", "Array": []}
        db.session.commit()
        row = self.override()
        expression = clone_effective_field_text_expression(deck_install_id=self.install.id,
            deck_item_id=self.item.id, target_release_sequence=1, source_field_def_id=self.word.id,
            checkpoint_field_name="Word", field_identity_key=self.word.id)
        self.assertEqual(db.session.execute(select(expression).where(Note.id == self.note.id)).scalar_one(), "personal")
        specs = [{"source_field_id": self.word.id, "identity_key": self.word.id, "checkpoint_name": "Word"}]
        def matches(term):
            statement = clone_note_search_ids(scope_condition=Note.id == self.note.id,
                field_specs=specs, deck_install_id=self.install.id, deck_item_id=self.item.id,
                target_sequence=1, keyword_like=f"%{term}%")
            return list(db.session.execute(statement).scalars())
        self.assertEqual(matches("personal"), [self.note.id])
        self.assertEqual(matches("base"), [])
        self.assertEqual(matches("secret"), [])
        row.operation, row.value = "remove", None
        db.session.commit()
        self.assertEqual(db.session.execute(select(expression).where(Note.id == self.note.id)).scalar_one(), "")
        self.assertEqual(matches("personal"), [])

    def test_publish_changes_base_without_overwriting_personal_field(self):
        row = self.override()
        with published_base_write():
            self.note.field_values = {"Word": "latest base", "Array": ["latest", ["nested"]]}
            db.session.flush()
        db.session.commit()
        schema = build_clone_schema_view(install=self.install, source_note_type_id=self.nt.id)
        values = apply_clone_note_field_overrides(install=self.install, source_note=self.note, schema_view=schema)
        self.assertEqual(values, {"Word": "personal", "Array": ["latest", ["nested"]]})
        db.session.delete(row)
        db.session.commit()
        self.assertEqual(apply_clone_note_field_overrides(install=self.install,
            source_note=self.note, schema_view=schema)["Word"], "latest base")

    def test_deleted_field_snapshot_hides_identity_and_retains_override(self):
        row = self.override()
        db.session.delete(self.word)
        db.session.commit()
        # Author deletion is still unpublished, so learner keeps the old schema.
        schema = build_clone_schema_view(install=self.install, source_note_type_id=self.nt.id)
        self.assertIn("Word", [field.name for field in schema.field_defs])
        snapshot = dict(self.item.published_schema_json)
        snapshot[self.word.id] = {**snapshot[self.word.id], "deleted_at": datetime.utcnow().isoformat()}
        self.item.published_schema_json = snapshot
        db.session.commit()
        schema = build_clone_schema_view(install=self.install, source_note_type_id=self.nt.id)
        self.assertNotIn("Word", [field.name for field in schema.field_defs])
        self.assertNotIn("Word", apply_clone_note_field_overrides(install=self.install,
            source_note=self.note, schema_view=schema))
        self.assertIsNotNone(db.session.get(DeckCloneNoteFieldOverride, row.id))

    def test_author_search_sort_and_delete_read_drafts(self):
        self.note.field_values = {"Word": "draft", "Array": ["new leaf"]}
        db.session.commit()
        self.assertEqual(db.session.execute(select(note_field_text_expression(self.word.id))
            .where(Note.id == self.note.id)).scalar_one(), "draft")
        self.assertEqual(list(db.session.execute(select(Note.id).where(
            note_values_search_condition(keyword_like="%new leaf%"))).scalars()), [self.note.id])
        stage_note_delete(self.note)
        db.session.commit()
        self.assertEqual(list(db.session.execute(select(Note.id).where(author_note_visible())).scalars()), [])
        self.assertEqual(published_note_values_for_ids(self.install, [self.note.id])[self.note.id]["Word"], "base")

    def test_new_source_branches_inherit_nearest_map_without_writing_folders(self):
        child = Deck(owner_user_id=self.author.id, note_type_id=self.nt.id, name="New child", parent_id=self.source.id)
        db.session.add(child)
        db.session.flush()
        grandchild = Deck(owner_user_id=self.author.id, note_type_id=self.nt.id, name="New grandchild", parent_id=child.id)
        db.session.add(grandchild)
        db.session.flush()
        with published_base_write():
            self.note.deck_id = grandchild.id
            db.session.flush()
        db.session.commit()
        before = Deck.query.filter_by(owner_user_id=self.learner.id).count()
        mapping = expanded_source_deck_mapping(self.install)
        self.assertEqual(mapping[grandchild.id], self.local.id)
        scope = resolve_clone_scope_for_local_deck(user_id=self.learner.id, local_deck_id=self.local.id)
        self.assertIn(grandchild.id, scope.source_deck_ids)
        statement = select(Note.id, DeckCloneDeckMap.local_deck_id).join(DeckCloneDeckMap,
            source_deck_map_condition(user_id=self.learner.id)).where(Note.id == self.note.id)
        self.assertEqual(list(db.session.execute(statement)), [(self.note.id, self.local.id)])
        self.assertEqual(Deck.query.filter_by(owner_user_id=self.learner.id).count(), before)

    def test_browse_search_and_detail_share_effective_base_values(self):
        from app.services.browse_note_service import list_notes, get_note_detail
        self.note.field_values = {"Word": "secret", "Array": []}
        db.session.commit()
        self.override()
        def browse(term):
            return list_notes(user_id=self.learner.id, admin_mode=False, timezone_name="UTC",
                query_args={"deck_id": str(self.local.id), "q": term, "sort_by": "word", "per_page": "1"})
        visible = browse("personal")
        self.assertEqual(visible["total"], 1)
        self.assertEqual(visible["items"][0]["word"], "personal")
        self.assertEqual(browse("secret")["total"], 0)
        self.assertEqual(browse("base")["total"], 0)
        detail = get_note_detail(user_id=self.learner.id, admin_mode=False, timezone_name="UTC",
            note_id=self.note.id, compact=True)
        self.assertEqual(detail["note"]["field_values"]["Word"], "personal")
        self.assertEqual(detail["note"]["field_values"]["Array"], ["array", ["nested"]])

    def test_browse_marks_changed_base_without_overwriting_personal_value(self):
        from app.services.browse_note_service import list_notes
        from app.services.note_base_comparison_service import base_value_hash
        row = self.override()
        row.base_hash = base_value_hash("base", exists=True)
        db.session.commit()
        with published_base_write():
            self.note.field_values = {"Word": "new published word", "Array": ["array", ["nested"]]}
            db.session.flush()
        db.session.commit()
        result = list_notes(user_id=self.learner.id, admin_mode=False, timezone_name="UTC",
            query_args={"deck_id": str(self.local.id), "per_page": "20"})
        self.assertEqual(result["items"][0]["word"], "personal")
        self.assertTrue(result["items"][0]["base_changed"])

    def test_author_browse_uses_draft_fields_tags_and_deck(self):
        from app.services.browse_note_service import list_notes, get_note_detail
        child = Deck(owner_user_id=self.author.id, note_type_id=self.nt.id, name="Draft destination", parent_id=self.source.id)
        db.session.add(child)
        db.session.commit()
        self.note.field_values = {"Word": "author draft", "Array": []}
        self.note.tags, self.note.deck_id = ["draft tag"], child.id
        db.session.commit()
        result = list_notes(user_id=self.author.id, admin_mode=False, timezone_name="UTC",
            query_args={"deck_id": str(child.id), "include_subdecks": "false", "q": "author draft", "tag": "draft tag"})
        self.assertEqual(result["total"], 1)
        self.assertEqual(result["items"][0]["tags"], ["draft tag"])
        self.assertEqual(result["items"][0]["deck_id"], child.id)
        detail = get_note_detail(user_id=self.author.id, admin_mode=False, timezone_name="UTC",
            note_id=self.note.id, compact=True)
        self.assertEqual(detail["note"]["deck_id"], child.id)

    def test_author_delete_draft_invalidates_only_author_cached_counts(self):
        from app.repositories.deck_count_snapshot_repository import read_revision_vectors
        from app.services.note_draft_service import stage_note_delete
        with patch.dict(self.app.config, {"DECK_COUNT_WRITE_ENABLED": True}):
            owner_before = read_revision_vectors(db.session, user_id=self.author.id, deck_ids=[self.source.id])
            learner_before = read_revision_vectors(db.session, user_id=self.learner.id, deck_ids=[self.source.id])
            revision = self.note.content_revision
            stage_note_delete(self.note)
            db.session.commit()
            owner_after = read_revision_vectors(db.session, user_id=self.author.id, deck_ids=[self.source.id])
            learner_after = read_revision_vectors(db.session, user_id=self.learner.id, deck_ids=[self.source.id])
            self.assertNotEqual(owner_before, owner_after)
            self.assertEqual(learner_before, learner_after)
            self.assertEqual(self.note.content_revision, revision)

    def test_keep_personal_value_checks_current_base_and_clears_changed_marker(self):
        from app.services.note_base_comparison_service import (
            base_value_hash, compare_overrides, keep_override, overrides_base_changed,
        )
        from app.services.deck_install_rebase_service import DeckInstallUpdateError
        row = self.override()
        row.base_hash = base_value_hash("earlier", exists=True)
        db.session.commit()
        page = compare_overrides(install_id=self.install.id, user_id=self.learner.id)
        self.assertTrue(page["items"][0]["base_changed"])
        with published_base_write():
            self.note.field_values = {"Word": "new Base", "Array": []}
            db.session.flush()
        db.session.commit()
        with self.assertRaises(DeckInstallUpdateError) as rejected:
            keep_override(install_id=self.install.id, override_id=row.id, user_id=self.learner.id,
                expected_overlay_revision=page["overlay_revision"],
                expected_base_hash=page["items"][0]["current_base_hash"])
        self.assertEqual(rejected.exception.error, "BASE_REVISION_STALE")
        fresh = compare_overrides(install_id=self.install.id, user_id=self.learner.id)
        keep_override(install_id=self.install.id, override_id=row.id, user_id=self.learner.id,
            expected_overlay_revision=fresh["overlay_revision"],
            expected_base_hash=fresh["items"][0]["current_base_hash"])
        current = compare_overrides(install_id=self.install.id, user_id=self.learner.id)
        self.assertFalse(current["items"][0]["base_changed"])
        self.assertEqual(current["items"][0]["personal_value"], "personal")
        self.assertEqual(self.note.field_values_by_id[self.word.id], "new Base")
        # A stale observation also needs no marker when Base now equals the edit.
        row.base_hash, row.value = base_value_hash("earlier", exists=True), "new Base"
        db.session.commit()
        self.assertFalse(compare_overrides(install_id=self.install.id, user_id=self.learner.id)["items"][0]["base_changed"])
        self.assertFalse(overrides_base_changed(self.install, {"Word": "new Base"}, [row]))

    def test_author_search_uses_retained_extra_deltas_without_base_false_positives(self):
        from app.services.note_base_context import base_maintenance
        with base_maintenance("Synthetic test extra fixture"):
            self.note.field_values = {"Word": "base", "Extra": {"old": "obsolete extra"}}
            db.session.flush()
        db.session.commit()
        self.note.field_values = {"Word": "draft", "Extra": {"new": "fresh extra"}, "Added": ["new extra"]}
        db.session.commit()
        def matches(term):
            return list(db.session.execute(select(Note.id).where(
                note_values_search_condition(keyword_like=f"%{term}%"))).scalars())
        self.assertEqual(matches("fresh extra"), [self.note.id])
        self.assertEqual(matches("new extra"), [self.note.id])
        self.assertEqual(matches("obsolete extra"), [])
        self.note.field_values = {"Word": "draft"}
        db.session.commit()
        self.assertEqual(matches("fresh extra"), [])
        self.assertEqual(matches("obsolete extra"), [])
