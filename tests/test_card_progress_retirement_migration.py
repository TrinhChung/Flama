"""Progress contraction requires a verified archive and matching NOTE checkpoint."""

from datetime import datetime, timezone
import importlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa

from migrations.progress_retirement_gate import AUDIT_ENV, snapshot_sha256
from migrations.retirement_archive import ARCHIVE_ENV, verify_restore, write_bundle
from tests import test_legacy_progress_retirement_audit as fixtures
from models import db
from models.study_authority_enrollment import StudyAuthorityEnrollment
from models.study_authority_storage_profile import StudyAuthorityStorageProfile
from models.study_progress_subject import StudyProgressSubject

migration = importlib.import_module('migrations.versions.20261012_000059_retire_card_progress')


class CardProgressRetirementMigrationTests(unittest.TestCase):
    # Reuse explicit private historical tables and actual NOTE codec state.
    setUp = fixtures.LegacyProgressRetirementAuditTests.setUp
    tearDown = fixtures.LegacyProgressRetirementAuditTests.tearDown
    _assign_state = fixtures.LegacyProgressRetirementAuditTests._assign_state
    _audit = fixtures.LegacyProgressRetirementAuditTests._audit

    def _prepare(self, temporary):
        archive = Path(temporary) / 'progress.json'
        report = Path(temporary) / 'audit.json'
        with db.engine.connect() as connection:
            write_bundle(connection, archive, ['card_progress'])
        restore = sa.create_engine(sa.URL.create('sqlite', database=str(Path(temporary) / 'restore.sqlite')))
        with restore.connect() as connection:
            verify_restore(connection, archive)
        restore.dispose()
        evidence = self._audit()
        self.assertEqual(evidence['status'], 'DATA_READY')
        evidence['observed_at_utc'] = datetime.now(timezone.utc).isoformat()
        from migrations.progress_retirement_gate import _json_value
        report.write_text(json.dumps(evidence, default=_json_value), encoding='utf-8')
        return archive, report

    @staticmethod
    def _run(method='upgrade'):
        db.session.remove()
        try:
            with db.engine.begin() as connection:
                op._proxy = Operations(MigrationContext.configure(connection))
                getattr(migration, method)()
        finally:
            op._proxy = None

    @staticmethod
    def _snapshots():
        names = ['study_progress_subjects', 'study_authority_enrollments', 'study_progress_history_facts',
                 'study_progress_lifecycle_events', 'review_events', 'study_authority_command_receipts']
        with db.engine.connect() as connection:
            return {name: snapshot_sha256(connection, name) for name in names}

    def test_verified_contraction_keeps_current_state_hash_revisions_and_history(self):
        before = self._snapshots()
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            statements = []
            def capture(connection, cursor, statement, parameters, context, executemany):
                statements.append(statement)
            sa.event.listen(db.engine, 'before_cursor_execute', capture)
            try:
                with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                    self._run()
                    self._run()  # idempotent after contraction
            finally:
                sa.event.remove(db.engine, 'before_cursor_execute', capture)
        self.assertNotIn('card_progress', sa.inspect(db.engine).get_table_names())
        self.assertEqual(self._snapshots(), before)
        self.assertFalse(any(statement.lstrip().upper().startswith(('INSERT ', 'UPDATE ', 'DELETE ')) for statement in statements))

    def test_missing_archive_refuses_populated_contraction(self):
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(RuntimeError, 'restore-verified archive'):
                self._run()
        self.assertIn('card_progress', sa.inspect(db.engine).get_table_names())

    def test_missing_audit_refuses_even_with_verified_archive(self):
        with TemporaryDirectory() as temporary:
            archive, _ = self._prepare(temporary)
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive)}, clear=True):
                with self.assertRaisesRegex(RuntimeError, 'fresh read-only audit'):
                    self._run()

    def test_newer_authority_revision_refuses_stale_checkpoint_without_rewriting_it(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            original_payload = dict(self.subject.state_payload)
            self.subject.authority_revision += 1
            db.session.commit()
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                with self.assertRaisesRegex(RuntimeError, 'Live study_progress_subjects changed'):
                    self._run()
            current = StudyProgressSubject.query.filter_by(learner_user_id=1).one()
            self.assertEqual(current.authority_revision, 4)
            self.assertEqual(current.state_payload, original_payload)
            self.assertIn('card_progress', sa.inspect(db.engine).get_table_names())

    def test_changed_current_hash_refuses_stale_checkpoint(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            self.subject.algorithm_state_hash = b'z' * 32
            db.session.commit()
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                with self.assertRaisesRegex(RuntimeError, 'Live study_progress_subjects changed'):
                    self._run()

    def test_frozen_progress_changed_since_archive_refuses_contraction(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            self.progress.reps += 1
            db.session.commit()
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                with self.assertRaisesRegex(RuntimeError, 'changed since retirement archive'):
                    self._run()

    def test_unenrolled_learner_is_not_silently_promoted(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            db.session.delete(db.session.get(StudyAuthorityEnrollment, 1))
            db.session.commit()
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                with self.assertRaisesRegex(RuntimeError, 'unenrolled learners'):
                    self._run()
            self.assertEqual(StudyAuthorityEnrollment.query.count(), 0)

    def test_stale_storage_profile_checkpoint_is_rejected(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            db.session.get(StudyAuthorityStorageProfile, 1).epoch += 1
            db.session.commit()
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                with self.assertRaisesRegex(RuntimeError, 'profile changed'):
                    self._run()

    def test_corrupt_or_blocked_audit_is_rejected_before_drop(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            original = json.loads(report.read_text(encoding='utf-8'))
            alterations = [dict(status='BLOCK'), dict(blockers=['INVALID_NOTE_STATE']),
                           dict(current_state_problems={'INVALID_STATE_VALUE': 1}),
                           dict(frozen_mapping_failure_codes={'UNSUPPORTED_QUEUE': 1}),
                           dict(snapshot_sha256={'card_progress': '0' * 64, 'study_progress_subjects': '0' * 64})]
            for change in alterations:
                with self.subTest(change=change):
                    report.write_text(json.dumps({**original, **change}), encoding='utf-8')
                    with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                        with self.assertRaises(RuntimeError):
                            self._run()
                    self.assertIn('card_progress', sa.inspect(db.engine).get_table_names())

    def test_inbound_foreign_key_prevents_drop_even_with_valid_evidence(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            with db.engine.begin() as connection:
                connection.exec_driver_sql('CREATE TABLE future_projection (progress_id INTEGER REFERENCES card_progress(id))')
            try:
                with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                    with self.assertRaisesRegex(RuntimeError, 'foreign-key consumers'):
                        self._run()
            finally:
                with db.engine.begin() as connection:
                    connection.exec_driver_sql('DROP TABLE future_projection')

    def test_downgrade_requires_actual_restored_evidence(self):
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                self._run()
                with self.assertRaisesRegex(RuntimeError, 'restore the verified progress archive first'):
                    self._run('downgrade')

    def test_downgrade_accepts_actual_exact_archive_restore(self):
        from migrations.retired_card_tables import CardProgress
        from migrations.retirement_archive import _decode, load_bundle
        with TemporaryDirectory() as temporary:
            archive, report = self._prepare(temporary)
            with patch.dict(os.environ, {ARCHIVE_ENV: str(archive), AUDIT_ENV: str(report)}):
                self._run()
                entry = load_bundle(archive)['tables'][0]
                with db.engine.begin() as connection:
                    CardProgress.__table__.create(connection)
                    connection.execute(CardProgress.__table__.insert(), [
                        dict(zip((column['name'] for column in entry['columns']), map(_decode, values)))
                        for values in entry['rows']])
                self._run('downgrade')
                with db.engine.connect() as connection:
                    self.assertEqual(snapshot_sha256(connection, 'card_progress')[1], 1)


class EmptyProgressRetirementTests(unittest.TestCase):
    def test_empty_fresh_install_initializes_note_profile_and_is_idempotent(self):
        engine = sa.create_engine('sqlite:///:memory:')
        metadata = sa.MetaData()
        sa.Table('users', metadata, sa.Column('id', sa.Integer, primary_key=True))
        sa.Table('study_progress_subjects', metadata, sa.Column('id', sa.Integer, primary_key=True))
        sa.Table('study_authority_enrollments', metadata, sa.Column('learner_user_id', sa.Integer, primary_key=True), sa.Column('mode_code', sa.String))
        sa.Table('study_authority_storage_profile', metadata, sa.Column('id', sa.Integer, primary_key=True),
                 sa.Column('profile_code', sa.String), sa.Column('epoch', sa.Integer), sa.Column('switched_at', sa.DateTime),
                 sa.Column('created_at', sa.DateTime), sa.Column('updated_at', sa.DateTime))
        sa.Table('card_progress', metadata, sa.Column('id', sa.Integer, primary_key=True))
        metadata.create_all(engine)
        try:
            with patch.dict(os.environ, {}, clear=True):
                with engine.begin() as connection:
                    op._proxy = Operations(MigrationContext.configure(connection))
                    migration.upgrade()
                    migration.upgrade()
                    profile = connection.execute(sa.text('SELECT profile_code, epoch, switched_at FROM study_authority_storage_profile')).one()
                    self.assertEqual(profile[:2], ('CONSOLIDATED_V1', 1))
                    self.assertIsNotNone(profile[2])
                    self.assertNotIn('card_progress', sa.inspect(connection).get_table_names())
        finally:
            op._proxy = None
            engine.dispose()


if __name__ == '__main__':
    unittest.main()
