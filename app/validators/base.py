"""Base DTO (Data Transfer Object) class powered by Pydantic v2.

Provides centralized request payload validation, type coercion, and seamless
integration with Flama's RequestValidationError and global error handler.
"""

from __future__ import annotations

from typing import Any, TypeVar
from pydantic import BaseModel, ConfigDict, ValidationError

from app.validators.flashcard_input import RequestValidationError

T = TypeVar("T", bound="BaseDTO")


class BaseDTO(BaseModel):
    """Base class for all typed request payload DTOs."""

    model_config = ConfigDict(
        extra="ignore",
        str_strip_whitespace=True,
        populate_by_name=True,
        validate_assignment=True,
    )

    @classmethod
    def from_payload(
        cls: type[T],
        payload: Any,
        *,
        field_prefix: str | None = None,
        default_error_code: str = "VALIDATION_ERROR",
    ) -> T:
        """Validate and parse arbitrary request payload into a typed DTO.

        Raises:
            RequestValidationError: If the payload is not a dict or fails validation.
        """
        if not isinstance(payload, dict):
            raise RequestValidationError(
                "Payload must be a JSON object.",
                field=field_prefix or "body",
                status=400,
                code=default_error_code,
            )

        try:
            return cls.model_validate(payload)
        except ValidationError as err:
            first_err = err.errors()[0]
            loc_parts = list(first_err.get("loc", ()))
            if field_prefix:
                loc_parts.insert(0, field_prefix)
            field = ".".join(str(p) for p in loc_parts) if loc_parts else None

            raw_msg = first_err.get("msg", "Validation error.")
            # Clean up Pydantic standard prefix if present
            if raw_msg.startswith("Value error, "):
                raw_msg = raw_msg[len("Value error, "):]

            raise RequestValidationError(
                raw_msg,
                field=field,
                status=400,
                code=default_error_code,
            ) from err
