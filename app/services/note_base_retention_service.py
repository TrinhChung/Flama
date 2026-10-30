"""Bounded 90-day tombstone cleanup; never discard referenced Note identity."""
from datetime import datetime, timedelta, timezone

from sqlalchemy import func, or_, select

from models import db
from models.note import Note
from models.note_type import NoteType
from models.note_draft import NoteDraft
from models.field_def import FieldDef
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_marketplace_item import DeckMarketplaceItem
from app.services.note_base_context import base_maintenance, published_base_enabled


def run_retention(*, apply=False, limit=200, now=None, after=None):
    if not published_base_enabled():
        raise ValueError("Published Base must be active before retention runs")
    if isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 1000:
        raise ValueError("limit must be between 1 and 1000")
    cutoff = (now or datetime.now(timezone.utc).replace(tzinfo=None)) - timedelta(days=90)
    if after is not None:
        from uuid import UUID
        after = str(UUID(after))
    notes = db.session.execute(select(Note).where(Note.deleted_at <= cutoff,
        Note.id > after if after else True).order_by(Note.id)
        .limit(limit).execution_options(include_deleted_notes=True, include_deleted_drafts=True)).scalars().all()
    expired_override_query = select(DeckCloneNoteFieldOverride).join(Note,
        Note.id == DeckCloneNoteFieldOverride.source_note_id).outerjoin(FieldDef,
            or_(FieldDef.id == DeckCloneNoteFieldOverride.source_field_def_id,
                FieldDef.id == DeckCloneNoteFieldOverride.field_identity_key)).where(
            or_(Note.deleted_at <= cutoff, FieldDef.deleted_at <= cutoff),
            DeckCloneNoteFieldOverride.id > after if after else True,
            DeckCloneNoteFieldOverride.updated_at <= cutoff).order_by(DeckCloneNoteFieldOverride.id)
    overrides = db.session.execute(expired_override_query.limit(limit).execution_options(
        include_deleted_notes=True, include_deleted_drafts=True, include_deleted_fields=True)).scalars().all()
    fields = db.session.execute(select(FieldDef).where(FieldDef.deleted_at <= cutoff,
        FieldDef.id > after if after else True)
        .order_by(FieldDef.id).limit(limit).execution_options(include_deleted_fields=True)).scalars().all()
    # A shared UUID cursor advances past retained references as well as purges.
    # Trim all three candidate streams at the first full page boundary, so a
    # resumed run neither skips candidates nor repeatedly counts a later page.
    boundaries = [rows[-1].id for rows in (notes, overrides, fields) if len(rows) == limit]
    next_cursor = min(boundaries) if boundaries else None
    if next_cursor:
        notes, overrides, fields = ([row for row in rows if row.id <= next_cursor]
            for rows in (notes, overrides, fields))
    snapshots = []
    if apply:
        # Use current locking reads after taking the same global lock order as
        # publish. An earlier REPEATABLE READ snapshot cannot decide deletion.
        lock_ids = sorted({row.id for row in notes} | {row.source_note_id for row in overrides})
        type_ids = sorted({row.note_type_id for row in notes + fields})
        if lock_ids:
            type_ids = sorted(set(type_ids) | set(db.session.execute(select(Note.note_type_id).where(
                Note.id.in_(lock_ids)).execution_options(include_deleted_notes=True, include_deleted_drafts=True)).scalars()))
        if type_ids:
            snapshots = db.session.execute(select(DeckMarketplaceItem.published_schema_json).where(
                DeckMarketplaceItem.source_note_type_id.in_(type_ids)).order_by(DeckMarketplaceItem.id)
                .with_for_update()).scalars().all()
            db.session.execute(select(NoteType.id).where(NoteType.id.in_(type_ids)).order_by(NoteType.id).with_for_update()).all()
        if lock_ids:
            current = db.session.execute(select(Note).where(Note.id.in_(lock_ids)).order_by(Note.id)
                .with_for_update().execution_options(include_deleted_notes=True, include_deleted_drafts=True,
                    populate_existing=True)).scalars().all()
            current = {row.id: row for row in current}
            notes = [current[row.id] for row in notes if row.id in current and current[row.id].deleted_at
                and current[row.id].deleted_at <= cutoff]
        if overrides:
            overrides = db.session.execute(expired_override_query.where(
                DeckCloneNoteFieldOverride.id.in_([row.id for row in overrides]))
                .with_for_update().execution_options(include_deleted_notes=True, include_deleted_drafts=True,
                    include_deleted_fields=True, populate_existing=True)).scalars().all()
        if fields:
            fields = db.session.execute(select(FieldDef).where(FieldDef.id.in_([row.id for row in fields]),
                FieldDef.deleted_at <= cutoff).order_by(FieldDef.id).with_for_update()
                .execution_options(include_deleted_fields=True, populate_existing=True)).scalars().all()
    else:
        snapshots = db.session.execute(select(DeckMarketplaceItem.published_schema_json)).scalars().all()
    def census(statement):
        return db.session.execute(statement.with_for_update() if apply else statement).scalars()
    # Simulate expired-override removal when deciding which Notes are eligible.
    expired_override_ids = {row.id for row in overrides}
    note_ids = [row.id for row in notes]
    from app.repositories.note_base_repository import progress_referenced_note_ids
    referenced = progress_referenced_note_ids(note_ids, lock=apply)
    if note_ids:
        referenced.update(census(select(DeckCloneNoteFieldOverride.source_note_id).where(
            DeckCloneNoteFieldOverride.source_note_id.in_(note_ids),
            DeckCloneNoteFieldOverride.id.not_in(expired_override_ids))))
        referenced.update(census(select(NoteDraft.note_id).where(NoteDraft.note_id.in_(note_ids))))
    purge_notes = [row for row in notes if row.id not in referenced]
    field_ids = {row.id for row in fields}
    referenced_fields = set()
    if field_ids:
        statement = select(DeckCloneNoteFieldOverride).where(
            or_(DeckCloneNoteFieldOverride.source_field_def_id.in_(field_ids),
                DeckCloneNoteFieldOverride.field_identity_key.in_(field_ids)),
            DeckCloneNoteFieldOverride.id.not_in(expired_override_ids))
        for row in census(statement):
            referenced_fields.add(row.source_field_def_id)
            referenced_fields.add(row.field_identity_key)
        for snapshot in snapshots:
            if isinstance(snapshot, dict):
                referenced_fields.update(identity for identity, payload in snapshot.items()
                    if identity in field_ids and isinstance(payload, dict) and not payload.get("deleted_at"))
        # Fetch identity keys only for drafts referencing candidate fields.
        paths = [f'$."{identity}"' for identity in sorted(field_ids)]
        statement = select(func.json_keys(NoteDraft.field_values_by_id)).where(
            func.json_contains_path(NoteDraft.field_values_by_id, "one", *paths) == 1)
        import json
        for keys in census(statement):
            referenced_fields.update(set(json.loads(keys) if isinstance(keys, str) else keys or []) & field_ids)
    purge_fields = [row for row in fields if row.id not in referenced_fields]
    report = {"apply": bool(apply), "retention_days": 90, "limit": limit, "next_cursor": next_cursor,
        "expired_overrides": len(overrides), "notes": len(purge_notes), "fields": len(purge_fields),
        "notes_retained_for_references": len(notes) - len(purge_notes)}
    if apply:
        try:
            with base_maintenance("90-day published content retention", session=db.session):
                for row in overrides + purge_notes + purge_fields:
                    db.session.delete(row)
                db.session.flush()
            db.session.commit()
        except Exception:
            db.session.rollback()
            raise
    else:
        db.session.rollback()
    return report
