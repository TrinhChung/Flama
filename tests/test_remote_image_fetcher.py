"""Remote image/page downloads go through the media worker, never a direct socket."""

from __future__ import annotations

import base64
import io
import json
import unittest
import urllib.error
from unittest.mock import MagicMock, patch

from flask import Flask

from app.services.remote_image_fetcher import fetch_remote_html, fetch_remote_image
from app.validators import RequestValidationError

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 32


def _worker_response(body: bytes, headers: dict[str, str]):
    response = MagicMock()
    response.read.side_effect = lambda size=-1: body if size < 0 else body[:size]
    response.headers = headers
    response.__enter__.return_value = response
    return response


class RemoteImageFetcherTests(unittest.TestCase):
    def setUp(self):
        # The client reads only app config; a bare app keeps the test off the database.
        self.app = Flask(__name__)
        self.app.config.update(
            MEDIA_SHARED_SECRET="test_shared_secret",
            GATEWAY_SECRET="test_gateway_secret",
            FLAMA_MEDIA_WORKER_URL="http://wg-worker212:4792",
        )
        self.ctx = self.app.app_context()
        self.ctx.push()
        self.addCleanup(self.ctx.pop)

    @patch("urllib.request.build_opener")
    def test_image_is_fetched_by_the_worker_with_a_fetch_ticket(self, build_opener):
        build_opener.return_value.open.return_value = _worker_response(
            PNG, {"Content-Type": "image/png", "X-Flama-Final-Url": "https://cdn.example.com/a/dog%20pic.png"}
        )
        payload = fetch_remote_image("https://cdn.example.com/start?id=1", max_bytes=1024, timeout_seconds=3, max_redirects=2)

        self.assertEqual(payload.content, PNG)
        self.assertEqual(payload.mime_type, "image/png")
        self.assertEqual(payload.source_url, "https://cdn.example.com/a/dog%20pic.png")
        self.assertTrue(payload.filename.endswith(".png"))
        request = build_opener.return_value.open.call_args.args[0]
        self.assertEqual(request.full_url, "http://wg-worker212:4792/media/fetch-url")
        self.assertEqual(request.get_header("X-flama-gateway-secret"), "test_gateway_secret")
        self.assertEqual(json.loads(request.data), {"url": "https://cdn.example.com/start?id=1", "kind": "image", "timeout_seconds": 3.0})
        ticket = request.get_header("Authorization").removeprefix("Bearer ").split(".")[0]
        claims = json.loads(base64.urlsafe_b64decode(ticket + "=="))
        self.assertEqual((claims["action"], claims["max_bytes"]), ("fetch_url", 1024))

    @patch("urllib.request.build_opener")
    def test_invalid_urls_are_rejected_before_contacting_the_worker(self, build_opener):
        for url in ("file:///etc/passwd", "https://user:pw@example.com/a.png", "https://example.com:8443/a.png", ""):
            with self.assertRaises(RequestValidationError):
                fetch_remote_image(url, max_bytes=1024, timeout_seconds=3, max_redirects=2)
        build_opener.return_value.open.assert_not_called()

    @patch("urllib.request.build_opener")
    def test_worker_rejections_map_to_existing_error_codes(self, build_opener):
        cases = [
            (400, {"error": "URL_NOT_ALLOWED", "message": "private"}, "IMAGE_REMOTE_HOST_NOT_ALLOWED", 400),
            (413, {"error": "PAYLOAD_TOO_LARGE"}, "MEDIA_TOO_LARGE", 413),
            (415, {"error": "MEDIA_TYPE_NOT_ALLOWED"}, "IMAGE_REMOTE_TYPE_NOT_ALLOWED", 415),
            (502, {"error": "FETCH_FAILED"}, "IMAGE_REMOTE_FETCH_FAILED", 422),
        ]
        for status, body, code, expected_status in cases:
            build_opener.return_value.open.side_effect = urllib.error.HTTPError(
                "http://wg-worker212:4792/media/fetch-url", status, "error", {}, io.BytesIO(json.dumps(body).encode())
            )
            with self.assertRaises(RequestValidationError) as raised:
                fetch_remote_image("https://cdn.example.com/dog.png", max_bytes=1024, timeout_seconds=3, max_redirects=2)
            self.assertEqual((raised.exception.code, raised.exception.status), (code, expected_status))

    @patch("urllib.request.build_opener")
    def test_unreachable_worker_is_a_503(self, build_opener):
        build_opener.return_value.open.side_effect = urllib.error.URLError("refused")
        with self.assertRaises(RequestValidationError) as raised:
            fetch_remote_image("https://cdn.example.com/dog.png", max_bytes=1024, timeout_seconds=3, max_redirects=2)
        self.assertEqual((raised.exception.code, raised.exception.status), ("MEDIA_WORKER_UNAVAILABLE", 503))

    @patch("urllib.request.build_opener")
    def test_missing_worker_url_never_falls_back_to_a_direct_request(self, build_opener):
        self.app.config["FLAMA_MEDIA_WORKER_URL"] = ""
        with self.assertRaises(RequestValidationError) as raised:
            fetch_remote_image("https://cdn.example.com/dog.png", max_bytes=1024, timeout_seconds=3, max_redirects=2)
        self.assertEqual(raised.exception.code, "MEDIA_NOT_CONFIGURED")
        build_opener.return_value.open.assert_not_called()

    @patch("urllib.request.build_opener")
    def test_html_page_uses_the_declared_charset(self, build_opener):
        html = "<html><head><title>Chữ</title></head></html>".encode("utf-8")
        build_opener.return_value.open.return_value = _worker_response(html, {"Content-Type": "text/html; charset=utf-8"})
        self.assertIn("Chữ", fetch_remote_html("https://example.com/article"))
        self.assertEqual(json.loads(build_opener.return_value.open.call_args.args[0].data)["kind"], "html")


if __name__ == "__main__":
    unittest.main()
