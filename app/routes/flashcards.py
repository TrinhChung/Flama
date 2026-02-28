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

from app.controllers import flashcards_import_controller as flashcard_import_ctrl
from app.controllers import flashcards_marketplace_controller as marketplace_ctrl
from app.controllers import flashcards_note_controller as flashcard_note_ctrl
from app.controllers import flashcards_share_controller as share_ctrl
from app.controllers.deck_controller import (
    collect_subtree_ids as _collect_deck_subtree_ids,
)
from app.controllers.study_controller import (
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
    is_field_empty,
    render_template_pair,
)
from app.services.stats_overview import (
    normalize_review_mode,
    record_review_event,
    update_user_timezone,
)
from app.utils.permissions import is_admin_user
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

FIELD_TYPES = {"text", "richtext", "image", "audio", "diagram"}
MEDIA_ALLOWED_PREFIX = "/media/proxy/"
ALLOWED_MEDIA_MIME_TYPES = {
    "image/jpeg",
    "image/png",
    "image/gif",
    "image/webp",
    "image/svg+xml",
    "audio/mpeg",
    "audio/ogg",
    "audio/wav",
    "audio/webm",
}
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
    return marketplace_ctrl.serialize_author(user_obj)


def _serialize_field(field: FieldDef) -> dict[str, Any]:
    return marketplace_ctrl.serialize_field(field)


def _serialize_template(template: Template) -> dict[str, Any]:
    return marketplace_ctrl.serialize_template(template)


def _serialize_note_type(note_type: NoteType) -> dict[str, Any]:
    return marketplace_ctrl.serialize_note_type(note_type)


def _clean_field_value(field_def: FieldDef, raw_value: Any) -> Any:
    return flashcard_note_ctrl.clean_field_value(
        field_def,
        raw_value,
        media_allowed_prefix=MEDIA_ALLOWED_PREFIX,
    )


def _validate_note_payload(note_type: NoteType, payload: dict[str, Any], *, partial: bool) -> tuple[dict[str, Any], str | None]:
    return flashcard_note_ctrl.validate_note_payload(
        note_type,
        payload,
        partial=partial,
        media_allowed_prefix=MEDIA_ALLOWED_PREFIX,
    )


def _normalize_tags(raw_tags: Any) -> list[str]:
    return marketplace_ctrl.normalize_tags(raw_tags)


def _normalize_marketplace_tags(raw_tags: Any) -> list[str]:
    return marketplace_ctrl.normalize_marketplace_tags(raw_tags)


def _parse_price_cents(raw_price: Any) -> int | None:
    return marketplace_ctrl.parse_price_cents(raw_price)


def _normalize_pricing(payload: dict[str, Any], *, current_mode: str, current_price_cents: int) -> tuple[str, int, str | None]:
    return marketplace_ctrl.normalize_pricing(
        payload,
        current_mode=current_mode,
        current_price_cents=current_price_cents,
    )


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
    return share_ctrl.validate_note_type_publish_requirements(note_type)


def _apply_note_type_marketplace_payload(note_type: NoteType, payload: dict[str, Any]) -> str | None:
    return share_ctrl.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin_user(current_user),
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )


def _make_unique_note_type_name(user_id: int, base_name: str) -> str:
    return share_ctrl.make_unique_note_type_name(user_id, base_name)


def _clone_note_type_for_user(source_note_type: NoteType, user_id: int) -> NoteType:
    return share_ctrl.clone_note_type_for_user(source_note_type, user_id)


def _touch_note_type_install_usage(*, user_id: int, installed_note_type_id: str, activity_at: datetime | None = None) -> None:
    share_ctrl.touch_note_type_install_usage(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
        activity_at=activity_at,
    )


def _note_type_reps_for_user(*, user_id: int, installed_note_type_id: str) -> int:
    return share_ctrl.note_type_reps_for_user(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
    )


def _is_note_type_install_active(install: NoteTypeInstall, *, now: datetime) -> bool:
    return share_ctrl.is_note_type_install_active(
        install,
        now=now,
        note_type_active_note_threshold=NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
        note_type_active_review_threshold=NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
        note_type_active_days_threshold=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    )


def _recompute_note_type_market_stats(note_type: NoteType) -> None:
    share_ctrl.recompute_note_type_market_stats(
        note_type,
        note_type_active_note_threshold=NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
        note_type_active_review_threshold=NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
        note_type_active_days_threshold=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    )


def _can_user_rate_note_type(note_type: NoteType, *, user_id: int) -> bool:
    return share_ctrl.can_user_rate_note_type(
        note_type,
        user_id=user_id,
        note_type_active_note_threshold=NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
        note_type_active_review_threshold=NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
        note_type_active_days_threshold=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    )


def _serialize_note_type_marketplace_card(note_type: NoteType) -> dict[str, Any]:
    return marketplace_ctrl.serialize_note_type_marketplace_card(note_type)


def _serialize_deck_marketplace_item(deck_item: DeckMarketplaceItem) -> dict[str, Any]:
    return marketplace_ctrl.serialize_deck_marketplace_item(deck_item)


def _validate_deck_publish_requirements(deck_item: DeckMarketplaceItem) -> str | None:
    return share_ctrl.validate_deck_publish_requirements(deck_item)


def _apply_deck_marketplace_payload(deck_item: DeckMarketplaceItem, payload: dict[str, Any]) -> str | None:
    return share_ctrl.apply_deck_marketplace_payload(
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
    return share_ctrl.resolve_single_note_type_for_deck(
        deck_id=deck_id,
        owner_user_id=owner_user_id,
    )


def _bind_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> str | None:
    return share_ctrl.bind_deck_item_source_note_type(
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
    return share_ctrl.validate_note_type_consistency_for_deck(
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
    return share_ctrl.deck_installs_covering_deck(user_id=user_id, deck_id=deck_id)


def _touch_deck_install_usage(*, user_id: int, local_deck_id: int, activity_at: datetime | None = None) -> None:
    share_ctrl.touch_deck_install_usage(
        user_id=user_id,
        local_deck_id=local_deck_id,
        activity_at=activity_at,
    )


def _resolve_clone_scope_for_local_deck(*, user_id: int, local_deck_id: int) -> share_ctrl.CloneDeckScope | None:
    return share_ctrl.resolve_clone_scope_for_local_deck(
        user_id=user_id,
        local_deck_id=local_deck_id,
    )


def _query_clone_scope_cards(scope: share_ctrl.CloneDeckScope):
    return share_ctrl.query_clone_scope_cards(scope)


def _is_card_visible_in_clone_scope(*, scope: share_ctrl.CloneDeckScope, card_obj: Card | None) -> bool:
    return share_ctrl.is_card_visible_in_clone_scope(scope=scope, card_obj=card_obj)


def _resolve_clone_scope_for_card(*, user_id: int, card_obj: Card | None) -> share_ctrl.CloneDeckScope | None:
    return share_ctrl.resolve_clone_scope_for_card(user_id=user_id, card_obj=card_obj)


def _resolve_local_clone_deck_id_for_source_deck(*, install_id: str, source_deck_id: int | None) -> int | None:
    return share_ctrl.resolve_local_clone_deck_id_for_source_deck(
        install_id=install_id,
        source_deck_id=source_deck_id,
    )


def _build_clone_schema_view(
    *,
    install: DeckInstall,
    source_note_type_id: str,
) -> share_ctrl.CloneSchemaView:
    return share_ctrl.build_clone_schema_view(
        install=install,
        source_note_type_id=source_note_type_id,
    )


def _apply_clone_note_field_overrides(
    *,
    install: DeckInstall,
    source_note: Note,
    schema_view: share_ctrl.CloneSchemaView,
) -> dict[str, Any]:
    return share_ctrl.apply_clone_note_field_overrides(
        install=install,
        source_note=source_note,
        schema_view=schema_view,
    )


def _get_user_deck_install_for_item(*, user_id: int, deck_item_id: str) -> DeckInstall | None:
    return share_ctrl.get_user_deck_install_for_item(
        user_id=user_id,
        deck_item_id=deck_item_id,
    )


def _upsert_clone_overlay(*, deck_install: DeckInstall, payload: dict[str, Any]) -> tuple[dict[str, int], str | None]:
    return share_ctrl.upsert_clone_overlay(deck_install=deck_install, payload=payload)


def _deck_reps_for_user(*, user_id: int, local_deck_id: int) -> int:
    return share_ctrl.deck_reps_for_user(user_id=user_id, local_deck_id=local_deck_id)


def _is_deck_install_active(install: DeckInstall) -> bool:
    return share_ctrl.is_deck_install_active(
        install,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )


def _recompute_deck_item_market_stats(deck_item: DeckMarketplaceItem) -> None:
    share_ctrl.recompute_deck_item_market_stats(
        deck_item,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )


def _can_user_rate_deck(deck_item: DeckMarketplaceItem, *, user_id: int) -> bool:
    return share_ctrl.can_user_rate_deck(
        deck_item,
        user_id=user_id,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )


def _is_note_type_visible_for_shared(note_type: NoteType) -> bool:
    return share_ctrl.is_note_type_visible_for_shared(note_type)


def _is_deck_item_visible_for_shared(deck_item: DeckMarketplaceItem) -> bool:
    return share_ctrl.is_deck_item_visible_for_shared(deck_item)


def _item_matches_search(query_text: str, *values: str | None) -> bool:
    return marketplace_ctrl.item_matches_search(query_text, *values)


def _filter_note_type_items(
    note_types: list[NoteType],
    *,
    query_text: str,
    category: str,
    tags: set[str],
    pricing_mode: str,
    min_price_cents: int | None,
    max_price_cents: int | None,
) -> list[NoteType]:
    return marketplace_ctrl.filter_note_type_items(
        note_types,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )


def _filter_deck_items(
    deck_items: list[DeckMarketplaceItem],
    *,
    query_text: str,
    category: str,
    tags: set[str],
    pricing_mode: str,
    min_price_cents: int | None,
    max_price_cents: int | None,
) -> list[DeckMarketplaceItem]:
    return marketplace_ctrl.filter_deck_items(
        deck_items,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )


def _sort_note_type_items(items: list[NoteType], sort_key: str) -> list[NoteType]:
    return marketplace_ctrl.sort_note_type_items(items, sort_key)


def _sort_deck_items(items: list[DeckMarketplaceItem], sort_key: str) -> list[DeckMarketplaceItem]:
    return marketplace_ctrl.sort_deck_items(items, sort_key)


def _collect_user_market_interests(user_id: int) -> tuple[set[str], set[str]]:
    return marketplace_ctrl.collect_user_market_interests(user_id)


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
    return marketplace_ctrl.score_market_item(
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
    return marketplace_ctrl.top_items_by_category_note_types(
        items,
        limit_per_category=limit_per_category,
        max_categories=max_categories,
    )


def _top_items_by_category_decks(items: list[DeckMarketplaceItem], *, limit_per_category: int = 5, max_categories: int = 3) -> dict[str, list[dict[str, Any]]]:
    return marketplace_ctrl.top_items_by_category_decks(
        items,
        limit_per_category=limit_per_category,
        max_categories=max_categories,
    )


def _create_cards_for_note(note: Note) -> None:
    flashcard_note_ctrl.create_cards_for_note(note)


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


@flashcards_bp.route("/flashcards/note-types")
@login_required
def note_type_manager():
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.updated_at.desc(), NoteType.created_at.desc())
        .all()
    )
    return render_template("flashcards/note_types.html", note_types=note_types)


@flashcards_bp.route("/flashcards/note-types/<note_type_id>")
@login_required
def note_type_detail_page(note_type_id: str):
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return redirect(url_for("flashcards.note_type_manager"))
    notes = Note.query.filter_by(note_type_id=note_type_id, user_id=current_user.id).order_by(Note.created_at.desc()).limit(30).all()
    return render_template("flashcards/note_type_detail.html", note_type=note_type, notes=notes)


@flashcards_bp.route("/flashcards/note-types/<note_type_id>/fields")
@login_required
def note_type_fields_page(note_type_id: str):
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return redirect(url_for("flashcards.note_type_manager"))
    return render_template("flashcards/note_type_fields.html", note_type=note_type)


@flashcards_bp.route("/flashcards/shared-note-types")
@login_required
def shared_note_types_page():
    return render_template("flashcards/shared_note_types.html")


@flashcards_bp.route("/flashcards/shared-note-types/<note_type_id>")
@login_required
def shared_note_type_detail_page(note_type_id: str):
    return render_template("flashcards/shared_note_type_detail.html", note_type_id=note_type_id)


@flashcards_bp.route("/flashcards/shared-decks")
@login_required
def shared_decks_page():
    return render_template("flashcards/shared_decks.html")


@flashcards_bp.route("/flashcards/shared-decks/<deck_item_id>")
@login_required
def shared_deck_detail_page(deck_item_id: str):
    return render_template("flashcards/shared_deck_detail.html", deck_item_id=deck_item_id)


@flashcards_bp.route("/flashcards/decks/<int:deck_id>/share", methods=["GET", "POST"])
@login_required
def share_deck_page(deck_id: int):
    deck = Deck.query.get_or_404(deck_id)
    
    # Validation 1: Ownership
    if not is_admin_user(current_user) and deck.owner_user_id != current_user.id:
        flash("Bạn không có quyền chia sẻ deck này.", "danger")
        return redirect(url_for("main.dashboard"))

    # Validation 2: Is downloaded deck (cannot re-share a downloaded deck)
    if deck.owner_user_id == current_user.id:
        from models.flashcard import DeckInstall
        # If user has an install record for this exact local deck, block re-sharing
        if DeckInstall.query.filter_by(user_id=current_user.id, local_deck_id=deck.id).first():
            flash("Bạn không thể chia sẻ lại deck đã được cài đặt từ Marketplace.", "danger")
            return redirect(url_for("main.dashboard"))
        
    # Validation 3: Child deck of a shared deck cannot be shared
    from models.flashcard import DeckMarketplaceItem
    current_parent = deck.parent_id
    while current_parent is not None:
        parent_deck = Deck.query.get(current_parent)
        if not parent_deck:
            break
        if DeckMarketplaceItem.query.filter_by(source_deck_id=parent_deck.id).first():
            flash(f"Deck cha '{parent_deck.name}' đã được chia sẻ. Không thể chia sẻ riêng lẻ deck con.", "warning")
            return redirect(url_for("main.dashboard"))
        current_parent = parent_deck.parent_id

    # Existing marketplace item
    existing_item = DeckMarketplaceItem.query.filter_by(source_deck_id=deck.id).first()

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        preview_text = request.form.get("preview_text", "").strip()
        primary_category = request.form.get("primary_category", "Japanese").strip()
        tags_raw = request.form.get("tags", "")
        tags = [t.strip() for t in tags_raw.split(",") if t.strip()]
        pricing_mode = request.form.get("pricing_mode", "free")
        # Ensure only published free, logic can be updated for payment later
        price_cents = int(request.form.get("price_cents", 0)) if pricing_mode == "paid" else 0
        
        if not title:
            flash("Tên hiển thị không được để trống.", "danger")
            return render_template("flashcards/shared_deck_publish.html", deck=deck, existing_item=existing_item)

        resolved_note_type_id, resolve_error = _resolve_single_note_type_for_deck(
            deck_id=deck.id,
            owner_user_id=current_user.id,
        )
        if resolve_error:
            flash(resolve_error, "danger")
            return render_template("flashcards/shared_deck_publish.html", deck=deck, existing_item=existing_item)            
        if not existing_item:
            existing_item = DeckMarketplaceItem(
                source_deck_id=deck.id,
                owner_user_id=current_user.id,
                is_official=is_admin_user(current_user),
                install_count=0,
                rating_avg=0.0,
                rating_count=0,
            )
            db.session.add(existing_item)
            
        existing_item.title = title
        existing_item.description = description
        existing_item.preview_text = preview_text
        existing_item.primary_category = primary_category
        existing_item.tags = tags
        existing_item.pricing_mode = pricing_mode
        existing_item.price_cents = price_cents
        existing_item.source_note_type_id = resolved_note_type_id
        existing_item.publish_status = "published"
        
        db.session.commit()
        flash("Tuyệt vời! Deck của bạn đã được chia sẻ lên Marketplace.", "success")
        return redirect(url_for("flashcards.shared_decks_page"))

    return render_template("flashcards/shared_deck_publish.html", deck=deck, existing_item=existing_item)


@flashcards_bp.route("/flashcards/notes/new")
@login_required
def note_editor_page():
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập trang này.", "danger")
        return redirect(url_for("main.dashboard"))
    note_types = NoteType.query.filter_by(user_id=current_user.id).order_by(NoteType.name.asc()).all()
    decks = Deck.query.order_by(Deck.name.asc()).all()
    return render_template("flashcards/note_editor.html", note_types=note_types, decks=decks)


def _parse_bool(value: Any, *, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


@flashcards_bp.route("/flashcards/import")
@login_required
def flashcard_import_page():
    decks = _collect_accessible_decks_for_import()
    deck_map = {deck.id: deck for deck in decks}
    deck_options = [
        {
            "id": deck.id,
            "name": deck.name,
            "path": _deck_path_label(deck, deck_map),
            "note_type_id": deck.note_type_id,
        }
        for deck in decks
    ]

    selected_deck_id: int | None = None
    selected_deck_raw = (request.args.get("deck_id") or "").strip()
    if selected_deck_raw:
        try:
            candidate = int(selected_deck_raw)
            if candidate in deck_map:
                selected_deck_id = candidate
        except (TypeError, ValueError):
            selected_deck_id = None
    if selected_deck_id is None and deck_options:
        selected_deck_id = int(deck_options[0]["id"])

    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.name.asc(), NoteType.updated_at.desc())
        .all()
    )
    note_type_options = [_serialize_note_type_for_import(note_type) for note_type in note_types]
    note_type_map = {item["id"]: item for item in note_type_options}

    selected_note_type_id = (request.args.get("note_type_id") or "").strip() or None
    if selected_note_type_id and selected_note_type_id not in note_type_map:
        selected_note_type_id = None

    if selected_note_type_id is None and selected_deck_id is not None:
        inferred = _infer_default_note_type_id_for_deck(selected_deck_id)
        if inferred and inferred in note_type_map:
            selected_note_type_id = inferred

    if selected_note_type_id is None and note_type_options:
        selected_note_type_id = note_type_options[0]["id"]

    uniqueness_defaults = {
        note_type.id: _default_uniqueness_fields(note_type)
        for note_type in note_types
    }

    return render_template(
        "flashcards/import.html",
        deck_options=deck_options,
        note_type_options=note_type_options,
        initial_deck_id=selected_deck_id,
        initial_note_type_id=selected_note_type_id,
        uniqueness_defaults=uniqueness_defaults,
    )


@flashcards_bp.route("/api/flashcards/import/parse", methods=["POST"])
@login_required
def flashcard_import_parse():
    note_type_id = (request.form.get("note_type_id") or "").strip()
    note_type = _get_note_type_or_404(note_type_id)
    if note_type is None:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404, field="note_type_id")

    upload = request.files.get("file")
    if upload is None or not upload.filename:
        return _api_error("VALIDATION_ERROR", "Import file is required.", field="file")

    delimiter_mode = (request.form.get("delimiter_mode") or "csv").strip().lower()
    custom_delimiter = request.form.get("custom_delimiter")
    has_header = _parse_bool(request.form.get("has_header"), default=True)

    try:
        delimiter = resolve_delimiter(delimiter_mode, custom_delimiter)
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc), field="delimiter_mode")

    file_bytes = upload.read()
    try:
        summary = create_import_session(
            user_id=current_user.id,
            filename=upload.filename,
            file_bytes=file_bytes,
            delimiter=delimiter,
            has_header=has_header,
            field_count=len(note_type.field_defs),
        )
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc))

    suggestions = suggest_mapping(
        field_defs=note_type.field_defs,
        has_header=has_header,
        header=summary.get("header") or [],
        column_count=int(summary.get("column_count") or 0),
    )

    return jsonify(
        {
            "token": summary.get("token"),
            "delimiter": delimiter,
            "has_header": has_header,
            "columns": summary.get("columns") or [],
            "column_count": int(summary.get("column_count") or 0),
            "total_rows": int(summary.get("total_rows") or 0),
            "preview_rows": summary.get("preview_rows") or [],
            "warnings": summary.get("warnings") or [],
            "suggested_mapping": suggestions,
        }
    )


def _resolve_import_execution_payload(payload: dict[str, Any]) -> tuple[dict[str, Any], NoteType, int | None]:
    return flashcard_import_ctrl.resolve_import_execution_payload(
        payload=payload,
        user_id=current_user.id,
        admin_mode=is_admin_user(current_user),
    )


@flashcards_bp.route("/api/flashcards/import/estimate", methods=["POST"])
@login_required
def flashcard_import_estimate():
    payload = request.get_json(silent=True) or {}
    try:
        session_meta, note_type, target_deck_id = _resolve_import_execution_payload(payload)
        report = run_import(
            user_id=current_user.id,
            session_meta=session_meta,
            note_type=note_type,
            target_deck_id=target_deck_id,
            mode=(payload.get("import_mode") or "upsert"),
            uniqueness_fields=payload.get("uniqueness_fields") or [],
            raw_mapping=payload.get("mapping") if isinstance(payload.get("mapping"), dict) else {},
            dont_overwrite_empty=_parse_bool(payload.get("dont_overwrite_empty"), default=True),
            confirm_column_mismatch=_parse_bool(payload.get("confirm_column_mismatch"), default=False),
            apply_changes=False,
            chunk_size=payload.get("chunk_size"),
        )
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc))

    return jsonify(report)


@flashcards_bp.route("/api/flashcards/import/execute", methods=["POST"])
@login_required
def flashcard_import_execute():
    payload = request.get_json(silent=True) or {}
    try:
        session_meta, note_type, target_deck_id = _resolve_import_execution_payload(payload)
        report = run_import(
            user_id=current_user.id,
            session_meta=session_meta,
            note_type=note_type,
            target_deck_id=target_deck_id,
            mode=(payload.get("import_mode") or "upsert"),
            uniqueness_fields=payload.get("uniqueness_fields") or [],
            raw_mapping=payload.get("mapping") if isinstance(payload.get("mapping"), dict) else {},
            dont_overwrite_empty=_parse_bool(payload.get("dont_overwrite_empty"), default=True),
            confirm_column_mismatch=_parse_bool(payload.get("confirm_column_mismatch"), default=False),
            apply_changes=True,
            chunk_size=payload.get("chunk_size"),
        )
    except ImportValidationError as exc:
        return _api_error("VALIDATION_ERROR", str(exc))

    summary = report.get("summary") or {}
    if int(summary.get("inserted") or 0) > 0 or int(summary.get("updated") or 0) > 0:
        _touch_note_type_install_usage(user_id=current_user.id, installed_note_type_id=note_type.id)
        install_rows = NoteTypeInstall.query.filter_by(
            user_id=current_user.id,
            installed_note_type_id=note_type.id,
        ).all()
        for install in install_rows:
            source_note_type = NoteType.query.get(install.source_note_type_id)
            if source_note_type:
                _recompute_note_type_market_stats(source_note_type)

    _audit(
        "note.import",
        {
            "note_type_id": note_type.id,
            "target_deck_id": target_deck_id,
            "mode": report.get("mode"),
            "summary": summary,
        },
    )
    db.session.commit()
    return jsonify(report)


@flashcards_bp.route("/flashcards/study")
@login_required
def flashcard_study_page():
    decks = Deck.query.order_by(Deck.name.asc()).all()
    return render_template("flashcards/study.html", decks=decks)


@flashcards_bp.route("/flashcards/notes")
@login_required
def notes_list_page():
    """Note management — list, filter, quick delete."""
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập trang này.", "danger")
        return redirect(url_for("main.dashboard"))
    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.name.asc())
        .all()
    )
    decks = Deck.query.order_by(Deck.name.asc()).all()

    # Filters from query string
    selected_nt = request.args.get("note_type_id", "")
    selected_deck = request.args.get("deck_id", "")
    search_q = request.args.get("q", "").strip()
    page = max(1, int(request.args.get("page", "1")))
    per_page = 30

    query = Note.query.filter_by(user_id=current_user.id)
    if selected_nt:
        query = query.filter(Note.note_type_id == selected_nt)
    if selected_deck:
        try:
            query = query.filter(Note.deck_id == int(selected_deck))
        except ValueError:
            pass

    # JSON search by first field value (simple contains)
    if search_q:
        query = query.filter(
            Note.field_values.cast(db.Text).ilike(f"%{search_q}%")
        )

    pagination = query.order_by(Note.updated_at.desc()).paginate(
        page=page, per_page=per_page, error_out=False
    )

    # Build display rows: extract first text field as "title"
    rows = []
    for note in pagination.items:
        note_type_obj = next(
            (nt for nt in note_types if nt.id == note.note_type_id), None
        )
        first_field = None
        if note_type_obj:
            sorted_fields = sorted(note_type_obj.field_defs, key=lambda f: f.position)
            for fd in sorted_fields:
                if fd.field_type in {"text", "richtext"}:
                    first_field = fd.name
                    break
        title = (note.field_values or {}).get(first_field or "", "") or f"Note #{note.id}"
        rows.append(
            {
                "note": note,
                "title": str(title)[:80],
                "note_type_name": note_type_obj.name if note_type_obj else "—",
            }
        )

    return render_template(
        "flashcards/notes_list.html",
        rows=rows,
        pagination=pagination,
        note_types=note_types,
        decks=decks,
        selected_nt=selected_nt,
        selected_deck=selected_deck,
        search_q=search_q,
    )


@flashcards_bp.route("/flashcards/notes/<note_id>/edit")
@login_required
def note_edit_page(note_id: str):
    """Edit an existing note."""
    if not is_admin_user(current_user):
        flash("Bạn không có quyền truy cập trang này.", "danger")
        return redirect(url_for("main.dashboard"))
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return redirect(url_for("flashcards.notes_list_page"))
    note_type = NoteType.query.get(note.note_type_id)
    decks = Deck.query.order_by(Deck.name.asc()).all()
    return render_template(
        "flashcards/note_edit.html",
        note=note,
        note_type=note_type,
        decks=decks,
    )


@flashcards_bp.route("/api/note-types", methods=["GET"])
@login_required
def list_note_types():
    note_types = NoteType.query.filter_by(user_id=current_user.id).order_by(NoteType.updated_at.desc()).all()
    return jsonify({"items": [_serialize_note_type(note_type) for note_type in note_types]})


@flashcards_bp.route("/api/note-types", methods=["POST"])
@login_required
def create_note_type():
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or payload.get("title") or "").strip()
    if not name:
        return _api_error("VALIDATION_ERROR", "Note type name is required.", field="name")

    if NoteType.query.filter_by(user_id=current_user.id, name=name).first():
        return _api_error("VALIDATION_ERROR", "Note type already exists.", field="name")

    note_type = NoteType(user_id=current_user.id, name=name)
    db.session.add(note_type)
    db.session.flush()

    input_fields = payload.get("field_defs")
    if not isinstance(input_fields, list) or not input_fields:
        input_fields = [{"name": "Word", "field_type": "text", "position": 0, "required": True}]

    for idx, row in enumerate(input_fields):
        field_name = (row.get("name") or "").strip()
        field_type = (row.get("field_type") or "text").strip()
        required = bool(row.get("required", False))
        if not field_name:
            return _api_error("VALIDATION_ERROR", "Field name is required.", field="field_defs")
        if field_type not in FIELD_TYPES:
            return _api_error("VALIDATION_ERROR", f"Unsupported field_type: {field_type}", field="field_defs")
        db.session.add(
            FieldDef(
                note_type_id=note_type.id,
                name=field_name,
                field_type=field_type,
                position=int(row.get("position", idx)),
                required=required,
            )
        )

    template_payload = payload.get("template") or {}
    front_html = (template_payload.get("front_html") or "{{Word}}").strip()
    back_html = (template_payload.get("back_html") or "{{Word}}").strip()
    shared_css = (template_payload.get("shared_css") or "").strip()
    template = Template(
        note_type_id=note_type.id,
        name=(template_payload.get("name") or "Card 1").strip() or "Card 1",
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=0,
        is_default=True,
    )
    db.session.add(template)
    metadata_error = _apply_note_type_marketplace_payload(note_type, payload)
    if metadata_error:
        db.session.rollback()
        return _api_error("VALIDATION_ERROR", metadata_error)
    _audit("note_type.create", {"note_type_id": note_type.id, "name": note_type.name})
    db.session.commit()
    return jsonify(_serialize_note_type(note_type)), 201


@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["GET"])
@login_required
def get_note_type_detail(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    return jsonify(_serialize_note_type(note_type))


@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["PATCH"])
@login_required
def patch_note_type(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    validation_error = _apply_note_type_marketplace_payload(note_type, payload)
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)
    _audit("note_type.update", {"note_type_id": note_type.id})
    db.session.commit()
    return jsonify(_serialize_note_type(note_type))


@flashcards_bp.route("/api/note-types/<note_type_id>", methods=["DELETE"])
@login_required
def delete_note_type(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    note_count = Note.query.filter_by(note_type_id=note_type.id).count()
    if note_count > 0:
        return _api_error("NOTE_TYPE_HAS_NOTES", "Cannot delete note type with existing notes.", status=409)
    db.session.delete(note_type)
    _audit("note_type.delete", {"note_type_id": note_type_id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/note-types/<note_type_id>/fields", methods=["GET"])
@login_required
def list_fields(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    fields = FieldDef.query.filter_by(note_type_id=note_type.id).order_by(FieldDef.position.asc()).all()
    return jsonify({"items": [_serialize_field(field) for field in fields]})


@flashcards_bp.route("/api/note-types/<note_type_id>/fields", methods=["POST"])
@login_required
def create_field(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip()
    field_type = (payload.get("field_type") or "text").strip()
    required = bool(payload.get("required", False))
    if not name:
        return _api_error("VALIDATION_ERROR", "Field name is required.", field="name")
    if field_type not in FIELD_TYPES:
        return _api_error("VALIDATION_ERROR", "Unsupported field_type.", field="field_type")
    if FieldDef.query.filter_by(note_type_id=note_type.id, name=name).first():
        return _api_error("VALIDATION_ERROR", "Field name already exists in this note type.", field="name")
    max_pos = db.session.query(db.func.max(FieldDef.position)).filter_by(note_type_id=note_type.id).scalar() or -1
    field = FieldDef(
        note_type_id=note_type.id,
        name=name,
        field_type=field_type,
        required=required,
        position=max_pos + 1,
    )
    db.session.add(field)
    _audit("field.create", {"note_type_id": note_type.id, "field_id": field.id, "name": field.name})
    db.session.commit()
    return jsonify(_serialize_field(field)), 201


@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>", methods=["PATCH"])
@login_required
def patch_field(note_type_id: str, field_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    field = FieldDef.query.filter_by(id=field_id, note_type_id=note_type.id).first()
    if not field:
        return _api_error("FIELD_NOT_FOUND", "Field not found.", status=404)
    payload = request.get_json(silent=True) or {}

    old_name = field.name
    new_name = (payload.get("name") or field.name).strip()
    new_type = (payload.get("field_type") or field.field_type).strip()
    required = payload.get("required")

    if not new_name:
        return _api_error("VALIDATION_ERROR", "Field name is required.", field="name")
    if new_type not in FIELD_TYPES:
        return _api_error("VALIDATION_ERROR", "Unsupported field_type.", field="field_type")
    conflict = FieldDef.query.filter(
        FieldDef.note_type_id == note_type.id,
        FieldDef.name == new_name,
        FieldDef.id != field.id,
    ).first()
    if conflict:
        return _api_error("VALIDATION_ERROR", "Field name already exists.", field="name")

    field.field_type = new_type
    if required is not None:
        field.required = bool(required)

    job_payload = None
    if old_name != new_name:
        job = _run_field_rename_job(note_type, field, old_name, new_name)
        field.name = new_name
        job_payload = {"job_id": job.id, "status": job.status, "processed_notes": job.processed_notes}

    _audit(
        "field.update",
        {"note_type_id": note_type.id, "field_id": field.id, "old_name": old_name, "new_name": field.name},
    )
    db.session.commit()
    response_payload = {"field": _serialize_field(field)}
    if job_payload:
        response_payload["rename_job"] = job_payload
    return jsonify(response_payload)


@flashcards_bp.route("/api/note-types/<note_type_id>/fields/<field_id>", methods=["DELETE"])
@login_required
def delete_field(note_type_id: str, field_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    field = FieldDef.query.filter_by(id=field_id, note_type_id=note_type.id).first()
    if not field:
        return _api_error("FIELD_NOT_FOUND", "Field not found.", status=404)

    notes = Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).all()
    for note in notes:
        values = dict(note.field_values or {})
        values.pop(field.name, None)
        note.field_values = values

    db.session.delete(field)
    _audit("field.delete", {"note_type_id": note_type.id, "field_id": field_id, "field_name": field.name})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/note-types/<note_type_id>/fields/reorder", methods=["POST"])
@login_required
def reorder_fields(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True)
    if not isinstance(payload, list):
        return _api_error("VALIDATION_ERROR", "Payload must be a list.", field="body")
    ok, err = _reorder_fields(note_type.id, payload)
    if not ok:
        return _api_error("VALIDATION_ERROR", err or "Invalid reorder payload.", field="body")
    _audit("field.reorder", {"note_type_id": note_type.id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["GET"])
@login_required
def list_templates(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    templates = Template.query.filter_by(note_type_id=note_type.id).order_by(Template.position.asc()).all()
    return jsonify({"items": [_serialize_template(template) for template in templates]})


@flashcards_bp.route("/api/note-types/<note_type_id>/templates", methods=["POST"])
@login_required
def create_template(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    name = (payload.get("name") or "").strip() or f"Card {Template.query.filter_by(note_type_id=note_type.id).count() + 1}"
    front_html = (payload.get("front_html") or "{{Word}}").strip()
    back_html = (payload.get("back_html") or "{{Word}}").strip()
    shared_css = (payload.get("shared_css") or "").strip()
    max_pos = db.session.query(db.func.max(Template.position)).filter_by(note_type_id=note_type.id).scalar() or -1
    template = Template(
        note_type_id=note_type.id,
        name=name,
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        position=max_pos + 1,
        is_default=False,
    )
    db.session.add(template)
    db.session.flush()
    notes = Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).all()
    for note in notes:
        db.session.add(Card(note_id=note.id, template_id=template.id))
    _audit("template.create", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify(_serialize_template(template)), 201


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["PATCH"])
@login_required
def patch_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    payload = request.get_json(silent=True) or {}
    if "name" in payload:
        template.name = (payload.get("name") or "").strip() or template.name
    if "front_html" in payload:
        template.front_html = str(payload.get("front_html") or "")
    if "back_html" in payload:
        template.back_html = str(payload.get("back_html") or "")
    if "shared_css" in payload:
        template.shared_css = str(payload.get("shared_css") or "")

    try:
        render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values={},
            media_assets=[],
            preview_note_key="validation",
        )
    except TemplateCompileError as exc:
        db.session.rollback()
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    _audit("template.update", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify(_serialize_template(template))


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>", methods=["DELETE"])
@login_required
def delete_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    if template.is_default:
        return _api_error("VALIDATION_ERROR", "Cannot delete default template.", status=409)
    if Template.query.filter_by(note_type_id=note_type.id).count() <= 1:
        return _api_error("VALIDATION_ERROR", "A note type requires at least one template.", status=409)
    Card.query.filter_by(template_id=template.id).delete()
    db.session.delete(template)
    _audit("template.delete", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/reset", methods=["POST"])
@login_required
def reset_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)
    template.front_html = LEGACY_FRONT_TEMPLATE.strip()
    template.back_html = LEGACY_BACK_TEMPLATE.strip()
    template.shared_css = LEGACY_SHARED_CSS.strip()
    db.session.commit()
    return jsonify(_serialize_template(template))


@flashcards_bp.route("/api/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_template(note_type_id: str, template_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    payload = request.get_json(silent=True) or {}
    note_id = (payload.get("note_id") or "").strip()
    raw_use_sample_data = payload.get("use_sample_data", False)
    use_sample_data = bool(raw_use_sample_data)
    if isinstance(raw_use_sample_data, str):
        use_sample_data = raw_use_sample_data.strip().lower() in {"1", "true", "yes", "on"}
    
    # Cho phép ghi đè nội dung HTML/CSS thông qua payload (phục vụ Live Preview chưa lưu)
    preview_front_html = template.front_html
    preview_back_html = template.back_html
    preview_shared_css = template.shared_css
    if "front_html" in payload:
        preview_front_html = str(payload.get("front_html") or "")
    if "back_html" in payload:
        preview_back_html = str(payload.get("back_html") or "")
    if "shared_css" in payload:
        preview_shared_css = str(payload.get("shared_css") or "")

    preview_template_obj = SimpleNamespace(
        id=template.id,
        front_html=preview_front_html,
        back_html=preview_back_html,
        shared_css=preview_shared_css,
        updated_at=template.updated_at,
    )

    sample_field_values: dict[str, Any]
    sample_media_assets: list[MediaAsset]
    preview_note_key: str
    if use_sample_data:
        sample_field_values = _build_preview_sample_values(note_type.field_defs)
        sample_media_assets = []
        preview_note_key = f"sample:{note_type.id}"
    else:
        note = None
        if note_id:
            note = Note.query.filter_by(id=note_id, user_id=current_user.id, note_type_id=note_type.id).first()
        if note is None:
            note = (
                Note.query.filter_by(note_type_id=note_type.id, user_id=current_user.id)
                .order_by(Note.created_at.asc())
                .first()
            )
        sample_field_values = {}
        sample_media_assets = []
        preview_note_key = note.id if note else "empty-note"
        if note:
            sample_field_values = note.field_values or {}
            sample_media_assets = note.media_assets

    try:
        rendered = render_template_pair(
            template=preview_template_obj,
            field_defs=note_type.field_defs,
            field_values=sample_field_values,
            media_assets=sample_media_assets,
            preview_note_key=preview_note_key,
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)


@flashcards_bp.route("/api/notes", methods=["GET"])
@login_required
def list_notes():
    note_type_id = (request.args.get("note_type_id") or "").strip()
    deck_id_raw = (request.args.get("deck_id") or "").strip()
    page = max(1, int(request.args.get("page", "1")))
    per_page = max(1, min(100, int(request.args.get("per_page", "20"))))

    query = Note.query.filter_by(user_id=current_user.id)
    if note_type_id:
        query = query.filter(Note.note_type_id == note_type_id)
    if deck_id_raw:
        try:
            deck_id = int(deck_id_raw)
            query = query.filter(Note.deck_id == deck_id)
        except ValueError:
            return _api_error("VALIDATION_ERROR", "deck_id must be an integer.", field="deck_id")

    pagination = query.order_by(Note.updated_at.desc()).paginate(page=page, per_page=per_page, error_out=False)
    items = []
    for note in pagination.items:
        items.append(
            {
                "id": note.id,
                "note_type_id": note.note_type_id,
                "deck_id": note.deck_id,
                "field_values": note.field_values or {},
                "tags": note.tags or [],
                "created_at": note.created_at.isoformat() if note.created_at else None,
                "updated_at": note.updated_at.isoformat() if note.updated_at else None,
            }
        )
    return jsonify(
        {
            "items": items,
            "page": page,
            "per_page": per_page,
            "total": pagination.total,
        }
    )


@flashcards_bp.route("/api/notes", methods=["POST"])
@login_required
def create_note():
    payload = request.get_json(silent=True) or {}
    note_type_id = (payload.get("note_type_id") or "").strip()
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    cleaned_values, err = _validate_note_payload(note_type, payload, partial=False)
    if err:
        return _api_error("VALIDATION_ERROR", err, field="field_values")
    tags = _normalize_tags(payload.get("tags"))
    deck_id = payload.get("deck_id")
    if deck_id in ("", None):
        parsed_deck_id = None
    else:
        try:
            parsed_deck_id = int(deck_id)
        except (TypeError, ValueError):
            return _api_error("VALIDATION_ERROR", "deck_id must be an integer.", field="deck_id")

    deck_consistency_error = _validate_note_type_consistency_for_deck(
        deck_id=parsed_deck_id,
        note_type_id=note_type.id,
        user_id=current_user.id,
    )
    if deck_consistency_error:
        return _api_error("VALIDATION_ERROR", deck_consistency_error, field="deck_id")

    note = Note(
        note_type_id=note_type.id,
        user_id=current_user.id,
        deck_id=parsed_deck_id,
        field_values=cleaned_values,
        tags=tags,
    )
    db.session.add(note)
    db.session.flush()
    _create_cards_for_note(note)
    _touch_note_type_install_usage(user_id=current_user.id, installed_note_type_id=note.note_type_id)
    install_rows = NoteTypeInstall.query.filter_by(
        user_id=current_user.id,
        installed_note_type_id=note.note_type_id,
    ).all()
    for install in install_rows:
        source_note_type = NoteType.query.get(install.source_note_type_id)
        if source_note_type:
            _recompute_note_type_market_stats(source_note_type)
    _audit("note.create", {"note_id": note.id, "note_type_id": note.note_type_id})
    db.session.commit()
    return jsonify({"id": note.id, "field_values": note.field_values, "tags": note.tags}), 201


@flashcards_bp.route("/api/notes/<note_id>", methods=["GET"])
@login_required
def get_note(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    return jsonify(
        {
            "id": note.id,
            "note_type_id": note.note_type_id,
            "deck_id": note.deck_id,
            "field_values": note.field_values or {},
            "tags": note.tags or [],
            "media_assets": [
                {
                    "id": asset.id,
                    "field_name": asset.field_name,
                    "filename": asset.filename,
                    "mime_type": asset.mime_type,
                    "url": f"/media/proxy/{asset.id}",
                }
                for asset in note.media_assets
            ],
        }
    )


@flashcards_bp.route("/api/notes/<note_id>", methods=["PATCH"])
@login_required
def patch_note(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    payload = request.get_json(silent=True) or {}
    note_type = _get_note_type_or_404(note.note_type_id)
    if note_type is None:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    cleaned_values, err = _validate_note_payload(note_type, payload, partial=True)
    if err:
        return _api_error("VALIDATION_ERROR", err, field="field_values")
    values = dict(note.field_values or {})
    values.update(cleaned_values)
    for field in note_type.field_defs:
        if field.required and is_field_empty(values.get(field.name)):
            return _api_error("VALIDATION_ERROR", f"Field '{field.name}' is required.", field=field.name)
    note.field_values = values

    if "tags" in payload:
        note.tags = _normalize_tags(payload.get("tags"))
    if "deck_id" in payload:
        deck_id = payload.get("deck_id")
        if deck_id in ("", None):
            note.deck_id = None
        else:
            try:
                note.deck_id = int(deck_id)
            except (TypeError, ValueError):
                return _api_error("VALIDATION_ERROR", "deck_id must be an integer.", field="deck_id")

    deck_consistency_error = _validate_note_type_consistency_for_deck(
        deck_id=note.deck_id,
        note_type_id=note.note_type_id,
        user_id=current_user.id,
        exclude_note_id=note.id,
    )
    if deck_consistency_error:
        return _api_error("VALIDATION_ERROR", deck_consistency_error, field="deck_id")
    _audit("note.update", {"note_id": note.id})
    db.session.commit()
    return jsonify({"id": note.id, "field_values": note.field_values, "tags": note.tags})


@flashcards_bp.route("/api/notes/<note_id>", methods=["DELETE"])
@login_required
def delete_note(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    db.session.delete(note)
    _audit("note.delete", {"note_id": note_id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/api/notes/<note_id>/media", methods=["POST"])
@login_required
def upload_note_media(note_id: str):
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return _api_error("FIELD_NOT_FOUND", "Note not found.", status=404)
    field_name = (request.form.get("field_name") or "").strip()
    if not field_name:
        return _api_error("VALIDATION_ERROR", "field_name is required.", field="field_name")
    field_def = FieldDef.query.filter_by(note_type_id=note.note_type_id, name=field_name).first()
    if not field_def:
        return _api_error("FIELD_NOT_FOUND", "Field not found in note type.", field="field_name", status=404)
    if field_def.field_type not in {"image", "audio", "diagram"}:
        return _api_error("VALIDATION_ERROR", "Field does not accept media.", field="field_name")

    uploaded = request.files.get("file")
    if uploaded is None or not uploaded.filename:
        return _api_error("VALIDATION_ERROR", "Missing uploaded file.", field="file")

    content = uploaded.read()
    if not content:
        return _api_error("VALIDATION_ERROR", "Uploaded file is empty.", field="file")

    max_bytes = int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 10 * 1024 * 1024))
    if len(content) > max_bytes:
        return _api_error("MEDIA_TOO_LARGE", f"File exceeds {max_bytes} bytes.", field="file", status=413)

    mime_type = uploaded.mimetype or "application/octet-stream"
    if mime_type not in ALLOWED_MEDIA_MIME_TYPES:
        return _api_error("MEDIA_TYPE_NOT_ALLOWED", f"Unsupported media type: {mime_type}", field="file", status=415)

    digest = hashlib.sha256(content).hexdigest()
    existing = MediaAsset.query.filter_by(note_id=note.id, field_name=field_name, sha256=digest).first()
    if existing:
        values = dict(note.field_values or {})
        values[field_name] = existing.id
        note.field_values = values
        db.session.commit()
        return jsonify({"asset_id": existing.id, "url": f"/media/proxy/{existing.id}", "field_name": field_name})

    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    safe_name = Path(uploaded.filename).name.replace(" ", "_")
    relative_dir = Path(str(current_user.id)) / note.id
    final_dir = upload_root / relative_dir
    final_dir.mkdir(parents=True, exist_ok=True)
    filename = f"{digest[:8]}_{safe_name}"
    relative_path = relative_dir / filename
    full_path = upload_root / relative_path
    full_path.write_bytes(content)

    asset = MediaAsset(
        note_id=note.id,
        field_name=field_name,
        filename=safe_name,
        mime_type=mime_type,
        storage_path=str(relative_path).replace("\\", "/"),
        sha256=digest,
        size_bytes=len(content),
    )
    db.session.add(asset)
    db.session.flush()
    values = dict(note.field_values or {})
    values[field_name] = asset.id
    note.field_values = values
    _audit("media.upload", {"note_id": note.id, "asset_id": asset.id, "field_name": field_name})
    db.session.commit()
    return jsonify({"asset_id": asset.id, "url": f"/media/proxy/{asset.id}", "field_name": field_name}), 201


@flashcards_bp.route("/api/media/<asset_id>", methods=["DELETE"])
@login_required
def delete_media(asset_id: str):
    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == current_user.id)
        .first()
    )
    if not asset:
        return _api_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    full_path = (upload_root / asset.storage_path).resolve()
    if full_path.exists():
        try:
            full_path.unlink()
        except OSError:
            logger.warning("Failed to delete media file %s", full_path)
    note = asset.note
    values = dict(note.field_values or {})
    if values.get(asset.field_name) == asset.id:
        values[asset.field_name] = ""
        note.field_values = values
    db.session.delete(asset)
    _audit("media.delete", {"asset_id": asset_id, "note_id": note.id})
    db.session.commit()
    return jsonify({"success": True})


@flashcards_bp.route("/media/proxy/<asset_id>", methods=["GET"])
@login_required
def proxy_media(asset_id: str):
    asset = (
        MediaAsset.query.join(Note, MediaAsset.note_id == Note.id)
        .filter(MediaAsset.id == asset_id, Note.user_id == current_user.id)
        .first()
    )
    if not asset:
        return _api_error("FIELD_NOT_FOUND", "Media asset not found.", status=404)
    upload_root = Path(current_app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"])
    full_path = (upload_root / asset.storage_path).resolve()
    if not full_path.exists():
        return _api_error("FIELD_NOT_FOUND", "Media file not found on disk.", status=404)
    return send_file(full_path, mimetype=asset.mime_type, conditional=True, max_age=3600)


@flashcards_bp.route("/api/study/next", methods=["GET"])
@login_required
def study_next():
    scope = (request.args.get("scope") or "deck").strip().lower()
    scope_id_raw = (request.args.get("scope_id") or "").strip()

    clone_scope: share_ctrl.CloneDeckScope | None = None
    query = None
    if scope == "deck":
        if not scope_id_raw:
            return _api_error("VALIDATION_ERROR", "scope_id is required for deck scope.", field="scope_id")
        try:
            scope_id = int(scope_id_raw)
        except ValueError:
            return _api_error("VALIDATION_ERROR", "scope_id must be an integer for deck scope.", field="scope_id")
        clone_scope = _resolve_clone_scope_for_local_deck(
            user_id=current_user.id,
            local_deck_id=scope_id,
        )
        if clone_scope is not None:
            query = _query_clone_scope_cards(clone_scope)
        else:
            scope_deck_ids = _collect_deck_subtree_ids(scope_id)
            if not scope_deck_ids:
                return jsonify({"card_id": None, "message": "No cards found for selected scope."})
            query = Card.query.join(Note, Card.note_id == Note.id).filter(
                Note.user_id == current_user.id,
                Note.deck_id.in_(scope_deck_ids),
            )
    elif scope == "note_type":
        if not scope_id_raw:
            return _api_error("VALIDATION_ERROR", "scope_id is required for note_type scope.", field="scope_id")
        query = Card.query.join(Note, Card.note_id == Note.id).filter(
            Note.user_id == current_user.id,
            Note.note_type_id == scope_id_raw,
        )
    else:
        return _api_error("VALIDATION_ERROR", f"Unsupported scope: {scope}", field="scope")

    if query is None:
        return jsonify({"card_id": None, "message": "No cards found for selected scope."})
    if not query.with_entities(Card.id).first():
        return jsonify({"card_id": None, "message": "No cards found for selected scope."})

    now = datetime.utcnow()
    selected_card_id = _query_next_due_card_id(
        query,
        user_id=current_user.id,
        now=now,
    )
    if not selected_card_id:
        return jsonify({"card_id": None, "message": "No due cards."})

    selected_card = query.filter(Card.id == selected_card_id).first()
    if not selected_card:
        return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)
    if clone_scope is not None and not _is_card_visible_in_clone_scope(scope=clone_scope, card_obj=selected_card):
        return jsonify({"card_id": None, "message": "No due cards."})

    progress = CardProgress.query.filter_by(user_id=current_user.id, card_id=selected_card.id).first()
    card_state = _card_state_from_progress(progress, now)
    interval_preview = computeAnswerPreview(card_state, default_deck_options(), now)

    note = selected_card.note
    template = selected_card.template
    render_field_defs = note.note_type.field_defs
    render_field_values = note.field_values or {}
    if clone_scope is not None:
        source_note_type_id = (clone_scope.install.source_note_type_id or note.note_type_id or "").strip()
        if source_note_type_id:
            schema_view = _build_clone_schema_view(
                install=clone_scope.install,
                source_note_type_id=source_note_type_id,
            )
            if schema_view.field_defs:
                render_field_defs = schema_view.field_defs
            render_field_values = _apply_clone_note_field_overrides(
                install=clone_scope.install,
                source_note=note,
                schema_view=schema_view,
            )
    try:
        rendered = render_template_pair(
            template=template,
            field_defs=render_field_defs,
            field_values=render_field_values,
            media_assets=note.media_assets,
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc))

    return jsonify(
        {
            "card_id": selected_card.id,
            "note_id": note.id,
            "template_id": template.id,
            "rendered_front_html": rendered["front_html"],
            "rendered_back_html": rendered["back_html"],
            "intervals_preview": interval_preview,
        }
    )


@flashcards_bp.route("/api/study/<card_id>/answer", methods=["POST"])
@login_required
def study_answer(card_id: str):
    payload = request.get_json(silent=True) or {}
    rating = (payload.get("rating") or "").strip().lower()
    if rating not in {"again", "hard", "good", "easy"}:
        return _api_error("VALIDATION_ERROR", "rating must be one of: again, hard, good, easy.", field="rating")

    scope = (payload.get("scope") or "").strip().lower()
    requested_scope_id = None
    if scope == "deck":
        try:
            requested_scope_id = int(payload.get("scope_id"))
        except (TypeError, ValueError):
            requested_scope_id = None

    card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id).first()
    if not card:
        return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)
    clone_scope: share_ctrl.CloneDeckScope | None = None
    if card.note.user_id != current_user.id:
        clone_scope = _resolve_clone_scope_for_card(user_id=current_user.id, card_obj=card)
        if clone_scope is None:
            return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)
        if not _is_card_visible_in_clone_scope(scope=clone_scope, card_obj=card):
            return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)

    progress = CardProgress.query.filter_by(user_id=current_user.id, card_id=card.id).first()
    if progress is None:
        progress = CardProgress(
            user_id=current_user.id,
            card_id=card.id,
            queue="new",
            step_index=0,
            due_at=None,
            due_day=None,
            interval_days=0,
            ease_factor=default_deck_options().startingEase,
            reps=0,
            lapses=0,
        )
        db.session.add(progress)
        db.session.flush()

    now = datetime.utcnow()
    current_state = _card_state_from_progress(progress, now)
    review_mode = normalize_review_mode(current_state.type)
    updated_state = applyAnswer(current_state, default_deck_options(), now, rating)  # type: ignore[arg-type]
    _apply_card_state_to_progress(progress, updated_state, now)
    _touch_note_type_install_usage(user_id=current_user.id, installed_note_type_id=card.note.note_type_id, activity_at=now)

    local_deck_id_for_usage = card.note.deck_id
    if clone_scope is not None:
        local_deck_id_for_usage = (
            requested_scope_id
            if requested_scope_id is not None
            else _resolve_local_clone_deck_id_for_source_deck(
                install_id=clone_scope.install.id,
                source_deck_id=card.note.deck_id,
            )
        ) or clone_scope.install.local_deck_id

    if local_deck_id_for_usage is not None:
        _touch_deck_install_usage(user_id=current_user.id, local_deck_id=local_deck_id_for_usage, activity_at=now)
    update_user_timezone(current_user, payload.get("timezone"))
    record_review_event(
        user_id=current_user.id,
        card_id=card.id,
        deck_id=local_deck_id_for_usage,
        note_type_id=card.note.note_type_id,
        reviewed_at=now,
        duration_ms=payload.get("duration_ms"),
        rating=rating,
        mode=review_mode,
    )
    _audit("study.answer", {"card_id": card.id, "rating": rating})
    db.session.commit()
    next_scope_id = requested_scope_id if requested_scope_id is not None else local_deck_id_for_usage
    next_card_url = url_for("flashcards.study_next", scope="deck", scope_id=next_scope_id) if next_scope_id else None
    next_url = None
    if scope == "deck":
        if requested_scope_id is not None:
            next_url = url_for("vocabulary.study_deck", deck_id=requested_scope_id)
    return jsonify(
        {
            "success": True,
            "next_url": next_url,
            "next_card_url": next_card_url,
            "intervals_preview": computeAnswerPreview(updated_state, default_deck_options(), now),
        }
    )


@flashcards_bp.route("/api/flashcards/seed-default-note-type", methods=["POST"])
@login_required
def seed_default_note_type():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)
    note_type, template = ensure_legacy_note_type(db.session, current_user.id)
    _audit("note_type.seed_default", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify({"note_type_id": note_type.id, "template_id": template.id})


def _parse_query_price_cents(param_name: str) -> int | None:
    return marketplace_ctrl.parse_query_price_cents(request.args.get(param_name))


@flashcards_bp.route("/api/note-types/<note_type_id>/publish", methods=["POST"])
@login_required
def publish_note_type(note_type_id: str):
    note_type = _get_note_type_or_404(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    payload = request.get_json(silent=True) or {}
    payload.setdefault("publish_status", "published")
    validation_error = _apply_note_type_marketplace_payload(note_type, payload)
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)
    _recompute_note_type_market_stats(note_type)
    _audit("note_type.publish", {"note_type_id": note_type.id, "publish_status": note_type.publish_status})
    db.session.commit()
    return jsonify(_serialize_note_type(note_type))


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


@flashcards_bp.route("/api/shared/note-types", methods=["GET"])
@login_required
def list_shared_note_types():
    query_text = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    tags = {item.lower() for item in _normalize_marketplace_tags(request.args.get("tags"))}
    pricing_mode = (request.args.get("pricing_mode") or request.args.get("pricing") or "").strip().lower()
    sort_key = (request.args.get("sort") or "popular").strip().lower()
    min_price_cents = _parse_query_price_cents("min_price")
    max_price_cents = _parse_query_price_cents("max_price")

    visible_note_types = [
        item for item in NoteType.query.order_by(NoteType.updated_at.desc()).all()
        if _is_note_type_visible_for_shared(item)
    ]
    filtered = _filter_note_type_items(
        visible_note_types,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )
    sorted_items = _sort_note_type_items(filtered, sort_key)

    installs = NoteTypeInstall.query.filter_by(user_id=current_user.id).all()
    install_map = {row.source_note_type_id: row for row in installs}
    payload_items = []
    for note_type in sorted_items:
        row = _serialize_note_type_marketplace_card(note_type)
        install = install_map.get(note_type.id)
        row["is_installed"] = install is not None
        row["installed_note_type_id"] = install.installed_note_type_id if install else None
        row["is_owner"] = note_type.user_id == current_user.id
        payload_items.append(row)
    return jsonify({"items": payload_items})


@flashcards_bp.route("/api/shared/note-types/<note_type_id>", methods=["GET"])
@login_required
def get_shared_note_type_detail(note_type_id: str):
    note_type = _get_shared_note_type_for_view(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    install = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id,
        user_id=current_user.id,
    ).first()
    review = NoteTypeReview.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).first()
    payload = _serialize_note_type_marketplace_card(note_type)
    payload["is_installed"] = install is not None
    payload["installed_note_type_id"] = install.installed_note_type_id if install else None
    payload["is_owner"] = note_type.user_id == current_user.id
    payload["can_rate"] = _can_user_rate_note_type(note_type, user_id=current_user.id)
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }
        if review
        else None
    )
    return jsonify(payload)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_note_type_template(note_type_id: str, template_id: str):
    note_type = _get_shared_note_type_for_view(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    sample_field_values = _build_preview_sample_values(note_type.field_defs)

    try:
        rendered = render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values=sample_field_values,
            media_assets=[],
            preview_note_key=f"shared-preview:{note_type.id}",
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/install", methods=["POST"])
@login_required
def install_shared_note_type(note_type_id: str):
    source_note_type = NoteType.query.get(note_type_id)
    if not source_note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    status = str(source_note_type.publish_status or "").strip().lower()
    if status not in PUBLISH_STATUSES_VISIBLE:
        return _api_error("VALIDATION_ERROR", "This note type is not available for install.", status=409)
    if source_note_type.user_id == current_user.id:
        return _api_error("VALIDATION_ERROR", "Owner cannot install own note type.", status=409)

    existing = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=current_user.id,
    ).first()
    if existing:
        return jsonify(
            {
                "installed_note_type_id": existing.installed_note_type_id,
                "source_note_type_id": source_note_type.id,
                "already_installed": True,
            }
        )

    installed_copy = _clone_note_type_for_user(source_note_type, current_user.id)
    now = datetime.utcnow()
    purchase_price_cents = int(source_note_type.price_cents or 0) if source_note_type.pricing_mode == "paid" else 0
    install_row = NoteTypeInstall(
        source_note_type_id=source_note_type.id,
        installed_note_type_id=installed_copy.id,
        user_id=current_user.id,
        purchase_price_cents=purchase_price_cents,
        installed_at=now,
        purchased_at=now if source_note_type.pricing_mode == "paid" else None,
    )
    db.session.add(install_row)
    _recompute_note_type_market_stats(source_note_type)
    _audit(
        "market.note_type.install",
        {
            "source_note_type_id": source_note_type.id,
            "installed_note_type_id": installed_copy.id,
            "price_cents": purchase_price_cents,
        },
    )
    db.session.commit()
    return jsonify(
        {
            "installed_note_type_id": installed_copy.id,
            "source_note_type_id": source_note_type.id,
            "purchase_price_cents": purchase_price_cents,
        }
    ), 201


@flashcards_bp.route("/api/shared/note-types/<note_type_id>/rate", methods=["POST"])
@login_required
def rate_shared_note_type(note_type_id: str):
    note_type = NoteType.query.get(note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)
    if not _can_user_rate_note_type(note_type, user_id=current_user.id):
        return _api_error("VALIDATION_ERROR", "You can only rate after real usage.", status=403)

    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating"))
    except (TypeError, ValueError):
        return _api_error("VALIDATION_ERROR", "rating must be an integer 1-5.", field="rating")
    if rating < 1 or rating > 5:
        return _api_error("VALIDATION_ERROR", "rating must be between 1 and 5.", field="rating")
    comment = (payload.get("comment") or "").strip() or None

    review = NoteTypeReview.query.filter_by(note_type_id=note_type.id, user_id=current_user.id).first()
    if review is None:
        review = NoteTypeReview(note_type_id=note_type.id, user_id=current_user.id, rating=rating, comment=comment)
        db.session.add(review)
    else:
        review.rating = rating
        review.comment = comment

    _recompute_note_type_market_stats(note_type)
    _audit("market.note_type.rate", {"note_type_id": note_type.id, "rating": rating})
    db.session.commit()
    return jsonify(
        {
            "note_type_id": note_type.id,
            "rating_avg": note_type.rating_avg,
            "rating_count": note_type.rating_count,
            "my_rating": rating,
        }
    )


@flashcards_bp.route("/api/shared/note-types/recommendations", methods=["GET"])
@login_required
def shared_note_type_recommendations():
    visible_items = [item for item in NoteType.query.all() if _is_note_type_visible_for_shared(item)]
    interests_categories, interests_tags = _collect_user_market_interests(current_user.id)
    cold_start = not interests_categories and not interests_tags

    scored: list[tuple[float, NoteType]] = []
    for item in visible_items:
        if item.user_id == current_user.id:
            continue
        score = _score_market_item(
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
        _serialize_note_type_marketplace_card(item)
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:12]
    ]

    trending_cutoff = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
    trending_counts_raw = (
        db.session.query(NoteTypeInstall.source_note_type_id, db.func.count(NoteTypeInstall.id))
        .filter(NoteTypeInstall.installed_at >= trending_cutoff)
        .group_by(NoteTypeInstall.source_note_type_id)
        .all()
    )
    trending_counts = {row[0]: int(row[1] or 0) for row in trending_counts_raw}
    trending = sorted(
        visible_items,
        key=lambda item: (trending_counts.get(item.id, 0), int(item.active_usage_count or 0), int(item.install_count or 0)),
        reverse=True,
    )[:12]
    new_and_updated = _sort_note_type_items(visible_items, "recently_updated")[:12]
    return jsonify(
        {
            "recommended_for_you": recommended,
            "top_by_category": _top_items_by_category_note_types(visible_items),
            "trending": [_serialize_note_type_marketplace_card(item) for item in trending],
            "new_and_updated": [_serialize_note_type_marketplace_card(item) for item in new_and_updated],
        }
    )


@flashcards_bp.route("/api/shared/decks", methods=["GET"])
@login_required
def list_shared_decks():
    query_text = (request.args.get("q") or "").strip()
    category = (request.args.get("category") or "").strip()
    tags = {item.lower() for item in _normalize_marketplace_tags(request.args.get("tags"))}
    pricing_mode = (request.args.get("pricing_mode") or request.args.get("pricing") or "").strip().lower()
    sort_key = (request.args.get("sort") or "popular").strip().lower()
    min_price_cents = _parse_query_price_cents("min_price")
    max_price_cents = _parse_query_price_cents("max_price")

    visible_items = [
        item for item in DeckMarketplaceItem.query.order_by(DeckMarketplaceItem.updated_at.desc()).all()
        if _is_deck_item_visible_for_shared(item)
    ]
    filtered = _filter_deck_items(
        visible_items,
        query_text=query_text,
        category=category,
        tags=tags,
        pricing_mode=pricing_mode,
        min_price_cents=min_price_cents,
        max_price_cents=max_price_cents,
    )
    sorted_items = _sort_deck_items(filtered, sort_key)
    installs = DeckInstall.query.filter_by(user_id=current_user.id).all()
    install_map = {row.deck_item_id: row for row in installs}
    payload_items = []
    for item in sorted_items:
        row = _serialize_deck_marketplace_item(item)
        install = install_map.get(item.id)
        row["is_installed"] = install is not None
        row["installed_deck_id"] = install.local_deck_id if install else None
        row["is_owner"] = item.owner_user_id == current_user.id
        payload_items.append(row)
    return jsonify({"items": payload_items})


@flashcards_bp.route("/api/shared/decks", methods=["POST"])
@login_required
def create_shared_deck_item():
    payload = request.get_json(silent=True) or {}
    title = (payload.get("title") or "").strip()
    if not title:
        return _api_error("VALIDATION_ERROR", "title is required.", field="title")

    deck_item = DeckMarketplaceItem(
        owner_user_id=current_user.id,
        title=title,
        description=(payload.get("description") or "").strip(),
        primary_category=(payload.get("primary_category") or "General").strip() or "General",
        tags=_normalize_marketplace_tags(payload.get("tags")),
        preview_text=(payload.get("preview_text") or "").strip() or None,
        sample_cards_count=0,
        pricing_mode="free",
        price_cents=0,
        version="1.0.0",
        publish_status="private",
        is_official=False,
    )
    db.session.add(deck_item)
    validation_error = _apply_deck_marketplace_payload(deck_item, payload)
    if validation_error:
        db.session.rollback()
        return _api_error("VALIDATION_ERROR", validation_error)
    if deck_item.source_deck_id is not None and not Deck.query.get(deck_item.source_deck_id):
        db.session.rollback()
        return _api_error("FIELD_NOT_FOUND", "source_deck_id not found.", field="source_deck_id", status=404)
    bind_error = _bind_deck_item_source_note_type(deck_item, require_source_note_type=True)
    if bind_error:
        db.session.rollback()
        return _api_error("VALIDATION_ERROR", bind_error, field="source_note_type_id")
    _recompute_deck_item_market_stats(deck_item)
    _audit("market.deck_item.create", {"deck_item_id": deck_item.id})
    db.session.commit()
    return jsonify(_serialize_deck_marketplace_item(deck_item)), 201


@flashcards_bp.route("/api/shared/decks/<deck_item_id>", methods=["GET"])
@login_required
def get_shared_deck_item(deck_item_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    _, changed = share_ctrl.sync_deck_item_source_note_type(
        deck_item,
        require_source_note_type=False,
    )
    if changed:
        db.session.commit()

    payload = share_ctrl.build_shared_deck_item_payload(
        deck_item,
        user_id=current_user.id,
        sample_limit=SHARED_DECK_TEST_SAMPLE_LIMIT,
        deck_active_review_threshold=DECK_ACTIVE_REVIEW_THRESHOLD,
    )

    return jsonify(payload)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_deck_template(deck_item_id: str, template_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    bind_error, changed = share_ctrl.sync_deck_item_source_note_type(
        deck_item,
        require_source_note_type=True,
    )
    if bind_error:
        return _api_error("VALIDATION_ERROR", bind_error, status=409)
    if changed:
        db.session.commit()

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        return _api_error("VALIDATION_ERROR", "Deck item has no source note type.", status=409)

    note_type = NoteType.query.get(source_note_type_id)
    if not note_type:
        return _api_error("FIELD_NOT_FOUND", "Note type not found.", status=404)

    template = Template.query.filter_by(id=template_id, note_type_id=note_type.id).first()
    if not template:
        return _api_error("FIELD_NOT_FOUND", "Template not found.", status=404)

    payload = request.get_json(silent=True) or {}
    requested_note_id = (payload.get("note_id") or "").strip() or None
    preview_note = share_ctrl.select_preview_note_for_shared_deck(
        deck_item,
        note_type_id=note_type.id,
        requested_note_id=requested_note_id,
    )

    if preview_note:
        preview_field_values = preview_note.field_values or {}
        preview_media_assets = preview_note.media_assets
        preview_note_key = f"shared-deck-preview:{deck_item.id}:{preview_note.id}"
    else:
        preview_field_values = _build_preview_sample_values(note_type.field_defs)
        preview_media_assets = []
        preview_note_key = f"shared-deck-preview:{deck_item.id}:sample"

    try:
        rendered = render_template_pair(
            template=template,
            field_defs=note_type.field_defs,
            field_values=preview_field_values,
            media_assets=preview_media_assets,
            preview_note_key=preview_note_key,
            allow_inline_script=True,
        )
    except TemplateCompileError as exc:
        return _api_error("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html")

    return jsonify(rendered)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>", methods=["PATCH"])
@login_required
def patch_shared_deck_item(deck_item_id: str):
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)
    if deck_item.owner_user_id != current_user.id and not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Only owner can edit deck item.", status=403)

    payload = request.get_json(silent=True) or {}
    validation_error = _apply_deck_marketplace_payload(deck_item, payload)
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)
    if deck_item.source_deck_id is not None and not Deck.query.get(deck_item.source_deck_id):
        return _api_error("FIELD_NOT_FOUND", "source_deck_id not found.", field="source_deck_id", status=404)
    bind_error = _bind_deck_item_source_note_type(deck_item, require_source_note_type=True)
    if bind_error:
        return _api_error("VALIDATION_ERROR", bind_error, field="source_note_type_id")
    _recompute_deck_item_market_stats(deck_item)
    _audit("market.deck_item.update", {"deck_item_id": deck_item.id})
    db.session.commit()
    return jsonify(_serialize_deck_marketplace_item(deck_item))


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/install", methods=["POST"])
@login_required
def install_shared_deck_item(deck_item_id: str):
    for attempt in range(1, SHARED_DECK_INSTALL_MAX_RETRIES + 1):
        deck_item = DeckMarketplaceItem.query.get(deck_item_id)
        if not deck_item:
            return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

        bind_error, changed = share_ctrl.sync_deck_item_source_note_type(
            deck_item,
            require_source_note_type=True,
        )
        if bind_error:
            return _api_error("VALIDATION_ERROR", bind_error, status=409)

        if changed:
            try:
                db.session.commit()
            except OperationalError as exc:
                db.session.rollback()
                if _is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                    logger.warning(
                        "Deadlock while syncing source note type for shared deck install "
                        "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                        deck_item_id,
                        current_user.id,
                        attempt,
                        SHARED_DECK_INSTALL_MAX_RETRIES,
                    )
                    time.sleep(0.05 * attempt)
                    continue
                raise

        try:
            install_result = share_ctrl.install_shared_deck_item_for_user(
                deck_item,
                user_id=current_user.id,
                publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
            )
        except share_ctrl.ShareControllerError as exc:
            db.session.rollback()
            return _api_error(
                exc.error,
                exc.message,
                status=exc.status,
                field=exc.field,
            )
        except OperationalError as exc:
            db.session.rollback()
            if _is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while installing shared deck "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    current_user.id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if _is_mysql_deadlock(exc):
                return _api_error(
                    "DEADLOCK_RETRY_EXCEEDED",
                    "Database deadlock detected. Please retry the install request.",
                    status=409,
                )
            raise

        if not install_result.get("created"):
            return jsonify(install_result.get("response") or {})

        _audit("market.deck_item.install", install_result.get("audit") or {})
        try:
            db.session.commit()
        except OperationalError as exc:
            db.session.rollback()
            if _is_mysql_deadlock(exc) and attempt < SHARED_DECK_INSTALL_MAX_RETRIES:
                logger.warning(
                    "Deadlock while committing shared deck install "
                    "(deck_item_id=%s, user_id=%s, attempt=%s/%s)",
                    deck_item_id,
                    current_user.id,
                    attempt,
                    SHARED_DECK_INSTALL_MAX_RETRIES,
                )
                time.sleep(0.05 * attempt)
                continue
            if _is_mysql_deadlock(exc):
                return _api_error(
                    "DEADLOCK_RETRY_EXCEEDED",
                    "Database deadlock detected. Please retry the install request.",
                    status=409,
                )
            raise

        return jsonify(install_result.get("response") or {}), 201

    return _api_error(
        "DEADLOCK_RETRY_EXCEEDED",
        "Database deadlock detected. Please retry the install request.",
        status=409,
    )


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/clone/overlay", methods=["POST"])
@login_required
def upsert_shared_deck_clone_overlay(deck_item_id: str):
    install = _get_user_deck_install_for_item(
        user_id=current_user.id,
        deck_item_id=deck_item_id,
    )
    if install is None:
        return _api_error("FIELD_NOT_FOUND", "Installed clone deck not found.", status=404)

    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        return _api_error("VALIDATION_ERROR", "Payload must be an object.")

    counters, validation_error = _upsert_clone_overlay(
        deck_install=install,
        payload=payload,
    )
    if validation_error:
        return _api_error("VALIDATION_ERROR", validation_error)

    _audit(
        "market.deck_item.clone_overlay.upsert",
        {
            "deck_item_id": deck_item_id,
            "deck_install_id": install.id,
            "changes": counters,
        },
    )
    db.session.commit()
    return jsonify(
        {
            "deck_item_id": deck_item_id,
            "deck_install_id": install.id,
            "installed_deck_id": install.local_deck_id,
            "changes": counters,
        }
    )


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/rate", methods=["POST"])
@login_required
def rate_shared_deck_item(deck_item_id: str):
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)
    if not _can_user_rate_deck(deck_item, user_id=current_user.id):
        return _api_error("VALIDATION_ERROR", "You can only rate after real usage.", status=403)

    payload = request.get_json(silent=True) or {}
    try:
        rating = int(payload.get("rating"))
    except (TypeError, ValueError):
        return _api_error("VALIDATION_ERROR", "rating must be an integer 1-5.", field="rating")
    if rating < 1 or rating > 5:
        return _api_error("VALIDATION_ERROR", "rating must be between 1 and 5.", field="rating")
    comment = (payload.get("comment") or "").strip() or None

    review = DeckReview.query.filter_by(deck_item_id=deck_item.id, user_id=current_user.id).first()
    if review is None:
        review = DeckReview(deck_item_id=deck_item.id, user_id=current_user.id, rating=rating, comment=comment)
        db.session.add(review)
    else:
        review.rating = rating
        review.comment = comment

    _recompute_deck_item_market_stats(deck_item)
    _audit("market.deck_item.rate", {"deck_item_id": deck_item.id, "rating": rating})
    db.session.commit()
    return jsonify(
        {
            "deck_item_id": deck_item.id,
            "rating_avg": deck_item.rating_avg,
            "rating_count": deck_item.rating_count,
            "my_rating": rating,
        }
    )


@flashcards_bp.route("/api/shared/decks/recommendations", methods=["GET"])
@login_required
def shared_deck_recommendations():
    visible_items = [item for item in DeckMarketplaceItem.query.all() if _is_deck_item_visible_for_shared(item)]
    interests_categories, interests_tags = _collect_user_market_interests(current_user.id)
    cold_start = not interests_categories and not interests_tags

    scored: list[tuple[float, DeckMarketplaceItem]] = []
    for item in visible_items:
        if item.owner_user_id == current_user.id:
            continue
        score = _score_market_item(
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
        _serialize_deck_marketplace_item(item)
        for _, item in sorted(scored, key=lambda row: row[0], reverse=True)[:12]
    ]

    trending_cutoff = datetime.utcnow() - timedelta(days=TRENDING_WINDOW_DAYS)
    trending_counts_raw = (
        db.session.query(DeckInstall.deck_item_id, db.func.count(DeckInstall.id))
        .filter(DeckInstall.installed_at >= trending_cutoff)
        .group_by(DeckInstall.deck_item_id)
        .all()
    )
    trending_counts = {row[0]: int(row[1] or 0) for row in trending_counts_raw}
    trending = sorted(
        visible_items,
        key=lambda item: (trending_counts.get(item.id, 0), int(item.active_usage_count or 0), int(item.install_count or 0)),
        reverse=True,
    )[:12]
    new_and_updated = _sort_deck_items(visible_items, "recently_updated")[:12]
    return jsonify(
        {
            "recommended_for_you": recommended,
            "top_by_category": _top_items_by_category_decks(visible_items),
            "trending": [_serialize_deck_marketplace_item(item) for item in trending],
            "new_and_updated": [_serialize_deck_marketplace_item(item) for item in new_and_updated],
        }
    )


@flashcards_bp.route("/api/shared/seed-defaults", methods=["POST"])
@login_required
def seed_marketplace_defaults():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)

    import os
    from models.user import User
    admin_email = os.environ.get("ADMIN_EMAIL", "chungtrinh2k2@gmail.com")
    admin_user_name = os.environ.get("ADMIN_USERNAME") or os.environ.get("ADMIN_USER", "chungtrinh2k2")
    admin_password = os.environ.get("ADMIN_PASSWORD", "chungtrinh1904")

    system_admin = User.query.filter_by(email=admin_email).first()
    if not system_admin:
        system_admin = User(
            email=admin_email,
            username=admin_user_name,
            is_admin=True,
        )
        system_admin.set_password(admin_password)
        db.session.add(system_admin)
        db.session.commit()
    elif not system_admin.is_admin:
        system_admin.is_admin = True
        db.session.commit()

    admin_id = system_admin.id

    note_type, _template = ensure_legacy_note_type(db.session, admin_id)
    note_type.description = note_type.description or "Official default Japanese vocabulary note type."
    note_type.primary_category = note_type.primary_category or "Japanese"
    note_type.tags = note_type.tags or ["official", "default", "japanese"]
    note_type.preview_text = note_type.preview_text or "Word / Reading / Meaning default layout."
    note_type.pricing_mode = "free"
    note_type.price_cents = 0
    note_type.version = note_type.version or "1.0.0"
    note_type.is_official = True
    note_type.publish_status = "published"
    note_type.published_at = note_type.published_at or datetime.utcnow()
    _recompute_note_type_market_stats(note_type)

    deck_item = DeckMarketplaceItem.query.filter_by(
        owner_user_id=admin_id,
        is_official=True,
        title="Official Starter Deck",
    ).first()
    source_deck = Deck.query.order_by(Deck.id.asc()).first()
    if source_deck is None:
        return _api_error(
            "VALIDATION_ERROR",
            "Cannot seed official shared deck without at least one source deck.",
            status=409,
        )
    # Stamp ownership on the source deck so it is recognised as admin-owned
    if source_deck.owner_user_id is None:
        source_deck.owner_user_id = admin_id
    if deck_item is None:
        deck_item = DeckMarketplaceItem(
            owner_user_id=admin_id,
            source_deck_id=source_deck.id,
            source_note_type_id=note_type.id,
            title="Official Starter Deck",
            description="Official default deck for new users.",
            primary_category="Japanese",
            tags=["official", "default", "starter"],
            preview_text="Starter deck with basic Japanese vocabulary.",
            sample_cards_count=20,
            pricing_mode="free",
            price_cents=0,
            version="1.0.0",
            publish_status="published",
            is_official=True,
            published_at=datetime.utcnow(),
        )
        db.session.add(deck_item)
    else:
        deck_item.source_deck_id = source_deck.id
        deck_item.source_note_type_id = note_type.id
        deck_item.pricing_mode = "free"
        deck_item.price_cents = 0
        deck_item.publish_status = "published"
        deck_item.is_official = True
        deck_item.published_at = deck_item.published_at or datetime.utcnow()
    _recompute_deck_item_market_stats(deck_item)

    _audit("market.seed_defaults", {"note_type_id": note_type.id, "deck_item_id": deck_item.id})
    db.session.commit()
    return jsonify({"note_type_id": note_type.id, "deck_item_id": deck_item.id})
