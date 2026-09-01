"""Run the disposable MySQL concurrency acceptance probe for P1-02.

The probe creates one uniquely named InnoDB table in the configured database,
runs two real two-connection lock scenarios, and drops the table in ``finally``.
Credentials are loaded from environment/.env and are never printed.
"""

from __future__ import annotations

import json
import os
import re
import threading
import time
import uuid
from pathlib import Path
from typing import Any

import pymysql


TABLE_PREFIX = "p102_concurrency_probe_"


def _dotenv_values(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.exists():
        return values
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _connection_config() -> dict[str, Any]:
    dotenv = _dotenv_values(Path(__file__).resolve().parents[1] / ".env")

    def setting(name: str, default: str = "") -> str:
        return str(os.environ.get(name) or dotenv.get(name) or default)

    password = setting("DB_PASSWORD")
    if not password:
        raise RuntimeError("DB_PASSWORD is required for the disposable MySQL probe")
    return {
        "host": setting("DB_HOST", "127.0.0.1"),
        "port": int(setting("DB_PORT", "3306")),
        "user": setting("DB_USER"),
        "password": password,
        "database": setting("DB_NAME"),
        "charset": "utf8mb4",
        "autocommit": False,
        "cursorclass": pymysql.cursors.DictCursor,
    }


def _connect(config: dict[str, Any]):
    return pymysql.connect(**config)


def _run_native_vs_snapshot(config: dict[str, Any], table: str) -> dict[str, Any]:
    setup = _connect(config)
    try:
        with setup.cursor() as cursor:
            cursor.execute(f"DELETE FROM `{table}`")
            cursor.execute(
                f"INSERT INTO `{table}` "
                "(subject_key, revision, applied_local_revision, snapshot_hash, interval_days) "
                "VALUES ('source', 1, 1, %s, 10)",
                ("a" * 64,),
            )
        setup.commit()
    finally:
        setup.close()

    native_locked = threading.Event()
    release_native = threading.Event()
    outcomes: dict[str, Any] = {}
    errors: list[str] = []

    def native_writer() -> None:
        connection = _connect(config)
        try:
            connection.begin()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT revision FROM `{table}` WHERE subject_key='source' FOR UPDATE"
                )
                revision = int(cursor.fetchone()["revision"])
                cursor.execute(
                    f"UPDATE `{table}` SET revision=%s, interval_days=99 "
                    "WHERE subject_key='source'",
                    (revision + 1,),
                )
            native_locked.set()
            if not release_native.wait(timeout=10):
                raise RuntimeError("native writer release timed out")
            connection.commit()
            outcomes["native_revision"] = revision + 1
        except Exception as exc:  # pragma: no cover - diagnostic path
            connection.rollback()
            errors.append(f"native_writer: {type(exc).__name__}: {exc}")
            native_locked.set()
        finally:
            connection.close()

    def snapshot_writer() -> None:
        connection = _connect(config)
        started_at = time.monotonic()
        try:
            connection.begin()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT revision, applied_local_revision FROM `{table}` "
                    "WHERE subject_key='source' FOR UPDATE"
                )
                row = cursor.fetchone()
            outcomes["snapshot_wait_ms"] = round(
                (time.monotonic() - started_at) * 1000,
                1,
            )
            if int(row["revision"]) != int(row["applied_local_revision"]):
                outcomes["snapshot_code"] = "LOCAL_PROGRESS_CHANGED"
                connection.rollback()
                return
            raise AssertionError("snapshot unexpectedly passed the local revision guard")
        except Exception as exc:  # pragma: no cover - diagnostic path
            connection.rollback()
            errors.append(f"snapshot_writer: {type(exc).__name__}: {exc}")
        finally:
            connection.close()

    native_thread = threading.Thread(target=native_writer, daemon=True)
    native_thread.start()
    if not native_locked.wait(timeout=10):
        raise RuntimeError("native writer did not acquire its row lock")
    snapshot_thread = threading.Thread(target=snapshot_writer, daemon=True)
    snapshot_thread.start()
    time.sleep(0.2)
    release_native.set()
    native_thread.join(timeout=10)
    snapshot_thread.join(timeout=10)
    if native_thread.is_alive() or snapshot_thread.is_alive():
        raise RuntimeError("native-vs-snapshot probe thread did not finish")
    if errors:
        raise RuntimeError("; ".join(errors))

    verify = _connect(config)
    try:
        with verify.cursor() as cursor:
            cursor.execute(
                f"SELECT revision, interval_days FROM `{table}` WHERE subject_key='source'"
            )
            final_row = cursor.fetchone()
    finally:
        verify.close()
    if outcomes.get("snapshot_code") != "LOCAL_PROGRESS_CHANGED":
        raise AssertionError("snapshot loser did not return LOCAL_PROGRESS_CHANGED")
    if (int(final_row["revision"]), int(final_row["interval_days"])) != (2, 99):
        raise AssertionError(f"unexpected native-vs-snapshot final row: {final_row}")
    return {
        **outcomes,
        "final_revision": int(final_row["revision"]),
        "final_interval_days": int(final_row["interval_days"]),
    }


def _run_session_vs_cutover(config: dict[str, Any], table: str) -> dict[str, Any]:
    setup = _connect(config)
    try:
        with setup.cursor() as cursor:
            cursor.execute(f"DELETE FROM `{table}`")
            cursor.executemany(
                f"INSERT INTO `{table}` "
                "(subject_key, revision, applied_local_revision, snapshot_hash, interval_days) "
                "VALUES (%s, %s, NULL, NULL, %s)",
                [("local", 7, 20), ("source", 10, 2)],
            )
        setup.commit()
    finally:
        setup.close()

    cutover_locked = threading.Event()
    release_cutover = threading.Event()
    outcomes: dict[str, Any] = {}
    errors: list[str] = []

    def cutover_writer() -> None:
        connection = _connect(config)
        try:
            connection.begin()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT subject_key, revision FROM `{table}` "
                    "WHERE subject_key IN ('local', 'source') "
                    "ORDER BY subject_key ASC FOR UPDATE"
                )
                rows = cursor.fetchall()
                outcomes["lock_order"] = [row["subject_key"] for row in rows]
                next_revision = max(int(row["revision"]) for row in rows) + 1
                cursor.execute(
                    f"UPDATE `{table}` SET revision=%s, interval_days=20 "
                    "WHERE subject_key='source'",
                    (next_revision,),
                )
                cursor.execute(f"DELETE FROM `{table}` WHERE subject_key='local'")
            cutover_locked.set()
            if not release_cutover.wait(timeout=10):
                raise RuntimeError("cutover writer release timed out")
            connection.commit()
            outcomes["cutover_revision"] = next_revision
        except Exception as exc:  # pragma: no cover - diagnostic path
            connection.rollback()
            errors.append(f"cutover_writer: {type(exc).__name__}: {exc}")
            cutover_locked.set()
        finally:
            connection.close()

    def stale_session_writer() -> None:
        connection = _connect(config)
        started_at = time.monotonic()
        try:
            connection.begin()
            with connection.cursor() as cursor:
                cursor.execute(
                    f"SELECT revision FROM `{table}` WHERE subject_key='source' FOR UPDATE"
                )
                revision = int(cursor.fetchone()["revision"])
            outcomes["session_wait_ms"] = round(
                (time.monotonic() - started_at) * 1000,
                1,
            )
            if revision != 10:
                outcomes["session_code"] = "CARD_PROGRESS_CONFLICT"
                connection.rollback()
                return
            raise AssertionError("stale session unexpectedly matched its base revision")
        except Exception as exc:  # pragma: no cover - diagnostic path
            connection.rollback()
            errors.append(f"stale_session_writer: {type(exc).__name__}: {exc}")
        finally:
            connection.close()

    cutover_thread = threading.Thread(target=cutover_writer, daemon=True)
    cutover_thread.start()
    if not cutover_locked.wait(timeout=10):
        raise RuntimeError("cutover writer did not acquire its row locks")
    session_thread = threading.Thread(target=stale_session_writer, daemon=True)
    session_thread.start()
    time.sleep(0.2)
    release_cutover.set()
    cutover_thread.join(timeout=10)
    session_thread.join(timeout=10)
    if cutover_thread.is_alive() or session_thread.is_alive():
        raise RuntimeError("session-vs-cutover probe thread did not finish")
    if errors:
        raise RuntimeError("; ".join(errors))

    verify = _connect(config)
    try:
        with verify.cursor() as cursor:
            cursor.execute(
                f"SELECT subject_key, revision, interval_days FROM `{table}` "
                "ORDER BY subject_key ASC"
            )
            final_rows = cursor.fetchall()
    finally:
        verify.close()
    if outcomes.get("lock_order") != ["local", "source"]:
        raise AssertionError(f"cutover lock order was not deterministic: {outcomes}")
    if outcomes.get("session_code") != "CARD_PROGRESS_CONFLICT":
        raise AssertionError("stale session did not return CARD_PROGRESS_CONFLICT")
    if len(final_rows) != 1 or final_rows[0]["subject_key"] != "source":
        raise AssertionError(f"cutover did not leave one source subject: {final_rows}")
    if (int(final_rows[0]["revision"]), int(final_rows[0]["interval_days"])) != (11, 20):
        raise AssertionError(f"unexpected session-vs-cutover final row: {final_rows[0]}")
    return {
        **outcomes,
        "final_revision": int(final_rows[0]["revision"]),
        "final_interval_days": int(final_rows[0]["interval_days"]),
        "local_row_deleted": True,
    }


def main() -> int:
    config = _connection_config()
    table = f"{TABLE_PREFIX}{uuid.uuid4().hex[:12]}"
    if not re.fullmatch(r"p102_concurrency_probe_[0-9a-f]{12}", table):
        raise RuntimeError("refusing to use an invalid probe table name")

    admin = _connect(config)
    try:
        with admin.cursor() as cursor:
            cursor.execute(
                f"CREATE TABLE `{table}` ("
                "subject_key VARCHAR(32) PRIMARY KEY, "
                "revision BIGINT NOT NULL, "
                "applied_local_revision BIGINT NULL, "
                "snapshot_hash CHAR(64) NULL, "
                "interval_days INT NOT NULL"
                ") ENGINE=InnoDB"
            )
        admin.commit()
    finally:
        admin.close()

    try:
        result = {
            "mysql_version": None,
            "native_vs_snapshot": _run_native_vs_snapshot(config, table),
            "session_vs_cutover": _run_session_vs_cutover(config, table),
            "probe_table_cleaned": False,
        }
        version_connection = _connect(config)
        try:
            with version_connection.cursor() as cursor:
                cursor.execute("SELECT VERSION() AS version")
                result["mysql_version"] = cursor.fetchone()["version"]
        finally:
            version_connection.close()
    finally:
        cleanup = _connect(config)
        try:
            with cleanup.cursor() as cursor:
                cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
            cleanup.commit()
        finally:
            cleanup.close()

    verify_cleanup = _connect(config)
    try:
        with verify_cleanup.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) AS count FROM information_schema.tables "
                "WHERE table_schema=%s AND table_name=%s",
                (config["database"], table),
            )
            result["probe_table_cleaned"] = int(cursor.fetchone()["count"]) == 0
    finally:
        verify_cleanup.close()
    if not result["probe_table_cleaned"]:
        raise AssertionError("disposable probe table was not cleaned")

    print(json.dumps(result, ensure_ascii=True, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
