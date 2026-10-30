"""Canonical Field ID writes, schema fencing and retained identity lifecycle.

Every ORM Note writer uses the same storage codec. Label adapters do not write
a named mirror, and schema rename/delete never walks or rewrites Note rows.
"""
from __future__ import annotations

import re
from sqlalchemy import event, inspect, select, update
from sqlalchemy.orm import Session, object_session, with_loader_criteria
from sqlalchemy.orm.attributes import set_committed_value

from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.field_def import FieldDef
from models.field_value_identity_definition import FieldValueIdentityDefinition
from models.media_asset import MediaAsset
from models.model_uuid import uuid_str
from models.note import Note
from models.note_draft import NoteDraft
from models.note_type import NoteType
from app.services.field_value_identity_service import FIELD_VALUE_CODEC, FieldIdentityConflict, FieldIdentityError, _json_object
from app.services.field_value_runtime_service import (
    added_field_identity_key, canonical_field_schema_for_note, clear_field_runtime_caches,
    clone_install_for_note, encode_pending_note_values, extra_field_identity_key, note_type_scope_id,
)


@event.listens_for(Note.tags, "set")
@event.listens_for(Note.deck_id, "set")
def _capture_note_metadata_intent(note, value, old_value, initiator):
    from app.services.note_base_context import base_write_authority, published_base_enabled
    if published_base_enabled() and not base_write_authority() and inspect(note).persistent and note.published_at is not None:
        from sqlalchemy.orm.attributes import flag_dirty
        note.__dict__.setdefault("_pending_note_metadata", {})[initiator.key] = value
        session = object_session(note)
        if session is not None:
            session.info.setdefault("flama.note_drafts.metadata_notes", set()).add(note)
        flag_dirty(note)


@event.listens_for(Session, "after_attach")
@event.listens_for(Session, "loaded_as_persistent")
@event.listens_for(Session, "deleted_to_persistent")
def _cache_attached_draft(session, row):
    if isinstance(row, NoteDraft):
        from app.services.note_draft_service import cache_note_draft
        cache_note_draft(session, row)


@event.listens_for(Session, "persistent_to_deleted")
@event.listens_for(Session, "pending_to_transient")
def _cache_removed_draft(session, row):
    if isinstance(row, NoteDraft):
        from app.services.note_draft_service import cache_note_draft
        cache_note_draft(session, row, remove=True)


@event.listens_for(Session, "persistent_to_detached")
def _uncache_detached_draft(session, row):
    if isinstance(row, NoteDraft):
        cache = session.info.get("flama.note_drafts.loaded", {})
        identity = inspect(row).identity[0]
        if cache.get(identity) is row:
            cache.pop(identity, None)


@event.listens_for(NoteDraft.note_id, "set")
def _cache_draft_identity(row, value, _old_value, _initiator):
    if inspect(row).persistent and inspect(row).identity[0] != value:
        raise FieldIdentityError("An existing Note draft cannot be retargeted")
    session = object_session(row)
    if session is not None and value is not None:
        from app.services.note_draft_service import cache_note_draft
        cache_note_draft(session, row, note_id=value)


def _changed(row, names):
    state = inspect(row)
    return any(state.attrs[name].history.has_changes() for name in names)


def _field_scope(field):
    history = inspect(field).attrs.note_type.history
    if history.added and history.added[0] is not None:
        return history.added[0].id
    if field.note_type_id:
        return field.note_type_id
    return history.deleted[0].id if history.deleted else None


def retain_field_definition(session, *, identity_key, identity_kind, field_id,
    note_type_id, deck_install_id=None, name, retired=False):
    """Keep identity/label history independent of live FieldDef deletion."""
    pending = next((row for row in session.new if isinstance(row, FieldValueIdentityDefinition)
                   and row.identity_key == identity_key), None)
    row = pending or session.get(FieldValueIdentityDefinition, identity_key)
    if row is None:
        row = FieldValueIdentityDefinition(identity_key=identity_key, identity_kind=identity_kind,
            field_id=field_id, note_type_id=note_type_id, deck_install_id=deck_install_id,
            retained_name=name, label_history=[name], is_retired=bool(retired))
        session.add(row)
    else:
        if (row.identity_kind != identity_kind or row.field_id != field_id
                or row.note_type_id != note_type_id or row.deck_install_id != deck_install_id):
            raise FieldIdentityError("A retained field identity cannot be reassigned to another scope")
        labels = list(row.label_history or [row.retained_name])
        if name not in labels:
            labels.append(name)
            row.label_history = labels
        row.is_retired = bool(retired)
    return row


def _media_note(session, asset):
    history = inspect(asset).attrs.note.history
    if history.has_changes() and history.added:
        return history.added[0]
    if inspect(asset).attrs.note_id.history.has_changes():
        return session.get(Note, asset.note_id)
    return asset.note or session.get(Note, asset.note_id)


@event.listens_for(Session, "before_flush")
def maintain_field_identity(session, _context, _instances):
    from app.services.note_base_context import base_write_authority, published_base_enabled
    enabled = published_base_enabled()
    authority = base_write_authority()
    session.info.pop('flama.note_drafts.bumped_heads', None)
    draft_notes = set()
    if enabled and not authority:
        from models.note_draft import NoteDraft
        from app.services.note_draft_service import lock_and_bump_note_listings
        from models.deck import Deck
        from models.deck_marketplace_item import DeckMarketplaceItem
        from types import SimpleNamespace
        decks = [row for row in session.new | session.dirty | session.deleted if isinstance(row, Deck)
            and (row in session.new or row in session.deleted or _changed(row, ('parent_id', 'parent')))]
        if decks:
            ids = [row.id for row in decks if inspect(row).persistent]
            old_parents = dict(session.connection().execute(select(Deck.__table__.c.id, Deck.__table__.c.parent_id)
                .where(Deck.__table__.c.id.in_(ids)).order_by(Deck.__table__.c.id).with_for_update(read=True)).all()) if ids else {}
            proxies = []
            for deck in decks:
                relationship = inspect(deck).attrs.parent.history
                parent_id = (relationship.added[0].id if relationship.added and relationship.added[0] else None
                    ) if relationship.has_changes() else deck.parent_id
                for deck_id in {deck.id, old_parents.get(deck.id), parent_id} - {None}:
                    proxies.append(SimpleNamespace(user_id=deck.owner_user_id, note_type_id=deck.note_type_id,
                        deck_id=deck_id, published_at=True))
            lock_and_bump_note_listings(session, proxies, all_owners=True)
            session.info['flama.note_drafts.invalidate_parents'] = True
        if any(isinstance(row, DeckMarketplaceItem) and (row in session.new or row in session.deleted
                or _changed(row, ('source_deck_id', 'source_note_type_id', 'owner_user_id')))
                for row in session.new | session.dirty | session.deleted):
            session.info['flama.note_drafts.invalidate_roots'] = True
        changed_notes = {row for row in session.new | session.dirty | session.deleted if isinstance(row, Note)}
        for row in session.new | session.dirty | session.deleted:
            if isinstance(row, NoteDraft):
                note = inspect(row).dict.get("note") or (session.get(Note, row.note_id, execution_options={
                    "include_deleted_notes": True, "include_deleted_drafts": True}) if row.note_id is not None else None)
                if note is not None:
                    if note.published_at is None and row not in session.deleted:
                        raise FieldIdentityError('Only a published Note may have a draft')
                    if note.published_at is not None:
                        from app.services.note_base_context import require_note_author_write
                        require_note_author_write(note.user_id)
                    changed_notes.add(note)
                    draft_notes.add(note)
        schema_types = {_field_scope(row) for row in session.new | session.dirty | session.deleted
            if isinstance(row, FieldDef) and (row in session.new or row in session.deleted
                or session.is_modified(row, include_collections=False))}
        lock_and_bump_note_listings(session, changed_notes, schema_type_ids=schema_types)
    if enabled and not authority:
        for row in session.new | session.dirty:
            if isinstance(row, Note) and (
                    row in session.new and (row.published_at is not None or row.deleted_at is not None)
                    or row not in session.new and _changed(row, ("published_at", "deleted_at"))):
                raise FieldIdentityError("Only atomic publish or audited maintenance may change Note publication state")
    for row in session.new:
        if isinstance(row, (NoteType, FieldDef, DeckCloneAddedFieldDef, DeckInstall)) and row.id is None:
            row.id = uuid_str()
    deleted_fields = {row for row in session.deleted if isinstance(row, FieldDef)}
    for parent in session.dirty:
        if isinstance(parent, NoteType):
            deleted_fields.update(row for row in inspect(parent).attrs.field_defs.history.deleted
                                  if row.note_type is None)
    if enabled and not authority:
        from datetime import datetime
        # A schema deletion changes one definition, never every Note value.
        # Reattach delete-orphans to their original parent to retain identity.
        for field in deleted_fields:
            scope = _field_scope(field)
            session.add(field)
            if field.note_type is None and scope:
                field.note_type = session.get(NoteType, scope)
            field.deleted_at = datetime.utcnow()
    fields = {row for row in session.new | session.dirty | session.deleted
              if isinstance(row, FieldDef) and (row in session.new or row in session.deleted
                  or session.is_modified(row, include_collections=False)
                  or _changed(row, ("note_type",)))} | deleted_fields
    added_fields = {row for row in session.new | session.dirty | session.deleted
                    if isinstance(row, DeckCloneAddedFieldDef) and (row in session.new or row in session.deleted
                        or session.is_modified(row, include_collections=False))}
    overrides = [row for row in session.new | session.dirty if isinstance(row, DeckCloneNoteFieldOverride)
                 and (row in session.new or _changed(row, ("field_identity_key", "deck_install_id", "source_note_id", "source_field_def_id")))]
    content_names = ("field_values_by_id", "field_values_extras", "note_type_id", "note_type", "tags", "deck_id", "user_id", "published_at", "deleted_at", "updated_at")
    notes = [row for row in session.new | session.dirty | session.deleted if isinstance(row, Note)
             and (row in session.new or "_pending_named_field_values" in row.__dict__
                  or "_pending_note_metadata" in row.__dict__ or _changed(row, content_names))]
    notes.extend(row for row in session.deleted if isinstance(row, Note) and row not in notes)
    draft_only_notes = draft_notes.difference(notes)
    notes.extend(draft_only_notes)
    media = [row for row in session.new | session.dirty if isinstance(row, MediaAsset)
             and (row in session.new or _changed(row, ("_field_name", "note_id", "note", "field_def_id", "field_identity_key")))]
    from app.services.note_base_context import listing_fenced_fields
    fenced_fields = listing_fenced_fields() if authority and enabled else None
    if fenced_fields is not None:
        if fields or added_fields or media or overrides or any(
                '_pending_named_field_values' in note.__dict__ for note in notes):
            raise FieldIdentityError('Scoped publication cannot include unrelated identity mutations')
        for note in notes:
            values = _json_object(note.field_values_by_id, 'Canonical ID values')
            _json_object(note.field_values_extras, 'Retained values')
            history = inspect(note).attrs.field_values_by_id.history
            previous = history.deleted[0] or {} if history.deleted else values
            if values.keys() - fenced_fields - previous.keys():
                raise FieldIdentityError('Publication contains an identity outside its fenced schema')
            note.field_values_codec = FIELD_VALUE_CODEC
            if _changed(note, content_names):
                note.content_revision = int(note.content_revision or 0) + 1
        return
    if not fields and not added_fields and not notes and not media and not overrides:
        return
    clear_field_runtime_caches(session)
    schema_changed = {_field_scope(field) for field in fields if _field_scope(field)}
    scopes = schema_changed | {note_type_scope_id(note) for note in notes if note_type_scope_id(note)}
    for asset in media:
        note = _media_note(session, asset)
        if note is not None:
            scopes.add(note_type_scope_id(note))
    for override in overrides:
        source_note = override.source_note or session.get(Note, override.source_note_id)
        if source_note is not None:
            scopes.add(note_type_scope_id(source_note))
        history = inspect(override).attrs.field_identity_key.history
        if override not in session.new and history.deleted and history.deleted[0] != override.field_identity_key:
            raise FieldIdentityError("An existing clone delta cannot be retargeted to another field identity")
    parents = {row.id: row for row in session.new if isinstance(row, NoteType)}
    # These entries are valid only while this transaction owns the parent X
    # lock. Other schema writers take that same lock before changing fields.
    locked_schemas = session.info.setdefault("flama.field_identity.locked_schemas", {}) if enabled else {}
    revisions = {}
    for type_id in sorted(value for value in scopes if value):
        if type_id in parents:
            parent = parents[type_id]
            old = int(parent.field_schema_revision or 0)
            revisions[type_id] = old
            if type_id in schema_changed:
                parent.field_schema_revision = old + 1
            continue
        locked = locked_schemas.get(type_id)
        old = locked[0] if locked is not None else session.execute(select(NoteType.field_schema_revision)
            .where(NoteType.id == type_id).with_for_update()).scalar_one_or_none()
        if old is None:
            continue
        revisions[type_id] = int(old)
        loaded = session.identity_map.get(session.identity_key(NoteType, type_id))
        if type_id in schema_changed:
            session.connection().execute(update(NoteType.__table__).where(NoteType.id == type_id)
                .values(field_schema_revision=NoteType.field_schema_revision + 1))
        if loaded is not None:
            set_committed_value(loaded, "field_schema_revision", int(old) + (type_id in schema_changed))
    for field in fields:
        scope = _field_scope(field)
        if scope is None:
            continue
        old_name = inspect(field).attrs.name.history.deleted
        definition = retain_field_definition(session, identity_key=field.id, identity_kind="owned",
            field_id=field.id, note_type_id=scope, name=old_name[0] if old_name else field.name,
            retired=field in deleted_fields or field in session.deleted or enabled and field.deleted_at is not None)
        if field.name not in definition.label_history:
            definition.label_history = [*definition.label_history, field.name]
    for field in added_fields:
        install = field.deck_install or session.get(DeckInstall, field.deck_install_id)
        if install is None:
            raise FieldIdentityError("Added field requires an install scope")
        name = (field.properties or {}).get("name") or field.name
        retain_field_definition(session, identity_key=added_field_identity_key(install.id, field.id),
            identity_kind="clone_added", field_id=field.id, note_type_id=None,
            deck_install_id=install.id, name=name, retired=field in session.deleted)
    for override in overrides:
        from app.services.clone_field_identity_service import capture_clone_override_identity
        identity = capture_clone_override_identity(override, session)
        install = override.deck_install or session.get(DeckInstall, override.deck_install_id)
        source_note = override.source_note or session.get(Note, override.source_note_id)
        if install is None or source_note is None:
            raise FieldIdentityError("Clone field override requires its Note/install scope")
        if identity.startswith("added:"):
            _, scope, field_id = identity.split(":", 2)
            field = session.get(DeckCloneAddedFieldDef, field_id)
            if field is None or scope != install.id or field.deck_install_id != scope:
                raise FieldIdentityError("Clone-added field identity is outside the install scope")
            retain_field_definition(session, identity_key=identity, identity_kind="clone_added",
                field_id=field_id, note_type_id=None, deck_install_id=scope,
                name=(field.properties or {}).get("name") or field.name)
        elif identity.startswith("extra:"):
            if identity != extra_field_identity_key(source_note.note_type_id, override.field_name):
                raise FieldIdentityError("Undeclared clone identity differs from its captured label scope")
            retain_field_definition(session, identity_key=identity, identity_kind="extra", field_id=None,
                note_type_id=source_note.note_type_id, name=override.field_name)
        else:
            field = session.get(FieldDef, identity)
            retained = session.get(FieldValueIdentityDefinition, identity) if field is None else None
            if (field is not None and (_field_scope(field) != source_note.note_type_id or field.id != identity)) or field is None and (
                    retained is None or retained.note_type_id != source_note.note_type_id):
                raise FieldIdentityError("Source field identity is outside the NoteType scope")
    captured = {}
    for type_id in sorted(value for value in scopes if value):
        locked = locked_schemas.get(type_id)
        records = {identity: dict(value) for identity, value in locked[1].items()} if locked is not None and type_id not in schema_changed else {
            row.id: dict(id=row.id, name=row.name, note_type_id=type_id)
                   for row in session.execute(select(FieldDef.id, FieldDef.name)
                       .where(FieldDef.note_type_id == type_id).with_for_update(
                           read=enabled and type_id not in schema_changed)).all()}
        for field in fields:
            if _field_scope(field) != type_id:
                continue
            if field in deleted_fields or field in session.deleted or enabled and field.deleted_at is not None:
                records.pop(field.id, None)
            else:
                records[field.id] = dict(id=field.id, name=field.name, note_type_id=type_id)
        captured[type_id] = records
        if enabled and type_id not in parents and type_id in revisions:
            locked_schemas[type_id] = (revisions[type_id] + (type_id in schema_changed), records)
    session.info["flama.field_identity.flush_schemas"] = captured
    encoded_notes = []
    for note in notes:
        type_id = note_type_scope_id(note)
        expected = note.__dict__.get("_pending_field_schema_revision")
        if expected is not None and expected != revisions.get(type_id):
            raise FieldIdentityConflict("The field schema changed while editing; refresh before retrying")
        schema = canonical_field_schema_for_note(note, session)
        if encode_pending_note_values(session, note, schema):
            encoded_notes.append(note)
        if note.field_values_by_id is None:
            note.field_values_by_id = {}
        if note.field_values_extras is None:
            note.field_values_extras = {}
        note.field_values_codec = FIELD_VALUE_CODEC
        values = _json_object(note.field_values_by_id, "Canonical ID values")
        history = inspect(note).attrs.field_values_by_id.history
        previous = history.deleted[0] or {} if note not in session.new and history.deleted else {}
        unknown = values.keys() - schema.ids.keys() - previous.keys()
        if unknown:
            retained = set(session.execute(select(FieldValueIdentityDefinition.identity_key).where(
                FieldValueIdentityDefinition.identity_key.in_(unknown),
                FieldValueIdentityDefinition.note_type_id == type_id,
                FieldValueIdentityDefinition.is_retired.is_(True))).scalars())
            if unknown - retained:
                raise FieldIdentityError("Canonical values contain an identity outside their NoteType/install scope")
        if note in session.new:
            note.content_revision = int(note.content_revision or 0)
        elif _changed(note, content_names):
            note.content_revision = int(note.content_revision) + 1
    from app.services.note_draft_service import redirect_published_note_writes
    redirect_published_note_writes(session, notes, draft_only=draft_only_notes)
    for asset in media:
        note = _media_note(session, asset)
        if note is None:
            raise FieldIdentityError("Media requires a scoped Note")
        schema = canonical_field_schema_for_note(note, session)
        raw_label = asset._field_name
        expected = schema.names.get(raw_label)
        existing = asset.field_identity_key
        if existing and asset not in session.new and not _changed(asset, ("note_id", "note")):
            if _changed(asset, ("field_def_id",)) and asset.field_def_id != (
                    None if existing.startswith("extra:") else existing.rsplit(":", 1)[-1]):
                raise FieldIdentityError("Media advisory reference cannot retarget its stable identity")
            if _changed(asset, ("_field_name",)) and existing in schema.ids and expected != existing:
                raise FieldIdentityError("Media label conflicts with its stable field identity")
            continue
        if expected is None:
            expected = extra_field_identity_key(schema.note_type_id, raw_label)
            retain_field_definition(session, identity_key=expected, identity_kind="extra", field_id=None,
                note_type_id=schema.note_type_id, name=raw_label)
        if existing and existing != expected:
            raise FieldIdentityError("Media reassignment requires an explicit stable field mapping")
        install = clone_install_for_note(note, session)
        if asset.field_def_id is not None and expected not in (asset.field_def_id,
                added_field_identity_key(install.id, asset.field_def_id) if install else asset.field_def_id):
            raise FieldIdentityError("Media field reference differs from its scoped label")
        asset.field_identity_key = expected
        asset.field_def_id = None if expected.startswith("extra:") else expected.rsplit(":", 1)[-1]
    session.info.setdefault("flama.field_identity.encoded_notes", set()).update(encoded_notes)


@event.listens_for(Session, "after_flush_postexec")
def _finish_encoded_notes(session, _context):
    for name in ('roots', 'parents'):
        if session.info.pop(f'flama.note_drafts.invalidate_{name}', False):
            session.info.pop(f'flama.note_drafts.fenced_{name}', None)
    for note in session.info.pop("flama.note_drafts.metadata_notes", set()):
        note.__dict__.pop("_pending_note_metadata", None)
    for note in session.info.pop("flama.field_identity.encoded_notes", set()):
        note.__dict__.pop("_pending_named_field_values", None)
        note.__dict__.pop("_pending_field_schema_revision", None)
        note.__dict__.pop("_client_field_schema_revision", None)
    clear_field_runtime_caches(session)


@event.listens_for(Session, "after_soft_rollback")
def _discard_pending_names(session, _transaction):
    from models.deck_marketplace_item import DeckMarketplaceItem
    session.info.pop("flama.field_identity.locked_schemas", None)
    session.info.pop("flama.note_drafts.metadata_notes", None)
    for note in list(session.identity_map.values()) + list(session.new):
        # Core revision increments use set_committed_value, so SQLAlchemy's
        # savepoint rollback does not know those clean ORM attributes changed.
        if isinstance(note, NoteType) and inspect(note).persistent:
            session.expire(note, ['field_schema_revision'])
        if isinstance(note, DeckMarketplaceItem) and inspect(note).persistent:
            session.expire(note, ['working_revision'])
        if isinstance(note, Note):
            note.__dict__.pop("_pending_note_metadata", None)
            note.__dict__.pop("_pending_named_field_values", None)
            note.__dict__.pop("_pending_field_schema_revision", None)
            note.__dict__.pop("_client_field_schema_revision", None)
    session.info.pop("flama.field_identity.encoded_notes", None)
    clear_field_runtime_caches(session)
    from app.services.note_draft_service import clear_note_draft_cache
    clear_note_draft_cache(session)


@event.listens_for(Session, "after_transaction_end")
def _end_field_transaction(session, transaction):
    if transaction.parent is None:
        session.info.pop("flama.field_identity.locked_schemas", None)
        clear_field_runtime_caches(session)
        from app.services.note_draft_service import clear_note_draft_cache
        clear_note_draft_cache(session)


@event.listens_for(Session, "do_orm_execute")
def guard_bulk_identity_writes(state):
    from app.services.note_base_context import author_view_user_id, base_write_authority, published_base_enabled
    enabled = published_base_enabled()
    if enabled and state.is_select:
        if not state.execution_options.get("include_deleted_notes"):
            state.statement = state.statement.options(with_loader_criteria(
                Note, lambda cls: cls.deleted_at.is_(None), include_aliases=True))
        if not state.execution_options.get("include_deleted_fields"):
            state.statement = state.statement.options(with_loader_criteria(
                FieldDef, lambda cls: cls.deleted_at.is_(None), include_aliases=True))
        actor = author_view_user_id()
        if actor is not None and not state.execution_options.get("include_deleted_drafts"):
            from models.note_draft import NoteDraft
            deleted = select(NoteDraft.note_id).where(NoteDraft.op == "delete")
            state.statement = state.statement.options(with_loader_criteria(
                Note, lambda cls: (cls.user_id != actor) | cls.id.not_in(deleted), include_aliases=True))
    if enabled and state.is_delete and getattr(getattr(state.statement, "table", None), "name", None) == "notes" and not base_write_authority():
        raise FieldIdentityError("Bulk Note deletion must use the draft/retention repository adapter")
    table_name = getattr(getattr(state.statement, "table", None), "name", None)
    if enabled and (state.is_update or state.is_insert or state.is_delete) and table_name == 'note_drafts' and not base_write_authority():
        raise FieldIdentityConflict('Bulk draft writes require owner-scoped ORM mutations')
    if enabled and (state.is_update or state.is_insert) and table_name == "notes" and not base_write_authority():
        raise FieldIdentityError("Bulk Published Note writes require atomic publish or audited maintenance")
    if state.execution_options.get("field_identity_scoped_schema"):
        return
    text = getattr(state.statement, "text", None)
    if text and re.search(r"\b(insert|update|replace|delete)\b", text, re.I) and re.search(
            r"\b(notes|note_drafts|field_defs|media_assets|deck_clone_added_field_defs|deck_clone_note_field_overrides)\b", text, re.I):
        raise FieldIdentityError("Raw field-identity writes require a scoped repository adapter")
    if not (state.is_update or state.is_insert or state.is_delete):
        return
    table = getattr(getattr(state.statement, "table", None), "name", None)
    if table in {"field_defs", "media_assets", "deck_clone_added_field_defs", "deck_clone_note_field_overrides"}:
        raise FieldIdentityError("Bulk field-identity writes require a scoped repository adapter")
    if table == "notes" and (state.is_insert or state.is_update):
        # Parameter-driven bulk UPDATE has no statement._values to inspect.
        # All content mutations also need revision/CAS maintenance, so reject
        # both forms rather than allowing parameter dictionaries to bypass it.
        raise FieldIdentityError("Bulk Note identity writes require a scoped repository adapter")
