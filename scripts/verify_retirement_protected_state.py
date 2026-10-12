"""Snapshot protected retirement data without booting the app or writing SQL.

Run before and after contraction with writers stopped. Outputs contain only
counts, checksums and schema facts; full archives remain separate and private.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys

import sqlalchemy as sa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.archive_retired_tables import _engine
from migrations.progress_retirement_gate import snapshot_sha256

PROTECTED_TABLES = (
    "study_progress_subjects", "study_authority_enrollments",
    "study_authority_storage_profile", "review_events",
    "study_authority_command_receipts", "study_progress_history_facts",
    "study_progress_lifecycle_events", "study_sessions", "study_session_cards",
    "study_session_commits", "study_session_batches", "study_session_authority_pins",
    "connect_source_note_refs", "connect_source_card_refs", "template_versions",
    "template_releases", "deck_release_template_pins", "deck_releases",
    "study_applications", "notes",
)
RETIRED_TABLES = (
    "cards", "card_progress", "vocabulary_column_preferences",
    "study_progress_backfill_runs", "study_progress_backfill_checkpoints",
    "study_progress_backfill_dispositions",
)


def snapshot(connection):
    inspector = sa.inspect(connection)
    tables = set(inspector.get_table_names())
    missing = set(PROTECTED_TABLES) - tables
    if missing:
        raise RuntimeError(f"Protected tables are missing: {sorted(missing)}")
    protected = {}
    for name in PROTECTED_TABLES:
        digest, count = snapshot_sha256(connection, name)
        protected[name] = {"rows": count, "sha256": digest}
    result = {
        "schema_version": "retirement-protected-state.v1",
        "captured_at_utc": datetime.now(timezone.utc).isoformat(),
        "database": connection.engine.url.database,
        "revision": connection.exec_driver_sql("SELECT version_num FROM alembic_version").scalar_one(),
        "protected": protected,
        "retired_tables_present": sorted(set(RETIRED_TABLES) & tables),
        "template_origin_present": any(column["name"] == "note_type_id"
                                       for column in inspector.get_columns("templates")),
        "alias_rows": None,
    }
    if "card_presentation_aliases" in tables:
        result["alias_rows"] = connection.exec_driver_sql("SELECT COUNT(*) FROM card_presentation_aliases").scalar_one()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--mysql-socket")
    parser.add_argument("--database")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--expected-revision")
    parser.add_argument("--require-retired", action="store_true")
    args = parser.parse_args()
    if args.output.exists():
        raise RuntimeError("Refusing to overwrite protected-state evidence")
    engine = _engine(args)
    try:
        with engine.connect() as connection:
            if engine.dialect.name != "mysql":
                raise RuntimeError("Deployment snapshots require MySQL")
            connection.exec_driver_sql("SET SESSION TRANSACTION ISOLATION LEVEL REPEATABLE READ")
            connection.exec_driver_sql("SET SESSION TRANSACTION READ ONLY")
            connection.commit()
            connection.exec_driver_sql("START TRANSACTION WITH CONSISTENT SNAPSHOT, READ ONLY")
            result = snapshot(connection)
            connection.rollback()
        result["failures"] = []
        if args.baseline:
            baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
            if baseline.get("schema_version") != result["schema_version"]:
                raise RuntimeError("Unsupported baseline format")
            for name in PROTECTED_TABLES:
                if baseline["protected"].get(name) != result["protected"][name]:
                    result["failures"].append(f"Protected data changed: {name}")
        if args.expected_revision and result["revision"] != args.expected_revision:
            result["failures"].append("Unexpected migration revision")
        if args.require_retired and (result["retired_tables_present"] or result["template_origin_present"]):
            result["failures"].append("Retired schema is still present")
        result["status"] = "PASS" if not result["failures"] else "FAIL"
        args.output.parent.mkdir(parents=True, exist_ok=True)
        with args.output.open("x", encoding="utf-8") as target:
            json.dump(result, target, indent=2)
            target.write("\n")
        print(json.dumps({"status": result["status"], "revision": result["revision"],
                          "protected_tables": len(PROTECTED_TABLES), "failures": result["failures"]}))
        return 0 if result["status"] == "PASS" else 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    raise SystemExit(main())
