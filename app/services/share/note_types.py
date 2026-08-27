"""NoteType marketplace publishing, schema validation, and cloning helpers."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal
import json
import logging
import time
from types import SimpleNamespace
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

from flask import current_app
from sqlalchemy import and_, case, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload

from app.repositories import (
    deck_change_request_repository,
    deck_release_repository,
    flashcards_share_repository,
    marketplace_taxonomy_repository,
    study_repository,
    vocabulary_repository,
)
from app.repositories.deck_tree_query import (
    collect_ancestor_ids,
    collect_subtree_ids,
)
from app.services import (
    deck_release_service,
    deck_working_tree_service,
    marketplace_query_service,
    marketplace_taxonomy_service,
    note_sync_service,
    study_service,
)
from app.services.share.constants import (
    DECK_ACTIVE_REVIEW_THRESHOLD,
    DEFAULT_VISIBLE_PUBLISH_STATUSES,
    FIELD_TYPES,
    MARKET_ACTIVITY_POLICY_VERSION,
    NOTE_TYPE_ACTIVE_DAYS_THRESHOLD,
    NOTE_TYPE_ACTIVE_NOTE_THRESHOLD,
    NOTE_TYPE_ACTIVE_REVIEW_THRESHOLD,
    PUBLISH_STATUSES_VISIBLE,
    SHARED_DECK_INSTALL_DEADLOCK_MESSAGE,
    SHARED_DECK_INSTALL_MAX_RETRIES,
    UTC,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.deck import Deck
from models.deck_change_request import DeckChangeRequest
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.deck_release import DeckRelease
from models.deck_release_entity_membership import DeckReleaseEntityMembership
from models.deck_review import DeckReview
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.note_type_review import NoteTypeReview
from models.taxonomy import TaxonomyDomain, TaxonomyLevel, TaxonomySubject, TaxonomyTopic
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)


from app.services.share.helpers import (
    ShareControllerError,
    _audit,
    _increment_counter,
    _is_mysql_deadlock,
    _set_note_type_install_market_activity,
    _utcnow,
    can_user_rate_note_type,
    is_note_type_visible_for_shared,
    make_unique_note_type_name,
    recompute_note_type_market_stats,
    touch_note_type_install_usage,
)

def create_note_type(
    user_id: int,
    payload: dict,
    is_admin: bool,
) -> tuple[NoteType | None, str | None, str | None]:
    name = (payload.get("name") or payload.get("title") or "").strip()
    if not name:
        return None, "Note type name is required.", "name"

    if NoteType.query.filter_by(user_id=user_id, name=name).first():
        return None, "Note type already exists.", "name"

    note_type = NoteType(user_id=user_id, name=name)
    db.session.add(note_type)
    db.session.flush()

    input_fields = payload.get("field_defs")
    if not isinstance(input_fields, list) or not input_fields:
        input_fields = [
            {
                "name": "Word",
                "field_type": "text",
                "position": 0,
                "required": True,
                "identity_role": "primary",
            }
        ]

    identity_count = sum(1 for row in input_fields if row.get("identity_role") == "primary")
    if identity_count > 1:
        db.session.rollback()
        return None, "Only one primary identity field is allowed.", "field_defs"

    for idx, row in enumerate(input_fields):
        field_name = (row.get("name") or "").strip()
        field_type = (row.get("field_type") or "text").strip()
        required = bool(row.get("required", False))
        identity_role = row.get("identity_role")
        if not field_name:
            db.session.rollback()
            return None, "Field name is required.", "field_defs"
        if field_type not in FIELD_TYPES:
            db.session.rollback()
            return None, f"Unsupported field_type: {field_type}", "field_defs"
        if identity_role not in (None, "primary"):
            db.session.rollback()
            return None, "identity_role must be null or primary.", "field_defs"
        if identity_role == "primary" and field_type != "text":
            db.session.rollback()
            return None, "The identity field must use the text field type.", "field_defs"
        if identity_role == "primary":
            required = True
        db.session.add(
            FieldDef(
                note_type_id=note_type.id,
                name=field_name,
                field_type=field_type,
                position=int(row.get("position", idx)),
                required=required,
                identity_role=identity_role,
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
    
    metadata_error = flashcards_share.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if metadata_error:
        db.session.rollback()
        return None, metadata_error, None
        
    _audit(user_id, "note_type.create", {"note_type_id": note_type.id, "name": note_type.name})
    db.session.commit()
    return note_type, None, None



def create_template(note_type_id: str, user_id: int, payload: dict) -> tuple[Template | None, str | None]:
    note_type = db.session.get(NoteType, note_type_id)
    if not note_type:
        return None, "Note type not found."
        
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
    notes = Note.query.filter_by(note_type_id=note_type.id, user_id=user_id).all()
    for note in notes:
        db.session.add(Card(note_id=note.id, template_id=template.id))
        
    _audit(user_id, "template.create", {"note_type_id": note_type.id, "template_id": template.id})
    db.session.commit()
    return template, None



def update_template(template: Template, user_id: int) -> None:
    _audit(user_id, "template.update", {"note_type_id": template.note_type_id, "template_id": template.id})
    db.session.commit()



def reset_template(template: Template, default_front: str, default_back: str, default_css: str) -> None:
    template.front_html = default_front
    template.back_html = default_back
    template.shared_css = default_css
    db.session.commit()



def publish_note_type(note_type: NoteType, user_id: int, payload: dict, is_admin: bool) -> tuple[bool, str | None]:
    payload.setdefault("publish_status", "published")
    validation_error = flashcards_share.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        db.session.rollback()
        return False, validation_error
        
    flashcards_share.recompute_note_type_market_stats(
        note_type,
        note_type_active_note_threshold=5,
        note_type_active_review_threshold=1,
        note_type_active_days_threshold=7,
    )
    _audit(user_id, "note_type.publish", {"note_type_id": note_type.id, "publish_status": note_type.publish_status})
    db.session.commit()
    return True, None



def is_installed_note_type_copy(note_type_id: str | None) -> bool:
    """Return whether a note type is a Marketplace-installed local copy."""
    normalized_id = str(note_type_id or "").strip()
    if not normalized_id:
        return False
    return (
        NoteTypeInstall.query.filter_by(installed_note_type_id=normalized_id).first()
        is not None
    )



def get_note_type_publish_eligibility(
    *,
    note_type: NoteType,
    user_id: int,
    is_admin: bool = False,
) -> dict[str, Any]:
    if note_type.user_id != user_id and not is_admin:
        return {
            "is_selectable": False,
            "block_code": "not_owned",
            "block_reason": "Note Type không thuộc quyền sở hữu của bạn.",
        }
    if is_installed_note_type_copy(note_type.id):
        return {
            "is_selectable": False,
            "block_code": "marketplace_install",
            "block_reason": "Note Type được cài từ Marketplace không thể chia sẻ lại.",
        }
    return {
        "is_selectable": True,
        "block_code": None,
        "block_reason": None,
    }



def validate_note_type_publish_requirements(note_type: NoteType) -> str | None:
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
    if note_type.pricing_mode == "paid" and int(note_type.price_amount_minor or 0) <= 0:
        return "Paid note type must have a positive price."
    if not note_type.field_defs:
        return "At least one field is required for publish."
    if not note_type.templates:
        return "At least one card template is required for publish."
    taxonomy_error = marketplace_taxonomy_service.validate_required_taxonomy(
        note_type.taxonomy_metadata if isinstance(note_type.taxonomy_metadata, dict) else {},
        content_type="note_type",
    )
    if taxonomy_error:
        return taxonomy_error
    return None


def apply_note_type_marketplace_payload(
    note_type: NoteType,
    payload: dict[str, Any],
    *,
    allow_set_official: bool,
    publish_statuses_visible: set[str] | None = None,
) -> str | None:
    visible_statuses = publish_statuses_visible or DEFAULT_VISIBLE_PUBLISH_STATUSES
    taxonomy_keys = {
        "taxonomy_domain",
        "domain",
        "taxonomy_subject",
        "subject",
        "taxonomy_difficulty_band",
        "difficulty_band",
        "level_band",
        "taxonomy_framework",
        "framework",
        "taxonomy_framework_level",
        "framework_level",
        "taxonomy_framework_track",
        "framework_track",
        "taxonomy_learning_goals",
        "learning_goals",
        "taxonomy_primary_topics",
        "primary_topics",
        "taxonomy_format_features",
        "format_features",
        "taxonomy_audience",
        "audience",
        "taxonomy_best_used_for",
        "best_used_for",
    }

    if "title" in payload or "name" in payload:
        new_name = (payload.get("title") or payload.get("name") or "").strip()
        if not new_name:
            return "Title is required."
        existing = flashcards_share_repository.check_note_type_name_exists(note_type.user_id, new_name, note_type.id)
        if existing:
            return "Another note type already uses this title."
        note_type.name = new_name

    if "description" in payload:
        note_type.description = (payload.get("description") or "").strip() or None
    if "primary_category" in payload:
        note_type.primary_category = (payload.get("primary_category") or "").strip() or None
    if "tags" in payload:
        note_type.tags = marketplace_query_service.normalize_marketplace_tags(payload.get("tags"))
    if any(key in payload for key in taxonomy_keys):
        taxonomy_metadata, taxonomy_error = marketplace_taxonomy_service.normalize_taxonomy_payload(
            payload,
            content_type="note_type",
        )
        if taxonomy_error:
            return taxonomy_error
        note_type.taxonomy_metadata = taxonomy_metadata
        suggested_category = marketplace_taxonomy_service.suggest_primary_category(taxonomy_metadata)
        if suggested_category and "primary_category" not in payload:
            note_type.primary_category = suggested_category
    if "preview_text" in payload:
        note_type.preview_text = (payload.get("preview_text") or "").strip() or None
    if "preview_image_url" in payload:
        note_type.preview_image_url = (payload.get("preview_image_url") or "").strip() or None
    if "version" in payload:
        note_type.version = (payload.get("version") or "").strip() or "1.0.0"
    if "changelog" in payload:
        note_type.changelog = (payload.get("changelog") or "").strip() or None

    pricing_mode, price_amount_minor, pricing_error = marketplace_query_service.normalize_pricing(
        payload,
        current_mode=str(note_type.pricing_mode or "free"),
        current_price_amount_minor=int(note_type.price_amount_minor or 0),
    )
    if pricing_error:
        return pricing_error
    note_type.pricing_mode = pricing_mode
    note_type.price_amount_minor = price_amount_minor

    if "is_official" in payload:
        if not allow_set_official:
            return "Only admin can set official flag."
        note_type.is_official = bool(payload.get("is_official"))

    if "publish_status" in payload:
        candidate_status = str(payload.get("publish_status") or "").strip().lower()
        if candidate_status not in {"private", "published", "unlisted", "archived"}:
            return "publish_status is invalid."
        if candidate_status in visible_statuses:
            err = validate_note_type_publish_requirements(note_type)
            if err:
                return err
            if note_type.publish_status not in visible_statuses:
                note_type.published_at = _utcnow()
            note_type.archived_at = None
        elif candidate_status == "archived":
            note_type.archived_at = _utcnow()
        note_type.publish_status = candidate_status

    if str(note_type.publish_status or "").strip().lower() in visible_statuses:
        return validate_note_type_publish_requirements(note_type)
    return None


def get_shared_note_type_for_view(
    note_type_id: str,
    user_id: int,
    publish_statuses_visible: set[str] | None = None,
) -> NoteType | None:
    note_type = flashcards_share_repository.get_note_type_by_id(note_type_id)
    if note_type is None:
        return None
    if not is_note_type_visible_for_shared(
        note_type,
        user_id=user_id,
        publish_statuses_visible=publish_statuses_visible,
    ):
        return None
    return note_type



def install_shared_note_type(source_note_type: NoteType, user_id: int) -> tuple[NoteType | None, int | None]:
    installed_copy = flashcards_share.clone_note_type_for_user(source_note_type, user_id)
    now = _utcnow()
    purchase_amount_minor = int(source_note_type.price_amount_minor or 0) if source_note_type.pricing_mode == "paid" else 0
    install_row = NoteTypeInstall(
        source_note_type_id=source_note_type.id,
        installed_note_type_id=installed_copy.id,
        user_id=user_id,
        purchase_amount_minor=purchase_amount_minor,
        installed_at=now,
        purchased_at=now if source_note_type.pricing_mode == "paid" else None,
        market_active=False,
        market_active_evaluated_at=now,
        market_active_policy_version=MARKET_ACTIVITY_POLICY_VERSION,
    )
    db.session.add(install_row)
    db.session.flush()
    _increment_counter(NoteType, source_note_type.id, NoteType.install_count, 1)
    _audit(
        user_id,
        "market.note_type.install",
        {
            "source_note_type_id": source_note_type.id,
            "installed_note_type_id": installed_copy.id,
            "price_amount_minor": purchase_amount_minor,
            "price_cents": purchase_amount_minor,
        },
    )
    db.session.commit()
    return installed_copy, purchase_amount_minor



def rate_shared_note_type(note_type: NoteType, user_id: int, rating: int, comment: str | None) -> None:
    review = NoteTypeReview.query.filter_by(note_type_id=note_type.id, user_id=user_id).first()
    if review is None:
        review = NoteTypeReview(note_type_id=note_type.id, user_id=user_id, rating=rating, comment=comment)
        db.session.add(review)
    else:
        review.rating = rating
        review.comment = comment

    flashcards_share.recompute_note_type_market_stats(note_type)
    _audit(user_id, "market.note_type.rate", {"note_type_id": note_type.id, "rating": rating})
    db.session.commit()



def clone_note_type_for_user(source_note_type: NoteType, user_id: int) -> NoteType:
    clone = NoteType(
        user_id=user_id,
        name=make_unique_note_type_name(user_id, source_note_type.name),
        description=source_note_type.description,
        primary_category=source_note_type.primary_category,
        tags=list(source_note_type.tags or []),
        preview_text=source_note_type.preview_text,
        preview_image_url=source_note_type.preview_image_url,
        pricing_mode="free",
        price_amount_minor=0,
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
                identity_role=field_def.identity_role,
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



def ensure_note_type_install_for_user(
    *,
    source_note_type: NoteType,
    user_id: int,
    installed_at: datetime | None = None,
) -> NoteTypeInstall:
    install_row = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=user_id,
    ).first()
    if install_row and (install_row.installed_note_type_id or "").strip():
        installed_copy = db.session.get(NoteType, install_row.installed_note_type_id)
        if installed_copy:
            return install_row

    installed_copy = flashcards_share.clone_note_type_for_user(source_note_type, user_id)
    now = installed_at or _utcnow()
    purchase_amount_minor = int(source_note_type.price_amount_minor or 0) if source_note_type.pricing_mode == "paid" else 0

    if install_row is None:
        install_row = NoteTypeInstall(
            source_note_type_id=source_note_type.id,
            installed_note_type_id=installed_copy.id,
            user_id=user_id,
            purchase_amount_minor=purchase_amount_minor,
            installed_at=now,
            purchased_at=now if source_note_type.pricing_mode == "paid" else None,
            market_active=False,
            market_active_evaluated_at=now,
            market_active_policy_version=MARKET_ACTIVITY_POLICY_VERSION,
        )
        db.session.add(install_row)
        db.session.flush()
        _increment_counter(NoteType, source_note_type.id, NoteType.install_count, 1)
    else:
        install_row.installed_note_type_id = installed_copy.id
        install_row.purchase_amount_minor = purchase_amount_minor
        if install_row.installed_at is None:
            install_row.installed_at = now
        install_row.purchased_at = now if source_note_type.pricing_mode == "paid" else None

    return install_row



