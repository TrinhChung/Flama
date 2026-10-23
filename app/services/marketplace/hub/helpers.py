"""Marketplace hub normalization, badges, actions, and filters matching."""

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


def _clean_text(raw_value: Any, *, max_length: int) -> str:
    return str(raw_value or "").strip()[:max_length]



def _normalize_enum(raw_value: Any, allowed: set[str], *, default: str = "") -> str:
    token = str(raw_value or "").strip().lower()
    return token if token in allowed else default



def _normalize_level(raw_value: Any) -> str:
    token = str(raw_value or "").strip().upper()
    return token if token in LEVEL_LABELS else ""



def _normalize_product_type(raw_value: str | None) -> str:
    token = str(raw_value or "").strip().lower()
    if token not in SUPPORTED_PRODUCT_TYPES:
        raise ValueError("Unsupported marketplace product type.")
    return token



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



