"""Disabled and local transactional email provider with safe metadata-only logging."""

from __future__ import annotations

from datetime import datetime, timezone
import logging

from app.email.address import mask_email
from app.email.constants import DeliveryStatus
from app.email.contracts import EmailConfig, EmailDeliveryResult, RenderedEmailMessage
from app.email.providers.base import BaseEmailProvider

logger = logging.getLogger(__name__)
UTC = timezone.utc


class DisabledEmailProvider(BaseEmailProvider):
    """
    Disabled / local email provider.

    Safely logs delivery metadata (category, template_key, masked recipient)
    while strictly omitting HTML/text body contents and token values.
    """

    @property
    def provider_name(self) -> str:
        return "disabled"

    def send(
        self,
        message: RenderedEmailMessage,
        config: EmailConfig,
    ) -> EmailDeliveryResult:
        masked_rec = mask_email(message.recipient)
        now = datetime.now(UTC).replace(tzinfo=None)

        # Log only safe metadata; never log message.html_body, message.text_body, or variables
        logger.info(
            "Transactional email delivery disabled/mocked: provider=%s, category=%s, template=%s, recipient=%s, correlation_id=%s",
            self.provider_name,
            message.category,
            message.template_key,
            masked_rec,
            message.correlation_id,
        )

        return EmailDeliveryResult(
            success=True,
            status=DeliveryStatus.DISABLED,
            provider=self.provider_name,
            provider_message_id=None,
            correlation_id=message.correlation_id,
            recipient_masked=masked_rec,
            sent_at=now,
            extra={"note": "Email delivery disabled by configuration or provider setting."},
        )
