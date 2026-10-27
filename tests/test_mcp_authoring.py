"""Pure MCP contract tests; persistence is covered by the local MySQL probe."""

from types import SimpleNamespace
from contextlib import nullcontext
import unittest
from unittest.mock import MagicMock, patch

from app.services.mcp_tool_registry import call_mcp_tool, get_mcp_tool, list_mcp_tools
from app.validators import RequestValidationError
from app.validators.mcp_authoring import planned_fields, validate_note_type_changes
from app.validators.template_library import TemplateLibraryError


class McpAuthoringTests(unittest.TestCase):
    def setUp(self):
        session = MagicMock(no_autoflush=nullcontext())
        patcher = patch("app.services.mcp.template_preview_tools.db.session", session)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_template_tools_are_discoverable_and_scoped(self):
        names = {item["name"] for item in list_mcp_tools()}
        for name in ("list_card_templates", "get_card_template", "create_card_template", "update_card_template",
                     "attach_card_template", "update_template_application"):
            self.assertIn(name, names)
            tool = get_mcp_tool(name)
            self.assertFalse(tool.is_public)
            self.assertEqual(tool.required_scope, "note-type:read" if name.startswith(("list", "get")) else "note-type:write")
        properties = get_mcp_tool("update_note_type").input_schema["properties"]
        self.assertIn("anyOf", properties["fields"])
        self.assertIn("anyOf", properties["templates"])

    def test_authoring_docs_describe_the_complete_workflow(self):
        result = call_mcp_tool(tool_name="get_flama_documentation", arguments={"topic": "note-type-authoring"})["structuredContent"]
        for text in ("create_note_type", "create_card_template", "attach_card_template", "input_bindings", "expected_current_version_id", "create_deck"):
            self.assertIn(text, result["content"])

    def test_list_defaults_to_bounded_compact_page(self):
        with patch("app.services.mcp.template_tools.library.list_templates", return_value={"items": []}) as service:
            call_mcp_tool(tool_name="list_card_templates", user_id=9, arguments={})
        service.assert_called_once_with(user_id=9, compact=True, page=1)

    def test_compact_get_and_write_responses_do_not_repeat_source(self):
        source = {"id": "t", "name": "Prompt", "input_schema": [], "front_html": "secret-source",
            "back_html": "back", "shared_css": "css", "applications": []}
        with patch("app.services.mcp.template_tools.library.get_template", return_value=source):
            compact = call_mcp_tool(tool_name="get_card_template", user_id=9, arguments={"template_id": "t"})["structuredContent"]
            full = call_mcp_tool(tool_name="get_card_template", user_id=9, arguments={"template_id": "t", "include_source": True})["structuredContent"]
        self.assertNotIn("front_html", compact)
        self.assertEqual(full["front_html"], "secret-source")

    def test_template_name_and_binding_edits_use_canonical_services(self):
        with patch("app.services.mcp.template_tools.library.get_template", return_value={"id": "t"}), \
                patch("app.services.mcp.template_tools.library.update_template", return_value={"id": "t", "name": "Renamed"}) as update:
            result = call_mcp_tool(tool_name="update_card_template", user_id=9,
                arguments={"template_id": "t", "name": "Renamed", "expected_current_version_id": "v1"})
        self.assertEqual(result["structuredContent"]["name"], "Renamed")
        update.assert_called_once_with(user_id=9, template_id="t", payload={"name": "Renamed", "expected_current_version_id": "v1"})
        with patch("app.services.mcp.template_tools._guard_note_type"), \
                patch("app.services.mcp.template_tools.library.update_application", return_value={"application_id": "a"}) as update:
            call_mcp_tool(tool_name="update_template_application", user_id=9,
                arguments={"note_type_id": "nt", "application_id": "a", "input_bindings": {"prompt": "f"}, "display_name": "Reading"})
        update.assert_called_once_with(user_id=9, note_type_id="nt", application_id="a",
            payload={"input_bindings": {"prompt": "f"}, "display_name": "Reading"})

    def test_new_template_tools_preserve_the_shared_schema_guard(self):
        from app.services.flashcard_content_service import ContentApiError
        with patch("app.services.mcp.template_tools.library._note_type", return_value=SimpleNamespace(id="nt")), \
                patch("app.services.mcp.template_tools.flashcard_content_service._ensure_version_safe_template_mutation",
                    side_effect=ContentApiError("SHARED_SCHEMA_VERSIONING_REQUIRED", "Use version-aware editing.", status=409)), \
                patch("app.services.mcp.template_tools.library.attach_template") as attach:
            result = call_mcp_tool(tool_name="attach_card_template", user_id=9,
                arguments={"note_type_id": "nt", "template_id": "t", "input_bindings": {}})
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "SHARED_SCHEMA_VERSIONING_REQUIRED")
        attach.assert_not_called()

    def test_stale_error_is_structured_and_forbidden_remains_an_error(self):
        with patch("app.services.mcp.template_tools.library.get_template", return_value={"id": "t"}), \
                patch("app.services.mcp.template_tools.library.update_template",
                    side_effect=TemplateLibraryError("TEMPLATE_VERSION_STALE", "Changed", status=409)):
            result = call_mcp_tool(tool_name="update_card_template", user_id=9,
                arguments={"template_id": "t", "name": "New", "expected_current_version_id": "old"})
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "TEMPLATE_VERSION_STALE")
        with patch("app.services.mcp.template_tools.library.get_template",
                side_effect=TemplateLibraryError("FORBIDDEN", "Forbidden", status=403)), self.assertRaises(RequestValidationError):
            call_mcp_tool(tool_name="get_card_template", user_id=9, arguments={"template_id": "other"})

    def test_invalid_shapes_never_reach_services(self):
        for name, args in (
            ("attach_card_template", {"note_type_id": "n", "template_id": "t", "input_bindings": {"x": 42}}),
            ("update_template_application", {"note_type_id": "n", "application_id": "a", "is_default": "false"}),
            ("create_card_template", {"name": "t", "input_schema": [{"key": "x", "type": "number"}]}),
            ("create_card_template", {"name": "t", "front_html": 12}),
            ("list_card_templates", {"page": True}),
        ):
            with self.subTest(name=name), patch("app.services.mcp.template_tools._call") as service:
                result = call_mcp_tool(tool_name=name, user_id=9, arguments=args)
                self.assertTrue(result["isError"])
                service.assert_not_called()

    def test_note_type_creation_rejects_accidental_required_flags_and_nontext_source(self):
        for args in ({"name": "New", "fields": [{"name": "Word", "required": "false"}]},
                {"name": "New", "fields": [{"name": "Word", "position": True}]},
                {"name": "New", "templates": [{"name": "Card", "front_html": {"bad": "value"}}]}):
            with self.subTest(args=args), patch("app.services.mcp_tool_service.create_note_type") as service:
                result = call_mcp_tool(tool_name="create_note_type", user_id=9, arguments=args)
            self.assertTrue(result["isError"])
            service.assert_not_called()

    def test_invalid_javascript_cannot_be_saved(self):
        with patch("app.services.mcp.template_tools.library.create_template") as service:
            result = call_mcp_tool(tool_name="create_card_template", user_id=9,
                arguments={"name": "Bad", "front_html": "<script>const bad = ;</script>"})
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["diagnostics"][0]["code"], "JAVASCRIPT_SYNTAX_ERROR")
        service.assert_not_called()

    def test_preview_reports_errors_as_data_without_connector_exception(self):
        for source in ("<script>function broken( {</script>", "{{#x}}broken{{/y}}"):
            result = call_mcp_tool(tool_name="preview_note_type_template", user_id=9, arguments={
                "input_schema": [{"key": "x", "type": "text", "label": "Prompt"}],
                "front_html": source, "back_html": "", "sample_values": {"x": "example"}})
            self.assertFalse(result.get("isError", False))
            self.assertFalse(result["structuredContent"]["valid"])
            self.assertEqual(result["structuredContent"]["checks"]["template"], "failed")
            self.assertIsNone(result["structuredContent"]["preview"])

    def test_empty_front_is_an_advisory_not_a_failure(self):
        result = call_mcp_tool(tool_name="preview_note_type_template", user_id=9, arguments={
            "input_schema": [], "front_html": "", "back_html": "", "sample_values": {}})["structuredContent"]
        self.assertTrue(result["valid"])
        self.assertEqual(result["diagnostics"][0]["code"], "EMPTY_FRONT_TEMPLATE")
        self.assertEqual(result["diagnostics"][0]["severity"], "warning")
        self.assertEqual(result["checks"]["server_render"], "passed")

    def test_field_changes_reject_invalid_types_booleans_and_unknown_operations(self):
        for fields in ({"modified": [{"name": "Word", "field_type": "number"}]},
                {"modified": [{"name": "Word", "required": "false"}]}, {"rename": []}, {"added": "bad"}, []):
            with self.subTest(fields=fields), self.assertRaises(RequestValidationError):
                validate_note_type_changes({"fields": fields})

    def test_field_plan_rejects_collisions_and_out_of_scope_references(self):
        fields = [SimpleNamespace(id="f", name="Word", field_type="text", position=0, required=True, identity_role="primary")]
        for change in ({"renamed": [{"old_name": "missing", "new_name": "Prompt"}]},
                {"added": [{"name": "word"}]}, [{"id": "foreign", "name": "Word"}],
                {"modified": [{"name": "Word", "field_type": "markdown"}]}):
            with self.subTest(change=change), self.assertRaises(RequestValidationError):
                planned_fields(fields, change)
        result = planned_fields(fields, {"renamed": [{"old_name": "Word", "new_name": "Prompt"}]})
        self.assertEqual(result[0]["id"], "f")
        self.assertEqual(result[0]["name"], "Prompt")
        self.assertEqual(fields[0].name, "Word")


if __name__ == "__main__":
    unittest.main()
