"""Reproduce GT-01 with isolated SQLite and the existing test harness."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from tests.test_template_default_content import TemplateDefaultContentTests


def main() -> None:
    TemplateDefaultContentTests.setUpClass()
    test = TemplateDefaultContentTests(methodName="test_helper_two_fields")
    test.setUp()
    try:
        for index, field in enumerate(["#Kanji", "!Word", "A.B"]):
            response = test.client.post(
                "/api/note-types",
                json={
                    "name": f"review-{index}",
                    "field_defs": [
                        {"name": field, "field_type": "text", "position": 0},
                    ],
                },
            )
            data = response.get_json()
            if response.status_code != 201:
                print(json.dumps({
                    "field": field,
                    "create_status": response.status_code,
                    "response": data,
                }))
                continue
            template = data["templates"][0]
            preview = test.client.post(
                f"/api/note-types/{data['id']}/templates/{template['id']}/preview",
                json={"use_sample_data": True},
            )
            result = preview.get_json()
            print(json.dumps({
                "field": field,
                "create_status": response.status_code,
                "front_source": template["front_html"],
                "preview_status": preview.status_code,
                "error": result.get("error"),
                "message": result.get("message"),
                "front_html": result.get("front_html"),
            }))
    finally:
        test.tearDown()


if __name__ == "__main__":
    main()
