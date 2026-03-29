"""Service layer for flashcards sharing functionality."""
from __future__ import annotations

import logging
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Any, Tuple

from sqlalchemy.exc import OperationalError

from app.repositories import flashcards_share_repository
from app.repositories.deck_tree_query import collect_ancestor_ids, collect_subtree_ids
from app.services import marketplace_query_service, marketplace_taxonomy_service
from models import db
from models.flashcard import (
    Card,
    CardProgress,
    DeckCloneAddedFieldDef,
    DeckCloneDeckMap,
    DeckCloneFieldDefOverride,
    DeckCloneFieldOrderOverride,
    DeckCloneNoteFieldOverride,
    DeckInstall,
    DeckMarketplaceItem,
    DeckReview,
    FieldDef,
    Note,
    NoteType,
    NoteTypeInstall,
    NoteTypeReview,
    Template,
)
from models.deck import Deck
from models.audit_log import AuditLog

logger = logging.getLogger(__name__)
# Keep self-references stable while legacy call sites are migrated.
flashcards_share = sys.modules[__name__]

FIELD_TYPES = {"text", "richtext", "markdown", "image", "audio", "diagram"}
PUBLISH_STATUSES_VISIBLE = {"published", "unlisted"}
DECK_ACTIVE_REVIEW_THRESHOLD = 3
SHARED_DECK_TEST_SAMPLE_LIMIT = 5
SHARED_DECK_INSTALL_MAX_RETRIES = 3


def _audit(user_id: int | None, action: str, payload: dict | None = None) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        payload=payload or {},
    )
    db.session.add(entry)


def _is_mysql_deadlock(exc: Exception) -> bool:
    """Best-effort deadlock detection used by retry wrappers."""
    original = getattr(exc, "orig", None)
    if original is None:
        return False
    args = getattr(original, "args", ()) or ()
    if args:
        code_text = str(args[0]).strip()
        if code_text in {"1205", "1213"}:
            return True
    message = str(original).lower()
    return "deadlock" in message or "lock wait timeout" in message


def create_note_type(
    user_id: int,
    payload: dict,
    is_admin: bool,
) -> tuple[NoteType | None, str | None, str | None]:
    name = (payload.get("name") or payload.get("title") or "").strip()
    if not name:
        return None, "Note type name is required.", "name"

    if NoteType.query.filter_by(user_id=user_id, name=name).first():
        return None, "Note type already exists.", "name"

    note_type = NoteType(user_id=user_id, name=name)
    db.session.add(note_type)
    db.session.flush()

    input_fields = payload.get("field_defs")
    if not isinstance(input_fields, list) or not input_fields:
        input_fields = [{"name": "Word", "field_type": "text", "position": 0, "required": True}]

    for idx, row in enumerate(input_fields):
        field_name = (row.get("name") or "").strip()
        field_type = (row.get("field_type") or "text").strip()
        required = bool(row.get("required", False))
        if not field_name:
            db.session.rollback()
            return None, "Field name is required.", "field_defs"
        if field_type not in FIELD_TYPES:
            db.session.rollback()
            return None, f"Unsupported field_type: {field_type}", "field_defs"
        db.session.add(
            FieldDef(
                note_type_id=note_type.id,
                name=field_name,
                field_type=field_type,
                position=int(row.get("position", idx)),
                required=required,
            )
        )

    template_payload = payload.get("template") or {}
    front_html = (template_payload.get("front_html") or "{{Word}}").strip()
    back_html = (template_payload.get("back_html") or "{{Word}}").strip()
    shared_css = (template_payload.get("shared_css") or "").strip()
    template = Template(
        note_type_id=note_type.id,
        name=(template_payload.get("name") or "Card 1").strip() or "Card 1",
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=0,
        is_default=True,
    )
    db.session.add(template)
    
    metadata_error = flashcards_share.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if metadata_error:
        db.session.rollback()
        return None, metadata_error, None
        
    _audit(user_id, "note_type.create", {"note_type_id": note_type.id, "name": note_type.name})
    db.session.commit()
    return note_type, None, None


def create_template(note_type_id: str, user_id: int, payload: dict) -> tuple[Template | None, str | None]:
    note_type = NoteType.query.get(note_type_id)
    if not note_type:
        return None, "Note type not found."
        
    name = (payload.get("name") or "").strip() or f"Card {Template.query.filter_by(note_type_id=note_type.id).count() + 1}"
    front_html = (payload.get("front_html") or "{{Word}}").strip()
    back_html = (payload.get("back_html") or "{{Word}}").strip()
    shared_css = (payload.get("shared_css") or "").strip()
    
    max_pos = db.session.query(db.func.max(Template.position)).filter_by(note_type_id=note_type.id).scalar() or -1
    template = Template(
        note_type_id=note_type.id,
        name=name,
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=max_pos + 1,
        is_default=False,
    )
    db.session.add(template)
    db.session.flush()
    notes = Note.query.filter_by(note_type_id=note_type.id, user_id=user_id).all()
    for note in notes:
        db.session.add(Card(note_id=note.id, template_id=template.id))
        
    _audit(user_id, "template.create", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return template, None


def update_template(template: Template, user_id: int) -> None:
    _audit(user_id, "template.update", {"note_type_id": template.note_type_id, "template_id": template.id})
    db.session.commit()


def reset_template(template: Template, default_front: str, default_back: str, default_css: str) -> None:
    template.front_html = default_front
    template.back_html = default_back
    template.shared_css = default_css
    db.session.commit()


def publish_note_type(note_type: NoteType, user_id: int, payload: dict, is_admin: bool) -> tuple[bool, str | None]:
    payload.setdefault("publish_status", "published")
    validation_error = flashcards_share.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        db.session.rollback()
        return False, validation_error
        
    flashcards_share.recompute_note_type_market_stats(
        note_type,
        note_type_active_note_threshold=5,
        note_type_active_review_threshold=1,
        note_type_active_days_threshold=7,
    )
    _audit(user_id, "note_type.publish", {"note_type_id": note_type.id, "publish_status": note_type.publish_status})
    db.session.commit()
    return True, None


def create_shared_deck_item(
    user_id: int,
    payload: dict,
    is_admin: bool,
    require_source_note_type: bool
) -> tuple[DeckMarketplaceItem | None, str | None, str | None]:
    title = (payload.get("title") or "").strip()
    if not title:
        return None, "title is required.", "title"

    deck_item = DeckMarketplaceItem(
        owner_user_id=user_id,
        title=title,
        description=(payload.get("description") or "").strip(),
        primary_category=(payload.get("primary_category") or "General").strip() or "General",
        tags=payload.get("tags") or [],
        preview_text=(payload.get("preview_text") or "").strip() or None,
        sample_cards_count=0,
        pricing_mode="free",
        price_amount_minor=0,
        version="1.0.0",
        publish_status="private",
        is_official=False,
    )
    db.session.add(deck_item)
    
    validation_error = flashcards_share.apply_deck_marketplace_payload(
        deck_item,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        db.session.rollback()
        return None, validation_error, None
        
    if deck_item.source_deck_id is not None and not Deck.query.get(deck_item.source_deck_id):
        db.session.rollback()
        return None, "source_deck_id not found.", "source_deck_id"
        
    bind_error = flashcards_share.bind_deck_item_source_note_type(
        deck_item, 
        require_source_note_type=require_source_note_type
    )
    if bind_error:
        db.session.rollback()
        return None, bind_error, "source_note_type_id"
        
    flashcards_share.recompute_deck_item_market_stats(
        deck_item,
        deck_active_note_threshold=5,
        deck_active_review_threshold=1,
        deck_active_days_threshold=7,
    )
    _audit(user_id, "market.deck_item.create", {"deck_item_id": deck_item.id})
    db.session.commit()
    return deck_item, None, None


def update_shared_deck_item(
    deck_item: DeckMarketplaceItem,
    user_id: int,
    payload: dict,
    is_admin: bool,
    require_source_note_type: bool
) -> tuple[bool, str | None, str | None]:
    validation_error = flashcards_share.apply_deck_marketplace_payload(
        deck_item,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        db.session.rollback()
        return False, validation_error, None
        
    if deck_item.source_deck_id is not None and not Deck.query.get(deck_item.source_deck_id):
        db.session.rollback()
        return False, "source_deck_id not found.", "source_deck_id"
        
    bind_error = flashcards_share.bind_deck_item_source_note_type(
        deck_item, 
        require_source_note_type=require_source_note_type
    )
    if bind_error:
        db.session.rollback()
        return False, bind_error, "source_note_type_id"
        
    flashcards_share.recompute_deck_item_market_stats(
        deck_item,
        deck_active_note_threshold=5,
        deck_active_review_threshold=1,
        deck_active_days_threshold=7,
    )
    _audit(user_id, "market.deck_item.update", {"deck_item_id": deck_item.id})
    db.session.commit()
    return True, None, None


def sync_deck_item_source_note_type_and_commit(
    deck_item: DeckMarketplaceItem,
    require_source_note_type: bool
) -> tuple[str | None, bool]:
    bind_error, changed = flashcards_share.sync_deck_item_source_note_type(
        deck_item, 
        require_source_note_type=require_source_note_type
    )
    if changed:
        db.session.commit()
    return bind_error, changed



def install_shared_note_type(source_note_type: NoteType, user_id: int) -> tuple[NoteType | None, int | None]:
    installed_copy = flashcards_share.clone_note_type_for_user(source_note_type, user_id)
    now = datetime.utcnow()
    purchase_amount_minor = int(source_note_type.price_amount_minor or 0) if source_note_type.pricing_mode == "paid" else 0
    install_row = NoteTypeInstall(
        source_note_type_id=source_note_type.id,
        installed_note_type_id=installed_copy.id,
        user_id=user_id,
        purchase_amount_minor=purchase_amount_minor,
        installed_at=now,
        purchased_at=now if source_note_type.pricing_mode == "paid" else None,
    )
    db.session.add(install_row)
    
    flashcards_share.recompute_note_type_market_stats(
        source_note_type,
        note_type_active_note_threshold=5,
        note_type_active_review_threshold=1,
        note_type_active_days_threshold=7,
    )
    _audit(
        user_id,
        "market.note_type.install",
        {
            "source_note_type_id": source_note_type.id,
            "installed_note_type_id": installed_copy.id,
            "price_amount_minor": purchase_amount_minor,
            "price_cents": purchase_amount_minor,
        },
    )
    db.session.commit()
    return installed_copy, purchase_amount_minor


def rate_shared_note_type(note_type: NoteType, user_id: int, rating: int, comment: str | None) -> None:
    review = NoteTypeReview.query.filter_by(note_type_id=note_type.id, user_id=user_id).first()
    if review is None:
        review = NoteTypeReview(note_type_id=note_type.id, user_id=user_id, rating=rating, comment=comment)
        db.session.add(review)
    else:
        review.rating = rating
        review.comment = comment

    flashcards_share.recompute_note_type_market_stats(
        note_type,
        note_type_active_note_threshold=5,
        note_type_active_review_threshold=1,
        note_type_active_days_threshold=7,
    )
    _audit(user_id, "market.note_type.rate", {"note_type_id": note_type.id, "rating": rating})
    db.session.commit()


def rate_shared_deck_item(deck_item: DeckMarketplaceItem, user_id: int, rating: int, comment: str | None) -> None:
    review = DeckReview.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if review is None:
        review = DeckReview(deck_item_id=deck_item.id, user_id=user_id, rating=rating, comment=comment)
        db.session.add(review)
    else:
        review.rating = rating
        review.comment = comment

    flashcards_share.recompute_deck_item_market_stats(
        deck_item,
        deck_active_note_threshold=5,
        deck_active_review_threshold=1,
        deck_active_days_threshold=7,
    )
    _audit(user_id, "market.deck_item.rate", {"deck_item_id": deck_item.id, "rating": rating})
    db.session.commit()


def upsert_shared_deck_clone_overlay(deck_item_id: str, install: DeckInstall, user_id: int, payload: dict) -> tuple[dict | None, str | None]:
    counters, validation_error = flashcards_share.upsert_clone_overlay(
        deck_install=install,
        payload=payload,
    )
    if validation_error:
        db.session.rollback()
        return None, validation_error

    _audit(
        user_id,
        "market.deck_item.clone_overlay.upsert",
        {
            "deck_item_id": deck_item_id,
            "deck_install_id": install.id,
            "changes": counters,
        },
    )
    db.session.commit()
    return counters, None


def install_shared_deck_item(deck_item_id: str, user_id: int, publish_statuses_visible: set[str]) -> tuple[dict | None, str | None, str | None, int]:
    for attempt in range(1, SHARED_DECK_INSTALL_MAX_RETRIES + 1):
        deck_item = DeckMarketplaceItem.query.get(deck_item_id)
        if not deck_item:
            return None, "Deck item not found.", None, 404

        bind_error, changed = flashcards_share.sync_deck_item_source_note_type(
            deck_item,
            require_source_note_type=True,
        )
        if bind_error:
            return None, bind_error, None, 409

        if changed:
            try:
                db.session.commit()
            except OperationalError as exc:
                db.session.rollback()
                if flashcards_share._is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                    logger.warning(
                        "Deadlock while syncing source note type for shared deck install "
                        "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                        deck_item_id,
                        user_id,
                        attempt,
                        SHARED_DECK_INSTALL_MAX_RETRIES,
                    )
                    time.sleep(0.05 * attempt)
                    continue
                raise

        try:
            install_result = flashcards_share.install_shared_deck_item_for_user(
                deck_item,
                user_id=user_id,
                publish_statuses_visible=publish_statuses_visible,
            )
        except flashcards_share.ShareControllerError as exc:
            db.session.rollback()
            return None, exc.message, exc.field, exc.status
        except OperationalError as exc:
            db.session.rollback()
            if flashcards_share._is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while installing shared deck "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    user_id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if flashcards_share._is_mysql_deadlock(exc):
                return None, "Database deadlock detected. Please retry the install request.", None, 409
            raise

        if not install_result.get("created"):
            return install_result.get("response") or {}, None, None, 200

        _audit(user_id, "market.deck_item.install", install_result.get("audit") or {})
        try:
            db.session.commit()
        except OperationalError as exc:
            db.session.rollback()
            if flashcards_share._is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while committing shared deck install "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    user_id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if flashcards_share._is_mysql_deadlock(exc):
                return None, "Database deadlock detected. Please retry the install request.", None, 409
            raise

        return install_result.get("response") or {}, None, None, 201

    return None, "Database deadlock detected. Please retry the install request.", None, 409


DEFAULT_VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}

class ShareControllerError(Exception):
    """Domain error for flashcard share/deck flows."""

    def __init__(
        self,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
        error: str = "VALIDATION_ERROR",
    ) -> None:
        super().__init__(message)
        self.message = message
        self.status = status
        self.field = field
        self.error = error

def make_unique_note_type_name(user_id: int, base_name: str) -> str:
    candidate = base_name.strip() or "Installed NoteType"
    if not flashcards_share_repository.get_note_type_by_name(user_id, candidate):
        return candidate
    counter = 2
    while True:
        candidate_with_counter = f"{candidate} ({counter})"
        if not flashcards_share_repository.get_note_type_by_name(user_id, candidate_with_counter):
            return candidate_with_counter
        counter += 1

def resolve_single_note_type_for_deck(
    *,
    deck_id: int,
    owner_user_id: int | None = None,
) -> tuple[str | None, str | None]:
    deck_ids = collect_subtree_ids(deck_id)
    note_type_ids = flashcards_share_repository.get_note_type_ids_for_decks_notes(
        deck_ids,
        owner_user_id,
    )

    if not note_type_ids:
        return None, "Deck has no notes, cannot infer source_note_type_id."
    if len(note_type_ids) > 1:
        return None, "All notes in one deck must use the same template (note type)."

    resolved_note_type_id = note_type_ids[0]
    resolved_note_type = NoteType.query.get(resolved_note_type_id)
    if not resolved_note_type:
        return None, "Deck source note type not found."
    if not resolved_note_type.templates:
        return None, "Deck source note type has no templates."
    return resolved_note_type.id, None

def bind_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> str | None:
    if deck_item.source_deck_id is None:
        return "source_deck_id is required."

    if deck_item.source_deck_id is not None:
        inferred_note_type_id, infer_error = resolve_single_note_type_for_deck(
            deck_id=deck_item.source_deck_id,
            owner_user_id=deck_item.owner_user_id,
        )
        if infer_error and require_source_note_type and not (deck_item.source_note_type_id or "").strip():
            return infer_error
        if inferred_note_type_id:
            if deck_item.source_note_type_id and deck_item.source_note_type_id != inferred_note_type_id:
                return "source_note_type_id does not match notes inside source_deck_id."
            deck_item.source_note_type_id = inferred_note_type_id

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        if require_source_note_type:
            return "source_note_type_id is required."
        return None

    source_note_type = NoteType.query.get(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type with at least one template."
    return None

def validate_note_type_consistency_for_deck(
    *,
    deck_id: int | None,
    note_type_id: str,
    user_id: int,
    exclude_note_id: str | None = None,
) -> str | None:
    if deck_id is None:
        return None

    existing_note_type_ids = flashcards_share_repository.get_note_type_ids_for_user_deck_notes(
        deck_id, user_id, exclude_note_id
    )

    if not existing_note_type_ids:
        return None
    if existing_note_type_ids == {note_type_id}:
        return None
    return "All notes in one deck must use the same template (note type)."

def _next_deck_position(parent_deck_id: int | None) -> int:
    return flashcards_share_repository.get_next_deck_position(parent_deck_id)

def sync_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> tuple[str | None, bool]:
    original_note_type_id = deck_item.source_note_type_id
    bind_error = bind_deck_item_source_note_type(
        deck_item,
        require_source_note_type=require_source_note_type,
    )
    changed = deck_item.source_note_type_id != original_note_type_id
    return bind_error, changed


def get_shared_note_type_for_view(
    note_type_id: str,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> NoteType | None:
    note_type = flashcards_share_repository.get_note_type_by_id(note_type_id)
    if note_type is None:
        return None
    if not is_note_type_visible_for_shared(
        note_type,
        user_id=user_id,
        publish_statuses_visible=publish_statuses_visible,
    ):
        return None
    return note_type


def get_shared_deck_item_for_view(
    deck_item_id: str,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> DeckMarketplaceItem | None:
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if deck_item is None:
        return None
    if not is_deck_item_visible_for_shared(
        deck_item,
        user_id=user_id,
        publish_statuses_visible=publish_statuses_visible,
    ):
        return None
    return deck_item

def build_shared_deck_item_payload(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    sample_limit: int,
    deck_active_review_threshold: int = 3,
    review_preview_limit: int = 20,
) -> dict[str, Any]:
    install = flashcards_share_repository.get_deck_install_by_user_and_item(user_id, deck_item.id)
    review = flashcards_share_repository.get_deck_review_by_user_and_item(user_id, deck_item.id)
    payload = marketplace_query_service.serialize_deck_marketplace_item(deck_item)
    payload["is_installed"] = install is not None
    payload["installed_deck_id"] = install.local_deck_id if install else None
    payload["is_owner"] = deck_item.owner_user_id == user_id
    payload["can_rate"] = can_user_rate_deck(
        deck_item,
        user_id=user_id,
        deck_active_review_threshold=deck_active_review_threshold,
    )
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }
        if review
        else None
    )
    recent_review_rows = (
        DeckReview.query.filter(
            DeckReview.deck_item_id == deck_item.id,
            DeckReview.user_id != user_id,
        )
        .order_by(DeckReview.updated_at.desc(), DeckReview.created_at.desc(), DeckReview.id.desc())
        .limit(max(1, int(review_preview_limit or 20)))
        .all()
    )
    payload["recent_reviews"] = [
        {
            "rating": int(row.rating or 0),
            "comment": row.comment,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "username": (row.user.username if row.user else "Unknown"),
        }
        for row in recent_review_rows
    ]
    payload["recent_reviews_count"] = len(payload["recent_reviews"])

    source_note_type_payload = None
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if source_note_type_id:
        source_note_type = NoteType.query.get(source_note_type_id)
        if source_note_type:
            ordered_templates = sorted(
                source_note_type.templates,
                key=lambda item: (int(item.position or 0), str(item.name or "").lower()),
            )
            source_note_type_payload = {
                "id": source_note_type.id,
                "name": source_note_type.name,
                "title": source_note_type.name,
                "publish_status": source_note_type.publish_status,
                "templates": [
                    {
                        "id": template.id,
                        "name": template.name,
                        "position": int(template.position or 0),
                        "is_default": bool(template.is_default),
                    }
                    for template in ordered_templates
                ],
            }
    payload["source_note_type"] = source_note_type_payload
    payload["test_samples"] = marketplace_query_service.build_shared_deck_test_samples(
        deck_item,
        limit=sample_limit,
    )
    payload["test_sample_limit"] = sample_limit
    return payload

def select_preview_note_for_shared_deck(
    deck_item: DeckMarketplaceItem,
    *,
    note_type_id: str,
    requested_note_id: str | None,
) -> Note | None:
    if deck_item.source_deck_id is None:
        return None

    deck_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not deck_ids:
        return None

    if requested_note_id:
        preview_note = flashcards_share_repository.get_preview_note_by_id(
            requested_note_id, note_type_id, deck_ids, deck_item.owner_user_id
        )
        if preview_note is not None:
            return preview_note

    return flashcards_share_repository.get_first_preview_note(
        note_type_id, deck_ids, deck_item.owner_user_id
    )

def _normalize_note_field_values_for_cutover(raw_values: dict | None) -> dict[str, str]:
    if not isinstance(raw_values, dict):
        return {}
    normalized: dict[str, str] = {}
    for key, value in raw_values.items():
        key_name = str(key).strip()
        if not key_name:
            continue
        normalized[key_name] = "" if value is None else str(value)
    return normalized

def _deck_paths_for_cutover(root_deck_id: int) -> dict[tuple[int, ...], int]:
    deck_ids = collect_subtree_ids(root_deck_id)
    if not deck_ids:
        return {}
    deck_rows = Deck.query.filter(Deck.id.in_(deck_ids)).all()
    if not deck_rows:
        return {}
    children_by_parent: dict[int | None, list[Deck]] = {}
    for deck_obj in deck_rows:
        children_by_parent.setdefault(deck_obj.parent_id, []).append(deck_obj)
    for rows in children_by_parent.values():
        rows.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    path_to_deck: dict[tuple[int, ...], int] = {}

    def _walk(deck_id: int, path: tuple[int, ...]) -> None:
        path_to_deck[path] = deck_id
        for index, child in enumerate(children_by_parent.get(deck_id, [])):
            _walk(child.id, path + (index,))

    _walk(root_deck_id, ())
    return path_to_deck

def _pair_legacy_local_source_notes_for_cutover(
    *,
    install: DeckInstall,
    source_to_local_deck_id: dict[int, int],
    source_owner_user_id: int | None,
    source_note_type_id: str | None,
    snapshot_at: datetime | None,
) -> list[tuple[Note, Note]]:
    local_to_source = {
        int(local_deck_id): int(source_deck_id)
        for source_deck_id, local_deck_id in source_to_local_deck_id.items()
    }
    pairs: list[tuple[Note, Note]] = []

    for local_deck_id in sorted(local_to_source.keys()):
        source_deck_id = local_to_source[local_deck_id]
        
        local_notes = flashcards_share_repository.get_notes_for_user_deck(install.user_id, local_deck_id)
        source_notes = flashcards_share_repository.get_source_notes_for_cutover(
            source_deck_id, source_owner_user_id, source_note_type_id, snapshot_at
        )

        if len(local_notes) != len(source_notes):
            raise ShareControllerError(
                (
                    f"Install {install.id}: note count mismatch in deck pair "
                    f"(local_deck_id={local_deck_id}, source_deck_id={source_deck_id}, "
                    f"local={len(local_notes)}, source={len(source_notes)})."
                ),
                status=409,
            )
        pairs.extend(zip(local_notes, source_notes))

    return pairs

def _merge_card_progress_rows_for_cutover(
    *,
    user_id: int,
    local_card_id: str,
    source_card_id: str,
) -> int:
    moved_count = 0
    progress_rows = flashcards_share_repository.get_card_progress_rows_for_local_card(user_id, local_card_id)
    
    for row in progress_rows:
        target = flashcards_share_repository.get_card_progress_for_source_card(user_id, source_card_id)
        if target is None:
            row.card_id = source_card_id
            moved_count += 1
            continue

        row_newer = (row.updated_at or datetime.min) >= (target.updated_at or datetime.min)
        if row_newer:
            target.queue = row.queue
            target.step_index = row.step_index
            target.due_at = row.due_at
            target.due_day = row.due_day
            target.interval_days = row.interval_days
            if hasattr(target, "interval_days_raw"):
                target.interval_days_raw = getattr(row, "interval_days_raw", None)
            target.is_suspended = bool(row.is_suspended)
            if hasattr(target, "is_buried"):
                target.is_buried = bool(getattr(row, "is_buried", False))
            if hasattr(target, "buried_until_day"):
                target.buried_until_day = getattr(row, "buried_until_day", None)
            target.ease_factor = row.ease_factor
            if hasattr(target, "review_kind"):
                target.review_kind = getattr(row, "review_kind", target.review_kind)
            if hasattr(target, "scheduler_mode"):
                target.scheduler_mode = getattr(row, "scheduler_mode", target.scheduler_mode)
            if hasattr(target, "memory_stability"):
                target.memory_stability = getattr(row, "memory_stability", None)
            if hasattr(target, "memory_difficulty"):
                target.memory_difficulty = getattr(row, "memory_difficulty", None)
            if hasattr(target, "suspension_reason"):
                target.suspension_reason = getattr(row, "suspension_reason", None)
            if hasattr(target, "last_leech_at"):
                target.last_leech_at = getattr(row, "last_leech_at", None)
            if hasattr(target, "last_leech_lapses"):
                target.last_leech_lapses = int(getattr(row, "last_leech_lapses", 0) or 0)
            if hasattr(target, "last_review_event_id"):
                target.last_review_event_id = getattr(row, "last_review_event_id", None)
            target.last_reviewed_at = row.last_reviewed_at or target.last_reviewed_at
        target.reps = max(int(target.reps or 0), int(row.reps or 0))
        target.lapses = max(int(target.lapses or 0), int(row.lapses or 0))
        db.session.delete(row)
        moved_count += 1
    return moved_count

def _assert_cutover_note_equivalence(
    *,
    install: DeckInstall,
    pairs: list[tuple[Note, Note]],
    schema_view: CloneSchemaView,
) -> None:
    for local_note, source_note in pairs:
        migrated_values = _normalize_note_field_values_for_cutover(
            apply_clone_note_field_overrides(
                install=install,
                source_note=source_note,
                schema_view=schema_view,
            )
        )
        local_values = _normalize_note_field_values_for_cutover(local_note.field_values)
        if migrated_values != local_values:
            raise ShareControllerError(
                (
                    f"Install {install.id}: cutover mismatch for source_note_id={source_note.id}, "
                    f"local_note_id={local_note.id}."
                ),
                status=409,
            )

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
    if note_type.pricing_mode == "paid" and int(note_type.price_amount_minor or 0) <= 0:
        return "Paid note type must have a positive price."
    if not note_type.field_defs:
        return "At least one field is required for publish."
    if not note_type.templates:
        return "At least one card template is required for publish."
    taxonomy_error = marketplace_taxonomy_service.validate_required_taxonomy(
        note_type.taxonomy_metadata if isinstance(note_type.taxonomy_metadata, dict) else {},
        content_type="note_type",
    )
    if taxonomy_error:
        return taxonomy_error
    return None

def apply_note_type_marketplace_payload(
    note_type: NoteType,
    payload: dict[str, Any],
    *,
    allow_set_official: bool,
    publish_statuses_visible: set[str] | None = None,
) -> str | None:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES
    taxonomy_keys = {
        "taxonomy_domain",
        "domain",
        "taxonomy_subject",
        "subject",
        "taxonomy_difficulty_band",
        "difficulty_band",
        "level_band",
        "taxonomy_framework",
        "framework",
        "taxonomy_framework_level",
        "framework_level",
        "taxonomy_framework_track",
        "framework_track",
        "taxonomy_learning_goals",
        "learning_goals",
        "taxonomy_primary_topics",
        "primary_topics",
        "taxonomy_format_features",
        "format_features",
        "taxonomy_audience",
        "audience",
        "taxonomy_best_used_for",
        "best_used_for",
    }

    if "title" in payload or "name" in payload:
        new_name = (payload.get("title") or payload.get("name") or "").strip()
        if not new_name:
            return "Title is required."
        existing = flashcards_share_repository.check_note_type_name_exists(note_type.user_id, new_name, note_type.id)
        if existing:
            return "Another note type already uses this title."
        note_type.name = new_name

    if "description" in payload:
        note_type.description = (payload.get("description") or "").strip() or None
    if "primary_category" in payload:
        note_type.primary_category = (payload.get("primary_category") or "").strip() or None
    if "tags" in payload:
        note_type.tags = marketplace_query_service.normalize_marketplace_tags(payload.get("tags"))
    if any(key in payload for key in taxonomy_keys):
        taxonomy_metadata, taxonomy_error = marketplace_taxonomy_service.normalize_taxonomy_payload(
            payload,
            content_type="note_type",
        )
        if taxonomy_error:
            return taxonomy_error
        note_type.taxonomy_metadata = taxonomy_metadata
        suggested_category = marketplace_taxonomy_service.suggest_primary_category(taxonomy_metadata)
        if suggested_category:
            note_type.primary_category = suggested_category
    if "preview_text" in payload:
        note_type.preview_text = (payload.get("preview_text") or "").strip() or None
    if "preview_image_url" in payload:
        note_type.preview_image_url = (payload.get("preview_image_url") or "").strip() or None
    if "version" in payload:
        note_type.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        note_type.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_amount_minor, pricing_error = marketplace_query_service.normalize_pricing(
        payload,
        current_mode=str(note_type.pricing_mode or "free"),
        current_price_amount_minor=int(note_type.price_amount_minor or 0),
    )
    if pricing_error:
        return pricing_error
    note_type.pricing_mode = pricing_mode
    note_type.price_amount_minor = price_amount_minor

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
    if deck_item.pricing_mode == "paid" and int(deck_item.price_amount_minor or 0) <= 0:
        return "Paid deck must have a positive price."
    if deck_item.source_deck_id is None:
        return "source_deck_id is required for publish."
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        return "source_note_type_id is required for publish."
    source_note_type = flashcards_share_repository.get_note_type_by_id(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found for publish."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type that has at least one template."
    taxonomy_error = marketplace_taxonomy_service.validate_required_taxonomy(
        deck_item.taxonomy_metadata if isinstance(deck_item.taxonomy_metadata, dict) else {},
        content_type="deck_marketplace_item",
    )
    if taxonomy_error:
        return taxonomy_error
    return None

def apply_deck_marketplace_payload(
    deck_item: DeckMarketplaceItem,
    payload: dict[str, Any],
    *,
    allow_set_official: bool,
    publish_statuses_visible: set[str] | None = None,
) -> str | None:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES
    taxonomy_keys = {
        "taxonomy_domain",
        "domain",
        "taxonomy_subject",
        "subject",
        "taxonomy_difficulty_band",
        "difficulty_band",
        "level_band",
        "taxonomy_framework",
        "framework",
        "taxonomy_framework_level",
        "framework_level",
        "taxonomy_framework_track",
        "framework_track",
        "taxonomy_learning_goals",
        "learning_goals",
        "taxonomy_primary_topics",
        "primary_topics",
        "taxonomy_format_features",
        "format_features",
        "taxonomy_audience",
        "audience",
    }

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
        deck_item.tags = marketplace_query_service.normalize_marketplace_tags(payload.get("tags"))
    if any(key in payload for key in taxonomy_keys):
        taxonomy_metadata, taxonomy_error = marketplace_taxonomy_service.normalize_taxonomy_payload(
            payload,
            content_type="deck_marketplace_item",
        )
        if taxonomy_error:
            return taxonomy_error
        deck_item.taxonomy_metadata = taxonomy_metadata
        suggested_category = marketplace_taxonomy_service.suggest_primary_category(taxonomy_metadata)
        if suggested_category:
            deck_item.primary_category = suggested_category
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

    pricing_mode, price_amount_minor, pricing_error = marketplace_query_service.normalize_pricing(
        payload,
        current_mode=str(deck_item.pricing_mode or "free"),
        current_price_amount_minor=int(deck_item.price_amount_minor or 0),
    )
    if pricing_error:
        return pricing_error
    deck_item.pricing_mode = pricing_mode
    deck_item.price_amount_minor = price_amount_minor

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

def is_note_type_visible_for_shared(
    note_type: NoteType,
    user_id: int | None = None,
    publish_statuses_visible: set[str] | None = None,
) -> bool:
    visible_statuses = publish_statuses_visible or PUBLISH_STATUSES_VISIBLE
    status = str(note_type.publish_status or "").strip().lower()
    if user_id is not None and note_type.user_id == user_id:
        return status != "archived"
    return status in visible_statuses


def is_deck_item_visible_for_shared(
    deck_item: DeckMarketplaceItem,
    user_id: int | None = None,
    publish_statuses_visible: set[str] | None = None,
) -> bool:
    visible_statuses = publish_statuses_visible or PUBLISH_STATUSES_VISIBLE
    status = str(deck_item.publish_status or "").strip().lower()
    if user_id is not None and deck_item.owner_user_id == user_id:
        return status != "archived"
    return status in visible_statuses



def touch_note_type_install_usage(
    *,
    user_id: int,
    installed_note_type_id: str,
    activity_at: datetime | None = None,
) -> None:
    install = flashcards_share_repository.get_note_type_install_by_user_and_source(
        user_id, installed_note_type_id
    )
    if not install:
        return
    now = activity_at or datetime.utcnow()
    if install.first_use_at is None:
        install.first_use_at = now
    install.last_activity_at = now

def note_type_reps_for_user(*, user_id: int, installed_note_type_id: str) -> int:
    return flashcards_share_repository.get_note_type_reps_for_user(user_id, installed_note_type_id)

def is_note_type_install_active(
    install: NoteTypeInstall,
    *,
    now: datetime,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> bool:
    if not install.installed_note_type_id:
        return False
    note_count = flashcards_share_repository.count_notes_by_note_type_for_user(
        install.user_id, install.installed_note_type_id
    )
    review_reps = note_type_reps_for_user(
        user_id=install.user_id,
        installed_note_type_id=install.installed_note_type_id,
    )
    first_use = install.first_use_at
    used_days = bool(
        first_use
        and now - first_use >= timedelta(days=note_type_active_days_threshold)
    )
    return (
        note_count >= note_type_active_note_threshold
        or review_reps >= note_type_active_review_threshold
        or used_days
    )

def recompute_note_type_market_stats(
    note_type: NoteType,
    *,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> None:
    now = datetime.utcnow()
    installs = flashcards_share_repository.get_note_type_installs_by_source(note_type.id)
    note_type.install_count = len(installs)
    note_type.active_usage_count = sum(
        1
        for install in installs
        if is_note_type_install_active(
            install,
            now=now,
            note_type_active_note_threshold=note_type_active_note_threshold,
            note_type_active_review_threshold=note_type_active_review_threshold,
            note_type_active_days_threshold=note_type_active_days_threshold,
        )
    )

    rating_avg, rating_count = flashcards_share_repository.get_note_type_market_rating_stats(note_type.id)
    note_type.rating_avg = rating_avg
    note_type.rating_count = rating_count

def can_user_rate_note_type(
    note_type: NoteType,
    *,
    user_id: int,
    note_type_active_note_threshold: int = 3,
    note_type_active_review_threshold: int = 3,
    note_type_active_days_threshold: int = 3,
) -> bool:
    if note_type.user_id == user_id:
        return False
    install = flashcards_share_repository.get_note_type_install_by_user_and_source(user_id, note_type.id)
    if not install:
        return False
    return is_note_type_install_active(
        install,
        now=datetime.utcnow(),
        note_type_active_note_threshold=note_type_active_note_threshold,
        note_type_active_review_threshold=note_type_active_review_threshold,
        note_type_active_days_threshold=note_type_active_days_threshold,
    )

def touch_deck_install_usage(
    *,
    user_id: int,
    local_deck_id: int,
    activity_at: datetime | None = None,
) -> None:
    installs = deck_installs_covering_deck(user_id=user_id, deck_id=local_deck_id)
    if not installs:
        return
    now = activity_at or datetime.utcnow()
    for install in installs:
        if install.first_use_at is None:
            install.first_use_at = now
        install.last_activity_at = now

def deck_reps_for_user(*, user_id: int, local_deck_id: int) -> int:
    clone_scope = resolve_clone_scope_for_local_deck(
        user_id=user_id,
        local_deck_id=local_deck_id,
    )
    if clone_scope is not None and clone_scope.source_deck_ids:
        return flashcards_share_repository.get_deck_reps_for_user_in_source_scope(
            user_id, 
            clone_scope.source_deck_ids, 
            clone_scope.source_owner_user_id, 
            clone_scope.base_snapshot_at
        )

    subtree_deck_ids = collect_subtree_ids(local_deck_id)
    return flashcards_share_repository.get_deck_reps_for_user_in_subtree(user_id, subtree_deck_ids)

def is_deck_install_active(
    install: DeckInstall,
    *,
    deck_active_review_threshold: int = 3,
) -> bool:
    if not install.local_deck_id:
        return False
    reps = deck_reps_for_user(user_id=install.user_id, local_deck_id=install.local_deck_id)
    return reps >= deck_active_review_threshold

def recompute_deck_item_market_stats(
    deck_item: DeckMarketplaceItem,
    *,
    deck_active_review_threshold: int = 3,
) -> None:
    installs = flashcards_share_repository.get_deck_installs_by_item(deck_item.id)
    deck_item.install_count = len(installs)
    deck_item.active_usage_count = sum(
        1
        for install in installs
        if is_deck_install_active(
            install,
            deck_active_review_threshold=deck_active_review_threshold,
        )
    )

    rating_avg, rating_count = flashcards_share_repository.get_deck_market_rating_stats(deck_item.id)
    deck_item.rating_avg = rating_avg
    deck_item.rating_count = rating_count

def can_user_rate_deck(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    deck_active_review_threshold: int = 3,
) -> bool:
    if deck_item.owner_user_id == user_id:
        return False
    install = flashcards_share_repository.get_deck_install_by_user_and_item(user_id, deck_item.id)
    if not install:
        return False
    return is_deck_install_active(
        install,
        deck_active_review_threshold=deck_active_review_threshold,
    )


def can_user_rate_deck_item(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    deck_active_review_threshold: int = DECK_ACTIVE_REVIEW_THRESHOLD,
) -> bool:
    return can_user_rate_deck(
        deck_item,
        user_id=user_id,
        deck_active_review_threshold=deck_active_review_threshold,
    )

def migrate_legacy_clone_install_to_overlay(
    install: DeckInstall,
) -> dict[str, int]:
    deck_item = DeckMarketplaceItem.query.get(install.deck_item_id)
    source_deck_id = install.source_deck_id or (deck_item.source_deck_id if deck_item else None)
    if source_deck_id is None:
        raise ShareControllerError(
            f"Install {install.id}: source_deck_id is required for cutover.",
            status=409,
        )
    source_deck = Deck.query.get(source_deck_id)
    if source_deck is None:
        raise ShareControllerError(
            f"Install {install.id}: source deck not found ({source_deck_id}).",
            status=404,
        )
    if install.local_deck_id is None:
        raise ShareControllerError(
            f"Install {install.id}: local_deck_id is required for cutover.",
            status=409,
        )
    local_deck = Deck.query.get(install.local_deck_id)
    if local_deck is None:
        raise ShareControllerError(
            f"Install {install.id}: local deck not found ({install.local_deck_id}).",
            status=404,
        )

    source_owner_user_id = install.source_owner_user_id or (deck_item.owner_user_id if deck_item else None)
    source_note_type_id = (
        (install.source_note_type_id or "").strip()
        or ((deck_item.source_note_type_id or "").strip() if deck_item else "")
    )
    snapshot_at = install.base_snapshot_at or install.installed_at

    map_rows = _ensure_clone_map_rows_for_cutover(
        install=install,
        source_root_deck_id=source_deck.id,
        local_root_deck_id=local_deck.id,
    )
    source_to_local = {
        int(row.source_deck_id): int(row.local_deck_id)
        for row in map_rows
        if row.source_deck_id is not None and row.local_deck_id is not None
    }
    if not source_to_local:
        raise ShareControllerError(
            f"Install {install.id}: source/local deck map is empty for cutover.",
            status=409,
        )

    pairs = _pair_legacy_local_source_notes_for_cutover(
        install=install,
        source_to_local_deck_id=source_to_local,
        source_owner_user_id=source_owner_user_id,
        source_note_type_id=source_note_type_id or None,
        snapshot_at=snapshot_at,
    )

    local_note_type_ids = sorted(
        {
            str(local_note.note_type_id).strip()
            for local_note, _source_note in pairs
            if (local_note.note_type_id or "").strip()
        }
    )
    local_note_type_id = local_note_type_ids[0] if len(local_note_type_ids) == 1 else None
    if len(local_note_type_ids) > 1:
        raise ShareControllerError(
            f"Install {install.id}: local legacy clone has multiple note types; cutover is ambiguous.",
            status=409,
        )

    if not source_note_type_id:
        source_note_type_ids = sorted(
            {
                str(source_note.note_type_id).strip()
                for _local_note, source_note in pairs
                if (source_note.note_type_id or "").strip()
            }
        )
        if len(source_note_type_ids) == 1:
            source_note_type_id = source_note_type_ids[0]
        elif len(source_note_type_ids) > 1:
            raise ShareControllerError(
                f"Install {install.id}: source clone scope has multiple note types; source_note_type_id is required.",
                status=409,
            )

    install.clone_mode = "logical_overlay"
    DeckCloneFieldDefOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneAddedFieldDef.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    DeckCloneNoteFieldOverride.query.filter_by(deck_install_id=install.id).delete(synchronize_session=False)
    db.session.flush()

    if source_note_type_id:
        schema_payload = _build_schema_overlay_payload_for_cutover(
            source_note_type_id=source_note_type_id,
            local_note_type_id=local_note_type_id,
        )
        if schema_payload:
            _counters, validation_error = upsert_clone_overlay(
                deck_install=install,
                payload=schema_payload,
            )
            if validation_error:
                raise ShareControllerError(
                    f"Install {install.id}: schema cutover failed: {validation_error}",
                    status=409,
                )
    elif local_note_type_id:
        raise ShareControllerError(
            f"Install {install.id}: source_note_type_id is required for schema cutover.",
            status=409,
        )

    if source_note_type_id:
        schema_view = build_clone_schema_view(
            install=install,
            source_note_type_id=source_note_type_id,
        )
    else:
        schema_view = CloneSchemaView(field_defs=[], removed_field_names=set(), renamed_field_names={})

    note_override_payload: list[dict[str, Any]] = []
    progress_migrated = 0
    local_note_ids: list[str] = []
    template_map_cache: dict[str, dict[str, str]] = {}

    for local_note, source_note in pairs:
        local_note_ids.append(local_note.id)
        note_override_payload.extend(
            _build_note_override_payload_for_cutover(
                install=install,
                source_note=source_note,
                local_note=local_note,
                schema_view=schema_view,
            )
        )

        local_note_type_key = str(local_note.note_type_id or "").strip()
        source_note_type_key = str(source_note.note_type_id or "").strip()
        template_key = f"{local_note_type_key}->{source_note_type_key}"
        template_map = template_map_cache.get(template_key)
        if template_map is None:
            local_templates = (
                Template.query.filter_by(note_type_id=local_note_type_key)
                .order_by(Template.position.asc(), Template.created_at.asc(), Template.id.asc())
                .all()
            )
            source_templates = (
                Template.query.filter_by(note_type_id=source_note_type_key)
                .order_by(Template.position.asc(), Template.created_at.asc(), Template.id.asc())
                .all()
            )
            if len(local_templates) != len(source_templates):
                raise ShareControllerError(
                    (
                        f"Install {install.id}: template count mismatch for note type pair "
                        f"({local_note_type_key} -> {source_note_type_key})."
                    ),
                    status=409,
                )
            template_map = {
                str(local_templates[idx].id): str(source_templates[idx].id)
                for idx in range(len(local_templates))
            }
            template_map_cache[template_key] = template_map

        source_cards_by_template = {
            str(card.template_id): card
            for card in Card.query.filter_by(note_id=source_note.id).all()
        }
        local_cards = Card.query.filter_by(note_id=local_note.id).all()
        for local_card in local_cards:
            source_template_id = template_map.get(str(local_card.template_id))
            if not source_template_id:
                raise ShareControllerError(
                    (
                        f"Install {install.id}: cannot map local template_id={local_card.template_id} "
                        f"for local_note_id={local_note.id}."
                    ),
                    status=409,
                )
            source_card = source_cards_by_template.get(str(source_template_id))
            if source_card is None:
                raise ShareControllerError(
                    (
                        f"Install {install.id}: source card not found for template_id={source_template_id} "
                        f"(source_note_id={source_note.id})."
                    ),
                    status=409,
                )
            progress_migrated += _merge_card_progress_rows_for_cutover(
                user_id=install.user_id,
                local_card_id=local_card.id,
                source_card_id=source_card.id,
            )

    if note_override_payload:
        _counters, validation_error = upsert_clone_overlay(
            deck_install=install,
            payload={"note_field_overrides": note_override_payload},
        )
        if validation_error:
            raise ShareControllerError(
                f"Install {install.id}: note cutover failed: {validation_error}",
                status=409,
            )

    if source_note_type_id:
        schema_view = build_clone_schema_view(
            install=install,
            source_note_type_id=source_note_type_id,
        )
    _assert_cutover_note_equivalence(
        install=install,
        pairs=pairs,
        schema_view=schema_view,
    )

    if local_note_ids:
        Note.query.filter(Note.id.in_(local_note_ids)).delete(synchronize_session=False)

    install.clone_mode = "logical_overlay"
    install.source_deck_id = source_deck.id
    install.source_note_type_id = source_note_type_id or None
    install.source_owner_user_id = source_owner_user_id
    install.base_snapshot_at = snapshot_at

    return {
        "deck_map_rows": len(source_to_local),
        "note_pairs": len(pairs),
        "note_overrides": len(note_override_payload),
        "progress_rows": progress_migrated,
    }


@dataclass
class CloneDeckScope:
    install: DeckInstall
    local_scope_deck_id: int
    local_deck_ids: list[int]
    source_deck_ids: list[int]
    source_to_local_deck_id: dict[int, int]
    source_owner_user_id: int | None
    base_snapshot_at: datetime | None

@dataclass
class CloneSchemaView:
    field_defs: list[SimpleNamespace]
    removed_field_names: set[str]
    renamed_field_names: dict[str, str]

def clone_note_type_for_user(source_note_type: NoteType, user_id: int) -> NoteType:
    clone = NoteType(
        user_id=user_id,
        name=make_unique_note_type_name(user_id, source_note_type.name),
        description=source_note_type.description,
        primary_category=source_note_type.primary_category,
        tags=list(source_note_type.tags or []),
        preview_text=source_note_type.preview_text,
        preview_image_url=source_note_type.preview_image_url,
        pricing_mode="free",
        price_amount_minor=0,
        version=source_note_type.version or "1.0.0",
        changelog=source_note_type.changelog,
        publish_status="private",
        is_official=False,
        install_count=0,
        active_usage_count=0,
        rating_avg=0.0,
        rating_count=0,
    )
    db.session.add(clone)
    db.session.flush()

    for field_def in sorted(source_note_type.field_defs, key=lambda item: item.position):
        db.session.add(
            FieldDef(
                note_type_id=clone.id,
                name=field_def.name,
                field_type=field_def.field_type,
                position=field_def.position,
                required=bool(field_def.required),
            )
        )

    for template in sorted(source_note_type.templates, key=lambda item: item.position):
        db.session.add(
            Template(
                note_type_id=clone.id,
                name=template.name,
                front_html=template.front_html,
                back_html=template.back_html,
                shared_css=template.shared_css,
                position=template.position,
                is_default=bool(template.is_default),
            )
        )

    return clone


def ensure_note_type_install_for_user(
    *,
    source_note_type: NoteType,
    user_id: int,
    installed_at: datetime | None = None,
) -> NoteTypeInstall:
    install_row = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=user_id,
    ).first()
    if install_row and (install_row.installed_note_type_id or "").strip():
        installed_copy = NoteType.query.get(install_row.installed_note_type_id)
        if installed_copy:
            return install_row

    installed_copy = flashcards_share.clone_note_type_for_user(source_note_type, user_id)
    now = installed_at or datetime.utcnow()
    purchase_amount_minor = int(source_note_type.price_amount_minor or 0) if source_note_type.pricing_mode == "paid" else 0

    if install_row is None:
        install_row = NoteTypeInstall(
            source_note_type_id=source_note_type.id,
            installed_note_type_id=installed_copy.id,
            user_id=user_id,
            purchase_amount_minor=purchase_amount_minor,
            installed_at=now,
            purchased_at=now if source_note_type.pricing_mode == "paid" else None,
        )
        db.session.add(install_row)
    else:
        install_row.installed_note_type_id = installed_copy.id
        install_row.purchase_amount_minor = purchase_amount_minor
        if install_row.installed_at is None:
            install_row.installed_at = now
        install_row.purchased_at = now if source_note_type.pricing_mode == "paid" else None

    flashcards_share.recompute_note_type_market_stats(source_note_type)
    return install_row


def clone_deck_subtree(
    *,
    source_deck_id: int,
    parent_id: int | None,
    deck_install_id: str | None = None,
    owner_user_id: int | None = None,
    note_type_id_map: dict[str, str] | None = None,
) -> Deck:
    source_deck = Deck.query.get(source_deck_id)
    if not source_deck:
        raise ValueError(f"Deck not found: {source_deck_id}")

    source_note_type_id = (source_deck.note_type_id or "").strip()
    mapped_note_type_id = (
        note_type_id_map.get(source_note_type_id)
        if note_type_id_map and source_note_type_id
        else None
    )

    cloned_deck = Deck(
        parent_id=parent_id,
        owner_user_id=owner_user_id,
        note_type_id=mapped_note_type_id or source_deck.note_type_id,
        name=source_deck.name,
        description=source_deck.description,
        position=_next_deck_position(parent_id),
    )
    db.session.add(cloned_deck)
    db.session.flush()

    if deck_install_id:
        db.session.add(
            DeckCloneDeckMap(
                deck_install_id=deck_install_id,
                local_deck_id=cloned_deck.id,
                source_deck_id=source_deck.id,
            )
        )

    child_decks = (
        Deck.query.filter_by(parent_id=source_deck.id)
        .order_by(Deck.position.asc(), Deck.id.asc())
        .all()
    )
    for child in child_decks:
        clone_deck_subtree(
            source_deck_id=child.id,
            parent_id=cloned_deck.id,
            deck_install_id=deck_install_id,
            owner_user_id=owner_user_id,
            note_type_id_map=note_type_id_map,
        )

    return cloned_deck

def _install_snapshot_at(install: DeckInstall) -> datetime | None:
    return install.base_snapshot_at or install.installed_at

def resolve_clone_scope_for_local_deck(
    *,
    user_id: int,
    local_deck_id: int,
) -> CloneDeckScope | None:
    installs = deck_installs_covering_deck(user_id=user_id, deck_id=local_deck_id)
    install = next(
        (
            row
            for row in installs
            if row.clone_mode == "logical_overlay"
            and row.source_deck_id is not None
            and row.local_deck_id is not None
        ),
        None,
    )
    if not install:
        return None

    local_scope_ids = collect_subtree_ids(local_deck_id)
    if not local_scope_ids:
        return None

    map_rows = flashcards_share_repository.get_clone_deck_maps(install.id, local_scope_ids)
    if not map_rows:
        if install.local_deck_id != local_deck_id or install.source_deck_id is None:
            return None
        source_deck_ids = collect_subtree_ids(install.source_deck_id)
        source_to_local = {int(deck_id): local_deck_id for deck_id in source_deck_ids}
        return CloneDeckScope(
            install=install,
            local_scope_deck_id=local_deck_id,
            local_deck_ids=local_scope_ids,
            source_deck_ids=source_deck_ids,
            source_to_local_deck_id=source_to_local,
            source_owner_user_id=install.source_owner_user_id,
            base_snapshot_at=_install_snapshot_at(install),
        )

    source_deck_ids = sorted({int(row.source_deck_id) for row in map_rows if row.source_deck_id is not None})
    source_to_local = {
        int(row.source_deck_id): int(row.local_deck_id)
        for row in map_rows
        if row.source_deck_id is not None and row.local_deck_id is not None
    }
    return CloneDeckScope(
        install=install,
        local_scope_deck_id=local_deck_id,
        local_deck_ids=local_scope_ids,
        source_deck_ids=source_deck_ids,
        source_to_local_deck_id=source_to_local,
        source_owner_user_id=install.source_owner_user_id,
        base_snapshot_at=_install_snapshot_at(install),
    )

def query_clone_scope_cards(scope: CloneDeckScope):
    return flashcards_share_repository.get_clone_scope_cards(
        scope.source_deck_ids, 
        scope.source_owner_user_id, 
        scope.base_snapshot_at
    )

def resolve_clone_scope_for_card(
    *,
    user_id: int,
    card_obj: Card | None,
) -> CloneDeckScope | None:
    if card_obj is None or card_obj.note is None or card_obj.note.deck_id is None:
        return None

    source_deck_id = int(card_obj.note.deck_id)
    rows = flashcards_share_repository.find_logical_overlay_installs_for_card(user_id, source_deck_id)
    for install, local_deck_id in rows:
        if install.source_owner_user_id is not None and card_obj.note.user_id != install.source_owner_user_id:
            continue
        snapshot_at = _install_snapshot_at(install)
        if snapshot_at is not None:
            note_created = card_obj.note.created_at or datetime.min
            card_created = card_obj.created_at or datetime.min
            if note_created > snapshot_at or card_created > snapshot_at:
                continue
        if local_deck_id is None:
            continue
        scope = resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=int(local_deck_id))
        if scope is not None:
            return scope
    return None

def resolve_local_clone_deck_id_for_source_deck(
    *,
    install_id: str,
    source_deck_id: int | None,
) -> int | None:
    if source_deck_id is None:
        return None
    row = flashcards_share_repository.get_clone_deck_map(install_id, source_deck_id)
    if not row or row.local_deck_id is None:
        return None
    return int(row.local_deck_id)

def build_clone_schema_view(
    *,
    install: DeckInstall,
    source_note_type_id: str,
) -> CloneSchemaView:
    snapshot_at = _install_snapshot_at(install)
    source_defs = flashcards_share_repository.get_field_defs_for_note_type(source_note_type_id, snapshot_at)

    override_rows = flashcards_share_repository.get_clone_field_overrides(install.id)
    override_by_source_id = {
        row.source_field_def_id: row
        for row in override_rows
        if row.source_field_def_id
    }
    removed_field_names: set[str] = set()
    renamed_field_names: dict[str, str] = {}
    resolved_defs: list[SimpleNamespace] = []

    for source_def in source_defs:
        override = override_by_source_id.get(source_def.id)
        if override and bool(override.is_disabled):
            removed_field_names.add(source_def.name)
            continue

        properties = override.properties if override and isinstance(override.properties, dict) else {}
        resolved_name = str(properties.get("name") or source_def.name).strip() or source_def.name
        if resolved_name != source_def.name:
            renamed_field_names[source_def.name] = resolved_name
        resolved_field_type = str(properties.get("field_type") or source_def.field_type or "text").strip().lower()
        if resolved_field_type not in FIELD_TYPES:
            resolved_field_type = str(source_def.field_type or "text")
        raw_position = properties.get("position")
        try:
            resolved_position = int(raw_position) if raw_position is not None else int(source_def.position or 0)
        except (TypeError, ValueError):
            resolved_position = int(source_def.position or 0)
        if "required" in properties:
            resolved_required = bool(properties.get("required"))
        else:
            resolved_required = bool(source_def.required)
        resolved_defs.append(
            SimpleNamespace(
                id=source_def.id,
                name=resolved_name,
                field_type=resolved_field_type,
                position=resolved_position,
                required=resolved_required,
            )
        )

    added_rows = flashcards_share_repository.get_clone_added_field_defs(install.id)
    for row in added_rows:
        properties = row.properties if isinstance(row.properties, dict) else {}
        resolved_name = str(properties.get("name") or row.name).strip() or row.name
        resolved_field_type = str(properties.get("field_type") or row.field_type or "text").strip().lower()
        if resolved_field_type not in FIELD_TYPES:
            resolved_field_type = str(row.field_type or "text")
        raw_position = properties.get("position")
        try:
            resolved_position = int(raw_position) if raw_position is not None else int(row.position or 0)
        except (TypeError, ValueError):
            resolved_position = int(row.position or 0)
        if "required" in properties:
            resolved_required = bool(properties.get("required"))
        else:
            resolved_required = bool(row.required)
        resolved_defs.append(
            SimpleNamespace(
                id=row.id,
                name=resolved_name,
                field_type=resolved_field_type,
                position=resolved_position,
                required=resolved_required,
            )
        )

    order_override = flashcards_share_repository.get_clone_field_order_override(install.id)
    ordered_def_ids = order_override.ordered_def_ids if order_override else []
    if isinstance(ordered_def_ids, list) and ordered_def_ids:
        order_index = {
            str(def_id): index
            for index, def_id in enumerate(ordered_def_ids)
            if isinstance(def_id, str) and def_id.strip()
        }
        resolved_defs.sort(
            key=lambda item: (
                order_index.get(str(item.id), 10_000_000),
                int(item.position or 0),
                str(item.name or "").lower(),
                str(item.id),
            )
        )
        for index, item in enumerate(resolved_defs):
            item.position = index
    else:
        resolved_defs.sort(
            key=lambda item: (
                int(item.position or 0),
                str(item.name or "").lower(),
                str(item.id),
            )
        )

    return CloneSchemaView(
        field_defs=resolved_defs,
        removed_field_names=removed_field_names,
        renamed_field_names=renamed_field_names,
    )

def apply_clone_note_field_overrides(
    *,
    install: DeckInstall,
    source_note: Note,
    schema_view: CloneSchemaView,
) -> dict[str, Any]:
    values = dict(source_note.field_values or {})

    for removed_name in schema_view.removed_field_names:
        values.pop(removed_name, None)

    for old_name, new_name in schema_view.renamed_field_names.items():
        if old_name == new_name:
            continue
        if old_name not in values:
            continue
        if new_name not in values:
            values[new_name] = values.get(old_name)
        values.pop(old_name, None)

    note_override_rows = flashcards_share_repository.get_clone_note_field_overrides(install.id, source_note.id)
    for row in note_override_rows:
        if row.operation == "remove":
            values.pop(row.field_name, None)
        else:
            values[row.field_name] = row.value

    for removed_name in schema_view.removed_field_names:
        values.pop(removed_name, None)

    return values

def get_user_deck_install_for_item(
    *,
    user_id: int,
    deck_item_id: str,
) -> DeckInstall | None:
    return (
        DeckInstall.query.filter_by(
            user_id=user_id,
            deck_item_id=deck_item_id,
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .first()
    )

def upsert_clone_overlay(
    *,
    deck_install: DeckInstall,
    payload: dict[str, Any],
) -> tuple[dict[str, int], str | None]:
    if deck_install.clone_mode != "logical_overlay":
        return {}, "This install does not support overlay edits."

    counters = {
        "updated_defs": 0,
        "disabled_defs": 0,
        "added_defs": 0,
        "updated_note_fields": 0,
        "removed_note_fields": 0,
    }

    source_note_type_id = (deck_install.source_note_type_id or "").strip()
    source_field_ids: set[str] = set()
    if source_note_type_id:
        source_field_rows = FieldDef.query.with_entities(FieldDef.id).filter(
            FieldDef.note_type_id == source_note_type_id
        )
        snapshot_at = _install_snapshot_at(deck_install)
        if snapshot_at is not None:
            source_field_rows = source_field_rows.filter(FieldDef.created_at <= snapshot_at)
        source_field_ids = {
            str(row[0])
            for row in source_field_rows.all()
            if row and row[0]
        }

    updated_defs_payload = payload.get("updated_defs")
    if updated_defs_payload is not None:
        if not isinstance(updated_defs_payload, list):
            return {}, "updated_defs must be a list."
        for item in updated_defs_payload:
            if not isinstance(item, dict):
                return {}, "Each updated_defs item must be an object."
            source_field_def_id = str(item.get("source_field_def_id") or "").strip()
            if not source_field_def_id:
                return {}, "source_field_def_id is required for updated_defs."
            if source_field_ids and source_field_def_id not in source_field_ids:
                return {}, "updated_defs references field outside pinned snapshot."

            override = DeckCloneFieldDefOverride.query.filter_by(
                deck_install_id=deck_install.id,
                source_field_def_id=source_field_def_id,
            ).first()
            if override is None:
                override = DeckCloneFieldDefOverride(
                    deck_install_id=deck_install.id,
                    source_field_def_id=source_field_def_id,
                    is_disabled=False,
                    properties={},
                )
                db.session.add(override)

            raw_properties = item.get("properties")
            next_properties = dict(override.properties or {})
            if isinstance(raw_properties, dict):
                for key in {"name", "field_type", "position", "required"}:
                    if key not in raw_properties:
                        continue
                    next_properties[key] = raw_properties.get(key)
            for key in {"name", "field_type", "position", "required"}:
                if key in item:
                    next_properties[key] = item.get(key)
            if next_properties:
                override.properties = next_properties
                counters["updated_defs"] += 1

            if "disabled" in item:
                override.is_disabled = bool(item.get("disabled"))
                if override.is_disabled:
                    counters["disabled_defs"] += 1

    disabled_def_ids_payload = payload.get("disabled_def_ids")
    if disabled_def_ids_payload is not None:
        if not isinstance(disabled_def_ids_payload, list):
            return {}, "disabled_def_ids must be a list."
        for raw_id in disabled_def_ids_payload:
            source_field_def_id = str(raw_id or "").strip()
            if not source_field_def_id:
                continue
            if source_field_ids and source_field_def_id not in source_field_ids:
                return {}, "disabled_def_ids references field outside pinned snapshot."
            override = DeckCloneFieldDefOverride.query.filter_by(
                deck_install_id=deck_install.id,
                source_field_def_id=source_field_def_id,
            ).first()
            if override is None:
                override = DeckCloneFieldDefOverride(
                    deck_install_id=deck_install.id,
                    source_field_def_id=source_field_def_id,
                    is_disabled=True,
                    properties={},
                )
                db.session.add(override)
            else:
                override.is_disabled = True
            counters["disabled_defs"] += 1

    added_defs_payload = payload.get("added_defs")
    if added_defs_payload is not None:
        if not isinstance(added_defs_payload, list):
            return {}, "added_defs must be a list."
        for item in added_defs_payload:
            if not isinstance(item, dict):
                return {}, "Each added_defs item must be an object."
            name = str(item.get("name") or "").strip()
            if not name:
                return {}, "added_defs.name is required."
            field_type = str(item.get("field_type") or "text").strip().lower()
            if field_type not in FIELD_TYPES:
                return {}, "added_defs.field_type is invalid."
            try:
                position = int(item.get("position") if item.get("position") is not None else 0)
            except (TypeError, ValueError):
                return {}, "added_defs.position must be an integer."
            row = DeckCloneAddedFieldDef(
                deck_install_id=deck_install.id,
                name=name,
                field_type=field_type,
                position=position,
                required=bool(item.get("required")),
                properties=item.get("properties") if isinstance(item.get("properties"), dict) else {},
            )
            db.session.add(row)
            counters["added_defs"] += 1

    removed_added_def_ids = payload.get("removed_added_def_ids")
    if removed_added_def_ids is not None:
        if not isinstance(removed_added_def_ids, list):
            return {}, "removed_added_def_ids must be a list."
        for raw_id in removed_added_def_ids:
            added_def_id = str(raw_id or "").strip()
            if not added_def_id:
                continue
            row = DeckCloneAddedFieldDef.query.filter_by(
                deck_install_id=deck_install.id,
                id=added_def_id,
            ).first()
            if row is not None:
                db.session.delete(row)

    clear_order_override = bool(payload.get("clear_order_override"))
    if clear_order_override:
        existing_order_override = DeckCloneFieldOrderOverride.query.filter_by(
            deck_install_id=deck_install.id
        ).first()
        if existing_order_override:
            db.session.delete(existing_order_override)

    order_override_payload = payload.get("ordered_def_ids")
    if order_override_payload is not None:
        if not isinstance(order_override_payload, list):
            return {}, "ordered_def_ids must be a list."
        order_row = DeckCloneFieldOrderOverride.query.filter_by(deck_install_id=deck_install.id).first()
        if order_row is None:
            order_row = DeckCloneFieldOrderOverride(
                deck_install_id=deck_install.id,
                ordered_def_ids=[],
            )
            db.session.add(order_row)
        order_row.ordered_def_ids = [
            str(item).strip()
            for item in order_override_payload
            if str(item).strip()
        ]

    note_field_overrides_payload = payload.get("note_field_overrides")
    if note_field_overrides_payload is not None:
        if not isinstance(note_field_overrides_payload, list):
            return {}, "note_field_overrides must be a list."
        snapshot_at = _install_snapshot_at(deck_install)
        for item in note_field_overrides_payload:
            if not isinstance(item, dict):
                return {}, "Each note_field_overrides item must be an object."
            source_note_id = str(item.get("source_note_id") or "").strip()
            field_name = str(item.get("field_name") or "").strip()
            if not source_note_id or not field_name:
                return {}, "note_field_overrides requires source_note_id and field_name."
            source_note = Note.query.get(source_note_id)
            if not source_note:
                return {}, "note_field_overrides references missing source note."
            if deck_install.source_owner_user_id is not None and source_note.user_id != deck_install.source_owner_user_id:
                return {}, "note_field_overrides references source note outside owner scope."
            if source_note.deck_id is None:
                return {}, "note_field_overrides source note has no deck."
            source_map_exists = DeckCloneDeckMap.query.filter_by(
                deck_install_id=deck_install.id,
                source_deck_id=source_note.deck_id,
            ).first()
            if source_map_exists is None:
                return {}, "note_field_overrides source note is outside clone scope."
            if snapshot_at is not None and (source_note.created_at or datetime.min) > snapshot_at:
                return {}, "note_field_overrides source note is newer than snapshot."

            operation = str(item.get("operation") or "set").strip().lower()
            if operation not in {"set", "remove"}:
                return {}, "note_field_overrides.operation must be set/remove."
            override = DeckCloneNoteFieldOverride.query.filter_by(
                deck_install_id=deck_install.id,
                source_note_id=source_note_id,
                field_name=field_name,
            ).first()
            if override is None:
                override = DeckCloneNoteFieldOverride(
                    deck_install_id=deck_install.id,
                    source_note_id=source_note_id,
                    field_name=field_name,
                )
                db.session.add(override)
            override.operation = operation
            if operation == "remove":
                override.value = None
                counters["removed_note_fields"] += 1
            else:
                override.value = item.get("value")
                counters["updated_note_fields"] += 1

    return counters, None

def deck_installs_covering_deck(*, user_id: int, deck_id: int) -> list[DeckInstall]:
    ancestors = collect_ancestor_ids(deck_id)
    if not ancestors:
        ancestors = []
    return flashcards_share_repository.get_user_deck_installs_covering_deck(user_id, ancestors + [deck_id])

def _ensure_clone_map_rows_for_cutover(
    *,
    install: DeckInstall,
    source_root_deck_id: int,
    local_root_deck_id: int,
) -> list[DeckCloneDeckMap]:
    existing_rows = flashcards_share_repository.get_clone_deck_maps(install.id)
    if existing_rows:
        return existing_rows
    local_deck_ids = collect_subtree_ids(local_root_deck_id)
    if not local_deck_ids:
        return []

    local_decks = Deck.query.filter(Deck.id.in_(local_deck_ids)).all()
    local_decks_by_parent: dict[int | None, list[Deck]] = {}
    for local_deck in local_decks:
        local_decks_by_parent.setdefault(local_deck.parent_id, []).append(local_deck)
    for rows in local_decks_by_parent.values():
        rows.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    source_deck_ids = collect_subtree_ids(source_root_deck_id)
    if not source_deck_ids:
        return []
    source_decks = Deck.query.filter(Deck.id.in_(source_deck_ids)).all()
    source_decks_by_parent: dict[int | None, list[Deck]] = {}
    for source_deck in source_decks:
        source_decks_by_parent.setdefault(source_deck.parent_id, []).append(source_deck)
    for rows in source_decks_by_parent.values():
        rows.sort(key=lambda item: ((item.position or 0), item.created_at, item.id))

    local_to_source: dict[int, int] = {local_root_deck_id: source_root_deck_id}

    def _walk_and_pair(local_pid: int, source_pid: int) -> None:
        local_children = local_decks_by_parent.get(local_pid, [])
        source_children = source_decks_by_parent.get(source_pid, [])
        for idx in range(min(len(local_children), len(source_children))):
            local_child_id = local_children[idx].id
            source_child_id = source_children[idx].id
            local_to_source[local_child_id] = source_child_id
            _walk_and_pair(local_child_id, source_child_id)

    _walk_and_pair(local_root_deck_id, source_root_deck_id)

    created_rows: list[DeckCloneDeckMap] = []
    for local_deck_id, source_deck_id in local_to_source.items():
        row = DeckCloneDeckMap(
            deck_install_id=install.id,
            source_deck_id=source_deck_id,
            local_deck_id=local_deck_id,
        )
        db.session.add(row)
        created_rows.append(row)
    db.session.flush()
    return created_rows

def _build_schema_overlay_payload_for_cutover(
    *,
    source_note_type_id: str,
    local_note_type_id: str | None,
) -> dict[str, Any]:
    if not source_note_type_id or not local_note_type_id or local_note_type_id == source_note_type_id:
        return {}

    source_defs = (
        FieldDef.query.filter_by(note_type_id=source_note_type_id)
        .order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc())
        .all()
    )
    local_defs = (
        FieldDef.query.filter_by(note_type_id=local_note_type_id)
        .order_by(FieldDef.position.asc(), FieldDef.created_at.asc(), FieldDef.id.asc())
        .all()
    )
    if not source_defs and not local_defs:
        return {}

    updated_defs: list[dict[str, Any]] = []
    disabled_def_ids: list[str] = []
    added_defs: list[dict[str, Any]] = []

    pair_count = min(len(source_defs), len(local_defs))
    for idx in range(pair_count):
        source_def = source_defs[idx]
        local_def = local_defs[idx]
        properties: dict[str, Any] = {}
        if (local_def.name or "") != (source_def.name or ""):
            properties["name"] = local_def.name
        if (local_def.field_type or "") != (source_def.field_type or ""):
            properties["field_type"] = local_def.field_type
        if bool(local_def.required) != bool(source_def.required):
            properties["required"] = bool(local_def.required)
        if int(local_def.position or 0) != int(source_def.position or 0):
            properties["position"] = int(local_def.position or 0)
        if properties:
            updated_defs.append(
                {
                    "source_field_def_id": source_def.id,
                    "properties": properties,
                }
            )

    if len(source_defs) > pair_count:
        disabled_def_ids.extend(source_def.id for source_def in source_defs[pair_count:])
    if len(local_defs) > pair_count:
        for local_def in local_defs[pair_count:]:
            added_defs.append(
                {
                    "name": local_def.name,
                    "field_type": local_def.field_type,
                    "position": int(local_def.position or 0),
                    "required": bool(local_def.required),
                }
            )

    payload: dict[str, Any] = {}
    if updated_defs:
        payload["updated_defs"] = updated_defs
    if disabled_def_ids:
        payload["disabled_def_ids"] = disabled_def_ids
    if added_defs:
        payload["added_defs"] = added_defs
    return payload

def _build_note_override_payload_for_cutover(
    *,
    install: DeckInstall,
    source_note: Note,
    local_note: Note,
    schema_view: CloneSchemaView,
) -> list[dict[str, Any]]:
    base_values = _normalize_note_field_values_for_cutover(
        apply_clone_note_field_overrides(
            install=install,
            source_note=source_note,
            schema_view=schema_view,
        )
    )
    local_values = _normalize_note_field_values_for_cutover(local_note.field_values)
    override_items: list[dict[str, Any]] = []

    all_keys = sorted(set(base_values.keys()) | set(local_values.keys()))
    for field_name in all_keys:
        has_base = field_name in base_values
        has_local = field_name in local_values
        if has_base and has_local and base_values[field_name] == local_values[field_name]:
            continue
        if has_local:
            override_items.append(
                {
                    "source_note_id": source_note.id,
                    "field_name": field_name,
                    "operation": "set",
                    "value": local_values[field_name],
                }
            )
            continue
        if has_base and not has_local:
            override_items.append(
                {
                    "source_note_id": source_note.id,
                    "field_name": field_name,
                    "operation": "remove",
                }
            )
    return override_items

def cutover_clone_model_to_overlay_only(*, fail_on_mismatch: bool = True) -> dict[str, Any]:
    legacy_installs = (
        DeckInstall.query.filter(
            db.or_(
                DeckInstall.clone_mode.is_(None),
                DeckInstall.clone_mode != "logical_overlay",
            )
        )
        .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
        .all()
    )
    summary = {
        "total_installs": len(legacy_installs),
        "migrated": 0,
        "failed": 0,
        "deck_map_rows": 0,
        "note_pairs": 0,
        "note_overrides": 0,
        "progress_rows": 0,
        "errors": [],
    }

    for install in legacy_installs:
        try:
            counters = migrate_legacy_clone_install_to_overlay(install)
            summary["migrated"] += 1
            summary["deck_map_rows"] += int(counters.get("deck_map_rows") or 0)
            summary["note_pairs"] += int(counters.get("note_pairs") or 0)
            summary["note_overrides"] += int(counters.get("note_overrides") or 0)
            summary["progress_rows"] += int(counters.get("progress_rows") or 0)
        except ShareControllerError as exc:
            db.session.rollback()
            summary["failed"] += 1
            summary["errors"].append(
                {
                    "deck_install_id": install.id,
                    "message": exc.message,
                    "status": exc.status,
                }
            )
            if fail_on_mismatch:
                raise

    return summary

def install_shared_deck_item_for_user(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> dict[str, Any]:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in visible_statuses:
        raise ShareControllerError(
            "This deck is not available for install.",
            status=409,
        )
    if deck_item.owner_user_id == user_id:
        raise ShareControllerError(
            "Owner cannot install own deck item.",
            status=409,
        )

    existing = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if existing:
        return {
            "created": False,
            "response": {
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
                "already_installed": True,
            },
        }

    now = datetime.utcnow()
    source_deck_id = deck_item.source_deck_id
    if source_deck_id is None:
        raise ShareControllerError(
            "source_deck_id is required for install.",
            status=409,
            field="source_deck_id",
        )
    source_deck = Deck.query.get(source_deck_id)
    if source_deck is None:
        raise ShareControllerError(
            "Source deck not found.",
            status=404,
            error="FIELD_NOT_FOUND",
        )

    note_type_id_map: dict[str, str] = {}
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if source_note_type_id:
        source_note_type = NoteType.query.get(source_note_type_id)
        if source_note_type is None:
            raise ShareControllerError(
                "source_note_type_id not found.",
                status=409,
                field="source_note_type_id",
            )
        note_type_install = ensure_note_type_install_for_user(
            source_note_type=source_note_type,
            user_id=user_id,
            installed_at=now,
        )
        installed_note_type_id = (note_type_install.installed_note_type_id or "").strip()
        if installed_note_type_id:
            note_type_id_map[source_note_type_id] = installed_note_type_id

    purchase_amount_minor = int(deck_item.price_amount_minor or 0) if deck_item.pricing_mode == "paid" else 0
    install = DeckInstall(
        deck_item_id=deck_item.id,
        user_id=user_id,
        local_deck_id=None,
        clone_mode="logical_overlay",
        source_deck_id=source_deck.id,
        source_note_type_id=(deck_item.source_note_type_id or "").strip() or None,
        source_owner_user_id=deck_item.owner_user_id,
        base_snapshot_at=now,
        purchase_amount_minor=purchase_amount_minor,
        installed_at=now,
        purchased_at=now if deck_item.pricing_mode == "paid" else None,
    )
    db.session.add(install)
    db.session.flush()

    local_deck_id = None
    cloned_root = clone_deck_subtree(
        source_deck_id=source_deck.id,
        parent_id=None,
        deck_install_id=install.id,
        owner_user_id=user_id,
        note_type_id_map=note_type_id_map,
    )
    if cloned_root.note_type_id is None and note_type_id_map:
        cloned_root.note_type_id = next(iter(note_type_id_map.values()))
    local_deck_id = cloned_root.id
    install.local_deck_id = local_deck_id

    recompute_deck_item_market_stats(deck_item)
    return {
        "created": True,
        "response": {
            "deck_item_id": deck_item.id,
            "installed_deck_id": local_deck_id,
            "purchase_amount_minor": purchase_amount_minor,
            "purchase_price_cents": purchase_amount_minor,
        },
        "audit": {
            "deck_item_id": deck_item.id,
            "local_deck_id": local_deck_id,
            "price_amount_minor": purchase_amount_minor,
            "price_cents": purchase_amount_minor,
        },
    }
