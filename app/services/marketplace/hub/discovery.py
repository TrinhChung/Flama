"""Marketplace discovery carousels, recommendations, collections, and sorting."""

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


from app.services.marketplace.hub.helpers import (
    _clean_text,
    _coerce_float,
    _matches_item_filters,
    _normalize_enum,
    _normalize_level,
    _normalize_product_type,
    _sorted_unique,
)
from app.services.marketplace.hub.serializers import (
    _serialize_deck_card,
    _serialize_note_type_card,
)

def _build_note_type_discovery(
    *,
    user_id: int,
    visible_items: list[NoteType],
    install_map: dict[str, NoteTypeInstall],
    saved_ids: set[str],
    pending_owned_ids: set[str],
) -> dict[str, Any]:
    recommended_items = _recommended_note_types(user_id=user_id, visible_items=visible_items)
    featured_source = _sort_note_types(visible_items, sort_key="popular")
    return {
        "hero": (
            _serialize_note_type_card(
                featured_source[0],
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            if featured_source
            else None
        ),
        "recommended": [
            _serialize_note_type_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in recommended_items[:MAX_SHELF_ITEMS]
        ],
        "featured": [
            _serialize_note_type_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in featured_source[:MAX_SHELF_ITEMS]
        ],
        "new_releases": [
            _serialize_note_type_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _sort_note_types(visible_items, sort_key="newest")[:MAX_SHELF_ITEMS]
        ],
        "best_sellers": [
            _serialize_note_type_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _sort_note_types(visible_items, sort_key="best_selling")[:MAX_SHELF_ITEMS]
        ],
        "top_rated": [
            _serialize_note_type_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _sort_note_types(visible_items, sort_key="top_rated")[:MAX_SHELF_ITEMS]
        ],
        "collections": _build_note_type_collections(
            visible_items=visible_items,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=pending_owned_ids,
        ),
    }



def _build_deck_discovery(
    *,
    user_id: int,
    visible_items: list[DeckMarketplaceItem],
    install_map: dict[str, DeckInstall],
    saved_ids: set[str],
    pending_owned_ids: set[str],
) -> dict[str, Any]:
    recommended_items = _recommended_decks(user_id=user_id, visible_items=visible_items)
    featured_source = _sort_deck_items(visible_items, sort_key="popular")
    return {
        "hero": (
            _serialize_deck_card(
                featured_source[0],
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            if featured_source
            else None
        ),
        "recommended": [
            _serialize_deck_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in recommended_items[:MAX_SHELF_ITEMS]
        ],
        "featured": [
            _serialize_deck_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in featured_source[:MAX_SHELF_ITEMS]
        ],
        "new_releases": [
            _serialize_deck_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _sort_deck_items(visible_items, sort_key="newest")[:MAX_SHELF_ITEMS]
        ],
        "best_sellers": [
            _serialize_deck_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _sort_deck_items(visible_items, sort_key="best_selling")[:MAX_SHELF_ITEMS]
        ],
        "top_rated": [
            _serialize_deck_card(
                item,
                user_id=user_id,
                install_map=install_map,
                saved_ids=saved_ids,
                pending_owned_ids=pending_owned_ids,
            )
            for item in _sort_deck_items(visible_items, sort_key="top_rated")[:MAX_SHELF_ITEMS]
        ],
        "collections": _build_deck_collections(
            visible_items=visible_items,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=pending_owned_ids,
        ),
    }



def _build_note_type_collections(
    *,
    visible_items: list[NoteType],
    user_id: int,
    install_map: dict[str, NoteTypeInstall],
    saved_ids: set[str],
    pending_owned_ids: set[str],
) -> list[dict[str, Any]]:
    collections: list[dict[str, Any]] = []
    items_by_id = {item.id: item for item in visible_items}
    grouped = marketplace_query_service.top_items_by_category_note_types(
        visible_items,
        include_definition=False,
    )
    for title, items in grouped.items():
        rows = []
        for payload in items[:MAX_SHELF_ITEMS]:
            note_type = items_by_id.get(payload["id"])
            if note_type is None:
                continue
            rows.append(
                _serialize_note_type_card(
                    note_type,
                    user_id=user_id,
                    install_map=install_map,
                    saved_ids=saved_ids,
                    pending_owned_ids=pending_owned_ids,
                )
            )
        collections.append({"title": title, "items": rows})
    return collections



def _build_deck_collections(
    *,
    visible_items: list[DeckMarketplaceItem],
    user_id: int,
    install_map: dict[str, DeckInstall],
    saved_ids: set[str],
    pending_owned_ids: set[str],
) -> list[dict[str, Any]]:
    collections: list[dict[str, Any]] = []
    items_by_id = {item.id: item for item in visible_items}
    grouped = marketplace_query_service.top_items_by_category_decks(visible_items)
    for title, items in grouped.items():
        rows = []
        for payload in items[:MAX_SHELF_ITEMS]:
            deck_item = items_by_id.get(payload["id"])
            if deck_item is None:
                continue
            rows.append(
                _serialize_deck_card(
                    deck_item,
                    user_id=user_id,
                    install_map=install_map,
                    saved_ids=saved_ids,
                    pending_owned_ids=pending_owned_ids,
                )
            )
        collections.append({"title": title, "items": rows})
    return collections



def _build_purchase_history(*, user_id: int, product_type: str) -> list[dict[str, Any]]:
    product_type = _normalize_product_type(product_type)
    rows = (
        db.session.query(PaymentOrder, PaymentOrderItem)
        .join(PaymentOrderItem, PaymentOrderItem.order_id == PaymentOrder.id)
        .filter(
            PaymentOrder.user_id == user_id,
            PaymentOrderItem.product_type == product_type,
        )
        .order_by(PaymentOrder.created_at.desc(), PaymentOrderItem.created_at.desc())
        .all()
    )
    history: list[dict[str, Any]] = []
    for order, item in rows:
        status_display = payment_presenters.build_order_row(order)
        history.append(
            {
                "order_id": order.id,
                "merchant_order_code": order.merchant_order_code,
                "product_ref_id": item.product_ref_id,
                "title": item.title_snapshot,
                "product_type": item.product_type,
                "product_type_label": payment_presenters.product_type_label(item.product_type),
                "status": order.status,
                "status_label": status_display["status_label"],
                "status_tone": status_display["status_tone"],
                "grant_status": order.grant_status,
                "grant_status_label": status_display["grant_status_label"],
                "total_amount_display": payment_presenters.format_minor_amount(
                    item.line_total_amount_minor or order.total_amount_minor,
                    currency_code=order.currency_code,
                ),
                "created_at": order.created_at.isoformat() if order.created_at else None,
                "paid_at": order.paid_at.isoformat() if order.paid_at else None,
                "is_owned_candidate": order.status in {"paid", "under_review"} and order.grant_status != "failed",
            }
        )
    return history



def _recommended_note_types(*, user_id: int, visible_items: list[NoteType]) -> list[NoteType]:
    candidate_items = [item for item in visible_items if item.user_id != user_id]
    if not candidate_items:
        return []

    interests_categories, interests_tags = marketplace_query_service.collect_user_market_interests(user_id)
    cold_start = not interests_categories and not interests_tags
    trending_counts = _note_type_trending_counts()

    scored: list[tuple[float, NoteType]] = []
    for item in candidate_items:
        score = marketplace_query_service.score_market_item(
            item_category=item.primary_category,
            item_tags=item.tags or [],
            rating_avg=float(item.rating_avg or 0.0),
            rating_count=int(item.rating_count or 0),
            active_usage_count=int(item.active_usage_count or 0),
            install_count=int(item.install_count or 0),
            updated_at=item.updated_at,
            interests_categories=interests_categories,
            interests_tags=interests_tags,
            is_official=bool(item.is_official),
            cold_start=cold_start,
        )
        score += min(1.0, trending_counts.get(item.id, 0) / 5.0)
        scored.append((score, item))

    ranked = sorted(
        scored,
        key=lambda row: (
            row[0],
            int(row[1].install_count or 0),
            int(row[1].active_usage_count or 0),
            float(row[1].rating_avg or 0.0),
            row[1].updated_at or datetime.min,
        ),
        reverse=True,
    )
    if ranked:
        return [item for _, item in ranked]
    return _sort_note_types(candidate_items, sort_key="popular")



def _recommended_decks(*, user_id: int, visible_items: list[DeckMarketplaceItem]) -> list[DeckMarketplaceItem]:
    interests_categories, interests_tags = marketplace_query_service.collect_user_market_interests(user_id)
    cold_start = not interests_categories and not interests_tags
    trending_counts = _deck_trending_counts()

    scored: list[tuple[float, DeckMarketplaceItem]] = []
    for item in visible_items:
        if item.owner_user_id == user_id:
            continue
        score = marketplace_query_service.score_market_item(
            item_category=item.primary_category,
            item_tags=item.tags or [],
            rating_avg=float(item.rating_avg or 0.0),
            rating_count=int(item.rating_count or 0),
            active_usage_count=int(item.active_usage_count or 0),
            install_count=int(item.install_count or 0),
            updated_at=item.updated_at,
            interests_categories=interests_categories,
            interests_tags=interests_tags,
            is_official=bool(item.is_official),
            cold_start=cold_start,
        )
        score += min(1.0, trending_counts.get(item.id, 0) / 5.0)
        scored.append((score, item))

    ranked = sorted(
        scored,
        key=lambda row: (
            row[0],
            int(row[1].install_count or 0),
            int(row[1].active_usage_count or 0),
            float(row[1].rating_avg or 0.0),
            row[1].updated_at or datetime.min,
        ),
        reverse=True,
    )
    if ranked:
        return [item for _, item in ranked]
    return [item for item in _sort_deck_items(visible_items, sort_key="popular") if item.owner_user_id != user_id]



def _note_type_trending_counts() -> dict[str, int]:
    cutoff = _utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
    rows = (
        db.session.query(NoteTypeInstall.source_note_type_id, db.func.count(NoteTypeInstall.id))
        .filter(NoteTypeInstall.installed_at >= cutoff)
        .group_by(NoteTypeInstall.source_note_type_id)
        .all()
    )
    return {
        str(item_id).strip(): int(total or 0)
        for item_id, total in rows
        if item_id is not None and str(item_id).strip()
    }



def _deck_trending_counts() -> dict[str, int]:
    cutoff = _utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
    rows = (
        db.session.query(DeckInstall.deck_item_id, db.func.count(DeckInstall.id))
        .filter(DeckInstall.installed_at >= cutoff)
        .group_by(DeckInstall.deck_item_id)
        .all()
    )
    return {
        str(item_id).strip(): int(total or 0)
        for item_id, total in rows
        if item_id is not None and str(item_id).strip()
    }



def _build_note_type_available_filters(items: list[NoteType]) -> dict[str, Any]:
    taxonomies = [
        marketplace_taxonomy_service.get_item_taxonomy(item, content_type="note_type")
        for item in items
    ]
    return {
        "categories": _sorted_unique((item.primary_category or "General") for item in items),
        "authors": _sorted_unique((item.owner.username if item.owner else "") for item in items),
        "tags": _sorted_unique(tag for item in items for tag in (item.tags or [])),
        "levels": _sorted_unique(level for row in taxonomies for level in [row.get("difficulty_band")] if level),
        "domains": _sorted_unique(row.get("domain") for row in taxonomies if row.get("domain")),
        "subjects": _sorted_unique(row.get("subject") for row in taxonomies if row.get("subject")),
        "framework_levels": _sorted_unique(row.get("framework_level") for row in taxonomies if row.get("framework_level")),
        "framework_tracks": _sorted_unique(row.get("framework_track") for row in taxonomies if row.get("framework_track")),
        "learning_goals": _sorted_unique(goal for row in taxonomies for goal in (row.get("learning_goals") or [])),
        "primary_topics": _sorted_unique(topic for row in taxonomies for topic in (row.get("primary_topics") or [])),
        "format_features": _sorted_unique(feature for row in taxonomies for feature in (row.get("format_features") or [])),
        "audiences": _sorted_unique(row.get("audience") for row in taxonomies if row.get("audience")),
    }



def _build_deck_available_filters(items: list[DeckMarketplaceItem]) -> dict[str, Any]:
    taxonomies = [
        marketplace_taxonomy_service.get_item_taxonomy(item, content_type="deck_marketplace_item")
        for item in items
    ]
    return {
        "categories": _sorted_unique((item.primary_category or "General") for item in items),
        "authors": _sorted_unique((item.owner.username if item.owner else "") for item in items),
        "tags": _sorted_unique(tag for item in items for tag in (item.tags or [])),
        "levels": _sorted_unique(level for row in taxonomies for level in [row.get("difficulty_band")] if level),
        "domains": _sorted_unique(row.get("domain") for row in taxonomies if row.get("domain")),
        "subjects": _sorted_unique(row.get("subject") for row in taxonomies if row.get("subject")),
        "framework_levels": _sorted_unique(row.get("framework_level") for row in taxonomies if row.get("framework_level")),
        "framework_tracks": _sorted_unique(row.get("framework_track") for row in taxonomies if row.get("framework_track")),
        "learning_goals": _sorted_unique(goal for row in taxonomies for goal in (row.get("learning_goals") or [])),
        "primary_topics": _sorted_unique(topic for row in taxonomies for topic in (row.get("primary_topics") or [])),
        "format_features": _sorted_unique(feature for row in taxonomies for feature in (row.get("format_features") or [])),
        "audiences": _sorted_unique(row.get("audience") for row in taxonomies if row.get("audience")),
    }



def _filter_note_types(items: list[NoteType], *, filters: dict[str, Any], user_id: int = 0) -> list[NoteType]:
    amounts = {}
    if filters.get("pricing_mode") in {"free", "paid"} or filters.get("min_price") is not None or filters.get("max_price") is not None:
        from app.services.note_type_bundle_pricing_service import pricing_breakdown
        amounts = {item.id: pricing_breakdown(db.session, note_type=item, user_id=user_id)["total_amount_minor"] for item in items}
    return [
        item
        for item in items
        if _matches_item_filters(
            title=item.name,
            description=item.description,
            author_username=(item.owner.username if item.owner else ""),
            category=item.primary_category,
            tags=item.tags or [],
            pricing_mode=("paid" if amounts[item.id] else "free") if item.id in amounts else str(item.pricing_mode or "free"),
            price_amount_minor=amounts.get(item.id, int(item.price_amount_minor or 0)),
            rating_avg=float(item.rating_avg or 0.0),
            install_count=int(item.install_count or 0),
            content_type="note_type",
            taxonomy=marketplace_taxonomy_service.get_item_taxonomy(item, content_type="note_type"),
            has_preview=bool((item.preview_text or "").strip() or (item.preview_image_url or "").strip()),
            filters=filters,
        )
    ]



def _filter_deck_items(items: list[DeckMarketplaceItem], *, filters: dict[str, Any]) -> list[DeckMarketplaceItem]:
    return [
        item
        for item in items
        if _matches_item_filters(
            title=item.title,
            description=item.description,
            author_username=(item.owner.username if item.owner else ""),
            category=item.primary_category,
            tags=item.tags or [],
            pricing_mode=str(item.pricing_mode or "free"),
            price_amount_minor=int(item.price_amount_minor or 0),
            rating_avg=float(item.rating_avg or 0.0),
            install_count=int(item.install_count or 0),
            content_type="deck_marketplace_item",
            taxonomy=marketplace_taxonomy_service.get_item_taxonomy(item, content_type="deck_marketplace_item"),
            has_preview=bool((item.preview_text or "").strip() or int(item.sample_cards_count or 0) > 0),
            filters=filters,
        )
    ]



def _sort_note_types(items: list[NoteType], *, sort_key: str, user_id: int = 0) -> list[NoteType]:
    token = str(sort_key or "popular").strip().lower()
    if token == "best_selling":
        return sorted(items, key=lambda item: (int(item.install_count or 0), int(item.active_usage_count or 0)), reverse=True)
    if token in {"price_low", "price_high"}:
        from app.services.note_type_bundle_pricing_service import pricing_breakdown
        amounts = {item.id: pricing_breakdown(db.session, note_type=item, user_id=user_id)["total_amount_minor"] for item in items}
        return sorted(items, key=lambda item: (amounts[item.id], item.updated_at or datetime.min), reverse=token == "price_high")
    return marketplace_query_service.sort_note_type_items(items, token)



def _sort_deck_items(items: list[DeckMarketplaceItem], *, sort_key: str) -> list[DeckMarketplaceItem]:
    token = str(sort_key or "popular").strip().lower()
    if token == "best_selling":
        return sorted(items, key=lambda item: (int(item.install_count or 0), int(item.active_usage_count or 0)), reverse=True)
    if token == "price_low":
        return sorted(items, key=lambda item: (int(item.price_amount_minor or 0), (item.updated_at or datetime.min)))
    if token == "price_high":
        return sorted(items, key=lambda item: (int(item.price_amount_minor or 0), (item.updated_at or datetime.min)), reverse=True)
    return marketplace_query_service.sort_deck_items(items, token)



def _author_other_note_types(*, current_item: NoteType, visible_items: list[NoteType], limit: int) -> list[NoteType]:
    return [
        item
        for item in visible_items
        if item.id != current_item.id and item.user_id == current_item.user_id
    ][:limit]



def _author_other_decks(*, current_item: DeckMarketplaceItem, visible_items: list[DeckMarketplaceItem], limit: int) -> list[DeckMarketplaceItem]:
    return [
        item
        for item in visible_items
        if item.id != current_item.id and item.owner_user_id == current_item.owner_user_id
    ][:limit]



def _related_note_types(*, current_item: NoteType, visible_items: list[NoteType], limit: int) -> list[NoteType]:
    current_tags = {str(tag).strip().lower() for tag in (current_item.tags or []) if str(tag).strip()}
    current_category = str(current_item.primary_category or "").strip().lower()
    scored: list[tuple[float, NoteType]] = []
    for item in visible_items:
        if item.id == current_item.id or item.user_id == current_item.user_id:
            continue
        candidate_tags = {str(tag).strip().lower() for tag in (item.tags or []) if str(tag).strip()}
        overlap = len(current_tags.intersection(candidate_tags))
        category_match = 1.5 if current_category and current_category == str(item.primary_category or "").strip().lower() else 0.0
        score = category_match + (overlap * 1.25) + float(item.rating_avg or 0.0) + min(2.0, int(item.install_count or 0) / 25)
        scored.append((score, item))
    return [item for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:limit]]



def _related_decks(*, current_item: DeckMarketplaceItem, visible_items: list[DeckMarketplaceItem], limit: int) -> list[DeckMarketplaceItem]:
    current_tags = {str(tag).strip().lower() for tag in (current_item.tags or []) if str(tag).strip()}
    current_category = str(current_item.primary_category or "").strip().lower()
    scored: list[tuple[float, DeckMarketplaceItem]] = []
    for item in visible_items:
        if item.id == current_item.id or item.owner_user_id == current_item.owner_user_id:
            continue
        candidate_tags = {str(tag).strip().lower() for tag in (item.tags or []) if str(tag).strip()}
        overlap = len(current_tags.intersection(candidate_tags))
        category_match = 1.5 if current_category and current_category == str(item.primary_category or "").strip().lower() else 0.0
        score = category_match + (overlap * 1.25) + float(item.rating_avg or 0.0) + min(2.0, int(item.install_count or 0) / 25)
        scored.append((score, item))
    return [item for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:limit]]



