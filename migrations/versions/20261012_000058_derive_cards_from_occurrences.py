"""Archive old presentation IDs and derive new presentations without Card rows.

Revision ID: 20261012_000058
Revises: 20261010_000056

This contraction requires a stopped-writer deployment window. It keeps every
old Card column in an immutable alias table and captures original entity sets
so a previously absent/deleted pair is not silently regenerated. Exact Card
creation timestamps are retained; StudyApplication timestamps are untouched.

Session, Connect, event, receipt and frozen CardProgress IDs are never rewritten.
Only live wire columns expand; CardProgress keeps its original column contract.
All Card foreign keys detach before the original table is removed. A rerun
verifies the archive before dropping anything, and a schema downgrade must use
a verified backup/compatible release instead of inventing old IDs or erasing
history from new presentations.
"""

from __future__ import annotations

from datetime import datetime

from alembic import op
import sqlalchemy as sa

revision = "20261012_000058"
down_revision = "20261010_000056"
branch_labels = None
depends_on = None

KEY_LENGTH = 80
ALIASES = "card_presentation_aliases"
NOTES = "card_presentation_cutover_notes"
APPLICATIONS = "card_presentation_cutover_applications"
CUTOVERS = "card_presentation_cutovers"
REFERENCES = (
    ("card_progress", True, 36, False),
    ("study_session_cards", False, 36, True),
    ("connect_source_card_refs", True, 36, True),
    ("review_events", False, 64, True),
)


def _definitions():
    metadata = sa.MetaData()
    aliases = sa.Table(
        ALIASES, metadata,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("note_id", sa.String(36), nullable=False, index=True),
        sa.Column("template_id", sa.String(36), nullable=False, index=True),
        sa.Column("application_id", sa.String(36), nullable=False, index=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("note_id", "application_id", name="uq_presentation_alias_note_application"),
    )
    notes = sa.Table(NOTES, metadata, sa.Column("note_id", sa.String(36), primary_key=True))
    applications = sa.Table(APPLICATIONS, metadata, sa.Column("application_id", sa.String(36), primary_key=True))
    cutovers = sa.Table(
        CUTOVERS, metadata,
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("captured_at", sa.DateTime(), nullable=False),
        sa.Column("source_row_count", sa.BigInteger, nullable=False),
    )
    return metadata, aliases, notes, applications, cutovers


def _archive(bind, cards, aliases):
    columns = list(aliases.c.keys())
    existing = aliases.alias("existing_presentation_alias")
    missing = sa.select(*(cards.c[name] for name in columns)).where(
        ~sa.select(existing.c.id).where(existing.c.id == cards.c.id).exists()
    )
    bind.execute(sa.insert(aliases).from_select(columns, missing))
    same = sa.and_(*(aliases.c[name] == cards.c[name] for name in columns))
    source_count = bind.execute(sa.select(sa.func.count()).select_from(cards)).scalar_one()
    alias_count = bind.execute(sa.select(sa.func.count()).select_from(aliases)).scalar_one()
    matched = bind.execute(sa.select(sa.func.count()).select_from(cards.join(aliases, same))).scalar_one()
    if source_count != alias_count or matched != source_count:
        raise RuntimeError("Presentation alias archive differs from original Card rows; contraction refused.")
    return source_count


def _capture_entities(bind, notes, applications, cutovers, source_count):
    captured = bind.execute(sa.select(cutovers.c.source_row_count).where(cutovers.c.id == 1)).scalar_one_or_none()
    if captured is not None:
        if captured != source_count:
            raise RuntimeError("Card count changed after cutover snapshot; stop all old writers before retrying.")
        return
    metadata = sa.MetaData()
    original_notes = sa.Table("notes", metadata, autoload_with=bind, resolve_fks=False)
    original_applications = sa.Table("study_applications", metadata, autoload_with=bind, resolve_fks=False)
    for baseline, original, column in (
        (notes, original_notes, "note_id"),
        (applications, original_applications, "application_id"),
    ):
        values = sa.select(original.c.id).where(
            ~sa.select(baseline.c[column]).where(baseline.c[column] == original.c.id).exists()
        )
        bind.execute(sa.insert(baseline).from_select([column], values))
    bind.execute(sa.insert(cutovers).values(id=1, captured_at=datetime.utcnow(), source_row_count=source_count))


def _detach_references(bind):
    for table, nullable, old_length, expand in REFERENCES:
        inspector = sa.inspect(bind)
        if not inspector.has_table(table):
            continue
        foreign_keys = [
            fk for fk in inspector.get_foreign_keys(table)
            if fk.get("referred_table") == "cards" and fk.get("constrained_columns") == ["card_id"]
        ]
        column = next(row for row in inspector.get_columns(table) if row["name"] == "card_id")
        needs_expand = expand and getattr(column["type"], "length", 0) < KEY_LENGTH
        if not foreign_keys and not needs_expand:
            continue
        # A naming convention identifies unnamed SQLite historical FKs during
        # batch reflection; MySQL keeps its actual constraint names.
        naming = {"fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s"}
        with op.batch_alter_table(table, naming_convention=naming) as batch:
            for fk in foreign_keys:
                name = fk.get("name") or f"fk_{table}_{fk['constrained_columns'][0]}_cards"
                batch.drop_constraint(name, type_="foreignkey")
            if needs_expand:
                batch.alter_column("card_id", existing_type=column["type"],
                                   type_=sa.String(KEY_LENGTH), existing_nullable=nullable)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    cards = None
    if inspector.has_table("cards"):
        cards = sa.Table("cards", sa.MetaData(), autoload_with=bind, resolve_fks=False)
        unattributed = bind.execute(sa.select(sa.func.count()).select_from(cards).where(
            cards.c.application_id.is_(None),
        )).scalar_one()
        if unattributed:
            raise RuntimeError(f"{unattributed} old Card(s) have no application; explicit attribution is required.")
        for target, column in (("notes", "note_id"), ("study_applications", "application_id")):
            parent = sa.Table(target, sa.MetaData(), autoload_with=bind, resolve_fks=False)
            unresolved = bind.execute(sa.select(sa.func.count()).select_from(cards).where(
                ~sa.select(parent.c.id).where(parent.c.id == cards.c[column]).exists(),
            )).scalar_one()
            if unresolved:
                raise RuntimeError(f"{unresolved} old Card(s) have unresolved {target}; contraction refused.")
        notes_parent = sa.Table("notes", sa.MetaData(), autoload_with=bind, resolve_fks=False)
        apps_parent = sa.Table("study_applications", sa.MetaData(), autoload_with=bind, resolve_fks=False)
        incompatible = bind.execute(sa.select(sa.func.count()).select_from(
            cards.join(notes_parent, notes_parent.c.id == cards.c.note_id)
            .join(apps_parent, apps_parent.c.id == cards.c.application_id)
        ).where(sa.or_(
            notes_parent.c.note_type_id != apps_parent.c.note_type_id,
            cards.c.template_id != apps_parent.c.template_id,
        ))).scalar_one()
        if incompatible:
            raise RuntimeError(f"{incompatible} old Card(s) have incompatible application identity; contraction refused.")
    metadata, aliases, notes, applications, cutovers = _definitions()
    metadata.create_all(bind, checkfirst=True)
    if cards is not None:
        source_count = _archive(bind, cards, aliases)
        _capture_entities(bind, notes, applications, cutovers, source_count)
    _detach_references(bind)
    if cards is not None:
        remaining = [
            table for table in sa.inspect(bind).get_table_names()
            if any(fk.get("referred_table") == "cards" for fk in sa.inspect(bind).get_foreign_keys(table))
        ]
        if remaining:
            raise RuntimeError(f"Card foreign keys remain in {remaining}; contraction refused.")
        # Verify again after DDL (MySQL DDL may implicitly commit).
        _archive(bind, cards, aliases)
        op.drop_table("cards")


def downgrade() -> None:
    raise RuntimeError(
        "Derived-card contraction cannot be safely downgraded in place: new pair IDs have no old UUID. "
        "Restore a verified backup into an isolated database, reconcile writes, and use a compatible release. "
        "Historical wire IDs, session snapshots and review events must never be rewritten or deleted."
    )
