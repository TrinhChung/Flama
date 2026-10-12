"""Deck, NoteType, and FieldDef resolvers for Connect protocol."""

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

from models.study_application import StudyApplication
from models import db
from models.audit_log import AuditLog
from models.card import Card
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
from models.study_application import StudyApplication
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


from app.services.connect.base import (
    ConnectError,
    PreparedNote,
    _deck_path,
    _normalized_identity,
)

def _owned_decks(user_id: int) -> list[Deck]:
    return (
        Deck.query.filter(Deck.owner_user_id == user_id, Deck.deleted_at.is_(None))
        .order_by(Deck.position.asc(), Deck.id.asc())
        .all()
    )



def deck_names(user_id: int) -> list[str]:
    return sorted({_deck_path(deck) for deck in _owned_decks(user_id)}, key=str.casefold)



def _resolve_deck(user_id: int, deck_name: object, *, lock: bool = False, allow_create: bool = False) -> Deck:
    if not isinstance(deck_name, str) or not deck_name.strip() or len(deck_name) > 2048:
        raise ConnectError("Thiếu deckName. Vui lòng chọn deck đích trong Yomitan.")
    target = deck_name.strip()

    # 1. Search by exact full path match (e.g. "Japanese::N3")
    owned = _owned_decks(user_id)
    matches = [deck for deck in owned if _deck_path(deck) == target]
    if len(matches) >= 1:
        target_deck = matches[0]
    else:
        # 2. Case-insensitive full-path match. Never bind a root name to an
        # unrelated nested deck that happens to share the same leaf name.
        lower_target = target.lower()
        matches = [deck for deck in owned if _deck_path(deck).lower() == lower_target]
        if len(matches) >= 1:
            target_deck = matches[0]
        elif allow_create:
            tokens = [t.strip() for t in target.split("::") if t.strip()]
            if not tokens:
                raise ConnectError("Không tìm thấy deck đích hoặc bạn không có quyền ghi vào deck này.")
            current_parent_id = None
            final_deck = None
            for token in tokens:
                existing = Deck.query.filter(
                    Deck.owner_user_id == user_id,
                    Deck.parent_id == current_parent_id if current_parent_id is not None else Deck.parent_id.is_(None),
                    Deck.name == token,
                    Deck.deleted_at.is_(None),
                ).first()
                if existing:
                    final_deck = existing
                    current_parent_id = existing.id
                else:
                    max_pos = db.session.query(db.func.max(Deck.position)).filter(
                        Deck.parent_id == current_parent_id if current_parent_id is not None else Deck.parent_id.is_(None)
                    ).scalar()
                    pos = int(max_pos or 0) + 1
                    node = Deck(
                        owner_user_id=user_id,
                        parent_id=current_parent_id,
                        name=token,
                        position=pos,
                    )
                    db.session.add(node)
                    db.session.flush()
                    final_deck = node
                    current_parent_id = node.id
            target_deck = final_deck
        else:
            raise ConnectError("Không tìm thấy deck đích hoặc bạn không có quyền ghi vào deck này.")

    if not lock:
        return target_deck

    deck = (
        Deck.query.filter(Deck.id == target_deck.id, Deck.owner_user_id == user_id, Deck.deleted_at.is_(None))
        .with_for_update()
        .first()
    )
    if deck is None:
        return target_deck
    return deck



def _accessible_note_types(
    user_id: int,
    *,
    eager_schema: bool = False,
) -> list[NoteType]:
    installed_ids = [
        r[0]
        for r in db.session.query(NoteTypeInstall.installed_note_type_id)
        .filter_by(user_id=user_id)
        .all()
        if r[0]
    ]
    query = NoteType.query.filter(
            (NoteType.user_id == user_id)
            | (NoteType.id.in_(installed_ids))
        )
    if eager_schema:
        query = query.options(
            selectinload(NoteType.field_defs),
            selectinload(NoteType.study_applications).selectinload(StudyApplication.template),
        )
    return query.order_by(NoteType.name.asc(), NoteType.id.asc()).all()



def model_names(user_id: int) -> list[str]:
    return [row.name for row in _accessible_note_types(user_id)]



def _resolve_note_type(user_id: int, model_name: object) -> NoteType:
    if not isinstance(model_name, str) or not model_name.strip() or len(model_name) > 255:
        raise ConnectError("modelName is required")
    target = model_name.strip()
    note_types = _accessible_note_types(user_id)
    id_matches = [nt for nt in note_types if nt.id == target]
    if id_matches:
        return id_matches[0]

    matches = [nt for nt in note_types if nt.name == target]
    if not matches:
        matches = [nt for nt in note_types if nt.name.lower() == target.lower()]
    if len(matches) != 1:
        raise ConnectError("model was not found or is ambiguous")
    return matches[0]



def _identity_field(note_type: NoteType) -> FieldDef:
    rows = [field for field in note_type.field_defs if field.identity_role == "primary"]
    if len(rows) != 1:
        raise ConnectError("model must declare exactly one primary identity field")
    field = rows[0]
    if field.field_type != "text" or not field.required:
        raise ConnectError("the primary identity field must be required text")
    return field



def model_field_names(user_id: int, model_name: object) -> list[str]:
    note_type = _resolve_note_type(user_id, model_name)
    identity = _identity_field(note_type)
    ordered = sorted(note_type.field_defs, key=lambda item: (item.position, item.id))
    return [identity.name] + [field.name for field in ordered if field.id != identity.id]



def _clone_map_for_deck(user_id: int, deck_id: int) -> DeckCloneDeckMap | None:
    return (
        DeckCloneDeckMap.query.join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id)
        .filter(
            DeckCloneDeckMap.local_deck_id == deck_id,
            DeckInstall.user_id == user_id,
            DeckInstall.clone_mode == "logical_overlay",
        )
        .first()
    )



def _find_existing_note(user_id: int, prepared: PreparedNote, *, lookup=None) -> Note | None:
    from app.services.connect.identity_lookup import NoteIdentityLookup

    return (lookup or NoteIdentityLookup(user_id)).existing_local_note(prepared)



