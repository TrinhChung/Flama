"""Single NOTE anchor-index upgrade/downgrade preserves every progress value."""

from datetime import datetime
import importlib
import unittest

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa
from app import create_audit_app  # Import application package before model contract modules.

migration = importlib.import_module('migrations.versions.20261012_000062_index_note_due_selection')


class NoteDueIndexMigrationTests(unittest.TestCase):
    def setUp(self):
        self.engine = sa.create_engine('sqlite:///:memory:')
        self.addCleanup(self.engine.dispose)
        metadata = sa.MetaData()
        self.table = sa.Table(migration.TABLE, metadata,
            sa.Column('id', sa.Integer, primary_key=True),
            sa.Column('learner_user_id', sa.Integer), sa.Column('normalized_queue', sa.String(20)),
            sa.Column('is_suspended', sa.Boolean), sa.Column('due_day', sa.Integer),
            sa.Column('due_at', sa.DateTime), sa.Column('live_note_id', sa.String(36)),
            sa.Column('semantic_state_hash', sa.LargeBinary), sa.Column('authority_revision', sa.Integer),
        )
        metadata.create_all(self.engine)
        with self.engine.begin() as connection:
            connection.execute(sa.insert(self.table).values(id=1, learner_user_id=7, normalized_queue='learning',
                is_suspended=False, due_day=None, due_at=datetime(2026, 10, 12, 1), live_note_id='note-1',
                semantic_state_hash=b'h' * 32, authority_revision=17))
        self.addCleanup(setattr, op, '_proxy', None)

    def _run(self, step):
        with self.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            getattr(migration, step)()

    def _rows(self):
        with self.engine.connect() as connection:
            return connection.execute(sa.select(self.table)).all()

    def test_upgrade_and_downgrade_are_repeatable_and_preserve_values(self):
        before = self._rows()
        self._run('upgrade')
        self._run('upgrade')
        index = next(row for row in sa.inspect(self.engine).get_indexes(migration.TABLE)
                     if row['name'] == migration.INDEX)
        self.assertEqual(index['column_names'], migration.COLUMNS)
        self.assertFalse(index['unique'])
        self.assertEqual(self._rows(), before)
        self._run('downgrade')
        self._run('downgrade')
        self.assertFalse(any(row['name'] == migration.INDEX
                             for row in sa.inspect(self.engine).get_indexes(migration.TABLE)))
        self.assertEqual(self._rows(), before)

    def test_wrong_existing_index_cannot_silently_pass_as_complete(self):
        sa.Index(migration.INDEX, self.table.c.learner_user_id).create(self.engine)
        with self.assertRaisesRegex(RuntimeError, 'differs'):
            self._run('upgrade')

    def test_model_matches_index_contract(self):
        from models.study_progress_subject import StudyProgressSubject
        index = next(row for row in StudyProgressSubject.__table__.indexes if row.name == migration.INDEX)
        self.assertEqual([column.name for column in index.columns], migration.COLUMNS)
        self.assertFalse(index.unique)


if __name__ == '__main__':
    unittest.main()
