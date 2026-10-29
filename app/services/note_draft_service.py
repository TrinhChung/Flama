"""Sparse author drafts.  The persisted Note row is always Published Base.

Delta envelopes distinguish a removed value from a stored JSON null.  Retained
undeclared labels use the existing ``extra:<hash>`` identities; ordinary Field
UUIDs never change when labels or order change.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import logging

from sqlalchemy import inspect, select, tuple_, update
from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import set_committed_value

from app.services.note_base_context import base_write_authority, published_base_enabled


_CACHE = "flama.note_drafts.loaded"
_log = logging.getLogger(__name__)
_CONTENT = ("field_values_by_id", "field_values_extras", "tags", "deck_id",
            "note_type_id", "user_id", "content_revision", "updated_at")


def merge_draft_values(base_by_id, base_extras, draft_delta):
    """Return fresh ``(by_id, extras)`` dictionaries without changing Base."""
    values, extras = deepcopy(base_by_id or {}), deepcopy(base_extras or {})
    for identity, change in (draft_delta or {}).items():
        if identity.startswith("meta:"):
            continue
        if not isinstance(change, dict) or change.get("op") not in {"set", "remove"}:
            raise ValueError("Invalid sparse Note draft operation")
        target = extras if identity.startswith("extra:") else values
        key = change.get("label") if identity.startswith("extra:") else identity
        if not isinstance(key, str):
            raise ValueError("An undeclared draft identity requires its captured label")
        if change["op"] == "remove":
            target.pop(key, None)
        else:
            if "value" not in change:
                raise ValueError("A set draft operation requires a value")
            target[key] = deepcopy(change["value"])
    return values, extras


def make_draft_delta(note_type_id, base_by_id, base_extras, values_by_id, extras):
    from app.services.field_value_runtime_service import extra_field_identity_key
    from app.services.field_value_identity_service import typed_value_equal
    delta = {}
    for key in (base_by_id or {}).keys() | (values_by_id or {}).keys():
        if key not in values_by_id:
            delta[key] = {"op": "remove"}
        elif key not in base_by_id or not typed_value_equal(values_by_id[key], base_by_id[key]):
            delta[key] = {"op": "set", "value": deepcopy(values_by_id[key])}
    for label in (base_extras or {}).keys() | (extras or {}).keys():
        key = extra_field_identity_key(note_type_id, label)
        if label not in extras:
            delta[key] = {"op": "remove", "label": label}
        elif label not in base_extras or not typed_value_equal(extras[label], base_extras[label]):
            delta[key] = {"op": "set", "label": label, "value": deepcopy(extras[label])}
    return delta


def clear_note_draft_cache(session):
    session.info.pop(_CACHE, None)


def stage_note_delete(note):
    """Stage a published deletion before any progress/media lifecycle cleanup."""
    from models.note_draft import NoteDraft
    session = object_session(note)
    if session is None or not published_base_enabled() or note.published_at is None:
        raise ValueError("Only a persisted Published Note can have a deletion draft")
    draft = get_note_draft(note)
    if draft is None:
        draft = NoteDraft(note_id=note.id, field_values_by_id={})
        session.add(draft)
    draft.op = "delete"
    draft.updated_at = datetime.utcnow()
    clear_note_draft_cache(session)
    return draft


def lock_and_bump_note_listings(session, notes, *, bump=True, schema_type_ids=()):
    """Fence author writes before the shared schema/Note locks.

    Lock candidates by owner and NoteType (including a draft move's source),
    then bump only listings covering a changed Note. There is no install scan.
    The increment is per flush; a later author save is a new working revision.
    """
    if not published_base_enabled() or base_write_authority() or not (notes or schema_type_ids):
        return
    from models.deck import Deck
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.note import Note
    from models.note_draft import NoteDraft
    from models.note_type import NoteType
    schema_type_ids = set(schema_type_ids) - {None}
    scopes = {(note.user_id, note.note_type_id) for note in notes
              if note.user_id is not None and note.note_type_id is not None}
    if schema_type_ids:
        scopes.update(session.connection().execute(select(NoteType.__table__.c.user_id,
            NoteType.__table__.c.id).where(NoteType.__table__.c.id.in_(schema_type_ids))).all())
    if not scopes:
        return
    table = DeckMarketplaceItem.__table__
    items = session.connection().execute(select(table).where(tuple_(
        table.c.owner_user_id, table.c.source_note_type_id).in_(sorted(scopes)))
        .order_by(table.c.id).with_for_update()).mappings().all()
    if not items or not bump:
        return
    deck_ids = {note.deck_id for note in notes if note.deck_id is not None}
    persistent_ids = [note.id for note in notes if inspect(note).persistent]
    if persistent_ids:
        deck_ids.update(value for value in session.connection().execute(select(Note.__table__.c.deck_id)
            .where(Note.__table__.c.id.in_(persistent_ids))).scalars() if value is not None)
        deck_ids.update(value for value in session.connection().execute(select(NoteDraft.__table__.c.deck_id)
            .where(NoteDraft.__table__.c.note_id.in_(persistent_ids))).scalars() if value is not None)
    for draft in session.new | session.dirty:
        if isinstance(draft, NoteDraft) and draft.deck_id is not None:
            deck_ids.add(draft.deck_id)
    from app.services.deck_count_projection_service import invalidate_learner_deck_counts
    invalidate_learner_deck_counts(session, {
        (note.user_id, deck_id) for note in notes if note.published_at is not None
        for deck_id in deck_ids | {0}
    })
    # One query per tree depth, shared by the entire changed Note batch.
    ancestors, frontier = set(), set(deck_ids)
    while frontier:
        ancestors.update(frontier)
        parents = set(session.connection().execute(select(Deck.__table__.c.parent_id)
            .where(Deck.__table__.c.id.in_(frontier))).scalars()) - {None}
        frontier = parents - ancestors
    for item in items:
        if item["source_deck_id"] not in ancestors and item["source_note_type_id"] not in schema_type_ids:
            continue
        revision = int(item["working_revision"] or 0) + 1
        session.connection().execute(update(table).where(table.c.id == item["id"])
            .values(working_revision=revision))
        loaded = session.identity_map.get(session.identity_key(DeckMarketplaceItem, item["id"]))
        if loaded is not None:
            set_committed_value(loaded, "working_revision", revision)


def load_note_drafts(session, notes):
    """Load only the requested/session page, once, with no process cache."""
    from models.note_draft import NoteDraft
    cache = session.info.setdefault(_CACHE, {})
    ids = {note.id for note in notes if note.id and getattr(note, "published_at", None)}
    missing = ids - cache.keys()
    if missing:
        with session.no_autoflush:
            cache.update(dict.fromkeys(missing))
            for draft in session.execute(select(NoteDraft).where(NoteDraft.note_id.in_(missing))).scalars():
                cache[draft.note_id] = draft
    for draft in session.new | session.dirty | session.deleted:
        if isinstance(draft, NoteDraft) and draft.note_id in ids:
            cache[draft.note_id] = None if draft in session.deleted else draft
    return {identity: cache.get(identity) for identity in ids}


def get_note_draft(note):
    if not published_base_enabled() or not getattr(note, "published_at", None):
        return None
    session = object_session(note)
    if session is None:
        return note.__dict__.get("_captured_note_draft")
    from models.note import Note
    # A property access batches the Notes already fetched for the current page.
    # Loading another page in the same transaction only queries its misses.
    notes = [row for row in session.identity_map.values() if isinstance(row, Note)]
    return load_note_drafts(session, notes).get(note.id)


def apply_draft_values(note, draft=None):
    if draft is None:
        draft = get_note_draft(note)
    return merge_draft_values(note.field_values_by_id, note.field_values_extras,
                              draft.field_values_by_id if draft is not None else {})


def effective_note_metadata(note, draft=None):
    if draft is None:
        draft = get_note_draft(note)
    if draft is None:
        return {"tags": deepcopy(note.tags), "deck_id": note.deck_id, "op": "edit"}
    delta = draft.field_values_by_id or {}
    deck_id = draft.deck_id if draft.deck_id is not None else note.deck_id
    if "meta:deck_id" in delta:
        deck_id = delta["meta:deck_id"]["value"]
    return {"tags": deepcopy(draft.tags if draft.tags is not None else note.tags),
            "deck_id": deck_id, "op": draft.op}


def redirect_published_note_writes(session, notes):
    """Called by the existing identity flush hook after value encoding.

    Lock order is schema parent (owned by that hook), then Notes, then drafts.
    Read Base in one batch instead of relying on possibly expired ORM history.
    """
    if not published_base_enabled():
        return set()
    from models.note import Note
    from models.note_draft import NoteDraft
    candidates = {note for note in notes if inspect(note).persistent}
    candidates.update(note for note in session.deleted if isinstance(note, Note))
    if not candidates:
        return set()
    columns = [Note.__table__.c.id, Note.__table__.c.published_at,
               Note.__table__.c.deleted_at, *(Note.__table__.c[name] for name in _CONTENT)]
    bases = {row.id: row for row in session.connection().execute(
        select(*columns).where(Note.__table__.c.id.in_([note.id for note in candidates]))
        .order_by(Note.__table__.c.id).with_for_update()).mappings()}
    authority = base_write_authority()
    if authority:
        if authority[0] == "maintenance":
            _log.warning("note_base_maintenance notes=%s reason=%s",
                         sorted(bases), authority[1])
        return set()
    redirected = set()
    drafts = {row.note_id: row for row in session.execute(select(NoteDraft).where(
        NoteDraft.note_id.in_(sorted(bases))).with_for_update()).scalars()}
    for row in session.new:
        if isinstance(row, NoteDraft):
            drafts[row.note_id] = row
    for note in sorted(candidates, key=lambda row: row.id):
        base = bases.get(note.id)
        if base is None or base["published_at"] is None:
            continue
        if base["deleted_at"] is not None:
            raise ValueError("A deleted Published Note cannot be edited or resurrected")
        if note.user_id != base["user_id"] or note.note_type_id != base["note_type_id"]:
            raise ValueError("A Published Note cannot change its owner or NoteType")
        deleting = note in session.deleted
        delta = make_draft_delta(base["note_type_id"], base["field_values_by_id"],
            base["field_values_extras"], note.field_values_by_id, note.field_values_extras)
        tags = deepcopy(note.tags) if note.tags != base["tags"] else None
        deck_id = note.deck_id if note.deck_id != base["deck_id"] else None
        if note.deck_id is None and base["deck_id"] is not None:
            delta["meta:deck_id"] = {"op": "set", "value": None}
        draft = drafts.get(note.id)
        # Metadata not explicitly touched by this save retains the existing
        # draft metadata; field edits use the full effective value dictionary.
        if draft is not None:
            intent = note.__dict__.get("_pending_note_metadata", {})
            if ("_pending_named_field_values" not in note.__dict__
                    and not inspect(note).attrs.field_values_by_id.history.has_changes()
                    and not inspect(note).attrs.field_values_extras.history.has_changes()):
                delta = deepcopy(draft.field_values_by_id or {})
            if "tags" not in intent and not inspect(note).attrs.tags.history.has_changes():
                tags = draft.tags
            if "deck_id" not in intent and not inspect(note).attrs.deck_id.history.has_changes():
                deck_id = draft.deck_id
                if "meta:deck_id" in (draft.field_values_by_id or {}):
                    delta["meta:deck_id"] = deepcopy(draft.field_values_by_id["meta:deck_id"])
            elif "deck_id" in intent:
                if note.deck_id is None and base["deck_id"] is not None:
                    delta["meta:deck_id"] = {"op": "set", "value": None}
                else:
                    delta.pop("meta:deck_id", None)
        if deleting:
            session.add(note)  # cancel the ORM delete and its cascaded children
        if deleting or delta or tags is not None or deck_id is not None:
            if draft is None:
                draft = NoteDraft(note_id=note.id)
                session.add(draft)
            draft.field_values_by_id = delta
            draft.tags, draft.deck_id = tags, deck_id
            draft.op = "delete" if deleting else "edit"
            draft.updated_at = datetime.utcnow()
        elif draft is not None:
            if inspect(draft).pending:
                session.expunge(draft)
            else:
                session.delete(draft)
        for name in _CONTENT:
            set_committed_value(note, name, deepcopy(base[name]))
        # Direct column mutations must not move publication/tombstone authority.
        set_committed_value(note, "published_at", base["published_at"])
        set_committed_value(note, "deleted_at", base["deleted_at"])
        redirected.add(note)
    clear_note_draft_cache(session)
    return redirected
