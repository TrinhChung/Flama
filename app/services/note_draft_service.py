"""Sparse author drafts.  The persisted Note row is always Published Base.

Delta envelopes distinguish a removed value from a stored JSON null.  Retained
undeclared labels use the existing ``extra:<hash>`` identities; ordinary Field
UUIDs never change when labels or order change.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime
import logging

from sqlalchemy import inspect, select, update
from sqlalchemy.orm import make_transient, make_transient_to_detached, object_session
from sqlalchemy.orm.attributes import NO_VALUE, flag_modified, set_committed_value

from app.services.note_base_context import (
    author_drafts_visible, base_write_authority, published_base_enabled, require_note_author_write,
)


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
    for key in ('flama.note_drafts.fenced_roots', 'flama.note_drafts.fenced_parents', 'flama.note_drafts.bumped_heads'):
        session.info.pop(key, None)


def cache_note_draft(session, draft, *, remove=False, note_id=None):
    """Mirror only this Draft's lifecycle in the transaction-local lookup."""
    state = inspect(draft)
    identity = note_id or (state.identity[0] if state.identity else state.dict.get("note_id"))
    if identity is None:
        note = state.dict.get("note")
        identity = inspect(note).identity[0] if note is not None and inspect(note).identity else None
    if identity is not None:
        session.info.setdefault(_CACHE, {})[identity] = None if remove else draft


def stage_note_delete(note):
    """Stage a published deletion before any progress/media lifecycle cleanup."""
    from models.note_draft import NoteDraft
    session = object_session(note)
    if session is None or not published_base_enabled() or note.published_at is None:
        raise ValueError("Only a persisted Published Note can have a deletion draft")
    require_note_author_write(note.user_id)
    draft = get_note_draft(note)
    if draft is None:
        draft = NoteDraft(note_id=note.id, field_values_by_id={})
        session.add(draft)
    draft.op = "delete"
    draft.updated_at = datetime.utcnow()
    cache_note_draft(session, draft)
    return draft


def lock_and_bump_note_listings(session, notes, *, bump=True, schema_type_ids=(), deck_ids=(), late=False, all_owners=False):
    """Fence covering listing heads, then schema/Notes; late fences never wait.

    Exact existing source-root index probes avoid locking sibling listings.
    Transaction-local entries remain valid while their row/range locks are held.
    """
    if not published_base_enabled() or base_write_authority() or not (notes or schema_type_ids):
        return
    from models.deck import Deck
    from models.deck_marketplace_item import DeckMarketplaceItem
    from app.services.field_value_identity_service import FieldIdentityConflict
    from sqlalchemy.exc import OperationalError
    roots = session.info.setdefault('flama.note_drafts.fenced_roots', {})
    parents = session.info.setdefault('flama.note_drafts.fenced_parents', {})
    schema_type_ids = set(schema_type_ids) - {None}
    owners = {note.user_id for note in notes if note.user_id is not None}
    deck_ids = set(deck_ids) - {None}
    for note in notes:
        if note.deck_id is not None:
            deck_ids.add(note.deck_id)
        state = inspect(note, raiseerr=False)
        if state is not None:
            deck_ids.update(value for value in state.attrs.deck_id.history.deleted if value is not None)
            cached = session.info.get(_CACHE, {}).get(state.identity[0] if state.identity else None)
            if cached is not None and cached.deck_id is not None:
                deck_ids.add(cached.deck_id)
            if cached is not None:
                target = (cached.field_values_by_id or {}).get('meta:deck_id', {}).get('value')
                if target is not None:
                    deck_ids.add(target)
    ancestors, frontier = set(), set(deck_ids)
    table = DeckMarketplaceItem.__table__
    try:
        while frontier:
            ancestors.update(frontier)
            missing = frontier - parents.keys()
            if missing:
                rows = session.connection().execute(select(Deck.__table__.c.id, Deck.__table__.c.parent_id)
                    .where(Deck.__table__.c.id.in_(sorted(missing))).order_by(Deck.__table__.c.id)
                    .with_for_update(read=True, nowait=late)).all()
                parents.update(dict.fromkeys(missing))
                parents.update(dict(rows))
            frontier = {parents[identity] for identity in frontier if parents.get(identity) is not None} - ancestors
        missing = ancestors - roots.keys()
        if missing:
            # This unique index predates Published Base. Do not let an owner-
            # index scan lock every same-type listing before filtering roots.
            statement = select(table).with_hint(table,
                'FORCE INDEX (uq_deck_marketplace_items_source_deck)', dialect_name='mysql').where(
                table.c.source_deck_id.in_(sorted(missing))).order_by(table.c.id).with_for_update(nowait=late)
            rows = session.connection().execute(statement).mappings().all()
            roots.update(dict.fromkeys(missing))
            roots.update({row['source_deck_id']: dict(row) for row in rows})
        items = {row['id']: row for root in ancestors if (row := roots.get(root))
            and (all_owners or row['owner_user_id'] in owners)}
        if schema_type_ids:
            rows = session.connection().execute(select(table).where(
                table.c.source_note_type_id.in_(sorted(schema_type_ids))).order_by(table.c.id)
                .with_for_update(nowait=late)).mappings()
            for row in rows:
                item = dict(row)
                items[row['id']] = item
                roots[row['source_deck_id']] = item
    except OperationalError as exc:
        if late and getattr(exc.orig, 'args', (None,))[0] in {1205, 3572}:
            raise FieldIdentityConflict('The Note scope changed during publication; refresh before retrying.') from exc
        raise
    if not bump:
        return
    from app.services.deck_count_projection_service import invalidate_learner_deck_counts
    invalidate_learner_deck_counts(session, {(note.user_id, deck_id) for note in notes
        if note.published_at is not None and note.user_id is not None for deck_id in deck_ids | {0}})
    bumped = session.info.setdefault('flama.note_drafts.bumped_heads', set())
    for item_id, item in sorted(items.items()):
        if item_id in bumped:
            continue
        session.connection().execute(update(table).where(table.c.id == item_id)
            .values(working_revision=table.c.working_revision + 1))
        item['working_revision'] = int(item['working_revision'] or 0) + 1
        bumped.add(item_id)
        loaded = session.identity_map.get(session.identity_key(DeckMarketplaceItem, item_id))
        if loaded is not None:
            set_committed_value(loaded, 'working_revision', item['working_revision'])


def load_note_drafts(session, notes):
    """Load only the requested/session page, once, with no process cache."""
    from models.note_draft import NoteDraft
    cache = session.info.setdefault(_CACHE, {})
    # Never refresh every expired Note merely to discover a page's Draft IDs.
    ids = {state.identity[0] for note in notes if (state := inspect(note)).identity
        and state.dict.get("published_at") and author_drafts_visible(state.dict.get("user_id"))}
    missing = ids - cache.keys()
    if missing:
        with session.no_autoflush:
            cache.update(dict.fromkeys(missing))
            ordered = sorted(missing)
            for offset in range(0, len(ordered), 500):
                for draft in session.execute(select(NoteDraft).where(
                        NoteDraft.note_id.in_(ordered[offset:offset + 500]))).scalars():
                    cache[draft.note_id] = draft
    return {identity: cache.get(identity) for identity in ids}


def get_note_draft(note):
    if not published_base_enabled() or not getattr(note, "published_at", None):
        return None
    if not author_drafts_visible(note.user_id):
        return None
    session = object_session(note)
    if session is None:
        return note.__dict__.get("_captured_note_draft")
    cache = session.info.setdefault(_CACHE, {})
    if note.id in cache:
        draft = cache[note.id]
        # Session.deleted creates a copy; the queued-deletion registry permits
        # an O(1) membership check before persistent_to_deleted fires at flush.
        return None if draft is not None and (inspect(draft).deleted or inspect(draft) in session._deleted) else draft
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


def effective_note_updated_at(note):
    draft = get_note_draft(note)
    return max((value for value in (note.updated_at, draft.updated_at if draft else None)
        if value is not None), default=None)


def _restore_note_base(note, base):
    for name in (*_CONTENT, 'published_at', 'deleted_at'):
        set_committed_value(note, name, deepcopy(base[name]))


def _current_draft(session, note_id, record):
    """Reconcile a locking Core read without another SELECT or stale ORM data.

    An explicit Draft mutation in this unit of work wins for its changed
    columns; untouched columns come from the current row, never an older RR
    snapshot. Source Note locks serialize concurrent saves of the same Note.
    """
    from models.note_draft import NoteDraft
    from app.services.field_value_identity_service import typed_value_equal
    row = session.identity_map.get(session.identity_key(NoteDraft, note_id))
    if row is None:
        row = session.info.setdefault(_CACHE, {}).get(note_id)
    state = inspect(row) if row is not None else None
    names = tuple(column.name for column in NoteDraft.__table__.columns if column.name != "note_id")
    pending = state is not None and state.pending
    deleting = row is not None and row in session.deleted
    intent = {name: deepcopy(state.dict[name]) for name in names if name in state.dict
        and (pending or state.attrs[name].history.has_changes())} if state else {}
    if state is not None and 'field_values_by_id' in state.dict:
        previous = state.committed_state.get('field_values_by_id', NO_VALUE)
        if previous is not NO_VALUE and not typed_value_equal(previous, state.dict['field_values_by_id']):
            intent['field_values_by_id'] = deepcopy(state.dict['field_values_by_id'])
    exists = record["draft_note_id"] is not None
    if not exists:
        if row is not None and not pending:
            session.expunge(row)
            if intent and not deleting:
                make_transient(row)
                defaults = {'field_values_by_id': {}, 'tags': None, 'deck_id': None,
                    'op': 'edit', 'updated_at': datetime.utcnow()}
                for name in names:
                    setattr(row, name, deepcopy(intent.get(name, defaults[name])))
                session.add(row)
            else:
                row = None
    else:
        if row is None:
            row = NoteDraft(note_id=note_id)
            for name in names:
                set_committed_value(row, name, deepcopy(record[f"draft_{name}"]))
            make_transient_to_detached(row)
            session.add(row)
        else:
            if pending:
                session.expunge(row)
                row.note_id = note_id
            for name in names:
                set_committed_value(row, name, deepcopy(record[f"draft_{name}"]))
            if pending:
                make_transient_to_detached(row)
                session.add(row)
            for name, value in intent.items():
                setattr(row, name, value)
                if name == "field_values_by_id":
                    flag_modified(row, name)
    cache = session.info.setdefault(_CACHE, {})
    cache[note_id] = None if deleting else row
    return row


def redirect_published_note_writes(session, notes, *, draft_only=()):
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
    draft_only = set(draft_only)
    for draft in session.new | session.dirty | session.deleted:
        if isinstance(draft, NoteDraft):
            note = inspect(draft).dict.get("note") or session.get(Note, draft.note_id,
                execution_options={"include_deleted_notes": True, "include_deleted_drafts": True})
            if note is not None and inspect(note).persistent and note not in candidates:
                candidates.add(note)
                draft_only.add(note)
    if not candidates:
        return set()
    columns = [Note.__table__.c.id, Note.__table__.c.published_at,
               Note.__table__.c.deleted_at, *(Note.__table__.c[name] for name in _CONTENT)]
    note_table, draft_table = Note.__table__, NoteDraft.__table__
    columns.extend(column.label(f"draft_{column.name}") for column in draft_table.columns)
    bases = {row.id: row for row in session.connection().execute(
        select(*columns).select_from(note_table.outerjoin(draft_table, draft_table.c.note_id == note_table.c.id))
        .where(note_table.c.id.in_([note.id for note in candidates]))
        .order_by(Note.__table__.c.id).with_for_update()).mappings()}
    authority = base_write_authority()
    if authority:
        if authority[0] == "maintenance":
            _log.warning("note_base_maintenance notes=%s reason=%s",
                         sorted(bases), authority[1])
        return set()
    # An old reader may have missed a committed move. Fence its actual Base
    # and current draft destination now, without reversing the lock order by
    # waiting for a head already held by a publisher.
    deck_ids = {value for row in bases.values() for value in (row['deck_id'], row['draft_deck_id']) if value is not None}
    lock_and_bump_note_listings(session, candidates, deck_ids=deck_ids, late=True)
    redirected = set()
    for note in sorted(candidates, key=lambda row: row.id):
        base = bases.get(note.id)
        if base is None or base["published_at"] is None:
            continue
        require_note_author_write(base["user_id"])
        if base["deleted_at"] is not None:
            raise ValueError("A deleted Published Note cannot be edited or resurrected")
        if note.user_id != base["user_id"] or note.note_type_id != base["note_type_id"]:
            raise ValueError("A Published Note cannot change its owner or NoteType")
        draft = _current_draft(session, note.id, base)
        if note in draft_only:
            _restore_note_base(note, base)
            continue
        deleting = note in session.deleted
        state = inspect(note)
        intent = note.__dict__.get('_pending_note_metadata', {})
        fields_touched = ('_pending_named_field_values' in note.__dict__
            or state.attrs.field_values_by_id.history.has_changes()
            or state.attrs.field_values_extras.history.has_changes())
        delta = make_draft_delta(base['note_type_id'], base['field_values_by_id'],
            base['field_values_extras'], note.field_values_by_id, note.field_values_extras
        ) if fields_touched else deepcopy(draft.field_values_by_id or {}) if draft is not None else {}
        # Untouched metadata/content must follow the current Base even if a
        # concurrent publication consumed the Draft in our old read snapshot.
        if 'tags' in intent or state.attrs.tags.history.has_changes():
            tags = deepcopy(note.tags) if note.tags != base['tags'] else None
        else:
            tags = draft.tags if draft is not None else None
        if 'deck_id' in intent or state.attrs.deck_id.history.has_changes():
            deck_id = note.deck_id if note.deck_id != base['deck_id'] else None
            if note.deck_id is None and base['deck_id'] is not None:
                delta['meta:deck_id'] = {'op': 'set', 'value': None}
            else:
                delta.pop('meta:deck_id', None)
        else:
            deck_id = draft.deck_id if draft is not None else None
            if draft is not None and 'meta:deck_id' in (draft.field_values_by_id or {}):
                delta['meta:deck_id'] = deepcopy(draft.field_values_by_id['meta:deck_id'])
        if deleting:
            session.add(note)  # cancel the ORM delete and its cascaded children
        if deleting or delta or tags is not None or deck_id is not None:
            if draft is None:
                draft = NoteDraft(note_id=note.id)
                session.add(draft)
            draft.field_values_by_id = delta
            # Python equality collapses True and 1 inside JSON dictionaries.
            flag_modified(draft, "field_values_by_id")
            draft.tags, draft.deck_id = tags, deck_id
            draft.op = "delete" if deleting else "edit"
            draft.updated_at = datetime.utcnow()
        elif draft is not None:
            if inspect(draft).pending:
                session.expunge(draft)
            else:
                session.delete(draft)
        _restore_note_base(note, base)
        redirected.add(note)
    return redirected
