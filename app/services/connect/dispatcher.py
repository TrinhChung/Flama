"""Shared AnkiConnect command dispatcher; adapters only supply policy."""
from typing import Any
from flask import current_app

from app.services import flama_connect_media_service
from app.services.connect.registry import FLAMA_CONNECT_PROTOCOL_VERSION, MAX_NOTES_PER_REQUEST, MAX_MULTI_ACTIONS, SUPPORTED_ACTIONS
from app.services.connect.actions import (
    CheckBatchContext,
    add_note,
    check_note,
    find_notes,
    get_user_info,
)
from app.services.connect.base import ConnectError
from app.services.connect.import_cards import (
    complete_import_session,
    get_import_note_statuses,
    get_import_status,
    import_cards,
)
from app.services.connect.import_session import create_import_session
from app.services.connect.resolvers import (
    deck_names,
    model_field_names,
    model_names,
)

def dispatch(user_id: int, action: str, params: dict[str, Any], *, standard=False, uow=None, scopes=None) -> Any:
    if action == "version":
        return FLAMA_CONNECT_PROTOCOL_VERSION
    if action == "apiReflect":
        scopes = params.get("scopes")
        actions = params.get("actions")
        if (
            not isinstance(scopes, list)
            or len(scopes) > 10
            or any(not isinstance(scope, str) or len(scope) > 64 for scope in scopes)
        ):
            raise ConnectError("scopes must be an array of strings")
        if actions is not None and (
            not isinstance(actions, list)
            or len(actions) > 100
            or any(not isinstance(item, str) or len(item) > 64 for item in actions)
        ):
            raise ConnectError("actions must be null or an array of strings")
        supported = [item for item in SUPPORTED_ACTIONS if not (standard and item == "storeMediaFile" and not current_app.config.get("CONNECT_ANKI_MEDIA_ENABLED", False))]
        reflected = supported if actions is None else [item for item in actions if item in supported]
        return {"scopes": [scope for scope in scopes if scope == "actions"], "actions": reflected}
    if action == "validateKey":
        return {"status": "valid", "userId": user_id}
    if action == "userInfo":
        return get_user_info(user_id)
    if action == "createImportSession":
        return create_import_session(user_id, params)
    if action == "importCards":
        return import_cards(user_id, params)
    if action == "getImportStatus":
        return get_import_status(user_id, params.get("importSessionId"))
    if action == "completeImportSession":
        return complete_import_session(user_id, params.get("importSessionId"))
    if action == "deckNames":
        return deck_names(user_id)
    if action == "modelNames":
        return model_names(user_id)
    if action == "modelFieldNames":
        return model_field_names(user_id, params.get("modelName"))
    if action in {"canAddNotes", "canAddNotesWithErrorDetail"}:
        notes = params.get("notes")
        if not isinstance(notes, list) or len(notes) > MAX_NOTES_PER_REQUEST:
            raise ConnectError(f"notes must be an array with at most {MAX_NOTES_PER_REQUEST} entries")
        context = CheckBatchContext(user_id)
        checks = [check_note(user_id, note, context=context, standard=standard) for note in notes]
        if action == "canAddNotes":
            return [allowed for allowed, _error in checks]
        return [{"canAdd": allowed, "error": error} for allowed, error in checks]
    if action == "findNotes":
        return find_notes(user_id, params.get("query"), strict=standard)
    if action == "addNote":
        return add_note(user_id, params.get("note"), standard=standard, uow=uow, scopes=scopes)
    if action == "storeMediaFile":
        if params.get("path") is not None or params.get("url") is not None:
            raise ConnectError("Flama Connect không nhận media từ đường dẫn hoặc URL.")
        if "deleteExisting" in params and not isinstance(params.get("deleteExisting"), bool):
            raise ConnectError("deleteExisting phải là boolean.")
        try:
            if standard:
                if not current_app.config.get("CONNECT_ANKI_MEDIA_ENABLED", False):
                    raise ConnectError("media mining is disabled")
                from app.services.connect.mining_media import stage
                return stage(user_id, params, uow)
            if params.get("importSessionId") is not None:
                return flama_connect_media_service.stage_import_media(
                    user_id=user_id,
                    session_id=params.get("importSessionId"),
                    filename=params.get("filename"),
                    data=params.get("data"),
                    media_kind=params.get("mediaKind"),
                )
            return flama_connect_media_service.stage_mp3(
                user_id=user_id,
                filename=params.get("filename"),
                data=params.get("data"),
            )
        except flama_connect_media_service.ConnectMediaError as exc:
            raise ConnectError(str(exc)) from exc
    raise ConnectError("unsupported action")


