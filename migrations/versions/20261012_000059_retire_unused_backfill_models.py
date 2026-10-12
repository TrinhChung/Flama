"""Retire four unused runtime tables, preserving verified external evidence.

Revision ID: 20261012_000059
Revises: 20261012_000058

Populated databases require FLAMA_RETIREMENT_ARCHIVE pointing to an archive
verified by restoration on the same dialect. All live checksums must match
before any DROP. Run with old writers stopped, after the compatible code is
deployed; MySQL DDL cannot transactionally undo a partly applied contraction.
Empty fresh chains need no archive. Downgrade requires actual archive restore.
"""

from alembic import op
import sqlalchemy as sa

from migrations.retirement_archive import assert_archive_matches

revision = "20261012_000059"
down_revision = "20261012_000058"
branch_labels = None
depends_on = None

# RESTRICT disposition -> run, CASCADE checkpoint -> run: children first.
TABLES = ("study_progress_backfill_dispositions", "study_progress_backfill_checkpoints",
          "study_progress_backfill_runs", "vocabulary_column_preferences")


def upgrade():
    bind = op.get_bind()
    present = set(sa.inspect(bind).get_table_names())
    targets = [name for name in TABLES if name in present]
    if not targets:
        return
    inbound = [f"{name}.{fk.get('name') or fk.get('constrained_columns')}"
               for name in sorted(present - set(TABLES))
               for fk in sa.inspect(bind).get_foreign_keys(name)
               if fk.get("referred_table") in targets]
    if inbound:
        raise RuntimeError("Retired tables still have external foreign-key consumers: " + ", ".join(inbound))
    counts = {name: int(bind.execute(sa.select(sa.func.count()).select_from(
        sa.Table(name, sa.MetaData(), autoload_with=bind, resolve_fks=False))).scalar_one())
        for name in targets}
    # Validate every target, including zero-row preferences, before first DROP.
    if any(counts.values()):
        assert_archive_matches(bind, targets)
    for name in targets:
        op.drop_table(name)


def downgrade():
    bind = op.get_bind()
    present = set(sa.inspect(bind).get_table_names())
    missing = sorted(set(TABLES) - present)
    if missing:
        raise RuntimeError("Refusing downgrade: restore the verified retirement archive first; "
                           f"missing tables: {', '.join(missing)}")
    assert_archive_matches(bind, TABLES)
