"""Transactional email constants, enums, and default values."""

from __future__ import annotations

from enum import Enum


class EmailCategory(str, Enum):
    """Finite set of recognized email categories."""

    SECURITY_PASSWORD_RESET = "security.password_reset"
    SECURITY_PASSWORD_CHANGED = "security.password_changed"
    IDENTITY_EMAIL_VERIFICATION = "identity.email_verification"
    BILLING_PAYMENT_RECEIPT = "billing.payment_receipt"
    BILLING_PAYMENT_ISSUE = "billing.payment_issue"
    COMMUNITY_MODERATION = "community.moderation"
    SYSTEM_NOTIFICATION = "system.notification"


class TemplateKey(str, Enum):
    """Finite set of recognized transactional email template keys."""

    SECURITY_PASSWORD_RESET = "security.password_reset"
    SECURITY_PASSWORD_CHANGED = "security.password_changed"
    IDENTITY_EMAIL_VERIFICATION = "identity.email_verification"
    SYSTEM_DELIVERY_TEST = "system.delivery_test"


class EmailProviderType(str, Enum):
    """Recognized transactional email providers."""

    MEMORY = "memory"
    DISABLED = "disabled"
    RESEND = "resend"
    SMTP = "smtp"



class EmailEnvironment(str, Enum):
    """Recognized deployment environments for email safety guards."""

    TEST = "test"
    LOCAL = "local"
    STAGING = "staging"
    PRODUCTION = "production"


class DeliveryStatus(str, Enum):
    """Standardized delivery outcome status."""

    SENT = "sent"
    DISABLED = "disabled"
    REDIRECTED = "redirected"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    FAILED = "failed"


DEFAULT_LOCALE = "vi"
SUPPORTED_LOCALES = ("vi", "ja", "en")
DEFAULT_FROM_NAME = "Flama"
DEFAULT_TIMEOUT_SECONDS = 10
MAX_EMAIL_LENGTH = 254
MAX_LOCAL_PART_LENGTH = 64

# Category to template key compatibility map
ALLOWED_CATEGORY_TEMPLATE_MAP: dict[TemplateKey, set[EmailCategory]] = {
    TemplateKey.SECURITY_PASSWORD_RESET: {
        EmailCategory.SECURITY_PASSWORD_RESET,
        EmailCategory.SYSTEM_NOTIFICATION,
    },
    TemplateKey.SECURITY_PASSWORD_CHANGED: {
        EmailCategory.SECURITY_PASSWORD_CHANGED,
        EmailCategory.SYSTEM_NOTIFICATION,
    },
    TemplateKey.IDENTITY_EMAIL_VERIFICATION: {
        EmailCategory.IDENTITY_EMAIL_VERIFICATION,
        EmailCategory.SYSTEM_NOTIFICATION,
    },
    TemplateKey.SYSTEM_DELIVERY_TEST: {
        EmailCategory.SYSTEM_NOTIFICATION,
    },
}
