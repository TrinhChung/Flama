"""Small, deliberately constrained Flama Connect protocol surface for Yomitan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import re
import unicodedata
from typing import Any

import uuid

from app.services import flashcards_share_service, flama_connect_media_service
from app.validators.flashcard_input import RequestValidationError, validate_note_create_request
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.connect_note_ref import ConnectNoteRef
from models.connect_pending_media import ConnectPendingMedia
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.template import Template
from models.user import User


FLAMA_CONNECT_PROTOCOL_VERSION = 6
MAX_NOTES_PER_REQUEST = 50
MAX_MULTI_ACTIONS = 10
SUPPORTED_ACTIONS = (
    "version",
    "apiReflect",
    "validateKey",
    "userInfo",
    "deckNames",
    "modelNames",
    "modelFieldNames",
    "canAddNotes",
    "canAddNotesWithErrorDetail",
    "findNotes",
    "multi",
    "addNote",
    "storeMediaFile",
    "createImportSession",
    "importCards",
    "getImportStatus",
)
_QUERY_CLAUSE_RE = re.compile(r'"((?:\\.|[^"\\])*)"')


class ConnectError(ValueError):
    pass


@dataclass(frozen=True)
class PreparedNote:
    deck: Deck
    note_type: NoteType
    fields: dict[str, str]
    tags: list[str]
    identity_field: FieldDef
    identity_value: str
    allow_duplicate: bool
    clone_map: DeckCloneDeckMap | None
    pending_audio: dict[str, ConnectPendingMedia]


def _normalized_identity(value: object) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return " ".join(text.replace("\r\n", "\n").replace("\r", "\n").split()).strip()


def _deck_path(deck: Deck) -> str:
    names: list[str] = []
    current: Deck | None = deck
    seen: set[int] = set()
    while current is not None and current.id not in seen and len(names) < 64:
        seen.add(current.id)
        names.append(current.name)
        current = current.parent
    return "::".join(reversed(names))


def _owned_decks(user_id: int) -> list[Deck]:
    return (
        Deck.query.filter(Deck.owner_user_id == user_id, Deck.deleted_at.is_(None))
        .order_by(Deck.position.asc(), Deck.id.asc())
        .all()
    )


def deck_names(user_id: int) -> list[str]:
    return sorted({_deck_path(deck) for deck in _owned_decks(user_id)}, key=str.casefold)


def _resolve_deck(user_id: int, deck_name: object, *, lock: bool = False, allow_create: bool = False) -> Deck:
    if not isinstance(deck_name, str) or not deck_name.strip() or len(deck_name) > 2048:
        raise ConnectError("Thiếu deckName. Vui lòng chọn deck đích trong Yomitan.")
    target = deck_name.strip()

    # 1. Search by exact full path match (e.g. "Japanese::N3")
    owned = _owned_decks(user_id)
    matches = [deck for deck in owned if _deck_path(deck) == target]
    if len(matches) >= 1:
        target_deck = matches[0]
    else:
        # 2. Case-insensitive path match or single name match
        lower_target = target.lower()
        matches = [deck for deck in owned if _deck_path(deck).lower() == lower_target or deck.name.lower() == lower_target]
        if len(matches) >= 1:
            target_deck = matches[0]
        elif allow_create:
            tokens = [t.strip() for t in target.split("::") if t.strip()]
            if not tokens:
                raise ConnectError("Không tìm thấy deck đích hoặc bạn không có quyền ghi vào deck này.")
            current_parent_id = None
            final_deck = None
            for token in tokens:
                existing = Deck.query.filter(
                    Deck.owner_user_id == user_id,
                    Deck.parent_id == current_parent_id if current_parent_id is not None else Deck.parent_id.is_(None),
                    Deck.name == token,
                    Deck.deleted_at.is_(None),
                ).first()
                if existing:
                    final_deck = existing
                    current_parent_id = existing.id
                else:
                    max_pos = db.session.query(db.func.max(Deck.position)).filter(
                        Deck.parent_id == current_parent_id if current_parent_id is not None else Deck.parent_id.is_(None)
                    ).scalar()
                    pos = int(max_pos or 0) + 1
                    node = Deck(
                        owner_user_id=user_id,
                        parent_id=current_parent_id,
                        name=token,
                        position=pos,
                    )
                    db.session.add(node)
                    db.session.flush()
                    final_deck = node
                    current_parent_id = node.id
            db.session.commit()
            target_deck = final_deck
        else:
            raise ConnectError("Không tìm thấy deck đích hoặc bạn không có quyền ghi vào deck này.")

    if not lock:
        return target_deck

    deck = (
        Deck.query.filter(Deck.id == target_deck.id, Deck.owner_user_id == user_id, Deck.deleted_at.is_(None))
        .with_for_update()
        .first()
    )
    if deck is None:
        return target_deck
    return deck


def _accessible_note_types(user_id: int) -> list[NoteType]:
    installed_ids = [
        r[0]
        for r in db.session.query(NoteTypeInstall.installed_note_type_id)
        .filter_by(user_id=user_id)
        .all()
        if r[0]
    ]
    return (
        NoteType.query.filter(
            (NoteType.user_id == user_id)
            | (NoteType.id.in_(installed_ids))
        )
        .order_by(NoteType.name.asc(), NoteType.id.asc())
        .all()
    )


def model_names(user_id: int) -> list[str]:
    return [row.name for row in _accessible_note_types(user_id)]


def _resolve_note_type(user_id: int, model_name: object) -> NoteType:
    if not isinstance(model_name, str) or not model_name.strip() or len(model_name) > 255:
        raise ConnectError("modelName is required")
    target = model_name.strip()
    note_types = _accessible_note_types(user_id)
    id_matches = [nt for nt in note_types if nt.id == target]
    if id_matches:
        return id_matches[0]

    matches = [nt for nt in note_types if nt.name == target]
    if not matches:
        matches = [nt for nt in note_types if nt.name.lower() == target.lower()]
    if len(matches) != 1:
        raise ConnectError("model was not found or is ambiguous")
    return matches[0]


def _identity_field(note_type: NoteType) -> FieldDef:
    rows = [field for field in note_type.field_defs if field.identity_role == "primary"]
    if len(rows) != 1:
        raise ConnectError("model must declare exactly one primary identity field")
    field = rows[0]
    if field.field_type != "text" or not field.required:
        raise ConnectError("the primary identity field must be required text")
    return field


def model_field_names(user_id: int, model_name: object) -> list[str]:
    note_type = _resolve_note_type(user_id, model_name)
    identity = _identity_field(note_type)
    ordered = sorted(note_type.field_defs, key=lambda item: (item.position, item.id))
    return [identity.name] + [field.name for field in ordered if field.id != identity.id]


def _clone_map_for_deck(user_id: int, deck_id: int) -> DeckCloneDeckMap | None:
    return (
        DeckCloneDeckMap.query.join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id)
        .filter(
            DeckCloneDeckMap.local_deck_id == deck_id,
            DeckInstall.user_id == user_id,
            DeckInstall.clone_mode == "logical_overlay",
        )
        .first()
    )


def _parse_note(user_id: int, raw_note: object, *, lock_deck: bool = False) -> PreparedNote:
    if not isinstance(raw_note, dict):
        raise ConnectError("note must be an object")
    unknown = set(raw_note) - {"deckName", "modelName", "fields", "tags", "options", "audio", "picture", "video"}
    if unknown:
        raise ConnectError("note contains unsupported properties")
    for media_key in ("audio", "picture", "video"):
        if raw_note.get(media_key):
            raise ConnectError("media import is not supported in this version")

    deck = _resolve_deck(user_id, raw_note.get("deckName"), lock=lock_deck)
    note_type = _resolve_note_type(user_id, raw_note.get("modelName"))
    if deck.note_type_id is not None and deck.note_type_id != note_type.id:
        raise ConnectError("deck is bound to a different model")
    if not note_type.templates:
        raise ConnectError("model has no card template")

    fields = raw_note.get("fields")
    if not isinstance(fields, dict) or len(fields) > 100:
        raise ConnectError("fields must be an object with at most 100 entries")
    if any(not isinstance(key, str) or not isinstance(value, str) for key, value in fields.items()):
        raise ConnectError("field names and values must be strings")
    if any(
        not key
        or len(key) > 255
        or any(ord(character) < 32 or ord(character) == 127 for character in key)
        for key in fields
    ):
        raise ConnectError("field names are invalid")
    field_defs_by_name = {field.name: field for field in note_type.field_defs}
    if any(
        field_defs_by_name.get(field_name) is not None
        and field_defs_by_name[field_name].field_type in {"image", "diagram"}
        and bool(str(value or "").strip())
        for field_name, value in fields.items()
    ):
        raise ConnectError("Flama Connect hiện chỉ hỗ trợ media audio MP3.")
    options = raw_note.get("options") or {}
    if not isinstance(options, dict):
        raise ConnectError("options must be an object")
    unknown_options = set(options) - {"allowDuplicate", "duplicateScope", "duplicateScopeOptions"}
    if unknown_options:
        raise ConnectError("options contains unsupported properties")
    if "allowDuplicate" in options and not isinstance(options.get("allowDuplicate"), bool):
        raise ConnectError("allowDuplicate must be a boolean")
    if "duplicateScope" in options and options.get("duplicateScope") not in {"collection", "deck", "deck-root"}:
        raise ConnectError("duplicateScope is invalid")
    duplicate_options = options.get("duplicateScopeOptions")
    if duplicate_options is not None:
        if not isinstance(duplicate_options, dict):
            raise ConnectError("duplicateScopeOptions must be an object")
        if set(duplicate_options) - {"deckName", "checkChildren", "checkAllModels"}:
            raise ConnectError("duplicateScopeOptions contains unsupported properties")
        # This is only Yomitan's duplicate-scope override. It may be null and
        # must never replace note.deckName as the destination deck.
        duplicate_deck_name = duplicate_options.get("deckName")
        if "deckName" in duplicate_options and duplicate_deck_name is not None:
            if (
                not isinstance(duplicate_deck_name, str)
                or len(duplicate_deck_name) > 2048
                or any(ord(character) < 32 or ord(character) == 127 for character in duplicate_deck_name)
            ):
                raise ConnectError("duplicateScopeOptions.deckName must be null or a valid string")
        for option_name in ("checkChildren", "checkAllModels"):
            if option_name in duplicate_options and not isinstance(duplicate_options.get(option_name), bool):
                raise ConnectError(f"duplicateScopeOptions.{option_name} must be a boolean")
    tags = raw_note.get("tags") or []
    try:
        pending_audio, allowed_media_references = flama_connect_media_service.resolve_pending_audio(
            user_id=user_id,
            note_type=note_type,
            raw_fields=fields,
            lock=lock_deck,
        )
    except flama_connect_media_service.ConnectMediaError as exc:
        raise ConnectError(str(exc)) from exc
    try:
        validated = validate_note_create_request(
            note_type=note_type,
            payload={
                "note_type_id": note_type.id,
                "deck_id": deck.id,
                "field_values": fields,
                "tags": tags,
            },
            note_media_ids=allowed_media_references,
        )
    except RequestValidationError as exc:
        raise ConnectError(str(exc)) from exc

    identity = _identity_field(note_type)
    identity_value = _normalized_identity(validated.field_values.get(identity.name))
    if not identity_value:
        raise ConnectError("the primary identity field cannot be empty")
    return PreparedNote(
        deck=deck,
        note_type=note_type,
        fields=validated.field_values,
        tags=list(validated.tags or []),
        identity_field=identity,
        identity_value=identity_value,
        allow_duplicate=bool(options.get("allowDuplicate", False)),
        clone_map=_clone_map_for_deck(user_id, deck.id),
        pending_audio=pending_audio,
    )


def _is_duplicate(user_id: int, prepared: PreparedNote) -> bool:
    local_notes = Note.query.filter_by(user_id=user_id, deck_id=prepared.deck.id).all()
    for note in local_notes:
        if _normalized_identity((note.field_values or {}).get(prepared.identity_field.name)) == prepared.identity_value:
            return True

    clone_map = prepared.clone_map
    if clone_map is None:
        return False
    install = clone_map.deck_install
    source_deck = db.session.get(Deck, clone_map.source_deck_id)
    if source_deck is None:
        return False
    schema = flashcards_share_service.build_clone_schema_view(
        install=install,
        source_note_type_id=source_deck.note_type_id,
    )
    identity_name = prepared.identity_field.name
    source_query = Note.query.filter(Note.deck_id == clone_map.source_deck_id)
    if install.source_owner_user_id is not None:
        source_query = source_query.filter(Note.user_id == install.source_owner_user_id)
    if install.base_snapshot_at or install.installed_at:
        source_query = source_query.filter(Note.created_at <= (install.base_snapshot_at or install.installed_at))
    for source_note in source_query.all():
        values = flashcards_share_service.apply_clone_note_field_overrides(
            install=install,
            source_note=source_note,
            schema_view=schema,
        )
        if _normalized_identity(values.get(identity_name)) == prepared.identity_value:
            return True
    return False


def _ensure_note_ref(note: Note, user_id: int) -> ConnectNoteRef:
    row = ConnectNoteRef.query.filter_by(
        note_id=note.id,
        user_id=user_id,
        provider="yomitan",
    ).first()
    if row is None:
        row = ConnectNoteRef(note_id=note.id, user_id=user_id, provider="yomitan")
        db.session.add(row)
        db.session.flush()
    return row


def check_note(user_id: int, raw_note: object) -> tuple[bool, str | None]:
    try:
        prepared = _parse_note(user_id, raw_note, lock_deck=False)
        if not prepared.allow_duplicate and _is_duplicate(user_id, prepared):
            return False, "cannot create note because it is a duplicate in the target deck"
        return True, None
    except ConnectError as exc:
        return False, str(exc)


def _find_existing_note(user_id: int, prepared: PreparedNote) -> Note | None:
    local_notes = Note.query.filter_by(user_id=user_id, deck_id=prepared.deck.id).all()
    for note in local_notes:
        if _normalized_identity((note.field_values or {}).get(prepared.identity_field.name)) == prepared.identity_value:
            return note
    return None


def add_note(user_id: int, raw_note: object) -> int:
    prepared = _parse_note(user_id, raw_note, lock_deck=True)
    if not prepared.allow_duplicate and _is_duplicate(user_id, prepared):
        existing_note = _find_existing_note(user_id, prepared)
        if existing_note:
            # Update fields if new content is present
            updated = False
            field_vals = dict(existing_note.field_values or {})
            for k, v in prepared.fields.items():
                if v and field_vals.get(k) != v:
                    field_vals[k] = v
                    updated = True
            if updated:
                existing_note.field_values = field_vals
                db.session.commit()
            return existing_note.id
        raise ConnectError("cannot create note because it is a duplicate in the target deck")
    if prepared.deck.note_type_id is None:
        prepared.deck.note_type_id = prepared.note_type.id

    materialized = None
    try:
        note = Note(
            note_type_id=prepared.note_type.id,
            user_id=user_id,
            deck_id=prepared.deck.id,
            field_values=prepared.fields,
            tags=prepared.tags,
        )
        db.session.add(note)
        db.session.flush()
        templates = Template.query.filter_by(note_type_id=prepared.note_type.id).order_by(Template.position.asc()).all()
        if not templates:
            tmpl = Template(
                note_type_id=prepared.note_type.id,
                name="Card 1",
                position=0,
                front_format="{{Front}}",
                back_format="{{Back}}",
            )
            db.session.add(tmpl)
            db.session.flush()
            templates = [tmpl]
        for template in templates:
            db.session.add(Card(note_id=note.id, template_id=template.id))

        materialized = flama_connect_media_service.materialize_audio(
            user_id=user_id,
            note=note,
            attachments=prepared.pending_audio,
        )

        if prepared.clone_map is not None:
            install = prepared.clone_map.deck_install
            db.session.add(DeckCloneAddedNote(deck_install_id=install.id, note_id=note.id))
            install.last_sync_status = "needs_sync"
            install.last_activity_at = datetime.utcnow()

        ref = _ensure_note_ref(note, user_id)
        db.session.add(
            AuditLog(
                user_id=user_id,
                action="connect.note.create",
                payload={
                    "note_id": note.id,
                    "connect_note_id": int(ref.id),
                    "deck_id": prepared.deck.id,
                    "note_type_id": prepared.note_type.id,
                    "clone_install_id": prepared.clone_map.deck_install_id if prepared.clone_map else None,
                    "media_count": len(prepared.pending_audio),
                },
            )
        )
        db.session.commit()
    except flama_connect_media_service.ConnectMediaError as exc:
        db.session.rollback()
        flama_connect_media_service.compensate_materialized(materialized)
        raise ConnectError(str(exc)) from exc
    except Exception:
        db.session.rollback()
        flama_connect_media_service.compensate_materialized(materialized)
        raise
    flama_connect_media_service.finalize_materialized(materialized)
    return int(ref.id)


def _unescape_query_clause(value: str) -> str:
    return value.replace('\\"', '"').replace("\\\\", "\\")


def find_notes(user_id: int, query: object) -> list[int]:
    if not isinstance(query, str) or len(query) > 2048:
        raise ConnectError("query must be a string no longer than 2048 characters")
    deck_name: str | None = None
    field_name: str | None = None
    field_value: str | None = None
    for raw_clause in _QUERY_CLAUSE_RE.findall(query):
        clause = _unescape_query_clause(raw_clause)
        if ":" not in clause:
            continue
        key, value = clause.split(":", 1)
        if key.casefold() == "deck":
            deck_name = value
        else:
            field_name, field_value = key, value
    if deck_name is None or field_name is None or field_value is None:
        return []
    deck = _resolve_deck(user_id, deck_name)
    expected = _normalized_identity(field_value)
    results: list[int] = []
    for note in Note.query.filter_by(user_id=user_id, deck_id=deck.id).all():
        note_type = db.session.get(NoteType, note.note_type_id)
        if note_type is None:
            continue
        try:
            identity = _identity_field(note_type)
        except ConnectError:
            continue
        if identity.name.casefold() != field_name.casefold():
            continue
        if _normalized_identity((note.field_values or {}).get(identity.name)) == expected:
            results.append(int(_ensure_note_ref(note, user_id).id))
    clone_map = _clone_map_for_deck(user_id, deck.id)
    if clone_map is not None:
        install = clone_map.deck_install
        source_deck = db.session.get(Deck, clone_map.source_deck_id)
        local_note_type = db.session.get(NoteType, deck.note_type_id) if deck.note_type_id else None
        if source_deck is not None and local_note_type is not None:
            try:
                local_identity = _identity_field(local_note_type)
            except ConnectError:
                local_identity = None
            if local_identity is not None and local_identity.name.casefold() == field_name.casefold():
                schema = flashcards_share_service.build_clone_schema_view(
                    install=install,
                    source_note_type_id=source_deck.note_type_id,
                )
                source_query = Note.query.filter(Note.deck_id == clone_map.source_deck_id)
                if install.source_owner_user_id is not None:
                    source_query = source_query.filter(Note.user_id == install.source_owner_user_id)
                if install.base_snapshot_at or install.installed_at:
                    source_query = source_query.filter(
                        Note.created_at <= (install.base_snapshot_at or install.installed_at)
                    )
                for source_note in source_query.all():
                    values = flashcards_share_service.apply_clone_note_field_overrides(
                        install=install,
                        source_note=source_note,
                        schema_view=schema,
                    )
                    if _normalized_identity(values.get(local_identity.name)) == expected:
                        results.append(int(_ensure_note_ref(source_note, user_id).id))
    return sorted(set(results))


def get_user_info(user_id: int) -> dict[str, Any]:
    user = db.session.get(User, user_id)
    if user is None:
        raise ConnectError("User not found")
    return {
        "userId": user.id,
        "username": user.username,
        "displayName": getattr(user, "username", "Flama User"),
        "workspace": "default",
        "importPermission": True,
        "uploadLimit": 1048576,
    }


def create_import_session(user_id: int, params: dict[str, Any]) -> dict[str, Any]:
    session_id = f"import_session_{uuid.uuid4().hex}"
    selected_decks = params.get("selectedDecks", [])
    if isinstance(selected_decks, list):
        for deck_name in selected_decks:
            if isinstance(deck_name, str) and deck_name.strip():
                try:
                    _resolve_deck(user_id, deck_name.strip(), allow_create=True)
                except Exception:
                    pass
    return {
        "importSessionId": session_id,
        "flamaUserId": user_id,
        "source": params.get("source", "Anki"),
        "startedAt": datetime.utcnow().isoformat() + "Z",
        "selectedDecks": selected_decks,
        "totalNotes": params.get("totalNotes", 0),
        "totalMedia": params.get("totalMedia", 0),
        "appVersion": params.get("appVersion", "1.0.0"),
    }


def import_cards(user_id: int, params: dict[str, Any]) -> dict[str, Any]:
    cards = params.get("cards")
    if not isinstance(cards, list):
        raise ConnectError("cards must be an array")
    results = []
    for card_data in cards:
        if not isinstance(card_data, dict):
            continue
        anki_note_id = card_data.get("ankiNoteId")
        content_hash = card_data.get("contentHash", "")
        idempotency_key = f"anki:{user_id}:{anki_note_id}:{content_hash}"
        note_payload = card_data.get("note")
        if note_payload and isinstance(note_payload, dict):
            try:
                note_id = add_note(user_id, note_payload)
                results.append({"ankiNoteId": anki_note_id, "imported": True, "noteId": note_id, "idempotencyKey": idempotency_key})
            except Exception as exc:
                results.append({"ankiNoteId": anki_note_id, "imported": False, "error": str(exc)})
        else:
            results.append({"ankiNoteId": anki_note_id, "imported": True, "noteId": None, "idempotencyKey": idempotency_key})
    return {"importSessionId": params.get("importSessionId"), "results": results}


def dispatch(user_id: int, action: str, params: dict[str, Any]) -> Any:
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
        reflected = list(SUPPORTED_ACTIONS) if actions is None else [item for item in actions if item in SUPPORTED_ACTIONS]
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
        return {"importSessionId": params.get("importSessionId"), "status": "completed"}
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
        checks = [check_note(user_id, note) for note in notes]
        if action == "canAddNotes":
            return [allowed for allowed, _error in checks]
        return [{"canAdd": allowed, "error": error} for allowed, error in checks]
    if action == "findNotes":
        return find_notes(user_id, params.get("query"))
    if action == "addNote":
        return add_note(user_id, params.get("note"))
    if action == "storeMediaFile":
        if params.get("path") is not None or params.get("url") is not None:
            raise ConnectError("Flama Connect không nhận media từ đường dẫn hoặc URL.")
        if "deleteExisting" in params and not isinstance(params.get("deleteExisting"), bool):
            raise ConnectError("deleteExisting phải là boolean.")
        try:
            return flama_connect_media_service.stage_mp3(
                user_id=user_id,
                filename=params.get("filename"),
                data=params.get("data"),
            )
        except flama_connect_media_service.ConnectMediaError as exc:
            raise ConnectError(str(exc)) from exc
    raise ConnectError("unsupported action")

