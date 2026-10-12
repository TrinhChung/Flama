"""Invalidate derived deck counts at the last outer transaction boundary.

Capture is lock free. SAVEPOINT frames retain ancestry until root completion;
rollback removes released descendants as well. Bulk content mutations use a
conservative epoch instead of enumerating Cards or installed learners.
"""

from dataclasses import dataclass, field

from flask import current_app, has_app_context
from sqlalchemy import event, inspect, select
from sqlalchemy.orm import Session
from sqlalchemy.orm.util import identity_key

from app.repositories.deck_count_snapshot_repository import (
    bump_content_revisions, bump_learner_revisions,
)
from models.card import card_key_pairs
from models.note import Note
from models.study_application import StudyApplication
from models.study_progress_subject import StudyProgressSubject

_KEY = "flama.deck_counts.transaction"
_BULK_TABLES = {
    "notes", "cards", "study_progress_subjects",
    "templates", "note_types", "study_applications", "users", "decks",
}
_SUBJECT_COLUMNS = (
    "learner_user_id", "logical_note_key", "live_note_id", "normalized_queue",
    "due_day", "due_at", "is_suspended", "is_buried", "buried_until_day",
)
_PROGRESS_COLUMNS = (
    "user_id", "card_id", "queue", "due_day", "due_at", "is_suspended",
    "is_buried", "buried_until_day",
)


@dataclass
class _Frame:
    content: set[int] = field(default_factory=set)
    learner: set[tuple[int, int]] = field(default_factory=set)


def writes_enabled(session):
    if "deck_count_write_enabled" in session.info:
        return bool(session.info["deck_count_write_enabled"])
    return bool(has_app_context() and current_app.config.get("DECK_COUNT_WRITE_ENABLED", False))


def _frame(session):
    root = session.get_transaction()
    if root is None:
        # do_orm_execute precedes SQLAlchemy's implicit autobegin when a bulk
        # mutation is the first statement. Establish its normal envelope now.
        session.begin()
        root = session.get_transaction()
    frames = session.info.setdefault(_KEY, {})
    return frames.setdefault(session.get_nested_transaction() or root, _Frame())


def invalidate_all_deck_counts(session):
    """Queue one global epoch for bulk operations with unknown membership."""
    session = session if isinstance(session, Session) else session()
    if writes_enabled(session):
        _frame(session).content.add(0)


def _values(obj, name):
    values = [getattr(obj, name, None)]
    values.extend(inspect(obj).attrs[name].history.deleted)
    return {value for value in values if value is not None}


def _changed(obj, columns):
    return any(inspect(obj).attrs[name].history.has_changes() for name in columns)


def _relationships(obj, name):
    state = inspect(obj)
    history = state.attrs[name].history
    return {value for value in (*history.added, *history.deleted, state.dict.get(name))
            if value is not None}


def _note_key(value):
    if isinstance(value, bytes):
        try:
            return value.decode("utf-8")
        except UnicodeDecodeError:
            return None
    return value if isinstance(value, str) else None


def _loaded_foreign_keys(session, model, ids, column):
    """Use loaded canonical rows without lazy loads or identity-map traversal."""
    known = {}
    for row_id in ids:
        row = session.identity_map.get(identity_key(model, row_id))
        if row is None:
            continue
        state = inspect(row)
        history = state.attrs[column].history
        if history.has_changes():
            if history.deleted:
                known[row_id] = history.deleted[0]
        elif column in state.dict:
            known[row_id] = state.dict[column]
    return known


@event.listens_for(Session, "before_flush")
def _capture_changes(session, flush_context, instances):
    if not writes_enabled(session):
        return
    lifecycle = session.new | session.deleted
    affected = [obj for obj in lifecycle | session.dirty if (
        isinstance(obj, Note) and (obj in lifecycle or _changed(obj, ("deck_id", "user_id", "note_type_id")))
        or isinstance(obj, StudyProgressSubject) and (obj in lifecycle or _changed(obj, _SUBJECT_COLUMNS))
    )]
    # Cards are derived (ADR P11): an occurrence that starts or stops being
    # ACTIVE changes the Cards of every Note of its NoteType.
    occurrences = [obj for obj in session.new | session.dirty if isinstance(obj, StudyApplication) and (
        obj in session.new or _changed(obj, ("status_code", "note_type_id")))]
    cascade = [obj for obj in session.deleted
               if obj.__table__.name in {"templates", "note_types", "study_applications", "users"}]
    if not affected and not cascade and not occurrences:
        return
    frame = _frame(session)
    if cascade:
        frame.content.add(0)
    note_type_ids = set().union(*(_values(obj, "note_type_id") for obj in occurrences))
    if any(obj.note_type_id is None for obj in occurrences):
        frame.content.add(0)  # A NoteType added in this flush has no ID yet.
    if note_type_ids:
        frame.content.update(int(value) for value in session.execute(
            select(Note.deck_id).where(Note.note_type_id.in_(sorted(note_type_ids)), Note.deck_id.is_not(None)).distinct()
        ).scalars())
    # Attribute replacement can hide an unloaded old foreign key. Do not
    # guess its prior scope; a single epoch safely covers that uncommon path.
    for obj in affected:
        names = (
            ("learner_user_id", "logical_note_key", "live_note_id") if isinstance(obj, StudyProgressSubject)
            else ()
        )
        if inspect(obj).persistent and any(
            inspect(obj).attrs[name].history.has_changes()
            and not inspect(obj).attrs[name].history.deleted for name in names
        ):
            frame.content.add(0)
    # Resolve before SQL flush so moved/deleted rows retain their old deck.
    # A presentation key names its Note; a legacy Card ID resolves via its registry row.
    note_ids = set()
    for obj in affected:
        if isinstance(obj, Note) and obj.id:
            note_ids.add(obj.id)
        elif isinstance(obj, StudyProgressSubject):
            note_ids.update(_values(obj, "live_note_id"))
            note_ids.update(key for value in _values(obj, "logical_note_key") if (key := _note_key(value)))
    notes = _loaded_foreign_keys(session, Note, note_ids, "deck_id")
    missing_notes = note_ids - notes.keys()
    if missing_notes:
        notes.update(session.execute(select(Note.id, Note.deck_id).where(Note.id.in_(missing_notes))).all())
    current_notes = {obj.id: obj.deck_id for obj in session.new | session.dirty | session.deleted
                     if isinstance(obj, Note) and obj.id is not None}

    def decks_for(ids):
        return {int(value) for note_id in ids for value in
                (notes.get(note_id), current_notes.get(note_id)) if value is not None}

    for obj in affected:
        if isinstance(obj, Note):
            frame.content.update(decks_for({obj.id}))
            frame.content.update(int(value) for value in _values(obj, "deck_id"))
        else:
            users = _values(obj, "learner_user_id")
            ids = _values(obj, "live_note_id") | {
                key for value in _values(obj, "logical_note_key") if (key := _note_key(value))
            }
            decks = decks_for(ids) or {0}
            if not users:
                frame.content.add(0)
            frame.learner.update((int(user_id), deck_id) for user_id in users for deck_id in decks)


@event.listens_for(Session, "do_orm_execute")
def _capture_bulk(execute_state):
    session = execute_state.session
    if not writes_enabled(session):
        return
    statement = execute_state.statement
    if execute_state.is_insert or execute_state.is_update or execute_state.is_delete:
        table = getattr(getattr(statement, "table", None), "name", None)
        if table not in _BULK_TABLES:
            return
        # This precise repository primitive inserts a pristine envelope or
        # performs an id=id no-op. Availability is written through ORM later.
        if table == "study_progress_subjects" and execute_state.execution_options.get("flama_pristine_subject_envelope"):
            return
        invalidate_all_deck_counts(session)
    elif getattr(statement, "text", None):
        import re
        sql = statement.text.lower()
        if re.search(r"\b(insert|update|delete|replace)\b", sql) and any(
                re.search(r"\b" + table + r"\b", sql) for table in _BULK_TABLES):
            invalidate_all_deck_counts(session)


@event.listens_for(Session, "before_commit")
def _finalize_outer(session):
    if not writes_enabled(session) or session.in_nested_transaction():
        return
    # All canonical domain changes must be flushed before acquiring revisions.
    session.flush()
    frames = session.info.get(_KEY, {})
    content = set().union(*(frame.content for frame in frames.values()))
    learner = set().union(*(frame.learner for frame in frames.values()))
    bump_content_revisions(session, content)
    bump_learner_revisions(session, learner)


@event.listens_for(Session, "after_soft_rollback")
def _discard_rollback(session, previous_transaction):
    frames = session.info.get(_KEY, {})
    for transaction in list(frames):
        ancestor = transaction
        while ancestor is not None:
            if ancestor is previous_transaction:
                del frames[transaction]
                break
            ancestor = ancestor.parent


@event.listens_for(Session, "after_transaction_end")
def _clear_root(session, transaction):
    if transaction.parent is None:
        session.info.pop(_KEY, None)
