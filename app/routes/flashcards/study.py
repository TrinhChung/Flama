"""Sub-module for flashcard routes."""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any
from uuid import uuid4
from flask import jsonify, request, redirect, url_for, flash, send_file, current_app, make_response
from flask_login import current_user, login_required
from app.spa import serve_react_spa
from sqlalchemy import select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import selectinload
from models import db
from models.flashcard import *
from models.deck import Deck
from app.utils.permissions import is_admin_user

# Import everything from core module so routes can use helpers
from . import *

from app.repositories.deck_tree_query import (
    collect_subtree_ids as _collect_deck_subtree_ids,
)
from app.repositories.study_repository import (
    query_pending_learning_summary as _query_pending_learning_summary,
    query_next_due_card_id as _query_next_due_card_id,
    query_study_queue_counts as _query_study_queue_counts,
)
from app.repositories.study_queue_repository import query_study_queue_card_refs

from app.routes.flashcards import (
    _resolve_clone_scope_for_local_deck,
    _query_clone_scope_cards,
    _is_card_visible_in_clone_scope,
    _build_clone_schema_view,
    _apply_clone_note_field_overrides,
    _resolve_clone_scope_for_card,
    _touch_note_type_install_usage,
    _resolve_local_clone_deck_id_for_source_deck,
    _touch_deck_install_usage,
    _audit,
)
from app.validators import (
    RequestValidationError,
    validate_study_composition_selection_request,
    validate_study_answer_request,
    validate_study_next_query,
)
from app.services.stats_overview import get_effective_timezone_name
from app.services.scheduler_config_service import resolve_deck_options
from app.services import study_artifact_service
from app.repositories.study_authority_repository import is_consolidated, lock_study_authority_route
from app.services.study_authority_read_service import (
    load_study_authority_availability_snapshot,
    load_study_authority_card_read,
    load_study_authority_card_reads,
    summarize_study_authority_queue,
)
from app.services import study_session_service
from app.services.db_errors import run_with_deadlock_retry
from app.services.study_action_runtime import (
    compute_review_previews,
    execute_review_action,
)
from app.presenters.vocabulary_presenter import note_field_values_as_strings


def _effective_scheduler_deck_id(
    card: Card,
    clone_scope: flashcards_share.CloneDeckScope | None,
) -> int | None:
    source_deck_id = getattr(card.note, "deck_id", None)
    if clone_scope is None:
        return int(source_deck_id) if source_deck_id is not None else None
    if (
        source_deck_id is not None
        and int(source_deck_id) in set(clone_scope.local_deck_ids)
        and flashcards_share.is_clone_added_note(
            scope=clone_scope,
            note_id=card.note.id,
        )
    ):
        return int(source_deck_id)
    if source_deck_id is not None:
        mapped = clone_scope.source_to_local_deck_id.get(int(source_deck_id))
        if mapped is not None:
            return int(mapped)
    return int(clone_scope.local_scope_deck_id)


def _build_study_scope_query(
    *,
    scope: str,
    scope_id_raw: str,
    allow_empty: bool = False,
):
    clone_scope: flashcards_share.CloneDeckScope | None = None
    query = None
    normalized_scope = str(scope or "").strip().lower()
    normalized_scope_id = str(scope_id_raw or "").strip()

    if normalized_scope == "deck":
        if not normalized_scope_id:
            return None, None, {
                "error": "DECK_NOT_FOUND",
                "message": "Bộ thẻ này không tồn tại hoặc đã bị xóa.",
                "status": 404,
            }
        try:
            scope_id = int(normalized_scope_id)
        except (TypeError, ValueError):
            return None, None, {
                "error": "DECK_NOT_FOUND",
                "message": "Bộ thẻ này không tồn tại hoặc đã bị xóa.",
                "status": 404,
            }

        scope_deck = db.session.get(Deck, scope_id)
        if scope_deck is None or scope_deck.deleted_at is not None:
            return None, None, {
                "error": "DECK_NOT_FOUND",
                "message": "Bộ thẻ này không tồn tại hoặc đã bị xóa.",
                "status": 404,
            }

        clone_scope = _resolve_clone_scope_for_local_deck(
            user_id=current_user.id,
            local_deck_id=scope_id,
        )
        if clone_scope is not None:
            query = _query_clone_scope_cards(clone_scope)
        else:
            is_admin = is_admin_user(current_user)
            is_owner = scope_deck.owner_user_id == current_user.id
            scope_deck_ids = _collect_deck_subtree_ids(scope_id)
            if not scope_deck_ids:
                return None, None, {
                    "error": "DECK_NOT_FOUND",
                    "message": "Bộ thẻ này không tồn tại hoặc đã bị xóa.",
                    "status": 404,
                }

            query = Card.query.join(Note, Card.note_id == Note.id).filter(
                Note.user_id == current_user.id,
                Note.deck_id.in_(scope_deck_ids),
            )
            has_owned_card = bool(query.with_entities(Card.id).first())

            if not is_admin and not is_owner and not has_owned_card:
                # Deck belongs to someone else and user does not have an installed clone.
                # Find if this deck or its ancestor has an active marketplace item.
                marketplace_item = None
                search_deck_ids = [scope_deck.id]
                curr = scope_deck
                while curr and curr.parent_id:
                    curr = db.session.get(Deck, curr.parent_id)
                    if curr:
                        search_deck_ids.append(curr.id)

                for d_id in search_deck_ids:
                    item = DeckMarketplaceItem.query.filter_by(
                        source_deck_id=d_id,
                    ).first()
                    if item:
                        marketplace_item = item
                        break

                marketplace_url = (
                    f"/marketplace/decks/{marketplace_item.id}"
                    if marketplace_item
                    else "/marketplace/decks"
                )
                return None, None, {
                    "error": "DECK_ACCESS_DENIED",
                    "message": "Bạn không thể truy cập bộ thẻ này.",
                    "status": 403,
                    "details": {
                        "deck_id": scope_id,
                        "deck_name": scope_deck.name,
                        "marketplace_url": marketplace_url,
                        "marketplace_item_id": marketplace_item.id if marketplace_item else None,
                    },
                }

    elif normalized_scope == "note_type":
        if not normalized_scope_id:
            return None, None, {
                "error": "NOTE_TYPE_NOT_FOUND",
                "message": "Loại thẻ không tồn tại.",
                "status": 404,
            }
        nt = db.session.get(NoteType, normalized_scope_id)
        if not nt:
            return None, None, {
                "error": "NOTE_TYPE_NOT_FOUND",
                "message": "Loại thẻ không tồn tại.",
                "status": 404,
            }
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == current_user.id,
            Note.note_type_id == normalized_scope_id,
        )

    if query is None:
        return None, None, {
            "error": "NO_STUDY_CARDS",
            "message": "Không tìm thấy thẻ học cho phạm vi đã chọn.",
            "status": 404,
        }
    if not allow_empty and not query.with_entities(Card.id).first():
        return None, None, {
            "error": "NO_STUDY_CARDS",
            "message": "Bộ thẻ này chưa có thẻ học nào.",
            "status": 404,
        }
    return query, clone_scope, None


def _build_study_next_payload(
    *,
    query,
    clone_scope: flashcards_share.CloneDeckScope | None,
    now: datetime,
    timezone_name: str,
    client_render: bool = False,
):
    route = lock_study_authority_route(
        db.session,
        learner_user_id=int(current_user.id),
        allow_note_authority=True,
    )
    authority_reads = None
    selected_cards_by_id = None
    if route.mode_code == "NOTE":
        if is_consolidated(route):
            cards = query_study_queue_card_refs(query)
            # ADR P10 §2.7: count and order the scope set-wise from the rows,
            # without locks or per-Card re-derivation (the offline audit does
            # that); only the returned Card takes the full locking read below.
            card_ids = query.with_entities(Card.id.label("id")).order_by(None).subquery("study_next_ids")
            scope_rows = (
                select(
                    Note.deck_id.label("deck_id"),
                    Card.id.label("card_id"),
                    Card.note_id.label("note_id"),
                )
                .join(Note, Note.id == Card.note_id)
                .where(Card.id.in_(select(card_ids.c.id)))
                .subquery("study_next_scope")
            )
            ordering_reads = load_study_authority_availability_snapshot(
                db.session,
                learner_user_id=int(current_user.id),
                cards=tuple(cards),
                scope=scope_rows,
                now_utc=now,
            )
        else:
            cards = query.options(selectinload(Card.note)).order_by(Card.id.asc()).all()
            selected_cards_by_id = {str(card.id): card for card in cards}
            # Options depend only on (learner, deck): resolve each deck once.
            options_by_deck_id: dict[Any, Any] = {}
            deck_options_by_card_id = {}
            for card in cards:
                deck_id = _effective_scheduler_deck_id(card, clone_scope)
                if deck_id not in options_by_deck_id:
                    options_by_deck_id[deck_id] = resolve_deck_options(
                        user_id=current_user.id,
                        deck_id=deck_id,
                    )
                deck_options_by_card_id[str(card.id)] = options_by_deck_id[deck_id]
            authority_reads = load_study_authority_card_reads(
                db.session,
                learner_user_id=int(current_user.id),
                cards=tuple(cards),
                now_utc=now,
                timezone_name=timezone_name,
                deck_options_by_card_id=deck_options_by_card_id,
            )
            ordering_reads = authority_reads
        queue_summary = summarize_study_authority_queue(
            cards=tuple(cards),
            reads_by_card_id=ordering_reads,
            learner_user_id=int(current_user.id),
            now_utc=now,
            timezone_name=timezone_name,
        )
        new_count = queue_summary.new_count
        learn_count = queue_summary.learn_count
        due_count = queue_summary.due_count
        selected_card_id = queue_summary.selected_card_id
        pending_learning_count = queue_summary.pending_learning_count
        next_due_at = queue_summary.next_due_at
    else:
        new_count, learn_count, due_count = _query_study_queue_counts(
            query,
            user_id=current_user.id,
            now=now,
            timezone_name=timezone_name,
        )
        selected_card_id = _query_next_due_card_id(
            query,
            user_id=current_user.id,
            now=now,
            timezone_name=timezone_name,
        )
        pending_learning_count = 0
        next_due_at = None
    if not selected_card_id:
        if route.mode_code == "LEGACY":
            pending_learning_count, next_due_at = _query_pending_learning_summary(
                query,
                user_id=current_user.id,
                now=now,
                timezone_name=timezone_name,
            )
        if pending_learning_count > 0:
            return {
                "card_id": None,
                "message": "Learning is still in progress.",
                "session_state": "waiting",
                "new_count": new_count,
                "learn_count": learn_count,
                "due_count": due_count,
                "authority_mode": route.mode_code,
                "next_due_at": (
                    f"{next_due_at.isoformat(timespec='seconds')}Z"
                    if next_due_at is not None
                    else None
                ),
            }
        return {
            "card_id": None,
            "message": "No due cards.",
            "session_state": "complete",
            "new_count": new_count,
            "learn_count": learn_count,
            "due_count": due_count,
            "authority_mode": route.mode_code,
        }

    selected_card = (
        selected_cards_by_id.get(selected_card_id)
        if selected_cards_by_id is not None
        else query.filter(Card.id == selected_card_id).first()
    )
    if not selected_card:
        return {"card_id": None, "message": "Card not found."}
    if clone_scope is not None and not _is_card_visible_in_clone_scope(scope=clone_scope, card_obj=selected_card):
        return {
            "card_id": None,
            "message": "No due cards.",
            "session_state": "complete",
            "new_count": new_count,
            "learn_count": learn_count,
            "due_count": due_count,
        }

    note = selected_card.note
    deck_options = resolve_deck_options(
        user_id=current_user.id,
        deck_id=_effective_scheduler_deck_id(selected_card, clone_scope),
    )
    authority_read = (
        authority_reads[selected_card_id]
        if authority_reads is not None
        else load_study_authority_card_read(
            db.session,
            learner_user_id=int(current_user.id),
            card=selected_card,
            now_utc=now,
            timezone_name=timezone_name,
            deck_options=deck_options,
        )
    )
    effective_context = study_artifact_service.build_effective_study_card(
        card=selected_card,
        clone_scope=clone_scope,
    )
    if client_render:
        template_version = study_artifact_service.template_version(effective_context)
        content_version = study_artifact_service.content_version(effective_context)
        public_item = study_artifact_service.public_deck_item(effective_context)
        install_id = effective_context.install_id
        if public_item is not None:
            template_url = url_for(
                "flashcards.study_public_artifact",
                deck_item_id=public_item.id,
                card_id=selected_card.id,
                kind="template",
                version=template_version,
            )
            content_url = url_for(
                "flashcards.study_public_artifact",
                deck_item_id=public_item.id,
                card_id=selected_card.id,
                kind="content",
                version=content_version,
            )
            visibility = "public"
        else:
            template_url = url_for(
                "flashcards.study_private_artifact",
                card_id=selected_card.id,
                kind="template",
                version=template_version,
                install_id=install_id,
            )
            content_url = url_for(
                "flashcards.study_private_artifact",
                card_id=selected_card.id,
                kind="content",
                version=content_version,
                install_id=install_id,
            )
            visibility = "private"
        selection_id = uuid4().hex
        state_version = authority_read.state_version
        return {
            "schema_version": study_artifact_service.MANIFEST_SCHEMA,
            "render_contract": "client_v1",
            "renderer_abi": study_artifact_service.RENDERER_ABI,
            "selection_id": selection_id,
            "session_state": "active",
            "card_id": selected_card.id,
            "note_id": note.id,
            "template_id": selected_card.template.id,
            "template_ref": {
                "id": str(selected_card.template.id),
                "version": template_version,
                "url": template_url,
                "visibility": visibility,
            },
            "content_ref": {
                "id": str(note.id),
                "version": content_version,
                "url": content_url,
                "visibility": visibility,
            },
            "review_state_version": state_version,
            "authority_mode": authority_read.route.mode_code,
            "authority_revision": authority_read.authority_revision,
            "intervals_ref": {
                "state_version": state_version,
                "url": url_for(
                    "flashcards.study_intervals_preview",
                    card_id=selected_card.id,
                    selection_id=selection_id,
                    review_state_version=state_version,
                    install_id=install_id,
                ),
            },
            "new_count": new_count,
            "learn_count": learn_count,
            "due_count": due_count,
            "can_edit_card": bool(note and note.user_id == current_user.id),
            "save_card_url": (
                url_for("flashcards.study_edit_card", card_id=selected_card.id)
                if note and note.user_id == current_user.id
                else None
            ),
            "load_note_url": (
                url_for("flashcards.get_note", note_id=note.id)
                if note and note.user_id == current_user.id
                else None
            ),
            "deck_id": note.deck_id if note else None,
            "tags": note.tags or [] if note else [],
            "note_type_name": note.note_type.name if note and note.note_type else "",
        }

    card_state = authority_read.state
    interval_preview = compute_review_previews(
        state=card_state,
        options=deck_options,
        now=now,
        timezone_name=timezone_name,
    )
    rendered = render_template_pair(
        template=effective_context.template,
        field_defs=effective_context.field_defs,
        field_values=effective_context.field_values,
        media_assets=note.media_assets,
    )
    return {
        "card_id": selected_card.id,
        "note_id": note.id,
        "template_id": effective_context.template.id,
        "rendered_front_html": rendered["front_html"],
        "rendered_back_html": rendered["back_html"],
        "rendered_front_payload": rendered.get("front_renderer_payload"),
        "rendered_back_payload": rendered.get("back_renderer_payload"),
        "intervals_preview": interval_preview,
        "authority_mode": authority_read.route.mode_code,
        "authority_revision": authority_read.authority_revision,
        "new_count": new_count,
        "learn_count": learn_count,
        "due_count": due_count,
        "can_edit_card": bool(note and note.user_id == current_user.id),
        "save_card_url": (
            url_for("flashcards.study_edit_card", card_id=selected_card.id)
            if note and note.user_id == current_user.id
            else None
        ),
        "load_note_url": (
            url_for("flashcards.get_note", note_id=note.id)
            if note and note.user_id == current_user.id
            else None
        ),
        "field_values": note_field_values_as_strings(note),
        "deck_id": note.deck_id if note else None,
        "tags": note.tags or [] if note else [],
        "note_type_name": note.note_type.name if note and note.note_type else "",
        "field_defs": [
            {
                "name": field_def.name,
                "field_type": field_def.field_type,
                "required": bool(field_def.required),
                "position": int(field_def.position or 0),
            }
            for field_def in sorted(note.note_type.field_defs, key=lambda item: item.position)
        ] if note and note.note_type else [],
    }


def _study_next_payload_for_scope(
    *,
    scope: str,
    scope_id_raw: str,
    now: datetime,
    timezone_name: str,
    client_render: bool = False,
):
    query, clone_scope, empty_payload = _build_study_scope_query(
        scope=scope,
        scope_id_raw=scope_id_raw,
    )
    if empty_payload is not None:
        return empty_payload
    try:
        return _build_study_next_payload(
            query=query,
            clone_scope=clone_scope,
            now=now,
            timezone_name=timezone_name,
            client_render=client_render,
        )
    except TemplateCompileError as exc:
        return {"card_id": None, "message": str(exc), "error": "TEMPLATE_COMPILE_ERROR"}
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code is None:
            raise
        db.session.rollback()
        return {
            "card_id": None,
            "message": str(exc),
            "error": str(code),
            "authority_error_status": 409,
        }



@flashcards_bp.route("/flashcards/study")
@login_required
def flashcard_study_page():
    decks = Deck.query.filter(Deck.deleted_at.is_(None)).order_by(Deck.name.asc()).all()
    return serve_react_spa()


def _no_store_json(payload: dict, status: int = 200):
    response = make_response(jsonify(payload), status)
    response.headers["Cache-Control"] = "private, no-store"
    response.headers["Pragma"] = "no-cache"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


def _study_error(
    error: str,
    message: str,
    *,
    status: int = 400,
    field: str | None = None,
    details: dict | None = None,
):
    payload = {"error": error, "message": message}
    if field is not None:
        payload["field"] = field
    if details is not None:
        payload["details"] = details
    return _no_store_json(payload, status)


def _load_private_artifact_context(
    *,
    card_id: str,
    install_id: str | None,
):
    card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id).first()
    if card is None or card.note is None:
        return None
    clone_scope = None
    if card.note.user_id != current_user.id:
        if not install_id:
            return None
        install = db.session.get(DeckInstall, install_id)
        if (
            install is None
            or install.user_id != current_user.id
            or install.local_deck_id is None
        ):
            return None
        clone_scope = flashcards_share.resolve_clone_scope_for_local_deck(
            user_id=current_user.id,
            local_deck_id=int(install.local_deck_id),
        )
        if (
            clone_scope is None
            or clone_scope.install.id != install.id
            or not flashcards_share.is_card_visible_in_clone_scope(
                scope=clone_scope,
                card_obj=card,
            )
        ):
            return None
    return study_artifact_service.build_effective_study_card(
        card=card,
        clone_scope=clone_scope,
    )


def _artifact_response(payload: dict, *, public: bool):
    version = str(payload.get("version") or "")
    if version and request.if_none_match.contains(version):
        response = make_response("", 304)
    else:
        response = make_response(jsonify(payload), 200)
    response.set_etag(version)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = (
        "public, max-age=31536000, s-maxage=31536000, immutable"
        if public
        else "private, no-cache, must-revalidate"
    )
    if not public:
        response.headers["Vary"] = "Cookie"
    return response


def _version_gone_response():
    return _no_store_json(
        {
            "error": "ARTIFACT_VERSION_GONE",
            "message": "Artifact version is no longer current; reload the study manifest.",
            "reload_manifest": True,
        },
        status=410,
    )


@flashcards_bp.route(
    "/api/study/artifacts/public/deck-items/<deck_item_id>/cards/<card_id>/<kind>/versions/<version>",
    methods=["GET"],
)
def study_public_artifact(deck_item_id: str, card_id: str, kind: str, version: str):
    if kind not in {"template", "content"}:
        return _no_store_json({"error": "NOT_FOUND", "message": "Artifact not found."}, 404)
    item = db.session.get(DeckMarketplaceItem, deck_item_id)
    card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id).first()
    if (
        item is None
        or card is None
        or not study_artifact_service.public_item_allows_card(item, card)
    ):
        return _no_store_json({"error": "NOT_FOUND", "message": "Artifact not found."}, 404)
    context = study_artifact_service.build_effective_study_card(
        card=card,
        clone_scope=None,
    )
    expected = (
        study_artifact_service.template_version(context)
        if kind == "template"
        else study_artifact_service.content_version(context)
    )
    if version != expected:
        return _version_gone_response()
    artifact = (
        study_artifact_service.build_template_artifact(context)
        if kind == "template"
        else study_artifact_service.build_content_artifact(context)
    )
    return _artifact_response(artifact, public=True)


@flashcards_bp.route(
    "/api/study/artifacts/private/cards/<card_id>/<kind>/versions/<version>",
    methods=["GET"],
)
@login_required
def study_private_artifact(card_id: str, kind: str, version: str):
    if kind not in {"template", "content"}:
        return _no_store_json({"error": "NOT_FOUND", "message": "Artifact not found."}, 404)
    context = _load_private_artifact_context(
        card_id=card_id,
        install_id=str(request.args.get("install_id") or "").strip() or None,
    )
    if context is None:
        return _no_store_json({"error": "NOT_FOUND", "message": "Artifact not found."}, 404)
    expected = (
        study_artifact_service.template_version(context)
        if kind == "template"
        else study_artifact_service.content_version(context)
    )
    if version != expected:
        return _version_gone_response()
    artifact = (
        study_artifact_service.build_template_artifact(context)
        if kind == "template"
        else study_artifact_service.build_content_artifact(context)
    )
    return _artifact_response(artifact, public=False)


@flashcards_bp.route("/api/study/cards/<card_id>/intervals-preview", methods=["GET"])
@login_required
def study_intervals_preview(card_id: str):
    context = _load_private_artifact_context(
        card_id=card_id,
        install_id=str(request.args.get("install_id") or "").strip() or None,
    )
    if context is None:
        return _no_store_json({"error": "FIELD_NOT_FOUND", "message": "Card not found."}, 404)
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    deck_options = resolve_deck_options(
        user_id=current_user.id,
        deck_id=_effective_scheduler_deck_id(
            context.card,
            context.clone_scope,
        ),
    )
    now = datetime.utcnow()
    try:
        authority_read = load_study_authority_card_read(
            db.session,
            learner_user_id=int(current_user.id),
            card=context.card,
            now_utc=now,
            timezone_name=timezone_name,
            deck_options=deck_options,
        )
    except Exception as exc:
        code = getattr(exc, "code", None)
        if code is None:
            raise
        db.session.rollback()
        return _no_store_json(
            {"error": str(code), "message": str(exc)},
            409,
        )
    state_version = authority_read.state_version
    requested_version = str(request.args.get("review_state_version") or "").strip()
    if requested_version and requested_version != state_version:
        return _no_store_json(
            {
                "error": "STALE_REVIEW_STATE",
                "message": "Review state changed; reload the study manifest.",
            },
            409,
        )
    card_state = authority_read.state
    preview = compute_review_previews(
        state=card_state,
        options=deck_options,
        now=now,
        timezone_name=timezone_name,
    )
    return _no_store_json(
        {
            "schema_version": study_artifact_service.INTERVALS_SCHEMA,
            "selection_id": str(request.args.get("selection_id") or ""),
            "card_id": context.card.id,
            "review_state_version": state_version,
            "authority_mode": authority_read.route.mode_code,
            "authority_revision": authority_read.authority_revision,
            "intervals_preview": preview,
        }
    )


@flashcards_bp.route("/api/study/scopes/<scope_type>/<scope_id>/compositions", methods=["GET"])
@login_required
def study_scope_compositions(scope_type: str, scope_id: str):
    from app.services.study_composition_service import (
        COMPOSITION_SCOPE_SCHEMA_VERSION,
        group_available_compositions,
        list_available_compositions_for_query,
    )
    normalized_scope = scope_type.strip().lower()
    if normalized_scope not in ("deck", "note_type"):
        return _study_error("INVALID_SCOPE", "Scope must be deck or note_type.", status=400)

    query, clone_scope, empty_payload = _build_study_scope_query(
        scope=normalized_scope,
        scope_id_raw=scope_id,
        allow_empty=True,
    )
    if empty_payload is not None or query is None:
        error_code = empty_payload.get("error", "NO_STUDY_CARDS") if empty_payload else "NO_STUDY_CARDS"
        message = empty_payload.get("message", "Không tìm thấy phạm vi học.") if empty_payload else "Không tìm thấy phạm vi học."
        details = empty_payload.get("details") if empty_payload else None
        return _study_error(
            error_code,
            message,
            status=int(empty_payload.get("status", 404)) if empty_payload else 404,
            details=details,
        )
    compositions = list_available_compositions_for_query(
        query,
        clone_scope=clone_scope,
    )
    groups = group_available_compositions(compositions)
    payload = {
        "schema_version": COMPOSITION_SCOPE_SCHEMA_VERSION,
        "scope_type": normalized_scope,
        "scope_id": scope_id,
        "cardinality": (
            "zero" if not compositions else "one" if len(compositions) == 1 else "many"
        ),
        "default_composition_id": (
            compositions[0].composition_id if len(compositions) == 1 else None
        ),
        "groups": [group.to_dict() for group in groups],
        "compositions": [c.to_dict() for c in compositions],
    }
    include_counts = str(request.args.get("include_counts") or "").strip().lower()
    if include_counts in {"1", "true", "yes"}:
        from app.services.study_composition_service import count_notes_by_composition

        payload["note_counts"] = count_notes_by_composition(
            query,
            clone_scope=clone_scope,
            compositions=compositions,
        )
    return jsonify(payload)


@flashcards_bp.route("/api/study/sessions", methods=["POST"])
@login_required
def study_session_open():
    payload = request.get_json(silent=True) or {}
    try:
        validated_query = validate_study_next_query(
            {
                "scope": str(payload.get("scope") or "deck"),
                "scope_id": str(payload.get("scope_id") or ""),
            }
        )
        validated_composition = validate_study_composition_selection_request(payload)
    except RequestValidationError as exc:
        return _study_error(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        )

    query, clone_scope, empty_payload = _build_study_scope_query(
        scope=validated_query.scope,
        scope_id_raw=validated_query.scope_id_raw,
        allow_empty=True,
    )
    if empty_payload is not None or query is None:
        error_code = (
            empty_payload.get("error", "NO_STUDY_CARDS")
            if empty_payload
            else "NO_STUDY_CARDS"
        )
        error_msg = (
            empty_payload.get("message", "Không tìm thấy thẻ học cho phạm vi đã chọn.")
            if empty_payload
            else "Không tìm thấy thẻ học cho phạm vi đã chọn."
        )
        status_code = (
            int(empty_payload.get("status", 404))
            if empty_payload
            else 404
        )
        response_data = {
            "error": error_code,
            "message": error_msg,
        }
        if empty_payload and empty_payload.get("details"):
            response_data["details"] = empty_payload["details"]
        return _no_store_json(response_data, status_code)

    timezone_name = get_effective_timezone_name(
        getattr(current_user, "timezone", "UTC")
    )
    try:
        from app.services.study_composition_service import (
            StudyCompositionError,
            resolve_composition_selection,
        )

        composition_selection = resolve_composition_selection(
            query,
            clone_scope=clone_scope,
            requested_composition_id=validated_composition.composition_id,
            request_source=validated_composition.source,
        )
        wire_schema_version = study_session_service.negotiate_session_wire_schema(
            payload.get("accepted_session_schema_versions"),
            v3_enabled=bool(
                current_app.config.get("STUDY_WIRE_V3_ENABLED", False)
            ),
            v4_enabled=bool(
                current_app.config.get("STUDY_WIRE_V4_ENABLED", False)
            ),
        )
        legacy_wire_schema_version = wire_schema_version
        if wire_schema_version == "study-session.v4":
            try:
                legacy_wire_schema_version = (
                    study_session_service.negotiate_session_wire_schema(
                        payload.get("accepted_session_schema_versions"),
                        v3_enabled=bool(
                            current_app.config.get("STUDY_WIRE_V3_ENABLED", False)
                        ),
                        v4_enabled=False,
                    )
                )
            except study_session_service.StudySessionError as exc:
                if exc.code != "UNSUPPORTED_SESSION_SCHEMA":
                    raise
                legacy_wire_schema_version = None
        result = run_with_deadlock_retry(
            lambda: study_session_service.open_study_session(
                user=current_user,
                query=query,
                clone_scope=clone_scope,
                scope_type=validated_query.scope,
                scope_id=validated_query.scope_id_raw,
                timezone_name=timezone_name,
                composition_selection=composition_selection,
                wire_schema_version=wire_schema_version,
                legacy_wire_schema_version=legacy_wire_schema_version,
                accepted_batch_schema_versions=payload.get("accepted_batch_schema_versions"),
                accepted_note_storage_profiles=payload.get("accepted_note_storage_profiles"),
            ),
            session=db.session,
            label="study session open",
        )
    except StudyCompositionError as exc:
        db.session.rollback()
        return _study_error(
            exc.code,
            str(exc),
            status=exc.status,
            details=exc.details,
        )
    except study_session_service.StudySessionError as exc:
        db.session.rollback()
        error_payload = {"error": exc.code, "message": str(exc)}
        if exc.details is not None:
            error_payload["details"] = exc.details
        return _no_store_json(error_payload, exc.status)
    return _no_store_json(result, 201)


@flashcards_bp.route(
    "/api/study/sessions/<session_id>",
    methods=["GET"],
)
@login_required
def study_session_status(session_id: str):
    try:
        result = study_session_service.get_study_session_status(
            user=current_user,
            session_id=session_id,
        )
    except study_session_service.StudySessionError as exc:
        db.session.rollback()
        error_payload = {"error": exc.code, "message": str(exc)}
        if exc.details is not None:
            error_payload["details"] = exc.details
        return _no_store_json(error_payload, exc.status)
    return _no_store_json(result)


@flashcards_bp.route(
    "/api/study/sessions/<session_id>/batch/<batch_id>",
    methods=["GET"],
)
@login_required
def study_session_batch_status(session_id: str, batch_id: str):
    from app.services.study_note_batch_transport_service import get_study_session_batch_status

    try:
        result = get_study_session_batch_status(user=current_user, session_id=session_id, batch_id=batch_id)
    except study_session_service.StudySessionError as exc:
        return _no_store_json({"error": exc.code, "message": str(exc)}, exc.status)
    return _no_store_json(result)


@flashcards_bp.route(
    "/api/study/sessions/<session_id>/batch",
    methods=["POST"],
)
@login_required
def study_session_batch(session_id: str):
    if not bool(current_app.config.get("STUDY_ASYNC_BATCH_ENABLED", False)):
        return _no_store_json(
            {
                "error": "ASYNC_BATCH_DISABLED",
                "message": (
                    "New asynchronous Study batches are disabled; retain "
                    "pending batch work and retry later."
                ),
            },
            503,
        )
    if (
        request.content_length is not None
        and request.content_length > study_session_service.MAX_COMMIT_BYTES
    ):
        return _no_store_json(
            {
                "error": "COMMIT_TOO_LARGE",
                "message": "Study batch payload exceeds the 5 MiB limit.",
            },
            413,
        )
    payload = request.get_json(silent=True) or {}
    try:
        result = study_session_service.enqueue_study_session_batch(
            user=current_user,
            session_id=session_id,
            payload=payload,
        )
    except study_session_service.StudySessionError as exc:
        db.session.rollback()
        error_payload = {"error": exc.code, "message": str(exc)}
        if exc.details is not None:
            error_payload["details"] = exc.details
        return _no_store_json(error_payload, exc.status)
    return _no_store_json(result, 202)


@flashcards_bp.route(
    "/api/study/sessions/<session_id>/commit",
    methods=["POST"],
)
@login_required
def study_session_commit(session_id: str):
    if (
        request.content_length is not None
        and request.content_length > study_session_service.MAX_COMMIT_BYTES
    ):
        return _no_store_json(
            {
                "error": "COMMIT_TOO_LARGE",
                "message": "Study commit payload exceeds the 5 MiB limit.",
            },
            413,
        )
    payload = request.get_json(silent=True) or {}
    is_async = (
        str(request.args.get("async") or "").strip().lower() in {"1", "true", "yes"}
        or bool(payload.get("async"))
    )
    if is_async and not bool(
        current_app.config.get("STUDY_ASYNC_BATCH_ENABLED", False)
    ):
        return _no_store_json(
            {
                "error": "ASYNC_BATCH_DISABLED",
                "message": (
                    "New asynchronous Study batches are disabled; retain "
                    "pending batch work and retry later."
                ),
            },
            503,
        )
    try:
        if is_async:
            result = study_session_service.enqueue_study_session_batch(
                user=current_user,
                session_id=session_id,
                payload=payload,
            )
            return _no_store_json(result, 202)
        result = run_with_deadlock_retry(
            lambda: study_session_service.commit_study_session(
                user=current_user,
                session_id=session_id,
                payload=payload,
            ),
            session=db.session,
            label="study session commit",
        )
    except study_session_service.StudySessionError as exc:
        db.session.rollback()
        error_payload = {"error": exc.code, "message": str(exc)}
        if exc.details is not None:
            error_payload["details"] = exc.details
        return _no_store_json(error_payload, exc.status)
    return _no_store_json(result)


@flashcards_bp.route("/api/study/session/next", methods=["GET"])
@flashcards_bp.route("/api/study/next", methods=["GET"])
@login_required
def study_next():
    try:
        validated_query = validate_study_next_query(request.args)
    except RequestValidationError as exc:
        return _study_error(exc.code, str(exc), status=exc.status, field=exc.field)

    scope = validated_query.scope
    scope_id_raw = validated_query.scope_id_raw
    now = datetime.utcnow()
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    client_render = (
        request.path == "/api/study/session/next"
        or str(request.args.get("render_contract") or "") == "client_v1"
    )
    payload = _study_next_payload_for_scope(
        scope=scope,
        scope_id_raw=scope_id_raw,
        now=now,
        timezone_name=timezone_name,
        client_render=client_render,
    )
    if client_render:
        payload.setdefault("schema_version", study_artifact_service.MANIFEST_SCHEMA)
        payload.setdefault("render_contract", "client_v1")
        payload.setdefault("renderer_abi", study_artifact_service.RENDERER_ABI)
    if payload.get("error") == "TEMPLATE_COMPILE_ERROR":
        return _study_error(
            "TEMPLATE_COMPILE_ERROR",
            payload.get("message") or "Template compile error.",
        )
    if payload.get("authority_error_status"):
        return _study_error(
            str(payload.get("error") or "AUTHORITY_READ_FAILED"),
            str(payload.get("message") or "Authority state could not be read."),
            status=int(payload["authority_error_status"]),
        )
    return _no_store_json(payload)

@flashcards_bp.route("/api/study/cards/<card_id>/answer", methods=["POST"])
@flashcards_bp.route("/api/study/<card_id>/answer", methods=["POST"])
@login_required
def study_answer(card_id: str):
    payload = request.get_json(silent=True) or {}
    client_render = (
        request.path == f"/api/study/cards/{card_id}/answer"
        or str(payload.get("render_contract") or "") == "client_v1"
    )
    try:
        validated_answer = validate_study_answer_request(payload)
    except RequestValidationError as exc:
        return _study_error(exc.code, str(exc), status=exc.status, field=exc.field)

    rating = validated_answer.rating
    scope = validated_answer.scope
    requested_scope_id = validated_answer.requested_scope_id
    requested_scope_id_raw = str(payload.get("scope_id") or "").strip()
    service_payload = dict(payload)
    service_payload["timezone"] = validated_answer.timezone
    service_payload["duration_ms"] = validated_answer.duration_ms

    card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id).first()
    if not card:
        return _study_error("FIELD_NOT_FOUND", "Card not found.", status=404)
    clone_scope: flashcards_share.CloneDeckScope | None = None
    if card.note.user_id != current_user.id:
        clone_scope = _resolve_clone_scope_for_card(user_id=current_user.id, card_obj=card)
        if clone_scope is None:
            return _study_error("FIELD_NOT_FOUND", "Card not found.", status=404)
        if not _is_card_visible_in_clone_scope(scope=clone_scope, card_obj=card):
            return _study_error("FIELD_NOT_FOUND", "Card not found.", status=404)

    now = datetime.utcnow()
    timezone_name = get_effective_timezone_name(getattr(current_user, "timezone", "UTC"))
    from app.services.study_service import (
        StudyReviewError,
        execute_native_review_command,
    )

    try:
        command_result = run_with_deadlock_retry(
            lambda: execute_native_review_command(
                user=current_user,
                card=card,
                action=rating,
                payload=service_payload,
                clone_scope=clone_scope,
                requested_scope_id=requested_scope_id,
                timezone_name=timezone_name,
                require_review_state_version=bool(client_render),
                review_state_version=str(payload.get("review_state_version") or "").strip() or None,
                now=now,
            ),
            session=db.session,
            label="study answer",
        )
        local_deck_id_for_usage = command_result.local_deck_id
    except StudyReviewError as exc:
        return _study_error(exc.code, str(exc), status=exc.status)

    next_scope_id = requested_scope_id if requested_scope_id is not None else local_deck_id_for_usage
    next_card_url = None
    if scope == "note_type" and requested_scope_id_raw:
        next_card_url = url_for("flashcards.study_next", scope="note_type", scope_id=requested_scope_id_raw)
    elif next_scope_id:
        next_card_url = url_for("flashcards.study_next", scope="deck", scope_id=next_scope_id)

    next_url = None
    if scope == "deck":
        if requested_scope_id is not None:
            next_url = url_for("vocabulary.study_deck", deck_id=requested_scope_id)
    next_card_payload = None
    prefetch_scope = str(scope or "").strip().lower()
    prefetch_scope_id_raw = requested_scope_id_raw
    if prefetch_scope == "deck":
        if next_scope_id is not None:
            prefetch_scope_id_raw = str(next_scope_id)
    elif prefetch_scope != "note_type":
        if next_scope_id is not None:
            prefetch_scope = "deck"
            prefetch_scope_id_raw = str(next_scope_id)
    if prefetch_scope in {"deck", "note_type"} and prefetch_scope_id_raw:
        prefetch_now = datetime.utcnow()
        next_card_payload = _study_next_payload_for_scope(
            scope=prefetch_scope,
            scope_id_raw=prefetch_scope_id_raw,
            now=prefetch_now,
            timezone_name=timezone_name,
            client_render=client_render,
        )
    response_payload = {
        "success": True,
        "next_url": next_url,
        "next_card_url": next_card_url,
        "applied_interval": command_result.intervals_preview.get(rating),
    }
    if command_result.authority_mode == "NOTE":
        response_payload["authority"] = {
            "mode": "NOTE",
            "operation_key": command_result.operation_key,
            "authority_revision": command_result.authority_revision,
            "progress_revision": command_result.progress_revision,
            "replayed": command_result.replayed,
        }
    if client_render:
        response_payload["next_manifest"] = next_card_payload
    else:
        response_payload["next_card_payload"] = next_card_payload
        response_payload["intervals_preview"] = command_result.intervals_preview
    return _no_store_json(response_payload)


@flashcards_bp.route("/api/study/cards/<card_id>/edit", methods=["PATCH"])
@login_required
def study_edit_card(card_id: str):
    payload = request.get_json(silent=True) or {}
    client_render = str(payload.get("render_contract") or "") == "client_v1"
    from app.services.study_card_editor_service import StudyCardEditError, update_study_card_note

    try:
        result = update_study_card_note(
            user_id=current_user.id,
            card_id=card_id,
            payload=payload,
            render_result=not client_render,
        )
    except StudyCardEditError as exc:
        return _study_error(
            exc.code,
            str(exc),
            status=exc.status,
            field=exc.field,
        )
    if client_render:
        context = _load_private_artifact_context(card_id=card_id, install_id=None)
        if context is not None:
            version = study_artifact_service.content_version(context)
            public_item = study_artifact_service.public_deck_item(context)
            if public_item is not None:
                artifact_url = url_for(
                    "flashcards.study_public_artifact",
                    deck_item_id=public_item.id,
                    card_id=card_id,
                    kind="content",
                    version=version,
                )
                visibility = "public"
            else:
                artifact_url = url_for(
                    "flashcards.study_private_artifact",
                    card_id=card_id,
                    kind="content",
                    version=version,
                )
                visibility = "private"
            result["content_ref"] = {
                "id": str(context.note.id),
                "version": version,
                "url": artifact_url,
                "visibility": visibility,
            }
    return _no_store_json(result)
