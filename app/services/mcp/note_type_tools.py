"""MCP note type schema operations: list, get schema, create, preview update, update, delete."""

from __future__ import annotations

import json
from functools import wraps
from typing import Any
from sqlalchemy import or_
from sqlalchemy.orm.attributes import set_committed_value

from models.field_types import FIELD_TYPES
from app.repositories import template_library_repository
from app.repositories.study_authority_repository import StudyAuthorityFenceError
from app.services import flashcard_content_service
from app.services.flashcard_renderer import TemplateCompileError, render_template_pair
from app.services.mcp.base import (
    _compact_description,
    _owned_note_type_for_mutation,
    _resolve_note_type_for_user,
)
from app.services.mcp_preview_service import (
    PreviewStoreUnavailable,
    compute_resource_version,
    consume_preview_token,
    create_preview_token,
    validate_preview_token,
)
from app.validators.flashcard_input import RequestValidationError
from models import db
from models.card import Card
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
from models.template import Template
from models.user import User


# ---------------------------------------------------------------------------


def list_note_types(*, user_id: int) -> list[dict[str, Any]]:
    """Return available note types (models) for the user."""
    note_types = (
        NoteType.query.filter(
            or_(
                NoteType.user_id == user_id,
                NoteType.is_official == True,
                NoteType.publish_status == "published",
            )
        )
        .order_by(NoteType.name.asc())
        .all()
    )

    items: list[dict[str, Any]] = []
    for nt in note_types:
        items.append(
            {
                "id": str(nt.id),
                "name": nt.name,
                "description": _compact_description(nt.description),
                "field_count": len(nt.field_defs),
                "template_count": len(template_library_repository.attached_templates(db.session, nt.id)),
                "is_official": bool(nt.is_official),
                "is_owner": int(nt.user_id) == int(user_id),
            }
        )
    return items


def get_note_type_schema(*, user_id: int, note_type_id: str | None = None, name: str | None = None) -> dict[str, Any]:
    """Return comprehensive field definitions, validation metadata, and templates for a specific note type."""
    query = NoteType.query.filter(
        or_(
            NoteType.user_id == user_id,
            NoteType.is_official == True,
            NoteType.publish_status == "published",
        )
    )
    if note_type_id:
        nt = query.filter(NoteType.id == note_type_id).first()
    elif name:
        nt = query.filter(NoteType.name == name).first()
    else:
        nt = None

    if nt is None:
        raise RequestValidationError(
            f"Không tìm thấy NoteType phù hợp ({note_type_id or name}).",
            field="note_type_id",
            status=404,
            code="NOT_FOUND",
        )

    is_owner = int(nt.user_id) == int(user_id)
    sorted_field_defs = sorted(nt.field_defs, key=lambda item: item.position)
    sorted_templates = sorted(template_library_repository.attached_templates(db.session, nt.id), key=lambda item: item.position)

    fields = [
        {
            "id": str(f.id),
            "name": f.name,
            "field_type": f.field_type,
            "position": f.position,
            "required": bool(f.required),
            "identity_role": f.identity_role,
            "default": None,
            "editable": is_owner,
            "validation_constraints": {
                "allowed_types": list(FIELD_TYPES),
                "required": bool(f.required),
                "is_primary_identity": f.identity_role == "primary",
                "max_length": 100000,
            },
        }
        for f in sorted_field_defs
    ]

    templates = [
        {
            "id": str(t.id),
            "application_id": t.application_id,
            "occurrence_key": t.application.occurrence_key,
            "input_bindings": t.application.input_bindings or {},
            "display_name": t.application.display_name,
            "name": t.name,
            "position": t.position,
            "is_default": bool(t.is_default),
            "front_html": t.front_html,
            "back_html": t.back_html,
            "shared_css": t.shared_css or "",
        }
        for t in sorted_templates
    ]
    if not is_owner:
        # Another author's live drafts are unpublished; show what the
        # marketplace shows, the immutable published release content.
        from app.services import marketplace_query_service

        templates = [
            {
                "id": str(t["id"]),
                "name": t["name"],
                "position": t["position"],
                "is_default": bool(t["is_default"]),
                "front_html": t["front_html"],
                "back_html": t["back_html"],
                "shared_css": t["shared_css"] or "",
            }
            for t in marketplace_query_service.serialize_note_type_templates(nt, published=True)
        ]

    return {
        "id": str(nt.id),
        "name": nt.name,
        "description": nt.description,
        "primary_category": nt.primary_category,
        "tags": list(nt.tags or []),
        "taxonomy_metadata": dict(nt.taxonomy_metadata or {}),
        "preview_text": nt.preview_text,
        "preview_image_url": nt.preview_image_url,
        "pricing_mode": str(nt.pricing_mode or "free"),
        "price_amount_minor": int(nt.price_amount_minor or 0),
        "publish_status": str(nt.publish_status or "private"),
        "is_official": bool(nt.is_official),
        "is_owner": is_owner,
        "field_names": [f.name for f in sorted_field_defs],
        "fields": fields,
        "templates": templates,
        "sample_note_payload": {
            "deck_id": None,
            "note_type_id": str(nt.id),
            "fields": {f.name: f"<{f.name}>" for f in sorted_field_defs},
            "tags": [],
        },
    }



# (_owned_note_type_for_mutation imported from base)

def create_note_type(
    *,
    user_id: int,
    name: str,
    description: str | None = None,
    primary_category: str | None = None,
    tags: list[str] | None = None,
    taxonomy_metadata: dict[str, Any] | None = None,
    preview_text: str | None = None,
    preview_image_url: str | None = None,
    fields: list[dict[str, Any]] | None = None,
    templates: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Create a new note type (model) with custom fields, templates, metadata, and taxonomy."""
    cleaned_name = str(name or "").strip()
    if not cleaned_name:
        raise RequestValidationError("Tên NoteType là bắt buộc.", field="name", status=400, code="INVALID_PARAMS")

    existing = NoteType.query.filter_by(user_id=user_id, name=cleaned_name).first()
    if existing is not None:
        raise RequestValidationError(
            f"Note type '{cleaned_name}' đã tồn tại.",
            field="name",
            status=400,
            code="NOTE_TYPE_ALREADY_EXISTS",
        )

    note_type = NoteType(
        user_id=user_id,
        name=cleaned_name,
        description=str(description).strip() if description is not None else None,
    )
    if primary_category is not None:
        note_type.primary_category = primary_category
    if tags is not None:
        note_type.tags = tags
    if preview_text is not None:
        note_type.preview_text = preview_text
    if preview_image_url is not None:
        note_type.preview_image_url = preview_image_url
    if taxonomy_metadata is not None:
        from app.services import marketplace_taxonomy_service
        normalized_tax, tax_err = marketplace_taxonomy_service.normalize_taxonomy_payload(
            taxonomy_metadata,
            content_type="note_type",
        )
        if tax_err:
            raise RequestValidationError(tax_err, field="taxonomy_metadata", status=400, code="TAXONOMY_VALIDATION_ERROR")
        note_type.taxonomy_metadata = normalized_tax
        if not primary_category:
            suggested = marketplace_taxonomy_service.suggest_primary_category(normalized_tax)
            if suggested:
                note_type.primary_category = suggested

    db.session.add(note_type)
    db.session.flush()

    if not fields:
        fields = [
            {"name": "Word", "field_type": "text", "position": 0, "required": True, "identity_role": "primary"},
            {"name": "Meaning", "field_type": "text", "position": 1, "required": True, "identity_role": None},
        ]

    field_defs_objs: list[FieldDef] = []
    seen_names: set[str] = set()
    primary_count = 0
    for idx, f in enumerate(fields):
        f_name = str(f.get("name") or "").strip()
        if not f_name:
            db.session.rollback()
            raise RequestValidationError(f"Field name at index {idx} cannot be empty.", field="fields", status=400, code="INVALID_PARAMS")
        if f_name.lower() in seen_names:
            db.session.rollback()
            raise RequestValidationError(f"Duplicate field name: '{f_name}'.", field="fields", status=400, code="DUPLICATE_FIELD_NAME")
        seen_names.add(f_name.lower())

        f_type = str(f.get("field_type") or "text").strip().lower()
        if f_type not in {"text", "richtext", "markdown", "image", "audio", "diagram"}:
            db.session.rollback()
            raise RequestValidationError(f"Unsupported field_type: '{f_type}'.", field="fields", status=400, code="INVALID_FIELD_TYPE")

        identity_role = f.get("identity_role")
        if identity_role == "primary":
            primary_count += 1
            if primary_count > 1:
                db.session.rollback()
                raise RequestValidationError("Only one primary identity field allowed.", field="fields", status=400, code="MULTIPLE_PRIMARY_IDENTITY")
            if f_type != "text":
                db.session.rollback()
                raise RequestValidationError("Primary identity field must have type 'text'.", field="fields", status=400, code="INVALID_IDENTITY_TYPE")

        f_obj = FieldDef(
            note_type_id=note_type.id,
            name=f_name,
            field_type=f_type,
            position=int(f.get("position", idx)),
            required=True if identity_role == "primary" else bool(f.get("required", False)),
            identity_role=identity_role,
        )
        db.session.add(f_obj)
        field_defs_objs.append(f_obj)

    db.session.flush()

    if templates is not None and len(templates) == 0:
        db.session.rollback()
        raise RequestValidationError(
            "NoteType phải có ít nhất một Template.",
            field="templates",
            status=400,
            code="NOTE_TYPE_MUST_HAVE_TEMPLATES",
        )

    if not templates:
        first_name = field_defs_objs[0].name
        second_name = field_defs_objs[1].name if len(field_defs_objs) > 1 else first_name
        templates = [
            {
                "name": "Card 1",
                "front_html": f"{{{{{first_name}}}}}",
                "back_html": f"{{{{FrontSide}}}}\n<hr id=\"answer\">\n{{{{{second_name}}}}}",
                "shared_css": "",
                "position": 0,
            }
        ]

    for idx, t in enumerate(templates):
        t_name = str(t.get("name") or f"Card {idx + 1}").strip()
        front_html = str(t.get("front_html") or f"{{{{{field_defs_objs[0].name}}}}}").strip()
        back_html = str(t.get("back_html") or f"{{{{FrontSide}}}}\n<hr id=\"answer\">\n{{{{{field_defs_objs[0].name}}}}}").strip()
        shared_css = str(t.get("shared_css") or "").strip()

        t_obj = template_library_repository.create_attached_template(db.session, note_type=note_type, name=t_name, front_html=front_html, back_html=back_html, shared_css=shared_css, position=int(t.get("position", idx)), is_default=idx == 0)

        try:
            render_template_pair(
                template=t_obj,
                field_defs=field_defs_objs,
                field_values={f.name: "sample" for f in field_defs_objs},
                preview_note_key="creation_check",
            )
        except Exception as exc:
            db.session.rollback()
            raise RequestValidationError(
                f"Lỗi cú pháp trong template '{t_name}': {str(exc)}",
                field="templates",
                status=400,
                code="TEMPLATE_SYNTAX_ERROR",
            ) from exc

        db.session.add(t_obj)

    db.session.commit()
    return get_note_type_schema(user_id=user_id, note_type_id=note_type.id)


def _note_type_update_resource_version(nt, *, notes_count, cards_count):
    # Child schema edits/replacements may preserve both counts and the parent's
    # DATETIME(0). Bind stable identities and content, not only that timestamp.
    return compute_resource_version(
        resource_type="note_type", resource_id=nt.id, notes_count=notes_count,
        cards_count=cards_count, updated_at=nt.updated_at,
        templates=[{key: getattr(row, key) for key in (
            "id", "name", "front_html", "back_html", "shared_css", "position", "is_default",
        )} | {"application_id": row.application_id, "occurrence_key": row.application.occurrence_key,
              "input_bindings": row.application.input_bindings}
         for row in sorted(template_library_repository.attached_templates(db.session, nt.id), key=lambda row: row.application_id)],
        fields=[{key: getattr(row, key) for key in (
            "id", "name", "field_type", "position", "required", "identity_role",
        )} for row in sorted(nt.field_defs, key=lambda row: row.id)],
    )


def preview_note_type_update(
    *,
    user_id: int,
    note_type_id: str,
    name: str | None = None,
    description: str | None = None,
    fields: list[dict[str, Any]] | dict[str, Any] | None = None,
    templates: list[dict[str, Any]] | dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Analyze and preview the impact of modifying a note type, fields, or templates."""
    nt = _owned_note_type_for_mutation(user_id=user_id, note_type_id=note_type_id)

    notes_count = Note.query.filter_by(note_type_id=nt.id, user_id=user_id).count()
    cards_count = Card.query.join(Note, Card.note_id == Note.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).count()
    decks_rows = db.session.query(Deck.id, Deck.name).join(Note, Note.deck_id == Deck.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).distinct().all()
    affected_decks = [{"id": int(r[0]), "name": r[1]} for r in decks_rows]

    current_field_map = {f.name: f for f in nt.field_defs}
    current_field_ids = {f.id: f for f in nt.field_defs}
    current_template_map = {t.name: t for t in template_library_repository.attached_templates(db.session, nt.id)}
    current_template_ids = {t.id: t for t in template_library_repository.attached_templates(db.session, nt.id)}

    added_fields: list[dict[str, Any]] = []
    renamed_fields: list[dict[str, str]] = []
    removed_fields: list[str] = []
    modified_fields: list[dict[str, Any]] = []
    added_templates: list[dict[str, Any]] = []
    updated_templates: list[dict[str, Any]] = []
    removed_templates: list[str] = []

    data_loss_possible = False
    template_regeneration_required = False
    validation_errors: list[str] = []
    warnings: list[str] = []

    # Parse Fields
    if fields is not None:
        if isinstance(fields, dict):
            for af in fields.get("added", []):
                added_fields.append({"name": af.get("name"), "field_type": af.get("field_type", "text")})
            for rf in fields.get("renamed", []):
                renamed_fields.append({"old_name": rf.get("old_name"), "new_name": rf.get("new_name")})
            for rm in fields.get("removed", []):
                removed_fields.append(str(rm))
            for mf in fields.get("modified", []):
                modified_fields.append(mf)
        elif isinstance(fields, list):
            new_names = set()
            for f in fields:
                f_name = f.get("name")
                f_id = f.get("id")
                old_name = f.get("old_name")
                new_names.add(f_name)

                if old_name and old_name in current_field_map and old_name != f_name:
                    renamed_fields.append({"old_name": old_name, "new_name": f_name})
                elif f_id and f_id in current_field_ids and current_field_ids[f_id].name != f_name:
                    renamed_fields.append({"old_name": current_field_ids[f_id].name, "new_name": f_name})
                elif f_name not in current_field_map and not old_name:
                    added_fields.append({"name": f_name, "field_type": f.get("field_type", "text")})

            renamed_old_names = {r["old_name"] for r in renamed_fields}
            for curr_name in current_field_map:
                if curr_name not in new_names and curr_name not in renamed_old_names:
                    removed_fields.append(curr_name)

    # Check data loss on removed fields
    for rem_f in removed_fields:
        if notes_count > 0:
            notes_with_data = 0
            for note in Note.query.filter_by(note_type_id=nt.id, user_id=user_id).all():
                if note.field_values and note.field_values.get(rem_f):
                    notes_with_data += 1
            if notes_with_data > 0:
                data_loss_possible = True
                warnings.append(
                    f"⚠️ Xóa trường '{rem_f}': Có {notes_with_data} note(s) đang chứa dữ liệu ở trường này. "
                    "Dữ liệu trong các trường này sẽ bị xóa vĩnh viễn khỏi các note."
                )
            else:
                warnings.append(f"Xóa trường '{rem_f}' (trường không chứa dữ liệu trong note nào).")

    # Templates are explicitly scoped applications. Retirement hides future
    # discovery while preserving definitions, NOTE progress and review history.
    if templates is not None:
        from app.services.study_note_template_service import _plan
        current = tuple(template_library_repository.attached_templates(db.session, nt.id))
        updates, additions, removed_ids = _plan(current, templates)
        added_templates = [dict(item) for item in additions]
        updated_templates = [dict(data, id=view.id, application_id=view.application_id) for view, data in updates]
        removed_templates = [view.name for view in current if view.application_id in removed_ids]
        if removed_ids:
            warnings.append("Retiring these presentations preserves Note progress and review history.")

    if renamed_fields:
        renamed_desc = ", ".join(f"{r['old_name']} -> {r['new_name']}" for r in renamed_fields)
        warnings.append(
            f"Đổi tên trường ({renamed_desc}): "
            f"Hệ thống sẽ tự động di chuyển dữ liệu trong {notes_count} note(s) sang tên trường mới mà không làm mất dữ liệu."
        )

    resource_version = _note_type_update_resource_version(nt, notes_count=notes_count, cards_count=cards_count)

    impact_summary = {
        "notes_count": notes_count,
        "cards_count": cards_count,
        "added_fields": len(added_fields),
        "renamed_fields": len(renamed_fields),
        "removed_fields": len(removed_fields),
        "added_templates": len(added_templates),
        "removed_templates": len(removed_templates),
        "data_loss_possible": data_loss_possible,
    }

    try:
        preview_id, expires_at = create_preview_token(
            user_id=user_id,
            action="update_note_type",
            resource_id=nt.id,
            resource_version=resource_version,
            impact_summary=impact_summary,
        )
    except PreviewStoreUnavailable as exc:
        raise RequestValidationError(
            str(exc),
            status=503,
            code="PREVIEW_STORE_UNAVAILABLE",
        ) from exc

    return {
        "preview_id": preview_id,
        "expires_at": expires_at,
        "resource_version": resource_version,
        "note_type_id": str(nt.id),
        "note_type_name": nt.name,
        "affected_notes": notes_count,
        "affected_cards": cards_count,
        "affected_decks": affected_decks,
        "changes": {
            "name_change": {"old": nt.name, "new": name} if (name and name != nt.name) else None,
            "description_change": bool(description is not None and description != nt.description),
            "added_fields": added_fields,
            "renamed_fields": renamed_fields,
            "removed_fields": removed_fields,
            "modified_fields": modified_fields,
            "added_templates": added_templates,
            "updated_templates": updated_templates,
            "removed_templates": removed_templates,
        },
        "data_loss_possible": data_loss_possible,
        "template_regeneration_required": template_regeneration_required,
        "validation_errors": validation_errors,
        "warnings": warnings,
        "requires_confirmation": data_loss_possible,
    }


def _detect_destructive_note_type_changes(
    *,
    nt: NoteType,
    fields: list[dict[str, Any]] | dict[str, Any] | None,
    templates: list[dict[str, Any]] | dict[str, Any] | None,
    notes_count: int,
    cards_count: int,
) -> tuple[bool, list[str]]:
    current_field_map = {f.name: f for f in nt.field_defs}
    current_field_ids = {f.id: f for f in nt.field_defs}
    current_template_map = {t.name: t for t in template_library_repository.attached_templates(db.session, nt.id)}
    current_template_ids = {t.id: t for t in template_library_repository.attached_templates(db.session, nt.id)}

    reasons: list[str] = []

    # Check removed fields
    removed_fields: list[str] = []
    if fields is not None:
        if isinstance(fields, dict):
            for rm in fields.get("removed", []):
                removed_fields.append(str(rm))
        elif isinstance(fields, list):
            new_names = set()
            renamed_old = set()
            for f in fields:
                f_name = f.get("name")
                f_id = f.get("id")
                old_name = f.get("old_name")
                new_names.add(f_name)
                if old_name and old_name in current_field_map and old_name != f_name:
                    renamed_old.add(old_name)
                elif f_id and f_id in current_field_ids and current_field_ids[f_id].name != f_name:
                    renamed_old.add(current_field_ids[f_id].name)
            for curr_name in current_field_map:
                if curr_name not in new_names and curr_name not in renamed_old:
                    removed_fields.append(curr_name)

    for rf in removed_fields:
        if notes_count > 0:
            reasons.append(f"Xóa trường '{rf}' khi có {notes_count} note(s) đang tồn tại")

    # Attachment retirement is not content/history deletion.
    if templates is not None:
        from app.services.study_note_template_service import _plan
        _plan(tuple(template_library_repository.attached_templates(db.session, nt.id)), templates)

    return bool(reasons), reasons


def _rollback_note_type_update_on_error(mutation):
    @wraps(mutation)
    def guarded(*args, **kwargs):
        try:
            return mutation(*args, **kwargs)
        except StudyAuthorityFenceError as exc:
            db.session.rollback()
            raise RequestValidationError(str(exc), field="templates", status=409, code=exc.code) from exc
        except Exception:
            db.session.rollback()
            raise
    return guarded


@_rollback_note_type_update_on_error
def update_note_type(
    *,
    user_id: int,
    note_type_id: str,
    name: str | None = None,
    description: str | None = None,
    primary_category: str | None = None,
    tags: list[str] | None = None,
    taxonomy_metadata: dict[str, Any] | None = None,
    preview_text: str | None = None,
    preview_image_url: str | None = None,
    pricing_mode: str | None = None,
    price_amount_minor: int | None = None,
    publish_status: str | None = None,
    fields: list[dict[str, Any]] | dict[str, Any] | None = None,
    templates: list[dict[str, Any]] | dict[str, Any] | None = None,
    preview_id: str | None = None,
    confirm: bool = False,
) -> dict[str, Any]:
    """Update a note type's schema, metadata, fields, or templates with data migration support."""
    nt = _owned_note_type_for_mutation(user_id=user_id, note_type_id=note_type_id)

    if templates is not None:
        from app.services import study_content_delete_service as content_topology

        try:
            # Template changes add/remove Cards on every Note of this type, so
            # fence every learner holding state on them, in learner ID order.
            type_card_ids = [
                str(row[0])
                for row in db.session.query(Card.id)
                .join(Note, Card.note_id == Note.id)
                .filter(Note.note_type_id == nt.id)
                # A retired occurrence's Cards still belong to their Notes.
                .execution_options(include_retired_cards=True)
                .all()
            ]
            authority_routes = content_topology.lock_content_delete_routes(
                db.session,
                actor_user_ids=(int(user_id),),
                card_ids=type_card_ids,
                deleted_note_ids=(),
            )
            authority_route = next(
                route for route in authority_routes if route.learner_user_id == int(user_id)
            )
            # Refresh after waiting for the learner fence; a repeatable-read
            # snapshot/cached relationship must not validate an older topology.
            nt = NoteType.query.filter_by(id=note_type_id, user_id=user_id).with_for_update().populate_existing().one()
            for relationship, model in (("study_applications", StudyApplication), ("field_defs", FieldDef)):
                rows = model.query.filter_by(note_type_id=nt.id).order_by(model.id).with_for_update().populate_existing().all()
                set_committed_value(nt, relationship, rows)
        except StudyAuthorityFenceError as exc:
            db.session.rollback()
            raise RequestValidationError(
                str(exc),
                field="templates",
                status=409,
                code=exc.code,
            ) from exc

    # The generic MCP note-type mutation rewrites fields/templates and cards
    # directly.  Shared decks require stable field/card identity plus release
    # dirty tracking, which is enforced by the dedicated field endpoints.
    # Keep this broad mutation path closed until template/card versioning is
    # part of DeckRelease instead of letting it bypass the publish gate.
    from app.services import deck_working_tree_service

    has_shared_lineage = deck_working_tree_service.note_type_has_shared_release_dependents(
        note_type_id=str(nt.id),
        owner_user_id=user_id,
    )
    changes_shared_shape = bool(
        fields is not None
        or templates is not None
        or (name is not None and str(name).strip() != str(nt.name or "").strip())
    )
    if has_shared_lineage and changes_shared_shape:
        raise RequestValidationError(
            "Published shared note types must be changed through version-aware field APIs; template/card changes are not release-versioned yet.",
            field=(
                "templates"
                if templates is not None
                else ("fields" if fields is not None else "name")
            ),
            status=409,
            code="SHARED_SCHEMA_VERSIONING_REQUIRED",
        )

    notes_query = db.session.query(Note.id).filter_by(note_type_id=nt.id, user_id=user_id)
    cards_query = db.session.query(Card.id).join(Note, Card.note_id == Note.id).filter(
        Note.note_type_id == nt.id, Note.user_id == user_id)
    if templates is not None:
        # Counts must use current reads too: the ownership lookup may have
        # established a MySQL repeatable-read snapshot before the fence wait.
        notes_count = len(notes_query.order_by(Note.id).with_for_update().all())
        cards_count = len(cards_query.order_by(Note.id, Card.id).with_for_update().all())
    else:
        notes_count = notes_query.count()
        cards_count = cards_query.count()

    is_destructive, destructive_reasons = _detect_destructive_note_type_changes(
        nt=nt,
        fields=fields,
        templates=templates,
        notes_count=notes_count,
        cards_count=cards_count,
    )

    if is_destructive:
        if not preview_id or not str(preview_id).strip():
            raise RequestValidationError(
                "Thao tác cập nhật NoteType này có khả năng gây mất dữ liệu ("
                + "; ".join(destructive_reasons)
                + "). Bắt buộc phải gọi preview_note_type_update trước để lấy preview_id và kiểm tra tác động.",
                field="preview_id",
                status=400,
                code="PREVIEW_REQUIRED",
            )
        if not confirm:
            raise RequestValidationError(
                "Thao tác cập nhật NoteType này có khả năng gây mất dữ liệu ("
                + "; ".join(destructive_reasons)
                + "). Bắt buộc phải có sự xác nhận của người dùng với confirm=true.",
                field="confirm",
                status=400,
                code="CONFIRMATION_REQUIRED",
            )

    current_resource_version = _note_type_update_resource_version(nt, notes_count=notes_count, cards_count=cards_count)

    if preview_id:
        is_valid, err_code, err_msg = validate_preview_token(
            preview_id=preview_id,
            user_id=user_id,
            action="update_note_type",
            resource_id=nt.id,
            current_resource_version=current_resource_version,
        )
        if not is_valid:
            preview_error_status = (
                503
                if err_code == "PREVIEW_STORE_UNAVAILABLE"
                else 409
                if err_code == "STALE_PREVIEW_ERROR"
                else 400
            )
            raise RequestValidationError(
                err_msg or "Preview token không hợp lệ hoặc đã hết hạn.",
                field="preview_id",
                status=preview_error_status,
                code=err_code or "INVALID_PREVIEW_TOKEN",
            )

    # 1. Update Name & Description
    if name is not None:
        clean_name = str(name).strip()
        if not clean_name:
            raise RequestValidationError("Tên NoteType không được để trống.", field="name", status=400, code="INVALID_PARAMS")
        if clean_name != nt.name:
            conflict = NoteType.query.filter_by(user_id=user_id, name=clean_name).first()
            if conflict:
                raise RequestValidationError(f"NoteType mang tên '{clean_name}' đã tồn tại.", field="name", status=400, code="DUPLICATE_NAME")
            nt.name = clean_name

    if description is not None:
        nt.description = str(description).strip() or None

    # Update Metadata, Taxonomy, Pricing, Publish Status
    meta_payload: dict[str, Any] = {}
    if primary_category is not None:
        meta_payload["primary_category"] = primary_category
    if tags is not None:
        meta_payload["tags"] = tags
    if preview_text is not None:
        meta_payload["preview_text"] = preview_text
    if preview_image_url is not None:
        meta_payload["preview_image_url"] = preview_image_url
    if pricing_mode is not None:
        meta_payload["pricing_mode"] = pricing_mode
    if price_amount_minor is not None:
        meta_payload["price_amount_minor"] = price_amount_minor
    if publish_status is not None:
        meta_payload["publish_status"] = publish_status
    if taxonomy_metadata is not None:
        meta_payload.update(taxonomy_metadata)

    if meta_payload:
        from app.services import flashcards_share_service
        user = db.session.get(User, user_id)
        is_admin = bool(user and user.is_admin)
        tax_err = flashcards_share_service.apply_note_type_marketplace_payload(
            nt,
            meta_payload,
            allow_set_official=is_admin,
            publish_statuses_visible=None,
        )
        if tax_err:
            raise RequestValidationError(tax_err, field="taxonomy_metadata", status=400, code="METADATA_UPDATE_ERROR")


    # 2. Update Fields
    if fields is not None:
        from app.services.template_library_service import initialize_legacy_bindings
        initialize_legacy_bindings(nt)
        current_fields = {f.name: f for f in nt.field_defs}
        current_field_ids = {f.id: f for f in nt.field_defs}

        if isinstance(fields, dict):
            # Process delta format
            for ren in fields.get("renamed", []):
                old_name = ren.get("old_name")
                new_name = ren.get("new_name")
                if old_name and new_name and old_name in current_fields and old_name != new_name:
                    field_obj = current_fields[old_name]
                    field_obj.name = new_name
                    current_fields.pop(old_name)
                    current_fields[new_name] = field_obj

            for rem_name in fields.get("removed", []):
                if rem_name in current_fields:
                    field_obj = current_fields[rem_name]
                    db.session.delete(field_obj)
                    current_fields.pop(rem_name)

            for add_f in fields.get("added", []):
                add_name = add_f.get("name")
                if add_name and add_name not in current_fields:
                    f_obj = FieldDef(
                        note_type_id=nt.id,
                        name=add_name,
                        field_type=add_f.get("field_type", "text"),
                        position=int(add_f.get("position", len(nt.field_defs))),
                        required=bool(add_f.get("required", False)),
                        identity_role=add_f.get("identity_role"),
                    )
                    db.session.add(f_obj)

            for mod_f in fields.get("modified", []):
                mod_name = mod_f.get("name")
                if mod_name in current_fields:
                    f_obj = current_fields[mod_name]
                    if "field_type" in mod_f:
                        f_obj.field_type = mod_f["field_type"]
                    if "required" in mod_f:
                        f_obj.required = bool(mod_f["required"])
                    if "position" in mod_f:
                        f_obj.position = int(mod_f["position"])
                    if "identity_role" in mod_f:
                        f_obj.identity_role = mod_f["identity_role"]

        elif isinstance(fields, list):
            # Process list format
            seen_names = set()
            retained_fields = set()
            for idx, f in enumerate(fields):
                f_name = f.get("name")
                f_id = f.get("id")
                old_name = f.get("old_name")

                if f_id and f_id in current_field_ids:
                    f_obj = current_field_ids[f_id]
                    if f_obj.name != f_name:
                        # Rename
                        f_obj.name = f_name
                    f_obj.field_type = f.get("field_type", f_obj.field_type)
                    f_obj.required = bool(f.get("required", f_obj.required))
                    f_obj.position = int(f.get("position", idx))
                    f_obj.identity_role = f.get("identity_role", f_obj.identity_role)
                    seen_names.add(f_name)
                    retained_fields.add(f_obj)
                elif old_name and old_name in current_fields:
                    f_obj = current_fields[old_name]
                    f_obj.name = f_name
                    f_obj.field_type = f.get("field_type", f_obj.field_type)
                    f_obj.required = bool(f.get("required", f_obj.required))
                    f_obj.position = int(f.get("position", idx))
                    f_obj.identity_role = f.get("identity_role", f_obj.identity_role)
                    seen_names.add(f_name)
                    retained_fields.add(f_obj)
                elif f_name in current_fields:
                    f_obj = current_fields[f_name]
                    f_obj.field_type = f.get("field_type", f_obj.field_type)
                    f_obj.required = bool(f.get("required", f_obj.required))
                    f_obj.position = int(f.get("position", idx))
                    f_obj.identity_role = f.get("identity_role", f_obj.identity_role)
                    seen_names.add(f_name)
                    retained_fields.add(f_obj)
                else:
                    # New field
                    f_obj = FieldDef(
                        note_type_id=nt.id,
                        name=f_name,
                        field_type=f.get("field_type", "text"),
                        position=int(f.get("position", idx)),
                        required=bool(f.get("required", False)),
                        identity_role=f.get("identity_role"),
                    )
                    db.session.add(f_obj)
                    seen_names.add(f_name)

            # Delete fields removed from list
            for curr_f in current_fields.values():
                if curr_f not in retained_fields:
                    db.session.delete(curr_f)

        db.session.flush()
        if not nt.field_defs:
            db.session.rollback()
            raise RequestValidationError(
                "NoteType phải có ít nhất một trường dữ liệu (field).",
                field="fields",
                status=400,
                code="NOTE_TYPE_MUST_HAVE_FIELDS",
            )

    # Attachment changes share one transaction with field edits and NOTE fences.
    if templates is not None:
        from app.services.study_note_template_service import stage_note_template_changes
        stage_note_template_changes(db.session, routes=authority_routes, note_type=nt,
            changes=templates, operation_key=f"mcp-note-type-template-update:{nt.id}:{preview_id or 'direct'}")

    if preview_id:
        consume_preview_token(preview_id)

    db.session.commit()
    return get_note_type_schema(user_id=user_id, note_type_id=nt.id)


def delete_note_type(
    *,
    user_id: int,
    note_type_id: str,
    confirm: bool = False,
    preview_id: str | None = None,
) -> dict[str, Any]:
    """Delete a note type with 2-step confirmation and safety checks."""
    nt = _owned_note_type_for_mutation(user_id=user_id, note_type_id=note_type_id)

    notes_count = Note.query.filter_by(note_type_id=nt.id, user_id=user_id).count()
    cards_count = Card.query.join(Note, Card.note_id == Note.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).count()
    decks_rows = db.session.query(Deck.id, Deck.name).join(Note, Note.deck_id == Deck.id).filter(Note.note_type_id == nt.id, Note.user_id == user_id).distinct().all()
    affected_decks = [{"id": int(r[0]), "name": r[1]} for r in decks_rows]

    current_resource_version = compute_resource_version(
        resource_type="note_type",
        resource_id=nt.id,
        notes_count=notes_count,
        cards_count=cards_count,
        updated_at=nt.updated_at,
    )

    if not confirm:
        try:
            preview_token_id, expires_at = create_preview_token(
                user_id=user_id,
                action="delete_note_type",
                resource_id=nt.id,
                resource_version=current_resource_version,
                impact_summary={
                    "notes_count": notes_count,
                    "cards_count": cards_count,
                    "affected_decks": affected_decks,
                },
            )
        except PreviewStoreUnavailable as exc:
            raise RequestValidationError(
                str(exc),
                status=503,
                code="PREVIEW_STORE_UNAVAILABLE",
            ) from exc

        can_delete = (notes_count == 0)
        warning_msg = (
            f"⚠️ CẢNH BÁO XÓA NOTE TYPE: Bạn đang chuẩn bị xóa NoteType '{nt.name}'. "
            if can_delete
            else (
                f"⚠️ KHÔNG THỂ XÓA: NoteType '{nt.name}' đang chứa {notes_count} note(s) và {cards_count} card(s) "
                f"thuộc {len(affected_decks)} deck(s). Theo business rule của hệ thống, không được xóa NoteType đang có notes. "
                "AI cần báo cho người dùng xóa hoặc di chuyển các notes trước."
            )
        )

        return {
            "requires_confirmation": True,
            "action": "delete_note_type",
            "preview_id": preview_token_id,
            "expires_at": expires_at,
            "resource_version": current_resource_version,
            "can_delete": can_delete,
            "impact": {
                "note_type_id": str(nt.id),
                "name": nt.name,
                "notes_count": notes_count,
                "cards_count": cards_count,
                "affected_decks": affected_decks,
            },
            "warning": warning_msg,
        }

    # If confirmed
    if preview_id:
        is_valid, err_code, err_msg = validate_preview_token(
            preview_id=preview_id,
            user_id=user_id,
            action="delete_note_type",
            resource_id=nt.id,
            current_resource_version=current_resource_version,
        )
        if not is_valid:
            preview_error_status = (
                503
                if err_code == "PREVIEW_STORE_UNAVAILABLE"
                else 409
                if err_code == "STALE_PREVIEW_ERROR"
                else 400
            )
            raise RequestValidationError(
                err_msg or "Preview token không hợp lệ hoặc đã hết hạn.",
                field="preview_id",
                status=preview_error_status,
                code=err_code or "INVALID_PREVIEW_TOKEN",
            )

    if notes_count > 0:
        raise RequestValidationError(
            f"Không thể xóa NoteType '{nt.name}' vì đang có {notes_count} notes sử dụng. Cần xóa hoặc di chuyển các notes trước khi xóa note type.",
            field="note_type_id",
            status=409,
            code="NOTE_TYPE_HAS_NOTES",
        )

    nt_name = nt.name
    nt_id = nt.id
    flashcard_content_service.delete_note_type(user_id=user_id, note_type_id=nt.id)

    if preview_id:
        consume_preview_token(preview_id)

    return {
        "success": True,
        "deleted": True,
        "note_type_id": str(nt_id),
        "note_type_name": nt_name,
        "message": f"NoteType '{nt_name}' đã được xóa thành công.",
    }


def _resolve_note_type_for_user(*, user_id: int, note_type_id: str | None = None, note_type_name: str | None = None) -> NoteType:
    query = NoteType.query.filter(
        or_(
            NoteType.user_id == user_id,
            NoteType.is_official == True,
            NoteType.publish_status == "published",
        )
    )
    if note_type_id:
        nt = query.filter(NoteType.id == note_type_id).first()
    elif note_type_name:
        nt = query.filter(NoteType.name == note_type_name).first()
    else:
        # Fallback to first available note type for user
        nt = query.order_by(NoteType.is_official.desc(), NoteType.created_at.asc()).first()

    if nt is None:
        raise RequestValidationError(
            f"Không tìm thấy NoteType ({note_type_id or note_type_name}).",
            field="note_type_id",
            status=404,
            code="NOTE_TYPE_NOT_FOUND",
        )
    return nt



