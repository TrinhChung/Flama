"""Structural Browse search regressions on disposable local MySQL schemas."""

from datetime import timedelta
import os
import re
import unittest
from unittest.mock import patch

from sqlalchemy import insert

from app.repositories import browse_note_repository
from app.services import browse_card_service, browse_note_service
from models import db
from models.deck import Deck
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_change import DeckReleaseChange
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_release_note_checkpoint import DeckReleaseNoteCheckpoint
from models.field_def import FieldDef
from models.note import Note
from tests import test_browse_query_bounds as fixtures
from tests import test_browse_mysql_contract as mysql_harness


@unittest.skipUnless(os.getenv('FLAMA_BROWSE_MYSQL_TESTS') == '1', 'Opt-in local MySQL qualification')
class BrowseSearchMySQLTests(unittest.TestCase):
    setUp = mysql_harness.BrowseMySQLContractTests.setUp

    def _notes(self, **args):
        with self.app.test_request_context('/api/browse/notes'), fixtures.StatementCounter() as sql:
            result = browse_note_service.list_notes(user_id=self.learner_id, admin_mode=False,
                timezone_name='UTC', query_args=args)
        return result, sql.statements

    def _legacy_ids(self, **args):
        # The unchanged Card query uses the old per-field scalar expressions.
        # These fixtures have one presentation per Note, so it is an independent
        # SQL oracle for matching, availability and deterministic Note ordering.
        with self.app.test_request_context('/api/browse/cards'):
            context = browse_card_service._build_browse_query(user_id=self.learner_id,
                admin_mode=False, timezone_name='UTC', query_args=args, notes_only=False)
            query = browse_note_repository.order_notes(context, user_id=self.learner_id)
            return [row[0] for row in query.with_entities(Note.id).all()]

    def test_mixed_search_matches_scalar_oracle_for_sort_status_and_empty_pages(self):
        fixtures.seed_owned_deck(self.learner_id, count=8)
        fixtures.seed_clone_install(self.learner_id, count=10, release=True, override_every=0)
        fixtures.seed_clone_install(self.learner_id, count=6, release=False, prefix='40000000', override_every=0)
        cases = [dict(q='w', sort_by=sort, sort_dir=direction)
            for sort in ('due', 'deck', 'word') for direction in ('asc', 'desc')]
        cases += [dict(q='w', status=status) for status in ('new', 'review', 'due', 'learn')]
        cases += [dict(q=needle) for needle in ('%', '_', 'absent-term')]
        for args in cases:
            with self.subTest(args=args):
                expected = self._legacy_ids(**args)
                for page in (1, 2, 99):
                    result, statements = self._notes(**args, page=page, per_page=3)
                    self.assertEqual(result['total'], len(expected))
                    self.assertEqual([row['note_id'] for row in result['items']], expected[(page - 1) * 3:page * 3])
                    self.assertEqual(result['pages'], (len(expected) + 2) // 3)
                    self.assertEqual(result['has_next'], page * 3 < len(expected))
                    self.assertEqual(sum('browse_search_matches' in sql for sql in statements), 1)

    def test_wide_schema_atomic_history_deltas_and_missing_checkpoint(self):
        ids = fixtures.seed_clone_install(self.learner_id, count=300, release=True, override_every=0)
        install = db.session.get(DeckInstall, ids['install_id'])
        initial_id = install.applied_release_id
        extra = [FieldDef(note_type_id=install.source_note_type_id, name=f'Extra {i}',
            field_type='text', position=3 + i) for i in range(20)]
        db.session.add_all(extra)
        db.session.flush()
        for field in extra:
            for key, value in dict(name=field.name, field_type='text', position=field.position, required=False).items():
                db.session.add(DeckReleaseChange(release_id=initial_id, release_sequence_no=1,
                    change_key=f'field:{field.id}:{key}', entity_kind='field_def', entity_id=field.id,
                    field_def_id=field.id, property_key=key, operation='add', after_value=value))
        fields = FieldDef.query.filter_by(note_type_id=install.source_note_type_id).all()
        db.session.execute(insert(DeckReleaseChange), [dict(release_id=initial_id, release_sequence_no=1,
            change_key=f'{note_id}:{field.id}', entity_kind='note_field', entity_id=note_id,
            field_def_id=field.id, property_key=f'field:{field.id}', operation='add', after_value='initial-noise')
            for note_id in ids['note_ids'] for field in fields])
        DeckReleaseNoteCheckpoint.query.filter_by(release_id=initial_id,
            source_note_id=ids['note_ids'][2]).delete()
        release = DeckRelease(deck_item_id=install.deck_item_id, sequence_no=2,
            version_label='2.0.0', status='published', created_by_user_id=install.source_owner_user_id)
        future = DeckRelease(deck_item_id=install.deck_item_id, sequence_no=3,
            version_label='3.0.0', status='published', created_by_user_id=install.source_owner_user_id)
        db.session.add_all([release, future])
        db.session.flush()
        install.applied_release_id = release.id
        word_id = ids['word_field_id']
        for index, operation, value in ((0, 'set', [['nested-delta', 'second'], 'third']), (1, 'remove', None)):
            db.session.add(DeckReleaseChange(release_id=release.id, release_sequence_no=2,
                change_key=f'word:{index}', entity_kind='note_field', entity_id=ids['note_ids'][index],
                field_def_id=word_id, property_key=f'field:{word_id}', operation=operation, after_value=value))
        db.session.add(DeckReleaseChange(release_id=future.id, release_sequence_no=3,
            change_key='future', entity_kind='note_field', entity_id=ids['note_ids'][3],
            field_def_id=word_id, property_key=f'field:{word_id}', operation='set', after_value='future-only'))
        db.session.add(DeckReleaseChange(release_id=release.id, release_sequence_no=2,
            change_key='rename-word', entity_kind='field_def', entity_id=word_id,
            field_def_id=word_id, property_key='name', operation='set', after_value='Renamed word'))
        added = DeckCloneAddedFieldDef(deck_install_id=install.id, name='Added', field_type='array', position=30)
        db.session.add(added)
        db.session.flush()
        db.session.add(DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=ids['note_ids'][4],
            field_identity_key=f'added:{install.id}:{added.id}', field_name='Added', operation='set',
            value=['local-added-only', ['nested']]))
        disabled = extra[0]
        db.session.add(DeckCloneFieldDefOverride(deck_install_id=install.id,
            source_field_def_id=disabled.id, is_disabled=True))
        db.session.add(DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=ids['note_ids'][5],
            source_field_def_id=disabled.id, field_identity_key=disabled.id, field_name=disabled.name,
            operation='set', value='disabled-only'))
        db.session.commit()
        for needle, expected in (
            ('initial-noise', {ids['note_ids'][2]}), ('nested-delta', {ids['note_ids'][0]}),
            ('local-added-only', {ids['note_ids'][4]}), ('future-only', set()), ('disabled-only', set()),
        ):
            with self.subTest(needle=needle):
                result, _ = self._notes(q=needle, per_page=500)
                self.assertEqual({row['note_id'] for row in result['items']}, expected)
                self.assertEqual(set(self._legacy_ids(q=needle)), expected)
        first, small_sql = self._notes(q='pinned', per_page=10)
        larger, larger_sql = self._notes(q='pinned', per_page=150)
        self.assertEqual(first['total'], larger['total'])
        self.assertEqual(first['items'], larger['items'][:10])
        self.assertEqual(len(small_sql), len(larger_sql), 'Search round trips must not grow per Note/field')

    def test_single_note_authorization_keeps_legacy_fallback_and_release_bounds(self):
        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=True, override_every=0)
        install = db.session.get(DeckInstall, ids['install_id'])
        DeckCloneDeckMap.query.filter_by(deck_install_id=install.id).delete()
        db.session.commit()
        common = dict(user_id=self.learner_id, admin_mode=False, timezone_name='UTC',
            note_id=ids['note_ids'][0], compact=True)
        with self.app.test_request_context('/'), patch.object(browse_card_service.vocabulary_ctrl,
                'collect_accessible_browse_decks', side_effect=AssertionError('No collection scan for one Note')):
            self.assertEqual(browse_note_service.get_note_detail(**common)['note']['id'], ids['note_ids'][0])
        membership = DeckReleaseEntityMembership.query.filter_by(deck_item_id=install.deck_item_id,
            entity_kind='note', entity_id=ids['note_ids'][0]).one()
        membership.removed_sequence = 1
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError) as error:
            browse_note_service.get_note_detail(**common)
        self.assertEqual(error.exception.status, 404)
        install.version_mode = 'legacy_snapshot'
        install.applied_release_id = None
        install.base_snapshot_at = fixtures.NOW
        db.session.get(Note, ids['note_ids'][0]).created_at = fixtures.NOW + timedelta(days=1)
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError):
            browse_note_service.get_note_detail(**common)

    def test_overlapping_parent_and_child_installs_keep_scope_precedence(self):
        ids = fixtures.seed_clone_install(self.learner_id, count=6, release=True, override_every=0)
        first = db.session.get(DeckInstall, ids['install_id'])
        item = DeckMarketplaceItem(owner_user_id=first.source_owner_user_id,
            source_deck_id=ids['source_child_id'], source_note_type_id=first.source_note_type_id,
            title='Child listing', publish_status='published', pricing_mode='free')
        local = Deck(name='Separate child install', owner_user_id=self.learner_id)
        db.session.add_all([item, local])
        db.session.flush()
        release = DeckRelease(deck_item_id=item.id, sequence_no=1, version_label='1.0.0',
            status='published', created_by_user_id=first.source_owner_user_id)
        db.session.add(release)
        db.session.flush()
        child_ids = {note.id for note in Note.query.filter_by(deck_id=ids['source_child_id']).all()}
        for change in DeckReleaseChange.query.filter_by(release_id=first.applied_release_id, entity_kind='field_def'):
            db.session.add(DeckReleaseChange(release_id=release.id, release_sequence_no=1,
                change_key=change.change_key, entity_kind='field_def', entity_id=change.entity_id,
                field_def_id=change.field_def_id, property_key=change.property_key,
                operation=change.operation, after_value=change.after_value))
        for checkpoint in DeckReleaseNoteCheckpoint.query.filter_by(release_id=first.applied_release_id):
            if checkpoint.source_note_id not in child_ids:
                continue
            db.session.add(DeckReleaseNoteCheckpoint(release_id=release.id, release_sequence_no=1,
                source_note_id=checkpoint.source_note_id, source_deck_id=ids['source_child_id'],
                note_type_id=checkpoint.note_type_id, field_values=checkpoint.field_values,
                tags=[], content_hash='child-checkpoint'))
            db.session.add(DeckReleaseEntityMembership(deck_item_id=item.id, entity_kind='note',
                entity_id=checkpoint.source_note_id, source_deck_id=ids['source_child_id'], introduced_sequence=1))
        second = DeckInstall(deck_item_id=item.id, user_id=self.learner_id, local_deck_id=local.id,
            clone_mode='logical_overlay', source_deck_id=ids['source_child_id'],
            source_note_type_id=first.source_note_type_id, source_owner_user_id=first.source_owner_user_id,
            version_mode='release', applied_release_id=release.id)
        db.session.add(second)
        db.session.flush()
        db.session.add(DeckCloneDeckMap(deck_install_id=second.id, local_deck_id=local.id,
            source_deck_id=ids['source_child_id']))
        db.session.commit()
        with self.app.test_request_context('/'):
            context = browse_card_service._build_browse_query(user_id=self.learner_id, admin_mode=False,
                timezone_name='UTC', query_args={}, notes_only=True)
        winner = next(scope.install for scope in context.clone_scopes
            if ids['source_child_id'] in scope.source_deck_ids)
        loser = second if winner.id == first.id else first
        note_id = sorted(child_ids)[0]
        db.session.add(DeckCloneNoteFieldOverride(deck_install_id=loser.id, source_note_id=note_id,
            source_field_def_id=ids['word_field_id'], field_identity_key=ids['word_field_id'],
            field_name='Word', operation='set', value='only-other-install'))
        db.session.commit()
        result, _ = self._notes(q='only-other-install')
        self.assertEqual(result['total'], 0)
        self.assertEqual(self._legacy_ids(q='only-other-install'), [])
        whole, _ = self._notes(q='pinned', per_page=100)
        self.assertEqual(whole['total'], 6, 'Overlapping installs must not duplicate Notes')
        detail = browse_note_service.get_note_detail(user_id=self.learner_id, admin_mode=False,
            timezone_name='UTC', note_id=note_id, compact=True)
        self.assertEqual(detail['note']['deck_install_id'], winner.id)
        self.assertNotEqual(detail['note']['field_values']['Word'], 'only-other-install')

    def test_editor_patch_does_not_reload_immutable_schema_events_after_commit(self):
        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=True, override_every=0)
        note_id = ids['note_ids'][0]
        original = dict(db.session.get(Note, note_id).field_values_by_id)
        with self.app.test_request_context('/'), fixtures.StatementCounter() as capture, patch.object(
                browse_card_service.vocabulary_ctrl, 'build_browse_card_detail',
                side_effect=AssertionError('Compact PATCH must not build legacy detail')), patch.object(
                browse_card_service.vocabulary_ctrl, 'collect_accessible_browse_decks',
                side_effect=AssertionError('Compact PATCH needs no collection tree')):
            result = browse_note_service.update_note(user_id=self.learner_id, admin_mode=False,
                timezone_name='UTC', note_id=note_id, compact_detail=True,
                payload={'field_values': {'Word': 'updated-locally'}})
        self.assertEqual(result['detail']['note']['field_values']['Word'], 'updated-locally')
        self.assertNotIn('media_assets', result['detail'])
        self.assertEqual(db.session.get(Note, note_id).field_values_by_id, original)
        self.assertFalse(any(re.search(r'from deck_release_changes\s+where deck_release_changes\.id\s*=',
            statement.lower()) for statement in capture.statements), 'Commit must not trigger per-event history reloads')


if __name__ == '__main__':
    unittest.main()
