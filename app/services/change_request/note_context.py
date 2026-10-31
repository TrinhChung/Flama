"""Whole-note context for contribution review.

Items carry only changed fields. Reviewers compare whole notes, so each page
also returns the note type's fields, the unchanged values of its notes and the
sub-deck each note sits in.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from app.services import flashcards_share
from app.services.change_request.helpers import (
    _apply_schema_only_values,
    _change_attr,
    _get_request_install,
    _load_notes_by_ids,
    _note_deck_ids,
    change_note_id,
)
from models import db
from models.deck import Deck
from models.deck_change_request import DeckChangeRequest
from models.deck_install import DeckInstall


def _subtree_decks(root_deck_id: int | None) -> dict[int, dict[str, Any]]:
    """Every deck under the root: its names from the root down, and its rank in tree order."""
    from app.repositories.deck_tree_query import collect_subtree_ids
    deck_ids = collect_subtree_ids(root_deck_id)
    if not deck_ids:
        return {}
    rows = {
        int(row.id): row
        for row in db.session.query(Deck.id, Deck.parent_id, Deck.name, Deck.position)
        .filter(Deck.id.in_(deck_ids)).all()
    }

    def lineage(deck_id: int) -> list[Any]:
        chain, current = [], rows.get(deck_id)
        while current is not None and len(chain) < len(rows):
            chain.append(current)
            if int(current.id) == int(root_deck_id) or current.parent_id is None:
                break
            current = rows.get(int(current.parent_id))
        return chain[::-1]

    lineages = {deck_id: lineage(deck_id) for deck_id in rows}
    ranked = sorted(rows, key=lambda deck_id: [
        (int(row.position or 0), str(row.name or "").casefold(), int(row.id)) for row in lineages[deck_id]
    ])
    return {
        deck_id: {"path": [str(row.name or "") for row in lineages[deck_id]], "order": rank}
        for rank, deck_id in enumerate(ranked)
    }


def viewer_deck_index(install: DeckInstall | None, *, as_owner: bool) -> dict[int, dict[str, Any]]:
    """Source deck id -> that deck as the viewer's own library names it.

    The owner sees their source tree; a learner sees the local folders the
    install maps it to (new author sub-decks fall under the nearest mapped one).
    """
    if install is None:
        return {}
    if as_owner:
        return {
            deck_id: {"key": str(deck_id), **deck}
            for deck_id, deck in _subtree_decks(install.source_deck_id).items()
        }
    from app.services.effective_note_reader import expanded_source_deck_mapping
    local_decks = _subtree_decks(install.local_deck_id)
    return {
        int(source_id): {"key": str(local_id), **local_decks[local_id]}
        for source_id, local_id in expanded_source_deck_mapping(install).items()
        if local_id in local_decks
    }


def _note_labels(changes: list[Any]) -> dict[str, str]:
    labels: dict[str, str] = {}
    for change in changes:
        note_id = change_note_id(change)
        if note_id and note_id not in labels:
            metadata = dict(_change_attr(change, "metadata_json") or {})
            labels[note_id] = str(metadata.get("source_note_label") or "")
    return labels


def note_context_payload(
    schema_view: Any,
    values_by_note: dict[str, dict[str, Any]],
    changes: list[Any],
    *,
    deck_by_note: dict[str, int | None] | None = None,
    deck_index: dict[int, dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Serialize only the fields the learner sees, for the notes on this page."""
    field_defs = [
        {"name": str(row.name), "field_type": str(row.field_type or "text")}
        for row in (schema_view.field_defs if schema_view is not None else [])
        if str(row.name or "").strip()
    ]
    names = [row["name"] for row in field_defs]
    notes = {}
    for note_id, label in _note_labels(changes).items():
        values = values_by_note.get(note_id)
        deck_id = (deck_by_note or {}).get(note_id)
        notes[note_id] = {
            "label": label,
            "values": (
                {name: values[name] for name in names if name in values}
                if values is not None
                else None
            ),
            "deck": (deck_index or {}).get(int(deck_id)) if deck_id is not None else None,
        }
    return {"field_defs": field_defs, "notes": notes}


def _base_values_for_requester(install: DeckInstall, note_ids: set[str]) -> dict[str, dict[str, Any]]:
    # Same Base the local preview diffed against, so learners never see
    # unpublished owner edits here.
    from app.services.effective_note_reader import current_release_for_install, install_release_id
    base_release = current_release_for_install(install)
    if install_release_id(install) and base_release is not None:
        from app.services import deck_release_service
        return deck_release_service.get_note_values_for_ids_at_release(base_release, note_ids)
    return {note_id: dict(note.field_values or {}) for note_id, note in _load_notes_by_ids(note_ids).items()}


def build_request_note_context(
    request_obj: DeckChangeRequest,
    items: list[Any],
    *,
    viewer_user_id: int,
) -> dict[str, Any]:
    install = _get_request_install(request_obj)
    note_ids = {note_id for item in items if (note_id := change_note_id(item))}
    if install is None or not str(install.source_note_type_id or "").strip():
        return note_context_payload(None, {}, items)
    schema_view = flashcards_share.build_clone_schema_view(
        install=install,
        source_note_type_id=str(install.source_note_type_id),
    )
    as_owner = int(request_obj.owner_user_id) == int(viewer_user_id)
    if as_owner:
        # The owner merges into their current notes, so show those.
        notes = _load_notes_by_ids(note_ids)
        raw_values = {note_id: dict(note.field_values or {}) for note_id, note in notes.items()}
        deck_by_note = {note_id: note.deck_id for note_id, note in notes.items()}
    else:
        raw_values = _base_values_for_requester(install, note_ids) if note_ids else {}
        deck_by_note = _note_deck_ids(note_ids)
    values_by_note = {
        note_id: _apply_schema_only_values(
            SimpleNamespace(field_values=values),
            removed_field_names=set(schema_view.removed_field_names or set()),
            renamed_field_names=dict(schema_view.renamed_field_names or {}),
        )
        for note_id, values in raw_values.items()
    }
    return note_context_payload(
        schema_view, values_by_note, items,
        deck_by_note=deck_by_note, deck_index=viewer_deck_index(install, as_owner=as_owner),
    )
