"""Transactional email providers package and factory."""

from __future__ import annotations

from app.email.constants import EmailProviderType
from app.email.errors import EmailConfigError
from app.email.providers.base import BaseEmailProvider
from app.email.providers.disabled import DisabledEmailProvider
from app.email.providers.memory import MemoryEmailProvider
from app.email.providers.resend import ResendHttpProvider
from app.email.providers.smtp import SmtpEmailProvider

__all__ = [
    "BaseEmailProvider",
    "DisabledEmailProvider",
    "MemoryEmailProvider",
    "ResendHttpProvider",
    "SmtpEmailProvider",
    "create_email_provider",
]


def create_email_provider(provider_type: EmailProviderType | str) -> BaseEmailProvider:
    """Factory creating the configured email delivery provider without network side effects."""
    raw_type = (
        provider_type.value
        if isinstance(provider_type, EmailProviderType)
        else str(provider_type).strip().lower()
    )

    if raw_type == EmailProviderType.MEMORY.value:
        return MemoryEmailProvider()
    if raw_type == EmailProviderType.DISABLED.value:
        return DisabledEmailProvider()
    if raw_type == EmailProviderType.RESEND.value:
        return ResendHttpProvider()
    if raw_type == EmailProviderType.SMTP.value:
        return SmtpEmailProvider()

    raise EmailConfigError(
        f"Unsupported email provider '{raw_type}'. Supported providers: {[p.value for p in EmailProviderType]}",
        extra={"provider": raw_type},
    )

