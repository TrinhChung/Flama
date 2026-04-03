"""Vocabulary management routes."""

from __future__ import annotations

import hashlib
import io
import re
from datetime import UTC, datetime
from pathlib import Path
from types import SimpleNamespace
from typing import Dict, List
from uuid import uuid4

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    send_file,
    request,
    url_for,
)
from flask_login import current_user, login_required
from sqlalchemy import func, or_
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import aliased, selectinload
from werkzeug.utils import secure_filename

from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.deck_tree_query import collect_subtree_ids as _collect_deck_subtree_ids
from app.repositories.study_repository import (
    LEARNING_QUEUE,
    LEARN_QUEUE,
    NEW_QUEUE,
    RELEARNING_QUEUE,
    REVIEW_QUEUE,
    active_progress_expr as _active_progress_expr,
    apply_card_state_to_progress as _apply_card_state_to_progress,
    card_state_from_progress as _card_state_from_progress,
    load_card_progress_map as _load_card_progress_map_for_user,
    normalized_queue_expr as _normalized_queue_expr,
    review_due_expr as _review_due_expr,
    select_next_due_card_from_loaded as _select_next_due_card_from_loaded,
    summarize_pending_learning_from_loaded as _summarize_pending_learning_from_loaded,
)
from app.utils.deck_move_token import parse_deck_move_token
from app.utils.permissions import is_admin_user
from app.services import tts_provider_service
from app.services.anki_scheduler import (
    computeAnswerPreview,
)
from app.services.scheduler_config_service import resolve_deck_options
from app.services.flashcard_renderer import TemplateCompileError, render_template_pair
from app.services.stats_overview import get_effective_timezone_name
from app.validators import (
    escape_like_pattern,
    RequestValidationError,
    validate_browse_card_update_request,
    validate_legacy_browse_note_update_request,
    sanitize_query_text,
)
from models import db
from models.flashcard import Card, Note
from models.deck import Deck
from models.card_progress import CardProgress

vocabulary_bp = Blueprint("vocabulary", __name__, url_prefix="/vocabulary")
_VOICEVOX_TEMPLATE_TOKEN_RE = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")
_AUDIO_FILE_EXT_RE = re.compile(r"\.(mp3|wav|ogg|opus|flac|m4a|aac|webm)(?:\?.*)?$", re.IGNORECASE)
_MD_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\([^)]+\)")
_MD_LINK_RE = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_MD_INLINE_STYLE_RE = re.compile(r"(\*\*|__|\*|_|~~|`)")
_MD_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s*")
_MD_LIST_MARKER_RE = re.compile(r"(?m)^\s{0,3}(?:[-+*]|\d+\.)\s+")


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


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
        "vocabulary.create_deck",
        "vocabulary.browse_api_decks_tree",
        "vocabulary.browse_api_cards",
        "vocabulary.browse_api_card_detail",
        "vocabulary.browse_api_card_update",
        "vocabulary.browse_api_card_delete",
        "vocabulary.browse_api_decks",
        "vocabulary.browse_api_notes",
        "vocabulary.browse_api_update_note",
        "vocabulary.browse_api_voicevox_preview",
        "vocabulary.browse_api_voicevox_precheck",
        "vocabulary.browse_api_voicevox_generate",
        "vocabulary.delete_deck",
        "vocabulary.reset_deck",
    }
    if endpoint in allowed_endpoints:
        return None
    return redirect(url_for("main.dashboard"))


def _legacy_structure_removed_response():
    message = (
        "Legacy Level/Topic/Lesson/Entry workflow has been removed. "
        "Use Deck + NoteType + Note + Card schema only."
    )
    if request.is_json:
        return jsonify({"success": False, "error": "LEGACY_STRUCTURE_REMOVED", "message": message}), 410
    if request.method == "GET":
        return message, 410
    flash(message, "warning")
    next_url = (request.form.get("next") or request.args.get("next") or "").strip()
    return redirect(next_url or url_for("vocabulary.browse"))




def _resolve_next_url(default_endpoint: str = "main.dashboard") -> str:
    """Return a safe in-app redirect target from `next` form value."""
    raw_next = (request.form.get("next") or "").strip()
    if raw_next.startswith("/") and not raw_next.startswith("//"):
        return raw_next
    return url_for(default_endpoint)




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




























def _normalize_tags_payload(raw_tags) -> list[str]:
    if isinstance(raw_tags, list):
        return [str(item).strip() for item in raw_tags if str(item).strip()]
    if isinstance(raw_tags, str):
        return [item.strip() for item in raw_tags.split(",") if item.strip()]
    return []


def _to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "y"}


def _collect_note_media_refs(note_obj: Note | None) -> set[str]:
    refs: set[str] = set()
    if note_obj is None:
        return refs
    for asset in note_obj.media_assets or []:
        asset_id = str(getattr(asset, "id", "") or "").strip()
        if asset_id:
            refs.add(asset_id)
            refs.add(f"/media/proxy/{asset_id}")
        filename = str(getattr(asset, "filename", "") or "").strip()
        if filename:
            refs.add(filename)
            refs.add(f"[sound:{filename}]")
    return refs


def _strip_richtext_to_plain(raw_value: object) -> str:
    text = str(raw_value or "")
    no_tags = re.sub(r"(?is)<[^>]+>", " ", text)
    normalized = " ".join(no_tags.replace("&nbsp;", " ").split())
    return normalized.strip()


def _strip_markdown_to_plain(raw_value: object) -> str:
    text = str(raw_value or "")
    text = _MD_IMAGE_RE.sub(r" \1 ", text)
    text = _MD_LINK_RE.sub(r" \1 ", text)
    text = _MD_HEADING_RE.sub("", text)
    text = _MD_LIST_MARKER_RE.sub("", text)
    text = _MD_INLINE_STYLE_RE.sub("", text)
    normalized = " ".join(text.split())
    return normalized.strip()


def _slug_filename_component(raw_value: object, *, fallback: str, max_len: int = 80) -> str:
    raw_text = str(raw_value or "").strip()
    if not raw_text:
        return fallback
    safe = secure_filename(raw_text).strip("._-")
    if not safe:
        safe = fallback
    return safe[:max_len] or fallback


def _render_voicevox_filename(
    *,
    template: str,
    extension: str,
    speaker_label: str,
    style_label: str,
    note_id: str,
    sequence: int,
) -> str:
    token_values = {
        "speaker": _slug_filename_component(speaker_label, fallback="speaker"),
        "style": _slug_filename_component(style_label, fallback="style"),
        "uid": uuid4().hex[:12],
        "note_id": _slug_filename_component(note_id, fallback="note", max_len=36),
        "index": str(int(sequence)),
        "date": _utcnow().strftime("%Y%m%d"),
        "timestamp": _utcnow().strftime("%Y%m%d%H%M%S"),
    }
    raw_template = str(template or "").strip() or "VOICEVOX-{{speaker}}_{{style}}_{{uid}}"

    def _replace_token(match: re.Match[str]) -> str:
        key = str(match.group(1) or "").strip().lower()
        return token_values.get(key, "")

    rendered = _VOICEVOX_TEMPLATE_TOKEN_RE.sub(_replace_token, raw_template).strip()
    base_name = secure_filename(rendered).strip("._-")
    if not base_name:
        base_name = f"voicevox_{token_values['uid']}"
    ext = _slug_filename_component(extension, fallback="wav", max_len=10).lstrip(".")
    return f"{base_name}.{ext}"


def _looks_like_audio_token(raw_value: object) -> bool:
    token = str(raw_value or "").strip()
    if not token:
        return False
    token_lower = token.lower()
    if token_lower.startswith("[sound:") and token.endswith("]"):
        return True
    if "<audio" in token_lower or token_lower.startswith("/media/proxy/"):
        return True
    if _AUDIO_FILE_EXT_RE.search(token_lower):
        return True
    return False


def _is_audio_like_field_value(raw_value: object) -> bool:
    text = str(raw_value or "").strip()
    if not text:
        return False

    chunks = [line.strip() for line in re.split(r"[\r\n]+", text) if line and line.strip()]
    if not chunks:
        return False
    return all(_looks_like_audio_token(chunk) for chunk in chunks)


def _apply_clone_overlay_to_browse_payload(
    *,
    payload: dict,
    card_obj: Card,
    clone_scope,
    deck_lookup: dict[int, str],
):
    from app.services import flashcards_share as share_ctrl

    note_obj = card_obj.note
    if note_obj is None or note_obj.deck_id is None:
        return payload

    source_note_type_id = (clone_scope.install.source_note_type_id or note_obj.note_type_id or "").strip()
    if source_note_type_id:
        schema_view = share_ctrl.build_clone_schema_view(
            install=clone_scope.install,
            source_note_type_id=source_note_type_id,
        )
        overlay_field_defs = schema_view.field_defs or (note_obj.note_type.field_defs if note_obj.note_type else [])
        overlay_field_values = share_ctrl.apply_clone_note_field_overrides(
            install=clone_scope.install,
            source_note=note_obj,
            schema_view=schema_view,
        )
    else:
        overlay_field_defs = note_obj.note_type.field_defs if note_obj.note_type else []
        overlay_field_values = dict(note_obj.field_values or {})

    normalized_values = {
        str(key).strip(): "" if value is None else str(value)
        for key, value in dict(overlay_field_values or {}).items()
        if str(key).strip()
    }
    ordered_defs = sorted(
        overlay_field_defs or [],
        key=lambda item: (int(getattr(item, "position", 0) or 0), str(getattr(item, "name", "")).lower()),
    )

    local_deck_id = (
        (clone_scope.source_to_local_deck_id or {}).get(int(note_obj.deck_id))
        or clone_scope.install.local_deck_id
    )
    local_deck_name = deck_lookup.get(int(local_deck_id or 0), "")

    proxy_note = SimpleNamespace(
        field_values=normalized_values,
        note_type=SimpleNamespace(field_defs=ordered_defs),
    )
    display_triplet = vocabulary_ctrl.note_display_triplet(proxy_note)

    card_payload = payload.get("card")
    if isinstance(card_payload, dict):
        card_payload["word"] = display_triplet.get("word", "")
        card_payload["reading"] = display_triplet.get("reading", "")
        card_payload["meaning"] = display_triplet.get("meaning", "")
        if local_deck_id is not None:
            card_payload["deck_id"] = int(local_deck_id)
        if local_deck_name:
            card_payload["deck_name"] = local_deck_name

    note_payload = payload.get("note")
    if isinstance(note_payload, dict):
        note_payload["field_values"] = normalized_values
        if local_deck_id is not None:
            note_payload["deck_id"] = int(local_deck_id)
        note_payload["deck_name"] = local_deck_name

    note_type_fields_payload = []
    for field_def in ordered_defs:
        field_name = str(getattr(field_def, "name", "") or "").strip()
        if not field_name:
            continue
        try:
            field_position = int(getattr(field_def, "position", 0) or 0)
        except (TypeError, ValueError):
            field_position = 0
        note_type_fields_payload.append(
            {
                "name": field_name,
                "field_type": str(getattr(field_def, "field_type", "text") or "text"),
                "required": bool(getattr(field_def, "required", False)),
                "position": field_position,
            }
        )
    fields_payload = list(note_type_fields_payload)
    existing_names = {field_def["name"] for field_def in note_type_fields_payload}
    for key in normalized_values:
        if key in existing_names:
            continue
        fields_payload.append(
            {
                "name": key,
                "field_type": "text",
                "required": False,
                "position": 9999,
            }
        )
    fields_payload.sort(key=lambda item: (int(item["position"]), item["name"].lower()))
    payload["fields"] = fields_payload
    payload["note_type_fields"] = note_type_fields_payload
    return payload


@vocabulary_bp.route("/api/browse/decks/tree", methods=["GET"])
@login_required
def browse_api_decks_tree():
    """Returns deck tree with aggregate card counts."""
    return jsonify(
        {
            "tree": vocabulary_ctrl.build_browse_deck_tree_payload(
                user_id=current_user.id,
                admin_mode=is_admin_user(current_user),
                timezone_name=get_effective_timezone_name(getattr(current_user, "timezone", "UTC")),
            )
        }
    )


@vocabulary_bp.route("/api/browse/decks", methods=["GET"])
@login_required
def browse_api_decks():
    """Backward-compatible flat deck list endpoint."""
    tree = vocabulary_ctrl.build_browse_deck_tree_payload(
        user_id=current_user.id,
        admin_mode=is_admin_user(current_user),
        timezone_name=get_effective_timezone_name(getattr(current_user, "timezone", "UTC")),
    )
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
    from app.services import flashcards_share as share_ctrl
    from models.flashcard import Card, DeckInstall, Note

    deck_id_raw = (request.args.get("deck_id") or "").strip()
    include_subdecks_raw = (request.args.get("include_subdecks") or "1").strip().lower()
    include_subdecks = include_subdecks_raw not in {"0", "false", "no"}
    try:
        keyword = sanitize_query_text(request.args.get("q"), field_name="q", max_length=120)
        tag = sanitize_query_text(request.args.get("tag"), field_name="tag", max_length=80)
    except RequestValidationError as exc:
        return jsonify({"error": str(exc), "field": exc.field, "code": exc.code}), exc.status

    status = (request.args.get("status") or "all").strip().lower()
    sort_by = (request.args.get("sort_by") or "due").strip().lower()
    sort_dir = (request.args.get("sort_dir") or "asc").strip().lower()

    if status not in {"all", NEW_QUEUE, "learn", "due", REVIEW_QUEUE}:
        return jsonify({"error": "Invalid status filter.", "field": "status"}), 400
    if sort_by not in {"due", "deck", "word"}:
        return jsonify({"error": "Invalid sort_by.", "field": "sort_by"}), 400
    if sort_dir not in {"asc", "desc"}:
        return jsonify({"error": "Invalid sort_dir.", "field": "sort_dir"}), 400

    try:
        page = max(1, int(request.args.get("page", "1")))
        per_page = max(20, min(200, int(request.args.get("per_page", "100"))))
    except (TypeError, ValueError):
        return jsonify({"error": "Invalid page/per_page"}), 400

    def _empty_result():
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

    scoped_decks = vocabulary_ctrl.collect_accessible_browse_decks(
        user_id=current_user.id,
        admin_mode=is_admin_user(current_user),
    )
    deck_lookup = {deck.id: deck.name for deck in scoped_decks}
    children_by_parent = vocabulary_ctrl.deck_children_map(scoped_decks)
    scoped_ids = {deck.id for deck in scoped_decks}
    selected_ids: set[int] | None = None
    if deck_id_raw:
        try:
            selected_deck_id = int(deck_id_raw)
        except (TypeError, ValueError):
            return jsonify({"error": "Invalid deck_id"}), 400
        if selected_deck_id not in scoped_ids:
            return jsonify({"error": "Deck not found"}), 404
        if include_subdecks:
            selected_ids = set(vocabulary_ctrl.collect_subtree_ids(selected_deck_id, children_by_parent))
        else:
            selected_ids = {selected_deck_id}

    progress_alias = aliased(CardProgress)
    progress_join = db.and_(
        progress_alias.card_id == Card.id,
        progress_alias.user_id == current_user.id,
    )

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .outerjoin(progress_alias, progress_join)
        .options(
            selectinload(Card.note).selectinload(Note.note_type),
            selectinload(Card.template),
        )
    )
    if is_admin_user(current_user):
        if selected_ids:
            query = query.filter(Note.deck_id.in_(selected_ids))
        elif scoped_ids:
            query = query.filter(Note.deck_id.in_(scoped_ids))
        else:
            return _empty_result()
    else:
        local_scope_ids = set(selected_ids or scoped_ids)
        clone_scopes = []
        source_to_local_deck_id: dict[int, int] = {}

        if selected_ids is not None:
            scope_candidates = sorted(local_scope_ids)
        else:
            install_root_rows = (
                db.session.query(DeckInstall.local_deck_id)
                .filter(
                    DeckInstall.user_id == current_user.id,
                    DeckInstall.clone_mode == "logical_overlay",
                    DeckInstall.local_deck_id.isnot(None),
                )
                .distinct()
                .all()
            )
            scope_candidates = [
                int(row[0])
                for row in install_root_rows
                if row and row[0] is not None
            ]

        covered_local_ids: set[int] = set()
        seen_scope_keys: set[tuple[str, int]] = set()
        for local_scope_deck_id in scope_candidates:
            if selected_ids is not None and local_scope_deck_id in covered_local_ids:
                continue
            clone_scope = share_ctrl.resolve_clone_scope_for_local_deck(
                user_id=current_user.id,
                local_deck_id=int(local_scope_deck_id),
            )
            if clone_scope is None or not clone_scope.source_deck_ids:
                continue
            scope_key = (clone_scope.install.id, int(clone_scope.local_scope_deck_id))
            if scope_key in seen_scope_keys:
                continue
            seen_scope_keys.add(scope_key)
            clone_scopes.append(clone_scope)
            covered_local_ids.update(
                int(deck_id)
                for deck_id in clone_scope.local_deck_ids
                if deck_id is not None
            )
            for source_deck_id, local_deck_id in (clone_scope.source_to_local_deck_id or {}).items():
                source_to_local_deck_id.setdefault(int(source_deck_id), int(local_deck_id))

        visibility_filters = []
        if local_scope_ids:
            visibility_filters.append(
                db.and_(
                    Note.user_id == current_user.id,
                    Note.deck_id.in_(local_scope_ids),
                )
            )
        for clone_scope in clone_scopes:
            scope_filters = [Note.deck_id.in_(clone_scope.source_deck_ids)]
            if clone_scope.source_owner_user_id is not None:
                scope_filters.append(Note.user_id == clone_scope.source_owner_user_id)
            if clone_scope.base_snapshot_at is not None:
                scope_filters.extend(
                    [
                        Note.created_at <= clone_scope.base_snapshot_at,
                        Card.created_at <= clone_scope.base_snapshot_at,
                    ]
                )
            visibility_filters.append(db.and_(*scope_filters))

        if not visibility_filters:
            return _empty_result()
        query = query.filter(db.or_(*visibility_filters))

        for source_deck_id, local_deck_id in source_to_local_deck_id.items():
            local_name = deck_lookup.get(local_deck_id)
            if local_name:
                deck_lookup.setdefault(source_deck_id, local_name)

    if keyword:
        keyword_like = f"%{escape_like_pattern(keyword.lower())}%"
        query = query.filter(
            func.lower(db.cast(Note.field_values, db.Text)).like(keyword_like, escape="\\")
        )
    if tag:
        tag_like = f"%{escape_like_pattern(tag.lower())}%"
        query = query.filter(
            func.lower(db.cast(Note.tags, db.Text)).like(tag_like, escape="\\")
        )

    now = _utcnow()
    normalized_progress_queue = _normalized_queue_expr(progress_alias)
    query = query.filter(_active_progress_expr(progress_alias))
    if status == NEW_QUEUE:
        query = query.filter(
            db.or_(
                progress_alias.id.is_(None),
                normalized_progress_queue == NEW_QUEUE,
            )
        )
    elif status == "learn":
        query = query.filter(normalized_progress_queue.in_([LEARNING_QUEUE, RELEARNING_QUEUE]))
    elif status in {"due", REVIEW_QUEUE}:
        query = query.filter(
            normalized_progress_queue == REVIEW_QUEUE,
            _review_due_expr(progress_alias, now=now),
        )

    if sort_by == "deck":
        query = query.outerjoin(Deck, Note.deck_id == Deck.id)
        if sort_dir == "desc":
            query = query.order_by(Deck.name.desc(), Card.updated_at.desc())
        else:
            query = query.order_by(Deck.name.asc(), Card.updated_at.desc())
    elif sort_by == "word":
        sort_expr = func.lower(db.cast(Note.field_values, db.Text))
        query = query.order_by(sort_expr.desc() if sort_dir == "desc" else sort_expr.asc(), Card.updated_at.desc())
    else:
        due_sort_day_expr = db.case(
            (normalized_progress_queue == REVIEW_QUEUE, progress_alias.due_day),
            else_=None,
        )
        due_sort_expr = progress_alias.due_at
        if sort_dir == "desc":
            query = query.order_by(
                due_sort_day_expr.is_(None),
                due_sort_day_expr.desc(),
                due_sort_expr.is_(None),
                due_sort_expr.desc(),
                Card.updated_at.desc(),
            )
        else:
            query = query.order_by(
                due_sort_day_expr.is_(None),
                due_sort_day_expr.asc(),
                due_sort_expr.is_(None),
                due_sort_expr.asc(),
                Card.updated_at.desc(),
            )

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    progress_map = _load_card_progress_map([card_obj.id for card_obj in pagination.items])
    rows = []
    for card_obj in pagination.items:
        row_payload = vocabulary_ctrl.build_browse_row(
            card_obj,
            deck_lookup,
            now,
            progress_obj=progress_map.get(card_obj.id),
            timezone_name=get_effective_timezone_name(getattr(current_user, "timezone", "UTC")),
        )
        if not is_admin_user(current_user) and card_obj.note and card_obj.note.user_id != current_user.id:
            clone_scope = share_ctrl.resolve_clone_scope_for_card(
                user_id=current_user.id,
                card_obj=card_obj,
            )
            if clone_scope is not None and share_ctrl.is_card_visible_in_clone_scope(
                scope=clone_scope,
                card_obj=card_obj,
            ):
                adjusted_payload = _apply_clone_overlay_to_browse_payload(
                    payload={"card": row_payload, "note": {}, "fields": []},
                    card_obj=card_obj,
                    clone_scope=clone_scope,
                    deck_lookup=deck_lookup,
                )
                row_payload = adjusted_payload.get("card") or row_payload
        rows.append(row_payload)
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
    from app.services import flashcards_share as share_ctrl
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
    card_obj = query.first()
    if not card_obj:
        return jsonify({"error": "Card not found"}), 404

    deck_lookup = {
        deck.id: deck.name
        for deck in vocabulary_ctrl.collect_accessible_browse_decks(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
        )
    }
    clone_scope = None
    if not is_admin_user(current_user) and card_obj.note and card_obj.note.user_id != current_user.id:
        clone_scope = share_ctrl.resolve_clone_scope_for_card(
            user_id=current_user.id,
            card_obj=card_obj,
        )
        if clone_scope is None or not share_ctrl.is_card_visible_in_clone_scope(
            scope=clone_scope,
            card_obj=card_obj,
        ):
            return jsonify({"error": "Card not found"}), 404
        for source_deck_id, local_deck_id in (clone_scope.source_to_local_deck_id or {}).items():
            local_name = deck_lookup.get(int(local_deck_id))
            if local_name:
                deck_lookup.setdefault(int(source_deck_id), local_name)

    progress = CardProgress.query.filter_by(
        user_id=current_user.id,
        card_id=card_obj.id,
    ).first()
    payload = vocabulary_ctrl.build_browse_card_detail(
        card_obj,
        deck_lookup,
        _utcnow(),
        progress_obj=progress,
        timezone_name=get_effective_timezone_name(getattr(current_user, "timezone", "UTC")),
    )
    if clone_scope is not None:
        payload = _apply_clone_overlay_to_browse_payload(
            payload=payload,
            card_obj=card_obj,
            clone_scope=clone_scope,
            deck_lookup=deck_lookup,
        )
    return jsonify(payload)


@vocabulary_bp.route("/api/browse/cards/<card_id>", methods=["PATCH"])
@login_required
def browse_api_card_update(card_id: str):
    """Update card note fields/deck/tags from Browse editor."""
    from app.services import browse_card_service

    admin_mode = is_admin_user(current_user)
    payload = request.get_json(silent=True) or {}
    try:
        result = browse_card_service.update_browse_card(
            user_id=current_user.id,
            admin_mode=admin_mode,
            timezone_name=get_effective_timezone_name(getattr(current_user, "timezone", "UTC")),
            card_id=card_id,
            payload=payload,
        )
    except browse_card_service.BrowseCardUpdateError as exc:
        response = {"error": str(exc)}
        if exc.include_details:
            response["field"] = exc.field
            response["code"] = exc.code
        return jsonify(response), exc.status
    return jsonify(result)


@vocabulary_bp.route("/api/browse/voicevox/preview", methods=["POST"])
@login_required
def browse_api_voicevox_preview():
    provider = tts_provider_service.find_provider_by_type(
        tts_provider_service.VOICEVOX_PROVIDER_TYPE,
        include_inactive=False,
    )
    if provider is None:
        return jsonify({"error": "Provider không tồn tại hoặc đang bị tắt."}), 404

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Payload phải là JSON object."}), 400

    settings_payload = body.get("settings")
    if settings_payload is not None and not isinstance(settings_payload, dict):
        return jsonify({"error": "settings phải là JSON object."}), 400

    character_id = str(body.get("character_id") or "").strip()
    text = str(body.get("text") or "").strip()
    api_key_override = str(body.get("api_key") or "").strip() or None
    use_opus = _to_bool(body.get("use_opus"))

    synth_result, errors, warnings = tts_provider_service.synthesize_voicevox_audio_for_user(
        db.session,
        user_id=current_user.id,
        provider=provider,
        text=text,
        character_id=character_id,
        settings_payload=settings_payload,
        api_key_override=api_key_override,
        use_opus=use_opus,
    )
    if errors or synth_result is None:
        return jsonify({"error": "; ".join(errors or ["Không tạo được preview audio."])}), 400

    response = send_file(
        io.BytesIO(synth_result.content),
        mimetype=synth_result.mime_type,
        as_attachment=False,
        download_name=f"voicevox-preview.{synth_result.extension}",
        max_age=0,
    )
    if warnings:
        response.headers["X-VoiceVox-Warnings"] = " | ".join(warnings)[:500]
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@vocabulary_bp.route("/api/browse/voicevox/precheck", methods=["POST"])
@login_required
def browse_api_voicevox_precheck():
    from models.flashcard import NoteType

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Payload phải là JSON object."}), 400

    raw_card_ids = body.get("card_ids")
    if not isinstance(raw_card_ids, list):
        return jsonify({"error": "card_ids phải là mảng."}), 400

    destination_field = str(body.get("destination_field") or "").strip()
    if not destination_field:
        return jsonify({"error": "destination_field là bắt buộc."}), 400

    card_ids: list[str] = []
    seen_card_ids: set[str] = set()
    for raw_id in raw_card_ids:
        card_id = str(raw_id or "").strip()
        if not card_id or card_id in seen_card_ids:
            continue
        seen_card_ids.add(card_id)
        card_ids.append(card_id)
    if not card_ids:
        return jsonify({"warning": False, "count": 0, "items": [], "mixed_note_types": False, "note_type_count": 0})

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id.in_(card_ids))
        .options(
            selectinload(Card.note)
            .selectinload(Note.note_type)
            .selectinload(NoteType.field_defs),
        )
    )
    if not is_admin_user(current_user):
        query = query.filter(Note.user_id == current_user.id)

    cards = query.all()
    if not cards:
        return jsonify({"warning": False, "count": 0, "items": [], "mixed_note_types": False, "note_type_count": 0})

    card_order = {card_id: index for index, card_id in enumerate(card_ids)}
    ordered_cards = sorted(cards, key=lambda item: card_order.get(item.id, 1_000_000))

    seen_note_ids: set[str] = set()
    note_type_ids: set[str] = set()
    warning_items: list[dict] = []
    for card_obj in ordered_cards:
        note_obj = card_obj.note
        if note_obj is None or note_obj.id in seen_note_ids:
            continue
        seen_note_ids.add(note_obj.id)
        note_type_ids.add(str(note_obj.note_type_id or "__missing__").strip() or "__missing__")

        field_defs = {
            str(field_def.name or "").strip(): field_def
            for field_def in (note_obj.note_type.field_defs if note_obj.note_type else [])
            if str(field_def.name or "").strip()
        }
        destination_def = field_defs.get(destination_field)
        if destination_def is None:
            continue

        note_values = dict(note_obj.field_values or {})
        existing_value = str(note_values.get(destination_field) or "").strip()
        if not existing_value or _is_audio_like_field_value(existing_value):
            continue

        warning_items.append(
            {
                "note_id": note_obj.id,
                "field_name": destination_field,
                "field_type": str(destination_def.field_type or "text"),
                "sample": existing_value[:120],
            }
        )

    return jsonify(
        {
            "warning": bool(warning_items),
            "count": len(warning_items),
            "items": warning_items[:5],
            "mixed_note_types": len(note_type_ids) > 1,
            "note_type_count": len(note_type_ids),
        }
    )


@vocabulary_bp.route("/api/browse/voicevox/generate", methods=["POST"])
@login_required
def browse_api_voicevox_generate():
    from models.flashcard import MediaAsset, NoteType

    provider = tts_provider_service.find_provider_by_type(
        tts_provider_service.VOICEVOX_PROVIDER_TYPE,
        include_inactive=False,
    )
    if provider is None:
        return jsonify({"error": "Provider không tồn tại hoặc đang bị tắt."}), 404

    body = request.get_json(silent=True) or {}
    if not isinstance(body, dict):
        return jsonify({"error": "Payload phải là JSON object."}), 400

    raw_card_ids = body.get("card_ids")
    if not isinstance(raw_card_ids, list):
        return jsonify({"error": "card_ids phải là mảng."}), 400

    card_ids: list[str] = []
    seen_card_ids: set[str] = set()
    for raw_id in raw_card_ids:
        card_id = str(raw_id or "").strip()
        if not card_id or card_id in seen_card_ids:
            continue
        seen_card_ids.add(card_id)
        card_ids.append(card_id)
    if not card_ids:
        return jsonify({"error": "Không có card nào được chọn để tạo audio."}), 400

    source_field = str(body.get("source_field") or "").strip()
    destination_field = str(body.get("destination_field") or "").strip()
    character_id = str(body.get("character_id") or "").strip()
    if not source_field:
        return jsonify({"error": "source_field là bắt buộc."}), 400
    if not destination_field:
        return jsonify({"error": "destination_field là bắt buộc."}), 400
    if not character_id:
        return jsonify({"error": "character_id là bắt buộc."}), 400

    settings_payload = body.get("settings")
    if settings_payload is not None and not isinstance(settings_payload, dict):
        return jsonify({"error": "settings phải là JSON object."}), 400

    append_audio = _to_bool(body.get("append_audio"))
    use_opus = _to_bool(body.get("use_opus"))
    filename_template = str(body.get("filename_template") or "").strip()
    speaker_label = str(body.get("speaker_label") or character_id).strip()
    style_label = str(body.get("style_label") or "").strip()
    api_key_override = str(body.get("api_key") or "").strip() or None

    query = (
        Card.query.join(Note, Card.note_id == Note.id)
        .filter(Card.id.in_(card_ids))
        .options(
            selectinload(Card.note)
            .selectinload(Note.note_type)
            .selectinload(NoteType.field_defs),
            selectinload(Card.note).selectinload(Note.media_assets),
        )
    )
    if not is_admin_user(current_user):
        query = query.filter(Note.user_id == current_user.id)

    cards = query.all()
    if not cards:
        return jsonify({"error": "Không tìm thấy card hợp lệ để tạo audio."}), 404

    card_order = {card_id: index for index, card_id in enumerate(card_ids)}
    ordered_cards = sorted(cards, key=lambda item: card_order.get(item.id, 1_000_000))

    selected_notes: list[Note] = []
    seen_note_ids: set[str] = set()
    for card_obj in ordered_cards:
        note_obj = card_obj.note
        if note_obj is None or note_obj.id in seen_note_ids:
            continue
        seen_note_ids.add(note_obj.id)
        selected_notes.append(note_obj)

    if not selected_notes:
        return jsonify({"error": "Không có note hợp lệ để tạo audio."}), 400

    selected_note_type_ids: set[str] = {
        str(note_obj.note_type_id or "__missing__").strip() or "__missing__"
        for note_obj in selected_notes
    }
    if len(selected_note_type_ids) > 1:
        return jsonify(
            {
                "error": "Các note được chọn không cùng note_type. Vui lòng chỉ chọn các từ cùng note_type.",
                "code": "mixed_note_types",
            }
        ), 400

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"]).resolve()
    generated_items: list[dict] = []
    skipped_items: list[dict] = []
    warning_items: list[str] = []
    audio_cache: dict[str, tuple[tts_provider_service.SynthesizedAudioResult, list[str]]] = {}
    audio_field_append_warned = False

    for sequence, note_obj in enumerate(selected_notes, start=1):
        field_defs = {
            str(field_def.name or "").strip(): field_def
            for field_def in (note_obj.note_type.field_defs if note_obj.note_type else [])
            if str(field_def.name or "").strip()
        }
        source_def = field_defs.get(source_field)
        destination_def = field_defs.get(destination_field)
        if source_def is None:
            skipped_items.append(
                {
                    "note_id": note_obj.id,
                    "reason": f"Note không có source field '{source_field}'.",
                }
            )
            continue
        if destination_def is None:
            skipped_items.append(
                {
                    "note_id": note_obj.id,
                    "reason": f"Note không có destination field '{destination_field}'.",
                }
            )
            continue

        note_values = dict(note_obj.field_values or {})
        source_text_raw = str(note_values.get(source_field) or "").strip()
        source_type = str(source_def.field_type or "").strip().lower()
        if source_type == "richtext":
            source_text = _strip_richtext_to_plain(source_text_raw)
        elif source_type == "markdown":
            source_text = _strip_markdown_to_plain(source_text_raw)
        else:
            source_text = source_text_raw
        source_text = source_text.strip()
        if not source_text:
            skipped_items.append(
                {
                    "note_id": note_obj.id,
                    "reason": "Source field trống.",
                }
            )
            continue

        cache_key = "|".join(
            [
                source_text,
                character_id,
                "opus" if use_opus else "default",
                str(settings_payload or {}),
            ]
        )
        cached = audio_cache.get(cache_key)
        if cached is None:
            synth_result, errors, warnings = tts_provider_service.synthesize_voicevox_audio_for_user(
                db.session,
                user_id=current_user.id,
                provider=provider,
                text=source_text,
                character_id=character_id,
                settings_payload=settings_payload,
                api_key_override=api_key_override,
                use_opus=use_opus,
            )
            if errors or synth_result is None:
                skipped_items.append(
                    {
                        "note_id": note_obj.id,
                        "reason": "; ".join(errors or ["VoiceVox synthesis thất bại."]),
                    }
                )
                continue
            if warnings:
                warning_items.extend(warnings)
            audio_cache[cache_key] = (synth_result, warnings)
        else:
            synth_result = cached[0]
            if cached[1]:
                warning_items.extend(cached[1])

        sha256 = hashlib.sha256(synth_result.content).hexdigest()
        existing_asset = MediaAsset.query.filter_by(
            note_id=note_obj.id,
            field_name=destination_field,
            sha256=sha256,
        ).first()

        if existing_asset is None:
            filename = _render_voicevox_filename(
                template=filename_template,
                extension=synth_result.extension or "wav",
                speaker_label=speaker_label,
                style_label=style_label,
                note_id=note_obj.id,
                sequence=sequence,
            )
            relative_dir = Path("voicevox") / str(current_user.id) / str(note_obj.id)
            relative_path = relative_dir / filename
            full_path = (upload_root / relative_path).resolve()
            counter = 2
            while full_path.exists():
                stem = Path(filename).stem
                suffix = Path(filename).suffix
                filename = f"{stem}_{counter}{suffix}"
                relative_path = relative_dir / filename
                full_path = (upload_root / relative_path).resolve()
                counter += 1

            full_path.parent.mkdir(parents=True, exist_ok=True)
            full_path.write_bytes(synth_result.content)
            existing_asset = MediaAsset(
                note_id=note_obj.id,
                field_name=destination_field,
                filename=filename,
                mime_type=synth_result.mime_type,
                storage_path=str(relative_path).replace("\\", "/"),
                sha256=sha256,
                size_bytes=len(synth_result.content),
            )
            db.session.add(existing_asset)
            db.session.flush()
        filename = str(existing_asset.filename or "")

        existing_value = str(note_values.get(destination_field) or "").strip()
        destination_type = str(destination_def.field_type or "").strip().lower()
        if append_audio and destination_type != "audio" and existing_value:
            next_value = f"{existing_value}\n{filename}"
        else:
            next_value = filename
            if append_audio and destination_type == "audio" and existing_value and not audio_field_append_warned:
                warning_items.append(
                    "Destination field kiểu audio không hỗ trợ append nhiều dòng, hệ thống đã ghi đè bằng file mới."
                )
                audio_field_append_warned = True
        note_values[destination_field] = next_value
        note_obj.field_values = note_values

        generated_items.append(
            {
                "note_id": note_obj.id,
                "asset_id": existing_asset.id,
                "filename": filename,
                "destination_field": destination_field,
                "value": next_value,
                "url": f"/media/proxy/{existing_asset.id}",
            }
        )

    try:
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        return jsonify({"error": "Không thể lưu kết quả generate audio vào database."}), 500

    unique_warnings = []
    seen_warnings: set[str] = set()
    for warning in warning_items:
        normalized = str(warning or "").strip()
        if not normalized or normalized in seen_warnings:
            continue
        seen_warnings.add(normalized)
        unique_warnings.append(normalized)

    output_root = str((upload_root / "voicevox" / str(current_user.id)).resolve())
    return jsonify(
        {
            "success": True,
            "generated_count": len(generated_items),
            "selected_note_count": len(selected_notes),
            "skipped_count": len(skipped_items),
            "items": generated_items,
            "skipped": skipped_items,
            "warnings": unique_warnings,
            "output_root": output_root,
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
    note_type_obj = note_obj.note_type
    if note_type_obj is None:
        return jsonify({"error": "Note type not found"}), 404

    note_media_ids = _collect_note_media_refs(note_obj)
    try:
        merged_values = validate_legacy_browse_note_update_request(
            note_type=note_type_obj,
            payload=payload,
            current_values=dict(note_obj.field_values or {}),
            note_media_ids=note_media_ids,
        )
    except RequestValidationError as exc:
        return (
            jsonify({"error": str(exc), "field": exc.field, "code": exc.code}),
            exc.status,
        )

    note_obj.field_values = merged_values
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
    parent_id_raw = (request.form.get("parent_id") or "").strip()
    deck_path_raw = (request.form.get("deck_path") or "").strip()
    deck_name = (request.form.get("name") or "").strip() or "New Deck"
    next_url = _resolve_next_url()
    admin_mode = is_admin_user(current_user)
    parent_resolution = vocabulary_ctrl.resolve_create_deck_parent(
        parent_id_raw=parent_id_raw,
        user_id=current_user.id,
        admin_mode=admin_mode,
    )
    if parent_resolution.error:
        flash(parent_resolution.error, "danger")
        return redirect(next_url)

    path_tokens = vocabulary_ctrl.parse_create_deck_tokens(
        deck_path_raw=deck_path_raw,
        fallback_name=deck_name,
    )
    path_tokens = vocabulary_ctrl.normalize_create_deck_tokens_for_parent(
        path_tokens=path_tokens,
        parent_path_tokens=vocabulary_ctrl.deck_name_path_tokens(parent_resolution.parent_deck),
        fallback_name=deck_name,
    )

    try:
        upsert_result = vocabulary_ctrl.upsert_deck_path(
            parent_id=parent_resolution.parent_id,
            path_tokens=path_tokens,
            owner_user_id=getattr(current_user, "id", None),
            admin_mode=admin_mode,
        )
        db.session.commit()
    except SQLAlchemyError:
        db.session.rollback()
        flash("Could not create deck. Please try again.", "danger")
        return redirect(next_url)

    if upsert_result.created_count == 0 and upsert_result.final_deck:
        flash(f"Deck already exists: {'::'.join(upsert_result.path_tokens)}", "info")
    elif upsert_result.created_count == 1 and upsert_result.final_deck:
        flash(f"Created deck: {upsert_result.final_deck.name}", "success")
    else:
        flash(f"Created {upsert_result.created_count} decks: {'::'.join(upsert_result.created_names)}", "success")
    return redirect(next_url)


@vocabulary_bp.route("/decks/<int:deck_id>/rename", methods=["POST"])
@login_required
def rename_deck(deck_id: int):
    """Rename an existing deck."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
        
    deck = Deck.query.get_or_404(deck_id)
    new_name = (request.form.get("name") or "").strip()
    next_url = _resolve_next_url()

    if not new_name:
        flash("Deck name cannot be empty.", "warning")
        return redirect(next_url)
    if new_name == deck.name:
        flash("Deck name is unchanged.", "info")
        return redirect(next_url)
    if vocabulary_ctrl.deck_name_exists_under_parent(parent_id=deck.parent_id, name=new_name, exclude_deck_id=deck.id):
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

    deck = Deck.query.get_or_404(deck_id)
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
        new_parent = Deck.query.get(new_parent_id)
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
    if vocabulary_ctrl.deck_name_exists_under_parent(parent_id=new_parent_id, name=deck.name, exclude_deck_id=deck.id):
        parent_label = new_parent.name if new_parent else "Root"
        flash(f"Parent '{parent_label}' already has a deck named '{deck.name}'.", "danger")
        return redirect(next_url)

    deck.parent_id = new_parent_id
    deck.position = vocabulary_ctrl.next_deck_position(new_parent_id)
    try:
        db.session.commit()
        flash(f"Deck '{deck.name}' moved successfully.", "success")
    except SQLAlchemyError:
        db.session.rollback()
        flash("Failed to move deck. Please try again.", "danger")
    
    return redirect(next_url)


def _can_current_user_delete_cloned_deck(deck_obj: Deck) -> bool:
    return vocabulary_ctrl.can_user_delete_cloned_deck(
        deck_obj=deck_obj,
        user_id=current_user.id,
    )


@vocabulary_bp.route("/decks/<int:deck_id>/delete", methods=["POST"])
@login_required
def delete_deck(deck_id: int):
    """Delete a deck subtree and all Note/Card data inside it."""
    deck = Deck.query.get_or_404(deck_id)
    if not is_admin_user(current_user) and not _can_current_user_delete_cloned_deck(deck):
        flash("You do not have permission to delete this deck.", "danger")
        return redirect(url_for("main.dashboard"))

    deck_name = deck.name
    next_url = _resolve_next_url()

    deck_ids_to_delete = _collect_deck_subtree_ids(deck.id)

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
            CardProgress.query.filter(CardProgress.card_id.in_(card_ids)).delete(
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
    deck = Deck.query.get_or_404(deck_id)
    if (
        not is_admin_user(current_user)
        and deck.owner_user_id != current_user.id
        and not _can_current_user_delete_cloned_deck(deck)
    ):
        return redirect(url_for("main.dashboard"))

    next_url = _resolve_next_url()

    deck_ids = _collect_deck_subtree_ids(deck.id)

    card_id_set = {
        str(row[0])
        for row in (
            db.session.query(Card.id)
            .join(Note, Card.note_id == Note.id)
            .filter(Note.deck_id.in_(deck_ids))
            .all()
        )
        if row and row[0]
    }

    # For logical-overlay installs, reset progress on source cards visible in this local scope.
    from app.services import flashcards_share as share_ctrl

    seen_scopes: set[tuple[str, int]] = set()
    for local_deck_id in sorted({int(deck_id_item) for deck_id_item in deck_ids if deck_id_item is not None}):
        clone_scope = share_ctrl.resolve_clone_scope_for_local_deck(
            user_id=current_user.id,
            local_deck_id=local_deck_id,
        )
        if clone_scope is None:
            continue
        scope_key = (clone_scope.install.id, int(clone_scope.local_scope_deck_id))
        if scope_key in seen_scopes:
            continue
        seen_scopes.add(scope_key)

        clone_card_rows = share_ctrl.query_clone_scope_cards(clone_scope).with_entities(Card.id).all()
        for row in clone_card_rows:
            if row and row[0]:
                card_id_set.add(str(row[0]))

    card_ids = sorted(card_id_set)

    if card_ids:
        deleted_count = (
            CardProgress.query.filter(
                CardProgress.user_id == current_user.id,
                CardProgress.card_id.in_(card_ids),
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


def _select_next_note_card(
    cards: List[Card],
    progress_map: Dict[str, CardProgress],
    now: datetime,
    *,
    timezone_name: str,
):
    return _select_next_due_card_from_loaded(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
        user_id=current_user.id,
    )


def _build_note_study_card_payload(card_obj: Card | None) -> SimpleNamespace | None:
    return vocabulary_ctrl.build_note_study_card_payload(card_obj)


def _render_note_study_flashcard(card_obj: Card | None) -> dict:
    return vocabulary_ctrl.render_note_study_flashcard(card_obj)


def _query_study_cards_for_deck_ids(deck_ids: list[int]) -> list[Card]:
    return vocabulary_ctrl.query_study_cards_for_deck_ids(
        user_id=current_user.id,
        deck_ids=deck_ids,
    )


def _load_card_progress_map(card_ids: list[str]) -> dict[str, CardProgress]:
    return _load_card_progress_map_for_user(user_id=current_user.id, card_ids=card_ids)


def _count_due_note_cards(
    cards: list[Card],
    progress_map: dict[str, CardProgress],
    *,
    now: datetime,
    timezone_name: str,
) -> tuple[int, int, int]:
    return vocabulary_ctrl.count_due_note_cards(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
    )


def _summarize_pending_learning_cards(
    cards: list[Card],
    progress_map: dict[str, CardProgress],
    *,
    now: datetime,
    timezone_name: str,
) -> tuple[int, datetime | None]:
    return _summarize_pending_learning_from_loaded(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
        user_id=current_user.id,
    )


@vocabulary_bp.route("/study/topic/<int:topic_id>")
@login_required
def study_topic(topic_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/study/deck/<int:deck_id>")
@login_required
def study_deck(deck_id: int):
    """Study cards across a deck subtree using Note/Card as the source of truth."""
    root_deck = Deck.query.get(deck_id)
    if not root_deck:
        abort(404)
    subtree_ids = _collect_deck_subtree_ids(root_deck.id)

    cards = _query_study_cards_for_deck_ids(subtree_ids)
    now = _utcnow()
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    card_ids = [card_obj.id for card_obj in cards]
    progress_map = _load_card_progress_map(card_ids)

    selected_card = _select_next_note_card(
        cards,
        progress_map,
        now,
        timezone_name=timezone_name,
    )
    due_new, due_learn, due_review = _count_due_note_cards(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
    )
    pending_learning_count, next_learning_due_at = _summarize_pending_learning_cards(
        cards,
        progress_map,
        now=now,
        timezone_name=timezone_name,
    )

    next_intervals_preview = None
    if selected_card:
        deck_options = resolve_deck_options(
            user_id=current_user.id,
            deck_id=getattr(selected_card.note, "deck_id", None),
        )
        card_state = _card_state_from_progress(
            progress_map.get(selected_card.id),
            now,
            timezone_name=timezone_name,
            user_id=current_user.id,
            options=deck_options,
        )
        next_intervals_preview = computeAnswerPreview(
            card_state,
            deck_options,
            now,
            timezone_name=timezone_name,
        )

    rendered_data = _render_note_study_flashcard(selected_card)
    card_payload = _build_note_study_card_payload(selected_card)
    from app.services import flashcards_share as share_ctrl

    can_edit_current_card = bool(
        selected_card
        and selected_card.note
        and selected_card.note.user_id == current_user.id
    )

    clone_scope = share_ctrl.resolve_clone_scope_for_local_deck(
        user_id=current_user.id,
        local_deck_id=root_deck.id,
    )
    if (
        clone_scope is not None
        and selected_card is not None
        and share_ctrl.is_card_visible_in_clone_scope(scope=clone_scope, card_obj=selected_card)
    ):
        source_note_type_id = (clone_scope.install.source_note_type_id or selected_card.note.note_type_id or "").strip()
        if source_note_type_id:
            schema_view = share_ctrl.build_clone_schema_view(
                install=clone_scope.install,
                source_note_type_id=source_note_type_id,
            )
            overlay_field_defs = schema_view.field_defs or selected_card.note.note_type.field_defs
            overlay_field_values = share_ctrl.apply_clone_note_field_overrides(
                install=clone_scope.install,
                source_note=selected_card.note,
                schema_view=schema_view,
            )
            try:
                rendered = render_template_pair(
                    template=selected_card.template,
                    field_defs=overlay_field_defs,
                    field_values=overlay_field_values,
                    media_assets=selected_card.note.media_assets,
                    allow_inline_script=True,
                    defer_inline_script=True,
                )
                rendered_data = {
                    "front": rendered.get("front_html", ""),
                    "back": rendered.get("back_html", ""),
                }
                if card_payload is not None:
                    card_payload.field_values = {
                        str(key): "" if value is None else str(value)
                        for key, value in overlay_field_values.items()
                    }
                    card_payload.field_defs = [
                        {
                            "name": field_def.name,
                            "field_type": field_def.field_type,
                            "required": bool(field_def.required),
                            "position": int(field_def.position or 0),
                        }
                        for field_def in overlay_field_defs
                    ]
            except TemplateCompileError:
                pass

    return render_template(
        "vocabulary_study.html",
        selected_deck=root_deck,
        card=card_payload,
        rendered_front=rendered_data.get("front"),
        rendered_back=rendered_data.get("back"),
        due_new=due_new,
        due_learn=due_learn,
        due_review=due_review,
        due_total=due_new + due_learn + due_review,
        is_waiting_session=bool(pending_learning_count and next_learning_due_at is not None),
        next_learning_due_at_iso=(
            f"{next_learning_due_at.isoformat(timespec='seconds')}Z"
            if next_learning_due_at is not None
            else None
        ),
        study_scope="deck",
        study_scope_id=root_deck.id,
        next_study_url=url_for("vocabulary.study_deck", deck_id=root_deck.id),
        next_intervals_preview=next_intervals_preview,
        answer_url=(url_for("flashcards.study_answer", card_id=selected_card.id) if selected_card else None),
        can_edit_current_card=can_edit_current_card,
        edit_card_api_url=(
            url_for("flashcards.study_edit_card", card_id=selected_card.id)
            if can_edit_current_card and selected_card
            else None
        ),
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


@vocabulary_bp.route("/entry/<int:legacy_entry_id>/field", methods=["POST"])
@login_required
def update_entry_field(legacy_entry_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entry/<int:legacy_entry_id>/fields", methods=["POST"])
@login_required
def update_entry_fields(legacy_entry_id: int):
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/entries/bulk", methods=["POST"])
@login_required
def bulk_update_entries():
    return _legacy_structure_removed_response()


@vocabulary_bp.route("/import", methods=["GET", "POST"])
@login_required
def import_csv():
    return _legacy_structure_removed_response()
