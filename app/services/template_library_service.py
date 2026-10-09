"""Personal reusable definitions and non-destructive NoteType attachments."""

from datetime import datetime, timezone
from types import SimpleNamespace
from sqlalchemy import select
from app.repositories import template_library_repository as repository
from app.repositories import template_version_repository
from app.validators.template_library import (TemplateLibraryError, body, text, validate_input_schema, infer_input_schema, validate_bindings, binding_warnings)
from app.services import template_version_service
from models import db
from models.card import Card
from models.note import Note
from models.note_type import NoteType
from models.study_application import StudyApplication
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


def serialize_template(template):
    return {"id": template.id, "owner_user_id": template.owner_user_id, "name": template.name, "description": template.description or "", "primary_category": template.primary_category, "origin": template.origin, "source_template_id": template.source_template_id, "source_version_id": template.source_version_id, "current_version_id": template.current_version_id, "front_html": template.front_html, "back_html": template.back_html, "shared_css": template.shared_css, "input_schema": effective_input_schema(template, getattr(template.note_type, "field_defs", ())), "archived_at": _iso(template.archived_at), "created_at": _iso(template.created_at), "updated_at": _iso(template.updated_at)}


def serialize_application(application):
    schema = effective_input_schema(application.template, application.note_type.field_defs)
    return {"id": application.id, "application_id": application.id, "note_type_id": application.note_type_id, "template_id": application.template_id, "occurrence_key": application.occurrence_key, "status_code": application.status_code, "display_name": application.display_name, "position": application.position, "is_default": bool(application.is_default), "input_bindings": application.input_bindings or {}, "input_schema": schema, "warnings": binding_warnings(schema, application.input_bindings, application.note_type.field_defs), "template": serialize_template(application.template)}


def _with_usage(template, usages, *, include_applications=False):
    result = {
        **serialize_template(template), "application_count": len(usages),
        "note_type_count": len({item["note_type_id"] for item in usages}),
    }
    if include_applications:
        result["applications"] = usages
    return result


def list_templates(*, user_id, include_archived=False, category=None, search=None, group="all"):
    if group not in {"all", "mine", "market", "standalone", "in_use"}:
        raise TemplateLibraryError("VALIDATION_ERROR", "Invalid library group.", field="group")
    templates = repository.library_query(db.session, user_id, include_archived=include_archived, category=category, search=search, group=group)
    usages = repository.template_usage(db.session, user_id, [item.id for item in templates])
    return {"schema_version": "template-library.v2", "items": [_with_usage(item, usages.get(item.id, [])) for item in templates]}


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
    schema = validate_input_schema(payload["input_schema"]) if "input_schema" in payload else effective_input_schema(template, getattr(template.note_type, "field_defs", ()))
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
    occurrence = text(payload.get("occurrence_key", "compat"), field="occurrence_key", maximum=64, required=True)
    def operation():
        template = _owned(user_id, template_id, lock=True)
        note_type = _note_type(user_id, note_type_id, lock=True)
        if template.archived_at:
            raise TemplateLibraryError("TEMPLATE_ARCHIVED", "Archived template cannot be attached.", status=409)
        application = db.session.execute(select(StudyApplication).where(StudyApplication.note_type_id == note_type.id, StudyApplication.template_id == template.id, StudyApplication.occurrence_key == occurrence).with_for_update()).scalar_one_or_none()
        if application is not None and application.status_code == "ACTIVE":
            raise TemplateLibraryError("APPLICATION_EXISTS", "This occurrence is already attached.", status=409)
        from app.services import study_content_delete_service as topology
        note_ids = list(db.session.execute(select(Note.id).where(Note.note_type_id == note_type.id, Note.user_id == user_id).order_by(Note.id)).scalars())
        routes = topology.lock_content_expansion_routes(db.session, actor_user_ids=(user_id,), note_ids=note_ids)
        plan = topology.prepare_content_expansion(db.session, routes=routes, note_ids=note_ids)
        topology.verify_content_expansion_scope(db.session, routes=routes, note_ids=note_ids)
        if application is None:
            application = StudyApplication(note_type=note_type, template=template, occurrence_key=occurrence, status_code="ACTIVE", input_bindings={}, position=0, is_default=False)
            db.session.add(application)
        else:
            application.status_code = "ACTIVE"
        _application_payload(application, payload, note_type)
        db.session.flush()
        existing = set(db.session.execute(select(Card.note_id).where(Card.application_id == application.id)).scalars())
        cards = [Card(note_id=note_id, template_id=template.id, application_id=application.id) for note_id in note_ids if note_id not in existing]
        db.session.add_all(cards)
        db.session.flush()
        topology.finalize_content_expansion(plan, new_cards=cards)
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
        application.status_code = "RETIRED"
        return lambda: serialize_application(application)
    return _commit(operation)
