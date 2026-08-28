"""Transactional email service core orchestrator."""

from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timezone
import logging
import time
from typing import Any

from flask import current_app, has_app_context

from app.email.address import mask_email
from app.email.constants import (
    DEFAULT_FROM_NAME,
    DEFAULT_TIMEOUT_SECONDS,
    DeliveryStatus,
    EmailEnvironment,
    EmailProviderType,
)
from app.email.contracts import (
    EmailConfig,
    EmailDeliveryResult,
    RenderedEmailMessage,
    TransactionalEmailRequest,
)
from app.email.errors import EmailConfigError, TransientEmailError
from app.email.guard import resolve_delivery_recipient, validate_production_config
from app.email.providers import BaseEmailProvider, create_email_provider
from app.email.renderer import TemplateRenderer

logger = logging.getLogger(__name__)
UTC = timezone.utc


def resolve_email_config(app_config: dict[str, Any] | None = None) -> EmailConfig:
    """Build EmailConfig from provided dict, active Flask app context, or defaults."""
    cfg = app_config
    if cfg is None and has_app_context():
        cfg = current_app.config  # type: ignore[assignment]
    if cfg is None:
        cfg = {}

    enabled = bool(cfg.get("EMAIL_ENABLED", False))
    provider = cfg.get("EMAIL_PROVIDER", EmailProviderType.DISABLED.value)
    environment = cfg.get("EMAIL_ENVIRONMENT", EmailEnvironment.LOCAL.value)
    from_address = str(cfg.get("EMAIL_FROM_ADDRESS") or "no-reply@flama.local").strip()
    from_name = str(cfg.get("EMAIL_FROM_NAME") or DEFAULT_FROM_NAME).strip()
    reply_to = str(cfg.get("EMAIL_REPLY_TO") or "").strip()
    allowlist_raw = cfg.get("EMAIL_RECIPIENT_ALLOWLIST", ())
    if isinstance(allowlist_raw, str):
        allowlist = tuple(item.strip() for item in allowlist_raw.split(",") if item.strip())
    else:
        allowlist = tuple(str(item).strip() for item in allowlist_raw if str(item).strip())

    redirect_all_to = str(cfg.get("EMAIL_REDIRECT_ALL_TO") or "").strip()
    resend_api_key = str(cfg.get("EMAIL_RESEND_API_KEY") or "").strip()
    smtp_host = str(cfg.get("EMAIL_SMTP_HOST") or "").strip()
    smtp_port = int(cfg.get("EMAIL_SMTP_PORT") or 587)
    smtp_user = str(cfg.get("EMAIL_SMTP_USER") or "").strip()
    smtp_password = str(cfg.get("EMAIL_SMTP_PASSWORD") or "")
    smtp_use_tls = bool(cfg.get("EMAIL_SMTP_USE_TLS", True))
    smtp_use_ssl = bool(cfg.get("EMAIL_SMTP_USE_SSL", False))
    timeout = int(cfg.get("EMAIL_PROVIDER_TIMEOUT_SECONDS") or DEFAULT_TIMEOUT_SECONDS)
    max_attempts = max(int(cfg.get("EMAIL_PROVIDER_MAX_ATTEMPTS") or 2), 1)
    retry_backoff = max(float(cfg.get("EMAIL_PROVIDER_RETRY_BACKOFF_SECONDS") or 0.25), 0.0)
    public_app_url = str(cfg.get("PUBLIC_APP_URL") or cfg.get("FRONTEND_URL") or "").strip().rstrip("/")

    return EmailConfig(
        enabled=enabled,
        provider=provider,
        environment=environment,
        from_address=from_address,
        from_name=from_name,
        reply_to=reply_to,
        recipient_allowlist=allowlist,
        redirect_all_to=redirect_all_to,
        resend_api_key=resend_api_key,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        smtp_user=smtp_user,
        smtp_password=smtp_password,
        smtp_use_tls=smtp_use_tls,
        smtp_use_ssl=smtp_use_ssl,
        provider_timeout_seconds=timeout,
        provider_max_attempts=max_attempts,
        provider_retry_backoff_seconds=retry_backoff,
        public_app_url=public_app_url,
    )


class TransactionalEmailService:
    """Core provider-neutral transactional email service."""

    def __init__(
        self,
        config: EmailConfig | None = None,
        provider: BaseEmailProvider | None = None,
        renderer: TemplateRenderer | None = None,
    ) -> None:
        self._config = config or resolve_email_config()
        self._renderer = renderer or TemplateRenderer()
        self._provider = provider or create_email_provider(self._config.provider)

    @property
    def config(self) -> EmailConfig:
        return self._config

    @property
    def provider(self) -> BaseEmailProvider:
        return self._provider

    @property
    def renderer(self) -> TemplateRenderer:
        return self._renderer

    def send(self, request: TransactionalEmailRequest) -> EmailDeliveryResult:
        """
        Validate, render, guard, and deliver a transactional email request.

        Safety:
        - Strict finite category and template key verification
        - HTML variable autoescaping
        - Address and CRLF injection prevention
        - Production fail-closed check
        - Non-production recipient redirect / allowlist guard
        - Disabled / EMAIL_ENABLED=False predictable return without external network call
        """
        now = datetime.now(UTC).replace(tzinfo=None)
        masked_rec = mask_email(getattr(request, "recipient", None))

        # 1. Production config validation
        validate_production_config(self._config)

        # 2. Check EMAIL_ENABLED
        if not self._config.enabled:
            logger.info(
                "Email delivery skipped (EMAIL_ENABLED is False): template=%s, recipient=%s, correlation_id=%s",
                getattr(request, "template_key", ""),
                masked_rec,
                getattr(request, "correlation_id", None),
            )
            return EmailDeliveryResult(
                success=True,
                status=DeliveryStatus.DISABLED,
                provider=self._provider.provider_name,
                provider_message_id=None,
                correlation_id=request.correlation_id,
                recipient_masked=masked_rec,
                sent_at=now,
                extra={"reason": "EMAIL_ENABLED is false"},
            )

        # 3. Render email message from version-controlled templates
        rendered = self._renderer.render(
            request,
            from_address=self._config.from_address,
            from_name=self._config.from_name,
            reply_to=self._config.reply_to or None,
        )

        # 4. Resolve delivery recipient with environment guards
        effective_recipient, orig_recipient, is_redirected = resolve_delivery_recipient(
            rendered.recipient,
            self._config,
        )

        final_message = rendered
        if is_redirected and orig_recipient:
            # Update recipient and attach tracing header
            new_headers = dict(rendered.headers)
            new_headers["X-Original-Recipient"] = orig_recipient
            final_message = replace(
                rendered,
                recipient=effective_recipient,
                headers=new_headers,
            )

        # 5. Deliver through configured provider
        delivery_result: EmailDeliveryResult | None = None
        for attempt in range(1, self._config.provider_max_attempts + 1):
            try:
                delivery_result = self._provider.send(final_message, self._config)
                break
            except TransientEmailError:
                if attempt >= self._config.provider_max_attempts:
                    raise
                delay = self._config.provider_retry_backoff_seconds * (2 ** (attempt - 1))
                logger.warning(
                    "Transient email delivery failure; retrying provider=%s attempt=%d/%d delay_seconds=%.2f correlation_id=%s",
                    self._provider.provider_name,
                    attempt + 1,
                    self._config.provider_max_attempts,
                    delay,
                    final_message.correlation_id,
                )
                if delay > 0:
                    time.sleep(delay)

        if delivery_result is None:  # pragma: no cover - defensive invariant
            raise RuntimeError("Email provider completed without a delivery result.")

        # If redirected, augment delivery result
        if is_redirected and orig_recipient:
            final_status = (
                DeliveryStatus.REDIRECTED
                if delivery_result.status == DeliveryStatus.SENT
                else delivery_result.status
            )
            delivery_result = replace(
                delivery_result,
                status=final_status,
                original_recipient_masked=mask_email(orig_recipient),
                recipient_masked=mask_email(effective_recipient),
            )

        return delivery_result


def get_email_service(
    app_config: dict[str, Any] | None = None,
    *,
    provider: BaseEmailProvider | None = None,
) -> TransactionalEmailService:
    """Factory helper to obtain a TransactionalEmailService instance."""
    config = resolve_email_config(app_config)
    return TransactionalEmailService(config=config, provider=provider)
