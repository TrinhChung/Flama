"""Static regression checks for the shared deck preview host."""

import unittest
from pathlib import Path


class SharedDeckDetailUiTests(unittest.TestCase):
    def test_marketplace_preview_uses_fixed_iframe_height(self):
        script_path = (
            Path(__file__).resolve().parents[1]
            / "static"
            / "js"
            / "pages"
            / "shared_deck_detail"
            / "main.js"
        )
        script = script_path.read_text(encoding="utf-8")

        self.assertIn("createRendererFrameController(previewFrame", script)
        self.assertIn("autoHeight: false", script)
        self.assertIn("fixedHeight: 416", script)


if __name__ == "__main__":
    unittest.main()
