"""Vocabulary domain controllers shared by browse/study routes."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import html
import logging
import re
from types import SimpleNamespace
from typing import Any

UTC = timezone.utc
logger = logging.getLogger(__name__)

from sqlalchemy.orm import selectinload

from app.repositories.deck_tree_query import collect_ancestor_ids
from app.repositories.study_repository import (
    LEARNING_QUEUE,
    LEARN_QUEUE,
    NEW_QUEUE,
    RELEARNING_QUEUE,
    REVIEW_QUEUE,
    counter_bucket_for_progress_values,
    effective_due_at_for_progress_values,
    normalize_progress_queue as _normalize_progress_queue,
)
from models import db
from models.card_progress import CardProgress
from models.deck import Deck
from models.flashcard import Card, DeckCloneDeckMap, DeckInstall, Note, NoteType


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


@dataclass
class DeckCreateParentResolution:
    parent_deck: Deck | None
    parent_id: int | None
    error: str | None = None


@dataclass
class DeckPathUpsertResult:
    final_deck: Deck | None
    created_count: int
    created_names: list[str]
    path_tokens: list[str]


def next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(db.func.max(Deck.position))
    if parent_deck_id is None:
        max_pos = query.filter(Deck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(Deck.parent_id == parent_deck_id).scalar()
    return int(max_pos or 0) + 1


def deck_name_exists_under_parent(
    *,
    parent_id: int | None,
    name: str,
    exclude_deck_id: int | None = None,
) -> bool:
    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        return False

    query = Deck.query.filter(
        db.func.lower(Deck.name) == normalized_name,
        Deck.deleted_at.is_(None),
    )
    if parent_id is None:
        query = query.filter(Deck.parent_id.is_(None))
    else:
        query = query.filter(Deck.parent_id == parent_id)
    if exclude_deck_id is not None:
        query = query.filter(Deck.id != exclude_deck_id)
    return query.first() is not None


def parse_create_deck_tokens(*, deck_path_raw: str, fallback_name: str) -> list[str]:
    raw = (deck_path_raw or "").strip() or (fallback_name or "").strip()
    tokens = [item.strip() for item in raw.split("::") if item and item.strip()]
    if tokens:
        return tokens
    return ["New Deck"]


def deck_name_path_tokens(deck_obj: Deck | None) -> list[str]:
    if deck_obj is None:
        return []

    tokens: list[str] = []
    cursor: Deck | None = deck_obj
    seen_ids: set[int] = set()
    while cursor and cursor.id not in seen_ids:
        seen_ids.add(cursor.id)
        name_token = (cursor.name or "").strip()
        if name_token:
            tokens.append(name_token)
        if cursor.parent_id is None:
            break
        cursor = Deck.query.get(cursor.parent_id)
    tokens.reverse()
    return tokens


def normalize_create_deck_tokens_for_parent(
    *,
    path_tokens: list[str],
    parent_path_tokens: list[str],
    fallback_name: str,
) -> list[str]:
    if not path_tokens:
        return [(fallback_name or "").strip() or "New Deck"]
    if not parent_path_tokens or len(path_tokens) < len(parent_path_tokens):
        return path_tokens

    prefix = path_tokens[: len(parent_path_tokens)]
    if [item.casefold() for item in prefix] != [item.casefold() for item in parent_path_tokens]:
        return path_tokens

    trimmed = path_tokens[len(parent_path_tokens) :]
    if trimmed:
        return trimmed
    return [(fallback_name or "").strip() or "New Deck"]


def resolve_create_deck_parent(
    *,
    parent_id_raw: str,
    user_id: int,
    admin_mode: bool,
) -> DeckCreateParentResolution:
    raw_value = (parent_id_raw or "").strip()
    if not raw_value:
        return DeckCreateParentResolution(parent_deck=None, parent_id=None)

    try:
        selected_parent_id = int(raw_value)
    except (TypeError, ValueError):
        return DeckCreateParentResolution(parent_deck=None, parent_id=None, error="Invalid parent deck.")

    parent_deck = Deck.query.get(selected_parent_id)
    if not parent_deck:
        return DeckCreateParentResolution(parent_deck=None, parent_id=None, error="Parent deck not found.")

    if not admin_mode:
        accessible_ids = {
            int(deck.id)
            for deck in collect_accessible_browse_decks(user_id=user_id, admin_mode=False)
            if deck.id is not None
        }
        if selected_parent_id not in accessible_ids:
            return DeckCreateParentResolution(parent_deck=None, parent_id=None, error="Parent deck not found.")

    return DeckCreateParentResolution(
        parent_deck=parent_deck,
        parent_id=selected_parent_id,
        error=None,
    )


def upsert_deck_path(
    *,
    parent_id: int | None,
    path_tokens: list[str],
    owner_user_id: int | None,
    admin_mode: bool,
    note_type_id: str | None = None,
) -> DeckPathUpsertResult:
    current_parent_id = parent_id
    created_count = 0
    created_names: list[str] = []
    final_deck: Deck | None = None

    for token in path_tokens:
        existing_query = Deck.query.filter(
            Deck.parent_id == current_parent_id,
            Deck.name == token,
            Deck.deleted_at.is_(None),
        )
        if not admin_mode:
            existing_query = existing_query.filter(Deck.owner_user_id == owner_user_id)

        existing = existing_query.order_by(Deck.id.asc()).first()
        if existing:
            final_deck = existing
            current_parent_id = existing.id
            continue

        effective_nt_id = note_type_id
        if effective_nt_id is None and current_parent_id is not None:
            parent_deck = db.session.get(Deck, current_parent_id)
            if parent_deck and parent_deck.note_type_id:
                effective_nt_id = parent_deck.note_type_id

        node = Deck(
            parent_id=current_parent_id,
            owner_user_id=owner_user_id,
            name=token,
            position=next_deck_position(current_parent_id),
            note_type_id=effective_nt_id,
        )
        db.session.add(node)
        db.session.flush()
        created_count += 1
        created_names.append(token)
        final_deck = node
        current_parent_id = node.id

    return DeckPathUpsertResult(
        final_deck=final_deck,
        created_count=created_count,
        created_names=created_names,
        path_tokens=path_tokens,
    )


def browse_first_non_empty(field_values: dict | None) -> str:
    if not isinstance(field_values, dict):
        return ""
    for value in field_values.values():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def note_field_values_as_strings(note_obj: Note | None) -> dict[str, str]:
    if not note_obj or not isinstance(note_obj.field_values, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, value in note_obj.field_values.items():
        key_name = str(key).strip()
        if not key_name:
            continue
        normalized[key_name] = "" if value is None else str(value).strip()
    return normalized


def note_ordered_field_names(note_obj: Note | None, *, text_only: bool = False) -> list[str]:
    ordered_names: list[str] = []
    if not note_obj:
        return ordered_names

    note_type_obj = note_obj.note_type
    if note_type_obj:
        sorted_defs = sorted(
            note_type_obj.field_defs,
            key=lambda item: ((item.position or 0), item.name.lower()),
        )
        for field_def in sorted_defs:
            if text_only and field_def.field_type not in {"text", "richtext", "markdown"}:
                continue
            field_name = (field_def.name or "").strip()
            if field_name and field_name not in ordered_names:
                ordered_names.append(field_name)

    field_values = note_field_values_as_strings(note_obj)
    extra_names = sorted(key for key in field_values.keys() if key not in ordered_names)
    ordered_names.extend(extra_names)
    return ordered_names


def format_display_summary(
    raw: str | None,
    max_length: int = 200,
    is_reading: bool = False,
    is_word: bool = False,
) -> str:
    """Format and clean HTML content for compact Browse Table summaries.

    - Strips fallback <rp> tags.
    - For is_reading: extracts <rt> kana from <ruby>.
    - For is_word: extracts base text/kanji from <ruby>.
    - For other (e.g. meaning): converts <ol>/<li> to '1. item; 2. item; ...',
      <ul>/<li> to 'item; item; ...', and <br>/<p> to '; ' or space.
    - Strips remaining HTML tags.
    - Unescapes HTML entities.
    - Collapses consecutive whitespace into single spaces and cleans punctuation.
    - Gracefully bounds output to max_length.
    """
    if not raw:
        return ""
    text = str(raw).strip()
    if not text:
        return ""

    # Strip fallback <rp> tags
    text = re.sub(r"(?is)<rp>[^<]*</rp>", "", text)

    # Ruby handling based on role
    if is_reading:
        def _replace_ruby_reading(match: re.Match) -> str:
            inner = match.group(1)
            rt_matches = re.findall(r"(?is)<rt\b[^>]*>([^<]*)</rt>", inner)
            if rt_matches:
                return "".join(rt_matches)
            return re.sub(r"(?is)<[^>]+>", "", inner)

        text = re.sub(r"(?is)<ruby\b[^>]*>(.*?)</ruby>", _replace_ruby_reading, text)
    elif is_word:
        def _replace_ruby_word(match: re.Match) -> str:
            inner = match.group(1)
            inner_no_rt = re.sub(r"(?is)<rt\b[^>]*>.*?</rt>", "", inner)
            return re.sub(r"(?is)<[^>]+>", "", inner_no_rt)

        text = re.sub(r"(?is)<ruby\b[^>]*>(.*?)</ruby>", _replace_ruby_word, text)
    else:
        def _replace_ruby_other(match: re.Match) -> str:
            inner = match.group(1)
            inner_no_rt = re.sub(r"(?is)<rt\b[^>]*>.*?</rt>", "", inner)
            return re.sub(r"(?is)<[^>]+>", "", inner_no_rt)

        text = re.sub(r"(?is)<ruby\b[^>]*>(.*?)</ruby>", _replace_ruby_other, text)

    # Strip any dangling <rt> tags
    text = re.sub(r"(?is)<rt\b[^>]*>.*?</rt>", "", text)

    # Convert ordered lists: <ol><li>item</li></ol> -> 1. item; 2. item; ...
    def _replace_ol(match: re.Match) -> str:
        inner = match.group(1)
        items = re.findall(r"(?is)<li\b[^>]*>(.*?)</li>", inner)
        if items:
            formatted = []
            for idx, item in enumerate(items, 1):
                clean = re.sub(r"(?is)<[^>]+>", " ", item)
                clean = " ".join(clean.split()).strip()
                if clean:
                    formatted.append(f"{idx}. {clean}")
            return "; ".join(formatted)
        return inner

    # Convert unordered lists: <ul><li>item</li></ul> -> item; item; ...
    def _replace_ul(match: re.Match) -> str:
        inner = match.group(1)
        items = re.findall(r"(?is)<li\b[^>]*>(.*?)</li>", inner)
        if items:
            formatted = []
            for item in items:
                clean = re.sub(r"(?is)<[^>]+>", " ", item)
                clean = " ".join(clean.split()).strip()
                if clean:
                    formatted.append(clean)
            return "; ".join(formatted)
        return inner

    text = re.sub(r"(?is)<ol\b[^>]*>(.*?)</ol>", _replace_ol, text)
    text = re.sub(r"(?is)<ul\b[^>]*>(.*?)</ul\s*>", _replace_ul, text)
    text = re.sub(r"(?is)<li\b[^>]*>(.*?)</li>", r"; \1", text)
    text = re.sub(r"(?is)<br\s*/?>", "; ", text)
    text = re.sub(r"(?is)</p\s*>", "; ", text)
    text = re.sub(r"(?is)<p\b[^>]*>", " ", text)

    # Strip remaining HTML tags
    text = re.sub(r"(?is)<[^>]+>", " ", text)

    # Unescape HTML entities
    text = html.unescape(text).replace("\xa0", " ")

    # Collapse consecutive whitespace into single spaces and clean punctuation
    text = " ".join(text.split()).strip()
    text = re.sub(r"\s*;\s*(?:;\s*)+", "; ", text)
    text = re.sub(r"\s*;\s*", "; ", text)
    text = text.strip(" ;,\t\r\n")

    if max_length > 0 and len(text) > max_length:
        text = text[: max_length - 3].rstrip() + "..."

    return text


def note_display_triplet(note_obj: Note | None) -> dict[str, str]:
    field_values = note_field_values_as_strings(note_obj)
    if not field_values:
        return {"word": "", "reading": "", "meaning": ""}

    ordered_text_names = note_ordered_field_names(note_obj, text_only=True)
    non_empty_values: list[str] = []
    for field_name in ordered_text_names:
        text = field_values.get(field_name, "").strip()
        if text:
            non_empty_values.append(text)

    if not non_empty_values:
        fallback = browse_first_non_empty(field_values)
        return {
            "word": format_display_summary(fallback, is_word=True),
            "reading": "",
            "meaning": "",
        }

    return {
        "word": format_display_summary(non_empty_values[0], is_word=True) if len(non_empty_values) >= 1 else "",
        "reading": format_display_summary(non_empty_values[1], is_reading=True) if len(non_empty_values) >= 2 else "",
        "meaning": format_display_summary(non_empty_values[2], is_reading=False, is_word=False) if len(non_empty_values) >= 3 else "",
    }


def browse_due_label(*, queue: str | None, due_at: datetime | None) -> str:
    queue_norm = (queue or NEW_QUEUE).strip().lower()
    if queue_norm == NEW_QUEUE:
        return "New"
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE, LEARN_QUEUE}:
        return "Learn"
    if due_at:
        return due_at.strftime("%Y-%m-%d %H:%M")
    return "Due"


def browse_status_code(*, queue: str | None, due_at: datetime | None, now: datetime) -> str:
    queue_norm = (queue or NEW_QUEUE).strip().lower()
    if queue_norm == NEW_QUEUE:
        return NEW_QUEUE
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE, LEARN_QUEUE}:
        return LEARNING_QUEUE
    if queue_norm == REVIEW_QUEUE and (due_at is None or due_at <= now):
        return REVIEW_QUEUE
    return queue_norm


def resolve_browse_queue_due(
    *,
    progress_obj: CardProgress | None,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[str, datetime | None]:
    if progress_obj is not None:
        return (
            _normalize_progress_queue(progress_obj.queue),
            effective_due_at_for_progress_values(
                queue=progress_obj.queue,
                due_at=progress_obj.due_at,
                due_day=progress_obj.due_day,
                now=now,
                timezone_name=timezone_name,
            ),
        )
    return NEW_QUEUE, None


def build_browse_row(
    card_obj: Card,
    deck_name_lookup: dict[int, str],
    now: datetime,
    progress_obj: CardProgress | None = None,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    note_obj = card_obj.note
    display_triplet = note_display_triplet(note_obj)
    word = display_triplet["word"]
    reading = display_triplet["reading"]
    meaning = display_triplet["meaning"]

    note_type_name = note_obj.note_type.name if note_obj and note_obj.note_type else "Unknown"
    template_name = card_obj.template.name if card_obj.template else "Card"
    card_type = f"{note_type_name} / {template_name}" if template_name else note_type_name
    deck_name = deck_name_lookup.get((note_obj.deck_id or 0) if note_obj else 0, "")
    queue_value, due_at_value = resolve_browse_queue_due(
        progress_obj=progress_obj,
        now=now,
        timezone_name=timezone_name,
    )
    status_code = browse_status_code(queue=queue_value, due_at=due_at_value, now=now)

    return {
        "card_id": card_obj.id,
        "note_id": note_obj.id if note_obj else None,
        "note_type_id": note_obj.note_type_id if note_obj else None,
        "card_type": card_type,
        "note_type": note_type_name,
        "template": template_name,
        "queue": queue_value,
        "status": status_code,
        "due_at": due_at_value.isoformat() if due_at_value else None,
        "due_label": browse_due_label(queue=queue_value, due_at=due_at_value),
        "deck_id": note_obj.deck_id if note_obj else None,
        "deck_name": deck_name,
        "word": word,
        "reading": reading,
        "meaning": meaning,
        "tags": (note_obj.tags or []) if note_obj else [],
        "updated_at": note_obj.updated_at.isoformat() if note_obj and note_obj.updated_at else None,
    }


def build_browse_card_detail(
    card_obj: Card,
    deck_name_lookup: dict[int, str],
    now: datetime,
    progress_obj: CardProgress | None = None,
    timezone_name: str = "UTC",
) -> dict[str, Any]:
    note_obj = card_obj.note
    note_type_obj = note_obj.note_type if note_obj else None
    field_values = note_obj.field_values if note_obj and isinstance(note_obj.field_values, dict) else {}
    field_defs = (
        sorted(note_type_obj.field_defs, key=lambda fd: int(fd.position or 0))
        if note_type_obj
        else []
    )

    note_type_fields = [
        {
            "name": field_def.name,
            "field_type": field_def.field_type,
            "required": bool(field_def.required),
            "position": field_def.position,
        }
        for field_def in field_defs
    ]
    fields = list(note_type_fields)
    existing_names = {field_def["name"] for field_def in note_type_fields}
    for key in field_values.keys():
        key_str = str(key)
        if key_str in existing_names:
            continue
        fields.append(
            {
                "name": key_str,
                "field_type": "text",
                "required": False,
                "position": 9999,
            }
        )
    fields.sort(key=lambda item: (int(item["position"]), item["name"].lower()))

    media_assets = []
    if note_obj:
        media_assets = [
            {
                "id": asset.id,
                "field_name": asset.field_name,
                "filename": asset.filename,
                "mime_type": asset.mime_type,
                "url": f"/media/proxy/{asset.id}",
            }
            for asset in note_obj.media_assets
        ]

    return {
        "card": build_browse_row(
            card_obj,
            deck_name_lookup,
            now,
            progress_obj=progress_obj,
            timezone_name=timezone_name,
        ),
        "note": {
            "id": note_obj.id if note_obj else None,
            "note_type_id": note_obj.note_type_id if note_obj else None,
            "note_type_name": note_type_obj.name if note_type_obj and note_type_obj.name else "NoteType",
            "deck_id": note_obj.deck_id if note_obj else None,
            "deck_name": deck_name_lookup.get((note_obj.deck_id or 0) if note_obj else 0, ""),
            "field_values": field_values,
            "tags": (note_obj.tags or []) if note_obj else [],
            "updated_at": note_obj.updated_at.isoformat() if note_obj and note_obj.updated_at else None,
        },
        "fields": fields,
        "note_type_fields": note_type_fields,
        "media_assets": media_assets,
        "can_upload_media": True,
        "media_disabled_reason": None,
    }


def collect_accessible_browse_decks(*, user_id: int, admin_mode: bool) -> list[Deck]:
    try:
        from flask import g, has_request_context

        if has_request_context():
            cache = getattr(g, "_accessible_browse_decks_cache", None)
            if cache is None:
                cache = {}
                setattr(g, "_accessible_browse_decks_cache", cache)
            cache_key = (user_id, admin_mode)
            if cache_key in cache:
                return cache[cache_key]
    except (ImportError, RuntimeError):
        has_request_context = None

    if admin_mode:
        result = (
            Deck.query.filter(
                Deck.deleted_at.is_(None),
                db.or_(
                    Deck.owner_user_id == user_id,
                    Deck.owner_user_id.is_(None),
                ),
            )
            .order_by(
                Deck.parent_id.isnot(None),
                Deck.position,
                Deck.created_at,
                Deck.id,
            )
            .all()
        )
        try:
            from flask import g, has_request_context

            if has_request_context():
                cache = getattr(g, "_accessible_browse_decks_cache", None)
                if cache is not None:
                    cache[(user_id, admin_mode)] = result
        except (ImportError, RuntimeError):
            pass
        return result

    all_decks = (
        Deck.query.filter(Deck.deleted_at.is_(None))
        .order_by(
            Deck.parent_id.isnot(None),
            Deck.position,
            Deck.created_at,
            Deck.id,
        )
        .all()
    )

    deck_map = {deck.id: deck for deck in all_decks}
    children_by_parent_all: dict[int, list[int]] = {}
    for deck in all_decks:
        if deck.parent_id is not None:
            children_by_parent_all.setdefault(deck.parent_id, []).append(deck.id)

    visible_ids: set[int] = set()

    owned_deck_rows = (
        db.session.query(Deck.id)
        .filter(
            Deck.owner_user_id == user_id,
            Deck.deleted_at.is_(None),
        )
        .all()
    )
    visible_ids.update(int(row[0]) for row in owned_deck_rows if row and row[0] is not None)

    deck_rows = (
        db.session.query(Note.deck_id)
        .filter(Note.user_id == user_id, Note.deck_id.isnot(None))
        .distinct()
        .all()
    )
    visible_ids.update(int(row[0]) for row in deck_rows if row and row[0] is not None)

    install_root_rows = (
        db.session.query(DeckInstall.local_deck_id)
        .filter(
            DeckInstall.user_id == user_id,
            DeckInstall.local_deck_id.isnot(None),
        )
        .distinct()
        .all()
    )
    install_root_ids = {int(row[0]) for row in install_root_rows if row and row[0] is not None}
    if install_root_ids:
        frontier = list(install_root_ids)
        while frontier:
            current_id = frontier.pop()
            if current_id not in visible_ids:
                visible_ids.add(current_id)
            for child_id in children_by_parent_all.get(current_id, []):
                if child_id not in visible_ids:
                    frontier.append(child_id)

    if not visible_ids:
        return []

    stack = list(visible_ids)
    while stack:
        current_id = stack.pop()
        deck_obj = deck_map.get(current_id)
        if not deck_obj or deck_obj.parent_id is None:
            continue
        if deck_obj.parent_id in visible_ids:
            continue
        visible_ids.add(deck_obj.parent_id)
        stack.append(deck_obj.parent_id)

    result = [deck for deck in all_decks if deck.id in visible_ids]
    try:
        from flask import g, has_request_context

        if has_request_context():
            cache = getattr(g, "_accessible_browse_decks_cache", None)
            if cache is not None:
                cache[(user_id, admin_mode)] = result
    except (ImportError, RuntimeError):
        pass
    return result


def deck_children_map(deck_list: list[Deck]) -> dict[int | None, list[Deck]]:
    mapping: dict[int | None, list[Deck]] = {}
    for deck_obj in deck_list:
        mapping.setdefault(deck_obj.parent_id, []).append(deck_obj)
    for children in mapping.values():
        children.sort(
            key=lambda deck_obj: ((deck_obj.position or 0), deck_obj.created_at, deck_obj.id)
        )
    return mapping


def collect_subtree_ids(
    root_id: int,
    children_by_parent: dict[int | None, list[Deck]],
) -> list[int]:
    result: list[int] = []
    stack = [root_id]
    while stack:
        current_id = stack.pop()
        result.append(current_id)
        for child in children_by_parent.get(current_id, []):
            stack.append(child.id)
    return result


def build_browse_deck_tree_payload(
    *,
    user_id: int,
    admin_mode: bool,
    timezone_name: str = "UTC",
) -> list[dict[str, Any]]:
    from app.repositories.study_repository import (
        _today_day_index,
        active_progress_expr,
        normalized_queue_expr,
        review_due_expr,
    )
    from app.services.scheduler_config_service import resolve_scheduler_runtime_settings

    now = _utcnow()
    scoped_decks = collect_accessible_browse_decks(user_id=user_id, admin_mode=admin_mode)
    if not scoped_decks:
        return []

    scoped_ids = {deck.id for deck in scoped_decks}
    deck_lookup = {deck.id: deck for deck in scoped_decks}
    children_by_parent = deck_children_map(scoped_decks)

    direct_counts = {
        deck_id: {"total": 0, "new": 0, "learn": 0, "due": 0}
        for deck_id in scoped_ids
    }

    runtime = resolve_scheduler_runtime_settings(user_id=user_id if not admin_mode else None)
    day_boundary_hour = int(runtime.day_boundary_hour_local)
    today_day_index = _today_day_index(
        now=now,
        timezone_name=timezone_name,
        day_boundary_hour_local=day_boundary_hour,
    )

    progress_alias = CardProgress
    progress_join = db.and_(
        progress_alias.card_id == Card.id,
        progress_alias.user_id == user_id,
    )
    active_expr = active_progress_expr(progress_alias, today_day_index=today_day_index)
    norm_queue = normalized_queue_expr(progress_alias)
    is_new = db.and_(active_expr, db.or_(progress_alias.id.is_(None), norm_queue == NEW_QUEUE))
    is_learn = db.and_(active_expr, norm_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE]))
    is_due_review = db.and_(
        active_expr,
        norm_queue == REVIEW_QUEUE,
        review_due_expr(
            progress_alias,
            now=now,
            timezone_name=timezone_name,
            day_boundary_hour_local=day_boundary_hour,
        ),
    )

    counts_query = (
        db.session.query(
            Note.deck_id,
            db.func.count(Card.id).label("total"),
            db.func.sum(db.case((is_new, 1), else_=0)).label("new"),
            db.func.sum(db.case((is_learn, 1), else_=0)).label("learn"),
            db.func.sum(db.case((is_due_review, 1), else_=0)).label("due"),
        )
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .outerjoin(progress_alias, progress_join)
        .filter(Note.deck_id.in_(scoped_ids))
    )
    if not admin_mode:
        counts_query = counts_query.filter(Note.user_id == user_id)
    counts_query = counts_query.group_by(Note.deck_id)

    for row in counts_query.all():
        deck_id = row[0]
        if deck_id is None:
            continue
        bucket = direct_counts.setdefault(
            int(deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
        )
        bucket["total"] += int(row[1] or 0)
        bucket["new"] += int(row[2] or 0)
        bucket["learn"] += int(row[3] or 0)
        bucket["due"] += int(row[4] or 0)

    logical_installs: list[DeckInstall] = []
    if not admin_mode:
        logical_installs = (
            DeckInstall.query.filter(
                DeckInstall.user_id == user_id,
                DeckInstall.clone_mode == "logical_overlay",
                DeckInstall.local_deck_id.isnot(None),
            )
            .order_by(DeckInstall.installed_at.asc(), DeckInstall.id.asc())
            .all()
        )
        maps_by_install: dict[str, dict[int, int]] = defaultdict(dict)
        if logical_installs:
            install_ids = [str(inst.id) for inst in logical_installs if inst.id is not None]
            if install_ids:
                all_map_rows = (
                    DeckCloneDeckMap.query.filter(DeckCloneDeckMap.deck_install_id.in_(install_ids))
                    .all()
                )
                source_to_install: dict[int, str] = {}
                source_to_local_all: dict[int, int] = {}
                has_overlap = False

                for row in all_map_rows:
                    if (
                        row.deck_install_id
                        and row.source_deck_id is not None
                        and row.local_deck_id is not None
                        and int(row.local_deck_id) in scoped_ids
                    ):
                        sid = int(row.source_deck_id)
                        lid = int(row.local_deck_id)
                        iid = str(row.deck_install_id)

                        prev_iid = source_to_install.get(sid)
                        if prev_iid is not None and prev_iid != iid:
                            logger.warning(
                                "Cross-install source overlap detected for user %s: source_deck_id=%s mapped to installs %s and %s",
                                user_id,
                                sid,
                                prev_iid,
                                iid,
                            )
                            has_overlap = True
                        else:
                            source_to_install[sid] = iid
                            source_to_local_all[sid] = lid

                        maps_by_install[iid][sid] = lid

                if not has_overlap:
                    install_conditions = []
                    for install in logical_installs:
                        inst_key = str(install.id)
                        source_to_local = maps_by_install.get(inst_key)
                        if not source_to_local:
                            continue
                        conds = [Note.deck_id.in_(list(source_to_local.keys()))]
                        if install.source_owner_user_id is not None:
                            conds.append(Note.user_id == install.source_owner_user_id)
                        snapshot_at = install.base_snapshot_at or install.installed_at
                        if snapshot_at is not None:
                            conds.append(Note.created_at <= snapshot_at)
                            conds.append(Card.created_at <= snapshot_at)
                        install_conditions.append(db.and_(*conds))

                    if install_conditions:
                        clone_counts_query = (
                            db.session.query(
                                Note.deck_id,
                                db.func.count(Card.id).label("total"),
                                db.func.sum(db.case((is_new, 1), else_=0)).label("new"),
                                db.func.sum(db.case((is_learn, 1), else_=0)).label("learn"),
                                db.func.sum(db.case((is_due_review, 1), else_=0)).label("due"),
                            )
                            .select_from(Card)
                            .join(Note, Card.note_id == Note.id)
                            .outerjoin(progress_alias, progress_join)
                            .filter(db.or_(*install_conditions))
                            .group_by(Note.deck_id)
                        )
                        for row in clone_counts_query.all():
                            source_deck_id = row[0]
                            if source_deck_id is None:
                                continue
                            local_deck_id = source_to_local_all.get(int(source_deck_id))
                            if local_deck_id is None:
                                continue
                            bucket = direct_counts.setdefault(
                                int(local_deck_id),
                                {"total": 0, "new": 0, "learn": 0, "due": 0},
                            )
                            bucket["total"] += int(row[1] or 0)
                            bucket["new"] += int(row[2] or 0)
                            bucket["learn"] += int(row[3] or 0)
                            bucket["due"] += int(row[4] or 0)
                else:
                    for install in logical_installs:
                        inst_key = str(install.id)
                        source_to_local = maps_by_install.get(inst_key)
                        if not source_to_local:
                            continue
                        clone_counts_query = (
                            db.session.query(
                                Note.deck_id,
                                db.func.count(Card.id).label("total"),
                                db.func.sum(db.case((is_new, 1), else_=0)).label("new"),
                                db.func.sum(db.case((is_learn, 1), else_=0)).label("learn"),
                                db.func.sum(db.case((is_due_review, 1), else_=0)).label("due"),
                            )
                            .select_from(Card)
                            .join(Note, Card.note_id == Note.id)
                            .outerjoin(progress_alias, progress_join)
                            .filter(Note.deck_id.in_(list(source_to_local.keys())))
                        )
                        if install.source_owner_user_id is not None:
                            clone_counts_query = clone_counts_query.filter(Note.user_id == install.source_owner_user_id)
                        snapshot_at = install.base_snapshot_at or install.installed_at
                        if snapshot_at is not None:
                            clone_counts_query = clone_counts_query.filter(
                                Note.created_at <= snapshot_at,
                                Card.created_at <= snapshot_at,
                            )
                        clone_counts_query = clone_counts_query.group_by(Note.deck_id)

                        for row in clone_counts_query.all():
                            source_deck_id = row[0]
                            if source_deck_id is None:
                                continue
                            local_deck_id = source_to_local.get(int(source_deck_id))
                            if local_deck_id is None:
                                continue
                            bucket = direct_counts.setdefault(
                                int(local_deck_id),
                                {"total": 0, "new": 0, "learn": 0, "due": 0},
                            )
                            bucket["total"] += int(row[1] or 0)
                            bucket["new"] += int(row[2] or 0)
                            bucket["learn"] += int(row[3] or 0)
                            bucket["due"] += int(row[4] or 0)

    deck_note_type_rows = (
        db.session.query(Note.deck_id, Note.note_type_id)
        .filter(Note.deck_id.in_(scoped_ids))
        .distinct()
        .all()
    )
    direct_deck_note_types: dict[int, set[str]] = {}
    all_nt_ids: set[str] = set()
    for row in deck_note_type_rows:
        if row[0] and row[1]:
            direct_deck_note_types.setdefault(int(row[0]), set()).add(str(row[1]))
            all_nt_ids.add(str(row[1]))

    if logical_installs:
        for install in logical_installs:
            inst_key = str(install.id)
            source_to_local = maps_by_install.get(inst_key, {})
            if install.source_note_type_id:
                snt_id = str(install.source_note_type_id)
                all_nt_ids.add(snt_id)
                for local_id in source_to_local.values():
                    direct_deck_note_types.setdefault(local_id, set()).add(snt_id)

    for d in scoped_decks:
        if d.note_type_id:
            all_nt_ids.add(str(d.note_type_id))

    nt_name_lookup: dict[str, str] = {}
    if all_nt_ids:
        for nt in NoteType.query.filter(NoteType.id.in_(all_nt_ids)).all():
            nt_name_lookup[str(nt.id)] = str(nt.name)

    def _build_node(deck_obj: Deck, prefix: str = "") -> dict[str, Any]:
        path = f"{prefix} :: {deck_obj.name}" if prefix else deck_obj.name
        direct = direct_counts.get(deck_obj.id, {"total": 0, "new": 0, "learn": 0, "due": 0})
        counts = {
            "total": int(direct["total"]),
            "new": int(direct["new"]),
            "learn": int(direct["learn"]),
            "due": int(direct["due"]),
        }
        subtree_nt_ids: set[str] = set(direct_deck_note_types.get(deck_obj.id, set()))
        if deck_obj.note_type_id:
            subtree_nt_ids.add(str(deck_obj.note_type_id))

        children_payload: list[dict[str, Any]] = []
        for child_obj in children_by_parent.get(deck_obj.id, []):
            child_payload = _build_node(child_obj, prefix=path)
            children_payload.append(child_payload)
            child_counts = child_payload["counts"]
            counts["total"] += int(child_counts["total"])
            counts["new"] += int(child_counts["new"])
            counts["learn"] += int(child_counts["learn"])
            counts["due"] += int(child_counts["due"])
            for child_nt_id in child_payload.get("note_type_ids", []):
                subtree_nt_ids.add(child_nt_id)

        sorted_nt_ids = sorted(list(subtree_nt_ids))
        nt_names = [nt_name_lookup.get(nid, nid) for nid in sorted_nt_ids]
        has_mixed = len(sorted_nt_ids) > 1
        resolved_note_type_id = sorted_nt_ids[0] if len(sorted_nt_ids) == 1 else (str(deck_obj.note_type_id) if deck_obj.note_type_id else None)
        resolved_note_type_name = nt_names[0] if len(nt_names) == 1 else None

        return {
            "id": deck_obj.id,
            "name": deck_obj.name,
            "path": path,
            "parent_id": deck_obj.parent_id,
            "note_type_id": str(resolved_note_type_id) if resolved_note_type_id else None,
            "note_type_name": resolved_note_type_name,
            "note_type_ids": sorted_nt_ids,
            "note_type_names": nt_names,
            "has_mixed_note_types": has_mixed,
            "counts": counts,
            "children": children_payload,
        }

    roots = [
        deck_obj
        for deck_obj in scoped_decks
        if deck_obj.parent_id is None or deck_obj.parent_id not in deck_lookup
    ]
    roots.sort(key=lambda deck_obj: ((deck_obj.position or 0), deck_obj.created_at, deck_obj.id))
    return [_build_node(root_obj, prefix="") for root_obj in roots]


def can_user_delete_cloned_deck(*, deck_obj: Deck, user_id: int) -> bool:
    if deck_obj.owner_user_id != user_id:
        return False

    ancestor_ids = collect_ancestor_ids(deck_obj.id)
    if not ancestor_ids:
        return False

    install_row = (
        db.session.query(DeckInstall.id)
        .filter(
            DeckInstall.user_id == user_id,
            DeckInstall.local_deck_id.in_(ancestor_ids),
        )
        .first()
    )
    return install_row is not None


def build_note_study_card_payload(card_obj: Card | None) -> SimpleNamespace | None:
    if not card_obj or not card_obj.note:
        return None

    note_obj = card_obj.note
    field_values = note_field_values_as_strings(note_obj)
    display_triplet = note_display_triplet(note_obj)
    note_type_obj = note_obj.note_type
    field_defs = sorted(note_type_obj.field_defs, key=lambda item: item.position) if note_type_obj else []

    payload = {
        "id": card_obj.id,
        "note_id": note_obj.id,
        "word": display_triplet["word"],
        "reading": display_triplet["reading"],
        "meaning": display_triplet["meaning"],
        "field_values": field_values,
        "field_defs": [
            {
                "name": field_def.name,
                "field_type": field_def.field_type,
                "required": bool(field_def.required),
                "position": int(field_def.position or 0),
            }
            for field_def in field_defs
        ],
    }
    return SimpleNamespace(**payload)


def render_note_study_flashcard(card_obj: Card | None) -> dict[str, Any]:
    from app.services.flashcard_renderer import TemplateCompileError, render_template_pair

    ret: dict[str, Any] = {"front": "", "back": "", "front_payload": None, "back_payload": None}
    if not card_obj or not card_obj.note or not card_obj.template:
        return ret

    note_obj = card_obj.note
    note_type = note_obj.note_type
    if not note_type:
        return ret

    try:
        rendered = render_template_pair(
            template=card_obj.template,
            field_defs=note_type.field_defs,
            field_values=note_obj.field_values or {},
            media_assets=note_obj.media_assets,
            preview_note_key=note_obj.id,
        )
        ret["front"] = rendered.get("front_html", "")
        ret["back"] = rendered.get("back_html", "")
        ret["front_payload"] = rendered.get("front_renderer_payload")
        ret["back_payload"] = rendered.get("back_renderer_payload")
    except TemplateCompileError as exc:
        ret["front"] = f"<div class='text-danger'>Error rendering front: {exc}</div>"
        ret["back"] = f"<div class='text-danger'>Error rendering back: {exc}</div>"

    return ret


def query_study_cards_for_deck_ids(*, user_id: int, deck_ids: list[int]) -> list[Card]:
    if not deck_ids:
        return []

    direct_cards = (
        Card.query.join(Note, Card.note_id == Note.id)
        .options(
            selectinload(Card.template),
            selectinload(Card.note).selectinload(Note.note_type),
            selectinload(Card.note).selectinload(Note.media_assets),
        )
        .filter(
            Note.user_id == user_id,
            Note.deck_id.in_(deck_ids),
        )
        .order_by(Card.created_at.asc(), Card.id.asc())
        .all()
    )
    seen_card_ids = {card_obj.id for card_obj in direct_cards}
    merged_cards = list(direct_cards)

    from app.services import flashcards_share as share_ctrl

    seen_scope_keys: set[tuple[str, int]] = set()
    for local_deck_id in sorted({int(deck_id) for deck_id in deck_ids if deck_id is not None}):
        clone_scope = share_ctrl.resolve_clone_scope_for_local_deck(
            user_id=user_id,
            local_deck_id=local_deck_id,
        )
        if clone_scope is None:
            continue
        scope_key = (clone_scope.install.id, int(clone_scope.local_scope_deck_id))
        if scope_key in seen_scope_keys:
            continue
        seen_scope_keys.add(scope_key)

        clone_cards = (
            share_ctrl.query_clone_scope_cards(clone_scope)
            .options(
                selectinload(Card.template),
                selectinload(Card.note).selectinload(Note.note_type),
                selectinload(Card.note).selectinload(Note.media_assets),
            )
            .order_by(Card.created_at.asc(), Card.id.asc())
            .all()
        )
        for card_obj in clone_cards:
            if card_obj.id in seen_card_ids:
                continue
            seen_card_ids.add(card_obj.id)
            merged_cards.append(card_obj)

    merged_cards.sort(key=lambda card_obj: (card_obj.created_at or datetime.min, card_obj.id))
    return merged_cards


def count_due_note_cards(
    cards: list[Card],
    progress_map: dict[str, CardProgress],
    *,
    now: datetime,
    timezone_name: str = "UTC",
) -> tuple[int, int, int]:
    due_new = 0
    due_learn = 0
    due_review = 0
    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        count_bucket = counter_bucket_for_progress_values(
            queue=progress.queue if progress else None,
            due_at=progress.due_at if progress else None,
            due_day=progress.due_day if progress else None,
            is_suspended=progress.is_suspended if progress else None,
            now=now,
            timezone_name=timezone_name,
        )
        if count_bucket == LEARNING_QUEUE:
            due_learn += 1
        elif count_bucket == REVIEW_QUEUE:
            due_review += 1
        elif count_bucket == NEW_QUEUE:
            due_new += 1
    return due_new, due_learn, due_review
