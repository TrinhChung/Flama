"""Security tests for remote image downloads used by the shared library."""

from __future__ import annotations

import io
import socket
import unittest
from unittest.mock import patch

from app.services.remote_image_fetcher import fetch_remote_image
from app.validators import RequestValidationError


class _FakeConnection:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _FakeResponse:
    def __init__(
        self,
        *,
        body: bytes = b"",
        status: int = 200,
        headers: dict[str, str] | None = None,
    ) -> None:
        self.status = status
        self._body = io.BytesIO(body)
        self._headers = dict(headers or {})
        self.closed = False

    def getheader(self, name: str):
        return self._headers.get(name)

    def read(self, size: int = -1) -> bytes:
        return self._body.read(size)

    def close(self) -> None:
        self.closed = True


class RemoteImageFetcherTests(unittest.TestCase):
    def test_fetches_bounded_public_image(self):
        connection = _FakeConnection()
        response = _FakeResponse(
            body=b"\x89PNG\r\n\x1a\npayload",
            headers={
                "Content-Type": "image/png",
                "Content-Length": "15",
            },
        )
        with (
            patch(
                "app.services.remote_image_fetcher._resolve_public_addresses",
                return_value=("93.184.216.34",),
            ),
            patch(
                "app.services.remote_image_fetcher._request_target",
                return_value=(connection, response),
            ),
        ):
            payload = fetch_remote_image(
                "https://cdn.example.com/assets/dog?id=1",
                max_bytes=1024,
                timeout_seconds=3,
                max_redirects=2,
            )

        self.assertEqual(payload.mime_type, "image/png")
        self.assertEqual(payload.filename, "dog.png")
        self.assertEqual(payload.content, b"\x89PNG\r\n\x1a\npayload")
        self.assertTrue(connection.closed)
        self.assertTrue(response.closed)

    def test_rejects_private_dns_result_before_connecting(self):
        private_result = [
            (
                socket.AF_INET,
                socket.SOCK_STREAM,
                socket.IPPROTO_TCP,
                "",
                ("127.0.0.1", 443),
            )
        ]
        with patch(
            "app.services.remote_image_fetcher.socket.getaddrinfo",
            return_value=private_result,
        ):
            with self.assertRaises(RequestValidationError) as caught:
                fetch_remote_image(
                    "https://images.example.test/dog.png",
                    max_bytes=1024,
                    timeout_seconds=3,
                    max_redirects=2,
                )
        self.assertEqual(caught.exception.code, "IMAGE_REMOTE_HOST_NOT_ALLOWED")

    def test_rejects_non_http_scheme_and_https_downgrade(self):
        with self.assertRaises(RequestValidationError) as scheme_error:
            fetch_remote_image(
                "file:///etc/passwd",
                max_bytes=1024,
                timeout_seconds=3,
                max_redirects=2,
            )
        self.assertEqual(
            scheme_error.exception.code,
            "IMAGE_REMOTE_SCHEME_NOT_ALLOWED",
        )

        connection = _FakeConnection()
        response = _FakeResponse(
            status=302,
            headers={"Location": "http://cdn.example.com/dog.png"},
        )
        with (
            patch(
                "app.services.remote_image_fetcher._resolve_public_addresses",
                return_value=("93.184.216.34",),
            ),
            patch(
                "app.services.remote_image_fetcher._request_target",
                return_value=(connection, response),
            ),
        ):
            with self.assertRaises(RequestValidationError) as downgrade_error:
                fetch_remote_image(
                    "https://cdn.example.com/dog.png",
                    max_bytes=1024,
                    timeout_seconds=3,
                    max_redirects=2,
                )
        self.assertEqual(
            downgrade_error.exception.code,
            "IMAGE_REMOTE_REDIRECT_DOWNGRADE",
        )

    def test_rejects_stream_that_exceeds_limit_without_content_length(self):
        connection = _FakeConnection()
        response = _FakeResponse(
            body=b"12345678901",
            headers={"Content-Type": "image/png"},
        )
        with (
            patch(
                "app.services.remote_image_fetcher._resolve_public_addresses",
                return_value=("93.184.216.34",),
            ),
            patch(
                "app.services.remote_image_fetcher._request_target",
                return_value=(connection, response),
            ),
        ):
            with self.assertRaises(RequestValidationError) as caught:
                fetch_remote_image(
                    "https://cdn.example.com/dog.png",
                    max_bytes=10,
                    timeout_seconds=3,
                    max_redirects=2,
                )
        self.assertEqual(caught.exception.code, "MEDIA_TOO_LARGE")


if __name__ == "__main__":
    unittest.main()
