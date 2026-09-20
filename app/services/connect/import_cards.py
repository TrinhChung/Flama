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
    vocabulary_repository,
)
from app.services import (
    anki_scheduler,
    deck_working_tree_service,
    flashcard_content_service,
    flashcards_share,
    flashcards_share_service,
    flama_connect_media_service,
    study_progress_lifecycle_mirror_service,
    study_progress_shadow_mirror_service,
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

def _reconcile_note_cards(
    note: Note,
    note_type: NoteType,
    *,
    is_new_note: bool = False,
    preserve_released_history: bool | None = None,
) -> None:
    templates = sorted(note_type.templates, key=lambda item: (item.position, item.id))
    if not templates:
        raise ConnectError("model has no card template")
    expected_ids = {template.id for template in templates}
    existing_by_template = {card.template_id: card for card in note.cards}
    requires_reconcile = expected_ids != set(existing_by_template)
    if requires_reconcile and not is_new_note:
        from app.services import deck_working_tree_service

        must_preserve_history = (
            deck_working_tree_service.note_has_shared_release_dependents(note)
            if preserve_released_history is None
            else preserve_released_history
        )
        if must_preserve_history:
            raise ConnectError(
                "cannot change card templates for a released shared note; "
                "template-aware deck releases are required to preserve study history"
            )
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
    source_note_ref: ConnectSourceNoteRef,
) -> list[dict[str, Any]]:
    if not cards_progress_payload:
        return []

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

    cards_in_scope = tuple(
        card
        for ord_idx, template in enumerate(templates)
        if ord_idx in progress_map
        for card in (existing_cards.get(template.id),)
        if card is not None
    )
    mirror_plan = study_progress_shadow_mirror_service.prepare_native_mirror(
        db.session,
        learner_user_id=user_id,
        cards=cards_in_scope,
    )
    applied_contexts: dict[
        str, study_progress_shadow_mirror_service.ExternalProgressMirrorContext
    ] = {}
    results: list[dict[str, Any]] = []
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

        anki_type = int(progress_data.get("type", 0))
        anki_queue = int(progress_data.get("queue", 0))

        # 0=new, 1=learning, 2=review, 3=relearning
        queue_map = {0: "new", 1: "learning", 2: "review", 3: "relearning"}
        desired_queue = queue_map.get(anki_type, "new")

        # queue: -1=suspended, -2=sched buried, -3=user buried
        desired_suspended = anki_queue == -1
        desired_buried = anki_queue in {-2, -3}
        desired_buried_until_day = (
            today_day_index_flama + 1 if desired_buried else None
        )

        relative_due = progress_data.get("relativeDue")
        due_at_str = progress_data.get("dueAt")
        desired_due_at = None
        desired_due_day = None
        compare_due_at = False
        if relative_due is not None:
            if isinstance(relative_due, bool) or not isinstance(relative_due, (int, float)):
                raise ConnectError("cardsProgress relativeDue must be a number or null")
            if not -365000 <= int(relative_due) <= 365000:
                raise ConnectError("cardsProgress relativeDue is out of range")
            desired_due_day = today_day_index_flama + int(relative_due)
            desired_due_at = _day_index_to_datetime(
                desired_due_day,
                boundary_hour,
                timezone_name=timezone_name,
            )
            compare_due_at = True
        elif due_at_str:
            if not isinstance(due_at_str, str) or len(due_at_str) > 64:
                raise ConnectError("cardsProgress dueAt is invalid")
            try:
                clean_str = due_at_str.replace("Z", "+00:00")
                dt = datetime.fromisoformat(clean_str)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                desired_due_at = dt
            except (TypeError, ValueError) as exc:
                raise ConnectError("cardsProgress dueAt is invalid") from exc
            compare_due_at = True
        elif anki_type == 2:
            desired_due_day = today_day_index_flama
            desired_due_at = now
        elif anki_type in {1, 3}:
            desired_due_at = now
        else:
            desired_due_at = now

        desired = {
            "queue": desired_queue,
            "step_index": 0,
            "due_at": desired_due_at,
            "due_day": desired_due_day,
            "interval_days": int(progress_data.get("interval", 0)),
            "interval_days_raw": float(progress_data.get("interval", 0)),
            "ease_factor": float(progress_data.get("factor", 2500)) / 1000.0,
            "is_suspended": desired_suspended,
            "is_buried": desired_buried,
            "buried_until_day": desired_buried_until_day,
            "review_kind": "review",
            "scheduler_mode": "anki",
            "memory_stability": None,
            "memory_difficulty": None,
            "suspension_reason": "anki_import" if desired_suspended else None,
            "reps": int(progress_data.get("reps", 0)),
            "lapses": int(progress_data.get("lapses", 0)),
            "last_reviewed_at": anki_last_reviewed_at,
        }

        def _matches_existing() -> bool:
            if progress is None:
                return False
            for field_name, expected in desired.items():
                if field_name == "due_at" and not compare_due_at:
                    continue
                actual = getattr(progress, field_name, None)
                if isinstance(expected, float):
                    if actual is None or abs(float(actual) - expected) > 1e-9:
                        return False
                elif actual != expected:
                    return False
            return True

        if progress is not None:
            current_reviewed_at = progress.last_reviewed_at
            if (
                current_reviewed_at is not None
                and anki_last_reviewed_at is not None
                and anki_last_reviewed_at < current_reviewed_at
            ):
                results.append(
                    {
                        "ord": ord_idx,
                        "cardId": str(card.id),
                        "state": "stale",
                        "code": "PROGRESS_STALE",
                        "revision": int(progress.revision or 0),
                    }
                )
                continue
            ambiguous_order = (
                (current_reviewed_at is None and anki_last_reviewed_at is None)
                or (current_reviewed_at is not None and anki_last_reviewed_at is None)
                or (
                    current_reviewed_at is not None
                    and anki_last_reviewed_at == current_reviewed_at
                )
            )
            if ambiguous_order:
                if _matches_existing():
                    results.append(
                        {
                            "ord": ord_idx,
                            "cardId": str(card.id),
                            "state": "unchanged",
                            "code": "PROGRESS_UNCHANGED",
                            "revision": int(progress.revision or 0),
                        }
                    )
                else:
                    results.append(
                        {
                            "ord": ord_idx,
                            "cardId": str(card.id),
                            "state": "conflict",
                            "code": "AMBIGUOUS_PROGRESS_ORDER",
                            "revision": int(progress.revision or 0),
                        }
                    )
                continue
        else:
            progress = CardProgress(user_id=user_id, card_id=card.id)
            db.session.add(progress)

        for field_name, value in desired.items():
            setattr(progress, field_name, value)
        progress.revision = int(progress.revision or 0) + 1
        try:
            db.session.flush()
        except IntegrityError as exc:
            conflict = ConnectError(
                "card progress changed while the imported snapshot was being applied"
            )
            setattr(conflict, "code", "CONCURRENT_PROGRESS_WRITE")
            raise conflict from exc
        results.append(
            {
                "ord": ord_idx,
                "cardId": str(card.id),
                "state": "applied",
                "code": "PROGRESS_APPLIED",
                "revision": int(progress.revision or 0),
            }
        )
        applied_contexts[str(card.id)] = (
            study_progress_shadow_mirror_service.ExternalProgressMirrorContext(
                provenance_code="CONNECT_LEGACY_PROGRESS",
                history_completeness_code="HISTORY_SNAPSHOT_ONLY",
                source_note_ref=source_note_ref,
            )
        )
    if applied_contexts:
        study_progress_shadow_mirror_service.finalize_external_progress_mirror(
            mirror_plan,
            applied_contexts=applied_contexts,
        )
    return results



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
    expected_template_ids = {template.id for template in prepared.note_type.templates}
    removed_cards = tuple(
        card for card in note.cards if card.template_id not in expected_template_ids
    )
    lifecycle_plan = study_progress_lifecycle_mirror_service.prepare_lifecycle_mirror(
        db.session,
        removed_card_ids=(card.id for card in removed_cards),
    )
    if removed_cards:
        CardProgress.query.filter(
            CardProgress.card_id.in_([str(card.id) for card in removed_cards])
        ).delete(synchronize_session=False)
    _reconcile_note_cards(
        note,
        prepared.note_type,
        is_new_note=created,
        preserve_released_history=preserve_released_history,
    )
    if lifecycle_plan is not None:
        study_progress_lifecycle_mirror_service.finalize_lifecycle_mirror(
            lifecycle_plan,
            transition_code="DETACHED_CONTRIBUTOR_DELETED",
            source_path="connect.import_cards.reconcile",
            operation_key=f"{session.id}:{external_note_id}:template-reconcile",
        )
    cards_progress_payload = card_data.get("cardsProgress")
    progress_results: list[dict[str, Any]] = []
    if cards_progress_payload:
        progress_results = _migrate_cards_progress(
            user_id,
            note,
            prepared.note_type,
            cards_progress_payload,
            source_ref,
        )
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
                    and (
                        card_ref.applied_local_revision is None
                        or int(progress.revision or 0)
                        != int(card_ref.applied_local_revision)
                    )
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



