"""Vocabulary management routes."""

from __future__ import annotations

from datetime import datetime, timedelta
from types import SimpleNamespace
from typing import Dict, List

from flask import (
    Blueprint,
    abort,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import selectinload

from app.utils.deck_move_token import parse_deck_move_token
from app.utils.permissions import is_admin_user
from app.services.anki_scheduler import (
    CardState,
    computeAnswerPreview,
    default_deck_options,
)
from models import db
from models.flashcard import Card, Note
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_progress import VocabularyProgress

LEARN_QUEUE = "learn"
REVIEW_QUEUE = "review"
NEW_QUEUE = "new"
LEARNING_QUEUE = "learning"
RELEARNING_QUEUE = "relearning"

vocabulary_bp = Blueprint("vocabulary", __name__, url_prefix="/vocabulary")


@vocabulary_bp.before_request
def restrict_non_admin_routes():
    """Allow regular users to access only study mode endpoints."""
    if not current_user.is_authenticated:
        return None
    if is_admin_user(current_user):
        return None

    endpoint = request.endpoint or ""
    allowed_endpoints = {
        "vocabulary.index",
        "vocabulary.study_deck",
        "vocabulary.browse",
        "vocabulary.browse_api_decks_tree",
        "vocabulary.browse_api_cards",
        "vocabulary.browse_api_card_detail",
        "vocabulary.browse_api_card_update",
        "vocabulary.browse_api_card_delete",
        "vocabulary.browse_api_decks",
        "vocabulary.browse_api_notes",
        "vocabulary.browse_api_update_note",
        "vocabulary.delete_deck",
    }
    if endpoint in allowed_endpoints:
        return None
    return redirect(url_for("main.dashboard"))


def _legacy_structure_removed_response():
    message = "Legacy Level/Topic/Lesson/Entry workflow has been removed. Please use Deck + NoteType + Note."
    if request.is_json:
        return jsonify({"success": False, "error": "LEGACY_STRUCTURE_REMOVED", "message": message}), 410
    if request.method == "GET":
        return message, 410
    flash(message, "warning")
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    return redirect(next_url or url_for("vocabulary.browse"))


def _normalize_progress_queue(value: str | None) -> str:
    normalized = (value or NEW_QUEUE).strip().lower()
    if normalized == LEARN_QUEUE:
        return LEARNING_QUEUE
    if normalized in {NEW_QUEUE, LEARNING_QUEUE, REVIEW_QUEUE, RELEARNING_QUEUE}:
        return normalized
    return NEW_QUEUE


def _card_state_from_progress(progress: VocabularyProgress | None, now: datetime) -> CardState:
    options = default_deck_options()
    if not progress:
        return CardState(
            type=NEW_QUEUE,
            stepIndex=0,
            due=now,
            dueDay=None,
            intervalDays=0,
            ease=options.startingEase,
            reps=0,
            lapses=0,
            lastReviewAt=None,
        )

    queue = _normalize_progress_queue(progress.queue)
    due_at = progress.due_at or now
    due_day = progress.due_day
    
    # Backward compatibility: if due_day not stored but queue=review, recalculate it
    if due_day is None and queue == REVIEW_QUEUE:
        shifted = due_at - timedelta(hours=options.dayBoundaryHourLocal)
        due_day = shifted.date().toordinal()

    return CardState(
        type=queue,  # type: ignore[arg-type]
        stepIndex=int(progress.step_index or 0),
        due=due_at,
        dueDay=due_day,
        intervalDays=float(progress.interval_days or 0),
        ease=float(progress.ease_factor or options.startingEase),
        reps=int(progress.reps or 0),
        lapses=int(progress.lapses or 0),
        lastReviewAt=progress.last_reviewed_at,
    )


def _apply_card_state_to_progress(
    progress: VocabularyProgress, card_state: CardState, now: datetime
) -> VocabularyProgress:
    options = default_deck_options()
    queue = _normalize_progress_queue(card_state.type)
    due_at = card_state.due
    due_day = card_state.dueDay
    
    if card_state.dueDay is not None:
        day_date = datetime.fromordinal(int(card_state.dueDay)).date()
        due_at = datetime.combine(day_date, datetime.min.time()) + timedelta(
            hours=options.dayBoundaryHourLocal
        )
    progress.queue = queue
    progress.step_index = int(card_state.stepIndex or 0)
    progress.due_at = due_at
    progress.due_day = due_day
    progress.interval_days = int(round(float(card_state.intervalDays or 0)))
    progress.ease_factor = float(card_state.ease or options.startingEase)
    progress.reps = int(card_state.reps or 0)
    progress.lapses = int(card_state.lapses or 0)
    progress.last_reviewed_at = card_state.lastReviewAt or now
    return progress


def _next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(func.max(VocabularyDeck.position))
    if parent_deck_id is None:
        max_pos = query.filter(VocabularyDeck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(VocabularyDeck.parent_id == parent_deck_id).scalar()
    return (max_pos or 0) + 1


def _resolve_next_url(default_endpoint: str = "main.dashboard") -> str:
    """Return a safe in-app redirect target from `next` form value."""
    raw_next = (request.form.get("next") or "").strip()
    if raw_next.startswith("/") and not raw_next.startswith("//"):
        return raw_next
    return url_for(default_endpoint)


def _deck_name_exists_under_parent(
    *,
    parent_id: int | None,
    name: str,
    exclude_deck_id: int | None = None,
) -> bool:
    """Check if a sibling deck with the same name already exists."""
    normalized_name = (name or "").strip().lower()
    if not normalized_name:
        return False

    query = VocabularyDeck.query.filter(func.lower(VocabularyDeck.name) == normalized_name)
    if parent_id is None:
        query = query.filter(VocabularyDeck.parent_id.is_(None))
    else:
        query = query.filter(VocabularyDeck.parent_id == parent_id)
    if exclude_deck_id is not None:
        query = query.filter(VocabularyDeck.id != exclude_deck_id)
    return query.first() is not None


def _is_due(progress: VocabularyProgress | None, now: datetime) -> bool:
    if progress is None:
        return True
    queue = _normalize_progress_queue(progress.queue)
    if queue == NEW_QUEUE:
        return True
    if progress.due_at is None:
        return True
    return progress.due_at <= now


@vocabulary_bp.route("/")
@login_required
def index():
    """Legacy hierarchy index removed; redirect to browse."""
    return redirect(url_for("vocabulary.browse"))


@vocabulary_bp.route("/browse")
@login_required
def browse():
    """Anki-like browser interface."""
    return render_template("vocabulary_browse.html")


def _browse_first_non_empty(field_values: dict | None) -> str:
    if not isinstance(field_values, dict):
        return ""
    for value in field_values.values():
        if value is None:
            continue
        text = str(value).strip()
        if text:
            return text
    return ""


def _note_field_values_as_strings(note_obj: Note | None) -> dict[str, str]:
    if not note_obj or not isinstance(note_obj.field_values, dict):
        return {}

    normalized: dict[str, str] = {}
    for key, value in note_obj.field_values.items():
        key_name = str(key).strip()
        if not key_name:
            continue
        normalized[key_name] = "" if value is None else str(value).strip()
    return normalized


def _note_ordered_field_names(note_obj: Note | None, *, text_only: bool = False) -> list[str]:
    ordered_names: list[str] = []
    if not note_obj:
        return ordered_names

    note_type_obj = note_obj.note_type
    if note_type_obj:
        sorted_defs = sorted(note_type_obj.field_defs, key=lambda item: ((item.position or 0), item.name.lower()))
        for field_def in sorted_defs:
            if text_only and field_def.field_type not in {"text", "richtext"}:
                continue
            field_name = (field_def.name or "").strip()
            if field_name and field_name not in ordered_names:
                ordered_names.append(field_name)

    field_values = _note_field_values_as_strings(note_obj)
    extra_names = sorted(key for key in field_values.keys() if key not in ordered_names)
    ordered_names.extend(extra_names)
    return ordered_names


def _note_display_triplet(note_obj: Note | None) -> dict[str, str]:
    """Build generic primary/secondary/tertiary labels from note fields without hardcoded names."""
    field_values = _note_field_values_as_strings(note_obj)
    if not field_values:
        return {"word": "", "reading": "", "meaning": ""}

    ordered_text_names = _note_ordered_field_names(note_obj, text_only=True)
    non_empty_values: list[str] = []
    for field_name in ordered_text_names:
        text = field_values.get(field_name, "").strip()
        if text:
            non_empty_values.append(text)

    if not non_empty_values:
        fallback = _browse_first_non_empty(field_values)
        return {"word": fallback, "reading": "", "meaning": ""}

    return {
        "word": non_empty_values[0] if len(non_empty_values) >= 1 else "",
        "reading": non_empty_values[1] if len(non_empty_values) >= 2 else "",
        "meaning": non_empty_values[2] if len(non_empty_values) >= 3 else "",
    }


def _browse_due_label(*, queue: str | None, due_at: datetime | None) -> str:
    queue_norm = (queue or NEW_QUEUE).strip().lower()
    if queue_norm == NEW_QUEUE:
        return "New"
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE, LEARN_QUEUE}:
        return "Learn"
    if due_at:
        return due_at.strftime("%Y-%m-%d %H:%M")
    return "Due"


def _browse_status_code(*, queue: str | None, due_at: datetime | None, now: datetime) -> str:
    queue_norm = (queue or NEW_QUEUE).strip().lower()
    if queue_norm == NEW_QUEUE:
        return NEW_QUEUE
    if queue_norm in {LEARNING_QUEUE, RELEARNING_QUEUE, LEARN_QUEUE}:
        return LEARNING_QUEUE
    if queue_norm == REVIEW_QUEUE and (due_at is None or due_at <= now):
        return REVIEW_QUEUE
    return queue_norm


def _build_browse_row(card_obj, deck_name_lookup: dict[int, str], now: datetime):
    note_obj = card_obj.note
    display_triplet = _note_display_triplet(note_obj)
    word = display_triplet["word"]
    reading = display_triplet["reading"]
    meaning = display_triplet["meaning"]

    note_type_name = note_obj.note_type.name if note_obj.note_type else "Unknown"
    template_name = card_obj.template.name if card_obj.template else "Card"
    card_type = f"{note_type_name} / {template_name}" if template_name else note_type_name
    deck_name = deck_name_lookup.get(note_obj.deck_id or 0, "")
    status_code = _browse_status_code(queue=card_obj.queue, due_at=card_obj.due_at, now=now)

    return {
        "card_id": card_obj.id,
        "note_id": note_obj.id,
        "note_type_id": note_obj.note_type_id,
        "card_type": card_type,
        "note_type": note_type_name,
        "template": template_name,
        "queue": (card_obj.queue or NEW_QUEUE).strip().lower(),
        "status": status_code,
        "due_at": card_obj.due_at.isoformat() if card_obj.due_at else None,
        "due_label": _browse_due_label(queue=card_obj.queue, due_at=card_obj.due_at),
        "deck_id": note_obj.deck_id,
        "deck_name": deck_name,
        "word": word,
        "reading": reading,
        "meaning": meaning,
        "tags": note_obj.tags or [],
        "updated_at": note_obj.updated_at.isoformat() if note_obj.updated_at else None,
    }


def _build_browse_card_detail(card_obj, deck_name_lookup: dict[int, str], now: datetime):
    note_obj = card_obj.note
    note_type_obj = note_obj.note_type
    field_values = note_obj.field_values or {}
    field_defs = sorted(note_type_obj.field_defs, key=lambda fd: fd.position) if note_type_obj else []

    fields = [
        {
            "name": field_def.name,
            "field_type": field_def.field_type,
            "required": bool(field_def.required),
            "position": field_def.position,
        }
        for field_def in field_defs
    ]
    existing_names = {field_def["name"] for field_def in fields}
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
        "card": _build_browse_row(card_obj, deck_name_lookup, now),
        "note": {
            "id": note_obj.id,
            "note_type_id": note_obj.note_type_id,
            "deck_id": note_obj.deck_id,
            "deck_name": deck_name_lookup.get(note_obj.deck_id or 0, ""),
            "field_values": field_values,
            "tags": note_obj.tags or [],
            "updated_at": note_obj.updated_at.isoformat() if note_obj.updated_at else None,
        },
        "fields": fields,
        "media_assets": media_assets,
    }


def _collect_accessible_browse_decks():
    from models.flashcard import Note

    all_decks = VocabularyDeck.query.order_by(
        VocabularyDeck.parent_id.isnot(None),
        VocabularyDeck.position,
        VocabularyDeck.created_at,
        VocabularyDeck.id,
    ).all()
    if is_admin_user(current_user):
        return all_decks

    deck_map = {deck.id: deck for deck in all_decks}
    deck_rows = (
        db.session.query(Note.deck_id)
        .filter(Note.user_id == current_user.id, Note.deck_id.isnot(None))
        .distinct()
        .all()
    )
    visible_ids = {int(row[0]) for row in deck_rows if row[0]}
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

    return [deck for deck in all_decks if deck.id in visible_ids]


def _deck_children_map(deck_list: list[VocabularyDeck]) -> dict[int | None, list[VocabularyDeck]]:
    mapping: dict[int | None, list[VocabularyDeck]] = {}
    for deck_obj in deck_list:
        mapping.setdefault(deck_obj.parent_id, []).append(deck_obj)
    for children in mapping.values():
        children.sort(key=lambda deck_obj: ((deck_obj.position or 0), deck_obj.created_at, deck_obj.id))
    return mapping


def _collect_subtree_ids(root_id: int, children_by_parent: dict[int | None, list[VocabularyDeck]]) -> list[int]:
    result: list[int] = []
    stack = [root_id]
    while stack:
        current_id = stack.pop()
        result.append(current_id)
        for child in children_by_parent.get(current_id, []):
            stack.append(child.id)
    return result


def _build_browse_deck_tree_payload():
    from models.flashcard import Card, Note

    now = datetime.utcnow()
    scoped_decks = _collect_accessible_browse_decks()
    if not scoped_decks:
        return []

    scoped_ids = {deck.id for deck in scoped_decks}
    deck_lookup = {deck.id: deck for deck in scoped_decks}
    children_by_parent = _deck_children_map(scoped_decks)

    direct_counts = {
        deck_id: {"total": 0, "new": 0, "learn": 0, "due": 0}
        for deck_id in scoped_ids
    }

    base_query = (
        db.session.query(Note.deck_id, Card.queue, func.count(Card.id))
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(scoped_ids))
    )
    if not is_admin_user(current_user):
        base_query = base_query.filter(Note.user_id == current_user.id)
    queue_rows = base_query.group_by(Note.deck_id, Card.queue).all()
    for deck_id, queue_value, total in queue_rows:
        if not deck_id:
            continue
        bucket = direct_counts.setdefault(
            int(deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
        )
        total_int = int(total or 0)
        bucket["total"] += total_int
        queue_norm = (queue_value or NEW_QUEUE).strip().lower()
        if queue_norm == NEW_QUEUE:
            bucket["new"] += total_int
        elif queue_norm in {LEARN_QUEUE, LEARNING_QUEUE, RELEARNING_QUEUE}:
            bucket["learn"] += total_int

    due_query = (
        db.session.query(Note.deck_id, func.count(Card.id))
        .select_from(Card)
        .join(Note, Card.note_id == Note.id)
        .filter(
            Note.deck_id.in_(scoped_ids),
            Card.queue == REVIEW_QUEUE,
            or_(Card.due_at.is_(None), Card.due_at <= now),
        )
    )
    if not is_admin_user(current_user):
        due_query = due_query.filter(Note.user_id == current_user.id)
    for deck_id, due_total in due_query.group_by(Note.deck_id).all():
        if not deck_id:
            continue
        bucket = direct_counts.setdefault(
            int(deck_id), {"total": 0, "new": 0, "learn": 0, "due": 0}
        )
        bucket["due"] = int(due_total or 0)

    def _build_node(deck_obj: VocabularyDeck):
        direct = direct_counts.get(
            deck_obj.id, {"total": 0, "new": 0, "learn": 0, "due": 0}
        )
        counts = {
            "total": int(direct["total"]),
            "new": int(direct["new"]),
            "learn": int(direct["learn"]),
            "due": int(direct["due"]),
        }
        children_payload = []
        for child_obj in children_by_parent.get(deck_obj.id, []):
            child_payload = _build_node(child_obj)
            children_payload.append(child_payload)
            child_counts = child_payload["counts"]
            counts["total"] += int(child_counts["total"])
            counts["new"] += int(child_counts["new"])
            counts["learn"] += int(child_counts["learn"])
            counts["due"] += int(child_counts["due"])
        return {
            "id": deck_obj.id,
            "name": deck_obj.name,
            "parent_id": deck_obj.parent_id,
            "counts": counts,
            "children": children_payload,
        }

    roots = [
        deck_obj
        for deck_obj in scoped_decks
        if deck_obj.parent_id is None or deck_obj.parent_id not in deck_lookup
    ]
    roots.sort(key=lambda deck_obj: ((deck_obj.position or 0), deck_obj.created_at, deck_obj.id))
    return [_build_node(root_obj) for root_obj in roots]


@vocabulary_bp.route("/api/browse/decks/tree", methods=["GET"])
@login_required
def browse_api_decks_tree():
    """Returns deck tree with aggregate card counts."""
    return jsonify({"tree": _build_browse_deck_tree_payload()})


@vocabulary_bp.route("/api/browse/decks", methods=["GET"])
@login_required
def browse_api_decks():
    """Backward-compatible flat deck list endpoint."""
    tree = _build_browse_deck_tree_payload()
    flat_items = []

    def _flatten(nodes: list[dict]):
        for node in nodes:
            flat_items.append(
                {
                    "id": node["id"],
                    "name": node["name"],
                    "parent_id": node["parent_id"],
                    "counts": node.get("counts", {}),
                }
            )
            _flatten(node.get("children", []))

    _flatten(tree)
    return jsonify({"decks": flat_items, "tree": tree})


@vocabulary_bp.route("/api/browse/cards", methods=["GET"])
@login_required
def browse_api_cards():
    """List cards for Browse modal with deck/filter/sort/paging."""
    from models.flashcard import Card, Note

    deck_id_raw = (request.args.get("deck_id") or "").strip()
    include_subdecks_raw = (request.args.get("include_subdecks") or "1").strip().lower()
    include_subdecks = include_subdecks_raw not in {"0", "false", "no"}
    keyword = (request.args.get("q") or "").strip()
    status = (request.args.get("status") or "all").strip().lower()
    tag = (request.args.get("tag") or "").strip()
    sort_by = (request.args.get("sort_by") or "due").strip().lower()
    sort_dir = (request.args.get("sort_dir") or "asc").strip().lower()

    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = max(20, min(200, int(request.args.get("per_page", "100"))))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid page/per_page"}), 400

    scoped_decks = _collect_accessible_browse_decks()
    deck_lookup = {deck.id: deck.name for deck in scoped_decks}
    children_by_parent = _deck_children_map(scoped_decks)
    scoped_ids = {deck.id for deck in scoped_decks}

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .options(
            selectinload(Card.note).selectinload(Note.note_type),
            selectinload(Card.template),
        )
    )
    if not is_admin_user(current_user):
        query = query.filter(Note.user_id == current_user.id)

    if deck_id_raw:
        try:
            selected_deck_id = int(deck_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid deck_id"}), 400
        if selected_deck_id not in scoped_ids:
            return jsonify({"error": "Deck not found"}), 404
        if include_subdecks:
            selected_ids = _collect_subtree_ids(selected_deck_id, children_by_parent)
            query = query.filter(Note.deck_id.in_(selected_ids))
        else:
            query = query.filter(Note.deck_id == selected_deck_id)
    elif scoped_ids:
        query = query.filter(Note.deck_id.in_(scoped_ids))
    else:
        return jsonify(
            {
                "items": [],
                "page": page,
                "per_page": per_page,
                "total": 0,
                "pages": 0,
                "has_next": False,
            }
        )

    if keyword:
        query = query.filter(func.lower(db.cast(Note.field_values, db.Text)).like(f"%{keyword.lower()}%"))
    if tag:
        query = query.filter(func.lower(db.cast(Note.tags, db.Text)).like(f"%{tag.lower()}%"))

    now = datetime.utcnow()
    if status == NEW_QUEUE:
        query = query.filter(Card.queue == NEW_QUEUE)
    elif status == "learn":
        query = query.filter(Card.queue.in_([LEARN_QUEUE, LEARNING_QUEUE, RELEARNING_QUEUE]))
    elif status in {"due", REVIEW_QUEUE}:
        query = query.filter(Card.queue == REVIEW_QUEUE).filter(
            or_(Card.due_at.is_(None), Card.due_at <= now)
        )

    if sort_by == "deck":
        query = query.outerjoin(VocabularyDeck, Note.deck_id == VocabularyDeck.id)
        if sort_dir == "desc":
            query = query.order_by(VocabularyDeck.name.desc(), Card.updated_at.desc())
        else:
            query = query.order_by(VocabularyDeck.name.asc(), Card.updated_at.desc())
    elif sort_by == "word":
        sort_expr = func.lower(db.cast(Note.field_values, db.Text))
        query = query.order_by(sort_expr.desc() if sort_dir == "desc" else sort_expr.asc(), Card.updated_at.desc())
    else:
        if sort_dir == "desc":
            query = query.order_by(Card.due_at.is_(None), Card.due_at.desc(), Card.updated_at.desc())
        else:
            query = query.order_by(Card.due_at.is_(None), Card.due_at.asc(), Card.updated_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    rows = [_build_browse_row(card_obj, deck_lookup, now) for card_obj in pagination.items]
    return jsonify(
        {
            "items": rows,
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
            "pages": pagination.pages,
            "has_next": pagination.has_next,
        }
    )


@vocabulary_bp.route("/api/browse/cards/<card_id>", methods=["GET"])
@login_required
def browse_api_card_detail(card_id: str):
    """Get full card detail for right editor panel."""
    from models.flashcard import Card, Note, NoteType

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id == card_id)
        .options(
            selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
            selectinload(Card.note).selectinload(Note.media_assets),
            selectinload(Card.template),
        )
    )
    if not is_admin_user(current_user):
        query = query.filter(Note.user_id == current_user.id)
    card_obj = query.first()
    if not card_obj:
        return jsonify({"error": "Card not found"}), 404

    deck_lookup = {deck.id: deck.name for deck in _collect_accessible_browse_decks()}
    return jsonify(_build_browse_card_detail(card_obj, deck_lookup, datetime.utcnow()))


@vocabulary_bp.route("/api/browse/cards/<card_id>", methods=["PATCH"])
@login_required
def browse_api_card_update(card_id: str):
    """Update card note fields/deck/tags from Browse editor."""
    from models.flashcard import Card, Note, NoteType

    query = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id)
    if not is_admin_user(current_user):
        query = query.filter(Note.user_id == current_user.id)
    card_obj = query.options(
        selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
        selectinload(Card.note).selectinload(Note.media_assets),
        selectinload(Card.template),
    ).first()
    if not card_obj:
        return jsonify({"error": "Card not found"}), 404

    payload = request.get_json(silent=True) or {}
    note_obj = card_obj.note
    note_type_obj = note_obj.note_type
    field_values = dict(note_obj.field_values or {})

    incoming_values = payload.get("field_values")
    if incoming_values is None and "fields" in payload:
        incoming_values = payload.get("fields")
    if incoming_values is not None:
        if not isinstance(incoming_values, dict):
            return jsonify({"error": "field_values must be an object"}), 400
        for key, value in incoming_values.items():
            key_name = str(key).strip()
            if not key_name:
                continue
            field_values[key_name] = "" if value is None else str(value)

    if note_type_obj:
        for field_def in note_type_obj.field_defs:
            if not field_def.required:
                continue
            if str(field_values.get(field_def.name, "")).strip():
                continue
            return jsonify({"error": f"Field '{field_def.name}' is required"}), 400

    if "deck_id" in payload:
        raw_deck_id = payload.get("deck_id")
        if raw_deck_id in (None, ""):
            note_obj.deck_id = None
        else:
            try:
                selected_deck_id = int(raw_deck_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid deck_id"}), 400
            if not VocabularyDeck.query.get(selected_deck_id):
                return jsonify({"error": "Deck not found"}), 404
            if not is_admin_user(current_user):
                allowed_deck_ids = {deck.id for deck in _collect_accessible_browse_decks()}
                if selected_deck_id not in allowed_deck_ids:
                    return jsonify({"error": "Deck is not accessible"}), 403
            note_obj.deck_id = selected_deck_id

    if "tags" in payload:
        raw_tags = payload.get("tags")
        if isinstance(raw_tags, list):
            note_obj.tags = [str(item).strip() for item in raw_tags if str(item).strip()]
        elif isinstance(raw_tags, str):
            note_obj.tags = [item.strip() for item in raw_tags.split(",") if item.strip()]
        else:
            note_obj.tags = []

    note_obj.field_values = field_values
    db.session.commit()

    deck_lookup = {deck.id: deck.name for deck in _collect_accessible_browse_decks()}
    now = datetime.utcnow()
    return jsonify(
        {
            "success": True,
            "row": _build_browse_row(card_obj, deck_lookup, now),
            "detail": _build_browse_card_detail(card_obj, deck_lookup, now),
        }
    )


@vocabulary_bp.route("/api/browse/cards/<card_id>", methods=["DELETE"])
@login_required
def browse_api_card_delete(card_id: str):
    """Delete one card (and delete its note if last card)."""
    from models.flashcard import Card, Note

    query = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id)
    if not is_admin_user(current_user):
        query = query.filter(Note.user_id == current_user.id)
    card_obj = query.first()
    if not card_obj:
        return jsonify({"error": "Card not found"}), 404

    note_id = card_obj.note_id
    db.session.delete(card_obj)
    db.session.flush()

    remaining = Card.query.filter(Card.note_id == note_id).count()
    if remaining == 0:
        note_obj = Note.query.get(note_id)
        if note_obj:
            db.session.delete(note_obj)
    db.session.commit()
    return jsonify({"success": True})


@vocabulary_bp.route("/api/browse/notes", methods=["GET"])
@login_required
def browse_api_notes():
    """Backward-compatible endpoint for legacy browse page."""
    result = browse_api_cards()
    if isinstance(result, tuple):
        return result
    payload = result.get_json(silent=True) or {}
    notes = []
    for item in payload.get("items", []):
        notes.append(
            {
                "id": item.get("note_id"),
                "sort_field": item.get("word", ""),
                "card_type": item.get("card_type", ""),
                "deck": item.get("deck_name", ""),
                "created_at": "",
                "fields": {
                    "Word": item.get("word", ""),
                    "Reading": item.get("reading", ""),
                    "Meaning": item.get("meaning", ""),
                },
            }
        )
    return jsonify({"notes": notes, "columns": ["Word", "Reading", "Meaning"]})


@vocabulary_bp.route("/api/browse/notes/<note_id>", methods=["PATCH"])
@login_required
def browse_api_update_note(note_id: str):
    """Backward-compatible note update endpoint."""
    from models.flashcard import Note

    note_obj = Note.query.get(note_id)
    if not note_obj:
        return jsonify({"error": "Note not found"}), 404
    if not is_admin_user(current_user) and note_obj.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    payload = request.get_json(silent=True) or {}
    incoming_values = payload.get("fields")
    if not isinstance(incoming_values, dict):
        return jsonify({"error": "Missing fields payload"}), 400

    current_values = dict(note_obj.field_values or {})
    for key, value in incoming_values.items():
        key_name = str(key).strip()
        if not key_name:
            continue
        current_values[key_name] = "" if value is None else str(value)
    note_obj.field_values = current_values
    db.session.commit()
    return jsonify({"success": True, "note": {"id": note_obj.id, "fields": note_obj.field_values}})


@vocabulary_bp.route("/levels/new", methods=["POST"])
@login_required
def create_level():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/decks/create", methods=["POST"])
@login_required
def create_deck():
    """Create deck(s) from path, auto-creating missing parents."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))

    parent_id_raw = (request.form.get("parent_id") or "").strip()
    deck_path_raw = (request.form.get("deck_path") or "").strip()
    deck_name = (request.form.get("name") or "").strip() or "New Deck"
    next_url = _resolve_next_url()

    tokens = [item.strip() for item in deck_path_raw.split("::") if item.strip()]
    if not tokens:
        if parent_id_raw:
            try:
                parent_id = int(parent_id_raw)
            except ValueError:
                flash("Invalid parent deck.", "danger")
                return redirect(next_url)
            parent_deck = VocabularyDeck.query.get(parent_id)
            if not parent_deck:
                flash("Parent deck not found.", "danger")
                return redirect(next_url)
            tokens = [parent_deck.name, deck_name]
        else:
            tokens = [deck_name]

    parent_id = None
    created_count = 0
    created_names: List[str] = []
    final_deck = None
    for token in tokens:
        existing = (
            VocabularyDeck.query.filter(
                VocabularyDeck.parent_id == parent_id,
                VocabularyDeck.name == token,
            )
            .order_by(VocabularyDeck.id.asc())
            .first()
        )
        if existing:
            final_deck = existing
            parent_id = existing.id
            continue

        node = VocabularyDeck(
            parent_id=parent_id,
            name=token,
            position=_next_deck_position(parent_id),
        )
        db.session.add(node)
        db.session.flush()
        created_count += 1
        created_names.append(token)
        final_deck = node
        parent_id = node.id

    db.session.commit()
    if created_count == 0 and final_deck:
        flash(f"Deck already exists: {'::'.join(tokens)}", "info")
    elif created_count == 1 and final_deck:
        flash(f"Created deck: {final_deck.name}", "success")
    else:
        flash(f"Created {created_count} decks: {'::'.join(created_names)}", "success")
    return redirect(next_url)


@vocabulary_bp.route("/decks/<int:deck_id>/rename", methods=["POST"])
@login_required
def rename_deck(deck_id: int):
    """Rename an existing deck."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
        
    deck = VocabularyDeck.query.get_or_404(deck_id)
    new_name = (request.form.get("name") or "").strip()
    next_url = _resolve_next_url()

    if not new_name:
        flash("Deck name cannot be empty.", "warning")
        return redirect(next_url)
    if new_name == deck.name:
        flash("Deck name is unchanged.", "info")
        return redirect(next_url)
    if _deck_name_exists_under_parent(parent_id=deck.parent_id, name=new_name, exclude_deck_id=deck.id):
        flash(f"Deck '{new_name}' already exists at this level.", "danger")
        return redirect(next_url)

    deck.name = new_name
    try:
        db.session.commit()
        flash(f"Deck renamed to: {new_name}", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Failed to rename deck. Please try again.", "danger")
    return redirect(next_url)


@vocabulary_bp.route("/decks/move", methods=["POST"])
@vocabulary_bp.route("/decks/<int:deck_id>/move", methods=["POST"])
@login_required
def move_deck(deck_id: int | None = None):
    """Move a deck to a new parent deck."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    
    next_url = _resolve_next_url()
    if deck_id is None:
        deck_token = (request.form.get("deck_token") or "").strip()
        deck_id = parse_deck_move_token(deck_token, user_id=current_user.id)
        if deck_id is None:
            flash("Move token is invalid or expired. Please reopen Deck Settings.", "danger")
            return redirect(next_url)

    deck = VocabularyDeck.query.get_or_404(deck_id)
    parent_token_raw = (request.form.get("parent_token") or "").strip()
    parent_id_raw = (request.form.get("parent_id") or "").strip()

    new_parent_id = None
    new_parent = None
    if parent_token_raw:
        parsed_parent_id = parse_deck_move_token(parent_token_raw, user_id=current_user.id)
        if parsed_parent_id is None:
            flash("Parent move token is invalid or expired.", "danger")
            return redirect(next_url)
        new_parent_id = parsed_parent_id
    elif parent_id_raw:
        try:
            new_parent_id = int(parent_id_raw)
        except ValueError:
            flash("Invalid parent deck.", "danger")
            return redirect(next_url)

    if new_parent_id is not None:
        new_parent = VocabularyDeck.query.get(new_parent_id)
        if not new_parent:
            flash("Parent deck not found.", "danger")
            return redirect(next_url)

        # Prevent moving into itself or its own descendants
        curr = new_parent
        while curr:
            if curr.id == deck.id:
                flash("Cannot move a deck into itself or its descendants.", "danger")
                return redirect(next_url)
            curr = curr.parent

    if deck.parent_id == new_parent_id:
        flash("Deck is already in the selected location.", "info")
        return redirect(next_url)
    if _deck_name_exists_under_parent(parent_id=new_parent_id, name=deck.name, exclude_deck_id=deck.id):
        parent_label = new_parent.name if new_parent else "Root"
        flash(f"Parent '{parent_label}' already has a deck named '{deck.name}'.", "danger")
        return redirect(next_url)

    deck.parent_id = new_parent_id
    deck.position = _next_deck_position(new_parent_id)
    try:
        db.session.commit()
        flash(f"Deck '{deck.name}' moved successfully.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Failed to move deck. Please try again.", "danger")
    
    return redirect(next_url)


def _collect_deck_ancestor_ids(deck_id: int) -> list[int]:
    ancestor_ids: list[int] = []
    current_id = int(deck_id)
    seen_ids: set[int] = set()

    while current_id not in seen_ids:
        seen_ids.add(current_id)
        ancestor_ids.append(current_id)
        parent_row = (
            db.session.query(VocabularyDeck.parent_id)
            .filter(VocabularyDeck.id == current_id)
            .first()
        )
        if not parent_row or parent_row[0] is None:
            break
        current_id = int(parent_row[0])

    return ancestor_ids


def _can_current_user_delete_cloned_deck(deck_obj: VocabularyDeck) -> bool:
    if deck_obj.owner_user_id != current_user.id:
        return False

    from models.flashcard import DeckInstall

    ancestor_ids = _collect_deck_ancestor_ids(deck_obj.id)
    if not ancestor_ids:
        return False

    install_row = (
        db.session.query(DeckInstall.id)
        .filter(
            DeckInstall.user_id == current_user.id,
            DeckInstall.local_deck_id.in_(ancestor_ids),
        )
        .first()
    )
    return install_row is not None


@vocabulary_bp.route("/decks/<int:deck_id>/delete", methods=["POST"])
@login_required
def delete_deck(deck_id: int):
    """Delete a deck subtree and all Note/Card data inside it."""
    deck = VocabularyDeck.query.get_or_404(deck_id)
    if not is_admin_user(current_user) and not _can_current_user_delete_cloned_deck(deck):
        flash("You do not have permission to delete this deck.", "danger")
        return redirect(url_for("main.dashboard"))

    deck_name = deck.name
    next_url = _resolve_next_url()

    all_decks = VocabularyDeck.query.order_by(
        VocabularyDeck.parent_id.isnot(None),
        VocabularyDeck.position,
        VocabularyDeck.created_at,
        VocabularyDeck.id,
    ).all()
    children_by_parent = _deck_children_map(all_decks)
    deck_ids_to_delete = _collect_subtree_ids(deck.id, children_by_parent)

    from models.flashcard import DeckInstall

    install_query = DeckInstall.query.filter(DeckInstall.local_deck_id.in_(deck_ids_to_delete))
    if not is_admin_user(current_user):
        install_query = install_query.filter(DeckInstall.user_id == current_user.id)
    install_query.delete(synchronize_session=False)

    note_rows = db.session.query(Note.id).filter(Note.deck_id.in_(deck_ids_to_delete)).all()
    note_ids = [str(row[0]) for row in note_rows if row and row[0]]
    if note_ids:
        card_rows = db.session.query(Card.id).filter(Card.note_id.in_(note_ids)).all()
        card_ids = [str(row[0]) for row in card_rows if row and row[0]]
        if card_ids:
            VocabularyProgress.query.filter(VocabularyProgress.new_card_id.in_(card_ids)).delete(
                synchronize_session=False
            )
            Card.query.filter(Card.id.in_(card_ids)).delete(synchronize_session=False)
        Note.query.filter(Note.id.in_(note_ids)).delete(synchronize_session=False)

    db.session.delete(deck)
    db.session.commit()

    flash(f"Deleted deck '{deck_name}' and all its contents.", "success")
    return redirect(next_url)


@vocabulary_bp.route("/decks/<int:deck_id>/reset", methods=["POST"])
@login_required
def reset_deck(deck_id: int):
    """Reset current-user progress for cards within a deck subtree."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))

    deck = VocabularyDeck.query.get_or_404(deck_id)
    next_url = _resolve_next_url()

    all_decks = VocabularyDeck.query.order_by(
        VocabularyDeck.parent_id.isnot(None),
        VocabularyDeck.position,
        VocabularyDeck.created_at,
        VocabularyDeck.id,
    ).all()
    children_by_parent = _deck_children_map(all_decks)
    deck_ids = _collect_subtree_ids(deck.id, children_by_parent)

    card_rows = (
        db.session.query(Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(Note.deck_id.in_(deck_ids))
        .all()
    )
    card_ids = [str(row[0]) for row in card_rows if row and row[0]]

    if card_ids:
        deleted_count = (
            VocabularyProgress.query.filter(
                VocabularyProgress.user_id == current_user.id,
                VocabularyProgress.new_card_id.in_(card_ids),
            ).delete(synchronize_session=False)
            or 0
        )
        db.session.commit()
        flash(f"Reset progress for {deleted_count} cards in '{deck.name}' (your account).", "success")
    else:
        flash(f"No cards to reset in '{deck.name}'.", "info")

    return redirect(next_url)


@vocabulary_bp.route("/topics/new", methods=["POST"])
@login_required
def create_topic():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lessons/new", methods=["POST"])
@login_required
def create_lesson():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lessons/<int:lesson_id>/delete", methods=["POST"])
@login_required
def delete_lesson(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/topics/<int:topic_id>/delete", methods=["POST"])
@login_required
def delete_topic(topic_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/topic/<int:topic_id>/open")
@login_required
def open_topic(topic_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/topic/<int:topic_id>")
@login_required
def topic(topic_id: int):
    return _legacy_structure_removed_response()


def _select_next_note_card(cards: List[Card], progress_map: Dict[str, VocabularyProgress], now: datetime):
    due_learn: list[Card] = []
    due_relearn: list[Card] = []
    due_review: list[Card] = []
    due_new: list[Card] = []
    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue == LEARNING_QUEUE:
            due_learn.append(card_obj)
        elif queue == RELEARNING_QUEUE:
            due_relearn.append(card_obj)
        elif queue == REVIEW_QUEUE:
            due_review.append(card_obj)
        else:
            due_new.append(card_obj)

    if due_relearn:
        return due_relearn[0]
    if due_learn:
        return due_learn[0]
    if due_review:
        return due_review[0]
    if due_new:
        return due_new[0]
    return None


def _build_note_study_card_payload(card_obj: Card | None) -> SimpleNamespace | None:
    if not card_obj or not card_obj.note:
        return None

    note_obj = card_obj.note
    field_values = _note_field_values_as_strings(note_obj)
    display_triplet = _note_display_triplet(note_obj)
    note_type_obj = note_obj.note_type
    field_defs = sorted(note_type_obj.field_defs, key=lambda item: item.position) if note_type_obj else []

    payload = {
        "id": card_obj.id,
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


def _render_note_study_flashcard(card_obj: Card | None) -> dict:
    from app.services.flashcard_renderer import TemplateCompileError, render_template_pair

    ret = {"front": "", "back": ""}
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
            allow_inline_script=True,
        )
        ret["front"] = rendered.get("front_html", "")
        ret["back"] = rendered.get("back_html", "")
    except TemplateCompileError as exc:
        ret["front"] = f"<div class='text-danger'>Error rendering front: {exc}</div>"
        ret["back"] = f"<div class='text-danger'>Error rendering back: {exc}</div>"

    return ret


def _query_study_cards_for_deck_ids(deck_ids: list[int]) -> list[Card]:
    if not deck_ids:
        return []

    return (
        Card.query.join(Note, Card.note_id == Note.id)
        .options(
            selectinload(Card.template),
            selectinload(Card.note).selectinload(Note.note_type),
            selectinload(Card.note).selectinload(Note.media_assets),
        )
        .filter(
            Note.user_id == current_user.id,
            Note.deck_id.in_(deck_ids),
        )
        .order_by(Card.created_at.asc(), Card.id.asc())
        .all()
    )


def _load_card_progress_map(card_ids: list[str]) -> dict[str, VocabularyProgress]:
    if not card_ids:
        return {}

    rows = VocabularyProgress.query.filter(
        VocabularyProgress.user_id == current_user.id,
        VocabularyProgress.new_card_id.in_(card_ids),
    ).all()
    return {row.new_card_id: row for row in rows if row.new_card_id}


def _count_due_note_cards(
    cards: list[Card],
    progress_map: dict[str, VocabularyProgress],
    *,
    now: datetime,
) -> tuple[int, int, int]:
    due_new = 0
    due_learn = 0
    due_review = 0
    for card_obj in cards:
        progress = progress_map.get(card_obj.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else NEW_QUEUE
        if queue in {LEARNING_QUEUE, RELEARNING_QUEUE}:
            due_learn += 1
        elif queue == REVIEW_QUEUE:
            due_review += 1
        else:
            due_new += 1
    return due_new, due_learn, due_review


@vocabulary_bp.route("/study/topic/<int:topic_id>")
@login_required
def study_topic(topic_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/study/deck/<int:deck_id>")
@login_required
def study_deck(deck_id: int):
    """Study cards across a deck subtree using Note/Card as the source of truth."""
    all_decks = VocabularyDeck.query.order_by(
        VocabularyDeck.parent_id.isnot(None),
        VocabularyDeck.position,
        VocabularyDeck.created_at,
        VocabularyDeck.id,
    ).all()
    deck_map = {deck.id: deck for deck in all_decks}
    root_deck = deck_map.get(deck_id)
    if not root_deck:
        abort(404)

    children_by_parent: Dict[int | None, List[VocabularyDeck]] = {}
    for deck in all_decks:
        children_by_parent.setdefault(deck.parent_id, []).append(deck)

    subtree_ids: List[int] = []

    def _collect(deck_node_id: int):
        subtree_ids.append(deck_node_id)
        for child in children_by_parent.get(deck_node_id, []):
            _collect(child.id)

    _collect(root_deck.id)

    cards = _query_study_cards_for_deck_ids(subtree_ids)
    now = datetime.utcnow()
    card_ids = [card_obj.id for card_obj in cards]
    progress_map = _load_card_progress_map(card_ids)

    selected_card = _select_next_note_card(cards, progress_map, now)
    due_new, due_learn, due_review = _count_due_note_cards(cards, progress_map, now=now)

    next_intervals_preview = None
    if selected_card:
        card_state = _card_state_from_progress(progress_map.get(selected_card.id), now)
        next_intervals_preview = computeAnswerPreview(card_state, default_deck_options(), now)

    rendered_data = _render_note_study_flashcard(selected_card)
    card_payload = _build_note_study_card_payload(selected_card)

    return render_template(
        "vocabulary_study.html",
        selected_level=None,
        selected_topic=SimpleNamespace(id=root_deck.id, name=root_deck.name),
        selected_lesson=None,
        card=card_payload,
        rendered_front=rendered_data.get("front"),
        rendered_back=rendered_data.get("back"),
        due_new=due_new,
        due_learn=due_learn,
        due_review=due_review,
        due_total=due_new + due_learn + due_review,
        admin_mode=is_admin_user(current_user),
        study_scope="deck",
        study_scope_id=root_deck.id,
        study_root_name=root_deck.name,
        study_root_url=url_for("vocabulary.study_deck", deck_id=root_deck.id),
        next_study_url=url_for("vocabulary.study_deck", deck_id=root_deck.id),
        next_intervals_preview=next_intervals_preview,
        answer_url=(url_for("flashcards.study_answer", card_id=selected_card.id) if selected_card else None),
        edit_action_url=None,
    )


@vocabulary_bp.route("/study/lesson/<int:lesson_id>")
@login_required
def study_lesson(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lesson/<int:lesson_id>")
@login_required
def lesson(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/lesson/<int:lesson_id>/download")
@login_required
def download_lesson_csv(lesson_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/column-widths", methods=["POST"])
@login_required
def save_column_width():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entry", methods=["POST"])
@login_required
def create_entry():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entry/<int:entry_id>/field", methods=["POST"])
@login_required
def update_entry_field(entry_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entry/<int:entry_id>/fields", methods=["POST"])
@login_required
def update_entry_fields(entry_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entries/bulk", methods=["POST"])
@login_required
def bulk_update_entries():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    return _legacy_structure_removed_response()
