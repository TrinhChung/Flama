"""Bounded author publication queries for the single Published Base."""
from sqlalchemy import or_, select

from models import db
from models.note import Note
from models.deck import Deck
from models.note_draft import NoteDraft
from models.field_def import FieldDef
from models.study_progress_subject import StudyProgressSubject
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from app.repositories.deck_tree_query import collect_subtree_ids


def source_deck_ids(item, *, lock=False):
    if not lock:
        return collect_subtree_ids(item.source_deck_id) if item.source_deck_id else []
    seen, frontier = set(), {item.source_deck_id} if item.source_deck_id else set()
    while frontier:
        seen.update(frontier)
        children = set(db.session.execute(select(Deck.id).where(Deck.parent_id.in_(frontier))
            .order_by(Deck.id).with_for_update(read=True)).scalars())
        frontier = children - seen
    return sorted(seen)


def pending_notes(item, *, lock=False, scoped=False):
    deck_ids = source_deck_ids(item, lock=lock)
    if not deck_ids:
        return []
    if scoped:
        return _scoped_pending_notes(item, deck_ids)
    statement = select(Note, NoteDraft).outerjoin(NoteDraft, NoteDraft.note_id == Note.id).where(
        Note.user_id == item.owner_user_id,
        or_(Note.deck_id.in_(deck_ids), NoteDraft.deck_id.in_(deck_ids)),
        Note.deleted_at.is_(None),
        or_(Note.published_at.is_(None), NoteDraft.note_id.is_not(None)),
    ).order_by(Note.id).execution_options(include_deleted_notes=True, include_deleted_drafts=True)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return db.session.execute(statement).all()


def snapshot_head_matches(item):
    """Prove sparse discovery belongs to the head already locked by publish."""
    from models.deck_marketplace_item import DeckMarketplaceItem
    table = DeckMarketplaceItem.__table__
    names = ('current_release_id', 'working_revision', 'source_deck_id', 'source_note_type_id', 'owner_user_id')
    row = db.session.connection().execute(select(*(table.c[name] for name in names))
        .where(table.c.id == item.id)).one()
    return tuple(row) == tuple(getattr(item, name) for name in names)


def _scoped_pending_notes(item, deck_ids):
    """Discover sparse IDs at a validated snapshot, lock only those PKs.

    New Notes use a current scope-index read. Authors fence the actual Base
    and draft destinations before persistence; a publisher holding that head
    therefore cannot miss a newly committed draft in a matching snapshot.
    """
    note, draft = Note.__table__, NoteDraft.__table__
    names = ('id', 'content_revision', 'published_at', 'deleted_at', 'deck_id', 'user_id', 'note_type_id')
    snapshots = {row.id: tuple(row) for row in db.session.connection().execute(select(
        *(note.c[name] for name in names)).select_from(draft.join(note, note.c.id == draft.c.note_id)).where(
            note.c.user_id == item.owner_user_id, note.c.deleted_at.is_(None),
            or_(note.c.deck_id.in_(deck_ids), draft.c.deck_id.in_(deck_ids)))).all()}
    result = []
    ordered = sorted(snapshots)
    for offset in range(0, len(ordered), 500):
        ids = ordered[offset:offset + 500]
        notes = db.session.execute(select(Note).where(Note.id.in_(ids)).order_by(Note.id)
            .with_for_update().execution_options(populate_existing=True,
                include_deleted_notes=True, include_deleted_drafts=True)).scalars().all()
        drafts = {row.note_id: row for row in db.session.execute(select(NoteDraft).where(
            NoteDraft.note_id.in_(ids)).order_by(NoteDraft.note_id).with_for_update()
            .execution_options(populate_existing=True)).scalars()}
        if len(notes) != len(ids) or len(drafts) != len(ids) or any(
                tuple(getattr(row, name) for name in names) != snapshots[row.id] for row in notes):
            from app.services.deck_release_service import DeckReleaseError
            raise DeckReleaseError('WORKING_REVISION_STALE', 'The source changed during publication; refresh before retrying.', status=409)
        result.extend((row, drafts[row.id]) for row in notes)
    new_notes = db.session.execute(select(Note).with_hint(Note,
        'FORCE INDEX (ix_notes_user_deck)', dialect_name='mysql').where(
        Note.user_id == item.owner_user_id, Note.deck_id.in_(deck_ids),
        Note.published_at.is_(None), Note.deleted_at.is_(None)).order_by(Note.id)
        .with_for_update().execution_options(populate_existing=True,
            include_deleted_notes=True, include_deleted_drafts=True)).scalars().all()
    result.extend((row, None) for row in new_notes if row.id not in snapshots)
    return sorted(result, key=lambda pair: pair[0].id)


def schema_snapshot(item, *, lock=False, scoped=False):
    if not item.source_note_type_id:
        return {}
    statement = select(FieldDef).where(
        FieldDef.note_type_id == item.source_note_type_id,
    ).order_by(FieldDef.position, FieldDef.id).execution_options(include_deleted_fields=True)
    if lock:
        statement = statement.with_for_update(read=scoped).execution_options(populate_existing=True)
    rows = db.session.execute(statement).scalars()
    return {str(row.id): {
        "name": row.name, "field_type": row.field_type, "position": int(row.position or 0),
        "required": bool(row.required), "identity_role": row.identity_role,
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
    } for row in rows}


def progress_referenced_note_ids(note_ids, *, lock=True):
    """Canonical logical identity survives a missing advisory live-note FK."""
    result = set()
    ids = list(note_ids)
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        live = select(StudyProgressSubject.live_note_id).where(StudyProgressSubject.live_note_id.in_(chunk))
        missing_fk = select(StudyProgressSubject.logical_note_key).where(
            StudyProgressSubject.live_note_id.is_(None),
            StudyProgressSubject.logical_note_key.in_([value.encode('utf-8') for value in chunk]))
        result.update(db.session.execute(live.with_for_update() if lock else live).scalars())
        result.update(bytes(value).decode('utf-8') for value in db.session.execute(
            missing_fk.with_for_update() if lock else missing_fk).scalars())
    return result


def referenced_note_ids(note_ids):
    """Retain identity whenever learner state or a sparse edit refers to it."""
    ids = list(note_ids)
    result = progress_referenced_note_ids(ids)
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        result.update(db.session.execute(select(DeckCloneNoteFieldOverride.source_note_id).where(
            DeckCloneNoteFieldOverride.source_note_id.in_(chunk),
        ).with_for_update()).scalars())
    return result
