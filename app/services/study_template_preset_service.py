"""User/deck presentation preferences, validated against the effective scope."""

from sqlalchemy import select
from models import db
from models.deck import Deck
from models.note_type import NoteType
from models.study_template_preset import StudyTemplatePreset
from models.template import Template
from app.validators.template_library import TemplateLibraryError, body, validate_bindings
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
    if not isinstance(bindings, dict) or any(key not in selected for key in bindings) or not isinstance(ask, bool):
        raise TemplateLibraryError("VALIDATION_ERROR", "Invalid preset bindings or prompt preference.")
    validated = {}
    for composition_id, mapping in bindings.items():
        composition = by_id[composition_id]
        note_type = db.session.get(NoteType, composition.note_type_id)
        template = db.session.get(Template, composition.template_id)
        # Clone sources use the install's pinned/copy input schema.
        if composition.context_kind == "installed_source":
            from app.repositories import template_release_repository
            scope = flashcards_share_service.resolve_clone_scope_for_local_deck(user_id=user_id, local_deck_id=deck_id)
            overrides = template_release_repository.load_effective_template_overrides(db.session, user_id=user_id, source_template_ids=[template.id], release_pins=template_release_repository.deck_pins(db.session, scope.install.applied_release_id))
            template = overrides.get(template.id, template)
        validated[composition_id] = validate_bindings(effective_input_schema(template, note_type.field_defs), mapping, note_type.field_defs)
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
    if row is None or row.ask_before_study or len(row.selected_compositions or []) != 1:
        return None
    available = _scope(user_id, int(scope_id))
    saved = row.selected_compositions[0]
    if saved not in {item.composition_id for item in available}:
        raise TemplateLibraryError("COMPOSITION_STALE", "Saved study composition is no longer available.", status=409)
    return saved


def session_input_bindings(user_id, scope_type, scope_id, composition_id):
    if scope_type != "deck":
        return None
    row = _row(user_id, int(scope_id))
    return (row.input_bindings or {}).get(composition_id) if row is not None else None
