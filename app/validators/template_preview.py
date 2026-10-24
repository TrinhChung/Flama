"""Preview values keep their shape regardless of the template input hint."""

from app.validators.flashcard_input import RequestValidationError, _clean_array_items


def preview_field_value(value, *, field_name):
    """Bound preview size/depth and sanitize list items without changing shape."""
    if isinstance(value, str):
        if len(value) <= 100_000:
            return value, len(value)
    elif isinstance(value, list):
        cleaned, budget = _clean_array_items(
            value, field_name=field_name, depth=1, budget=100_000, maximum=100_000,
        )
        return cleaned, 100_000 - budget
    raise RequestValidationError(
        f"field_values.{field_name} must be text or a JSON array within the preview size limit.",
        field=f"field_values.{field_name}",
    )
