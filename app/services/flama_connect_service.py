"""Small, deliberately constrained Flama Connect protocol surface for Yomitan."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta
import hashlib
import json
import math
import re
import unicodedata
from typing import Any

from sqlalchemy.orm import selectinload

from app.services import flashcards_share_service, flama_connect_media_service
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.validators.flashcard_input import RequestValidationError, validate_note_create_request
from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.connect_note_ref import ConnectNoteRef
from models.connect_pending_media import ConnectPendingMedia
from models.connect_import_session import ConnectImportSession
from models.connect_note_type_ref import ConnectNoteTypeRef
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_deck_ref import ConnectSourceDeckRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.deck import Deck
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_install import DeckInstall
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.media_asset import MediaAsset
from models.template import Template
from models.user import User


FLAMA_CONNECT_PROTOCOL_VERSION = 6
MAX_NOTES_PER_REQUEST = 50
MAX_MULTI_ACTIONS = 10
SUPPORTED_ACTIONS = (
    "version",
    "apiReflect",
    "deckNames",
    "modelNames",
    "modelFieldNames",
    "canAddNotes",
    "canAddNotesWithErrorDetail",
    "findNotes",
    "multi",
    "addNote",
    "storeMediaFile",
)
IMPORT_SESSION_MODES = {"strict", "auto_sync_missing"}
IMPORT_SESSION_READY = "note_types_ready"
IMPORT_SESSION_TTL_HOURS = 24
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
    pending_import_media: dict[str, Any]


@dataclass(frozen=True)
class ImportBatchContext:
    """Stable schema/deck state reused by every note in one transport package."""

    note_types_by_id: dict[str, NoteType]
    note_type_hashes_by_id: dict[str, str]
    decks_by_path: dict[str, Deck]
    clone_maps_by_deck_id: dict[int, DeckCloneDeckMap]


@dataclass(frozen=True)
class NormalizedNoteTypePlan:
    source_model_id: str
    source_model_name: str
    target_note_type_id: str | None
    fields: tuple[dict[str, Any], ...]
    templates: tuple[dict[str, str], ...]
    field_mapping: dict[str, str]
    schema_hash: str


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
        # 2. Case-insensitive full-path match. Never bind a root name to an
        # unrelated nested deck that happens to share the same leaf name.
        lower_target = target.lower()
        matches = [deck for deck in owned if _deck_path(deck).lower() == lower_target]
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


def _accessible_note_types(
    user_id: int,
    *,
    eager_schema: bool = False,
) -> list[NoteType]:
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
    if eager_schema:
        query = query.options(
            selectinload(NoteType.field_defs),
            selectinload(NoteType.templates),
        )
    return query.order_by(NoteType.name.asc(), NoteType.id.asc()).all()


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


def _parse_note(
    user_id: int,
    raw_note: object,
    *,
    lock_deck: bool = False,
    allow_create_deck: bool = False,
    allow_mixed_model: bool = False,
    import_session_id: str | None = None,
    batch_context: ImportBatchContext | None = None,
    existing_note: Note | None = None,
) -> PreparedNote:
    if not isinstance(raw_note, dict):
        raise ConnectError("note must be an object")
    unknown = set(raw_note) - {"deckName", "modelName", "fields", "tags", "options", "audio", "picture", "video"}
    if unknown:
        raise ConnectError("note contains unsupported properties")
    for media_key in ("audio", "picture", "video"):
        if raw_note.get(media_key):
            raise ConnectError("media import is not supported in this version")

    deck_name = raw_note.get("deckName")
    normalized_deck_name = deck_name.strip() if isinstance(deck_name, str) else ""
    deck = batch_context.decks_by_path.get(normalized_deck_name) if batch_context else None
    if deck is None:
        deck = _resolve_deck(
            user_id,
            deck_name,
            lock=lock_deck,
            allow_create=allow_create_deck,
        )

    model_name = raw_note.get("modelName")
    normalized_model_name = model_name.strip() if isinstance(model_name, str) else ""
    note_type = batch_context.note_types_by_id.get(normalized_model_name) if batch_context else None
    if note_type is None:
        note_type = _resolve_note_type(user_id, model_name)
    if not allow_mixed_model and deck.note_type_id is not None and deck.note_type_id != note_type.id:
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
    fields = normalize_anki_field_values(fields, tuple(note_type.field_defs))
    if import_session_id is None and any(
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
    pending_audio: dict[str, ConnectPendingMedia] = {}
    pending_import_media: dict[str, Any] = {}
    try:
        if import_session_id is not None:
            pending_import_media, allowed_media_references = flama_connect_media_service.resolve_import_media(
                user_id=user_id,
                session_id=import_session_id,
                note_type=note_type,
                raw_fields=fields,
                lock=lock_deck,
                existing_note=existing_note,
            )
        else:
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
            allow_missing_media=import_session_id is not None,
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
        clone_map=(
            batch_context.clone_maps_by_deck_id.get(deck.id)
            if batch_context is not None
            else _clone_map_for_deck(user_id, deck.id)
        ),
        pending_audio=pending_audio,
        pending_import_media=pending_import_media,
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
    local_notes = Note.query.filter_by(
        user_id=user_id,
        deck_id=prepared.deck.id,
        note_type_id=prepared.note_type.id,
    ).all()
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
            changed_field_names: set[str] = set()
            field_vals = dict(existing_note.field_values or {})
            for k, v in prepared.fields.items():
                if v and field_vals.get(k) != v:
                    field_vals[k] = v
                    updated = True
                    changed_field_names.add(k)
            if updated:
                existing_note.field_values = field_vals
                if prepared.clone_map is None:
                    from app.services import deck_working_tree_service

                    deck_working_tree_service.mark_note_fields_changed(
                        note=existing_note,
                        field_names=changed_field_names,
                    )
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
        else:
            from app.services import deck_working_tree_service

            deck_working_tree_service.mark_note_fields_changed(
                note=note,
                field_names=(note.field_values or {}).keys(),
                operation="add",
            )

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


def _session_source_key(params: dict[str, Any]) -> str:
    raw = params.get("sourceKey") or params.get("source") or "anki"
    value = str(raw).strip()
    if not value or len(value) > 255 or any(ord(char) < 32 for char in value):
        raise ConnectError("sourceKey is invalid")
    return value


def _migrate_source_aliases(user_id: int, source_key: str, raw_aliases: object) -> None:
    """Move legacy endpoint-based refs into the profile-aware source namespace."""
    if raw_aliases is None:
        return
    if not isinstance(raw_aliases, list) or len(raw_aliases) > 5:
        raise ConnectError("sourceAliases must be an array with at most 5 entries")
    aliases: list[str] = []
    for raw in raw_aliases:
        alias = str(raw or "").strip()
        if not alias or len(alias) > 255 or any(ord(char) < 32 for char in alias):
            raise ConnectError("sourceAliases contains an invalid source key")
        if alias != source_key and alias not in aliases:
            aliases.append(alias)

    specs = (
        (ConnectNoteTypeRef, "external_model_id", "note_type_id"),
        (ConnectSourceDeckRef, "external_deck_id", "deck_id"),
        (ConnectSourceNoteRef, "external_note_id", "note_id"),
    )
    for alias in aliases:
        for model, external_field, target_field in specs:
            rows = model.query.filter_by(user_id=user_id, source_key=alias).all()
            for row in rows:
                external_id = getattr(row, external_field)
                existing = model.query.filter_by(
                    user_id=user_id,
                    source_key=source_key,
                    **{external_field: external_id},
                ).first()
                if existing is None:
                    row.source_key = source_key
                elif getattr(existing, target_field) == getattr(row, target_field):
                    db.session.delete(row)


def _normalize_note_type_plan(raw: object) -> NormalizedNoteTypePlan:
    if not isinstance(raw, dict):
        raise ConnectError("noteTypes entries must be objects")
    source_model_name = str(raw.get("sourceModelName") or "").strip()
    source_model_id = str(raw.get("sourceModelId") or source_model_name).strip()
    if not source_model_name or len(source_model_name) > 255:
        raise ConnectError("sourceModelName is invalid")
    if not source_model_id or len(source_model_id) > 128:
        raise ConnectError("sourceModelId is invalid")

    raw_fields = raw.get("fields")
    if not isinstance(raw_fields, list) or not 1 <= len(raw_fields) <= 100:
        raise ConnectError(f'NoteType "{source_model_name}" must declare between 1 and 100 fields')
    fields: list[dict[str, Any]] = []
    seen_fields: set[str] = set()
    allowed_field_types = {"text", "richtext", "markdown", "image", "audio", "diagram"}
    for position, item in enumerate(raw_fields):
        if isinstance(item, str):
            name = item.strip()
            field_type = "text"
        elif isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            field_type = str(item.get("fieldType") or item.get("field_type") or "text").strip().lower()
        else:
            raise ConnectError(f'NoteType "{source_model_name}" contains an invalid field')
        key = name.casefold()
        if not name or len(name) > 255 or key in seen_fields:
            raise ConnectError(f'NoteType "{source_model_name}" contains duplicate or invalid fields')
        if field_type not in allowed_field_types:
            raise ConnectError(f'NoteType "{source_model_name}" contains an unsupported field type')
        seen_fields.add(key)
        fields.append({"name": name, "field_type": field_type, "position": position})

    raw_templates = raw.get("templates") or []
    if not isinstance(raw_templates, list) or len(raw_templates) > 50:
        raise ConnectError(f'NoteType "{source_model_name}" templates are invalid')
    templates: list[dict[str, str]] = []
    for index, item in enumerate(raw_templates):
        if not isinstance(item, dict):
            raise ConnectError(f'NoteType "{source_model_name}" contains an invalid template')
        name = str(item.get("name") or f"Card {index + 1}").strip()
        front = str(item.get("frontHtml") or item.get("front") or "")
        back = str(item.get("backHtml") or item.get("back") or "")
        css = str(item.get("sharedCss") or item.get("css") or "")
        if not name or len(name) > 255 or len(front) > 1_000_000 or len(back) > 1_000_000 or len(css) > 1_000_000:
            raise ConnectError(f'NoteType "{source_model_name}" contains an invalid template')
        templates.append({"name": name, "front_html": front, "back_html": back, "shared_css": css})
    if not templates:
        first_name = fields[0]["name"]
        second_name = fields[1]["name"] if len(fields) > 1 else first_name
        templates.append(
            {
                "name": "Card 1",
                "front_html": f"{{{{{first_name}}}}}",
                "back_html": f"{{{{FrontSide}}}}<hr>{{{{{second_name}}}}}",
                "shared_css": "",
            }
        )

    raw_mapping = raw.get("fieldMapping") or {}
    if not isinstance(raw_mapping, dict):
        raise ConnectError(f'NoteType "{source_model_name}" fieldMapping must be an object')
    field_mapping = {
        str(source).strip(): str(target).strip()
        for source, target in raw_mapping.items()
        if str(source).strip() and str(target).strip() and str(target).strip() != "ignore"
    }
    target_id_raw = raw.get("targetNoteTypeId")
    target_note_type_id = str(target_id_raw).strip() if target_id_raw else None
    canonical = json.dumps(
        {
            "source_model_id": source_model_id,
            "fields": fields,
            "templates": templates,
            "field_mapping": field_mapping,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return NormalizedNoteTypePlan(
        source_model_id=source_model_id,
        source_model_name=source_model_name,
        target_note_type_id=target_note_type_id,
        fields=tuple(fields),
        templates=tuple(templates),
        field_mapping=field_mapping,
        schema_hash=hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
    )


def _existing_target_for_plan(
    *,
    user_id: int,
    source_key: str,
    plan: NormalizedNoteTypePlan,
) -> NoteType | None:
    if plan.target_note_type_id:
        try:
            return _resolve_note_type(user_id, plan.target_note_type_id)
        except ConnectError:
            return None
    ref = ConnectNoteTypeRef.query.filter_by(
        user_id=user_id,
        source_key=source_key,
        external_model_id=plan.source_model_id,
    ).first()
    if ref is not None:
        try:
            return _resolve_note_type(user_id, ref.note_type_id)
        except ConnectError:
            return None
    return None


def _validate_existing_target(plan: NormalizedNoteTypePlan, target: NoteType) -> list[str]:
    blockers: list[str] = []
    target_fields = {field.name: field for field in target.field_defs}
    if not plan.field_mapping:
        exact_names = {field["name"] for field in plan.fields}
        if exact_names.issubset(target_fields):
            plan.field_mapping.update({name: name for name in exact_names})
    unknown_sources = sorted(set(plan.field_mapping) - {field["name"] for field in plan.fields})
    unknown_targets = sorted(set(plan.field_mapping.values()) - set(target_fields))
    if unknown_sources:
        blockers.append(f"mapping contains unknown source fields: {', '.join(unknown_sources)}")
    if unknown_targets:
        blockers.append(f"mapping targets missing fields: {', '.join(unknown_targets)}")
    primary_fields = [field.name for field in target.field_defs if field.identity_role == "primary"]
    if len(primary_fields) != 1:
        blockers.append("target must declare exactly one primary identity field")
    elif primary_fields[0] not in set(plan.field_mapping.values()):
        blockers.append(f'primary field "{primary_fields[0]}" is not mapped')
    required_targets = {field.name for field in target.field_defs if field.required}
    missing_required = sorted(required_targets - set(plan.field_mapping.values()))
    if missing_required:
        blockers.append(f"required target fields are not mapped: {', '.join(missing_required)}")
    if len(target.templates) < len(plan.templates):
        blockers.append("target has fewer card templates than the Anki NoteType")
    return blockers


def _create_note_type_from_plan(user_id: int, plan: NormalizedNoteTypePlan) -> NoteType:
    name = plan.source_model_name
    existing_name = NoteType.query.filter_by(user_id=user_id, name=name).first()
    if existing_name is not None:
        raise ConnectError(
            f'NoteType "{name}" already exists but is not mapped. Select it explicitly or resolve the conflict.'
        )
    note_type = NoteType(user_id=user_id, name=name)
    db.session.add(note_type)
    db.session.flush()

    primary_index = next(
        (index for index, field in enumerate(plan.fields) if field["field_type"] == "text"),
        None,
    )
    if primary_index is None:
        raise ConnectError(f'NoteType "{name}" needs at least one text field for identity')
    for index, field in enumerate(plan.fields):
        db.session.add(
            FieldDef(
                note_type_id=note_type.id,
                name=field["name"],
                field_type=field["field_type"],
                position=index,
                required=index == primary_index,
                identity_role="primary" if index == primary_index else None,
            )
        )
    for index, template in enumerate(plan.templates):
        db.session.add(
            Template(
                note_type_id=note_type.id,
                name=template["name"],
                front_html=template["front_html"],
                back_html=template["back_html"],
                shared_css=template["shared_css"],
                position=index,
                is_default=index == 0,
            )
        )
    db.session.flush()
    return note_type


def _target_note_type_hash(note_type: NoteType) -> str:
    payload = {
        "fields": [
            {
                "name": field.name,
                "field_type": field.field_type,
                "position": field.position,
                "required": bool(field.required),
                "identity_role": field.identity_role,
            }
            for field in sorted(note_type.field_defs, key=lambda item: (item.position, item.id))
        ],
        "templates": [
            {
                "name": template.name,
                "front_html": template.front_html,
                "back_html": template.back_html,
                "shared_css": template.shared_css,
                "position": template.position,
            }
            for template in sorted(note_type.templates, key=lambda item: (item.position, item.id))
        ],
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def prepare_import_batch_context(
    *,
    user_id: int,
    session: ConnectImportSession,
    cards: list[dict[str, Any]],
) -> ImportBatchContext:
    """Load immutable package-level lookup state once instead of once per note."""

    bindings = dict(session.note_type_bindings or {})
    target_note_type_ids = {
        str(binding.get("targetNoteTypeId") or "")
        for binding in bindings.values()
        if isinstance(binding, dict) and binding.get("targetNoteTypeId")
    }
    note_types = _accessible_note_types(user_id, eager_schema=True)
    note_types_by_id = {
        note_type.id: note_type
        for note_type in note_types
        if note_type.id in target_note_type_ids
    }
    note_type_hashes_by_id = {
        note_type_id: _target_note_type_hash(note_type)
        for note_type_id, note_type in note_types_by_id.items()
    }

    target_paths = {
        str(note_payload.get("deckName") or "").strip()
        for card in cards
        if isinstance(card, dict)
        and isinstance((note_payload := card.get("note")), dict)
        and str(note_payload.get("deckName") or "").strip()
    }
    owned_decks = _owned_decks(user_id)
    decks_by_path = {
        path: deck
        for deck in owned_decks
        if (path := _deck_path(deck)) in target_paths
    }
    target_deck_ids = [deck.id for deck in decks_by_path.values()]
    if target_deck_ids:
        locked_by_id = {
            deck.id: deck
            for deck in Deck.query.filter(
                Deck.id.in_(target_deck_ids),
                Deck.owner_user_id == user_id,
                Deck.deleted_at.is_(None),
            )
            .with_for_update()
            .all()
        }
        decks_by_path = {
            path: locked_by_id.get(deck.id, deck)
            for path, deck in decks_by_path.items()
        }

    clone_maps_by_deck_id: dict[int, DeckCloneDeckMap] = {}
    if target_deck_ids:
        clone_maps = (
            DeckCloneDeckMap.query.join(
                DeckInstall,
                DeckInstall.id == DeckCloneDeckMap.deck_install_id,
            )
            .filter(
                DeckCloneDeckMap.local_deck_id.in_(target_deck_ids),
                DeckInstall.user_id == user_id,
                DeckInstall.clone_mode == "logical_overlay",
            )
            .all()
        )
        clone_maps_by_deck_id = {
            clone_map.local_deck_id: clone_map for clone_map in clone_maps
        }

    return ImportBatchContext(
        note_types_by_id=note_types_by_id,
        note_type_hashes_by_id=note_type_hashes_by_id,
        decks_by_path=decks_by_path,
        clone_maps_by_deck_id=clone_maps_by_deck_id,
    )


def _upsert_note_type_ref(
    *,
    user_id: int,
    source_key: str,
    plan: NormalizedNoteTypePlan,
    note_type: NoteType,
) -> None:
    ref = ConnectNoteTypeRef.query.filter_by(
        user_id=user_id,
        source_key=source_key,
        external_model_id=plan.source_model_id,
    ).first()
    if ref is None:
        ref = ConnectNoteTypeRef(
            user_id=user_id,
            source_key=source_key,
            external_model_id=plan.source_model_id,
            external_model_name=plan.source_model_name,
            note_type_id=note_type.id,
            schema_hash=plan.schema_hash,
        )
        db.session.add(ref)
    else:
        ref.external_model_name = plan.source_model_name
        ref.note_type_id = note_type.id
        ref.schema_hash = plan.schema_hash


def create_import_session(user_id: int, params: dict[str, Any]) -> dict[str, Any]:
    mode = str(params.get("mode") or "strict").strip()
    if mode not in IMPORT_SESSION_MODES:
        raise ConnectError("mode must be strict or auto_sync_missing")
    source_key = _session_source_key(params)
    _migrate_source_aliases(user_id, source_key, params.get("sourceAliases"))
    selected_decks_raw = params.get("selectedDecks") or []
    if not isinstance(selected_decks_raw, list) or not selected_decks_raw:
        raise ConnectError("selectedDecks must contain at least one target deck")
    selected_decks: list[str] = []
    for item in selected_decks_raw:
        path = str(item or "").strip()
        if not path or len(path) > 2048 or any(ord(char) < 32 for char in path):
            raise ConnectError("selectedDecks contains an invalid deck path")
        if path not in selected_decks:
            selected_decks.append(path)

    raw_plans = params.get("noteTypes")
    if not isinstance(raw_plans, list) or not raw_plans:
        raise ConnectError("noteTypes preflight inventory is required")
    plans = [_normalize_note_type_plan(raw) for raw in raw_plans]
    if len({plan.source_model_id for plan in plans}) != len(plans):
        raise ConnectError("noteTypes contains duplicate source model IDs")

    blockers: list[dict[str, str]] = []
    resolved: dict[str, NoteType] = {}
    missing: list[NormalizedNoteTypePlan] = []
    for plan in plans:
        target = _existing_target_for_plan(user_id=user_id, source_key=source_key, plan=plan)
        if target is None:
            if mode == "strict":
                blockers.append(
                    {
                        "sourceModelId": plan.source_model_id,
                        "sourceModelName": plan.source_model_name,
                        "code": "NOTE_TYPE_MISSING",
                        "message": "ChÆ°a cÃ³ Flama NoteType Ä‘Ã­ch.",
                    }
                )
            else:
                missing.append(plan)
            continue
        plan_blockers = _validate_existing_target(plan, target)
        for message in plan_blockers:
            blockers.append(
                {
                    "sourceModelId": plan.source_model_id,
                    "sourceModelName": plan.source_model_name,
                    "code": "NOTE_TYPE_INCOMPATIBLE",
                    "message": message,
                }
            )
        if not plan_blockers:
            resolved[plan.source_model_id] = target

    if not blockers:
        for plan in missing:
            target = _create_note_type_from_plan(user_id, plan)
            plan.field_mapping.update({field["name"]: field["name"] for field in plan.fields})
            resolved[plan.source_model_id] = target

    bindings: dict[str, dict[str, Any]] = {}
    if not blockers:
        for plan in plans:
            target = resolved[plan.source_model_id]
            _upsert_note_type_ref(
                user_id=user_id,
                source_key=source_key,
                plan=plan,
                note_type=target,
            )
            bindings[plan.source_model_id] = {
                "sourceModelName": plan.source_model_name,
                "targetNoteTypeId": target.id,
                "fieldMapping": dict(plan.field_mapping),
                "schemaHash": plan.schema_hash,
                "targetSchemaHash": _target_note_type_hash(target),
            }

        raw_decks = params.get("decks") or []
        if not isinstance(raw_decks, list) or len(raw_decks) > 10_000:
            raise ConnectError("decks manifest is invalid")
        normalized_decks: list[dict[str, str]] = []
        for item in raw_decks:
            if not isinstance(item, dict):
                raise ConnectError("decks manifest entries must be objects")
            source_deck_id = str(item.get("sourceDeckId") or "").strip()
            source_path = str(item.get("sourcePath") or "").strip()
            target_path = str(item.get("targetPath") or "").strip()
            if (
                not source_deck_id
                or len(source_deck_id) > 128
                or not source_path
                or len(source_path) > 2048
                or target_path not in selected_decks
            ):
                raise ConnectError("decks manifest contains an invalid mapping")
            normalized_decks.append(
                {
                    "source_deck_id": source_deck_id,
                    "source_path": source_path,
                    "target_path": target_path,
                }
            )

        target_decks: dict[str, Deck] = {}
        for item in sorted(normalized_decks, key=lambda value: value["target_path"].count("::")):
            source_deck_id = item["source_deck_id"]
            source_path = item["source_path"]
            target_path = item["target_path"]
            deck_ref = ConnectSourceDeckRef.query.filter_by(
                user_id=user_id,
                source_key=source_key,
                external_deck_id=source_deck_id,
            ).first()
            desired: Deck | None = None
            try:
                desired = _resolve_deck(user_id, target_path)
            except ConnectError:
                desired = None
            referenced = db.session.get(Deck, deck_ref.deck_id) if deck_ref is not None else None
            if (
                referenced is not None
                and referenced.owner_user_id == user_id
                and referenced.deleted_at is None
                and desired is None
            ):
                tokens = [token.strip() for token in target_path.split("::") if token.strip()]
                if not tokens:
                    raise ConnectError("decks manifest contains an invalid target path")
                parent = _resolve_deck(user_id, "::".join(tokens[:-1]), allow_create=True) if len(tokens) > 1 else None
                referenced.name = tokens[-1]
                referenced.parent_id = parent.id if parent is not None else None
                desired = referenced
            if desired is None:
                desired = _resolve_deck(user_id, target_path, allow_create=True)
            target_decks[target_path] = desired
            if deck_ref is None:
                db.session.add(
                    ConnectSourceDeckRef(
                        user_id=user_id,
                        source_key=source_key,
                        external_deck_id=source_deck_id,
                        source_path=source_path,
                        deck_id=desired.id,
                    )
                )
            else:
                deck_ref.source_path = source_path
                deck_ref.deck_id = desired.id
        for path in selected_decks:
            if path not in target_decks:
                target_decks[path] = _resolve_deck(user_id, path, allow_create=True)

    now = datetime.utcnow()
    session = ConnectImportSession(
        user_id=user_id,
        source=str(params.get("source") or "anki")[:64],
        source_key=source_key,
        mode=mode,
        status="blocked_note_types" if blockers else IMPORT_SESSION_READY,
        source_root_path=str(params.get("sourceRootPath") or "")[:2048] or None,
        target_root_path=str(params.get("targetRootPath") or "")[:2048] or None,
        selected_decks=selected_decks,
        note_type_bindings=bindings,
        blockers=blockers,
        plan_hash=str(params.get("planHash") or "")[:64] or None,
        total_notes=max(0, int(params.get("totalNotes") or 0)),
        total_media=max(0, int(params.get("totalMedia") or 0)),
        expires_at=now + timedelta(hours=IMPORT_SESSION_TTL_HOURS),
    )
    db.session.add(session)
    db.session.flush()
    return {
        "importSessionId": session.id,
        "status": session.status,
        "noteTypeBindings": bindings,
        "blockers": blockers,
        "selectedDecks": selected_decks,
        "startedAt": now.isoformat() + "Z",
    }


def _get_import_session(user_id: int, session_id: object, *, require_ready: bool) -> ConnectImportSession:
    if not isinstance(session_id, str) or not session_id.strip():
        raise ConnectError("importSessionId is required")
    session = ConnectImportSession.query.filter_by(id=session_id.strip(), user_id=user_id).first()
    if session is None:
        raise ConnectError("import session was not found")
    if session.expires_at <= datetime.utcnow():
        session.status = "expired"
        raise ConnectError("import session has expired")
    if require_ready and session.status not in {IMPORT_SESSION_READY, "importing"}:
        raise ConnectError("all NoteTypes must be ready before importing cards or media")
    return session


def _reconcile_note_cards(note: Note, note_type: NoteType) -> None:
    templates = sorted(note_type.templates, key=lambda item: (item.position, item.id))
    if not templates:
        raise ConnectError("model has no card template")
    expected_ids = {template.id for template in templates}
    existing_by_template = {card.template_id: card for card in note.cards}
    for card in list(note.cards):
        if card.template_id not in expected_ids:
            db.session.delete(card)
    for template in templates:
        if template.id not in existing_by_template:
            db.session.add(Card(note_id=note.id, template_id=template.id))


def _migrate_cards_progress(
    user_id: int,
    note: Note,
    note_type: NoteType,
    cards_progress_payload: list[dict[str, Any]],
) -> None:
    if not cards_progress_payload:
        return

    from datetime import datetime, timezone
    from app.services.scheduler_config_service import resolve_scheduler_runtime_settings
    from app.services.anki_scheduler import _day_index, _day_index_to_datetime
    from models.card import Card
    from models.card_progress import CardProgress
    from models.user import User

    user = db.session.get(User, user_id)
    timezone_name = getattr(user, "timezone", "UTC") or "UTC"
    runtime = resolve_scheduler_runtime_settings(user_id=user_id)
    boundary_hour = runtime.day_boundary_hour_local

    now = datetime.utcnow()
    today_day_index_flama = _day_index(now, boundary_hour, timezone_name=timezone_name)

    templates = sorted(note_type.templates, key=lambda item: (item.position, item.id))

    # Flush newly reconciled cards and query them directly
    db.session.flush()
    existing_cards = {card.template_id: card for card in Card.query.filter_by(note_id=note.id).all()}

    if not isinstance(cards_progress_payload, list) or len(cards_progress_payload) > 100:
        raise ConnectError("cardsProgress must be an array with at most 100 entries")
    progress_map: dict[int, dict[str, Any]] = {}
    for item in cards_progress_payload:
        if not isinstance(item, dict):
            raise ConnectError("cardsProgress entries must be objects")
        ord_value = item.get("ord")
        if isinstance(ord_value, bool) or not isinstance(ord_value, int) or not 0 <= ord_value <= 99:
            raise ConnectError("cardsProgress ord must be an integer between 0 and 99")
        if ord_value in progress_map:
            raise ConnectError("cardsProgress contains duplicate ord values")
        for field_name in ("type", "queue", "interval", "factor", "reps", "lapses"):
            value = item.get(field_name, 0)
            if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(float(value)):
                raise ConnectError(f"cardsProgress {field_name} must be a finite number")
        if int(item.get("type", 0)) not in {0, 1, 2, 3}:
            raise ConnectError("cardsProgress type is invalid")
        if int(item.get("queue", 0)) not in {-3, -2, -1, 0, 1, 2, 3, 4}:
            raise ConnectError("cardsProgress queue is invalid")
        if not 0 <= int(item.get("interval", 0)) <= 365000:
            raise ConnectError("cardsProgress interval is out of range")
        if not 0 <= int(item.get("factor", 0)) <= 10000:
            raise ConnectError("cardsProgress factor is out of range")
        if not 0 <= int(item.get("reps", 0)) <= 2_000_000_000:
            raise ConnectError("cardsProgress reps is out of range")
        if not 0 <= int(item.get("lapses", 0)) <= 2_000_000_000:
            raise ConnectError("cardsProgress lapses is out of range")
        progress_map[ord_value] = item

    for ord_idx, template in enumerate(templates):
        card = existing_cards.get(template.id)
        if not card:
            continue

        progress_data = progress_map.get(ord_idx)
        if not progress_data:
            continue

        progress = CardProgress.query.filter_by(
            user_id=user_id,
            card_id=card.id,
        ).with_for_update().first()
        existing_progress = progress is not None

        anki_last_reviewed_at = None
        last_rev_str = progress_data.get("lastReviewAt")
        if last_rev_str:
            if not isinstance(last_rev_str, str) or len(last_rev_str) > 64:
                raise ConnectError("cardsProgress lastReviewAt is invalid")
            try:
                clean_str = last_rev_str.replace("Z", "+00:00")
                anki_last_reviewed_at = datetime.fromisoformat(clean_str)
                if anki_last_reviewed_at.tzinfo is not None:
                    anki_last_reviewed_at = anki_last_reviewed_at.astimezone(timezone.utc).replace(tzinfo=None)
            except ValueError as exc:
                raise ConnectError("cardsProgress lastReviewAt is invalid") from exc

        # Conflict Handling: Newest progress wins
        if progress is not None:
            if progress.last_reviewed_at is not None:
                if anki_last_reviewed_at is not None and anki_last_reviewed_at >= progress.last_reviewed_at:
                    pass
                else:
                    continue
        else:
            progress = CardProgress(user_id=user_id, card_id=card.id)
            db.session.add(progress)

        anki_type = progress_data.get("type", 0)
        anki_queue = progress_data.get("queue", 0)

        # 0=new, 1=learning, 2=review, 3=relearning
        queue_map = {0: "new", 1: "learning", 2: "review", 3: "relearning"}
        progress.queue = queue_map.get(anki_type, "new")

        # queue: -1=suspended, -2=sched buried, -3=user buried
        progress.is_suspended = (anki_queue == -1)
        progress.is_buried = (anki_queue in {-2, -3})
        if progress.is_buried:
            progress.buried_until_day = today_day_index_flama + 1
        else:
            progress.buried_until_day = None

        progress.interval_days = int(progress_data.get("interval", 0))
        progress.interval_days_raw = float(progress_data.get("interval", 0))
        progress.ease_factor = float(progress_data.get("factor", 2500)) / 1000.0
        progress.reps = int(progress_data.get("reps", 0))
        progress.lapses = int(progress_data.get("lapses", 0))
        progress.last_reviewed_at = anki_last_reviewed_at

        relative_due = progress_data.get("relativeDue")
        due_at_str = progress_data.get("dueAt")
        if relative_due is not None:
            if isinstance(relative_due, bool) or not isinstance(relative_due, (int, float)):
                raise ConnectError("cardsProgress relativeDue must be a number or null")
            if not -365000 <= int(relative_due) <= 365000:
                raise ConnectError("cardsProgress relativeDue is out of range")
            progress.due_day = today_day_index_flama + int(relative_due)
            progress.due_at = _day_index_to_datetime(
                progress.due_day,
                boundary_hour,
                timezone_name=timezone_name,
            )
        elif due_at_str:
            if not isinstance(due_at_str, str) or len(due_at_str) > 64:
                raise ConnectError("cardsProgress dueAt is invalid")
            try:
                clean_str = due_at_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_str)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                progress.due_at = dt
            except (TypeError, ValueError) as exc:
                raise ConnectError("cardsProgress dueAt is invalid") from exc
            progress.due_day = None
        elif anki_type == 2:
            progress.due_day = today_day_index_flama
            progress.due_at = now
        elif anki_type in {1, 3}:
            progress.due_at = now
            progress.due_day = None
        else:
            progress.due_day = None
            progress.due_at = now

        progress.step_index = 0
        progress.review_kind = "review"
        progress.scheduler_mode = runtime.scheduler_mode
        if existing_progress:
            progress.revision = int(progress.revision or 0) + 1


def _upsert_import_card(
    *,
    user_id: int,
    session: ConnectImportSession,
    card_data: dict[str, Any],
    batch_context: ImportBatchContext | None = None,
) -> tuple[Note, bool, bool, Any, Any]:
    external_note_id = str(card_data.get("ankiNoteId") or "").strip()
    source_model_id = str(card_data.get("sourceModelId") or "").strip()
    source_deck_path = str(card_data.get("sourceDeckPath") or "").strip()
    source_deck_id = str(card_data.get("sourceDeckId") or source_deck_path).strip()
    content_hash = str(card_data.get("contentHash") or "").strip()
    if not external_note_id or len(external_note_id) > 128:
        raise ConnectError("ankiNoteId is invalid")
    if not source_model_id or source_model_id not in dict(session.note_type_bindings or {}):
        raise ConnectError("card references a NoteType that did not pass preflight")
    if not source_deck_path or len(source_deck_path) > 2048:
        raise ConnectError("sourceDeckPath is required")
    if not re.fullmatch(r"[0-9a-fA-F]{64}", content_hash):
        raise ConnectError("contentHash must be a SHA-256 hex string")
    note_payload = card_data.get("note")
    if not isinstance(note_payload, dict):
        raise ConnectError("card note payload is required")
    target_deck_path = str(note_payload.get("deckName") or "").strip()
    if target_deck_path not in set(session.selected_decks or []):
        raise ConnectError("card references a deck path that did not pass preflight")
    binding = dict(session.note_type_bindings or {}).get(source_model_id) or {}
    target_note_type_id = str(binding.get("targetNoteTypeId") or "")
    if str(note_payload.get("modelName") or "") != target_note_type_id:
        raise ConnectError("card target NoteType does not match the preflight binding")
    target_note_type = (
        batch_context.note_types_by_id.get(target_note_type_id)
        if batch_context is not None
        else None
    )
    if target_note_type is None:
        target_note_type = _resolve_note_type(user_id, target_note_type_id)
    target_schema_hash = (
        batch_context.note_type_hashes_by_id.get(target_note_type_id)
        if batch_context is not None
        else None
    ) or _target_note_type_hash(target_note_type)
    if target_schema_hash != str(binding.get("targetSchemaHash") or ""):
        session.status = "blocked_note_types"
        raise ConnectError("target NoteType changed after preflight; run preflight again")

    source_ref = ConnectSourceNoteRef.query.filter_by(
        user_id=user_id,
        source_key=session.source_key,
        external_note_id=external_note_id,
    ).with_for_update().first()
    note = source_ref.note if source_ref is not None else None
    prepared = _parse_note(
        user_id,
        note_payload,
        lock_deck=True,
        allow_create_deck=True,
        allow_mixed_model=True,
        import_session_id=session.id,
        batch_context=batch_context,
        existing_note=note,
    )
    already_counted = bool(
        source_ref is not None
        and source_ref.last_session_id == session.id
        and source_ref.content_hash == content_hash.lower()
    )
    created = False
    changed_field_names: set[str] = set()
    if note is None:
        note = Note(
            note_type_id=prepared.note_type.id,
            user_id=user_id,
            deck_id=prepared.deck.id,
            field_values=prepared.fields,
            tags=prepared.tags,
        )
        db.session.add(note)
        db.session.flush()
        created = True
    else:
        previous_values = dict(note.field_values or {})
        note.note_type_id = prepared.note_type.id
        note.deck_id = prepared.deck.id
        note.field_values = prepared.fields
        note.tags = prepared.tags
        changed_field_names = {
            key
            for key in set(previous_values) | set(prepared.fields)
            if previous_values.get(key) != prepared.fields.get(key)
        }

    if prepared.clone_map is not None:
        install = prepared.clone_map.deck_install
        added_note = DeckCloneAddedNote.query.filter_by(
            deck_install_id=install.id,
            note_id=note.id,
        ).first()
        if added_note is None:
            db.session.add(
                DeckCloneAddedNote(deck_install_id=install.id, note_id=note.id)
            )
        install.last_sync_status = "needs_sync"
        install.last_activity_at = datetime.utcnow()
    else:
        from app.services import deck_working_tree_service

        deck_working_tree_service.mark_note_fields_changed(
            note=note,
            field_names=(note.field_values or {}).keys() if created else changed_field_names,
            operation="add" if created else "set",
        )

    has_other_note_type = Note.query.filter(
        Note.user_id == user_id,
        Note.deck_id == prepared.deck.id,
        Note.note_type_id != prepared.note_type.id,
    ).first() is not None
    if has_other_note_type or (
        prepared.deck.note_type_id is not None
        and prepared.deck.note_type_id != prepared.note_type.id
    ):
        # Anki permits multiple NoteTypes in one deck. Keep the type on each
        # Note and clear the deck-level default instead of flattening/splitting.
        prepared.deck.note_type_id = None
    elif prepared.deck.note_type_id is None:
        prepared.deck.note_type_id = prepared.note_type.id
    deck_ref = ConnectSourceDeckRef.query.filter_by(
        user_id=user_id,
        source_key=session.source_key,
        external_deck_id=source_deck_id,
    ).first()
    if deck_ref is None:
        db.session.add(
            ConnectSourceDeckRef(
                user_id=user_id,
                source_key=session.source_key,
                external_deck_id=source_deck_id,
                source_path=source_deck_path,
                deck_id=prepared.deck.id,
            )
        )
    else:
        deck_ref.source_path = source_deck_path
        deck_ref.deck_id = prepared.deck.id
    _reconcile_note_cards(note, prepared.note_type)
    cards_progress_payload = card_data.get("cardsProgress")
    if cards_progress_payload:
        _migrate_cards_progress(user_id, note, prepared.note_type, cards_progress_payload)
    materialized = flama_connect_media_service.materialize_import_media(
        user_id=user_id,
        note=note,
        attachments=prepared.pending_import_media,
    )
    connect_ref = _ensure_note_ref(note, user_id)

    if source_ref is None:
        source_ref = ConnectSourceNoteRef(
            user_id=user_id,
            source_key=session.source_key,
            external_note_id=external_note_id,
            source_model_id=source_model_id,
            source_deck_path=source_deck_path,
            note_id=note.id,
            content_hash=content_hash.lower(),
            last_session_id=session.id,
        )
        db.session.add(source_ref)
    else:
        source_ref.source_model_id = source_model_id
        source_ref.source_deck_path = source_deck_path
        source_ref.note_id = note.id
        source_ref.content_hash = content_hash.lower()
        source_ref.last_session_id = session.id

    db.session.add(
        AuditLog(
            user_id=user_id,
            action="connect.note.import",
            payload={
                "session_id": session.id,
                "note_id": note.id,
                "external_note_id": external_note_id,
                "deck_id": prepared.deck.id,
                "note_type_id": prepared.note_type.id,
                "created": created,
            },
        )
    )
    return note, created, already_counted, connect_ref, materialized


def import_cards(
    user_id: int,
    params: dict[str, Any],
    *,
    commit: bool = True,
    batch_context: ImportBatchContext | None = None,
) -> dict[str, Any]:
    session = _get_import_session(user_id, params.get("importSessionId"), require_ready=True)
    cards = params.get("cards")
    if not isinstance(cards, list) or len(cards) > MAX_NOTES_PER_REQUEST:
        raise ConnectError(f"cards must be an array with at most {MAX_NOTES_PER_REQUEST} entries")
    if batch_context is None:
        batch_context = prepare_import_batch_context(
            user_id=user_id,
            session=session,
            cards=[card for card in cards if isinstance(card, dict)],
        )
    session.status = "importing"
    session.attempted_notes = min(
        int(session.total_notes or 0),
        int(session.attempted_notes or 0) + len(cards),
    )
    results: list[dict[str, Any]] = []
    materialized_results: list[Any] = []
    for card_data in cards:
        if not isinstance(card_data, dict):
            results.append({"ankiNoteId": None, "imported": False, "error": "card must be an object"})
            continue
        anki_note_id = card_data.get("ankiNoteId")
        materialized = None
        try:
            with db.session.begin_nested():
                note, created, already_counted, connect_ref, materialized = _upsert_import_card(
                    user_id=user_id,
                    session=session,
                    card_data=card_data,
                    batch_context=batch_context,
                )
                db.session.flush()
            materialized_results.append(materialized)
            results.append(
                {
                    "ankiNoteId": anki_note_id,
                    "imported": True,
                    "created": created,
                    "noteId": note.id,
                    "connectNoteId": int(connect_ref.id),
                }
            )
            if not already_counted:
                session.processed_notes += 1
            session.error_summary = [
                item
                for item in list(session.error_summary or [])
                if not isinstance(item, dict) or item.get("ankiNoteId") != anki_note_id
            ]
        except Exception as exc:
            flama_connect_media_service.compensate_materialized(materialized)
            results.append({"ankiNoteId": anki_note_id, "imported": False, "error": str(exc)})
            errors = list(session.error_summary or [])
            if len(errors) < 100:
                errors.append({"ankiNoteId": anki_note_id, "error": str(exc)})
            session.error_summary = errors
    # Completion is an explicit transport boundary. Progress and review
    # packages are intentionally uploaded after note packages.
    if commit:
        try:
            db.session.commit()
        except Exception:
            db.session.rollback()
            for materialized in materialized_results:
                flama_connect_media_service.compensate_materialized(materialized)
            raise
    return {"importSessionId": session.id, "status": session.status, "results": results}


def get_import_status(user_id: int, session_id: object) -> dict[str, Any]:
    session = _get_import_session(user_id, session_id, require_ready=False)
    return {
        "importSessionId": session.id,
        "status": session.status,
        "mode": session.mode,
        "blockers": list(session.blockers or []),
        "noteTypeBindings": dict(session.note_type_bindings or {}),
        "totalNotes": session.total_notes,
        "processedNotes": session.processed_notes,
        "attemptedNotes": session.attempted_notes,
        "totalMedia": session.total_media,
        "processedMedia": session.processed_media,
        "errors": list(session.error_summary or []),
        "expiresAt": session.expires_at.isoformat() + "Z",
    }


def get_import_note_statuses(
    user_id: int,
    session_id: object,
    notes: object,
) -> dict[str, Any]:
    session = _get_import_session(user_id, session_id, require_ready=True)
    if not isinstance(notes, list) or len(notes) > 1000:
        raise ConnectError("notes must be an array with at most 1000 entries")

    requested: dict[str, str] = {}
    requested_cards: dict[str, list[dict[str, Any]]] = {}
    original_ids: dict[str, object] = {}
    for item in notes:
        if not isinstance(item, dict):
            raise ConnectError("note status entries must be objects")
        external_id = str(item.get("ankiNoteId") or "").strip()
        content_hash = str(item.get("contentHash") or "").strip().lower()
        if not external_id or len(external_id) > 128:
            raise ConnectError("note status ankiNoteId is invalid")
        if not re.fullmatch(r"[0-9a-f]{64}", content_hash):
            raise ConnectError("note status contentHash must be a SHA-256 hex string")
        if external_id in requested:
            raise ConnectError("note status contains duplicate ankiNoteId values")
        requested[external_id] = content_hash
        original_ids[external_id] = item.get("ankiNoteId")
        raw_cards = item.get("cards") or []
        if not isinstance(raw_cards, list) or len(raw_cards) > 100:
            raise ConnectError("note status cards must be an array with at most 100 entries")
        normalized_cards: list[dict[str, Any]] = []
        seen_card_ids: set[str] = set()
        for raw_card in raw_cards:
            if not isinstance(raw_card, dict):
                raise ConnectError("note status card entries must be objects")
            source_card_id = str(raw_card.get("sourceCardId") or "").strip()
            snapshot_hash = str(raw_card.get("snapshotHash") or "").strip().lower()
            if not source_card_id or len(source_card_id) > 128 or source_card_id in seen_card_ids:
                raise ConnectError("note status sourceCardId is invalid or duplicated")
            if not re.fullmatch(r"[0-9a-f]{64}", snapshot_hash):
                raise ConnectError("note status snapshotHash must be a SHA-256 hex string")
            seen_card_ids.add(source_card_id)
            normalized_cards.append(
                {"sourceCardId": source_card_id, "snapshotHash": snapshot_hash}
            )
        requested_cards[external_id] = normalized_cards

    refs = ConnectSourceNoteRef.query.filter(
        ConnectSourceNoteRef.user_id == user_id,
        ConnectSourceNoteRef.source_key == session.source_key,
        ConnectSourceNoteRef.external_note_id.in_(list(requested)),
    ).all() if requested else []
    refs_by_external_id = {row.external_note_id: row for row in refs}
    requested_card_ids = [
        card["sourceCardId"]
        for cards in requested_cards.values()
        for card in cards
    ]
    card_refs = ConnectSourceCardRef.query.filter(
        ConnectSourceCardRef.user_id == user_id,
        ConnectSourceCardRef.source_key == session.source_key,
        ConnectSourceCardRef.external_card_id.in_(requested_card_ids),
    ).all() if requested_card_ids else []
    card_refs_by_external_id = {row.external_card_id: row for row in card_refs}
    orphan_review_card_ids = {
        row[0]
        for row in db.session.query(ConnectReviewEventRef.external_card_id)
        .filter(
            ConnectReviewEventRef.user_id == user_id,
            ConnectReviewEventRef.source_key == session.source_key,
            ConnectReviewEventRef.external_card_id.in_(requested_card_ids),
            ConnectReviewEventRef.status == "imported",
            ConnectReviewEventRef.review_event_id.is_(None),
        )
        .distinct()
        .all()
    } if requested_card_ids else set()
    note_ids = [row.note_id for row in refs if row.note_id]
    media_by_note: dict[str, set[str]] = {}
    if note_ids:
        for asset in MediaAsset.query.filter(MediaAsset.note_id.in_(note_ids)).all():
            if asset.sha256:
                media_by_note.setdefault(asset.note_id, set()).add(asset.sha256.lower())

    results: list[dict[str, Any]] = []
    for external_id, content_hash in requested.items():
        ref = refs_by_external_id.get(external_id)
        if ref is None or ref.note is None:
            state = "new"
            media_hashes: list[str] = []
        else:
            state = "unchanged" if ref.content_hash == content_hash else "changed"
            media_hashes = sorted(media_by_note.get(ref.note_id, set()))
        cards_result: list[dict[str, Any]] = []
        for requested_card in requested_cards.get(external_id, []):
            card_ref = card_refs_by_external_id.get(requested_card["sourceCardId"])
            if card_ref is not None and card_ref.external_note_id != external_id:
                card_ref = None
            if card_ref is None:
                progress_state = "new"
                review_cursor = None
            else:
                progress = CardProgress.query.filter_by(
                    user_id=user_id,
                    card_id=card_ref.card_id,
                ).first()
                local_changed = (
                    progress is not None
                    and card_ref.applied_local_revision is not None
                    and int(progress.revision or 0) != int(card_ref.applied_local_revision)
                )
                if local_changed:
                    progress_state = "local_changed"
                elif card_ref.snapshot_hash == requested_card["snapshotHash"]:
                    progress_state = "unchanged"
                else:
                    progress_state = "changed"
                # A cursor is only valid while every imported provenance row
                # still has its ReviewEvent analytics projection. Returning a
                # null cursor requests an idempotent replay and repairs gaps.
                review_cursor = (
                    None
                    if requested_card["sourceCardId"] in orphan_review_card_ids
                    else card_ref.review_cursor
                )
            cards_result.append(
                {
                    "sourceCardId": requested_card["sourceCardId"],
                    "progressState": progress_state,
                    "reviewCursor": str(review_cursor) if review_cursor is not None else None,
                }
            )
        results.append(
            {
                "ankiNoteId": original_ids[external_id],
                "state": state,
                "mediaHashes": media_hashes,
                "cards": cards_result,
            }
        )
    return {"importSessionId": session.id, "notes": results}


def complete_import_session(
    user_id: int,
    session_id: object,
    *,
    expected_notes: object | None = None,
) -> dict[str, Any]:
    session = _get_import_session(user_id, session_id, require_ready=False)
    if session.status in {"blocked_note_types", "failed", "cancelled", "expired"}:
        raise ConnectError("import session cannot be completed from its current state")
    if session.status == "completed":
        from app.services import flama_connect_package_service

        flama_connect_package_service.cleanup_session_staging(session)
        return get_import_status(user_id, session.id)
    if session.status == "partial_failed":
        return get_import_status(user_id, session.id)
    if expected_notes is None:
        expected_notes = session.total_notes
    if isinstance(expected_notes, bool) or not isinstance(expected_notes, int):
        raise ConnectError("expectedNotes must be a non-negative integer")
    if expected_notes < 0 or expected_notes > session.total_notes:
        raise ConnectError("expectedNotes is outside the preflight note count")
    if session.attempted_notes < expected_notes:
        raise ConnectError(
            f"import is incomplete: attempted {session.attempted_notes} of {expected_notes} expected notes"
        )
    session.total_notes = expected_notes
    session.status = "partial_failed" if session.error_summary else "completed"
    session.completed_at = datetime.utcnow()
    if session.status == "completed":
        from app.services import flama_connect_package_service

        flama_connect_package_service.cleanup_session_staging(session)
    return get_import_status(user_id, session.id)


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

