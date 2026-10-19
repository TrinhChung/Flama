"""Single-authority Field ID storage with name adapters at external boundaries.

The Note name view is computed from current scoped definitions. It is never a
second persisted authority. Retired IDs remain lossless tombstones, while old
release/session payloads continue to use their immutable historical codecs.
"""
from __future__ import annotations

from copy import deepcopy
import hashlib

from sqlalchemy import inspect, or_, select
from sqlalchemy.orm import object_session
from sqlalchemy.orm.attributes import flag_dirty

from app.services.field_value_identity_service import (
    FIELD_VALUE_CODEC, CapturedFieldSchema, FieldIdentityConflict, FieldIdentityError,
    _json_object, capture_field_schema, encode_named_values,
)

_CACHE = "flama.field_identity.runtime_schema"
_SCOPES = "flama.field_identity.runtime_install"
_FLUSH_SCHEMAS = "flama.field_identity.flush_schemas"
_PARENTS = "flama.field_identity.runtime_parents"


def extra_field_identity_key(note_type_id, name):
    """Explicit undeclared-label disposition, never a fabricated Field UUID."""
    return "extra:" + hashlib.sha256((str(note_type_id) + "\0" + name).encode("utf-8")).hexdigest()


def added_field_identity_key(install_id, field_id):
    return f"added:{install_id}:{field_id}"


def note_type_scope_id(note):
    state = inspect(note)
    history = state.attrs.note_type.history
    if history.has_changes() and history.added and history.added[0] is not None:
        return history.added[0].id
    return note.note_type_id or (note.note_type.id if note.note_type is not None else None)


def clone_install_for_note(note, session=None):
    from models.deck_clone_added_note import DeckCloneAddedNote
    from models.deck_clone_deck_map import DeckCloneDeckMap
    from models.deck_install import DeckInstall
    from models.note_type import NoteType
    from models.note_type_install import NoteTypeInstall
    session = session or object_session(note)
    if session is None:
        return None
    key = (note.deck_id, note.user_id) if note.deck_id is not None else (None, note.id, note.user_id)
    cache = session.info.setdefault(_SCOPES, {})
    for row in session.new:
        if isinstance(row, DeckCloneAddedNote) and (row.note is note or note.id and row.note_id == note.id):
            return row.deck_install or session.get(DeckInstall, row.deck_install_id)
        if isinstance(row, DeckCloneDeckMap) and note.deck_id is not None and row.local_deck_id == note.deck_id:
            return row.deck_install or session.get(DeckInstall, row.deck_install_id)
    if key not in cache:
        with session.no_autoflush:
            install_ids = set()
            if note.deck_id is not None:
                install_ids.update(session.execute(select(DeckCloneDeckMap.deck_install_id)
                    .where(DeckCloneDeckMap.local_deck_id == note.deck_id)).scalars())
            elif note.id:
                type_id = note_type_scope_id(note)
                parent_cache = session.info.setdefault(_PARENTS, {})
                parent = parent_cache.get(type_id) or session.get(NoteType, type_id)
                if parent is not None:
                    parent_cache[type_id] = parent
                local_type_key = ("installed_type", type_id, note.user_id)
                if local_type_key not in cache:
                    cache[local_type_key] = session.execute(select(NoteTypeInstall.id).where(
                        NoteTypeInstall.installed_note_type_id == type_id,
                        NoteTypeInstall.user_id == note.user_id).limit(1)).first() is not None
                if cache[local_type_key] or parent is not None and parent.user_id != note.user_id:
                    install_ids.update(session.execute(select(DeckCloneAddedNote.deck_install_id)
                        .where(DeckCloneAddedNote.note_id == note.id)).scalars())
            if len(install_ids) > 1:
                raise FieldIdentityError("A local Note has ambiguous install scope")
            install = session.get(DeckInstall, next(iter(install_ids))) if install_ids else None
            if install is not None and install.user_id != note.user_id:
                raise FieldIdentityError("A local Note cannot use another learner's install schema")
            cache[key] = install
    return cache[key]


def canonical_field_schema_for_note(note, session=None):
    """Current owned/local definitions plus explicitly namespaced added fields."""
    from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
    from models.field_def import FieldDef
    from models.note_type import NoteType
    from models.model_uuid import uuid_str
    session = session or object_session(note)
    type_id = note_type_scope_id(note)
    if not type_id:
        raise FieldIdentityError("A NoteType is required before resolving values")
    if session is None:
        parent = note.__dict__.get("note_type")
        if parent is None or "field_defs" not in parent.__dict__:
            raise FieldIdentityError("Detached Notes require their captured field schema")
        return capture_field_schema(type_id, parent.field_schema_revision or 0, parent.field_defs)
    with session.no_autoflush:
        parent_cache = session.info.setdefault(_PARENTS, {})
        parent = note.__dict__.get("note_type") or parent_cache.get(type_id) or session.get(NoteType, type_id)
        if parent is None:
            parent = next((row for row in session.new if isinstance(row, NoteType) and row.id == type_id), None)
        if parent is None:
            raise FieldIdentityError("NoteType schema is missing")
        parent_cache[type_id] = parent
        install = clone_install_for_note(note, session)
        cache_key = (type_id, int(parent.field_schema_revision or 0),
            install.id if install else None, int(install.overlay_revision or 0) if install else None)
        cache = session.info.setdefault(_CACHE, {})
        if cache_key in cache:
            return cache[cache_key]
        records = session.info.get(_FLUSH_SCHEMAS, {}).get(type_id)
        if records is None:
            records = {row.id: dict(id=row.id, name=row.name, note_type_id=type_id)
                for row in session.execute(select(FieldDef.id, FieldDef.name)
                    .where(FieldDef.note_type_id == type_id)).all()}
            for field in session.new | session.dirty | session.deleted:
                if not isinstance(field, FieldDef):
                    continue
                scope = field.note_type_id or (field.note_type.id if field.note_type is not None else None)
                if scope != type_id:
                    continue
                if field.id is None:
                    field.id = uuid_str()
                if field in session.deleted or field.note_type is None and inspect(field).attrs.note_type.history.has_changes():
                    records.pop(field.id, None)
                else:
                    records[field.id] = dict(id=field.id, name=field.name, note_type_id=type_id)
        else:
            records = dict(records)
        if install is not None:
            added = {row.id: row for row in session.execute(select(DeckCloneAddedFieldDef)
                .where(DeckCloneAddedFieldDef.deck_install_id == install.id)).scalars()}
            for row in session.new | session.dirty | session.deleted:
                if isinstance(row, DeckCloneAddedFieldDef) and row.deck_install_id == install.id:
                    if row.id is None:
                        row.id = uuid_str()
                    if row in session.deleted:
                        added.pop(row.id, None)
                    else:
                        added[row.id] = row
            for field in added.values():
                identity = added_field_identity_key(install.id, field.id)
                properties = field.properties if isinstance(field.properties, dict) else {}
                records[identity] = dict(id=identity, name=properties.get("name") or field.name, note_type_id=type_id)
        schema = capture_field_schema(type_id, parent.field_schema_revision or 0, records.values())
        cache[cache_key] = schema
        return schema


def read_note_named_values(note):
    pending = note.__dict__.get("_pending_named_field_values")
    if pending is not None:
        return deepcopy(pending)
    state = inspect(note)
    if state.transient and note.field_values_by_id is None:
        return {}
    if note.field_values_codec != FIELD_VALUE_CODEC:
        raise FieldIdentityError("Note is not in the canonical Field ID codec; run the offline cutover")
    schema = canonical_field_schema_for_note(note)
    values = _json_object(note.field_values_by_id, "ID values")
    result = deepcopy(_json_object(note.field_values_extras or {}, "Retained undeclared values"))
    if result.keys() & schema.names.keys():
        raise FieldIdentityError("Undeclared value collides with a declared label; explicit disposition required")
    for identity, label in schema.fields:
        if identity not in values:
            continue
        if label in result:
            raise FieldIdentityError("Undeclared value collides with a declared label; explicit disposition required")
        result[label] = deepcopy(values[identity])
    return result


def write_note_named_values(note, values):
    values = deepcopy(_json_object(values, "Field values"))
    session = object_session(note)
    if session is not None and inspect(note).persistent:
        with session.no_autoflush:
            schema = canonical_field_schema_for_note(note, session)
            note.__dict__.setdefault("_pending_field_schema_revision", schema.revision)
    note.__dict__["_pending_named_field_values"] = values
    if session is not None:
        flag_dirty(note)


def _reject_stale_labels(session, note, schema, values):
    from models.field_value_identity_definition import FieldValueIdentityDefinition
    unknown = set(values) - schema.names.keys()
    unknown -= set(note.field_values_extras or {})
    retained_ids = set(note.field_values_by_id or {}) - schema.ids.keys()
    client_revision = note.__dict__.get("_client_field_schema_revision")
    check_reused = bool(retained_ids) and inspect(note).persistent and client_revision != schema.revision
    if not unknown and not check_reused:
        return
    install = clone_install_for_note(note, session)
    definitions = session.execute(select(FieldValueIdentityDefinition).where(
        or_(FieldValueIdentityDefinition.note_type_id == schema.note_type_id,
            FieldValueIdentityDefinition.deck_install_id == install.id if install else False),
        FieldValueIdentityDefinition.identity_kind != "extra")).scalars()
    for definition in definitions:
        labels = set(definition.label_history or [definition.retained_name])
        if unknown & labels:
            raise FieldIdentityConflict("A field label changed or was removed; refresh the schema before editing")
        if check_reused and definition.identity_key in retained_ids and labels & values.keys() & schema.names.keys():
            raise FieldIdentityConflict("A removed label now identifies another Field; provide the current schema revision or stable Field ID")


def encode_pending_note_values(session, note, schema):
    """Resolve the boundary write once, preserving retired ID tombstones."""
    pending = note.__dict__.get("_pending_named_field_values")
    if pending is None:
        return False
    _reject_stale_labels(session, note, schema, pending)
    encoded = encode_named_values(schema, pending)
    current = _json_object(note.field_values_by_id or {}, "Existing ID values")
    retained = {identity: deepcopy(value) for identity, value in current.items() if identity not in schema.ids}
    note.field_values_by_id = dict(retained, **encoded.by_id)
    note.field_values_extras = encoded.extras
    note.field_values_codec = FIELD_VALUE_CODEC
    return True


def read_media_field_label(asset):
    """Current label by stable identity; raw advisory remains historical only."""
    from models.field_def import FieldDef
    from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
    session = object_session(asset)
    identity = asset.field_identity_key
    if session is not None and identity:
        with session.no_autoflush:
            if identity.startswith("added:"):
                _, install_id, field_id = identity.split(":", 2)
                field = session.get(DeckCloneAddedFieldDef, field_id)
                if field is not None and field.deck_install_id == install_id:
                    properties = field.properties if isinstance(field.properties, dict) else {}
                    return properties.get("name") or field.name
            elif not identity.startswith("extra:"):
                field = session.get(FieldDef, identity)
                if field is not None and asset.note is not None and field.note_type_id == note_type_scope_id(asset.note):
                    return field.name
    return asset._field_name


def clear_field_runtime_caches(session):
    for key in (_CACHE, _SCOPES, _FLUSH_SCHEMAS, _PARENTS):
        session.info.pop(key, None)
