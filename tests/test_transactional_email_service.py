"""Unit and integration tests for transactional email core subsystem."""

from __future__ import annotations

import io
import json
import logging
import smtplib
import socket
import unittest
from unittest.mock import MagicMock, patch
import urllib.error

from app import create_app
from app.email import (
    DeliveryStatus,
    DisabledEmailProvider,
    EmailCategory,
    EmailConfig,
    EmailConfigError,
    EmailEnvironment,
    EmailProviderType,
    EmailValidationError,
    HeaderInjectionError,
    MemoryEmailProvider,
    PermanentEmailError,
    RecipientNotAllowedError,
    RenderedEmailMessage,
    ResendHttpProvider,
    SmtpEmailProvider,
    TemplateKey,
    TemplateRenderer,
    TransactionalEmailRequest,
    TransactionalEmailService,
    TransientEmailError,
    get_email_service,
    mask_email,
    resolve_email_config,
    validate_email_address,
)
from app.email.address import assert_no_header_injection, format_sender_header


class TransactionalEmailServiceTests(unittest.TestCase):
    """Comprehensive test suite for the provider-neutral transactional email subsystem."""

    def setUp(self) -> None:
        self.memory_provider = MemoryEmailProvider()
        self.default_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.MEMORY,
            environment=EmailEnvironment.TEST,
            from_address="no-reply@flama.local",
            from_name="Flama",
            reply_to="support@flama.local",
            public_app_url="https://flama.local",
        )
        self.service = TransactionalEmailService(
            config=self.default_config,
            provider=self.memory_provider,
        )

    # --------------------------------------------------------------------------
    # 1. Template Rendering & HTML Autoescaping
    # --------------------------------------------------------------------------

    def test_render_password_reset_html_and_text(self) -> None:
        """Render password reset email and verify HTML, plaintext, CTA, and expiration."""
        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={
                "reset_url": "https://flama.local/reset-password?token=secret_token_123",
                "recipient_name": "Tài khoản Flama",
                "expires_in_minutes": 15,
                "support_email": "support@flama.local",
            },
            category=EmailCategory.SECURITY_PASSWORD_RESET,
            correlation_id="corr-reset-1",
        )

        res = self.service.send(req)
        self.assertTrue(res.success)
        self.assertEqual(res.status, DeliveryStatus.SENT)
        self.assertEqual(len(self.memory_provider.sent_messages), 1)

        msg = self.memory_provider.get_last_message()
        self.assertIsNotNone(msg)
        assert msg is not None

        self.assertEqual(msg.recipient, "user@example.com")
        self.assertEqual(msg.subject, "[Flama] Yêu cầu đặt lại mật khẩu")
        self.assertEqual(msg.category, EmailCategory.SECURITY_PASSWORD_RESET.value)
        self.assertEqual(msg.correlation_id, "corr-reset-1")

        # HTML body checks
        self.assertIn("https://flama.local/reset-password?token=secret_token_123", msg.html_body)
        self.assertIn("Đặt lại mật khẩu", msg.html_body)
        self.assertIn("15 phút", msg.html_body)
        self.assertIn("Tài khoản Flama", msg.html_body)

        # Plain-text body checks
        self.assertIn("https://flama.local/reset-password?token=secret_token_123", msg.text_body)
        self.assertIn("15 phút", msg.text_body)
        self.assertIn("Tài khoản Flama", msg.text_body)

    def test_render_password_changed_html_and_text(self) -> None:
        """Render password changed notification and verify HTML, text, and security warning."""
        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_CHANGED,
            recipient="user@example.com",
            variables={
                "recipient_name": "Nguyễn Văn A",
                "changed_at": "2026-08-28 21:00:00 UTC",
                "device_summary": "Chrome on Windows (IP: 192.0.2.1)",
                "support_email": "security@flama.local",
            },
            category=EmailCategory.SECURITY_PASSWORD_CHANGED,
            correlation_id="corr-changed-1",
        )

        res = self.service.send(req)
        self.assertTrue(res.success)
        self.assertEqual(res.status, DeliveryStatus.SENT)

        msg = self.memory_provider.get_last_message()
        self.assertIsNotNone(msg)
        assert msg is not None

        self.assertEqual(msg.subject, "[Flama] Mật khẩu tài khoản của bạn đã được thay đổi")
        self.assertIn("Nguyễn Văn A", msg.html_body)
        self.assertIn("2026-08-28 21:00:00 UTC", msg.html_body)
        self.assertIn("Chrome on Windows (IP: 192.0.2.1)", msg.html_body)
        self.assertIn("security@flama.local", msg.html_body)

        # Plain text
        self.assertIn("Nguyễn Văn A", msg.text_body)
        self.assertIn("security@flama.local", msg.text_body)

    def test_html_autoescape_prevents_xss(self) -> None:
        """Autoescape must escape malicious HTML variables into safe entity references."""
        xss_payload = "<script>alert('xss')</script>"
        img_payload = '<img src="x" onerror="stealCookies()">'

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_CHANGED,
            recipient="user@example.com",
            variables={
                "recipient_name": xss_payload,
                "device_summary": img_payload,
                "support_email": "support@flama.local",
            },
            category=EmailCategory.SECURITY_PASSWORD_CHANGED,
        )

        self.service.send(req)
        msg = self.memory_provider.get_last_message()
        assert msg is not None

        # Verify raw script/img tags are not present in HTML
        self.assertNotIn("<script>", msg.html_body)
        self.assertNotIn("<img", msg.html_body)
        self.assertIn("&lt;script&gt;alert(&#39;xss&#39;)&lt;/script&gt;", msg.html_body)
        self.assertIn("&lt;img src=&#34;x&#34; onerror=&#34;stealCookies()&#34;&gt;", msg.html_body)

    # --------------------------------------------------------------------------
    # 2. Required Variables Validation
    # --------------------------------------------------------------------------

    def test_missing_required_variable_raises(self) -> None:
        """Missing required variables like reset_url must raise EmailValidationError."""
        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={},  # missing reset_url
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(EmailValidationError) as ctx:
            self.service.send(req)
        self.assertIn("Missing required template variables", str(ctx.exception))

    def test_invalid_reset_url_scheme_raises(self) -> None:
        """Non-http/https schemes in reset_url must be rejected."""
        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "javascript:alert(1)"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(EmailValidationError) as ctx:
            self.service.send(req)
        self.assertIn("must be a valid http or https URL", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 3. Finite Template Key and Category Validation
    # --------------------------------------------------------------------------

    def test_unknown_template_key_rejected(self) -> None:
        """Arbitrary/unregistered template keys must be rejected."""
        req = TransactionalEmailRequest(
            template_key="unknown_random_template",
            recipient="user@example.com",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(EmailValidationError) as ctx:
            self.service.send(req)
        self.assertIn("Unknown template_key", str(ctx.exception))

    def test_unknown_category_rejected(self) -> None:
        """Arbitrary category strings must be rejected."""
        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "https://flama.local/reset"},
            category="unregistered_arbitrary_category",
        )

        with self.assertRaises(EmailValidationError) as ctx:
            self.service.send(req)
        self.assertIn("Unknown category", str(ctx.exception))

    def test_category_template_mismatch_rejected(self) -> None:
        """Incompatible category and template key combinations must be rejected."""
        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.BILLING_PAYMENT_RECEIPT,  # Incompatible category
        )

        with self.assertRaises(EmailValidationError) as ctx:
            self.service.send(req)
        self.assertIn("is not valid for template_key", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 4. Address Validation, Header Injection Prevention & Masking
    # --------------------------------------------------------------------------

    def test_crlf_in_recipient_rejected(self) -> None:
        """Carriage return or line feed in recipient address must raise HeaderInjectionError."""
        malicious_addresses = [
            "victim@example.com\r\nBcc: evil@attacker.com",
            "victim@example.com\nBcc: evil@attacker.com",
            "victim@example.com\rBcc: evil@attacker.com",
            "victim%0a@example.com",
            "victim%0d@example.com",
        ]
        for addr in malicious_addresses:
            with self.subTest(addr=addr):
                req = TransactionalEmailRequest(
                    template_key=TemplateKey.SECURITY_PASSWORD_RESET,
                    recipient=addr,
                    variables={"reset_url": "https://flama.local/reset"},
                    category=EmailCategory.SECURITY_PASSWORD_RESET,
                )
                with self.assertRaises(HeaderInjectionError):
                    self.service.send(req)

    def test_crlf_in_sender_identity_rejected(self) -> None:
        """Carriage return or line feed in from_name or from_address must be rejected."""
        with self.assertRaises(HeaderInjectionError):
            assert_no_header_injection("Flama Admin\r\nSubject: Injected", "from_name")

    def test_crlf_in_reset_url_rejected(self) -> None:
        """CRLF inside reset_url variable must be rejected."""
        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "https://flama.local/reset\r\nSet-Cookie: evil"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )
        with self.assertRaises(HeaderInjectionError):
            self.service.send(req)

    def test_invalid_email_syntax_rejected(self) -> None:
        """Malformed email strings must raise EmailValidationError."""
        invalid_emails = [
            "",
            "   ",
            "not-an-email",
            "user@",
            "@domain.com",
            "user@domain",
            "user..double@domain.com",
            "user@domain..com",
            "user space@domain.com",
        ]
        for addr in invalid_emails:
            with self.subTest(addr=addr):
                with self.assertRaises(EmailValidationError):
                    validate_email_address(addr)

    def test_email_masking_for_pii_logging(self) -> None:
        """Masking utility must safely obfuscate addresses without crashing."""
        self.assertEqual(mask_email("alice@example.com"), "a***e@example.com")
        self.assertEqual(mask_email("ab@domain.com"), "a***@domain.com")
        self.assertEqual(mask_email("a@domain.com"), "a***@domain.com")
        self.assertEqual(mask_email("user.name+tag@sub.domain.org"), "u***g@sub.domain.org")
        self.assertEqual(mask_email(""), "***")
        self.assertEqual(mask_email(None), "***")
        self.assertEqual(mask_email("not-valid"), "***")

    def test_sender_header_formatting(self) -> None:
        """Sender header format must comply with RFC formatting."""
        self.assertEqual(
            format_sender_header("no-reply@flama.local", "Flama"),
            '"Flama" <no-reply@flama.local>',
        )
        self.assertEqual(
            format_sender_header("no-reply@flama.local", None),
            "no-reply@flama.local",
        )

    # --------------------------------------------------------------------------
    # 5. Memory Provider & Disabled Provider
    # --------------------------------------------------------------------------

    def test_memory_provider_lifecycle(self) -> None:
        """Memory provider records messages and permits clearing for isolated tests."""
        provider = MemoryEmailProvider()
        self.assertEqual(len(provider.sent_messages), 0)

        msg = RenderedEmailMessage(
            recipient="test@example.com",
            subject="Test Subject",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@flama.local",
        )
        cfg = EmailConfig(enabled=True, provider=EmailProviderType.MEMORY)

        result = provider.send(msg, cfg)
        self.assertTrue(result.success)
        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(len(provider.sent_messages), 1)
        self.assertIsNotNone(result.provider_message_id)

        provider.clear()
        self.assertEqual(len(provider.sent_messages), 0)
        self.assertEqual(len(provider.deliveries), 0)

    def test_disabled_provider_logs_safely_without_bodies_or_tokens(self) -> None:
        """Disabled provider returns success with status DISABLED and logs only safe metadata."""
        disabled_provider = DisabledEmailProvider()
        msg = RenderedEmailMessage(
            recipient="test@example.com",
            subject="Secret Subject",
            html_body="<p>Secret token is 123456</p>",
            text_body="Secret token is 123456",
            from_address="no-reply@flama.local",
            category=EmailCategory.SECURITY_PASSWORD_RESET.value,
            template_key=TemplateKey.SECURITY_PASSWORD_RESET.value,
            correlation_id="corr-disabled-1",
        )
        cfg = EmailConfig(enabled=True, provider=EmailProviderType.DISABLED)

        with self.assertLogs("app.email.providers.disabled", level=logging.INFO) as log_ctx:
            result = disabled_provider.send(msg, cfg)

        self.assertTrue(result.success)
        self.assertEqual(result.status, DeliveryStatus.DISABLED)
        self.assertIsNone(result.provider_message_id)

        # Verify log contents: metadata present, bodies and tokens ABSENT
        combined_logs = "\n".join(log_ctx.output)
        self.assertIn("category=security.password_reset", combined_logs)
        self.assertIn("correlation_id=corr-disabled-1", combined_logs)
        self.assertIn("recipient=t***t@example.com", combined_logs)
        self.assertNotIn("Secret token is 123456", combined_logs)
        self.assertNotIn("<p>Secret token", combined_logs)

    def test_email_enabled_false_skips_external_send(self) -> None:
        """When EMAIL_ENABLED is False, service returns DISABLED without invoking provider."""
        mock_provider = MagicMock()
        mock_provider.provider_name = "resend"

        disabled_config = EmailConfig(
            enabled=False,
            provider=EmailProviderType.RESEND,
            environment=EmailEnvironment.LOCAL,
            from_address="no-reply@flama.local",
        )
        service = TransactionalEmailService(
            config=disabled_config,
            provider=mock_provider,
        )

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        result = service.send(req)
        self.assertTrue(result.success)
        self.assertEqual(result.status, DeliveryStatus.DISABLED)
        # Ensure provider was never called
        mock_provider.send.assert_not_called()

    # --------------------------------------------------------------------------
    # 6. Environment Safety Guards (Non-Production vs Production)
    # --------------------------------------------------------------------------

    def test_non_production_redirect_all_to(self) -> None:
        """Non-production redirect replaces recipient and attaches X-Original-Recipient header."""
        staging_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.MEMORY,
            environment=EmailEnvironment.STAGING,
            redirect_all_to="dev-sink@flama.local",
            from_address="no-reply@flama.local",
        )
        service = TransactionalEmailService(
            config=staging_config,
            provider=self.memory_provider,
        )

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="real-user@production-customer.com",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        result = service.send(req)
        self.assertTrue(result.success)
        self.assertEqual(result.status, DeliveryStatus.REDIRECTED)
        self.assertEqual(result.recipient_masked, mask_email("dev-sink@flama.local"))
        self.assertEqual(result.original_recipient_masked, mask_email("real-user@production-customer.com"))

        sent = self.memory_provider.get_last_message()
        assert sent is not None
        self.assertEqual(sent.recipient, "dev-sink@flama.local")
        self.assertEqual(sent.headers.get("X-Original-Recipient"), "real-user@production-customer.com")

    def test_non_production_allowlist_permits_whitelisted_recipient(self) -> None:
        """Allowlisted email or domain is permitted in non-production."""
        staging_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.MEMORY,
            environment=EmailEnvironment.STAGING,
            recipient_allowlist=("qa-lead@flama.local", "@staging-test.org"),
            from_address="no-reply@flama.local",
        )
        service = TransactionalEmailService(
            config=staging_config,
            provider=self.memory_provider,
        )

        # 1. Exact match
        req1 = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="qa-lead@flama.local",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )
        res1 = service.send(req1)
        self.assertTrue(res1.success)
        self.assertEqual(res1.status, DeliveryStatus.SENT)

        # 2. Domain wildcard match
        req2 = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="anyone@staging-test.org",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )
        res2 = service.send(req2)
        self.assertTrue(res2.success)

    def test_non_production_allowlist_blocks_unauthorized_recipient(self) -> None:
        """Recipients not in non-production allowlist must raise RecipientNotAllowedError."""
        staging_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.MEMORY,
            environment=EmailEnvironment.STAGING,
            recipient_allowlist=("qa-lead@flama.local",),
            from_address="no-reply@flama.local",
        )
        service = TransactionalEmailService(
            config=staging_config,
            provider=self.memory_provider,
        )

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="external-person@example.com",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(RecipientNotAllowedError):
            service.send(req)

    def test_non_production_resend_without_guard_blocked(self) -> None:
        """Resend provider in non-production without allowlist or redirect must fail closed."""
        unguarded_staging_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            environment=EmailEnvironment.STAGING,
            resend_api_key="re_staging_key",
            from_address="no-reply@flama.local",
            recipient_allowlist=(),
            redirect_all_to="",
        )
        service = TransactionalEmailService(
            config=unguarded_staging_config,
            provider=ResendHttpProvider(),
        )

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="someone@example.com",
            variables={"reset_url": "https://flama.local/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(RecipientNotAllowedError):
            service.send(req)

    # --------------------------------------------------------------------------
    # 7. Production Fail-Closed Configuration
    # --------------------------------------------------------------------------

    def test_production_missing_api_key_fails_closed(self) -> None:
        """Production with Resend must fail closed if API key is missing."""
        prod_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            environment=EmailEnvironment.PRODUCTION,
            resend_api_key="",  # Missing!
            from_address="no-reply@flama.vn",
            public_app_url="https://flama.vn",
        )
        service = TransactionalEmailService(
            config=prod_config,
            provider=ResendHttpProvider(),
        )

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "https://flama.vn/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(EmailConfigError) as ctx:
            service.send(req)
        self.assertIn("EMAIL_RESEND_API_KEY is missing", str(ctx.exception))

    def test_production_missing_from_address_fails_closed(self) -> None:
        """Production with Resend must fail closed if from_address is missing."""
        prod_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            environment=EmailEnvironment.PRODUCTION,
            resend_api_key="re_prod_key",
            from_address="",  # Missing!
            public_app_url="https://flama.vn",
        )
        service = TransactionalEmailService(
            config=prod_config,
            provider=ResendHttpProvider(),
        )

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "https://flama.vn/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(EmailConfigError) as ctx:
            service.send(req)
        self.assertIn("EMAIL_FROM_ADDRESS", str(ctx.exception))

    def test_production_missing_public_app_url_fails_closed(self) -> None:
        """Production with Resend must fail closed if PUBLIC_APP_URL is missing."""
        prod_config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            environment=EmailEnvironment.PRODUCTION,
            resend_api_key="re_prod_key",
            from_address="no-reply@flama.vn",
            public_app_url="",  # Missing!
        )
        service = TransactionalEmailService(
            config=prod_config,
            provider=ResendHttpProvider(),
        )

        req = TransactionalEmailRequest(
            template_key=TemplateKey.SECURITY_PASSWORD_RESET,
            recipient="user@example.com",
            variables={"reset_url": "https://flama.vn/reset"},
            category=EmailCategory.SECURITY_PASSWORD_RESET,
        )

        with self.assertRaises(EmailConfigError) as ctx:
            service.send(req)
        self.assertIn("PUBLIC_APP_URL", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 8. Resend HTTP Adapter: Mapping, Idempotency & Provider Message ID Parsing
    # --------------------------------------------------------------------------

    @patch("urllib.request.urlopen")
    def test_resend_http_request_mapping_and_idempotency_key(self, mock_urlopen: MagicMock) -> None:
        """Verify Resend HTTP request headers, payload mapping, Idempotency-Key, and timeout."""
        mock_response = MagicMock()
        mock_response.getcode.return_value = 200
        mock_response.read.return_value = json.dumps({"id": "re_abc123456789"}).encode("utf-8")
        mock_response.__enter__.return_value = mock_response
        mock_urlopen.return_value = mock_response

        resend_provider = ResendHttpProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            resend_api_key="re_test_secret_key",
            provider_timeout_seconds=7,
        )
        msg = RenderedEmailMessage(
            recipient="customer@example.com",
            subject="Test Subject",
            html_body="<p>Hello HTML</p>",
            text_body="Hello Plain",
            from_address="no-reply@flama.local",
            from_name="Flama Security",
            reply_to="support@flama.local",
            category=EmailCategory.SECURITY_PASSWORD_RESET.value,
            correlation_id="event-uuid-98765",
            headers={"X-Custom-Trace": "trace-123"},
        )

        result = resend_provider.send(msg, config)

        self.assertTrue(result.success)
        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(result.provider, "resend")
        self.assertEqual(result.provider_message_id, "re_abc123456789")

        # Verify urllib call
        self.assertEqual(mock_urlopen.call_count, 1)
        req_arg = mock_urlopen.call_args[0][0]
        timeout_arg = mock_urlopen.call_args[1].get("timeout")

        self.assertEqual(timeout_arg, 7)
        self.assertEqual(req_arg.full_url, "https://api.resend.com/emails")
        self.assertEqual(req_arg.get_method(), "POST")

        # Verify request headers
        self.assertEqual(req_arg.headers.get("Authorization"), "Bearer re_test_secret_key")
        self.assertEqual(req_arg.headers.get("Content-type"), "application/json")
        self.assertEqual(req_arg.headers.get("Idempotency-key"), "event-uuid-98765")

        # Verify request JSON body
        body_dict = json.loads(req_arg.data.decode("utf-8"))
        self.assertEqual(body_dict.get("from"), '"Flama Security" <no-reply@flama.local>')
        self.assertEqual(body_dict.get("to"), ["customer@example.com"])
        self.assertEqual(body_dict.get("subject"), "Test Subject")
        self.assertEqual(body_dict.get("html"), "<p>Hello HTML</p>")
        self.assertEqual(body_dict.get("text"), "Hello Plain")
        self.assertEqual(body_dict.get("reply_to"), ["support@flama.local"])
        self.assertEqual(body_dict.get("tags"), [{"name": "category", "value": "security.password_reset"}])
        self.assertEqual(body_dict.get("headers"), {"X-Custom-Trace": "trace-123"})

    def test_service_retries_transient_failure_only(self) -> None:
        provider = MagicMock(spec=MemoryEmailProvider)
        provider.provider_name = "mock-live"
        provider.send.side_effect = [
            TransientEmailError("temporary outage"),
            self.memory_provider.send(
                RenderedEmailMessage(
                    recipient="user@example.com",
                    subject="placeholder",
                    html_body="<p>placeholder</p>",
                    text_body="placeholder",
                    from_address="no-reply@flama.local",
                ),
                self.default_config,
            ),
        ]
        config = EmailConfig(
            **{
                **self.default_config.__dict__,
                "provider_max_attempts": 2,
                "provider_retry_backoff_seconds": 0,
            }
        )
        service = TransactionalEmailService(config=config, provider=provider)
        result = service.send(
            TransactionalEmailRequest(
                template_key=TemplateKey.SECURITY_PASSWORD_CHANGED,
                recipient="user@example.com",
                variables={"recipient_name": "User"},
                category=EmailCategory.SECURITY_PASSWORD_CHANGED,
            )
        )
        self.assertTrue(result.success)
        self.assertEqual(provider.send.call_count, 2)

    def test_service_does_not_retry_permanent_failure(self) -> None:
        provider = MagicMock(spec=MemoryEmailProvider)
        provider.provider_name = "mock-live"
        provider.send.side_effect = PermanentEmailError("invalid credential")
        config = EmailConfig(
            **{
                **self.default_config.__dict__,
                "provider_max_attempts": 3,
                "provider_retry_backoff_seconds": 0,
            }
        )
        service = TransactionalEmailService(config=config, provider=provider)
        with self.assertRaises(PermanentEmailError):
            service.send(
                TransactionalEmailRequest(
                    template_key=TemplateKey.SECURITY_PASSWORD_CHANGED,
                    recipient="user@example.com",
                    variables={"recipient_name": "User"},
                    category=EmailCategory.SECURITY_PASSWORD_CHANGED,
                )
            )
        self.assertEqual(provider.send.call_count, 1)

    # --------------------------------------------------------------------------
    # 9. Error Classification: Transient vs Permanent
    # --------------------------------------------------------------------------

    @patch("urllib.request.urlopen")
    def test_resend_500_server_error_classified_as_transient(self, mock_urlopen: MagicMock) -> None:
        """HTTP 500 server error from Resend must raise TransientEmailError with is_transient=True."""
        err_response = io.BytesIO(json.dumps({"message": "Internal server error"}).encode("utf-8"))
        http_error = urllib.error.HTTPError(
            url="https://api.resend.com/emails",
            code=500,
            msg="Internal Server Error",
            hdrs={},  # type: ignore[arg-type]
            fp=err_response,
        )
        mock_urlopen.side_effect = http_error

        resend_provider = ResendHttpProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            resend_api_key="re_test_key",
        )
        msg = RenderedEmailMessage(
            recipient="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@flama.local",
        )

        with self.assertRaises(TransientEmailError) as ctx:
            resend_provider.send(msg, config)
        self.assertTrue(ctx.exception.is_transient)
        self.assertIn("500", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_resend_429_rate_limit_classified_as_transient(self, mock_urlopen: MagicMock) -> None:
        """HTTP 429 Too Many Requests from Resend must raise TransientEmailError with is_transient=True."""
        err_response = io.BytesIO(json.dumps({"message": "Rate limit exceeded"}).encode("utf-8"))
        http_error = urllib.error.HTTPError(
            url="https://api.resend.com/emails",
            code=429,
            msg="Too Many Requests",
            hdrs={},  # type: ignore[arg-type]
            fp=err_response,
        )
        mock_urlopen.side_effect = http_error

        resend_provider = ResendHttpProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            resend_api_key="re_test_key",
        )
        msg = RenderedEmailMessage(
            recipient="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@flama.local",
        )

        with self.assertRaises(TransientEmailError) as ctx:
            resend_provider.send(msg, config)
        self.assertTrue(ctx.exception.is_transient)
        self.assertIn("429", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_resend_network_timeout_classified_as_transient(self, mock_urlopen: MagicMock) -> None:
        """Socket timeout / URLError must raise TransientEmailError with is_transient=True."""
        mock_urlopen.side_effect = socket.timeout("timed out")

        resend_provider = ResendHttpProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            resend_api_key="re_test_key",
        )
        msg = RenderedEmailMessage(
            recipient="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@flama.local",
        )

        with self.assertRaises(TransientEmailError) as ctx:
            resend_provider.send(msg, config)
        self.assertTrue(ctx.exception.is_transient)

    @patch("urllib.request.urlopen")
    def test_resend_422_validation_error_classified_as_permanent(self, mock_urlopen: MagicMock) -> None:
        """HTTP 422 Unprocessable Entity from Resend must raise PermanentEmailError with is_transient=False."""
        err_response = io.BytesIO(
            json.dumps({"name": "validation_error", "message": "Domain is not verified"}).encode("utf-8")
        )
        http_error = urllib.error.HTTPError(
            url="https://api.resend.com/emails",
            code=422,
            msg="Unprocessable Entity",
            hdrs={},  # type: ignore[arg-type]
            fp=err_response,
        )
        mock_urlopen.side_effect = http_error

        resend_provider = ResendHttpProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            resend_api_key="re_test_key",
        )
        msg = RenderedEmailMessage(
            recipient="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@unverified.org",
        )

        with self.assertRaises(PermanentEmailError) as ctx:
            resend_provider.send(msg, config)
        self.assertFalse(ctx.exception.is_transient)
        self.assertIn("Domain is not verified", str(ctx.exception))

    @patch("urllib.request.urlopen")
    def test_resend_401_unauthorized_classified_as_permanent(self, mock_urlopen: MagicMock) -> None:
        """HTTP 401 Unauthorized from Resend must raise PermanentEmailError."""
        err_response = io.BytesIO(
            json.dumps({"name": "missing_api_key", "message": "API key is invalid"}).encode("utf-8")
        )
        http_error = urllib.error.HTTPError(
            url="https://api.resend.com/emails",
            code=401,
            msg="Unauthorized",
            hdrs={},  # type: ignore[arg-type]
            fp=err_response,
        )
        mock_urlopen.side_effect = http_error

        resend_provider = ResendHttpProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.RESEND,
            resend_api_key="re_invalid_key",
        )
        msg = RenderedEmailMessage(
            recipient="test@example.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@flama.local",
        )

        with self.assertRaises(PermanentEmailError) as ctx:
            resend_provider.send(msg, config)
        self.assertFalse(ctx.exception.is_transient)
        self.assertIn("API key is invalid", str(ctx.exception))

    # --------------------------------------------------------------------------
    # 10. SMTP Provider Adapter Tests
    # --------------------------------------------------------------------------

    @patch("smtplib.SMTP")
    def test_smtp_provider_send_success(self, mock_smtp_cls: MagicMock) -> None:
        """SMTP provider constructs MIME message, connects, authenticates, and sends."""
        mock_server = MagicMock()
        mock_smtp_cls.return_value = mock_server

        smtp_provider = SmtpEmailProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.SMTP,
            smtp_host="smtp.example.com",
            smtp_port=587,
            smtp_user="user@example.com",
            smtp_password="password123",
            smtp_use_tls=True,
            smtp_use_ssl=False,
        )
        msg = RenderedEmailMessage(
            recipient="recipient@example.com",
            subject="Test Subject",
            html_body="<p>Hello SMTP</p>",
            text_body="Hello SMTP Text",
            from_address="no-reply@example.com",
            from_name="Flama Mailer",
            reply_to="support@example.com",
            correlation_id="corr-smtp-1",
        )

        result = smtp_provider.send(msg, config)

        self.assertTrue(result.success)
        self.assertEqual(result.status, DeliveryStatus.SENT)
        self.assertEqual(result.provider, "smtp")
        self.assertIsNotNone(result.provider_message_id)

        mock_smtp_cls.assert_called_once_with(host="smtp.example.com", port=587, timeout=10)
        mock_server.starttls.assert_called_once()
        mock_server.login.assert_called_once_with("user@example.com", "password123")
        mock_server.send_message.assert_called_once()
        mock_server.quit.assert_called_once()

    @patch("smtplib.SMTP")
    def test_smtp_auth_error_classified_as_permanent(self, mock_smtp_cls: MagicMock) -> None:
        """SMTPAuthenticationError must raise PermanentEmailError."""
        mock_server = MagicMock()
        mock_server.login.side_effect = smtplib.SMTPAuthenticationError(535, b"Authentication credentials invalid")
        mock_smtp_cls.return_value = mock_server

        smtp_provider = SmtpEmailProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.SMTP,
            smtp_host="smtp.example.com",
            smtp_user="baduser",
            smtp_password="wrongpassword",
        )
        msg = RenderedEmailMessage(
            recipient="recipient@example.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@example.com",
        )

        with self.assertRaises(PermanentEmailError) as ctx:
            smtp_provider.send(msg, config)
        self.assertFalse(ctx.exception.is_transient)
        self.assertIn("Authentication credentials invalid", str(ctx.exception))

    @patch("smtplib.SMTP")
    def test_smtp_connection_error_classified_as_transient(self, mock_smtp_cls: MagicMock) -> None:
        """SMTPConnectError must raise TransientEmailError."""
        mock_smtp_cls.side_effect = smtplib.SMTPConnectError(421, b"Service not available")

        smtp_provider = SmtpEmailProvider()
        config = EmailConfig(
            enabled=True,
            provider=EmailProviderType.SMTP,
            smtp_host="smtp.example.com",
        )
        msg = RenderedEmailMessage(
            recipient="recipient@example.com",
            subject="Test",
            html_body="<p>Test</p>",
            text_body="Test",
            from_address="no-reply@example.com",
        )

        with self.assertRaises(TransientEmailError) as ctx:
            smtp_provider.send(msg, config)
        self.assertTrue(ctx.exception.is_transient)

    # --------------------------------------------------------------------------
    # 11. Startup and Config Isolation (No Network Calls on App Boot)
    # --------------------------------------------------------------------------

    def test_startup_and_factory_offline(self) -> None:
        """App initialization and get_email_service() must perform zero network calls."""
        with patch("urllib.request.urlopen") as mock_urlopen:
            app = create_app(
                {
                    "TESTING": True,
                    "SQLALCHEMY_DATABASE_URI": "sqlite:///:memory:",
                    "EMAIL_ENABLED": False,
                    "EMAIL_PROVIDER": "disabled",
                }
            )
            with app.app_context():
                service = get_email_service()
                self.assertIsNotNone(service)
                self.assertEqual(service.config.provider, "disabled")
            mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
