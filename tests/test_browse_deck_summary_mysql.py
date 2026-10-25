"""Progressive Browse structure/summary parity on disposable local MySQL."""

import os
import unittest
from unittest.mock import patch

from app.services import browse_card_service, browse_deck_service, browse_note_service
from app.validators.browse_decks import validate_deck_summary_ids, validate_structure_only
from app.validators import RequestValidationError
from models import db
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from tests import test_browse_query_bounds as fixtures
from tests import test_browse_mysql_contract as mysql_harness


@unittest.skipUnless(os.getenv("FLAMA_BROWSE_MYSQL_TESTS") == "1", "Opt-in local MySQL qualification")
class BrowseDeckSummaryMySQLTests(unittest.TestCase):
    setUp = mysql_harness.BrowseMySQLContractTests.setUp

    def _full(self, admin=False):
        with self.app.test_request_context('/api/browse/decks?view=notes'):
            return browse_note_service.build_decks(user_id=self.learner_id,
                admin_mode=admin, timezone_name='UTC')['decks']

    def _summary(self, ids, admin=False):
        with self.app.test_request_context('/api/browse/decks/summaries'):
            return browse_deck_service.build_summaries(user_id=self.learner_id,
                admin_mode=admin, timezone_name='UTC', deck_ids=tuple(ids))['decks']

    def _assert_parity(self, ids, admin=False):
        full = {row['id']: row for row in self._full(admin)}
        summaries = self._summary(ids, admin)
        self.assertEqual([row['id'] for row in summaries], ids)
        for row in summaries:
            self.assertTrue(row['summary_loaded'])
            expected = {key: value for key, value in full[row['id']].items() if key != 'path'}
            self.assertEqual({key: value for key, value in row.items() if key != 'summary_loaded'}, expected)

    def test_structure_preserves_tree_without_counters_or_note_type_distribution(self):
        fixtures.seed_owned_deck(self.learner_id, count=8)
        fixtures.seed_clone_install(self.learner_id, count=6, release=True)
        full = self._full()
        with self.app.test_request_context('/api/browse/decks?view=notes&structure_only=1'), fixtures.StatementCounter() as sql, \
                patch.object(browse_note_service.repository, 'deck_counts', side_effect=AssertionError('No aggregate for structure')):
            structure = browse_deck_service.build_structure(user_id=self.learner_id, admin_mode=False)['decks']
        self.assertEqual(structure, [{**{key: row[key] for key in ('id', 'name', 'parent_id', 'path')},
            'summary_loaded': False} for row in full])
        self.assertFalse(any('count(' in statement.lower() for statement in sql.statements))
        self.assertFalse(any('notes_note_type_id' in statement.lower() for statement in sql.statements))
        self.assertFalse(any('field_values' in statement.lower() for statement in sql.statements))

    def test_owned_overlapping_roots_keep_rollups_and_mixed_type_metadata(self):
        root = fixtures.seed_owned_deck(self.learner_id, count=8)
        child = Deck.query.filter_by(parent_id=root).one()
        other = NoteType(user_id=self.learner_id, name='Second type')
        db.session.add(other)
        db.session.flush()
        note = Note.query.filter_by(deck_id=child.id).first()
        note.field_values_by_id = {}
        note.note_type_id = other.id
        db.session.commit()
        self._assert_parity([root, child.id])
        summary = self._summary([root])[0]
        self.assertEqual(summary['counts']['total'], 8)
        self.assertTrue(summary['has_mixed_note_types'])

    def test_release_clone_and_snapshot_summaries_match_full_sidebar(self):
        release = fixtures.seed_clone_install(self.learner_id, count=8, release=True)
        snapshot = fixtures.seed_clone_install(self.learner_id, count=6, release=False, prefix='50000000')
        self._assert_parity([release['local_root_id'], release['local_child_id'], snapshot['local_root_id']])

    def test_small_summary_does_not_query_other_owned_subtrees(self):
        root = fixtures.seed_owned_deck(self.learner_id, count=8)
        unrelated = Deck(name='Unrelated', owner_user_id=self.learner_id)
        db.session.add(unrelated)
        db.session.commit()
        with patch.object(browse_card_service.vocabulary_ctrl, 'collect_accessible_browse_decks',
                side_effect=AssertionError('Owned summary needs no collection resolver')):
            row = self._summary([root])[0]
        self.assertEqual(row['counts']['total'], 8)

    def test_admin_summary_prunes_foreign_branches_like_full_sidebar(self):
        root = fixtures.seed_owned_deck(self.learner_id, count=4)
        foreign_owner = fixtures.seed_learner(username='foreign-summary-owner')
        foreign = Deck(name='Foreign branch', owner_user_id=foreign_owner, parent_id=root)
        db.session.add(foreign)
        db.session.flush()
        hidden = Deck(name='Hidden behind foreign', owner_user_id=self.learner_id, parent_id=foreign.id)
        unowned = Deck(name='Unowned branch', owner_user_id=None, parent_id=root)
        db.session.add_all([hidden, unowned])
        db.session.commit()
        self._assert_parity([root, unowned.id], admin=True)
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._summary([foreign.id], admin=True)
        self.assertEqual(caught.exception.status, 404)

    def test_inaccessible_batch_fails_without_partial_summary(self):
        root = fixtures.seed_owned_deck(self.learner_id, count=4)
        other = fixtures.seed_learner(username='private-summary-owner')
        private = Deck(name='Private folder', owner_user_id=other)
        db.session.add(private)
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._summary([root, private.id])
        self.assertEqual(caught.exception.status, 404)

    def test_http_contract_validation_and_legacy_response(self):
        from app.api import register_api_blueprints
        register_api_blueprints(self.app)
        root = fixtures.seed_owned_deck(self.learner_id, count=4)
        client = self.app.test_client()
        self.assertEqual(client.get(f'/api/browse/decks/summaries?deck_ids={root}').status_code, 401)
        with client.session_transaction() as session:
            session['_user_id'] = str(self.learner_id)
            session['_fresh'] = True
        # This fixture keeps one outer app context across client requests.
        from flask import g
        g.pop('_login_user', None)
        structure = client.get('/api/browse/decks?view=notes&structure_only=1')
        self.assertEqual(structure.status_code, 200, structure.get_json())
        self.assertTrue(all(row['summary_loaded'] is False for row in structure.get_json()['decks']))
        summary = client.get(f'/api/browse/decks/summaries?deck_ids={root}')
        self.assertEqual(summary.status_code, 200, summary.get_json())
        self.assertEqual(summary.get_json()['decks'][0]['counts']['total'], 4)
        legacy = client.get('/api/browse/decks?view=notes')
        self.assertEqual(legacy.status_code, 200)
        self.assertTrue(all('counts' in row and 'summary_loaded' not in row for row in legacy.get_json()['decks']))
        for suffix in ('', '?deck_ids=0', '?deck_ids=a', '?deck_ids=1,', '?deck_ids=' + ','.join(map(str, range(1, 52)))):
            self.assertEqual(client.get('/api/browse/decks/summaries' + suffix).status_code, 400)
        self.assertEqual(client.get('/api/browse/decks?view=notes&structure_only=invalid').status_code, 400)


class BrowseDeckInputTests(unittest.TestCase):
    def test_bounded_inputs(self):
        self.assertEqual(validate_deck_summary_ids(' 12,13,12 '), (12, 13))
        for value in ('', '-1', '0', '1.2', '1,', '999999999999999999999', '１２'):
            with self.subTest(value=value), self.assertRaises(RequestValidationError):
                validate_deck_summary_ids(value)
        self.assertTrue(validate_structure_only('true'))
        self.assertFalse(validate_structure_only(None))


if __name__ == '__main__':
    unittest.main()
