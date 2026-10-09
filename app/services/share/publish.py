"""Deck marketplace publishing, eligibility verification, and payload management."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

from app.repositories import (
    deck_change_request_repository,
    deck_release_repository,
    flashcards_share_repository,
    marketplace_taxonomy_repository,
    study_repository,
    vocabulary_repository,
)
from app.repositories.deck_tree_query import (
    collect_ancestor_ids,
    collect_subtree_ids,
)
from app.services import (
    deck_release_service,
    deck_working_tree_service,
    marketplace_query_service,
    marketplace_taxonomy_service,
    note_sync_service,
    study_service,
)
from app.services.deck_publish_index import DeckPublishSummary, build_deck_publish_index
from app.services.share.constants import (
    DECK_ACTIVE_REVIEW_THRESHOLD,
    DEFAULT_VISIBLE_PUBLISH_STATUSES,
    FIELD_TYPES,
    MARKET_ACTIVITY_POLICY_VERSION,
    NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
    NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
    PUBLISH_STATUSES_VISIBLE,
    SHARED_DECK_INSTALL_DEADLOCK_MESSAGE,
    SHARED_DECK_INSTALL_MAX_RETRIES,
    UTC,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_change_request import DeckChangeRequest
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_review import DeckReview
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.taxonomy import (
    TaxonomyDomain,
    TaxonomyFramework,
    TaxonomyFrameworkLevel,
    TaxonomySubject,
)
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)


from app.services.share.helpers import (
    ShareControllerError,
    _audit,
    _stage_initial_release_if_visible,
    _utcnow,
    can_user_rate_deck,
    can_user_rate_deck_item,
    ensure_visible_deck_item_initial_release,
    is_deck_item_visible_for_shared,
    recompute_deck_item_market_stats,
    resolve_single_note_type_for_deck,
    sync_deck_item_source_note_type_and_commit,
    validate_deck_source_note_type_provenance,
    validate_marketplace_note_type_for_deck,
)
from app.services.share.note_types import (
    get_note_type_publish_eligibility,
    is_installed_note_type_copy,
)
from app.services.share.install import _installed_local_deck_ids



def _deck_publish_context(*, user_id: int) -> tuple[dict[int, Deck], set[int], dict[int, DeckMarketplaceItem]]:
    owned_decks = (
        Deck.query.filter(
            Deck.owner_user_id == user_id,
            Deck.deleted_at.is_(None),
        )
        .order_by(
            Deck.parent_id.isnot(None),
            Deck.position.asc(),
            Deck.created_at.asc(),
            Deck.id.asc(),
        )
        .all()
    )
    deck_by_id = {int(deck.id): deck for deck in owned_decks}
    deck_ids = list(deck_by_id)
    shared_by_source = {
        int(item.source_deck_id): item
        for item in (
            DeckMarketplaceItem.query.filter(
                DeckMarketplaceItem.source_deck_id.in_(deck_ids)
            ).all()
            if deck_ids
            else []
        )
        if item.source_deck_id is not None
    }
    return deck_by_id, _installed_local_deck_ids(user_id=user_id), shared_by_source



@dataclass(frozen=True)
class DeckPublishBatchContext:
    """Bounded summaries, with the original fields retained for old callers."""
    subtree_ids_by_deck: dict[int, set[int]]       # Compatibility input; options leave this empty.
    deck_to_note_types: dict[int, set[str]]        # Map deck_id -> set of note_type IDs
    marketplace_installed_nt_ids: set[str]        # Set of note_type IDs installed from Marketplace
    active_template_nt_ids: set[str]               # Set of note_type IDs with ACTIVE templates
    summaries_by_deck: dict[int, DeckPublishSummary] | None = None


def get_deck_publish_eligibility(
    *,
    user_id: int,
    deck: Deck,
    allow_existing: bool = False,
    context: tuple[dict[int, Deck], set[int], dict[int, DeckMarketplaceItem]] | None = None,
    batch_context: DeckPublishBatchContext | None = None,
) -> dict[str, Any]:
    if deck.deleted_at is not None or deck.owner_user_id != user_id:
        return {
            "is_selectable": False,
            "block_code": "not_owned",
            "block_reason": "Chỉ có thể chia sẻ bộ thẻ do bạn tự tạo hoặc đồng bộ từ Anki.",
            "shared_item_id": None,
        }

    deck_by_id, installed_scope_ids, shared_by_source = context or _deck_publish_context(
        user_id=user_id
    )
    deck_id = int(deck.id)

    if deck_id in installed_scope_ids:
        return {
            "is_selectable": False,
            "block_code": "marketplace_clone",
            "block_reason": "Bộ thẻ được cài từ Marketplace không thể chia sẻ lại.",
            "shared_item_id": None,
        }

    # =========================================================================
    # NHÁNH 1: BATCH IN-MEMORY RESOLUTION (O(1) RAM - không sinh SQL)
    # =========================================================================
    summary = None
    if batch_context is not None:
        summaries = getattr(batch_context, "summaries_by_deck", None)
        summary = summaries.get(deck_id) if summaries is not None else None
        inferred_note_type_id = None
        if summary is not None:
            candidate_nt_id = summary.note_type_id
            if not summary.mixed_note_types and candidate_nt_id in batch_context.active_template_nt_ids:
                inferred_note_type_id = candidate_nt_id
            descendant_ids = (
                {summary.smallest_shared_descendant}
                if summary.smallest_shared_descendant is not None else set()
            )
        else:
            # Preserve callers that still construct the original batch context.
            sub_ids = batch_context.subtree_ids_by_deck.get(deck_id, {deck_id})
            subtree_nt_ids = {
                nt for sid in sub_ids for nt in batch_context.deck_to_note_types.get(sid, set())
            }
            if len(subtree_nt_ids) == 1:
                candidate_nt_id = next(iter(subtree_nt_ids))
                if candidate_nt_id in batch_context.active_template_nt_ids:
                    inferred_note_type_id = candidate_nt_id
            descendant_ids = sub_ids - {deck_id}

        if inferred_note_type_id and (inferred_note_type_id in batch_context.marketplace_installed_nt_ids):
            return {
                "is_selectable": False,
                "block_code": "marketplace_note_type",
                "block_reason": "Bộ thẻ dùng Note Type cài từ Marketplace nên không thể chia sẻ lại.",
                "shared_item_id": None,
            }

    # =========================================================================
    # NHÁNH 2: STANDALONE FALLBACK RESOLUTION (Bảo toàn 100% hợp đồng gọi đơn lẻ)
    # =========================================================================
    else:
        inferred_note_type_id, _ = resolve_single_note_type_for_deck(
            deck_id=deck_id,
            owner_user_id=user_id,
        )
        if inferred_note_type_id and is_installed_note_type_copy(inferred_note_type_id):
            return {
                "is_selectable": False,
                "block_code": "marketplace_note_type",
                "block_reason": "Bộ thẻ dùng Note Type cài từ Marketplace nên không thể chia sẻ lại.",
                "shared_item_id": None,
            }
        descendant_ids = set(collect_subtree_ids(deck_id)) - {deck_id}

    existing_item = shared_by_source.get(deck_id)
    if existing_item is not None and not allow_existing:
        return {
            "is_selectable": False,
            "block_code": "already_shared",
            "block_reason": "Bộ thẻ này đã được chia sẻ và không thể chia sẻ lại.",
            "shared_item_id": existing_item.id,
        }

    descendant_items = [
        (descendant_id, shared_by_source[descendant_id])
        for descendant_id in sorted(descendant_ids)
        if descendant_id in shared_by_source
    ]
    if descendant_items:
        descendant_id, descendant_item = descendant_items[0]
        descendant_deck = deck_by_id.get(descendant_id)
        descendant_name = (
            descendant_deck.name if descendant_deck is not None else str(descendant_id)
        )
        return {
            "is_selectable": False,
            "block_code": "descendant_shared",
            "block_reason": (
                f"Không thể chia sẻ bộ cha vì bộ con '{descendant_name}' đã được chia sẻ."
            ),
            "shared_item_id": descendant_item.id,
        }

    seen: set[int] = {deck_id}
    parent_id = summary.nearest_shared_ancestor if summary is not None else deck.parent_id
    while parent_id is not None and int(parent_id) not in seen:
        current_parent_id = int(parent_id)
        seen.add(current_parent_id)
        parent_item = shared_by_source.get(current_parent_id)
        if parent_item is not None:
            parent_deck = deck_by_id.get(current_parent_id)
            parent_name = parent_deck.name if parent_deck is not None else str(current_parent_id)
            return {
                "is_selectable": False,
                "block_code": "ancestor_shared",
                "block_reason": f"Không thể chia sẻ bộ con vì bộ cha '{parent_name}' đã được chia sẻ.",
                "shared_item_id": parent_item.id,
            }
        parent_deck = deck_by_id.get(current_parent_id)
        if parent_deck is None:
            break
        parent_id = parent_deck.parent_id

    return {
        "is_selectable": True,
        "block_code": None,
        "block_reason": None,
        "shared_item_id": existing_item.id if existing_item is not None else None,
    }


def build_deck_publish_options(*, user_id: int) -> dict[str, Any]:
    context = _deck_publish_context(user_id=user_id)
    deck_by_id, _installed_scope_ids, _shared_by_source = context
    deck_ids = list(deck_by_id.keys())

    if not deck_ids:
        return {"items": []}

    direct_card_count, deck_to_note_types = flashcards_share_repository.batch_get_deck_publish_facts(
        user_id=user_id,
        deck_ids=deck_ids,
    )
    all_used_nt_ids = {
        nt_id for nt_set in deck_to_note_types.values() for nt_id in nt_set
    }

    # 4. Batch marketplace installed note types (1 SQL)
    marketplace_installed_nt_ids: set[str] = (
        flashcards_share_repository.batch_get_installed_note_type_ids(all_used_nt_ids)
        if all_used_nt_ids
        else set()
    )

    # 5. Batch active templates (1 SQL)
    active_template_nt_ids: set[str] = (
        flashcards_share_repository.batch_get_active_template_note_type_ids(all_used_nt_ids)
        if all_used_nt_ids
        else set()
    )

    summaries_by_deck = build_deck_publish_index(
        parent_ids={
            deck_id: int(deck.parent_id) if deck.parent_id is not None else None
            for deck_id, deck in deck_by_id.items()
        },
        direct_card_counts=direct_card_count,
        deck_to_note_types=deck_to_note_types,
        shared_deck_ids=set(_shared_by_source),
    )
    batch_context = DeckPublishBatchContext(
        subtree_ids_by_deck={},  # Legacy context slot; no descendant sets are materialized.
        deck_to_note_types=deck_to_note_types,
        marketplace_installed_nt_ids=marketplace_installed_nt_ids,
        active_template_nt_ids=active_template_nt_ids,
        summaries_by_deck=summaries_by_deck,
    )

    items = []
    for deck_id, deck in deck_by_id.items():
        eligibility = get_deck_publish_eligibility(
            user_id=user_id,
            deck=deck,
            context=context,
            batch_context=batch_context,
        )
        items.append(
            {
                "id": deck_id,
                "name": deck.name,
                "parent_id": int(deck.parent_id) if deck.parent_id is not None else None,
                "card_count": summaries_by_deck[deck_id].card_count,
                **eligibility,
            }
        )
    return {"items": items}



def create_shared_deck_item(
    user_id: int,
    payload: dict,
    is_admin: bool,
    require_source_note_type: bool
) -> tuple[DeckMarketplaceItem | None, str | None, str | None]:
    source_deck_id_raw = payload.get("source_deck_id")
    try:
        source_deck_id = int(source_deck_id_raw)
    except (TypeError, ValueError):
        return None, "source_deck_id must be an integer.", "source_deck_id"
    source_deck = db.session.get(Deck, source_deck_id)
    if source_deck is None or source_deck.deleted_at is not None:
        return None, "source_deck_id not found.", "source_deck_id"
    eligibility = get_deck_publish_eligibility(
        user_id=user_id,
        deck=source_deck,
    )
    if not eligibility["is_selectable"]:
        return None, str(eligibility["block_reason"]), "source_deck_id"

    title = (payload.get("title") or "").strip() or (source_deck.name or "").strip()
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
    
    deferred_status = payload.get("publish_status") if "publish_status" in payload else None
    initial_payload = dict(payload)
    initial_payload["title"] = title
    initial_payload.pop("publish_status", None)
    validation_error = flashcards_share.apply_deck_marketplace_payload(
        deck_item,
        initial_payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        db.session.rollback()
        return None, validation_error, None
        
    if deck_item.source_deck_id is not None and not db.session.get(Deck, deck_item.source_deck_id):
        db.session.rollback()
        return None, "source_deck_id not found.", "source_deck_id"
        
    bind_error = flashcards_share.bind_deck_item_source_note_type(
        deck_item, 
        require_source_note_type=require_source_note_type
    )
    if bind_error:
        db.session.rollback()
        return None, bind_error, "source_note_type_id"

    if deferred_status is not None:
        validation_error = flashcards_share.apply_deck_marketplace_payload(
            deck_item,
            {"publish_status": deferred_status},
            allow_set_official=is_admin,
            publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
        )
        if validation_error:
            db.session.rollback()
            return None, validation_error, None
        
    flashcards_share.recompute_deck_item_market_stats(
        deck_item,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )
    initial_release_error = flashcards_share._stage_initial_release_if_visible(deck_item)
    if initial_release_error:
        db.session.rollback()
        return None, initial_release_error, "publish_status"
    _audit(user_id, "market.deck_item.create", {"deck_item_id": deck_item.id})
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        duplicate = DeckMarketplaceItem.query.filter_by(
            source_deck_id=source_deck_id
        ).first()
        if duplicate is not None:
            return None, "Bộ thẻ này đã được chia sẻ và không thể chia sẻ lại.", "source_deck_id"
        raise
    return deck_item, None, None



def update_shared_deck_item(
    deck_item: DeckMarketplaceItem,
    user_id: int,
    payload: dict,
    is_admin: bool,
    require_source_note_type: bool
) -> tuple[bool, str | None, str | None]:
    if deck_item.current_release_id is not None:
        if (
            "version" in payload
            and str(payload.get("version") or "").strip() != str(deck_item.version or "").strip()
        ):
            return False, "version is managed by immutable deck releases.", "version"
        if (
            "changelog" in payload
            and (str(payload.get("changelog") or "").strip() or None)
            != (str(deck_item.changelog or "").strip() or None)
        ):
            return False, "changelog is managed by immutable deck releases.", "changelog"

    if "source_deck_id" in payload:
        raw_source_deck_id = payload.get("source_deck_id")
        try:
            requested_source_deck_id = int(raw_source_deck_id)
        except (TypeError, ValueError):
            return False, "source_deck_id must be an integer.", "source_deck_id"
        if requested_source_deck_id != deck_item.source_deck_id:
            return False, "source_deck_id cannot be changed after listing creation.", "source_deck_id"

    if "source_note_type_id" in payload:
        requested_note_type_id = str(payload.get("source_note_type_id") or "").strip() or None
        current_note_type_id = str(deck_item.source_note_type_id or "").strip() or None
        if requested_note_type_id != current_note_type_id:
            return False, "source_note_type_id cannot be changed after listing creation.", "source_note_type_id"

    validation_error = flashcards_share.apply_deck_marketplace_payload(
        deck_item,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        db.session.rollback()
        return False, validation_error, None
        
    if deck_item.source_deck_id is not None and not db.session.get(Deck, deck_item.source_deck_id):
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
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )
    initial_release_error = flashcards_share._stage_initial_release_if_visible(deck_item)
    if initial_release_error:
        db.session.rollback()
        return False, initial_release_error, "publish_status"
    _audit(user_id, "market.deck_item.update", {"deck_item_id": deck_item.id})
    db.session.commit()
    return True, None, None



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
    provenance_error = validate_deck_source_note_type_provenance(
        deck_item=deck_item,
        source_note_type=source_note_type,
    )
    if provenance_error:
        return provenance_error
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type that has at least one template."
    mismatch_error = validate_marketplace_note_type_for_deck(
        deck_id=deck_item.source_deck_id,
        note_type_id=source_note_type_id,
        user_id=deck_item.owner_user_id,
        publish_backstop=True,
    )
    if mismatch_error:
        return mismatch_error
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
        "subcategory",
        "target_audience",
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
        if suggested_category and "primary_category" not in payload:
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
        raw_source_note_type_id = payload.get("source_note_type_id")
        if isinstance(raw_source_note_type_id, dict):
            raw_source_note_type_id = raw_source_note_type_id.get("id")
        deck_item.source_note_type_id = (str(raw_source_note_type_id or "")).strip() or None
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

    from app.services.marketplace_pricing_service import validate_student_offer

    student_offer_mode_raw = payload.get("student_offer_mode", deck_item.student_offer_mode)
    student_discount_percent_raw = payload.get(
        "student_discount_percent", deck_item.student_discount_percent
    )
    st_mode, st_percent, st_err = validate_student_offer(
        pricing_mode=deck_item.pricing_mode,
        student_offer_mode=student_offer_mode_raw,
        student_discount_percent=student_discount_percent_raw,
    )
    if st_err:
        return st_err
    deck_item.student_offer_mode = st_mode
    deck_item.student_discount_percent = st_percent

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
                deck_item.published_at = _utcnow()
            deck_item.archived_at = None
        elif candidate_status == "archived":
            deck_item.archived_at = _utcnow()
        deck_item.publish_status = candidate_status

    if str(deck_item.publish_status or "").strip().lower() in visible_statuses:
        return validate_deck_publish_requirements(deck_item)
    return None


def get_shared_deck_item_for_view(
    deck_item_id: str,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> DeckMarketplaceItem | None:
    deck_item = db.session.get(DeckMarketplaceItem, deck_item_id)
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
        source_note_type = db.session.get(NoteType, source_note_type_id)
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
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )
    _audit(user_id, "market.deck_item.rate", {"deck_item_id": deck_item.id, "rating": rating})
    db.session.commit()



