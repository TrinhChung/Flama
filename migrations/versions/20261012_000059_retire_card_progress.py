"""Contract frozen per-Card progress after verified archive and NOTE audit.

Existing NOTE state is never rewritten. Old writers must be stopped before
the audit and DDL. A complete same-dialect archive restore and exact matching
current-state audit are required for populated tables; empty fresh bootstraps
start in the consolidated profile. Downgrade requires real archived data.
"""

from alembic import op
import sqlalchemy as sa

from migrations.progress_retirement_gate import (
    assert_note_authority, assert_progress_audit_matches, initialize_empty_note_profile,
)
from migrations.retirement_archive import assert_archive_matches

revision = '20261012_000059'
down_revision = '20261012_000058'
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    present = set(sa.inspect(bind).get_table_names())
    if 'card_progress' not in present:
        return
    table = sa.Table('card_progress', sa.MetaData(), autoload_with=bind, resolve_fks=False)
    count = int(bind.execute(sa.select(sa.func.count()).select_from(table)).scalar_one())
    incoming = [f'{name}.{fk.get("name") or fk.get("constrained_columns")}'
                for name in sorted(present - {'card_progress'})
                for fk in sa.inspect(bind).get_foreign_keys(name)
                if fk.get('referred_table') == 'card_progress']
    if incoming:
        raise RuntimeError('Progress still has foreign-key consumers: ' + ', '.join(incoming))
    assert_note_authority(bind)
    if count:
        assert_archive_matches(bind, ['card_progress'])
        assert_progress_audit_matches(bind)
    else:
        initialize_empty_note_profile(bind)
    op.drop_table('card_progress')


def downgrade():
    bind = op.get_bind()
    if 'card_progress' not in sa.inspect(bind).get_table_names():
        raise RuntimeError('Refusing downgrade: restore the verified progress archive first')
    assert_archive_matches(bind, ['card_progress'])
