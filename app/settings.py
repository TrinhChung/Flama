"""Lightweight app configuration helpers."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any, Mapping
from urllib.parse import quote_plus

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
_PROCESS_TEST_MEDIA_DIRECTORY: tempfile.TemporaryDirectory[str] | None = None


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


def resolve_test_media_upload_root() -> Path:
    """Return one writable media root isolated to the current test process."""
    configured = os.getenv("FLAMA_TEST_MEDIA_UPLOAD_ROOT", "").strip()
    if configured:
        return resolve_media_upload_root(configured)

    global _PROCESS_TEST_MEDIA_DIRECTORY
    if _PROCESS_TEST_MEDIA_DIRECTORY is None:
        _PROCESS_TEST_MEDIA_DIRECTORY = tempfile.TemporaryDirectory(
            prefix="flama-test-media-"
        )
    return Path(_PROCESS_TEST_MEDIA_DIRECTORY.name).resolve()


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
        else (os.getenv("SQLALCHEMY_DATABASE_URI") or build_database_uri_from_env())
    )

    engine_options: dict[str, Any] = {
        "pool_pre_ping": True,
        "pool_recycle": coerce_int_env("DB_POOL_RECYCLE_SECONDS", default=1800),
    }
    if str(database_uri).startswith(("mysql:", "mysql+")):
        engine_options.update(
            pool_size=coerce_int_env("DB_POOL_SIZE", default=4),
            max_overflow=coerce_int_env("DB_MAX_OVERFLOW", default=1),
            pool_timeout=coerce_int_env("DB_POOL_TIMEOUT_SECONDS", default=5),
        )

    explicit_media_root = str(
        (overrides or {}).get("FLASHCARD_MEDIA_UPLOAD_ROOT") or ""
    ).strip()
    is_testing = bool((overrides or {}).get("TESTING", False))
    initial_media_root = (
        explicit_media_root
        or (str(resolve_test_media_upload_root()) if is_testing else None)
    )

    config: dict[str, Any] = {
        "SECRET_KEY": os.getenv("SECRET_KEY", "change-me"),
        # Production keeps Werkzeug's current secure default. Test apps use a
        # deliberately cheap but still valid hash so unrelated integration
        # fixtures do not spend most of their runtime deriving passwords.
        "PASSWORD_HASH_METHOD": (
            os.getenv("PASSWORD_HASH_METHOD", "").strip()
            or ("pbkdf2:sha256:1000" if is_testing else "")
        ),
        # Most backend tests exercise JSON APIs and only need an HTML response
        # for incidental redirects. A dedicated SPA artifact contract disables
        # this shell and verifies the real Vite build separately.
        "SPA_TEST_SHELL_ENABLED": is_testing,
        "SQLALCHEMY_DATABASE_URI": database_uri,
        "SQLALCHEMY_TRACK_MODIFICATIONS": False,
        "SQLALCHEMY_ENGINE_OPTIONS": engine_options,
        "CORS_ALLOWED_ORIGINS": comma_separated_env("CORS_ALLOWED_ORIGINS"),
        "FRONTEND_URL": os.getenv("FRONTEND_URL", "").strip().rstrip("/"),
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
        "CONNECT_CARD_PACKAGE_TARGET_ITEMS": coerce_int_env(
            "CONNECT_CARD_PACKAGE_TARGET_ITEMS",
            default=500,
        ),
        "FLASHCARD_MEDIA_UPLOAD_ROOT": str(resolve_media_upload_root(initial_media_root)),
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
        "MEDIA_PROXY_USE_XACCEL": (
            os.getenv("MEDIA_PROXY_USE_XACCEL", "0").strip().lower() in {"1", "true", "yes", "on"}
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
        "MCP_TOKEN_RATE_LIMIT_ENABLED": coerce_bool_env(
            "MCP_TOKEN_RATE_LIMIT_ENABLED",
            default=False,
        ),
        "MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS": coerce_int_env(
            "MCP_TOKEN_RATE_LIMIT_WINDOW_SECONDS",
            default=60,
        ),
        "MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS": coerce_int_env(
            "MCP_TOKEN_RATE_LIMIT_MAX_REQUESTS",
            default=100_000,
        ),
        "REDIS_URL": os.getenv("REDIS_URL", "redis://127.0.0.1:6379/0").strip(),
        "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS": coerce_int_env(
            "REDIS_SOCKET_CONNECT_TIMEOUT_SECONDS", default=1
        ),
        "REDIS_SOCKET_TIMEOUT_SECONDS": coerce_int_env(
            "REDIS_SOCKET_TIMEOUT_SECONDS", default=1
        ),
        # Opt-in only: real admission additionally requires a live compatible
        # continuous consumer in the same explicit namespace/database pool.
        # Existing accepted work drains independently of this issuance switch.
        "STUDY_ASYNC_BATCH_ENABLED": coerce_bool_env(
            "STUDY_ASYNC_BATCH_ENABLED",
            default=False,
        ),
        # Empty preserves the legacy test/manual queue, but a continuous worker
        # requires explicit isolation. Changing it does not remove DB admissions.
        "STUDY_QUEUE_NAMESPACE": os.getenv("STUDY_QUEUE_NAMESPACE", "").strip(),
        # Wire v3 creation is negotiated per client and enabled only after all
        # HTTP/worker consumers have dual readers. Existing v2 readers remain.
        "STUDY_WIRE_V3_ENABLED": coerce_bool_env(
            "STUDY_WIRE_V3_ENABLED",
            default=False,
        ),
        # Wire v4 is NOTE-authority-only (Note-token leases). Off by default;
        # it must be enabled before any learner is enrolled in NOTE (R1).
        "STUDY_WIRE_V4_ENABLED": coerce_bool_env(
            "STUDY_WIRE_V4_ENABLED",
            default=False,
        ),
        # Phase 4 shadow progress remains inert until each later rollout gate
        # is approved independently.  None of these flags grants read authority.
        "STUDY_PROGRESS_SHADOW_WRITE_ENABLED": coerce_bool_env(
            "STUDY_PROGRESS_SHADOW_WRITE_ENABLED",
            default=False,
        ),
        "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED": coerce_bool_env(
            "STUDY_PROGRESS_SHADOW_COMPARE_ENABLED",
            default=False,
        ),
        "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED": coerce_bool_env(
            "STUDY_PROGRESS_SHADOW_BACKFILL_ENABLED",
            default=False,
        ),
        "RATE_LIMIT_BACKEND": os.getenv("RATE_LIMIT_BACKEND", "local").strip().lower(),
        "RATE_LIMIT_KEY_PREFIX": os.getenv("RATE_LIMIT_KEY_PREFIX", "flama:v1").strip(),
        "RATE_LIMIT_HMAC_KEY": os.getenv("RATE_LIMIT_HMAC_KEY", "").strip(),
        "RATE_LIMIT_DAILY_ENABLED": coerce_bool_env("RATE_LIMIT_DAILY_ENABLED", default=True),
        "RATE_LIMIT_REGULAR_DAILY_MAX": coerce_int_env("RATE_LIMIT_REGULAR_DAILY_MAX", default=300),
        "RATE_LIMIT_CREATOR_DAILY_MAX": coerce_int_env("RATE_LIMIT_CREATOR_DAILY_MAX", default=2000),
        "RATE_LIMIT_ENTERPRISE_DAILY_MAX": coerce_int_env("RATE_LIMIT_ENTERPRISE_DAILY_MAX", default=10000),
        "RATE_LIMIT_DAILY_TIMEZONE": os.getenv("RATE_LIMIT_DAILY_TIMEZONE", "Asia/Ho_Chi_Minh").strip() or "Asia/Ho_Chi_Minh",
        "MCP_PREVIEW_BACKEND": os.getenv("MCP_PREVIEW_BACKEND", "local").strip().lower(),
        "MCP_PREVIEW_TTL_SECONDS": coerce_int_env("MCP_PREVIEW_TTL_SECONDS", default=600),
        "SHARED_DECK_TREE_CLONE_MODE": os.getenv(
            "SHARED_DECK_TREE_CLONE_MODE", "batched"
        ).strip().lower(),
        "DECK_SOURCE_NOTETYPE_GUARD_MODE": os.getenv(
            "DECK_SOURCE_NOTETYPE_GUARD_MODE", "shadow"
        ).strip().lower(),
        "MARKETPLACE_SAMPLE_MODE": os.getenv(
            "MARKETPLACE_SAMPLE_MODE", "shadow_cache"
        ).strip().lower(),
        "MARKETPLACE_SAMPLE_SCHEMA_VERSION": 1,
        "FLASHCARD_RENDER_PREVIEW_CACHE_MAX_ENTRIES": coerce_int_env(
            "FLASHCARD_RENDER_PREVIEW_CACHE_MAX_ENTRIES", default=512
        ),


        "PAYOS_CLIENT_ID": os.getenv("PAYOS_CLIENT_ID", "").strip(),
        "PAYOS_API_KEY": os.getenv("PAYOS_API_KEY", "").strip(),
        "PAYOS_CHECKSUM_KEY": os.getenv("PAYOS_CHECKSUM_KEY", "").strip(),
        "SUPPORT_CONTACT_EMAIL": (
            os.getenv("SUPPORT_CONTACT_EMAIL", "").strip()
            or os.getenv("ADMIN_EMAIL", "").strip()
        ),
        "TRUST_PROXY": coerce_bool_env(
            "TRUST_PROXY",
            default=coerce_bool_env("FLAMA_TRUST_PROXY", default=False),
        ),
        "EMAIL_ENABLED": coerce_bool_env("EMAIL_ENABLED", default=False),
        "EMAIL_PROVIDER": (os.getenv("EMAIL_PROVIDER", "disabled").strip().lower() or "disabled"),
        "EMAIL_ENVIRONMENT": (os.getenv("EMAIL_ENVIRONMENT", "local").strip().lower() or "local"),
        "EMAIL_FROM_ADDRESS": os.getenv("EMAIL_FROM_ADDRESS", "no-reply@flama.local").strip(),
        "EMAIL_FROM_NAME": os.getenv("EMAIL_FROM_NAME", "Flama").strip() or "Flama",
        "EMAIL_REPLY_TO": os.getenv("EMAIL_REPLY_TO", "").strip(),
        "EMAIL_RECIPIENT_ALLOWLIST": comma_separated_env("EMAIL_RECIPIENT_ALLOWLIST"),
        "EMAIL_REDIRECT_ALL_TO": os.getenv("EMAIL_REDIRECT_ALL_TO", "").strip(),
        "EMAIL_RESEND_API_KEY": os.getenv("EMAIL_RESEND_API_KEY", "").strip(),
        "EMAIL_SMTP_HOST": os.getenv("EMAIL_SMTP_HOST", "").strip(),
        "EMAIL_SMTP_PORT": coerce_int_env("EMAIL_SMTP_PORT", default=587),
        "EMAIL_SMTP_USER": os.getenv("EMAIL_SMTP_USER", "").strip(),
        "EMAIL_SMTP_PASSWORD": os.getenv("EMAIL_SMTP_PASSWORD", ""),
        "EMAIL_SMTP_USE_TLS": coerce_bool_env("EMAIL_SMTP_USE_TLS", default=True),
        "EMAIL_SMTP_USE_SSL": coerce_bool_env("EMAIL_SMTP_USE_SSL", default=False),
        "EMAIL_PROVIDER_TIMEOUT_SECONDS": coerce_int_env(
            "EMAIL_PROVIDER_TIMEOUT_SECONDS",
            default=10,
        ),
        "EMAIL_PROVIDER_MAX_ATTEMPTS": coerce_int_env(
            "EMAIL_PROVIDER_MAX_ATTEMPTS", default=2
        ),
        "EMAIL_PROVIDER_RETRY_BACKOFF_SECONDS": float(
            os.getenv("EMAIL_PROVIDER_RETRY_BACKOFF_SECONDS", "0.25") or "0.25"
        ),
        "PUBLIC_APP_URL": (
            os.getenv("PUBLIC_APP_URL", "").strip().rstrip("/")
            or os.getenv("FRONTEND_URL", "").strip().rstrip("/")
        ),
        "PASSWORD_RESET_TOKEN_TTL_MINUTES": coerce_int_env(
            "PASSWORD_RESET_TOKEN_TTL_MINUTES", default=30
        ),
        "PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS": coerce_int_env(
            "PASSWORD_RESET_RATE_LIMIT_WINDOW_SECONDS", default=900
        ),
        "PASSWORD_RESET_RATE_LIMIT_MAX_REQUESTS": coerce_int_env(
            "PASSWORD_RESET_RATE_LIMIT_MAX_REQUESTS", default=3
        ),
        "GOOGLE_OAUTH_CLIENT_ID": os.getenv("GOOGLE_OAUTH_CLIENT_ID", "").strip(),
        "GOOGLE_OAUTH_CLIENT_SECRET": os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "").strip(),
        "GOOGLE_OAUTH_REDIRECT_URI": os.getenv("GOOGLE_OAUTH_REDIRECT_URI", "").strip(),
    }
    config["PAYMENTS_V1_ENABLED"] = config["PAYMENTS_ENABLED"]

    if overrides:
        config.update(overrides)

    if bool(config.get("TESTING")) and not (
        overrides and "RATE_LIMIT_DAILY_ENABLED" in overrides
    ):
        # Most tests do not exercise quotas. Keep them order-independent; the
        # dedicated rate-limit suites opt in explicitly.
        config["RATE_LIMIT_DAILY_ENABLED"] = False

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

    # By default, in production/normal runtime, schema is managed solely by Alembic migrations.
    # App startup only runs DB create/maintenance in TESTING mode or if explicitly enabled via env/override.
    config.setdefault(
        "STARTUP_RUN_MAINTENANCE",
        coerce_bool_env("STARTUP_RUN_MAINTENANCE", default=testing),
    )
    config.setdefault(
        "STARTUP_RUN_DB_CREATE_ALL",
        coerce_bool_env("STARTUP_RUN_DB_CREATE_ALL", default=testing),
    )
    config.setdefault(
        "STARTUP_RUN_USER_MANAGEMENT_SCHEMA",
        coerce_bool_env("STARTUP_RUN_USER_MANAGEMENT_SCHEMA", default=testing),
    )
    config.setdefault(
        "STARTUP_RUN_BACKWARD_COMPAT_SCHEMA",
        coerce_bool_env("STARTUP_RUN_BACKWARD_COMPAT_SCHEMA", default=False),
    )
    config.setdefault(
        "STARTUP_CHECK_DB_CONNECTIVITY",
        coerce_bool_env("STARTUP_CHECK_DB_CONNECTIVITY", default=True),
    )
    # Seed operations are decoupled from normal app startup
    config.setdefault("STARTUP_RUN_DEFAULT_USER_ROLE_SEED", testing)
    config.setdefault("STARTUP_RUN_DEFAULT_TTS_PROVIDER_SEED", testing)
    config.setdefault("STARTUP_RUN_CLONE_CUTOVER", False)
    config.setdefault(
        "STARTUP_CUTOVER_FAIL_ON_MISMATCH",
        _startup_cutover_fail_on_mismatch_default(default_cutover_fail_on_mismatch),
    )
    config.setdefault("WTF_CSRF_ENABLED", not testing)
    config.setdefault("CSRF_EXEMPT_ENDPOINTS", {"payments.payos_webhook"})
    config.setdefault("SESSION_COOKIE_HTTPONLY", True)
    config.setdefault("SESSION_COOKIE_SAMESITE", "Lax")
    config.setdefault(
        "LOGIN_RATE_LIMIT_ENABLED",
        coerce_bool_env("LOGIN_RATE_LIMIT_ENABLED", default=not testing),
    )
    config.setdefault(
        "LOGIN_RATE_LIMIT_WINDOW_SECONDS",
        coerce_int_env("LOGIN_RATE_LIMIT_WINDOW_SECONDS", default=60),
    )
    config.setdefault(
        "LOGIN_RATE_LIMIT_MAX_ATTEMPTS",
        coerce_int_env("LOGIN_RATE_LIMIT_MAX_ATTEMPTS", default=5),
    )
    config.setdefault(
        "LOGIN_RATE_LIMIT_LOCKOUT_SECONDS",
        coerce_int_env("LOGIN_RATE_LIMIT_LOCKOUT_SECONDS", default=5 * 60),
    )
    if testing:
        config.setdefault("EMAIL_PROVIDER", "memory")
        config.setdefault("EMAIL_ENVIRONMENT", "test")


def _startup_cutover_fail_on_mismatch_default(default: bool) -> bool:
    if os.getenv("STARTUP_CUTOVER_FAIL_ON_MISMATCH") is not None:
        return coerce_bool_env("STARTUP_CUTOVER_FAIL_ON_MISMATCH", default=default)
    return coerce_bool_env("FLASHCARDS_SHARE_CUTOVER_FAIL_ON_MISMATCH", default=default)
