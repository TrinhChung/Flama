"""Check migration 50 on a disposable local MySQL database (P10-09).

Builds the current schema plus the five retired tables (frozen definitions)
and the production ``study_progress_history_facts.contributor_id`` foreign key
with its index, seeds ``--subjects`` subjects with a token, a contributor and
a history fact each, then reports that upgrade refuses a non-consolidated
profile, drops the tables, the foreign key and its index without touching any
history fact, that downgrade refuses until the tables are restored, and that a
restore + downgrade + upgrade round trip works. Only a generated local
database is created and dropped.

    python scripts/probe_p10_drop_mysql.py --subjects 40000
"""

from __future__ import annotations

import argparse
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
from migrations.retired_note_progress_tables import RETIRED_METADATA  # noqa: E402
from models import db  # noqa: E402
from scripts.mysql_probe_db import (  # noqa: E402
    _connection_settings, _database_uri, _source_database_collation,
)

migration = importlib.import_module("migrations.versions.20261003_000050_drop_retired_note_progress_tables")
PROBE_NAME_PATTERN = re.compile(r"^flama_p10_drop_probe_[0-9]+_[a-f0-9]{8}$")
FACTS = migration.FACTS
_BATCH = 2000


def _run(app, step):
    with app.app_context():
        with db.engine.begin() as connection:
            from alembic import op

            op._proxy = Operations(MigrationContext.configure(connection))
            started = time.perf_counter()
            try:
                getattr(migration, step)()
            except RuntimeError as exc:
                return {"refused": str(exc)}
            return {"seconds": round(time.perf_counter() - started, 3)}


def _create_retired(app, *, with_fact_fk: bool):
    with app.app_context():
        RETIRED_METADATA.create_all(bind=db.engine, tables=[
            RETIRED_METADATA.tables[name] for name in reversed(migration.TABLES)])
        if with_fact_fk:
            # As on production: the FK with its own index on (contributor_id).
            db.session.execute(sa.text(
                f"ALTER TABLE {FACTS} ADD KEY contributor_id (contributor_id), "
                "ADD CONSTRAINT fk_probe_history_contributor FOREIGN KEY (contributor_id) "
                "REFERENCES study_progress_contributors (id) ON DELETE SET NULL"))
            db.session.commit()


def _seed_contributors(app, subjects: int):
    with app.app_context():
        for start in range(1, subjects + 1, _BATCH):
            ids = range(start, min(subjects, start + _BATCH - 1) + 1)
            db.session.execute(sa.text(
                "INSERT INTO study_progress_contributors (id, subject_id, subject_generation, source_progress_id, "
                "card_progress_revision, raw_schema_version, storage_codec, raw_payload, raw_payload_size, "
                "raw_progress_hash, logical_card_key, pointer_status, history_completeness_code, "
                "current_provenance_code, lineage_vector_hash, contributor_status, created_at, updated_at) VALUES "
                + ",".join(
                    f"({i}, {i}, 1, {i}, 0, 'card-progress-raw.v1', 'canonical-json-v1', JSON_OBJECT('id', {i}), "
                    f"9, REPEAT('r', 32), 'card-{i}', 'ABSENT', 'HISTORY_NATIVE_COMPLETE', 'UNKNOWN_LEGACY', "
                    "REPEAT('l', 32), 'ACTIVE', NOW(6), NOW(6))"
                    for i in ids)))
            db.session.execute(sa.text(
                "INSERT INTO study_authority_subject_tokens (subject_id, subject_generation, authority_revision, "
                "created_at, updated_at) VALUES "
                + ",".join(f"({i}, 1, 1, NOW(6), NOW(6))" for i in ids)))
        db.session.commit()


def _fact_vector(app):
    with app.app_context():
        return [int(value or 0) for value in db.session.execute(sa.text(
            f"SELECT COUNT(*), COALESCE(SUM(contributor_id), 0), COUNT(contributor_id) FROM {FACTS}")).one()]


def _fact_constraints(app):
    with app.app_context():
        inspector = sa.inspect(db.engine)
        return {
            "fks": sorted(fk["name"] for fk in inspector.get_foreign_keys(FACTS)
                          if fk["referred_table"] == migration.CONTRIBUTORS),
            "indexes": sorted(index["name"] for index in inspector.get_indexes(FACTS)
                              if index["column_names"] == ["contributor_id"]),
            "retired_tables": sorted(set(migration.TABLES) & set(inspector.get_table_names())),
        }


def run(*, subjects: int) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p10_drop_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("The drop probe requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    report: dict = {"subjects": subjects}
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 COLLATE {_source_database_collation(admin)}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
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
            for start in range(1, subjects + 1, _BATCH):
                ids = range(start, min(subjects, start + _BATCH - 1) + 1)
                db.session.execute(sa.text(
                    "INSERT INTO study_progress_subjects (id, learner_user_id, logical_note_key, subject_generation, "
                    "mirror_revision, status_code, contributor_count, created_at, updated_at) VALUES "
                    + ",".join(f"({i}, 1, UNHEX(SHA2('{i}', 256)), 1, 1, 'MIRRORED_SINGLE', 1, NOW(6), NOW(6))"
                               for i in ids)))
            db.session.execute(sa.text(
                "INSERT INTO study_authority_storage_profile (id, profile_code, epoch, created_at, updated_at) "
                "VALUES (1, 'CANONICAL_V1', 2, NOW(6), NOW(6))"))
            db.session.commit()
        _create_retired(app, with_fact_fk=True)
        _seed_contributors(app, subjects)
        with app.app_context():
            for start in range(1, subjects + 1, _BATCH):
                ids = range(start, min(subjects, start + _BATCH - 1) + 1)
                db.session.execute(sa.text(
                    f"INSERT INTO {FACTS} (learner_user_id, subject_id, contributor_id, logical_card_key, "
                    "fact_identity_hash, history_schema_version, storage_codec, occurred_at, ingested_at, "
                    "provenance_code, history_completeness_code, fact_payload, fact_payload_size, fact_payload_hash, "
                    "created_at) VALUES " + ",".join(
                        f"(1, {i}, {i}, 'card-{i}', UNHEX(SHA2('fact-{i}', 256)), 'v1', 'c', NOW(6), NOW(6), "
                        "'NATIVE_DIRECT', 'HISTORY_NATIVE_COMPLETE', JSON_OBJECT(), 2, REPEAT('h', 32), NOW(6))"
                        for i in ids)))
            db.session.commit()
        before = _fact_vector(app)
        report["before"] = {"facts": before, **_fact_constraints(app)}
        report["canonical_profile"] = _run(app, "upgrade")
        with app.app_context():
            db.session.execute(sa.text(
                "UPDATE study_authority_storage_profile SET profile_code = 'CONSOLIDATED_V1', epoch = 3 WHERE id = 1"))
            db.session.commit()
        report["upgrade"] = _run(app, "upgrade")
        report["after"] = {"facts": _fact_vector(app), **_fact_constraints(app)}
        report["upgrade_again"] = _run(app, "upgrade")
        report["downgrade_without_restore"] = _run(app, "downgrade")
        # Restoring the dump recreates the tables with their rows.
        _create_retired(app, with_fact_fk=False)
        _seed_contributors(app, subjects)
        report["downgrade_after_restore"] = _run(app, "downgrade")
        report["restored"] = _fact_constraints(app)
        report["reupgrade"] = _run(app, "upgrade")
        report["final"] = {"facts": _fact_vector(app), **_fact_constraints(app)}
        problems = []
        if "refused" not in report["canonical_profile"]:
            problems.append("upgrade did not refuse CANONICAL_V1")
        if report["before"]["fks"] == [] or report["before"]["indexes"] == []:
            problems.append("fixture lacks the production foreign key or its index")
        for step in ("after", "final"):
            if report[step]["facts"] != before:
                problems.append(f"{step}: history facts changed")
            if report[step]["fks"] or report[step]["indexes"] or report[step]["retired_tables"]:
                problems.append(f"{step}: retired schema left behind")
        if "seconds" not in report["upgrade"] or "seconds" not in report["upgrade_again"]:
            problems.append("upgrade failed")
        if "refused" not in report["downgrade_without_restore"]:
            problems.append("downgrade did not require the restored tables")
        if not report["restored"]["fks"] or not report["restored"]["indexes"]:
            problems.append("downgrade did not restore the foreign key and its index")
        report["problems"] = problems
        report["status"] = "FAIL" if problems else "PASS"
        return report
    finally:
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_dropped"] = True
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subjects", type=int, default=2000)
    args = parser.parse_args()
    report = run(subjects=args.subjects)
    print(json.dumps(report, indent=1, sort_keys=True, default=str))
    return 0 if report.get("status") == "PASS" else 1


if __name__ == "__main__":
    sys.exit(main())
