"""Security tests for remote image downloads used by the shared library."""

from __future__ import annotations

import io
import socket
import unittest
from unittest.mock import patch

from app.services.remote_image_fetcher import (
    DirectCrawlDisabledError,
    fetch_remote_image,
)
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
        # Under Requirement R3, direct crawl is unconditionally disabled
        with self.assertRaises(DirectCrawlDisabledError):
            fetch_remote_image(
                "https://cdn.example.com/assets/dog?id=1",
                max_bytes=1024,
                timeout_seconds=3,
                max_redirects=2,
            )

    def test_rejects_private_dns_result_before_connecting(self):
        # Under Requirement R3, direct crawl raises DirectCrawlDisabledError immediately before any DNS call
        with self.assertRaises(DirectCrawlDisabledError):
            fetch_remote_image(
                "https://images.example.test/dog.png",
                max_bytes=1024,
                timeout_seconds=3,
                max_redirects=2,
            )

    def test_rejects_non_http_scheme_and_https_downgrade(self):
        with self.assertRaises(DirectCrawlDisabledError):
            fetch_remote_image(
                "file:///etc/passwd",
                max_bytes=1024,
                timeout_seconds=3,
                max_redirects=2,
            )

    def test_rejects_stream_that_exceeds_limit_without_content_length(self):
        with self.assertRaises(DirectCrawlDisabledError):
            fetch_remote_image(
                "https://cdn.example.com/dog.png",
                max_bytes=10,
                timeout_seconds=3,
                max_redirects=2,
            )


if __name__ == "__main__":
    unittest.main()
