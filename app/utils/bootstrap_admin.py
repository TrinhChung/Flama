"""Load bootstrap admin credentials from environment variables."""

from __future__ import annotations

import os
from dataclasses import dataclass


@dataclass(frozen=True)
class BootstrapAdminCredentials:
    email: str
    username: str
    password: str


class MissingBootstrapAdminCredentials(RuntimeError):
    """Raised when required bootstrap admin env vars are missing."""


def resolve_bootstrap_admin_credentials(*, require_password: bool = True) -> BootstrapAdminCredentials:
    email = str(os.environ.get("ADMIN_EMAIL") or "").strip()
    username = (
        str(os.environ.get("ADMIN_USERNAME") or "").strip()
        or str(os.environ.get("ADMIN_USER") or "").strip()
        or (email.split("@", 1)[0] if email and "@" in email else "")
    )
    password = str(os.environ.get("ADMIN_PASSWORD") or "").strip()

    missing_fields: list[str] = []
    if not email:
        missing_fields.append("ADMIN_EMAIL")
    if not username:
        missing_fields.append("ADMIN_USERNAME")
    if require_password and not password:
        missing_fields.append("ADMIN_PASSWORD")

    if missing_fields:
        joined = ", ".join(missing_fields)
        raise MissingBootstrapAdminCredentials(
            f"Thiếu biến môi trường bootstrap admin: {joined}."
        )

    return BootstrapAdminCredentials(
        email=email,
        username=username,
        password=password,
    )
