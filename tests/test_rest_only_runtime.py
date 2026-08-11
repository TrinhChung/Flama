"""Contract tests for the REST-only Flask runtime and React HTML shell."""

import unittest
from unittest.mock import patch

from flask import Response

from app import create_app
from models import db


class RestOnlyRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.app = create_app(
            {
                "TESTING": True,
                "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                "WTF_CSRF_ENABLED": False,
                "LEGACY_HTTP_ADAPTERS_ENABLED": False,
            }
        )
        self.client = self.app.test_client()

    def tearDown(self):
        with self.app.app_context():
            db.session.remove()
            db.drop_all()

    def test_flask_has_no_jinja_template_folder(self):
        self.assertIsNone(self.app.template_folder)

    def test_navigation_is_served_by_react_without_page_database_work(self):
        with patch(
            "app.spa.serve_react_spa",
            return_value=Response("react-shell", content_type="text/html"),
        ):
            for path in ("/", "/login", "/dashboard", "/unknown/deep-link"):
                with self.subTest(path=path):
                    response = self.client.get(path)
                    self.assertEqual(response.status_code, 200)
                    self.assertEqual(response.data, b"react-shell")

    def test_api_auth_failure_remains_json(self):
        response = self.client.get("/api/dashboard")
        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.get_json()["error"], "AUTHENTICATION_REQUIRED")

    def test_legacy_mutation_and_nested_api_adapter_are_retired(self):
        form_response = self.client.post("/login", data={"email": "old@example.com"})
        nested_api_response = self.client.get("/vocabulary/api/browse/cards")
        for response in (form_response, nested_api_response):
            self.assertEqual(response.status_code, 410)
            self.assertEqual(response.get_json()["error"], "LEGACY_ENDPOINT_REMOVED")

    def test_required_static_renderer_is_not_intercepted(self):
        response = self.client.get("/static/js/card_renderer_host.js")
        self.assertEqual(response.status_code, 200)
        self.assertIn("javascript", response.content_type)


if __name__ == "__main__":
    unittest.main()
