"""Check complete Study sibling vectors and lock scope on disposable MySQL.

Uses the real repository helpers, captures their executed SQL for EXPLAIN,
and checks a second connection against both the original and batched helper.
Includes a high-fraction 501-Note fixture crossing the 500-key chunk boundary.
Only a generated loopback database is written or dropped. The configured
schema is used only to read its default collation from information_schema.

    python scripts/probe_study_session_scaling_mysql.py --output output/study_scaling_mysql_probe_20261004.json

This bounded correctness probe does not prove deadlock freedom under load or
the engine's internal lock acquisition order from SQL ORDER BY.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4

from dotenv import load_dotenv
import pymysql
from sqlalchemy import event, select, text
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from app import create_app
from app.repositories.study_authority_repository import (
    lock_study_authority_route,
    lock_study_authority_siblings,
    lock_study_authority_siblings_many,
)
from app.services.study_session_authority_pin_service import lock_study_session_authority_subjects
from models import db
from models.card import Card
from models.note import Note
from models.study_application import StudyApplication
from models.study_session import StudySession
from models.study_session_card import StudySessionCard
from models.user import User
from scripts.mysql_probe_db import (
    _connection_settings, _database_uri, _source_database_collation, SCHEMA_IDENTIFIER,
)
from tests.test_study_note_batch import StudyNoteBatchTests
from tests.test_study_session_install_usage import StudySessionInstallUsageTests

PROBE_NAME_PATTERN = re.compile(r"^flama_study_scaling_probe_[0-9]+_[a-f0-9]{8}$")


def _probe_app(uri):
    from sqlalchemy.engine import make_url
    url = make_url(uri)
    if (url.get_backend_name() != "mysql" or url.host not in {"localhost", "127.0.0.1", "::1"}
            or not PROBE_NAME_PATTERN.fullmatch(url.database or "")):
        raise RuntimeError("Refusing a non-local/non-disposable Study probe database.")
    return create_app({
        "TESTING": True, "SQLALCHEMY_DATABASE_URI": uri,
        "WTF_CSRF_ENABLED": False, "STARTUP_RUN_MAINTENANCE": False,
        "STARTUP_RUN_DB_CREATE_ALL": False, "STARTUP_CHECK_DB_CONNECTIVITY": False,
        "STUDY_WIRE_V4_ENABLED": True, "STUDY_ASYNC_BATCH_ENABLED": False,
        "REDIS_URL": "", "STUDY_QUEUE_NAMESPACE": "",
    })


def _assert_probe_database(database_name):
    if not PROBE_NAME_PATTERN.fullmatch(database_name) or db.engine.url.database != database_name:
        raise RuntimeError("Study fixture is not bound to its generated database.")


def _vector(value):
    return (value.learner_user_id, value.subject_id, value.subject_generation,
            value.live_note_id, tuple(card.id for card in value.cards))


def _context(fixture, snapshot, database_name):
    _assert_probe_database(database_name)
    route = lock_study_authority_route(db.session, learner_user_id=fixture.user_id, allow_note_authority=True)
    lease = db.session.get(StudySession, snapshot["session_id"])
    memberships = db.session.execute(select(StudySessionCard).where(
        StudySessionCard.session_id == lease.id,
    ).order_by(StudySessionCard.ordinal).with_for_update()).scalars().all()
    card_ids = [row.card_id for row in memberships]
    note_ids = sorted(set(db.session.execute(select(Card.note_id).where(Card.id.in_(card_ids))).scalars()))
    subjects = lock_study_session_authority_subjects(
        db.session, route=route, logical_note_keys=note_ids,
        now_utc=lease.opened_at, create_token_if_missing=False,
    )
    return route, subjects.locked_by_logical_note_key, memberships


def _captured_selects(call):
    statements = []
    def before(_conn, _cursor, statement, parameters, _context, _many):
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append((statement, parameters))
    event.listen(db.engine, "before_cursor_execute", before)
    try:
        value = call()
    finally:
        event.remove(db.engine, "before_cursor_execute", before)
    return value, statements


def _is_note_lock_read(statement):
    return re.match(r"SELECT\s+(?:STRAIGHT_JOIN\s+)?notes\.id,\s+notes\.note_type_id\b",
                    statement.lstrip()) is not None


def _explain_actual(statements):
    """Explain captured production-helper SQL; never emit parameters or raw SQL."""
    plans = []
    for statement, parameters in statements:
        rows = db.session.connection().exec_driver_sql("EXPLAIN " + statement, parameters).mappings()
        plans.append([
            {key: row[key] for key in ("table", "type", "key", "rows", "Extra")}
            for row in rows if row["table"] is not None
        ])
    return plans


def _blocked(writer, statement, parameters):
    try:
        with writer.cursor() as cursor:
            cursor.execute(statement, parameters)
        return False
    except pymysql.err.OperationalError as exc:
        if exc.args[0] != 1205:
            raise
        return True
    finally:
        writer.rollback()


def _writer(settings, database_name):
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Unsafe disposable writer database.")
    writer = pymysql.connect(**{**settings, "database": database_name, "autocommit": False})
    with writer.cursor() as cursor:
        cursor.execute("SET SESSION innodb_lock_wait_timeout=1")
    return writer


def _run_probe(app, settings, database_name):
    result = {"checks": {}}
    fixture = StudyNoteBatchTests()
    fixture.app = app
    fixture._seed(note_count=10)
    with app.app_context():
        _assert_probe_database(database_name)
        source = db.session.get(Card, fixture.snapshot["cards"][0]["card_id"])
        outside_note = Note(user_id=fixture.user_id, note_type_id=source.note.note_type_id,
                            deck_id=fixture.deck_id, field_values={"Word": "outside-lease"})
        db.session.add(outside_note)
        db.session.flush()
        outside_card = Card.query.filter_by(note_id=outside_note.id, application_id=source.application_id).one()
        db.session.commit()
        outside_note_id = outside_note.id
        db.session.rollback()

        route, subjects, memberships = _context(fixture, fixture.snapshot, database_name)
        old, old_sql = _captured_selects(lambda: {
            key: lock_study_authority_siblings(db.session, route=route, locked=value)
            for key, value in subjects.items()
        })
        many, new_sql = _captured_selects(lambda: lock_study_authority_siblings_many(
            db.session, route=route, locked_by_logical_note_key=subjects,
        ))
        result["owned_fixture"] = {
            "notes": 10, "templates": 2, "selected_cards": len(memberships),
            "complete_cards": sum(len(row.cards) for row in many.values()),
            "old_sibling_selects": len(old_sql), "new_sibling_selects": len(new_sql),
        }
        result["checks"]["owned_complete_vector_parity"] = {
            key: _vector(value) for key, value in old.items()
        } == {key: _vector(value) for key, value in many.items()}
        note_lock_sql = [(sql, params) for sql, params in new_sql
                         if _is_note_lock_read(sql)]
        result["checks"]["note_rows_shared_locked"] = bool(note_lock_sql) and all(
            "LOCK IN SHARE MODE" in sql.upper() or "FOR SHARE" in sql.upper()
            for sql, _params in note_lock_sql)
        result["small_fixture_plans"] = _explain_actual(new_sql)
        db.session.rollback()

        source = db.session.get(Card, fixture.snapshot["cards"][0]["card_id"])
        note_id = source.note_id
        db.session.rollback()
        route, subjects, memberships = _context(fixture, fixture.snapshot, database_name)
        vectors = lock_study_authority_siblings_many(db.session, route=route, locked_by_logical_note_key=subjects)
        subject_id = next(iter(subjects.values())).subject.id
        probes = {
            "note_update": ("UPDATE notes SET updated_at=updated_at WHERE id=%s", (note_id,)),
            "subject_update": ("UPDATE study_progress_subjects SET authority_revision=authority_revision WHERE id=%s", (subject_id,)),
        }
        outside = {
            "outside_note_update": ("UPDATE notes SET updated_at=updated_at WHERE id=%s", (outside_note_id,)),
        }
        writer = _writer(settings, database_name)
        try:
            batched = {name: _blocked(writer, *query) for name, query in {**probes, **outside}.items()}
            result["batched_helper_blocked_writes"] = batched
            # An overlapping canonical batch takes the same learner fence and
            # then tries the real Subject helper, rather than just raw SQL.
            with Session(db.engine) as secondary:
                secondary.execute(text("SET SESSION innodb_lock_wait_timeout=1"))
                other_route = lock_study_authority_route(secondary, learner_user_id=fixture.user_id, allow_note_authority=True)
                try:
                    lock_study_session_authority_subjects(
                        secondary, route=other_route, logical_note_keys=[note_id],
                        now_utc=db.session.get(StudySession, fixture.snapshot["session_id"]).opened_at,
                        create_token_if_missing=False,
                    )
                    result["checks"]["overlapping_batch_subject_lock_blocked"] = False
                except OperationalError as exc:
                    if exc.orig.args[0] != 1205:
                        raise
                    result["checks"]["overlapping_batch_subject_lock_blocked"] = True
                finally:
                    secondary.rollback()
            db.session.rollback()
            result["checks"]["writes_succeed_after_release"] = all(
                not _blocked(writer, *query) for query in probes.values()
            )
            route, subjects, _memberships = _context(fixture, fixture.snapshot, database_name)
            for locked in subjects.values():
                lock_study_authority_siblings(db.session, route=route, locked=locked)
            baseline = {name: _blocked(writer, *query) for name, query in {**probes, **outside}.items()}
            result["single_helper_blocked_writes"] = baseline
            result["checks"]["required_lock_protection_matches_single_helper"] = all(
                baseline[name] and batched[name] for name in probes
            )
            result["checks"]["outside_update_breadth_not_increased"] = all(
                not batched[name] or baseline[name] for name in outside
            )
            result["checks"]["outside_updates_unblocked"] = all(not batched[name] for name in outside)
            db.session.rollback()
        finally:
            writer.close()

    overlay = StudySessionInstallUsageTests()
    overlay.app, overlay.client, overlay.user_id = app, fixture.client, fixture.user_id
    overlay._install_overlay(notes=4)
    snapshot = overlay._open()
    with app.app_context():
        route, subjects, memberships = _context(overlay, snapshot, database_name)
        single = {key: lock_study_authority_siblings(db.session, route=route, locked=value) for key, value in subjects.items()}
        many = lock_study_authority_siblings_many(db.session, route=route, locked_by_logical_note_key=subjects)
        result["overlay_fixture"] = {
            "notes": 4, "selected_cards": len(memberships),
            "publisher_owned": all(db.session.get(Note, key).user_id != fixture.user_id for key in many),
        }
        result["checks"]["publisher_overlay_vector_parity"] = {
            key: _vector(value) for key, value in single.items()
        } == {key: _vector(value) for key, value in many.items()}
        # Keep these unrelated rows while creating the 501-Note fixture.
        user = db.session.get(User, fixture.user_id)
        user.username, user.email = "probe-previous", "probe-previous@example.invalid"
        db.session.commit()
    fixture._seed(note_count=501)
    with app.app_context():
        route, subjects, memberships = _context(fixture, fixture.snapshot, database_name)
        many, captured = _captured_selects(lambda: lock_study_authority_siblings_many(
            db.session, route=route, locked_by_logical_note_key=subjects,
        ))
        plans = _explain_actual(captured)
        result["chunk_fixture"] = {
            "notes": 501, "selected_cards": len(memberships),
            "complete_cards": sum(len(row.cards) for row in many.values()),
            "sibling_selects": len(captured), "plans": plans,
        }
        result["checks"]["chunk_boundary_complete_vector"] = len(many) == 501 and all(len(row.cards) == 2 for row in many.values())
        result["checks"]["chunk_boundary_six_selects"] = len(captured) == 6
        locked_note_plans = _explain_actual([
            (sql, params) for sql, params in captured
            if _is_note_lock_read(sql)])
        result["checks"]["note_point_plans_at_high_fraction"] = bool(locked_note_plans) and all(
            row["type"] in {"eq_ref", "const"} and row["key"] == "PRIMARY"
            for plan in locked_note_plans for row in plan if row["table"] == "notes"
        )
        from sqlalchemy import inspect
        result["checks"]["physical_card_table_absent"] = "cards" not in inspect(db.engine).get_table_names()
        writer = _writer(settings, database_name)
        try:
            result["checks"]["high_fraction_outside_updates_unblocked"] = all(
                not _blocked(writer, *query) for query in outside.values()
            )
        finally:
            writer.close()
            db.session.rollback()
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    load_dotenv(ROOT_DIR / ".env")
    settings = _connection_settings()
    if settings["host"] not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("Disposable Study probes require localhost MySQL.")
    database_name = f"flama_study_scaling_probe_{os.getpid()}_{uuid4().hex[:8]}"
    if not PROBE_NAME_PATTERN.fullmatch(database_name):
        raise RuntimeError("Unsafe disposable schema name.")
    admin = pymysql.connect(**settings)
    created, app = False, None
    result = {"environment": "Disposable local MySQL; generated schema only"}
    try:
        collation = _source_database_collation(admin)
        if not SCHEMA_IDENTIFIER.fullmatch(collation):
            raise RuntimeError("Unsafe schema collation.")
        with admin.cursor() as cursor:
            cursor.execute("SELECT VERSION(), @@transaction_isolation")
            result["mysql_version"], result["transaction_isolation"] = cursor.fetchone()
            if result["transaction_isolation"] != "REPEATABLE-READ":
                raise RuntimeError("This locking probe requires the default REPEATABLE-READ isolation.")
            cursor.execute(f"CREATE DATABASE `{database_name}` CHARACTER SET utf8mb4 COLLATE {collation}")
            created = True
        app = _probe_app(_database_uri(settings, database_name))
        result.update(_run_probe(app, settings, database_name))
    finally:
        if app is not None:
            with app.app_context():
                _assert_probe_database(database_name)
                db.session.remove()
                db.engine.dispose()
        if created:
            if not PROBE_NAME_PATTERN.fullmatch(database_name):
                raise RuntimeError("Refusing unsafe probe cleanup.")
            with admin.cursor() as cursor:
                cursor.execute(f"DROP DATABASE `{database_name}`")
            result["disposable_schema_removed"] = True
        admin.close()
    if args.output is not None:
        args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, indent=2))
    if not all(result["checks"].values()):
        raise RuntimeError("Study sibling scaling probe failed one or more checks.")


if __name__ == "__main__":
    main()
