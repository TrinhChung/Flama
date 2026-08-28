"""Resend HTTP transactional email API provider adapter."""

from __future__ import annotations

from datetime import datetime, timezone
import json
import logging
import socket
from typing import Any
import urllib.error
import urllib.request

from app.email.address import format_sender_header, mask_email
from app.email.constants import DEFAULT_TIMEOUT_SECONDS, DeliveryStatus
from app.email.contracts import EmailConfig, EmailDeliveryResult, RenderedEmailMessage
from app.email.errors import (
    EmailConfigError,
    PermanentEmailError,
    TransientEmailError,
)
from app.email.providers.base import BaseEmailProvider

logger = logging.getLogger(__name__)
UTC = timezone.utc

RESEND_API_ENDPOINT = "https://api.resend.com/emails"


class ResendHttpProvider(BaseEmailProvider):
    """HTTP client adapter for Resend transactional email API using Python standard library."""

    def __init__(self, endpoint_url: str = RESEND_API_ENDPOINT) -> None:
        self.endpoint_url = endpoint_url

    @property
    def provider_name(self) -> str:
        return "resend"

    def build_payload(self, message: RenderedEmailMessage) -> dict[str, Any]:
        """Map RenderedEmailMessage into Resend API JSON payload."""
        from_header = format_sender_header(message.from_address, message.from_name)
        payload: dict[str, Any] = {
            "from": from_header,
            "to": [message.recipient],
            "subject": message.subject,
            "html": message.html_body,
            "text": message.text_body,
        }

        if message.reply_to:
            payload["reply_to"] = [message.reply_to]

        if message.headers:
            payload["headers"] = dict(message.headers)

        if message.category:
            payload["tags"] = [{"name": "category", "value": str(message.category)}]

        return payload

    def build_headers(
        self,
        api_key: str,
        correlation_id: str | None = None,
    ) -> dict[str, str]:
        """Construct HTTP headers for Resend API request including Idempotency-Key."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Flama-Transactional-Email/1.0",
        }
        if correlation_id and correlation_id.strip():
            headers["Idempotency-Key"] = correlation_id.strip()
        return headers

    def send(
        self,
        message: RenderedEmailMessage,
        config: EmailConfig,
    ) -> EmailDeliveryResult:
        """Send message via Resend HTTP API with timeout and error classification."""
        api_key = (config.resend_api_key or "").strip()
        if not api_key:
            raise EmailConfigError(
                "Resend provider cannot send email: EMAIL_RESEND_API_KEY is not configured.",
                extra={"provider": self.provider_name},
            )

        timeout = int(config.provider_timeout_seconds or DEFAULT_TIMEOUT_SECONDS)
        payload = self.build_payload(message)
        headers = self.build_headers(api_key, correlation_id=message.correlation_id)

        try:
            body_bytes = json.dumps(payload).encode("utf-8")
        except (TypeError, ValueError) as exc:
            raise PermanentEmailError(
                f"Failed to serialize Resend payload: {exc}",
                extra={"provider": self.provider_name},
            ) from exc

        req = urllib.request.Request(
            url=self.endpoint_url,
            data=body_bytes,
            headers=headers,
            method="POST",
        )

        masked_rec = mask_email(message.recipient)
        start_time = datetime.now(UTC)

        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                status_code = response.getcode()
                response_body = response.read().decode("utf-8")
                now = datetime.now(UTC).replace(tzinfo=None)

                try:
                    data = json.loads(response_body) if response_body else {}
                except json.JSONDecodeError:
                    data = {}

                provider_message_id = data.get("id")
                if not provider_message_id and isinstance(data, dict):
                    provider_message_id = data.get("data", {}).get("id")

                logger.info(
                    "Resend delivery accepted: msg_id=%s, recipient=%s, category=%s, correlation_id=%s, status=%d",
                    provider_message_id,
                    masked_rec,
                    message.category,
                    message.correlation_id,
                    status_code,
                )

                return EmailDeliveryResult(
                    success=True,
                    status=DeliveryStatus.SENT,
                    provider=self.provider_name,
                    provider_message_id=str(provider_message_id) if provider_message_id else None,
                    correlation_id=message.correlation_id,
                    recipient_masked=masked_rec,
                    sent_at=now,
                    extra={
                        "http_status": status_code,
                        "elapsed_ms": int((datetime.now(UTC) - start_time).total_seconds() * 1000),
                    },
                )

        except urllib.error.HTTPError as exc:
            status_code = exc.code
            raw_err = ""
            try:
                raw_err = exc.read().decode("utf-8")
            except Exception:
                pass

            err_data: dict[str, Any] = {}
            try:
                err_data = json.loads(raw_err) if raw_err else {}
            except Exception:
                pass

            error_message = (
                err_data.get("message")
                or err_data.get("error", {}).get("message")
                or str(exc.reason)
            )

            # Classify error: 429 and 5xx are transient; 4xx are permanent
            is_transient = status_code == 429 or status_code >= 500
            err_extra = {
                "http_status": status_code,
                "provider": self.provider_name,
                "recipient_masked": masked_rec,
                "category": message.category,
                "correlation_id": message.correlation_id,
                "resend_error_name": err_data.get("name"),
            }

            logger.error(
                "Resend API error: status=%d, transient=%s, recipient=%s, error=%s",
                status_code,
                is_transient,
                masked_rec,
                error_message,
            )

            if is_transient:
                raise TransientEmailError(
                    f"Resend temporary error ({status_code}): {error_message}",
                    code="RESEND_TRANSIENT_ERROR",
                    extra=err_extra,
                ) from exc
            else:
                raise PermanentEmailError(
                    f"Resend client error ({status_code}): {error_message}",
                    code="RESEND_PERMANENT_ERROR",
                    extra=err_extra,
                ) from exc

        except (urllib.error.URLError, TimeoutError, socket.timeout, socket.gaierror, OSError) as exc:
            logger.error(
                "Resend network error: recipient=%s, correlation_id=%s, error=%s",
                masked_rec,
                message.correlation_id,
                exc,
            )
            raise TransientEmailError(
                f"Resend network/connection error: {exc}",
                code="RESEND_NETWORK_ERROR",
                extra={
                    "provider": self.provider_name,
                    "recipient_masked": masked_rec,
                    "correlation_id": message.correlation_id,
                },
            ) from exc
