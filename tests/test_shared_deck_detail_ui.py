"""Static regression checks for the React shared-deck preview."""

import unittest
from pathlib import Path


class SharedDeckDetailUiTests(unittest.TestCase):
    def test_marketplace_preview_uses_react_card_renderer(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "frontend"
            / "src"
            / "features"
            / "marketplace"
            / "pages"
            / "SharedDeckDetailPage.tsx"
        )
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("/api/shared/decks/${id}/templates/${selectedTemplateId}/preview", script)
        self.assertIn("<CardDisplay", script)
        self.assertIn('scope="shared_deck_preview"', script)


if __name__ == "__main__":
    unittest.main()
