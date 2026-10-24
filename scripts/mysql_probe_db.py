"""Connection helpers for disposable local MySQL probes (generated databases only)."""

from __future__ import annotations

from contextlib import contextmanager
import os
import re
from unittest.mock import patch
from urllib.parse import quote_plus

import pymysql

SCHEMA_IDENTIFIER = re.compile(r"^[A-Za-z0-9_]+$")

# Everything that defines the schema's shape; never row counts, statistics
# or AUTO_INCREMENT counters, which a reset changes on purpose.
_SHAPE_QUERIES = (
    "SELECT TABLE_NAME, TABLE_TYPE, ENGINE, TABLE_COLLATION FROM information_schema.TABLES "
    "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME",
    "SELECT TABLE_NAME, ORDINAL_POSITION, COLUMN_NAME, COLUMN_TYPE, IS_NULLABLE, COLUMN_DEFAULT, EXTRA, "
    "COLLATION_NAME FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME, ORDINAL_POSITION",
    "SELECT TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX, COLUMN_NAME, NON_UNIQUE, SUB_PART, EXPRESSION, IS_VISIBLE "
    "FROM information_schema.STATISTICS WHERE TABLE_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME, INDEX_NAME, SEQ_IN_INDEX",
    "SELECT TABLE_NAME, CONSTRAINT_NAME, CONSTRAINT_TYPE FROM information_schema.TABLE_CONSTRAINTS "
    "WHERE TABLE_SCHEMA = DATABASE() ORDER BY TABLE_NAME, CONSTRAINT_NAME",
    "SELECT TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION, COLUMN_NAME, REFERENCED_TABLE_NAME, "
    "REFERENCED_COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE WHERE TABLE_SCHEMA = DATABASE() "
    "ORDER BY TABLE_NAME, CONSTRAINT_NAME, ORDINAL_POSITION",
    "SELECT TABLE_NAME, CONSTRAINT_NAME, UPDATE_RULE, DELETE_RULE FROM information_schema.REFERENTIAL_CONSTRAINTS "
    "WHERE CONSTRAINT_SCHEMA = DATABASE() ORDER BY TABLE_NAME, CONSTRAINT_NAME",
    "SELECT CONSTRAINT_NAME, CHECK_CLAUSE FROM information_schema.CHECK_CONSTRAINTS "
    "WHERE CONSTRAINT_SCHEMA = DATABASE() ORDER BY CONSTRAINT_NAME",
)


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


def _schema_shape(connection) -> tuple:
    return tuple(tuple(tuple(row) for row in connection.exec_driver_sql(query)) for query in _SHAPE_QUERIES)


def _base_tables(connection) -> list[str]:
    tables = [row[0] for row in connection.exec_driver_sql(
        "SELECT TABLE_NAME FROM information_schema.TABLES "
        "WHERE TABLE_SCHEMA = DATABASE() AND TABLE_TYPE = 'BASE TABLE' ORDER BY TABLE_NAME")]
    unsafe = [table for table in tables if not SCHEMA_IDENTIFIER.fullmatch(table)]
    if unsafe:
        raise RuntimeError(f"Refusing to reset a probe table with an unsafe name: {unsafe[0]!r}")
    return tables


def _non_empty_tables(connection, tables: list[str]) -> list[str]:
    if not tables:
        return []
    probe = " UNION ALL ".join(
        f"SELECT '{table}' FROM DUAL WHERE EXISTS (SELECT 1 FROM `{table}`)" for table in tables)
    return [row[0] for row in connection.exec_driver_sql(probe)]


def _empty_tables(connection, auto_increment_tables: set[str]) -> int:
    """Delete every row and restart AUTO_INCREMENT; prove the schema is empty."""

    tables = _base_tables(connection)
    dirty = _non_empty_tables(connection, tables)
    connection.exec_driver_sql("SET SESSION FOREIGN_KEY_CHECKS = 0")
    try:
        for table in dirty:
            connection.exec_driver_sql(f"DELETE FROM `{table}`")
        connection.commit()
        # Fixtures name rows by id (user 1); a fresh table would start there.
        for table in dirty:
            if table in auto_increment_tables:
                connection.exec_driver_sql(f"ALTER TABLE `{table}` AUTO_INCREMENT = 1")
    finally:
        connection.exec_driver_sql("SET SESSION FOREIGN_KEY_CHECKS = 1")
    leftover = _non_empty_tables(connection, tables)
    connection.rollback()
    if leftover:
        raise RuntimeError(f"Probe schema reset left rows in {', '.join(leftover)}.")
    return len(dirty)


@contextmanager
def reuse_generated_schema(database_name: str):
    """Build a probe's generated schema once and empty it between tests.

    The SQLite fixtures that probes reuse call db.create_all() in setUp and
    db.drop_all() in tearDown. On MySQL every CREATE TABLE is data-dictionary
    DDL, so rebuilding all tables cost about 7 s per test on CI (14 s locally)
    while the test itself took under a second. Inside this context drop_all
    deletes the rows of every non-empty table, restarts its AUTO_INCREMENT and
    proves the schema is empty; the next create_all then finds every table.
    A test that changed the schema (the migration cases) leaves a shape that
    differs from the first build, so that schema is dropped for real and the
    next test builds a fresh one. Any engine bound elsewhere keeps the real
    drop_all: only the generated schema named here is ever emptied.
    Yields counters {"resets", "rebuilds", "tables_emptied"} for the report.
    """

    from models import db

    if not SCHEMA_IDENTIFIER.fullmatch(database_name or ""):
        raise RuntimeError("Schema reuse requires a generated probe schema name.")
    create_all, drop_all = db.create_all, db.drop_all
    built: dict[str, object] = {}
    counters = {"resets": 0, "rebuilds": 0, "tables_emptied": 0}

    def owned() -> bool:
        return db.engine.dialect.name == "mysql" and db.engine.url.database == database_name

    def reusing_create_all(*args, **kwargs):
        create_all(*args, **kwargs)
        if "shape" not in built and owned():
            with db.engine.connect() as connection:
                shape = _schema_shape(connection)
            built["shape"] = shape
            # Columns rows: (table, position, name, type, nullable, default, extra, collation).
            built["auto_increment"] = {row[0] for row in shape[1] if "auto_increment" in (row[6] or "").lower()}

    def resetting_drop_all(*args, **kwargs):
        if "shape" not in built or not owned():
            return drop_all(*args, **kwargs)
        db.session.remove()
        with db.engine.connect() as connection:
            unchanged = _schema_shape(connection) == built["shape"]
            connection.rollback()
            if unchanged:
                counters["tables_emptied"] += _empty_tables(connection, built["auto_increment"])
        if not unchanged:
            counters["rebuilds"] += 1
            return drop_all(*args, **kwargs)
        counters["resets"] += 1
        return None

    with patch.object(db, "create_all", reusing_create_all), patch.object(db, "drop_all", resetting_drop_all):
        yield counters

