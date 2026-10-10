"""Errors, dataclasses, and normalization utilities for Flama Connect."""

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

from app.services.connect.registry import (
    FLAMA_CONNECT_PROTOCOL_VERSION, MAX_NOTES_PER_REQUEST, MAX_MULTI_ACTIONS, SUPPORTED_ACTIONS,
)
IMPORT_SESSION_MODES = {"strict", "auto_sync_missing"}
IMPORT_SESSION_READY = "note_types_ready"
IMPORT_SESSION_TTL_HOURS = 24
_QUERY_CLAUSE_RE = re.compile(r'"((?:\\.|[^"\\])*)"')


class ConnectError(ValueError):
    pass


@dataclass(frozen=True)

class PreparedNote:
    deck: Deck
    note_type: NoteType
    fields: dict[str, str]
    tags: list[str]
    identity_field: FieldDef
    identity_value: str
    allow_duplicate: bool
    clone_map: DeckCloneDeckMap | None
    pending_audio: dict[str, ConnectPendingMedia]
    pending_import_media: dict[str, Any]


@dataclass(frozen=True)

class ImportBatchContext:
    """Stable schema/deck state reused by every note in one transport package."""

    note_types_by_id: dict[str, NoteType]
    note_type_hashes_by_id: dict[str, str]
    decks_by_path: dict[str, Deck]
    clone_maps_by_deck_id: dict[int, DeckCloneDeckMap]


@dataclass(frozen=True)

class NormalizedNoteTypePlan:
    source_model_id: str
    source_model_name: str
    target_note_type_id: str | None
    fields: tuple[dict[str, Any], ...]
    templates: tuple[dict[str, str], ...]
    field_mapping: dict[str, str]
    schema_hash: str



def _normalized_identity(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split()).strip()



def _deck_path(deck: Deck) -> str:
    names: list[str] = []
    current: Deck | None = deck
    seen: set[int] = set()
    while current is not None and current.id not in seen and len(names) < 64:
        seen.add(current.id)
        names.append(current.name)
        current = current.parent
    return "::".join(reversed(names))



def _unescape_query_clause(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")



def _session_source_key(params: dict[str, Any]) -> str:
    raw = params.get("sourceKey") or params.get("source") or "anki"
    value = str(raw).strip()
    if not value or len(value) > 255 or any(ord(char) < 32 for char in value):
        raise ConnectError("sourceKey is invalid")
    return value



