"""Logging redaction helper to prevent sensitive Flama Connect keys from leaking into log files or exception traces."""

import logging
import re

# Matches Flama API keys like flama_yt_12345678_abcdef... or flama_test_xxxx...
KEY_PATTERN = re.compile(r"flama_[a-zA-Z0-9_-]{12,128}")
# Matches Authorization or X-Flama-Connect-Key header values
HEADER_PATTERN = re.compile(r"(Authorization|X-Flama-Connect-Key)\s*:\s*([^\r\n,]+)", re.IGNORECASE)
# Matches key in URL paths
URL_KEY_PATTERN = re.compile(r"(/v1/flama-connect/)(flama_[a-zA-Z0-9_-]{12,128})", re.IGNORECASE)


def mask_key(key: str) -> str:
    """Masks a Flama Connect key to format like flama_yt_****...****UXw."""
    if not isinstance(key, str) or len(key) < 12:
        return "flama_****"
    prefix = key[:8]
    suffix = key[-3:]
    return f"{prefix}****...****{suffix}"


def redact_sensitive_text(text: str) -> str:
    """Sanitizes text by replacing sensitive keys and headers with masked placeholders."""
    if not isinstance(text, str) or not text:
        return text

    # Redact URL keys first
    def url_sub(match: re.Match) -> str:
        return f"{match.group(1)}{mask_key(match.group(2))}"

    text = URL_KEY_PATTERN.sub(url_sub, text)

    # Redact header strings
    def header_sub(match: re.Match) -> str:
        header_name = match.group(1)
        raw_val = match.group(2).strip()
        if raw_val.startswith("Bearer "):
            bearer_key = raw_val[7:].strip()
            return f"{header_name}: Bearer {mask_key(bearer_key)}"
        return f"{header_name}: {mask_key(raw_val)}"

    text = HEADER_PATTERN.sub(header_sub, text)

    # Redact standalone keys
    def key_sub(match: re.Match) -> str:
        return mask_key(match.group(0))

    text = KEY_PATTERN.sub(key_sub, text)
    return text


class RedactingFormatter(logging.Formatter):
    """Logging formatter that automatically redacts sensitive keys from formatted messages."""

    def format(self, record: logging.LogRecord) -> str:
        formatted = super().format(record)
        return redact_sensitive_text(formatted)
