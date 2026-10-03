"""Restore a single-schema dump into a generated LOCAL database, then remove it.

Never restores over DB_NAME. A successful rehearsal is not cutover/PITR
approval: record a fresh dump and binlog watermark during the P9-06 freeze.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import sys
import tempfile
import time

import pymysql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts.mysql_probe_db import _connection_settings, _source_database_collation  # noqa: E402

TARGET = re.compile(r"^flama_p9_restore_[0-9]+_[a-f0-9]{8}$")
DATABASE_DIRECTIVE = re.compile(rb"^\s*(?:/\*![0-9]+\s*)?(?:CREATE\s+DATABASE|DROP\s+DATABASE|USE\s+)", re.I)


def validate_target(settings, target):
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not TARGET.fullmatch(target):
        raise ValueError("Restore rehearsal requires a generated local database")
    if target == os.getenv("DB_NAME"):
        raise ValueError("Configured database is never a restore target")


def inspect_dump(path):
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    completed, watermark = False, None
    with gzip.open(path, "rb") as source:
        for line in source:
            if DATABASE_DIRECTIVE.match(line):
                raise ValueError("Restore refuses database-switching directives; supply a single-schema dump")
            if line.startswith(b"-- Dump completed"):
                completed = True
            if line.startswith((b"-- CHANGE MASTER TO", b"-- CHANGE REPLICATION SOURCE TO")):
                watermark = line.decode("ascii").strip()
    if not completed:
        raise ValueError("Dump has no completion marker")
    return {"backup_sha256": digest.hexdigest(), "backup_bytes": path.stat().st_size,
            "binlog_watermark": watermark}


def _option(value):
    return '"' + str(value).replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r") + '"'


def restore_dump(settings, target, backup: Path, executable: str) -> float:
    """Pipe ``backup`` into the already created ``target``; return seconds."""

    validate_target(settings, target)
    with tempfile.TemporaryDirectory(prefix="flama-p9-client-") as directory:
        defaults = Path(directory) / "client.cnf"
        defaults.write_text("[client]\n" + "\n".join(f"{key}={_option(settings[key])}"
                            for key in ("host", "port", "user", "password")) + "\n", encoding="utf-8")
        if os.name != "nt":
            defaults.chmod(0o600)
        started = time.monotonic()
        with tempfile.TemporaryFile() as errors:
            process = subprocess.Popen([executable, f"--defaults-file={defaults}", "--binary-mode",
                                        "--default-character-set=utf8mb4", f"--database={target}"],
                                       stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=errors)
            try:
                with gzip.open(backup, "rb") as source:
                    shutil.copyfileobj(source, process.stdin, length=1024 * 1024)
                process.stdin.close()
                code = process.wait()
                if code:
                    raise RuntimeError(f"mysql restore failed with exit {code}; no source database was modified")
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
        return round(time.monotonic() - started, 3)


def run_probe(backup: Path, *, mysql_binary: str, env_file: Path | None = None):
    load_dotenv(env_file or ROOT / ".env")
    settings = _connection_settings()
    target = f"flama_p9_restore_{os.getpid()}_{secrets.token_hex(4)}"
    validate_target(settings, target)
    manifest = inspect_dump(backup)
    executable = shutil.which(mysql_binary)
    if not executable:
        raise ValueError("mysql client executable is required")
    report = {"schema_version": "p9-backup-restore-rehearsal.v1", **manifest,
              "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "configured_database_modified": False, "pitr_proven": False, "cutover_approved": False}
    connection = pymysql.connect(**settings)
    created = False
    try:
        collation = _source_database_collation(connection)
        with connection.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{target}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
        report["restore_seconds"] = restore_dump(settings, target, backup, executable)
        connection.select_db(target)
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
            counts = {}
            for table in tables:
                if not re.fullmatch(r"[a-zA-Z0-9_]+", table):
                    raise ValueError("Unexpected table identifier in restored schema")
                cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
                counts[table] = int(cursor.fetchone()[0])
            report["row_counts"] = counts
            cursor.execute("SELECT version_num FROM alembic_version")
            report["alembic_revisions"] = [row[0] for row in cursor.fetchall()]
            cursor.execute("SELECT profile_code, epoch FROM study_authority_storage_profile")
            report["storage_profiles"] = [list(row) for row in cursor.fetchall()]
            # CONSOLIDATED_V1: a row holds its state and the state's hash together.
            cursor.execute("SELECT COUNT(*) FROM study_progress_subjects WHERE (state_payload IS NULL) <> (semantic_state_hash IS NULL)")
            report["row_state_mismatches"] = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM study_progress_history_facts h LEFT JOIN study_progress_subjects p ON p.id=h.subject_id WHERE p.id IS NULL")
            report["history_orphans"] = int(cursor.fetchone()[0])
            cursor.execute("SELECT COUNT(*) FROM study_authority_command_receipts r LEFT JOIN review_events e ON e.id=r.review_event_id LEFT JOIN study_progress_history_facts h ON h.id=r.history_fact_id WHERE (r.review_event_id IS NOT NULL AND e.id IS NULL) OR (r.history_fact_id IS NOT NULL AND h.id IS NULL)")
            report["receipt_orphans"] = int(cursor.fetchone()[0])
        report["status"] = "PASS" if not any(report[key] for key in
                                             ("row_state_mismatches", "history_orphans", "receipt_orphans")) else "FAIL"
        return report
    finally:
        if created:
            validate_target(settings, target)
            with connection.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{target}`")
            report["probe_database_removed"] = True
        connection.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--mysql-binary", default="mysql")
    parser.add_argument("--env-file", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = run_probe(args.backup, mysql_binary=args.mysql_binary, env_file=args.env_file)
    args.output.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps({key: result[key] for key in ("status", "restore_seconds", "configured_database_modified", "probe_database_removed")}))
    return 0 if result["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
