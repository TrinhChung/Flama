"""Flama Connect service (backward-compatibility facade).

All implementations have been modularized into domain submodules under `app.services.connect`.
"""

from app.services.connect import *
from app.services.connect import (
    _normalized_identity,
    _deck_path,
    _unescape_query_clause,
    _session_source_key,
    _owned_decks,
    _resolve_deck,
    _accessible_note_types,
    _resolve_note_type,
    _identity_field,
    _clone_map_for_deck,
    _find_existing_note,
    _parse_note,
    _is_duplicate,
    _ensure_note_ref,
    _migrate_source_aliases,
    _normalize_note_type_plan,
    _existing_target_for_plan,
    _validate_existing_target,
    _create_note_type_from_plan,
    _target_note_type_hash,
    _upsert_note_type_ref,
    _get_import_session,
    _reconcile_note_cards,
    _migrate_cards_progress,
    _upsert_import_card,
)
