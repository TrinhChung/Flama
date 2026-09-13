"""Portable SQLAlchemy types used by Phase 4 shadow-progress models."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.dialects import mysql


MYSQL_TABLE_OPTIONS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}

MYSQL_PARENT_COLLATIONS_INFO_KEY = "mysql_parent_collations"


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


def align_mysql_parent_collations(
    table: sa.Table,
    connection: sa.engine.Connection,
    **_kwargs: object,
) -> None:
    """Match live string FK columns to their existing MySQL parent columns.

    MySQL requires both sides of a string foreign key to have the same
    character set and collation.  The legacy UUID parents inherit the database
    default, while Phase 4 tables deliberately use ``utf8mb4_unicode_ci``.
    Resolve the parent metadata at DDL time so fresh MySQL 8 databases
    (normally ``utf8mb4_0900_ai_ci``) and older Flama databases both work
    without altering an authoritative parent table.
    """

    if connection.dialect.name != "mysql":
        return

    references = table.info.get(MYSQL_PARENT_COLLATIONS_INFO_KEY, {})
    if not references:
        return

    schema_name = table.schema or connection.dialect.default_schema_name
    for column_name, (parent_table, parent_column) in references.items():
        column = table.c[column_name]
        row = connection.execute(
            sa.text(
                "SELECT DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
                "CHARACTER_SET_NAME, COLLATION_NAME "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = :schema_name "
                "AND TABLE_NAME = :table_name "
                "AND COLUMN_NAME = :column_name"
            ),
            {
                "schema_name": schema_name,
                "table_name": parent_table,
                "column_name": parent_column,
            },
        ).mappings().one_or_none()
        if row is None:
            raise RuntimeError(
                f"Cannot resolve MySQL type for {table.name}.{column_name}: "
                f"parent {parent_table}.{parent_column} does not exist."
            )

        data_type = str(row["DATA_TYPE"] or "").lower()
        parent_length = row["CHARACTER_MAXIMUM_LENGTH"]
        charset = str(row["CHARACTER_SET_NAME"] or "").lower()
        collation = str(row["COLLATION_NAME"] or "").lower()
        expected_length = getattr(column.type, "length", None)
        if (
            data_type not in {"char", "varchar"}
            or int(parent_length or 0) != int(expected_length or 0)
            or not charset
            or not collation
        ):
            raise RuntimeError(
                f"Cannot align MySQL type for {table.name}.{column_name}: "
                f"parent {parent_table}.{parent_column} is "
                f"{data_type}({parent_length}) {charset}/{collation}, expected "
                f"a collated string of length {expected_length}."
            )

        portable_type: sa.types.TypeEngine
        mysql_type: sa.types.TypeEngine
        if isinstance(column.type, sa.CHAR):
            portable_type = sa.CHAR(expected_length)
            mysql_type = mysql.CHAR(
                expected_length,
                charset=charset,
                collation=collation,
            )
        else:
            portable_type = sa.String(expected_length)
            mysql_type = mysql.VARCHAR(
                expected_length,
                charset=charset,
                collation=collation,
            )
        column.type = portable_type.with_variant(mysql_type, "mysql")


def register_mysql_parent_collations(
    table: sa.Table,
    references: dict[str, tuple[str, str]],
) -> None:
    """Declare parent-collated FK columns and align them before table DDL."""

    unknown_columns = sorted(set(references) - set(table.c.keys()))
    if unknown_columns:
        raise ValueError(
            f"Unknown parent-collated columns for {table.name}: "
            + ", ".join(unknown_columns)
        )
    table.info[MYSQL_PARENT_COLLATIONS_INFO_KEY] = dict(references)
    sa.event.listen(table, "before_create", align_mysql_parent_collations)
