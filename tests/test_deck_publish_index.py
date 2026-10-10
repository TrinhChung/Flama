"""Publish summary parity with the old reachable-set oracle and scale guards."""

from collections import defaultdict, deque
from dataclasses import fields
import random
from types import SimpleNamespace
import tracemalloc
import unittest

from app.services.deck_publish_index import build_deck_publish_index
from app.services import flashcards_share_service
from app.services.share import publish


def _legacy_subtrees(parent_ids):
    children = defaultdict(list)
    for deck_id, parent_id in parent_ids.items():
        if parent_id is not None and parent_id != deck_id:
            children[parent_id].append(deck_id)
    subtrees = {}
    for root_id in parent_ids:
        reachable = {root_id}
        queue = deque([root_id])
        while queue:
            for child_id in children[queue.popleft()]:
                if child_id not in reachable:
                    reachable.add(child_id)
                    queue.append(child_id)
        subtrees[root_id] = reachable
    return subtrees


class DeckPublishIndexTests(unittest.TestCase):
    def _assert_oracle(self, parent_ids, counts, note_types, shared_ids):
        summaries = build_deck_publish_index(
            parent_ids=parent_ids, direct_card_counts=counts,
            deck_to_note_types=note_types, shared_deck_ids=shared_ids,
        )
        subtrees = _legacy_subtrees(parent_ids)
        for deck_id, reachable in subtrees.items():
            summary = summaries[deck_id]
            self.assertEqual(summary.card_count, sum(counts.get(member_id, 0) for member_id in reachable))
            subtree_nt_ids = {nt_id for member_id in reachable for nt_id in note_types.get(member_id, ())}
            self.assertEqual(summary.mixed_note_types, len(subtree_nt_ids) > 1)
            self.assertEqual(summary.note_type_id, next(iter(subtree_nt_ids)) if len(subtree_nt_ids) == 1 else None)
            self.assertEqual(summary.smallest_shared_descendant, min((reachable - {deck_id}) & shared_ids, default=None))
            seen = {deck_id}
            parent_id = parent_ids[deck_id]
            ancestor_id = None
            while parent_id is not None and parent_id not in seen:
                seen.add(parent_id)
                if parent_id in shared_ids:
                    ancestor_id = parent_id
                    break
                if parent_id not in parent_ids:
                    break
                parent_id = parent_ids[parent_id]
            self.assertEqual(summary.nearest_shared_ancestor, ancestor_id)
        return summaries, subtrees

    def test_small_graph_oracle_including_cycles_self_loops_and_dangling_parents(self):
        rng = random.Random(20261010)
        for _ in range(100):
            node_count = rng.randint(1, 45)
            parent_ids = {node_id: rng.choice([None, 1000, *range(node_count)]) for node_id in range(node_count)}
            counts = {node_id: rng.randint(0, 7) for node_id in parent_ids}
            note_types = {node_id: set(rng.sample(["a", "b", "c"], rng.randint(0, 3))) for node_id in parent_ids}
            shared = {node_id for node_id in [1000, *parent_ids] if rng.random() < 0.25}
            self._assert_oracle(parent_ids, counts, note_types, shared)

    def test_eligibility_exact_parity_with_legacy_context_and_allow_existing(self):
        parent_ids = {1: None, 2: 1, 3: 2, 4: 1, 5: 6, 6: 5, 7: 5, 8: 8, 9: 1000, 10: None, 11: None}
        counts = {deck_id: deck_id for deck_id in parent_ids}
        note_types = {deck_id: {"installed"} for deck_id in parent_ids if deck_id <= 4}
        note_types[3] = {"installed", "another"}
        note_types[10] = {"installed"}
        shared_ids = {1, 3, 4, 5, 8, 1000}
        summaries, subtrees = self._assert_oracle(parent_ids, counts, note_types, shared_ids)
        decks = {deck_id: SimpleNamespace(
            id=deck_id, name=f"Deck {deck_id}", parent_id=parent_id,
            owner_user_id=1, deleted_at=None,
        ) for deck_id, parent_id in parent_ids.items()}
        decks[11].owner_user_id = 2
        shared = {deck_id: SimpleNamespace(id=f"listing-{deck_id}") for deck_id in shared_ids}
        context = (decks, {4}, shared)
        for service in (flashcards_share_service, publish):
            legacy = service.DeckPublishBatchContext(subtrees, note_types, {"installed"}, {"installed", "another"})
            bounded = service.DeckPublishBatchContext({}, note_types, {"installed"}, {"installed", "another"}, summaries)
            for allow_existing in (False, True):
                for deck in decks.values():
                    with self.subTest(service=service.__name__, deck=deck.id, allow_existing=allow_existing):
                        old_result = service.get_deck_publish_eligibility(
                            user_id=1, deck=deck, allow_existing=allow_existing,
                            context=context, batch_context=legacy,
                        )
                        new_result = service.get_deck_publish_eligibility(
                            user_id=1, deck=deck, allow_existing=allow_existing,
                            context=context, batch_context=bounded,
                        )
                        self.assertEqual(new_result, old_result)

    def test_descendant_uses_smallest_id_and_ancestor_uses_nearest_parent(self):
        parents = {1: None, 20: 1, 30: 20, 7: 30, 5: 30, 40: 30}
        summaries, _ = self._assert_oracle(parents, {}, {}, {1, 20, 7, 5})
        self.assertEqual(summaries[30].smallest_shared_descendant, 5)
        self.assertEqual(summaries[30].nearest_shared_ancestor, 20)
        self.assertEqual(summaries[20].nearest_shared_ancestor, 1)

    def test_empty_graph(self):
        self.assertEqual(build_deck_publish_index(
            parent_ids={}, direct_card_counts={}, deck_to_note_types={}, shared_deck_ids=set(),
        ), {})

    def test_deep_chain_allocations_remain_bounded_and_linear(self):
        peaks = {}
        for size in (1000, 2000, 4000):
            parents = {deck_id: deck_id - 1 if deck_id else None for deck_id in range(size)}
            counts = dict.fromkeys(parents, 1)
            note_types = {size - 1: {"one"}}
            tracemalloc.start()
            try:
                summaries = build_deck_publish_index(
                    parent_ids=parents, direct_card_counts=counts,
                    deck_to_note_types=note_types, shared_deck_ids={size - 1},
                )
                peaks[size] = tracemalloc.get_traced_memory()[1]
            finally:
                tracemalloc.stop()
            self.assertEqual(summaries[0].card_count, size)
            self.assertEqual(summaries[size - 1].card_count, 1)
            self.assertEqual(summaries[0].note_type_id, "one")
            self.assertEqual(summaries[0].smallest_shared_descendant, size - 1)
            self.assertIsNone(summaries[size - 1].smallest_shared_descendant)
            self.assertEqual(len(summaries), size)
            self.assertEqual(len(fields(summaries[0])), 5)
            self.assertFalse(hasattr(summaries[0], "__dict__"))
        self.assertLessEqual(peaks[2000], 20 * 1024 * 1024)
        self.assertLessEqual(peaks[4000], 2.5 * peaks[2000])

    def test_large_cycle_counts_each_deck_once_and_excludes_self_from_shared_ancestors(self):
        size = 4000
        parents = {deck_id: (deck_id + 1) % size for deck_id in range(size)}
        summaries = build_deck_publish_index(
            parent_ids=parents, direct_card_counts=dict.fromkeys(parents, 1),
            deck_to_note_types={size - 1: {"one"}}, shared_deck_ids={0},
        )
        self.assertTrue(all(summary.card_count == size for summary in summaries.values()))
        self.assertTrue(all(summary.note_type_id == "one" for summary in summaries.values()))
        self.assertIsNone(summaries[0].smallest_shared_descendant)
        self.assertIsNone(summaries[0].nearest_shared_ancestor)
        self.assertTrue(all(summary.nearest_shared_ancestor == 0 for deck_id, summary in summaries.items() if deck_id != 0))


if __name__ == "__main__":
    unittest.main()
