"""Comprehensive 4-Tier Opaque-Box E2E Test Suite for Yomitan Ingestion & Smart Normalizer Pipeline.

Authoritative Reference:
- ORIGINAL_REQUEST.md (## 2026-09-19T01:32:29Z)
- PROJECT.md (Architecture, Code Layout, Feature Inventory, Interface Contracts)
- TEST_INFRA.md (Philosophy, Harness, 4-Tier Test Classification)
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import re
import tempfile
import unittest

from app.connect import create_connect_app
from app.services.anki_content_normalizer import normalize_anki_field_values
from app.services import user_api_token_service
from models import db
from models.deck import Deck
from models.field_def import FieldDef
from models.note import Note
from models.note_type import NoteType
from models.template import Template
from models.user import User


_HTML_TAG_RE = re.compile(r"(?is)<\s*/?\s*[a-z!][^>]*>")


@dataclass(frozen=True)
class MockFieldDef:
    name: str
    field_type: str = "text"
    identity_role: str | None = None
    position: int = 0
    required: bool = False


class AnkiNormalizerTestBase(unittest.TestCase):
    """Base test class providing an isolated in-memory Flama Connect environment."""

    @classmethod
    def setUpClass(cls):
        cls.upload_root = tempfile.TemporaryDirectory()
        cls.app = create_connect_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "CONNECT_CORS_ALLOWED_ORIGINS": (),
                "CONNECT_LEGACY_WEB_ACTIONS_ENABLED": True,
                "CONNECT_IP_RATE_LIMIT": 5000,
                "CONNECT_TOKEN_RATE_LIMIT": 5000,
                "CONNECT_USER_RATE_LIMIT": 5000,
                "CONNECT_ADD_NOTE_RATE_LIMIT": 5000,
                "CONNECT_MEDIA_RATE_LIMIT": 5000,
                "CONNECT_MEDIA_MAX_BYTES": 1024 * 1024,
                "FLASHCARD_MEDIA_UPLOAD_ROOT": cls.upload_root.name,
            }
        )

    @classmethod
    def tearDownClass(cls):
        cls.upload_root.cleanup()

    def setUp(self):
        self.upload_tmp = tempfile.TemporaryDirectory(dir=self.upload_root.name)
        self.app.config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = self.upload_tmp.name
        self.client = self.app.test_client()
        with self.app.app_context():
            db.create_all()
            owner = User(username="yomitan-user", email="yomitan@example.com")
            owner.set_password("securepassword")
            db.session.add(owner)
            db.session.flush()
            self.user_id = owner.id

            # Standard Vocabulary Note Type (Text fields)
            note_type = NoteType(user_id=owner.id, name="Yomitan Standard")
            db.session.add(note_type)
            db.session.flush()
            self.note_type_id = note_type.id

            self.field_word = FieldDef(
                note_type_id=note_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
                identity_role="primary",
            )
            self.field_reading = FieldDef(
                note_type_id=note_type.id,
                name="Reading",
                field_type="text",
                position=1,
                required=False,
                identity_role="secondary",
            )
            self.field_meaning = FieldDef(
                note_type_id=note_type.id,
                name="Meaning",
                field_type="text",
                position=2,
                required=False,
            )
            self.field_sentence = FieldDef(
                note_type_id=note_type.id,
                name="Sentence",
                field_type="text",
                position=3,
                required=False,
            )
            self.field_pitch = FieldDef(
                note_type_id=note_type.id,
                name="Pitch",
                field_type="text",
                position=4,
                required=False,
            )
            db.session.add_all([
                self.field_word,
                self.field_reading,
                self.field_meaning,
                self.field_sentence,
                self.field_pitch,
            ])

            # RichText Note Type
            rich_type = NoteType(user_id=owner.id, name="Yomitan Rich")
            db.session.add(rich_type)
            db.session.flush()
            self.rich_note_type_id = rich_type.id

            self.rich_field_word = FieldDef(
                note_type_id=rich_type.id,
                name="Word",
                field_type="text",
                position=0,
                required=True,
                identity_role="primary",
            )
            self.rich_field_reading = FieldDef(
                note_type_id=rich_type.id,
                name="Reading",
                field_type="text",
                position=1,
                required=False,
            )
            self.rich_field_glossary = FieldDef(
                note_type_id=rich_type.id,
                name="Glossary",
                field_type="richtext",
                position=2,
                required=False,
            )
            self.rich_field_notes = FieldDef(
                note_type_id=rich_type.id,
                name="Notes",
                field_type="richtext",
                position=3,
                required=False,
            )
            db.session.add_all([
                self.rich_field_word,
                self.rich_field_reading,
                self.rich_field_glossary,
                self.rich_field_notes,
            ])

            # Templates for card generation
            template_std = Template(
                note_type_id=note_type.id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Reading}}<br>{{Meaning}}",
            )
            template_rich = Template(
                note_type_id=rich_type.id,
                name="Card 1",
                front_html="{{Word}}",
                back_html="{{Reading}}<br>{{Glossary}}",
            )
            db.session.add_all([template_std, template_rich])

            # Standard Deck
            inbox = Deck(owner_user_id=owner.id, name="Default")
            db.session.add(inbox)

            # API Token for Yomitan
            token_obj = user_api_token_service.issue_token(user_id=owner.id, name="Yomitan Extension")
            db.session.commit()

            self.token = token_obj.plaintext
            self.deck_id = inbox.id

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()
        self.upload_tmp.cleanup()

    def _rpc(self, action: str, params: dict | None = None) -> dict:
        """Call Flama Connect JSON-RPC endpoint."""
        response = self.client.post(
            "/v1/flama-connect",
            json={
                "action": action,
                "params": params or {},
                "version": 2,
                "key": self.token,
            },
        )
        self.assertEqual(response.status_code, 200)
        return response.get_json()


# =====================================================================
# TIER 1: FEATURE COVERAGE (>=5 tests per feature, 25 tests)
# =====================================================================

class TestTier1FeatureCoverage(AnkiNormalizerTestBase):
    """Tier 1: Comprehensive feature coverage across all 5 core normalizer feature sets."""

    # -----------------------------------------------------------------
    # Feature 1: Yomitan Term Markers (5 tests)
    # -----------------------------------------------------------------

    def test_tier1_term_expression_plain(self):
        """{expression}: Plain text headword in Kanji/Kana preserved as plain text."""
        defs = [MockFieldDef("Word", "text", identity_role="primary")]
        res = normalize_anki_field_values({"Word": "日本語"}, defs)
        self.assertEqual(res["Word"], "日本語")

    def test_tier1_term_reading_kana(self):
        """{reading}: Plain text Kana reading preserved as plain text."""
        defs = [MockFieldDef("Reading", "text", identity_role="secondary")]
        res = normalize_anki_field_values({"Reading": "にほんご"}, defs)
        self.assertEqual(res["Reading"], "にほんご")

    def test_tier1_term_furigana_into_reading_extracts_kana(self):
        """{furigana} into Reading field: extracts only Kana reading from <rt> tags."""
        defs = [MockFieldDef("Reading", "text", identity_role="secondary")]
        res = normalize_anki_field_values({"Reading": "<ruby>食<rt>た</rt></ruby>べる"}, defs)
        self.assertEqual(res["Reading"], "たべる")

    def test_tier1_term_furigana_into_word_extracts_kanji(self):
        """{furigana} into Word/Primary field: extracts base Kanji, stripping ruby/rt."""
        defs = [MockFieldDef("Word", "text", identity_role="primary")]
        res = normalize_anki_field_values({"Word": "<ruby>食<rt>た</rt></ruby>べる"}, defs)
        self.assertEqual(res["Word"], "食べる")

    def test_tier1_term_furigana_plain_bracket_preserved(self):
        """{furigana-plain}: Bracket notation 日本語[にほんご] preserved in text field."""
        defs = [MockFieldDef("Word", "text")]
        res = normalize_anki_field_values({"Word": "日本語[にほんご]"}, defs)
        self.assertEqual(res["Word"], "日本語[にほんご]")

    # -----------------------------------------------------------------
    # Feature 2: Yomitan Glossary Markers (5 tests)
    # -----------------------------------------------------------------

    def test_tier1_glossary_ol_li_to_numbered_text(self):
        """{glossary}: <ol><li> list converted into clean numbered plain text."""
        defs = [MockFieldDef("Meaning", "text")]
        html_input = "<ol><li><span>to eat</span></li><li><span>to consume</span></li></ol>"
        res = normalize_anki_field_values({"Meaning": html_input}, defs)
        self.assertIn("1. to eat", res["Meaning"])
        self.assertIn("2. to consume", res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier1_glossary_brief_nested_spans(self):
        """{glossary-brief}: list with inner class/style spans stripped to clean text."""
        defs = [MockFieldDef("Meaning", "text")]
        html_input = '<ol><li><span class="gloss-desc" style="color:red">eat; consume</span></li></ol>'
        res = normalize_anki_field_values({"Meaning": html_input}, defs)
        self.assertIn("eat; consume", res["Meaning"])
        self.assertNotIn("gloss-desc", res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier1_glossary_plain_br_to_newlines(self):
        """{glossary-plain}: <br> tags converted to clean single newlines."""
        defs = [MockFieldDef("Meaning", "text")]
        html_input = "first definition<br>second definition<br/>third definition"
        res = normalize_anki_field_values({"Meaning": html_input}, defs)
        self.assertEqual(res["Meaning"], "first definition\nsecond definition\nthird definition")
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier1_single_glossary_dict_handling(self):
        """{single-glossary-DICT}: single dictionary glossary converted to numbered plain text."""
        defs = [MockFieldDef("Meaning", "text")]
        html_input = "<ol><li><span>primary definition from JMdict</span></li></ol>"
        res = normalize_anki_field_values({"Meaning": html_input}, defs)
        self.assertIn("1. primary definition from JMdict", res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier1_glossary_ul_bulleted_conversion(self):
        """<ul> list converted to bulleted plain text in text fields."""
        defs = [MockFieldDef("Meaning", "text")]
        html_input = "<ul><li>alpha</li><li>beta</li></ul>"
        res = normalize_anki_field_values({"Meaning": html_input}, defs)
        self.assertTrue("alpha" in res["Meaning"] and "beta" in res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    # -----------------------------------------------------------------
    # Feature 3: Yomitan Sentence Markers (5 tests)
    # -----------------------------------------------------------------

    def test_tier1_sentence_bold_headword_stripped(self):
        """{sentence}: <b> headword tag stripped cleanly for text field."""
        defs = [MockFieldDef("Sentence", "text")]
        res = normalize_anki_field_values({"Sentence": "昨日、りんごを<b>食べた</b>。"}, defs)
        self.assertEqual(res["Sentence"], "昨日、りんごを食べた。")
        self.assertIsNone(_HTML_TAG_RE.search(res["Sentence"]))

    def test_tier1_sentence_furigana_ruby_to_base(self):
        """{sentence-furigana}: sentence containing <ruby> and <b> extracts base sentence."""
        defs = [MockFieldDef("Sentence", "text")]
        html_input = "昨日、りんごを<b><ruby>食<rt>た</rt></ruby>べた</b>。"
        res = normalize_anki_field_values({"Sentence": html_input}, defs)
        self.assertEqual(res["Sentence"], "昨日、りんごを食べた。")
        self.assertIsNone(_HTML_TAG_RE.search(res["Sentence"]))

    def test_tier1_sentence_furigana_plain_brackets(self):
        """{sentence-furigana-plain}: bracket notation preserved while <b> stripped."""
        defs = [MockFieldDef("Sentence", "text")]
        res = normalize_anki_field_values({"Sentence": "昨日、りんごを<b>食[た]べた</b>。"}, defs)
        self.assertEqual(res["Sentence"], "昨日、りんごを食[た]べた。")

    def test_tier1_sentence_multiple_bold_phrases(self):
        """Sentence with multiple bold spans all stripped cleanly."""
        defs = [MockFieldDef("Sentence", "text")]
        res = normalize_anki_field_values({"Sentence": "<b>彼</b>は<b>りんご</b>を食べた。"}, defs)
        self.assertEqual(res["Sentence"], "彼はりんごを食べた。")

    def test_tier1_sentence_nested_formatting_tags(self):
        """Sentence with nested <i>, <b>, <small> formatting tags stripped cleanly."""
        defs = [MockFieldDef("Sentence", "text")]
        html_input = "<i>例文：</i><b>食べた</b>（<small>過去形</small>）"
        res = normalize_anki_field_values({"Sentence": html_input}, defs)
        self.assertEqual(res["Sentence"], "例文：食べた（過去形）")

    # -----------------------------------------------------------------
    # Feature 4: Yomitan Pitch Accent Markers (5 tests)
    # -----------------------------------------------------------------

    def test_tier1_pitch_accents_list_to_plain_text(self):
        """{pitch-accents}: pitch accent list converted to clean numbered plain text."""
        defs = [MockFieldDef("Pitch", "text")]
        html_input = '<ol><li><span>たべる</span> <span class="pitch-accent-tag">[2]</span></li></ol>'
        res = normalize_anki_field_values({"Pitch": html_input}, defs)
        self.assertIn("たべる", res["Pitch"])
        self.assertIn("[2]", res["Pitch"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Pitch"]))

    def test_tier1_pitch_accent_graphs_svg_in_text_field(self):
        """{pitch-accent-graphs}: SVG markup completely stripped in text field."""
        defs = [MockFieldDef("Pitch", "text")]
        html_input = '<svg viewBox="0 0 100 20"><path d="M0 10 L50 10"/><circle cx="10" cy="10" r="3"/><text x="10" y="15">2</text></svg>'
        res = normalize_anki_field_values({"Pitch": html_input}, defs)
        self.assertNotIn("<svg", res["Pitch"])
        self.assertNotIn("<path", res["Pitch"])
        self.assertNotIn("<circle", res["Pitch"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Pitch"]))

    def test_tier1_pitch_accent_graphs_svg_in_richtext_field(self):
        """{pitch-accent-graphs}: SVG markup safely preserved in richtext field."""
        defs = [MockFieldDef("Notes", "richtext")]
        html_input = '<svg viewBox="0 0 100 20"><path d="M0 10 L50 10"/><circle cx="10" cy="10" r="3"/></svg>'
        res = normalize_anki_field_values({"Notes": html_input}, defs)
        self.assertIn("<svg", res["Notes"])
        self.assertIn("viewBox", res["Notes"])

    def test_tier1_pitch_accent_positions_numeric(self):
        """{pitch-accent-positions}: downstep number e.g. [2] preserved in text field."""
        defs = [MockFieldDef("Pitch", "text")]
        res = normalize_anki_field_values({"Pitch": "[2]"}, defs)
        self.assertEqual(res["Pitch"], "[2]")

    def test_tier1_pitch_accent_categories_text(self):
        """{pitch-accent-categories}: group category name preserved in text field."""
        defs = [MockFieldDef("Pitch", "text")]
        res = normalize_anki_field_values({"Pitch": "atamadaka"}, defs)
        self.assertEqual(res["Pitch"], "atamadaka")

    # -----------------------------------------------------------------
    # Feature 5: Field-Type-Awareness (5 tests)
    # -----------------------------------------------------------------

    def test_tier1_type_text_strips_all_html(self):
        """Text field guarantees 0 unstripped HTML tags."""
        defs = [MockFieldDef("Word", "text", identity_role="primary")]
        html_input = "<span><b><i><ruby>日<rt>に</rt>本<rt>ほん</rt></ruby></i></b></span>"
        res = normalize_anki_field_values({"Word": html_input}, defs)
        self.assertEqual(res["Word"], "日本")
        self.assertIsNone(_HTML_TAG_RE.search(res["Word"]))

    def test_tier1_type_richtext_preserves_ruby_and_lists(self):
        """Richtext field preserves semantic tags (<ruby>, <ol>, <li>, <b>)."""
        defs = [MockFieldDef("Glossary", "richtext")]
        html_input = "<ol><li><b>to eat</b>: <ruby>食<rt>た</rt></ruby>べる</li></ol>"
        res = normalize_anki_field_values({"Glossary": html_input}, defs)
        self.assertIn("<ruby>", res["Glossary"])
        self.assertIn("<ol>", res["Glossary"])
        self.assertIn("<b>", res["Glossary"])

    def test_tier1_type_richtext_bleach_sanitizes(self):
        """Richtext field sanitizes dangerous script tags while keeping safe tags."""
        defs = [MockFieldDef("Glossary", "richtext")]
        html_input = "<ol><li>Safe text</li></ol><script>alert('pwn')</script>"
        res = normalize_anki_field_values({"Glossary": html_input}, defs)
        self.assertNotIn("<script>", res["Glossary"])
        self.assertNotIn("alert('pwn')", res["Glossary"])
        self.assertIn("<ol>", res["Glossary"])

    def test_tier1_type_markdown_leaves_markdown_markup(self):
        """Markdown field preserves markdown symbols intact."""
        defs = [MockFieldDef("Notes", "markdown")]
        md_input = "# Header 1\n\n- item 1\n- item 2\n\n**bold text**"
        res = normalize_anki_field_values({"Notes": md_input}, defs)
        self.assertEqual(res["Notes"], md_input)

    def test_tier1_type_unknown_fallback_to_text_stripping(self):
        """Unrecognized field types fall back to safe text normalization."""
        defs = [MockFieldDef("Custom", "unknown_type")]
        res = normalize_anki_field_values({"Custom": "<b>clean</b>"}, defs)
        self.assertEqual(res["Custom"], "clean")


# =====================================================================
# TIER 2: BOUNDARY & CORNER CASES (>=5 tests per feature, 35 tests)
# =====================================================================

class TestTier2BoundaryCornerCases(AnkiNormalizerTestBase):
    """Tier 2: Extreme boundary conditions, stress payloads, security, and corner cases."""

    # -----------------------------------------------------------------
    # Feature 6: Boundary Inputs (5 tests)
    # -----------------------------------------------------------------

    def test_tier2_boundary_empty_string_payload(self):
        """Empty string input returns empty string without error."""
        defs = [MockFieldDef("Word", "text")]
        res = normalize_anki_field_values({"Word": ""}, defs)
        self.assertEqual(res["Word"], "")

    def test_tier2_boundary_whitespace_only_payload(self):
        """Whitespace-only input returns empty or stripped string."""
        defs = [MockFieldDef("Word", "text")]
        res = normalize_anki_field_values({"Word": "   \n\t  "}, defs)
        self.assertEqual(res["Word"].strip(), "")

    def test_tier2_boundary_single_char_kanji(self):
        """Single character Kanji boundary."""
        defs = [MockFieldDef("Word", "text")]
        res = normalize_anki_field_values({"Word": "日"}, defs)
        self.assertEqual(res["Word"], "日")

    def test_tier2_boundary_vietnamese_diacritics(self):
        """Vietnamese diacritics and complex unicode characters preserved intact."""
        defs = [MockFieldDef("Meaning", "text")]
        vi_text = "Nghĩa: Ăn cơm, dùng bữa trưa; Phở bò tái nạm gầu."
        res = normalize_anki_field_values({"Meaning": vi_text}, defs)
        self.assertEqual(res["Meaning"], vi_text)

    def test_tier2_boundary_multilingual_cjk_english(self):
        """Multi-lingual CJK and Western characters combined."""
        defs = [MockFieldDef("Meaning", "text")]
        multi_text = "Chinese: 吃饭 (chī fàn); Japanese: 食べる (taberu); English: to eat."
        res = normalize_anki_field_values({"Meaning": multi_text}, defs)
        self.assertEqual(res["Meaning"], multi_text)

    # -----------------------------------------------------------------
    # Feature 7: Massive HTML Overhead (>6k HTML, <5k Text) (5 tests)
    # -----------------------------------------------------------------

    def test_tier2_massive_html_overhead_under_5k_text_passes(self):
        """Payload with HTML > 6,000 chars but plain text < 5,000 chars passes without 400."""
        defs = [MockFieldDef("Meaning", "text")]
        # Generate 6,500 chars of HTML with 1,500 chars of text
        items = []
        for i in range(45):
            items.append(f'<li class="dict-item-{i}" data-index="{i}"><span class="gloss-item" style="color:#333;font-size:14px">Definition number {i} for this vocabulary item</span></li>')
        html_payload = f'<ol class="dict-group" data-dictionary="Daijirin">{"".join(items)}</ol>'
        self.assertGreater(len(html_payload), 6000)

        res = normalize_anki_field_values({"Meaning": html_payload}, defs)
        # Normalized text must be under 5,000 chars and contain 0 HTML tags
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))
        self.assertIn("Definition number 0", res["Meaning"])
        self.assertIn("Definition number 29", res["Meaning"])

    def test_tier2_heavy_nested_spans_and_classes_passes(self):
        """Deeply nested spans and attributes exceeding 6,200 chars strip clean."""
        defs = [MockFieldDef("Meaning", "text")]
        nested_spans = '<div class="yomitan-popup">' + ('<span class="wrapper">' * 50) + 'Real Meaning' + ('</span>' * 50) + '</div>'
        bloated = nested_spans * 40
        self.assertGreater(len(bloated), 6000)
        res = normalize_anki_field_values({"Meaning": bloated}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))
        self.assertIn("Real Meaning", res["Meaning"])

    def test_tier2_multi_dict_markup_bloat_passes(self):
        """Multi-dictionary wrapper markup totaling 7,500 chars stripped clean."""
        defs = [MockFieldDef("Meaning", "text")]
        dict_block = (
            '<div class="dict-entry" data-dict="Kojien">'
            '<header class="dict-hdr"><span class="badge">Kojien</span></header>'
            '<ol class="dict-senses"><li><span class="def">Meaning A</span></li><li><span class="def">Meaning B</span></li></ol>'
            '</div>'
        )
        payload = dict_block * 35
        self.assertGreater(len(payload), 7000)
        res = normalize_anki_field_values({"Meaning": payload}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier2_large_attribute_bloat_passes(self):
        """Extremely long data-* attributes (6,500 chars total) stripped cleanly."""
        defs = [MockFieldDef("Meaning", "text")]
        huge_attr = "x" * 2000
        html = f'<p data-meta="{huge_attr}">Def 1</p><p data-meta="{huge_attr}">Def 2</p><p data-meta="{huge_attr}">Def 3</p>'
        self.assertGreater(len(html), 6000)
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertNotIn("xxxx", res["Meaning"])
        self.assertIn("Def 1", res["Meaning"])

    def test_tier2_repeated_styling_tags_bloat_passes(self):
        """Repeated inline styling tags totaling 6,200 chars stripped cleanly."""
        defs = [MockFieldDef("Meaning", "text")]
        chunk = "<b><i><u><font color='blue'>entry</font></u></i></b> "
        html = chunk * 150
        self.assertGreater(len(html), 6000)
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    # -----------------------------------------------------------------
    # Feature 8: Massive Text (>5k Chars Graceful Semantic Trimming) (5 tests)
    # -----------------------------------------------------------------

    def test_tier2_oversized_text_graceful_trim_appends_ellipsis(self):
        """Plain text exceeding 5,000 characters is trimmed gracefully with '...'."""
        defs = [MockFieldDef("Meaning", "text")]
        long_text = "A" * 6000
        res = normalize_anki_field_values({"Meaning": long_text}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertTrue(res["Meaning"].endswith("..."))

    def test_tier2_oversized_text_trims_at_numbered_sense_boundary(self):
        """Oversized text with numbered senses trims at complete sense boundary."""
        defs = [MockFieldDef("Meaning", "text")]
        # Generate numbered senses of 200 chars each: 35 senses = 7,000 chars
        senses = [f"{i}. " + ("Definition sentence content. " * 6) for i in range(1, 36)]
        long_text = "\n".join(senses)
        self.assertGreater(len(long_text), 6000)

        res = normalize_anki_field_values({"Meaning": long_text}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertTrue(res["Meaning"].endswith("..."))
        # Must preserve earlier senses intact
        self.assertIn("1. Definition sentence content.", res["Meaning"])
        self.assertIn("10. Definition sentence content.", res["Meaning"])

    def test_tier2_oversized_text_trims_at_sentence_terminal(self):
        """Oversized text with Japanese periods (。) trims at complete sentence boundary."""
        defs = [MockFieldDef("Meaning", "text")]
        sentence = "これは非常に長い辞書の解説文であり、例文を含んでいます。"
        long_text = sentence * 180  # ~5,580 chars
        self.assertGreater(len(long_text), 5000)

        res = normalize_anki_field_values({"Meaning": long_text}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertTrue(res["Meaning"].endswith("..."))

    def test_tier2_oversized_text_trims_at_clause_boundary(self):
        """Oversized text with semicolons trims at clause delimiter."""
        defs = [MockFieldDef("Meaning", "text")]
        clause = "sense part one; sense part two; sense part three; "
        long_text = clause * 120  # ~6,000 chars
        res = normalize_anki_field_values({"Meaning": long_text}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertTrue(res["Meaning"].endswith("..."))

    def test_tier2_oversized_text_hard_cut_preserves_unicode(self):
        """Oversized text without punctuation cuts cleanly without splitting multi-byte characters."""
        defs = [MockFieldDef("Meaning", "text")]
        long_cjk = "あ" * 5500
        res = normalize_anki_field_values({"Meaning": long_cjk}, defs)
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertTrue(res["Meaning"].endswith("..."))
        # Must decode cleanly without encoding errors
        res["Meaning"].encode("utf-8").decode("utf-8")

    # -----------------------------------------------------------------
    # Feature 9: RichText Boundary (20k Chars Balanced Tags) (5 tests)
    # -----------------------------------------------------------------

    def test_tier2_richtext_approaching_20k_preserves_valid_html(self):
        """Richtext approaching 20,000 characters is preserved and remains valid HTML."""
        defs = [MockFieldDef("Glossary", "richtext")]
        item = "<li><b>definition entry</b>: sample explanation text</li>"
        # 55 chars * 340 = ~18,700 chars
        html = f"<ol>{item * 340}</ol>"
        self.assertGreater(len(html), 18000)
        self.assertLessEqual(len(html), 20000)

        res = normalize_anki_field_values({"Glossary": html}, defs)
        self.assertLessEqual(len(res["Glossary"]), 20000)
        self.assertIn("<ol>", res["Glossary"])
        self.assertIn("</ol>", res["Glossary"])

    def test_tier2_richtext_over_20k_balanced_tag_closure(self):
        """Richtext exceeding 20,000 chars is trimmed to <= 20,000 with all open tags closed."""
        defs = [MockFieldDef("Glossary", "richtext")]
        item = "<li><span><b>item title</b>: long explanation paragraph here</span></li>"
        html = f"<ol>{item * 400}</ol>"  # ~28,000 chars
        self.assertGreater(len(html), 25000)

        res = normalize_anki_field_values({"Glossary": html}, defs)
        self.assertLessEqual(len(res["Glossary"]), 20000)
        # All tags must be balanced
        self.assertEqual(res["Glossary"].count("<ol>"), res["Glossary"].count("</ol>"))
        self.assertEqual(res["Glossary"].count("<b>"), res["Glossary"].count("</b>"))

    def test_tier2_richtext_deeply_nested_lists_closure(self):
        """Nested lists truncated at 20k boundary close all parent tags."""
        defs = [MockFieldDef("Glossary", "richtext")]
        sub = "<ul><li>sub-item detail</li></ul>"
        item = f"<li>top-level {sub}</li>"
        html = f"<ol>{item * 350}</ol>"  # ~25,000 chars

        res = normalize_anki_field_values({"Glossary": html}, defs)
        self.assertLessEqual(len(res["Glossary"]), 20000)
        self.assertEqual(res["Glossary"].count("<ol>"), res["Glossary"].count("</ol>"))
        self.assertEqual(res["Glossary"].count("<ul>"), res["Glossary"].count("</ul>"))

    def test_tier2_richtext_table_tag_closure(self):
        """Table truncated at 20k boundary closes all open <table>, <tr>, <td> tags."""
        defs = [MockFieldDef("Glossary", "richtext")]
        row = "<tr><td>Kanji</td><td>Kana</td><td>English definition</td></tr>"
        html = f"<table><tbody>{row * 350}</tbody></table>"

        res = normalize_anki_field_values({"Glossary": html}, defs)
        self.assertLessEqual(len(res["Glossary"]), 20000)
        self.assertEqual(res["Glossary"].count("<table>"), res["Glossary"].count("</table>"))
        self.assertEqual(res["Glossary"].count("<tr>"), res["Glossary"].count("</tr>"))

    def test_tier2_richtext_svg_graph_length_budget(self):
        """SVG graph in richtext fits within length budget and remains intact."""
        defs = [MockFieldDef("Notes", "richtext")]
        svg = '<svg viewBox="0 0 100 20"><path d="M0 10 L50 10"/><circle cx="10" cy="10" r="3"/></svg>'
        html = f"<p>Pitch curve:</p>{svg}"
        res = normalize_anki_field_values({"Notes": html}, defs)
        self.assertIn("<svg", res["Notes"])
        self.assertIn("</svg>", res["Notes"])

    # -----------------------------------------------------------------
    # Feature 10: Nested Ruby & Complex Structures (5 tests)
    # -----------------------------------------------------------------

    def test_tier2_nested_ruby_multiple_rt_and_rp(self):
        """Multi-segment ruby with <rp> parenthesis tags correctly parsed."""
        defs = [
            MockFieldDef("Word", "text", identity_role="primary"),
            MockFieldDef("Reading", "text", identity_role="secondary"),
        ]
        ruby_input = "<ruby>日<rp>(</rp><rt>に</rt><rp>)</rp>本<rp>(</rp><rt>ほん</rt><rp>)</rp>語<rp>(</rp><rt>ご</rt><rp>)</rp></ruby>"
        res = normalize_anki_field_values({"Word": ruby_input, "Reading": ruby_input}, defs)
        self.assertEqual(res["Word"], "日本語")
        self.assertEqual(res["Reading"], "にほんご")

    def test_tier2_nested_ol_inside_li_structures(self):
        """Nested ordered list inside list item converted to clean hierarchy."""
        defs = [MockFieldDef("Meaning", "text")]
        html = "<ol><li>Main sense<ol><li>Sub sense A</li><li>Sub sense B</li></ol></li><li>Second main sense</li></ol>"
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertIn("Main sense", res["Meaning"])
        self.assertIn("Sub sense A", res["Meaning"])
        self.assertIn("Second main sense", res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier2_mixed_ruby_with_hyperlinks_and_spans(self):
        """Ruby wrapped inside anchor and styling spans stripped cleanly in text."""
        defs = [MockFieldDef("Word", "text", identity_role="primary")]
        html = '<a href="https://example.com" class="link"><span class="highlight"><ruby>漢<rt>かん</rt>字<rt>じ</rt></ruby></span></a>'
        res = normalize_anki_field_values({"Word": html}, defs)
        self.assertEqual(res["Word"], "漢字")
        self.assertIsNone(_HTML_TAG_RE.search(res["Word"]))

    def test_tier2_ruby_with_partial_kana_affixes(self):
        """Prefix/suffix kana attached to ruby extracted properly."""
        defs = [
            MockFieldDef("Word", "text", identity_role="primary"),
            MockFieldDef("Reading", "text", identity_role="secondary"),
        ]
        html = "お<ruby>願<rt>ねが</rt></ruby>いする"
        res = normalize_anki_field_values({"Word": html, "Reading": html}, defs)
        self.assertEqual(res["Word"], "お願いする")
        self.assertEqual(res["Reading"], "おねがいする")

    def test_tier2_deeply_nested_mixed_definition_blocks(self):
        """Complex combination of div, p, ol, li, span, b cleanly normalized."""
        defs = [MockFieldDef("Meaning", "text")]
        html = '<div><p><b>Overview:</b></p><ol><li><span>Sense 1: <i>Literal meaning</i></span></li></ol></div>'
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertIn("Overview:", res["Meaning"])
        self.assertIn("Sense 1: Literal meaning", res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    # -----------------------------------------------------------------
    # Feature 11: Security & XSS Neutralization (5 tests)
    # -----------------------------------------------------------------

    def test_tier2_security_script_tag_content_stripped_in_text(self):
        """<script> tags and their inner executable code are completely removed."""
        defs = [MockFieldDef("Meaning", "text")]
        html = "Safe text<script type='text/javascript'>alert('pwn'); document.cookie='x';</script> more safe text"
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertNotIn("<script", res["Meaning"])
        self.assertNotIn("document.cookie", res["Meaning"])
        self.assertIn("Safe text", res["Meaning"])
        self.assertIn("more safe text", res["Meaning"])

    def test_tier2_security_onerror_handlers_stripped_in_text(self):
        """Elements with onerror or onload handlers stripped completely."""
        defs = [MockFieldDef("Meaning", "text")]
        html = 'Normal definition<img src="invalid" onerror="alert(1)" /><svg onload="alert(2)"></svg>'
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertNotIn("onerror", res["Meaning"])
        self.assertNotIn("onload", res["Meaning"])
        self.assertEqual(res["Meaning"].strip(), "Normal definition")

    def test_tier2_security_javascript_pseudo_protocol_stripped(self):
        """javascript: URLs neutralized and tags stripped."""
        defs = [MockFieldDef("Meaning", "text")]
        html = '<a href="javascript:alert(1)">Click here</a> for meaning'
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertNotIn("javascript:", res["Meaning"])
        self.assertIn("Click here for meaning", res["Meaning"])

    def test_tier2_security_richtext_bleach_strips_scripts(self):
        """Richtext field sanitizes scripts via bleach while keeping safe formatting."""
        defs = [MockFieldDef("Glossary", "richtext")]
        html = '<p>Definition</p><script>evil()</script><b onclick="harm()">Bold</b>'
        res = normalize_anki_field_values({"Glossary": html}, defs)
        self.assertNotIn("<script", res["Glossary"])
        self.assertNotIn("evil()", res["Glossary"])
        self.assertNotIn("onclick", res["Glossary"])
        self.assertIn("<p>Definition</p>", res["Glossary"])
        self.assertIn("<b>Bold</b>", res["Glossary"])

    def test_tier2_security_richtext_disallowed_tags_stripped(self):
        """Disallowed tags (<object>, <embed>, <iframe>) stripped in richtext."""
        defs = [MockFieldDef("Glossary", "richtext")]
        html = '<b>Meaning</b><iframe src="https://attacker.com"></iframe><embed src="flash.swf">'
        res = normalize_anki_field_values({"Glossary": html}, defs)
        self.assertNotIn("<iframe", res["Glossary"])
        self.assertNotIn("<embed", res["Glossary"])
        self.assertIn("<b>Meaning</b>", res["Glossary"])

    # -----------------------------------------------------------------
    # Feature 12: HTML Entity Unescaping (5 tests)
    # -----------------------------------------------------------------

    def test_tier2_entities_quot_amp_apos_nbsp_in_text(self):
        """Safe text entities decoded properly (&quot;, &amp;, &#39;, &nbsp;)."""
        defs = [MockFieldDef("Meaning", "text")]
        html = "&quot;to eat&quot; &amp; &apos;to consume&apos;&nbsp;(formal)"
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertEqual(res["Meaning"], '"to eat" & \'to consume\' (formal)')

    def test_tier2_entities_hex_and_decimal_numeric_entities(self):
        """Numeric character references decoded properly."""
        defs = [MockFieldDef("Meaning", "text")]
        html = "&#65;&#66;&#67; &#x3042;&#x3044;&#x3046;"
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertEqual(res["Meaning"], "ABC あいう")

    def test_tier2_entities_unscathed_special_cjk_characters(self):
        """Japanese punctuation marks and brackets preserved."""
        defs = [MockFieldDef("Meaning", "text")]
        text = "「食べる」【動詞】（他動詞）〜を食べる。"
        res = normalize_anki_field_values({"Meaning": text}, defs)
        self.assertEqual(res["Meaning"], text)

    def test_tier2_entities_prevent_unescaping_into_harmful_tags(self):
        """Entity-encoded script tags in text remain plain text without becoming raw tags."""
        defs = [MockFieldDef("Meaning", "text")]
        html = "&lt;script&gt;alert(1)&lt;/script&gt;"
        res = normalize_anki_field_values({"Meaning": html}, defs)
        # Even if unescaped or preserved, it must NOT execute as a script or cause HTML tag rejection
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier2_entities_mixed_in_numbered_definitions(self):
        """Entities inside list elements decoded in final numbered output."""
        defs = [MockFieldDef("Meaning", "text")]
        html = "<ol><li>Tom &amp; Jerry</li><li>Ben &amp; Jerry&#39;s</li></ol>"
        res = normalize_anki_field_values({"Meaning": html}, defs)
        self.assertIn("Tom & Jerry", res["Meaning"])
        self.assertIn("Ben & Jerry's", res["Meaning"])


# =====================================================================
# TIER 3: CROSS-FEATURE COMBINATIONS (5 tests)
# =====================================================================

class TestTier3CrossFeatureCombinations(AnkiNormalizerTestBase):
    """Tier 3: Pairwise combinations and full Flama Connect RPC wire format verification."""

    def test_tier3_pairwise_full_yomitan_1click_note_creation(self):
        """Full 1-click note creation with {expression}, {furigana}, {glossary}, and {sentence}."""
        payload = {
            "note": {
                "deckName": "Default",
                "modelName": "Yomitan Standard",
                "fields": {
                    "Word": "<ruby>食<rt>た</rt></ruby>べる",
                    "Reading": "<ruby>食<rt>た</rt></ruby>べる",
                    "Meaning": "<ol><li><span>to eat</span></li><li><span>to consume</span></li></ol>",
                    "Sentence": "昨日、美味しいりんごを<b>食べた</b>。",
                    "Pitch": '<ol><li><span>たべる</span> <span class="pitch-tag">[2]</span></li></ol>',
                },
                "tags": ["yomitan", "jlpt-n5"],
                "options": {"allowDuplicate": False},
            }
        }
        res = self._rpc("addNote", payload)
        if isinstance(res, dict) and "error" in res:
            self.fail(f"addNote failed with error: {res['error']}")
        note_id = res
        self.assertIsNotNone(note_id)

        # Inspect persisted note in database
        with self.app.app_context():
            note = Note.query.get(note_id)
            self.assertIsNotNone(note)
            fields = note.field_values
            self.assertEqual(fields["Word"], "食べる")
            self.assertEqual(fields["Reading"], "たべる")
            self.assertIn("1. to eat", fields["Meaning"])
            self.assertEqual(fields["Sentence"], "昨日、美味しいりんごを食べた。")
            self.assertIsNone(_HTML_TAG_RE.search(fields["Word"]))
            self.assertIsNone(_HTML_TAG_RE.search(fields["Reading"]))
            self.assertIsNone(_HTML_TAG_RE.search(fields["Meaning"]))
            self.assertIsNone(_HTML_TAG_RE.search(fields["Sentence"]))

    def test_tier3_duplicate_check_canAddNotes_with_ruby_word(self):
        """canAddNotes duplicate check normalizes incoming ruby before checking duplicates."""
        # 1. First add note
        self._rpc(
            "addNote",
            {
                "note": {
                    "deckName": "Default",
                    "modelName": "Yomitan Standard",
                    "fields": {"Word": "飲む", "Reading": "のむ", "Meaning": "to drink"},
                }
            },
        )

        # 2. Check duplicate with ruby in Word
        check_payload = {
            "notes": [
                {
                    "deckName": "Default",
                    "modelName": "Yomitan Standard",
                    "fields": {
                        "Word": "<ruby>飲<rt>の</rt></ruby>む",
                        "Reading": "のむ",
                    },
                }
            ]
        }
        res = self._rpc("canAddNotes", check_payload)
        if isinstance(res, dict) and "error" in res:
            self.fail(f"canAddNotes failed with error: {res['error']}")
        # Should detect as duplicate -> False
        self.assertEqual(res, [False])

    def test_tier3_duplicate_check_canAddNotesWithErrorDetail(self):
        """canAddNotesWithErrorDetail reports duplicate without 400 validation failure."""
        self._rpc(
            "addNote",
            {
                "note": {
                    "deckName": "Default",
                    "modelName": "Yomitan Standard",
                    "fields": {"Word": "走る", "Reading": "はしる", "Meaning": "to run"},
                }
            },
        )
        check_payload = {
            "notes": [
                {
                    "deckName": "Default",
                    "modelName": "Yomitan Standard",
                    "fields": {"Word": "<ruby>走<rt>はし</rt></ruby>る"},
                },
                {
                    "deckName": "Default",
                    "modelName": "Yomitan Standard",
                    "fields": {"Word": "新しい単語"},
                },
            ]
        }
        res = self._rpc("canAddNotesWithErrorDetail", check_payload)
        if isinstance(res, dict) and "error" in res:
            self.fail(f"canAddNotesWithErrorDetail failed with error: {res['error']}")
        self.assertEqual(len(res), 2)
        self.assertFalse(res[0]["canAdd"])
        self.assertTrue(res[1]["canAdd"])

    def test_tier3_mixed_text_and_richtext_in_single_note(self):
        """Single note with both text fields (Word, Reading) and richtext fields (Glossary)."""
        payload = {
            "note": {
                "deckName": "Default",
                "modelName": "Yomitan Rich",
                "fields": {
                    "Word": "<ruby>勉強<rt>べんきょう</rt></ruby>する",
                    "Reading": "<ruby>勉強<rt>べんきょう</rt></ruby>する",
                    "Glossary": "<ol><li><b>to study</b>: diligence</li></ol>",
                    "Notes": "<p>Notes with <ruby>ルビ<rt>るび</rt></ruby></p>",
                },
            }
        }
        res = self._rpc("addNote", payload)
        if isinstance(res, dict) and "error" in res:
            self.fail(f"addNote failed with error: {res['error']}")
        note_id = res

        with self.app.app_context():
            note = Note.query.get(note_id)
            fields = note.field_values
            # Text fields are stripped
            self.assertEqual(fields["Word"], "勉強する")
            self.assertEqual(fields["Reading"], "べんきょうする")
            self.assertIsNone(_HTML_TAG_RE.search(fields["Word"]))
            # Richtext fields preserve safe tags
            self.assertIn("<ol>", fields["Glossary"])
            self.assertIn("<b>", fields["Glossary"])
            self.assertIn("<ruby>", fields["Notes"])

    def test_tier3_multi_field_import_session_batch_ingestion(self):
        """Direct normalization of multi-field dictionary batches."""
        defs = [
            MockFieldDef("Word", "text", identity_role="primary"),
            MockFieldDef("Reading", "text", identity_role="secondary"),
            MockFieldDef("Meaning", "text"),
            MockFieldDef("Glossary", "richtext"),
        ]
        batch = {
            "Word": "<ruby>車<rt>くるま</rt></ruby>",
            "Reading": "<ruby>車<rt>くるま</rt></ruby>",
            "Meaning": "<ol><li>car; automobile</li></ol>",
            "Glossary": "<ol><li><b>car</b>; vehicle</li></ol>",
        }
        res = normalize_anki_field_values(batch, defs)
        self.assertEqual(res["Word"], "車")
        self.assertEqual(res["Reading"], "くるま")
        self.assertIn("1. car; automobile", res["Meaning"])
        self.assertIn("<ol><li><b>car</b>", res["Glossary"])


# =====================================================================
# TIER 4: REAL-WORLD APPLICATION SCENARIOS (5 tests)
# =====================================================================

class TestTier4RealWorldScenarios(AnkiNormalizerTestBase):
    """Tier 4: Realistic production exports from Daijirin, Kojien, JMdict, Jidoujisho, Yomichan."""

    def test_tier4_scenario_daijirin_polysemous_verb_kakeru(self):
        """Realistic Daijirin entry for polysemous verb 「かける」 (25 senses, ~9,500 chars HTML)."""
        defs = [
            MockFieldDef("Word", "text", identity_role="primary"),
            MockFieldDef("Reading", "text", identity_role="secondary"),
            MockFieldDef("Meaning", "text"),
        ]
        senses_html = []
        for i in range(1, 41):
            senses_html.append(
                f'<li class="sense-item" data-sense="{i}">'
                f'<span class="sense-num">({i})</span> '
                f'<span class="sense-def">物の表面に他の物を作用させる。薬をかける。アイロンをかける。目的に向けて行動を起こす。</span> '
                f'<span class="sense-sample">【用例】壁に絵をかける。命をかける。時間をかける。保険をかける。</span>'
                f'</li>'
            )
        daijirin_html = (
            '<div class="daijirin-entry">'
            '<header><span class="headword">かける【掛ける・懸ける】</span><span class="pos">下一動他</span></header>'
            f'<ol class="senses-list">{"".join(senses_html)}</ol>'
            '</div>'
        )
        self.assertGreater(len(daijirin_html), 7000)

        payload = {
            "Word": "<ruby>掛<rt>か</rt></ruby>ける",
            "Reading": "<ruby>掛<rt>か</rt></ruby>ける",
            "Meaning": daijirin_html,
        }
        res = normalize_anki_field_values(payload, defs)

        self.assertEqual(res["Word"], "掛ける")
        self.assertEqual(res["Reading"], "かける")
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))
        self.assertIn("壁に絵をかける", res["Meaning"])

    def test_tier4_scenario_kojien_unabridged_archaic_entry(self):
        """Realistic Kojien unabridged entry with classical Japanese citations and historical kana."""
        defs = [
            MockFieldDef("Word", "text", identity_role="primary"),
            MockFieldDef("Reading", "text", identity_role="secondary"),
            MockFieldDef("Meaning", "text"),
        ]
        kojien_html = (
            '<div class="kojien-entry">'
            '<h3>もののあはれ【物の哀れ】</h3>'
            '<p class="historical-orthography">歴史的仮名遣い：もののあはれ</p>'
            '<ol>'
            '<li><span>平安時代の文学理念の一。自然や人事に対して生じる、しみじみとした情感や感動。</span>'
            '<span class="source">「源氏物語」の主題とされる。本居宣長が「紫文要領」などで提唱。</span></li>'
            '<li><span>しみじみとした情趣。哀愁。</span></li>'
            '</ol>'
            '</div>'
        )
        payload = {
            "Word": "物の哀れ",
            "Reading": "もののあわれ",
            "Meaning": kojien_html,
        }
        res = normalize_anki_field_values(payload, defs)
        self.assertEqual(res["Word"], "物の哀れ")
        self.assertEqual(res["Reading"], "もののあわれ")
        self.assertIn("平安時代の文学理念の一", res["Meaning"])
        self.assertIn("源氏物語", res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier4_scenario_jmdict_40_sense_vocabulary_export(self):
        """Realistic JMdict 40-sense export with part-of-speech and cross-reference tags."""
        defs = [
            MockFieldDef("Word", "text", identity_role="primary"),
            MockFieldDef("Meaning", "text"),
        ]
        items = []
        for i in range(1, 41):
            items.append(f'<li><span class="pos">[v1, vt]</span> <span class="gloss">sense meaning {i}</span> <span class="xref">[See also: xref_{i}]</span></li>')
        jmdict_html = f'<ol class="jmdict">{"".join(items)}</ol>'

        res = normalize_anki_field_values({"Word": "取る", "Meaning": jmdict_html}, defs)
        self.assertEqual(res["Word"], "取る")
        self.assertLessEqual(len(res["Meaning"]), 5000)
        self.assertIn("sense meaning 1", res["Meaning"])
        self.assertIsNone(_HTML_TAG_RE.search(res["Meaning"]))

    def test_tier4_scenario_jidoujisho_yomitan_browser_popup(self):
        """Jidoujisho / Yomitan browser pop-up export with subtitle context and cloze."""
        payload = {
            "note": {
                "deckName": "Default",
                "modelName": "Yomitan Standard",
                "fields": {
                    "Word": "<ruby>約束<rt>やくそく</rt></ruby>",
                    "Reading": "<ruby>約束<rt>やくそく</rt></ruby>",
                    "Meaning": "<ol><li><span>promise; agreement; arrangement</span></li></ol>",
                    "Sentence": "君との<b><ruby>約束<rt>やくそく</rt></ruby></b>は忘れない。",
                    "Pitch": '<ol><li><span>やくそく</span> [0]</li></ol>',
                },
                "tags": ["anime", "subtitle", "jidoujisho"],
            }
        }
        res = self._rpc("addNote", payload)
        if isinstance(res, dict) and "error" in res:
            self.fail(f"addNote failed with error: {res['error']}")
        note_id = res

        with self.app.app_context():
            note = Note.query.get(note_id)
            fields = note.field_values
            self.assertEqual(fields["Word"], "約束")
            self.assertEqual(fields["Reading"], "やくそく")
            self.assertEqual(fields["Sentence"], "君との約束は忘れない。")
            self.assertIn("promise; agreement", fields["Meaning"])

    def test_tier4_scenario_yomichan_legacy_sound_bracket_payload(self):
        """Yomichan legacy payload with sound tag [sound:...] and bracket furigana."""
        defs = [
            MockFieldDef("Word", "text", identity_role="primary"),
            MockFieldDef("Reading", "text", identity_role="secondary"),
            MockFieldDef("Meaning", "text"),
            MockFieldDef("Audio", "audio"),
        ]
        payload = {
            "Word": "猫[ねこ]",
            "Reading": "ねこ",
            "Meaning": "cat<br>feline animal",
            "Audio": "[sound:yomichan_neko.mp3]",
        }
        res = normalize_anki_field_values(payload, defs)
        self.assertEqual(res["Word"], "猫[ねこ]")
        self.assertEqual(res["Reading"], "ねこ")
        self.assertEqual(res["Meaning"], "cat\nfeline animal")
        # Audio media reference must be preserved intact
        self.assertEqual(res["Audio"], "[sound:yomichan_neko.mp3]")


if __name__ == "__main__":
    unittest.main()
