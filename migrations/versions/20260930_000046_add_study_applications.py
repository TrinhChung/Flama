"""Add Phase 6 application occurrences and Note attribution snapshots.

Revision ID: 20260930_000046
Revises: 20260925_000045
Create Date: 2026-09-30 00:00:46

Additive only, no existing value changes:

* ``study_applications``: one compatibility occurrence per Template
  (``occurrence_key = 'compat'``, ``source_ord`` = the Template's current
  ``position``, which is what Anki ordinal mapping uses today);
* ``cards.application_id``: backfilled 1:1 from the Card's Template occurrence;
* ``review_events.note_id`` and ``connect_source_card_refs.note_id``: the
  Card's Note. Refs are backfilled here; events are backfilled after the
  deploy in committed batches (``flask study-phase6-attribution-backfill``,
  which also binds rows the previous release wrote while this migration ran).
  Unresolvable rows stay NULL.
* ``connect_source_card_refs.card_id`` becomes nullable with ``ON DELETE SET
  NULL``; ``(note_id, template_id)`` stops being unique on ``cards``.

Downgrade removes only derivable data and refuses when an occurrence other
than the compatibility one, or a Note snapshot that no live Card can
reproduce, would be lost.
"""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime
import uuid

from alembic import op
import sqlalchemy as sa


revision = "20260930_000046"
down_revision = "20260925_000045"
branch_labels = None
depends_on = None

APPLICATIONS = "study_applications"
COMPAT = "compat"
CARD_APPLICATION_INDEX = "ix_cards_application_id"
CARD_APPLICATION_FK = "fk_cards_application_id"
CARD_APPLICATION_UNIQUE = "uq_cards_note_application"
EVENT_NOTE_INDEX = "ix_review_events_user_note"
REF_NOTE_INDEX = "ix_connect_source_card_refs_note_id"
_INSERT_CHUNK = 500


def _columns(inspector, table: str) -> dict[str, dict]:
    return {column["name"]: column for column in inspector.get_columns(table)}


def _index_names(inspector, table: str) -> set[str]:
    names = {index["name"] for index in inspector.get_indexes(table)}
    names.update(
        constraint["name"]
        for constraint in inspector.get_unique_constraints(table)
        if constraint.get("name")
    )
    return names


def _create_applications_table(bind) -> None:
    if sa.inspect(bind).has_table(APPLICATIONS):
        return
    op.create_table(
        APPLICATIONS,
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column(
            "note_type_id",
            sa.String(36),
            sa.ForeignKey("note_types.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "template_id",
            sa.String(36),
            sa.ForeignKey("templates.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("occurrence_key", sa.String(64), nullable=False),
        sa.Column("source_ord", sa.Integer(), nullable=True),
        sa.Column("status_code", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "template_id",
            "occurrence_key",
            name="uq_study_applications_template_occurrence",
        ),
        sa.CheckConstraint(
            "status_code IN ('ACTIVE')",
            name="ck_study_applications_status",
        ),
    )
    op.create_index(
        "ix_study_applications_note_type_ord",
        APPLICATIONS,
        ["note_type_id", "source_ord"],
    )


def _backfill_compat_applications(bind) -> None:
    missing = bind.execute(
        sa.text(
            "SELECT t.id, t.note_type_id, t.position FROM templates t "
            "WHERE NOT EXISTS (SELECT 1 FROM study_applications a "
            "WHERE a.template_id = t.id AND a.occurrence_key = :compat) "
            "ORDER BY t.id"
        ),
        {"compat": COMPAT},
    ).all()
    now = datetime.utcnow().replace(microsecond=0)
    table = sa.table(
        APPLICATIONS,
        sa.column("id", sa.String),
        sa.column("note_type_id", sa.String),
        sa.column("template_id", sa.String),
        sa.column("occurrence_key", sa.String),
        sa.column("source_ord", sa.Integer),
        sa.column("status_code", sa.String),
        sa.column("created_at", sa.DateTime),
        sa.column("updated_at", sa.DateTime),
    )
    rows = [
        {
            "id": str(uuid.uuid4()),
            "note_type_id": str(row.note_type_id),
            "template_id": str(row.id),
            "occurrence_key": COMPAT,
            "source_ord": int(row.position) if row.position is not None else None,
            "status_code": "ACTIVE",
            "created_at": now,
            "updated_at": now,
        }
        for row in missing
    ]
    for start in range(0, len(rows), _INSERT_CHUNK):
        bind.execute(table.insert(), rows[start:start + _INSERT_CHUNK])


def _add_card_application(bind) -> None:
    inspector = sa.inspect(bind)
    if "application_id" not in _columns(inspector, "cards"):
        op.add_column("cards", sa.Column("application_id", sa.String(36), nullable=True))
    inspector = sa.inspect(bind)
    names = _index_names(inspector, "cards")
    if CARD_APPLICATION_INDEX not in names:
        op.create_index(CARD_APPLICATION_INDEX, "cards", ["application_id"])
    if CARD_APPLICATION_UNIQUE not in names:
        if bind.dialect.name == "sqlite":
            op.create_index(
                CARD_APPLICATION_UNIQUE, "cards", ["note_id", "application_id"], unique=True
            )
        else:
            op.create_unique_constraint(
                CARD_APPLICATION_UNIQUE, "cards", ["note_id", "application_id"]
            )
    if bind.dialect.name != "sqlite" and not any(
        fk.get("referred_table") == APPLICATIONS
        for fk in sa.inspect(bind).get_foreign_keys("cards")
    ):
        # Every application_id is still NULL, so there is nothing to validate;
        # without the check MySQL adds the FK in place instead of copying cards.
        with _foreign_key_checks_off(bind):
            op.create_foreign_key(
                CARD_APPLICATION_FK,
                "cards",
                APPLICATIONS,
                ["application_id"],
                ["id"],
                ondelete="CASCADE",
            )
    _bind_cards(bind)


def _bind_cards(bind) -> None:
    bind.execute(
        sa.text(
            "UPDATE cards SET application_id = (SELECT a.id FROM study_applications a "
            "WHERE a.template_id = cards.template_id AND a.occurrence_key = :compat) "
            "WHERE application_id IS NULL"
        ),
        {"compat": COMPAT},
    )


@contextmanager
def _foreign_key_checks_off(bind):
    if bind.dialect.name != "mysql":
        yield
        return
    bind.execute(sa.text("SET SESSION foreign_key_checks = 0"))
    try:
        yield
    finally:
        bind.execute(sa.text("SET SESSION foreign_key_checks = 1"))


def _add_note_snapshot(
    bind, *, table: str, index: str, index_columns: list[str], backfill: bool
) -> None:
    """Add ``note_id`` online; backfill here only when the table is small.

    ``review_events`` is backfilled afterwards in committed batches by
    ``flask study-review-event-note-backfill``: one statement over every row
    would lock the whole table (gaps included) and hold back learners'
    answers during the deploy.
    """

    inspector = sa.inspect(bind)
    if "note_id" not in _columns(inspector, table):
        op.add_column(table, sa.Column("note_id", sa.String(36), nullable=True))
    if index not in _index_names(sa.inspect(bind), table):
        op.create_index(index, table, index_columns)
    if backfill:
        bind.execute(
            sa.text(
                f"UPDATE {table} SET note_id = (SELECT c.note_id FROM cards c "
                f"WHERE c.id = {table}.card_id) WHERE note_id IS NULL"
            )
        )


REF_CARD_FK = "fk_connect_source_card_refs_card_id"


def _ref_card_fk(bind) -> dict | None:
    return next(
        (
            fk
            for fk in sa.inspect(bind).get_foreign_keys("connect_source_card_refs")
            if fk.get("referred_table") == "cards" and fk.get("constrained_columns") == ["card_id"]
        ),
        None,
    )


def _set_ref_card_on_delete(bind, *, keep_on_card_delete: bool) -> None:
    """``card_id`` NULL + SET NULL keeps the ref (and sync cursors) when a Card goes.

    SQLite schemas come from model metadata in tests; only MySQL is altered.
    """

    if bind.dialect.name == "sqlite":
        return
    fk = _ref_card_fk(bind)
    wanted = "SET NULL" if keep_on_card_delete else "CASCADE"
    if fk is not None and str((fk.get("options") or {}).get("ondelete") or "").upper() == wanted:
        return
    if fk is not None and fk.get("name"):
        op.drop_constraint(fk["name"], "connect_source_card_refs", type_="foreignkey")
    op.alter_column(
        "connect_source_card_refs",
        "card_id",
        existing_type=sa.String(36),
        nullable=keep_on_card_delete,
    )
    # Every card_id was valid under the previous constraint; skip re-validation
    # so the constraint is added in place.
    with _foreign_key_checks_off(bind):
        op.create_foreign_key(
            REF_CARD_FK,
            "connect_source_card_refs",
            "cards",
            ["card_id"],
            ["id"],
            ondelete=wanted,
        )


NOTE_TEMPLATE_UNIQUE = "uq_cards_note_template"


def _drop_note_template_unique(bind) -> None:
    """(note_id, application_id) now carries uniqueness; a Template may repeat."""

    if NOTE_TEMPLATE_UNIQUE not in _index_names(sa.inspect(bind), "cards"):
        return
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("cards") as batch:
            batch.drop_constraint(NOTE_TEMPLATE_UNIQUE, type_="unique")
    else:
        op.drop_constraint(NOTE_TEMPLATE_UNIQUE, "cards", type_="unique")


def _restore_note_template_unique(bind) -> None:
    if NOTE_TEMPLATE_UNIQUE in _index_names(sa.inspect(bind), "cards"):
        return
    duplicates = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM (SELECT note_id, template_id FROM cards "
            "GROUP BY note_id, template_id HAVING COUNT(*) > 1) d"
        )
    ).scalar_one()
    if duplicates:
        raise RuntimeError(
            f"Cannot restore {NOTE_TEMPLATE_UNIQUE}: {duplicates} Note(s) apply a Template twice."
        )
    if bind.dialect.name == "sqlite":
        with op.batch_alter_table("cards") as batch:
            batch.create_unique_constraint(NOTE_TEMPLATE_UNIQUE, ["note_id", "template_id"])
    else:
        op.create_unique_constraint(NOTE_TEMPLATE_UNIQUE, "cards", ["note_id", "template_id"])


def _verify(bind, *, existing_card_ids: set[str]) -> None:
    inspector = sa.inspect(bind)
    if not inspector.has_table(APPLICATIONS):
        raise RuntimeError("study_applications was not created.")
    for table in ("cards", "review_events", "connect_source_card_refs"):
        column = "application_id" if table == "cards" else "note_id"
        found = _columns(inspector, table).get(column)
        if found is None or not found["nullable"] or not isinstance(found["type"], sa.String):
            raise RuntimeError(f"{table}.{column} has an incompatible contract.")
    unmapped = {
        str(card_id)
        for card_id in bind.execute(
            sa.text("SELECT id FROM cards WHERE application_id IS NULL")
        ).scalars()
    }
    if unmapped & existing_card_ids:
        raise RuntimeError(
            f"{len(unmapped & existing_card_ids)} Card(s) have no application occurrence after backfill."
        )
    if unmapped:
        # The previous release keeps serving while the deploy migrates; Cards
        # it created just now are bound by `flask study-phase6-attribution-backfill`.
        print(f"[20260930_000046] {len(unmapped)} Card(s) created during the migration are left "
              "for study-phase6-attribution-backfill.")
    mismatched = bind.execute(
        sa.text(
            "SELECT COUNT(*) FROM cards c JOIN study_applications a ON a.id = c.application_id "
            "JOIN templates t ON t.id = a.template_id "
            "WHERE a.template_id <> c.template_id OR a.note_type_id <> t.note_type_id"
        )
    ).scalar_one()
    if mismatched:
        raise RuntimeError(f"{mismatched} Card(s) point at another Template's occurrence.")


def upgrade() -> None:
    bind = op.get_bind()
    existing_card_ids = {str(card_id) for card_id in bind.execute(sa.text("SELECT id FROM cards")).scalars()}
    _create_applications_table(bind)
    _backfill_compat_applications(bind)
    _add_card_application(bind)
    _add_note_snapshot(
        bind, table="review_events", index=EVENT_NOTE_INDEX, index_columns=["user_id", "note_id"],
        backfill=False,
    )
    _add_note_snapshot(
        bind, table="connect_source_card_refs", index=REF_NOTE_INDEX, index_columns=["note_id"],
        backfill=True,
    )
    _set_ref_card_on_delete(bind, keep_on_card_delete=True)
    _drop_note_template_unique(bind)
    # Templates and Cards the serving release wrote during the steps above.
    _backfill_compat_applications(bind)
    _bind_cards(bind)
    _verify(bind, existing_card_ids=existing_card_ids)


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    if inspector.has_table(APPLICATIONS):
        extra = bind.execute(
            sa.text("SELECT COUNT(*) FROM study_applications WHERE occurrence_key <> :compat"),
            {"compat": COMPAT},
        ).scalar_one()
        if extra:
            raise RuntimeError(
                "Cannot drop application occurrences: repeated applications exist."
            )
    unbound_refs = bind.execute(
        sa.text("SELECT COUNT(*) FROM connect_source_card_refs WHERE card_id IS NULL")
    ).scalar_one()
    if unbound_refs:
        raise RuntimeError(
            f"Cannot restore NOT NULL card_id: {unbound_refs} Connect card ref(s) outlived "
            "their Card and keep only Note lineage."
        )
    for table in ("review_events", "connect_source_card_refs"):
        if "note_id" not in _columns(sa.inspect(bind), table):
            continue
        orphaned = bind.execute(
            sa.text(
                f"SELECT COUNT(*) FROM {table} x LEFT JOIN cards c ON c.id = x.card_id "
                "WHERE x.note_id IS NOT NULL AND (c.id IS NULL OR c.note_id <> x.note_id)"
            )
        ).scalar_one()
        if orphaned:
            raise RuntimeError(
                f"Cannot drop {table}.note_id: {orphaned} row(s) keep Note attribution "
                "that no live Card can reproduce."
            )
    _restore_note_template_unique(bind)
    _set_ref_card_on_delete(bind, keep_on_card_delete=False)
    names = _index_names(sa.inspect(bind), "review_events")
    if EVENT_NOTE_INDEX in names:
        op.drop_index(EVENT_NOTE_INDEX, table_name="review_events")
    if "note_id" in _columns(sa.inspect(bind), "review_events"):
        op.drop_column("review_events", "note_id")
    names = _index_names(sa.inspect(bind), "connect_source_card_refs")
    if REF_NOTE_INDEX in names:
        op.drop_index(REF_NOTE_INDEX, table_name="connect_source_card_refs")
    if "note_id" in _columns(sa.inspect(bind), "connect_source_card_refs"):
        op.drop_column("connect_source_card_refs", "note_id")
    if "application_id" in _columns(sa.inspect(bind), "cards"):
        if bind.dialect.name != "sqlite":
            for fk in sa.inspect(bind).get_foreign_keys("cards"):
                if fk.get("referred_table") == APPLICATIONS and fk.get("name"):
                    op.drop_constraint(fk["name"], "cards", type_="foreignkey")
        names = _index_names(sa.inspect(bind), "cards")
        if CARD_APPLICATION_UNIQUE in names:
            if bind.dialect.name == "sqlite":
                op.drop_index(CARD_APPLICATION_UNIQUE, table_name="cards")
            else:
                op.drop_constraint(CARD_APPLICATION_UNIQUE, "cards", type_="unique")
        if CARD_APPLICATION_INDEX in _index_names(sa.inspect(bind), "cards"):
            op.drop_index(CARD_APPLICATION_INDEX, table_name="cards")
        if bind.dialect.name == "sqlite":
            with op.batch_alter_table("cards") as batch:
                batch.drop_column("application_id")
        else:
            op.drop_column("cards", "application_id")
    if sa.inspect(bind).has_table(APPLICATIONS):
        # The (note_type_id, source_ord) index backs the note_type FK on
        # MySQL, so it is dropped with the table rather than on its own.
        op.drop_table(APPLICATIONS)
