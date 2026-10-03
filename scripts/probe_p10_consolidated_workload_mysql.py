"""Replay a NOTE workload on a restored production dump after the P10 switch.

Restores the pre-P9-06 dump into a generated LOCAL database, applies
migration 49, runs the P9-06 switch (CANONICAL_V1), measures the learners'
readers and keeps their response bodies, plans and runs the one-way P10 switch
(CONSOLIDATED_V1), then measures the same readers again and compares the
bodies. Writes then go through the real HTTP/MCP entrypoints (the P9 workload:
v4 session open/commit on owned and installed decks, direct REST and MCP
answers, a new Note studied, a deck reset) with a SQL trace of every table the
consolidated profile retires. It reports the switch evidence, reader timings
and parity, retired-table statements (DELETE of ``card_progress`` is content
cleanup and reported separately), the read audit of each learner and row-level
integrity. The generated database is dropped in ``finally``; DB_NAME is never
touched.

    python scripts/probe_p10_consolidated_workload_mysql.py --backup output/p9-restore/pre-p906.sql.gz \
        --output output/p10/consolidated-workload.json
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import sys
import time
from unittest import mock

from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa
from sqlalchemy import event as sql_event

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.probe_p9_backup_restore_mysql import inspect_dump, restore_dump, validate_target  # noqa: E402
from scripts.probe_p9_canonical_workload_mysql import (  # noqa: E402
    _client, _learners, _measure_reads, _probe_app, _read_audit, _read_urls, _rows, _scalar,
    _study_deck, _workload,
)
from scripts.probe_phase4_shadow_schema_mysql import (  # noqa: E402
    _connection_settings, _database_uri, _source_database_collation,
)

RETIRED_TABLES = re.compile(
    r"\b(card_progress|study_progress_states|study_authority_subject_tokens|"
    r"study_progress_contributors|study_progress_availability|study_progress_lineage_refs)\b",
    re.IGNORECASE,
)
PROFILES = frozenset({"PROJECTION_V1", "CANONICAL_V1", "CONSOLIDATED_V1"})
# Fields that legitimately differ between two reads of the same data. A deck
# move alias hashes a timestamped signed move token, so it changes per request.
_VOLATILE = re.compile(r"(_at|_at_utc|generated|elapsed|duration|token|session_id|request_id|move_alias)$")
INTEGRITY = {
    "stateful_rows_without_availability": (
        "SELECT COUNT(*) FROM study_progress_subjects WHERE semantic_state_hash IS NOT NULL "
        "AND (normalized_queue IS NULL OR projection_version IS NULL)"),
    "states_without_consolidated_row": (
        "SELECT COUNT(*) FROM study_progress_states s JOIN study_progress_subjects p ON p.id = s.subject_id "
        "WHERE p.semantic_state_hash IS NULL AND p.status_code LIKE 'MIRRORED_%'"),
    "receipt_orphans": (
        "SELECT COUNT(*) FROM study_authority_command_receipts r LEFT JOIN review_events e "
        "ON e.id=r.review_event_id LEFT JOIN study_progress_history_facts h ON h.id=r.history_fact_id "
        "WHERE (r.review_event_id IS NOT NULL AND e.id IS NULL) OR "
        "(r.history_fact_id IS NOT NULL AND h.id IS NULL)"),
}


class _Trace:
    """Statements per workload step, and those naming a retired table."""

    def __init__(self, engine):
        self.engine = engine
        self.step = "setup"
        self.statements = Counter()
        self.card_progress = Counter()  # read by the shared P9 workload helpers
        self.retired = Counter()

    def __enter__(self):
        sql_event.listen(self.engine, "before_cursor_execute", self._on)
        return self

    def __exit__(self, *_exc):
        sql_event.remove(self.engine, "before_cursor_execute", self._on)

    def _on(self, _conn, _cursor, statement, *_args):
        self.statements[self.step] += 1
        match = RETIRED_TABLES.search(statement)
        if match:
            verb = statement.split()[0].upper()
            self.retired[(self.step, f"{verb} {match.group(1).lower()}")] += 1


def _stable(value):
    """Response body without per-request volatile fields, for parity."""

    if isinstance(value, dict):
        return {key: _stable(item) for key, item in sorted(value.items()) if not _VOLATILE.search(str(key))}
    if isinstance(value, list):
        return [_stable(item) for item in value]
    return value


def _bodies(app, learners: dict[str, int], decks: dict[str, int]) -> dict:
    bodies = {}
    for role, user_id in learners.items():
        client = _client(app, user_id)
        for label, url in _read_urls(decks[role]):
            response = client.get(url)
            bodies[f"{role}.{label}"] = (response.status_code, _stable(response.get_json()))
    return bodies


def _differences(left, right, path="", found=None, limit=20):
    found = [] if found is None else found
    if len(found) >= limit:
        return found
    if isinstance(left, dict) and isinstance(right, dict):
        for key in sorted(set(left) | set(right)):
            _differences(left.get(key), right.get(key), f"{path}.{key}", found, limit)
    elif isinstance(left, list) and isinstance(right, list) and len(left) == len(right):
        for index, (a, b) in enumerate(zip(left, right)):
            _differences(a, b, f"{path}[{index}]", found, limit)
    elif left != right:
        found.append({"path": path, "canonical": str(left)[:120], "consolidated": str(right)[:120]})
    return found


def _upgrade_to_49(app) -> float:
    from alembic import op
    from alembic.migration import MigrationContext
    from alembic.operations import Operations
    from models import db

    migration = importlib.import_module("migrations.versions.20261003_000049_consolidate_note_progress_row")
    with app.app_context():
        with db.engine.begin() as connection:
            op._proxy = Operations(MigrationContext.configure(connection))
            started = time.perf_counter()
            migration.upgrade()
            elapsed = time.perf_counter() - started
            connection.execute(sa.text("UPDATE alembic_version SET version_num = '20261003_000049'"))
        op._proxy = None
    return round(elapsed, 3)


def run(backup: Path, *, mysql_binary: str) -> dict:
    load_dotenv(ROOT / ".env")
    settings = _connection_settings()
    target = f"flama_p9_restore_{os.getpid()}_{secrets.token_hex(4)}"
    validate_target(settings, target)
    executable = shutil.which(mysql_binary)
    if not executable:
        raise ValueError("mysql client executable is required")
    report: dict = {"schema_version": "p10-consolidated-workload.v1", **inspect_dump(backup),
                    "observed_at_utc": datetime.utcnow().replace(microsecond=0).isoformat() + "Z",
                    "configured_database_modified": False}
    admin = pymysql.connect(**settings)
    created = False
    app = None
    # The release under test may not list CONSOLIDATED_V1 yet; the probe does.
    supported = mock.patch("app.repositories.study_authority_repository.SUPPORTED_STORAGE_PROFILES", PROFILES)
    supported.start()
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{target}` CHARACTER SET utf8mb4 "
                           f"COLLATE {_source_database_collation(admin)}")
            created = True
        report["restore_seconds"] = restore_dump(settings, target, backup, executable)
        app = _probe_app(_database_uri(settings, target))
        report["migration_49_seconds"] = _upgrade_to_49(app)
        from app.services.study_consolidated_switch_service import (
            apply_consolidated_switch,
            plan_consolidated_switch,
        )
        from app.services.study_storage_profile_service import apply_storage_profile_switch
        from models import db

        from app.repositories.study_authority_repository import read_study_storage_profile

        with app.app_context():
            # A dump taken after P9-06 is already CANONICAL_V1.
            if read_study_storage_profile(db.session) == "PROJECTION_V1":
                report["p9_switch"] = apply_storage_profile_switch(db.session, now_utc=datetime.utcnow())
                db.session.commit()
            else:
                report["p9_switch"] = {"skipped": read_study_storage_profile(db.session)}
                db.session.rollback()
        learners = _learners(app)
        decks = {}
        for role, user_id in learners.items():
            deck_id, _snapshot = _study_deck(app, _client(app, user_id), user_id)
            decks[role] = deck_id
        report.update({"learners": learners, "decks": decks})
        report["reads_canonical_v1"] = _measure_reads(app, learners, decks)
        canonical_bodies = _bodies(app, learners, decks)
        with app.app_context():
            started = time.perf_counter()
            report["p10_plan"] = plan_consolidated_switch(db.session)
            report["p10_plan"]["seconds"] = round(time.perf_counter() - started, 3)
            started = time.perf_counter()
            report["p10_switch"] = apply_consolidated_switch(db.session, now_utc=datetime.utcnow())
            db.session.commit()
            report["p10_switch"]["seconds"] = round(time.perf_counter() - started, 3)
        report["reads_consolidated_v1"] = _measure_reads(app, learners, decks)
        consolidated_bodies = _bodies(app, learners, decks)
        report["reader_parity"] = {
            name: {
                "status": [canonical_bodies[name][0], consolidated_bodies[name][0]],
                "differences": _differences(canonical_bodies[name][1], consolidated_bodies[name][1]),
            }
            for name in canonical_bodies
        }
        with app.app_context():
            engine = db.engine
        with _Trace(engine) as trace:
            _workload(app, trace, learners, decks, report)
        report["statements_by_step"] = dict(trace.statements)
        report["retired_table_statements"] = {f"{step}:{operation}": count
                                              for (step, operation), count in sorted(trace.retired.items())}
        offending = sum(count for (_step, operation), count in trace.retired.items()
                        if operation != "DELETE card_progress")
        report["integrity"] = {name: int(_scalar(app, sql)) for name, sql in INTEGRITY.items()}
        report["read_audit"] = {role: _read_audit(app, user_id) for role, user_id in learners.items()}
        report["status"] = "PASS" if (
            offending == 0
            and not report["p10_plan"]["blockers"]
            and not any(report["integrity"].values())
            and all(not row["differences"] and row["status"][0] == row["status"][1]
                    for row in report["reader_parity"].values())
            and all(audit.get("status") == "PASS" and audit.get("storage_profile") == "CONSOLIDATED_V1"
                    for audit in report["read_audit"].values())
            and not any("error" in str(step.get("outcome")) for step in report["workload"].values())
        ) else "FAIL"
        report["retired_table_statements_outside_cleanup"] = offending
        return report
    finally:
        supported.stop()
        if app is not None:
            from models import db

            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            validate_target(settings, target)
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{target}`")
            report["probe_database_removed"] = True
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--backup", type=Path, required=True)
    parser.add_argument("--mysql-binary", default="mysql")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args.backup, mysql_binary=args.mysql_binary)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=1, default=str), encoding="utf-8")
    print(json.dumps({key: report.get(key) for key in (
        "status", "retired_table_statements_outside_cleanup", "integrity", "p10_switch")}, default=str))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
