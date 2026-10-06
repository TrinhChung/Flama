"""Unit tests for app.services.template_tokens.

Verifies Mustache token parsing, rewriting, base variable resolution,
and template content hashing according to GT-08 specification.
"""

import unittest
from app.services.template_tokens import (
    TemplateTokenError,
    base_variable_name,
    extract_variable_names,
    rewrite_variable_names,
    template_content_hash,
)


class TestExtractVariableNames(unittest.TestCase):
    def test_table_cases(self) -> None:
        table = [
            ("<div>{{Word}}</div>", ["Word"]),
            ("{{ Word }} {{Word}}", ["Word"]),
            ("{{{Meaning}}}", ["Meaning"]),
            ("{{& Meaning}}", ["Meaning"]),
            ("{{#Audio}}<b>{{Audio}}</b>{{/Audio}}{{^Audio}}none{{/Audio}}", ["Audio"]),
            ("{{! comment {{Hidden}} }}x{{Word}}", ["Word"]),
            ("{{> partial}}{{Word}}", ["Word"]),
            ("{{#list}}{{.}}{{/list}}", ["list"]),
            ("{{Meaning VN}}", ["Meaning VN"]),
            ("{{a.b}}{{a}}", ["a.b", "a"]),
            ('<img src="{{Image_url}}">{{#Image_urls}}{{.}}{{/Image_urls}}', ["Image_url", "Image_urls"]),
            ("{{漢字}}<hr>{{Nghĩa}}", ["漢字", "Nghĩa"]),
            ("<script>var w='{{Word}}';</script>", ["Word"]),
            ("", []),
            (None, []),
            ("{{}} {{ }}", []),
            ("{{!multi\nline}}{{B}}{{A}}", ["B", "A"]),
        ]
        for source, expected in table:
            with self.subTest(source=source):
                self.assertEqual(extract_variable_names(source), expected)

    def test_delimiter_change_raises_error(self) -> None:
        with self.assertRaises(TemplateTokenError) as ctx:
            extract_variable_names("{{=<% %>=}}")
        self.assertEqual(ctx.exception.code, "DELIMITER_CHANGE_UNSUPPORTED")


class TestRewriteVariableNames(unittest.TestCase):
    def test_table_cases(self) -> None:
        table = [
            ("<div>{{Word}}</div>", {"Word": "Kanji"}, "<div>{{Kanji}}</div>"),
            ("{{ Word }}|{{{ Word }}}|{{& Word}}", {"Word": "Kanji"}, "{{ Kanji }}|{{{ Kanji }}}|{{& Kanji}}"),
            ("{{# Audio }}x{{/ Audio}}{{^Audio}}y{{/Audio}}", {"Audio": "Sound"}, "{{# Sound }}x{{/ Sound}}{{^Sound}}y{{/Sound}}"),
            ("{{Image_url}} {{#Image_urls}}{{.}}{{/Image_urls}}", {"Image": "Pic"}, "{{Pic_url}} {{#Pic_urls}}{{.}}{{/Pic_urls}}"),
            ("{{Image_url}}", {"Image": "Pic", "Image_url": "Other"}, "{{Other}}"),
            ("{{! Word }}{{> Word}}{{Word}}", {"Word": "K"}, "{{! Word }}{{> Word}}{{K}}"),
            ("{{a.b}}{{a}}", {"a": "x"}, "{{a.b}}{{x}}"),
            ("{{Words}}{{Word}}", {"Word": "K"}, "{{Words}}{{K}}"),
            ("{{Meaning}}", {"Word": "K"}, "{{Meaning}}"),
            ("<script>var w='{{Word}}';</script>", {"Word": "語"}, "<script>var w='{{語}}';</script>"),
            ("{{prompt}}<hr>{{answer}}", {"prompt": "Kanji", "answer": "Meaning VN"}, "{{Kanji}}<hr>{{Meaning VN}}"),
            ("{{A}}{{B}}", {"A": "B", "B": "A"}, "{{B}}{{A}}"),
        ]
        for source, mapping, expected in table:
            with self.subTest(source=source, mapping=mapping):
                self.assertEqual(rewrite_variable_names(source, mapping), expected)

    def test_round_trip_for_all_valid_extract_sources(self) -> None:
        valid_sources = [
            "<div>{{Word}}</div>",
            "{{ Word }} {{Word}}",
            "{{{Meaning}}}",
            "{{& Meaning}}",
            "{{#Audio}}<b>{{Audio}}</b>{{/Audio}}{{^Audio}}none{{/Audio}}",
            "{{! comment {{Hidden}} }}x{{Word}}",
            "{{> partial}}{{Word}}",
            "{{#list}}{{.}}{{/list}}",
            "{{Meaning VN}}",
            "{{a.b}}{{a}}",
            '<img src="{{Image_url}}">{{#Image_urls}}{{.}}{{/Image_urls}}',
            "{{漢字}}<hr>{{Nghĩa}}",
            "<script>var w='{{Word}}';</script>",
            "",
            None,
            "{{}} {{ }}",
            "{{!multi\nline}}{{B}}{{A}}",
        ]
        for s in valid_sources:
            with self.subTest(source=s):
                names = extract_variable_names(s)
                identity_mapping = {n: n for n in names}
                expected = "" if s is None else s
                self.assertEqual(rewrite_variable_names(s, identity_mapping), expected)

    def test_invalid_mappings_raise_value_error(self) -> None:
        invalid_mappings = [
            {"Word": ""},
            {"Word": "a}b"},
            {"Word": " K"},
            {"Word": "{x"},
            {"Word": "K "},
            {"Word": "   "},
            {"Word": None},
            {"Word": 123},
            {"Word": False},
        ]
        for mapping in invalid_mappings:
            with self.subTest(mapping=mapping):
                with self.assertRaises(ValueError):
                    rewrite_variable_names("{{Word}}", mapping)

    def test_none_source(self) -> None:
        self.assertEqual(rewrite_variable_names(None, {}), "")
        self.assertEqual(rewrite_variable_names(None, {"Word": "Kanji"}), "")

    def test_delimiter_change_in_rewrite_raises_error(self) -> None:
        with self.assertRaises(TemplateTokenError) as ctx:
            rewrite_variable_names("{{=<% %>=}}", {})
        self.assertEqual(ctx.exception.code, "DELIMITER_CHANGE_UNSUPPORTED")


class TestBaseVariableName(unittest.TestCase):
    def test_table_cases(self) -> None:
        table = [
            ("Image_url", {"Image"}, "Image"),
            ("Image_urls", {"Image"}, "Image"),
            ("Image_url", {"Image", "Image_url"}, "Image_url"),
            ("Foo_url", {"Image"}, "Foo_url"),
            ("Word", {"Word"}, "Word"),
        ]
        for name, known, expected in table:
            with self.subTest(name=name, known=known):
                self.assertEqual(base_variable_name(name, known), expected)


class TestTemplateContentHash(unittest.TestCase):
    def test_golden_value(self) -> None:
        golden = "7848287f04a3dc0ce90078c66bc73ee7f1e184d47f03e922a595baa6e1f7f698"
        actual = template_content_hash("{{Word}}", "{{Word}}<hr>{{Meaning}}", "")
        self.assertEqual(actual, golden)

    def test_none_matches_empty_string(self) -> None:
        self.assertEqual(
            template_content_hash(None, None, None),
            template_content_hash("", "", ""),
        )

    def test_single_char_diff_changes_hash(self) -> None:
        base = template_content_hash("{{Word}}", "{{Meaning}}", ".card{}")
        diff_front = template_content_hash("{{Word }}", "{{Meaning}}", ".card{}")
        diff_back = template_content_hash("{{Word}}", "{{Meaning }}", ".card{}")
        diff_css = template_content_hash("{{Word}}", "{{Meaning}}", ".card{ }")
        self.assertNotEqual(base, diff_front)
        self.assertNotEqual(base, diff_back)
        self.assertNotEqual(base, diff_css)

    def test_swapped_front_back_changes_hash(self) -> None:
        h1 = template_content_hash("A", "B", "")
        h2 = template_content_hash("B", "A", "")
        self.assertNotEqual(h1, h2)

    def test_digest_length_and_hex_chars(self) -> None:
        h = template_content_hash("front", "back", "css")
        self.assertEqual(len(h), 64)
        self.assertTrue(all(c in "0123456789abcdef" for c in h))


class TestAdversarialEdgeCases(unittest.TestCase):
    def test_real_world_legacy_template_round_trip(self) -> None:
        from app.services.flashcard_legacy import LEGACY_FRONT_TEMPLATE, LEGACY_BACK_TEMPLATE

        front_vars = extract_variable_names(LEGACY_FRONT_TEMPLATE)
        self.assertIn("word", front_vars)
        self.assertEqual(
            rewrite_variable_names(LEGACY_FRONT_TEMPLATE, {v: v for v in front_vars}),
            LEGACY_FRONT_TEMPLATE,
        )

        back_vars = extract_variable_names(LEGACY_BACK_TEMPLATE)
        self.assertIn("word", back_vars)
        self.assertIn("word_audio", back_vars)
        self.assertEqual(
            rewrite_variable_names(LEGACY_BACK_TEMPLATE, {v: v for v in back_vars}),
            LEGACY_BACK_TEMPLATE,
        )

        # Test rewriting variables in real template
        rewritten = rewrite_variable_names(
            LEGACY_BACK_TEMPLATE,
            {"word": "vocabulary", "word_audio": "audio_clip"},
        )
        rewritten_vars = extract_variable_names(rewritten)
        self.assertIn("vocabulary", rewritten_vars)
        self.assertIn("audio_clip", rewritten_vars)
        self.assertNotIn("word", rewritten_vars)
        self.assertNotIn("word_audio", rewritten_vars)

    def test_unicode_and_vietnamese_variable_names(self) -> None:
        src = "{{ Từ vựng }} - {{ Nghĩa tiếng Việt }} - {{ 漢字 }}"
        extracted = extract_variable_names(src)
        self.assertEqual(extracted, ["Từ vựng", "Nghĩa tiếng Việt", "漢字"])

        rewritten = rewrite_variable_names(
            src,
            {
                "Từ vựng": "Word",
                "Nghĩa tiếng Việt": "Meaning",
                "漢字": "Kanji",
            },
        )
        self.assertEqual(rewritten, "{{ Word }} - {{ Meaning }} - {{ Kanji }}")

    def test_chevron_render_parity(self) -> None:
        import chevron

        source = (
            "<div>{{! comment {{Hidden}} }}Hello {{Word}}!</div>\n"
            "{{#Items}}Item: {{.}}{{/Items}}\n"
            "{{^Show}}Hidden block{{/Show}}"
        )
        vars_found = extract_variable_names(source)
        self.assertEqual(vars_found, ["Word", "Items", "Show"])

        rewritten = rewrite_variable_names(
            source,
            {"Word": "Name", "Items": "List", "Show": "Visible"},
        )
        # Verify rendered output matches chevron semantics
        rendered_orig = chevron.render(
            source,
            {"Word": "Flama", "Items": ["a", "b"], "Show": False},
        )
        rendered_rewritten = chevron.render(
            rewritten,
            {"Name": "Flama", "List": ["a", "b"], "Visible": False},
        )
        self.assertEqual(rendered_orig, rendered_rewritten)

    def test_edge_tags_with_spaces_and_sigils(self) -> None:
        source = "{{ #  spaced_tag  }}content{{ /  spaced_tag  }}"
        self.assertEqual(extract_variable_names(source), ["spaced_tag"])
        rewritten = rewrite_variable_names(source, {"spaced_tag": "new_tag"})
        self.assertEqual(rewritten, "{{ #  new_tag  }}content{{ /  new_tag  }}")

    def test_empty_and_dot_sigil_tags_ignored(self) -> None:
        source = "{{}} {{  }} {{#}} {{^}} {{/}} {{&}} {{.}} {{{.}}} {{{ }}}"
        self.assertEqual(extract_variable_names(source), [])
        self.assertEqual(rewrite_variable_names(source, {"any": "thing"}), source)

    def test_delimiter_variations_raise_error(self) -> None:
        for delim in ["{{ = <% %> = }}", "{{ = | | = }}", "{{=foo=}}", "{{ = }}"]:
            with self.subTest(delim=delim):
                with self.assertRaises(TemplateTokenError) as ctx:
                    extract_variable_names(delim)
                self.assertEqual(ctx.exception.code, "DELIMITER_CHANGE_UNSUPPORTED")
                with self.assertRaises(TemplateTokenError) as ctx2:
                    rewrite_variable_names(delim, {})
                self.assertEqual(ctx2.exception.code, "DELIMITER_CHANGE_UNSUPPORTED")

    def test_triple_brace_url_rewriting_and_crlf_preservation(self) -> None:
        source = "<div>\r\n{{{Image_url}}}\r\n{{{Image_urls}}}\r\n</div>"
        rewritten = rewrite_variable_names(source, {"Image": "Photo"})
        expected = "<div>\r\n{{{Photo_url}}}\r\n{{{Photo_urls}}}\r\n</div>"
        self.assertEqual(rewritten, expected)
        self.assertIn("\r\n", rewritten)


if __name__ == "__main__":
    unittest.main()
