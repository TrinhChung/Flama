"""Cover learner deck-scope lookups without fetching every Note row.

Revision ID: 20261024_000073
Revises: 20261020_000071
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa

revision = '20261024_000073'
down_revision = '20261020_000071'
branch_labels = None
depends_on = None

INDEX = 'ix_notes_user_deck'


@contextmanager
def _online_index(bind):
    previous = int(bind.execute(sa.text('SELECT @@SESSION.lock_wait_timeout')).scalar_one())
    bind.execute(sa.text('SET SESSION lock_wait_timeout = 15'))
    try:
        yield
    finally:
        bind.execute(sa.text(f'SET SESSION lock_wait_timeout = {previous}'))


def upgrade():
    bind = op.get_bind()
    indexes = sa.inspect(bind).get_indexes('notes')
    existing = next((index for index in indexes if index['name'] == INDEX), None)
    if existing:
        if existing['column_names'] != ['user_id', 'deck_id']:
            raise RuntimeError('ix_notes_user_deck exists with different columns')
        return
    if bind.dialect.name == 'mysql':
        with _online_index(bind):
            op.execute(sa.text('ALTER TABLE notes ADD INDEX ix_notes_user_deck (user_id, deck_id), ALGORITHM=INPLACE, LOCK=NONE'))
    else:
        op.create_index(INDEX, 'notes', ['user_id', 'deck_id'])


def downgrade():
    bind = op.get_bind()
    if not any(index['name'] == INDEX for index in sa.inspect(bind).get_indexes('notes')):
        return
    if bind.dialect.name == 'mysql':
        with _online_index(bind):
            op.execute(sa.text('ALTER TABLE notes DROP INDEX ix_notes_user_deck, ALGORITHM=INPLACE, LOCK=NONE'))
    else:
        op.drop_index(INDEX, table_name='notes')
