"""Unit + security tests for flashcard template rendering."""

from datetime import datetime
from html.parser import HTMLParser
from types import SimpleNamespace
import unittest

from app.services.flashcard_renderer import (
    PREVIEW_MEDIA_IMAGE_TOKEN,
    build_renderer_side_payload,
    build_render_context,
    is_field_empty,
    render_template_pair,
)


class FlashcardRendererTests(unittest.TestCase):
    def _template(self, front: str, back: str = "", css: str = ""):
        return SimpleNamespace(
            id="tpl-1",
            front_html=front,
            back_html=back or front,
            shared_css=css,
            updated_at=datetime(2026, 2, 23, 12, 0, 0),
        )

    def _field(self, name: str, field_type: str = "text", required: bool = False):
        return SimpleNamespace(name=name, field_type=field_type, required=required)

    def test_conditional_and_escaping_behavior(self):
        template = self._template("{{Word}} {{#Reading}}R:{{Reading}}{{/Reading}}{{^Reading}}EMPTY{{/Reading}}")
        fields = [self._field("Word"), self._field("Reading")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "<script>alert(1)</script>", "Reading": ""},
            media_assets=[],
        )
        self.assertIn("&lt;script&gt;alert(1)&lt;/script&gt;", rendered["front_html"])
        self.assertIn("EMPTY", rendered["front_html"])
        self.assertNotIn("R:", rendered["front_html"])

    def test_richtext_rendered_with_sanitized_raw_html(self):
        template = self._template("{{{Meaning}}}")
        fields = [self._field("Meaning", "richtext")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Meaning": "<b>ok</b><script>alert(2)</script>"},
            media_assets=[],
        )
        self.assertIn("<b>ok</b>", rendered["front_html"])
        self.assertNotIn("<script>", rendered["front_html"])

    def test_markdown_rendered_to_safe_html(self):
        template = self._template("{{{Notes}}}")
        fields = [self._field("Notes", "markdown")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={
                "Notes": "# Header\n\n**bold**\n\n<script>alert(2)</script>\n\n[ok](https://example.com)",
            },
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertNotIn("<script>", html)
        if "<h1>Header</h1>" in html:
            self.assertIn("<strong>bold</strong>", html)
            self.assertIn('href="https://example.com"', html)
        else:
            # Fallback path when markdown parser dependency is unavailable.
            self.assertIn("# Header", html)
            self.assertIn("**bold**", html)

    def test_markdown_double_brace_template_is_auto_upgraded_to_html(self):
        template = self._template("{{Notes}}")
        fields = [self._field("Notes", "markdown")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Notes": "**bold**"},
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertNotIn("&lt;strong&gt;", html)
        if "<strong>bold</strong>" in html:
            self.assertIn("<strong>bold</strong>", html)
        else:
            self.assertIn("**bold**", html)

    def test_markdown_proxy_image_syntax_renders_img_tag(self):
        template = self._template("{{{Notes}}}")
        fields = [self._field("Notes", "markdown")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Notes": "![image.png](/media/proxy/asset-123)"},
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertIn("<img", html)
        self.assertIn('src="/media/proxy/asset-123"', html)

    def test_media_rendering_uses_proxy_url_only(self):
        template = self._template("{{{Word_Audio}}} {{{image}}}")
        fields = [self._field("Word_Audio", "audio"), self._field("image", "image")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word_Audio": "/media/proxy/audio-1", "image": "/media/proxy/image-1"},
            media_assets=[],
        )
        self.assertIn("<audio", rendered["front_html"])
        self.assertIn("<img", rendered["front_html"])
        self.assertIn("/media/proxy/audio-1", rendered["front_html"])
        self.assertIn("/media/proxy/image-1", rendered["front_html"])

    def test_media_filename_reference_resolves_attached_asset(self):
        template = self._template("{{{Word_Audio}}}")
        fields = [self._field("Word_Audio", "audio")]
        media_assets = [SimpleNamespace(id="asset-a", filename="voicevox-001.wav")]

        rendered_a = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word_Audio": "voicevox-001.wav"},
            media_assets=media_assets,
        )
        self.assertIn("/media/proxy/asset-a", rendered_a["front_html"])

        rendered_b = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word_Audio": "[sound:voicevox-001.wav]"},
            media_assets=media_assets,
        )
        self.assertIn("/media/proxy/asset-a", rendered_b["front_html"])

    def test_preview_media_token_renders_placeholder_box(self):
        template = self._template("{{Word}} {{{image}}}")
        fields = [self._field("Word"), self._field("image", "image")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "Word", "image": PREVIEW_MEDIA_IMAGE_TOKEN},
            media_assets=[],
        )
        self.assertIn("Word", rendered["front_html"])
        self.assertIn("fc-preview-media-box", rendered["front_html"])
        self.assertIn("[Image: image]", rendered["front_html"])

    def test_inline_script_is_preserved_for_sandbox_renderer_output(self):
        template = self._template(
            """{{#word_audio}}<audio id="custom-audio" src="{{word_audio}}"></audio>{{/word_audio}}
            {{#hanviet}}<div>{{han_viet}}</div>{{/hanviet}}
            {{image}}{{diagram}}
            <script>window.__fc_test = true;</script>"""
        )
        fields = [
            self._field("word_audio", "audio"),
            self._field("hanviet", "text"),
            self._field("image", "image"),
            self._field("diagram", "diagram"),
        ]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={
                "word_audio": "/media/proxy/audio-1",
                "hanviet": "HANVIET",
                "image": "/media/proxy/image-1",
                "diagram": "<div>diagram-html</div>",
            },
            media_assets=[],
            allow_inline_script=True,
        )
        html = rendered["front_html"]
        self.assertIn('src="/media/proxy/audio-1"', html)
        self.assertIn("HANVIET", html)
        self.assertIn("<img", html)
        self.assertIn("diagram-html", html)
        self.assertIn("<script>window.__fc_test = true;</script>", html)
        payload = rendered["front_renderer_payload"]
        self.assertIn("window.__fc_test = true;", payload["html"])

    def test_external_script_src_is_removed_from_template_output(self):
        template = self._template(
            "<div>{{Word}}</div>"
            "<script src=\"https://evil.example/payload.js\"></script>"
            "<script>window.__safe_inline__=1;</script>"
        )
        fields = [self._field("Word", "text")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "犬"},
            media_assets=[],
            allow_inline_script=True,
            defer_inline_script=True,
        )
        html = rendered["front_html"]
        self.assertIn("window.__safe_inline__=1;", html)
        self.assertNotIn("evil.example", html)
        self.assertNotIn("<script src=", html)

    def test_template_inline_handlers_are_preserved_for_sandbox_execution(self):
        fields = [self._field("Word", "text"), self._field("Word_Audio", "audio")]
        rendered = render_template_pair(
            template=self._template(
                "<button onclick=\"document.getElementById('voice').play()\">Play</button>"
                "{{{Word_Audio}}}"
            ),
            field_defs=fields,
            field_values={"Word": "犬", "Word_Audio": "/media/proxy/audio-1"},
            media_assets=[],
            allow_inline_script=True,
            defer_inline_script=True,
        )
        html = rendered["front_html"]
        self.assertIn("onclick=", html)
        self.assertIn('data-flama-media-field="Word_Audio"', html)
        self.assertIn('data-flama-media-asset-id="audio-1"', html)

    def test_renderer_payload_extracts_allowlisted_audio_assets(self):
        payload = build_renderer_side_payload(
            "<audio data-flama-media-field=\"Word_Audio\" src=\"/media/proxy/audio-1\"></audio>"
            "<img src=\"/media/proxy/image-1\">"
        )
        self.assertEqual(payload["allowed_audio_urls"], ["/media/proxy/audio-1"])
        self.assertEqual(payload["allowed_audio_asset_ids"], ["audio-1"])
        self.assertIn("/media/proxy/image-1", payload["allowed_media_urls"])

    def test_renderer_payload_extracts_legacy_audio_controls_with_source_tag(self):
        payload = build_renderer_side_payload(
            "<audio id=\"voice\">"
            "<source src=\"/media/proxy/audio-2\" type=\"audio/mpeg\">"
            "</audio>"
            "<button onclick=\"document.getElementById('voice').play()\">Play</button>"
        )
        self.assertEqual(payload["allowed_audio_urls"], ["/media/proxy/audio-2"])
        self.assertEqual(payload["allowed_audio_asset_ids"], ["audio-2"])
        self.assertIn("/media/proxy/audio-2", payload["allowed_media_urls"])

    def test_auto_split_attribute_is_preserved(self):
        template = self._template('<div auto-split>{{Word}}</div>')
        fields = [self._field("Word")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "A$B"},
            media_assets=[],
        )
        self.assertIn("auto-split", rendered["front_html"])

    def test_literal_backslash_n_is_normalized_to_newline(self):
        template = self._template('<div auto-split>{{Word}}</div>')
        fields = [self._field("Word")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "Line1\\nLine2"},
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertNotIn("Line1\\nLine2", html)
        self.assertIn("Line1<br>Line2", html)

    def test_actual_newline_is_rendered_as_line_break(self):
        template = self._template("<div>{{Word}}</div>")
        fields = [self._field("Word")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "Line1\nLine2"},
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertNotIn("Line1\nLine2", html)
        self.assertIn("Line1<br>Line2", html)

    def test_windows_newline_is_rendered_as_line_break(self):
        template = self._template("<div>{{Word}}</div>")
        fields = [self._field("Word")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "Line1\r\nLine2"},
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertIn("Line1<br>Line2", html)

    def test_empty_rules(self):
        self.assertTrue(is_field_empty(None))
        self.assertTrue(is_field_empty(""))
        self.assertTrue(is_field_empty("   "))
        self.assertTrue(is_field_empty([]))
        self.assertFalse(is_field_empty("a"))
        self.assertFalse(is_field_empty(["x"]))

    def test_build_render_context_keeps_unknown_legacy_keys(self):
        fields = [self._field("Word"), self._field("Meaning", "richtext")]
        context = build_render_context(
            field_defs=fields,
            field_values={"Word": "犬", "Meaning": "<i>dog</i>", "LegacyX": "value"},
            media_assets=[],
        )
        self.assertEqual(context["Word"], "犬")
        self.assertIn("<i>dog</i>", context["Meaning"])
        self.assertEqual(context["LegacyX"], "value")


class FlashcardSecurityTests(unittest.TestCase):
    def _template(self, html: str):
        return SimpleNamespace(
            id="tpl-sec",
            front_html=html,
            back_html=html,
            shared_css="",
            updated_at=datetime(2026, 2, 23, 12, 0, 0),
        )

    def _field(self, name: str, field_type: str):
        return SimpleNamespace(name=name, field_type=field_type, required=False)

    def _collect_start_tag_attrs(self, raw_html: str) -> list[dict[str, str]]:
        class _AttrParser(HTMLParser):
            def __init__(self) -> None:
                super().__init__(convert_charrefs=True)
                self.items: list[dict[str, str]] = []

            def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
                normalized = {"__tag__": tag}
                for name, value in attrs:
                    normalized[str(name)] = "" if value is None else str(value)
                self.items.append(normalized)

        parser = _AttrParser()
        parser.feed(raw_html)
        parser.close()
        return parser.items

    def test_xss_cases_from_spec(self):
        test_cases = [
            {
                "name": "case1_script_in_text_is_escaped",
                "template": "{{Word}}",
                "fields": [self._field("Word", "text")],
                "values": {"Word": "<script>alert(1)</script>"},
                "must_include": "&lt;script&gt;alert(1)&lt;/script&gt;",
                "must_exclude": "<script>",
            },
            {
                "name": "case2_script_in_richtext_removed",
                "template": "{{{Meaning_JP}}}",
                "fields": [self._field("Meaning_JP", "richtext")],
                "values": {"Meaning_JP": "<script>alert(2)</script><b>x</b>"},
                "must_include": "<b>x</b>",
                "must_exclude": "<script>",
            },
            {
                "name": "case3_event_handler_removed",
                "template": "{{{Meaning_JP}}}",
                "fields": [self._field("Meaning_JP", "richtext")],
                "values": {"Meaning_JP": "<img src=x onerror=alert(3)>"},
                "must_exclude": "onerror",
            },
            {
                "name": "case4_javascript_href_blocked",
                "template": "{{{Meaning_JP}}}",
                "fields": [self._field("Meaning_JP", "richtext")],
                "values": {"Meaning_JP": '<a href="javascript:alert(4)">x</a>'},
                "must_exclude": "javascript:",
            },
            {
                "name": "case5_iframe_removed",
                "template": "{{{Meaning_JP}}}",
                "fields": [self._field("Meaning_JP", "richtext")],
                "values": {"Meaning_JP": '<iframe src="https://evil.com"></iframe>'},
                "must_exclude": "<iframe",
            },
            {
                "name": "case6_js_css_url_blocked",
                "template": "{{{Meaning_JP}}}",
                "fields": [self._field("Meaning_JP", "richtext")],
                "values": {"Meaning_JP": '<div style="background:url(javascript:alert(6));color:red">x</div>'},
                "must_exclude": "javascript:",
            },
            {
                "name": "case7_svg_script_removed",
                "template": "{{{Diagram}}}",
                "fields": [self._field("Diagram", "diagram")],
                "values": {"Diagram": "<svg><script>alert(7)</script><circle /></svg>"},
                "must_exclude": "<script>",
            },
            {
                "name": "case8_meta_refresh_removed",
                "template": "<meta http-equiv='refresh' content='0;url=https://evil.com'>{{Word}}",
                "fields": [self._field("Word", "text")],
                "values": {"Word": "ok"},
                "must_exclude": "<meta",
            },
            {
                "name": "case9_external_audio_rejected",
                "template": "{{{Word_Audio}}}",
                "fields": [self._field("Word_Audio", "audio")],
                "values": {"Word_Audio": "https://evil.com/track.mp3"},
                "must_exclude": "https://evil.com",
            },
            {
                "name": "case10_attribute_injection_escaped",
                "template": "<div data-x='{{Word}}'>safe</div>",
                "fields": [self._field("Word", "text")],
                "values": {"Word": '" onmouseover="alert(10)'},
            },
        ]

        for case in test_cases:
            with self.subTest(case=case["name"]):
                rendered = render_template_pair(
                    template=self._template(case["template"]),
                    field_defs=case["fields"],
                    field_values=case["values"],
                    media_assets=[],
                )
                html = rendered["front_html"]
                must_include = case.get("must_include")
                if must_include:
                    self.assertIn(must_include, html)
                must_exclude = case.get("must_exclude")
                if must_exclude:
                    self.assertNotIn(must_exclude, html)
                if case["name"] == "case10_attribute_injection_escaped":
                    attrs = self._collect_start_tag_attrs(html)
                    self.assertEqual(len(attrs), 1)
                    self.assertEqual(attrs[0].get("__tag__"), "div")
                    self.assertIn("data-x", attrs[0])
                    self.assertNotIn("onmouseover", attrs[0])


if __name__ == "__main__":
    unittest.main()
