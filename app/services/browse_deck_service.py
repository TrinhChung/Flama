"""Load Browse's deck structure independently of scoped study summaries."""

from app.repositories import browse_deck_repository, browse_note_repository, vocabulary_repository
from app.services import browse_card_service as shared


def _structure_rows(decks):
    by_id = {int(deck.id): deck for deck in decks}
    children = vocabulary_repository.deck_children_map(decks)
    roots = [deck for deck in decks if deck.parent_id not in by_id]
    roots.sort(key=lambda deck: (deck.position or 0, deck.created_at, deck.id))
    result, visited = [], set()

    def visit(deck, prefix):
        if deck.id in visited:
            return
        visited.add(deck.id)
        path = f"{prefix} :: {deck.name}" if prefix else deck.name
        result.append({"id": deck.id, "name": deck.name, "parent_id": deck.parent_id,
            "path": path, "summary_loaded": False})
        for child in children.get(deck.id, []):
            visit(child, path)

    for root in roots:
        visit(root, "")
    return result


def build_structure(*, user_id, admin_mode):
    # No list context, NoteType distribution or progress aggregate on this path.
    decks = vocabulary_repository.collect_accessible_browse_decks(
        user_id=user_id, admin_mode=admin_mode)
    return {"decks": _structure_rows(decks)}


def build_summaries(*, user_id, admin_mode, timezone_name, deck_ids):
    context = shared._build_browse_query(user_id=user_id, admin_mode=admin_mode,
        timezone_name=timezone_name, query_args={}, notes_only=True, scope_only=True,
        scoped_deck_ids=deck_ids)
    if context is None:
        raise shared.BrowseApiError("Deck not found", status=404)
    by_id = context.deck_by_id
    children = vocabulary_repository.deck_children_map(list(by_id.values()))
    direct_types, names = browse_deck_repository.direct_note_types(context,
        user_id=user_id, admin_mode=admin_mode)
    boundary = int(context.runtime_settings.day_boundary_hour_local)
    today = shared.study_repository._today_day_index(now=context.now,
        timezone_name=timezone_name, day_boundary_hour_local=boundary)
    direct_counts = browse_note_repository.deck_counts(context, user_id=user_id,
        admin_mode=admin_mode, today_day_index=today,
        day_cutoff_utc=shared._day_index_to_datetime(today + 1, boundary,
            timezone_name=timezone_name))
    cached = {}

    def summary(deck_id, visiting):
        if deck_id in cached:
            return cached[deck_id]
        deck = by_id[deck_id]
        counts = dict(direct_counts.get(deck_id, {"total": 0, "new": 0, "learn": 0, "due": 0}))
        types = set(direct_types.get(deck_id, ()))
        for child in children.get(deck_id, []):
            if child.id in visiting:
                continue
            nested = summary(child.id, visiting | {child.id})
            for key in counts:
                counts[key] += nested["counts"][key]
            types.update(nested["note_type_ids"])
        sorted_types = sorted(types)
        resolved_type = sorted_types[0] if len(sorted_types) == 1 else str(deck.note_type_id or "") or None
        result = {"id": deck.id, "name": deck.name, "parent_id": deck.parent_id,
            "note_type_id": resolved_type,
            "note_type_name": names.get(sorted_types[0], sorted_types[0]) if len(sorted_types) == 1 else None,
            "note_type_ids": sorted_types,
            "note_type_names": [names.get(type_id, type_id) for type_id in sorted_types],
            "has_mixed_note_types": len(sorted_types) > 1,
            "counts": counts, "summary_loaded": True}
        cached[deck_id] = result
        return result

    # Path is structural and is retained from the structure query on the client.
    # Only requested nodes are returned; descendants participate in the rollup.
    return {"decks": [summary(deck_id, {deck_id}) for deck_id in deck_ids]}
