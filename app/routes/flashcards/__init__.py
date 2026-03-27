"""Flashcard v2 API + minimal management/study pages."""

from __future__ import annotations

import hashlib

import logging

import time

from datetime import datetime, timedelta

from pathlib import Path

from types import SimpleNamespace

from typing import Any

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from flask_login import current_user, login_required

from sqlalchemy.exc import OperationalError

from app.repositories import flashcards_import_repository as flashcard_import_ctrl

from app.services import marketplace_query_service

from app.services import flashcards_share

from app.repositories.deck_tree_query import (
    collect_subtree_ids as _collect_deck_subtree_ids,
)

from app.repositories.study_repository import (
    apply_card_state_to_progress as _apply_card_state_to_progress,
    card_state_from_progress as _card_state_from_progress,
    query_next_due_card_id as _query_next_due_card_id,
)

from app.services.anki_scheduler import (
    applyAnswer,
    computeAnswerPreview,
    default_deck_options,
)

from app.services.flashcard_legacy import (
    LEGACY_BACK_TEMPLATE,
    LEGACY_FRONT_TEMPLATE,
    LEGACY_SHARED_CSS,
    ensure_legacy_note_type,
)

from app.services.flashcard_import import (
    ImportValidationError,
    create_import_session,
    resolve_delimiter,
    run_import,
    suggest_mapping,
)

from app.services.flashcard_renderer import (
    PREVIEW_MEDIA_AUDIO_TOKEN,
    PREVIEW_MEDIA_DIAGRAM_TOKEN,
    PREVIEW_MEDIA_IMAGE_TOKEN,
    TemplateCompileError,
    render_template_pair,
)

from app.services.stats_overview import (
    normalize_review_mode,
    record_review_event,
    update_user_timezone,
)

from app.utils.permissions import is_admin_user
from app.validators import ALLOWED_MEDIA_MIME_TYPES as VALIDATOR_ALLOWED_MEDIA_MIME_TYPES

from models import db

from models.flashcard import (
    AuditLog,
    Card,
    DeckInstall,
    DeckMarketplaceItem,
    DeckReview,
    FieldDef,
    FieldRenameJob,
    MediaAsset,
    Note,
    NoteType,
    NoteTypeInstall,
    NoteTypeReview,
    Template,
)

from models.deck import Deck

from models.card_progress import CardProgress

flashcards_bp = Blueprint("flashcards", __name__)

logger = logging.getLogger(__name__)

FIELD_TYPES = {"text", "richtext", "markdown", "image", "audio", "diagram"}

ALLOWED_MEDIA_MIME_TYPES = set(VALIDATOR_ALLOWED_MEDIA_MIME_TYPES)

CSP_CARD_POLICY = (
    "default-src 'none'; "
    "style-src 'unsafe-inline'; "
    "img-src /media/proxy/; "
    "media-src /media/proxy/; "
    "frame-ancestors 'self'"
)

PUBLISH_STATUSES_VISIBLE = {"published", "unlisted"}

NOTE_TYPE_ACTIVE_NOTE_THRESHOLD = 3

NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD = 3

NOTE_TYPE_ACTIVE_DAYS_THRESHOLD = 3

DECK_ACTIVE_REVIEW_THRESHOLD = 3

TRENDING_WINDOW_DAYS = 7

RECENCY_WINDOW_DAYS = 30

SHARED_DECK_TEST_SAMPLE_LIMIT = 5

SHARED_DECK_INSTALL_MAX_RETRIES = 3

def _api_error(
    error: str,
    message: str,
    *,
    status: int = 400,
    field: str | None = None,
    line: int | None = None,
):
    payload: dict[str, Any] = {"error": error, "message": message}
    if field is not None:
        payload["field"] = field
    if line is not None:
        payload["line"] = line
    return jsonify(payload), status

def _is_mysql_deadlock(exc: OperationalError) -> bool:
    original = getattr(exc, "orig", None)
    args = getattr(original, "args", ()) if original is not None else ()
    if args:
        if str(args[0]) == "1213":
            return True
        if "deadlock found when trying to get lock" in " ".join(str(item) for item in args).lower():
            return True
    return "deadlock found when trying to get lock" in str(exc).lower()

def _audit(action: str, payload: dict[str, Any] | None = None) -> None:
    entry = AuditLog(
        user_id=getattr(current_user, "id", None) if getattr(current_user, "is_authenticated", False) else None,
        action=action,
        payload=payload or {},
    )
    db.session.add(entry)

def _get_note_type_or_404(note_type_id: str) -> NoteType | None:
    return NoteType.query.filter_by(id=note_type_id, user_id=current_user.id).first()

def _serialize_author(user_obj: Any) -> dict[str, Any]:
    return marketplace_query_service.serialize_author(user_obj)

def _serialize_field(field: FieldDef) -> dict[str, Any]:
    return marketplace_query_service.serialize_field(field)

def _serialize_template(template: Template) -> dict[str, Any]:
    return marketplace_query_service.serialize_template(template)

def _serialize_note_type(note_type: NoteType) -> dict[str, Any]:
    return marketplace_query_service.serialize_note_type(note_type)

def _normalize_tags(raw_tags: Any) -> list[str]:
    return marketplace_query_service.normalize_tags(raw_tags)

def _normalize_marketplace_tags(raw_tags: Any) -> list[str]:
    return marketplace_query_service.normalize_marketplace_tags(raw_tags)

def _parse_price_amount_minor(raw_price: Any) -> int | None:
    return marketplace_query_service.parse_price_amount_minor(raw_price)

def _normalize_pricing(payload: dict[str, Any], *, current_mode: str, current_price_amount_minor: int) -> tuple[str, int, str | None]:
    return marketplace_query_service.normalize_pricing(
        payload,
        current_mode=current_mode,
        current_price_amount_minor=current_price_amount_minor,
    )

def _parse_price_cents(raw_price: Any) -> int | None:
    return _parse_price_amount_minor(raw_price)

def _build_preview_sample_values(field_defs: list[FieldDef]) -> dict[str, Any]:
    sample_values: dict[str, Any] = {}
    for field_def in field_defs:
        if field_def.field_type == "image":
            sample_values[field_def.name] = PREVIEW_MEDIA_IMAGE_TOKEN
        elif field_def.field_type == "audio":
            sample_values[field_def.name] = PREVIEW_MEDIA_AUDIO_TOKEN
        elif field_def.field_type == "diagram":
            sample_values[field_def.name] = PREVIEW_MEDIA_DIAGRAM_TOKEN
        else:
            sample_values[field_def.name] = field_def.name
    return sample_values

def _validate_note_type_publish_requirements(note_type: NoteType) -> str | None:
    return flashcards_share.validate_note_type_publish_requirements(note_type)

def _apply_note_type_marketplace_payload(note_type: NoteType, payload: dict[str, Any]) -> str | None:
    return flashcards_share.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin_user(current_user),
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )

def _make_unique_note_type_name(user_id: int, base_name: str) -> str:
    return flashcards_share.make_unique_note_type_name(user_id, base_name)

def _clone_note_type_for_user(source_note_type: NoteType, user_id: int) -> NoteType:
    return flashcards_share.clone_note_type_for_user(source_note_type, user_id)

def _touch_note_type_install_usage(*, user_id: int, installed_note_type_id: str, activity_at: datetime | None = None) -> None:
    flashcards_share.touch_note_type_install_usage(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
        activity_at=activity_at,
    )

def _note_type_reps_for_user(*, user_id: int, installed_note_type_id: str) -> int:
    return flashcards_share.note_type_reps_for_user(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
    )

def _is_note_type_install_active(install: NoteTypeInstall, *, now: datetime) -> bool:
    return flashcards_share.is_note_type_install_active(
        install,
        now=now,
        note_type_active_note_threshold=NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
        note_type_active_review_threshold=NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
        note_type_active_days_threshold=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    )

def _recompute_note_type_market_stats(note_type: NoteType) -> None:
    flashcards_share.recompute_note_type_market_stats(
        note_type,
        note_type_active_note_threshold=NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
        note_type_active_review_threshold=NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
        note_type_active_days_threshold=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    )

def _can_user_rate_note_type(note_type: NoteType, *, user_id: int) -> bool:
    return flashcards_share.can_user_rate_note_type(
        note_type,
        user_id=user_id,
        note_type_active_note_threshold=NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
        note_type_active_review_threshold=NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
        note_type_active_days_threshold=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    )

def _serialize_note_type_marketplace_card(note_type: NoteType) -> dict[str, Any]:
    return marketplace_query_service.serialize_note_type_marketplace_card(note_type)

def _serialize_deck_marketplace_item(deck_item: DeckMarketplaceItem) -> dict[str, Any]:
    return marketplace_query_service.serialize_deck_marketplace_item(deck_item)

def _validate_deck_publish_requirements(deck_item: DeckMarketplaceItem) -> str | None:
    return flashcards_share.validate_deck_publish_requirements(deck_item)

def _apply_deck_marketplace_payload(deck_item: DeckMarketplaceItem, payload: dict[str, Any]) -> str | None:
    return flashcards_share.apply_deck_marketplace_payload(
        deck_item,
        payload,
        allow_set_official=is_admin_user(current_user),
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )

def _resolve_single_note_type_for_deck(
    *,
    deck_id: int,
    owner_user_id: int | None = None,
) -> tuple[str | None, str | None]:
    return flashcards_share.resolve_single_note_type_for_deck(
        deck_id=deck_id,
        owner_user_id=owner_user_id,
    )

def _bind_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> str | None:
    return flashcards_share.bind_deck_item_source_note_type(
        deck_item,
        require_source_note_type=require_source_note_type,
    )

def _validate_note_type_consistency_for_deck(
    *,
    deck_id: int | None,
    note_type_id: str,
    user_id: int,
    exclude_note_id: str | None = None,
) -> str | None:
    return flashcards_share.validate_note_type_consistency_for_deck(
        deck_id=deck_id,
        note_type_id=note_type_id,
        user_id=user_id,
        exclude_note_id=exclude_note_id,
    )

def _collect_accessible_decks_for_import() -> list[Deck]:
    return flashcard_import_ctrl.collect_accessible_decks_for_import(
        user_id=current_user.id,
        admin_mode=is_admin_user(current_user),
    )

def _deck_path_label(deck_obj: Deck, deck_map: dict[int, Deck]) -> str:
    return flashcard_import_ctrl.deck_path_label(deck_obj, deck_map)

def _serialize_note_type_for_import(note_type: NoteType) -> dict[str, Any]:
    return flashcard_import_ctrl.serialize_note_type_for_import(note_type)

def _default_uniqueness_fields(note_type: NoteType) -> list[str]:
    return flashcard_import_ctrl.default_uniqueness_fields(note_type)

def _infer_default_note_type_id_for_deck(deck_id: int | None) -> str | None:
    return flashcard_import_ctrl.infer_default_note_type_id_for_deck(
        deck_id=deck_id,
        user_id=current_user.id,
    )

def _deck_installs_covering_deck(*, user_id: int, deck_id: int) -> list[DeckInstall]:
    return flashcards_share.deck_installs_covering_deck(user_id=user_id, deck_id=deck_id)

def _touch_deck_install_usage(*, user_id: int, local_deck_id: int, activity_at: datetime | None = None) -> None:
    flashcards_share.touch_deck_install_usage(
        user_id=user_id,
        local_deck_id=local_deck_id,
        activity_at=activity_at,
    )

def _resolve_clone_scope_for_local_deck(*, user_id: int, local_deck_id: int) -> flashcards_share.CloneDeckScope | None:
    return flashcards_share.resolve_clone_scope_for_local_deck(
        user_id=user_id,
        local_deck_id=local_deck_id,
    )

def _query_clone_scope_cards(scope: flashcards_share.CloneDeckScope):
    return flashcards_share.query_clone_scope_cards(scope)

def _is_card_visible_in_clone_scope(*, scope: flashcards_share.CloneDeckScope, card_obj: Card | None) -> bool:
    return flashcards_share.is_card_visible_in_clone_scope(scope=scope, card_obj=card_obj)

def _resolve_clone_scope_for_card(*, user_id: int, card_obj: Card | None) -> flashcards_share.CloneDeckScope | None:
    return flashcards_share.resolve_clone_scope_for_card(user_id=user_id, card_obj=card_obj)

def _resolve_local_clone_deck_id_for_source_deck(*, install_id: str, source_deck_id: int | None) -> int | None:
    return flashcards_share.resolve_local_clone_deck_id_for_source_deck(
        install_id=install_id,
        source_deck_id=source_deck_id,
    )

def _build_clone_schema_view(
    *,
    install: DeckInstall,
    source_note_type_id: str,
) -> flashcards_share.CloneSchemaView:
    return flashcards_share.build_clone_schema_view(
        install=install,
        source_note_type_id=source_note_type_id,
    )

def _apply_clone_note_field_overrides(
    *,
    install: DeckInstall,
    source_note: Note,
    schema_view: flashcards_share.CloneSchemaView,
) -> dict[str, Any]:
    return flashcards_share.apply_clone_note_field_overrides(
        install=install,
        source_note=source_note,
        schema_view=schema_view,
    )

def _get_user_deck_install_for_item(*, user_id: int, deck_item_id: str) -> DeckInstall | None:
    return flashcards_share.get_user_deck_install_for_item(
        user_id=user_id,
        deck_item_id=deck_item_id,
    )

def _upsert_clone_overlay(*, deck_install: DeckInstall, payload: dict[str, Any]) -> tuple[dict[str, int], str | None]:
    return flashcards_share.upsert_clone_overlay(deck_install=deck_install, payload=payload)

def _deck_reps_for_user(*, user_id: int, local_deck_id: int) -> int:
    return flashcards_share.deck_reps_for_user(user_id=user_id, local_deck_id=local_deck_id)

def _is_deck_install_active(install: DeckInstall) -> bool:
    return flashcards_share.is_deck_install_active(
        install,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )

def _recompute_deck_item_market_stats(deck_item: DeckMarketplaceItem) -> None:
    flashcards_share.recompute_deck_item_market_stats(
        deck_item,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )

def _can_user_rate_deck(deck_item: DeckMarketplaceItem, *, user_id: int) -> bool:
    return flashcards_share.can_user_rate_deck(
        deck_item,
        user_id=user_id,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )

def _is_note_type_visible_for_shared(note_type: NoteType) -> bool:
    return flashcards_share.is_note_type_visible_for_shared(note_type)

def _is_deck_item_visible_for_shared(deck_item: DeckMarketplaceItem) -> bool:
    return flashcards_share.is_deck_item_visible_for_shared(deck_item)

def _item_matches_search(query_text: str, *values: str | None) -> bool:
    return marketplace_query_service.item_matches_search(query_text, *values)

def _filter_note_type_items(
    note_types: list[NoteType],
    *,
    query_text: str,
    category: str,
    tags: set[str],
    pricing_mode: str,
    min_price_amount_minor: int | None,
    max_price_amount_minor: int | None,
) -> list[NoteType]:
    return marketplace_query_service.filter_note_type_items(
        note_types,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_amount_minor=min_price_amount_minor,
        max_price_amount_minor=max_price_amount_minor,
    )

def _filter_deck_items(
    deck_items: list[DeckMarketplaceItem],
    *,
    query_text: str,
    category: str,
    tags: set[str],
    pricing_mode: str,
    min_price_amount_minor: int | None,
    max_price_amount_minor: int | None,
) -> list[DeckMarketplaceItem]:
    return marketplace_query_service.filter_deck_items(
        deck_items,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_amount_minor=min_price_amount_minor,
        max_price_amount_minor=max_price_amount_minor,
    )

def _sort_note_type_items(items: list[NoteType], sort_key: str) -> list[NoteType]:
    return marketplace_query_service.sort_note_type_items(items, sort_key)

def _sort_deck_items(items: list[DeckMarketplaceItem], sort_key: str) -> list[DeckMarketplaceItem]:
    return marketplace_query_service.sort_deck_items(items, sort_key)

def _collect_user_market_interests(user_id: int) -> tuple[set[str], set[str]]:
    return marketplace_query_service.collect_user_market_interests(user_id)

def _score_market_item(
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
) -> float:
    return marketplace_query_service.score_market_item(
        item_category=item_category,
        item_tags=item_tags,
        rating_avg=rating_avg,
        rating_count=rating_count,
        active_usage_count=active_usage_count,
        install_count=install_count,
        updated_at=updated_at,
        interests_categories=interests_categories,
        interests_tags=interests_tags,
        is_official=is_official,
        cold_start=cold_start,
        recency_window_days=RECENCY_WINDOW_DAYS,
    )

def _top_items_by_category_note_types(items: list[NoteType], *, limit_per_category: int = 5, max_categories: int = 3) -> dict[str, list[dict[str, Any]]]:
    return marketplace_query_service.top_items_by_category_note_types(
        items,
        limit_per_category=limit_per_category,
        max_categories=max_categories,
    )

def _top_items_by_category_decks(items: list[DeckMarketplaceItem], *, limit_per_category: int = 5, max_categories: int = 3) -> dict[str, list[dict[str, Any]]]:
    return marketplace_query_service.top_items_by_category_decks(
        items,
        limit_per_category=limit_per_category,
        max_categories=max_categories,
    )

def _create_cards_for_note(note: Note) -> None:
    templates = (
        Template.query.filter_by(note_type_id=note.note_type_id)
        .order_by(Template.position.asc())
        .all()
    )
    existing_template_ids = {card.template_id for card in note.cards}
    for template in templates:
        if template.id in existing_template_ids:
            continue
        db.session.add(
            Card(
                note_id=note.id,
                template_id=template.id,
            )
        )

def _reorder_fields(note_type_id: str, reorder_payload: list[dict[str, Any]]) -> tuple[bool, str | None]:
    fields = FieldDef.query.filter_by(note_type_id=note_type_id).all()
    field_map = {field.id: field for field in fields}
    if len(reorder_payload) != len(fields):
        return False, "Reorder payload must include all fields."

    seen = set()
    for row in reorder_payload:
        fid = row.get("id")
        position = row.get("position")
        if fid not in field_map:
            return False, f"Unknown field id: {fid}"
        if fid in seen:
            return False, "Duplicate field id in reorder payload."
        seen.add(fid)
        try:
            field_map[fid].position = int(position)
        except (TypeError, ValueError):
            return False, f"Invalid position for field {fid}"
    return True, None

def _run_field_rename_job(note_type: NoteType, field_def: FieldDef, old_name: str, new_name: str) -> FieldRenameJob:
    job = FieldRenameJob(
        note_type_id=note_type.id,
        user_id=current_user.id,
        field_def_id=field_def.id,
        old_name=old_name,
        new_name=new_name,
        status="running",
        total_notes=Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).count(),
        processed_notes=0,
    )
    db.session.add(job)
    db.session.flush()
    try:
        notes = Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).all()
        for note in notes:
            values = dict(note.field_values or {})
            if old_name in values and new_name not in values:
                values[new_name] = values.pop(old_name)
            elif old_name in values:
                values.pop(old_name)
            note.field_values = values
            job.processed_notes += 1
        job.status = "completed"
    except Exception as exc:  # pragma: no cover - defensive
        job.status = "failed"
        job.error_message = str(exc)
        logger.exception("Field rename job failed: %s", job.id)
    return job

@flashcards_bp.after_request
def _set_card_security_headers(response):
    if request.path.endswith("/preview") or request.path.startswith("/api/study"):
        response.headers["Content-Security-Policy"] = CSP_CARD_POLICY
    return response

@flashcards_bp.route("/flashcards")
@login_required
def flashcards_home():
    return redirect(url_for("flashcards.note_type_manager"))

def _parse_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}

def _resolve_import_execution_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], NoteType, int | None]:
    return flashcard_import_ctrl.resolve_import_execution_payload(
        payload=payload,
        user_id=current_user.id,
        admin_mode=is_admin_user(current_user),
    )

def _parse_query_price_amount_minor(param_name: str) -> int | None:
    return marketplace_query_service.parse_query_price_amount_minor(request.args.get(param_name))

def _parse_query_price_cents(param_name: str) -> int | None:
    return _parse_query_price_amount_minor(param_name)

def _get_shared_note_type_for_view(note_type_id: str) -> NoteType | None:
    note_type = NoteType.query.get(note_type_id)
    if not note_type:
        return None

    status = str(note_type.publish_status or "").strip().lower()
    is_owner = note_type.user_id == current_user.id
    if status == "private" and not is_owner:
        return None
    if status == "archived" and not is_owner:
        return None
    return note_type

def _get_shared_deck_item_for_view(deck_item_id: str) -> DeckMarketplaceItem | None:
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if not deck_item:
        return None

    status = str(deck_item.publish_status or "").strip().lower()
    is_owner = deck_item.owner_user_id == current_user.id
    if status == "private" and not is_owner:
        return None
    if status == "archived" and not is_owner:
        return None
    return deck_item


# Sub-modules currently rely on `from . import *`, including private helpers.
__all__ = [name for name in globals() if not name.startswith("__")]

# Register sub-routes
from . import note_type, share, import_export, study, media
