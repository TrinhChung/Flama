"""NOTE-only Browse bounds and queue/anchor SQL scheduling contracts."""

from datetime import datetime, timedelta
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from sqlalchemy import event, insert, text

from app import create_app
from app.repositories import study_repository
from app.services import browse_card_service, study_authority_read_service
from app.services.anki_scheduler import CardState
from app.services.study_authority_read_service import (
    StudyAuthorityAvailabilityRead, StudyAuthorityAvailabilitySnapshot,
    summarize_study_authority_queue,
)
from app.services.study_note_card_projection import NoteCardBurial, project_note_state
from app.services.study_progress_contract import ALGORITHM_KEY, ALGORITHM_VERSION, STORAGE_CODEC
from app.services.study_progress_shadow_codec import serialize_card_state
from models import db
from models.card import Card, INCLUDE_RETIRED_CARDS, PresentationAlias
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_subject import StudyProgressSubject
from models.template import Template
from models.user import User
from tests.study_note_fixtures import attach_template


NOW = datetime(2026, 10, 12, 1, 30)
RUNTIME = SimpleNamespace(day_boundary_hour_local=4, learn_ahead_seconds=1200)


class NoteQueryRetirementTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app({
            'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'REDIS_URL': '', 'DECK_COUNT_WRITE_ENABLED': False,
            'REVIEW_ANALYTICS_WRITE_ENABLED': False, 'STUDY_NOTE_COUNT_ENABLED': False,
            'STARTUP_RUN_MAINTENANCE': False, 'STARTUP_CHECK_DB_CONNECTIVITY': False,
            'WTF_CSRF_ENABLED': False,
        })
        self.context = self.app.app_context()
        self.context.push()
        self.addCleanup(self.context.pop)
        self.addCleanup(db.session.remove)
        db.create_all()
        self.addCleanup(db.drop_all)
        self.user = User(username='query-retirement', email='query-retirement@example.test')
        db.session.add(self.user)
        db.session.flush()
        self.deck = Deck(name='Queue', owner_user_id=self.user.id)
        self.note_type = NoteType(name='Queue', user_id=self.user.id)
        db.session.add_all([self.deck, self.note_type])
        db.session.flush()
        db.session.add(FieldDef(note_type_id=self.note_type.id, name='Word', field_type='text', position=0))
        self.template = attach_template(db.session, note_type_id=self.note_type.id, owner_user_id=self.user.id,
                                        name='Front', front_html='{{Word}}', back_html='{{Word}}')
        db.session.add(StudyAuthorityEnrollment(learner_user_id=self.user.id, mode_code='NOTE', epoch=1,
                                                created_at=NOW, updated_at=NOW))
        db.session.add(StudyAuthorityStorageProfile(id=1, profile_code='CONSOLIDATED_V1', epoch=3,
                                                    switched_at=NOW, created_at=NOW, updated_at=NOW))
        db.session.commit()
        self.runtime_patch = patch('app.repositories.study_repository.resolve_scheduler_runtime_settings',
                                   return_value=RUNTIME)
        self.runtime_patch.start()
        self.addCleanup(self.runtime_patch.stop)

    def _add(self, index, queue=None, *, due_at=None, due_day=None, buried=False,
             buried_until=None, suspended=False, status='MIRRORED_SINGLE'):
        note_id = f'10000000-0000-0000-0000-{index:012d}'
        note = Note(id=note_id, user_id=self.user.id, note_type_id=self.note_type.id,
                    deck_id=self.deck.id, field_values={'Word': f'{index:08d}'},
                    created_at=NOW - timedelta(days=2), updated_at=NOW)
        db.session.add(note)
        db.session.flush()
        card = Card.query.filter_by(note_id=note.id).one()
        if queue is not None:
            state = CardState(type=queue, stepIndex=0, due=due_at, dueDay=due_day,
                              intervalDays=1, ease=2.5, reps=1, lapses=0, lastReviewAt=None,
                              suspended=suspended)
            document = serialize_card_state(state)
            projection = project_note_state(document.payload, burial=NoteCardBurial(buried, buried_until))
            subject = StudyProgressSubject(learner_user_id=self.user.id,
                logical_note_key=note.id.encode(), live_note_id=note.id, status_code=status,
                algorithm_key=ALGORITHM_KEY, algorithm_version=ALGORITHM_VERSION,
                state_schema_version=projection.state_schema_version, storage_codec=STORAGE_CODEC,
                state_payload=document.payload, state_payload_size=document.size,
                algorithm_state_hash=projection.algorithm_state_hash,
                semantic_state_hash=projection.semantic_state_hash,
                projection_version=projection.projection_version, normalized_queue=projection.normalized_queue,
                due_at=projection.due_at, due_day=projection.due_day, is_suspended=projection.is_suspended,
                is_buried=projection.is_buried, buried_until_day=projection.buried_until_day,
                history_completeness_code='HISTORY_NATIVE_COMPLETE', current_provenance_code='NATIVE_DIRECT',
                created_at=NOW, updated_at=NOW)
            db.session.add(subject)
        db.session.commit()
        return card

    def _query(self):
        return Card.query.join(Note, Note.id == Card.note_id).filter(Note.deck_id == self.deck.id)

    def _oracle(self, *, timezone_name='UTC', query=None):
        cards = (query or self._query()).all()
        subjects = {row.live_note_id: row for row in StudyProgressSubject.query.all()}
        reads = {}
        for card in cards:
            subject = subjects.get(card.note_id)
            reads[card.id] = StudyAuthorityAvailabilitySnapshot(StudyAuthorityAvailabilityRead(
                normalized_queue=subject.normalized_queue if subject else 'new',
                due_at=subject.due_at if subject else None, due_day=subject.due_day if subject else None,
                is_suspended=subject.is_suspended if subject else False,
                is_buried=subject.is_buried if subject else False,
                buried_until_day=subject.buried_until_day if subject else None,
                card_created_at=card.created_at, card_order_key=card.order_key.encode(),
            ))
        with patch('app.services.study_authority_read_service.resolve_scheduler_runtime_settings', return_value=RUNTIME):
            return summarize_study_authority_queue(cards=cards, reads_by_card_id=reads,
                learner_user_id=self.user.id, now_utc=NOW, timezone_name=timezone_name)

    def test_queue_anchor_order_matches_note_authority_for_timezones_nulls_ties_and_burial(self):
        future_day = study_repository._today_day_index(now=NOW, timezone_name='UTC',
                                                       day_boundary_hour_local=4) + 2
        boundary = study_repository._next_day_boundary(now=NOW, timezone_name='UTC',
                                                       day_boundary_hour_local=4)
        for index, queue, due_at, due_day in (
            (1, 'relearning', NOW - timedelta(minutes=3), None),
            (2, 'relearning', NOW + timedelta(days=1), 1),
            (3, 'learning', NOW - timedelta(minutes=3), None),
            (4, 'learning', NOW - timedelta(minutes=3), None),
            (5, 'learning', None, 1),
            (6, 'review', NOW + timedelta(days=2), 1),
            (7, 'review', None, 1),
            (8, 'review', NOW + timedelta(hours=1), None),
            (9, 'review', None, None),
            (10, 'new', None, None),
            (11, None, None, None),
            (12, 'learning', NOW + timedelta(minutes=10), None),
            (13, 'relearning', NOW + timedelta(minutes=10), None),
            (14, 'learning', NOW + timedelta(hours=1), None),
            (15, 'relearning', None, future_day),
            (19, 'learning', NOW + timedelta(minutes=30), future_day),
            (20, 'review', boundary, None),
            (21, 'learning', None, future_day - 1),
            (22, 'review', NOW - timedelta(hours=1), future_day - 1),
        ):
            self._add(index, queue, due_at=due_at, due_day=due_day)
        self._add(16, 'relearning', due_day=1, suspended=True)
        self._add(17, 'relearning', due_day=1, buried=True)
        self._add(18, 'learning', due_day=1, buried=True, buried_until=1)
        self._add(23, 'review', due_day=1, buried=True, buried_until=future_day - 2)
        for timezone_name in ('UTC', 'Asia/Tokyo', 'America/New_York', 'Pacific/Honolulu'):
            with self.subTest(timezone=timezone_name):
                oracle = self._oracle(timezone_name=timezone_name)
                query = self._query()
                self.assertEqual(study_repository.query_study_card_order(query, user_id=self.user.id,
                    now=NOW, timezone_name=timezone_name), (oracle.due_card_ids, oracle.learn_ahead_card_ids))
                self.assertEqual(study_repository.query_next_due_card_id(query, user_id=self.user.id,
                    now=NOW, timezone_name=timezone_name), oracle.selected_card_id)
                self.assertEqual(study_repository.query_study_queue_counts(query, user_id=self.user.id,
                    now=NOW, timezone_name=timezone_name), (oracle.new_count, oracle.learn_count, oracle.due_count))
                self.assertEqual(study_repository.query_pending_learning_summary(query, user_id=self.user.id,
                    now=NOW, timezone_name=timezone_name), (oracle.pending_learning_count, oracle.next_due_at))

    def test_learn_ahead_only_after_due_new_and_review_queues_are_empty(self):
        self._add(1, 'learning', due_at=NOW + timedelta(minutes=10))
        ahead = self._add(2, 'relearning', due_at=NOW + timedelta(minutes=15))
        self.assertEqual(study_repository.query_next_due_card_id(self._query(), user_id=self.user.id,
            now=NOW), ahead.id)
        new = self._add(3)
        self.assertEqual(study_repository.query_next_due_card_id(self._query(), user_id=self.user.id,
            now=NOW), new.id)

    def test_archived_card_uuid_breaks_ties_without_changing_presentation_wire_id(self):
        first = self._add(1, 'review', due_at=NOW, due_day=1)
        second = self._add(2, 'review', due_at=NOW, due_day=1)
        rows = []
        for card, old_id in ((first, 'ffffffff-ffff-ffff-ffff-ffffffffffff'),
                             (second, '00000000-0000-0000-0000-000000000001')):
            rows.append({'id': old_id, 'note_id': card.note_id, 'application_id': card.application_id,
                         'template_id': card.template_id, 'created_at': NOW, 'updated_at': NOW})
        # Cutover fixtures seed the immutable alias registry through Core.
        with db.engine.begin() as connection:
            connection.execute(insert(PresentationAlias.__table__), rows)
        db.session.expire_all()
        oracle = self._oracle()
        self.assertEqual(oracle.selected_card_id, second.id)
        self.assertEqual(study_repository.query_next_due_card_id(self._query(), user_id=self.user.id,
                                                               now=NOW), second.id)
        self.assertEqual(study_repository.query_study_card_order(self._query(), user_id=self.user.id,
                                                               now=NOW)[0], (second.id, first.id))
        self.assertEqual(len(second.id), 73)

    def test_picker_uses_bounded_limit_range_branches_without_case_queue_sort(self):
        self._add(1, 'relearning', due_day=1)
        statements = []
        def capture(_conn, _cursor, statement, *_args):
            statements.append(statement)
        event.listen(db.engine, 'before_cursor_execute', capture)
        try:
            study_repository.query_next_due_card_id(self._query(), user_id=self.user.id, now=NOW)
        finally:
            event.remove(db.engine, 'before_cursor_execute', capture)
        selects = [s for s in statements if 'study_progress_subjects' in s]
        self.assertLessEqual(len(selects), 6)
        for statement in selects:
            self.assertIn('LIMIT', statement)
            self.assertNotIn('CASE WHEN study_progress_subjects', statement)
            self.assertNotIn('card_progress', statement)
        due_groups, _ahead = study_repository._ordered_study_card_queries(
            self._query().execution_options(**{INCLUDE_RETIRED_CARDS: True}), user_id=self.user.id, now=NOW)
        self.assertTrue(all(branch.get_execution_options()[INCLUDE_RETIRED_CARDS]
                            for group in due_groups for branch in group))

    def test_retired_release_scope_option_and_note_count_units_survive_picker(self):
        card = self._add(1, 'learning', due_day=1)
        attach_template(db.session, note_type_id=self.note_type.id, owner_user_id=self.user.id, name='Back')
        db.session.commit()
        self.assertEqual(study_repository.query_study_queue_counts(self._query(), user_id=self.user.id,
            now=NOW), (0, 2, 0))
        self.app.config['STUDY_NOTE_COUNT_ENABLED'] = True
        self.assertEqual(study_repository.query_study_queue_counts(self._query(), user_id=self.user.id,
            now=NOW), (0, 1, 0))
        for application in StudyApplication.query.all():
            application.status_code = 'RETIRED'
        db.session.commit()
        self.assertIsNone(study_repository.query_next_due_card_id(self._query(), user_id=self.user.id, now=NOW))
        pinned = self._query().execution_options(**{INCLUDE_RETIRED_CARDS: True})
        self.assertEqual(study_repository.query_next_due_card_id(pinned, user_id=self.user.id, now=NOW),
                         self._oracle(query=pinned).selected_card_id)

    def _browse(self, **args):
        return browse_card_service.list_browse_cards(user_id=self.user.id, admin_mode=False,
            timezone_name='UTC', query_args={'deck_id': self.deck.id, 'per_page': 7, **args})

    def _bulk_stateful_notes(self):
        # Bulk content insertion creates no Card records; one application derives 2000.
        rows = [{'id': f'10000000-0000-0000-0000-{index:012d}', 'user_id': self.user.id,
                 'note_type_id': self.note_type.id, 'deck_id': self.deck.id,
                 'field_values': {'Word': f'{index:08d}'}, 'created_at': NOW, 'updated_at': NOW}
                for index in range(1, 2001)]
        db.session.execute(insert(Note), rows)
        document = serialize_card_state(CardState(type='review', stepIndex=0, due=NOW, dueDay=1,
            intervalDays=1, ease=2.5, reps=1, lapses=0, lastReviewAt=None))
        projection = project_note_state(document.payload, burial=NoteCardBurial())
        states = [{
            'learner_user_id': self.user.id, 'logical_note_key': row['id'].encode(),
            'live_note_id': row['id'], 'status_code': 'MIRRORED_SINGLE',
            'algorithm_key': ALGORITHM_KEY, 'algorithm_version': ALGORITHM_VERSION,
            'state_schema_version': projection.state_schema_version, 'storage_codec': STORAGE_CODEC,
            'state_payload': document.payload, 'state_payload_size': document.size,
            'algorithm_state_hash': projection.algorithm_state_hash,
            'semantic_state_hash': projection.semantic_state_hash,
            'projection_version': projection.projection_version, 'normalized_queue': 'review',
            'due_at': NOW, 'due_day': 1, 'is_suspended': False, 'is_buried': False,
            'history_completeness_code': 'HISTORY_NATIVE_COMPLETE', 'current_provenance_code': 'NATIVE_DIRECT',
            'created_at': NOW, 'updated_at': NOW,
        } for row in rows]
        db.session.execute(insert(StudyProgressSubject), states)
        db.session.commit()

    def test_browse_deep_validation_is_page_bounded_on_large_collection(self):
        self._bulk_stateful_notes()
        statements, requested = [], []
        original = browse_card_service.load_study_authority_card_reads
        def wrapped(*args, **kwargs):
            requested.append(len(kwargs['cards']))
            return original(*args, **kwargs)
        def capture(_conn, _cursor, statement, *_args):
            statements.append(statement)
        event.listen(db.engine, 'before_cursor_execute', capture)
        try:
            with patch.object(browse_card_service, 'load_study_authority_card_reads', side_effect=wrapped), \
                 patch.object(study_authority_read_service, 'validate_consolidated_subject',
                              wraps=study_authority_read_service.validate_consolidated_subject) as validate:
                page = self._browse(page=1)
                second = self._browse(page=2)
                self.assertEqual(validate.call_count, 14)
        finally:
            event.remove(db.engine, 'before_cursor_execute', capture)
        self.assertEqual((page['total'], page['pages'], len(page['items'])), (2000, 286, 7))
        self.assertEqual(second['total'], 2000)
        self.assertFalse({row['card_id'] for row in page['items']} & {row['card_id'] for row in second['items']})
        self.assertEqual(requested, [7, 7])
        self.assertFalse(any('browse_candidates' in statement or 'browse_candidate_rows' in statement
                             for statement in statements))
        aggregates = [s for s in statements if 'count(distinct' in s.lower()]
        self.assertEqual(len(aggregates), 2)

    def test_study_next_serving_endpoint_counts_in_sql_and_validates_only_selected_note(self):
        self._bulk_stateful_notes()
        client = self.app.test_client()
        with client.session_transaction() as login:
            login['_user_id'], login['_fresh'] = str(self.user.id), True
        statements = []
        def capture(_conn, _cursor, statement, *_args):
            statements.append(statement)
        event.listen(db.engine, 'before_cursor_execute', capture)
        try:
            with patch.object(study_authority_read_service, 'validate_consolidated_subject',
                              wraps=study_authority_read_service.validate_consolidated_subject) as validate, \
                 patch('app.routes.flashcards.study.query_study_queue_card_refs', create=True,
                       side_effect=AssertionError('loaded every presentation')), \
                 patch('app.routes.flashcards.study.load_study_authority_availability_snapshot', create=True,
                       side_effect=AssertionError('loaded every Note availability')):
                response = client.get('/api/study/next', query_string={
                    'scope': 'deck', 'scope_id': self.deck.id, 'render_contract': 'client_v1',
                })
                self.assertEqual(response.status_code, 200, response.get_json())
                body = response.get_json()
                self.assertEqual((body['new_count'], body['learn_count'], body['due_count']), (0, 0, 2000))
                self.assertEqual(body['authority_mode'], 'NOTE')
                self.assertTrue(body['card_id'].startswith('10000000-0000-0000-0000-000000000001.'))
                self.assertEqual(validate.call_count, 1)
        finally:
            event.remove(db.engine, 'before_cursor_execute', capture)
        aggregates = [s for s in statements if 'count(distinct' in s.lower()]
        self.assertEqual(len(aggregates), 1)
        candidate_selects = [s for s in statements if 'ORDER BY study_progress_subjects_1' in s]
        self.assertLessEqual(len(candidate_selects), 16)
        self.assertTrue(all('LIMIT' in s for s in candidate_selects))

    def test_browse_count_rejects_detached_envelope_even_outside_requested_status(self):
        self._add(1)
        card = self._add(2, 'review', due_day=99999)
        subject = StudyProgressSubject.query.filter_by(live_note_id=card.note_id).one()
        subject.live_note_id = None
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._browse(status='new')
        self.assertEqual((caught.exception.status, caught.exception.code), (409, 'DETACHED_AUTHORITY_SUBJECT'))

    def test_browse_count_rejects_empty_nonpristine_envelope_before_status_filter(self):
        card = self._add(1)
        db.session.add(StudyProgressSubject(learner_user_id=self.user.id,
            logical_note_key=card.note_id.encode(), live_note_id=card.note_id,
            status_code='QUARANTINED_CORRUPT_STATE', created_at=NOW, updated_at=NOW))
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._browse(status='review')
        self.assertEqual(caught.exception.code, 'INCOMPLETE_AUTHORITY_COVERAGE')

    def test_browse_returned_page_still_rejects_semantic_hash_drift(self):
        card = self._add(1, 'review', due_day=1)
        subject = StudyProgressSubject.query.filter_by(live_note_id=card.note_id).one()
        subject.semantic_state_hash = b'x' * 32
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._browse()
        self.assertIn(caught.exception.code, ('AUTHORITY_READ_PARITY_DIVERGED', 'AUTHORITY_STATE_DIVERGED'))

    def test_browse_count_rejects_partial_state_group_instead_of_pristine_fallback(self):
        card = self._add(1, 'review', due_day=99999)
        # Model CHECK normally prevents partial groups. Simulate externally
        # damaged evidence to prove that a status filter cannot hide it.
        db.session.execute(text('PRAGMA ignore_check_constraints = ON'))
        subject = StudyProgressSubject.query.filter_by(live_note_id=card.note_id).one()
        subject.algorithm_key = None
        db.session.commit()
        with self.assertRaises(browse_card_service.BrowseApiError) as caught:
            self._browse(status='new')
        self.assertEqual(caught.exception.code, 'INCOMPLETE_AUTHORITY_COVERAGE')


if __name__ == '__main__':
    unittest.main()
