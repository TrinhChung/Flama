"""Lightweight app configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent


def load_environment() -> None:
    """Load .env values once per process."""
    load_dotenv()


def coerce_bool_env(name: str, *, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    token = str(raw_value).strip().lower()
    if not token:
        return default
    if token in {"1", "true", "yes", "on"}:
        return True
    if token in {"0", "false", "no", "off"}:
        return False
    return default


def coerce_int_env(name: str, *, default: int) -> int:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    try:
        return int(str(raw_value).strip())
    except (TypeError, ValueError):
        return default


def comma_separated_env(name: str) -> tuple[str, ...]:
    return tuple(
        value
        for raw_value in os.getenv(name, "").split(",")
        if (value := raw_value.strip().rstrip("/"))
    )


def resolve_media_upload_root(raw_value: str | None = None, *, base_dir: Path = BASE_DIR) -> Path:
    """Resolve media root path for local media uploads."""
    raw = str(raw_value or "").strip() or os.getenv("FLASHCARD_MEDIA_UPLOAD_ROOT", "").strip()
    if raw:
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = (base_dir / candidate).resolve()
        else:
            candidate = candidate.resolve()
    else:
        # Keep the default inside static for local Windows development so uploads
        # do not depend on an external writable folder configuration.
        candidate = (base_dir / "static" / "uploads" / "flashcard_media").resolve()
    candidate.mkdir(parents=True, exist_ok=True)
    return candidate


def build_database_uri_from_env() -> str:
    """Construct the MySQL connection string from environment variables."""
    db_user = os.getenv("DB_USER", "").strip()
    db_password = os.getenv("DB_PASSWORD", "")
    db_host = os.getenv("DB_HOST", "localhost").strip()
    db_port = os.getenv("DB_PORT", "3306").strip()
    db_name = os.getenv("DB_NAME", "").strip()

    if not db_user or not db_name:
        raise RuntimeError(
            "DB_USER và DB_NAME phải được cấu hình trong tập tin .env."
        )

    safe_password = quote_plus(db_password)
    return (
        f"mysql+pymysql://{db_user}:{safe_password}"
        f"@{db_host}:{db_port}/{db_name}?charset=utf8mb4"
    )


def build_app_config(overrides: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Build a single config mapping from env plus optional overrides."""
    load_environment()
    database_uri = (
        overrides.get("SQLALCHEMY_DATABASE_URI")
        if overrides and overrides.get("SQLALCHEMY_DATABASE_URI")
        else build_database_uri_from_env()
    )

    config: dict[str, Any] = {
        "SECRET_KEY": os.getenv("SECRET_KEY", "change-me"),
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": {
            "pool_pre_ping": True,
            "pool_recycle": 1800,
        },
        "CORS_ALLOWED_ORIGINS": comma_separated_env("CORS_ALLOWED_ORIGINS"),
        # Browser-driven Anki imports now terminate on the canonical Flask API.
        # Keep the established package-service keys during the transport
        # migration so deployments retain the same bounded upload behavior.
        "ANKI_IMPORT_PACKAGE_MAX_BYTES": coerce_int_env(
            "ANKI_IMPORT_PACKAGE_MAX_BYTES",
            default=16 * 1024 * 1024,
        ),
        "CONNECT_PACKAGE_MAX_BYTES": coerce_int_env(
            "CONNECT_PACKAGE_MAX_BYTES",
            default=16 * 1024 * 1024,
        ),
        "CONNECT_PACKAGE_MAX_ENTRIES": coerce_int_env(
            "CONNECT_PACKAGE_MAX_ENTRIES",
            default=500,
        ),
        "CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES": coerce_int_env(
            "CONNECT_PACKAGE_MAX_UNCOMPRESSED_BYTES",
            default=64 * 1024 * 1024,
        ),
        "CONNECT_PACKAGE_MAX_COMPRESSION_RATIO": coerce_int_env(
            "CONNECT_PACKAGE_MAX_COMPRESSION_RATIO",
            default=100,
        ),
        "CONNECT_IMPORT_MEDIA_MAX_BYTES": coerce_int_env(
            "CONNECT_IMPORT_MEDIA_MAX_BYTES",
            default=10 * 1024 * 1024,
        ),
        "CONNECT_CARD_PACKAGE_MAX_ITEMS": coerce_int_env(
            "CONNECT_CARD_PACKAGE_MAX_ITEMS",
            default=1000,
        ),
        "FLASHCARD_MEDIA_UPLOAD_ROOT": str(resolve_media_upload_root()),
        "FLASHCARD_MEDIA_MAX_BYTES": int(os.getenv("FLASHCARD_MEDIA_MAX_BYTES", str(10 * 1024 * 1024))),
        "IMAGE_LIBRARY_MAX_BYTES": int(os.getenv("IMAGE_LIBRARY_MAX_BYTES", str(5 * 1024 * 1024))),
        "IMAGE_LIBRARY_MAX_PIXELS": coerce_int_env(
            "IMAGE_LIBRARY_MAX_PIXELS",
            default=25_000_000,
        ),
        "IMAGE_LIBRARY_REMOTE_FETCH_TIMEOUT_SECONDS": coerce_int_env(
            "IMAGE_LIBRARY_REMOTE_FETCH_TIMEOUT_SECONDS",
            default=6,
        ),
        "IMAGE_LIBRARY_REMOTE_FETCH_MAX_REDIRECTS": coerce_int_env(
            "IMAGE_LIBRARY_REMOTE_FETCH_MAX_REDIRECTS",
            default=3,
        ),
        "FLASHCARD_MEDIA_SCAN_ENABLED": (
            os.getenv("FLASHCARD_MEDIA_SCAN_ENABLED", "0").strip().lower() in {"1", "true", "yes", "on"}
        ),
        "FLASHCARD_MEDIA_SCANNER": None,
        "PAYMENTS_ENABLED": coerce_bool_env(
            "PAYMENTS_ENABLED",
            default=coerce_bool_env("PAYMENTS_V1_ENABLED", default=False),
        ),
        "PAYMENTS_PROVIDER": (os.getenv("PAYMENTS_PROVIDER", "payos").strip().lower() or "payos"),
        "PAYMENTS_PAID_INSTALL_REQUIRED": coerce_bool_env("PAYMENTS_PAID_INSTALL_REQUIRED", default=False),
        "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED": coerce_bool_env(
            "PAYMENTS_WEBHOOK_AUTO_GRANT_ENABLED",
            default=False,
        ),
        "PAYMENTS_ORDER_EXPIRY_SECONDS": coerce_int_env(
            "PAYMENTS_ORDER_EXPIRY_SECONDS",
            default=30 * 60,
        ),
        "MCP_TOKEN_TTL_SECONDS": coerce_int_env("MCP_TOKEN_TTL_SECONDS", default=10 * 60),
        "MCP_TOKEN_MAX_REQUESTS": coerce_int_env("MCP_TOKEN_MAX_REQUESTS", default=30),
        "MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS": coerce_int_env(
            "MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS",
            default=60,
        ),
        "MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS": coerce_int_env(
            "MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS",
            default=20,
        ),
        "PAYOS_CLIENT_ID": os.getenv("PAYOS_CLIENT_ID", "").strip(),
        "PAYOS_API_KEY": os.getenv("PAYOS_API_KEY", "").strip(),
        "PAYOS_CHECKSUM_KEY": os.getenv("PAYOS_CHECKSUM_KEY", "").strip(),
        "SUPPORT_CONTACT_EMAIL": (
            os.getenv("SUPPORT_CONTACT_EMAIL", "").strip()
            or os.getenv("ADMIN_EMAIL", "").strip()
        ),
    }
    config["PAYMENTS_V1_ENABLED"] = config["PAYMENTS_ENABLED"]

    if overrides:
        config.update(overrides)

    config["FLASHCARD_MEDIA_UPLOAD_ROOT"] = str(
        resolve_media_upload_root(config.get("FLASHCARD_MEDIA_UPLOAD_ROOT"))
    )
    _apply_startup_defaults(config)
    return config


def _apply_startup_defaults(config: dict[str, Any]) -> None:
    testing = bool(config.get("TESTING", False))
    default_cutover_fail_on_mismatch = os.getenv("FLASK_ENV", "").strip().lower() not in {
        "development",
        "dev",
    }

    config.setdefault("STARTUP_RUN_MAINTENANCE", True)
    config.setdefault("STARTUP_RUN_DB_CREATE_ALL", True)
    config.setdefault("STARTUP_RUN_USER_MANAGEMENT_SCHEMA", True)
    config.setdefault("STARTUP_RUN_BACKWARD_COMPAT_SCHEMA", True)
    config.setdefault("STARTUP_RUN_DEFAULT_USER_ROLE_SEED", True)
    config.setdefault("STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED", True)
    # Clone cutover is a one-time corrective task and usually unnecessary in tests.
    config.setdefault("STARTUP_RUN_CLONE_CUTOVER", not testing)
    config.setdefault(
        "STARTUP_CUTOVER_FAIL_ON_MISMATCH",
        _startup_cutover_fail_on_mismatch_default(default_cutover_fail_on_mismatch),
    )
    config.setdefault("WTF_CSRF_ENABLED", not testing)
    config.setdefault("CSRF_EXEMPT_ENDPOINTS", {"payments.payos_webhook"})
    config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    config.setdefault("LOGIN_RATE_LIMIT_ENABLED", not testing)
    config.setdefault("LOGIN_RATE_LIMIT_WINDOW_SECONDS", 60)
    config.setdefault("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", 5)
    config.setdefault("LOGIN_RATE_LIMIT_LOCKOUT_SECONDS", 5 * 60)


def _startup_cutover_fail_on_mismatch_default(default: bool) -> bool:
    if os.getenv("STARTUP_CUTOVER_FAIL_ON_MISMATCH") is not None:
        return coerce_bool_env("STARTUP_CUTOVER_FAIL_ON_MISMATCH", default=default)
    return coerce_bool_env("FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH", default=default)
