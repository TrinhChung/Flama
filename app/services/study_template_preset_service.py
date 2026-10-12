"""User/deck presentation preferences, validated against the effective scope."""

from sqlalchemy import select
from sqlalchemy.orm import selectinload
from types import SimpleNamespace
from models import db
from models.deck import Deck
from models.note_type import NoteType
from models.study_template_preset import StudyTemplatePreset
from models.template import Template
from models.study_application import StudyApplication
from app.validators.template_library import TemplateLibraryError, body, validate_bindings, binding_warnings, validate_input_schema
from app.services import flashcards_share_service, study_composition_service
from app.services.template_library_service import effective_input_schema


def _scope(user_id, deck_id):
    deck = db.session.get(Deck, deck_id)
    clone = flashcards_share_service.resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=deck_id)
    if deck is None or (int(deck.owner_user_id or 0) != int(user_id) and clone is None):
        raise TemplateLibraryError("DECK_NOT_FOUND", "Deck not found.", status=404)
    return study_composition_service.list_available_compositions_for_scope("deck", deck_id, user_id)


def _row(user_id, deck_id, *, lock=False):
    statement = select(StudyTemplatePreset).where(StudyTemplatePreset.user_id == user_id, StudyTemplatePreset.deck_id == deck_id)
    if lock:
        statement = statement.with_for_update()
    return db.session.execute(statement).scalar_one_or_none()


def _serialize(row, available):
    valid = {item.composition_id for item in available}
    selected = list(row.selected_compositions or []) if row is not None else []
    return {"schema_version": "study-template-preset.v2", "selected_compositions": selected, "input_bindings": row.input_bindings or {} if row is not None else {}, "ask_before_study": bool(row.ask_before_study) if row is not None else True, "stale_compositions": [item for item in selected if item not in valid]}


def get_preset(*, user_id, deck_id):
    available = _scope(user_id, deck_id)
    return {"deck_id": deck_id, **_serialize(_row(user_id, deck_id), available)}


def binding_context(composition, *, clone_scope=None, template_overrides=None, templates=None, note_types=None):
    """Use the same source and field scope as the study renderer."""
    note_type = note_types[composition.note_type_id] if note_types is not None else db.session.get(NoteType, composition.note_type_id)
    template = templates[composition.template_id] if templates is not None else db.session.get(Template, composition.template_id)
    fields = list(note_type.field_defs)
    if composition.context_kind == "installed_source":
        if clone_scope is None:
            raise TemplateLibraryError("COMPOSITION_OUT_OF_SCOPE", "Installed composition requires its deck scope.", status=403)
        schema = flashcards_share_service.build_clone_schema_view(
            install=clone_scope.install,
            source_note_type_id=clone_scope.install.source_note_type_id or composition.note_type_id,
        )
        fields = list(schema.field_defs)
        if template_overrides is None:
            from app.repositories import template_release_repository
            template_overrides = template_release_repository.load_effective_template_overrides(
                db.session, user_id=clone_scope.install.user_id,
                source_template_ids=[template.id],
                release_pins=template_release_repository.deck_pins(db.session, clone_scope.install.applied_release_id),
            )
    if template_overrides is not None:
        template = template_overrides.get(template.id, template)
    return template, fields


def template_inputs_for_compositions(compositions, *, user_id, clone_scope=None):
    """Preparation DTO, resolved in batches without reading note content."""
    from app.repositories import template_release_repository
    from app.services.effective_template_service import resolve_effective_template

    if not compositions:
        return {}
    template_ids = sorted({item.template_id for item in compositions})
    note_type_ids = sorted({item.note_type_id for item in compositions})
    templates, note_types, applications = {}, {}, {}
    for offset in range(0, len(template_ids), 500):
        ids = template_ids[offset:offset + 500]
        templates.update({item.id: item for item in db.session.scalars(select(Template).where(Template.id.in_(ids)))})
        for application in db.session.scalars(select(StudyApplication).where(StudyApplication.template_id.in_(ids), StudyApplication.status_code == "ACTIVE")):
            applications[(application.note_type_id, application.template_id)] = application
    for offset in range(0, len(note_type_ids), 500):
        note_types.update({item.id: item for item in db.session.scalars(select(NoteType).where(
            NoteType.id.in_(note_type_ids[offset:offset + 500]),
        ).options(selectinload(NoteType.field_defs)))})
    pins = template_release_repository.deck_pins(db.session, clone_scope.install.applied_release_id) if (
        clone_scope is not None and clone_scope.install.applied_release_id
    ) else {}
    overrides = template_release_repository.load_effective_template_overrides(
        db.session, user_id=user_id, source_template_ids=template_ids, release_pins=pins,
    )
    result = {}
    for composition in compositions:
        application = applications.get((composition.note_type_id, composition.template_id))
        template, fields = binding_context(composition, clone_scope=clone_scope,
            template_overrides=overrides, templates=templates, note_types=note_types)
        source = resolve_effective_template(SimpleNamespace(
            template=templates[composition.template_id], application=application,
            application_id=application.id if application else None,
        ), clone_scope, template_overrides=overrides)
        schema = validate_input_schema(effective_input_schema(template, fields))
        bindings = getattr(source, "input_bindings", None)
        if bindings is None:
            names = {field.name: str(field.id) for field in fields}
            bindings = {item["key"]: names.get(item["key"]) for item in schema}
        else:
            bindings = {item["key"]: bindings.get(item["key"]) for item in schema}
        from app.services.study_artifact_service import serialize_field_defs
        result[composition.composition_id] = {
            "input_schema": schema,
            "field_defs": serialize_field_defs(fields),
            "input_bindings": bindings,
            "warnings": binding_warnings(schema, bindings, fields),
        }
    return result


def validate_session_bindings(composition, bindings, *, clone_scope=None, template_overrides=None):
    template, fields = binding_context(
        composition, clone_scope=clone_scope, template_overrides=template_overrides,
    )
    return validate_bindings(validate_input_schema(effective_input_schema(template, fields)), bindings, fields)


def save_preset(*, user_id, deck_id, payload):
    body(payload, {"selected_compositions", "input_bindings", "ask_before_study"})
    available = _scope(user_id, deck_id)
    by_id = {item.composition_id: item for item in available}
    selected = payload.get("selected_compositions", [])
    bindings = payload.get("input_bindings", {})
    ask = payload.get("ask_before_study", True)
    if not isinstance(selected, list) or any(not isinstance(item, str) for item in selected) or len(set(selected)) != len(selected):
        raise TemplateLibraryError("VALIDATION_ERROR", "selected_compositions must be a unique string array.", field="selected_compositions")
    if any(item not in by_id for item in selected):
        raise TemplateLibraryError("COMPOSITION_OUT_OF_SCOPE", "Selected composition is outside this deck.", status=403)
    if not isinstance(bindings, dict) or any(key not in by_id for key in bindings) or not isinstance(ask, bool):
        raise TemplateLibraryError("VALIDATION_ERROR", "Invalid preset bindings or prompt preference.")
    validated = {}
    clone_scope = flashcards_share_service.resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=deck_id)
    for composition_id, mapping in bindings.items():
        composition = by_id[composition_id]
        validated[composition_id] = validate_session_bindings(composition, mapping, clone_scope=clone_scope)
    try:
        # Serialize concurrent creation through a real existing parent row.
        db.session.execute(select(Deck.id).where(Deck.id == deck_id).with_for_update()).scalar_one()
        row = _row(user_id, deck_id, lock=True)
        if row is None:
            row = StudyTemplatePreset(user_id=user_id, deck_id=deck_id)
            db.session.add(row)
        row.selected_compositions, row.input_bindings, row.ask_before_study = selected, validated, ask
        db.session.commit()
        return {"deck_id": deck_id, **_serialize(row, available)}
    except Exception:
        db.session.rollback()
        raise


def resolve_session_preset(user_id, scope_type, scope_id, requested_composition_id):
    if requested_composition_id is not None or scope_type != "deck":
        return requested_composition_id
    row = _row(user_id, int(scope_id))
    if row is None or row.ask_before_study or not (row.selected_compositions or []):
        return None
    available = _scope(user_id, int(scope_id))
    valid = {item.composition_id for item in available}
    saved = next((item for item in (row.selected_compositions or []) if item in valid), None)
    if saved is None:
        raise TemplateLibraryError("COMPOSITION_STALE", "Saved study composition is no longer available.", status=409)
    return saved


def session_input_bindings(user_id, scope_type, scope_id, composition_id):
    if scope_type != "deck":
        return None
    row = _row(user_id, int(scope_id))
    return (row.input_bindings or {}).get(composition_id) if row is not None else None
