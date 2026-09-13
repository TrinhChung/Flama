"""Portable SQLAlchemy types used by Phase 4 shadow-progress models."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import mysql


MYSQL_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


def bigint() -> sa.types.TypeEngine:
    return sa.BigInteger()


def bigint_pk() -> sa.types.TypeEngine:
    # SQLite autoincrement requires the literal INTEGER PRIMARY KEY spelling.
    return sa.BigInteger().with_variant(sa.Integer(), "sqlite")


def datetime6() -> sa.types.TypeEngine:
    return sa.DateTime().with_variant(mysql.DATETIME(fsp=6), "mysql")


def ascii_string(length: int, *, fixed: bool = False) -> sa.types.TypeEngine:
    portable = sa.CHAR(length) if fixed else sa.String(length)
    mysql_type = (
        mysql.CHAR(length, charset="ascii", collation="ascii_bin")
        if fixed
        else mysql.VARCHAR(length, charset="ascii", collation="ascii_bin")
    )
    return portable.with_variant(mysql_type, "mysql")


def binary_string(length: int) -> sa.types.TypeEngine:
    return sa.LargeBinary(length).with_variant(mysql.VARBINARY(length), "mysql")


def binary_hash() -> sa.types.TypeEngine:
    return sa.LargeBinary(32).with_variant(mysql.BINARY(32), "mysql")
