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
)
MANAGED_VARIABLE_KEYS = (
    "CORS_ALLOWED_ORIGINS",
    "FLASK_APP",
    "DB_PORT",
    "FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH",
    "FLASHCARD_MEDIA_MAX_BYTES",
    "FLASHCARD_MEDIA_SCAN_ENABLED",
    "PAYMENTS_ENABLED",
    "PAYMENTS_PAID_INSTALL_REQUIRED",
    "PAYMENTS_PROVIDER",
)
MANAGED_ENV_KEYS = MANAGED_SECRET_KEYS + MANAGED_VARIABLE_KEYS
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


def build_payload(output_path: Path) -> None:
    values: dict[str, str] = {}
    missing_keys: list[str] = []

    for key in MANAGED_ENV_KEYS:
        value = os.environ.get(key, "")
        if not value:
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
    if not isinstance(encoded_values, dict) or set(encoded_values) != set(MANAGED_ENV_KEYS):
        raise ManagedEnvironmentError("Managed environment payload keys do not match the allowed key set.")

    values: dict[str, str] = {}
    for key in MANAGED_ENV_KEYS:
        encoded_value = encoded_values.get(key)
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
        key: _format_environment_assignment(key, values[key])
        for key in MANAGED_ENV_KEYS
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

    for key in MANAGED_ENV_KEYS:
        if key in seen_keys:
            continue
        output_lines.append(desired_lines[key])
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
