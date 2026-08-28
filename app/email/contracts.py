"""Typed contracts for transactional email requests, rendered payloads, and results."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from app.email.constants import (
    DEFAULT_FROM_NAME,
    DEFAULT_LOCALE,
    DEFAULT_TIMEOUT_SECONDS,
    DeliveryStatus,
    EmailCategory,
    EmailEnvironment,
    EmailProviderType,
    TemplateKey,
)


@dataclass(frozen=True)
class TransactionalEmailRequest:
    """Business caller contract for requesting a transactional email delivery."""

    template_key: TemplateKey | str
    recipient: str
    variables: dict[str, Any]
    locale: str = DEFAULT_LOCALE
    category: EmailCategory | str = EmailCategory.SYSTEM_NOTIFICATION
    correlation_id: str | None = None
    safe_metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RenderedEmailMessage:
    """Immutable fully rendered email payload ready for provider delivery."""

    recipient: str
    subject: str
    html_body: str
    text_body: str
    from_address: str
    from_name: str = DEFAULT_FROM_NAME
    reply_to: str | None = None
    category: str = EmailCategory.SYSTEM_NOTIFICATION.value
    template_key: str = ""
    correlation_id: str | None = None
    locale: str = DEFAULT_LOCALE
    safe_metadata: dict[str, Any] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True)
class EmailDeliveryResult:
    """Structured delivery outcome returned from provider and service."""

    success: bool
    status: DeliveryStatus | str
    provider: str
    provider_message_id: str | None = None
    correlation_id: str | None = None
    recipient_masked: str = ""
    original_recipient_masked: str | None = None
    error_code: str | None = None
    error_message: str | None = None
    is_transient: bool = False
    sent_at: datetime | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "status": str(self.status.value if isinstance(self.status, DeliveryStatus) else self.status),
            "provider": self.provider,
            "provider_message_id": self.provider_message_id,
            "correlation_id": self.correlation_id,
            "recipient_masked": self.recipient_masked,
            "original_recipient_masked": self.original_recipient_masked,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "is_transient": self.is_transient,
            "sent_at": self.sent_at.isoformat() if self.sent_at else None,
            "extra": self.extra,
        }


@dataclass(frozen=True)
class EmailConfig:
    """Resolved transactional email configuration."""

    enabled: bool = False
    provider: EmailProviderType | str = EmailProviderType.DISABLED
    environment: EmailEnvironment | str = EmailEnvironment.LOCAL
    from_address: str = "no-reply@flama.local"
    from_name: str = DEFAULT_FROM_NAME
    reply_to: str = ""
    recipient_allowlist: tuple[str, ...] = field(default_factory=tuple)
    redirect_all_to: str = ""
    resend_api_key: str = ""
    smtp_host: str = ""
    smtp_port: int = 587
    smtp_user: str = ""
    smtp_password: str = ""
    smtp_use_tls: bool = True
    smtp_use_ssl: bool = False
    provider_timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS
    provider_max_attempts: int = 2
    provider_retry_backoff_seconds: float = 0.25
    public_app_url: str = ""
