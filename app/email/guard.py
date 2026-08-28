"""Environment-level recipient safety guards and production fail-closed validator."""

from __future__ import annotations

from typing import Tuple
from urllib.parse import urlparse

from app.email.address import mask_email, validate_email_address
from app.email.constants import EmailEnvironment, EmailProviderType
from app.email.contracts import EmailConfig
from app.email.errors import EmailConfigError, RecipientNotAllowedError


def validate_production_config(config: EmailConfig) -> None:
    """Ensure production deployment fails closed if essential email credentials/URLs are missing."""
    environment = (
        config.environment.value
        if isinstance(config.environment, EmailEnvironment)
        else str(config.environment).lower().strip()
    )
    if environment != EmailEnvironment.PRODUCTION.value:
        return

    provider = (
        config.provider.value
        if isinstance(config.provider, EmailProviderType)
        else str(config.provider).lower().strip()
    )

    if not config.enabled:
        return

    # Live providers must fail closed when production credentials are incomplete.
    if provider == EmailProviderType.RESEND.value:
        if not config.resend_api_key or not config.resend_api_key.strip():
            raise EmailConfigError(
                "Production email is enabled with 'resend' provider, but EMAIL_RESEND_API_KEY is missing.",
                extra={"environment": environment, "provider": provider},
            )

        if not config.from_address or not config.from_address.strip():
            raise EmailConfigError(
                "Production email requires a valid EMAIL_FROM_ADDRESS.",
                extra={"environment": environment},
            )

        validate_email_address(config.from_address, field_name="EMAIL_FROM_ADDRESS")

        if not config.public_app_url or not config.public_app_url.strip():
            raise EmailConfigError(
                "Production email requires a configured PUBLIC_APP_URL for canonical links.",
                extra={"environment": environment},
            )

        parsed_url = urlparse(config.public_app_url.strip())
        if not parsed_url.scheme or not parsed_url.netloc:
            raise EmailConfigError(
                f"PUBLIC_APP_URL '{config.public_app_url}' is not a valid absolute URL.",
                extra={"public_app_url": config.public_app_url},
            )

    if provider == EmailProviderType.SMTP.value:
        if not config.smtp_host or not config.smtp_host.strip():
            raise EmailConfigError(
                "Production email is enabled with 'smtp' provider, but EMAIL_SMTP_HOST is missing.",
                extra={"environment": environment, "provider": provider},
            )
        if not config.from_address or not config.from_address.strip():
            raise EmailConfigError(
                "Production email requires a valid EMAIL_FROM_ADDRESS.",
                extra={"environment": environment},
            )
        validate_email_address(config.from_address, field_name="EMAIL_FROM_ADDRESS")
        if not config.public_app_url or not config.public_app_url.strip():
            raise EmailConfigError(
                "Production email requires a configured PUBLIC_APP_URL for canonical links.",
                extra={"environment": environment},
            )


def is_recipient_allowed(recipient: str, allowlist: tuple[str, ...]) -> bool:
    """Check if recipient matches exact address or domain wildcard in allowlist."""
    norm_rec = recipient.strip().lower()
    rec_domain = norm_rec.split("@")[-1] if "@" in norm_rec else ""

    for pattern in allowlist:
        clean = pattern.strip().lower()
        if not clean:
            continue
        if clean in ("*", "*@*", "*.*"):
            return True
        if clean == norm_rec:
            return True
        if clean.startswith("@") and rec_domain == clean.lstrip("@"):
            return True
        if clean.startswith("*@") and rec_domain == clean[2:]:
            return True
    return False



def resolve_delivery_recipient(
    recipient: str,
    config: EmailConfig,
) -> Tuple[str, str | None, bool]:
    """
    Apply environment safety guards to determine effective delivery recipient.

    Returns:
        (effective_recipient, original_recipient_or_none, is_redirected)
    """
    environment = (
        config.environment.value
        if isinstance(config.environment, EmailEnvironment)
        else str(config.environment).lower().strip()
    )
    provider = (
        config.provider.value
        if isinstance(config.provider, EmailProviderType)
        else str(config.provider).lower().strip()
    )

    clean_recipient = recipient.strip()

    # 1. In production, send directly to intended recipient
    if environment == EmailEnvironment.PRODUCTION.value:
        return clean_recipient, None, False

    # 2. Non-production: check redirection
    if config.redirect_all_to and config.redirect_all_to.strip():
        redirect_target = validate_email_address(
            config.redirect_all_to.strip(),
            field_name="EMAIL_REDIRECT_ALL_TO",
        )
        return redirect_target, clean_recipient, True

    # 3. Non-production: check allowlist
    if config.recipient_allowlist:
        if is_recipient_allowed(clean_recipient, config.recipient_allowlist):
            return clean_recipient, None, False
        raise RecipientNotAllowedError(
            f"Recipient '{mask_email(clean_recipient)}' is not in non-production allowlist.",
            extra={
                "environment": environment,
                "recipient_masked": mask_email(clean_recipient),
            },
        )

    # 4. Non-production without redirect or allowlist
    # Live providers must not send to arbitrary recipients outside production.
    if provider in {EmailProviderType.RESEND.value, EmailProviderType.SMTP.value}:
        raise RecipientNotAllowedError(
            "Non-production live email delivery is blocked because neither EMAIL_REDIRECT_ALL_TO "
            "nor EMAIL_RECIPIENT_ALLOWLIST is configured.",
            extra={"environment": environment, "provider": provider},
        )

    # Memory and disabled providers are safe sinks
    return clean_recipient, None, False
