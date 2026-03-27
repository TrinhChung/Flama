"""Marketplace and serialization controllers for flashcards routes."""

from __future__ import annotations

import random
import re
from datetime import datetime
from typing import Any

from app.repositories.deck_tree_query import collect_subtree_ids
from app.template_formatters import format_vnd
from models import db
from models.flashcard import DeckInstall, DeckMarketplaceItem, FieldDef, Note, NoteType, Template


def serialize_author(user_obj: Any) -> dict[str, Any]:
    if not user_obj:
        return {"id": None, "username": "Unknown"}
    return {
        "id": user_obj.id,
        "username": user_obj.username,
    }


def serialize_field(field: FieldDef) -> dict[str, Any]:
    return {
        "id": field.id,
        "note_type_id": field.note_type_id,
        "name": field.name,
        "field_type": field.field_type,
        "position": field.position,
        "required": bool(field.required),
    }


def serialize_template(template: Template) -> dict[str, Any]:
    return {
        "id": template.id,
        "note_type_id": template.note_type_id,
        "name": template.name,
        "front_html": template.front_html,
        "back_html": template.back_html,
        "shared_css": template.shared_css,
        "position": template.position,
        "is_default": bool(template.is_default),
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def serialize_note_type(note_type: NoteType) -> dict[str, Any]:
    price_amount_minor = int(note_type.price_amount_minor or 0)
    return {
        "id": note_type.id,
        "name": note_type.name,
        "title": note_type.name,
        "description": note_type.description,
        "primary_category": note_type.primary_category,
        "tags": note_type.tags or [],
        "preview_text": note_type.preview_text,
        "preview_image_url": note_type.preview_image_url,
        "pricing_mode": note_type.pricing_mode,
        "price_amount_minor": price_amount_minor,
        "price_cents": price_amount_minor,
        "version": note_type.version,
        "changelog": note_type.changelog,
        "publish_status": note_type.publish_status,
        "is_official": bool(note_type.is_official),
        "published_at": note_type.published_at.isoformat() if note_type.published_at else None,
        "archived_at": note_type.archived_at.isoformat() if note_type.archived_at else None,
        "install_count": int(note_type.install_count or 0),
        "active_usage_count": int(note_type.active_usage_count or 0),
        "rating_avg": float(note_type.rating_avg or 0.0),
        "rating_count": int(note_type.rating_count or 0),
        "author": serialize_author(note_type.owner),
        "created_at": note_type.created_at.isoformat() if note_type.created_at else None,
        "updated_at": note_type.updated_at.isoformat() if note_type.updated_at else None,
        "field_defs": [
            serialize_field(field)
            for field in sorted(note_type.field_defs, key=lambda item: item.position)
        ],
        "templates": [
            serialize_template(template)
            for template in sorted(note_type.templates, key=lambda item: item.position)
        ],
    }


def normalize_tags(raw_tags: Any) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, list):
        return [str(item).strip() for item in raw_tags if str(item).strip()]
    if isinstance(raw_tags, str):
        return [item.strip() for item in raw_tags.split(",") if item.strip()]
    return []


def normalize_marketplace_tags(raw_tags: Any) -> list[str]:
    normalized = normalize_tags(raw_tags)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        dedup.append(item)
    return dedup


def parse_price_amount_minor(raw_price: Any) -> int | None:
    if raw_price in (None, ""):
        return None
    if isinstance(raw_price, bool):
        return None
    if isinstance(raw_price, int):
        return raw_price
    if isinstance(raw_price, float):
        return int(raw_price) if raw_price.is_integer() else None
    text = str(raw_price).strip()
    if not text:
        return None
    normalized = re.sub(r"(?i)\s*(vnđ|vnd|₫)\s*$", "", text).strip()
    if not normalized:
        return None
    compact = re.sub(r"\s+", "", normalized)
    if re.fullmatch(r"[-+]?\d+", compact):
        try:
            return int(compact)
        except ValueError:
            return None
    if re.fullmatch(r"[-+]?\d{1,3}(?:[.,]\d{3})+", compact):
        try:
            return int(compact.replace(".", "").replace(",", ""))
        except ValueError:
            return None
    return None


def parse_price_cents(raw_price: Any) -> int | None:
    return parse_price_amount_minor(raw_price)


def normalize_pricing(
    payload: dict[str, Any],
    *,
    current_mode: str,
    current_price_amount_minor: int,
) -> tuple[str, int, str | None]:
    mode_raw = payload.get("pricing_mode", payload.get("pricing"))
    mode = current_mode
    if mode_raw is not None:
        mode_candidate = str(mode_raw).strip().lower()
        if mode_candidate not in {"free", "paid"}:
            return mode, current_price_amount_minor, "pricing_mode must be 'free' or 'paid'."
        mode = mode_candidate

    price_amount_minor = current_price_amount_minor
    if "price_amount_minor" in payload:
        parsed_price = parse_price_amount_minor(payload.get("price_amount_minor"))
        if parsed_price is None:
            return mode, current_price_amount_minor, "price_amount_minor is invalid."
        price_amount_minor = parsed_price
    elif "price_cents" in payload:
        parsed_price = parse_price_amount_minor(payload.get("price_cents"))
        if parsed_price is None:
            return mode, current_price_amount_minor, "price_amount_minor is invalid."
        price_amount_minor = parsed_price
    elif "price" in payload:
        parsed_price = parse_price_amount_minor(payload.get("price"))
        if parsed_price is None:
            return mode, current_price_amount_minor, "price is invalid."
        price_amount_minor = parsed_price

    if mode == "free":
        return mode, 0, None
    if price_amount_minor <= 0:
        return mode, price_amount_minor, "Paid items must have price > 0."
    return mode, price_amount_minor, None


def _format_marketplace_price_display(pricing_mode: str, amount_minor: int) -> str:
    if pricing_mode == "free":
        return "Miễn phí"
    return format_vnd(amount_minor)


def serialize_note_type_marketplace_card(note_type: NoteType) -> dict[str, Any]:
    payload = serialize_note_type(note_type)
    payload["price_display"] = _format_marketplace_price_display(
        str(note_type.pricing_mode or "free"),
        int(note_type.price_amount_minor or 0),
    )
    return payload


def serialize_deck_marketplace_item(deck_item: DeckMarketplaceItem) -> dict[str, Any]:
    price_amount_minor = int(deck_item.price_amount_minor or 0)
    return {
        "id": deck_item.id,
        "title": deck_item.title,
        "description": deck_item.description,
        "primary_category": deck_item.primary_category,
        "tags": deck_item.tags or [],
        "preview_text": deck_item.preview_text,
        "sample_cards_count": int(deck_item.sample_cards_count or 0),
        "source_deck_id": deck_item.source_deck_id,
        "source_note_type_id": deck_item.source_note_type_id,
        "pricing_mode": deck_item.pricing_mode,
        "price_amount_minor": price_amount_minor,
        "price_cents": price_amount_minor,
        "price_display": _format_marketplace_price_display(
            str(deck_item.pricing_mode or "free"),
            price_amount_minor,
        ),
        "version": deck_item.version,
        "changelog": deck_item.changelog,
        "publish_status": deck_item.publish_status,
        "is_official": bool(deck_item.is_official),
        "install_count": int(deck_item.install_count or 0),
        "active_usage_count": int(deck_item.active_usage_count or 0),
        "rating_avg": float(deck_item.rating_avg or 0.0),
        "rating_count": int(deck_item.rating_count or 0),
        "author": serialize_author(deck_item.owner),
        "published_at": deck_item.published_at.isoformat() if deck_item.published_at else None,
        "archived_at": deck_item.archived_at.isoformat() if deck_item.archived_at else None,
        "updated_at": deck_item.updated_at.isoformat() if deck_item.updated_at else None,
        "created_at": deck_item.created_at.isoformat() if deck_item.created_at else None,
    }


def first_non_empty_field_text(field_values: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key not in field_values:
            continue
        candidate = field_values.get(key)
        if candidate is None:
            continue
        text = str(candidate).strip()
        if text:
            return text
    return ""


def serialize_note_test_sample(note: Note) -> dict[str, Any] | None:
    field_values = note.field_values if isinstance(note.field_values, dict) else {}

    word = first_non_empty_field_text(
        field_values,
        ["Word", "word", "Term", "term", "Vocabulary", "vocabulary"],
    )
    if not word:
        for raw_value in field_values.values():
            if raw_value is None:
                continue
            text = str(raw_value).strip()
            if text:
                word = text
                break
    if not word:
        return None

    reading = first_non_empty_field_text(
        field_values,
        ["Reading", "reading", "Kana", "kana", "Yomigana", "yomigana"],
    )
    meaning = first_non_empty_field_text(
        field_values,
        [
            "Meaning",
            "meaning",
            "Meaning_VI",
            "meaning_vi",
            "Meaning_JP",
            "meaning_jp",
            "Translation_VI",
            "translation_vi",
        ],
    )

    return {
        "note_id": note.id,
        "word": word,
        "reading": reading,
        "meaning": meaning,
    }


def build_shared_deck_test_samples(
    deck_item: DeckMarketplaceItem,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    if limit <= 0:
        return []
    if deck_item.source_deck_id is None:
        return []

    deck_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not deck_ids:
        return []

    note_query = Note.query.filter(Note.deck_id.in_(deck_ids))
    if deck_item.owner_user_id is not None:
        note_query = note_query.filter(Note.user_id == deck_item.owner_user_id)
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if source_note_type_id:
        note_query = note_query.filter(Note.note_type_id == source_note_type_id)

    note_candidates: list[dict[str, Any]] = []
    for note in note_query.all():
        sample = serialize_note_test_sample(note)
        if sample is not None:
            note_candidates.append(sample)

    if not note_candidates:
        return []

    random.shuffle(note_candidates)
    return note_candidates[:limit]


def item_matches_search(query_text: str, *values: str | None) -> bool:
    if not query_text:
        return True
    lowered = query_text.lower()
    for value in values:
        if value and lowered in value.lower():
            return True
    return False


def filter_note_type_items(
    note_types: list[NoteType],
    *,
    query_text: str,
    category: str,
    tags: set[str],
    pricing_mode: str,
    min_price_amount_minor: int | None,
    max_price_amount_minor: int | None,
) -> list[NoteType]:
    filtered: list[NoteType] = []
    for note_type in note_types:
        if not item_matches_search(query_text, note_type.name, note_type.description):
            continue
        if category and (note_type.primary_category or "").strip().lower() != category.lower():
            continue
        item_tags = {tag.lower() for tag in (note_type.tags or [])}
        if tags and not tags.intersection(item_tags):
            continue
        if pricing_mode in {"free", "paid"} and note_type.pricing_mode != pricing_mode:
            continue
        price_value = int(note_type.price_amount_minor or 0)
        if min_price_amount_minor is not None and price_value < min_price_amount_minor:
            continue
        if max_price_amount_minor is not None and price_value > max_price_amount_minor:
            continue
        filtered.append(note_type)
    return filtered


def filter_deck_items(
    deck_items: list[DeckMarketplaceItem],
    *,
    query_text: str,
    category: str,
    tags: set[str],
    pricing_mode: str,
    min_price_amount_minor: int | None,
    max_price_amount_minor: int | None,
) -> list[DeckMarketplaceItem]:
    filtered: list[DeckMarketplaceItem] = []
    for deck_item in deck_items:
        if not item_matches_search(query_text, deck_item.title, deck_item.description):
            continue
        if category and (deck_item.primary_category or "").strip().lower() != category.lower():
            continue
        item_tags = {tag.lower() for tag in (deck_item.tags or [])}
        if tags and not tags.intersection(item_tags):
            continue
        if pricing_mode in {"free", "paid"} and deck_item.pricing_mode != pricing_mode:
            continue
        price_value = int(deck_item.price_amount_minor or 0)
        if min_price_amount_minor is not None and price_value < min_price_amount_minor:
            continue
        if max_price_amount_minor is not None and price_value > max_price_amount_minor:
            continue
        filtered.append(deck_item)
    return filtered


def sort_note_type_items(items: list[NoteType], sort_key: str) -> list[NoteType]:
    key = (sort_key or "popular").strip().lower()
    if key == "top_rated":
        return sorted(
            items,
            key=lambda item: (
                float(item.rating_avg or 0.0),
                int(item.rating_count or 0),
                int(item.active_usage_count or 0),
            ),
            reverse=True,
        )
    if key == "newest":
        return sorted(items, key=lambda item: (item.created_at or datetime.min), reverse=True)
    if key == "recently_updated":
        return sorted(items, key=lambda item: (item.updated_at or datetime.min), reverse=True)
    return sorted(
        items,
        key=lambda item: (
            int(item.active_usage_count or 0),
            int(item.install_count or 0),
            float(item.rating_avg or 0.0),
        ),
        reverse=True,
    )


def sort_deck_items(items: list[DeckMarketplaceItem], sort_key: str) -> list[DeckMarketplaceItem]:
    key = (sort_key or "popular").strip().lower()
    if key == "top_rated":
        return sorted(
            items,
            key=lambda item: (
                float(item.rating_avg or 0.0),
                int(item.rating_count or 0),
                int(item.active_usage_count or 0),
            ),
            reverse=True,
        )
    if key == "newest":
        return sorted(items, key=lambda item: (item.created_at or datetime.min), reverse=True)
    if key == "recently_updated":
        return sorted(items, key=lambda item: (item.updated_at or datetime.min), reverse=True)
    return sorted(
        items,
        key=lambda item: (
            int(item.active_usage_count or 0),
            int(item.install_count or 0),
            float(item.rating_avg or 0.0),
        ),
        reverse=True,
    )


def collect_user_market_interests(user_id: int) -> tuple[set[str], set[str]]:
    categories: set[str] = set()
    tags: set[str] = set()

    user_note_types = (
        db.session.query(NoteType)
        .join(Note, Note.note_type_id == NoteType.id)
        .filter(Note.user_id == user_id)
        .all()
    )
    for note_type in user_note_types:
        if note_type.primary_category:
            categories.add(note_type.primary_category.strip().lower())
        for tag in note_type.tags or []:
            tags.add(str(tag).strip().lower())

    user_notes = Note.query.filter_by(user_id=user_id).all()
    for note in user_notes:
        for tag in note.tags or []:
            tags.add(str(tag).strip().lower())

    deck_installs = DeckInstall.query.filter_by(user_id=user_id).all()
    if deck_installs:
        deck_item_ids = [row.deck_item_id for row in deck_installs]
        deck_items = DeckMarketplaceItem.query.filter(DeckMarketplaceItem.id.in_(deck_item_ids)).all()
        for deck_item in deck_items:
            if deck_item.primary_category:
                categories.add(deck_item.primary_category.strip().lower())
            for tag in deck_item.tags or []:
                tags.add(str(tag).strip().lower())

    return categories, tags


def score_market_item(
    *,
    item_category: str | None,
    item_tags: list[str] | None,
    rating_avg: float,
    rating_count: int,
    active_usage_count: int,
    install_count: int,
    updated_at: datetime | None,
    interests_categories: set[str],
    interests_tags: set[str],
    is_official: bool,
    cold_start: bool,
    recency_window_days: int = 30,
) -> float:
    category_match = (
        1.0 if item_category and item_category.strip().lower() in interests_categories else 0.0
    )
    normalized_item_tags = {
        tag.strip().lower()
        for tag in (item_tags or [])
        if str(tag).strip()
    }
    overlap_count = len(normalized_item_tags.intersection(interests_tags))
    tag_match = min(1.0, overlap_count / 3) if normalized_item_tags else 0.0
    rating_score = (float(rating_avg or 0.0) / 5.0) * min(1.0, int(rating_count or 0) / 20)
    usage_score = min(1.0, int(active_usage_count or 0) / 100) * 0.7 + min(
        1.0, int(install_count or 0) / 200
    ) * 0.3
    days_since_update = (
        (datetime.utcnow() - updated_at).days
        if updated_at is not None
        else recency_window_days
    )
    recency_score = max(0.0, 1 - (days_since_update / recency_window_days))

    score = (
        category_match * 3.0
        + tag_match * 2.0
        + rating_score * 2.0
        + usage_score * 2.0
        + recency_score * 1.0
    )
    if cold_start and is_official:
        score += 2.5
    return score


def top_items_by_category_note_types(
    items: list[NoteType],
    *,
    limit_per_category: int = 5,
    max_categories: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[NoteType]] = {}
    for item in items:
        category = (item.primary_category or "General").strip()
        buckets.setdefault(category, []).append(item)

    ranked_categories = sorted(
        buckets.keys(),
        key=lambda category: max(
            (
                (bucket_item.active_usage_count or 0, bucket_item.rating_avg or 0.0)
                for bucket_item in buckets[category]
            ),
            default=(0, 0.0),
        ),
        reverse=True,
    )[:max_categories]

    result: dict[str, list[dict[str, Any]]] = {}
    for category in ranked_categories:
        sorted_bucket = sort_note_type_items(buckets[category], "popular")[:limit_per_category]
        result[category] = [serialize_note_type_marketplace_card(item) for item in sorted_bucket]
    return result


def top_items_by_category_decks(
    items: list[DeckMarketplaceItem],
    *,
    limit_per_category: int = 5,
    max_categories: int = 3,
) -> dict[str, list[dict[str, Any]]]:
    buckets: dict[str, list[DeckMarketplaceItem]] = {}
    for item in items:
        category = (item.primary_category or "General").strip()
        buckets.setdefault(category, []).append(item)

    ranked_categories = sorted(
        buckets.keys(),
        key=lambda category: max(
            (
                (bucket_item.active_usage_count or 0, bucket_item.rating_avg or 0.0)
                for bucket_item in buckets[category]
            ),
            default=(0, 0.0),
        ),
        reverse=True,
    )[:max_categories]

    result: dict[str, list[dict[str, Any]]] = {}
    for category in ranked_categories:
        sorted_bucket = sort_deck_items(buckets[category], "popular")[:limit_per_category]
        result[category] = [serialize_deck_marketplace_item(item) for item in sorted_bucket]
    return result


def parse_query_price_amount_minor(raw_value: Any) -> int | None:
    if raw_value is None:
        return None
    text = str(raw_value).strip()
    if not text:
        return None
    parsed = parse_price_amount_minor(text)
    if parsed is None:
        return None
    return max(0, parsed)


def parse_query_price_cents(raw_value: Any) -> int | None:
    return parse_query_price_amount_minor(raw_value)

def get_visible_note_types(user_id: int) -> list[NoteType]:
    from app.services import flashcards_share as flashcards_share
    return [
        item
        for item in NoteType.query.order_by(NoteType.updated_at.desc()).all()
        if flashcards_share.is_note_type_visible_for_shared(item, user_id, flashcards_share.PUBLISH_STATUSES_VISIBLE)
    ]

def get_visible_deck_items(user_id: int) -> list[DeckMarketplaceItem]:
    from app.services import flashcards_share as flashcards_share
    return [
        item
        for item in DeckMarketplaceItem.query.order_by(DeckMarketplaceItem.updated_at.desc()).all()
        if flashcards_share.is_deck_item_visible_for_shared(item, user_id, flashcards_share.PUBLISH_STATUSES_VISIBLE)
    ]

def get_note_type_recommendations(user_id: int, visible_items: list[NoteType]) -> dict[str, Any]:
    from app.services import flashcards_share as flashcards_share
    from models.flashcard import NoteTypeInstall
    from models import db
    from datetime import timedelta
    
    interests_categories, interests_tags = collect_user_market_interests(user_id)
    cold_start = not interests_categories and not interests_tags

    scored = []
    for item in visible_items:
        if item.user_id == user_id:
            continue
        score = score_market_item(
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
        scored.append((score, item))

    recommended = [
        serialize_note_type_marketplace_card(item)
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:12]
    ]

    trending_cutoff = datetime.utcnow() - timedelta(days=flashcards_share.TRENDING_WINDOW_DAYS)
    trending_counts_raw = (
        db.session.query(NoteTypeInstall.source_note_type_id, db.func.count(NoteTypeInstall.id))
        .filter(NoteTypeInstall.installed_at >= trending_cutoff)
        .group_by(NoteTypeInstall.source_note_type_id)
        .all()
    )
    trending_counts = {row[0]: int(row[1] or 0) for row in trending_counts_raw}

    trending = sorted(
        visible_items,
        key=lambda item: (
            trending_counts.get(item.id, 0),
            int(item.active_usage_count or 0),
            int(item.install_count or 0),
        ),
        reverse=True,
    )[:12]

    new_and_updated = sort_note_type_items(visible_items, "recently_updated")[:12]

    return {
        "recommended_for_you": recommended,
        "top_by_category": top_items_by_category_note_types(visible_items),
        "trending": [serialize_note_type_marketplace_card(item) for item in trending],
        "new_and_updated": [serialize_note_type_marketplace_card(item) for item in new_and_updated],
    }

def get_deck_recommendations(user_id: int, visible_items: list[DeckMarketplaceItem]) -> dict[str, Any]:
    from app.services import flashcards_share as flashcards_share
    from models.flashcard import DeckInstall
    from models import db
    from datetime import timedelta
    
    interests_categories, interests_tags = collect_user_market_interests(user_id)
    cold_start = not interests_categories and not interests_tags

    scored = []
    for item in visible_items:
        if item.owner_user_id == user_id:
            continue
        score = score_market_item(
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
        scored.append((score, item))

    recommended = [
        serialize_deck_marketplace_item(item)
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:12]
    ]

    trending_cutoff = datetime.utcnow() - timedelta(days=flashcards_share.TRENDING_WINDOW_DAYS)
    trending_counts_raw = (
        db.session.query(DeckInstall.deck_item_id, db.func.count(DeckInstall.id))
        .filter(DeckInstall.installed_at >= trending_cutoff)
        .group_by(DeckInstall.deck_item_id)
        .all()
    )
    trending_counts = {row[0]: int(row[1] or 0) for row in trending_counts_raw}

    trending = sorted(
        visible_items,
        key=lambda item: (
            trending_counts.get(item.id, 0),
            int(item.active_usage_count or 0),
            int(item.install_count or 0),
        ),
        reverse=True,
    )[:12]

    new_and_updated = sort_deck_items(visible_items, "recently_updated")[:12]

    return {
        "recommended_for_you": recommended,
        "top_by_category": top_items_by_category_decks(visible_items),
        "trending": [serialize_deck_marketplace_item(item) for item in trending],
        "new_and_updated": [serialize_deck_marketplace_item(item) for item in new_and_updated],
    }
