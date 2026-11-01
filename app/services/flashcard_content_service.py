"""Application services for flashcard note types, templates, fields, and notes."""

from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import dataclass
from functools import wraps
from types import SimpleNamespace
from typing import Any, Mapping

from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.services import (
    deck_working_tree_service,
    flashcards_share_service,
    marketplace_query_service,
    study_progress_lifecycle_mirror_service,
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
from app.services.note_value_precondition_service import check_note_write_preconditions, note_revision_payload
from app.validators import (
    RequestValidationError,
    validate_note_create_request,
    validate_note_patch_request,
)
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.field_def import FieldDef
from models.field_types import ARRAY_FIELD_TYPE, FIELD_TYPES
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.study_application import StudyApplication
from models.study_progress_subject import StudyProgressSubject
from models.template import Template


logger = logging.getLogger(__name__)
ALLOWED_TEMPLATE_HOTFIX_FIELDS = frozenset(
    {"name", "front_html", "back_html", "shared_css", "change_note"}
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
from app.services.media_field_codec import store_media_url


def list_note_types(*, user_id: int, compact: bool = False, summary: bool = False) -> dict[str, Any]:
    if summary:
        from app.repositories.note_type_summary_repository import list_summaries
        return {"items": list_summaries(user_id=user_id)}
    installed_ids = [
        r[0]
        for r in db.session.query(NoteTypeInstall.installed_note_type_id)
        .filter_by(user_id=user_id)
        .all()
        if r[0]
    ]
    query = NoteType.query.filter(
        (NoteType.user_id == user_id)
        | (NoteType.id.in_(installed_ids))
    )
    if compact:
        rows = (
            query.options(selectinload(NoteType.field_defs))
            .order_by(NoteType.name.asc(), NoteType.updated_at.desc())
            .all()
        )
    else:
        rows = (
            query.options(
                selectinload(NoteType.field_defs),
                selectinload(NoteType.study_applications).selectinload(StudyApplication.template),
                selectinload(NoteType.owner),
            )
            .order_by(NoteType.name.asc(), NoteType.updated_at.desc())
            .all()
        )
    installed_id_set = {str(note_type_id) for note_type_id in installed_ids}
    if compact:
        return {
            "items": [
                {
                    "id": row.id,
                    "name": row.name,
                    "title": row.name,
                    "is_marketplace_install": str(row.id) in installed_id_set,
                    "field_defs": [
                        marketplace_query_service.serialize_field(field)
                        for field in sorted(row.field_defs, key=lambda item: item.position)
                    ],
                }
                for row in rows
            ]
        }
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


@dataclass(frozen=True)
class _NoteTypePurgeScope:
    note_ids: tuple[str, ...]
    card_ids: tuple[str, ...]
    learner_user_ids: tuple[int, ...]


def _note_type_purge_scope(
    note_type: NoteType, *, current_read: bool = False
) -> _NoteTypePurgeScope:
    """Discover content and learners referenced by study or install rows."""
    from models.deck_install import DeckInstall
    from models.deck_marketplace_item import DeckMarketplaceItem
    from models.review_event import ReviewEvent
    from models.study_session import StudySession
    from models.study_session_card import StudySessionCard

    def read(query):
        # A second plain SELECT would reuse MySQL's REPEATABLE READ snapshot.
        return query.with_for_update() if current_read else query

    note_query = (
        db.session.query(Note.id, Note.user_id)
        .filter(Note.note_type_id == note_type.id)
        .order_by(Note.id.asc())
    )
    note_rows = read(note_query).all()
    note_ids = tuple(str(row.id) for row in note_rows)
    card_ids_found = []
    for offset in range(0, len(note_ids), 500):
        card_query = db.session.query(Card.id).filter(
            Card.note_id.in_(note_ids[offset : offset + 500])
        )
        card_ids_found.extend(str(row.id) for row in read(card_query).all())
    card_ids = tuple(sorted(card_ids_found))
    learner_ids = {int(note_type.user_id)}
    learner_ids.update(int(row.user_id) for row in note_rows)

    def collect_learner_ids(query) -> None:
        learner_ids.update(int(row[0]) for row in read(query.distinct()).all())

    for query in (
        db.session.query(NoteTypeInstall.user_id).filter(
            (NoteTypeInstall.source_note_type_id == note_type.id)
            | (NoteTypeInstall.installed_note_type_id == note_type.id)
        ),
        db.session.query(DeckInstall.user_id).filter(
            DeckInstall.source_note_type_id == note_type.id
        ),
        db.session.query(DeckInstall.user_id)
        .join(DeckMarketplaceItem, DeckInstall.deck_item_id == DeckMarketplaceItem.id)
        .filter(DeckMarketplaceItem.source_note_type_id == note_type.id),
    ):
        collect_learner_ids(query)

    collect_learner_ids(
        db.session.query(StudySession.user_id)
        .join(StudySessionCard, StudySessionCard.session_id == StudySession.id)
        .filter(StudySessionCard.note_type_id == note_type.id)
    )

    # A shared source Card can have progress owned by a different learner.
    # Also include a subject even when its live Note pointer was detached.
    for offset in range(0, len(note_ids), 500):
        note_chunk = note_ids[offset : offset + 500]
        subject_query = (
            db.session.query(StudyProgressSubject.learner_user_id)
            .filter(
                (StudyProgressSubject.live_note_id.in_(note_chunk))
                | StudyProgressSubject.logical_note_key.in_(
                    [note_id.encode("utf-8") for note_id in note_chunk]
                )
            )
        )
        collect_learner_ids(subject_query)
    from app.repositories.study_authority_repository import projection_is_live

    projection_live = projection_is_live(db.session)
    for offset in range(0, len(card_ids), 500):
        card_chunk = card_ids[offset : offset + 500]
        pass
        collect_learner_ids(
            db.session.query(StudySession.user_id)
            .join(StudySessionCard, StudySessionCard.session_id == StudySession.id)
            .filter(StudySessionCard.card_id.in_(card_chunk))
        )
    collect_learner_ids(
        db.session.query(ReviewEvent.user_id).filter(
            ReviewEvent.note_type_id == note_type.id
        )
    )
    return _NoteTypePurgeScope(
        note_ids=note_ids,
        card_ids=card_ids,
        learner_user_ids=tuple(sorted(learner_ids)),
    )


def _rollback_content_delete_on_error(mutation):
    @wraps(mutation)
    def guarded(*args, **kwargs):
        try:
            return mutation(*args, **kwargs)
        except StudyAuthorityFenceError as exc:
            db.session.rollback()
            raise ContentApiError(exc.code, str(exc), status=409) from exc
        except Exception:
            db.session.rollback()
            raise
    return guarded


@_rollback_content_delete_on_error
def delete_note_type(*, user_id: int, note_type_id: str, purge: bool = False, is_admin: bool = False) -> dict[str, bool]:
    if purge:
        if not is_admin:
            raise ContentApiError("FORBIDDEN", "Only administrators can purge note types.", status=403)
        # Purge spans owner content, installed copies and shared Card progress.
        # Take all learner fences before locking/deleting content or provenance.
        try:
            with db.session.no_autoflush:
                note_type = db.session.get(NoteType, note_type_id)
                if note_type is None:
                    raise ContentApiError(
                        "FIELD_NOT_FOUND", "Note type not found.", status=404
                    )
                scope = _note_type_purge_scope(note_type)
            authority_routes = []
            for learner_id in scope.learner_user_ids:
                route = lock_study_authority_route(
                    db.session,
                    learner_user_id=learner_id,
                    allow_note_authority=True,
                )
                authority_routes.append(route)
            locked_note_type = (
                db.session.query(NoteType)
                .filter(NoteType.id == note_type_id)
                .with_for_update()
                .populate_existing()
                .one_or_none()
            )
            if locked_note_type is None:
                raise StudyAuthorityFenceError(
                    "PURGE_SCOPE_CHANGED", "Note type changed during purge admission."
                )
            if _note_type_purge_scope(locked_note_type, current_read=True) != scope:
                raise StudyAuthorityFenceError(
                    "PURGE_SCOPE_CHANGED",
                    "Note-type purge scope changed while learner routes were locked.",
                )
        except StudyAuthorityFenceError as exc:
            db.session.rollback()
            raise ContentApiError(exc.code, str(exc), status=409) from exc

        from models.deck_change_request import DeckChangeRequest
        from models.deck_install import DeckInstall
        from models.deck_marketplace_item import DeckMarketplaceItem
        from models.review_event import ReviewEvent
        from app.services.study_content_delete_service import prepare_content_delete, finalize_content_delete

        lifecycle_plan = prepare_content_delete(db.session, routes=authority_routes,
            card_ids=scope.card_ids, note_ids=scope.note_ids)

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
        if scope.card_ids:
            pass  # NOTE lifecycle state is handled by the fenced deletion plan.
        finalize_content_delete(
            lifecycle_plan,
            source_path="flashcards.note_type_purge",
            operation_key=f"note-type-purge:{note_type_id}",
        )
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
    if (new_type == ARRAY_FIELD_TYPE and field.field_type != ARRAY_FIELD_TYPE) or (
        field.field_type == ARRAY_FIELD_TYPE and new_type != ARRAY_FIELD_TYPE
    ):
        raise ContentApiError(
            "FIELD_TYPE_REQUIRES_CONVERSION",
            "Direct type changes involving array fields are not permitted.",
            status=409,
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

    if old_name != new_name:
        # Freeze the legacy name->ID map before changing field names. Reusable
        # bindings survive rename; stored Mustache sources stay byte-identical.
        from app.services.template_library_service import initialize_legacy_bindings
        initialize_legacy_bindings(note_type)
        field.name = new_name
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
    from app.services.note_base_context import published_base_enabled
    if not published_base_enabled() and deck_working_tree_service.note_type_has_shared_release_dependents(
        note_type_id=note_type.id,
        owner_user_id=user_id,
    ):
        raise ContentApiError(
            "SHARED_ENTITY_RETIRE_REQUIRED",
            "Published shared fields must be retired through a release-safe operation.",
            status=409,
        )
    if published_base_enabled():
        from datetime import datetime, timezone
        field.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        deck_working_tree_service.mark_field_def_changed(field_def=field,
            owner_user_id=user_id, property_keys=["deleted_at"], operation="remove")
    else:
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
    # Preserve the compatibility list DTO; input schema/bindings are exposed by
    # library/application APIs. Order/default/membership still come from use.
    items = []
    seen_template_ids = set()
    for item in marketplace_query_service.serialize_note_type_templates(note_type):
        if item["id"] in seen_template_ids:
            continue
        seen_template_ids.add(item["id"])
        items.append({key: value for key, value in item.items()
                      if key not in {"input_schema", "input_bindings"}})
    template_ids = [str(item["id"]) for item in items]
    note_counts: dict[str, int] = {}
    if template_ids:
        note_counts = {
            str(template_id): int(count or 0)
            for template_id, count in db.session.query(
                Card.template_id,
                db.func.count(db.distinct(Card.note_id)),
            )
            .filter(
                Card.template_id.in_(template_ids),
                Card.note.has(db.and_(Note.note_type_id == note_type.id, Note.user_id == int(user_id))),
            )
            .group_by(Card.template_id)
            .all()
        }
    return {
        "items": [
            {
                **item,
                "note_count": note_counts.get(str(item["id"]), 0),
            }
            for item in items
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
    # A new Template sibling writes no learner progress (ADR P10 §2.3).
    template, error = flashcards_share_service.create_template(
        note_type_id=note_type.id,
        user_id=user_id,
        payload=payload,
        commit=False,
    )
    if template is None:
        db.session.rollback()
        raise ContentApiError(
            "VALIDATION_ERROR",
            error or "Unable to create template.",
        )
    db.session.commit()
    return _serialize_attached_template(template, note_type_id=note_type.id)


def update_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    from app.services.template_version_service import (
        TemplateVersionError, mark_template_version, validate_change_note,
    )
    try:
        change_note = validate_change_note(payload)
    except TemplateVersionError as exc:
        raise ContentApiError(exc.code, str(exc), status=exc.status, field=exc.field) from exc
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    template = _template(note_type_id=note_type.id, template_id=template_id)
    is_content_only = _is_template_content_only_payload(payload)
    _ensure_version_safe_template_mutation(
        note_type=note_type,
        owner_user_id=user_id,
        allow_released_template_content_hotfix=is_content_only,
    )
    mark_template_version(template, origin="edit", actor_user_id=user_id, change_note=change_note)
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
    return _serialize_attached_template(template, note_type_id=note_type.id)


def reset_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
) -> dict[str, Any]:
    from app.services.template_version_service import mark_template_version
    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    template = _template(note_type_id=note_type.id, template_id=template_id)
    _ensure_version_safe_template_mutation(
        note_type=note_type,
        owner_user_id=user_id,
    )
    mark_template_version(template, origin="reset", actor_user_id=user_id)
    template.front_html = LEGACY_FRONT_TEMPLATE.strip()
    template.back_html = LEGACY_BACK_TEMPLATE.strip()
    template.shared_css = LEGACY_SHARED_CSS.strip()
    db.session.commit()
    return _serialize_attached_template(template, note_type_id=note_type.id)


def delete_template(
    *,
    user_id: int,
    note_type_id: str,
    template_id: str,
) -> dict[str, bool]:
    from app.repositories import template_library_repository as library_repository

    note_type = _owned_note_type(user_id=user_id, note_type_id=note_type_id)
    template = _template(note_type_id=note_type.id, template_id=template_id)
    _ensure_version_safe_template_mutation(
        note_type=note_type,
        owner_user_id=user_id,
    )
    # Membership, default and the last-template rule come from this NoteType's
    # active occurrences, as listed by the editor.
    active = library_repository.applications(db.session, note_type.id)
    own = [row for row in active if row.template_id == template.id]
    if any(row.is_default for row in own):
        raise ContentApiError(
            "VALIDATION_ERROR",
            "Cannot delete default template.",
            status=409,
        )
    remaining = [row for row in active if row.template_id != template.id]
    if not remaining:
        raise ContentApiError(
            "VALIDATION_ERROR",
            "A note type requires at least one template.",
            status=409,
        )
    # Removing an attachment preserves the independent definition and old leases.
    library_repository.detach_template(db.session, note_type.id, template)
    _audit(user_id, "template.detach", {"note_type_id": note_type.id, "template_id": template.id})
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
    field_defs = note_type.field_defs
    application = (
        StudyApplication.query.filter_by(
            note_type_id=note_type.id, template_id=template.id, status_code="ACTIVE",
        )
        .order_by(StudyApplication.position, StudyApplication.id)
        .first()
    )
    if application is not None and isinstance(application.input_bindings, Mapping):
        # Same input projection as study rendering; unset (legacy) bindings,
        # identity bindings and schemaless templates keep the original fields.
        from app.services.template_binding_service import prepare_bound_fields

        field_defs, values = prepare_bound_fields(
            SimpleNamespace(id=template.id, input_schema=template.input_schema),
            field_defs,
            values,
            input_bindings=application.input_bindings,
        )
    try:
        result = dict(render_template_pair(
            template=preview_template_obj,
            field_defs=field_defs,
            field_values=values,
            media_assets=media_assets,
            preview_note_key=preview_key,
        ))
        from app.services.template_authoring_service import build_candidate_preview
        result["study_preview"] = build_candidate_preview(
            template=preview_template_obj, field_defs=field_defs, field_values=values,
            media_assets=media_assets, sample_source={"kind": "editor_sample" if use_sample else "owned_note"},
        )
        return result
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
            from app.validators.template_preview import preview_field_value
            from app.validators.flashcard_input import RequestValidationError
            try:
                supplied_value, supplied_chars = preview_field_value(supplied_value, field_name=name)
            except RequestValidationError as exc:
                raise ContentApiError(
                    "VALIDATION_ERROR", str(exc), field=f"field_values.{name}",
                ) from exc
            total_supplied_chars += supplied_chars
            if total_supplied_chars > 250_000:
                raise ContentApiError(
                    "VALIDATION_ERROR",
                    "field_values is too large for preview.",
                    field="field_values",
                )
            sample_values[name] = supplied_value
            if isinstance(supplied_value, list):
                # A template hint must not stringify a native list as Markdown
                # or turn it into media HTML before its script can handle it.
                f_def.field_type = "array"
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
        result = dict(render_template_pair(
            template=preview_template_obj,
            field_defs=field_defs,
            field_values=sample_values,
            media_assets=[],
            preview_note_key=f"raw_preview:{preview_hash}",
        ))
        from app.services.template_authoring_service import build_candidate_preview
        result["study_preview"] = build_candidate_preview(
            template=preview_template_obj, field_defs=field_defs, field_values=sample_values,
            sample_source={"kind": "editor_sample", "provided_keys": list(raw_field_values)},
        )
        return result
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
            "url": store_media_url(asset.id),
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
    try:
        authority_route = lock_study_authority_route(
            db.session,
            learner_user_id=int(user_id),
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise ContentApiError(exc.code, str(exc), status=409) from exc
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
    # The Note's Cards are derived from its NoteType's occurrences (ADR P11).
    cards = Card.query.filter_by(note_id=note.id).order_by(Card.id.asc()).all()
    try:
        study_progress_lifecycle_mirror_service.materialize_new_note_authority(
            db.session,
            route=authority_route,
            note=note,
            cards=cards,
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise ContentApiError(exc.code, str(exc), status=409) from exc
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
    from app.services.note_draft_service import effective_note_metadata
    original_deck_id = effective_note_metadata(note)["deck_id"]
    note_type = _owned_note_type(
        user_id=user_id,
        note_type_id=note.note_type_id,
    )
    try:
        check_note_write_preconditions(note, payload)
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
        "tags": effective_note_metadata(note)["tags"],
        **note_revision_payload(note),
    }


def delete_note(*, user_id: int, note_id: str) -> dict[str, bool]:
    note = _owned_note(user_id=user_id, note_id=note_id)
    from app.services.note_base_context import published_base_enabled
    if published_base_enabled() and note.published_at is not None:
        from app.services.note_draft_service import stage_note_delete
        stage_note_delete(note)
        _audit(user_id, "note.delete.draft", {"note_id": note.id})
        db.session.commit()
        return {"success": True}
    if deck_working_tree_service.note_has_shared_release_dependents(note):
        raise ContentApiError(
            "SHARED_ENTITY_RETIRE_REQUIRED",
            "Published shared notes cannot be hard-deleted because learner history must be preserved.",
            status=409,
        )
    from app.services import study_content_delete_service as content_delete

    card_ids = [str(card.id) for card in note.cards]
    deleted_note_ids = (str(note.id),)
    # Other learners (for example logical-overlay installers) can hold state
    # on these Cards; every affected learner is fenced and planned together.
    try:
        authority_routes = content_delete.lock_content_delete_routes(
            db.session,
            actor_user_ids=(int(user_id),),
            card_ids=card_ids,
            deleted_note_ids=deleted_note_ids,
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
        lifecycle_plan = content_delete.prepare_content_delete(
            db.session,
            routes=authority_routes,
            card_ids=card_ids,
            note_ids=deleted_note_ids,
            cancel_legacy_sessions=False,
        )
        content_delete.verify_content_delete_scope(
            db.session,
            routes=authority_routes,
            card_ids=card_ids,
            deleted_note_ids=deleted_note_ids,
        )
        if card_ids:
            pass  # NOTE lifecycle state is handled by the fenced deletion plan.
        content_delete.finalize_content_delete(
            lifecycle_plan,
            source_path="flashcards.note_delete",
            operation_key=f"note-delete:{note.id}",
        )
    except StudyAuthorityFenceError as exc:
        db.session.rollback()
        raise ContentApiError(exc.code, str(exc), status=409) from exc
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


def _serialize_attached_template(template: Template, *, note_type_id: str):
    application = StudyApplication.query.filter_by(
        note_type_id=note_type_id, template_id=template.id, status_code="ACTIVE",
    ).order_by(StudyApplication.position, StudyApplication.id).first()
    return marketplace_query_service.serialize_template(template, application=application,
                                                        note_type_id=note_type_id)


def _template(*, note_type_id: str, template_id: str) -> Template:
    row = Template.query.filter(
        Template.id == template_id,
        Template.id.in_(
            db.session.query(StudyApplication.template_id).filter(
                StudyApplication.note_type_id == note_type_id,
                StudyApplication.status_code == "ACTIVE",
            )
        ),
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
    from app.services.note_draft_service import effective_note_metadata
    metadata = effective_note_metadata(note)
    return {
        "id": note.id,
        "note_type_id": note.note_type_id,
        "deck_id": metadata["deck_id"],
        "field_values": note.field_values or {},
        **note_revision_payload(note),
        "tags": metadata["tags"] or [],
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


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
