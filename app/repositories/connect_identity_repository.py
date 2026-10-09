"""Narrow reads for Connect identity checks; callers own transactions."""

from sqlalchemy import literal
from sqlalchemy.orm import selectinload

from models import db
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template


def local_identity_rows(*, user_id: int, deck_id: int, field_name: str):
    # Keep JSON's value type. Casting/lowercasing in SQL would change the
    # NFKC/whitespace normalization used by Connect, or its case sensitivity.
    return db.session.query(
        Note.id,
        Note.note_type_id,
        Note.field_values[field_name].label("identity_value"),
    ).filter(Note.user_id == user_id, Note.deck_id == deck_id).all()


def local_note_types(*, user_id: int, deck_id: int):
    local_note_exists = db.session.query(Note.id).filter(
        Note.note_type_id == NoteType.id,
        Note.user_id == user_id,
        Note.deck_id == deck_id,
    ).exists()
    return NoteType.query.filter(local_note_exists).options(
        selectinload(NoteType.field_defs),
    ).all()


def has_active_template(note_type_id: str) -> bool:
    return db.session.query(Template.id).join(
        StudyApplication, StudyApplication.template_id == Template.id,
    ).filter(
        StudyApplication.note_type_id == note_type_id,
        StudyApplication.status_code == "ACTIVE",
    ).first() is not None


def _source_conditions(install, source_deck_id: int, *, uses_release: bool):
    conditions = [Note.deck_id == source_deck_id]
    if install.source_owner_user_id is not None:
        conditions.append(Note.user_id == install.source_owner_user_id)
    snapshot_at = install.base_snapshot_at or install.installed_at
    if not uses_release and snapshot_at is not None:
        conditions.append(Note.created_at <= snapshot_at)
    return conditions


def clone_source_rows(*, install, source_deck_id: int, uses_release: bool):
    # A versioned install must not hydrate source-live field values. Its
    # values come from the immutable release reader in the service instead.
    values = literal(None) if uses_release else Note.field_values
    return db.session.query(
        Note.id, Note.note_type_id, values.label("field_values"),
    ).filter(*_source_conditions(install, source_deck_id, uses_release=uses_release)).all()


def clone_note_overrides(*, install, source_deck_id: int, uses_release: bool):
    return DeckCloneNoteFieldOverride.query.join(
        Note, Note.id == DeckCloneNoteFieldOverride.source_note_id,
    ).filter(
        DeckCloneNoteFieldOverride.deck_install_id == install.id,
        *_source_conditions(install, source_deck_id, uses_release=uses_release),
    ).all()


def local_note_by_id(*, user_id: int, deck_id: int, note_type_id: str, note_id: str):
    return Note.query.filter_by(
        id=note_id, user_id=user_id, deck_id=deck_id, note_type_id=note_type_id,
    ).first()
