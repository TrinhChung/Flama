"""Client adapter for communicating with Flama Media Service (Go daemon on Worker 212).

Chung VPS remains the sole authority for authentication, permissions, database models,
and URL resolution. This client delegates heavy binary processing, EXIF stripping,
and CAS storage to Worker 212 over WireGuard.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import io
import json
import logging
import time
from typing import Any
import urllib.error
import urllib.request

from flask import current_app

logger = logging.getLogger(__name__)


class FlamaMediaClientError(Exception):
    def __init__(self, message: str, status_code: int = 502, error_code: str = "MEDIA_WORKER_ERROR"):
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code


def generate_upload_ticket(
    user_id: int | None = None,
    max_bytes: int | None = None,
    ttl_seconds: int = 300,
    action: str = "upload",
) -> str:
    """Generate an HMAC-SHA256 presigned upload ticket for flama-media."""
    secret = str(current_app.config.get("MEDIA_SHARED_SECRET") or "").strip()
    if not secret:
        raise FlamaMediaClientError("MEDIA_SHARED_SECRET is not configured on Chung VPS", status_code=500)

    limit = max_bytes or int(current_app.config.get("FLASHCARD_MEDIA_MAX_BYTES", 20 * 1024 * 1024))
    ticket = {
        "user_id": int(user_id) if user_id is not None else 0,
        "max_bytes": limit,
        "exp": int(time.time()) + ttl_seconds,
        "action": action,
    }

    raw_payload = json.dumps(ticket, separators=(",", ":")).encode("utf-8")
    b64_payload = base64.urlsafe_b64encode(raw_payload).decode("utf-8").rstrip("=")
    sig = hmac.new(secret.encode("utf-8"), b64_payload.encode("utf-8"), hashlib.sha256).hexdigest()
    return f"{b64_payload}.{sig}"


def send_media_to_worker(
    file_bytes: bytes,
    filename: str,
    content_type: str = "application/octet-stream",
    user_id: int | None = None,
) -> dict[str, Any]:
    """Forward a media file to Worker 212 over WireGuard for sanitization, CAS deduplication, and storage.

    Returns the Worker 212 response dict:
    {
        "asset_id": "<sha256>",
        "url": "/media/proxy/<asset_id>",
        "sha256": "<sha256>",
        "size_bytes": 1234,
        "content_type": "image/png",
        "deduplicated": bool
    }
    """
    worker_url = str(current_app.config.get("FLAMA_MEDIA_WORKER_URL", "http://10.10.0.6:4792")).rstrip("/")
    gateway_secret = str(current_app.config.get("GATEWAY_SECRET") or "").strip()
    ticket = generate_upload_ticket(user_id=user_id, max_bytes=len(file_bytes) + 1024)

    boundary = "----FlamaBoundary" + hashlib.md5(f"{time.time()}_{len(file_bytes)}".encode()).hexdigest()
    body = io.BytesIO()
    body.write(f"--{boundary}\r\n".encode("utf-8"))
    safe_filename = filename.replace('"', '\\"')
    body.write(
        f'Content-Disposition: form-data; name="file"; filename="{safe_filename}"\r\n'.encode("utf-8")
    )
    body.write(f"Content-Type: {content_type}\r\n\r\n".encode("utf-8"))
    body.write(file_bytes)
    body.write(b"\r\n")
    body.write(f"--{boundary}--\r\n".encode("utf-8"))

    upload_endpoint = f"{worker_url}/media/upload"
    headers = {
        "Content-Type": f"multipart/form-data; boundary={boundary}",
        "Authorization": f"Bearer {ticket}",
        "User-Agent": "Flama-ChungVPS/1.0",
    }
    if gateway_secret:
        headers["X-Flama-Gateway-Secret"] = gateway_secret

    req = urllib.request.Request(upload_endpoint, data=body.getvalue(), headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = resp.read()
            return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.error("[MEDIA_CLIENT] Worker 212 returned HTTP %s: %s", exc.code, err_body)
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("message") or err_json.get("error") or err_body
            err_code = err_json.get("error") or "MEDIA_WORKER_ERROR"
        except Exception:
            msg = err_body
            err_code = "MEDIA_WORKER_ERROR"
        raise FlamaMediaClientError(msg, status_code=exc.code, error_code=err_code) from exc
    except Exception as exc:
        logger.exception("[MEDIA_CLIENT] Failed to connect to media worker on 212: %s", exc)
        raise FlamaMediaClientError(
            f"Cannot connect to media worker: {exc}",
            status_code=503,
            error_code="MEDIA_WORKER_UNAVAILABLE",
        ) from exc


def send_zip_to_worker(zip_bytes: bytes, user_id: int | None = None) -> dict[str, Any]:
    """Forward a ZIP archive to Worker 212 for Zip-Slip safe extraction and CAS persistence."""
    worker_url = str(current_app.config.get("FLAMA_MEDIA_WORKER_URL", "http://10.10.0.6:4792")).rstrip("/")
    gateway_secret = str(current_app.config.get("GATEWAY_SECRET") or "").strip()
    ticket = generate_upload_ticket(user_id=user_id, max_bytes=len(zip_bytes) + 1024)

    upload_endpoint = f"{worker_url}/media/upload-zip"
    headers = {
        "Content-Type": "application/zip",
        "Authorization": f"Bearer {ticket}",
        "User-Agent": "Flama-ChungVPS/1.0",
    }
    if gateway_secret:
        headers["X-Flama-Gateway-Secret"] = gateway_secret

    req = urllib.request.Request(upload_endpoint, data=zip_bytes, headers=headers, method="POST")

    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = resp.read()
            return json.loads(data.decode("utf-8"))
    except urllib.error.HTTPError as exc:
        err_body = exc.read().decode("utf-8", errors="replace")
        logger.error("[MEDIA_CLIENT] Worker 212 returned HTTP %s on zip upload: %s", exc.code, err_body)
        try:
            err_json = json.loads(err_body)
            msg = err_json.get("message") or err_json.get("error") or err_body
            err_code = err_json.get("error") or "ZIP_PROCESSING_ERROR"
        except Exception:
            msg = err_body
            err_code = "ZIP_PROCESSING_ERROR"
        raise FlamaMediaClientError(msg, status_code=exc.code, error_code=err_code) from exc
    except Exception as exc:
        logger.exception("[MEDIA_CLIENT] Failed to connect to media worker for zip: %s", exc)
        raise FlamaMediaClientError(
            f"Cannot connect to media worker: {exc}",
            status_code=503,
            error_code="MEDIA_WORKER_UNAVAILABLE",
        ) from exc
