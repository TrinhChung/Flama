"""Bounded publish summaries for a parent graph, including malformed cycles.

Each deck has at most one parent. Peeling leaves therefore gives an iterative
post-order; the remaining nodes are disjoint cycles. Roll up each cycle once
instead of retaining every root's descendant set. Work and storage are O(D+K),
where K is the number of direct (deck, NoteType) pairs.
"""

from collections import deque
from dataclasses import dataclass
from typing import Mapping


@dataclass(frozen=True, slots=True)
class DeckPublishSummary:
    card_count: int
    note_type_id: str | None
    mixed_note_types: bool
    smallest_shared_descendant: int | None
    nearest_shared_ancestor: int | None


@dataclass(slots=True)
class _Rollup:
    card_count: int = 0
    note_type_id: str | None = None
    mixed_note_types: bool = False
    shared_ids: tuple[int, ...] = ()

    def merge_note_type(self, note_type_id: str | None, mixed: bool = False):
        if mixed or (self.note_type_id is not None and note_type_id is not None and self.note_type_id != note_type_id):
            self.mixed_note_types = True
            self.note_type_id = None
        elif not self.mixed_note_types and note_type_id is not None:
            self.note_type_id = note_type_id

    def merge(self, other: "_Rollup"):
        self.card_count += other.card_count
        self.merge_note_type(other.note_type_id, other.mixed_note_types)
        # At most four IDs; retaining two lets a root exclude itself.
        self.shared_ids = tuple(sorted(set(self.shared_ids + other.shared_ids))[:2])


def build_deck_publish_index(
    *,
    parent_ids: Mapping[int, int | None],
    direct_card_counts: Mapping[int, int],
    deck_to_note_types: Mapping[int, set[str]],
    shared_deck_ids: set[int],
) -> dict[int, DeckPublishSummary]:
    remaining_children = dict.fromkeys(parent_ids, 0)
    rollups = {}
    for deck_id, parent_id in parent_ids.items():
        if parent_id in remaining_children:
            remaining_children[parent_id] += 1
        rollup = _Rollup(
            card_count=int(direct_card_counts.get(deck_id, 0)),
            shared_ids=(deck_id,) if deck_id in shared_deck_ids else (),
        )
        for note_type_id in deck_to_note_types.get(deck_id, ()):
            rollup.merge_note_type(note_type_id)
        rollups[deck_id] = rollup

    queue = deque(deck_id for deck_id, count in remaining_children.items() if count == 0)
    postorder = []
    while queue:
        deck_id = queue.popleft()
        postorder.append(deck_id)
        parent_id = parent_ids[deck_id]
        if parent_id in remaining_children:
            rollups[parent_id].merge(rollups[deck_id])
            remaining_children[parent_id] -= 1
            if remaining_children[parent_id] == 0:
                queue.append(parent_id)

    nearest_ancestors: dict[int, int | None] = {}
    cycle_nodes_seen = set()
    for deck_id, count in remaining_children.items():
        if count == 0 or deck_id in cycle_nodes_seen:
            continue
        cycle = []
        current_id = deck_id
        while current_id not in cycle_nodes_seen:
            cycle_nodes_seen.add(current_id)
            cycle.append(current_id)
            current_id = parent_ids[current_id]
        component = _Rollup()
        for member_id in cycle:
            component.merge(rollups[member_id])
        for member_id in cycle:
            rollups[member_id] = component

        # cycle[i+1] is cycle[i]'s parent. Two reverse passes find the first
        # shared parent after wrapping, and exclude self when it is the only
        # shared node in that cycle. Attached descendants are not ancestors.
        next_shared = None
        for index in range(2 * len(cycle) - 1, -1, -1):
            member_id = cycle[index % len(cycle)]
            if index < len(cycle):
                nearest_ancestors[member_id] = next_shared if next_shared != member_id else None
            if member_id in shared_deck_ids:
                next_shared = member_id

    for deck_id in reversed(postorder):
        parent_id = parent_ids[deck_id]
        # Check before the in-scope lookup to retain the legacy context
        # behavior for an explicitly supplied shared dangling parent.
        nearest_ancestors[deck_id] = (
            parent_id if parent_id in shared_deck_ids
            else nearest_ancestors.get(parent_id)
        )

    return {
        deck_id: DeckPublishSummary(
            card_count=rollup.card_count,
            note_type_id=rollup.note_type_id,
            mixed_note_types=rollup.mixed_note_types,
            smallest_shared_descendant=next((
                shared_id for shared_id in rollup.shared_ids if shared_id != deck_id
            ), None),
            nearest_shared_ancestor=nearest_ancestors.get(deck_id),
        )
        for deck_id, rollup in rollups.items()
    }
