"""Import session preparation, NoteType schema planning, and session initialization."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import math
import re
import time
from typing import Any, Callable, Dict, Iterable, List, Optional, Set, Tuple
import unicodedata

from flask import current_app
from sqlalchemy import and_, asc, desc, func, or_
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import joinedload, selectinload

from app.repositories import (
    flashcards_share_repository,
    study_repository,
    template_library_repository,
    vocabulary_repository,
)
from app.repositories.study_authority_repository import lock_study_authority_route
from app.services import (
    anki_scheduler,
    deck_working_tree_service,
    flashcard_content_service,
    flashcards_share,
    flashcards_share_service,
    flama_connect_media_service,
    study_service,
)
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.validators.flashcard_input import RequestValidationError, validate_note_create_request

from models import db
from models.audit_log import AuditLog
from models.card import Card
from models.card_progress import CardProgress
from models.connect_import_media import ConnectImportMedia
from models.connect_import_package import ConnectImportPackage
from models.connect_import_session import ConnectImportSession
from models.connect_note_ref import ConnectNoteRef
from models.connect_note_type_ref import ConnectNoteTypeRef
from models.connect_pending_media import ConnectPendingMedia
from models.connect_review_event_ref import ConnectReviewEventRef
from models.connect_source_card_ref import ConnectSourceCardRef
from models.connect_source_deck_ref import ConnectSourceDeckRef
from models.connect_source_note_ref import ConnectSourceNoteRef
from models.deck import Deck
from models.deck_clone_added_field_def import DeckCloneAddedFieldDef
from models.deck_clone_added_note import DeckCloneAddedNote
from models.deck_clone_deck_map import DeckCloneDeckMap
from models.deck_clone_field_def_override import DeckCloneFieldDefOverride
from models.deck_clone_field_order_override import DeckCloneFieldOrderOverride
from models.deck_clone_note_field_override import DeckCloneNoteFieldOverride
from models.deck_install import DeckInstall
from models.deck_marketplace_item import DeckMarketplaceItem
from models.field_def import FieldDef
from models.media_asset import MediaAsset
from models.note import Note
from models.note_type import NoteType
from models.note_type_install import NoteTypeInstall
from models.review_event import ReviewEvent
from models.template import Template
from models.user import User

logger = logging.getLogger(__name__)
UTC = timezone.utc

from app.services.connect.registry import (
    FLAMA_CONNECT_PROTOCOL_VERSION, MAX_NOTES_PER_REQUEST, MAX_MULTI_ACTIONS, SUPPORTED_ACTIONS,
)
IMPORT_SESSION_MODES = {"strict", "auto_sync_missing"}
IMPORT_SESSION_READY = "note_types_ready"
IMPORT_SESSION_TTL_HOURS = 24
_QUERY_CLAUSE_RE = re.compile(r'"((?:\\.|[^"\\])*)"')


from app.services.connect.base import (
    ConnectError,
    ImportBatchContext,
    NormalizedNoteTypePlan,
    _deck_path,
    _session_source_key,
)
from app.services.connect.resolvers import (
    _accessible_note_types,
    _owned_decks,
    _resolve_deck,
    _resolve_note_type,
)

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
    if len(_anki_card_slots(target)) < len(plan.templates):
        blockers.append("target has fewer card templates than the Anki NoteType")
    return blockers


def _anki_card_slots(note_type: NoteType) -> list[str]:
    """Card identities matched by Anki card ordinal, in ordinal order.

    Mirrored Anki templates are this NoteType's own definitions (Template IDs,
    retired ones included so later ordinals never shift). A received NoteType
    has none and uses its active occurrences instead (application IDs).
    """
    templates = sorted(note_type.templates, key=lambda item: (item.position, item.id))
    if templates:
        return [template.id for template in templates]
    return [row.id for row in template_library_repository.applications(db.session, note_type.id)]



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
    """Load package lookups after the learner fence, before any Deck row lock."""

    # The context takes Deck FOR UPDATE locks below. Every card-import path
    # must first hold the same learner prefix lock used by enrollment.
    lock_study_authority_route(
        db.session,
        learner_user_id=int(user_id),
        allow_note_authority=True,
    )

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
    # Session creation may auto-create NoteTypes/Decks or rebind source Decks.
    # Hold the learner prefix before those mutations so enrollment cannot
    # overtake this package setup transaction.
    lock_study_authority_route(
        db.session,
        learner_user_id=int(user_id),
        allow_note_authority=True,
    )
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
                # Renaming/re-parenting a Deck is presentation context only;
                # NOTE state is keyed by learner/Note, so both modes relocate.
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



