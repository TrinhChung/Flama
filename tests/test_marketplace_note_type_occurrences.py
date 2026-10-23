"""Published occurrence selection tests without database or provider fixtures."""

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from flask import Flask

from app.api.v1.marketplace.note_types import marketplace_note_types_bp
from app.services import marketplace_note_type_service as service


class MarketplaceOccurrencePreviewTests(unittest.TestCase):
    def setUp(self):
        self.note_type = SimpleNamespace(id="note-type")
        self.definition = {"release_available": True, "field_defs": [
            {"id": "field-a", "name": "Front", "field_type": "text"},
            {"id": "field-b", "name": "Back", "field_type": "text"},
        ], "templates": [
            {"id": "source-template", "application_id": "application-a", "input_bindings": {"word": "field-a"}},
            {"id": "source-template", "application_id": "application-b", "input_bindings": {"word": "field-b"}},
        ]}
        for mocked in (
            patch.object(service, "_get_shared_note_type_for_view", return_value=self.note_type),
            patch("app.services.note_type_release_service.released_definition", return_value=self.definition),
        ):
            mocked.start()
            self.addCleanup(mocked.stop)
        self.renderer = patch.object(service, "render_template_pair", side_effect=lambda **kw: {
            "front_html": kw["template"].input_bindings["word"], "back_html": "back",
        }).start()
        self.addCleanup(patch.stopall)

    def preview(self, **values):
        return service.preview_shared_note_type_template(user_id=9, note_type_id="note-type",
            template_id="source-template", **values)

    def test_second_occurrence_uses_its_own_mapping(self):
        result = self.preview(application_id="application-b")
        self.assertEqual(result["front_html"], "field-b")
        self.assertEqual(self.renderer.call_args.kwargs["preview_note_key"],
            "shared-preview:note-type:application-b")

    def test_ambiguous_source_requires_explicit_occurrence(self):
        with self.assertRaises(service.MarketplaceNoteTypeError) as caught:
            self.preview()
        self.assertEqual((caught.exception.error, caught.exception.status), ("APPLICATION_SELECTION_REQUIRED", 409))
        self.renderer.assert_not_called()

    def test_occurrence_cannot_select_another_source_or_note_type(self):
        for application in ("different-note-type-app", "wrong-template-app"):
            with self.subTest(application=application), self.assertRaises(service.MarketplaceNoteTypeError) as caught:
                self.preview(application_id=application)
            self.assertEqual(caught.exception.status, 404)
        self.renderer.assert_not_called()

    def test_unique_occurrence_retains_empty_body_compatibility(self):
        self.definition["templates"] = self.definition["templates"][:1]
        self.assertEqual(self.preview()["front_html"], "field-a")

    def test_invalid_occurrence_input_is_rejected(self):
        for value in ("", " ", 1, [], "x" * 37):
            with self.subTest(value=value), self.assertRaises(service.MarketplaceNoteTypeError) as caught:
                self.preview(application_id=value)
            self.assertEqual((caught.exception.status, caught.exception.field), (400, "application_id"))

    def test_route_passes_occurrence_and_rejects_non_object(self):
        app = Flask(__name__)
        app.config.update(TESTING=True, LOGIN_DISABLED=True)
        app.register_blueprint(marketplace_note_types_bp, url_prefix="/api")
        client = app.test_client()
        url = "/api/marketplace/note-types/note-type/templates/source-template/preview"
        with patch("app.api.v1.marketplace.note_types.current_user", SimpleNamespace(id=9)):
            selected = client.post(url, json={"application_id": "application-b"})
            self.assertEqual(selected.status_code, 200)
            self.assertEqual(selected.get_json()["front_html"], "field-b")
            for invalid in (["application-b"], "application-b", 5):
                rejected = client.post(url, json=invalid)
                self.assertEqual(rejected.status_code, 400)


if __name__ == "__main__":
    unittest.main()
