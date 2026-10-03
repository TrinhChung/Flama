"""Verify that read-only audits run under a SELECT-only MySQL principal.

Read-only readiness and audit commands call ``collect_connection_safety``
before inspecting application tables; a principal with any write grant is
refused.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any, Iterable

import sqlalchemy as sa
from flask import current_app, has_app_context

from models import db

_ALLOWED_READ_PRIVILEGES = frozenset({"SELECT", "SHOW VIEW", "USAGE"})


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def analyze_mysql_grants(grants: Iterable[str]) -> dict[str, Any]:
    """Classify grants without returning principal names or raw grant text."""

    normalized = [str(item or "").strip().upper() for item in grants]
    privilege_tokens: set[str] = set()
    has_select = False
    has_grant_option = False
    unparsed_grant_rows = 0
    for grant in normalized:
        match = re.search(r"\bGRANT\s+(.+?)\s+ON\s+", grant)
        if match:
            privilege_tokens.update(
                token.strip() for token in match.group(1).split(",") if token.strip()
            )
        else:
            unparsed_grant_rows += 1
        has_select = has_select or "SELECT" in privilege_tokens
        has_grant_option = has_grant_option or "WITH GRANT OPTION" in grant

    disallowed = sorted(privilege_tokens - _ALLOWED_READ_PRIVILEGES)
    if has_grant_option and "GRANT OPTION" not in disallowed:
        disallowed.append("GRANT OPTION")
    if unparsed_grant_rows:
        disallowed.append("UNPARSED OR ROLE GRANT")
    disallowed = sorted(disallowed)
    return {
        "grant_row_count": len(normalized),
        "unparsed_grant_row_count": unparsed_grant_rows,
        "has_select": has_select,
        "disallowed_privileges": disallowed,
        "select_only_verified": bool(
            has_select and not disallowed and not unparsed_grant_rows
        ),
    }


def collect_connection_safety() -> dict[str, Any]:
    """Verify MySQL audit credentials before reading application tables."""

    dialect = str(db.engine.dialect.name or "").lower()
    if not dialect.startswith("mysql"):
        return {
            "dialect": dialect,
            "evidence_scope": "non-mysql-fixture",
            "select_only_verified": False,
            "current_mysql_evidence": False,
        }

    identity = db.session.execute(
        sa.text(
            "SELECT CURRENT_USER() AS connected_principal, DATABASE() AS database_name, "
            "@@version AS server_version, @@sql_mode AS sql_mode, "
            "@@character_set_database AS database_charset, "
            "@@collation_database AS database_collation, @@time_zone AS time_zone, "
            "@@transaction_isolation AS transaction_isolation"
        )
    ).mappings().one()
    grant_rows = db.session.execute(sa.text("SHOW GRANTS FOR CURRENT_USER")).all()
    grants = [str(row[0]) for row in grant_rows]
    grant_analysis = analyze_mysql_grants(grants)
    if not grant_analysis["select_only_verified"]:
        raise RuntimeError(
            "Audit refused before application-table inspection: the MySQL principal "
            "is not verified SELECT-only."
        )
    isolation = str(identity.get("transaction_isolation") or "").upper()
    if (
        has_app_context()
        and current_app.config.get("STUDY_PROGRESS_SHADOW_COMPARE_ENABLED", False)
        and isolation != "REPEATABLE-READ"
    ):
        raise RuntimeError(
            "Audit refused before application-table inspection: shadow comparison "
            "requires a REPEATABLE-READ MySQL snapshot."
        )

    principal = str(identity.get("connected_principal") or "")
    database_name = str(identity.get("database_name") or "")
    return {
        "dialect": dialect,
        "evidence_scope": "current-mysql-select-only",
        "select_only_verified": True,
        "current_mysql_evidence": True,
        "principal_sha256": _sha256_text(principal),
        "database_sha256": _sha256_text(database_name),
        "server_version": str(identity.get("server_version") or ""),
        "sql_mode": sorted(
            item.strip()
            for item in str(identity.get("sql_mode") or "").split(",")
            if item.strip()
        ),
        "database_charset": str(identity.get("database_charset") or ""),
        "database_collation": str(identity.get("database_collation") or ""),
        "time_zone": str(identity.get("time_zone") or ""),
        "transaction_isolation": isolation,
        **grant_analysis,
    }
