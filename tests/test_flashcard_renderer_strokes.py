"""Tests for flashcard rendering safety with static stroke SVG URLs."""

import unittest
from app.services.flashcard_renderer import (
    prepare_client_template_source,
    sanitize_html_fragment,
    sanitize_template_html_fragment,
)


class TestFlashcardRendererStrokes(unittest.TestCase):
    def test_sanitize_html_fragment_preserves_stroke_svg(self):
        stroke_html = (
            '<div class="flama-stroke-diagram" data-locale="ja">'
            '<img src="/static/strokes/ja/52c9.svg" alt="勉" title="勉" class="stroke-svg" loading="lazy" />'
            '<img src="/static/strokes/ja/5f37.svg" alt="強" title="強" class="stroke-svg" loading="lazy" />'
            '</div>'
        )
        sanitized = sanitize_html_fragment(stroke_html)
        self.assertIn('/static/strokes/ja/52c9.svg', sanitized)
        self.assertIn('/static/strokes/ja/5f37.svg', sanitized)
        self.assertIn('alt="勉"', sanitized)
        self.assertIn('title="勉"', sanitized)
        self.assertIn('class="stroke-svg"', sanitized)

    def test_sanitize_html_fragment_strips_disallowed_urls(self):
        malicious_html = '<img src="https://evil.com/exploit.svg" onerror="alert(1)" />'
        sanitized = sanitize_html_fragment(malicious_html)
        self.assertNotIn('evil.com', sanitized)
        self.assertNotIn('onerror', sanitized)

    def test_sanitize_template_preserves_stroke_diagram_placeholder(self):
        template_html = (
            '<div class="card-back">'
            '{{#StrokeDiagram}}'
            '<div class="stroke-container">{{{StrokeDiagram}}}</div>'
            '{{/StrokeDiagram}}'
            '</div>'
        )
        res = prepare_client_template_source(template_html, field_defs=[])
        self.assertIn('{{{StrokeDiagram}}}', res["source"])


if __name__ == "__main__":
    unittest.main()
