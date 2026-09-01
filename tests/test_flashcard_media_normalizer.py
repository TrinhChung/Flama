"""Unit tests for typed media migration decisions."""

import unittest
from types import SimpleNamespace

from app.services.flashcard_media_normalizer import (
    classify_media_field_value,
    normalize_media_field_value,
    normalize_single_media_reference,
)
from app.services.media_field_codec import (
    MediaFieldValueError,
    build_media_reference_lookup,
    is_canonical_media_url,
    normalize_media_reference_for_write,
)


class FlashcardMediaNormalizerTests(unittest.TestCase):
    def test_empty_values(self):
        self.assertEqual(normalize_single_media_reference(""), "")
        self.assertEqual(normalize_media_field_value(None), "")

    def test_https_and_managed_urls_are_preserved_by_type(self):
        self.assertEqual(
            normalize_single_media_reference("https://example.com/audio.mp3", field_type="audio"),
            "https://example.com/audio.mp3",
        )
        self.assertEqual(
            normalize_single_media_reference("https://example.com/image.png", field_type="image"),
            "https://example.com/image.png",
        )
        self.assertEqual(
            normalize_single_media_reference("/media/library/stroke_ja_4e00.svg", field_type="diagram"),
            "/media/library/stroke_ja_4e00.svg",
        )

    def test_sound_syntax_and_filename_resolve_to_proxy(self):
        asset = SimpleNamespace(id="asset-xyz", filename="sound.wav", mime_type="audio/wav")
        lookup = build_media_reference_lookup([asset])
        self.assertEqual(
            normalize_single_media_reference("[sound:sound.wav]", lookup, field_type="audio"),
            "/media/proxy/asset-xyz",
        )
        self.assertEqual(
            normalize_single_media_reference("sound.wav", lookup, field_type="audio"),
            "/media/proxy/asset-xyz",
        )

    def test_external_sound_url_is_extracted(self):
        self.assertEqual(
            normalize_single_media_reference(
                "[sound:https://example.com/sound.mp3]",
                field_type="audio",
            ),
            "https://example.com/sound.mp3",
        )

    def test_html_image_urls_are_extracted_in_order(self):
        decision = classify_media_field_value(
            '<div><img src="https://example.com/1.png"><img src="/media/library/stroke_ja_4e00.svg"></div>',
            field_type="diagram",
        )
        self.assertEqual(decision.action, "normalize")
        self.assertEqual(
            decision.value,
            "https://example.com/1.png\n/media/library/stroke_ja_4e00.svg",
        )

    def test_html_with_insecure_media_is_quarantined_without_mutation(self):
        raw = '<img src="http://cdn.example.com/legacy.png">'
        decision = classify_media_field_value(raw, field_type="image")
        self.assertEqual(decision.action, "quarantine")
        self.assertEqual(decision.reason, "insecure_http")
        self.assertEqual(decision.value, raw)

    def test_managed_library_url_rejects_path_traversal(self):
        self.assertFalse(is_canonical_media_url("/media/library/../../secret.png"))

    def test_only_explicitly_allowlisted_staged_filename_is_accepted(self):
        self.assertEqual(
            normalize_media_reference_for_write(
                "pending.mp3",
                field_type="audio",
                reference_lookup={"pending.mp3"},
            ),
            "pending.mp3",
        )
        with self.assertRaises(MediaFieldValueError):
            normalize_media_reference_for_write(
                "other.mp3",
                field_type="audio",
                reference_lookup={"pending.mp3"},
            )

    def test_image_html_in_audio_field_is_cleared(self):
        decision = classify_media_field_value(
            '<img src="https://example.com/image.png">',
            field_type="audio",
        )
        self.assertEqual(decision.action, "clear")
        self.assertEqual(decision.reason, "wrong_media_kind")
        self.assertEqual(decision.value, "")
        self.assertTrue(decision.semantic_change)

    def test_correct_kind_missing_binary_is_quarantined_not_deleted(self):
        decision = classify_media_field_value("missing.wav", field_type="audio")
        self.assertEqual(decision.action, "quarantine")
        self.assertEqual(decision.reason, "missing_binary")
        self.assertEqual(decision.value, "missing.wav")

    def test_wrong_kind_and_plain_values_are_cleared(self):
        wrong_kind = classify_media_field_value("photo.png", field_type="audio")
        plain = classify_media_field_value("not media", field_type="image")
        literal_null = classify_media_field_value("null", field_type="diagram")
        self.assertEqual(wrong_kind.action, "clear")
        self.assertEqual(plain.action, "clear")
        self.assertEqual(literal_null.action, "clear")

    def test_unresolved_uuid_is_quarantined_without_fabricating_proxy(self):
        uuid_value = "12345678-1234-1234-1234-123456789abc"
        decision = classify_media_field_value(uuid_value, field_type="audio")
        self.assertEqual(decision.action, "quarantine")
        self.assertEqual(decision.value, uuid_value)

    def test_multiline_values_are_deduplicated(self):
        raw = "https://example.com/1.jpg\nhttps://example.com/1.jpg\nhttps://example.com/2.jpg"
        self.assertEqual(
            normalize_media_field_value(raw, field_type="image"),
            "https://example.com/1.jpg\nhttps://example.com/2.jpg",
        )

    def test_legacy_json_url_array_becomes_newline_contract(self):
        decision = classify_media_field_value(
            '["https://example.com/1.png", "/media/library/stroke_ja_4e00.svg"]',
            field_type="image",
        )
        self.assertEqual(decision.action, "normalize")
        self.assertEqual(
            decision.value,
            "https://example.com/1.png\n/media/library/stroke_ja_4e00.svg",
        )

    def test_legacy_json_array_with_missing_binary_is_quarantined_unchanged(self):
        raw = '["missing.png"]'
        decision = classify_media_field_value(raw, field_type="image")
        self.assertEqual(decision.action, "quarantine")
        self.assertEqual(decision.value, raw)


if __name__ == "__main__":
    unittest.main()
