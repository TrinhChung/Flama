"""Connection helpers for disposable local MySQL probes (generated databases only)."""

from __future__ import annotations

import os
import re
from urllib.parse import quote_plus

import pymysql

SCHEMA_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")


def _connection_settings() -> dict[str, object]:
    password = os.getenv("DB_PASSWORD", "")
    user = os.getenv("DB_USER", "").strip()
    if not user:
        raise RuntimeError("DB_USER is required for the disposable MySQL probe.")
    return {
        "host": os.getenv("DB_HOST", "127.0.0.1").strip() or "127.0.0.1",
        "port": int(os.getenv("DB_PORT", "3306")),
        "user": user,
        "password": password,
        "charset": "utf8mb4",
        "autocommit": True,
    }


def _source_database_collation(admin: pymysql.connections.Connection) -> str:
    """Match the configured schema default without reading application rows."""

    source_database = os.getenv("DB_NAME", "").strip()
    if not SCHEMA_IDENTIFIER.fullmatch(source_database):
        raise RuntimeError("A safe DB_NAME is required for the disposable MySQL probe.")
    with admin.cursor() as cursor:
        cursor.execute(
            "SELECT DEFAULT_CHARACTER_SET_NAME, DEFAULT_COLLATION_NAME "
            "FROM information_schema.SCHEMATA WHERE SCHEMA_NAME=%s",
            (source_database,),
        )
        row = cursor.fetchone()
    if row is None or row[0] != "utf8mb4" or not SCHEMA_IDENTIFIER.fullmatch(str(row[1])):
        raise RuntimeError("The configured schema must use a safe utf8mb4 collation.")
    return str(row[1])


def _database_uri(settings: dict[str, object], database_name: str) -> str:
    return (
        "mysql+pymysql://"
        f"{quote_plus(str(settings['user']))}:{quote_plus(str(settings['password']))}"
        f"@{settings['host']}:{settings['port']}/{database_name}?charset=utf8mb4"
    )

