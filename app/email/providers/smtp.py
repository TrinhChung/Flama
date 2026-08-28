"""Standard SMTP transactional email provider adapter."""

from __future__ import annotations

from datetime import datetime, timezone
from email.header import Header
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import logging
import smtplib
import socket
from typing import Any
import uuid

from app.email.address import format_sender_header, mask_email
from app.email.constants import DEFAULT_TIMEOUT_SECONDS, DeliveryStatus
from app.email.contracts import EmailConfig, EmailDeliveryResult, RenderedEmailMessage
from app.email.errors import EmailConfigError, PermanentEmailError, TransientEmailError
from app.email.providers.base import BaseEmailProvider

logger = logging.getLogger(__name__)
UTC = timezone.utc


class SmtpEmailProvider(BaseEmailProvider):
    """Standard SMTP provider adapter using Python standard library smtplib."""

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
        user: str | None = None,
        password: str | None = None,
        use_tls: bool = True,
        use_ssl: bool = False,
    ) -> None:
        self.host = host
        self.port = port
        self.user = user
        self.password = password
        self.use_tls = use_tls
        self.use_ssl = use_ssl

    @property
    def provider_name(self) -> str:
        return "smtp"

    def build_mime_message(self, message: RenderedEmailMessage) -> MIMEMultipart:
        """Construct standard RFC MIME multipart/alternative email message."""
        msg = MIMEMultipart("alternative")
        msg["Subject"] = Header(message.subject, "utf-8").encode()
        msg["From"] = format_sender_header(message.from_address, message.from_name)
        msg["To"] = message.recipient
        if message.reply_to:
            msg["Reply-To"] = message.reply_to

        msg_id = f"<{uuid.uuid4().hex}@{message.from_address.split('@')[-1]}>"
        msg["Message-ID"] = msg_id

        if message.correlation_id:
            msg["X-Correlation-ID"] = message.correlation_id

        for k, v in message.headers.items():
            if k not in msg:
                msg[k] = v

        # Plain text part first, HTML part second
        if message.text_body:
            part_text = MIMEText(message.text_body, "plain", "utf-8")
            msg.attach(part_text)
        if message.html_body:
            part_html = MIMEText(message.html_body, "html", "utf-8")
            msg.attach(part_html)

        return msg

    def send(
        self,
        message: RenderedEmailMessage,
        config: EmailConfig,
    ) -> EmailDeliveryResult:
        """Send message via SMTP server with TLS/SSL, authentication, and error classification."""
        host = (self.host or config.smtp_host).strip()
        port = int(self.port or config.smtp_port or 587)
        user = (self.user or config.smtp_user).strip()
        raw_password = (self.password or config.smtp_password or "").strip()
        # If host is Gmail and password contains 16 chars with spaces, remove spaces
        if "gmail.com" in host.lower() and len(raw_password.replace(" ", "")) == 16:
            password = raw_password.replace(" ", "")
        else:
            password = raw_password
        use_tls = self.use_tls if self.host is not None else config.smtp_use_tls
        use_ssl = self.use_ssl if self.host is not None else config.smtp_use_ssl
        timeout = int(config.provider_timeout_seconds or DEFAULT_TIMEOUT_SECONDS)

        if not host:
            raise EmailConfigError(
                "SMTP provider requires EMAIL_SMTP_HOST configuration.",
                extra={"provider": self.provider_name},
            )

        mime_msg = self.build_mime_message(message)
        masked_rec = mask_email(message.recipient)
        start_time = datetime.now(UTC)

        server: smtplib.SMTP | smtplib.SMTP_SSL | None = None
        try:
            if use_ssl:
                server = smtplib.SMTP_SSL(host=host, port=port, timeout=timeout)
            else:
                server = smtplib.SMTP(host=host, port=port, timeout=timeout)
                server.ehlo()
                if use_tls:
                    server.starttls()
                    server.ehlo()

            if user and password:
                server.login(user, password)

            server.send_message(mime_msg)
            now = datetime.now(UTC).replace(tzinfo=None)
            msg_id = mime_msg.get("Message-ID")

            logger.info(
                "SMTP email delivered: msg_id=%s, recipient=%s, category=%s, correlation_id=%s",
                msg_id,
                masked_rec,
                message.category,
                message.correlation_id,
            )

            return EmailDeliveryResult(
                success=True,
                status=DeliveryStatus.SENT,
                provider=self.provider_name,
                provider_message_id=msg_id,
                correlation_id=message.correlation_id,
                recipient_masked=masked_rec,
                sent_at=now,
                extra={
                    "host": host,
                    "port": port,
                    "elapsed_ms": int((datetime.now(UTC) - start_time).total_seconds() * 1000),
                },
            )

        except smtplib.SMTPAuthenticationError as exc:
            logger.error("SMTP authentication failed for user %s: %s", user, exc)
            raise PermanentEmailError(
                f"SMTP authentication failed: {exc}",
                code="SMTP_AUTH_ERROR",
                extra={"provider": self.provider_name, "host": host, "user": user},
            ) from exc

        except smtplib.SMTPRecipientsRefused as exc:
            logger.error("SMTP recipient refused for %s: %s", masked_rec, exc)
            raise PermanentEmailError(
                f"SMTP recipient refused: {exc}",
                code="SMTP_RECIPIENT_REFUSED",
                extra={"provider": self.provider_name, "recipient_masked": masked_rec},
            ) from exc

        except (smtplib.SMTPSenderRefused, smtplib.SMTPDataError) as exc:
            logger.error("SMTP permanent error: %s", exc)
            raise PermanentEmailError(
                f"SMTP delivery error: {exc}",
                code="SMTP_PERMANENT_ERROR",
                extra={"provider": self.provider_name},
            ) from exc

        except (
            smtplib.SMTPServerDisconnected,
            smtplib.SMTPConnectError,
            smtplib.SMTPException,
            socket.timeout,
            TimeoutError,
            OSError,
        ) as exc:
            logger.error("SMTP network / transient error: %s", exc)
            raise TransientEmailError(
                f"SMTP connection error: {exc}",
                code="SMTP_TRANSIENT_ERROR",
                extra={"provider": self.provider_name, "host": host},
            ) from exc

        finally:
            if server is not None:
                try:
                    server.quit()
                except Exception:
                    pass
