"""Extracted share submodule."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any

from sqlalchemy.orm import joinedload
from sqlalchemy.orm.attributes import flag_modified
from sqlalchemy.exc import OperationalError

from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import *

from app.controllers import flashcards_marketplace_controller as marketplace_ctrl
from app.controllers.deck_controller import collect_ancestor_ids, collect_subtree_ids

# We will let them import classes/constants from core
from .core import *

def validate_note_type_publish_requirements(note_type: NoteType) -> str | None:
    if not (note_type.name or "").strip():
        return "Title is required for publish."
    if not (note_type.description or "").strip():
        return "Description is required for publish."
    if not (note_type.primary_category or "").strip():
        return "primary_category is required for publish."
    preview_text = (note_type.preview_text or "").strip()
    preview_image = (note_type.preview_image_url or "").strip()
    if not preview_text and not preview_image:
        return "Preview text or preview image is required for publish."
    if not (note_type.version or "").strip():
        return "Version is required for publish."
    if note_type.pricing_mode == "paid" and int(note_type.price_cents or 0) <= 0:
        return "Paid note type must have a positive price."
    if not note_type.field_defs:
        return "At least one field is required for publish."
    if not note_type.templates:
        return "At least one card template is required for publish."
    return None

def apply_note_type_marketplace_payload(
    note_type: NoteType,
    payload: dict[str, Any],
    *,
    allow_set_official: bool,
    publish_statuses_visible: set[str] | None = None,
) -> str | None:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    if "title" in payload or "name" in payload:
        new_name = (payload.get("title") or payload.get("name") or "").strip()
        if not new_name:
            return "Title is required."
        existing = NoteType.query.filter(
            NoteType.user_id == note_type.user_id,
            NoteType.name == new_name,
            NoteType.id != note_type.id,
        ).first()
        if existing:
            return "Another note type already uses this title."
        note_type.name = new_name

    if "description" in payload:
        note_type.description = (payload.get("description") or "").strip() or None
    if "primary_category" in payload:
        note_type.primary_category = (payload.get("primary_category") or "").strip() or None
    if "tags" in payload:
        note_type.tags = marketplace_ctrl.normalize_marketplace_tags(payload.get("tags"))
    if "preview_text" in payload:
        note_type.preview_text = (payload.get("preview_text") or "").strip() or None
    if "preview_image_url" in payload:
        note_type.preview_image_url = (payload.get("preview_image_url") or "").strip() or None
    if "version" in payload:
        note_type.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        note_type.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_cents, pricing_error = marketplace_ctrl.normalize_pricing(
        payload,
        current_mode=str(note_type.pricing_mode or "free"),
        current_price_cents=int(note_type.price_cents or 0),
    )
    if pricing_error:
        return pricing_error
    note_type.pricing_mode = pricing_mode
    note_type.price_cents = price_cents

    if "is_official" in payload:
        if not allow_set_official:
            return "Only admin can set official flag."
        note_type.is_official = bool(payload.get("is_official"))

    if "publish_status" in payload:
        candidate_status = str(payload.get("publish_status") or "").strip().lower()
        if candidate_status not in {"private", "published", "unlisted", "archived"}:
            return "publish_status is invalid."
        if candidate_status in visible_statuses:
            err = validate_note_type_publish_requirements(note_type)
            if err:
                return err
            if note_type.publish_status not in visible_statuses:
                note_type.published_at = datetime.utcnow()
            note_type.archived_at = None
        elif candidate_status == "archived":
            note_type.archived_at = datetime.utcnow()
        note_type.publish_status = candidate_status

    return None

def validate_deck_publish_requirements(deck_item: DeckMarketplaceItem) -> str | None:
    if not (deck_item.title or "").strip():
        return "Title is required for publish."
    if not (deck_item.description or "").strip():
        return "Description is required for publish."
    if not (deck_item.primary_category or "").strip():
        return "primary_category is required for publish."
    if not (deck_item.preview_text or "").strip() and int(deck_item.sample_cards_count or 0) <= 0:
        return "Preview text or sample_cards_count > 0 is required for publish."
    if not (deck_item.version or "").strip():
        return "Version is required for publish."
    if deck_item.pricing_mode == "paid" and int(deck_item.price_cents or 0) <= 0:
        return "Paid deck must have a positive price."
    if deck_item.source_deck_id is None:
        return "source_deck_id is required for publish."
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        return "source_note_type_id is required for publish."
    source_note_type = NoteType.query.get(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found for publish."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type that has at least one template."
    return None

def apply_deck_marketplace_payload(
    deck_item: DeckMarketplaceItem,
    payload: dict[str, Any],
    *,
    allow_set_official: bool,
    publish_statuses_visible: set[str] | None = None,
) -> str | None:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if not title:
            return "title is required."
        deck_item.title = title
    if "description" in payload:
        deck_item.description = (payload.get("description") or "").strip()
    if "primary_category" in payload:
        category = (payload.get("primary_category") or "").strip()
        if not category:
            return "primary_category is required."
        deck_item.primary_category = category
    if "tags" in payload:
        deck_item.tags = marketplace_ctrl.normalize_marketplace_tags(payload.get("tags"))
    if "preview_text" in payload:
        deck_item.preview_text = (payload.get("preview_text") or "").strip() or None
    if "sample_cards_count" in payload:
        try:
            deck_item.sample_cards_count = max(0, int(payload.get("sample_cards_count") or 0))
        except (TypeError, ValueError):
            return "sample_cards_count must be an integer."
    if "source_deck_id" in payload:
        source_deck_id_raw = payload.get("source_deck_id")
        if source_deck_id_raw in (None, ""):
            deck_item.source_deck_id = None
        else:
            try:
                deck_item.source_deck_id = int(source_deck_id_raw)
            except (TypeError, ValueError):
                return "source_deck_id must be an integer."
    if "source_note_type_id" in payload:
        deck_item.source_note_type_id = (payload.get("source_note_type_id") or "").strip() or None
    if "version" in payload:
        deck_item.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        deck_item.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_cents, pricing_error = marketplace_ctrl.normalize_pricing(
        payload,
        current_mode=str(deck_item.pricing_mode or "free"),
        current_price_cents=int(deck_item.price_cents or 0),
    )
    if pricing_error:
        return pricing_error
    deck_item.pricing_mode = pricing_mode
    deck_item.price_cents = price_cents

    if "is_official" in payload:
        if not allow_set_official:
            return "Only admin can set official flag."
        deck_item.is_official = bool(payload.get("is_official"))

    if "publish_status" in payload:
        candidate_status = str(payload.get("publish_status") or "").strip().lower()
        if candidate_status not in {"private", "published", "unlisted", "archived"}:
            return "publish_status is invalid."
        if candidate_status in visible_statuses:
            err = validate_deck_publish_requirements(deck_item)
            if err:
                return err
            if deck_item.publish_status not in visible_statuses:
                deck_item.published_at = datetime.utcnow()
            deck_item.archived_at = None
        elif candidate_status == "archived":
            deck_item.archived_at = datetime.utcnow()
        deck_item.publish_status = candidate_status

    return None

def is_card_visible_in_clone_scope(
    *,
    scope: CloneDeckScope,
    card_obj: Card | None,
) -> bool:
    if card_obj is None or card_obj.note is None:
        return False
    if card_obj.note.deck_id is None or int(card_obj.note.deck_id) not in set(scope.source_deck_ids):
        return False
    if scope.source_owner_user_id is not None and card_obj.note.user_id != scope.source_owner_user_id:
        return False
    if scope.base_snapshot_at is not None:
        note_created = card_obj.note.created_at or datetime.min
        card_created = card_obj.created_at or datetime.min
        if note_created > scope.base_snapshot_at or card_created > scope.base_snapshot_at:
            return False
    return True

def is_note_type_visible_for_shared(note_type: NoteType) -> bool:
    return str(note_type.publish_status or "").strip().lower() == "published"

def is_deck_item_visible_for_shared(deck_item: DeckMarketplaceItem) -> bool:
    return str(deck_item.publish_status or "").strip().lower() == "published"

