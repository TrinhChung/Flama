"""Release-safety tests for the media cache deployment helper."""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import unittest
from unittest.mock import patch


SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "deploy_cloudflare_cache_rule.py"
SPEC = importlib.util.spec_from_file_location("deploy_cloudflare_cache_rule", SCRIPT_PATH)
assert SPEC is not None and SPEC.loader is not None
cache_rule_script = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cache_rule_script)


class CloudflareCacheRuleTests(unittest.TestCase):
    def test_rule_bounds_browser_and_edge_staleness(self):
        rule = cache_rule_script._build_cache_rule()
        parameters = rule["action_parameters"]

        self.assertEqual(parameters["edge_ttl"]["default"], 86400)
        self.assertEqual(
            parameters["edge_ttl"]["status_code_ttl"],
            [
                {"status_code": 200, "value": 86400},
                {"status_code": 206, "value": 86400},
                {"status_code_range": {"from": 400, "to": 499}, "value": 0},
                {"status_code_range": {"from": 500, "to": 599}, "value": 0},
            ],
        )
        self.assertEqual(
            parameters["browser_ttl"],
            {"mode": "override_origin", "default": 3600},
        )

    def test_rule_expression_matches_media_proxy_root_and_subpaths(self):
        rule = cache_rule_script._build_cache_rule()
        expression = rule["expression"]
        self.assertIn('http.host eq "api.flama.vn"', expression)
        self.assertIn('http.request.uri.path eq "/media/proxy"', expression)
        self.assertIn('starts_with(http.request.uri.path, "/media/proxy/")', expression)
        self.assertEqual(expression, cache_rule_script.MATCH_EXPRESSION)

    def test_missing_zone_id_stops_before_loading_token_or_calling_api(self):
        with (
            patch.object(cache_rule_script, "_load_optional_setting", return_value=""),
            patch.object(cache_rule_script, "_load_token") as load_token,
            patch.object(cache_rule_script, "_cf_api") as api,
            patch("sys.stderr"),
        ):
            with self.assertRaises(SystemExit) as error:
                cache_rule_script.main()

        self.assertEqual(error.exception.code, 1)
        load_token.assert_not_called()
        api.assert_not_called()

    def test_zone_id_can_be_loaded_from_dotenv(self):
        with (
            patch.dict(os.environ, {}, clear=True),
            patch.object(Path, "exists", return_value=True),
            patch.object(Path, "read_text", return_value='CLOUDFLARE_ZONE_ID="zone-from-dotenv"\n'),
        ):
            self.assertEqual(
                cache_rule_script._load_optional_setting(("CLOUDFLARE_ZONE_ID",)),
                "zone-from-dotenv",
            )

    def test_existing_rule_is_reconciled_with_patch(self):
        calls: list[tuple[str, str, dict | None]] = []

        def fake_api(method: str, path: str, _token: str, body: dict | None = None):
            calls.append((method, path, body))
            if path.endswith("/rulesets"):
                return {
                    "result": [
                        {"id": "ruleset-1", "phase": cache_rule_script.PHASE, "kind": "zone"}
                    ]
                }
            if path.endswith("/rulesets/ruleset-1"):
                return {
                    "result": {
                        "rules": [
                            {"id": "rule-1", "description": cache_rule_script.LEGACY_RULE_DESCRIPTION}
                        ]
                    }
                }
            return {"success": True, "result": {"id": "ruleset-1"}}

        with (
            patch.object(cache_rule_script, "_load_token", return_value="token"),
            patch.object(cache_rule_script, "_load_global_auth", return_value=None),
            patch.object(cache_rule_script, "_cf_api", side_effect=fake_api),
            patch.dict(os.environ, {"CLOUDFLARE_ZONE_ID": "zone-1"}, clear=False),
        ):
            cache_rule_script.main(purge_existing=True)

        patch_calls = [call for call in calls if call[0] == "PATCH"]
        self.assertEqual(len(patch_calls), 1)
        self.assertEqual(
            patch_calls[0][1],
            "/zones/zone-1/rulesets/ruleset-1/rules/rule-1",
        )
        self.assertEqual(patch_calls[0][2], cache_rule_script._build_cache_rule())
        purge_calls = [call for call in calls if call[1].endswith("/purge_cache")]
        self.assertEqual(
            purge_calls,
            [
                (
                    "POST",
                    "/zones/zone-1/purge_cache",
                    {"prefixes": [cache_rule_script.MEDIA_CACHE_PREFIX]},
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
