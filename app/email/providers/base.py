"""Abstract base class for transactional email delivery providers."""

from __future__ import annotations

from abc import ABC, abstractmethod

from app.email.contracts import EmailConfig, EmailDeliveryResult, RenderedEmailMessage


class BaseEmailProvider(ABC):
    """Abstract transactional email provider contract."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Unique identifier of the provider."""
        ...

    @abstractmethod
    def send(
        self,
        message: RenderedEmailMessage,
        config: EmailConfig,
    ) -> EmailDeliveryResult:
        """
        Deliver a fully rendered email message.

        Must return a structured EmailDeliveryResult and raise classified
        EmailDeliveryError (TransientEmailError or PermanentEmailError) on failures.
        """
        ...
