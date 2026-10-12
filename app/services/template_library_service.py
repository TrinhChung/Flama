"""Personal reusable definitions and non-destructive NoteType attachments."""

from datetime import datetime, timezone
from types import SimpleNamespace
from sqlalchemy import delete, select
from app.repositories import template_library_repository as repository
from app.repositories import template_version_repository
from app.validators.template_library import (TemplateLibraryError, body, text, validate_input_schema, infer_input_schema, validate_bindings, binding_warnings)
from app.services import template_version_service
from models import db
from models.note_type import NoteType
from models.study_application import COMPAT_OCCURRENCE_KEY, StudyApplication
from models.template import Template

CONTENT_KEYS = {"front_html", "back_html", "shared_css", "input_schema"}
WRITE_KEYS = CONTENT_KEYS | {"name", "description", "primary_category", "change_note", "expected_current_version_id"}


def _commit(operation):
    try:
        result = operation()
        db.session.commit()
        return result() if callable(result) else result
    except Exception:
        db.session.rollback()
        raise


def _owned(user_id, template_id, *, lock=False):
    template = template_version_repository.owned_template(db.session, user_id=user_id, template_id=template_id, lock=lock)
    if template is None:
        raise TemplateLibraryError("TEMPLATE_NOT_FOUND", "Template not found.", status=404)
    return template


def _note_type(user_id, note_type_id, *, lock=False):
    statement = select(NoteType).where(NoteType.id == str(note_type_id), NoteType.user_id == int(user_id))
    if lock:
        statement = statement.with_for_update()
    row = db.session.execute(statement).scalar_one_or_none()
    if row is None:
        raise TemplateLibraryError("NOTE_TYPE_NOT_FOUND", "NoteType not found.", status=404)
    return row


def effective_input_schema(template, field_defs=()):
    return template.input_schema or infer_input_schema(template.front_html, template.back_html, field_defs)


def initialize_legacy_bindings(note_type):
    names = {field.name: str(field.id) for field in note_type.field_defs}
    for application in repository.applications(db.session, note_type.id, include_retired=True):
        if application.input_bindings is None:
            schema = effective_input_schema(application.template, note_type.field_defs)
            application.input_bindings = {item["key"]: names.get(item["key"]) for item in schema}


def _iso(value):
    return value.replace(tzinfo=timezone.utc).isoformat() if value is not None else None


def serialize_template(template, *, include_source=True):
    result = {"id": template.id, "owner_user_id": template.owner_user_id, "name": template.name, "description": template.description or "", "primary_category": template.primary_category, "origin": template.origin, "source_template_id": template.source_template_id, "source_version_id": template.source_version_id, "current_version_id": template.current_version_id, "input_schema": effective_input_schema(template, ()), "archived_at": _iso(template.archived_at), "created_at": _iso(template.created_at), "updated_at": _iso(template.updated_at)}
    if include_source:
        result.update(front_html=template.front_html, back_html=template.back_html, shared_css=template.shared_css)
    return result


def serialize_application(application):
    schema = effective_input_schema(application.template, application.note_type.field_defs)
    return {"id": application.id, "application_id": application.id, "note_type_id": application.note_type_id, "template_id": application.template_id, "occurrence_key": application.occurrence_key, "status_code": application.status_code, "display_name": application.display_name, "position": application.position, "is_default": bool(application.is_default), "input_bindings": application.input_bindings or {}, "input_schema": schema, "warnings": binding_warnings(schema, application.input_bindings, application.note_type.field_defs), "template": serialize_template(application.template)}


def _with_usage(template, usages, *, include_applications=False, include_source=True):
    result = {
        **serialize_template(template, include_source=include_source), "application_count": len(usages),
        "note_type_count": len({item["note_type_id"] for item in usages}),
    }
    if include_applications:
        result["applications"] = usages
    return result


def list_templates(*, user_id, include_archived=False, category=None, search=None, group="all", compact=False, page=None, page_size=None):
    if group not in {"all", "mine", "market", "standalone", "in_use"}:
        raise TemplateLibraryError("VALIDATION_ERROR", "Invalid library group.", field="group")
    paged = page is not None or page_size is not None
    if paged:
        for field, value in (("page", page if page is not None else 1), ("page_size", page_size if page_size is not None else 24)):
            if isinstance(value, bool) or len(str(value)) > 10 or not str(value).isascii() or not str(value).isdigit() or not 1 <= int(value) <= 2_147_483_647:
                raise TemplateLibraryError("VALIDATION_ERROR", f"{field} must be an integer between 1 and 2147483647.", field=field)
        page = int(page if page is not None else 1)
        page_size = min(int(page_size if page_size is not None else 24), 100)
    templates, total = repository.library_query(db.session, user_id, include_archived=include_archived, category=category, search=search, group=group, compact=compact, page=page if paged else None, page_size=page_size or 24)
    usages = repository.template_usage(db.session, user_id, [item.id for item in templates])
    result = {"schema_version": "template-library.v2", "items": [_with_usage(item, usages.get(item.id, []), include_source=not compact) for item in templates]}
    if paged:
        result["pagination"] = {"page": page, "page_size": page_size, "total": total, "has_more": page * page_size < total}
    return result


def get_template(*, user_id, template_id):
    template = _owned(user_id, template_id)
    usages = repository.template_usage(db.session, user_id, [template.id])
    return _with_usage(template, usages.get(template.id, []), include_applications=True)


def preview_template(*, user_id, template_id, payload):
    """Compile an owned template draft without persisting source or history."""
    body(payload, CONTENT_KEYS | {"sample_values"})
    template = _owned(user_id, template_id)
    draft = SimpleNamespace(**{
        key: text(payload.get(key, getattr(template, key)), field=key)
        for key in ("front_html", "back_html", "shared_css")
    })
    schema = validate_input_schema(payload["input_schema"]) if "input_schema" in payload else effective_input_schema(template, ())
    values = payload.get("sample_values", {})
    if not isinstance(values, dict):
        raise TemplateLibraryError("VALIDATION_ERROR", "sample_values must be an object.", field="sample_values")
    unknown = set(values) - {item["key"] for item in schema}
    if unknown:
        raise TemplateLibraryError("INPUT_NOT_FOUND", "Unknown preview input.", field="sample_values")
    from app.services.flashcard_content_service import preview_raw_template
    return preview_raw_template(payload={
        **vars(draft), "fields": [{"name": item["key"], "field_type": item["type"]} for item in schema],
        "field_values": values,
    })


def _apply_content(template, payload):
    for key in ("name", "description", "primary_category", "front_html", "back_html", "shared_css"):
        if key in payload:
            value = payload[key]
            if key == "primary_category" and value is None:
                setattr(template, key, None)
                continue
            setattr(template, key, text(value, field=key, maximum={"name": 255, "primary_category": 120}.get(key), required=key == "name"))
    if "input_schema" in payload:
        template.input_schema = validate_input_schema(payload["input_schema"])
    elif template.input_schema is None:
        template.input_schema = infer_input_schema(template.front_html or "", template.back_html or "")
    # Compile with the existing renderer, including script/media sanitization.
    from app.services.flashcard_renderer import render_template_pair, TemplateCompileError
    fields = [SimpleNamespace(id=f"input:{item['key']}", name=item["key"], field_type=item["type"], position=index) for index, item in enumerate(template.input_schema or [])]
    try:
        render_template_pair(template=template, field_defs=fields, field_values={}, media_assets=[], preview_note_key="library-validation")
    except TemplateCompileError as exc:
        raise TemplateLibraryError("TEMPLATE_COMPILE_ERROR", str(exc), field="front_html") from exc


def create_template(*, user_id, payload):
    body(payload, WRITE_KEYS)
    if "name" not in payload:
        raise TemplateLibraryError("VALIDATION_ERROR", "Template name is required.", field="name")
    def operation():
        template = Template(owner_user_id=user_id, front_html="", back_html="", shared_css="", input_schema=None, origin="authored", position=0, is_default=False)
        _apply_content(template, payload)
        db.session.add(template)
        template_version_service.mark_template_version(template, origin="create", actor_user_id=user_id, change_note=template_version_service.validate_change_note(payload))
        return lambda: serialize_template(template)
    return _commit(operation)


def update_template(*, user_id, template_id, payload):
    body(payload, WRITE_KEYS)
    def operation():
        template = _owned(user_id, template_id, lock=True)
        if "expected_current_version_id" in payload and payload["expected_current_version_id"] != template.current_version_id:
            raise TemplateLibraryError("TEMPLATE_VERSION_STALE", "Template changed since it was loaded.", status=409)
        _apply_content(template, payload)
        template_version_service.mark_template_version(template, origin="edit", actor_user_id=user_id, change_note=template_version_service.validate_change_note(payload))
        return lambda: {**serialize_template(template), "affected_applications": [item.id for item in db.session.execute(select(StudyApplication).where(StudyApplication.template_id == template.id, StudyApplication.status_code == "ACTIVE")).scalars()]}
    return _commit(operation)


def duplicate_template(*, user_id, template_id, payload):
    body(payload, {"name"})
    source = _owned(user_id, template_id)
    if source.origin == "market_copy" or source.source_template_id:
        raise TemplateLibraryError("MARKET_TEMPLATE_REPUBLISH_FORBIDDEN", "Received marketplace templates cannot be duplicated into authored definitions.", status=403)
    data = {key: getattr(source, key) for key in CONTENT_KEYS | {"description", "primary_category"}}
    data["description"] = source.description or ""
    data["name"] = payload.get("name", source.name + " (copy)")
    return create_template(user_id=user_id, payload=data)


def archive_template(*, user_id, template_id, payload):
    body(payload, {"archived"})
    if not isinstance(payload.get("archived"), bool):
        raise TemplateLibraryError("VALIDATION_ERROR", "archived must be boolean.", field="archived")
    def operation():
        template = _owned(user_id, template_id, lock=True)
        template.archived_at = datetime.utcnow() if payload["archived"] else None
        return lambda: serialize_template(template)
    return _commit(operation)


def delete_template(*, user_id, template_id):
    def operation():
        template = _owned(user_id, template_id, lock=True)
        active_applications = list(
            db.session.execute(
                select(StudyApplication).where(
                    StudyApplication.template_id == template.id,
                    StudyApplication.status_code == "ACTIVE",
                )
            ).scalars()
        )
        if active_applications:
            raise TemplateLibraryError(
                "TEMPLATE_IN_USE",
                f"Template is currently in use in {len(active_applications)} active note type(s). Retire or remove them first.",
                status=409,
            )
        from models.template_release import TemplateRelease
        if db.session.execute(select(TemplateRelease.id).where(TemplateRelease.template_id == template.id)).first():
            raise TemplateLibraryError(
                "TEMPLATE_HAS_RELEASES",
                "Cannot delete a published template with releases. Please archive it instead.",
                status=409,
            )
        from models.template_subscription import TemplateSubscription
        if db.session.execute(select(TemplateSubscription.id).where(TemplateSubscription.source_template_id == template.id)).first():
            raise TemplateLibraryError(
                "TEMPLATE_HAS_SUBSCRIBERS",
                "Cannot delete a template with active subscribers. Please archive it instead.",
                status=409,
            )
        db.session.execute(
            delete(TemplateSubscription).where(TemplateSubscription.local_template_id == template.id)
        )
        from models.template_publication import TemplatePublication
        db.session.execute(
            delete(TemplatePublication).where(TemplatePublication.template_id == template.id)
        )
        # Every occurrence is retired here and is now deleted with the
        # Template: forget their Cards (ADR P11).
        from app.services import study_content_delete_service as content_delete
        content_delete.stop_presenting(
            db.session,
            application_ids=db.session.execute(
                select(StudyApplication.id).where(StudyApplication.template_id == template.id)
            ).scalars().all(),
        )
        db.session.execute(
            delete(StudyApplication).where(StudyApplication.template_id == template.id)
        )
        db.session.delete(template)
        return lambda: {"success": True, "id": template_id}

    return _commit(operation)


def list_applications(*, user_id, note_type_id, include_retired=False):
    _note_type(user_id, note_type_id)
    return {"schema_version": "template-applications.v2", "items": [serialize_application(item) for item in repository.applications(db.session, note_type_id, include_retired=include_retired)]}


def _application(user_id, note_type_id, application_id, *, lock=False):
    _note_type(user_id, note_type_id, lock=lock)
    statement = select(StudyApplication).where(StudyApplication.note_type_id == note_type_id, StudyApplication.id == application_id)
    if lock:
        statement = statement.with_for_update().execution_options(populate_existing=True)
    item = db.session.execute(statement).scalar_one_or_none()
    if item is None:
        raise TemplateLibraryError("APPLICATION_NOT_FOUND", "Template application not found.", status=404)
    return item


def _application_payload(application, payload, note_type):
    schema = effective_input_schema(application.template, note_type.field_defs)
    if "input_bindings" in payload:
        application.input_bindings = validate_bindings(schema, payload["input_bindings"], note_type.field_defs)
    if "display_name" in payload:
        application.display_name = None if payload["display_name"] is None else text(payload["display_name"], field="display_name", maximum=255)
    if "position" in payload:
        value = payload["position"]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise TemplateLibraryError("VALIDATION_ERROR", "position must be a nonnegative integer.", field="position")
        application.position = value
    if "is_default" in payload:
        if not isinstance(payload["is_default"], bool):
            raise TemplateLibraryError("VALIDATION_ERROR", "is_default must be boolean.", field="is_default")
        if payload["is_default"]:
            for sibling in repository.applications(db.session, note_type.id):
                sibling.is_default = False
        application.is_default = payload["is_default"]


def attach_template(*, user_id, note_type_id, payload):
    body(payload, {"template_id", "occurrence_key", "input_bindings", "display_name", "position", "is_default"})
    template_id = text(payload.get("template_id"), field="template_id", required=True)
    if "occurrence_key" in payload and payload.get("occurrence_key") is not None:
        text(payload.get("occurrence_key"), field="occurrence_key", maximum=64, required=True)
    def operation():
        template = _owned(user_id, template_id, lock=True)
        note_type = _note_type(user_id, note_type_id, lock=True)
        if template.archived_at:
            raise TemplateLibraryError("TEMPLATE_ARCHIVED", "Archived template cannot be attached.", status=409)
        existing_rows = db.session.execute(
            select(StudyApplication)
            .where(
                StudyApplication.note_type_id == note_type.id,
                StudyApplication.template_id == template.id,
            )
            .order_by(
                db.case((StudyApplication.occurrence_key == COMPAT_OCCURRENCE_KEY, 0), else_=1),
                StudyApplication.id,
            )
            .with_for_update()
        ).scalars().all()
        if any(row.status_code == "ACTIVE" for row in existing_rows):
            raise TemplateLibraryError("APPLICATION_EXISTS", "This template is already attached.", status=409)
        application = existing_rows[0] if existing_rows else None
        # Derived presentations need one attachment row, not per-Note writes.
        if application is None:
            application = StudyApplication(note_type=note_type, template=template, occurrence_key=COMPAT_OCCURRENCE_KEY, status_code="ACTIVE", input_bindings={}, position=0, is_default=False)
            db.session.add(application)
        else:
            application.status_code = "ACTIVE"
        _application_payload(application, payload, note_type)
        db.session.flush()
        return lambda: serialize_application(application)
    return _commit(operation)


def update_application(*, user_id, note_type_id, application_id, payload):
    body(payload, {"input_bindings", "display_name", "position", "is_default"})
    def operation():
        application = _application(user_id, note_type_id, application_id, lock=True)
        if application.status_code != "ACTIVE":
            raise TemplateLibraryError("APPLICATION_RETIRED", "Application is retired.", status=409)
        _application_payload(application, payload, application.note_type)
        return lambda: serialize_application(application)
    return _commit(operation)


def retire_application(*, user_id, note_type_id, application_id):
    def operation():
        application = _application(user_id, note_type_id, application_id, lock=True)
        # A retired occurrence presents no Card to new discovery; its Cards stay
        # addressable and reactivation restores the same keys (ADR P11).
        application.status_code = "RETIRED"
        return lambda: serialize_application(application)
    return _commit(operation)
