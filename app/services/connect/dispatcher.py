"""AnkiConnect / Yomitan RPC command dispatcher."""

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
from app.services.anki_content_normalizer import normalize_anki_field_values
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


from app.services.connect.actions import (
    CheckBatchContext,
    add_note,
    check_note,
    find_notes,
    get_user_info,
)
from app.services.connect.base import ConnectError
from app.services.connect.import_cards import (
    complete_import_session,
    get_import_note_statuses,
    get_import_status,
    import_cards,
)
from app.services.connect.import_session import create_import_session
from app.services.connect.resolvers import (
    deck_names,
    model_field_names,
    model_names,
)

def dispatch(user_id: int, action: str, params: dict[str, Any]) -> Any:
    if action == "version":
        return FLAMA_CONNECT_PROTOCOL_VERSION
    if action == "apiReflect":
        scopes = params.get("scopes")
        actions = params.get("actions")
        if (
            not isinstance(scopes, list)
            or len(scopes) > 10
            or any(not isinstance(scope, str) or len(scope) > 64 for scope in scopes)
        ):
            raise ConnectError("scopes must be an array of strings")
        if actions is not None and (
            not isinstance(actions, list)
            or len(actions) > 100
            or any(not isinstance(item, str) or len(item) > 64 for item in actions)
        ):
            raise ConnectError("actions must be null or an array of strings")
        reflected = list(SUPPORTED_ACTIONS) if actions is None else [item for item in actions if item in SUPPORTED_ACTIONS]
        return {"scopes": [scope for scope in scopes if scope == "actions"], "actions": reflected}
    if action == "validateKey":
        return {"status": "valid", "userId": user_id}
    if action == "userInfo":
        return get_user_info(user_id)
    if action == "createImportSession":
        return create_import_session(user_id, params)
    if action == "importCards":
        return import_cards(user_id, params)
    if action == "getImportStatus":
        return get_import_status(user_id, params.get("importSessionId"))
    if action == "completeImportSession":
        return complete_import_session(user_id, params.get("importSessionId"))
    if action == "deckNames":
        return deck_names(user_id)
    if action == "modelNames":
        return model_names(user_id)
    if action == "modelFieldNames":
        return model_field_names(user_id, params.get("modelName"))
    if action in {"canAddNotes", "canAddNotesWithErrorDetail"}:
        notes = params.get("notes")
        if not isinstance(notes, list) or len(notes) > MAX_NOTES_PER_REQUEST:
            raise ConnectError(f"notes must be an array with at most {MAX_NOTES_PER_REQUEST} entries")
        context = CheckBatchContext(user_id)
        checks = [check_note(user_id, note, context=context) for note in notes]
        if action == "canAddNotes":
            return [allowed for allowed, _error in checks]
        return [{"canAdd": allowed, "error": error} for allowed, error in checks]
    if action == "findNotes":
        return find_notes(user_id, params.get("query"))
    if action == "addNote":
        return add_note(user_id, params.get("note"))
    if action == "storeMediaFile":
        if params.get("path") is not None or params.get("url") is not None:
            raise ConnectError("Flama Connect không nhận media từ đường dẫn hoặc URL.")
        if "deleteExisting" in params and not isinstance(params.get("deleteExisting"), bool):
            raise ConnectError("deleteExisting phải là boolean.")
        try:
            if params.get("importSessionId") is not None:
                return flama_connect_media_service.stage_import_media(
                    user_id=user_id,
                    session_id=params.get("importSessionId"),
                    filename=params.get("filename"),
                    data=params.get("data"),
                    media_kind=params.get("mediaKind"),
                )
            return flama_connect_media_service.stage_mp3(
                user_id=user_id,
                filename=params.get("filename"),
                data=params.get("data"),
            )
        except flama_connect_media_service.ConnectMediaError as exc:
            raise ConnectError(str(exc)) from exc
    raise ConnectError("unsupported action")


