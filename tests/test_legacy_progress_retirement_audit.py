"""Coverage, state integrity and non-mutation gates for legacy retirement."""

from datetime import datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

import sqlalchemy as sa

from app import create_audit_app
from app.services.study_consolidated_progress_service import clear_note_progress
from app.services.study_progress_shadow_mapper import MappedCardProgress, map_card_progress
from models import db
from migrations.retired_card_tables import Card, CardProgress, RETIRED_CARD_METADATA
from migrations.retirement_archive import verify_restore, write_bundle
from models.card import PresentationAlias
from models.note import Note
from models.note_type import NoteType
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_application import StudyApplication
from models.study_progress_subject import StudyProgressSubject
from models.user import User
from scripts.audit_legacy_progress_retirement import audit_connection, _mapped_frozen_progress
from tests.study_note_fixtures import attach_template

OLD = datetime(2026, 9, 30)
CUT = datetime(2026, 10, 3)
LATER = datetime(2026, 10, 12)
NOTE_ID = '10000000-0000-0000-0000-000000000001'
CARD_ID = '20000000-0000-0000-0000-000000000001'


class LegacyProgressRetirementAuditTests(unittest.TestCase):
    def setUp(self):
        self.app = create_audit_app({
            'TESTING': True, 'SQLALCHEMY_DATABASE_URI': 'sqlite:///:memory:',
            'REDIS_URL': '', 'DECK_COUNT_WRITE_ENABLED': False,
            'REVIEW_ANALYTICS_WRITE_ENABLED': False,
        })
        self.context = self.app.app_context()
        self.context.push()
        db.create_all()
        RETIRED_CARD_METADATA.create_all(db.engine, tables=[Card.__table__, CardProgress.__table__])
        db.session.execute(sa.insert(User).values(id=1, username='audit', email='audit@example.test'))
        db.session.execute(sa.insert(NoteType).values(id='type-1', user_id=1, name='Audit'))
        template = attach_template(db.session, note_type_id='type-1', owner_user_id=1, name='Front', created_at=OLD)
        application = StudyApplication.query.filter_by(template_id=template.id).one()
        db.session.execute(sa.insert(Note).values(id=NOTE_ID, note_type_id='type-1', user_id=1, created_at=OLD))
        db.session.execute(sa.insert(Card).values(id=CARD_ID, note_id=NOTE_ID,
                                                  template_id=template.id, application_id=application.id, created_at=OLD))
        self.progress = CardProgress(id=1, user_id=1, card_id=CARD_ID, queue='review',
                                     due_day=20500, interval_days=12, interval_days_raw=12.0,
                                     reps=17, revision=3, created_at=OLD, updated_at=OLD)
        db.session.add(self.progress)
        db.session.flush()
        db.session.add(StudyAuthorityEnrollment(learner_user_id=1, mode_code='NOTE', epoch=1,
                                                created_at=CUT, updated_at=CUT))
        db.session.add(StudyAuthorityStorageProfile(id=1, profile_code='CONSOLIDATED_V1', epoch=3,
                                                    switched_at=CUT, created_at=CUT, updated_at=CUT))
        self.subject = StudyProgressSubject(learner_user_id=1, logical_note_key=NOTE_ID.encode(),
                                            live_note_id=NOTE_ID, status_code='MIRRORED_SINGLE',
                                            authority_revision=3, contributor_count=1,
                                            created_at=CUT, updated_at=CUT)
        self._assign_state(self.progress)
        db.session.add(self.subject)
        db.session.commit()

    def tearDown(self):
        db.session.remove()
        RETIRED_CARD_METADATA.drop_all(db.engine, tables=[CardProgress.__table__, Card.__table__], checkfirst=True)
        db.drop_all()
        self.context.pop()

    def _assign_state(self, progress):
        mapped = map_card_progress(progress, card_created_at=OLD, card_order_key=CARD_ID)
        self.assertIsInstance(mapped, MappedCardProgress)
        for key in ('algorithm_key', 'algorithm_version', 'state_schema_version', 'storage_codec',
                    'algorithm_state_hash', 'semantic_state_hash'):
            setattr(self.subject, key, getattr(mapped, key))
        self.subject.state_payload = mapped.state.payload
        self.subject.state_payload_size = mapped.state.size
        self.subject.history_completeness_code = 'HISTORY_IMPORTED_PARTIAL'
        self.subject.current_provenance_code = 'UNKNOWN_LEGACY'
        for key in ('projection_version', 'normalized_queue', 'due_at', 'due_day',
                    'is_suspended', 'is_buried', 'buried_until_day'):
            setattr(self.subject, key, getattr(mapped.availability, key))

    def _audit(self, archive_bundle=None):
        statements = []
        with db.engine.connect() as connection:
            def record(_connection, _cursor, statement, *_args):
                statements.append(statement.lstrip().split()[0].upper())
            sa.event.listen(connection, 'before_cursor_execute', record)
            report = audit_connection(connection, archive_bundle=archive_bundle)
            connection.rollback()
        self.assertTrue(set(statements) <= {'SELECT', 'PRAGMA'}, statements)
        return report

    def test_complete_coverage_and_read_only_repeatability(self):
        first, second = self._audit(), self._audit()
        self.assertEqual(first['status'], 'DATA_READY')
        self.assertEqual(first['snapshot_sha256'], second['snapshot_sha256'])
        self.assertEqual(first['progress_coverage']['covered_rows'], 1)
        self.assertEqual(first['frozen_state_comparison'], {'same_semantic_state': 1})
        self.assertEqual(db.session.get(CardProgress, 1).reps, 17)

    def test_newer_note_progress_is_preserved(self):
        values = {c.name: getattr(self.progress, c.name) for c in CardProgress.__table__.columns}
        values.update(reps=18, due_day=20510)
        self._assign_state(SimpleNamespace(**values))
        self.subject.authority_revision = 4
        self.subject.updated_at = LATER
        db.session.commit()
        original = dict(self.subject.state_payload)
        report = self._audit()
        self.assertEqual(report['status'], 'DATA_READY')
        self.assertEqual(report['frozen_state_comparison'], {'different_current_state_preserved': 1})
        db.session.expire_all()
        self.assertEqual(self.subject.state_payload, original)
        self.assertEqual(self.subject.authority_revision, 4)

    def test_missing_subject_blocks_retirement(self):
        db.session.delete(self.subject)
        db.session.commit()
        report = self._audit()
        self.assertIn('NOTE_PROGRESS_COVERAGE_GAP', report['blockers'])
        self.assertEqual(report['progress_coverage']['missing_subject_rows'], 1)

    def test_missing_state_is_not_treated_as_migrated(self):
        clear_note_progress(self.subject, now_utc=LATER)
        self.subject.status_code = 'NO_CURRENT_PROGRESS'
        db.session.commit()
        self.assertIn('NOTE_PROGRESS_COVERAGE_GAP', self._audit()['blockers'])

    def test_legacy_and_unenrolled_learners_block_retirement(self):
        enrollment = db.session.get(StudyAuthorityEnrollment, 1)
        enrollment.mode_code = 'LEGACY'
        db.session.commit()
        self.assertIn('LEGACY_LEARNERS', self._audit()['blockers'])
        db.session.delete(enrollment)
        db.session.commit()
        self.assertIn('UNENROLLED_LEARNERS', self._audit()['blockers'])

    def test_invalid_state_hash_blocks_retirement(self):
        self.subject.algorithm_state_hash = b'x' * 32
        db.session.commit()
        self.assertIn('INVALID_NOTE_STATE', self._audit()['blockers'])

    def test_availability_drift_blocks_retirement(self):
        self.subject.due_day += 1
        db.session.commit()
        self.assertIn('INVALID_NOTE_STATE', self._audit()['blockers'])

    def test_new_legacy_write_blocks_retirement(self):
        self.progress.updated_at = LATER
        db.session.commit()
        self.assertIn('LEGACY_WRITES_AFTER_CUTOVER', self._audit()['blockers'])

    def test_missing_cutover_time_cannot_certify_no_late_legacy_writes(self):
        db.session.get(StudyAuthorityStorageProfile, 1).switched_at = None
        db.session.commit()
        self.assertIn('CUTOVER_TIMESTAMP_MISSING', self._audit()['blockers'])

    def test_invalid_note_identity_is_reported_and_kept_in_row_count(self):
        self.subject.logical_note_key = b'\xff'
        db.session.commit()
        report = self._audit()
        self.assertEqual(report['status'], 'BLOCK')
        self.assertEqual(report['current_subjects'], 1)
        self.assertEqual(report['current_state_problems']['INVALID_NOTE_IDENTITY'], 1)
        self.assertIn('NOTE_PROGRESS_COVERAGE_GAP', report['blockers'])

    def test_orphan_progress_does_not_disappear_from_accounting(self):
        self.progress.card_id = None
        db.session.commit()
        report = self._audit()
        self.assertEqual(report['progress_coverage']['old_rows'], 1)
        self.assertEqual(report['progress_coverage']['unresolved_rows'], 1)
        self.assertIn('UNRESOLVED_LEGACY_PROGRESS', report['blockers'])

    def test_reflected_mysql_boolean_flags_are_normalized_strictly(self):
        raw = {c.name: getattr(self.progress, c.name) for c in CardProgress.__table__.columns}
        raw.update(is_suspended=1, is_buried=0)
        self.assertIsInstance(_mapped_frozen_progress(raw, card_created_at=OLD), MappedCardProgress)
        raw['is_suspended'] = 2
        self.assertNotIsInstance(_mapped_frozen_progress(raw, card_created_at=OLD), MappedCardProgress)

    def test_post_contraction_uses_verified_archive_and_exact_alias_without_progress_table(self):
        before = self._audit()
        with TemporaryDirectory() as temporary:
            bundle = Path(temporary) / 'progress.json'
            with db.engine.connect() as connection:
                write_bundle(connection, bundle, ['card_progress'])
            restore = sa.create_engine(sa.URL.create('sqlite', database=str(Path(temporary) / 'restore.sqlite')))
            with restore.connect() as connection:
                verify_restore(connection, bundle)
            restore.dispose()
            db.session.remove()
            with db.engine.begin() as connection:
                names = list(Card.__table__.columns.keys())
                connection.execute(PresentationAlias.__table__.insert().from_select(names, sa.select(*Card.__table__.columns)))
                CardProgress.__table__.drop(connection)
                Card.__table__.drop(connection)
            after = self._audit(archive_bundle=bundle)
            self.assertEqual(after['status'], 'DATA_READY')
            self.assertEqual(after['snapshot_sha256'], before['snapshot_sha256'])
            self.assertEqual(after['progress_coverage']['covered_rows'], 1)
            self.assertNotIn('card_progress', sa.inspect(db.engine).get_table_names())
            self.assertNotIn('card_progress', db.metadata.tables)
            db.create_all()
            self.assertNotIn('card_progress', sa.inspect(db.engine).get_table_names())
            self.assertNotIn('cards', sa.inspect(db.engine).get_table_names())


if __name__ == '__main__':
    unittest.main()
