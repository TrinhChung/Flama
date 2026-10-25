"""Metadata projections for bounded Browse deck summaries."""

from models import db
from models.note import Note
from models.note_type import NoteType


def direct_note_types(context, *, user_id, admin_mode):
    """Preserve the full deck API's local membership and installed-type labels."""
    deck_ids = set(context.deck_by_id)
    by_deck = {deck_id: set() for deck_id in deck_ids}
    if deck_ids:
        for deck_id, type_id in db.session.query(Note.deck_id, Note.note_type_id).filter(
            Note.deck_id.in_(deck_ids)
        ).distinct():
            if deck_id is not None and type_id:
                by_deck[int(deck_id)].add(str(type_id))
    if not admin_mode and deck_ids:
        from models.deck_install import DeckInstall
        from models.deck_clone_deck_map import DeckCloneDeckMap
        # Match persisted metadata in the full tree API. Resolver fallback maps
        # authorize content, but must not invent NoteType labels for legacy trees.
        for local_id, type_id in db.session.query(
            DeckCloneDeckMap.local_deck_id, DeckInstall.source_note_type_id
        ).join(DeckInstall, DeckInstall.id == DeckCloneDeckMap.deck_install_id).filter(
            DeckInstall.user_id == user_id,
            DeckInstall.clone_mode == "logical_overlay",
            DeckInstall.local_deck_id.isnot(None),
            DeckCloneDeckMap.local_deck_id.in_(deck_ids),
        ):
            if type_id:
                by_deck[int(local_id)].add(str(type_id))
    for deck_id, deck in context.deck_by_id.items():
        if deck.note_type_id:
            by_deck[deck_id].add(str(deck.note_type_id))
    all_types = set().union(*by_deck.values()) if by_deck else set()
    names = dict(db.session.query(NoteType.id, NoteType.name).filter(
        NoteType.id.in_(all_types)
    )) if all_types else {}
    return by_deck, names
