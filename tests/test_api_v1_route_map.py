"""Contract snapshot for the canonical REST API URL map."""

from __future__ import annotations

import json
import os
from pathlib import Path
import unittest

from app import create_app
from models import db

SNAPSHOT_PATH = Path(__file__).resolve().parent / "snapshots" / "api_v1_routes.json"


def _extract_actual_rules(app) -> set[tuple[str, str]]:
    return {
        (method, rule.rule)
        for rule in app.url_map.iter_rules()
        if rule.endpoint.startswith("api_v1.")
        for method in rule.methods - {"HEAD", "OPTIONS"}
    }


def _save_snapshot(rules: set[tuple[str, str]]) -> None:
    SNAPSHOT_PATH.parent.mkdir(parents=True, exist_ok=True)
    sorted_rules = sorted(rules, key=lambda item: (item[1], item[0]))
    formatted_entries = [
        f"  {json.dumps([method, path], ensure_ascii=False)}"
        for method, path in sorted_rules
    ]
    content = "[\n" + ",\n".join(formatted_entries) + "\n]\n"
    SNAPSHOT_PATH.write_text(content, encoding="utf-8")


def _load_snapshot() -> set[tuple[str, str]] | None:
    if not SNAPSHOT_PATH.exists():
        return None
    with open(SNAPSHOT_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return {tuple(item) for item in data}


class ApiRouteMapTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
            }
        )

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_rule_and_method_contract_is_stable(self):
        actual = _extract_actual_rules(self.app)

        should_update = (
            os.getenv("UPDATE_SNAPSHOT", "").strip().lower() in {"1", "true", "yes", "on"}
            or os.getenv("UPDATE_ROUTE_SNAPSHOT", "").strip().lower() in {"1", "true", "yes", "on"}
        )

        if should_update:
            _save_snapshot(actual)
            print(f"\n[OK] Updated API route snapshot at {SNAPSHOT_PATH} ({len(actual)} routes).")
            return

        expected = _load_snapshot()
        if expected is None:
            self.fail(
                f"Snapshot file not found at {SNAPSHOT_PATH}.\n"
                "Run with UPDATE_SNAPSHOT=1 to generate it:\n"
                "  UPDATE_SNAPSHOT=1 py -3.12 -m unittest tests/test_api_v1_route_map.py"
            )

        if actual != expected:
            added = sorted(actual - expected, key=lambda item: (item[1], item[0]))
            removed = sorted(expected - actual, key=lambda item: (item[1], item[0]))

            diff_lines = []
            if added:
                diff_lines.append(f"\nAdded routes ({len(added)}):")
                for method, path in added:
                    diff_lines.append(f"  + {method:<7} {path}")
            if removed:
                diff_lines.append(f"\nRemoved routes ({len(removed)}):")
                for method, path in removed:
                    diff_lines.append(f"  - {method:<7} {path}")

            help_msg = (
                "\n\nTo accept these changes and update the snapshot, run:\n"
                "  python scripts/update_route_snapshot.py\n"
                "or:\n"
                "  UPDATE_SNAPSHOT=1 python -m unittest tests/test_api_v1_route_map.py\n"
                "or in PowerShell:\n"
                "  $env:UPDATE_SNAPSHOT='1'; py -3.12 -m unittest tests/test_api_v1_route_map.py"
            )

            self.fail(
                f"API route contract snapshot mismatch! (Expected {len(expected)}, got {len(actual)})"
                + "\n".join(diff_lines)
                + help_msg
            )

        self.assertFalse(
            any(rule.rule.startswith("/api/v1") for rule in self.app.url_map.iter_rules()),
            "Legacy /api/v1 prefix detected in route rules.",
        )


if __name__ == "__main__":
    unittest.main()
