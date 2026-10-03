"""Measure migration 47 at production scale on MySQL and check its guards.

The deploy runs ``flask db upgrade`` while the previous release still serves
requests. This bench builds a disposable head-46 database (current metadata,
then migration 47's own downgrade), seeds contributors like production
(one per subject, ~670-byte raw evidence), keeps an "old release" writer
updating and inserting contributors during the upgrade, and reports the
upgrade time, the writer's worst statement latency, and whether any seeded
evidence changed. It then checks the new CHECK/unique constraints, that the
downgrade refuses while CANONICAL evidence exists, and a clean
downgrade/upgrade round trip. Only a generated local database is created and
dropped.

    python scripts/bench_p9_profile_migration_mysql.py --contributors 40671
"""

from __future__ import annotations

import argparse
from datetime import datetime
import importlib
import json
import os
from pathlib import Path
import random
import re
import secrets
import sys
import threading
import time

from alembic import op
from alembic.migration import MigrationContext
from alembic.operations import Operations
from dotenv import load_dotenv
import pymysql
import sqlalchemy as sa

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app  # noqa: E402
from app.services.study_progress_contract import CONTRIBUTOR_RAW_EVIDENCE_COLUMNS  # noqa: E402
from models import db  # noqa: E402
from scripts.mysql_probe_db import (  # noqa: E402
    _connection_settings, _database_uri, _source_database_collation,
)

migration = importlib.import_module("migrations.versions.20261001_000047_add_study_storage_profile")
PROBE_NAME_PATTERN = re.compile(r"^flama_p9_profile_probe_[0-9]+_[a-f0-9]{8}$")
LEARNERS = 20
_CHUNK = 2000
NOW = datetime(2026, 10, 1, 12, 0, 0)
FINGERPRINT = (
    "SELECT COUNT(*), SUM(CRC32(raw_payload)), SUM(CRC32(raw_progress_hash)), "
    "SUM(source_progress_id), SUM(card_progress_revision), SUM(CRC32(logical_card_key)) "
    "FROM study_progress_contributors WHERE id <= :seeded"
)
CONTRIBUTOR_INSERT = (
    "INSERT INTO study_progress_contributors (subject_id, subject_generation, source_progress_id, "
    "logical_card_key, card_progress_revision, raw_schema_version, storage_codec, raw_payload, "
    "raw_payload_size, raw_progress_hash, pointer_status, history_completeness_code, "
    "current_provenance_code, lineage_vector_hash, contributor_status, created_at, updated_at) "
    "VALUES (%(subject)s, 1, %(source)s, %(key)s, 3, 'card-progress-raw.v1', 'canonical-json-v1', "
    "%(payload)s, 670, %(hash)s, 'VALID', 'HISTORY_NATIVE_COMPLETE', 'NATIVE_SESSION', %(lineage)s, "
    "'ACTIVE', %(now)s, %(now)s)"
)


def _probe_app(uri: str):
    url = sa.engine.make_url(uri)
    if (
        url.get_backend_name() != "mysql"
        or url.host not in {"localhost", "127.0.0.1", "::1"}
        or not PROBE_NAME_PATTERN.fullmatch(url.database or "")
    ):
        raise ValueError("P9 profile bench requires a generated local MySQL database.")
    return create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": uri, "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False, "STARTUP_CHECK_DB_CONNECTIVITY": False, "REDIS_URL": "",
    })


def _exec(sql: str, **params):
    return db.session.execute(sa.text(sql), params)


def _run(step) -> float:
    started = time.perf_counter()
    with db.engine.begin() as connection:
        op._proxy = Operations(MigrationContext.configure(connection))
        try:
            step()
        finally:
            op._proxy = None
    return round(time.perf_counter() - started, 2)


def _payload(index: int) -> str:
    return json.dumps({"id": index, "pad": "p" * 640})


def _contributor_row(subject: int, source: int, index: int) -> dict:
    return {
        "subject": subject, "source": source, "key": f"card-{index}".encode(),
        "payload": _payload(index), "hash": secrets.token_bytes(32), "lineage": b"\x44" * 32,
        "now": NOW,
    }


def _seed(connection, contributors: int) -> int:
    with connection.cursor() as cursor:
        for start in range(0, contributors, _CHUNK):
            indexes = range(start + 1, min(contributors, start + _CHUNK) + 1)
            cursor.executemany(
                "INSERT INTO study_progress_subjects (id, learner_user_id, logical_note_key, "
                "subject_generation, mirror_revision, status_code, contributor_count, created_at, "
                "updated_at) VALUES (%s, %s, %s, 1, 1, 'NO_CURRENT_PROGRESS', 1, %s, %s)",
                [(index, index % LEARNERS + 1, f"note-{index}".encode(), NOW, NOW) for index in indexes],
            )
            cursor.executemany(
                CONTRIBUTOR_INSERT, [_contributor_row(index, index, index) for index in indexes]
            )
    return contributors


class OldReleaseWriter(threading.Thread):
    """Updates and inserts contributors the way the serving release does."""

    def __init__(self, settings: dict, database: str, seeded: int) -> None:
        super().__init__(daemon=True)
        self.settings, self.database, self.seeded = settings, database, seeded
        self.stop_event = threading.Event()
        self.latencies: list[float] = []
        self.errors: list[str] = []
        self.inserted = 0

    def run(self) -> None:
        connection = pymysql.connect(**{**self.settings, "database": self.database})
        rng = random.Random(47)
        next_id = self.seeded + 1_000_000
        try:
            with connection.cursor() as cursor:
                while not self.stop_event.is_set():
                    started = time.perf_counter()
                    try:
                        if rng.random() < 0.2:
                            cursor.execute(
                                "INSERT INTO study_progress_subjects (id, learner_user_id, "
                                "logical_note_key, subject_generation, mirror_revision, status_code, "
                                "contributor_count, created_at, updated_at) VALUES "
                                "(%s, 1, %s, 1, 1, 'NO_CURRENT_PROGRESS', 1, %s, %s)",
                                (next_id, f"new-{next_id}".encode(), NOW, NOW),
                            )
                            cursor.execute(CONTRIBUTOR_INSERT, _contributor_row(next_id, next_id, next_id))
                            next_id += 1
                            self.inserted += 1
                        else:
                            cursor.execute(
                                "UPDATE study_progress_contributors SET updated_at = %s WHERE id = %s",
                                (datetime.utcnow(), rng.randint(1, self.seeded)),
                            )
                    except pymysql.MySQLError as exc:
                        self.errors.append(f"{type(exc).__name__}: {exc}")
                    self.latencies.append(time.perf_counter() - started)
                    time.sleep(0.005)
        finally:
            connection.close()

    def finish(self) -> dict:
        self.stop_event.set()
        self.join(timeout=30)
        ordered = sorted(self.latencies)
        return {
            "statements": len(ordered),
            "inserted_contributors": self.inserted,
            "max_latency_ms": round(ordered[-1] * 1000, 1) if ordered else None,
            "p99_latency_ms": round(ordered[int(len(ordered) * 0.99)] * 1000, 1) if ordered else None,
            "error_count": len(self.errors),
            "errors": self.errors[:3],
        }


def _raw_not_null() -> bool:
    columns = {column["name"]: column for column in sa.inspect(db.engine).get_columns(migration.CONTRIBUTORS)}
    return all(not columns[name]["nullable"] for name in CONTRIBUTOR_RAW_EVIDENCE_COLUMNS)


def _rejected(sql: str, **params) -> str | None:
    try:
        _exec(sql, **params)
        db.session.commit()
    except sa.exc.DBAPIError as exc:
        db.session.rollback()
        return str(exc.orig.args[0]) if exc.orig is not None and exc.orig.args else type(exc).__name__
    return None


def _constraint_checks() -> dict:
    subject = _exec("SELECT MAX(id) FROM study_progress_subjects").scalar_one() + 1
    _exec(
        "INSERT INTO study_progress_subjects (id, learner_user_id, logical_note_key, subject_generation, "
        "mirror_revision, status_code, contributor_count, created_at, updated_at) VALUES "
        "(:id, 1, :key, 1, 1, 'NO_CURRENT_PROGRESS', 1, :now, :now)",
        id=subject, key=b"check-note", now=NOW,
    )
    db.session.commit()
    canonical = (
        "INSERT INTO study_progress_contributors (subject_id, subject_generation, evidence_kind, "
        "logical_card_key, pointer_status, history_completeness_code, current_provenance_code, "
        "lineage_vector_hash, contributor_status, created_at, updated_at) VALUES "
        "(:subject, 1, :kind, :key, 'ABSENT', 'HISTORY_NATIVE_COMPLETE', 'NATIVE_SESSION', :lineage, "
        "'ACTIVE', :now, :now)"
    )
    params = {"subject": subject, "lineage": b"\x44" * 32, "now": NOW}
    results = {
        "legacy_without_raw_rejected": _rejected(canonical, kind="LEGACY_PROJECTION", key=b"c-1", **params),
        "canonical_accepted": _rejected(canonical, kind="CANONICAL", key=b"c-1", **params) is None,
        "duplicate_generation_card_rejected": _rejected(canonical, kind="CANONICAL", key=b"c-1", **params),
        "unknown_kind_rejected": _rejected(canonical, kind="OTHER", key=b"c-2", **params),
        "canonical_with_raw_rejected": _rejected(
            "UPDATE study_progress_contributors SET evidence_kind = 'CANONICAL' WHERE id = 1"
        ),
    }
    try:
        _run(migration.downgrade)
        results["downgrade_refused_with_canonical"] = False
    except RuntimeError as exc:
        results["downgrade_refused_with_canonical"] = "no CardProgress evidence" in str(exc)
    db.session.remove()
    _exec("DELETE FROM study_progress_contributors WHERE subject_id = :subject", subject=subject)
    _exec("DELETE FROM study_progress_subjects WHERE id = :subject", subject=subject)
    db.session.commit()
    return results


def run_bench(contributors: int) -> dict:
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    name = f"flama_p9_profile_probe_{os.getpid()}_{secrets.token_hex(4)}"
    if settings["host"] not in {"localhost", "127.0.0.1", "::1"} or not PROBE_NAME_PATTERN.fullmatch(name):
        raise ValueError("P9 profile bench requires a generated local MySQL database.")
    admin = pymysql.connect(**settings)
    created = False
    app = None
    report: dict = {"schema_version": "p9-profile-migration-bench-mysql.v1", "configured_database_modified": False}
    try:
        with admin.cursor() as cursor:
            cursor.execute(f"CREATE DATABASE `{name}` CHARACTER SET utf8mb4 "
                           f"COLLATE {_source_database_collation(admin)}")
            created = True
            cursor.execute("SELECT VERSION()")
            report["mysql_version"] = cursor.fetchone()[0]
        app = _probe_app(_database_uri(settings, name))
        with app.app_context():
            db.metadata.create_all(bind=db.engine)
            report["reconstruct_head_46_seconds"] = _run(migration.downgrade)
            head_46 = (
                _raw_not_null()
                and not sa.inspect(db.engine).has_table(migration.PROFILE_TABLE)
                and migration.EVIDENCE_COLUMN not in {c["name"] for c in sa.inspect(db.engine).get_columns(migration.CONTRIBUTORS)}
            )
            report["head_46_reconstructed"] = head_46
            from models.user import User

            # ORM bulk insert applies the model's Python-side defaults.
            db.session.execute(sa.insert(User), [
                {"id": index, "username": f"p9-{index}", "email": f"p9-{index}@example.test"}
                for index in range(1, LEARNERS + 1)
            ])
            db.session.commit()
            seed_connection = pymysql.connect(**{**settings, "database": name})
            started = time.perf_counter()
            seeded = _seed(seed_connection, contributors)
            seed_connection.close()
            report["seed"] = {"contributors": seeded, "seconds": round(time.perf_counter() - started, 1)}
            before = tuple(_exec(FINGERPRINT, seeded=seeded).one())
            db.session.remove()

            writer = OldReleaseWriter(settings, name, seeded)
            writer.start()
            time.sleep(0.5)
            report["upgrade_seconds"] = _run(migration.upgrade)
            time.sleep(0.5)
            report["old_release_writer"] = writer.finish()
            report["second_upgrade_seconds"] = _run(migration.upgrade)
            db.session.remove()
            after = tuple(_exec(FINGERPRINT, seeded=seeded).one())
            report["seeded_evidence_unchanged"] = before == after
            report["rows"] = {
                "contributors": int(_exec("SELECT COUNT(*) FROM study_progress_contributors").scalar_one()),
                "expected": seeded + report["old_release_writer"]["inserted_contributors"],
                "not_legacy_projection": int(_exec(
                    "SELECT COUNT(*) FROM study_progress_contributors WHERE evidence_kind <> 'LEGACY_PROJECTION'"
                ).scalar_one()),
                "profile": list(_exec("SELECT profile_code, epoch FROM study_authority_storage_profile").one()),
            }
            report["constraints"] = _constraint_checks()
            report["downgrade_seconds"] = _run(migration.downgrade)
            report["downgrade_restores_not_null"] = _raw_not_null()
            report["reupgrade_seconds"] = _run(migration.upgrade)
            db.session.remove()
            report["evidence_unchanged_after_round_trip"] = tuple(_exec(FINGERPRINT, seeded=seeded).one()) == before

            constraints = report["constraints"]
            problems = []
            if not head_46:
                problems.append("head 46 was not reconstructed")
            if not report["seeded_evidence_unchanged"] or not report["evidence_unchanged_after_round_trip"]:
                problems.append("seeded evidence changed")
            if report["rows"]["contributors"] != report["rows"]["expected"] or report["rows"]["not_legacy_projection"]:
                problems.append("contributor rows lost or reclassified")
            if report["rows"]["profile"] != ["PROJECTION_V1", 1]:
                problems.append("profile row not seeded as PROJECTION_V1")
            if report["old_release_writer"]["error_count"]:
                problems.append("old release writes failed during upgrade")
            if not (
                constraints["canonical_accepted"] and constraints["downgrade_refused_with_canonical"]
                and all(constraints[key] for key in (
                    "legacy_without_raw_rejected", "duplicate_generation_card_rejected",
                    "unknown_kind_rejected", "canonical_with_raw_rejected",
                ))
            ):
                problems.append("constraint or downgrade guard missing")
            if not report["downgrade_restores_not_null"]:
                problems.append("downgrade did not restore NOT NULL")
            report["problems"] = problems
            report["status"] = "PASS" if not problems else "FAIL"
        return report
    finally:
        if app is not None:
            with app.app_context():
                db.session.remove()
                db.engine.dispose()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{name}`")
            report["probe_database_dropped"] = True
        admin.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--contributors", type=int, default=40671)
    args = parser.parse_args()
    result = run_bench(args.contributors)
    print(json.dumps(result, indent=2, default=str))
    raise SystemExit(0 if result.get("status") == "PASS" else 1)
