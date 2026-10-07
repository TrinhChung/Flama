"""Compatibility parity for the Card presentation-source seam (CT-04)."""

import hashlib
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.presenters import vocabulary_presenter
from app.repositories import vocabulary_repository
from app.services import study_artifact_service
from app.services.effective_template_service import resolve_effective_template
from app.services.flashcard_renderer import render_template_pair


class EffectiveTemplateServiceTests(unittest.TestCase):
    def _make_card(self, suffix="owned"):
        fields = [
            SimpleNamespace(id="field-word", name="Word", field_type="text", required=True, position=0),
            SimpleNamespace(id="field-meaning", name="Meaning", field_type="richtext", required=False, position=1),
        ]
        note_type = SimpleNamespace(id="type-source", field_defs=fields)
        note = SimpleNamespace(
            id=f"note-{suffix}", note_type_id=note_type.id, note_type=note_type,
            field_values={"Word": "犬", "Meaning": "<strong>dog</strong>"}, media_assets=[],
        )
        template = SimpleNamespace(
            id=f"template-{suffix}", name="Card 1", note_type_id=note_type.id,
            front_html="<div>{{Word}}</div>",
            back_html='<div>{{Meaning}}</div><script>window.ready = true</script>',
            shared_css=".card { color: red; }", updated_at="2026-10-07T00:00:00",
        )
        return SimpleNamespace(id=f"card-{suffix}", template_id=template.id, template=template, note=note)

    def _scope(self):
        return SimpleNamespace(install=SimpleNamespace(id="install-1", source_note_type_id="type-source"))

    def _assert_compatibility(self, context, card, fields, values):
        legacy = study_artifact_service.EffectiveStudyCard(
            card=card, note=card.note, template=card.template,
            field_defs=fields, field_values=values, clone_scope=context.clone_scope,
        )
        self.assertIs(context.template, card.template)
        # Independently freeze the current artifact version material so a seam
        # change cannot silently change IDs, renderer ABI, or overlay hashing.
        raw = {
            "schema_version": "study-template.v1", "renderer_abi": "flama-client-mustache.v2",
            "template_id": card.template.id, "front_source": card.template.front_html,
            "back_source": card.template.back_html, "shared_css": card.template.shared_css,
            "field_defs": [{"id": field.id, "name": field.name, "field_type": field.field_type,
                            "required": field.required, "position": field.position} for field in fields],
        }
        expected_version = "sha256-" + hashlib.sha256(json.dumps(
            raw, sort_keys=True, separators=(",", ":"), ensure_ascii=False,
        ).encode("utf-8")).hexdigest()
        self.assertEqual(study_artifact_service.template_version(context), expected_version)
        self.assertEqual(study_artifact_service.build_template_artifact(context),
                         study_artifact_service.build_template_artifact(legacy))
        self.assertEqual(study_artifact_service.build_content_artifact(context),
                         study_artifact_service.build_content_artifact(legacy))
        actual_render = render_template_pair(
            template=context.template, field_defs=context.field_defs,
            field_values=context.field_values, media_assets=card.note.media_assets,
        )
        self.assertEqual(actual_render, render_template_pair(
            template=card.template, field_defs=fields, field_values=values, media_assets=card.note.media_assets,
        ))

    def test_owned_artifacts_and_server_render_preserve_sources_ids_and_hashes(self):
        card = self._make_card()
        context = study_artifact_service.build_effective_study_card(card=card, clone_scope=None)
        self._assert_compatibility(context, card, card.note.note_type.field_defs, dict(card.note.field_values))
        self.assertIsNone(context.install_id)

    def test_installed_overlay_preserves_effective_fields_values_and_artifact_hashes(self):
        card = self._make_card("overlay")
        scope = self._scope()
        fields = [SimpleNamespace(**vars(field)) for field in card.note.note_type.field_defs]
        fields[0].field_type = "richtext"
        values = {"Word": "<em>猫</em>", "Meaning": "cat"}
        override_rows = [SimpleNamespace(id="overlay-value")]
        with patch.object(study_artifact_service.flashcards_share_service, "build_clone_schema_view",
                          return_value=SimpleNamespace(field_defs=fields)) as schema, \
             patch.object(study_artifact_service.flashcards_share_service, "apply_clone_note_field_overrides",
                          return_value=values) as overlays, \
             patch.object(study_artifact_service.flashcards_share_service, "is_clone_added_note") as added_lookup:
            context = study_artifact_service.build_effective_study_card(
                card=card, clone_scope=scope, clone_added_note_ids=frozenset(),
                note_override_rows_by_note_id={card.note.id: override_rows}, template_overrides={},
            )
        self._assert_compatibility(context, card, fields, values)
        self.assertIs(context.clone_scope, scope)
        self.assertEqual(context.install_id, "install-1")
        self.assertEqual(card.note.field_values["Word"], "犬")
        schema.assert_called_once()
        self.assertEqual(overlays.call_args.kwargs["note_override_rows"], override_rows)
        added_lookup.assert_not_called()

    def test_local_added_note_keeps_local_content_and_does_not_apply_source_overlay(self):
        card = self._make_card("local-added")
        with patch.object(study_artifact_service.flashcards_share_service, "build_clone_schema_view") as schema, \
             patch.object(study_artifact_service.flashcards_share_service, "apply_clone_note_field_overrides") as overlays, \
             patch("app.services.study_artifact_service.resolve_effective_template",
                   wraps=resolve_effective_template) as resolver:
            context = study_artifact_service.build_effective_study_card(
                card=card, clone_scope=self._scope(), clone_added_note_ids=frozenset({card.note.id}),
            )
        self._assert_compatibility(context, card, card.note.note_type.field_defs, dict(card.note.field_values))
        self.assertIsNone(context.clone_scope)
        self.assertEqual(len(resolver.call_args.args), 1)
        schema.assert_not_called()
        overlays.assert_not_called()

    def test_batch_source_changes_new_artifact_without_mutating_source_or_frozen_artifact(self):
        card = self._make_card("override")
        original = study_artifact_service.build_effective_study_card(card=card, clone_scope=None)
        frozen_artifact = study_artifact_service.build_template_artifact(original)
        replacement = SimpleNamespace(**vars(card.template))
        replacement.front_html = "<b>{{Word}}</b>"
        overrides = {card.template.id: replacement}
        with patch.object(study_artifact_service.flashcards_share_service, "build_clone_schema_view") as schema:
            resolved = study_artifact_service.build_effective_study_card(
                card=card, clone_scope=None, template_overrides=overrides,
            )
        artifact = study_artifact_service.build_template_artifact(resolved)
        self.assertIs(resolved.template, replacement)
        self.assertEqual(artifact["id"], card.template_id)
        self.assertNotEqual(artifact["version"], frozen_artifact["version"])
        self.assertEqual(frozen_artifact["front_source"], "<div>{{Word}}</div>")
        self.assertEqual(card.template.front_html, "<div>{{Word}}</div>")
        self.assertEqual(study_artifact_service.content_version(original),
                         study_artifact_service.content_version(resolved))
        schema.assert_not_called()

    def test_no_override_follows_original_and_wrong_identity_is_rejected(self):
        card = self._make_card("identity")
        for overrides in (None, {}, {card.template_id: None}):
            self.assertIs(resolve_effective_template(card, self._scope(), template_overrides=overrides), card.template)
        with self.assertRaisesRegex(ValueError, "preserve the source Template ID"):
            resolve_effective_template(card, template_overrides={card.template_id: SimpleNamespace(id="fork-id")})
        self.assertIsNone(resolve_effective_template(SimpleNamespace(template=None)))

    def test_browse_render_helpers_share_the_source_seam_and_preserve_renderer_payload(self):
        for module in (vocabulary_repository, vocabulary_presenter):
            with self.subTest(module=module.__name__):
                card = self._make_card(module.__name__)
                baseline = render_template_pair(
                    template=card.template, field_defs=card.note.note_type.field_defs,
                    field_values=card.note.field_values, media_assets=[], preview_note_key=card.note.id,
                )
                expected = {"front": baseline["front_html"], "back": baseline["back_html"],
                            "front_payload": baseline["front_renderer_payload"],
                            "back_payload": baseline["back_renderer_payload"]}
                self.assertEqual(module.render_note_study_flashcard(card), expected)
                replacement = SimpleNamespace(**vars(card.template))
                replacement.front_html = "<b>{{Word}}</b>"
                rendered = module.render_note_study_flashcard(
                    card, clone_scope=self._scope(), template_overrides={card.template_id: replacement},
                )
                self.assertIn("<b>犬</b>", rendered["front"])
                self.assertEqual(card.template.front_html, "<div>{{Word}}</div>")


if __name__ == "__main__":
    unittest.main()
