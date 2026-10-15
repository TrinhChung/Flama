"""Stable scoped identities for mutable clone field deltas.

Stored advisory labels remain byte-identical during cutover; published and
frozen fingerprints continue to use their original versioned representation.
"""
from __future__ import annotations

from sqlalchemy import event, inspect, or_, select
from sqlalchemy.orm import Session

from app.services.field_value_identity_service import FieldIdentityError, FieldIdentityConflict
from models import db
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.field_def import FieldDef
from models.note import Note


def lock_clone_overlay_write(install, *, expected_revision=None):
    from app.services.share.helpers import _fence_overlay_install_route
    from models.deck_install import DeckInstall
    if expected_revision is not None and (isinstance(expected_revision, bool)
            or not isinstance(expected_revision, int) or expected_revision < 0):
        raise FieldIdentityError("Overlay revision must be a non-negative integer")
    _fence_overlay_install_route(user_id=install.user_id)
    session = db.session()
    state = inspect(install)
    with session.no_autoflush:
        if state.persistent and not session.is_modified(install, include_collections=False):
            install = session.execute(select(DeckInstall).where(DeckInstall.id == install.id)
                .with_for_update().execution_options(populate_existing=True)).scalar_one()
        elif state.persistent:
            current = session.execute(select(DeckInstall.overlay_revision)
                .where(DeckInstall.id == install.id).with_for_update()).scalar_one()
            if int(current or 0) != int(install.overlay_revision or 0):
                raise FieldIdentityConflict("The clone overlay changed; reload before editing")
    if expected_revision is not None and expected_revision != int(install.overlay_revision or 0):
        raise FieldIdentityConflict("The clone overlay changed; reload before editing")
    return install


def clone_field_identity_labels(install, schema_view, session=None):
    from app.services.field_value_runtime_service import added_field_identity_key
    session = session or db.session
    key = (install.id, int(install.overlay_revision or 0),
        tuple((str(field.id), str(field.name)) for field in schema_view.field_defs))
    cache = session.info.setdefault("flama.clone_field_identity.labels", {})
    if key in cache:
        return cache[key]
    if all(getattr(field, "field_identity_key", None) for field in schema_view.field_defs):
        labels = {str(field.field_identity_key): str(field.name) for field in schema_view.field_defs}
        cache[key] = labels
        return labels
    with session.no_autoflush:
        added_ids = set(session.execute(select(DeckCloneAddedFieldDef.id)
            .where(DeckCloneAddedFieldDef.deck_install_id == install.id)).scalars())
        added_ids.update(row.id for row in session.new
            if isinstance(row, DeckCloneAddedFieldDef) and row.deck_install_id == install.id)
    labels = {(added_field_identity_key(install.id, field.id) if field.id in added_ids else str(field.id)):
        str(field.name) for field in schema_view.field_defs if field.id and field.name}
    cache[key] = labels
    return labels


@event.listens_for(Session, "after_transaction_end")
def _clear_clone_label_cache(session, transaction):
    if transaction.parent is None:
        session.info.pop("flama.clone_field_identity.labels", None)


def clone_override_field_label(row, install, schema_view, *, identity_labels=None):
    labels = identity_labels if identity_labels is not None else clone_field_identity_labels(install, schema_view)
    identity = row.field_identity_key
    if not identity:
        raise FieldIdentityError("Clone override requires the canonical field identity cutover")
    if identity in labels:
        return labels[identity]
    if identity.startswith("extra:") and row.field_name not in labels.values():
        return row.field_name
    # Deleted/disabled fields are retained for history, never made active by
    # a same-name replacement or a label-only fallback.
    return None


def capture_clone_override_identity(row, session):
    """Constructor compatibility at flush; persist one stable identity only."""
    from app.services import flashcards_share_service
    from app.services.field_value_runtime_service import extra_field_identity_key
    from models.deck_install import DeckInstall
    if row.field_identity_key:
        return row.field_identity_key
    with session.no_autoflush:
        install = row.deck_install or session.get(DeckInstall, row.deck_install_id)
        if install is None:
            raise FieldIdentityError("Clone override install scope is missing")
        source_note = row.source_note or session.get(Note, row.source_note_id)
        if source_note is None:
            raise FieldIdentityError("Clone override source Note is missing")
        if row.source_field_def_id:
            identity = str(row.source_field_def_id)
        else:
            schema = flashcards_share_service.build_clone_schema_view(install=install,
                source_note_type_id=install.source_note_type_id or source_note.note_type_id)
            labels = clone_field_identity_labels(install, schema, session)
            matches = [key for key, label in labels.items() if label == row.field_name]
            if len(matches) > 1:
                raise FieldIdentityError("Clone field label is ambiguous")
            identity = matches[0] if matches else extra_field_identity_key(source_note.note_type_id, row.field_name)
        row.field_identity_key = identity
        return identity


def stage_clone_note_field_override(*, install, source_note, field_name, operation, value,
    field_identity_key=None, identity_labels=None, removal_identity_labels=None):
    from app.services import flashcards_share_service
    from app.services.field_value_runtime_service import extra_field_identity_key
    from models.field_value_identity_definition import FieldValueIdentityDefinition
    if identity_labels is None:
        schema = flashcards_share_service.build_clone_schema_view(install=install,
            source_note_type_id=install.source_note_type_id or source_note.note_type_id)
        identity_labels = clone_field_identity_labels(install, schema)
    labels = identity_labels
    # A schema edit can disable a field and clear its value in the same
    # transaction. Resolve removal against the schema captured before that
    # edit as well, while all value writes require the resulting active schema.
    removal_labels = (removal_identity_labels or {}) if operation == "remove" else {}
    identity = field_identity_key
    if identity:
        if identity in labels:
            field_name = labels[identity]
        elif identity in removal_labels:
            field_name = removal_labels[identity]
        elif identity != extra_field_identity_key(source_note.note_type_id, field_name):
            raise FieldIdentityError("Clone field identity is outside its active schema")
    else:
        matches = {key for mapping in (labels, removal_labels)
            for key, label in mapping.items() if label == field_name}
        if len(matches) > 1:
            raise FieldIdentityError("Clone field label is ambiguous")
        identity = next(iter(matches)) if matches else extra_field_identity_key(source_note.note_type_id, field_name)
    if identity.startswith("extra:"):
        definitions = db.session.execute(select(FieldValueIdentityDefinition).where(
            or_(FieldValueIdentityDefinition.note_type_id == source_note.note_type_id,
                FieldValueIdentityDefinition.deck_install_id == install.id),
            FieldValueIdentityDefinition.identity_kind != "extra")).scalars()
        if any(field_name in (row.label_history or [row.retained_name]) for row in definitions):
            raise FieldIdentityConflict("Clone field label changed; reload the applied schema")
    row = DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id,
        source_note_id=source_note.id, field_identity_key=identity).first()
    if row is None:
        row = DeckCloneNoteFieldOverride(deck_install_id=install.id, source_note_id=source_note.id,
            field_identity_key=identity, field_name=field_name,
            source_field_def_id=identity if not identity.startswith(("added:", "extra:"))
                and db.session.get(FieldDef, identity) is not None else None,
            base_release_id=install.applied_release_id)
        db.session.add(row)
    row.operation = operation
    row.value = None if operation == "remove" else value
    return row
