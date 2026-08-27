"""Marketplace card item, library row, and review/feedback serialization."""

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
    payment_service,
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
    _build_badges,
    _clean_text,
    _infer_market_levels,
    _popularity_bucket,
    _primary_action,
    _primary_cta_label,
    _resolve_ownership_status,
    _truncate_text,
    _weighted_average_rating,
)

def _serialize_note_type_card(
    note_type: NoteType,
    *,
    user_id: int,
    install_map: dict[str, NoteTypeInstall],
    saved_ids: set[str],
    pending_owned_ids: set[str],
) -> dict[str, Any]:
    payload = marketplace_query_service.serialize_note_type_marketplace_card(
        note_type,
        include_definition=False,
    )
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



def _deck_install_sort_key(install: DeckInstall) -> tuple[datetime, datetime, str]:
    return (
        install.last_activity_at or datetime.min,
        install.installed_at or datetime.min,
        str(install.id or ""),
    )



def _serialize_deck_install_library_row(
    *,
    deck_item: DeckMarketplaceItem,
    install: DeckInstall,
    user_id: int,
    install_map: dict[str, DeckInstall],
    saved_ids: set[str],
) -> dict[str, Any]:
    payload = _serialize_deck_card(
        deck_item,
        user_id=user_id,
        install_map=install_map,
        saved_ids=saved_ids,
        pending_owned_ids=set(),
    )
    applied_release = install.applied_release
    available_release = deck_item.current_release
    applied_sequence = int(applied_release.sequence_no or 0) if applied_release else 0
    available_sequence = int(available_release.sequence_no or 0) if available_release else 0
    update_available = available_sequence > applied_sequence
    payload.update(
        {
            "deck_install_id": install.id,
            "last_sync_status": str(install.last_sync_status or "").strip().lower() or None,
            "version_mode": install.version_mode,
            "overlay_revision": int(install.overlay_revision or 0),
            "applied_release": (
                {
                    "id": applied_release.id,
                    "sequence_no": applied_sequence,
                    "version_label": applied_release.version_label,
                }
                if applied_release
                else None
            ),
            "available_release": (
                {
                    "id": available_release.id,
                    "sequence_no": available_sequence,
                    "version_label": available_release.version_label,
                    "published_at": (
                        available_release.published_at.isoformat()
                        if available_release.published_at
                        else None
                    ),
                }
                if available_release
                else None
            ),
            "update_available": update_available,
            "unread_update": bool(
                update_available
                and str(install.seen_release_id or "")
                != str(available_release.id if available_release else "")
            ),
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
    now = _utcnow()
    install_map = {row.source_note_type_id: row for row in installs}
    source_ids = list(install_map.keys()) or [""]
    note_types = {
        item.id: item
        for item in (
            NoteType.query.options(joinedload(NoteType.owner))
            .filter(NoteType.id.in_(source_ids))
            .all()
        )
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
        if flashcards_share_service.is_note_type_install_active(install, now=now):
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
        for item in (
            NoteType.query.options(joinedload(NoteType.owner))
            .filter(NoteType.id.in_(list(not_installed_ids) or [""]))
            .all()
        )
    ]
    saved_items = [
        _serialize_note_type_card(
            item,
            user_id=user_id,
            install_map=install_map,
            saved_ids=saved_ids,
            pending_owned_ids=set(),
        )
        for item in (
            NoteType.query.options(joinedload(NoteType.owner))
            .filter(NoteType.id.in_(list(saved_ids) or [""]))
            .all()
        )
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
        for item in (
            DeckMarketplaceItem.query.options(
                joinedload(DeckMarketplaceItem.current_release)
            )
            .filter(DeckMarketplaceItem.id.in_(source_ids))
            .all()
        )
    }
    using_now: list[dict[str, Any]] = []
    installed: list[dict[str, Any]] = []
    for install in sorted(
        installs,
        key=_deck_install_sort_key,
        reverse=True,
    ):
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
        NoteType.query.options(joinedload(NoteType.owner))
        .filter_by(user_id=user_id)
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



