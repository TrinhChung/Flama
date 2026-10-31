"""Pure selection rules for contributions; no database involved."""
import unittest
from types import SimpleNamespace

from app.services.change_request.helpers import (
    end_page_on_note_boundary,
    select_local_changes,
    select_request_items,
)
from app.validators.deck_change_request import ChangeSelectionInput


def note_change(item_id, note_id, *, added_field=None):
    return SimpleNamespace(id=item_id, change_type="note_field_set", source_ref_id=note_id,
        local_ref_id=f"override-{item_id}", path_key="Field",
        metadata_json={"source_note_id": note_id, "local_added_field_def_id": added_field})


def field_addition(item_id, added_field):
    return SimpleNamespace(id=item_id, change_type="field_def_add", source_ref_id=None,
        local_ref_id=added_field, path_key="Extra", metadata_json={"field_name": "Extra"})


class ChangeSelectionTests(unittest.TestCase):
    def test_accepting_a_note_keeps_the_learner_field_it_writes_to(self):
        addition = field_addition("add", "extra-1")
        uses_new_field = note_change("a", "note-a", added_field="extra-1")
        other = note_change("b", "note-b")
        chosen = select_request_items([addition, uses_new_field, other],
            ChangeSelectionInput(mode="only", ids=frozenset({"a"})))
        self.assertEqual([item.id for item in chosen], ["add", "a"])

    def test_declining_only_unrelated_notes_keeps_order(self):
        items = [field_addition("add", "extra-1"), note_change("a", "note-a"), note_change("b", "note-b")]
        chosen = select_request_items(items, ChangeSelectionInput(mode="all_except", ids=frozenset({"add", "b"})))
        self.assertEqual([item.id for item in chosen], ["a"])

    def test_local_selection_picks_notes_and_the_schema_group(self):
        payloads = [
            {"change_type": "field_def_update", "local_ref_id": "o", "path_key": "name", "metadata_json": {}},
            {"change_type": "note_field_set", "source_ref_id": "n1", "metadata_json": {"source_note_id": "n1"}},
            {"change_type": "note_field_set", "source_ref_id": "n2", "metadata_json": {"source_note_id": "n2"}},
        ]
        without_schema = select_local_changes(payloads, ChangeSelectionInput(
            mode="all_except", ids=frozenset({"n2"}), include_schema_changes=False))
        self.assertEqual(without_schema, [payloads[1]])
        only_second = select_local_changes(payloads, ChangeSelectionInput(mode="only", ids=frozenset({"n2"})))
        self.assertEqual(only_second, [payloads[0], payloads[2]])

    def test_pages_end_before_a_note_that_continues(self):
        page = [note_change("a", "n1"), note_change("b", "n2")]
        self.assertEqual([row.id for row in end_page_on_note_boundary(page, note_change("c", "n2"))], ["a"])
        self.assertEqual(end_page_on_note_boundary(page, note_change("c", "n3")), page)
        single = [note_change("a", "n1")]
        self.assertEqual(end_page_on_note_boundary(single, note_change("b", "n1")), single)


if __name__ == "__main__":
    unittest.main()
