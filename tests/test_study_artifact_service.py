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


if __name__ == "__main__":
    unittest.main()
