"""Drop secondary indexes that another index or no query already covers.

Approved 2026-10-25 (docs/plans/INDEX_REMOVAL_PROPOSAL_2026-10-25.md). Each
index is either a left prefix of a kept index on the same table, which also
backs any foreign key on that prefix, or a single column no query filters by.
Production showed 0 reads over 7.4 days for the second kind. Downgrade
recreates every index with its original columns.

Revision ID: 20261025_000074
Revises: 20261024_000073
"""
from contextlib import contextmanager

from alembic import op
import sqlalchemy as sa

revision = '20261025_000074'
down_revision = '20261024_000073'
branch_labels = None
depends_on = None

INDEXES = {
    'review_events': {
        'ix_review_events_study_session_id': ['study_session_id'],
        'ix_review_events_user_id': ['user_id'],
        'ix_review_events_review_kind': ['review_kind'],
        'ix_review_events_scheduler_mode': ['scheduler_mode'],
    },
    'notes': {'ix_notes_user_id': ['user_id']},
    'card_presentation_aliases': {'ix_card_presentation_aliases_note_id': ['note_id']},
    'deck_working_dirty_entities': {'ix_deck_working_dirty_entities_deck_item_id': ['deck_item_id']},
    'deck_release_changes': {'ix_deck_release_changes_release_id': ['release_id']},
    'connect_review_event_refs': {
        'ix_connect_review_event_refs_user_id': ['user_id'],
        'ix_connect_review_event_refs_status': ['status'],
    },
    'media_assets': {'ix_media_assets_note_id': ['note_id']},
    'connect_import_media': {'ix_connect_import_media_session_id': ['session_id']},
    'deck_release_entity_memberships': {'ix_deck_release_entity_memberships_deck_item_id': ['deck_item_id']},
    'deck_release_note_checkpoints': {'ix_deck_release_note_checkpoints_release_id': ['release_id']},
    'study_session_cards': {'ix_study_session_cards_session_id': ['session_id']},
    'connect_source_card_refs': {'ix_connect_source_card_refs_user_id': ['user_id']},
    'connect_source_note_refs': {'ix_connect_source_note_refs_user_id': ['user_id']},
    'media_field_migration_items': {
        f'ix_media_field_migration_items_{column}': [column]
        for column in ('action', 'entity_id', 'reason', 'deck_id', 'entity_type', 'user_id')
    },
}


@contextmanager
def _online_ddl(bind):
    previous = int(bind.execute(sa.text('SELECT @@SESSION.lock_wait_timeout')).scalar_one())
    bind.execute(sa.text('SET SESSION lock_wait_timeout = 15'))
    try:
        yield
    finally:
        bind.execute(sa.text(f'SET SESSION lock_wait_timeout = {previous}'))


def _existing(bind, table):
    inspector = sa.inspect(bind)
    if table not in inspector.get_table_names():
        return None
    return {index['name']: index['column_names'] for index in inspector.get_indexes(table)}


def upgrade():
    bind = op.get_bind()
    for table, indexes in INDEXES.items():
        existing = _existing(bind, table)
        if existing is None:
            continue
        present = [name for name in indexes if name in existing]
        if not present:
            continue
        if bind.dialect.name == 'mysql':
            drops = ', '.join(f'DROP INDEX {name}' for name in present)
            with _online_ddl(bind):
                op.execute(sa.text(f'ALTER TABLE {table} {drops}, ALGORITHM=INPLACE, LOCK=NONE'))
        else:
            for name in present:
                op.drop_index(name, table_name=table)


def downgrade():
    bind = op.get_bind()
    for table, indexes in INDEXES.items():
        existing = _existing(bind, table)
        if existing is None:
            continue
        missing = {}
        for name, columns in indexes.items():
            if name not in existing:
                missing[name] = columns
            elif existing[name] != columns:
                raise RuntimeError(f'{table}.{name} exists with different columns')
        if not missing:
            continue
        if bind.dialect.name == 'mysql':
            adds = ', '.join(f'ADD INDEX {name} ({", ".join(columns)})' for name, columns in missing.items())
            with _online_ddl(bind):
                op.execute(sa.text(f'ALTER TABLE {table} {adds}, ALGORITHM=INPLACE, LOCK=NONE'))
        else:
            for name, columns in missing.items():
                op.create_index(name, table, columns)
