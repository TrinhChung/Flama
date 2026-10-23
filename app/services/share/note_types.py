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
from app.repositories import template_library_repository
from models import db
from models.audit_log import AuditLog
from models.card import Card
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
from models.taxonomy import (
    TaxonomyDomain,
    TaxonomyFramework,
    TaxonomyFrameworkLevel,
    TaxonomySubject,
)
from models.study_application import StudyApplication
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)


from app.services.share.helpers import (
    ShareControllerError,
    _active_note_type_templates,
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


def default_template_sources(field_rows: list[tuple[int, str]]) -> tuple[str, str]:
    """Return (front_html, back_html) for a new template.

    field_rows: (position, name) of the NoteType's fields, any order.
    """
    cleaned = [
        (int(pos), str(name).strip())
        for pos, name in field_rows
        if name and str(name).strip()
    ]
    cleaned.sort(key=lambda item: (item[0], item[1]))
    if not cleaned:
        return "{{Word}}", "{{Word}}"
    names = [name for _, name in cleaned]
    for name in names[:2]:
        if name == "." or name[0] in "#^/!>&=" or "{" in name or "}" in name:
            raise ValueError(
                f"Field name '{name}' cannot be used in an automatic template. "
                "Rename the field or provide explicit front_html and back_html."
            )
    first = "{{" + names[0] + "}}"
    if len(names) >= 2:
        back = first + "<hr>" + "{{" + names[1] + "}}"
    else:
        back = first
    return first, back


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
    try:
        default_front, default_back = default_template_sources(
            [
                (int(row.get("position", idx)), str(row.get("name") or "").strip())
                for idx, row in enumerate(input_fields)
            ]
        ) if not template_payload.get("front_html") or not template_payload.get("back_html") else ("", "")
    except ValueError as exc:
        db.session.rollback()
        return None, str(exc), "field_defs"
    front_html = (template_payload.get("front_html") or default_front).strip()
    back_html = (template_payload.get("back_html") or default_back).strip()
    shared_css = (template_payload.get("shared_css") or "").strip()
    template = template_library_repository.create_attached_template(db.session, note_type=note_type, name=(template_payload.get("name") or "Card 1").strip() or "Card 1", front_html=front_html, back_html=back_html, shared_css=shared_css, position=0, is_default=True)
    db.session.add(template)
    from app.services.template_version_service import mark_template_version
    mark_template_version(template, origin="create", actor_user_id=user_id)

    metadata_error = apply_note_type_marketplace_payload(
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


def create_template(
    note_type_id: str,
    user_id: int,
    payload: dict,
    *,
    commit: bool = True,
) -> tuple[Template | None, str | None]:
    note_type = db.session.get(NoteType, note_type_id)
    if not note_type:
        return None, "Note type not found."

    name = (payload.get("name") or "").strip() or f"Card {len(template_library_repository.applications(db.session, note_type.id)) + 1}"
    try:
        default_front, default_back = default_template_sources(
            [(int(field.position or 0), str(field.name or "")) for field in note_type.field_defs]
        ) if not payload.get("front_html") or not payload.get("back_html") else ("", "")
    except ValueError as exc:
        return None, str(exc)
    front_html = (payload.get("front_html") or default_front).strip()
    back_html = (payload.get("back_html") or default_back).strip()
    shared_css = (payload.get("shared_css") or "").strip()

    max_pos = db.session.query(db.func.max(StudyApplication.position)).filter_by(
        note_type_id=note_type.id
    ).scalar()
    template = template_library_repository.create_attached_template(db.session, note_type=note_type, name=name, front_html=front_html, back_html=back_html, shared_css=shared_css, position=(int(max_pos) + 1) if max_pos is not None else 0, is_default=False)
    db.session.add(template)
    from app.services.template_version_service import mark_template_version
    mark_template_version(template, origin="create", actor_user_id=user_id)
    # The flush gives the Template its compatibility occurrence, which presents
    # it on every Note of the NoteType; nothing is written per Note (ADR P11).
    db.session.flush()

    _audit(user_id, "template.create", {"note_type_id": note_type.id, "template_id": template.id})
    if commit:
        db.session.commit()
    else:
        db.session.flush()
    return template, None


def update_template(template: Template, user_id: int) -> None:
    _audit(user_id, "template.update", {"template_id": template.id})
    db.session.commit()


def reset_template(template: Template, default_front: str, default_back: str, default_css: str) -> None:
    template.front_html = default_front
    template.back_html = default_back
    template.shared_css = default_css
    db.session.commit()


def publish_note_type(note_type: NoteType, user_id: int, payload: dict, is_admin: bool) -> tuple[bool, str | None]:
    payload.setdefault("publish_status", "published")
    validation_error = apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=is_admin,
        publish_statuses_visible=PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        db.session.rollback()
        return False, validation_error

    recompute_note_type_market_stats(
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
    template_error = _note_type_template_reference_error(note_type)
    if template_error:
        return {"is_selectable": False, "block_code": "marketplace_template", "block_reason": template_error}
    return {
        "is_selectable": True,
        "block_code": None,
        "block_reason": None,
    }


def validate_note_type_publish_requirements(note_type: NoteType) -> str | None:
    template_error = _note_type_template_reference_error(note_type)
    if template_error:
        return template_error
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
    if not _active_note_type_templates(note_type.id):
        return "At least one card template is required for publish."
    taxonomy_error = marketplace_taxonomy_service.validate_required_taxonomy(
        note_type.taxonomy_metadata if isinstance(note_type.taxonomy_metadata, dict) else {},
        content_type="note_type",
    )
    if taxonomy_error:
        return taxonomy_error
    return None


def _note_type_template_reference_error(note_type):
    from app.services.note_type_bundle_publication_service import reference_validation_error
    return reference_validation_error(db.session, note_type_id=note_type.id,
        actor_user_id=note_type.user_id)


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
        if candidate_status in visible_statuses:
            db.session.flush()
            from app.services.note_type_release_service import stage_publication, NoteTypeReleaseError
            from app.services.note_type_bundle_publication_service import stage_template_listings
            from app.services.template_release_service import TemplateReleaseError
            try:
                stage_template_listings(db.session, note_type=note_type,
                    actor_user_id=note_type.user_id, payload=payload)
                stage_publication(db.session, note_type=note_type, actor_user_id=note_type.user_id)
            except (NoteTypeReleaseError, TemplateReleaseError) as exc:
                db.session.rollback()
                return str(exc)

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
    from app.services.note_type_release_service import stage_receipt
    install_row, created = stage_receipt(db.session, source_note_type=source_note_type, user_id=user_id)
    installed_copy = db.session.get(NoteType, install_row.installed_note_type_id)
    purchase_amount_minor = int(install_row.purchase_amount_minor or 0)
    _audit(
        user_id,
        "market.note_type.install",
        {
            "source_note_type_id": source_note_type.id,
            "installed_note_type_id": installed_copy.id,
            "price_amount_minor": purchase_amount_minor,
            "price_cents": purchase_amount_minor,
            "restored": not created,
            "applied_release_id": install_row.applied_release_id,
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

    recompute_note_type_market_stats(note_type)
    _audit(user_id, "market.note_type.rate", {"note_type_id": note_type.id, "rating": rating})
    db.session.commit()



def clone_note_type_for_user(source_note_type: NoteType, user_id: int, *, copy_legacy_templates=True) -> NoteType:
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

    raw_copies = []
    by_source_definition = {}
    source_field_names = {str(field.id): field.name for field in source_note_type.field_defs}
    clone_field_ids = {field.name: str(field.id) for field in clone.field_defs}
    for view in (template_library_repository.attached_templates(db.session, source_note_type.id)
                 if copy_legacy_templates else []):
        source_application = view.application
        mapped_bindings = {key: clone_field_ids.get(source_field_names.get(str(value)))
                           for key, value in (source_application.input_bindings or {}).items()}
        copied_template = by_source_definition.get(view.id)
        if copied_template is None:
            copied_template = template_library_repository.create_attached_template(
                db.session, note_type=clone, owner_user_id=user_id, origin="market_copy",
                source_template_id=view.id, source_version_id=view.current_version_id,
                input_schema=view.input_schema, name=view.name, front_html=view.front_html,
                back_html=view.back_html, shared_css=view.shared_css, position=view.position,
                is_default=bool(view.is_default), occurrence_key=source_application.occurrence_key,
                source_ord=source_application.source_ord, input_bindings=mapped_bindings,
            )
            by_source_definition[view.id] = copied_template
            raw_copies.append(copied_template)
        else:
            db.session.add(StudyApplication(note_type=clone, template=copied_template,
                occurrence_key=source_application.occurrence_key, source_ord=source_application.source_ord,
                position=source_application.position, is_default=bool(source_application.is_default),
                display_name=source_application.display_name, input_bindings=mapped_bindings, status_code="ACTIVE"))
    db.session.info.setdefault("flama.template_clone_compat", {})[clone.id] = raw_copies

    return clone



def ensure_note_type_install_for_user(
    *,
    source_note_type: NoteType,
    user_id: int,
    installed_at: datetime | None = None,
    copy_legacy_templates: bool = True,
) -> NoteTypeInstall:
    install_row = NoteTypeInstall.query.filter_by(
        source_note_type_id=source_note_type.id,
        user_id=user_id,
    ).first()
    if install_row and (install_row.installed_note_type_id or "").strip():
        installed_copy = db.session.get(NoteType, install_row.installed_note_type_id)
        if installed_copy:
            return install_row

    installed_copy = clone_note_type_for_user(source_note_type, user_id, copy_legacy_templates=copy_legacy_templates)
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



