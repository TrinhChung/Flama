import unittest
from types import SimpleNamespace

from app.services import study_artifact_service


class StudyArtifactServiceTest(unittest.TestCase):
    def make_context(self):
        field_defs = [
            SimpleNamespace(
                id="field-1",
                name="Word",
                field_type="text",
                required=True,
                position=0,
            ),
            SimpleNamespace(
                id="field-2",
                name="Meaning",
                field_type="richtext",
                required=False,
                position=1,
            ),
        ]
        note_type = SimpleNamespace(field_defs=field_defs)
        note = SimpleNamespace(
            id="note-1",
            note_type=note_type,
            field_values={"Word": "犬", "Meaning": "<strong>dog</strong>"},
            media_assets=[],
        )
        template = SimpleNamespace(
            id="template-1",
            front_html="<div>{{Word}}</div>",
            back_html="<div>{{Meaning}}</div><script>window.ready = true</script>",
            shared_css=".card { color: red; }",
        )
        card = SimpleNamespace(id="card-1", note=note, template=template)
        return study_artifact_service.EffectiveStudyCard(
            card=card,
            note=note,
            template=template,
            field_defs=field_defs,
            field_values=dict(note.field_values),
        )

    def test_versions_change_independently(self):
        context = self.make_context()
        template_before = study_artifact_service.template_version(context)
        content_before = study_artifact_service.content_version(context)

        context.field_values["Word"] = "猫"
        self.assertEqual(
            template_before,
            study_artifact_service.template_version(context),
        )
        self.assertNotEqual(
            content_before,
            study_artifact_service.content_version(context),
        )

    def test_template_artifact_defers_mustache_and_separates_script(self):
        artifact = study_artifact_service.build_template_artifact(self.make_context())
        self.assertIn("{{Word}}", artifact["front_source"])
        self.assertNotIn("<script", artifact["back_source"])
        self.assertNotIn("__FC_INLINE_SCRIPT_BLOCK_", artifact["back_source"])
        self.assertEqual(
            artifact["back_inline_scripts"],
            ["<script>window.ready = true</script>"],
        )

    def test_content_artifact_builds_safe_render_context(self):
        artifact = study_artifact_service.build_content_artifact(self.make_context())
        self.assertEqual(artifact["render_context"]["Word"], "犬")
        self.assertEqual(
            artifact["render_context"]["Meaning"],
            "<strong>dog</strong>",
        )

    def test_audio_custom_html_compiles_without_changing_template_or_note_fields(self):
        context = self.make_context()
        audio_field = SimpleNamespace(
            id="field-audio",
            name="word_audio",
            field_type="audio",
            required=False,
            position=2,
        )
        context.field_defs.append(audio_field)
        context.note.note_type.field_defs = context.field_defs
        context.field_values["word_audio"] = "word.mp3"
        context.note.field_values["word_audio"] = "word.mp3"
        context.note.media_assets = [SimpleNamespace(
            id="audio-1",
            field_name="word_audio",
            filename="word.mp3",
            mime_type="audio/mpeg",
            sha256="sha-audio",
        )]
        context.template.back_html = (
            '<audio id="voice" src="{{word_audio}}"></audio>'
            '<button onclick="document.getElementById(\'voice\').play()">🔊</button>'
            '<script>document.getElementById("voice").play()</script>'
        )
        original_template = context.template.back_html
        original_values = dict(context.note.field_values)

        template_artifact = study_artifact_service.build_template_artifact(context)
        content_artifact = study_artifact_service.build_content_artifact(context)

        self.assertEqual(context.template.back_html, original_template)
        self.assertEqual(context.note.field_values, original_values)
        self.assertEqual(template_artifact["renderer_abi"], "flama-client-mustache.v2")
        self.assertIn('src="{{word_audio}}"', template_artifact["back_source"])
        self.assertEqual(
            content_artifact["render_context"]["word_audio"],
            "/media/proxy/audio-1",
        )
        self.assertEqual(
            content_artifact["media"][0]["proxy_url"],
            "/media/proxy/audio-1",
        )


if __name__ == "__main__":
    unittest.main()
