"""Check migration 49 on a disposable local MySQL database (P10-02).

Builds the current schema, seeds ``--subjects`` learner/Note subjects, then
runs migration 49's downgrade and upgrade and reports their duration, that
MySQL enforces every consolidated-row CHECK, that the storage profile accepts
``CONSOLIDATED_V1`` only after the upgrade, and that downgrade refuses
consolidated progress. Only a generated local database is created and dropped.

    python scripts/probe_p10_schema_mysql.py --subjects 40000
"""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import re
import secrets
import sys
import time

from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from app.services.study_progress_contract import subject_progress_checks  # noqa: E402
from models import db  # noqa: E402
from scripts.mysql_probe_db import (  # noqa: E402
    _connection_settings, _database_uri, _source_database_collation,
)

migration = importlib.import_module("migrations.versions.20261003_000049_consolidate_note_progress_row")
PROBE_NAME_PATTERN = re.compile(r"^flama_p10_schema_probe_[0-9]+_[a-f0-9]{8}$")
NOW = datetime(2026, 10, 3, 9, 0, 0)
FULL = {
    "algorithm_key": "'legacy-anki'", "algorithm_version": "'1.0.0'",
    "state_schema_version": "'anki-card-state.v1'", "storage_codec": "'flama-canonical-state-json.v1'",
    "state_payload": "JSON_OBJECT('type','new')", "state_payload_size": "15",
    "algorithm_state_hash": "REPEAT('a',32)", "semantic_state_hash": "REPEAT('s',32)",
    "authority_revision": "1", "projection_version": "'availability-anchor.v1'",
    "normalized_queue": "'new'", "is_suspended": "0", "is_buried": "0",
    "history_completeness_code": "'HISTORY_NATIVE_COMPLETE'", "current_provenance_code": "'NATIVE_SESSION'",
}


def _run(app, step):
    with app.app_context():
        with db.engine.begin() as connection:
            from alembic import op

            op._proxy = Operations(MigrationContext.configure(connection))
            started = time.perf_counter()
            getattr(migration, step)()
            return round(time.perf_counter() - started, 3)


def _refused(app, sql):
    with app.app_context():
        try:
            with db.engine.begin() as connection:
                connection.execute(sa.text(sql))
        except sa.exc.DBAPIError as exc:
            return str(exc.orig.args[0]) if getattr(exc, "orig", None) is not None else "error"
    return None


def run(*, subjects: int) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p10_schema_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("The schema probe requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"subjects": subjects}
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {_source_database_collation(admin)}")
            created = True
        app = create_app({
            "TESTING": True, "SQLALCHEMY_DATABASE_URI": _database_uri(settings, name),
            "STARTUP_RUN_MAINTENANCE": False, "STARTUP_RUN_DB_CREATE_ALL": False,
            "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
        })
        with app.app_context():
            db.create_all()
            from models.user import User

            db.session.add(User(id=1, username="probe", email="probe@example.test"))
            db.session.flush()
            db.session.execute(sa.text(
                "INSERT INTO study_authority_storage_profile (id, profile_code, epoch, created_at, updated_at) "
                "VALUES (1, 'CANONICAL_V1', 2, NOW(6), NOW(6))"))
            db.session.commit()
        report["downgrade_empty_s"] = _run(app, "downgrade")
        with app.app_context():
            batch = 5000
            for start in range(0, subjects, batch):
                values = ",".join(
                    f"(1, UNHEX(SHA2('{index}', 256)), 1, 1, 'MIRRORED_SINGLE', 1, NOW(6), NOW(6))"
                    for index in range(start, min(subjects, start + batch))
                )
                db.session.execute(sa.text(
                    "INSERT INTO study_progress_subjects (learner_user_id, logical_note_key, subject_generation, "
                    "mirror_revision, status_code, contributor_count, created_at, updated_at) VALUES " + values))
            db.session.commit()
        report["upgrade_s"] = _run(app, "upgrade")
        with app.app_context():
            names = {row["name"] for row in sa.inspect(db.engine).get_check_constraints("study_progress_subjects")}
            report["checks_present"] = sorted(set(subject_progress_checks()) & names)
            report["checks_missing"] = sorted(set(subject_progress_checks()) - names)
        columns = ", ".join(FULL)
        report["full_row_accepted"] = _refused(app, (
            "INSERT INTO study_progress_subjects (learner_user_id, logical_note_key, subject_generation, "
            f"mirror_revision, status_code, contributor_count, created_at, updated_at, {columns}) VALUES "
            f"(1, 'full', 1, 0, 'MIRRORED_SINGLE', 0, NOW(6), NOW(6), {', '.join(FULL.values())})")) is None
        refusals = {}
        for missing in FULL:
            if missing == "authority_revision":
                continue
            partial = {key: value for key, value in FULL.items() if key != missing}
            refusals[missing] = _refused(app, (
                "INSERT INTO study_progress_subjects (learner_user_id, logical_note_key, subject_generation, "
                f"mirror_revision, status_code, contributor_count, created_at, updated_at, {', '.join(partial)}) "
                f"VALUES (1, 'partial-{missing}', 1, 0, 'MIRRORED_SINGLE', 0, NOW(6), NOW(6), {', '.join(partial.values())})"))
        report["partial_rows_refused"] = all(code == "3819" for code in refusals.values())
        report["partial_refusal_codes"] = sorted(set(refusals.values()))
        report["consolidated_profile_accepted"] = _refused(
            app, "UPDATE study_authority_storage_profile SET profile_code = 'CONSOLIDATED_V1'") is None
        try:
            _run(app, "downgrade")
            report["downgrade_refused"] = False
        except RuntimeError as exc:
            report["downgrade_refused"] = str(exc)
        with app.app_context():
            db.session.execute(sa.text("UPDATE study_authority_storage_profile SET profile_code = 'CANONICAL_V1'"))
            db.session.execute(sa.text("DELETE FROM study_progress_subjects WHERE logical_note_key = 'full'"))
            db.session.commit()
        report["downgrade_s"] = _run(app, "downgrade")
        report["consolidated_profile_refused_after_downgrade"] = _refused(
            app, "UPDATE study_authority_storage_profile SET profile_code = 'CONSOLIDATED_V1'") == "3819"
        report["reupgrade_s"] = _run(app, "upgrade")
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_removed"] = True
        admin.close()
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subjects", type=int, default=40000)
    args = parser.parse_args()
    report = run(subjects=args.subjects)
    print(json.dumps(report, indent=1))
    ok = (not report.get("checks_missing") and report.get("full_row_accepted") and report.get("partial_rows_refused")
          and report.get("consolidated_profile_accepted") and report.get("downgrade_refused")
          and report.get("consolidated_profile_refused_after_downgrade"))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
