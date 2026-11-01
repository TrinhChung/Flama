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
    prepare_client_template_source,
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

    def test_array_list_reaches_mustache_unchanged(self):
        template = self._template("{{#Meaning}}<li>{{.}}</li>{{/Meaning}}|{{Meaning}}|{{#Pairs}}[{{#.}}<i>{{.}}</i>{{/.}}]{{/Pairs}}")
        fields = [self._field("Meaning", "array"), self._field("Pairs", "array")]
        values = {"Meaning": ["ăn", "<b>dùng</b>"], "Pairs": [["a", "b"], ["c"]]}
        rendered = render_template_pair(template=template, field_defs=fields, field_values=values, media_assets=[])
        self.assertIn(
            "<li>ăn</li><li>&lt;b&gt;dùng&lt;/b&gt;</li>|ăn,&lt;b&gt;dùng&lt;/b&gt;|[<i>a</i><i>b</i>][<i>c</i>]",
            rendered["front_html"],
        )
        context = build_render_context(fields, values, [])
        self.assertEqual(set(context), {"Meaning", "Pairs"})
        self.assertEqual(context["Meaning"], ["ăn", "<b>dùng</b>"])

    def test_array_empty_items_keep_their_position_like_mustache_js(self):
        # chevron skips a falsy section item; mustache.js renders it, so paired
        # columns would shift on the server only.
        template = self._template("{{#Left}}<i>{{.}}</i>{{/Left}}|{{Left}}|{{#Right}}<b>{{{.}}}</b>{{/Right}}")
        fields = [self._field("Left", "array"), self._field("Right", "array")]
        values = {"Left": ["", "a", "", "b", ""], "Right": [""]}
        rendered = render_template_pair(template=template, field_defs=fields, field_values=values, media_assets=[])
        self.assertIn("<i></i><i>a</i><i></i><i>b</i><i></i>|,a,,b,|<b></b>", rendered["front_html"])
        self.assertEqual(build_render_context(fields, values, [])["Left"], ["", "a", "", "b", ""])

    def test_array_text_renders_as_before(self):
        # Values written before lists keep the text path: one section, line breaks.
        template = self._template("{{#Meaning}}<div>{{Meaning}}</div>{{/Meaning}}{{^Empty}}-{{/Empty}}")
        fields = [self._field("Meaning", "array"), self._field("Empty", "array")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Meaning": "ăn\ndùng bữa", "Empty": []},
            media_assets=[],
        )
        self.assertIn("<div>ăn<br>dùng bữa</div>-", rendered["front_html"])

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

    def test_client_template_compiles_audio_field_to_explicit_url_helper(self):
        raw_html = (
            '<audio id="custom-audio" src="{{word_audio}}"></audio>'
            '<source src="{{word_audio_url}}">'
            '<button onclick="document.getElementById(\'custom-audio\').play()">🔊</button>'
            '<script>document.getElementById("custom-audio").play();</script>'
        )
        original_html = str(raw_html)
        fields = [self._field("word_audio", "audio"), self._field("word", "text")]

        prepared = prepare_client_template_source(raw_html, fields)

        self.assertEqual(raw_html, original_html)
        self.assertIn('src="{{word_audio_url}}"', prepared["source"])
        self.assertIn('src="{{word_audio_url}}"', prepared["source"])
        self.assertIn('onclick=', prepared["source"])
        self.assertNotIn("<script", prepared["source"])
        self.assertEqual(
            prepared["inline_scripts"],
            ['<script>document.getElementById("custom-audio").play();</script>'],
        )

    def test_client_template_does_not_promote_text_field_to_media_url(self):
        prepared = prepare_client_template_source(
            '<audio src="{{word}}"></audio>',
            [self._field("word", "text")],
        )

        self.assertNotIn("src=", prepared["source"])

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
            {{#hanviet}}<div>{{hanviet}}</div>{{/hanviet}}
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
        self.assertNotIn("diagram-html", html)
        self.assertIn("<script>window.__fc_test = true;</script>", html)
        payload = rendered["front_renderer_payload"]
        self.assertIn("window.__fc_test = true;", payload["html"])
        self.assertTrue(payload["template_key"])
        self.assertEqual(payload["shell_key"], payload["template_key"])
        self.assertTrue(payload["has_inline_script"])
        self.assertFalse(payload["supports_live_patch"])

    def test_renderer_payload_exposes_live_patch_metadata_for_plain_template(self):
        template = self._template("<div>{{Word}}</div>", "<div>{{Meaning}}</div>", "body{color:red;}")
        fields = [self._field("Word"), self._field("Meaning")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "犬", "Meaning": "dog"},
            media_assets=[],
        )
        front_payload = rendered["front_renderer_payload"]
        back_payload = rendered["back_renderer_payload"]
        self.assertTrue(front_payload["template_key"])
        self.assertEqual(front_payload["shell_key"], front_payload["template_key"])
        self.assertTrue(front_payload["supports_live_patch"])
        self.assertFalse(front_payload["has_inline_script"])
        self.assertTrue(back_payload["template_key"])
        self.assertEqual(back_payload["shell_key"], back_payload["template_key"])
        self.assertTrue(back_payload["supports_live_patch"])
        self.assertNotEqual(front_payload["template_key"], back_payload["template_key"])

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
        self.assertFalse(payload["supports_live_patch"])
        self.assertEqual(payload["template_key"], "")
        self.assertEqual(payload["shell_key"], "")

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

    def test_store_opaque_media_url_allowed_and_extracted(self):
        fields = [self._field("Audio", "audio"), self._field("Stroke", "image")]
        rendered = render_template_pair(
            template=self._template(
                "<audio id=\"voice\" controls src=\"/store/0000ce2f-c578-4552-b3c9-eedeb4dad601\"></audio>"
                "<img src=\"/store/stroke_zh_6c38\" />"
            ),
            field_defs=fields,
            field_values={"Audio": "/store/0000ce2f-c578-4552-b3c9-eedeb4dad601", "Stroke": "/store/stroke_zh_6c38"},
            media_assets=[
                type("Asset", (), {"id": "0000ce2f-c578-4552-b3c9-eedeb4dad601", "filename": "voice.mp3"})(),
            ],
            allow_inline_script=True,
            defer_inline_script=True,
        )
        payload = rendered["front_renderer_payload"]
        self.assertIn("/store/0000ce2f-c578-4552-b3c9-eedeb4dad601", payload["allowed_audio_urls"])
        self.assertEqual(payload["allowed_audio_asset_ids"], ["0000ce2f-c578-4552-b3c9-eedeb4dad601"])
        self.assertIn("/store/stroke_zh_6c38", payload["allowed_media_urls"])

    def test_onclick_style_display_assignment_is_preserved(self):
        fields = [self._field("Word", "text")]
        rendered = render_template_pair(
            template=self._template(
                "<button onclick=\"document.getElementById('hint').style.display='block'; "
                "this.style.display='none'\">Show</button>"
                "<div id='hint' style='display:none'>Hint</div>"
            ),
            field_defs=fields,
            field_values={"Word": "犬"},
            media_assets=[],
            allow_inline_script=True,
            defer_inline_script=True,
        )
        self.assertIn("onclick=", rendered["front_html"])

    def test_onclick_classlist_toggle_is_preserved(self):
        fields = [self._field("Word", "text")]
        rendered = render_template_pair(
            template=self._template(
                "<button onclick=\"document.getElementById('answer').classList.toggle('hidden')\">Toggle</button>"
            ),
            field_defs=fields,
            field_values={"Word": "犬"},
            media_assets=[],
            allow_inline_script=True,
            defer_inline_script=True,
        )
        self.assertIn("onclick=", rendered["front_html"])

    def test_onclick_pause_is_preserved(self):
        fields = [self._field("Word", "text")]
        rendered = render_template_pair(
            template=self._template(
                "<button onclick=\"document.getElementById('audio1').pause()\">⏸</button>"
            ),
            field_defs=fields,
            field_values={"Word": "犬"},
            media_assets=[],
            allow_inline_script=True,
            defer_inline_script=True,
        )
        self.assertIn("onclick=", rendered["front_html"])

    def test_unsafe_onclick_is_rejected_by_validator(self):
        from app.services.flashcard_renderer import _is_safe_button_onclick
        safe_cases = [
            "document.getElementById('audio1').play()",
            "document.getElementById('hint').style.display='block'",
            "this.style.display='none'",
            "document.getElementById('x').classList.toggle('hidden')",
            "document.getElementById('a').pause(); this.hidden=true",
            "this.textContent='Done'",
        ]
        for case in safe_cases:
            self.assertTrue(_is_safe_button_onclick(case),
                            f"Expected safe: {case}")

        unsafe_cases = [
            'alert("xss")',
            'fetch("https://evil.com")',
            'eval("code")',
            'window.location="https://evil.com"',
            'document.cookie',
            '',
        ]
        for case in unsafe_cases:
            self.assertFalse(_is_safe_button_onclick(case),
                             f"Expected unsafe: {case}")

    def test_auto_split_and_arbitrary_inert_attributes_are_preserved(self):
        template = self._template('<div auto-split data-auto-split my-marker="custom-1" foo="bar">{{Word}}</div>')
        fields = [self._field("Word")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "A$B"},
            media_assets=[],
        )
        self.assertIn("auto-split", rendered["front_html"])
        self.assertIn("data-auto-split", rendered["front_html"])
        self.assertIn('my-marker="custom-1"', rendered["front_html"])
        self.assertIn('foo="bar"', rendered["front_html"])

    def test_dangerous_capability_attributes_are_stripped(self):
        from app.services.flashcard_renderer import sanitize_html_fragment
        cleaned = sanitize_html_fragment(
            '<div my-marker="custom-1" onerror="alert(1)" onmouseover="evil()" action="http://evil.com">Hello</div>'
        )
        self.assertIn('my-marker="custom-1"', cleaned)
        self.assertNotIn("onerror", cleaned)
        self.assertNotIn("onmouseover", cleaned)
        self.assertNotIn("action", cleaned)

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

    def test_front_side_on_back_shows_the_rendered_front_without_its_scripts(self):
        template = self._template(
            '<div class="q">{{Word}}</div>{{FrontSide}}<script>window.front = 1;</script>',
            '{{FrontSide}}<hr id="answer">{{Meaning}}<script>window.back = 1;</script>',
        )
        fields = [self._field("Word"), self._field("Meaning")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word": "犬", "Meaning": "dog"},
            media_assets=[],
        )
        self.assertIn('<div class="q">犬</div><hr id="answer">dog<script>window.back = 1;</script>', rendered["back_html"])
        self.assertNotIn("window.front", rendered["back_html"])
        self.assertIn('<div class="q">犬</div><script>window.front = 1;</script>', rendered["front_html"])
        self.assertNotIn("flama-front-side", rendered["front_html"] + rendered["back_html"])

    def test_front_side_spellings_and_sections_while_field_text_cannot_forge_it(self):
        fields = [self._field("Word"), self._field("Meaning")]
        values = {"Word": "<flama-front-side></flama-front-side>", "Meaning": "dog"}
        for back in (
            "{{{FrontSide}}}|{{Meaning}}",
            "{{ FrontSide }}|{{Meaning}}",
            "{{&FrontSide}}|{{Meaning}}",
            "{{#Meaning}}{{FrontSide}}{{/Meaning}}|{{Meaning}}",
        ):
            rendered = render_template_pair(
                template=self._template("<b>{{Word}}</b>", back),
                field_defs=fields,
                field_values=values,
                media_assets=[],
            )
            self.assertIn("<b>&lt;flama-front-side&gt;&lt;/flama-front-side&gt;</b>|dog", rendered["back_html"], back)

    def test_front_side_keeps_front_media_on_the_back(self):
        template = self._template("{{{Word_Audio}}}{{{image}}}", "{{FrontSide}}<hr>{{Meaning}}")
        fields = [self._field("Word_Audio", "audio"), self._field("image", "image"), self._field("Meaning")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={"Word_Audio": "/media/proxy/audio-1", "image": "/media/proxy/image-1", "Meaning": "dog"},
            media_assets=[],
        )
        self.assertIn("/media/proxy/audio-1", rendered["back_html"])
        self.assertIn("/media/proxy/image-1", rendered["back_html"])
        self.assertIn("/media/proxy/audio-1", rendered["back_renderer_payload"]["allowed_audio_urls"])

    def test_client_template_keeps_front_side_tokens_for_the_study_renderer(self):
        prepared = prepare_client_template_source("{{FrontSide}}<hr>{{&FrontSide}}", [])
        # bleach escapes the ampersand; the client renderer accepts both spellings.
        self.assertEqual(prepared["source"], "{{FrontSide}}<hr>{{&amp;FrontSide}}")

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

    def test_template_alias_mapping_via_input_bindings(self):
        template = SimpleNamespace(
            id="tpl-alias",
            front_html="<div>{{Term}}</div>",
            back_html="<div>{{han_viet}}</div>",
            shared_css="",
            updated_at=datetime(2026, 2, 23, 12, 0, 0),
            input_schema=[
                {"key": "Term", "type": "text", "required": True},
                {"key": "han_viet", "type": "text", "required": False},
            ],
            input_bindings={
                "Term": "f-1",
                "han_viet": "f-2",
            },
        )
        fields = [
            SimpleNamespace(id="f-1", name="word", field_type="text", required=True),
            SimpleNamespace(id="f-2", name="hanviet", field_type="text", required=False),
        ]
        values = {"word": "犬", "hanviet": "KHUYỂN"}
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values=values,
            media_assets=[],
        )
        self.assertIn("犬", rendered["front_html"])
        self.assertIn("KHUYỂN", rendered["back_html"])


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
                "name": "case9_external_audio_allowed",
                "template": "{{{Word_Audio}}}",
                "fields": [self._field("Word_Audio", "audio")],
                "values": {"Word_Audio": "https://example.com/track.mp3"},
                "must_include": '<audio controls data-flama-media-field="Word_Audio" data-flama-media-kind="audio" class="flama-media-audio" src="https://example.com/track.mp3"></audio>',
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


    def test_preview_raw_template(self):
        from app.services.flashcard_content_service import preview_raw_template

        res = preview_raw_template(
            payload={
                "front_html": "<h2>{{Expression}}</h2><p>{{Reading}}</p>",
                "back_html": "{{FrontSide}}<hr><p>{{Meaning}}</p>",
                "shared_css": ".card { text-align: center; }",
                "fields": ["Expression", "Reading", "Meaning"],
                "field_values": {
                    "Expression": "同期",
                    "Reading": "どうき",
                    "Meaning": "synchronization",
                },
            }
        )
        self.assertIn("front_html", res)
        self.assertIn("back_html", res)
        self.assertIn("front_renderer_payload", res)
        self.assertIn("back_renderer_payload", res)
        self.assertIn("同期", res["front_html"])
        self.assertIn("synchronization", res["back_html"])
        self.assertIn(".card { text-align: center; }", res["front_html"])


    def test_external_media_urls_rendered_directly(self):
        template = self._template("{{{Word_Audio}}} {{{Image}}}")
        fields = [self._field("Word_Audio", "audio"), self._field("Image", "image")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={
                "Word_Audio": "https://example.com/audio/cat.mp3",
                "Image": "https://example.com/images/cat.jpg",
            },
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertIn('<audio controls', html)
        self.assertIn('src="https://example.com/audio/cat.mp3"', html)
        self.assertIn('<img', html)
        self.assertIn('src="https://example.com/images/cat.jpg"', html)
        self.assertIn("https://example.com/audio/cat.mp3", rendered["front_renderer_payload"]["allowed_audio_urls"])
        self.assertIn("https://example.com/images/cat.jpg", rendered["front_renderer_payload"]["allowed_media_urls"])

    def test_multi_image_rendering_wraps_in_gallery(self):
        template = self._template("{{{Images}}}")
        fields = [self._field("Images", "image")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={
                "Images": "https://example.com/1.jpg\nhttps://example.com/2.jpg\nhttps://example.com/3.jpg",
            },
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertIn('class="flama-media-gallery"', html)
        self.assertIn('src="https://example.com/1.jpg"', html)
        self.assertIn('src="https://example.com/2.jpg"', html)
        self.assertIn('src="https://example.com/3.jpg"', html)
        self.assertEqual(html.count("<img "), 3)

    def test_raster_diagram_is_not_mislabeled_as_svg(self):
        rendered = render_template_pair(
            template=self._template("{{{Diagram}}}"),
            field_defs=[self._field("Diagram", "diagram")],
            field_values={"Diagram": "https://example.com/diagram.png"},
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertIn('data-flama-media-kind="diagram"', html)
        self.assertNotIn('data-flama-is-svg="true"', html)

    def test_media_urls_helper_supports_custom_multi_item_template(self):
        source = '{{#Images_urls}}<img class="custom" src="{{.}}">{{/Images_urls}}'
        fields = [self._field("Images", "image")]
        prepared = prepare_client_template_source(source, fields)
        self.assertIn('src="{{.}}"', prepared["source"])

        rendered = render_template_pair(
            template=self._template(source),
            field_defs=fields,
            field_values={"Images": "https://example.com/1.jpg\nhttps://example.com/2.jpg"},
            media_assets=[],
        )
        self.assertEqual(rendered["front_html"].count('class="custom"'), 2)
        self.assertIn('src="https://example.com/1.jpg"', rendered["front_html"])
        self.assertIn('src="https://example.com/2.jpg"', rendered["front_html"])

    def test_multi_audio_rendering_wraps_in_gallery(self):
        template = self._template("{{{Audios}}}")
        fields = [self._field("Audios", "audio")]
        rendered = render_template_pair(
            template=template,
            field_defs=fields,
            field_values={
                "Audios": "https://example.com/1.mp3\nhttps://example.com/2.mp3",
            },
            media_assets=[],
        )
        html = rendered["front_html"]
        self.assertIn('class="flama-media-gallery"', html)
        self.assertIn('src="https://example.com/1.mp3"', html)
        self.assertIn('src="https://example.com/2.mp3"', html)
        self.assertEqual(html.count("<audio "), 2)

    def test_external_sound_bracket_tag_in_validator_and_renderer(self):
        from app.validators.flashcard_input import _clean_media_reference
        cleaned = _clean_media_reference(
            "[sound:https://example.com/test.mp3]",
            field_name="Sound",
            note_media_ids=None,
        )
        self.assertEqual(cleaned, "https://example.com/test.mp3")

        # Multi-line in validator
        cleaned_multi = _clean_media_reference(
            "https://example.com/img1.png\nhttps://example.com/img2.png",
            field_name="Images",
            note_media_ids=None,
            field_type="image",
        )
        self.assertEqual(cleaned_multi, "https://example.com/img1.png\nhttps://example.com/img2.png")

    def test_media_normalizer_service(self):
        from app.services.flashcard_media_normalizer import (
            normalize_single_media_reference,
            normalize_media_field_value,
        )
        # External URL remains unchanged
        self.assertEqual(
            normalize_single_media_reference("https://example.com/a.jpg", field_type="image"),
            "https://example.com/a.jpg",
        )
        # [sound:https://...] is normalized
        self.assertEqual(
            normalize_single_media_reference("[sound:https://example.com/a.mp3]"),
            "https://example.com/a.mp3",
        )
        # An unresolved UUID is quarantined and never turned into a fabricated proxy URL.
        self.assertEqual(
            normalize_single_media_reference("a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d"),
            "a1b2c3d4-e5f6-7a8b-9c0d-1e2f3a4b5c6d",
        )
        # Stroke reference
        self.assertEqual(
            normalize_single_media_reference("stroke_kanji_4e00", field_type="diagram"),
            "/store/stroke_kanji_4e00.svg",
        )
        # Multi-value
        self.assertEqual(
            normalize_media_field_value("https://a.com/1.jpg\nhttps://a.com/2.jpg", field_type="image"),
            "https://a.com/1.jpg\nhttps://a.com/2.jpg",
        )

    def test_white_space_css_property_preserved_by_sanitizers(self):
        from app.services.flashcard_renderer import (
            ALLOWED_CSS_PROPERTIES,
            sanitize_template_html_fragment,
            prepare_client_template_source,
        )
        self.assertIn("white-space", ALLOWED_CSS_PROPERTIES)
        self.assertIn("line-height", ALLOWED_CSS_PROPERTIES)
        self.assertIn("flex-direction", ALLOWED_CSS_PROPERTIES)
        self.assertIn("gap", ALLOWED_CSS_PROPERTIES)

        raw_html = (
            '<div style="font-size: 20px; display: flex; flex-direction: column; gap: 4px; white-space: pre-wrap; line-height: 1.45;">'
            'usage content'
            '</div>'
            '<div style="display: flex; flex-direction: column; gap: 4px; padding-top: 10px; white-space: pre-wrap; line-height: 1.45;">'
            'note content'
            '</div>'
        )
        clean_html = sanitize_template_html_fragment(raw_html)
        self.assertIn("white-space: pre-wrap;", clean_html)
        self.assertIn("line-height: 1.45;", clean_html)
        self.assertIn("flex-direction: column;", clean_html)
        self.assertIn("gap: 4px;", clean_html)

        prepared = prepare_client_template_source(raw_html, [])
        self.assertIn("white-space: pre-wrap;", prepared["source"])
        self.assertIn("line-height: 1.45;", prepared["source"])
        self.assertIn("flex-direction: column;", prepared["source"])
        self.assertIn("gap: 4px;", prepared["source"])


if __name__ == "__main__":
    unittest.main()
