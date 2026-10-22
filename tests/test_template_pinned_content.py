"""Pure presentation-policy checks: no database or dialect emulation."""

import unittest

from app.repositories.template_release_repository import resolve_pinned_content


class PinnedContentTests(unittest.TestCase):
    def setUp(self):
        self.old = {"front_html": "v1 {{term}}", "back_html": "v1 back",
                    "shared_css": ".v1{}", "input_schema": [{"key": "term", "type": "text"}]}
        self.new = {**self.old, "front_html": "v2 {{term}}", "shared_css": ".v2{}"}

    def test_receiving_another_decks_release_does_not_upgrade_this_decks_pin(self):
        effective, customized = resolve_pinned_content(self.old, self.new, self.new)
        self.assertEqual(effective, self.old)
        self.assertFalse(customized)

    def test_only_explicit_personal_edits_are_projected_onto_the_pinned_release(self):
        local = {**self.new, "shared_css": ".my-colors{}"}
        effective, customized = resolve_pinned_content(self.old, self.new, local)
        self.assertEqual(effective["front_html"], self.old["front_html"])
        self.assertEqual(effective["shared_css"], ".my-colors{}")
        self.assertTrue(customized)
        effective["input_schema"][0]["key"] = "changed-only-in-result"
        self.assertEqual(self.old["input_schema"][0]["key"], "term")

    def test_restoring_a_personal_field_to_upstream_restores_deck_pin(self):
        changed, _ = resolve_pinned_content(self.old, self.new, {**self.new, "front_html": "Mine"})
        restored, customized = resolve_pinned_content(self.old, self.new, self.new)
        self.assertEqual(changed["front_html"], "Mine")
        self.assertEqual(restored["front_html"], self.old["front_html"])
        self.assertFalse(customized)


if __name__ == "__main__":
    unittest.main()
