"""Note Browse on disposable local MySQL; no presentation expansion."""

import os
import unittest
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from app.services import browse_card_service, browse_note_service
from models import db
from models.note import Note
from models.study_application import StudyApplication
from models.field_def import FieldDef
from models.study_progress_subject import StudyProgressSubject
from tests import test_browse_query_bounds as fixtures
from tests import test_browse_mysql_contract as mysql_harness


@unittest.skipUnless(os.getenv("FLAMA_BROWSE_MYSQL_TESTS") == "1", "Opt-in local MySQL qualification")
class BrowseNotesMySQLTests(unittest.TestCase):
    setUp = mysql_harness.BrowseMySQLContractTests.setUp

    def _notes(self, **args):
        with self.app.test_request_context('/api/browse/notes?view=rows'), fixtures.StatementCounter() as capture:
            result = browse_note_service.list_notes(user_id=self.learner_id, admin_mode=False,
                timezone_name='UTC', query_args=args)
        return result, capture

    def test_owned_notes_without_active_templates_can_list_read_and_edit(self):
        deck_id = fixtures.seed_owned_deck(self.learner_id, count=4)
        StudyApplication.query.update({'status_code': 'RETIRED'})
        db.session.commit()
        page, capture = self._notes(deck_id=deck_id)
        self.assertEqual(page['total'], 4)
        self.assertEqual(len(page['items']), 4)
        for statement in capture.statements:
            lowered = statement.lower()
            self.assertNotIn('study_applications', lowered)
            self.assertNotIn('card_presentations', lowered)
            self.assertNotIn(' templates', lowered)
            self.assertNotIn('row_number', lowered)
        row = page['items'][0]
        self.assertNotIn('card_id', row)
        self.assertNotIn('template', row)
        with self.app.test_request_context('/api/browse/decks?view=notes'), fixtures.StatementCounter() as counts_sql:
            decks = browse_note_service.build_decks(user_id=self.learner_id, admin_mode=False, timezone_name='UTC')
        self.assertEqual(next(d for d in decks['decks'] if d['id'] == deck_id)['counts']['total'], 4)
        self.assertFalse(any('study_applications' in sql.lower() or 'card_presentations' in sql.lower() for sql in counts_sql.statements))
        detail = browse_note_service.get_note_detail(user_id=self.learner_id, admin_mode=False,
            timezone_name='UTC', note_id=row['note_id'])
        self.assertEqual(detail['note']['id'], row['note_id'])
        self.assertNotIn('card', detail)
        response = browse_note_service.update_note(user_id=self.learner_id, admin_mode=False,
            timezone_name='UTC', note_id=row['note_id'], payload={'field_values': {'Word': 'changed'}})
        self.assertEqual(response['detail']['note']['field_values']['Word'], 'changed')
        db.session.add(FieldDef(note_type_id=detail['note']['note_type_id'], name='Audio', field_type='audio', position=3))
        db.session.commit()
        from app.services import browse_voicevox_service, flashcard_audio_scan_service
        with fixtures.StatementCounter() as audio_sql, TemporaryDirectory() as media_root:
            check = browse_voicevox_service.precheck_voicevox(user_id=self.learner_id, admin_mode=False,
                payload={'note_ids': [row['note_id']], 'destination_field': 'Audio'})
            scan = flashcard_audio_scan_service.scan_deck_audio(user_id=self.learner_id, admin_mode=False,
                deck_id=deck_id, upload_root=Path(media_root), note_only=True)
        self.assertEqual(check['note_type_count'], 1)
        self.assertEqual(len(scan['notes']), 4)
        self.assertFalse(any('study_applications' in sql.lower() or 'card_presentations' in sql.lower() for sql in audio_sql.statements))

    def test_multiple_applications_never_multiply_note_total(self):
        fixtures.seed_owned_deck(self.learner_id, count=6)
        application = StudyApplication.query.first()
        fixtures.attach_template(db.session, note_type_id=application.note_type_id,
            owner_user_id=self.learner_id, name='Another', front_html='{{Word}}', back_html='{{Meaning}}')
        db.session.commit()
        first, _ = self._notes(per_page=2)
        second, _ = self._notes(per_page=2, page=2)
        self.assertEqual(first['total'], 6)
        self.assertEqual(first['pages'], 3)
        self.assertFalse({r['note_id'] for r in first['items']} & {r['note_id'] for r in second['items']})

    def test_release_clone_values_and_search_are_pinned(self):
        self._assert_clone_values(release=True)

    def test_snapshot_clone_values_and_search_are_pinned(self):
        self._assert_clone_values(release=False)

    def test_clone_search_values_preserve_clears_and_pinned_release_history(self):
        from app.repositories.browse_card_repository import clone_effective_field_text_expression
        from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
        from models.deck_install import DeckInstall
        from models.deck_release import DeckRelease
        from models.deck_release_change import DeckReleaseChange

        ids = fixtures.seed_clone_install(self.learner_id, count=9, release=True, override_every=0)
        install = db.session.get(DeckInstall, ids['install_id'])
        word_id = ids['word_field_id']
        releases = []
        for sequence in (2, 3):
            release = DeckRelease(deck_item_id=install.deck_item_id, sequence_no=sequence,
                version_label=f'{sequence}.0.0', status='published', created_by_user_id=install.source_owner_user_id)
            db.session.add(release)
            db.session.flush()
            releases.append(release)
        install.applied_release_id = releases[0].id
        changes = [(1, 'set', None), (2, 'set', ''), (3, 'remove', 'ignored'),
            (4, 'set', [['nested', 'values'], 'last']), (5, 'set', 'release-value'),
            (6, 'set', 'release-value'), (7, 'set', None), (8, 'set', 'legacy-identity')]
        for index, operation, value in changes:
            db.session.add(DeckReleaseChange(release_id=releases[0].id, release_sequence_no=2,
                change_key=f'note:{index}:word', entity_kind='note_field', entity_id=ids['note_ids'][index],
                field_def_id=None if index == 8 else word_id, property_key=f'field:{word_id}',
                operation=operation, after_value=value))
        # A newer published value must not leak into an install pinned to v2.
        db.session.add(DeckReleaseChange(release_id=releases[1].id, release_sequence_no=3,
            change_key='future-word', entity_kind='note_field', entity_id=ids['note_ids'][0],
            field_def_id=word_id, property_key=f'field:{word_id}', operation='set', after_value='future-value'))
        for index, operation, value in ((5, 'set', None), (6, 'remove', None), (7, 'set', 'local-value')):
            db.session.add(DeckCloneNoteFieldOverride(deck_install_id=install.id,
                source_note_id=ids['note_ids'][index], source_field_def_id=word_id,
                field_identity_key=word_id, field_name='Word', operation=operation, value=value))
        db.session.commit()
        expression = clone_effective_field_text_expression(deck_install_id=install.id,
            deck_item_id=install.deck_item_id, target_release_sequence=2,
            source_field_def_id=word_id, checkpoint_field_name='Word', field_identity_key=word_id)
        values = dict(db.session.query(Note.id, expression).filter(Note.id.in_(ids['note_ids'])).all())
        self.assertEqual(values[ids['note_ids'][0]], 'pinned-word-000001')
        for index in (1, 2, 3, 5, 6):
            self.assertEqual(values[ids['note_ids'][index]], '', f'cleared field {index} fell back to base')
        self.assertEqual(json.loads(values[ids['note_ids'][4]]), [['nested', 'values'], 'last'])
        self.assertEqual(values[ids['note_ids'][7]], 'local-value')
        self.assertEqual(values[ids['note_ids'][8]], 'legacy-identity')

        snapshot = fixtures.seed_clone_install(self.learner_id, count=4, release=False,
            override_every=0, prefix='50000000')
        for index, operation, value in ((1, 'set', None), (2, 'set', ''), (3, 'remove', None)):
            db.session.add(DeckCloneNoteFieldOverride(deck_install_id=snapshot['install_id'],
                source_note_id=snapshot['note_ids'][index], source_field_def_id=snapshot['word_field_id'],
                field_identity_key=snapshot['word_field_id'], field_name='Word', operation=operation, value=value))
        db.session.commit()
        expression = clone_effective_field_text_expression(deck_install_id=snapshot['install_id'],
            deck_item_id=None, target_release_sequence=None, source_field_def_id=snapshot['word_field_id'],
            checkpoint_field_name='Word', field_identity_key=snapshot['word_field_id'])
        values = dict(db.session.query(Note.id, expression).filter(Note.id.in_(snapshot['note_ids'])).all())
        self.assertEqual([values[note_id] for note_id in snapshot['note_ids']], ['w000001', '', '', ''])

    def test_no_search_matches_return_empty_pagination_without_loading_a_page(self):
        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=True)
        page, capture = self._notes(deck_id=ids['local_root_id'], q='no-matching-note', page=7, per_page=20)
        self.assertEqual(page, {'items': [], 'page': 7, 'per_page': 20,
            'total': 0, 'pages': 0, 'has_next': False})
        note_page_reads = [sql for sql in capture.statements if 'from notes' in sql.lower()
            and 'limit' in sql.lower() and not sql.lstrip().lower().startswith('select count(')]
        self.assertEqual(note_page_reads, [], 'An empty result should not repeat the search to fetch a page')

    def _assert_clone_values(self, *, release):
        ids = fixtures.seed_clone_install(self.learner_id, count=4, release=release, prefix='40000000' if release else '30000000')
        page, _ = self._notes(deck_id=ids['local_root_id'])
        self.assertEqual(page['total'], 4)
        note_id = page['items'][0]['note_id']
        detail = browse_note_service.get_note_detail(user_id=self.learner_id, admin_mode=False,
            timezone_name='UTC', note_id=note_id)
        self.assertIn(detail['note']['deck_id'], [ids['local_root_id'], ids['local_child_id']])
        self.assertFalse(detail['can_upload_media'])
        with self.app.test_request_context('/api/browse/decks?view=notes'):
            decks = browse_note_service.build_decks(user_id=self.learner_id, admin_mode=False, timezone_name='UTC')
        self.assertEqual(next(d for d in decks['decks'] if d['id'] == ids['local_root_id'])['counts']['total'], 4)
        value = detail['note']['field_values']['Word']
        found, _ = self._notes(deck_id=ids['local_root_id'], q=value)
        self.assertIn(note_id, {r['note_id'] for r in found['items']})
        original = dict(db.session.get(Note, note_id).field_values_by_id)
        from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
        meaning = FieldDef.query.filter_by(note_type_id=detail['note']['note_type_id'], name='Meaning').first()
        db.session.add(DeckCloneFieldDefOverride(deck_install_id=detail['note']['deck_install_id'],
            source_field_def_id=meaning.id, properties={'name': 'Answers', 'field_type': 'array'}))
        db.session.commit()
        response = browse_note_service.update_note(user_id=self.learner_id, admin_mode=False,
            timezone_name='UTC', note_id=note_id, payload={'field_values': {'Word': 'local-only', 'Answers': [['one', 'two'], 'three']}})
        self.assertEqual(response['detail']['note']['field_values']['Word'], 'local-only')
        self.assertEqual(response['detail']['note']['field_values']['Answers'], [['one', 'two'], 'three'])
        self.assertEqual(db.session.get(Note, note_id).field_values_by_id, original)
        selected = browse_note_service.selected_note_values(user_id=self.learner_id, admin_mode=False,
            timezone_name='UTC', note_ids=[note_id])
        self.assertEqual(selected[0].field_values['Answers'], [['one', 'two'], 'three'])
        from app.services.worksheets.worksheet_service import generate_worksheet_preview
        preview = generate_worksheet_preview(user_id=self.learner_id, payload={
            'deck_id': ids['local_root_id'], 'note_ids': [note_id], 'template_id': 'deck_table',
            'field_mapping': {'custom_columns': ['Word', 'Answers']}, 'options': {}})
        self.assertGreater(preview['total_pages'], 0)
        self.assertIn('local-only', json.dumps(preview, ensure_ascii=False))

    def test_note_page_still_rejects_divergent_progress(self):
        fixtures.seed_owned_deck(self.learner_id, count=4)
        subject = StudyProgressSubject.query.filter(StudyProgressSubject.semantic_state_hash.isnot(None)).first()
        subject.normalized_queue = 'new'
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._notes()
        self.assertEqual(caught.exception.status, 409)

    def test_note_http_resources_keep_validation_and_revisions(self):
        from app.api import register_api_blueprints
        register_api_blueprints(self.app)
        fixtures.seed_owned_deck(self.learner_id, count=2)
        note = Note.query.filter_by(user_id=self.learner_id).first()
        client = self.app.test_client()
        with client.session_transaction() as session:
            session['_user_id'] = str(self.learner_id)
            session['_fresh'] = True
        listing = client.get('/api/browse/notes?view=rows').get_json()
        self.assertEqual(listing['total'], 2)
        detail = client.get(f'/api/browse/notes/{note.id}').get_json()
        token = client.get('/api/session').get_json()['csrf_token']
        headers = {'X-CSRF-Token': token}
        payload = {'field_values': {'Word': 'from-http'},
            'expected_content_revision': detail['note']['content_revision'],
            'expected_field_schema_revision': detail['note']['field_schema_revision']}
        saved = client.patch(f'/api/browse/notes/{note.id}?view=rows', json=payload, headers=headers)
        self.assertEqual(saved.status_code, 200, saved.get_json())
        self.assertEqual(saved.get_json()['detail']['note']['field_values']['Word'], 'from-http')
        stale = client.patch(f'/api/browse/notes/{note.id}?view=rows', json=payload, headers=headers)
        self.assertEqual(stale.status_code, 409, stale.get_json())

    def test_unauthorized_note_is_not_readable(self):
        stranger = fixtures.seed_learner(username='stranger')
        deck_id = fixtures.seed_owned_deck(stranger, count=2)
        note = Note.query.filter_by(deck_id=deck_id).first()
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            browse_note_service.get_note_detail(user_id=self.learner_id, admin_mode=False,
                timezone_name='UTC', note_id=note.id)
        self.assertEqual(caught.exception.status, 404)
        with self.assertRaises(browse_card_service.BrowseApiError):
            browse_note_service.selected_note_values(user_id=self.learner_id, admin_mode=False,
                timezone_name='UTC', note_ids=[note.id])
