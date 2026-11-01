"""Tests for Flama Media Client adapter."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock, patch

from flask import Flask

from app.services import flama_media_client
from app.services.flama_media_client import FlamaMediaClientError


class FlamaMediaClientTests(unittest.TestCase):
    def setUp(self):
        # The client reads only app config; a bare app keeps the test off the database.
        self.app = Flask(__name__)
        self.app.config.update(
            TESTING=True,
            MEDIA_SHARED_SECRET="test_shared_secret_12345",
            GATEWAY_SECRET="test_gw_secret_67890",
            FLAMA_MEDIA_WORKER_URL="http://wg-worker212:4792",
            INTERNAL_SECURITY_SECRET="test_private_control_key",
        )

    def test_generate_upload_ticket(self):
        with self.app.app_context():
            ticket = flama_media_client.generate_upload_ticket(user_id=42, max_bytes=1024, ttl_seconds=60)
            self.assertIn(".", ticket)
            parts = ticket.split(".")
            self.assertEqual(len(parts), 2)

    @patch("urllib.request.urlopen")
    def test_send_media_to_worker_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'{"asset_id":"abc123hash","url":"/media/proxy/abc123hash","sha256":"abc123hash","size_bytes":100,"content_type":"image/png","deduplicated":false}'
        mock_resp.__enter__.return_value = mock_resp
        mock_urlopen.return_value = mock_resp

        with self.app.app_context():
            result = flama_media_client.send_media_to_worker(
                file_bytes=b"fake-image-bytes",
                filename="test.png",
                content_type="image/png",
                user_id=1,
            )
            self.assertEqual(result["asset_id"], "abc123hash")
            self.assertEqual(result["url"], "/media/proxy/abc123hash")
            self.assertFalse(result["deduplicated"])

    @patch("urllib.request.urlopen")
    def test_missing_worker_url_fails_without_network(self, mock_urlopen):
        self.app.config["FLAMA_MEDIA_WORKER_URL"] = ""
        with self.app.app_context():
            with self.assertRaises(FlamaMediaClientError) as ctx:
                flama_media_client.send_zip_to_worker(b"zip-bytes", user_id=1)
        self.assertEqual(ctx.exception.error_code, "MEDIA_NOT_CONFIGURED")
        mock_urlopen.assert_not_called()

    @patch("urllib.request.build_opener")
    def test_internal_control_sends_only_json_and_dedicated_secret(self, build_opener):
        response = MagicMock()
        response.read.return_value = b'{"items":[]}'
        response.__enter__.return_value = response
        build_opener.return_value.open.return_value = response
        with self.app.app_context():
            result = flama_media_client.internal_request("/media/commit", {"user_id": 42, "items": []})
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(result, {"items": []})
        self.assertEqual(request.full_url, "http://wg-worker212:4792/media/commit")
        self.assertEqual(request.get_header("X-internal-secret"), "test_private_control_key")
        self.assertIsNone(request.get_header("Authorization"))
        self.assertIsNone(request.get_header("X-flama-gateway-secret"))
        self.assertIsInstance(build_opener.call_args.args[0], flama_media_client._NoInternalRedirects)

    def test_internal_redirect_handler_does_not_forward_credentials(self):
        self.assertIsNone(flama_media_client._NoInternalRedirects().redirect_request(
            None, None, 302, "redirect", {}, "https://other.example.test/"))


if __name__ == "__main__":
    unittest.main()
