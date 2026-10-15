"""Canonical Field ID writes, schema fencing and retained identity lifecycle.

Every ORM Note writer uses the same storage codec. Label adapters do not write
a named mirror, and schema rename/delete never walks or rewrites Note rows.
"""
from __future__ import annotations

import re
from sqlalchemy import event, inspect, select, update
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import set_committed_value

from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.field_def import FieldDef
from models.field_value_identity_definition import FieldValueIdentityDefinition
from models.media_asset import MediaAsset
from models.model_uuid import uuid_str
from models.note import Note
from models.note_type import NoteType
from app.services.field_value_identity_service import FIELD_VALUE_CODEC, FieldIdentityConflict, FieldIdentityError, _json_object
from app.services.field_value_runtime_service import (
    added_field_identity_key, canonical_field_schema_for_note, clear_field_runtime_caches,
    clone_install_for_note, encode_pending_note_values, extra_field_identity_key, note_type_scope_id,
)


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
    for row in session.new:
        if isinstance(row, (NoteType, FieldDef, DeckCloneAddedFieldDef, DeckInstall)) and row.id is None:
            row.id = uuid_str()
    deleted_fields = {row for row in session.deleted if isinstance(row, FieldDef)}
    for parent in session.dirty:
        if isinstance(parent, NoteType):
            deleted_fields.update(row for row in inspect(parent).attrs.field_defs.history.deleted
                                  if row.note_type is None)
    fields = {row for row in session.new | session.dirty | session.deleted
              if isinstance(row, FieldDef) and (row in session.new or row in session.deleted
                  or session.is_modified(row, include_collections=False)
                  or _changed(row, ("note_type",)))} | deleted_fields
    added_fields = {row for row in session.new | session.dirty | session.deleted
                    if isinstance(row, DeckCloneAddedFieldDef) and (row in session.new or row in session.deleted
                        or session.is_modified(row, include_collections=False))}
    overrides = [row for row in session.new | session.dirty if isinstance(row, DeckCloneNoteFieldOverride)
                 and (row in session.new or _changed(row, ("field_identity_key", "deck_install_id", "source_note_id", "source_field_def_id")))]
    content_names = ("field_values_by_id", "field_values_extras", "note_type_id", "note_type", "tags", "deck_id", "user_id")
    notes = [row for row in session.new | session.dirty if isinstance(row, Note)
             and (row in session.new or "_pending_named_field_values" in row.__dict__ or _changed(row, content_names))]
    media = [row for row in session.new | session.dirty if isinstance(row, MediaAsset)
             and (row in session.new or _changed(row, ("_field_name", "note_id", "note", "field_def_id", "field_identity_key")))]
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
    revisions = {}
    for type_id in sorted(value for value in scopes if value):
        if type_id in parents:
            parent = parents[type_id]
            old = int(parent.field_schema_revision or 0)
            revisions[type_id] = old
            if type_id in schema_changed:
                parent.field_schema_revision = old + 1
            continue
        old = session.execute(select(NoteType.field_schema_revision)
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
            retired=field in deleted_fields or field in session.deleted)
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
        records = {row.id: dict(id=row.id, name=row.name, note_type_id=type_id)
                   for row in session.execute(select(FieldDef.id, FieldDef.name)
                       .where(FieldDef.note_type_id == type_id).with_for_update()).all()}
        for field in fields:
            if _field_scope(field) != type_id:
                continue
            if field in deleted_fields or field in session.deleted:
                records.pop(field.id, None)
            else:
                records[field.id] = dict(id=field.id, name=field.name, note_type_id=type_id)
        captured[type_id] = records
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
    for note in session.info.pop("flama.field_identity.encoded_notes", set()):
        note.__dict__.pop("_pending_named_field_values", None)
        note.__dict__.pop("_pending_field_schema_revision", None)
        note.__dict__.pop("_client_field_schema_revision", None)
    clear_field_runtime_caches(session)


@event.listens_for(Session, "after_soft_rollback")
def _discard_pending_names(session, _transaction):
    for note in list(session.identity_map.values()) + list(session.new):
        if isinstance(note, Note):
            note.__dict__.pop("_pending_named_field_values", None)
            note.__dict__.pop("_pending_field_schema_revision", None)
            note.__dict__.pop("_client_field_schema_revision", None)
    session.info.pop("flama.field_identity.encoded_notes", None)
    clear_field_runtime_caches(session)


@event.listens_for(Session, "after_transaction_end")
def _end_field_transaction(session, transaction):
    if transaction.parent is None:
        clear_field_runtime_caches(session)


@event.listens_for(Session, "do_orm_execute")
def guard_bulk_identity_writes(state):
    if state.execution_options.get("field_identity_scoped_schema"):
        return
    text = getattr(state.statement, "text", None)
    if text and re.search(r"\b(insert|update|replace|delete)\b", text, re.I) and re.search(
            r"\b(notes|field_defs|media_assets|deck_clone_added_field_defs|deck_clone_note_field_overrides)\b", text, re.I):
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
