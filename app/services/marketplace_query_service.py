"""Marketplace and serialization controllers for flashcards routes."""

from __future__ import annotations

import json
import random
import re
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from typing import Any

from flask import current_app, has_app_context

UTC = timezone.utc
SHARED_DECK_SAMPLE_CACHE_MAX_BYTES = 16 * 1024

from app.repositories.deck_tree_query import collect_subtree_ids
from app.repositories import flashcards_share_repository, template_release_repository
from app.template_formatters import format_vnd
from app.services import marketplace_taxonomy_service
from models import db
from models.field_types import field_value_text
from models.flashcard import Card, Deck, DeckInstall, DeckMarketplaceItem, FieldDef, Note, NoteType, Template


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def serialize_author(user_obj: Any) -> dict[str, Any]:
    if not user_obj:
        return {"id": None, "username": "Unknown", "display_name": "Unknown", "avatar_url": None}
    return {
        "id": user_obj.id,
        "username": user_obj.username,
        "display_name": getattr(user_obj, "display_name", None) or user_obj.username,
        "avatar_url": getattr(user_obj, "avatar_url", None),
    }


def serialize_field(field: FieldDef) -> dict[str, Any]:
    return {
        "id": field.id,
        "note_type_id": field.note_type_id,
        "name": field.name,
        "field_type": field.field_type,
        "position": field.position,
        "required": bool(field.required),
        "identity_role": getattr(field, "identity_role", None),
    }


def serialize_template(template: Template, *, application=None, note_type_id=None) -> dict[str, Any]:
    application = application or getattr(template, 'application', None)
    template = getattr(template, 'template', template)
    return {
        "id": template.id,
        "note_type_id": application.note_type_id if application is not None else note_type_id,
        "application_id": application.id if application is not None else None,
        "name": template.name,
        "front_html": template.front_html,
        "back_html": template.back_html,
        "shared_css": template.shared_css,
        "position": application.position if application is not None else 0,
        "is_default": bool(application.is_default) if application is not None else False,
        "input_schema": template.input_schema or [],
        "input_bindings": application.input_bindings or {} if application is not None else {},
        "current_version_id": template.current_version_id,
        "updated_at": template.updated_at.isoformat() if template.updated_at else None,
    }


def serialize_note_type_templates(note_type: NoteType, *, published=False):
    if not note_type.id or not has_app_context():
        return [serialize_template(app.template, application=app)
                for app in sorted(note_type.study_applications, key=lambda app: (app.position, app.id or ''))
                if app.status_code == 'ACTIVE']
    attached = flashcards_share_repository.get_template_applications_by_note_type(note_type.id)
    result = []
    for template, app in attached:
        payload = serialize_template(template, application=app)
        if published:
            publication = template_release_repository.publication(db.session, template.id)
            release = template_release_repository.release(db.session, publication["current_release_id"], template.id) if publication and publication["current_release_id"] else None
            content = template_release_repository.version(db.session, release["version_id"], template.id) if release else None
            if content:
                payload.update(**{key: content[key] for key in ("front_html", "back_html", "shared_css", "input_schema")}, current_version_id=content["id"])
        result.append(payload)
    return result


def serialize_note_type(
    note_type: NoteType,
    *,
    include_definition: bool = True,
    published_template_content: bool = False,
) -> dict[str, Any]:
    price_amount_minor = int(note_type.price_amount_minor or 0)
    definition = None
    if published_template_content:
        from app.services.note_type_release_service import released_definition
        definition = released_definition(db.session, note_type, include_definition=include_definition)
    taxonomy_item = SimpleNamespace(**definition) if definition and definition["release_available"] else note_type
    taxonomy_metadata = marketplace_taxonomy_service.get_item_taxonomy(taxonomy_item, content_type="note_type")
    taxonomy_display = marketplace_taxonomy_service.build_taxonomy_display(taxonomy_metadata, content_type="note_type")
    payload = {
        "id": note_type.id,
        "field_schema_revision": int(note_type.field_schema_revision or 0),
        "name": note_type.name,
        "title": note_type.name,
        "description": note_type.description,
        "primary_category": note_type.primary_category,
        "tags": note_type.tags or [],
        "display_tags": marketplace_taxonomy_service.merge_detail_tags(
            free_tags=taxonomy_item.tags or [],
            metadata=taxonomy_metadata,
            content_type="note_type",
        ),
        "taxonomy_metadata": taxonomy_metadata,
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
        **taxonomy_display,
    }
    if include_definition and not published_template_content:
        payload["field_defs"] = [
            serialize_field(field)
            for field in sorted(note_type.field_defs, key=lambda item: item.position)
        ]
        payload["templates"] = serialize_note_type_templates(note_type, published=published_template_content)
    if definition is not None:
        if not include_definition:
            definition.pop("field_defs", None)
            definition.pop("templates", None)
        payload.update(definition)
        payload["taxonomy_metadata"] = taxonomy_metadata
    return payload


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
    mode = str(pricing_mode or "free").strip().lower()
    if mode == "course_key":
        return "Mã khóa học"
    if mode == "free":
        return "Miễn phí"
    return format_vnd(amount_minor)


def serialize_note_type_marketplace_card(
    note_type: NoteType,
    *,
    include_definition: bool = True,
    user_id: int = 0,
) -> dict[str, Any]:
    payload = serialize_note_type(
        note_type,
        include_definition=include_definition,
        published_template_content=True,
    )
    from app.services.note_type_bundle_pricing_service import pricing_breakdown
    breakdown = pricing_breakdown(db.session, note_type=note_type, user_id=user_id)
    payload["bundle_pricing_mode"] = str(note_type.pricing_mode or "free")
    payload["bundle_price_amount_minor"] = breakdown["bundle_amount_minor"]
    payload["pricing_breakdown"] = breakdown
    payload["pricing_mode"] = "paid" if breakdown["payment_required"] else "free"
    payload["price_amount_minor"] = payload["price_cents"] = breakdown["total_amount_minor"]
    payload["price_display"] = _format_marketplace_price_display(payload["pricing_mode"], breakdown["total_amount_minor"])
    template_prices = {item["template_id"]: item for item in breakdown["templates"]}
    for template in payload.get("templates", []):
        price = template_prices.get(template["id"])
        if price:
            template.update({key: price[key] for key in ("source_template_id", "author", "pricing_mode",
                "price_amount_minor", "already_entitled", "is_owned_by_author")})
    return payload


def compute_deck_item_stats(deck_item: DeckMarketplaceItem) -> dict[str, Any]:
    if deck_item.source_deck_id is None:
        return {
            "note_count": 0,
            "card_count": 0,
            "lesson_count": 0,
            "total_decks": 0,
            "has_subdecks": False,
        }

    subtree_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not subtree_ids:
        return {
            "note_count": 0,
            "card_count": 0,
            "lesson_count": 0,
            "total_decks": 0,
            "has_subdecks": False,
        }

    total_decks = len(subtree_ids)
    has_subdecks = total_decks > 1
    lesson_count = (total_decks - 1) if has_subdecks else 1

    note_query = db.session.query(db.func.count(Note.id)).filter(Note.deck_id.in_(subtree_ids))
    if deck_item.owner_user_id is not None:
        note_query = note_query.filter(Note.user_id == deck_item.owner_user_id)
    note_count = note_query.scalar() or 0

    card_query = (
        db.session.query(db.func.count(Card.id))
        .join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(subtree_ids))
    )
    if deck_item.owner_user_id is not None:
        card_query = card_query.filter(Note.user_id == deck_item.owner_user_id)
    card_count = card_query.scalar() or 0
    if card_count == 0 and note_count > 0:
        card_count = note_count

    return {
        "note_count": int(note_count),
        "card_count": int(card_count),
        "lesson_count": int(lesson_count),
        "total_decks": int(total_decks),
        "has_subdecks": bool(has_subdecks),
    }


def batch_compute_deck_items_stats(
    deck_items: list[DeckMarketplaceItem],
) -> dict[str, dict[str, Any]]:
    stats_by_item_id: dict[str, dict[str, Any]] = {}
    item_by_source_deck: dict[int, list[DeckMarketplaceItem]] = {}
    all_source_deck_ids: list[int] = []

    for item in deck_items:
        stats_by_item_id[item.id] = {
            "note_count": 0,
            "card_count": 0,
            "lesson_count": 0,
            "total_decks": 0,
            "has_subdecks": False,
        }
        if item.source_deck_id is not None:
            item_by_source_deck.setdefault(item.source_deck_id, []).append(item)
            all_source_deck_ids.append(item.source_deck_id)

    if not all_source_deck_ids:
        return stats_by_item_id

    deck_subtrees = _collect_subtree_ids_by_root(set(item_by_source_deck))
    all_subtree_ids = {
        deck_id
        for subtree_ids in deck_subtrees.values()
        for deck_id in subtree_ids
    }

    if not all_subtree_ids:
        return stats_by_item_id

    note_counts_raw = (
        db.session.query(Note.deck_id, Note.user_id, db.func.count(Note.id))
        .filter(Note.deck_id.in_(all_subtree_ids))
        .group_by(Note.deck_id, Note.user_id)
        .all()
    )
    note_count_map: dict[tuple[int, int | None], int] = {}
    for d_id, u_id, count in note_counts_raw:
        deck_id = int(d_id)
        normalized_user_id = int(u_id) if u_id is not None else None
        normalized_count = int(count or 0)
        note_count_map[(deck_id, normalized_user_id)] = normalized_count

    card_counts_raw = (
        db.session.query(Note.deck_id, Note.user_id, db.func.count(Card.id))
        .join(Card, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(all_subtree_ids))
        .group_by(Note.deck_id, Note.user_id)
        .all()
    )
    card_count_map: dict[tuple[int, int | None], int] = {}
    for d_id, u_id, count in card_counts_raw:
        deck_id = int(d_id)
        normalized_user_id = int(u_id) if u_id is not None else None
        normalized_count = int(count or 0)
        card_count_map[(deck_id, normalized_user_id)] = normalized_count

    for source_id, items in item_by_source_deck.items():
        sub_ids = deck_subtrees.get(source_id, [])
        total_decks = len(sub_ids)
        has_subdecks = total_decks > 1
        lesson_count = (total_decks - 1) if has_subdecks else (1 if total_decks == 1 else 0)

        for item in items:
            total_notes = 0
            total_cards = 0
            owner_id = item.owner_user_id
            for d_id in sub_ids:
                total_notes += note_count_map.get((d_id, owner_id), 0)
                total_cards += card_count_map.get((d_id, owner_id), 0)

            if total_cards == 0 and total_notes > 0:
                total_cards = total_notes

            stats_by_item_id[item.id] = {
                "note_count": int(total_notes),
                "card_count": int(total_cards),
                "lesson_count": int(lesson_count),
                "total_decks": int(total_decks),
                "has_subdecks": bool(has_subdecks),
            }

    return stats_by_item_id


def _collect_subtree_ids_by_root(root_ids: set[int]) -> dict[int, list[int]]:
    """Collect many deck subtrees with one SELECT per tree depth.

    A deck can itself be the root of one listing and a descendant of another,
    so the frontier carries every listing root that owns each discovered node.
    """
    normalized_roots = {int(root_id) for root_id in root_ids}
    descendants = {root_id: {root_id} for root_id in normalized_roots}
    frontier: dict[int, set[int]] = {
        root_id: {root_id} for root_id in normalized_roots
    }

    while frontier:
        child_rows = (
            db.session.query(Deck.id, Deck.parent_id)
            .filter(Deck.parent_id.in_(frontier))
            .all()
        )
        next_frontier: dict[int, set[int]] = {}
        for child_id_raw, parent_id_raw in child_rows:
            child_id = int(child_id_raw)
            parent_id = int(parent_id_raw)
            for root_id in frontier.get(parent_id, set()):
                if child_id in descendants[root_id]:
                    continue
                descendants[root_id].add(child_id)
                next_frontier.setdefault(child_id, set()).add(root_id)
        frontier = next_frontier

    return {
        root_id: sorted(subtree_ids)
        for root_id, subtree_ids in descendants.items()
    }


def build_shared_deck_lessons_structure(deck_item: DeckMarketplaceItem) -> list[dict[str, Any]]:
    if deck_item.source_deck_id is None:
        return []

    subtree_ids = collect_subtree_ids(deck_item.source_deck_id)
    if not subtree_ids:
        return []

    decks = (
        Deck.query.filter(Deck.id.in_(subtree_ids), Deck.deleted_at.is_(None))
        .order_by(Deck.parent_id.isnot(None), Deck.position, Deck.id)
        .all()
    )
    if not decks:
        return []

    deck_by_id = {deck.id: deck for deck in decks}
    children_by_parent: dict[int | None, list[Deck]] = {}
    for deck in decks:
        children_by_parent.setdefault(deck.parent_id, []).append(deck)

    note_query = (
        db.session.query(Note.deck_id, db.func.count(Note.id))
        .filter(Note.deck_id.in_(subtree_ids))
    )
    if deck_item.owner_user_id is not None:
        note_query = note_query.filter(Note.user_id == deck_item.owner_user_id)
    note_counts = {int(d_id): int(cnt) for d_id, cnt in note_query.group_by(Note.deck_id).all()}

    card_query = (
        db.session.query(Note.deck_id, db.func.count(Card.id))
        .join(Card, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(subtree_ids))
    )
    if deck_item.owner_user_id is not None:
        card_query = card_query.filter(Note.user_id == deck_item.owner_user_id)
    card_counts = {int(d_id): int(cnt) for d_id, cnt in card_query.group_by(Note.deck_id).all()}

    subtree_note_sums: dict[int, int] = {}
    subtree_card_sums: dict[int, int] = {}

    def _calc_subtree_counts(deck_id: int) -> tuple[int, int]:
        n_cnt = note_counts.get(deck_id, 0)
        c_cnt = card_counts.get(deck_id, 0)
        for child in children_by_parent.get(deck_id, []):
            child_n, child_c = _calc_subtree_counts(child.id)
            n_cnt += child_n
            c_cnt += child_c
        subtree_note_sums[deck_id] = n_cnt
        subtree_card_sums[deck_id] = c_cnt
        return n_cnt, c_cnt

    root_id = deck_item.source_deck_id
    if root_id in deck_by_id:
        _calc_subtree_counts(root_id)

    lessons: list[dict[str, Any]] = []

    def _walk(deck_id: int, depth: int) -> None:
        deck = deck_by_id.get(deck_id)
        if not deck:
            return
        direct_notes = note_counts.get(deck_id, 0)
        direct_cards = card_counts.get(deck_id, 0)
        total_notes = subtree_note_sums.get(deck_id, direct_notes)
        total_cards = subtree_card_sums.get(deck_id, direct_cards)

        lessons.append(
            {
                "id": deck.id,
                "name": deck.name,
                "parent_id": deck.parent_id,
                "depth": depth,
                "is_root": deck_id == root_id,
                "direct_note_count": direct_notes,
                "direct_card_count": direct_cards,
                "note_count": direct_notes if depth > 0 else total_notes,
                "card_count": direct_cards if depth > 0 else total_cards,
                "total_note_count": total_notes,
                "total_card_count": total_cards,
                "has_children": bool(children_by_parent.get(deck_id)),
            }
        )
        for child in children_by_parent.get(deck_id, []):
            _walk(child.id, depth + 1)

    if root_id in deck_by_id:
        _walk(root_id, 0)

    return lessons


def serialize_deck_marketplace_item(
    deck_item: DeckMarketplaceItem,
    stats: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if stats is None:
        stats = compute_deck_item_stats(deck_item)

    price_amount_minor = int(deck_item.price_amount_minor or 0)
    taxonomy_metadata = marketplace_taxonomy_service.get_item_taxonomy(
        deck_item,
        content_type="deck_marketplace_item",
    )
    taxonomy_display = marketplace_taxonomy_service.build_taxonomy_display(
        taxonomy_metadata,
        content_type="deck_marketplace_item",
    )
    return {
        "id": deck_item.id,
        "title": deck_item.title,
        "description": deck_item.description,
        "primary_category": deck_item.primary_category,
        "tags": deck_item.tags or [],
        "display_tags": marketplace_taxonomy_service.merge_detail_tags(
            free_tags=deck_item.tags or [],
            metadata=taxonomy_metadata,
            content_type="deck_marketplace_item",
        ),
        "taxonomy_metadata": taxonomy_metadata,
        "preview_text": deck_item.preview_text,
        "sample_cards_count": int(deck_item.sample_cards_count or 0),
        "note_count": int(stats.get("note_count") or 0),
        "card_count": int(stats.get("card_count") or 0),
        "lesson_count": int(stats.get("lesson_count") or 0),
        "total_decks": int(stats.get("total_decks") or 0),
        "has_subdecks": bool(stats.get("has_subdecks", False)),
        "source_deck_id": deck_item.source_deck_id,
        "source_note_type_id": deck_item.source_note_type_id,
        "distribution_mode": getattr(deck_item, "distribution_mode", "free") or "free",
        "requires_access_key": bool(
            getattr(deck_item, "distribution_mode", "free") == "course_key"
        ),
        "course_title": getattr(deck_item, "course_title", None),
        "course_description": getattr(deck_item, "course_description", None),
        "course_url": getattr(deck_item, "course_url", None),
        "course_instructions": getattr(deck_item, "course_instructions", None),
        "pricing_mode": deck_item.pricing_mode,
        "price_amount_minor": price_amount_minor,
        "price_cents": price_amount_minor,
        "price_display": _format_marketplace_price_display(
            "course_key"
            if getattr(deck_item, "distribution_mode", "free") == "course_key"
            else str(deck_item.pricing_mode or "free"),
            price_amount_minor,
        ),
        "student_offer_mode": str(deck_item.student_offer_mode or "none"),
        "student_discount_percent": (
            int(deck_item.student_discount_percent)
            if deck_item.student_discount_percent is not None
            else None
        ),
        "has_student_offer": (
            deck_item.pricing_mode == "paid"
            and str(deck_item.student_offer_mode or "none") in {"free", "percent_discount"}
        ),
        "version": deck_item.version,
        "changelog": deck_item.changelog,
        "current_release_id": (
            str(deck_item.current_release_id)
            if deck_item.current_release_id is not None
            else None
        ),
        "working_revision": int(deck_item.working_revision or 0),
        "release_versioned": deck_item.current_release_id is not None,
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
        **taxonomy_display,
    }


def first_non_empty_field_text(field_values: dict[str, Any], keys: list[str]) -> str:
    for key in keys:
        if key not in field_values:
            continue
        text = field_value_text(field_values.get(key)).strip()
        if text:
            return text
    return ""


def serialize_note_test_sample(note: Note) -> dict[str, Any] | None:
    field_values = note.field_values if isinstance(note.field_values, dict) else {}
    return serialize_field_values_test_sample(note_id=note.id, field_values=field_values)


def serialize_field_values_test_sample(
    *, note_id: str, field_values: dict[str, Any]
) -> dict[str, Any] | None:

    word = first_non_empty_field_text(
        field_values,
        ["Word", "word", "Term", "term", "Vocabulary", "vocabulary"],
    )
    if not word:
        for raw_value in field_values.values():
            text = field_value_text(raw_value).strip()
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
        "note_id": str(note_id),
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
    mode = str(current_app.config.get("MARKETPLACE_SAMPLE_MODE", "release_cache")).strip().lower()
    schema_version = int(current_app.config.get("MARKETPLACE_SAMPLE_SCHEMA_VERSION", 1))
    cached = _cached_release_samples(
        deck_item,
        limit=limit,
        schema_version=schema_version,
    )
    if cached is not None:
        if mode == "shadow_cache":
            live = _build_live_deck_test_samples(deck_item, limit=limit, randomized=False)
            if live != cached:
                current_app.logger.info(
                    "Marketplace sample cache shadow mismatch deck_item_id=%s",
                    deck_item.id,
                )
        return cached
    if mode == "release_cache":
        return []
    return _build_live_deck_test_samples(deck_item, limit=limit, randomized=True)


def build_release_sample_cache(
    deck_item: DeckMarketplaceItem,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    return _build_live_deck_test_samples(deck_item, limit=limit, randomized=False)


def build_release_sample_cache_from_release(
    deck_item: DeckMarketplaceItem,
    release,
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    from app.repositories import deck_release_repository
    from app.services import deck_release_service

    sequence_no = int(release.sequence_no or 0)
    memberships = [
        row
        for row in deck_release_repository.list_memberships_for_entities(
            deck_item_id=str(deck_item.id),
            entity_kind="note",
        )
        if int(row.introduced_sequence or 0) <= sequence_no
        and (row.removed_sequence is None or int(row.removed_sequence) > sequence_no)
    ]
    note_ids = sorted(str(row.entity_id) for row in memberships)[: max(limit * 4, 20)]
    values_by_note = deck_release_service.get_note_values_for_ids_at_release(
        release,
        note_ids,
    )
    samples: list[dict[str, Any]] = []
    for note_id in note_ids:
        sample = serialize_field_values_test_sample(
            note_id=note_id,
            field_values=values_by_note.get(note_id, {}),
        )
        if sample is not None:
            samples.append(_sanitize_sample_payload(sample))
        if len(samples) >= limit:
            break
    return _bounded_sanitized_samples(samples, limit=limit)


def _cached_release_samples(
    deck_item: DeckMarketplaceItem,
    *,
    limit: int,
    schema_version: int,
) -> list[dict[str, Any]] | None:
    if (
        not deck_item.current_release_id
        or str(deck_item.preview_samples_release_id or "") != str(deck_item.current_release_id)
        or int(deck_item.preview_samples_schema_version or 0) != schema_version
        or not isinstance(deck_item.preview_samples_json, list)
    ):
        return None
    return _bounded_sanitized_samples(
        deck_item.preview_samples_json,
        limit=limit,
    )


def _build_live_deck_test_samples(
    deck_item: DeckMarketplaceItem,
    *,
    limit: int,
    randomized: bool,
) -> list[dict[str, Any]]:
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
    sample_pool_limit = max(limit * 4, 20)
    for note in note_query.order_by(Note.id.asc()).limit(sample_pool_limit).all():
        sample = serialize_note_test_sample(note)
        if sample is not None:
            note_candidates.append(_sanitize_sample_payload(sample))

    if not note_candidates:
        return []

    if randomized:
        random.shuffle(note_candidates)
    return _bounded_sanitized_samples(note_candidates, limit=limit)


def _sanitize_sample_payload(sample: dict[str, Any]) -> dict[str, str]:
    limits = {"note_id": 64, "word": 240, "reading": 240, "meaning": 800}
    return {
        key: str(sample.get(key) or "")[:max_length]
        for key, max_length in limits.items()
    }


def _bounded_sanitized_samples(
    rows: list[Any],
    *,
    limit: int,
) -> list[dict[str, str]]:
    bounded: list[dict[str, str]] = []
    total_bytes = 2  # JSON array brackets.
    for row in rows:
        if len(bounded) >= max(limit, 0):
            break
        if not isinstance(row, dict):
            continue
        sample = _sanitize_sample_payload(row)
        encoded_bytes = len(
            json.dumps(
                sample,
                ensure_ascii=False,
                separators=(",", ":"),
            ).encode("utf-8")
        )
        separator_bytes = 1 if bounded else 0
        if total_bytes + separator_bytes + encoded_bytes > SHARED_DECK_SAMPLE_CACHE_MAX_BYTES:
            break
        bounded.append(sample)
        total_bytes += separator_bytes + encoded_bytes
    return bounded


def item_matches_search(query_text: str, *values: str | None) -> bool:
    if not query_text:
        return True
    lowered = query_text.lower()
    for value in values:
        if value and lowered in value.lower():
            return True
    return False


def _item_matches_category_or_taxonomy(
    *,
    item_category: str | None,
    item_tags: list[str] | None,
    taxonomy: dict[str, Any],
    category_filter: str,
    content_type: str = "deck_marketplace_item",
) -> bool:
    cat_lower = category_filter.strip().lower()
    if not cat_lower:
        return True

    # 1. Exact or case-insensitive match on primary_category
    if item_category and item_category.strip().lower() == cat_lower:
        return True

    # 2. Match domain or domain_label
    if (taxonomy.get("domain") or "").strip().lower() == cat_lower:
        return True
    if (taxonomy.get("domain_label") or "").strip().lower() == cat_lower:
        return True

    # 3. Match subject or subject_label
    if (taxonomy.get("subject") or "").strip().lower() == cat_lower:
        return True
    if (taxonomy.get("subject_label") or "").strip().lower() == cat_lower:
        return True

    # 4. Match framework or framework_label
    if (taxonomy.get("framework") or "").strip().lower() == cat_lower:
        return True
    if (taxonomy.get("framework_label") or "").strip().lower() == cat_lower:
        return True

    # 5. Match framework_level or framework_level_label
    if (taxonomy.get("framework_level") or "").strip().lower() == cat_lower:
        return True
    if (taxonomy.get("framework_level_label") or "").strip().lower() == cat_lower:
        return True

    # 6. Composite JLPT / framework matching (e.g. "jlpt n5", "jlpt_n5", "n5")
    fw = (taxonomy.get("framework") or "").strip().lower()
    fw_lvl = (taxonomy.get("framework_level") or "").strip().lower()
    if fw and fw_lvl:
        if cat_lower in {f"{fw} {fw_lvl}", f"{fw}_{fw_lvl}", f"{fw}{fw_lvl}"}:
            return True
        fw_lbl = (taxonomy.get("framework_label") or "").strip().lower()
        if cat_lower in {f"{fw_lbl} {fw_lvl}", f"{fw_lbl}_{fw_lvl}", f"{fw_lbl}{fw_lvl}"}:
            return True

    # 7. Match learning goals (ids and labels)
    goals = {str(g).strip().lower() for g in (taxonomy.get("learning_goals") or []) if str(g).strip()}
    goal_labels = {str(l).strip().lower() for l in (taxonomy.get("learning_goal_labels") or []) if str(l).strip()}
    if cat_lower in goals or cat_lower in goal_labels:
        return True

    # 8. Match primary topics (ids and labels)
    topics = {str(t).strip().lower() for t in (taxonomy.get("primary_topics") or []) if str(t).strip()}
    topic_labels = {str(l).strip().lower() for l in (taxonomy.get("primary_topic_labels") or []) if str(l).strip()}
    if cat_lower in topics or cat_lower in topic_labels:
        return True

    # 9. Match format features (ids and labels)
    features = {str(f).strip().lower() for f in (taxonomy.get("format_features") or []) if str(f).strip()}
    feature_labels = {str(l).strip().lower() for l in (taxonomy.get("format_feature_labels") or []) if str(l).strip()}
    if cat_lower in features or cat_lower in feature_labels:
        return True

    # 10. Match difficulty band / level
    if (taxonomy.get("difficulty_band") or "").strip().lower() == cat_lower:
        return True
    if (taxonomy.get("difficulty_band_label") or "").strip().lower() == cat_lower:
        return True

    # 11. Match catalog tags & chips
    catalog_tags = {str(t).strip().lower() for t in (taxonomy.get("catalog_tags") or []) if str(t).strip()}
    catalog_chips = {str(c).strip().lower() for c in (taxonomy.get("catalog_chips") or []) if str(c).strip()}
    if cat_lower in catalog_tags or cat_lower in catalog_chips:
        return True

    # 12. Match item tags
    tags = {str(t).strip().lower() for t in (item_tags or []) if str(t).strip()}
    if cat_lower in tags:
        return True

    # 13. Substring matching in combined searchable taxonomy text
    taxonomy_text = marketplace_taxonomy_service.build_searchable_taxonomy_text(
        taxonomy,
        content_type=content_type,
    ).lower()
    if cat_lower in taxonomy_text:
        return True

    return False


def filter_note_type_items(
    note_types: list[NoteType],
    *,
    query_text: str = "",
    category: str = "",
    tags: set[str] | None = None,
    pricing_mode: str = "",
    min_price_amount_minor: int | None = None,
    max_price_amount_minor: int | None = None,
    domain: str = "",
    subject: str = "",
    framework: str = "",
    framework_level: str = "",
    difficulty_band: str = "",
    learning_goals: set[str] | None = None,
    primary_topics: set[str] | None = None,
    format_features: set[str] | None = None,
) -> list[NoteType]:
    filtered: list[NoteType] = []
    for note_type in note_types:
        taxonomy = marketplace_taxonomy_service.get_item_taxonomy(
            note_type,
            content_type="note_type",
        )
        taxonomy_text = marketplace_taxonomy_service.build_searchable_taxonomy_text(
            taxonomy,
            content_type="note_type",
        )
        if not item_matches_search(
            query_text,
            note_type.name,
            note_type.description,
            note_type.primary_category,
            " ".join(note_type.tags or []),
            taxonomy_text,
        ):
            continue
        if category and not _item_matches_category_or_taxonomy(
            item_category=note_type.primary_category,
            item_tags=note_type.tags,
            taxonomy=taxonomy,
            category_filter=category,
            content_type="note_type",
        ):
            continue
        if domain and (taxonomy.get("domain") or "").strip().lower() != domain.strip().lower():
            continue
        if subject and (taxonomy.get("subject") or "").strip().lower() != subject.strip().lower():
            continue
        if framework and (taxonomy.get("framework") or "").strip().lower() != framework.strip().lower():
            continue
        if framework_level and (taxonomy.get("framework_level") or "").strip().lower() != framework_level.strip().lower():
            continue
        if difficulty_band and (taxonomy.get("difficulty_band") or "").strip().lower() != difficulty_band.strip().lower():
            continue
        if learning_goals:
            item_goals = {str(g).strip().lower() for g in (taxonomy.get("learning_goals") or []) if str(g).strip()}
            if not item_goals.intersection({str(g).strip().lower() for g in learning_goals if str(g).strip()}):
                continue
        if primary_topics:
            item_topics = {str(t).strip().lower() for t in (taxonomy.get("primary_topics") or []) if str(t).strip()}
            if not item_topics.intersection({str(t).strip().lower() for t in primary_topics if str(t).strip()}):
                continue
        if format_features:
            item_features = {str(f).strip().lower() for f in (taxonomy.get("format_features") or []) if str(f).strip()}
            if not item_features.intersection({str(f).strip().lower() for f in format_features if str(f).strip()}):
                continue
        item_tags = {tag.lower() for tag in (note_type.tags or [])}
        catalog_tags = {str(t).strip().lower() for t in (taxonomy.get("catalog_tags") or []) if str(t).strip()}
        if tags and not tags.intersection(item_tags) and not tags.intersection(catalog_tags):
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
    query_text: str = "",
    category: str = "",
    tags: set[str] | None = None,
    pricing_mode: str = "",
    min_price_amount_minor: int | None = None,
    max_price_amount_minor: int | None = None,
    domain: str = "",
    subject: str = "",
    framework: str = "",
    framework_level: str = "",
    difficulty_band: str = "",
    learning_goals: set[str] | None = None,
    primary_topics: set[str] | None = None,
    format_features: set[str] | None = None,
) -> list[DeckMarketplaceItem]:
    filtered: list[DeckMarketplaceItem] = []
    for deck_item in deck_items:
        taxonomy = marketplace_taxonomy_service.get_item_taxonomy(
            deck_item,
            content_type="deck_marketplace_item",
        )
        taxonomy_text = marketplace_taxonomy_service.build_searchable_taxonomy_text(
            taxonomy,
            content_type="deck_marketplace_item",
        )
        if not item_matches_search(
            query_text,
            deck_item.title,
            deck_item.description,
            deck_item.primary_category,
            " ".join(deck_item.tags or []),
            taxonomy_text,
        ):
            continue
        if category and not _item_matches_category_or_taxonomy(
            item_category=deck_item.primary_category,
            item_tags=deck_item.tags,
            taxonomy=taxonomy,
            category_filter=category,
            content_type="deck_marketplace_item",
        ):
            continue
        if domain and (taxonomy.get("domain") or "").strip().lower() != domain.strip().lower():
            continue
        if subject and (taxonomy.get("subject") or "").strip().lower() != subject.strip().lower():
            continue
        if framework and (taxonomy.get("framework") or "").strip().lower() != framework.strip().lower():
            continue
        if framework_level and (taxonomy.get("framework_level") or "").strip().lower() != framework_level.strip().lower():
            continue
        if difficulty_band and (taxonomy.get("difficulty_band") or "").strip().lower() != difficulty_band.strip().lower():
            continue
        if learning_goals:
            item_goals = {str(g).strip().lower() for g in (taxonomy.get("learning_goals") or []) if str(g).strip()}
            if not item_goals.intersection({str(g).strip().lower() for g in learning_goals if str(g).strip()}):
                continue
        if primary_topics:
            item_topics = {str(t).strip().lower() for t in (taxonomy.get("primary_topics") or []) if str(t).strip()}
            if not item_topics.intersection({str(t).strip().lower() for t in primary_topics if str(t).strip()}):
                continue
        if format_features:
            item_features = {str(f).strip().lower() for f in (taxonomy.get("format_features") or []) if str(f).strip()}
            if not item_features.intersection({str(f).strip().lower() for f in format_features if str(f).strip()}):
                continue
        item_tags = {tag.lower() for tag in (deck_item.tags or [])}
        catalog_tags = {str(t).strip().lower() for t in (taxonomy.get("catalog_tags") or []) if str(t).strip()}
        if tags and not tags.intersection(item_tags) and not tags.intersection(catalog_tags):
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
        (_utcnow() - updated_at).days
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
    include_definition: bool = True,
    user_id: int = 0,
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
        result[category] = [
            serialize_note_type_marketplace_card(
                item,
                include_definition=include_definition,
                user_id=user_id,
            )
            for item in sorted_bucket
        ]
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
        serialize_note_type_marketplace_card(item, user_id=user_id)
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:12]
    ]

    trending_cutoff = _utcnow() - timedelta(days=7)
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
        "top_by_category": top_items_by_category_note_types(visible_items, user_id=user_id),
        "trending": [serialize_note_type_marketplace_card(item, user_id=user_id) for item in trending],
        "new_and_updated": [serialize_note_type_marketplace_card(item, user_id=user_id) for item in new_and_updated],
    }

def get_deck_recommendations(user_id: int, visible_items: list[DeckMarketplaceItem]) -> dict[str, Any]:
    from app.services import flashcards_share as flashcards_share
    
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

    trending_cutoff = _utcnow() - timedelta(days=7)
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
