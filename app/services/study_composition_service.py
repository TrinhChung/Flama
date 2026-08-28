"""StudyMode & Composition contract and compatibility resolution.

Phase 3 establishes the composition responsibility:
Decoupling Template presentation, Interaction type, and Algorithm execution
from rigid physical Card structures while providing seamless backward compatibility
for existing Templates and Cards without requiring data regeneration.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from models import db
from models.card import Card
from models.deck import Deck
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from app.repositories.deck_tree_query import collect_subtree_ids
from app.services.study_action_runtime import REVIEW_TRIGGER_CONTRACT_VERSION
from app.services.study_algorithm_registry import DEFAULT_ALGORITHM_IDENTITY


DEFAULT_STUDY_MODE_KEY = "flashcard"
DEFAULT_INTERACTION_KEY = "review.four-rating"
DEFAULT_TRIGGER_KEY = "scheduler.review"


@dataclass(frozen=True)
class AppliedComposition:
    composition_id: str
    mode_key: str
    note_type_id: str
    template_id: str
    template_name: str
    is_default: bool
    interaction_key: str = DEFAULT_INTERACTION_KEY
    trigger_key: str = DEFAULT_TRIGGER_KEY
    trigger_contract_version: str = REVIEW_TRIGGER_CONTRACT_VERSION
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def make_compatibility_composition_id(note_type_id: str | int, template_id: str | int) -> str:
    return f"comp:notetype:{note_type_id}:template:{template_id}"


def build_compatibility_composition(
    template: Template,
    *,
    mode_key: str = DEFAULT_STUDY_MODE_KEY,
    interaction_key: str = DEFAULT_INTERACTION_KEY,
    trigger_key: str = DEFAULT_TRIGGER_KEY,
    trigger_contract_version: str = REVIEW_TRIGGER_CONTRACT_VERSION,
    algorithm_key: str = DEFAULT_ALGORITHM_IDENTITY.key,
    algorithm_version: str = DEFAULT_ALGORITHM_IDENTITY.version,
) -> AppliedComposition:
    note_type_id = str(template.note_type_id)
    template_id = str(template.id)
    return AppliedComposition(
        composition_id=make_compatibility_composition_id(note_type_id, template_id),
        mode_key=mode_key,
        note_type_id=note_type_id,
        template_id=template_id,
        template_name=str(template.name or ""),
        is_default=bool(template.is_default),
        interaction_key=interaction_key,
        trigger_key=trigger_key,
        trigger_contract_version=trigger_contract_version,
        algorithm_key=algorithm_key,
        algorithm_version=algorithm_version,
    )


def resolve_compatibility_composition_for_card(card: Card) -> AppliedComposition:
    template = db.session.get(Template, card.template_id)
    if template is None:
        raise ValueError(f"Card {card.id} references missing template {card.template_id}")
    return build_compatibility_composition(template)


def resolve_compatibility_compositions_for_note_type(
    note_type_id: str | int,
) -> list[AppliedComposition]:
    templates = (
        Template.query.filter(Template.note_type_id == str(note_type_id))
        .order_by(Template.position.asc(), Template.id.asc())
        .all()
    )
    return [build_compatibility_composition(t) for t in templates]


def list_available_compositions_for_scope(
    scope_type: str,
    scope_id: str | int,
    user_id: int,
) -> list[AppliedComposition]:
    """List distinct applicable compositions for a deck or note_type study entry."""
    if scope_type == "note_type":
        nt = db.session.get(NoteType, str(scope_id))
        if nt is None or nt.user_id != user_id:
            return []
        return resolve_compatibility_compositions_for_note_type(scope_id)

    if scope_type == "deck":
        deck_id = int(scope_id) if str(scope_id).isdigit() else None
        if deck_id is None:
            return []

        # Recursively include child decks — matches study session scope resolution.
        scope_deck_ids = collect_subtree_ids(deck_id)
        if not scope_deck_ids:
            return []

        note_type_ids = (
            db.session.query(db.distinct(Note.note_type_id))
            .filter(Note.deck_id.in_(scope_deck_ids), Note.user_id == user_id)
            .all()
        )
        if not note_type_ids:
            deck = db.session.get(Deck, deck_id)
            if (
                deck is not None
                and deck.note_type_id is not None
                and deck.owner_user_id == user_id
            ):
                return resolve_compatibility_compositions_for_note_type(
                    str(deck.note_type_id)
                )
            return []

        compositions: list[AppliedComposition] = []
        seen_comp_ids: set[str] = set()
        for (nt_id,) in note_type_ids:
            if nt_id:
                for comp in resolve_compatibility_compositions_for_note_type(str(nt_id)):
                    if comp.composition_id not in seen_comp_ids:
                        seen_comp_ids.add(comp.composition_id)
                        compositions.append(comp)
        return compositions

    return []
