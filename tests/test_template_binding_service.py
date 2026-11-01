"""Input binding projection, media safety, and immutable artifact parity."""

from dataclasses import replace
import unittest
from types import SimpleNamespace
from uuid import UUID

from app.services import study_artifact_service
from app.services.effective_template_service import resolve_effective_template
from app.services.flashcard_renderer import build_render_context, render_template_pair
from app.services.template_binding_service import (
    apply_binding_projection, binding_warnings, prepare_bound_fields,
)


class TemplateBindingServiceTests(unittest.TestCase):
    def _field(self, field_id, name, field_type="text", position=0):
        return SimpleNamespace(id=field_id, name=name, field_type=field_type, position=position, required=False)

    def _template(self, schema=None, bindings=None, front="{{term}}", back="{{answer}}"):
        return SimpleNamespace(
            id="template-source", name="Card", front_html=front, back_html=back,
            shared_css="", updated_at="2026-10-07", input_schema=schema or [], input_bindings=bindings,
        )

    def _context(self, template, fields, values, media=None):
        note = SimpleNamespace(id="note-source", field_values=dict(values), media_assets=media or [],
                               note_type_id="type-source", note_type=SimpleNamespace(field_defs=fields))
        card = SimpleNamespace(id="card-source", template_id=template.id, template=template, note=note)
        return study_artifact_service.EffectiveStudyCard(
            card=card, note=note, template=template, field_defs=fields, field_values=dict(values),
        )

    def test_rename_tracks_field_id_while_storage_sources_remain_unchanged(self):
        field = self._field("field-stable", "Word")
        template = self._template([{ "key": "term", "type": "text", "required": True }],
                                  {"term": field.id}, back="")
        original_sources = template.front_html, template.back_html, template.shared_css
        before = render_template_pair(template=template, field_defs=[field], field_values={"Word": "犬"})
        field.name = "Expression"
        after = render_template_pair(template=template, field_defs=[field], field_values={"Expression": "猫"})
        self.assertEqual(before["front_html"], "犬")
        self.assertEqual(after["front_html"], "猫")
        self.assertEqual(original_sources, (template.front_html, template.back_html, template.shared_css))
        self.assertEqual(template.input_bindings, {"term": "field-stable"})

    def test_unbound_and_stale_inputs_shadow_real_fields_and_helper_values(self):
        fields = [self._field("real-term", "term"), self._field("real-answer", "answer"),
                  self._field("real-extra", "extra"), self._field("real-url", "term_url", position=1)]
        template = self._template(
            [{"key": "term", "type": "audio", "required": True},
             {"key": "answer", "type": "text", "required": False}],
            {"answer": "removed-field"}, front='<audio src="{{term}}"></audio>{{answer}}', back="",
        )
        values = {"term": "secret.mp3", "term_url": "/media/proxy/secret", "answer": "SECRET", "extra": "kept"}
        projected_fields, projected_values = prepare_bound_fields(template, fields, values)
        context = build_render_context(projected_fields, projected_values, [])
        self.assertEqual(context["term"], "")
        self.assertEqual(context["term_url"], "")
        self.assertEqual(context["term_urls"], [])
        self.assertEqual(context["answer"], "")
        self.assertEqual(context["extra"], "kept")
        self.assertEqual(values["answer"], "SECRET")
        self.assertEqual(len([field for field in projected_fields if field.name == "term"]), 1)
        self.assertEqual({warning["code"] for warning in binding_warnings(template, fields)},
                         {"REQUIRED_INPUT_UNBOUND", "INPUT_FIELD_NOT_FOUND"})
        rendered = render_template_pair(template=template, field_defs=fields, field_values=values)
        self.assertNotIn("SECRET", rendered["front_html"])
        self.assertNotIn("/media/proxy/secret", rendered["front_html"])

    def test_bound_media_uses_existing_proxy_resolution_and_client_safe_url_compilation(self):
        fields = [self._field("audio-field", "Sound", "audio"),
                  self._field("image-field", "Picture", "image", position=1)]
        template = self._template(
            [{"key": "voice", "type": "audio"}, {"key": "image", "type": "image"}],
            {"voice": "audio-field", "image": "image-field"},
            front='<audio src="{{voice}}"></audio><img src="{{image}}">', back="{{voice}}",
        )
        media = [SimpleNamespace(id="audio-asset", filename="sound.mp3", field_name="Sound",
                                 mime_type="audio/mpeg", sha256="audio-hash"),
                 SimpleNamespace(id="image-asset", filename="picture.png", field_name="Picture",
                                 mime_type="image/png", sha256="image-hash")]
        context = self._context(template, fields, {"Sound": "sound.mp3", "Picture": "picture.png"}, media)
        artifact = study_artifact_service.build_template_artifact(context)
        content = study_artifact_service.build_content_artifact(context)
        self.assertIn('src="{{voice_url}}"', artifact["front_source"])
        self.assertIn('src="{{image_url}}"', artifact["front_source"])
        self.assertEqual(content["render_context"]["voice_url"], "/store/audio-asset")
        self.assertEqual(content["render_context"]["image_url"], "/store/image-asset")
        rendered = render_template_pair(template=template, field_defs=fields,
                                        field_values=context.field_values, media_assets=media)
        self.assertIn('src="/store/audio-asset"', rendered["front_html"])
        self.assertIn('src="/store/image-asset"', rendered["front_html"])
        self.assertEqual(rendered["front_renderer_payload"]["allowed_audio_asset_ids"], ["audio-asset"])
        self.assertEqual(template.front_html, '<audio src="{{voice}}"></audio><img src="{{image}}">')

    def test_media_binding_rejects_unsafe_url_values(self):
        template = self._template([{"key": "voice", "type": "audio"}], {"voice": "audio"},
                                  front='<audio src="{{voice}}"></audio>', back="{{voice}}")
        for value in ("javascript:alert(1)", "data:text/html,evil"):
            with self.subTest(value=value):
                result = render_template_pair(template=template, field_defs=[self._field("audio", "Sound", "audio")],
                                              field_values={"Sound": value}, media_assets=[])
                self.assertNotIn(value, result["front_html"] + result["back_html"])
                self.assertEqual(result["front_renderer_payload"]["allowed_audio_urls"], [])
        permitted = render_template_pair(
            template=template, field_defs=[self._field("audio", "Sound", "audio")],
            field_values={"Sound": "https://media.example/sound.mp3"}, media_assets=[],
        )
        self.assertEqual(permitted["front_renderer_payload"]["allowed_audio_urls"],
                         ["https://media.example/sound.mp3"])

    def test_richtext_and_markdown_aliases_still_use_sanitization(self):
        fields = [self._field("rich", "Meaning", "richtext"), self._field("md", "Example", "markdown", 1)]
        template = self._template([{"key": "term", "type": "richtext"}, {"key": "answer", "type": "markdown"}],
                                  {"term": "rich", "answer": "md"})
        result = render_template_pair(template=template, field_defs=fields,
                                      field_values={"Meaning": '<b>dog</b><script>alert(1)</script>',
                                                    "Example": "**safe** <img src=\"javascript:alert(1)\">"})
        self.assertIn("<b>dog</b>", result["front_html"])
        self.assertIn("<strong>safe</strong>", result["back_html"])
        self.assertNotIn("<script", result["front_html"])
        self.assertNotIn("<img", result["back_html"])
        self.assertIn("&lt;img", result["back_html"])

    def test_duplicate_target_aliases_have_unique_stable_uuid_ids(self):
        fields = [self._field("word", "Word")]
        template = self._template([{"key": "term", "type": "text"}, {"key": "answer", "type": "text"}],
                                  {"term": "word", "answer": "word"})
        first, values = prepare_bound_fields(template, fields, {"Word": "犬"})
        second, _ = prepare_bound_fields(template, fields, {"Word": "犬"})
        self.assertEqual([field.id for field in first], [field.id for field in second])
        self.assertEqual(len({field.id for field in first}), len(first))
        for field in first[1:]:
            self.assertEqual(UUID(field.id).version, 5)
        self.assertEqual(values["term"], values["answer"])

    def test_identity_bindings_preserve_legacy_and_declared_schema_fields_values_hashes(self):
        fields = [self._field("field-word", "Word")]
        values = {"Word": "犬"}
        for schema in ([], [{"key": "Word", "type": "text"}]):
            with self.subTest(schema=schema):
                template = self._template(schema, {"Word": "field-word"}, front="{{Word}}", back="")
                result_fields, result_values = prepare_bound_fields(template, fields, values)
                self.assertIs(result_fields, fields)
                self.assertIs(result_values, values)
                bound = self._context(template, fields, values)
                legacy_template = SimpleNamespace(**{**vars(template), "input_schema": [], "input_bindings": None})
                legacy = replace(bound, template=legacy_template)
                self.assertEqual(study_artifact_service.template_version(bound), study_artifact_service.template_version(legacy))
                self.assertEqual(study_artifact_service.build_template_artifact(bound),
                                 study_artifact_service.build_template_artifact(legacy))

    def test_rebinding_changes_hash_even_with_same_values_and_preserves_frozen_context(self):
        fields = [self._field("one", "Word"), self._field("two", "Reading", position=1)]
        template = self._template([{"key": "term", "type": "text"}], {"term": "one"}, back="")
        context = apply_binding_projection(self._context(template, fields, {"Word": "same", "Reading": "same"}))
        frozen = study_artifact_service.build_template_artifact(context)
        frozen_content = study_artifact_service.build_content_artifact(context)
        replacement = SimpleNamespace(**{**vars(template), "input_bindings": {"term": "two"}})
        changed = apply_binding_projection(replace(context, template=replacement))
        self.assertNotEqual(study_artifact_service.template_version(context), study_artifact_service.template_version(changed))
        self.assertNotEqual(study_artifact_service.content_version(context), study_artifact_service.content_version(changed))
        self.assertEqual(study_artifact_service.build_template_artifact(context), frozen)
        self.assertEqual(study_artifact_service.build_content_artifact(context), frozen_content)
        self.assertIs(apply_binding_projection(context), context)
        self.assertEqual(template.input_bindings, {"term": "one"})

    def test_projection_metadata_detaches_source_fields_and_hashes_mapping(self):
        fields = [self._field("one", "Word"), self._field("two", "Reading", position=1)]
        template = self._template([{"key": "term", "type": "text"}], {"term": "one"}, back="")
        context = apply_binding_projection(self._context(template, fields, {"Word": "dog"}))
        artifact = study_artifact_service.build_template_artifact(context)
        projection = artifact["binding_projection"]
        material = {key: value for key, value in projection.items() if key != "fingerprint"}
        self.assertEqual(projection["fingerprint"], study_artifact_service.canonical_digest(material))
        self.assertEqual(projection["input_bindings"], {"term": "one"})
        self.assertEqual(projection["field_defs"][0]["name"], "Word")
        fields[0].name = "Renamed"
        self.assertEqual(study_artifact_service.build_template_artifact(context), artifact)

    def test_resolver_uses_owned_application_or_pinned_application_bindings_without_mutation(self):
        fields = [self._field("one", "Word"), self._field("two", "Meaning", position=1)]
        template = self._template([{"key": "term", "type": "text"}], front="{{term}}", back="")
        context = self._context(template, fields, {"Word": "犬", "Meaning": "dog"})
        card = context.card
        card.application_id = "app-source"
        card.application = SimpleNamespace(id=card.application_id, input_bindings={"term": "one"})
        owned = resolve_effective_template(card)
        self.assertEqual(owned.input_bindings, {"term": "one"})
        pinned = SimpleNamespace(id=template.id, front_html="{{term}}", back_html="", shared_css="",
                                 input_schema=template.input_schema,
                                 applications_json={"app-source": {"input_bindings": {"term": "two"}}})
        resolved = resolve_effective_template(card, template_overrides={template.id: pinned})
        self.assertEqual(resolved.input_bindings, {"term": "two"})
        self.assertEqual(resolved.id, template.id)
        self.assertEqual(resolved.name, "Card")
        resolved.input_bindings["term"] = "changed-copy"
        self.assertEqual(pinned.applications_json["app-source"]["input_bindings"], {"term": "two"})
        self.assertEqual(card.application.input_bindings, {"term": "one"})
        self.assertIsNone(template.input_bindings)

    def test_preview_cache_invalidates_when_content_or_binding_changes(self):
        fields = [self._field("one", "Word"), self._field("two", "Reading", position=1)]
        template = self._template([{"key": "term", "type": "text"}], {"term": "one"}, back="")
        first = render_template_pair(template=template, field_defs=fields,
                                     field_values={"Word": "犬", "Reading": "いぬ"}, preview_note_key="binding-cache-note")
        edited = render_template_pair(template=template, field_defs=fields,
                                      field_values={"Word": "猫", "Reading": "ねこ"}, preview_note_key="binding-cache-note")
        template.input_bindings = {"term": "two"}
        rebound = render_template_pair(template=template, field_defs=fields,
                                       field_values={"Word": "猫", "Reading": "ねこ"}, preview_note_key="binding-cache-note")
        self.assertEqual((first["front_html"], edited["front_html"], rebound["front_html"]), ("犬", "猫", "ねこ"))


if __name__ == "__main__":
    unittest.main()
