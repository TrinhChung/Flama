"""Email template rendering engine using Jinja2 with strict autoescape and variable validation."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable
from urllib.parse import urlparse

from jinja2 import Environment, FileSystemLoader, TemplateNotFound, select_autoescape

from app.email.address import (
    assert_no_header_injection,
    validate_email_address,
    validate_sender_identity,
)
from app.email.constants import (
    ALLOWED_CATEGORY_TEMPLATE_MAP,
    DEFAULT_FROM_NAME,
    DEFAULT_LOCALE,
    EmailCategory,
    TemplateKey,
)
from app.email.contracts import RenderedEmailMessage, TransactionalEmailRequest
from app.email.errors import EmailValidationError, HeaderInjectionError

TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"


@dataclass(frozen=True)
class TemplateSpec:
    """Specification and validation rules for an email template."""

    key: TemplateKey
    folder: str
    base_name: str
    required_variables: tuple[str, ...]
    variable_validators: dict[str, Callable[[Any], None]]


def _validate_reset_url(url: Any) -> None:
    """Validate that reset_url is a well-formed http/https URL without CRLF."""
    if not url or not isinstance(url, str):
        raise EmailValidationError(
            "Variable 'reset_url' must be a non-empty string.",
            extra={"variable": "reset_url"},
        )
    assert_no_header_injection(url, field_name="reset_url")
    parsed = urlparse(url.strip())
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        raise EmailValidationError(
            "Variable 'reset_url' must be a valid http or https URL.",
            extra={"variable": "reset_url", "value": url},
        )


TEMPLATE_REGISTRY: dict[TemplateKey, TemplateSpec] = {
    TemplateKey.SECURITY_PASSWORD_RESET: TemplateSpec(
        key=TemplateKey.SECURITY_PASSWORD_RESET,
        folder="security",
        base_name="password_reset",
        required_variables=("reset_url",),
        variable_validators={"reset_url": _validate_reset_url},
    ),
    TemplateKey.SECURITY_PASSWORD_CHANGED: TemplateSpec(
        key=TemplateKey.SECURITY_PASSWORD_CHANGED,
        folder="security",
        base_name="password_changed",
        required_variables=(),
        variable_validators={},
    ),
    TemplateKey.IDENTITY_EMAIL_VERIFICATION: TemplateSpec(
        key=TemplateKey.IDENTITY_EMAIL_VERIFICATION,
        folder="identity",
        base_name="email_verification",
        required_variables=("verification_code",),
        variable_validators={},
    ),
    TemplateKey.SYSTEM_DELIVERY_TEST: TemplateSpec(
        key=TemplateKey.SYSTEM_DELIVERY_TEST,
        folder="system",
        base_name="delivery_test",
        required_variables=(),
        variable_validators={},
    ),
}


class TemplateRenderer:
    """Renders version-controlled HTML and plain-text email templates."""

    def __init__(self, templates_dir: Path | None = None) -> None:
        self.templates_dir = templates_dir or TEMPLATES_DIR
        self._env = Environment(
            loader=FileSystemLoader(str(self.templates_dir)),
            autoescape=select_autoescape(
                enabled_extensions=("html", "xml"),
                default_for_string=True,
                default=False,
            ),
            trim_blocks=True,
            lstrip_blocks=True,
        )

    def validate_request(self, request: TransactionalEmailRequest) -> TemplateSpec:
        """Validate template key, category compatibility, recipient, and required variables."""
        if not isinstance(request, TransactionalEmailRequest):
            raise EmailValidationError(
                "Request must be an instance of TransactionalEmailRequest."
            )

        # 1. Finite Template Key validation
        raw_key = str(
            request.template_key.value
            if isinstance(request.template_key, TemplateKey)
            else request.template_key
        ).strip()

        try:
            template_key = TemplateKey(raw_key)
        except ValueError:
            allowed_keys = [k.value for k in TemplateKey]
            raise EmailValidationError(
                f"Unknown template_key '{raw_key}'. Allowed keys: {allowed_keys}",
                extra={"template_key": raw_key, "allowed_keys": allowed_keys},
            )

        # 2. Finite Category validation
        raw_cat = str(
            request.category.value
            if isinstance(request.category, EmailCategory)
            else request.category
        ).strip()

        try:
            category = EmailCategory(raw_cat)
        except ValueError:
            allowed_cats = [c.value for c in EmailCategory]
            raise EmailValidationError(
                f"Unknown category '{raw_cat}'. Allowed categories: {allowed_cats}",
                extra={"category": raw_cat, "allowed_categories": allowed_cats},
            )

        # 3. Check Category-Template compatibility
        allowed_for_template = ALLOWED_CATEGORY_TEMPLATE_MAP.get(template_key, set())
        if allowed_for_template and category not in allowed_for_template:
            raise EmailValidationError(
                f"Category '{category.value}' is not valid for template_key '{template_key.value}'.",
                extra={
                    "category": category.value,
                    "template_key": template_key.value,
                    "allowed_categories": [c.value for c in allowed_for_template],
                },
            )

        # 4. Recipient address validation & CRLF prevention
        validate_email_address(request.recipient, field_name="recipient")

        # 5. Required variables validation
        spec = TEMPLATE_REGISTRY.get(template_key)
        if not spec:
            raise EmailValidationError(
                f"No template specification registered for key '{template_key.value}'.",
                extra={"template_key": template_key.value},
            )

        variables = request.variables or {}
        if not isinstance(variables, dict):
            raise EmailValidationError(
                "Email request variables must be a dictionary.",
                extra={"variables_type": type(variables).__name__},
            )

        missing = [var for var in spec.required_variables if var not in variables or variables[var] is None or str(variables[var]).strip() == ""]
        if missing:
            raise EmailValidationError(
                f"Missing required template variables for '{template_key.value}': {missing}",
                extra={"template_key": template_key.value, "missing_variables": missing},
            )

        # 6. Run variable-specific validators
        for var_name, validator_fn in spec.variable_validators.items():
            if var_name in variables:
                validator_fn(variables[var_name])

        return spec

    def render(
        self,
        request: TransactionalEmailRequest,
        *,
        from_address: str,
        from_name: str = DEFAULT_FROM_NAME,
        reply_to: str | None = None,
    ) -> RenderedEmailMessage:
        """Render both HTML and plain-text versions of the requested email template."""
        spec = self.validate_request(request)

        # Validate sender and reply-to identities
        safe_from_address, safe_from_name = validate_sender_identity(from_address, from_name)
        safe_reply_to = None
        if reply_to:
            safe_reply_to = validate_email_address(reply_to, field_name="reply_to")

        locale = (request.locale or DEFAULT_LOCALE).strip().lower()
        context: dict[str, Any] = {
            **(request.variables or {}),
            "locale": locale,
            "category": request.category.value if isinstance(request.category, EmailCategory) else str(request.category),
            "correlation_id": request.correlation_id or "",
        }

        # Render Subject
        subject_template_path = f"{spec.folder}/{spec.base_name}.subject.txt"
        try:
            subject_tmpl = self._env.get_template(subject_template_path)
            rendered_subject = subject_tmpl.render(context).strip()
        except TemplateNotFound:
            rendered_subject = f"[{safe_from_name}] Thông báo hệ thống"

        assert_no_header_injection(rendered_subject, field_name="subject")
        if not rendered_subject:
            raise EmailValidationError("Rendered subject must not be empty.")

        context["subject"] = rendered_subject

        # Render HTML
        html_template_path = f"{spec.folder}/{spec.base_name}.html"
        try:
            html_tmpl = self._env.get_template(html_template_path)
            rendered_html = html_tmpl.render(context)
        except TemplateNotFound as exc:
            raise EmailValidationError(
                f"HTML template file '{html_template_path}' not found.",
                extra={"template_path": html_template_path},
            ) from exc

        # Render Plain Text
        text_template_path = f"{spec.folder}/{spec.base_name}.txt"
        try:
            text_tmpl = self._env.get_template(text_template_path)
            rendered_text = text_tmpl.render(context)
        except TemplateNotFound as exc:
            raise EmailValidationError(
                f"Plain text template file '{text_template_path}' not found.",
                extra={"template_path": text_template_path},
            ) from exc

        return RenderedEmailMessage(
            recipient=request.recipient.strip(),
            subject=rendered_subject,
            html_body=rendered_html,
            text_body=rendered_text,
            from_address=safe_from_address,
            from_name=safe_from_name,
            reply_to=safe_reply_to,
            category=request.category.value if isinstance(request.category, EmailCategory) else str(request.category),
            template_key=spec.key.value,
            correlation_id=request.correlation_id,
            locale=locale,
            safe_metadata=dict(request.safe_metadata or {}),
        )
