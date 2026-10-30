"""Expand single Published Base and sparse author drafts (#263).

This leaves historical release tables intact for cutover rehearsal/rollback.
Backfill reflects the current historical release; the reviewed D6 cutover is a
separate operational step and must never be run implicitly during app startup.

Revision ID: 20261029_000076
Revises: 20261025_000075
"""
from __future__ import annotations

import json

from alembic import op
import sqlalchemy as sa

revision = "20261029_000076"
down_revision = "20261025_000075"
branch_labels = None
depends_on = None


def _add_nullable(bind, table, columns):
    existing = {row["name"] for row in sa.inspect(bind).get_columns(table)}
    missing = [(name, kind) for name, kind in columns if name not in existing]
    if bind.dialect.name == "mysql" and missing:
        # Explicit INSTANT: fail rather than silently rebuild a populated table.
        additions = ", ".join(
            f"ADD COLUMN `{name}` {kind.compile(dialect=bind.dialect)} NULL"
            for name, kind in missing
        )
        bind.exec_driver_sql(f"ALTER TABLE `{table}` {additions}, ALGORITHM=INSTANT")
    else:
        for name, kind in missing:
            op.add_column(table, sa.Column(name, kind, nullable=True))
    return {name for name, _kind in missing}


def _json(value):
    return json.loads(value) if isinstance(value, str) else value


def backfill_current_release(bind, *, notes=True, schema=True, missing_only=False):
    """Use only frozen legacy release evidence; never current author values."""
    items = bind.execute(sa.text(
        "SELECT i.id, i.published_schema_json, r.id AS release_id, r.sequence_no, r.published_at "
        "FROM deck_marketplace_items i JOIN deck_releases r ON r.id=i.current_release_id "
        "WHERE r.status='published' ORDER BY i.id"
    )).mappings().all()
    item_table = sa.table("deck_marketplace_items", sa.column("id", sa.String(36)),
                         sa.column("published_schema_json", sa.JSON))
    for item in items:
        parameters = {"item": item["id"], "sequence": item["sequence_no"]}
        memberships = bind.execute(sa.text(
            "SELECT entity_kind,entity_id FROM deck_release_entity_memberships "
            "WHERE deck_item_id=:item AND introduced_sequence<=:sequence "
            "AND (removed_sequence IS NULL OR removed_sequence>:sequence)"
        ), parameters).mappings().all()
        active_notes = [row["entity_id"] for row in memberships if row["entity_kind"] == "note"]
        if notes and active_notes:
            # Bounded batches keep MySQL placeholder size independent of deck size.
            statement = sa.text(
                "UPDATE notes SET published_at=:published WHERE id IN :ids "
                "AND published_at IS NULL"
            ).bindparams(sa.bindparam("ids", expanding=True))
            for offset in range(0, len(active_notes), 500):
                bind.execute(statement, {"published": item["published_at"],
                                        "ids": active_notes[offset:offset + 500]})
        if not schema or missing_only and item["published_schema_json"] is not None:
            continue
        fields = {}
        changes = bind.execute(sa.text(
            "SELECT c.entity_id,c.field_def_id,c.property_key,c.operation,c.after_value "
            "FROM deck_release_changes c JOIN deck_releases r ON r.id=c.release_id "
            "WHERE r.deck_item_id=:item AND r.status='published' "
            "AND c.release_sequence_no<=:sequence AND c.entity_kind='field_def' "
            "ORDER BY c.release_sequence_no,c.id"
        ), parameters).mappings()
        for change in changes:
            identity = str(change["field_def_id"] or change["entity_id"])
            payload = fields.setdefault(identity, {})
            if change["operation"] in {"add", "set"}:
                payload[change["property_key"]] = _json(change["after_value"])
            elif change["operation"] == "remove":
                payload.pop(change["property_key"], None)
        active_fields = {str(row["entity_id"]) for row in memberships if row["entity_kind"] == "field_def"}
        has_field_memberships = bind.execute(sa.text(
            "SELECT 1 FROM deck_release_entity_memberships "
            "WHERE deck_item_id=:item AND entity_kind='field_def' LIMIT 1"
        ), {"item": item["id"]}).first() is not None
        if has_field_memberships:
            fields = {key: value for key, value in fields.items() if key in active_fields}
        bind.execute(item_table.update().where(item_table.c.id == item["id"]).values(published_schema_json=fields))


def upgrade():
    bind = op.get_bind()
    _add_nullable(bind, "notes", [("published_at", sa.DateTime()), ("deleted_at", sa.DateTime())])
    _add_nullable(bind, "field_defs", [("deleted_at", sa.DateTime())])
    _add_nullable(bind, "deck_marketplace_items", [("published_schema_json", sa.JSON())])
    _add_nullable(bind, "deck_clone_note_field_overrides", [("base_hash", sa.String(64))])
    if not sa.inspect(bind).has_table("note_drafts"):
        options = {"mysql_engine": "InnoDB", "mysql_charset": "utf8mb4"} if bind.dialect.name == "mysql" else {}
        if bind.dialect.name == "mysql":
            # UUID foreign keys must inherit the referenced column's collation,
            # which can differ from both server and database defaults.
            collation = bind.execute(sa.text(
                "SELECT COLLATION_NAME FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME='notes' AND COLUMN_NAME='id'"
            )).scalar_one()
            options["mysql_collate"] = collation
        op.create_table(
            "note_drafts",
            sa.Column("note_id", sa.String(36), sa.ForeignKey("notes.id", ondelete="CASCADE", name="fk_note_drafts_note"), primary_key=True),
            sa.Column("field_values_by_id", sa.JSON(), nullable=False),
            sa.Column("tags", sa.JSON(), nullable=True),
            sa.Column("deck_id", sa.Integer(), nullable=True),
            sa.Column("op", sa.String(16), nullable=False, server_default="edit"),
            sa.Column("updated_at", sa.DateTime(), nullable=False),
            **options,
        )
    # MySQL DDL commits individually. If a previous attempt stopped after adding
    # columns but before backfill, a retry must finish the missing data as well.
    backfill_current_release(bind, missing_only=True)


def downgrade():
    bind = op.get_bind()
    # A code rollback needs the operational receipt, not destruction of drafts.
    if bind.execute(sa.text("SELECT 1 FROM note_drafts LIMIT 1")).first():
        raise RuntimeError("Restore author drafts with the cutover rollback receipt before downgrading.")
    for table in ("notes", "field_defs"):
        if bind.execute(sa.text(f"SELECT 1 FROM {table} WHERE deleted_at IS NOT NULL LIMIT 1")).first():
            raise RuntimeError("Cannot downgrade while tombstones exist; restore the pre-cutover backup.")
    op.drop_table("note_drafts")
    op.drop_column("deck_clone_note_field_overrides", "base_hash")
    op.drop_column("deck_marketplace_items", "published_schema_json")
    op.drop_column("field_defs", "deleted_at")
    op.drop_column("notes", "deleted_at")
    op.drop_column("notes", "published_at")
