#!/usr/bin/env python3
"""Build and apply the GitHub-managed production environment payload."""

from __future__ import annotations

import argparse
import base64
import binascii
import json
import os
import re
import stat
import tempfile
from pathlib import Path


MANAGED_SECRET_KEYS = (
    "ADMIN_EMAIL",
    "ADMIN_PASSWORD",
    "ADMIN_USER",
    "DB_PASSWORD",
    "PAYOS_API_KEY",
    "PAYOS_CHECKSUM_KEY",
    "PAYOS_CLIENT_ID",
    "EMAIL_SMTP_PASSWORD",
    "EMAIL_RESEND_API_KEY",
    "GOOGLE_OAUTH_CLIENT_SECRET",
)
MANAGED_VARIABLE_KEYS = (
    "CORS_ALLOWED_ORIGINS",
    "CONNECT_CORS_ALLOWED_ORIGINS",
    "FLASK_APP",
    "DB_PORT",
    "DB_POOL_SIZE",
    "DB_MAX_OVERFLOW",
    "DB_POOL_TIMEOUT_SECONDS",
    "DB_POOL_RECYCLE_SECONDS",
    "FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH",
    "FLASHCARD_MEDIA_MAX_BYTES",
    "FLASHCARD_MEDIA_SCAN_ENABLED",
    "MEDIA_PROXY_USE_XACCEL",
    "PAYMENTS_ENABLED",
    "PAYMENTS_ORDER_EXPIRY_SECONDS",
    "PAYMENTS_PAID_INSTALL_REQUIRED",
    "PAYMENTS_PROVIDER",
    "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED",
    "REDIS_URL",
    "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS",
    "REDIS_SOCKET_TIMEOUT_SECONDS",
    "STUDY_QUEUE_NAMESPACE",
    "STUDY_ASYNC_BATCH_ENABLED",
    "RATE_LIMIT_BACKEND",
    "RATE_LIMIT_KEY_PREFIX",
    "RATE_LIMIT_DAILY_ENABLED",
    "RATE_LIMIT_REGULAR_DAILY_MAX",
    "RATE_LIMIT_CREATOR_DAILY_MAX",
    "RATE_LIMIT_ENTERPRISE_DAILY_MAX",
    "RATE_LIMIT_DAILY_TIMEZONE",
    "LOGIN_RATE_LIMIT_ENABLED",
    "LOGIN_RATE_LIMIT_WINDOW_SECONDS",
    "LOGIN_RATE_LIMIT_MAX_ATTEMPTS",
    "LOGIN_RATE_LIMIT_LOCKOUT_SECONDS",
    "MCP_TOKEN_RATE_LIMIT_ENABLED",
    "MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS",
    "MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS",
    "MCP_PREVIEW_BACKEND",
    "MCP_PREVIEW_TTL_SECONDS",
    "SHARED_DECK_TREE_CLONE_MODE",
    "DECK_SOURCE_NOTETYPE_GUARD_MODE",
    "MARKETPLACE_SAMPLE_MODE",
    "FLASHCARD_RENDER_PREVIEW_CACHE_MAX_ENTRIES",
    "EMAIL_ENABLED",
    "EMAIL_PROVIDER",
    "EMAIL_ENVIRONMENT",
    "EMAIL_FROM_ADDRESS",
    "EMAIL_FROM_NAME",
    "EMAIL_SMTP_HOST",
    "EMAIL_SMTP_PORT",
    "EMAIL_SMTP_USER",
    "EMAIL_SMTP_USE_TLS",
    "EMAIL_SMTP_USE_SSL",
    "PUBLIC_APP_URL",
    "FRONTEND_URL",
    "TRUST_PROXY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_REDIRECT_URI",
)
MANAGED_ENV_KEYS = MANAGED_SECRET_KEYS + MANAGED_VARIABLE_KEYS
MANAGED_VARIABLE_DEFAULTS = {
    "FLASK_APP": "wsgi.py",
    "DB_PORT": "3306",
    "DB_POOL_SIZE": "4",
    "DB_MAX_OVERFLOW": "1",
    "DB_POOL_TIMEOUT_SECONDS": "5",
    "DB_POOL_RECYCLE_SECONDS": "1800",
    "FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH": "0",
    "FLASHCARD_MEDIA_MAX_BYTES": "10485760",
    "FLASHCARD_MEDIA_SCAN_ENABLED": "0",
    "MEDIA_PROXY_USE_XACCEL": "true",
    "PAYMENTS_ENABLED": "0",
    "PAYMENTS_ORDER_EXPIRY_SECONDS": "1800",
    "PAYMENTS_PAID_INSTALL_REQUIRED": "0",
    "PAYMENTS_PROVIDER": "payos",
    "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": "1",
    "REDIS_URL": "redis://127.0.0.1:6379/0",
    "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS": "1",
    "REDIS_SOCKET_TIMEOUT_SECONDS": "1",
    "STUDY_QUEUE_NAMESPACE": "flama-production",
    "STUDY_ASYNC_BATCH_ENABLED": "0",
    "RATE_LIMIT_BACKEND": "redis",
    "RATE_LIMIT_KEY_PREFIX": "flama:v1",
    "RATE_LIMIT_DAILY_ENABLED": "true",
    "RATE_LIMIT_REGULAR_DAILY_MAX": "300",
    "RATE_LIMIT_CREATOR_DAILY_MAX": "2000",
    "RATE_LIMIT_ENTERPRISE_DAILY_MAX": "10000",
    "RATE_LIMIT_DAILY_TIMEZONE": "Asia/Ho_Chi_Minh",
    "LOGIN_RATE_LIMIT_ENABLED": "true",
    "LOGIN_RATE_LIMIT_WINDOW_SECONDS": "60",
    "LOGIN_RATE_LIMIT_MAX_ATTEMPTS": "5",
    "LOGIN_RATE_LIMIT_LOCKOUT_SECONDS": "300",
    "MCP_TOKEN_RATE_LIMIT_ENABLED": "false",
    "MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS": "60",
    "MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS": "100000",
    "MCP_PREVIEW_BACKEND": "redis",
    "MCP_PREVIEW_TTL_SECONDS": "600",
    "SHARED_DECK_TREE_CLONE_MODE": "batched",
    "DECK_SOURCE_NOTETYPE_GUARD_MODE": "shadow",
    "MARKETPLACE_SAMPLE_MODE": "shadow_cache",
    "FLASHCARD_RENDER_PREVIEW_CACHE_MAX_ENTRIES": "512",
    "EMAIL_ENABLED": "true",
    "EMAIL_PROVIDER": "smtp",
    "EMAIL_ENVIRONMENT": "production",
    "EMAIL_FROM_ADDRESS": "chungtrinh2k2@gmail.com",
    "EMAIL_FROM_NAME": "Flama",
    "EMAIL_SMTP_HOST": "smtp.gmail.com",
    "EMAIL_SMTP_PORT": "587",
    "EMAIL_SMTP_USER": "chungtrinh2k2@gmail.com",
    "EMAIL_SMTP_USE_TLS": "true",
    "EMAIL_SMTP_USE_SSL": "false",
    "TRUST_PROXY": "1",
    "FRONTEND_URL": "https://flama.vn",
    "PUBLIC_APP_URL": "https://flama.vn",
    "CORS_ALLOWED_ORIGINS": "https://flama.vn",
    "CONNECT_CORS_ALLOWED_ORIGINS": "*",
    "GOOGLE_OAUTH_REDIRECT_URI": "https://api.flama.vn/auth/google/callback",
}
_ENV_ASSIGNMENT_RE = re.compile(r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=")


class ManagedEnvironmentError(RuntimeError):
    """Raised when a managed environment payload is invalid."""


def _validate_value(key: str, value: str) -> str:
    if not value:
        raise ManagedEnvironmentError(f"Managed environment value is empty: {key}")
    if any(character in value for character in ("\x00", "\r", "\n")):
        raise ManagedEnvironmentError(f"Managed environment value contains an unsupported character: {key}")
    return value


def _write_private_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
    except Exception:
        try:
            os.close(descriptor)
        except OSError:
            pass
        raise
    os.chmod(path, 0o600)


OPTIONAL_MANAGED_KEYS = (
    "EMAIL_SMTP_PASSWORD",
    "EMAIL_RESEND_API_KEY",
    "GOOGLE_OAUTH_CLIENT_ID",
    "GOOGLE_OAUTH_CLIENT_SECRET",
)


def build_payload(output_path: Path) -> None:
    values: dict[str, str] = {}
    missing_keys: list[str] = []

    for key in MANAGED_ENV_KEYS:
        value = os.environ.get(key, "") or MANAGED_VARIABLE_DEFAULTS.get(key, "")
        if not value:
            if key not in OPTIONAL_MANAGED_KEYS:
                missing_keys.append(key)
            continue
        validated_value = _validate_value(key, value)
        values[key] = base64.b64encode(validated_value.encode("utf-8")).decode("ascii")

    if missing_keys:
        raise ManagedEnvironmentError(
            "Missing required GitHub environment values: " + ", ".join(missing_keys)
        )

    payload = {
        "version": 1,
        "values": values,
    }
    _write_private_text(
        output_path,
        json.dumps(payload, separators=(",", ":"), sort_keys=True) + "\n",
    )
    print("Built managed environment payload for: " + ", ".join(MANAGED_ENV_KEYS))


def _load_payload(payload_path: Path) -> dict[str, str]:
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedEnvironmentError("Unable to read the managed environment payload.") from exc

    if not isinstance(payload, dict) or payload.get("version") != 1:
        raise ManagedEnvironmentError("Unsupported managed environment payload version.")

    encoded_values = payload.get("values")
    if not isinstance(encoded_values, dict):
        raise ManagedEnvironmentError("Managed environment payload values are invalid.")

    payload_keys = set(encoded_values)
    allowed_keys = set(MANAGED_ENV_KEYS)
    required_keys = set(MANAGED_ENV_KEYS) - set(OPTIONAL_MANAGED_KEYS)

    if not payload_keys.issubset(allowed_keys) or not required_keys.issubset(payload_keys):
        raise ManagedEnvironmentError("Managed environment payload keys do not match the allowed key set.")

    values: dict[str, str] = {}
    for key, encoded_value in encoded_values.items():
        if not isinstance(encoded_value, str):
            raise ManagedEnvironmentError(f"Managed environment payload value is invalid: {key}")
        try:
            decoded_value = base64.b64decode(encoded_value, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError) as exc:
            raise ManagedEnvironmentError(
                f"Managed environment payload value cannot be decoded: {key}"
            ) from exc
        values[key] = _validate_value(key, decoded_value)
    return values


def _format_environment_assignment(key: str, value: str) -> str:
    escaped_value = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'{key}="{escaped_value}"'


def _atomic_replace(path: Path, content: str) -> None:
    current_stat = path.stat()
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary_path = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary_path, stat.S_IMODE(current_stat.st_mode))
        if hasattr(os, "chown"):
            os.chown(temporary_path, current_stat.st_uid, current_stat.st_gid)
        os.replace(temporary_path, path)
    finally:
        temporary_path.unlink(missing_ok=True)


def apply_payload(*, environment_path: Path, payload_path: Path) -> list[str]:
    if not environment_path.is_file():
        raise ManagedEnvironmentError(f"Server environment file does not exist: {environment_path}")

    values = _load_payload(payload_path)
    desired_lines = {
        key: _format_environment_assignment(key, value)
        for key, value in values.items()
    }

    output_lines: list[str] = []
    seen_keys: set[str] = set()
    changed_keys: set[str] = set()

    for line in environment_path.read_text(encoding="utf-8").splitlines():
        match = _ENV_ASSIGNMENT_RE.match(line)
        key = match.group(1) if match else ""
        if key not in desired_lines:
            output_lines.append(line)
            continue
        if key in seen_keys:
            changed_keys.add(key)
            continue

        desired_line = desired_lines[key]
        output_lines.append(desired_line)
        seen_keys.add(key)
        if line != desired_line:
            changed_keys.add(key)

    for key, desired_line in desired_lines.items():
        if key in seen_keys:
            continue
        output_lines.append(desired_line)
        changed_keys.add(key)

    if not changed_keys:
        print("GitHub-managed server environment keys already match.")
        return []

    _atomic_replace(environment_path, "\n".join(output_lines) + "\n")
    ordered_changed_keys = [key for key in MANAGED_ENV_KEYS if key in changed_keys]
    print("Updated GitHub-managed server environment keys: " + ", ".join(ordered_changed_keys))
    return ordered_changed_keys


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    build_parser = subparsers.add_parser("build", help="Build a payload from process environment variables.")
    build_parser.add_argument("--output", type=Path, required=True)

    apply_parser = subparsers.add_parser("apply", help="Apply a payload to a server EnvironmentFile.")
    apply_parser.add_argument("--env-file", type=Path, required=True)
    apply_parser.add_argument("--payload-file", type=Path, required=True)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    try:
        if args.command == "build":
            build_payload(args.output)
        else:
            apply_payload(
                environment_path=args.env_file,
                payload_path=args.payload_file,
            )
    except ManagedEnvironmentError as exc:
        parser.error(str(exc))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
