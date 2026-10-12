"""Index NOTE queue/anchor range selection without changing progress values.

Revision ID: 20261012_000062
Revises: 20261012_000061

The current learner/Note index only narrows a picker to a learner's whole
collection. Queue and suspension are equalities; due_day is either a day
range or NULL followed by a due_at range. This single index supports both.
MySQL8 DDL explicitly requires INPLACE/LOCK NONE instead of silently copying
the table. Some mixed anchor/creation-order cases may still sort the small
filtered range; scheduling anchors and all state/history values are retained.
"""

from alembic import op
import sqlalchemy as sa

revision = '20261012_000062'
down_revision = '20261012_000061'
branch_labels = None
depends_on = None

TABLE = 'study_progress_subjects'
INDEX = 'ix_sp_subject_note_due'
COLUMNS = ['learner_user_id', 'normalized_queue', 'is_suspended', 'due_day', 'due_at', 'live_note_id']


def _existing(bind):
    inspector = sa.inspect(bind)
    if not inspector.has_table(TABLE):
        raise RuntimeError('NOTE progress table is missing; due-index migration refused.')
    for index in inspector.get_indexes(TABLE):
        if index['name'] == INDEX:
            if index['column_names'] != COLUMNS or index.get('unique'):
                raise RuntimeError('Existing NOTE due index differs from the migration contract.')
            return True
    return False


def upgrade():
    bind = op.get_bind()
    if _existing(bind):
        return
    if bind.dialect.name == 'mysql':
        columns = ', '.join(f'`{column}`' for column in COLUMNS)
        op.execute(f'ALTER TABLE `{TABLE}` ADD INDEX `{INDEX}` ({columns}), ALGORITHM=INPLACE, LOCK=NONE')
    else:
        op.create_index(INDEX, TABLE, COLUMNS)


def downgrade():
    bind = op.get_bind()
    if not _existing(bind):
        return
    if bind.dialect.name == 'mysql':
        op.execute(f'ALTER TABLE `{TABLE}` DROP INDEX `{INDEX}`, ALGORITHM=INPLACE, LOCK=NONE')
    else:
        op.drop_index(INDEX, table_name=TABLE)
