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

    def test_javascript_syntax_and_early_errors_cannot_pass_or_render(self):
        for script in ("const broken = ;", "const missing;", "return 1;", "const x=1; const x=2;"):
            with self.subTest(script=script):
                result = self.candidate(front_html=f"<script>{script}</script>")
                self.assertEqual(result["checks"]["template"], "failed")
                self.assertEqual(result["checks"]["javascript_syntax"], "failed")
                self.assertEqual(result["checks"]["server_render"], "not_run")
                self.assertIsNone(result["preview"])
                self.assertEqual(result["diagnostics"][0]["code"], "JAVASCRIPT_SYNTAX_ERROR")

    def test_modern_javascript_is_parsed_but_never_executed(self):
        result = self.candidate(front_html='''<script>
            const value = globalThis.missing?.value ?? [1, 2];
            class Example { #value = 1; get value() { return this.#value; } }
            throw new Error("Do not execute"); while (true) {}
        </script><script type="module">export const value = await Promise.resolve(1);</script>''')
        self.assertEqual(result["checks"]["javascript_syntax"], "passed")
        self.assertEqual(result["checks"]["server_render"], "passed")
        self.assertEqual(result["checks"]["study_browser"], "not_run")
        self.assertEqual(result["checks"]["interaction"], "not_run")

    def test_javascript_error_coordinates_reference_original_back_html(self):
        result = self.candidate(back_html='<div>日本語</div>\r\n<script>\r\nconst broken = ;\r\n</script>')
        error = next(d for d in result["diagnostics"] if d["code"] == "JAVASCRIPT_SYNTAX_ERROR")
        self.assertEqual((error["source_part"], error["line"], error["column"]), ("back_html", 3, 16))

    def test_module_syntax_uses_the_renderer_normalized_script_type(self):
        for script_type in ("module", " module ", " MODULE "):
            with self.subTest(script_type=script_type):
                result = self.candidate(front_html=f'<script type="{script_type}">export const answer = await Promise.resolve(42);</script>')
                self.assertEqual(result["checks"]["javascript_syntax"], "passed", result["diagnostics"])
                self.assertEqual(result["checks"]["server_render"], "passed")
                self.assertIn('<script type="module">', result["preview"]["template_artifact"]["front_inline_scripts"][0])

    def test_unknown_input_has_original_position_and_declared_suggestions(self):
        result = self.candidate(input_schema=[{"key": "question", "type": "text"}],
            sample_values={"question": "Hello"},
            front_html='<script>\nconst literal = "{{not_an_input}}";\n</script>\n<div>日本語 {{quesion}}</div>')
        warnings = [d for d in result["diagnostics"] if d["code"] == "UNDECLARED_VARIABLE"]
        self.assertEqual(len(warnings), 1)
        self.assertEqual((warnings[0]["line"], warnings[0]["column"]), (4, 12))
        self.assertIn("question", warnings[0]["suggestions"])

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
    def test_invalid_tool_arguments_are_repairable_without_artifacts(self):
        from app.services.mcp_tool_registry import call_mcp_tool
        from app.validators.mcp_template_preview import TEMPLATE_PREVIEW_OUTPUT_SCHEMA
        for arguments in ({"sample_values": {}}, {"sample_values": {}, "template_id": "wrong"},
            {"sample_values": {}, "input_schema": [], "front_html": "", "back_html": "", "include_preview": "false"}):
            result = call_mcp_tool(tool_name="preview_note_type_template", user_id=1, arguments=arguments)
            self.assertFalse(result.get("isError", False))
            self.assertFalse(result["structuredContent"]["valid"])
            data = result["structuredContent"]
            self.assertTrue(set(TEMPLATE_PREVIEW_OUTPUT_SCHEMA["required"]) <= set(data))
            self.assertEqual(data["checks"]["input"], "failed")
            self.assertEqual(data["checks"]["javascript_syntax"], "not_run")
            self.assertIsNone(data["candidate_hash"])
            self.assertIsNone(data["preview"])
            self.assertIn("line", data["diagnostics"][0])
            self.assertIn("column", data["diagnostics"][0])

    def test_tool_returns_small_metadata_and_hydrates_ui_without_echoing_source(self):
        from app.services.mcp_tool_registry import call_mcp_tool
        session = MagicMock()
        args = dict(input_schema=[], sample_values={}, front_html="<p>unique-source-token</p>", back_html="")
        with patch("app.services.mcp.template_preview_tools.db.session", session), \
                patch("app.services.mcp_resource_registry.template_preview_ui_available", return_value=True):
            wrapped = call_mcp_tool(tool_name="preview_note_type_template", user_id=1, arguments=args)
            data = wrapped["structuredContent"]
            self.assertTrue(data["preview_available"])
            self.assertIsNone(data["preview"])
            self.assertNotIn("server_render", data)
            self.assertNotIn("unique-source-token", json.dumps(data))
            self.assertIn("unique-source-token", json.dumps(wrapped["_meta"]))
            detailed = call_mcp_tool(tool_name="preview_note_type_template", user_id=1,
                arguments=dict(args, include_preview=True, include_server_render=True))["structuredContent"]
            self.assertIsNotNone(detailed["preview"])
            self.assertIn("unique-source-token", detailed["server_render"]["front_html"])

    def test_compact_schema_retains_only_needed_target_references_and_no_source_echo(self):
        from app.services.mcp.note_type_tools import compact_note_type_schema
        from app.services.mcp.authoring_responses import wrap_schema_result
        schema = {"id": "note-type", "name": "Example", "description": "Purpose", "is_owner": True,
            "is_official": False, "field_names": ["question"], "sample_note_payload": {"note_type_id": "note-type"},
            "fields": [{"id": "internal-field-id", "name": "question", "field_type": "text", "required": True,
                "identity_role": None, "validation_constraints": {"max_length": 100000}}],
            "templates": [{"id": "internal-template-id", "application_id": "needed-occurrence", "name": "Card",
                "position": 0, "is_default": True, "input_bindings": {"question": "internal-field-id"},
                "front_html": "<div>" + "source-marker" * 1000 + "</div>", "back_html": "", "shared_css": ""}]}
        compact = compact_note_type_schema(schema)
        wrapped = wrap_schema_result(compact)
        text = json.dumps(wrapped)
        for value in ("source-marker", "internal-field-id", "internal-template-id", "sample_note_payload"):
            self.assertNotIn(value, text)
        self.assertIn("needed-occurrence", text)
        self.assertEqual(compact["fields"][0]["name"], "question")
        self.assertLess(len(text), len(json.dumps(schema)) / 4)
        self.assertNotEqual(wrapped["content"][0]["text"], json.dumps(compact))

    def test_create_tool_keeps_syntax_diagnostics_and_legacy_error_code(self):
        from app.services.mcp_tool_registry import call_mcp_tool
        result = call_mcp_tool(tool_name="create_note_type", user_id=1, arguments={"name": "Bad",
            "fields": [{"name": "question", "field_type": "text"}],
            "templates": [{"name": "Front", "front_html": "<script>const x = ;</script>", "back_html": ""}]})
        self.assertTrue(result["isError"])
        self.assertEqual(result["structuredContent"]["error"]["code"], "TEMPLATE_SYNTAX_ERROR")
        self.assertEqual(result["structuredContent"]["checks"]["javascript_syntax"], "failed")
        self.assertEqual(result["structuredContent"]["diagnostics"][0]["source_part"], "front_html")

    def test_http_preview_report_is_data_and_auth_failure_stays_protocol_error(self):
        from flask_login import LoginManager
        from app.connect.mcp import mcp_connect_bp
        app = Flask(__name__)
        app.config["SECRET_KEY"] = "test"
        LoginManager(app)
        app.register_blueprint(mcp_connect_bp)
        session = MagicMock()
        with patch("app.connect.mcp.db.session", session), \
                patch("app.connect.mcp.mcp_auth_service.authenticate_mcp_request", return_value=SimpleNamespace(
                    user=SimpleNamespace(id=1), auth_type="test")), \
                patch("app.connect.mcp.quota_service.consume", return_value=SimpleNamespace(allowed=True)):
            response = app.test_client().post("/v1/mcp", json={"jsonrpc": "2.0", "id": 1,
                "method": "tools/call", "params": {"name": "preview_note_type_template", "arguments": {"sample_values": {}}}})
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.get_json()["result"].get("isError", False))
        self.assertFalse(response.get_json()["result"]["structuredContent"]["valid"])
        session.rollback.assert_not_called()
        session.commit.assert_called_once()
        from app.services.mcp.authoring_responses import wrap_preview_error
        with self.assertRaises(RequestValidationError):
            wrap_preview_error(RequestValidationError("Forbidden", status=403, code="FORBIDDEN"))
    def test_meta_is_backward_compatible_and_missing_build_is_not_advertised(self):
        from app.services.mcp_tool_registry import LIST_MY_DECKS_TOOL, PREVIEW_NOTE_TYPE_TEMPLATE_TOOL
        self.assertNotIn("_meta", LIST_MY_DECKS_TOOL.to_mcp_payload())
        with patch("app.services.mcp_resource_registry.template_preview_ui_available", return_value=False):
            self.assertNotIn("_meta", PREVIEW_NOTE_TYPE_TEMPLATE_TOOL.to_mcp_payload())
        with patch("app.services.mcp_resource_registry.template_preview_ui_available", return_value=True):
            tool = PREVIEW_NOTE_TYPE_TEMPLATE_TOOL.to_mcp_payload()
            self.assertEqual(tool["_meta"]["ui"]["resourceUri"], "ui://flama/template-preview/v2.html")
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
                self.assertIsNotNone(registry.read_resource("ui://flama/template-preview/v1.html"))
                self.assertIsNone(registry.read_resource("ui://flama/../../.env"))
                self.assertIsNone(registry.read_resource(str(artifact)))
                self.assertIn("Mustache", registry.read_resource("flama://docs/template-authoring")["text"])

    def test_media_origin_is_separate_from_frontend_origin(self):
        from app.services import mcp_resource_registry as registry
        app = Flask(__name__)
        app.config.update(MCP_TEMPLATE_PREVIEW_UI_ENABLED=True,
            PUBLIC_APP_URL="https://flama.vn", MCP_TEMPLATE_PREVIEW_MEDIA_BASE_URL="https://api.flama.vn/media/")
        with app.app_context(), tempfile.TemporaryDirectory() as folder:
            artifact = Path(folder) / "index.html"
            artifact.write_text("<!doctype html><title>Preview</title>", encoding="utf-8")
            with patch.object(registry, "_UI_PATH", artifact):
                self.assertEqual(registry.media_base_url(), "https://api.flama.vn/")
                meta = registry.read_resource(registry.TEMPLATE_PREVIEW_URI)["_meta"]["ui"]["csp"]
                self.assertEqual(meta["resourceDomains"], ["https://api.flama.vn"])
                self.assertNotIn("https://flama.vn", meta["resourceDomains"])
            app.config["MCP_TEMPLATE_PREVIEW_MEDIA_BASE_URL"] = "javascript:alert(1)"
            self.assertEqual(registry.media_base_url(), "")

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
