from __future__ import annotations

from datetime import datetime, timedelta
import re
from typing import Any

from app.services import flashcards_share_service, marketplace_query_service, marketplace_taxonomy_service
from app.services.payment import presenters as payment_presenters
from models import db
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_review import DeckReview
from models.marketplace_saved_item import MarketplaceSavedItem
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note_type_review import NoteTypeReview
from models.payment_order import PaymentOrder
from models.payment_order_item import PaymentOrderItem


VISIBLE_PUBLISH_STATUSES = {"published", "unlisted"}
SUPPORTED_PRODUCT_TYPES = {"note_type", "deck_marketplace_item"}
LEVEL_LABELS = ("N5", "N4", "N3", "N2", "N1", "BEGINNER", "INTERMEDIATE", "ADVANCED")
MAX_SHELF_ITEMS = 8
MAX_LIBRARY_ITEMS = 12
MAX_FEEDBACK_ITEMS = 8
MAX_RELATED_ITEMS = 6
MAX_AUTHOR_ITEMS = 6
TRENDING_WINDOW_DAYS = 7


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


def build_note_type_marketplace_hub(*, user_id: int, filters: dict[str, Any]) -> dict[str, Any]:
    visible_items = [
        item
        for item in NoteType.query.order_by(NoteType.updated_at.desc()).all()
        if flashcards_share_service.is_note_type_visible_for_shared(
            item,
            user_id=user_id,
            publish_statuses_visible=VISIBLE_PUBLISH_STATUSES,
        )
    ]
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


def _serialize_note_type_card(
    note_type: NoteType,
    *,
    user_id: int,
    install_map: dict[str, NoteTypeInstall],
    saved_ids: set[str],
    pending_owned_ids: set[str],
) -> dict[str, Any]:
    payload = marketplace_query_service.serialize_note_type_marketplace_card(note_type)
    taxonomy_display = marketplace_taxonomy_service.build_taxonomy_display(
        payload.get("taxonomy_metadata") or {},
        content_type="note_type",
    )
    ownership_status = _resolve_ownership_status(
        is_owner=note_type.user_id == user_id,
        is_installed=note_type.id in install_map,
        is_pending_owned=note_type.id in pending_owned_ids,
    )
    level_tokens = taxonomy_display.get("catalog_chips") or _infer_market_levels(
        payload.get("title"),
        payload.get("description"),
        payload.get("primary_category"),
        tags=payload.get("tags") or [],
    )
    payload.update(
        {
            "is_owner": ownership_status == "owner",
            "is_installed": ownership_status == "installed",
            "installed_note_type_id": (
                install_map[note_type.id].installed_note_type_id
                if note_type.id in install_map
                else None
            ),
            "is_saved": note_type.id in saved_ids,
            "ownership_status": ownership_status,
            "level_tokens": level_tokens,
            "short_description": _truncate_text(payload.get("description"), max_length=160),
            "primary_cta_label": _primary_cta_label(
                ownership_status=ownership_status,
                pricing_mode=str(note_type.pricing_mode or "free"),
            ),
            "primary_action": _primary_action(ownership_status=ownership_status),
            "badges": _build_badges(
                pricing_mode=str(note_type.pricing_mode or "free"),
                is_official=bool(note_type.is_official),
                ownership_status=ownership_status,
                is_saved=note_type.id in saved_ids,
            ),
            "author_filter_token": (payload.get("author") or {}).get("username") or "",
            "popularity_bucket": _popularity_bucket(int(note_type.install_count or 0)),
            "subject_label": taxonomy_display.get("subject_label"),
            "difficulty_label": taxonomy_display.get("difficulty_label"),
            "framework_level_label": taxonomy_display.get("framework_level_label"),
            "learning_goal_labels": taxonomy_display.get("learning_goal_labels") or [],
            "primary_topic_labels": taxonomy_display.get("primary_topic_labels") or [],
            "display_tags": payload.get("display_tags") or [],
        }
    )
    return payload


def _serialize_deck_card(
    deck_item: DeckMarketplaceItem,
    *,
    user_id: int,
    install_map: dict[str, DeckInstall],
    saved_ids: set[str],
    pending_owned_ids: set[str],
) -> dict[str, Any]:
    payload = marketplace_query_service.serialize_deck_marketplace_item(deck_item)
    taxonomy_display = marketplace_taxonomy_service.build_taxonomy_display(
        payload.get("taxonomy_metadata") or {},
        content_type="deck_marketplace_item",
    )
    ownership_status = _resolve_ownership_status(
        is_owner=deck_item.owner_user_id == user_id,
        is_installed=deck_item.id in install_map,
        is_pending_owned=deck_item.id in pending_owned_ids,
    )
    level_tokens = taxonomy_display.get("catalog_chips") or _infer_market_levels(
        payload.get("title"),
        payload.get("description"),
        payload.get("primary_category"),
        tags=payload.get("tags") or [],
    )
    payload.update(
        {
            "is_owner": ownership_status == "owner",
            "is_installed": ownership_status == "installed",
            "installed_deck_id": (
                install_map[deck_item.id].local_deck_id
                if deck_item.id in install_map
                else None
            ),
            "is_saved": deck_item.id in saved_ids,
            "ownership_status": ownership_status,
            "level_tokens": level_tokens,
            "short_description": _truncate_text(payload.get("description"), max_length=160),
            "primary_cta_label": _primary_cta_label(
                ownership_status=ownership_status,
                pricing_mode=str(deck_item.pricing_mode or "free"),
            ),
            "primary_action": _primary_action(ownership_status=ownership_status),
            "badges": _build_badges(
                pricing_mode=str(deck_item.pricing_mode or "free"),
                is_official=bool(deck_item.is_official),
                ownership_status=ownership_status,
                is_saved=deck_item.id in saved_ids,
            ),
            "author_filter_token": (payload.get("author") or {}).get("username") or "",
            "popularity_bucket": _popularity_bucket(int(deck_item.install_count or 0)),
            "subject_label": taxonomy_display.get("subject_label"),
            "difficulty_label": taxonomy_display.get("difficulty_label"),
            "framework_level_label": taxonomy_display.get("framework_level_label"),
            "learning_goal_labels": taxonomy_display.get("learning_goal_labels") or [],
            "primary_topic_labels": taxonomy_display.get("primary_topic_labels") or [],
            "display_tags": payload.get("display_tags") or [],
        }
    )
    return payload


def _build_note_type_library(
    *,
    user_id: int,
    installs: list[NoteTypeInstall],
    saved_ids: set[str],
    purchase_history: list[dict[str, Any]],
) -> dict[str, Any]:
    install_map = {row.source_note_type_id: row for row in installs}
    source_ids = list(install_map.keys()) or [""]
    note_types = {
        item.id: item
        for item in NoteType.query.filter(NoteType.id.in_(source_ids)).all()
    }
    using_now: list[dict[str, Any]] = []
    installed: list[dict[str, Any]] = []
    for install in sorted(
        installs,
        key=lambda row: (
            row.last_activity_at or datetime.min,
            row.installed_at or datetime.min,
            row.id,
        ),
        reverse=True,
    ):
        note_type = note_types.get(install.source_note_type_id)
        if note_type is None:
            continue
        payload = _serialize_note_type_card(
            note_type,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=set(),
        )
        payload["installed_at"] = install.installed_at.isoformat() if install.installed_at else None
        payload["last_activity_at"] = install.last_activity_at.isoformat() if install.last_activity_at else None
        if flashcards_share_service.is_note_type_install_active(install):
            using_now.append(payload)
        else:
            installed.append(payload)

    not_installed_ids = {
        row["product_ref_id"]
        for row in purchase_history
        if row["is_owned_candidate"] and row["product_ref_id"] not in install_map
    }
    not_installed_items = [
        _serialize_note_type_card(
            item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=not_installed_ids,
        )
        for item in NoteType.query.filter(NoteType.id.in_(list(not_installed_ids) or [""])).all()
    ]
    saved_items = [
        _serialize_note_type_card(
            item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=set(),
        )
        for item in NoteType.query.filter(NoteType.id.in_(list(saved_ids) or [""])).all()
        if item.id not in install_map and item.id not in not_installed_ids and item.user_id != user_id
    ]
    return {
        "summary": {
            "owned_count": len(installed) + len(using_now) + len(not_installed_items),
            "using_count": len(using_now),
            "saved_count": len(saved_items),
            "purchase_count": len(purchase_history),
        },
        "using_now": using_now[:MAX_LIBRARY_ITEMS],
        "installed": installed[:MAX_LIBRARY_ITEMS],
        "not_installed": not_installed_items[:MAX_LIBRARY_ITEMS],
        "saved": saved_items[:MAX_LIBRARY_ITEMS],
        "purchase_history": purchase_history[:MAX_LIBRARY_ITEMS],
    }


def _build_deck_library(
    *,
    user_id: int,
    installs: list[DeckInstall],
    saved_ids: set[str],
    purchase_history: list[dict[str, Any]],
) -> dict[str, Any]:
    install_map = {row.deck_item_id: row for row in installs}
    source_ids = list(install_map.keys()) or [""]
    deck_items = {
        item.id: item
        for item in DeckMarketplaceItem.query.filter(DeckMarketplaceItem.id.in_(source_ids)).all()
    }
    using_now: list[dict[str, Any]] = []
    installed: list[dict[str, Any]] = []
    for install in sorted(
        installs,
        key=lambda row: (
            row.last_activity_at or datetime.min,
            row.installed_at or datetime.min,
            row.id,
        ),
        reverse=True,
    ):
        deck_item = deck_items.get(install.deck_item_id)
        if deck_item is None:
            continue
        payload = _serialize_deck_card(
            deck_item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=set(),
        )
        payload["installed_at"] = install.installed_at.isoformat() if install.installed_at else None
        payload["last_activity_at"] = install.last_activity_at.isoformat() if install.last_activity_at else None
        if flashcards_share_service.is_deck_install_active(install):
            using_now.append(payload)
        else:
            installed.append(payload)

    not_installed_ids = {
        row["product_ref_id"]
        for row in purchase_history
        if row["is_owned_candidate"] and row["product_ref_id"] not in install_map
    }
    not_installed_items = [
        _serialize_deck_card(
            item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=not_installed_ids,
        )
        for item in DeckMarketplaceItem.query.filter(DeckMarketplaceItem.id.in_(list(not_installed_ids) or [""])).all()
    ]
    saved_items = [
        _serialize_deck_card(
            item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=set(),
        )
        for item in DeckMarketplaceItem.query.filter(DeckMarketplaceItem.id.in_(list(saved_ids) or [""])).all()
        if item.id not in install_map and item.id not in not_installed_ids and item.owner_user_id != user_id
    ]
    return {
        "summary": {
            "owned_count": len(installed) + len(using_now) + len(not_installed_items),
            "using_count": len(using_now),
            "saved_count": len(saved_items),
            "purchase_count": len(purchase_history),
        },
        "using_now": using_now[:MAX_LIBRARY_ITEMS],
        "installed": installed[:MAX_LIBRARY_ITEMS],
        "not_installed": not_installed_items[:MAX_LIBRARY_ITEMS],
        "saved": saved_items[:MAX_LIBRARY_ITEMS],
        "purchase_history": purchase_history[:MAX_LIBRARY_ITEMS],
    }


def _build_note_type_seller(*, user_id: int) -> dict[str, Any]:
    owned_items = (
        NoteType.query.filter_by(user_id=user_id)
        .order_by(NoteType.updated_at.desc(), NoteType.created_at.desc())
        .all()
    )
    items = [
        _serialize_note_type_card(
            item,
            user_id=user_id,
            install_map={},
            saved_ids=set(),
            pending_owned_ids=set(),
        )
        for item in owned_items
    ]
    return {
        "summary": {
            "total_listings": len(owned_items),
            "published_count": sum(1 for item in owned_items if str(item.publish_status or "") in VISIBLE_PUBLISH_STATUSES),
            "draft_count": sum(1 for item in owned_items if str(item.publish_status or "") == "private"),
            "archived_count": sum(1 for item in owned_items if str(item.publish_status or "") == "archived"),
            "total_installs": sum(int(item.install_count or 0) for item in owned_items),
            "active_usage_count": sum(int(item.active_usage_count or 0) for item in owned_items),
            "avg_rating": _weighted_average_rating(owned_items),
            "rating_count": sum(int(item.rating_count or 0) for item in owned_items),
        },
        "published": [item for item in items if str(item.get("publish_status") or "") in VISIBLE_PUBLISH_STATUSES][:MAX_LIBRARY_ITEMS],
        "drafts": [item for item in items if str(item.get("publish_status") or "") == "private"][:MAX_LIBRARY_ITEMS],
        "archived": [item for item in items if str(item.get("publish_status") or "") == "archived"][:MAX_LIBRARY_ITEMS],
        "recent_feedback": _build_recent_feedback_for_note_types(user_id=user_id),
    }


def _build_deck_seller(*, user_id: int) -> dict[str, Any]:
    owned_items = (
        DeckMarketplaceItem.query.filter_by(owner_user_id=user_id)
        .order_by(DeckMarketplaceItem.updated_at.desc(), DeckMarketplaceItem.created_at.desc())
        .all()
    )
    items = [
        _serialize_deck_card(
            item,
            user_id=user_id,
            install_map={},
            saved_ids=set(),
            pending_owned_ids=set(),
        )
        for item in owned_items
    ]
    return {
        "summary": {
            "total_listings": len(owned_items),
            "published_count": sum(1 for item in owned_items if str(item.publish_status or "") in VISIBLE_PUBLISH_STATUSES),
            "draft_count": sum(1 for item in owned_items if str(item.publish_status or "") == "private"),
            "archived_count": sum(1 for item in owned_items if str(item.publish_status or "") == "archived"),
            "total_installs": sum(int(item.install_count or 0) for item in owned_items),
            "active_usage_count": sum(int(item.active_usage_count or 0) for item in owned_items),
            "avg_rating": _weighted_average_rating(owned_items),
            "rating_count": sum(int(item.rating_count or 0) for item in owned_items),
        },
        "published": [item for item in items if str(item.get("publish_status") or "") in VISIBLE_PUBLISH_STATUSES][:MAX_LIBRARY_ITEMS],
        "drafts": [item for item in items if str(item.get("publish_status") or "") == "private"][:MAX_LIBRARY_ITEMS],
        "archived": [item for item in items if str(item.get("publish_status") or "") == "archived"][:MAX_LIBRARY_ITEMS],
        "recent_feedback": _build_recent_feedback_for_decks(user_id=user_id),
    }


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
    grouped = marketplace_query_service.top_items_by_category_note_types(visible_items)
    for title, items in grouped.items():
        rows = []
        for payload in items[:MAX_SHELF_ITEMS]:
            note_type = NoteType.query.get(payload["id"])
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
    grouped = marketplace_query_service.top_items_by_category_decks(visible_items)
    for title, items in grouped.items():
        rows = []
        for payload in items[:MAX_SHELF_ITEMS]:
            deck_item = DeckMarketplaceItem.query.get(payload["id"])
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
    interests_categories, interests_tags = marketplace_query_service.collect_user_market_interests(user_id)
    cold_start = not interests_categories and not interests_tags
    trending_counts = _note_type_trending_counts()

    scored: list[tuple[float, NoteType]] = []
    for item in visible_items:
        if item.user_id == user_id:
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
    return [item for item in _sort_note_types(visible_items, sort_key="popular") if item.user_id != user_id]


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
    cutoff = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
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
    cutoff = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
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


def _build_recent_note_type_reviews(*, note_type_id: str, exclude_user_id: int | None) -> list[dict[str, Any]]:
    query = NoteTypeReview.query.filter(NoteTypeReview.note_type_id == note_type_id)
    if exclude_user_id is not None:
        query = query.filter(NoteTypeReview.user_id != exclude_user_id)
    rows = (
        query.order_by(
            NoteTypeReview.updated_at.desc(),
            NoteTypeReview.created_at.desc(),
            NoteTypeReview.id.desc(),
        )
        .limit(MAX_FEEDBACK_ITEMS)
        .all()
    )
    return [
        {
            "rating": int(row.rating or 0),
            "comment": row.comment,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
            "username": row.user.username if row.user else "Unknown",
        }
        for row in rows
    ]


def _build_recent_feedback_for_note_types(*, user_id: int) -> list[dict[str, Any]]:
    rows = (
        NoteTypeReview.query.join(NoteType, NoteType.id == NoteTypeReview.note_type_id)
        .filter(NoteType.user_id == user_id)
        .order_by(NoteTypeReview.updated_at.desc(), NoteTypeReview.created_at.desc())
        .limit(MAX_FEEDBACK_ITEMS)
        .all()
    )
    return [
        {
            "item_id": row.note_type_id,
            "title": row.note_type.name if row.note_type else "Template",
            "rating": int(row.rating or 0),
            "comment": row.comment,
            "username": row.user.username if row.user else "Unknown",
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


def _build_recent_feedback_for_decks(*, user_id: int) -> list[dict[str, Any]]:
    rows = (
        DeckReview.query.join(DeckMarketplaceItem, DeckMarketplaceItem.id == DeckReview.deck_item_id)
        .filter(DeckMarketplaceItem.owner_user_id == user_id)
        .order_by(DeckReview.updated_at.desc(), DeckReview.created_at.desc())
        .limit(MAX_FEEDBACK_ITEMS)
        .all()
    )
    return [
        {
            "item_id": row.deck_item_id,
            "title": row.deck_item.title if row.deck_item else "Deck",
            "rating": int(row.rating or 0),
            "comment": row.comment,
            "username": row.user.username if row.user else "Unknown",
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
        for row in rows
    ]


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


def _filter_note_types(items: list[NoteType], *, filters: dict[str, Any]) -> list[NoteType]:
    return [
        item
        for item in items
        if _matches_item_filters(
            title=item.name,
            description=item.description,
            author_username=(item.owner.username if item.owner else ""),
            category=item.primary_category,
            tags=item.tags or [],
            pricing_mode=str(item.pricing_mode or "free"),
            price_amount_minor=int(item.price_amount_minor or 0),
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


def _sort_note_types(items: list[NoteType], *, sort_key: str) -> list[NoteType]:
    token = str(sort_key or "popular").strip().lower()
    if token == "best_selling":
        return sorted(items, key=lambda item: (int(item.install_count or 0), int(item.active_usage_count or 0)), reverse=True)
    if token == "price_low":
        return sorted(items, key=lambda item: (int(item.price_amount_minor or 0), (item.updated_at or datetime.min)))
    if token == "price_high":
        return sorted(items, key=lambda item: (int(item.price_amount_minor or 0), (item.updated_at or datetime.min)), reverse=True)
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


def _matches_item_filters(
    *,
    title: str | None,
    description: str | None,
    author_username: str | None,
    category: str | None,
    tags: list[str],
    pricing_mode: str,
    price_amount_minor: int,
    rating_avg: float,
    install_count: int,
    content_type: str,
    taxonomy: dict[str, Any],
    has_preview: bool,
    filters: dict[str, Any],
) -> bool:
    query_text = str(filters.get("q") or "").strip().lower()
    author_filter = str(filters.get("author") or "").strip().lower()
    domain_filter = str(filters.get("domain") or "").strip().lower()
    subject_filter = str(filters.get("subject") or "").strip().lower()
    difficulty_filter = str(filters.get("difficulty_band") or "").strip().lower()
    framework_level_filter = str(filters.get("framework_level") or "").strip().lower()
    framework_track_filter = str(filters.get("framework_track") or "").strip().lower()
    audience_filter = str(filters.get("audience") or "").strip().lower()
    learning_goals_filter = {
        str(item).strip().lower()
        for item in (filters.get("learning_goals") or [])
        if str(item).strip()
    }
    primary_topics_filter = {
        str(item).strip().lower()
        for item in (filters.get("primary_topics") or [])
        if str(item).strip()
    }
    format_features_filter = {
        str(item).strip().lower()
        for item in (filters.get("format_features") or [])
        if str(item).strip()
    }
    has_preview_filter = str(filters.get("has_preview") or "").strip().lower()
    category_filter = str(filters.get("category") or "").strip().lower()
    tags_filter = {str(item).strip().lower() for item in (filters.get("tags") or []) if str(item).strip()}
    pricing_filter = str(filters.get("pricing_mode") or "").strip().lower()
    popularity_filter = str(filters.get("popularity") or "").strip().lower()
    min_rating = filters.get("min_rating")
    min_price = filters.get("min_price")
    max_price = filters.get("max_price")

    taxonomy_text = marketplace_taxonomy_service.build_searchable_taxonomy_text(
        taxonomy,
        content_type=content_type,
    )
    searchable = " ".join(
        part
        for part in [
            str(title or "").strip(),
            str(description or "").strip(),
            str(author_username or "").strip(),
            str(category or "").strip(),
            " ".join(str(tag) for tag in tags or []),
            taxonomy_text,
        ]
        if part
    ).lower()
    if query_text and query_text not in searchable:
        return False
    if author_filter and author_filter not in str(author_username or "").strip().lower():
        return False
    if category_filter and category_filter != str(category or "").strip().lower():
        return False
    if domain_filter and domain_filter != str(taxonomy.get("domain") or "").strip().lower():
        return False
    if subject_filter and subject_filter != str(taxonomy.get("subject") or "").strip().lower():
        return False
    if difficulty_filter and difficulty_filter != str(taxonomy.get("difficulty_band") or "").strip().lower():
        return False
    if framework_level_filter and framework_level_filter != str(taxonomy.get("framework_level") or "").strip().lower():
        return False
    if framework_track_filter and framework_track_filter != str(taxonomy.get("framework_track") or "").strip().lower():
        return False
    if audience_filter and audience_filter != str(taxonomy.get("audience") or "").strip().lower():
        return False
    normalized_tags = {str(tag).strip().lower() for tag in tags if str(tag).strip()}
    if tags_filter and not normalized_tags.intersection(tags_filter):
        return False
    normalized_goals = {str(item).strip().lower() for item in (taxonomy.get("learning_goals") or []) if str(item).strip()}
    if learning_goals_filter and not normalized_goals.intersection(learning_goals_filter):
        return False
    normalized_topics = {str(item).strip().lower() for item in (taxonomy.get("primary_topics") or []) if str(item).strip()}
    if primary_topics_filter and not normalized_topics.intersection(primary_topics_filter):
        return False
    normalized_features = {str(item).strip().lower() for item in (taxonomy.get("format_features") or []) if str(item).strip()}
    if format_features_filter and not normalized_features.intersection(format_features_filter):
        return False
    if pricing_filter in {"free", "paid"} and pricing_filter != pricing_mode:
        return False
    if has_preview_filter == "yes" and not has_preview:
        return False
    if has_preview_filter == "no" and has_preview:
        return False
    if min_price is not None and price_amount_minor < int(min_price):
        return False
    if max_price is not None and price_amount_minor > int(max_price):
        return False
    if min_rating is not None and float(rating_avg or 0.0) < float(min_rating):
        return False
    if popularity_filter and _popularity_bucket(install_count) != popularity_filter:
        return False
    return True


def _infer_market_levels(*texts: str | None, tags: list[str]) -> list[str]:
    haystack = " ".join(str(part or "") for part in texts).lower()
    haystack += " " + " ".join(str(tag or "") for tag in tags).lower()
    levels: list[str] = []
    if re.search(r"\bn5\b|jlpt\s*n5|beginner", haystack):
        levels.append("N5")
    if re.search(r"\bn4\b|jlpt\s*n4", haystack):
        levels.append("N4")
    if re.search(r"\bn3\b|jlpt\s*n3|intermediate", haystack):
        levels.append("N3")
    if re.search(r"\bn2\b|jlpt\s*n2", haystack):
        levels.append("N2")
    if re.search(r"\bn1\b|jlpt\s*n1|advanced", haystack):
        levels.append("N1")
    if "beginner" in haystack:
        levels.append("Beginner")
    if "intermediate" in haystack:
        levels.append("Intermediate")
    if "advanced" in haystack:
        levels.append("Advanced")
    dedup: list[str] = []
    seen: set[str] = set()
    for value in levels:
        if value in seen:
            continue
        seen.add(value)
        dedup.append(value)
    return dedup


def _build_badges(
    *,
    pricing_mode: str,
    is_official: bool,
    ownership_status: str,
    is_saved: bool,
) -> list[str]:
    badges: list[str] = []
    if is_official:
        badges.append("Official")
    if ownership_status == "owner":
        badges.append("Cua ban")
    elif ownership_status == "installed":
        badges.append("Da cai")
    elif ownership_status == "owned_pending":
        badges.append("Da mua")
    if is_saved and ownership_status not in {"owner", "installed"}:
        badges.append("Da luu")
    if pricing_mode == "free":
        badges.append("Mien phi")
    return badges[:4]


def _resolve_ownership_status(*, is_owner: bool, is_installed: bool, is_pending_owned: bool) -> str:
    if is_owner:
        return "owner"
    if is_installed:
        return "installed"
    if is_pending_owned:
        return "owned_pending"
    return "available"


def _primary_action(*, ownership_status: str) -> str:
    if ownership_status == "owner":
        return "edit"
    if ownership_status == "installed":
        return "installed"
    if ownership_status == "owned_pending":
        return "order"
    return "install"


def _primary_cta_label(*, ownership_status: str, pricing_mode: str) -> str:
    if ownership_status == "owner":
        return "Chinh sua"
    if ownership_status == "installed":
        return "Da cai"
    if ownership_status == "owned_pending":
        return "Xem don hang"
    if pricing_mode == "paid":
        return "Mua"
    return "Tai xuong"


def _popularity_bucket(install_count: int) -> str:
    if int(install_count or 0) >= 50:
        return "bestseller"
    if int(install_count or 0) >= 10:
        return "popular"
    return "emerging"


def _weighted_average_rating(items: list[Any]) -> float:
    weighted_total = 0.0
    count_total = 0
    for item in items:
        rating_count = int(getattr(item, "rating_count", 0) or 0)
        weighted_total += float(getattr(item, "rating_avg", 0.0) or 0.0) * rating_count
        count_total += rating_count
    return (weighted_total / count_total) if count_total > 0 else 0.0


def _normalize_product_type(raw_value: str | None) -> str:
    token = str(raw_value or "").strip().lower()
    if token not in SUPPORTED_PRODUCT_TYPES:
        raise ValueError("Unsupported marketplace product type.")
    return token


def _normalize_level(raw_value: Any) -> str:
    token = str(raw_value or "").strip().upper()
    return token if token in LEVEL_LABELS else ""


def _normalize_enum(raw_value: Any, allowed: set[str], *, default: str = "") -> str:
    token = str(raw_value or "").strip().lower()
    return token if token in allowed else default


def _clean_text(raw_value: Any, *, max_length: int) -> str:
    return str(raw_value or "").strip()[:max_length]


def _coerce_float(raw_value: Any, *, minimum: float, maximum: float) -> float | None:
    if raw_value in (None, ""):
        return None
    try:
        value = float(str(raw_value).strip())
    except (TypeError, ValueError):
        return None
    return max(minimum, min(maximum, value))


def _sorted_unique(values: Any) -> list[str]:
    cleaned = {str(value).strip() for value in values if str(value).strip()}
    return sorted(cleaned, key=lambda value: value.lower())


def _truncate_text(raw_value: Any, *, max_length: int) -> str:
    text = str(raw_value or "").strip()
    if len(text) <= max_length:
        return text
    return text[: max_length - 1].rstrip() + "..."
