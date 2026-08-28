"""Transactional email error types and classification."""

from __future__ import annotations

from typing import Any


class EmailError(Exception):
    """Base exception for all transactional email subsystem errors."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "EMAIL_ERROR",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.extra = extra or {}

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": self.code,
            "message": self.message,
            "extra": self.extra,
        }


class EmailConfigError(EmailError):
    """Raised when email configuration is missing, invalid, or fails production safety checks."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "EMAIL_CONFIG_ERROR",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, extra=extra)


class EmailValidationError(EmailError):
    """Raised when an email request, template key, category, address, or variable set is invalid."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "EMAIL_VALIDATION_ERROR",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, extra=extra)


class HeaderInjectionError(EmailValidationError):
    """Raised when CR or LF characters are detected in headers, addresses, or subject fields."""

    def __init__(
        self,
        message: str = "Header injection detected: carriage return or line feed characters in email fields.",
        *,
        code: str = "HEADER_INJECTION_DETECTED",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, extra=extra)


class RecipientNotAllowedError(EmailError):
    """Raised when environment safety guards block sending to an unapproved recipient."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "RECIPIENT_NOT_ALLOWED",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, extra=extra)


class EmailDeliveryError(EmailError):
    """Base exception for email provider delivery failures."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "EMAIL_DELIVERY_ERROR",
        is_transient: bool = False,
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, extra=extra)
        self.is_transient = is_transient


class TransientEmailError(EmailDeliveryError):
    """Temporary delivery failure (5xx, network timeout, rate limit) suitable for bounded retry."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "TRANSIENT_EMAIL_ERROR",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, is_transient=True, extra=extra)


class PermanentEmailError(EmailDeliveryError):
    """Permanent delivery failure (4xx, invalid recipient syntax, rejected credential) that must not be retried infinitely."""

    def __init__(
        self,
        message: str,
        *,
        code: str = "PERMANENT_EMAIL_ERROR",
        extra: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message, code=code, is_transient=False, extra=extra)
