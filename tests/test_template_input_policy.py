"""Pure validation/render contracts: storage is typed, template bindings are advisory."""

from types import SimpleNamespace
import unittest

from app.services.flashcard_content_service import ContentApiError, preview_raw_template
from app.services.template_binding_service import prepare_bound_fields
from app.validators.flashcard_input import RequestValidationError, clean_array_fields, clean_note_field_values
from app.validators.template_library import TemplateLibraryError, binding_warnings, validate_bindings
from models.field_types import FIELD_TYPES


class TemplateInputPolicyTests(unittest.TestCase):
    def test_every_field_type_can_bind_to_every_template_input(self):
        for source_type in FIELD_TYPES:
            field = SimpleNamespace(id="source", name="Source", field_type=source_type)
            for expected_type in FIELD_TYPES:
                with self.subTest(source=source_type, expected=expected_type):
                    schema = [{"key": "target", "type": expected_type, "required": True}]
                    mapping = {"target": field.id}
                    self.assertEqual(validate_bindings(schema, mapping, [field]), mapping)
                    warnings = binding_warnings(schema, mapping, [field])
                    self.assertEqual(len(warnings), int(source_type != expected_type))
                    if warnings:
                        self.assertEqual(warnings[0]["code"], "INPUT_TYPE_MISMATCH")

    def test_scope_and_schema_errors_remain_errors(self):
        schema = [{"key": "target", "type": "text"}]
        for mapping, code in [({"target": "foreign"}, "FIELD_OUT_OF_SCOPE"),
                              ({"unknown": None}, "INPUT_NOT_FOUND")]:
            with self.assertRaises(TemplateLibraryError) as raised:
                validate_bindings(schema, mapping, [])
            self.assertEqual(raised.exception.code, code)

    def test_projection_preserves_source_type_and_nested_list(self):
        value = ["one", ["two", ""], "one"]
        field = SimpleNamespace(id="source", name="Source", field_type="array", position=0)
        template = SimpleNamespace(id="template", input_schema=[{"key": "target", "type": "audio"}],
                                   input_bindings={"target": "source"})
        fields, values = prepare_bound_fields(template, [field], {"Source": value})
        self.assertIs(values["target"], value)
        self.assertEqual(next(item for item in fields if item.name == "target").field_type, "array")

    def test_direct_array_writes_require_lists_but_legacy_reads_and_imports_work(self):
        field = SimpleNamespace(id="a", name="Items", field_type="array", required=False)
        note_type = SimpleNamespace(field_defs=[field])
        for value in ("one\ntwo", '["one"]', 5, {}, None):
            with self.subTest(value=value), self.assertRaises(RequestValidationError):
                clean_note_field_values(note_type=note_type, raw_field_values={"Items": value}, partial=False)
        value = ["one", ["two", ""], "one"]
        values, _ = clean_note_field_values(note_type=note_type, raw_field_values={"Items": value}, partial=False)
        self.assertEqual(values["Items"], value)
        values, _ = clean_note_field_values(note_type=note_type, raw_field_values={}, partial=True,
                                           current_values={"Items": "legacy\ntext"})
        self.assertEqual(values["Items"], "legacy\ntext")
        self.assertEqual(clean_array_fields({"Items": "one\ntwo"}, [field])["Items"], ["one", "two"])

    def test_text_field_does_not_store_a_list_as_python_repr(self):
        note_type = SimpleNamespace(field_defs=[SimpleNamespace(name="Text", field_type="text", required=False)])
        with self.assertRaises(RequestValidationError):
            clean_note_field_values(note_type=note_type, raw_field_values={"Text": ["one"]}, partial=False)

    def test_preview_keeps_lists_despite_template_type_hints(self):
        for hint in FIELD_TYPES:
            with self.subTest(hint=hint):
                result = preview_raw_template(payload={
                    "front_html": "{{#target}}[{{.}}]{{/target}}", "back_html": "",
                    "fields": [{"name": "target", "field_type": hint}],
                    "field_values": {"target": ["one", "two"]},
                })
                self.assertEqual(result["front_html"], "[one][two]")

    def test_preview_rejects_invalid_items_and_unsafe_or_oversized_arrays(self):
        for value in ([{}], [5], [[[["deep"]]]], ["<script>alert(1)</script>"], ["x" * 100_001]):
            with self.subTest(value_type=type(value).__name__), self.assertRaises(ContentApiError):
                preview_raw_template(payload={"front_html": "{{target}}",
                    "fields": [{"name": "target", "field_type": "text"}], "field_values": {"target": value}})
