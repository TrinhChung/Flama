"""Built-in preview media are deterministic, playable and independent of storage."""

from io import BytesIO
import unittest
import wave
from xml.etree import ElementTree

from app.services.template_preview_sample_service import preview_sample_media


class TemplatePreviewSampleTests(unittest.TestCase):
    def test_audio_is_a_small_valid_pcm_wave(self):
        data, mime, filename = preview_sample_media("sample-audio")
        self.assertEqual(mime, "audio/wav")
        self.assertTrue(filename.endswith(".wav"))
        with wave.open(BytesIO(data), "rb") as audio:
            self.assertEqual(audio.getnchannels(), 1)
            self.assertEqual(audio.getsampwidth(), 2)
            self.assertGreater(audio.getnframes(), 0)
            self.assertLessEqual(audio.getnframes() / audio.getframerate(), 1)
            self.assertTrue(any(audio.readframes(audio.getnframes())))
        self.assertLess(len(data), 16_000)

    def test_svg_samples_have_no_active_or_external_content(self):
        for sample in ("sample-image", "sample-diagram"):
            data, mime, _ = preview_sample_media(sample)
            self.assertEqual(mime, "image/svg+xml")
            root = ElementTree.fromstring(data)
            self.assertEqual(root.tag, "{http://www.w3.org/2000/svg}svg")
            for element in root.iter():
                self.assertNotIn(element.tag.rsplit("}", 1)[-1], ("script", "image", "foreignObject"))
                self.assertFalse(any(name.startswith("on") or name.endswith("href") for name in element.attrib))

    def test_user_asset_ids_do_not_resolve_to_a_sample(self):
        for asset_id in ("", "sample-image-other", "../sample-image", "some-user-asset"):
            self.assertIsNone(preview_sample_media(asset_id))


if __name__ == "__main__":
    unittest.main()
