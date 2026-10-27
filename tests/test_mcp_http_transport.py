"""Database-free checks of the MCP HTTP notification contract on both URLs."""

import unittest

from flask import Flask

from app.connect.mcp import mcp_connect_bp
from app.routes.mcp import mcp_bp


class McpHttpTransportTests(unittest.TestCase):
    def setUp(self):
        app = Flask(__name__)
        app.config["TESTING"] = True
        app.register_blueprint(mcp_bp)
        app.register_blueprint(mcp_connect_bp)
        self.client = app.test_client()

    def test_notifications_are_accepted_without_a_body_on_both_endpoints(self):
        for path in ("/api/mcp", "/v1/mcp", "/v1/mcp/test-token"):
            for method in ("notifications/initialized", "notifications/cancelled"):
                with self.subTest(path=path, method=method):
                    response = self.client.post(path, json={
                        "jsonrpc": "2.0", "method": method,
                        "params": {"requestId": 1} if method.endswith("cancelled") else {},
                    }, headers={"Accept": "application/json, text/event-stream"})
                    self.assertEqual(response.status_code, 202)
                    self.assertEqual(response.data, b"")
                    self.assertEqual(response.headers["MCP-Protocol-Version"], "2025-11-25")

    def test_transport_remains_responsive_after_notification(self):
        for path in ("/api/mcp", "/v1/mcp"):
            with self.subTest(path=path):
                self.client.post(path, json={"jsonrpc": "2.0", "method": "notifications/initialized"})
                response = self.client.post(path, json={"jsonrpc": "2.0", "id": 7, "method": "ping"})
                self.assertEqual(response.status_code, 200)
                self.assertEqual(response.get_json(), {"jsonrpc": "2.0", "id": 7, "result": {}})


if __name__ == "__main__":
    unittest.main()
