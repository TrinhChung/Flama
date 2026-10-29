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


def pending_notes(item, *, lock=False):
    deck_ids = source_deck_ids(item, lock=lock)
    if not deck_ids:
        return []
    statement = select(Note, NoteDraft).outerjoin(NoteDraft, NoteDraft.note_id == Note.id).where(
        Note.user_id == item.owner_user_id,
        or_(Note.deck_id.in_(deck_ids), NoteDraft.deck_id.in_(deck_ids)),
        Note.deleted_at.is_(None),
        or_(Note.published_at.is_(None), NoteDraft.note_id.is_not(None)),
    ).order_by(Note.id).execution_options(include_deleted_notes=True, include_deleted_drafts=True)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    return db.session.execute(statement).all()


def schema_snapshot(item, *, lock=False):
    if not item.source_note_type_id:
        return {}
    statement = select(FieldDef).where(
        FieldDef.note_type_id == item.source_note_type_id,
    ).order_by(FieldDef.position, FieldDef.id).execution_options(include_deleted_fields=True)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    rows = db.session.execute(statement).scalars()
    return {str(row.id): {
        "name": row.name, "field_type": row.field_type, "position": int(row.position or 0),
        "required": bool(row.required), "identity_role": row.identity_role,
        "deleted_at": row.deleted_at.isoformat() if row.deleted_at else None,
    } for row in rows}


def referenced_note_ids(note_ids):
    """Retain identity whenever learner state or a sparse edit refers to it."""
    result = set()
    ids = list(note_ids)
    for offset in range(0, len(ids), 500):
        chunk = ids[offset:offset + 500]
        result.update(db.session.execute(select(StudyProgressSubject.live_note_id).where(
            StudyProgressSubject.live_note_id.in_(chunk),
        ).with_for_update()).scalars())
        result.update(db.session.execute(select(DeckCloneNoteFieldOverride.source_note_id).where(
            DeckCloneNoteFieldOverride.source_note_id.in_(chunk),
        ).with_for_update()).scalars())
    return result
