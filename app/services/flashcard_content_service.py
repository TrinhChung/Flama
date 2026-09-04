"""Application services for flashcard note types, templates, fields, and notes."""

from __future__ import annotations

import hashlib
import json
import logging
from types import SimpleNamespace
from typing import Any, Mapping

from app.services import (
    deck_working_tree_service,
    flashcards_share_service,
    marketplace_query_service,
)
from app.services.flashcard_legacy import (
    LEGACY_BACK_TEMPLATE,
    LEGACY_FRONT_TEMPLATE,
    LEGACY_SHARED_CSS,
)
from app.services.flashcard_renderer import (
    PREVIEW_MEDIA_AUDIO_TOKEN,
    PREVIEW_MEDIA_DIAGRAM_TOKEN,
    PREVIEW_MEDIA_IMAGE_TOKEN,
    TemplateCompileError,
    render_template_pair,
)
from app.validators import (
    RequestValidationError,
    validate_note_create_request,
    validate_note_patch_request,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.field_def import FieldDef
from models.field_rename_job import FieldRenameJob
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.template import Template


logger = logging.getLogger(__name__)
FIELD_TYPES = {"text", "richtext", "markdown", "image", "audio", "diagram"}
ALLOWED_TEMPLATE_HOTFIX_FIELDS = frozenset(
    {"name", "front_html", "back_html", "shared_css"}
)


def _is_template_content_only_payload(payload: dict[str, Any]) -> bool:
    if not payload:
        return True
    return bool(set(payload.keys()).issubset(ALLOWED_TEMPLATE_HOTFIX_FIELDS))


class ContentApiError(ValueError):
    def __init__(
        self,
        error: str,
        message: str,
        *,
        status: int = 400,
        field: str | None = None,
    ) -> None:
        super().__init__(message)
        self.error = error
        self.status = int(status)
        self.field = field


from sqlalchemy.orm import selectinload


def list_note_types(*, user_id: int) -> dict[str, Any]:
    installed_ids = [
        r[0]
        for r in db.session.query(NoteTypeInstall.installed_note_type_id)
        .filter_by(user_id=user_id)
        .all()
        if r[0]
    ]
    rows = (
        NoteType.query.filter(
            (NoteType.user_id == user_id)
            | (NoteType.id.in_(installed_ids))
        )
        .options(
            selectinload(NoteType.field_defs),
            selectinload(NoteType.templates),
            selectinload(NoteType.owner),
        )
        .order_by(NoteType.name.asc(), NoteType.updated_at.desc())
        .all()
    )
    installed_id_set = {str(note_type_id) for note_type_id in installed_ids}
    return {
        "items": [
            {
                **marketplace_query_service.serialize_note_type(row),
                "is_marketplace_install": str(row.id) in installed_id_set,
            }
            for row in rows
        ]
    }


def get_note_type(*, user_id: int, note_type_id: str) -> dict[str, Any]:
    return marketplace_query_service.serialize_note_type(
        _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    )


def create_note_type(
    *,
    user_id: int,
    admin_mode: bool,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type, message, field = flashcards_share_service.create_note_type(
        user_id=user_id,
        payload=payload,
        is_admin=admin_mode,
    )
    if note_type is None:
        raise ContentApiError(
            "VALIDATION_ERROR",
            message or "Unable to create note type.",
            field=field,
        )
    return marketplace_query_service.serialize_note_type(note_type)


def update_note_type(
    *,
    user_id: int,
    admin_mode: bool,
    note_type_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    requested_name = str(
        payload.get("title") or payload.get("name") or ""
    ).strip()
    if (
        requested_name
        and requested_name != str(note_type.name or "").strip()
        and deck_working_tree_service.note_type_has_shared_release_dependents(
            note_type_id=str(note_type.id),
            owner_user_id=user_id,
        )
    ):
        raise ContentApiError(
            "SHARED_SCHEMA_VERSIONING_REQUIRED",
            "The name of a released shared note type cannot change until note-type metadata is versioned.",
            status=409,
            field="name",
        )
    requested_status = str(payload.get("publish_status") or "").strip().lower()
    if requested_status in flashcards_share_service.PUBLISH_STATUSES_VISIBLE:
        eligibility = flashcards_share_service.get_note_type_publish_eligibility(
            note_type=note_type,
            user_id=user_id,
            is_admin=admin_mode,
        )
        if not eligibility["is_selectable"]:
            raise ContentApiError(
                "CONFLICT",
                str(eligibility["block_reason"]),
                status=409,
                field="publish_status",
            )
    validation_error = flashcards_share_service.apply_note_type_marketplace_payload(
        note_type,
        payload,
        allow_set_official=admin_mode,
        publish_statuses_visible=flashcards_share_service.PUBLISH_STATUSES_VISIBLE,
    )
    if validation_error:
        raise ContentApiError("VALIDATION_ERROR", validation_error)
    _audit(user_id, "note_type.update", {"note_type_id": note_type.id})
    db.session.commit()
    return marketplace_query_service.serialize_note_type(note_type)


def delete_note_type(*, user_id: int, note_type_id: str, purge: bool = False, is_admin: bool = False) -> dict[str, bool]:
    if purge:
        if not is_admin:
            raise ContentApiError("FORBIDDEN", "Only administrators can purge note types.", status=403)
        note_type = db.session.get(NoteType, note_type_id)
        if note_type is None:
            raise ContentApiError("FIELD_NOT_FOUND", "Note type not found.", status=404)

        from models.deck_change_request import DeckChangeRequest
        from models.deck_install import DeckInstall
        from models.deck_marketplace_item import DeckMarketplaceItem
        from models.review_event import ReviewEvent

        # 1. Preserve immutable study history while detaching the purged
        # content dimension. This also keeps imported Anki provenance valid.
        ReviewEvent.query.filter(ReviewEvent.note_type_id == note_type_id).update(
            {ReviewEvent.note_type_id: None},
            synchronize_session=False,
        )

        # 2. Delete all DeckChangeRequests referencing this note type
        DeckChangeRequest.query.filter(DeckChangeRequest.source_note_type_id == note_type_id).delete(synchronize_session=False)

        # 3. Delete all DeckInstalls referencing this note type
        DeckInstall.query.filter(DeckInstall.source_note_type_id == note_type_id).delete(synchronize_session=False)

        # 4. Delete all DeckMarketplaceItems referencing this note type
        DeckMarketplaceItem.query.filter(DeckMarketplaceItem.source_note_type_id == note_type_id).delete(synchronize_session=False)

        # 5. Delete all NoteTypeInstalls where this note type is source or installed
        install_query = NoteTypeInstall.query.filter(
            (NoteTypeInstall.source_note_type_id == note_type_id) |
            (NoteTypeInstall.installed_note_type_id == note_type_id)
        )
        install_rows = install_query.with_for_update().all()
        flashcards_share_service.remove_note_type_install_market_counters(
            install_rows
        )
        install_query.delete(synchronize_session=False)

        # 6. Delete NoteType itself, which cascades
        db.session.delete(note_type)
        _audit(user_id, "note_type.purge", {"note_type_id": note_type_id})
        db.session.commit()
        return {"success": True, "purged": True}

    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    if Note.query.filter_by(note_type_id=note_type.id).count() > 0:
        raise ContentApiError(
            "NOTE_TYPE_HAS_NOTES",
            "Cannot delete note type with existing notes.",
            status=409,
        )
    source_install_count = NoteTypeInstall.query.filter_by(
        source_note_type_id=note_type.id
    ).count()
    has_marketplace_history = (
        str(note_type.publish_status or "").strip().lower() != "private"
        or source_install_count > 0
        or bool(note_type.reviews)
    )
    if has_marketplace_history:
        from datetime import datetime, timezone

        note_type.publish_status = "archived"
        note_type.archived_at = datetime.now(timezone.utc).replace(tzinfo=None)
        _audit(
            user_id,
            "note_type.archive",
            {"note_type_id": note_type.id, "reason": "marketplace_lineage"},
        )
        db.session.commit()
        return {"success": True, "archived": True}

    flashcards_share_service.deactivate_note_type_installs_for_deleted_copy(
        user_id=user_id,
        installed_note_type_id=note_type.id,
    )
    db.session.delete(note_type)
    _audit(user_id, "note_type.delete", {"note_type_id": note_type.id})
    db.session.commit()
    return {"success": True}


def list_fields(*, user_id: int, note_type_id: str) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    rows = (
        FieldDef.query.filter_by(note_type_id=note_type.id)
        .order_by(FieldDef.position.asc())
        .all()
    )
    return {
        "items": [
            marketplace_query_service.serialize_field(row)
            for row in rows
        ]
    }


def create_field(
    *,
    user_id: int,
    note_type_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    name = str(payload.get("name") or "").strip()
    field_type = str(payload.get("field_type") or "text").strip()
    identity_role = payload.get("identity_role")
    if identity_role not in (None, "primary"):
        raise ContentApiError(
            "VALIDATION_ERROR",
            "identity_role must be null or primary.",
            field="identity_role",
        )
    if not name:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Field name is required.",
            field="name",
        )
    if field_type not in FIELD_TYPES:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Unsupported field_type.",
            field="field_type",
        )
    if FieldDef.query.filter_by(note_type_id=note_type.id, name=name).first():
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Field name already exists in this note type.",
            field="name",
        )
    if identity_role == "primary":
        if field_type != "text":
            raise ContentApiError(
                "VALIDATION_ERROR",
                "The identity field must use the text field type.",
                field="field_type",
            )
        if FieldDef.query.filter_by(note_type_id=note_type.id, identity_role="primary").first():
            raise ContentApiError(
                "VALIDATION_ERROR",
                "This note type already has a primary identity field.",
                field="identity_role",
            )
    max_position = (
        db.session.query(db.func.max(FieldDef.position))
        .filter_by(note_type_id=note_type.id)
        .scalar()
    )
    field = FieldDef(
        note_type_id=note_type.id,
        name=name,
        field_type=field_type,
        required=True if identity_role == "primary" else bool(payload.get("required", False)),
        identity_role=identity_role,
        position=(int(max_position) if max_position is not None else -1) + 1,
    )
    db.session.add(field)
    db.session.flush()
    deck_working_tree_service.mark_field_def_changed(
        field_def=field,
        owner_user_id=user_id,
        property_keys={"name", "field_type", "position", "required", "identity_role"},
        operation="add",
    )
    _audit(
        user_id,
        "field.create",
        {"note_type_id": note_type.id, "field_id": field.id, "name": field.name},
    )
    db.session.commit()
    return marketplace_query_service.serialize_field(field)


def update_field(
    *,
    user_id: int,
    note_type_id: str,
    field_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    field = _field(note_type_id=note_type.id, field_id=field_id)
    previous_properties = {
        "name": field.name,
        "field_type": field.field_type,
        "required": bool(field.required),
        "identity_role": field.identity_role,
    }
    old_name = field.name
    new_name = str(payload.get("name") or field.name).strip()
    new_type = str(payload.get("field_type") or field.field_type).strip()
    new_identity_role = payload.get("identity_role", field.identity_role)
    new_required = bool(payload.get("required")) if "required" in payload else bool(field.required)
    if new_identity_role not in (None, "primary"):
        raise ContentApiError(
            "VALIDATION_ERROR",
            "identity_role must be null or primary.",
            field="identity_role",
        )
    if not new_name:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Field name is required.",
            field="name",
        )
    if new_type not in FIELD_TYPES:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Unsupported field_type.",
            field="field_type",
        )
    conflict = FieldDef.query.filter(
        FieldDef.note_type_id == note_type.id,
        FieldDef.name == new_name,
        FieldDef.id != field.id,
    ).first()
    if conflict:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Field name already exists.",
            field="name",
        )
    if new_identity_role == "primary":
        if new_type != "text":
            raise ContentApiError(
                "VALIDATION_ERROR",
                "The identity field must use the text field type.",
                field="field_type",
            )
        if not new_required:
            raise ContentApiError(
                "VALIDATION_ERROR",
                "The identity field must be required.",
                field="required",
            )
        identity_conflict = FieldDef.query.filter(
            FieldDef.note_type_id == note_type.id,
            FieldDef.identity_role == "primary",
            FieldDef.id != field.id,
        ).first()
        if identity_conflict:
            raise ContentApiError(
                "VALIDATION_ERROR",
                "This note type already has a primary identity field.",
                field="identity_role",
            )
    field.field_type = new_type
    field.required = new_required
    field.identity_role = new_identity_role

    job_payload = None
    if old_name != new_name:
        job = _rename_field_values(
            user_id=user_id,
            note_type=note_type,
            field=field,
            old_name=old_name,
            new_name=new_name,
        )
        field.name = new_name
        job_payload = {
            "job_id": job.id,
            "status": job.status,
            "processed_notes": job.processed_notes,
        }
    current_properties = {
        "name": field.name,
        "field_type": field.field_type,
        "required": bool(field.required),
        "identity_role": field.identity_role,
    }
    changed_properties = {
        key
        for key, value in current_properties.items()
        if previous_properties.get(key) != value
    }
    if changed_properties:
        deck_working_tree_service.mark_field_def_changed(
            field_def=field,
            owner_user_id=user_id,
            property_keys=changed_properties,
        )
    _audit(
        user_id,
        "field.update",
        {
            "note_type_id": note_type.id,
            "field_id": field.id,
            "old_name": old_name,
            "new_name": field.name,
        },
    )
    db.session.commit()
    result: dict[str, Any] = {
        "field": marketplace_query_service.serialize_field(field)
    }
    if job_payload:
        result["rename_job"] = job_payload
    return result


def delete_field(
    *,
    user_id: int,
    note_type_id: str,
    field_id: str,
) -> dict[str, bool]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    field = _field(note_type_id=note_type.id, field_id=field_id)
    if field.identity_role == "primary":
        raise ContentApiError(
            "IDENTITY_FIELD_REQUIRED",
            "Clear or reassign the primary identity field before deleting it.",
            status=409,
        )
    if deck_working_tree_service.note_type_has_shared_release_dependents(
        note_type_id=note_type.id,
        owner_user_id=user_id,
    ):
        raise ContentApiError(
            "SHARED_ENTITY_RETIRE_REQUIRED",
            "Published shared fields must be retired through a release-safe operation.",
            status=409,
        )
    for note in Note.query.filter_by(
        note_type_id=note_type.id,
        user_id=user_id,
    ).all():
        values = dict(note.field_values or {})
        values.pop(field.name, None)
        note.field_values = values
    db.session.delete(field)
    _audit(
        user_id,
        "field.delete",
        {
            "note_type_id": note_type.id,
            "field_id": field.id,
            "field_name": field.name,
        },
    )
    db.session.commit()
    return {"success": True}


def reorder_fields(
    *,
    user_id: int,
    note_type_id: str,
    payload: object,
) -> dict[str, bool]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    if not isinstance(payload, list):
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Payload must be a list.",
            field="body",
        )
    fields = FieldDef.query.filter_by(note_type_id=note_type.id).all()
    field_map = {field.id: field for field in fields}
    if len(payload) != len(fields):
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Reorder payload must include all fields.",
            field="body",
        )
    seen: set[str] = set()
    for row in payload:
        if not isinstance(row, dict):
            raise ContentApiError(
                "VALIDATION_ERROR",
                "Invalid reorder payload.",
                field="body",
            )
        field_id = row.get("id")
        if field_id not in field_map:
            raise ContentApiError(
                "VALIDATION_ERROR",
                f"Unknown field id: {field_id}",
                field="body",
            )
        if field_id in seen:
            raise ContentApiError(
                "VALIDATION_ERROR",
                "Duplicate field id in reorder payload.",
                field="body",
            )
        seen.add(field_id)
        try:
            field_map[field_id].position = int(row.get("position"))
        except (TypeError, ValueError) as exc:
            raise ContentApiError(
                "VALIDATION_ERROR",
                f"Invalid position for field {field_id}",
                field="body",
            ) from exc
    for field in fields:
        deck_working_tree_service.mark_field_def_changed(
            field_def=field,
            owner_user_id=user_id,
            property_keys={"position"},
        )
    _audit(user_id, "field.reorder", {"note_type_id": note_type.id})
    db.session.commit()
    return {"success": True}


def list_templates(*, user_id: int, note_type_id: str) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    rows = (
        Template.query.filter_by(note_type_id=note_type.id)
        .order_by(Template.position.asc())
        .all()
    )
    return {
        "items": [
            marketplace_query_service.serialize_template(row)
            for row in rows
        ]
    }


def create_template(
    *,
    user_id: int,
    note_type_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    _ensure_version_safe_template_mutation(
        note_type=note_type,
        owner_user_id=user_id,
    )
    template, error = flashcards_share_service.create_template(
        note_type_id=note_type.id,
        user_id=user_id,
        payload=payload,
    )
    if template is None:
        raise ContentApiError(
            "VALIDATION_ERROR",
            error or "Unable to create template.",
        )
    return marketplace_query_service.serialize_template(template)


def update_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    template = _template(note_type_id=note_type.id, template_id=template_id)
    is_content_only = _is_template_content_only_payload(payload)
    _ensure_version_safe_template_mutation(
        note_type=note_type,
        owner_user_id=user_id,
        allow_released_template_content_hotfix=is_content_only,
    )
    if "name" in payload:
        template.name = str(payload.get("name") or "").strip() or template.name
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
        raise ContentApiError(
            "TEMPLATE_COMPILE_ERROR",
            str(exc),
            field="front_html",
        ) from exc
    _audit(
        user_id,
        "template.update",
        {"note_type_id": note_type.id, "template_id": template.id},
    )
    db.session.commit()
    return marketplace_query_service.serialize_template(template)


def reset_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    template = _template(note_type_id=note_type.id, template_id=template_id)
    _ensure_version_safe_template_mutation(
        note_type=note_type,
        owner_user_id=user_id,
    )
    template.front_html = LEGACY_FRONT_TEMPLATE.strip()
    template.back_html = LEGACY_BACK_TEMPLATE.strip()
    template.shared_css = LEGACY_SHARED_CSS.strip()
    db.session.commit()
    return marketplace_query_service.serialize_template(template)


def delete_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
) -> dict[str, bool]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    template = _template(note_type_id=note_type.id, template_id=template_id)
    _ensure_version_safe_template_mutation(
        note_type=note_type,
        owner_user_id=user_id,
    )
    if template.is_default:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Cannot delete default template.",
            status=409,
        )
    if Template.query.filter_by(note_type_id=note_type.id).count() <= 1:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "A note type requires at least one template.",
            status=409,
        )
    Card.query.filter_by(template_id=template.id).delete()
    db.session.delete(template)
    _audit(
        user_id,
        "template.delete",
        {"note_type_id": note_type.id, "template_id": template.id},
    )
    db.session.commit()
    return {"success": True}


def preview_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    template = _template(note_type_id=note_type.id, template_id=template_id)
    raw_sample = payload.get("use_sample_data", False)
    use_sample = bool(raw_sample)
    if isinstance(raw_sample, str):
        use_sample = raw_sample.strip().lower() in {"1", "true", "yes", "on"}
    preview_template_obj = SimpleNamespace(
        id=template.id,
        front_html=str(payload.get("front_html") or "")
        if "front_html" in payload
        else template.front_html,
        back_html=str(payload.get("back_html") or "")
        if "back_html" in payload
        else template.back_html,
        shared_css=str(payload.get("shared_css") or "")
        if "shared_css" in payload
        else template.shared_css,
        updated_at=template.updated_at,
    )
    if use_sample:
        values = _preview_sample_values(note_type.field_defs)
        media_assets = []
        preview_key = f"sample:{note_type.id}"
    else:
        note_id = str(payload.get("note_id") or "").strip()
        note = None
        if note_id:
            note = Note.query.filter_by(
                id=note_id,
                user_id=user_id,
                note_type_id=note_type.id,
            ).first()
        if note is None:
            note = (
                Note.query.filter_by(
                    note_type_id=note_type.id,
                    user_id=user_id,
                )
                .order_by(Note.created_at.asc())
                .first()
            )
        values = note.field_values or {} if note else {}
        media_assets = note.media_assets if note else []
        preview_key = note.id if note else "empty-note"
    try:
        return render_template_pair(
            template=preview_template_obj,
            field_defs=note_type.field_defs,
            field_values=values,
            media_assets=media_assets,
            preview_note_key=preview_key,
        )
    except TemplateCompileError as exc:
        raise ContentApiError(
            "TEMPLATE_COMPILE_ERROR",
            str(exc),
            field="front_html",
        ) from exc


def preview_raw_template(
    *,
    payload: dict[str, Any],
) -> dict[str, Any]:
    front_html = str(payload.get("front_html") or "")
    back_html = str(payload.get("back_html") or "")
    shared_css = str(payload.get("shared_css") or "")
    raw_fields = payload.get("fields") or []
    raw_field_values = payload.get("field_values") or {}

    if not isinstance(raw_fields, list) or len(raw_fields) > 100:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "fields must be a list with at most 100 entries.",
            field="fields",
        )
    if not isinstance(raw_field_values, dict):
        raise ContentApiError(
            "VALIDATION_ERROR",
            "field_values must be an object.",
            field="field_values",
        )

    field_defs = []
    sample_values: dict[str, Any] = {}
    total_supplied_chars = 0

    for idx, f in enumerate(raw_fields):
        name = str(f if isinstance(f, str) else (f.get("name", "") if isinstance(f, dict) else "")).strip()
        if not name:
            continue
        field_type = str(f.get("field_type", "text")) if isinstance(f, dict) else "text"

        if isinstance(f, str):
            lower = name.lower()
            if any(k in lower for k in ["audio", "sound", "voice"]):
                field_type = "audio"
            elif any(k in lower for k in ["image", "pic", "photo", "img"]):
                field_type = "image"
            elif any(k in lower for k in ["back", "meaning", "example", "definition"]):
                field_type = "richtext"

        f_def = SimpleNamespace(id=f"f_{idx}", name=name, field_type=field_type, position=idx)
        field_defs.append(f_def)

        supplied_value = raw_field_values.get(name)
        if supplied_value is not None:
            if not isinstance(supplied_value, str) or len(supplied_value) > 100_000:
                raise ContentApiError(
                    "VALIDATION_ERROR",
                    f"field_values.{name} must be a string no longer than 100000 characters.",
                    field=f"field_values.{name}",
                )
            total_supplied_chars += len(supplied_value)
            if total_supplied_chars > 250_000:
                raise ContentApiError(
                    "VALIDATION_ERROR",
                    "field_values is too large for preview.",
                    field="field_values",
                )
            sample_values[name] = supplied_value
        elif field_type == "image":
            sample_values[name] = PREVIEW_MEDIA_IMAGE_TOKEN
        elif field_type == "audio":
            sample_values[name] = PREVIEW_MEDIA_AUDIO_TOKEN
        else:
            sample_values[name] = f"{{{{{name}}}}}"

    preview_template_obj = SimpleNamespace(
        id="raw_preview",
        front_html=front_html,
        back_html=back_html,
        shared_css=shared_css,
        updated_at="",
    )

    preview_hash = hashlib.sha256(
        (front_html + back_html + shared_css + json.dumps(sample_values)).encode("utf-8")
    ).hexdigest()[:16]

    try:
        return render_template_pair(
            template=preview_template_obj,
            field_defs=field_defs,
            field_values=sample_values,
            media_assets=[],
            preview_note_key=f"raw_preview:{preview_hash}",
        )
    except TemplateCompileError as exc:
        raise ContentApiError(
            "TEMPLATE_COMPILE_ERROR",
            str(exc),
            field="front_html",
        ) from exc



def list_notes(
    *,
    user_id: int,
    query_args: Mapping[str, Any],
) -> dict[str, Any]:
    note_type_id = str(query_args.get("note_type_id") or "").strip()
    deck_id_raw = str(query_args.get("deck_id") or "").strip()
    try:
        page = max(1, int(query_args.get("page") or "1"))
        per_page = max(1, min(100, int(query_args.get("per_page") or "20")))
    except (TypeError, ValueError) as exc:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "page and per_page must be integers.",
            field="page",
        ) from exc
    query = Note.query.filter_by(user_id=user_id)
    if note_type_id:
        query = query.filter(Note.note_type_id == note_type_id)
    if deck_id_raw:
        try:
            query = query.filter(Note.deck_id == int(deck_id_raw))
        except ValueError as exc:
            raise ContentApiError(
                "VALIDATION_ERROR",
                "deck_id must be an integer.",
                field="deck_id",
            ) from exc
    pagination = query.order_by(Note.updated_at.desc()).paginate(
        page=page,
        per_page=per_page,
        error_out=False,
    )
    return {
        "items": [_serialize_note(note) for note in pagination.items],
        "page": page,
        "per_page": per_page,
        "total": pagination.total,
    }


def get_note(*, user_id: int, note_id: str) -> dict[str, Any]:
    note = _owned_note(user_id=user_id, note_id=note_id)
    payload = _serialize_note(note)
    payload["media_assets"] = [
        {
            "id": asset.id,
            "field_name": asset.field_name,
            "filename": asset.filename,
            "mime_type": asset.mime_type,
            "url": f"/media/proxy/{asset.id}",
        }
        for asset in note.media_assets
    ]
    return payload


def create_note(
    *,
    user_id: int,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note_type_id = str(payload.get("note_type_id") or "").strip()
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    try:
        validated = validate_note_create_request(
            note_type=note_type,
            payload=payload,
        )
    except RequestValidationError as exc:
        raise _validation_error(exc) from exc
    consistency_error = flashcards_share_service.validate_note_type_consistency_for_deck(
        deck_id=validated.deck_id,
        note_type_id=note_type.id,
        user_id=user_id,
    )
    if consistency_error:
        raise ContentApiError(
            "VALIDATION_ERROR",
            consistency_error,
            field="deck_id",
        )
    note = Note(
        note_type_id=note_type.id,
        user_id=user_id,
        deck_id=validated.deck_id,
        field_values=validated.field_values,
        tags=validated.tags,
    )
    db.session.add(note)
    db.session.flush()
    from app.services import media_staging_service
    committed_values = media_staging_service.commit_all_staged_urls_in_field_values(
        user_id=user_id,
        note_id=note.id,
        field_values=note.field_values,
    )
    if committed_values != note.field_values:
        note.field_values = committed_values
        db.session.flush()
    _create_cards(note)
    deck_working_tree_service.mark_note_fields_changed(
        note=note,
        field_names=(note.field_values or {}).keys(),
        operation="add",
    )
    flashcards_share_service.touch_note_type_install_usage(
        user_id=user_id,
        installed_note_type_id=note.note_type_id,
    )
    _refresh_source_note_type_stats(
        user_id=user_id,
        installed_note_type_id=note.note_type_id,
    )
    _audit(
        user_id,
        "note.create",
        {"note_id": note.id, "note_type_id": note.note_type_id},
    )
    db.session.flush()
    cards = Card.query.filter_by(note_id=note.id).order_by(Card.id.asc()).all()
    card_ids = [str(card.id) for card in cards]
    db.session.commit()
    return {
        "id": note.id,
        "deck_id": note.deck_id,
        "note_type_id": note.note_type_id,
        "field_values": note.field_values,
        "tags": note.tags,
        "card_ids": card_ids,
        "first_card_id": card_ids[0] if card_ids else None,
    }


def update_note(
    *,
    user_id: int,
    note_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    note = _owned_note(user_id=user_id, note_id=note_id)
    original_deck_id = note.deck_id
    note_type = _owned_note_type(
        user_id=user_id,
        note_type_id=note.note_type_id,
    )
    try:
        validated = validate_note_patch_request(
            note_type=note_type,
            payload=payload,
            current_values=dict(note.field_values or {}),
            note_media_ids=_note_media_refs(note),
        )
    except RequestValidationError as exc:
        raise _validation_error(exc) from exc
    if (
        validated.update_deck
        and original_deck_id != validated.deck_id
        and deck_working_tree_service.note_has_shared_release_dependents(note)
    ):
        raise ContentApiError(
            "SHARED_ENTITY_RETIRE_REQUIRED",
            (
                "A released shared note cannot move decks until release-aware "
                "membership moves are supported."
            ),
            status=409,
            field="deck_id",
        )
    if validated.update_tags:
        _ensure_version_safe_note_tags_mutation(
            note=note,
            next_tags=validated.tags,
        )
    if validated.field_updates:
        values = dict(note.field_values or {})
        values.update(validated.field_updates)
        from app.services import media_staging_service
        values = media_staging_service.commit_all_staged_urls_in_field_values(
            user_id=user_id,
            note_id=note.id,
            field_values=values,
        )
        note.field_values = values
    if validated.update_tags:
        note.tags = validated.tags
    if validated.update_deck:
        note.deck_id = validated.deck_id
    consistency_error = flashcards_share_service.validate_note_type_consistency_for_deck(
        deck_id=note.deck_id,
        note_type_id=note.note_type_id,
        user_id=user_id,
        exclude_note_id=note.id,
    )
    if consistency_error:
        db.session.rollback()
        raise ContentApiError(
            "VALIDATION_ERROR",
            consistency_error,
            field="deck_id",
        )
    deck_changed = validated.update_deck and original_deck_id != note.deck_id
    if validated.field_updates and not deck_changed:
        deck_working_tree_service.mark_note_fields_changed(
            note=note,
            field_names=validated.field_updates.keys(),
        )
    if deck_changed:
        all_field_names = list((note.field_values or {}).keys())
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=[
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "remove",
                    "deck_id": original_deck_id,
                },
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "add",
                    "deck_id": note.deck_id,
                },
            ],
        )
    _audit(user_id, "note.update", {"note_id": note.id})
    db.session.commit()
    return {
        "id": note.id,
        "field_values": note.field_values,
        "tags": note.tags,
    }


def delete_note(*, user_id: int, note_id: str) -> dict[str, bool]:
    note = _owned_note(user_id=user_id, note_id=note_id)
    if deck_working_tree_service.note_has_shared_release_dependents(note):
        raise ContentApiError(
            "SHARED_ENTITY_RETIRE_REQUIRED",
            "Published shared notes cannot be hard-deleted because learner history must be preserved.",
            status=409,
        )
    deck_working_tree_service.mark_note_field_batches_changed(
        mutations=[
            {
                "note": note,
                "field_names": (note.field_values or {}).keys(),
                "operation": "remove",
            }
        ],
    )
    db.session.delete(note)
    _audit(user_id, "note.delete", {"note_id": note.id})
    db.session.commit()
    return {"success": True}


def _owned_note_type(*, user_id: int, note_type_id: str) -> NoteType:
    row = NoteType.query.filter_by(id=note_type_id, user_id=user_id).first()
    if row is None:
        raise ContentApiError(
            "FIELD_NOT_FOUND",
            "Note type not found.",
            status=404,
        )
    return row


def _ensure_version_safe_template_mutation(
    *,
    note_type: NoteType,
    owner_user_id: int,
    allow_released_template_content_hotfix: bool = False,
) -> None:
    """Prevent template/card changes from bypassing immutable deck releases.

    Release deltas currently version field definitions and note-field values.
    Templates also determine the physical Card rows, so mutating them while a
    released lineage has learners would otherwise leak unpublished owner work
    into installed decks and could destroy CardProgress history.  Keep the
    operation closed until template/card changes have their own release-safe
    representation.

    TEMPORARY (#138 / P3 compatibility):
    Allows the source author to hotfix existing template presentation content
    (front_html, back_html, shared_css, name) in-place without deleting or
    recreating physical Cards, pending full P3 presentation versioning (#137).
    """

    if not deck_working_tree_service.note_type_has_shared_release_dependents(
        note_type_id=str(note_type.id),
        owner_user_id=owner_user_id,
    ):
        return

    is_source_author = int(note_type.user_id) == int(owner_user_id)
    if is_source_author and allow_released_template_content_hotfix:
        # TEMPORARY: P3/#137 compatibility hotfix path.
        # Overwrites the live compatibility Template row in place.
        return

    raise ContentApiError(
        "SHARED_SCHEMA_VERSIONING_REQUIRED",
        (
            "Templates used by a released shared deck cannot be changed yet. "
            "Create a new note type or wait for template-aware releases so "
            "installed card and study history remain stable."
        ),
        status=409,
        field="template",
    )


def _ensure_version_safe_note_tags_mutation(
    *,
    note: Note,
    next_tags: list[Any] | None,
) -> None:
    if list(note.tags or []) == list(next_tags or []):
        return
    if not deck_working_tree_service.note_has_shared_release_dependents(note):
        return
    raise ContentApiError(
        "SHARED_NOTE_METADATA_VERSIONING_REQUIRED",
        (
            "Tags on a released shared note cannot change until note metadata "
            "is included in deck releases."
        ),
        status=409,
        field="tags",
    )


def _owned_note(*, user_id: int, note_id: str) -> Note:
    row = Note.query.filter_by(id=note_id, user_id=user_id).first()
    if row is None:
        raise ContentApiError(
            "FIELD_NOT_FOUND",
            "Note not found.",
            status=404,
        )
    return row


def _field(*, note_type_id: str, field_id: str) -> FieldDef:
    row = FieldDef.query.filter_by(
        id=field_id,
        note_type_id=note_type_id,
    ).first()
    if row is None:
        raise ContentApiError(
            "FIELD_NOT_FOUND",
            "Field not found.",
            status=404,
        )
    return row


def _template(*, note_type_id: str, template_id: str) -> Template:
    row = Template.query.filter_by(
        id=template_id,
        note_type_id=note_type_id,
    ).first()
    if row is None:
        raise ContentApiError(
            "FIELD_NOT_FOUND",
            "Template not found.",
            status=404,
        )
    return row


def _audit(user_id: int | None, action: str, payload: dict[str, Any]) -> None:
    db.session.add(AuditLog(user_id=user_id, action=action, payload=payload))


def _rename_field_values(
    *,
    user_id: int,
    note_type: NoteType,
    field: FieldDef,
    old_name: str,
    new_name: str,
) -> FieldRenameJob:
    job = FieldRenameJob(
        note_type_id=note_type.id,
        user_id=user_id,
        field_def_id=field.id,
        old_name=old_name,
        new_name=new_name,
        status="running",
        total_notes=Note.query.filter_by(
            note_type_id=note_type.id,
            user_id=user_id,
        ).count(),
        processed_notes=0,
    )
    db.session.add(job)
    db.session.flush()
    try:
        for note in Note.query.filter_by(
            note_type_id=note_type.id,
            user_id=user_id,
        ).all():
            values = dict(note.field_values or {})
            if old_name in values and new_name not in values:
                values[new_name] = values.pop(old_name)
            elif old_name in values:
                values.pop(old_name)
            note.field_values = values
            job.processed_notes += 1
        job.status = "completed"
    except Exception as exc:  # pragma: no cover
        job.status = "failed"
        job.error_message = str(exc)
        logger.exception("Field rename job failed: %s", job.id)
    return job


def _preview_sample_values(field_defs: list[FieldDef]) -> dict[str, Any]:
    values: dict[str, Any] = {}
    for field_def in field_defs:
        if field_def.field_type == "image":
            values[field_def.name] = PREVIEW_MEDIA_IMAGE_TOKEN
        elif field_def.field_type == "audio":
            values[field_def.name] = PREVIEW_MEDIA_AUDIO_TOKEN
        elif field_def.field_type == "diagram":
            values[field_def.name] = PREVIEW_MEDIA_DIAGRAM_TOKEN
        else:
            values[field_def.name] = field_def.name
    return values


def _serialize_note(note: Note) -> dict[str, Any]:
    return {
        "id": note.id,
        "note_type_id": note.note_type_id,
        "deck_id": note.deck_id,
        "field_values": note.field_values or {},
        "tags": note.tags or [],
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def _create_cards(note: Note) -> None:
    templates = (
        Template.query.filter_by(note_type_id=note.note_type_id)
        .order_by(Template.position.asc())
        .all()
    )
    for template in templates:
        db.session.add(Card(note=note, note_id=note.id, template_id=template.id))


def _refresh_source_note_type_stats(
    *,
    user_id: int,
    installed_note_type_id: str,
) -> None:
    installs = NoteTypeInstall.query.filter_by(
        user_id=user_id,
        installed_note_type_id=installed_note_type_id,
    ).all()
    for install in installs:
        source = db.session.get(NoteType, install.source_note_type_id)
        if source:
            flashcards_share_service.recompute_note_type_market_stats(
                source,
                note_type_active_note_threshold=3,
                note_type_active_review_threshold=3,
                note_type_active_days_threshold=3,
            )


def _note_media_refs(note: Note):
    from app.services.media_field_codec import build_media_reference_lookup

    return build_media_reference_lookup(note.media_assets or [])


def _validation_error(exc: RequestValidationError) -> ContentApiError:
    return ContentApiError(
        exc.code,
        str(exc),
        status=exc.status,
        field=exc.field,
    )
