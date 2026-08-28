"""Transactional email subsystem for Flama."""

from __future__ import annotations

from app.email.address import mask_email, validate_email_address
from app.email.constants import (
    DEFAULT_FROM_NAME,
    DEFAULT_LOCALE,
    DeliveryStatus,
    EmailCategory,
    EmailEnvironment,
    EmailProviderType,
    TemplateKey,
)
from app.email.contracts import (
    EmailConfig,
    EmailDeliveryResult,
    RenderedEmailMessage,
    TransactionalEmailRequest,
)
from app.email.errors import (
    EmailConfigError,
    EmailDeliveryError,
    EmailError,
    EmailValidationError,
    HeaderInjectionError,
    PermanentEmailError,
    RecipientNotAllowedError,
    TransientEmailError,
)
from app.email.providers import (
    BaseEmailProvider,
    DisabledEmailProvider,
    MemoryEmailProvider,
    ResendHttpProvider,
    SmtpEmailProvider,
    create_email_provider,
)
from app.email.renderer import TemplateRenderer
from app.email.service import (
    TransactionalEmailService,
    get_email_service,
    resolve_email_config,
)

__all__ = [
    "BaseEmailProvider",
    "DEFAULT_FROM_NAME",
    "DEFAULT_LOCALE",
    "DeliveryStatus",
    "DisabledEmailProvider",
    "EmailCategory",
    "EmailConfig",
    "EmailConfigError",
    "EmailDeliveryError",
    "EmailDeliveryResult",
    "EmailEnvironment",
    "EmailError",
    "EmailProviderType",
    "EmailValidationError",
    "HeaderInjectionError",
    "MemoryEmailProvider",
    "PermanentEmailError",
    "RecipientNotAllowedError",
    "RenderedEmailMessage",
    "ResendHttpProvider",
    "SmtpEmailProvider",
    "TemplateKey",
    "TemplateRenderer",
    "TransactionalEmailRequest",
    "TransactionalEmailService",
    "TransientEmailError",
    "create_email_provider",
    "get_email_service",
    "mask_email",
    "resolve_email_config",
    "validate_email_address",
]

