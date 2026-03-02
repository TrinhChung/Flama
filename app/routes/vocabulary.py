"""Vocabulary management routes."""

from __future__ import annotations

from datetime import datetime
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
from sqlalchemy.orm import aliased, selectinload

from app.repositories import vocabulary_repository as vocabulary_ctrl
from app.repositories.deck_tree_query import collect_subtree_ids as _collect_deck_subtree_ids
from app.repositories.study_repository import (
    LEARNING_QUEUE,
    LEARN_QUEUE,
    NEW_QUEUE,
    RELEARNING_QUEUE,
    REVIEW_QUEUE,
    apply_card_state_to_progress as _apply_card_state_to_progress,
    card_state_from_progress as _card_state_from_progress,
    load_card_progress_map as _load_card_progress_map_for_user,
    select_next_due_card_from_loaded as _select_next_due_card_from_loaded,
)
from app.utils.deck_move_token import parse_deck_move_token
from app.utils.permissions import is_admin_user
from app.services.anki_scheduler import (
    computeAnswerPreview,
    default_deck_options,
)
from app.services.flashcard_renderer import TemplateCompileError, render_template_pair
from models import db
from models.flashcard import Card, Note
from models.deck import Deck
from models.card_progress import CardProgress

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
        "vocabulary.create_deck",
        "vocabulary.browse_api_decks_tree",
        "vocabulary.browse_api_cards",
        "vocabulary.browse_api_card_detail",
        "vocabulary.browse_api_card_update",
        "vocabulary.browse_api_card_delete",
        "vocabulary.browse_api_decks",
        "vocabulary.browse_api_notes",
        "vocabulary.browse_api_update_note",
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

    fields_payload = []
    for field_def in ordered_defs:
        field_name = str(getattr(field_def, "name", "") or "").strip()
        if not field_name:
            continue
        try:
            field_position = int(getattr(field_def, "position", 0) or 0)
        except (TypeError, ValueError):
            field_position = 0
        fields_payload.append(
            {
                "name": field_name,
                "field_type": str(getattr(field_def, "field_type", "text") or "text"),
                "required": bool(getattr(field_def, "required", False)),
                "position": field_position,
            }
        )
    existing_names = {field_def["name"] for field_def in fields_payload}
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
        query = query.filter(func.lower(db.cast(Note.field_values, db.Text)).like(f"%{keyword.lower()}%"))
    if tag:
        query = query.filter(func.lower(db.cast(Note.tags, db.Text)).like(f"%{tag.lower()}%"))

    now = datetime.utcnow()
    if status == NEW_QUEUE:
        query = query.filter(db.or_(progress_alias.id.is_(None), progress_alias.queue == NEW_QUEUE))
    elif status == "learn":
        query = query.filter(progress_alias.queue.in_([LEARN_QUEUE, LEARNING_QUEUE, RELEARNING_QUEUE]))
    elif status in {"due", REVIEW_QUEUE}:
        query = query.filter(progress_alias.queue == REVIEW_QUEUE).filter(
            or_(progress_alias.due_at.is_(None), progress_alias.due_at <= now)
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
        due_sort_expr = progress_alias.due_at
        if sort_dir == "desc":
            query = query.order_by(due_sort_expr.is_(None), due_sort_expr.desc(), Card.updated_at.desc())
        else:
            query = query.order_by(due_sort_expr.is_(None), due_sort_expr.asc(), Card.updated_at.desc())

    pagination = query.paginate(page=page, per_page=per_page, error_out=False)
    progress_map = _load_card_progress_map([card_obj.id for card_obj in pagination.items])
    rows = []
    for card_obj in pagination.items:
        row_payload = vocabulary_ctrl.build_browse_row(
            card_obj,
            deck_lookup,
            now,
            progress_obj=progress_map.get(card_obj.id),
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
        datetime.utcnow(),
        progress_obj=progress,
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
    from app.services import flashcards_share as share_ctrl
    from models.flashcard import Card, Note, NoteType

    query = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id)
    card_obj = query.options(
        selectinload(Card.note).selectinload(Note.note_type).selectinload(NoteType.field_defs),
        selectinload(Card.note).selectinload(Note.media_assets),
        selectinload(Card.template),
    ).first()
    if not card_obj:
        return jsonify({"error": "Card not found"}), 404

    note_obj = card_obj.note
    clone_scope = None
    if not is_admin_user(current_user) and note_obj and note_obj.user_id != current_user.id:
        clone_scope = share_ctrl.resolve_clone_scope_for_card(
            user_id=current_user.id,
            card_obj=card_obj,
        )
        if clone_scope is None or not share_ctrl.is_card_visible_in_clone_scope(
            scope=clone_scope,
            card_obj=card_obj,
        ):
            return jsonify({"error": "Card not found"}), 404

    payload = request.get_json(silent=True) or {}
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

    if clone_scope is not None and not is_admin_user(current_user):
        mapped_local_deck_id = (
            (clone_scope.source_to_local_deck_id or {}).get(int(note_obj.deck_id or 0))
            or clone_scope.install.local_deck_id
        )
        if "deck_id" in payload:
            raw_deck_id = payload.get("deck_id")
            if raw_deck_id in (None, ""):
                selected_deck_id = None
            else:
                try:
                    selected_deck_id = int(raw_deck_id)
                except (TypeError, ValueError):
                    return jsonify({"error": "Invalid deck_id"}), 400
            if selected_deck_id != (int(mapped_local_deck_id) if mapped_local_deck_id is not None else None):
                return jsonify({"error": "Moving cloned cards across decks is not supported."}), 400

        if "tags" in payload:
            incoming_tags = _normalize_tags_payload(payload.get("tags"))
            current_tags = _normalize_tags_payload(note_obj.tags or [])
            if incoming_tags != current_tags:
                return jsonify({"error": "Editing tags for cloned cards is not supported."}), 400

        note_override_items = []
        if isinstance(incoming_values, dict):
            for key, value in incoming_values.items():
                key_name = str(key).strip()
                if not key_name:
                    continue
                note_override_items.append(
                    {
                        "source_note_id": note_obj.id,
                        "field_name": key_name,
                        "operation": "set",
                        "value": "" if value is None else str(value),
                    }
                )

        if note_override_items:
            _, validation_error = share_ctrl.upsert_clone_overlay(
                deck_install=clone_scope.install,
                payload={"note_field_overrides": note_override_items},
            )
            if validation_error:
                db.session.rollback()
                return jsonify({"error": validation_error}), 400
        db.session.commit()

        deck_lookup = {
            deck.id: deck.name
            for deck in vocabulary_ctrl.collect_accessible_browse_decks(
                user_id=current_user.id,
                admin_mode=is_admin_user(current_user),
            )
        }
        for source_deck_id, local_deck_id in (clone_scope.source_to_local_deck_id or {}).items():
            local_name = deck_lookup.get(int(local_deck_id))
            if local_name:
                deck_lookup.setdefault(int(source_deck_id), local_name)
        progress = CardProgress.query.filter_by(
            user_id=current_user.id,
            card_id=card_obj.id,
        ).first()
        now = datetime.utcnow()
        detail_payload = vocabulary_ctrl.build_browse_card_detail(card_obj, deck_lookup, now, progress_obj=progress)
        detail_payload = _apply_clone_overlay_to_browse_payload(
            payload=detail_payload,
            card_obj=card_obj,
            clone_scope=clone_scope,
            deck_lookup=deck_lookup,
        )
        return jsonify(
            {
                "success": True,
                "row": detail_payload.get("card"),
                "detail": detail_payload,
            }
        )

    if "deck_id" in payload:
        raw_deck_id = payload.get("deck_id")
        if raw_deck_id in (None, ""):
            note_obj.deck_id = None
        else:
            try:
                selected_deck_id = int(raw_deck_id)
            except (TypeError, ValueError):
                return jsonify({"error": "Invalid deck_id"}), 400
            if not Deck.query.get(selected_deck_id):
                return jsonify({"error": "Deck not found"}), 404
            if not is_admin_user(current_user):
                allowed_deck_ids = {
                    deck.id
                    for deck in vocabulary_ctrl.collect_accessible_browse_decks(
                        user_id=current_user.id,
                        admin_mode=is_admin_user(current_user),
                    )
                }
                if selected_deck_id not in allowed_deck_ids:
                    return jsonify({"error": "Deck is not accessible"}), 403
            note_obj.deck_id = selected_deck_id

    if "tags" in payload:
        note_obj.tags = _normalize_tags_payload(payload.get("tags"))

    note_obj.field_values = field_values
    db.session.commit()

    deck_lookup = {
        deck.id: deck.name
        for deck in vocabulary_ctrl.collect_accessible_browse_decks(
            user_id=current_user.id,
            admin_mode=is_admin_user(current_user),
        )
    }
    progress = CardProgress.query.filter_by(
        user_id=current_user.id,
        card_id=card_obj.id,
    ).first()
    now = datetime.utcnow()
    return jsonify(
        {
            "success": True,
            "row": vocabulary_ctrl.build_browse_row(card_obj, deck_lookup, now, progress_obj=progress),
            "detail": vocabulary_ctrl.build_browse_card_detail(card_obj, deck_lookup, now, progress_obj=progress),
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
    if not is_admin_user(current_user) and not _can_current_user_delete_cloned_deck(deck):
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


def _select_next_note_card(cards: List[Card], progress_map: Dict[str, CardProgress], now: datetime):
    return _select_next_due_card_from_loaded(cards, progress_map, now=now)


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
) -> tuple[int, int, int]:
    return vocabulary_ctrl.count_due_note_cards(cards, progress_map, now=now)


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
    from app.services import flashcards_share as share_ctrl

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
        study_scope="deck",
        study_scope_id=root_deck.id,
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
