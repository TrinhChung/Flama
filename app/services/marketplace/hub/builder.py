"""Public Marketplace Hub builders and workspace views."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import json
import logging
import math
import re
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.orm import joinedload

from app.repositories import (
    flashcards_share_repository,
    marketplace_taxonomy_repository,
    payment_repository,
    vocabulary_repository,
)
from app.services import (
    flashcards_share,
    flashcards_share_service,
    marketplace_query_service,
    marketplace_taxonomy_service,
)
from app.services.payment import presenters as payment_presenters
from models import db
from models.card import Card
from models.deck import Deck
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_review import DeckReview
from models.marketplace_saved_item import MarketplaceSavedItem
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note_type_review import NoteTypeReview
from models.payment_attempt import PaymentAttempt
from models.payment_entitlement import PaymentEntitlement
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem
from models.user import User

logger = logging.getLogger(__name__)
UTC = timezone.utc

VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}
SUPPORTED_PRODUCT_TYPES = {"note_type", "deck_marketplace_item"}
LEVEL_LABELS = ("N5", "N4", "N3", "N2", "N1", "BEGINNER", "INTERMEDIATE", "ADVANCED")
MAX_SHELF_ITEMS = 8
MAX_LIBRARY_ITEMS = 12
MAX_FEEDBACK_ITEMS = 8
MAX_RELATED_ITEMS = 6
MAX_AUTHOR_ITEMS = 6
TRENDING_WINDOW_DAYS = 7


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


from app.services.marketplace.hub.discovery import (
    _author_other_decks,
    _author_other_note_types,
    _build_deck_available_filters,
    _build_deck_collections,
    _build_deck_discovery,
    _build_note_type_available_filters,
    _build_note_type_collections,
    _build_note_type_discovery,
    _build_purchase_history,
    _filter_deck_items,
    _filter_note_types,
    _recommended_decks,
    _recommended_note_types,
    _related_decks,
    _related_note_types,
    _sort_deck_items,
    _sort_note_types,
)
from app.services.marketplace.hub.helpers import (
    _build_badges,
    _clean_text,
    _coerce_float,
    _normalize_enum,
    _normalize_level,
    _normalize_product_type,
    _popularity_bucket,
    _primary_action,
    _primary_cta_label,
    _resolve_ownership_status,
    _weighted_average_rating,
)
from app.services.marketplace.hub.serializers import (
    _build_deck_library,
    _build_deck_seller,
    _build_note_type_library,
    _build_note_type_seller,
    _build_recent_feedback_for_decks,
    _build_recent_feedback_for_note_types,
    _build_recent_note_type_reviews,
    _deck_install_sort_key,
    _serialize_deck_card,
    _serialize_deck_install_library_row,
    _serialize_note_type_card,
)

def parse_marketplace_filters(args: Any) -> dict[str, Any]:
    return {
        "q": _clean_text(args.get("q"), max_length=160),
        "author": _clean_text(args.get("author"), max_length=120),
        "domain": _clean_text(args.get("domain"), max_length=64),
        "subject": _clean_text(args.get("subject"), max_length=64),
        "difficulty_band": _clean_text(args.get("difficulty_band"), max_length=32),
        "framework_level": _clean_text(args.get("framework_level"), max_length=64),
        "framework_track": _clean_text(args.get("framework_track"), max_length=64),
        "learning_goals": marketplace_query_service.normalize_marketplace_tags(args.get("learning_goals")),
        "primary_topics": marketplace_query_service.normalize_marketplace_tags(args.get("primary_topics")),
        "format_features": marketplace_query_service.normalize_marketplace_tags(args.get("format_features")),
        "audience": _clean_text(args.get("audience"), max_length=64),
        "has_preview": _normalize_enum(args.get("has_preview"), {"", "yes", "no"}),
        "category": _clean_text(args.get("category"), max_length=120),
        "tags": marketplace_query_service.normalize_marketplace_tags(args.get("tags")),
        "pricing_mode": _normalize_enum(args.get("pricing_mode"), {"", "free", "paid"}),
        "sort": _normalize_enum(
            args.get("sort"),
            {
                "",
                "popular",
                "top_rated",
                "newest",
                "recently_updated",
                "best_selling",
                "price_low",
                "price_high",
            },
            default="recently_updated",
        ),
        "level": _normalize_level(args.get("level")),
        "popularity": _normalize_enum(
            args.get("popularity"),
            {"", "emerging", "popular", "bestseller"},
        ),
        "min_rating": _coerce_float(args.get("min_rating"), minimum=0.0, maximum=5.0),
        "min_price": marketplace_query_service.parse_query_price_amount_minor(args.get("min_price")),
        "max_price": marketplace_query_service.parse_query_price_amount_minor(args.get("max_price")),
    }



def build_note_type_marketplace_hub(
    *,
    user_id: int,
    filters: dict[str, Any],
    compact: bool = False,
) -> dict[str, Any]:
    visible_items = (
        NoteType.query.options(joinedload(NoteType.owner))
        .filter(
            NoteType.publish_status != "archived",
            or_(
                NoteType.user_id == user_id,
                NoteType.publish_status.in_(tuple(VISIBLE_PUBLISH_STATUSES)),
            ),
        )
        .order_by(NoteType.updated_at.desc())
        .all()
    )
    installs = NoteTypeInstall.query.filter_by(user_id=user_id).all()
    install_map = {row.source_note_type_id: row for row in installs}
    saved_ids = get_saved_item_ids(user_id=user_id, product_type="note_type")
    purchase_history = _build_purchase_history(user_id=user_id, product_type="note_type")
    pending_owned_ids = {
        row["product_ref_id"]
        for row in purchase_history
        if row["is_owned_candidate"] and row["product_ref_id"] not in install_map
    }

    filtered_items = _filter_note_types(visible_items, filters=filters)
    sorted_items = _sort_note_types(filtered_items, sort_key=filters.get("sort") or "popular")
    marketplace_items = [
        _serialize_note_type_card(
            item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=pending_owned_ids,
        )
        for item in sorted_items
    ]

    library_payload = _build_note_type_library(
        user_id=user_id,
        installs=installs,
        saved_ids=saved_ids,
        purchase_history=purchase_history,
    )
    if compact:
        seller_payload = {
            "summary": {
                "total_listings": 0,
                "published_count": 0,
                "draft_count": 0,
                "archived_count": 0,
                "total_installs": 0,
                "active_usage_count": 0,
                "avg_rating": 0.0,
                "rating_count": 0,
            },
            "published": [],
            "drafts": [],
            "archived": [],
            "recent_feedback": [],
        }
        discovery_payload = {
            "hero": None,
            "recommended": [],
            "featured": [],
            "new_releases": [],
            "best_sellers": [],
            "top_rated": [],
            "collections": [],
        }
    else:
        seller_payload = _build_note_type_seller(user_id=user_id)
        discovery_payload = _build_note_type_discovery(
            user_id=user_id,
            visible_items=visible_items,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=pending_owned_ids,
        )
    return {
        "market_kind": "note_type",
        "filters": filters,
        "taxonomy_schema": marketplace_taxonomy_service.build_taxonomy_schema(content_type="note_type"),
        "available_filters": _build_note_type_available_filters(visible_items),
        "summary": {
            "market_count": len(marketplace_items),
            "library_count": int(library_payload["summary"]["owned_count"]),
            "saved_count": int(library_payload["summary"]["saved_count"]),
            "seller_count": int(seller_payload["summary"]["total_listings"]),
        },
        "discovery": discovery_payload,
        "marketplace": {
            "items": marketplace_items,
            "result_count": len(marketplace_items),
        },
        "library": library_payload,
        "seller": seller_payload,
    }



def build_deck_marketplace_hub(*, user_id: int, filters: dict[str, Any]) -> dict[str, Any]:
    visible_items = [
        item
        for item in DeckMarketplaceItem.query.order_by(DeckMarketplaceItem.updated_at.desc()).all()
        if flashcards_share_service.is_deck_item_visible_for_shared(
            item,
            user_id=user_id,
            publish_statuses_visible=VISIBLE_PUBLISH_STATUSES,
        )
    ]
    installs = DeckInstall.query.filter_by(user_id=user_id).all()
    install_map = {row.deck_item_id: row for row in installs}
    saved_ids = get_saved_item_ids(user_id=user_id, product_type="deck_marketplace_item")
    purchase_history = _build_purchase_history(user_id=user_id, product_type="deck_marketplace_item")
    pending_owned_ids = {
        row["product_ref_id"]
        for row in purchase_history
        if row["is_owned_candidate"] and row["product_ref_id"] not in install_map
    }

    filtered_items = _filter_deck_items(visible_items, filters=filters)
    sorted_items = _sort_deck_items(filtered_items, sort_key=filters.get("sort") or "popular")
    marketplace_items = [
        _serialize_deck_card(
            item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=pending_owned_ids,
        )
        for item in sorted_items
    ]

    library_payload = _build_deck_library(
        user_id=user_id,
        installs=installs,
        saved_ids=saved_ids,
        purchase_history=purchase_history,
    )
    seller_payload = _build_deck_seller(user_id=user_id)
    discovery_payload = _build_deck_discovery(
        user_id=user_id,
        visible_items=visible_items,
        install_map=install_map,
        saved_ids=saved_ids,
        pending_owned_ids=pending_owned_ids,
    )
    return {
        "market_kind": "deck_marketplace_item",
        "filters": filters,
        "taxonomy_schema": marketplace_taxonomy_service.build_taxonomy_schema(content_type="deck_marketplace_item"),
        "available_filters": _build_deck_available_filters(visible_items),
        "summary": {
            "market_count": len(marketplace_items),
            "library_count": int(library_payload["summary"]["owned_count"]),
            "saved_count": int(library_payload["summary"]["saved_count"]),
            "seller_count": int(seller_payload["summary"]["total_listings"]),
        },
        "discovery": discovery_payload,
        "marketplace": {
            "items": marketplace_items,
            "result_count": len(marketplace_items),
        },
        "library": library_payload,
        "seller": seller_payload,
    }



def build_installed_deck_workspace(*, user_id: int) -> dict[str, Any]:
    installs = (
        DeckInstall.query.options(joinedload(DeckInstall.applied_release))
        .filter_by(user_id=user_id)
        .all()
    )
    install_map = {row.deck_item_id: row for row in installs}
    saved_ids = get_saved_item_ids(user_id=user_id, product_type="deck_marketplace_item")
    source_ids = list(install_map.keys()) or [""]
    deck_items = {
        item.id: item
        for item in (
            DeckMarketplaceItem.query.options(
                joinedload(DeckMarketplaceItem.current_release)
            )
            .filter(DeckMarketplaceItem.id.in_(source_ids))
            .all()
        )
    }

    items: list[dict[str, Any]] = []
    using_count = 0
    available_count = 0
    owned_count = 0
    update_count = 0
    unread_update_count = 0

    for install in sorted(installs, key=_deck_install_sort_key, reverse=True):
        deck_item = deck_items.get(install.deck_item_id)
        if deck_item is None:
            continue
        payload = _serialize_deck_install_library_row(
            deck_item=deck_item,
            install=install,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
        )
        is_active = flashcards_share_service.is_deck_install_active(install)
        payload["install_bucket"] = "using_now" if is_active else "installed"
        items.append(payload)
        update_count += int(bool(payload.get("update_available")))
        unread_update_count += int(bool(payload.get("unread_update")))
        if is_active:
            using_count += 1
        else:
            available_count += 1

    owned_items = (
        DeckMarketplaceItem.query.join(
            Deck,
            Deck.id == DeckMarketplaceItem.source_deck_id,
        )
        .filter(
            DeckMarketplaceItem.owner_user_id == user_id,
            DeckMarketplaceItem.publish_status != "archived",
            Deck.owner_user_id == user_id,
            Deck.deleted_at.is_(None),
        )
        .order_by(
            DeckMarketplaceItem.updated_at.desc(),
            DeckMarketplaceItem.created_at.desc(),
            DeckMarketplaceItem.id.asc(),
        )
        .all()
    )
    for deck_item in owned_items:
        # A creator manages and studies the source deck directly. Creating a
        # DeckInstall for their own listing would produce a redundant clone and
        # break the logical-overlay ownership boundary.
        if deck_item.id in install_map:
            continue
        payload = _serialize_deck_card(
            deck_item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=set(),
        )
        payload.update(
            {
                "installed_deck_id": deck_item.source_deck_id,
                "install_bucket": "owned",
                "installed_at": None,
                "last_activity_at": None,
                "last_sync_status": None,
            }
        )
        items.append(payload)
        owned_count += 1

    return {
        "summary": {
            "total_installed_count": len(items),
            "using_count": using_count,
            "available_count": available_count,
            "owned_count": owned_count,
            "update_count": update_count,
            "unread_update_count": unread_update_count,
        },
        "items": items,
    }



def save_item_for_user(*, user_id: int, product_type: str, product_ref_id: str) -> bool:
    product_type = _normalize_product_type(product_type)
    product_ref_id = str(product_ref_id or "").strip()
    if not product_ref_id:
        raise ValueError("product_ref_id is required")
    existing = MarketplaceSavedItem.query.filter_by(
        user_id=user_id,
        product_type=product_type,
        product_ref_id=product_ref_id,
    ).first()
    if existing is not None:
        return False
    db.session.add(
        MarketplaceSavedItem(
            user_id=user_id,
            product_type=product_type,
            product_ref_id=product_ref_id,
        )
    )
    return True



def remove_saved_item_for_user(*, user_id: int, product_type: str, product_ref_id: str) -> bool:
    product_type = _normalize_product_type(product_type)
    row = MarketplaceSavedItem.query.filter_by(
        user_id=user_id,
        product_type=product_type,
        product_ref_id=str(product_ref_id or "").strip(),
    ).first()
    if row is None:
        return False
    db.session.delete(row)
    return True



def get_saved_item_ids(*, user_id: int, product_type: str) -> set[str]:
    product_type = _normalize_product_type(product_type)
    rows = MarketplaceSavedItem.query.filter_by(
        user_id=user_id,
        product_type=product_type,
    ).all()
    return {
        str(row.product_ref_id or "").strip()
        for row in rows
        if str(row.product_ref_id or "").strip()
    }



def build_note_type_detail_extras(*, note_type: NoteType, user_id: int) -> dict[str, Any]:
    saved_ids = get_saved_item_ids(user_id=user_id, product_type="note_type")
    install_map = {
        row.source_note_type_id: row
        for row in NoteTypeInstall.query.filter_by(user_id=user_id).all()
    }
    purchase_history = _build_purchase_history(user_id=user_id, product_type="note_type")
    pending_owned_ids = {
        row["product_ref_id"]
        for row in purchase_history
        if row["is_owned_candidate"] and row["product_ref_id"] not in install_map
    }
    visible_items = [
        item
        for item in NoteType.query.order_by(NoteType.updated_at.desc()).all()
        if flashcards_share_service.is_note_type_visible_for_shared(
            item,
            user_id=user_id,
            publish_statuses_visible=VISIBLE_PUBLISH_STATUSES,
        )
    ]
    ownership_status = _resolve_ownership_status(
        is_owner=note_type.user_id == user_id,
        is_installed=note_type.id in install_map,
        is_pending_owned=note_type.id in pending_owned_ids,
    )
    return {
        "is_saved": note_type.id in saved_ids,
        "ownership_status": ownership_status,
        "badges": _build_badges(
            pricing_mode=str(note_type.pricing_mode or "free"),
            is_official=bool(note_type.is_official),
            ownership_status=ownership_status,
            is_saved=note_type.id in saved_ids,
        ),
        "author_profile": build_author_market_profile(author_id=note_type.user_id),
        "author_other_items": [
            _serialize_note_type_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _author_other_note_types(
                current_item=note_type,
                visible_items=visible_items,
                limit=MAX_AUTHOR_ITEMS,
            )
        ],
        "related_items": [
            _serialize_note_type_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _related_note_types(
                current_item=note_type,
                visible_items=visible_items,
                limit=MAX_RELATED_ITEMS,
            )
        ],
        "recent_reviews": _build_recent_note_type_reviews(note_type_id=note_type.id, exclude_user_id=user_id),
    }



def build_deck_detail_extras(*, deck_item: DeckMarketplaceItem, user_id: int) -> dict[str, Any]:
    saved_ids = get_saved_item_ids(user_id=user_id, product_type="deck_marketplace_item")
    install_map = {
        row.deck_item_id: row
        for row in DeckInstall.query.filter_by(user_id=user_id).all()
    }
    purchase_history = _build_purchase_history(user_id=user_id, product_type="deck_marketplace_item")
    pending_owned_ids = {
        row["product_ref_id"]
        for row in purchase_history
        if row["is_owned_candidate"] and row["product_ref_id"] not in install_map
    }
    visible_items = [
        item
        for item in DeckMarketplaceItem.query.order_by(DeckMarketplaceItem.updated_at.desc()).all()
        if flashcards_share_service.is_deck_item_visible_for_shared(
            item,
            user_id=user_id,
            publish_statuses_visible=VISIBLE_PUBLISH_STATUSES,
        )
    ]
    ownership_status = _resolve_ownership_status(
        is_owner=deck_item.owner_user_id == user_id,
        is_installed=deck_item.id in install_map,
        is_pending_owned=deck_item.id in pending_owned_ids,
    )
    return {
        "is_saved": deck_item.id in saved_ids,
        "ownership_status": ownership_status,
        "badges": _build_badges(
            pricing_mode=str(deck_item.pricing_mode or "free"),
            is_official=bool(deck_item.is_official),
            ownership_status=ownership_status,
            is_saved=deck_item.id in saved_ids,
        ),
        "author_profile": build_author_market_profile(author_id=deck_item.owner_user_id),
        "author_other_items": [
            _serialize_deck_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _author_other_decks(
                current_item=deck_item,
                visible_items=visible_items,
                limit=MAX_AUTHOR_ITEMS,
            )
        ],
        "related_items": [
            _serialize_deck_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _related_decks(
                current_item=deck_item,
                visible_items=visible_items,
                limit=MAX_RELATED_ITEMS,
            )
        ],
    }



def build_author_market_profile(*, author_id: int | None) -> dict[str, Any]:
    if not author_id:
        return {
            "id": None,
            "username": "Unknown",
            "published_count": 0,
            "note_type_count": 0,
            "deck_count": 0,
            "total_installs": 0,
            "active_usage_count": 0,
            "avg_rating": 0.0,
            "rating_count": 0,
        }

    note_types = (
        NoteType.query.filter(
            NoteType.user_id == author_id,
            NoteType.publish_status.in_(tuple(VISIBLE_PUBLISH_STATUSES)),
        )
        .order_by(NoteType.updated_at.desc())
        .all()
    )
    deck_items = (
        DeckMarketplaceItem.query.filter(
            DeckMarketplaceItem.owner_user_id == author_id,
            DeckMarketplaceItem.publish_status.in_(tuple(VISIBLE_PUBLISH_STATUSES)),
        )
        .order_by(DeckMarketplaceItem.updated_at.desc())
        .all()
    )
    username = "Unknown"
    if note_types and note_types[0].owner is not None:
        username = note_types[0].owner.username or username
    elif deck_items and deck_items[0].owner is not None:
        username = deck_items[0].owner.username or username

    rating_count = sum(int(item.rating_count or 0) for item in note_types) + sum(
        int(item.rating_count or 0) for item in deck_items
    )
    weighted_rating_total = sum(
        float(item.rating_avg or 0.0) * int(item.rating_count or 0)
        for item in note_types
    ) + sum(
        float(item.rating_avg or 0.0) * int(item.rating_count or 0)
        for item in deck_items
    )
    avg_rating = (weighted_rating_total / rating_count) if rating_count > 0 else 0.0
    return {
        "id": author_id,
        "username": username,
        "published_count": len(note_types) + len(deck_items),
        "note_type_count": len(note_types),
        "deck_count": len(deck_items),
        "total_installs": sum(int(item.install_count or 0) for item in note_types) + sum(
            int(item.install_count or 0) for item in deck_items
        ),
        "active_usage_count": sum(int(item.active_usage_count or 0) for item in note_types) + sum(
            int(item.active_usage_count or 0) for item in deck_items
        ),
        "avg_rating": avg_rating,
        "rating_count": rating_count,
    }



