"""Pure candidate/contract tests: no app boot, schema setup or database access."""

import copy
import json
from pathlib import Path
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import MagicMock, patch
from flask import Flask

from app.services.flashcard_renderer import render_template_pair
from app.services.template_authoring_service import preview_candidate, build_candidate_preview
from app.validators.flashcard_input import RequestValidationError
from app.validators.mcp_template_preview import validate_template_preview_arguments


class TemplateAuthoringTests(unittest.TestCase):
    def candidate(self, **changes):
        payload = dict(input_schema=[{"key": "options", "type": "array"}],
            front_html="{{#options}}<li>{{.}}</li>{{/options}}", back_html="{{FrontSide}}",
            sample_values={"options": ["A", "B"]})
        payload.update(changes)
        return preview_candidate(**payload)

    def test_native_lists_and_study_artifacts_without_browser_claim(self):
        result = self.candidate()
        self.assertEqual(result["checks"]["server_render"], "passed")
        self.assertEqual(result["checks"]["study_browser"], "not_run")
        self.assertEqual(result["checks"]["interaction"], "not_run")
        self.assertEqual(result["preview"]["content_artifact"]["field_values"]["options"], ["A", "B"])
        self.assertEqual(result["preview"]["template_artifact"]["schema_version"], "study-template.v1")
        self.assertIn("<li>A</li><li>B</li>", result["server_render"]["front_html"])

    def test_bad_sections_and_handlebars_cannot_claim_compile_pass(self):
        for source in ("{{#options}}x{{/wrong}}", "{{#each options}}x{{/each options}}"):
            result = self.candidate(front_html=source)
            self.assertEqual(result["checks"]["template"], "failed")
            self.assertIsNone(result["preview"])
            self.assertEqual(result["checks"]["server_render"], "not_run")

    def test_context_warnings_are_explicit_and_scripts_remain_literal(self):
        result = self.candidate(front_html='{{@index}}<script>const x="{{options.0}}";</script>',
            shared_css=".x { width:{{options.0}}; }")
        codes = {item["code"] for item in result["diagnostics"]}
        self.assertTrue({"LOOP_METADATA_UNSUPPORTED", "SCRIPT_TOKENS_LITERAL", "SHARED_CSS_NOT_INTERPOLATED"} <= codes)
        self.assertIn("{{options.0}}", result["preview"]["template_artifact"]["front_inline_scripts"][0])

    def test_declared_names_with_else_prefix_are_normal_inputs(self):
        result = self.candidate(input_schema=[{"key": "elsewhere", "type": "text"}],
            front_html="{{elsewhere}}", sample_values={"elsewhere": "valid"})
        self.assertEqual(result["checks"]["template"], "passed")
        self.assertEqual(result["server_render"]["front_html"], "valid")

    def test_python_methods_and_attributes_are_not_template_data(self):
        result = self.candidate(front_html="{{options.0}}|{{#options}}{{index}}/{{__class__}}/{{.}};{{/options}}|{{options.append}}")
        rendered = result["server_render"]["front_html"]
        self.assertEqual(rendered, "A|//A;//B;|")
        self.assertNotIn("built-in", rendered)

    def test_nested_and_empty_list_values_keep_positions(self):
        result = self.candidate(sample_values={"options": ["", ["C", "D"], "E"]})
        self.assertEqual(result["preview"]["content_artifact"]["field_values"]["options"], ["", ["C", "D"], "E"])
        self.assertEqual(result["server_render"]["front_html"], "<li></li><li>C,D</li><li>E</li>")

    def test_candidate_digest_changes_with_samples_and_is_stable(self):
        first = self.candidate()
        self.assertEqual(first["candidate_hash"], self.candidate()["candidate_hash"])
        self.assertNotEqual(first["candidate_hash"], self.candidate(sample_values={"options": ["changed"]})["candidate_hash"])

    def test_samples_are_explicit_bounded_and_not_numeric(self):
        for values in ({"options": [1]}, {"options": {"a": "B"}}, {"options": "x" * 100001}):
            with self.assertRaises(RequestValidationError):
                self.candidate(sample_values=values)
        with self.assertRaises(RequestValidationError):
            validate_template_preview_arguments({"front_html": "x", "back_html": "x", "input_schema": []})
        with self.assertRaises(RequestValidationError):
            validate_template_preview_arguments({"sample_values": {}, "template_id": "ambiguous"})

    def test_quiz_profile_validates_positions_only_when_opted_in(self):
        schema = [{"key": "options", "type": "array"}, {"key": "correct_answers", "type": "array"}]
        for answers in (["0"], ["3"], ["1", "1"], [], ["01"]):
            samples = {"options": ["A", "B"], "correct_answers": answers}
            invalid = self.candidate(input_schema=schema, sample_values=samples, profile="quiz")
            self.assertEqual(invalid["checks"]["input"], "failed")
            generic = self.candidate(input_schema=schema, sample_values=samples)
            self.assertEqual(generic["checks"]["input"], "passed")
        valid = self.candidate(input_schema=schema, sample_values={"options": ["A", "B"], "correct_answers": ["1", "2"]}, profile="quiz")
        self.assertEqual(valid["checks"]["input"], "passed")

    def test_bound_occurrence_uses_source_fields_and_keeps_snapshot(self):
        fields = [SimpleNamespace(id="f-1", name="Choices", field_type="array", required=False, position=0)]
        values = {"Choices": ["A", "B"]}
        template = SimpleNamespace(id="tpl", updated_at="", input_schema=[{"key": "options", "type": "array"}],
            input_bindings={"options": "f-1"}, front_html="{{#options}}{{.}}{{/options}}", back_html="", shared_css="")
        before = copy.deepcopy(values)
        result = build_candidate_preview(template=template, field_defs=fields, field_values=values)
        self.assertEqual(result["preview"]["content_artifact"]["field_values"]["options"], ["A", "B"])
        self.assertEqual(result["preview"]["template_artifact"]["binding_projection"]["input_bindings"], {"options": "f-1"})
        self.assertEqual(values, before)


class McpTemplatePreviewSurfaceTests(unittest.TestCase):
    def test_meta_is_backward_compatible_and_missing_build_is_not_advertised(self):
        from app.services.mcp_tool_registry import LIST_MY_DECKS_TOOL, PREVIEW_NOTE_TYPE_TEMPLATE_TOOL
        self.assertNotIn("_meta", LIST_MY_DECKS_TOOL.to_mcp_payload())
        with patch("app.services.mcp_resource_registry.template_preview_ui_available", return_value=False):
            self.assertNotIn("_meta", PREVIEW_NOTE_TYPE_TEMPLATE_TOOL.to_mcp_payload())
        with patch("app.services.mcp_resource_registry.template_preview_ui_available", return_value=True):
            tool = PREVIEW_NOTE_TYPE_TEMPLATE_TOOL.to_mcp_payload()
            self.assertEqual(tool["_meta"]["ui"]["resourceUri"], "ui://flama/template-preview/v1.html")
            self.assertTrue(tool["annotations"]["readOnlyHint"])
            self.assertEqual(tool["outputSchema"]["properties"]["schema_version"]["const"], "template-preview.v1")

    def test_resource_allowlist_keeps_docs_and_never_resolves_paths(self):
        from app.services import mcp_resource_registry as registry
        app = Flask(__name__)
        app.config["MCP_TEMPLATE_PREVIEW_UI_ENABLED"] = True
        with tempfile.TemporaryDirectory() as folder, app.app_context():
            artifact = Path(folder) / "index.html"
            artifact.write_text("<!doctype html><title>Preview</title>", encoding="utf-8")
            with patch.object(registry, "_UI_PATH", artifact):
                resources = registry.list_resources()
                self.assertIn(registry.TEMPLATE_PREVIEW_URI, {item["uri"] for item in resources})
                self.assertIn("flama://docs/template-authoring", {item["uri"] for item in resources})
                resource = registry.read_resource(registry.TEMPLATE_PREVIEW_URI)
                self.assertEqual(resource["mimeType"], "text/html;profile=mcp-app")
                self.assertIn("<!doctype html>", resource["text"])
                self.assertIsNone(registry.read_resource("ui://flama/../../.env"))
                self.assertIsNone(registry.read_resource(str(artifact)))
                self.assertIn("Mustache", registry.read_resource("flama://docs/template-authoring")["text"])

    def test_raw_tool_uses_no_persistence_operations(self):
        from app.services.mcp.template_preview_tools import preview_note_type_template
        session = MagicMock()
        with patch("app.services.mcp.template_preview_tools.db.session", session):
            result = preview_note_type_template(user_id=123, arguments=dict(
                input_schema=[{"key": "x", "type": "text"}], front_html="{{x}}", back_html="",
                sample_values={"x": "sample"}))
        session.add.assert_not_called()
        session.flush.assert_not_called()
        session.commit.assert_not_called()
        session.execute.assert_not_called()
        self.assertFalse(result.get("isError", False))
        self.assertEqual(result["structuredContent"]["checks"]["interaction"], "not_run")

    def test_http_discovery_resource_link_and_rollout_fallback(self):
        from app.connect.mcp import mcp_connect_bp
        from app.services import mcp_resource_registry as registry
        app = Flask(__name__)
        app.config.update(MCP_TEMPLATE_PREVIEW_UI_ENABLED=True, PUBLIC_APP_URL="https://media.example.test")
        app.register_blueprint(mcp_connect_bp)
        client = app.test_client()
        with tempfile.TemporaryDirectory() as folder:
            artifact = Path(folder) / "index.html"
            artifact.write_text("<!doctype html><title>Preview</title>", encoding="utf-8")
            with patch.object(registry, "_UI_PATH", artifact):
                def rpc(method, params=None):
                    return client.post("/v1/mcp", json={"jsonrpc": "2.0", "id": 1,
                        "method": method, "params": params or {}})
                tools = rpc("tools/list").get_json()["result"]["tools"]
                preview = next(item for item in tools if item["name"] == "preview_note_type_template")
                uri = preview["_meta"]["ui"]["resourceUri"]
                resource = rpc("resources/read", {"uri": uri}).get_json()["result"]["contents"][0]
                self.assertIn("Preview", resource["text"])
                self.assertEqual(resource["_meta"]["ui"]["csp"]["resourceDomains"], ["https://media.example.test"])
                missing = rpc("resources/read", {"uri": "ui://flama/unknown"})
                self.assertEqual(missing.get_json()["error"]["data"]["code"], "RESOURCE_NOT_FOUND")
                app.config["MCP_TEMPLATE_PREVIEW_UI_ENABLED"] = False
                self.assertNotIn(uri, {item["uri"] for item in rpc("resources/list").get_json()["result"]["resources"]})
                preview = next(item for item in rpc("tools/list").get_json()["result"]["tools"]
                    if item["name"] == "preview_note_type_template")
                self.assertNotIn("_meta", preview)

    def test_known_invalid_mutation_candidate_is_rejected_before_fencing(self):
        from app.services.mcp import note_type_tools
        nt = SimpleNamespace(id="nt", field_defs=[])
        with patch.object(note_type_tools, "_owned_note_type_for_mutation", return_value=nt), \
                patch.object(note_type_tools.template_library_repository, "attached_templates", return_value=[]), \
                patch.object(note_type_tools.db, "session", MagicMock()):
            with self.assertRaises(RequestValidationError) as caught:
                note_type_tools.update_note_type(user_id=1, note_type_id="nt", templates=[{
                    "name": "bad", "front_html": "{{#each options}}x{{/each options}}", "back_html": ""}])
        self.assertEqual(caught.exception.code, "TEMPLATE_SYNTAX_ERROR")

    def test_create_rejects_bad_source_before_database_access_with_legacy_error_prefix(self):
        from app.services.mcp.note_type_tools import create_note_type
        with self.assertRaises(RequestValidationError) as caught:
            create_note_type(user_id=1, name="Invalid", fields=[{"name": "x", "field_type": "array"}],
                templates=[{"name": "Card 1", "front_html": "{{#UnclosedTag}}", "back_html": ""}])
        self.assertEqual(caught.exception.code, "TEMPLATE_SYNTAX_ERROR")
        self.assertIn("Lỗi cú pháp trong template", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
