"""Card and review progress import, reconciliation, and session completion."""

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
from app.repositories.study_authority_repository import (
    StudyAuthorityFenceError,
    lock_study_authority_route,
)
from app.services import (
    anki_scheduler,
    deck_working_tree_service,
    flashcard_content_service,
    flashcards_share,
    flashcards_share_service,
    flama_connect_media_service,
    stats_overview,
    study_service,
)
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.services.scheduler_config_service import resolve_deck_options
from app.services.study_authority_read_service import (
    StudyAuthorityReadError,
    load_study_authority_card_reads,
)
from app.services.study_progress_shadow_codec import StudyProgressCodecError
from app.validators.flashcard_input import RequestValidationError, validate_note_create_request

from models import db
from models.audit_log import AuditLog
from models.card import Card
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
from models.study_progress_subject import StudyProgressSubject
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


from app.services.connect.actions import (
    _ensure_note_ref,
    _parse_note,
)
from app.services.connect.base import (
    ConnectError,
    ImportBatchContext,
    _deck_path,
    _normalized_identity,
)
from app.services.connect.import_session import (
    _anki_card_slots,
    _get_import_session,
    _target_note_type_hash,
    _upsert_note_type_ref,
    prepare_import_batch_context,
)
from app.services.connect.resolvers import (
    _identity_field,
    _resolve_deck,
    _resolve_note_type,
)

def _note_card_plan(note: Note, note_type: NoteType):
    """The Note's Cards are its NoteType's ACTIVE occurrences (ADR P11): require one."""
    if not template_library_repository.card_slots(db.session, note_type.id):
        raise ConnectError("model has no card template")


def _reconcile_note_cards(
    note: Note,
    note_type: NoteType,
    *,
    is_new_note: bool = False,
    preserve_released_history: bool | None = None,
    plan=None,
) -> None:
    """Cards are derived from the NoteType's occurrences: nothing to reconcile.

    Kept for callers of the Connect facade; it only checks that the NoteType
    presents at least one Card.
    """
    _note_card_plan(note, note_type)
    db.session.expire(note, ["cards"])


def _reconcile_note_authority_cards(
    *,
    user_id: int,
    note: Note,
    note_type: NoteType,
    is_new_note: bool,
    preserve_released_history: bool | None,
    operation_key: str,
) -> None:
    """Under NOTE as under LEGACY, a Note's Cards follow its NoteType (ADR P11)."""
    _reconcile_note_cards(note, note_type, is_new_note=is_new_note,
                          preserve_released_history=preserve_released_history)





def _upsert_import_card(
    *,
    user_id: int,
    session: ConnectImportSession,
    card_data: dict[str, Any],
    batch_context: ImportBatchContext | None = None,
) -> tuple[Note, bool, bool, Any, Any, list[dict[str, Any]]]:
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
    previous_deck_id: int | None = None
    preserve_released_history = False
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
        from app.services import deck_working_tree_service

        previous_deck_id = note.deck_id
        previous_tags = list(note.tags or [])
        preserve_released_history = (
            deck_working_tree_service.note_has_shared_release_dependents(note)
        )
        if previous_deck_id != prepared.deck.id and preserve_released_history:
            raise ConnectError(
                "cannot move a released shared note between decks until "
                "release-aware membership moves are supported"
            )
        if (
            str(note.note_type_id) != str(prepared.note_type.id)
            and preserve_released_history
        ):
            raise ConnectError(
                "cannot change the note type of a released shared note; "
                "schema-aware deck releases are required"
            )
        if previous_tags != list(prepared.tags or []) and preserve_released_history:
            raise ConnectError(
                "cannot change tags on a released shared note until note "
                "metadata is versioned in deck releases"
            )
        previous_values = dict(note.field_values or {})
        if str(note.note_type_id) != str(prepared.note_type.id):
            # The Note now presents the new NoteType's occurrences (ADR P11).
            from app.services import study_content_delete_service as content_topology
            content_topology.stop_note_presentations(
                db.session, note_id=note.id, note_type_id=note.note_type_id)
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
    db.session.flush()

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
    authority_route = lock_study_authority_route(
        db.session,
        learner_user_id=user_id,
        allow_note_authority=True,
    )
    # The Note's Cards follow its NoteType's occurrences (ADR P11).
    _reconcile_note_cards(
        note,
        prepared.note_type,
        is_new_note=created,
        preserve_released_history=preserve_released_history,
    )
    cards_progress_payload = card_data.get("cardsProgress")
    progress_results: list[dict[str, Any]] = []
    if cards_progress_payload:
        # Per-Card legacy progress cannot express one learner/Note state.
        # Content is imported; progress must arrive as a Note snapshot.
        if not isinstance(cards_progress_payload, list) or len(cards_progress_payload) > 100:
            raise ConnectError("cardsProgress must be an array with at most 100 entries")
        progress_results = [
            {
                "ord": item.get("ord") if isinstance(item, dict) else None,
                "state": "unsupported",
                "code": "NOTE_SNAPSHOT_REQUIRED",
            }
            for item in cards_progress_payload
        ]
    materialized = flama_connect_media_service.materialize_import_media(
        user_id=user_id,
        note=note,
        attachments=prepared.pending_import_media,
    )
    if prepared.clone_map is None:
        from app.services import deck_working_tree_service

        if created:
            dirty_mutations = [
                {
                    "note": note,
                    "field_names": (note.field_values or {}).keys(),
                    "operation": "add",
                }
            ]
        elif previous_deck_id != note.deck_id:
            all_field_names = set(previous_values) | set(note.field_values or {})
            dirty_mutations = [
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "remove",
                    "deck_id": previous_deck_id,
                },
                {
                    "note": note,
                    "field_names": all_field_names,
                    "operation": "add",
                    "deck_id": note.deck_id,
                },
            ]
        else:
            final_changed_names = {
                key
                for key in set(previous_values) | set(note.field_values or {})
                if previous_values.get(key) != (note.field_values or {}).get(key)
            }
            dirty_mutations = [
                {
                    "note": note,
                    "field_names": final_changed_names,
                    "operation": "set",
                }
            ]
        deck_working_tree_service.mark_note_field_batches_changed(
            mutations=dirty_mutations,
        )
    connect_ref = _ensure_note_ref(note, user_id)

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
    return (
        note,
        created,
        already_counted,
        connect_ref,
        materialized,
        progress_results,
    )



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
    # Also cover direct callers that pass an already prepared batch context.
    # This shared prefix lock survives all per-card savepoints and preserves
    # the learner -> Deck -> content ordering for the entire import call.
    lock_study_authority_route(
        db.session,
        learner_user_id=user_id,
        allow_note_authority=True,
    )
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
                # Card/content import can change NoteType and Card topology. It
                # takes the learner fence before source, content or progress
                # rows so an enrollment switch cannot race a late failure; NOTE
                # topology goes through the multi-learner coordinator.
                lock_study_authority_route(
                    db.session,
                    learner_user_id=user_id,
                    allow_note_authority=True,
                )
                (
                    note,
                    created,
                    already_counted,
                    connect_ref,
                    materialized,
                    progress_results,
                ) = _upsert_import_card(
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
                    "progressResults": progress_results,
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
            results.append(
                {
                    "ankiNoteId": anki_note_id,
                    "imported": False,
                    "code": getattr(exc, "code", "CARD_IMPORT_FAILED"),
                    "error": str(exc),
                }
            )
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



class ConnectAuthorityReadError(ConnectError):
    """A NOTE import-status read cannot trust its compatibility cursor."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.status = 409


def _verify_note_authority_import_status(
    *,
    user_id: int,
    requested_cards: dict[str, list[dict[str, Any]]],
    refs_by_external_id: dict[str, ConnectSourceNoteRef],
    card_refs_by_external_id: dict[str, ConnectSourceCardRef],
    consolidated: bool = False,
) -> None:
    """Validate every sibling before exposing a NOTE source-progress cursor."""

    note_ids: set[str] = set()
    matched_refs: list[tuple[ConnectSourceCardRef, str]] = []
    for external_note_id, cards in requested_cards.items():
        for requested_card in cards:
            card_ref = card_refs_by_external_id.get(requested_card["sourceCardId"])
            if card_ref is None or card_ref.external_note_id != external_note_id:
                continue
            note_ref = refs_by_external_id.get(external_note_id)
            if note_ref is None or not note_ref.note_id:
                raise ConnectAuthorityReadError(
                    "INCOMPLETE_AUTHORITY_COMPATIBILITY",
                    "NOTE import card has no source Note mapping.",
                )
            note_ids.add(str(note_ref.note_id))
            matched_refs.append((card_ref, str(note_ref.note_id)))
    if not matched_refs:
        return

    notes = (
        Note.query.options(selectinload(Note.cards))
        .filter(Note.user_id == user_id, Note.id.in_(sorted(note_ids)))
        .all()
    )
    notes_by_id = {str(note.id): note for note in notes}
    if set(notes_by_id) != note_ids or any(not note.cards for note in notes):
        raise ConnectAuthorityReadError(
            "INCOMPLETE_AUTHORITY_COMPATIBILITY",
            "NOTE import source Note or its Card siblings are missing.",
        )
    card_ids_by_note_id = {
        note_id: {str(card.id) for card in note.cards}
        for note_id, note in notes_by_id.items()
    }
    for card_ref, note_id in matched_refs:
        if str(card_ref.card_id) not in card_ids_by_note_id[note_id]:
            raise ConnectAuthorityReadError(
                "INCOMPLETE_AUTHORITY_COMPATIBILITY",
                "NOTE import source Card mapping differs from its Note.",
            )

    subject_by_note_key = {
        bytes(subject.logical_note_key): subject
        for subject in StudyProgressSubject.query.filter(
            StudyProgressSubject.learner_user_id == user_id,
            StudyProgressSubject.logical_note_key.in_(
                sorted(note_id.encode("utf-8") for note_id in note_ids)
            ),
        ).all()
    }
    for note in notes:
        subject = subject_by_note_key.get(str(note.id).encode("utf-8"))
        if (
            subject is None
            or str(subject.live_note_id or "") != str(note.id)
            # CONSOLIDATED_V1 (ADR P10): Cards carry no progress, nothing to count.
            or (not consolidated and int(subject.contributor_count) != len(note.cards))
        ):
            raise ConnectAuthorityReadError(
                "INCOMPLETE_AUTHORITY_COMPATIBILITY",
                "NOTE import Card topology differs from its canonical subject.",
            )

    user = db.session.get(User, user_id)
    timezone_name = stats_overview.get_effective_timezone_name(
        getattr(user, "timezone", "UTC")
    )
    options_by_deck_id: dict[int | None, anki_scheduler.DeckOptions] = {}
    cards: list[Card] = []
    deck_options_by_card_id: dict[str, anki_scheduler.DeckOptions] = {}
    for note in notes:
        if note.deck_id not in options_by_deck_id:
            options_by_deck_id[note.deck_id] = resolve_deck_options(
                user_id=user_id, deck_id=note.deck_id
            )
        for card in note.cards:
            cards.append(card)
            deck_options_by_card_id[str(card.id)] = options_by_deck_id[note.deck_id]
    try:
        load_study_authority_card_reads(
            db.session,
            learner_user_id=user_id,
            cards=tuple(cards),
            now_utc=datetime.now(UTC).replace(tzinfo=None),
            timezone_name=timezone_name,
            deck_options_by_card_id=deck_options_by_card_id,
        )
    except (
        StudyAuthorityFenceError,
        StudyAuthorityReadError,
        StudyProgressCodecError,
    ) as exc:
        raise ConnectAuthorityReadError(exc.code, str(exc)) from exc


def get_import_note_statuses(
    user_id: int,
    session_id: object,
    notes: object,
) -> dict[str, Any]:
    try:
        route = lock_study_authority_route(
            db.session,
            learner_user_id=user_id,
            allow_note_authority=True,
        )
    except StudyAuthorityFenceError as exc:
        raise ConnectAuthorityReadError(exc.code, str(exc)) from exc
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
    _verify_note_authority_import_status(
        user_id=user_id,
        requested_cards=requested_cards,
        refs_by_external_id=refs_by_external_id,
        card_refs_by_external_id=card_refs_by_external_id,
        consolidated=route.storage_profile == "CONSOLIDATED_V1",
    )
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

    # NOTE fences refs on the Note row's authority revision (ADR P9-03 §2.6).
    canonical = route.mode_code == "NOTE"
    token_revision_by_card_id: dict[str, int] = {}
    from models.card import Card
    from models.study_progress_subject import StudyProgressSubject

    fenced_card_ids = sorted({str(row.card_id) for row in card_refs if row.card_id})
    if fenced_card_ids:
        from models.card import load_cards

        # ADR P10: the revision is a column of the Note's own row.
        note_by_card_id = {
            card_id: str(card.note_id) for card_id, card in load_cards(db.session, fenced_card_ids).items()
        }
        revision_by_note_id = {
            str(note_id): int(revision)
            for note_id, revision in db.session.query(
                StudyProgressSubject.live_note_id, StudyProgressSubject.authority_revision,
            ).filter(
                StudyProgressSubject.learner_user_id == user_id,
                StudyProgressSubject.live_note_id.in_(sorted(set(note_by_card_id.values()))),
            ).all()
        } if note_by_card_id else {}
        token_revision_by_card_id = {
            card_id: revision_by_note_id[note_id]
            for card_id, note_id in note_by_card_id.items() if note_id in revision_by_note_id
        }

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
            revision = token_revision_by_card_id.get(str(card_ref.card_id))
            local_changed = (
                card_ref.applied_local_revision_state == "AUTHORITY"
                and card_ref.applied_authority_revision is not None
                and revision is not None
                and int(card_ref.applied_authority_revision) != revision
            )
            if card_ref is not None:
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
                    "serverSnapshotHash": (
                        str(card_ref.snapshot_hash)
                        if card_ref is not None and card_ref.snapshot_hash
                        else None
                    ),
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



