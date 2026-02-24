"""Flashcard v2 API + minimal management/study pages."""

from __future__ import annotations

import hashlib
import logging
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

from app.services.anki_scheduler import (
    CardState,
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
from app.services.flashcard_renderer import (
    PREVIEW_MEDIA_AUDIO_TOKEN,
    PREVIEW_MEDIA_DIAGRAM_TOKEN,
    PREVIEW_MEDIA_IMAGE_TOKEN,
    TemplateCompileError,
    is_field_empty,
    render_template_pair,
    sanitize_richtext,
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
from models.vocabulary_deck import VocabularyDeck
from models.vocabulary_entry import VocabularyEntry
from models.vocabulary_progress import VocabularyProgress

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
    if not user_obj:
        return {"id": None, "username": "Unknown"}
    return {
        "id": user_obj.id,
        "username": user_obj.username,
    }


def _serialize_field(field: FieldDef) -> dict[str, Any]:
    return {
        "id": field.id,
        "note_type_id": field.note_type_id,
        "name": field.name,
        "field_type": field.field_type,
        "position": field.position,
        "required": bool(field.required),
    }


def _serialize_template(template: Template) -> dict[str, Any]:
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


def _serialize_note_type(note_type: NoteType) -> dict[str, Any]:
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
        "price_cents": int(note_type.price_cents or 0),
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
        "author": _serialize_author(note_type.owner),
        "created_at": note_type.created_at.isoformat() if note_type.created_at else None,
        "updated_at": note_type.updated_at.isoformat() if note_type.updated_at else None,
        "field_defs": [_serialize_field(field) for field in sorted(note_type.field_defs, key=lambda item: item.position)],
        "templates": [
            _serialize_template(template)
            for template in sorted(note_type.templates, key=lambda item: item.position)
        ],
    }


def _clean_field_value(field_def: FieldDef, raw_value: Any) -> Any:
    if field_def.field_type == "richtext":
        return sanitize_richtext("" if raw_value is None else str(raw_value))
    if field_def.field_type in {"image", "audio", "diagram"}:
        if raw_value is None:
            return ""
        candidate = str(raw_value).strip()
        if candidate.startswith(MEDIA_ALLOWED_PREFIX):
            return candidate
        if MediaAsset.query.get(candidate):
            return candidate
        return ""
    return "" if raw_value is None else str(raw_value).strip()


def _validate_note_payload(note_type: NoteType, payload: dict[str, Any], *, partial: bool) -> tuple[dict[str, Any], str | None]:
    field_map = {field.name: field for field in note_type.field_defs}
    field_values = payload.get("field_values")
    if field_values is None:
        field_values = {}
    if not isinstance(field_values, dict):
        return {}, "field_values must be an object."

    unknown = [key for key in field_values.keys() if key not in field_map]
    if unknown:
        return {}, f"Unknown fields: {', '.join(unknown)}"

    cleaned: dict[str, Any] = {}
    for name, field_def in field_map.items():
        if name in field_values:
            cleaned[name] = _clean_field_value(field_def, field_values.get(name))

    if not partial:
        for name, field_def in field_map.items():
            if name not in cleaned:
                cleaned[name] = ""
            if field_def.required and is_field_empty(cleaned[name]):
                return {}, f"Field '{name}' is required."
    return cleaned, None


def _normalize_tags(raw_tags: Any) -> list[str]:
    if raw_tags is None:
        return []
    if isinstance(raw_tags, list):
        tags = [str(item).strip() for item in raw_tags if str(item).strip()]
        return tags
    if isinstance(raw_tags, str):
        return [item.strip() for item in raw_tags.split(",") if item.strip()]
    return []


def _normalize_marketplace_tags(raw_tags: Any) -> list[str]:
    normalized = _normalize_tags(raw_tags)
    dedup: list[str] = []
    seen: set[str] = set()
    for item in normalized:
        lowered = item.lower()
        if lowered in seen:
            continue
        seen.add(lowered)
        dedup.append(item)
    return dedup


def _parse_price_cents(raw_price: Any) -> int | None:
    if raw_price in (None, ""):
        return None
    if isinstance(raw_price, int):
        return raw_price
    if isinstance(raw_price, float):
        return int(round(raw_price * 100))
    text = str(raw_price).strip()
    if not text:
        return None
    if "." in text:
        try:
            return int(round(float(text) * 100))
        except ValueError:
            return None
    try:
        return int(text)
    except ValueError:
        return None


def _normalize_pricing(payload: dict[str, Any], *, current_mode: str, current_price_cents: int) -> tuple[str, int, str | None]:
    mode_raw = payload.get("pricing_mode", payload.get("pricing"))
    mode = current_mode
    if mode_raw is not None:
        mode_candidate = str(mode_raw).strip().lower()
        if mode_candidate not in {"free", "paid"}:
            return mode, current_price_cents, "pricing_mode must be 'free' or 'paid'."
        mode = mode_candidate

    price_cents = current_price_cents
    if "price_cents" in payload:
        parsed_price = _parse_price_cents(payload.get("price_cents"))
        if parsed_price is None:
            return mode, current_price_cents, "price_cents is invalid."
        price_cents = parsed_price
    elif "price" in payload:
        parsed_price = _parse_price_cents(payload.get("price"))
        if parsed_price is None:
            return mode, current_price_cents, "price is invalid."
        price_cents = parsed_price

    if mode == "free":
        return mode, 0, None
    if price_cents <= 0:
        return mode, price_cents, "Paid items must have price > 0."
    return mode, price_cents, None


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


def _build_preview_values_from_vocabulary_entry(
    entry: VocabularyEntry,
    field_defs: list[FieldDef],
) -> dict[str, Any]:
    # Keep compatibility with both legacy (Word/Reading/...) and flama (word/reading/...) field names.
    raw_values = {
        "Word": entry.word or "",
        "word": entry.word or "",
        "hanviet": entry.hanviet or "",
        "Reading": entry.reading or "",
        "reading": entry.reading or "",
        "Translation_VI": entry.translation_vi or "",
        "translation_vi": entry.translation_vi or "",
        "Meaning_JP": entry.meaning_jp or "",
        "meaning_jp": entry.meaning_jp or "",
        "Meaning_VI": entry.meaning_vi or "",
        "meaning_vi": entry.meaning_vi or "",
        "Usage_JP": entry.usage_jp or "",
        "usage_jp": entry.usage_jp or "",
        "Usage_VI": entry.usage_vi or "",
        "usage_vi": entry.usage_vi or "",
        "Example_JP": entry.example_jp or "",
        "example_jp": entry.example_jp or "",
        "Example_VI": entry.example_vi or "",
        "example_vi": entry.example_vi or "",
        "Additional_Note_JP": entry.additional_note_jp or "",
        "additional_note_jp": entry.additional_note_jp or "",
        "Additional_Note_VI": entry.additional_note_vi or "",
        "additional_note_vi": entry.additional_note_vi or "",
        "image": entry.image or "",
        "Diagram": entry.diagram or "",
        "diagram": entry.diagram or "",
        "Word_Audio": entry.word_audio or "",
        "word_audio": entry.word_audio or "",
        "Example_Audio": entry.example_audio or "",
        "example_audio": entry.example_audio or "",
    }

    preview_values: dict[str, Any] = {}
    for field_def in field_defs:
        raw_value = raw_values.get(field_def.name, "")
        if field_def.field_type == "image":
            preview_values[field_def.name] = PREVIEW_MEDIA_IMAGE_TOKEN if raw_value else ""
        elif field_def.field_type == "audio":
            preview_values[field_def.name] = PREVIEW_MEDIA_AUDIO_TOKEN if raw_value else ""
        elif field_def.field_type == "diagram":
            preview_values[field_def.name] = PREVIEW_MEDIA_DIAGRAM_TOKEN if raw_value else ""
        else:
            preview_values[field_def.name] = raw_value

    for key, value in raw_values.items():
        if key not in preview_values:
            preview_values[key] = value
    return preview_values


def _validate_note_type_publish_requirements(note_type: NoteType) -> str | None:
    if not (note_type.name or "").strip():
        return "Title is required for publish."
    if not (note_type.description or "").strip():
        return "Description is required for publish."
    if not (note_type.primary_category or "").strip():
        return "primary_category is required for publish."
    preview_text = (note_type.preview_text or "").strip()
    preview_image = (note_type.preview_image_url or "").strip()
    if not preview_text and not preview_image:
        return "Preview text or preview image is required for publish."
    if not (note_type.version or "").strip():
        return "Version is required for publish."
    if note_type.pricing_mode == "paid" and int(note_type.price_cents or 0) <= 0:
        return "Paid note type must have a positive price."
    if not note_type.field_defs:
        return "At least one field is required for publish."
    if not note_type.templates:
        return "At least one card template is required for publish."
    return None


def _apply_note_type_marketplace_payload(note_type: NoteType, payload: dict[str, Any]) -> str | None:
    if "title" in payload or "name" in payload:
        new_name = (payload.get("title") or payload.get("name") or "").strip()
        if not new_name:
            return "Title is required."
        existing = NoteType.query.filter(
            NoteType.user_id == note_type.user_id,
            NoteType.name == new_name,
            NoteType.id != note_type.id,
        ).first()
        if existing:
            return "Another note type already uses this title."
        note_type.name = new_name

    if "description" in payload:
        note_type.description = (payload.get("description") or "").strip() or None
    if "primary_category" in payload:
        note_type.primary_category = (payload.get("primary_category") or "").strip() or None
    if "tags" in payload:
        note_type.tags = _normalize_marketplace_tags(payload.get("tags"))
    if "preview_text" in payload:
        note_type.preview_text = (payload.get("preview_text") or "").strip() or None
    if "preview_image_url" in payload:
        note_type.preview_image_url = (payload.get("preview_image_url") or "").strip() or None
    if "version" in payload:
        note_type.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        note_type.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_cents, pricing_error = _normalize_pricing(
        payload,
        current_mode=str(note_type.pricing_mode or "free"),
        current_price_cents=int(note_type.price_cents or 0),
    )
    if pricing_error:
        return pricing_error
    note_type.pricing_mode = pricing_mode
    note_type.price_cents = price_cents

    if "is_official" in payload:
        if not is_admin_user(current_user):
            return "Only admin can set official flag."
        note_type.is_official = bool(payload.get("is_official"))

    if "publish_status" in payload:
        candidate_status = str(payload.get("publish_status") or "").strip().lower()
        if candidate_status not in {"private", "published", "unlisted", "archived"}:
            return "publish_status is invalid."
        if candidate_status in PUBLISH_STATUSES_VISIBLE:
            err = _validate_note_type_publish_requirements(note_type)
            if err:
                return err
            if note_type.publish_status not in PUBLISH_STATUSES_VISIBLE:
                note_type.published_at = datetime.utcnow()
            note_type.archived_at = None
        elif candidate_status == "archived":
            note_type.archived_at = datetime.utcnow()
        note_type.publish_status = candidate_status

    return None


def _make_unique_note_type_name(user_id: int, base_name: str) -> str:
    candidate = base_name.strip() or "Installed NoteType"
    if not NoteType.query.filter_by(user_id=user_id, name=candidate).first():
        return candidate
    counter = 2
    while True:
        candidate_with_counter = f"{candidate} ({counter})"
        if not NoteType.query.filter_by(user_id=user_id, name=candidate_with_counter).first():
            return candidate_with_counter
        counter += 1


def _clone_note_type_for_user(source_note_type: NoteType, user_id: int) -> NoteType:
    clone = NoteType(
        user_id=user_id,
        name=_make_unique_note_type_name(user_id, source_note_type.name),
        description=source_note_type.description,
        primary_category=source_note_type.primary_category,
        tags=list(source_note_type.tags or []),
        preview_text=source_note_type.preview_text,
        preview_image_url=source_note_type.preview_image_url,
        pricing_mode="free",
        price_cents=0,
        version=source_note_type.version or "1.0.0",
        changelog=source_note_type.changelog,
        publish_status="private",
        is_official=False,
        install_count=0,
        active_usage_count=0,
        rating_avg=0.0,
        rating_count=0,
    )
    db.session.add(clone)
    db.session.flush()

    for field_def in sorted(source_note_type.field_defs, key=lambda item: item.position):
        db.session.add(
            FieldDef(
                note_type_id=clone.id,
                name=field_def.name,
                field_type=field_def.field_type,
                position=field_def.position,
                required=bool(field_def.required),
            )
        )

    for template in sorted(source_note_type.templates, key=lambda item: item.position):
        db.session.add(
            Template(
                note_type_id=clone.id,
                name=template.name,
                front_html=template.front_html,
                back_html=template.back_html,
                shared_css=template.shared_css,
                position=template.position,
                is_default=bool(template.is_default),
            )
        )

    return clone


def _touch_note_type_install_usage(*, user_id: int, installed_note_type_id: str, activity_at: datetime | None = None) -> None:
    install = NoteTypeInstall.query.filter_by(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
    ).first()
    if not install:
        return
    now = activity_at or datetime.utcnow()
    if install.first_use_at is None:
        install.first_use_at = now
    install.last_activity_at = now


def _note_type_reps_for_user(*, user_id: int, installed_note_type_id: str) -> int:
    result = (
        db.session.query(db.func.coalesce(db.func.sum(VocabularyProgress.reps), 0))
        .select_from(VocabularyProgress)
        .join(Card, VocabularyProgress.new_card_id == Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(
            VocabularyProgress.user_id == user_id,
            Note.note_type_id == installed_note_type_id,
        )
        .scalar()
    )
    return int(result or 0)


def _is_note_type_install_active(install: NoteTypeInstall, *, now: datetime) -> bool:
    if not install.installed_note_type_id:
        return False
    note_count = Note.query.filter_by(
        user_id=install.user_id,
        note_type_id=install.installed_note_type_id,
    ).count()
    review_reps = _note_type_reps_for_user(
        user_id=install.user_id,
        installed_note_type_id=install.installed_note_type_id,
    )
    first_use = install.first_use_at
    used_days = bool(first_use and now - first_use >= timedelta(days=NOTE_TYPE_ACTIVE_DAYS_THRESHOLD))
    return (
        note_count >= NOTE_TYPE_ACTIVE_NOTE_THRESHOLD
        or review_reps >= NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD
        or used_days
    )


def _recompute_note_type_market_stats(note_type: NoteType) -> None:
    now = datetime.utcnow()
    installs = NoteTypeInstall.query.filter_by(source_note_type_id=note_type.id).all()
    note_type.install_count = len(installs)
    note_type.active_usage_count = sum(1 for install in installs if _is_note_type_install_active(install, now=now))

    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(NoteTypeReview.rating), 0.0),
            db.func.count(NoteTypeReview.id),
        )
        .filter(NoteTypeReview.note_type_id == note_type.id)
        .first()
    )
    note_type.rating_avg = float(rating_avg or 0.0)
    note_type.rating_count = int(rating_count or 0)


def _can_user_rate_note_type(note_type: NoteType, *, user_id: int) -> bool:
    if note_type.user_id == user_id:
        return False
    install = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id,
        user_id=user_id,
    ).first()
    if not install:
        return False
    return _is_note_type_install_active(install, now=datetime.utcnow())


def _serialize_note_type_marketplace_card(note_type: NoteType) -> dict[str, Any]:
    payload = _serialize_note_type(note_type)
    payload["price_display"] = "Free" if note_type.pricing_mode == "free" else f"${(note_type.price_cents or 0) / 100:.2f}"
    return payload


def _serialize_deck_marketplace_item(deck_item: DeckMarketplaceItem) -> dict[str, Any]:
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
        "price_cents": int(deck_item.price_cents or 0),
        "price_display": "Free" if deck_item.pricing_mode == "free" else f"${(deck_item.price_cents or 0) / 100:.2f}",
        "version": deck_item.version,
        "changelog": deck_item.changelog,
        "publish_status": deck_item.publish_status,
        "is_official": bool(deck_item.is_official),
        "install_count": int(deck_item.install_count or 0),
        "active_usage_count": int(deck_item.active_usage_count or 0),
        "rating_avg": float(deck_item.rating_avg or 0.0),
        "rating_count": int(deck_item.rating_count or 0),
        "author": _serialize_author(deck_item.owner),
        "published_at": deck_item.published_at.isoformat() if deck_item.published_at else None,
        "archived_at": deck_item.archived_at.isoformat() if deck_item.archived_at else None,
        "updated_at": deck_item.updated_at.isoformat() if deck_item.updated_at else None,
        "created_at": deck_item.created_at.isoformat() if deck_item.created_at else None,
    }


def _validate_deck_publish_requirements(deck_item: DeckMarketplaceItem) -> str | None:
    if not (deck_item.title or "").strip():
        return "Title is required for publish."
    if not (deck_item.description or "").strip():
        return "Description is required for publish."
    if not (deck_item.primary_category or "").strip():
        return "primary_category is required for publish."
    if not (deck_item.preview_text or "").strip() and int(deck_item.sample_cards_count or 0) <= 0:
        return "Preview text or sample_cards_count > 0 is required for publish."
    if not (deck_item.version or "").strip():
        return "Version is required for publish."
    if deck_item.pricing_mode == "paid" and int(deck_item.price_cents or 0) <= 0:
        return "Paid deck must have a positive price."
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        return "source_note_type_id is required for publish."
    source_note_type = NoteType.query.get(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found for publish."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type that has at least one template."
    return None


def _apply_deck_marketplace_payload(deck_item: DeckMarketplaceItem, payload: dict[str, Any]) -> str | None:
    if "title" in payload:
        title = (payload.get("title") or "").strip()
        if not title:
            return "title is required."
        deck_item.title = title
    if "description" in payload:
        deck_item.description = (payload.get("description") or "").strip()
    if "primary_category" in payload:
        category = (payload.get("primary_category") or "").strip()
        if not category:
            return "primary_category is required."
        deck_item.primary_category = category
    if "tags" in payload:
        deck_item.tags = _normalize_marketplace_tags(payload.get("tags"))
    if "preview_text" in payload:
        deck_item.preview_text = (payload.get("preview_text") or "").strip() or None
    if "sample_cards_count" in payload:
        try:
            deck_item.sample_cards_count = max(0, int(payload.get("sample_cards_count") or 0))
        except (TypeError, ValueError):
            return "sample_cards_count must be an integer."
    if "source_deck_id" in payload:
        source_deck_id_raw = payload.get("source_deck_id")
        if source_deck_id_raw in (None, ""):
            deck_item.source_deck_id = None
        else:
            try:
                deck_item.source_deck_id = int(source_deck_id_raw)
            except (TypeError, ValueError):
                return "source_deck_id must be an integer."
    if "source_note_type_id" in payload:
        deck_item.source_note_type_id = (payload.get("source_note_type_id") or "").strip() or None
    if "version" in payload:
        deck_item.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        deck_item.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_cents, pricing_error = _normalize_pricing(
        payload,
        current_mode=str(deck_item.pricing_mode or "free"),
        current_price_cents=int(deck_item.price_cents or 0),
    )
    if pricing_error:
        return pricing_error
    deck_item.pricing_mode = pricing_mode
    deck_item.price_cents = price_cents

    if "is_official" in payload:
        if not is_admin_user(current_user):
            return "Only admin can set official flag."
        deck_item.is_official = bool(payload.get("is_official"))

    if "publish_status" in payload:
        candidate_status = str(payload.get("publish_status") or "").strip().lower()
        if candidate_status not in {"private", "published", "unlisted", "archived"}:
            return "publish_status is invalid."
        if candidate_status in PUBLISH_STATUSES_VISIBLE:
            err = _validate_deck_publish_requirements(deck_item)
            if err:
                return err
            if deck_item.publish_status not in PUBLISH_STATUSES_VISIBLE:
                deck_item.published_at = datetime.utcnow()
            deck_item.archived_at = None
        elif candidate_status == "archived":
            deck_item.archived_at = datetime.utcnow()
        deck_item.publish_status = candidate_status

    return None


def _resolve_single_note_type_for_deck(
    *,
    deck_id: int,
    owner_user_id: int | None = None,
) -> tuple[str | None, str | None]:
    query = db.session.query(Note.note_type_id).filter(Note.deck_id == deck_id)
    if owner_user_id is not None:
        query = query.filter(Note.user_id == owner_user_id)

    note_type_ids = sorted({row[0] for row in query.all() if row[0]})
    if not note_type_ids:
        has_entries = (
            db.session.query(VocabularyEntry.id)
            .filter(VocabularyEntry.deck_id == deck_id)
            .first()
            is not None
        )
        if has_entries and owner_user_id is not None:
            fallback_note_type, _fallback_template = ensure_legacy_note_type(db.session, owner_user_id)
            return fallback_note_type.id, None
        return None, "Deck has no notes, cannot infer source_note_type_id."
    if len(note_type_ids) > 1:
        return None, "All notes in one deck must use the same template (note type)."

    resolved_note_type_id = note_type_ids[0]
    resolved_note_type = NoteType.query.get(resolved_note_type_id)
    if not resolved_note_type:
        return None, "Deck source note type not found."
    if not resolved_note_type.templates:
        return None, "Deck source note type has no templates."
    return resolved_note_type.id, None


def _bind_deck_item_source_note_type(
    deck_item: DeckMarketplaceItem,
    *,
    require_source_note_type: bool,
) -> str | None:
    if deck_item.source_deck_id is not None:
        inferred_note_type_id, infer_error = _resolve_single_note_type_for_deck(
            deck_id=deck_item.source_deck_id,
            owner_user_id=deck_item.owner_user_id,
        )
        if infer_error and require_source_note_type and not (deck_item.source_note_type_id or "").strip():
            return infer_error
        if inferred_note_type_id:
            if deck_item.source_note_type_id and deck_item.source_note_type_id != inferred_note_type_id:
                return "source_note_type_id does not match notes inside source_deck_id."
            deck_item.source_note_type_id = inferred_note_type_id

    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if not source_note_type_id:
        if require_source_note_type:
            return "source_note_type_id is required."
        return None

    source_note_type = NoteType.query.get(source_note_type_id)
    if not source_note_type:
        return "source_note_type_id not found."
    if not source_note_type.templates:
        return "source_note_type_id must reference a note type with at least one template."
    return None


def _validate_note_type_consistency_for_deck(
    *,
    deck_id: int | None,
    note_type_id: str,
    user_id: int,
    exclude_note_id: str | None = None,
) -> str | None:
    if deck_id is None:
        return None

    query = db.session.query(Note.note_type_id).filter(
        Note.deck_id == deck_id,
        Note.user_id == user_id,
    )
    if exclude_note_id:
        query = query.filter(Note.id != exclude_note_id)

    existing_note_type_ids = {row[0] for row in query.distinct().all() if row[0]}
    if not existing_note_type_ids:
        return None
    if existing_note_type_ids == {note_type_id}:
        return None
    return "All notes in one deck must use the same template (note type)."


def _next_deck_position(parent_deck_id: int | None) -> int:
    query = db.session.query(db.func.max(VocabularyDeck.position))
    if parent_deck_id is None:
        max_pos = query.filter(VocabularyDeck.parent_id.is_(None)).scalar()
    else:
        max_pos = query.filter(VocabularyDeck.parent_id == parent_deck_id).scalar()
    return int(max_pos or 0) + 1


def _clone_deck_subtree(
    *,
    source_deck_id: int,
    parent_id: int | None,
    owner_user_id: int | None = None,
    root_suffix: str | None = None,
) -> VocabularyDeck:
    source_deck = VocabularyDeck.query.get(source_deck_id)
    if not source_deck:
        raise ValueError(f"Deck not found: {source_deck_id}")

    cloned_deck = VocabularyDeck(
        parent_id=parent_id,
        owner_user_id=owner_user_id,
        name=source_deck.name,
        description=source_deck.description,
        position=_next_deck_position(parent_id),
    )
    db.session.add(cloned_deck)
    db.session.flush()

    source_entries = VocabularyEntry.query.filter_by(deck_id=source_deck.id).all()
    for entry in source_entries:
        db.session.add(
            VocabularyEntry(
                lesson_id=None,
                deck_id=cloned_deck.id,
                word=entry.word,
                hanviet=entry.hanviet,
                reading=entry.reading,
                translation_vi=entry.translation_vi,
                meaning_jp=entry.meaning_jp,
                meaning_vi=entry.meaning_vi,
                usage_jp=entry.usage_jp,
                usage_vi=entry.usage_vi,
                example_jp=entry.example_jp,
                example_vi=entry.example_vi,
                additional_note_jp=entry.additional_note_jp,
                additional_note_vi=entry.additional_note_vi,
                image=entry.image,
                diagram=entry.diagram,
                word_audio=entry.word_audio,
                example_audio=entry.example_audio,
            )
        )

    child_decks = (
        VocabularyDeck.query.filter_by(parent_id=source_deck.id)
        .order_by(VocabularyDeck.position.asc(), VocabularyDeck.id.asc())
        .all()
    )
    for child in child_decks:
        _clone_deck_subtree(
            source_deck_id=child.id,
            parent_id=cloned_deck.id,
            owner_user_id=owner_user_id,
        )

    return cloned_deck


def _touch_deck_install_usage(*, user_id: int, local_deck_id: int, activity_at: datetime | None = None) -> None:
    install = DeckInstall.query.filter_by(user_id=user_id, local_deck_id=local_deck_id).first()
    if not install:
        return
    now = activity_at or datetime.utcnow()
    if install.first_use_at is None:
        install.first_use_at = now
    install.last_activity_at = now


def _deck_reps_for_user(*, user_id: int, local_deck_id: int) -> int:
    legacy_reps = (
        db.session.query(db.func.coalesce(db.func.sum(VocabularyProgress.reps), 0))
        .select_from(VocabularyProgress)
        .join(VocabularyEntry, VocabularyProgress.entry_id == VocabularyEntry.id)
        .filter(
            VocabularyProgress.user_id == user_id,
            VocabularyEntry.deck_id == local_deck_id,
        )
        .scalar()
    ) or 0

    flashcard_reps = (
        db.session.query(db.func.coalesce(db.func.sum(VocabularyProgress.reps), 0))
        .select_from(VocabularyProgress)
        .join(Card, VocabularyProgress.new_card_id == Card.id)
        .join(Note, Card.note_id == Note.id)
        .filter(
            VocabularyProgress.user_id == user_id,
            Note.deck_id == local_deck_id,
        )
        .scalar()
    ) or 0
    return int(legacy_reps or 0) + int(flashcard_reps or 0)


def _is_deck_install_active(install: DeckInstall) -> bool:
    if not install.local_deck_id:
        return False
    reps = _deck_reps_for_user(user_id=install.user_id, local_deck_id=install.local_deck_id)
    return reps >= DECK_ACTIVE_REVIEW_THRESHOLD


def _recompute_deck_item_market_stats(deck_item: DeckMarketplaceItem) -> None:
    installs = DeckInstall.query.filter_by(deck_item_id=deck_item.id).all()
    deck_item.install_count = len(installs)
    deck_item.active_usage_count = sum(1 for install in installs if _is_deck_install_active(install))

    rating_avg, rating_count = (
        db.session.query(
            db.func.coalesce(db.func.avg(DeckReview.rating), 0.0),
            db.func.count(DeckReview.id),
        )
        .filter(DeckReview.deck_item_id == deck_item.id)
        .first()
    )
    deck_item.rating_avg = float(rating_avg or 0.0)
    deck_item.rating_count = int(rating_count or 0)


def _can_user_rate_deck(deck_item: DeckMarketplaceItem, *, user_id: int) -> bool:
    if deck_item.owner_user_id == user_id:
        return False
    install = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=user_id).first()
    if not install:
        return False
    return _is_deck_install_active(install)


def _is_note_type_visible_for_shared(note_type: NoteType) -> bool:
    return str(note_type.publish_status or "").strip().lower() == "published"


def _is_deck_item_visible_for_shared(deck_item: DeckMarketplaceItem) -> bool:
    return str(deck_item.publish_status or "").strip().lower() == "published"


def _item_matches_search(query_text: str, *values: str | None) -> bool:
    if not query_text:
        return True
    lowered = query_text.lower()
    for value in values:
        if value and lowered in value.lower():
            return True
    return False


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
    filtered: list[NoteType] = []
    for note_type in note_types:
        if not _item_matches_search(query_text, note_type.name, note_type.description):
            continue
        if category and (note_type.primary_category or "").strip().lower() != category.lower():
            continue
        item_tags = {tag.lower() for tag in (note_type.tags or [])}
        if tags and not tags.intersection(item_tags):
            continue
        if pricing_mode in {"free", "paid"} and note_type.pricing_mode != pricing_mode:
            continue
        price_value = int(note_type.price_cents or 0)
        if min_price_cents is not None and price_value < min_price_cents:
            continue
        if max_price_cents is not None and price_value > max_price_cents:
            continue
        filtered.append(note_type)
    return filtered


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
    filtered: list[DeckMarketplaceItem] = []
    for deck_item in deck_items:
        if not _item_matches_search(query_text, deck_item.title, deck_item.description):
            continue
        if category and (deck_item.primary_category or "").strip().lower() != category.lower():
            continue
        item_tags = {tag.lower() for tag in (deck_item.tags or [])}
        if tags and not tags.intersection(item_tags):
            continue
        if pricing_mode in {"free", "paid"} and deck_item.pricing_mode != pricing_mode:
            continue
        price_value = int(deck_item.price_cents or 0)
        if min_price_cents is not None and price_value < min_price_cents:
            continue
        if max_price_cents is not None and price_value > max_price_cents:
            continue
        filtered.append(deck_item)
    return filtered


def _sort_note_type_items(items: list[NoteType], sort_key: str) -> list[NoteType]:
    key = (sort_key or "popular").strip().lower()
    if key == "top_rated":
        return sorted(
            items,
            key=lambda item: (float(item.rating_avg or 0.0), int(item.rating_count or 0), int(item.active_usage_count or 0)),
            reverse=True,
        )
    if key == "newest":
        return sorted(items, key=lambda item: (item.created_at or datetime.min), reverse=True)
    if key == "recently_updated":
        return sorted(items, key=lambda item: (item.updated_at or datetime.min), reverse=True)
    return sorted(
        items,
        key=lambda item: (int(item.active_usage_count or 0), int(item.install_count or 0), float(item.rating_avg or 0.0)),
        reverse=True,
    )


def _sort_deck_items(items: list[DeckMarketplaceItem], sort_key: str) -> list[DeckMarketplaceItem]:
    key = (sort_key or "popular").strip().lower()
    if key == "top_rated":
        return sorted(
            items,
            key=lambda item: (float(item.rating_avg or 0.0), int(item.rating_count or 0), int(item.active_usage_count or 0)),
            reverse=True,
        )
    if key == "newest":
        return sorted(items, key=lambda item: (item.created_at or datetime.min), reverse=True)
    if key == "recently_updated":
        return sorted(items, key=lambda item: (item.updated_at or datetime.min), reverse=True)
    return sorted(
        items,
        key=lambda item: (int(item.active_usage_count or 0), int(item.install_count or 0), float(item.rating_avg or 0.0)),
        reverse=True,
    )


def _collect_user_market_interests(user_id: int) -> tuple[set[str], set[str]]:
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
    category_match = 1.0 if item_category and item_category.strip().lower() in interests_categories else 0.0
    normalized_item_tags = {tag.strip().lower() for tag in (item_tags or []) if str(tag).strip()}
    overlap_count = len(normalized_item_tags.intersection(interests_tags))
    tag_match = min(1.0, overlap_count / 3) if normalized_item_tags else 0.0
    rating_score = (float(rating_avg or 0.0) / 5.0) * min(1.0, int(rating_count or 0) / 20)
    usage_score = min(1.0, int(active_usage_count or 0) / 100) * 0.7 + min(1.0, int(install_count or 0) / 200) * 0.3
    days_since_update = (
        (datetime.utcnow() - updated_at).days
        if updated_at is not None
        else RECENCY_WINDOW_DAYS
    )
    recency_score = max(0.0, 1 - (days_since_update / RECENCY_WINDOW_DAYS))

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


def _top_items_by_category_note_types(items: list[NoteType], *, limit_per_category: int = 5, max_categories: int = 3) -> dict[str, list[dict[str, Any]]]:
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
        sorted_bucket = _sort_note_type_items(buckets[category], "popular")[:limit_per_category]
        result[category] = [_serialize_note_type_marketplace_card(item) for item in sorted_bucket]
    return result


def _top_items_by_category_decks(items: list[DeckMarketplaceItem], *, limit_per_category: int = 5, max_categories: int = 3) -> dict[str, list[dict[str, Any]]]:
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
        sorted_bucket = _sort_deck_items(buckets[category], "popular")[:limit_per_category]
        result[category] = [_serialize_deck_marketplace_item(item) for item in sorted_bucket]
    return result


def _create_cards_for_note(note: Note) -> None:
    templates = Template.query.filter_by(note_type_id=note.note_type_id).order_by(Template.position.asc()).all()
    existing_template_ids = {card.template_id for card in note.cards}
    for template in templates:
        if template.id in existing_template_ids:
            continue
        card = Card(
            note_id=note.id,
            template_id=template.id,
            queue="new",
        )
        db.session.add(card)


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


def _normalize_progress_queue(value: str | None) -> str:
    normalized = (value or "new").strip().lower()
    if normalized == "learn":
        return "learning"
    if normalized in {"new", "learning", "review", "relearning"}:
        return normalized
    return "new"


def _card_state_from_progress(progress: VocabularyProgress | None, now: datetime) -> CardState:
    options = default_deck_options()
    if not progress:
        return CardState(
            type="new",
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
    if due_day is None and queue == "review":
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


def _apply_card_state_to_progress(progress: VocabularyProgress, card_state: CardState, now: datetime) -> VocabularyProgress:
    options = default_deck_options()
    queue = _normalize_progress_queue(card_state.type)
    due_at = card_state.due
    due_day = card_state.dueDay
    if due_day is not None:
        day_date = datetime.fromordinal(int(due_day)).date()
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


def _is_due(progress: VocabularyProgress | None, now: datetime) -> bool:
    if progress is None:
        return True
    queue = _normalize_progress_queue(progress.queue)
    if queue == "new":
        return True
    if progress.due_at is None:
        return True
    return progress.due_at <= now


def _pick_due_card(cards: list[Card], progress_map: dict[str, VocabularyProgress], now: datetime) -> Card | None:
    due_relearn: list[Card] = []
    due_learn: list[Card] = []
    due_review: list[Card] = []
    due_new: list[Card] = []
    for card in cards:
        progress = progress_map.get(card.id)
        if not _is_due(progress, now):
            continue
        queue = _normalize_progress_queue(progress.queue) if progress else "new"
        if queue == "relearning":
            due_relearn.append(card)
        elif queue == "learning":
            due_learn.append(card)
        elif queue == "review":
            due_review.append(card)
        else:
            due_new.append(card)
    for group in (due_relearn, due_learn, due_review, due_new):
        if group:
            return group[0]
    return None


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
    deck = VocabularyDeck.query.get_or_404(deck_id)
    
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
        parent_deck = VocabularyDeck.query.get(current_parent)
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
        return redirect(url_for("main.dashboard"))
    note_types = NoteType.query.filter_by(user_id=current_user.id).order_by(NoteType.name.asc()).all()
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()
    return render_template("flashcards/note_editor.html", note_types=note_types, decks=decks)


@flashcards_bp.route("/flashcards/study")
@login_required
def flashcard_study_page():
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()
    return render_template("flashcards/study.html", decks=decks)


@flashcards_bp.route("/flashcards/notes")
@login_required
def notes_list_page():
    """Note management — list, filter, quick delete."""
    if not is_admin_user(current_user):
        return redirect(url_for("main.dashboard"))
    note_types = (
        NoteType.query.filter_by(user_id=current_user.id)
        .order_by(NoteType.name.asc())
        .all()
    )
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()

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
        return redirect(url_for("main.dashboard"))
    note = Note.query.filter_by(id=note_id, user_id=current_user.id).first()
    if not note:
        return redirect(url_for("flashcards.notes_list_page"))
    note_type = NoteType.query.get(note.note_type_id)
    decks = VocabularyDeck.query.order_by(VocabularyDeck.name.asc()).all()
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
        db.session.add(Card(note_id=note.id, template_id=template.id, queue="new"))
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

    query = Card.query.join(Note, Card.note_id == Note.id).filter(Note.user_id == current_user.id)
    if scope == "deck":
        if not scope_id_raw:
            return _api_error("VALIDATION_ERROR", "scope_id is required for deck scope.", field="scope_id")
        try:
            scope_id = int(scope_id_raw)
        except ValueError:
            return _api_error("VALIDATION_ERROR", "scope_id must be an integer for deck scope.", field="scope_id")
        query = query.filter(Note.deck_id == scope_id)
    elif scope == "note_type":
        if not scope_id_raw:
            return _api_error("VALIDATION_ERROR", "scope_id is required for note_type scope.", field="scope_id")
        query = query.filter(Note.note_type_id == scope_id_raw)
    else:
        return _api_error("VALIDATION_ERROR", f"Unsupported scope: {scope}", field="scope")

    cards = query.order_by(Card.created_at.asc(), Card.id.asc()).all()
    if not cards:
        return jsonify({"card_id": None, "message": "No cards found for selected scope."})

    card_ids = [card.id for card in cards]
    progress_rows = VocabularyProgress.query.filter(
        VocabularyProgress.user_id == current_user.id,
        VocabularyProgress.new_card_id.in_(card_ids),
    ).all()
    progress_map = {row.new_card_id: row for row in progress_rows if row.new_card_id}
    now = datetime.utcnow()
    selected_card = _pick_due_card(cards, progress_map, now)
    if not selected_card:
        return jsonify({"card_id": None, "message": "No due cards."})

    progress = progress_map.get(selected_card.id)
    card_state = _card_state_from_progress(progress, now)
    interval_preview = computeAnswerPreview(card_state, default_deck_options(), now)

    note = selected_card.note
    template = selected_card.template
    try:
        rendered = render_template_pair(
            template=template,
            field_defs=note.note_type.field_defs,
            field_values=note.field_values or {},
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

    card = Card.query.join(Note, Card.note_id == Note.id).filter(Card.id == card_id, Note.user_id == current_user.id).first()
    if not card:
        return _api_error("FIELD_NOT_FOUND", "Card not found.", status=404)

    progress = VocabularyProgress.query.filter_by(user_id=current_user.id, new_card_id=card.id).first()
    if progress is None:
        progress = VocabularyProgress(
            user_id=current_user.id,
            entry_id=None,
            new_card_id=card.id,
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
    updated_state = applyAnswer(current_state, default_deck_options(), now, rating)  # type: ignore[arg-type]
    _apply_card_state_to_progress(progress, updated_state, now)
    _touch_note_type_install_usage(user_id=current_user.id, installed_note_type_id=card.note.note_type_id, activity_at=now)
    note_type_installs = NoteTypeInstall.query.filter_by(
        user_id=current_user.id,
        installed_note_type_id=card.note.note_type_id,
    ).all()
    for install in note_type_installs:
        source_note_type = NoteType.query.get(install.source_note_type_id)
        if source_note_type:
            _recompute_note_type_market_stats(source_note_type)

    if card.note.deck_id is not None:
        _touch_deck_install_usage(user_id=current_user.id, local_deck_id=card.note.deck_id, activity_at=now)
        deck_installs = DeckInstall.query.filter_by(user_id=current_user.id, local_deck_id=card.note.deck_id).all()
        for deck_install in deck_installs:
            deck_item = DeckMarketplaceItem.query.get(deck_install.deck_item_id)
            if deck_item:
                _recompute_deck_item_market_stats(deck_item)
    _audit("study.answer", {"card_id": card.id, "rating": rating})
    db.session.commit()
    next_url = url_for("flashcards.study_next", scope="deck", scope_id=card.note.deck_id) if card.note.deck_id else None
    return jsonify({"success": True, "next_card_url": next_url, "intervals_preview": computeAnswerPreview(updated_state, default_deck_options(), now)})


@flashcards_bp.route("/api/flashcards/seed-default-note-type", methods=["POST"])
@flashcards_bp.route("/api/flashcards/seed-legacy", methods=["POST"])
@login_required
def seed_legacy_note_type():
    if not is_admin_user(current_user):
        return _api_error("VALIDATION_ERROR", "Admin only endpoint.", status=403)
    note_type, template = ensure_legacy_note_type(db.session, current_user.id)
    _audit("note_type.seed_default", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return jsonify({"note_type_id": note_type.id, "template_id": template.id})


def _parse_query_price_cents(param_name: str) -> int | None:
    raw_value = (request.args.get(param_name) or "").strip()
    if not raw_value:
        return None
    parsed = _parse_price_cents(raw_value)
    if parsed is None:
        return None
    return max(0, parsed)


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
    if deck_item.source_deck_id is not None and not VocabularyDeck.query.get(deck_item.source_deck_id):
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

    original_note_type_id = deck_item.source_note_type_id
    _bind_deck_item_source_note_type(deck_item, require_source_note_type=False)
    if deck_item.source_note_type_id != original_note_type_id:
        db.session.commit()

    install = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=current_user.id).first()
    review = DeckReview.query.filter_by(deck_item_id=deck_item.id, user_id=current_user.id).first()
    payload = _serialize_deck_marketplace_item(deck_item)
    payload["is_installed"] = install is not None
    payload["installed_deck_id"] = install.local_deck_id if install else None
    payload["is_owner"] = deck_item.owner_user_id == current_user.id
    payload["can_rate"] = _can_user_rate_deck(deck_item, user_id=current_user.id)
    payload["my_review"] = (
        {
            "rating": review.rating,
            "comment": review.comment,
            "updated_at": review.updated_at.isoformat() if review.updated_at else None,
        }
        if review
        else None
    )

    source_note_type_payload = None
    source_note_type_id = (deck_item.source_note_type_id or "").strip()
    if source_note_type_id:
        source_note_type = NoteType.query.get(source_note_type_id)
        if source_note_type:
            ordered_templates = sorted(
                source_note_type.templates,
                key=lambda item: (int(item.position or 0), str(item.name or "").lower()),
            )
            source_note_type_payload = {
                "id": source_note_type.id,
                "name": source_note_type.name,
                "title": source_note_type.name,
                "publish_status": source_note_type.publish_status,
                "templates": [
                    {
                        "id": template.id,
                        "name": template.name,
                        "position": int(template.position or 0),
                        "is_default": bool(template.is_default),
                    }
                    for template in ordered_templates
                ],
            }
    payload["source_note_type"] = source_note_type_payload

    return jsonify(payload)


@flashcards_bp.route("/api/shared/decks/<deck_item_id>/templates/<template_id>/preview", methods=["POST"])
@login_required
def preview_shared_deck_template(deck_item_id: str, template_id: str):
    deck_item = _get_shared_deck_item_for_view(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    original_note_type_id = deck_item.source_note_type_id
    bind_error = _bind_deck_item_source_note_type(deck_item, require_source_note_type=True)
    if bind_error:
        return _api_error("VALIDATION_ERROR", bind_error, status=409)
    if deck_item.source_note_type_id != original_note_type_id:
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

    preview_note = None
    preview_entry = None
    if deck_item.source_deck_id is not None:
        query = Note.query.filter_by(
            deck_id=deck_item.source_deck_id,
            note_type_id=note_type.id,
        )
        if deck_item.owner_user_id is not None:
            query = query.filter(Note.user_id == deck_item.owner_user_id)
        preview_note = query.order_by(Note.created_at.asc(), Note.id.asc()).first()
        if preview_note is None:
            preview_entry = (
                VocabularyEntry.query.filter_by(deck_id=deck_item.source_deck_id)
                .order_by(VocabularyEntry.created_at.asc(), VocabularyEntry.id.asc())
                .first()
            )

    if preview_note:
        preview_field_values = preview_note.field_values or {}
        preview_media_assets = preview_note.media_assets
        preview_note_key = f"shared-deck-preview:{deck_item.id}:{preview_note.id}"
    elif preview_entry:
        preview_field_values = _build_preview_values_from_vocabulary_entry(preview_entry, note_type.field_defs)
        preview_media_assets = []
        preview_note_key = f"shared-deck-preview:{deck_item.id}:entry:{preview_entry.id}"
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
    if deck_item.source_deck_id is not None and not VocabularyDeck.query.get(deck_item.source_deck_id):
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
    deck_item = DeckMarketplaceItem.query.get(deck_item_id)
    if not deck_item:
        return _api_error("FIELD_NOT_FOUND", "Deck item not found.", status=404)

    original_note_type_id = deck_item.source_note_type_id
    bind_error = _bind_deck_item_source_note_type(deck_item, require_source_note_type=True)
    if bind_error:
        return _api_error("VALIDATION_ERROR", bind_error, status=409)
    if deck_item.source_note_type_id != original_note_type_id:
        db.session.commit()

    status = str(deck_item.publish_status or "").strip().lower()
    if status not in PUBLISH_STATUSES_VISIBLE:
        return _api_error("VALIDATION_ERROR", "This deck is not available for install.", status=409)
    if deck_item.owner_user_id == current_user.id:
        return _api_error("VALIDATION_ERROR", "Owner cannot install own deck item.", status=409)

    existing = DeckInstall.query.filter_by(deck_item_id=deck_item.id, user_id=current_user.id).first()
    if existing:
        return jsonify(
            {
                "deck_item_id": deck_item.id,
                "installed_deck_id": existing.local_deck_id,
                "already_installed": True,
            }
        )

    now = datetime.utcnow()
    local_deck_id = None
    if deck_item.source_deck_id is not None:
        source_deck = VocabularyDeck.query.get(deck_item.source_deck_id)
        if source_deck is None:
            return _api_error("FIELD_NOT_FOUND", "Source deck not found.", status=404)
        cloned_root = _clone_deck_subtree(
            source_deck_id=source_deck.id,
            parent_id=None,
            owner_user_id=current_user.id,
        )
        local_deck_id = cloned_root.id

    purchase_price_cents = int(deck_item.price_cents or 0) if deck_item.pricing_mode == "paid" else 0
    install = DeckInstall(
        deck_item_id=deck_item.id,
        user_id=current_user.id,
        local_deck_id=local_deck_id,
        purchase_price_cents=purchase_price_cents,
        installed_at=now,
        purchased_at=now if deck_item.pricing_mode == "paid" else None,
    )
    db.session.add(install)

    auto_note_type_install = None
    if deck_item.source_note_type_id:
        source_note_type = NoteType.query.get(deck_item.source_note_type_id)
        existing_note_install = NoteTypeInstall.query.filter_by(
            source_note_type_id=deck_item.source_note_type_id,
            user_id=current_user.id,
        ).first()
        if (
            source_note_type
            and existing_note_install is None
            and source_note_type.pricing_mode == "free"
            and bool(source_note_type.is_official)
            and str(source_note_type.publish_status or "").strip().lower() in PUBLISH_STATUSES_VISIBLE
            and source_note_type.user_id != current_user.id
        ):
            installed_copy = _clone_note_type_for_user(source_note_type, current_user.id)
            auto_note_type_install = NoteTypeInstall(
                source_note_type_id=source_note_type.id,
                installed_note_type_id=installed_copy.id,
                user_id=current_user.id,
                purchase_price_cents=0,
                installed_at=now,
            )
            db.session.add(auto_note_type_install)
            _recompute_note_type_market_stats(source_note_type)

    _recompute_deck_item_market_stats(deck_item)
    _audit(
        "market.deck_item.install",
        {
            "deck_item_id": deck_item.id,
            "local_deck_id": local_deck_id,
            "price_cents": purchase_price_cents,
            "auto_note_type_install": bool(auto_note_type_install),
        },
    )
    db.session.commit()
    return jsonify(
        {
            "deck_item_id": deck_item.id,
            "installed_deck_id": local_deck_id,
            "purchase_price_cents": purchase_price_cents,
            "auto_note_type_installed": bool(auto_note_type_install),
        }
    ), 201


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
    source_deck = VocabularyDeck.query.order_by(VocabularyDeck.id.asc()).first()
    # Stamp ownership on the source deck so it is recognised as admin-owned
    if source_deck and source_deck.owner_user_id is None:
        source_deck.owner_user_id = admin_id
    if deck_item is None:
        deck_item = DeckMarketplaceItem(
            owner_user_id=admin_id,
            source_deck_id=source_deck.id if source_deck else None,
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
        if source_deck:
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
