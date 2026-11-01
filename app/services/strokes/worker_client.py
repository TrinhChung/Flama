"""Small JSON control client; SVG bytes are generated on212 and stored onOV."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from flask import current_app


class StrokeWorkerError(ValueError):
    pass


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # An internal control secret must never follow a redirect to another host.
        return None


def _open_internal(request):
    return urllib.request.build_opener(_NoRedirect()).open(request, timeout=60)


def generate_strokes(characters: list[str], locale: str, *, force: bool = False) -> dict[str, dict[str, Any]]:
    """Return verified worker metadata without accepting worker-supplied URLs."""
    base_url = str(current_app.config.get("FLAMA_MEDIA_WORKER_URL") or "").rstrip("/")
    secret = str(current_app.config.get("INTERNAL_SECURITY_SECRET") or "")
    parsed = urllib.parse.urlsplit(base_url)
    if (parsed.scheme not in {"http", "https"} or not parsed.netloc or parsed.username
            or parsed.query or parsed.fragment or not secret):
        raise StrokeWorkerError("Chưa cấu hình kết nối nội bộ tới dịch vụ SVG stroke.")

    unique = list(dict.fromkeys(characters))
    result: dict[str, dict[str, Any]] = {}
    # Keep a cold upstream fetch batch within one HTTP request's deadline.
    for offset in range(0, len(unique), 15):
        chunk = unique[offset:offset + 15]
        payload = {"characters": chunk, "locale": locale}
        if force:
            payload["force"] = True
        request = urllib.request.Request(
            f"{base_url}/internal/strokes/generate",
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "X-Internal-Secret": secret},
            method="POST",
        )
        try:
            with _open_internal(request) as response:
                data = response.read(256 * 1024 + 1)
            if len(data) > 256 * 1024:
                raise ValueError("response exceeds limit")
            payload = json.loads(data)
            items = payload.get("items") if isinstance(payload, dict) else None
            if not isinstance(items, list) or len(items) != len(chunk):
                raise ValueError("invalid worker items")
            for char, item in zip(chunk, items):
                expected_hex = format(ord(char), "x")
                expected_key = f"stroke_{locale.replace('-', '_')}_{expected_hex}"
                if (
                    not isinstance(item, dict)
                    or item.get("char") != char
                    or item.get("hex") != expected_hex
                    or item.get("image_key") != expected_key
                    or type(item.get("available")) is not bool
                ):
                    raise ValueError("invalid worker identity")
                if item["available"]:
                    digest = item.get("sha256")
                    size = item.get("size_bytes")
                    if (
                        not isinstance(digest, str)
                        or len(digest) != 64
                        or any(ch not in "0123456789abcdef" for ch in digest)
                        or type(size) is not int
                        or not 0 < size <= 1024 * 1024
                    ):
                        raise ValueError("invalid worker receipt")
                result[char] = item
        except (OSError, ValueError, TypeError, urllib.error.URLError) as exc:
            raise StrokeWorkerError("Dịch vụ SVG stroke chưa xác nhận lưu file trên OV. Vui lòng thử lại.") from exc
    return result
