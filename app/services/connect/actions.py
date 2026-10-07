"""Single-note actions: check_note, add_note, find_notes, get_user_info."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import re
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple
import unicodedata

from flask import current_app
from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload, selectinload

from app.repositories import (
    flashcards_share_repository,
    study_repository,
    vocabulary_repository,
)
from app.services import (
    anki_scheduler,
    deck_working_tree_service,
    flashcard_content_service,
    flashcards_share,
    flashcards_share_service,
    flama_connect_media_service,
    study_service,
)
from app.services.anki_content_normalizer import (
    normalize_anki_field_values,
    normalize_anki_text_entities,
)
from app.validators.flashcard_input import RequestValidationError, validate_note_create_request

from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.connect_import_media import ConnectImportMedia
from models.connect_import_package import ConnectImportPackage
from models.connect_import_session import ConnectImportSession
from models.connect_note_ref import ConnectNoteRef
from models.connect_note_type_ref import ConnectNoteTypeRef
from models.connect_pending_media import ConnectPendingMedia
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_deck_ref import ConnectSourceDeckRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.review_event import ReviewEvent
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)
UTC = timezone.utc

FLAMA_CONNECT_PROTOCOL_VERSION = 6
MAX_NOTES_PER_REQUEST = 50
MAX_MULTI_ACTIONS = 10
SUPPORTED_ACTIONS = (
    "version",
    "apiReflect",
    "deckNames",
    "modelNames",
    "modelFieldNames",
    "canAddNotes",
    "canAddNotesWithErrorDetail",
    "findNotes",
    "multi",
    "addNote",
    "storeMediaFile",
)
IMPORT_SESSION_MODES = {"strict", "auto_sync_missing"}
IMPORT_SESSION_READY = "note_types_ready"
IMPORT_SESSION_TTL_HOURS = 24
_QUERY_CLAUSE_RE = re.compile(r'"((?:\\.|[^"\\])*)"')


from app.services.connect.base import (
    ConnectError,
    ImportBatchContext,
    PreparedNote,
    _deck_path,
    _normalized_identity,
    _unescape_query_clause,
)
from app.services.connect.resolvers import (
    _clone_map_for_deck,
    _find_existing_note,
    _identity_field,
    _resolve_deck,
    _resolve_note_type,
)

def _parse_note(
    user_id: int,
    raw_note: object,
    *,
    lock_deck: bool = False,
    allow_create_deck: bool = False,
    allow_mixed_model: bool = False,
    import_session_id: str | None = None,
    batch_context: ImportBatchContext | None = None,
    existing_note: Note | None = None,
) -> PreparedNote:
    if not isinstance(raw_note, dict):
        raise ConnectError("note must be an object")
    unknown = set(raw_note) - {"deckName", "modelName", "fields", "tags", "options", "audio", "picture", "video"}
    if unknown:
        raise ConnectError("note contains unsupported properties")
    for media_key in ("audio", "picture", "video"):
        if raw_note.get(media_key):
            raise ConnectError("media import is not supported in this version")

    deck_name = raw_note.get("deckName")
    normalized_deck_name = deck_name.strip() if isinstance(deck_name, str) else ""
    deck = batch_context.decks_by_path.get(normalized_deck_name) if batch_context else None
    if deck is None:
        deck = _resolve_deck(
            user_id,
            deck_name,
            lock=lock_deck,
            allow_create=allow_create_deck,
        )

    model_name = raw_note.get("modelName")
    normalized_model_name = model_name.strip() if isinstance(model_name, str) else ""
    note_type = batch_context.note_types_by_id.get(normalized_model_name) if batch_context else None
    if note_type is None:
        note_type = _resolve_note_type(user_id, model_name)
    if not allow_mixed_model and deck.note_type_id is not None and deck.note_type_id != note_type.id:
        raise ConnectError("deck is bound to a different model")
    if not note_type.templates:
        raise ConnectError("model has no card template")

    fields = raw_note.get("fields")
    if not isinstance(fields, dict) or len(fields) > 100:
        raise ConnectError("fields must be an object with at most 100 entries")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in fields.items()):
        raise ConnectError("field names and values must be strings")
    if any(
        not key
        or len(key) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in key)
        for key in fields
    ):
        raise ConnectError("field names are invalid")
    field_defs_by_name = {field.name: field for field in note_type.field_defs}
    if import_session_id is None:
        fields = normalize_anki_field_values(fields, tuple(note_type.field_defs))
    else:
        fields = {
            name: normalize_anki_text_entities(value)
            for name, value in fields.items()
        }
    if import_session_id is None and any(
        field_defs_by_name.get(field_name) is not None
        and field_defs_by_name[field_name].field_type in {"image", "diagram"}
        and bool(str(value or "").strip())
        for field_name, value in fields.items()
    ):
        raise ConnectError("Flama Connect hiện chỉ hỗ trợ media audio MP3.")
    options = raw_note.get("options") or {}
    if not isinstance(options, dict):
        raise ConnectError("options must be an object")
    unknown_options = set(options) - {"allowDuplicate", "duplicateScope", "duplicateScopeOptions"}
    if unknown_options:
        raise ConnectError("options contains unsupported properties")
    if "allowDuplicate" in options and not isinstance(options.get("allowDuplicate"), bool):
        raise ConnectError("allowDuplicate must be a boolean")
    if "duplicateScope" in options and options.get("duplicateScope") not in {"collection", "deck", "deck-root"}:
        raise ConnectError("duplicateScope is invalid")
    duplicate_options = options.get("duplicateScopeOptions")
    if duplicate_options is not None:
        if not isinstance(duplicate_options, dict):
            raise ConnectError("duplicateScopeOptions must be an object")
        if set(duplicate_options) - {"deckName", "checkChildren", "checkAllModels"}:
            raise ConnectError("duplicateScopeOptions contains unsupported properties")
        # This is only Yomitan's duplicate-scope override. It may be null and
        # must never replace note.deckName as the destination deck.
        duplicate_deck_name = duplicate_options.get("deckName")
        if "deckName" in duplicate_options and duplicate_deck_name is not None:
            if (
                not isinstance(duplicate_deck_name, str)
                or len(duplicate_deck_name) > 2048
                or any(ord(character) < 32 or ord(character) == 127 for character in duplicate_deck_name)
            ):
                raise ConnectError("duplicateScopeOptions.deckName must be null or a valid string")
        for option_name in ("checkChildren", "checkAllModels"):
            if option_name in duplicate_options and not isinstance(duplicate_options.get(option_name), bool):
                raise ConnectError(f"duplicateScopeOptions.{option_name} must be a boolean")
    tags = raw_note.get("tags") or []
    pending_audio: dict[str, ConnectPendingMedia] = {}
    pending_import_media: dict[str, Any] = {}
    try:
        if import_session_id is not None:
            pending_import_media, allowed_media_references = flama_connect_media_service.resolve_import_media(
                user_id=user_id,
                session_id=import_session_id,
                note_type=note_type,
                raw_fields=fields,
                lock=lock_deck,
                existing_note=existing_note,
            )
        else:
            pending_audio, allowed_media_references = flama_connect_media_service.resolve_pending_audio(
                user_id=user_id,
                note_type=note_type,
                raw_fields=fields,
                lock=lock_deck,
            )
    except flama_connect_media_service.ConnectMediaError as exc:
        raise ConnectError(str(exc)) from exc
    try:
        validated = validate_note_create_request(
            note_type=note_type,
            payload={
                "note_type_id": note_type.id,
                "deck_id": deck.id,
                "field_values": fields,
                "tags": tags,
            },
            note_media_ids=allowed_media_references,
            allow_missing_media=import_session_id is not None,
        )
    except RequestValidationError as exc:
        raise ConnectError(str(exc)) from exc

    identity = _identity_field(note_type)
    identity_value = _normalized_identity(validated.field_values.get(identity.name))
    if not identity_value:
        raise ConnectError("the primary identity field cannot be empty")
    return PreparedNote(
        deck=deck,
        note_type=note_type,
        fields=validated.field_values,
        tags=list(validated.tags or []),
        identity_field=identity,
        identity_value=identity_value,
        allow_duplicate=bool(options.get("allowDuplicate", False)),
        clone_map=(
            batch_context.clone_maps_by_deck_id.get(deck.id)
            if batch_context is not None
            else _clone_map_for_deck(user_id, deck.id)
        ),
        pending_audio=pending_audio,
        pending_import_media=pending_import_media,
    )



def _is_duplicate(user_id: int, prepared: PreparedNote) -> bool:
    local_notes = Note.query.filter_by(user_id=user_id, deck_id=prepared.deck.id).all()
    for note in local_notes:
        if _normalized_identity((note.field_values or {}).get(prepared.identity_field.name)) == prepared.identity_value:
            return True

    clone_map = prepared.clone_map
    if clone_map is None:
        return False
    install = clone_map.deck_install
    source_deck = db.session.get(Deck, clone_map.source_deck_id)
    if source_deck is None:
        return False
    schema = flashcards_share_service.build_clone_schema_view(
        install=install,
        source_note_type_id=source_deck.note_type_id,
    )
    identity_name = prepared.identity_field.name
    source_query = Note.query.filter(Note.deck_id == clone_map.source_deck_id)
    if install.source_owner_user_id is not None:
        source_query = source_query.filter(Note.user_id == install.source_owner_user_id)
    if install.base_snapshot_at or install.installed_at:
        source_query = source_query.filter(Note.created_at <= (install.base_snapshot_at or install.installed_at))
    for source_note in source_query.all():
        values = flashcards_share_service.apply_clone_note_field_overrides(
            install=install,
            source_note=source_note,
            schema_view=schema,
        )
        if _normalized_identity(values.get(identity_name)) == prepared.identity_value:
            return True
    return False



def _ensure_note_ref(note: Note, user_id: int) -> ConnectNoteRef:
    row = ConnectNoteRef.query.filter_by(
        note_id=note.id,
        user_id=user_id,
        provider="yomitan",
    ).first()
    if row is None:
        ref_kwargs: dict[str, Any] = {
            "note_id": note.id,
            "user_id": user_id,
            "provider": "yomitan",
        }
        if note.id and str(note.id).isdigit():
            cand_id = int(note.id)
            if not db.session.get(ConnectNoteRef, cand_id):
                ref_kwargs["id"] = cand_id
        row = ConnectNoteRef(**ref_kwargs)
        db.session.add(row)
        db.session.flush()
    return row



def check_note(user_id: int, raw_note: object) -> tuple[bool, str | None]:
    try:
        prepared = _parse_note(user_id, raw_note, lock_deck=False)
        if not prepared.allow_duplicate and _is_duplicate(user_id, prepared):
            return False, "cannot create note because it is a duplicate in the target deck"
        return True, None
    except ConnectError as exc:
        return False, str(exc)



def add_note(user_id: int, raw_note: object) -> int:
    prepared = _parse_note(user_id, raw_note, lock_deck=True)
    if not prepared.allow_duplicate and _is_duplicate(user_id, prepared):
        existing_note = _find_existing_note(user_id, prepared)
        if existing_note:
            # Update fields if new content is present
            updated = False
            changed_field_names: set[str] = set()
            field_vals = dict(existing_note.field_values or {})
            for k, v in prepared.fields.items():
                if v and field_vals.get(k) != v:
                    field_vals[k] = v
                    updated = True
                    changed_field_names.add(k)
            if updated:
                existing_note.field_values = field_vals
                if prepared.clone_map is None:
                    from app.services import deck_working_tree_service

                    deck_working_tree_service.mark_note_fields_changed(
                        note=existing_note,
                        field_names=changed_field_names,
                    )
                db.session.commit()
            return int(_ensure_note_ref(existing_note, user_id).id)
        raise ConnectError("cannot create note because it is a duplicate in the target deck")
    if prepared.deck.note_type_id is None:
        prepared.deck.note_type_id = prepared.note_type.id

    materialized = None
    try:
        max_ref_id = db.session.query(db.func.max(ConnectNoteRef.id)).scalar() or 0
        next_ref_id = int(max_ref_id) + 1
        note_id = str(next_ref_id)
        while db.session.query(Note.id).filter_by(id=note_id).first() is not None:
            next_ref_id += 1
            note_id = str(next_ref_id)

        note = Note(
            id=note_id,
            note_type_id=prepared.note_type.id,
            user_id=user_id,
            deck_id=prepared.deck.id,
            field_values=prepared.fields,
            tags=prepared.tags,
        )
        db.session.add(note)
        db.session.flush()
        from app.repositories.template_library_repository import create_cards_for_note
        from models.study_application import StudyApplication
        templates = StudyApplication.query.filter_by(note_type_id=prepared.note_type.id, status_code="ACTIVE").all()
        if not templates:
            # An intentionally retired NoteType stays empty. Only legacy
            # types without any occurrence receive the compatibility default.
            if StudyApplication.query.filter_by(note_type_id=prepared.note_type.id).first() is not None:
                raise ValueError("NoteType has no active template application.")
            tmpl = Template(
                note_type_id=prepared.note_type.id,
                name="Card 1",
                position=0,
                front_format="{{Front}}",
                back_format="{{Back}}",
            )
            db.session.add(tmpl)
            db.session.flush()
        create_cards_for_note(db.session, note)

        materialized = flama_connect_media_service.materialize_audio(
            user_id=user_id,
            note=note,
            attachments=prepared.pending_audio,
        )

        if prepared.clone_map is not None:
            install = prepared.clone_map.deck_install
            db.session.add(DeckCloneAddedNote(deck_install_id=install.id, note_id=note.id))
            install.last_sync_status = "needs_sync"
            install.last_activity_at = datetime.utcnow()
        else:
            from app.services import deck_working_tree_service

            deck_working_tree_service.mark_note_fields_changed(
                note=note,
                field_names=(note.field_values or {}).keys(),
                operation="add",
            )

        ref = _ensure_note_ref(note, user_id)
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="connect.note.create",
                payload={
                    "note_id": note.id,
                    "connect_note_id": int(ref.id),
                    "deck_id": prepared.deck.id,
                    "note_type_id": prepared.note_type.id,
                    "clone_install_id": prepared.clone_map.deck_install_id if prepared.clone_map else None,
                    "media_count": len(prepared.pending_audio),
                },
            )
        )
        db.session.commit()
    except flama_connect_media_service.ConnectMediaError as exc:
        db.session.rollback()
        flama_connect_media_service.compensate_materialized(materialized)
        raise ConnectError(str(exc)) from exc
    except Exception:
        db.session.rollback()
        flama_connect_media_service.compensate_materialized(materialized)
        raise
    flama_connect_media_service.finalize_materialized(materialized)
    return int(ref.id)



def find_notes(user_id: int, query: object) -> list[int]:
    if not isinstance(query, str) or len(query) > 2048:
        raise ConnectError("query must be a string no longer than 2048 characters")
    deck_name: str | None = None
    field_name: str | None = None
    field_value: str | None = None
    for raw_clause in _QUERY_CLAUSE_RE.findall(query):
        clause = _unescape_query_clause(raw_clause)
        if ":" not in clause:
            continue
        key, value = clause.split(":", 1)
        if key.casefold() == "deck":
            deck_name = value
        else:
            field_name, field_value = key, value
    if deck_name is None or field_name is None or field_value is None:
        return []
    deck = _resolve_deck(user_id, deck_name)
    expected = _normalized_identity(field_value)
    results: list[int] = []
    for note in Note.query.filter_by(user_id=user_id, deck_id=deck.id).all():
        note_type = db.session.get(NoteType, note.note_type_id)
        if note_type is None:
            continue
        try:
            identity = _identity_field(note_type)
        except ConnectError:
            continue
        if identity.name.casefold() != field_name.casefold():
            continue
        if _normalized_identity((note.field_values or {}).get(identity.name)) == expected:
            results.append(int(_ensure_note_ref(note, user_id).id))
    clone_map = _clone_map_for_deck(user_id, deck.id)
    if clone_map is not None:
        install = clone_map.deck_install
        source_deck = db.session.get(Deck, clone_map.source_deck_id)
        local_note_type = db.session.get(NoteType, deck.note_type_id) if deck.note_type_id else None
        if source_deck is not None and local_note_type is not None:
            try:
                local_identity = _identity_field(local_note_type)
            except ConnectError:
                local_identity = None
            if local_identity is not None and local_identity.name.casefold() == field_name.casefold():
                schema = flashcards_share_service.build_clone_schema_view(
                    install=install,
                    source_note_type_id=source_deck.note_type_id,
                )
                source_query = Note.query.filter(Note.deck_id == clone_map.source_deck_id)
                if install.source_owner_user_id is not None:
                    source_query = source_query.filter(Note.user_id == install.source_owner_user_id)
                if install.base_snapshot_at or install.installed_at:
                    source_query = source_query.filter(
                        Note.created_at <= (install.base_snapshot_at or install.installed_at)
                    )
                for source_note in source_query.all():
                    values = flashcards_share_service.apply_clone_note_field_overrides(
                        install=install,
                        source_note=source_note,
                        schema_view=schema,
                    )
                    if _normalized_identity(values.get(local_identity.name)) == expected:
                        results.append(int(_ensure_note_ref(source_note, user_id).id))
    return sorted(set(results))



def get_user_info(user_id: int) -> dict[str, Any]:
    user = db.session.get(User, user_id)
    if user is None:
        raise ConnectError("User not found")
    return {
        "userId": user.id,
        "username": user.username,
        "displayName": getattr(user, "username", "Flama User"),
        "workspace": "default",
        "importPermission": True,
        "uploadLimit": 1048576,
    }



