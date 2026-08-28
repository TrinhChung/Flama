"""Email address validation, sanitization, header injection prevention, and PII masking."""

from __future__ import annotations

import re
from typing import Any

from app.email.constants import MAX_EMAIL_LENGTH, MAX_LOCAL_PART_LENGTH
from app.email.errors import HeaderInjectionError, EmailValidationError

# Stricter RFC-compliant transactional email address regex
_EMAIL_PATTERN = re.compile(
    r"^(?P<local>[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+(?:\.[a-zA-Z0-9!#$%&'*+/=?^_`{|}~-]+)*)"
    r"@"
    r"(?P<domain>(?:[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?\.)+[a-zA-Z0-9](?:[a-zA-Z0-9-]*[a-zA-Z0-9])?)$"
)


def assert_no_header_injection(value: Any, field_name: str = "field") -> None:
    """Ensure a string contains no CRLF characters that could enable mail header injection."""
    if value is None:
        return
    text = str(value)
    if "\r" in text or "\n" in text or "%0d" in text.lower() or "%0a" in text.lower():
        raise HeaderInjectionError(
            f"Carriage return or line feed detected in {field_name}.",
            extra={"field": field_name},
        )


def validate_email_address(address: str, field_name: str = "recipient") -> str:
    """Validate and normalize an email address, rejecting injection and malformed syntax."""
    if not address or not isinstance(address, str):
        raise EmailValidationError(
            f"Email {field_name} must be a non-empty string.",
            extra={"field": field_name},
        )

    assert_no_header_injection(address, field_name)
    normalized = address.strip()

    if not normalized:
        raise EmailValidationError(
            f"Email {field_name} must not be blank.",
            extra={"field": field_name},
        )

    if len(normalized) > MAX_EMAIL_LENGTH:
        raise EmailValidationError(
            f"Email {field_name} exceeds maximum length of {MAX_EMAIL_LENGTH} characters.",
            extra={"field": field_name, "length": len(normalized)},
        )

    if ".." in normalized or "@" not in normalized:
        raise EmailValidationError(
            f"Email {field_name} format is invalid.",
            extra={"field": field_name},
        )

    match = _EMAIL_PATTERN.match(normalized)
    if not match:
        raise EmailValidationError(
            f"Email {field_name} is not a valid email address.",
            extra={"field": field_name},
        )

    local_part = match.group("local")
    if len(local_part) > MAX_LOCAL_PART_LENGTH:
        raise EmailValidationError(
            f"Email {field_name} local-part exceeds {MAX_LOCAL_PART_LENGTH} characters.",
            extra={"field": field_name},
        )

    domain_part = match.group("domain")
    # TLD must be at least 2 characters
    tld = domain_part.split(".")[-1]
    if len(tld) < 2 or tld.isdigit():
        raise EmailValidationError(
            f"Email {field_name} has an invalid top-level domain.",
            extra={"field": field_name},
        )

    return f"{local_part}@{domain_part.lower()}"


def validate_sender_identity(
    address: str,
    name: str | None = None,
) -> tuple[str, str]:
    """Validate sender address and display name."""
    valid_address = validate_email_address(address, field_name="from_address")
    safe_name = ""
    if name:
        assert_no_header_injection(name, field_name="from_name")
        safe_name = str(name).strip()
    return valid_address, safe_name


def format_sender_header(from_address: str, from_name: str | None = None) -> str:
    """Format RFC-compliant From header string."""
    if from_name:
        clean_name = from_name.strip().replace('"', '\\"')
        return f'"{clean_name}" <{from_address}>'
    return from_address


def mask_email(address: str | None) -> str:
    """Mask email address for safe PII-compliant logging without leaking full mailbox."""
    if not address or not isinstance(address, str) or "@" not in address:
        return "***"
    try:
        local, domain = address.split("@", 1)
    except ValueError:
        return "***"

    local = local.strip()
    domain = domain.strip().lower()

    if len(local) <= 1:
        masked_local = f"{local}***"
    elif len(local) == 2:
        masked_local = f"{local[0]}***"
    else:
        masked_local = f"{local[0]}***{local[-1]}"

    return f"{masked_local}@{domain}"
